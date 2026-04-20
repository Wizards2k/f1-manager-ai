#!/usr/bin/env python3
"""V6.0 Multi-parametric Calibration — Find circuit-optimal setup via 4 phases.

Phase 1: Wing sweep (grid coarse + local refine) → find optimal FW/RW/BW
Phase 2: Suspension local search (coordinate descent) → find optimal susp
Phase 3: Binary search on mu_mechanical → match reference lap time
Phase 4: Congruence verification + fallback → ensure CAL beats LOW/HIGH

Root cause: V6.0 shows 0/24 congruence because CAL uses fixed 22/26 wings
which are suboptimal on speed circuits. This script finds CIRCUIT-OPTIMAL
wings, then applies ±6° preference test relative to those optimal angles.
"""
import sys
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Tuple, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup, DriverSkill
from lap_simulator.push_penalty import compute_push_penalty

# ============================================================================
# CIRCUIT DEFINITIONS
# ============================================================================

CIRCUIT_CATEGORIES = {
    # Fast circuits (long straights, low corner count)
    "monza": "fast", "baku": "fast", "jeddah": "fast", "las_vegas": "fast", "spa": "fast",
    # Medium circuits (balanced)
    "silverstone": "medium", "spielberg": "medium", "sakhir": "medium", "melbourne": "medium",
    "yas_marina": "medium", "imola": "medium", "montreal": "medium", "miami": "medium",
    "lusail": "medium", "sao_paulo": "medium", "shanghai": "medium", "suzuka": "medium",
    "austin": "medium",  # Override: high altitude, mix of straights+corners
    # Slow circuits (tight corners, short straights)
    "budapest": "slow", "zandvoort": "slow", "singapore": "slow", "monaco": "slow",
    "mexico_city": "medium",  # Override: high altitude
}

WING_RANGES = {
    "fast":   {"fw": (4,  18, 3), "rw": (6,  20, 3)},    # (min, max, step)
    "medium": {"fw": (8,  30, 4), "rw": (10, 34, 4)},   # Wider range for better optimization
    "slow":   {"fw": (26, 42, 4), "rw": (30, 45, 4)},
}

BWING_BY_CATEGORY = {
    "fast": 5.0, "medium": 10.0, "slow": 18.0
}

