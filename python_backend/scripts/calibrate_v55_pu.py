#!/usr/bin/env python3
"""V5.5 PU Stateful Calibration — Find optimal mu_mechanical per circuit.

Strategy: Binary search on mu_mechanical in the aero calibration JSON files.
Each step: write new mu → clear LRU cache → simulate → check error.
"""
import sys
import json
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.integrator.waypoint_integrator import integrate_lap_hd
import lap_simulator.physics_engine.integrator.waypoint_integrator as _wi

# CRITICAL: waypoint_integrator.py uses relative imports, so the
# get_aero_calibration it uses is from 'calibration.aero_calibration',
# NOT from 'lap_simulator.physics_v4.calibration.aero_calibration'.
# These are TWO DIFFERENT module instances with separate LRU caches!
# We must clear the cache on the one actually used by the integrator.
try:
    from calibration.aero_calibration import get_aero_calibration as _get_aero_cal_internal
except ImportError:
    from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration as _get_aero_cal_internal

ALL_CIRCUITS = {
    "baku": {"circuit_id": "az-2016_baku", "front_wing": 12.0, "rear_wing": 14.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 101.117, "susp_source": "monza"},
    "spa": {"circuit_id": "be-1925_spa_francorchamps", "front_wing": 10.0, "rear_wing": 12.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 100.562, "susp_source": "monza"},
    "shanghai": {"circuit_id": "cn-2004_shanghai", "front_wing": 20.0, "rear_wing": 24.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 90.641, "susp_source": "silverstone"},
    "sakhir": {"circuit_id": "bh-2002_sakhir", "front_wing": 14.0, "rear_wing": 16.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 89.841, "susp_source": "monza"},
    "melbourne": {"circuit_id": "au-1953_melbourne", "front_wing": 18.0, "rear_wing": 22.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 75.096, "susp_source": "silverstone"},
    "yas_marina": {"circuit_id": "ae-2009_yas_marina", "front_wing": 18.0, "rear_wing": 22.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 82.207, "susp_source": "silverstone"},
    "barcelona": {"circuit_id": "es-1991_barcelona", "front_wing": 22.0, "rear_wing": 26.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 71.546, "susp_source": "silverstone"},
    "jeddah": {"circuit_id": "sa-2021_jeddah", "front_wing": 12.0, "rear_wing": 14.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 87.294, "susp_source": "monza"},
    "singapore": {"circuit_id": "sg-2008_singapore", "front_wing": 34.0, "rear_wing": 38.0, "compound": "C6", "fuel_kg": 20.0, "ref_time": 89.158, "susp_source": "monaco"},
    "sao_paulo": {"circuit_id": "br-1940_sao_paulo", "front_wing": 20.0, "rear_wing": 24.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 69.511, "susp_source": "silverstone"},
    "monaco": {"circuit_id": "mc-1929_monaco", "front_wing": 38.0, "rear_wing": 42.0, "compound": "C6", "fuel_kg": 20.0, "ref_time": 69.954, "susp_source": "monaco"},
    "suzuka": {"circuit_id": "jp-1962_suzuka", "front_wing": 24.0, "rear_wing": 28.0, "compound": "C3", "fuel_kg": 20.0, "ref_time": 86.995, "susp_source": "silverstone"},
    "silverstone": {"circuit_id": "gb-1948_silverstone", "front_wing": 22.0, "rear_wing": 26.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 85.010, "susp_source": "silverstone"},
    "zandvoort": {"circuit_id": "nl-1948_zandvoort", "front_wing": 28.0, "rear_wing": 32.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 68.662, "susp_source": "monaco"},
    "budapest": {"circuit_id": "hu-1986_budapest", "front_wing": 28.0, "rear_wing": 32.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 75.372, "susp_source": "monaco"},
    "monza": {"circuit_id": "it-1922_monza", "front_wing": 8.0, "rear_wing": 10.0, "compound": "C5", "fuel_kg": 20.0, "ref_time": 78.869, "susp_source": "monza"},
    "montreal": {"circuit_id": "ca-1978_montreal", "front_wing": 22.0, "rear_wing": 26.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 70.899, "susp_source": "silverstone"},
    "imola": {"circuit_id": "it-1953_imola", "front_wing": 18.0, "rear_wing": 22.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 74.670, "susp_source": "silverstone"},
    "mexico_city": {"circuit_id": "mx-1962_mexico_city", "front_wing": 22.0, "rear_wing": 26.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 75.586, "susp_source": "silverstone"},
    "miami": {"circuit_id": "us-2022_miami", "front_wing": 18.0, "rear_wing": 22.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 86.204, "susp_source": "silverstone"},
    "lusail": {"circuit_id": "qa-2004_lusail", "front_wing": 22.0, "rear_wing": 26.0, "compound": "C3", "fuel_kg": 20.0, "ref_time": 79.387, "susp_source": "silverstone"},
    "spielberg": {"circuit_id": "at-1969_spielberg", "front_wing": 18.0, "rear_wing": 22.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 63.971, "susp_source": "silverstone"},
    "austin": {"circuit_id": "us-2012_austin", "front_wing": 22.0, "rear_wing": 26.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 92.510, "susp_source": "silverstone"},
    "las_vegas": {"circuit_id": "us-2023_las_vegas", "front_wing": 10.0, "rear_wing": 12.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 107.934, "susp_source": "monza"},
}