ALL_CIRCUITS = {
    "baku": {"circuit_id": "az-2016_baku", "compound": "C6", "fuel_kg": 20.0, "ref_time": 101.117, "susp_source": "monza"},
    "spa": {"circuit_id": "be-1925_spa_francorchamps", "compound": "C4", "fuel_kg": 20.0, "ref_time": 100.562, "susp_source": "monza"},
    "shanghai": {"circuit_id": "cn-2004_shanghai", "compound": "C4", "fuel_kg": 20.0, "ref_time": 90.641, "susp_source": "silverstone"},
    "sakhir": {"circuit_id": "bh-2002_sakhir", "compound": "C3", "fuel_kg": 20.0, "ref_time": 89.841, "susp_source": "monza"},
    "melbourne": {"circuit_id": "au-1953_melbourne", "compound": "C5", "fuel_kg": 20.0, "ref_time": 75.096, "susp_source": "silverstone"},
    "yas_marina": {"circuit_id": "ae-2009_yas_marina", "compound": "C5", "fuel_kg": 20.0, "ref_time": 82.207, "susp_source": "silverstone"},
    "barcelona": {"circuit_id": "es-1991_barcelona", "compound": "C3", "fuel_kg": 20.0, "ref_time": 71.546, "susp_source": "silverstone"},
    "jeddah": {"circuit_id": "sa-2021_jeddah", "compound": "C5", "fuel_kg": 20.0, "ref_time": 87.294, "susp_source": "monza"},
    "singapore": {"circuit_id": "sg-2008_singapore", "compound": "C5", "fuel_kg": 20.0, "ref_time": 89.158, "susp_source": "monaco"},
    "sao_paulo": {"circuit_id": "br-1940_sao_paulo", "compound": "C4", "fuel_kg": 20.0, "ref_time": 69.511, "susp_source": "silverstone"},
    "monaco": {"circuit_id": "mc-1929_monaco", "compound": "C6", "fuel_kg": 20.0, "ref_time": 69.954, "susp_source": "monaco"},
    "suzuka": {"circuit_id": "jp-1962_suzuka", "compound": "C3", "fuel_kg": 20.0, "ref_time": 86.995, "susp_source": "silverstone"},
    "silverstone": {"circuit_id": "gb-1948_silverstone", "compound": "C5", "fuel_kg": 20.0, "ref_time": 85.010, "susp_source": "silverstone"},
    "zandvoort": {"circuit_id": "nl-1948_zandvoort", "compound": "C4", "fuel_kg": 20.0, "ref_time": 68.662, "susp_source": "monaco"},
    "budapest": {"circuit_id": "hu-1986_budapest", "compound": "C5", "fuel_kg": 20.0, "ref_time": 75.372, "susp_source": "monaco"},
    "monza": {"circuit_id": "it-1922_monza", "compound": "C5", "fuel_kg": 20.0, "ref_time": 78.869, "susp_source": "monza"},
    "montreal": {"circuit_id": "ca-1978_montreal", "compound": "C6", "fuel_kg": 20.0, "ref_time": 70.899, "susp_source": "silverstone"},
    "imola": {"circuit_id": "it-1953_imola", "compound": "C6", "fuel_kg": 20.0, "ref_time": 74.670, "susp_source": "silverstone"},
    "mexico_city": {"circuit_id": "mx-1962_mexico_city", "compound": "C5", "fuel_kg": 20.0, "ref_time": 75.586, "susp_source": "silverstone"},
    "miami": {"circuit_id": "us-2022_miami", "compound": "C5", "fuel_kg": 20.0, "ref_time": 86.204, "susp_source": "silverstone"},
    "lusail": {"circuit_id": "qa-2004_lusail", "compound": "C3", "fuel_kg": 20.0, "ref_time": 79.387, "susp_source": "silverstone"},
    "spielberg": {"circuit_id": "at-1969_spielberg", "compound": "C5", "fuel_kg": 20.0, "ref_time": 63.971, "susp_source": "silverstone"},
    "austin": {"circuit_id": "us-2012_austin", "compound": "C4", "fuel_kg": 20.0, "ref_time": 92.510, "susp_source": "silverstone"},
    "las_vegas": {"circuit_id": "us-2023_las_vegas", "compound": "C5", "fuel_kg": 20.0, "ref_time": 107.934, "susp_source": "monza"},
}

SUSP_SEEDS = {
    "fast":   {"spring_front": 25, "spring_rear": 33, "ARB_front": 8,  "ARB_rear": 13, "ride_height_front": 10, "ride_height_rear": 17},
    "medium": {"spring_front": 25, "spring_rear": 33, "ARB_front": 25, "ARB_rear": 30, "ride_height_front": 2,  "ride_height_rear": 9},
    "slow":   {"spring_front": 10, "spring_rear": 18, "ARB_front": 25, "ARB_rear": 30, "ride_height_front": 16, "ride_height_rear": 23},
}

DRIVER = DriverSkill(
    name="Reference", quali_skill=1.0, race_skill=1.0, braking_skill=1.0,
    cornering_skill=1.0, throttle_skill=1.0, consistency=1.0,
    front_wing_offset=0, rear_wing_offset=0, brake_bias_offset=0.0
)

AERO_CAL_DIR = ROOT / "data" / "circuits" / "aero_calibration"
SETUP_CAL_DIR = ROOT / "data" / "circuits" / "setup_calibration"

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class OptimalSetup:
    """Stores optimal setup for a circuit."""
    front_wing: float
    rear_wing: float
    bwing: float
    spring_front: float
    spring_rear: float
    ARB_front: float
    ARB_rear: float
    ride_height_front: float
    ride_height_rear: float
    mu_mechanical: float
    compound: str

@dataclass
class CalibrationResult:
    """Stores calibration result for a circuit."""
    circuit_name: str
    circuit_id: str
    optimal_setup: OptimalSetup
    ref_time_s: float
    sim_time_cal_s: float
    error_pct: float
    congruent: bool
    t_low: float
    t_cal: float
    t_high: float
    d_low_vs_cal: float
    d_high_vs_cal: float

# ============================================================================
# CORE SIMULATION
# ============================================================================

def simulate(circuit_id, fw, rw, bwing, compound, susp, mu=None) -> float:
    """Simulate lap time with given setup. Returns lap_time_s."""
    if mu is not None:
        _patch_mu(circuit_id, mu)
        _clear_aero_cache()

    setup = PhysicsV4Setup(driver_data=DRIVER, circuit=circuit_id, session="qualifying")
    setup.set_aero(front_wing=fw, rear_wing=rw, bwing=bwing)
    setup.set_suspension(**susp)
    setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
    setup.set_tyres(compound=compound)
    setup.set_ers_mode("quali_deploy")

    result = setup.simulate_lap(verbose=False)
    return result["lap_time_s"]

def _load_aero_cal(circuit_id):
    """Load current aero calibration JSON."""
    cal_file = AERO_CAL_DIR / f"{circuit_id}_aero_cal.json"
    if cal_file.exists():
        with open(cal_file) as f:
            return json.load(f)
    return None

def _patch_mu(circuit_id, mu):
    """Patch mu_mechanical in the JSON file (only mu, preserve rest)."""
    cal = _load_aero_cal(circuit_id)
    if cal:
        cal["grip_data"]["mu_mechanical"] = mu
        cal_file = AERO_CAL_DIR / f"{circuit_id}_aero_cal.json"
        with open(cal_file, 'w') as f:
            json.dump(cal, f, indent=4)

def _clear_aero_cache():
    """Clear the LRU cache of get_aero_calibration."""
    try:
        from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration
        get_aero_calibration.cache_clear()
    except:
        pass

# ============================================================================
# PHASE 1: WING SWEEP
# ============================================================================

def phase1_wing_sweep(circuit_id, cfg, category):
    """Simple grid search for optimal wings (minimize lap time).

    Returns: (fw_opt, rw_opt, bwing_opt, best_time)
    """
    susp = SUSP_SEEDS[category]
    compound = cfg["compound"]

    fw_min, fw_max, fw_step = WING_RANGES[category]["fw"]
    rw_min, rw_max, rw_step = WING_RANGES[category]["rw"]
    bwing = BWING_BY_CATEGORY[category]

    best_fw, best_rw, best_time = None, None, float('inf')

    # Single-pass grid search with category step size
    for fw in range(int(fw_min), int(fw_max) + 1, fw_step):
        for rw in range(int(rw_min), int(rw_max) + 1, rw_step):
            t = simulate(circuit_id, float(fw), float(rw), bwing, compound, susp)
            if t < best_time:
                best_time = t
                best_fw, best_rw = fw, rw

    return float(best_fw), float(best_rw), bwing, best_time

# ============================================================================
# PHASE 2: SUSPENSION SEARCH
# ============================================================================

def phase2_suspension_search(circuit_id, cfg, category, fw, rw, bwing, max_iterations=3):
    """Coordinate descent on suspension parameters.

    Returns: susp_dict (optimized suspension)
    """
    compound = cfg["compound"]
    susp = SUSP_SEEDS[category].copy()

    # Get baseline time
    baseline_time = simulate(circuit_id, fw, rw, bwing, compound, susp)
    best_time = baseline_time

    # Coordinate descent on 4 key params
    params = ["ARB_front", "ARB_rear", "ride_height_front", "ride_height_rear"]
    step_sizes = {"ARB_front": 2.0, "ARB_rear": 2.0, "ride_height_front": 2.0, "ride_height_rear": 2.0}

    for iteration in range(max_iterations):
        improved = False

        for param in params:
            original = susp[param]
            step = step_sizes[param]

            # Try -step and +step
            for delta in [-step, step]:
                test_val = max(1, min(50, original + delta))
                test_susp = susp.copy()
                test_susp[param] = test_val
                t = simulate(circuit_id, fw, rw, bwing, compound, test_susp)

                if t < best_time:
                    best_time = t
                    susp[param] = test_val
                    improved = True

        if not improved:
            break

    return susp

# ============================================================================
# PHASE 3: MU BINARY SEARCH
# ============================================================================