SUSP_SETUPS = {
    "monza": {"spring_front": 25.0, "spring_rear": 33.0, "arb_front": 8.0, "arb_rear": 13.0, "ride_height_front": 10.0, "ride_height_rear": 17.0},
    "monaco": {"spring_front": 10.0, "spring_rear": 18.0, "arb_front": 25.0, "arb_rear": 30.0, "ride_height_front": 16.0, "ride_height_rear": 23.0},
    "silverstone": {"spring_front": 25.0, "spring_rear": 33.0, "arb_front": 25.0, "arb_rear": 30.0, "ride_height_front": 2.0, "ride_height_rear": 9.0},
}

AERO_CAL_DIR = ROOT / "data" / "circuits" / "aero_calibration"


def load_aero_cal(circuit_id):
    """Load aero calibration JSON."""
    cal_file = AERO_CAL_DIR / f"{circuit_id}_aero_cal.json"
    if cal_file.exists():
        with open(cal_file) as f:
            return json.load(f)
    return None


def save_aero_cal(circuit_id, data):
    """Save aero calibration JSON and clear LRU caches."""
    cal_file = AERO_CAL_DIR / f"{circuit_id}_aero_cal.json"
    with open(cal_file, 'w') as f:
        json.dump(data, f, indent=4)
    # Clear BOTH LRU caches (they're different module instances due to
    # relative vs absolute imports in waypoint_integrator.py)
    _get_aero_cal_internal.cache_clear()
    try:
        from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration
        get_aero_calibration.cache_clear()
    except ImportError:
        pass


def get_mu_mechanical(data):
    """Get mu_mechanical from aero cal data."""
    return data.get("grip_data", {}).get("mu_mechanical", None)


def set_mu_mechanical(data, mu_value):
    """Set mu_mechanical in aero cal data (returns new copy)."""
    new_data = copy.deepcopy(data)
    new_data["grip_data"]["mu_mechanical"] = round(mu_value, 4)
    if "notes" not in new_data["grip_data"]:
        new_data["grip_data"]["notes"] = {}
    new_data["grip_data"]["notes"]["v55_calibration"] = (
        f"V5.5: mu_mechanical={round(mu_value, 4)} for <0.5% error (PU stateful)"
    )
    return new_data


def simulate(name, cfg):
    """Simulate a single circuit."""
    susp = SUSP_SETUPS[cfg["susp_source"]]
    r = integrate_lap_hd(
        circuit_id=cfg["circuit_id"],
        aero_setup={"front_wing": cfg["front_wing"], "rear_wing": cfg["rear_wing"]},
        mass_kg=798 + cfg["fuel_kg"],
        tyre_compound=cfg["compound"],
        driver_skill=1.0,
        suspension_setup=susp,
        verbose=False,
    )
    return r["lap_time_s"]


def calibrate_circuit(name, cfg, target_pct=0.3):
    """Binary search for optimal mu_mechanical."""
    ref_time = cfg["ref_time"]
    circuit_id = cfg["circuit_id"]
    
    # Load current calibration
    cal_data = load_aero_cal(circuit_id)
    if cal_data is None:
        print(f"  {name}: No aero calibration file found, skipping")
        return None
    
    current_mu = get_mu_mechanical(cal_data)
    if current_mu is None:
        print(f"  {name}: No mu_mechanical in calibration, skipping")
        return None
    
    # Simulate with current mu
    sim_time = simulate(name, cfg)
    delta = sim_time - ref_time
    pct = abs(delta) / ref_time * 100
    print(f"  {name}: mu={current_mu:.4f} sim={sim_time:.3f}s d={delta:+.3f}s ({pct:.2f}%)")
    
    if pct <= target_pct:
        print(f"    -> Already within {target_pct}%, no adjustment needed")
        return current_mu
    
    # Binary search bounds
    if delta > 0:
        # Too slow → need more grip → increase mu
        mu_low = current_mu
        mu_high = current_mu * 1.20
    else:
        # Too fast → need less grip → decrease mu
        mu_low = current_mu * 0.80
        mu_high = current_mu
    
    best_mu = current_mu
    best_pct = pct
    best_delta = delta
    
    for iteration in range(20):
        mu_mid = (mu_low + mu_high) / 2
        
        # Write new mu, clear cache, simulate
        new_cal = set_mu_mechanical(cal_data, mu_mid)
        save_aero_cal(circuit_id, new_cal)
        
        sim_time = simulate(name, cfg)
        delta = sim_time - ref_time
        pct = abs(delta) / ref_time * 100
        
        if pct < best_pct:
            best_mu = mu_mid
            best_pct = pct
            best_delta = delta
            cal_data = new_cal  # Keep this as the new baseline
        
        if pct <= target_pct:
            break
        
        if delta > 0:
            mu_low = mu_mid
        else:
            mu_high = mu_mid
    
    # Ensure best mu is saved
    final_cal = set_mu_mechanical(load_aero_cal(circuit_id), best_mu)
    save_aero_cal(circuit_id, final_cal)
    
    print(f"    -> Calibrated: mu={best_mu:.4f} d={best_delta:+.3f}s ({best_pct:.2f}%)")
    return best_mu