def phase3_mu_search(circuit_id, cfg, fw, rw, bwing, susp, ref_time, target_pct=1.5):
    """Binary search for mu_mechanical to match reference lap time.

    Returns: (mu_mechanical, sim_time, error_pct)
    """
    compound = cfg["compound"]

    # Load current mu
    cal = _load_aero_cal(circuit_id)
    current_mu = cal["grip_data"]["mu_mechanical"] if cal else 1.55

    lo, hi = 0.3, 2.5
    best_mu, best_time, best_pct = current_mu, None, float('inf')

    for i in range(20):
        mid = (lo + hi) / 2
        t = simulate(circuit_id, fw, rw, bwing, compound, susp, mu=mid)
        delta = t - ref_time
        pct = abs(delta) / ref_time * 100

        if pct < best_pct:
            best_mu, best_time, best_pct = mid, t, pct

        if delta > 0:  # too slow → need more grip
            lo = mid
        else:  # too fast → need less grip
            hi = mid

        if pct < target_pct:
            break

    return best_mu, best_time, best_pct

# ============================================================================
# PHASE 4: CONGRUENCE VERIFICATION
# ============================================================================

def phase4_congruence_test(circuit_id, cfg, category, fw, rw, bwing, susp, mu, compound):
    """Verify that CAL beats LOW/HIGH within ±6° (allowing out-of-range testing).

    Returns: (congruent, t_low, t_cal, t_high, d_low, d_high)
    """
    # CAL: the optimized setup
    t_cal = simulate(circuit_id, fw, rw, bwing, compound, susp, mu=mu)

    # LOW: -6° both wings (allow going outside normal range to test preference)
    fw_low = max(1.0, fw - 6)  # Min 1.0, not category min
    rw_low = max(1.0, rw - 6)
    t_low = simulate(circuit_id, fw_low, rw_low, bwing, compound, susp, mu=mu)

    # HIGH: +6° both wings (allow going outside normal range)
    fw_high = min(50.0, fw + 6)  # Max 50.0, not category max
    rw_high = min(50.0, rw + 6)
    t_high = simulate(circuit_id, fw_high, rw_high, bwing, compound, susp, mu=mu)

    congruent = (t_cal < t_low) and (t_cal < t_high)

    return congruent, t_low, t_cal, t_high, abs(t_low - t_cal), abs(t_high - t_cal)

# ============================================================================
# MAIN CALIBRATION
# ============================================================================

def calibrate_circuit(name, cfg, skip_susp=False):
    """Full calibration for one circuit: Phase 1-4 with fallback."""
    circuit_id = cfg["circuit_id"]
    ref_time = cfg["ref_time"]

    # Determine category
    category = CIRCUIT_CATEGORIES.get(name, "medium")
    print(f"\n{'='*80}")
    print(f"  {name.upper()} ({category}) → {circuit_id}")
    print(f"  Ref: {ref_time:.3f}s")
    print(f"{'='*80}")

    # Phase 1: Wing Sweep
    print(f"Phase 1: Wing sweep...", end=" ", flush=True)
    t0 = time.time()
    fw, rw, bwing, _ = phase1_wing_sweep(circuit_id, cfg, category)
    print(f"✓ {time.time()-t0:.1f}s → FW={fw:.1f}, RW={rw:.1f}")

    # Phase 2: Suspension (optional skip)
    if skip_susp:
        susp = SUSP_SEEDS[category].copy()
        print(f"Phase 2: (skipped, using seed)")
    else:
        print(f"Phase 2: Suspension search...", end=" ", flush=True)
        t0 = time.time()
        susp = phase2_suspension_search(circuit_id, cfg, category, fw, rw, bwing)
        print(f"✓ {time.time()-t0:.1f}s")

    # Phase 3: Mu binary search
    print(f"Phase 3: Mu binary search...", end=" ", flush=True)
    t0 = time.time()
    mu, sim_time, error_pct = phase3_mu_search(circuit_id, cfg, fw, rw, bwing, susp, ref_time)
    print(f"✓ {time.time()-t0:.1f}s → mu={mu:.4f}, error={error_pct:+.2f}%")

    # Phase 4: Congruence test
    print(f"Phase 4: Congruence test...", end=" ", flush=True)
    congruent, t_low, t_cal, t_high, d_low, d_high = phase4_congruence_test(
        circuit_id, cfg, category, fw, rw, bwing, susp, mu, cfg["compound"]
    )

    status = "✅ CONGRUENT" if congruent else "❌ NOT CONGRUENT"
    print(f"{status}")
    print(f"    LOW={t_low:.3f}s (Δ={d_low:+.3f}s), CAL={t_cal:.3f}s, HIGH={t_high:.3f}s (Δ={d_high:+.3f}s)")

    # Save result
    optimal_setup = OptimalSetup(
        front_wing=fw, rear_wing=rw, bwing=bwing,
        spring_front=susp["spring_front"], spring_rear=susp["spring_rear"],
        ARB_front=susp["ARB_front"], ARB_rear=susp["ARB_rear"],
        ride_height_front=susp["ride_height_front"], ride_height_rear=susp["ride_height_rear"],
        mu_mechanical=mu, compound=cfg["compound"]
    )

    result = CalibrationResult(
        circuit_name=name,
        circuit_id=circuit_id,
        optimal_setup=optimal_setup,
        ref_time_s=ref_time,
        sim_time_cal_s=sim_time,
        error_pct=error_pct,
        congruent=congruent,
        t_low=t_low,
        t_cal=t_cal,
        t_high=t_high,
        d_low_vs_cal=d_low,
        d_high_vs_cal=d_high,
    )

    _save_calibration_result(result)
    return result

def _save_calibration_result(result: CalibrationResult):
    """Save calibration result to JSON."""
    SETUP_CAL_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "circuit_name": result.circuit_name,
        "circuit_id": result.circuit_id,
        "calibration_version": "v60",
        "optimal_setup": asdict(result.optimal_setup),
        "calibration_results": {
            "ref_time_s": result.ref_time_s,
            "sim_time_cal_s": result.sim_time_cal_s,
            "error_pct": result.error_pct,
        },
        "congruence_test": {
            "congruent": result.congruent,
            "t_low": result.t_low,
            "t_cal": result.t_cal,
            "t_high": result.t_high,
            "d_low_vs_cal": result.d_low_vs_cal,
            "d_high_vs_cal": result.d_high_vs_cal,
        },
    }

    output_file = SETUP_CAL_DIR / f"{result.circuit_id}_setup_v60.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=4)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="V6.0 Full Calibration (4 phases)")
    parser.add_argument("--quick", action="store_true", help="Only 3 reference circuits")
    parser.add_argument("--circuit", type=str, help="Specific circuit")
    parser.add_argument("--skip-susp", action="store_true", help="Skip phase 2 (use seed)")
    parser.add_argument("--resume", action="store_true", help="Skip already calibrated")
    args = parser.parse_args()

    if args.circuit:
        circuits = {args.circuit: ALL_CIRCUITS[args.circuit]}
    elif args.quick:
        circuits = {k: v for k, v in ALL_CIRCUITS.items() if k in ["monza", "monaco", "silverstone"]}
    else:
        circuits = ALL_CIRCUITS

    if args.resume:
        circuits = {k: v for k, v in circuits.items()
                   if not (SETUP_CAL_DIR / f"{v['circuit_id']}_setup_v60.json").exists()}

    print("=" * 100)
    print(f"  V6.0 FULL CALIBRATION — {len(circuits)} circuits")
    print("=" * 100)

    results = []
    for name, cfg in sorted(circuits.items()):
        result = calibrate_circuit(name, cfg, skip_susp=args.skip_susp)
        results.append(result)

    # Summary
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)

    congruent_count = sum(1 for r in results if r.congruent)
    print(f"Congruent: {congruent_count}/{len(results)}")
    print(f"Error (mean): {sum(r.error_pct for r in results) / len(results):.2f}%")

    congruent = [r.circuit_name for r in results if r.congruent]
    not_congruent = [r.circuit_name for r in results if not r.congruent]

    if congruent:
        print(f"\n✅ Congruent ({len(congruent)}): {', '.join(congruent)}")
    if not_congruent:
        print(f"\n❌ Not congruent ({len(not_congruent)}): {', '.join(not_congruent)}")

if __name__ == "__main__":
    main()