def main():
    import argparse
    parser = argparse.ArgumentParser(description="V5.5 PU Stateful Calibration")
    parser.add_argument("--quick", action="store_true", help="Only calibrate 3 reference circuits")
    parser.add_argument("--circuit", type=str, default=None, help="Calibrate specific circuit")
    parser.add_argument("--target", type=float, default=0.3, help="Target error pct (default: 0.3)")
    args = parser.parse_args()
    
    if args.circuit:
        circuits = {args.circuit: ALL_CIRCUITS[args.circuit]}
    elif args.quick:
        circuits = {k: v for k, v in ALL_CIRCUITS.items() if k in ["monza", "monaco", "silverstone"]}
    else:
        circuits = ALL_CIRCUITS
    
    print("=" * 80)
    print(f"  V5.5 PU STATEFUL CALIBRATION — {len(circuits)} circuits")
    print(f"  Target: <{args.target}% error per circuit")
    print("=" * 80)
    
    # Baseline
    print("\n--- BASELINE ---")
    baseline = {}
    for name, cfg in sorted(circuits.items()):
        sim_time = simulate(name, cfg)
        ref_time = cfg["ref_time"]
        delta = sim_time - ref_time
        pct = abs(delta) / ref_time * 100
        flag = "OK" if pct < 0.5 else ("WARN" if pct < 1.0 else "FAIL")
        baseline[name] = (sim_time, delta, pct)
        print(f"  {name:>15s}: sim={sim_time:.3f}s d={delta:+.3f}s ({pct:.2f}%) {flag}")
    
    avg_pct = sum(v[2] for v in baseline.values()) / len(baseline)
    print(f"\n  Baseline avg: {avg_pct:.2f}%")
    
    # Calibrate circuits > target
    print(f"\n--- CALIBRATION (target <{args.target}%) ---")
    calibrated = {}
    for name, cfg in sorted(circuits.items()):
        if baseline[name][2] <= args.target:
            print(f"  {name}: OK ({baseline[name][2]:.2f}%), skip")
            continue
        new_mu = calibrate_circuit(name, cfg, target_pct=args.target)
        if new_mu is not None:
            calibrated[name] = (baseline[name][2], new_mu)
    
    # Final validation
    print(f"\n--- FINAL VALIDATION ---")
    _get_aero_cal_internal.cache_clear()
    try:
        from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration
        get_aero_calibration.cache_clear()
    except ImportError:
        pass
    
    final = {}
    for name, cfg in sorted(circuits.items()):
        sim_time = simulate(name, cfg)
        ref_time = cfg["ref_time"]
        delta = sim_time - ref_time
        pct = abs(delta) / ref_time * 100
        flag = "OK" if pct < 0.5 else ("WARN" if pct < 1.0 else "FAIL")
        final[name] = (sim_time, delta, pct)
        print(f"  {name:>15s}: sim={sim_time:.3f}s d={delta:+.3f}s ({pct:.2f}%) {flag}")
    
    avg_pct = sum(v[2] for v in final.values()) / len(final)
    print(f"\n  Final avg: {avg_pct:.2f}%")
    print(f"  Under 0.5%: {sum(1 for v in final.values() if v[2] < 0.5)}/{len(final)}")
    print(f"  Under 1.0%: {sum(1 for v in final.values() if v[2] < 1.0)}/{len(final)}")
    
    if calibrated:
        print(f"\n  Changes:")
        for name, (old_pct, new_mu) in sorted(calibrated.items()):
            new_pct = final[name][2]
            print(f"    {name}: {old_pct:.2f}% -> {new_pct:.2f}% (mu={new_mu:.4f})")


if __name__ == "__main__":
    main()