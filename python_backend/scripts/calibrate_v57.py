#!/usr/bin/env python3
"""V5.7 Re-calibration — Find optimal mu_mechanical per circuit after aero drag fix.

The V5.7 aero changes (K_FACTOR wings +0.35/+0.40, K_FACTOR floor +0.16/+0.20)
increased drag, making lap times slower. This script finds the new mu_mechanical
that brings each circuit back to <0.5% error.

Uses the same PhysicsV4Setup pipeline as validate_v56.py.
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup, DriverSkill
from lap_simulator.push_penalty import compute_push_penalty
from lap_simulator.data_types import CircuitConfig

# Same circuits as validate_v56.py
ALL_CIRCUITS = {
    "baku": {"circuit_id": "az-2016_baku", "front_wing": 12.0, "rear_wing": 14.0, "compound": "C6", "fuel_kg": 20.0, "ref_time": 101.117, "susp_source": "monza", "bwing": 5.0},
    "spa": {"circuit_id": "be-1925_spa_francorchamps", "front_wing": 10.0, "rear_wing": 12.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 100.562, "susp_source": "monza", "bwing": 5.0},
    "shanghai": {"circuit_id": "cn-2004_shanghai", "front_wing": 20.0, "rear_wing": 24.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 90.641, "susp_source": "silverstone", "bwing": 10.0},
    "sakhir": {"circuit_id": "bh-2002_sakhir", "front_wing": 14.0, "rear_wing": 16.0, "compound": "C3", "fuel_kg": 20.0, "ref_time": 89.841, "susp_source": "monza", "bwing": 5.0},
    "melbourne": {"circuit_id": "au-1953_melbourne", "front_wing": 18.0, "rear_wing": 22.0, "compound": "C5", "fuel_kg": 20.0, "ref_time": 75.096, "susp_source": "silverstone", "bwing": 10.0},
    "yas_marina": {"circuit_id": "ae-2009_yas_marina", "front_wing": 18.0, "rear_wing": 22.0, "compound": "C5", "fuel_kg": 20.0, "ref_time": 82.207, "susp_source": "silverstone", "bwing": 10.0},
    "barcelona": {"circuit_id": "es-1991_barcelona", "front_wing": 22.0, "rear_wing": 26.0, "compound": "C3", "fuel_kg": 20.0, "ref_time": 71.546, "susp_source": "silverstone", "bwing": 10.0},
    "jeddah": {"circuit_id": "sa-2021_jeddah", "front_wing": 12.0, "rear_wing": 14.0, "compound": "C5", "fuel_kg": 20.0, "ref_time": 87.294, "susp_source": "monza", "bwing": 5.0},
    "singapore": {"circuit_id": "sg-2008_singapore", "front_wing": 34.0, "rear_wing": 38.0, "compound": "C5", "fuel_kg": 20.0, "ref_time": 89.158, "susp_source": "monaco", "bwing": 18.0},
    "sao_paulo": {"circuit_id": "br-1940_sao_paulo", "front_wing": 20.0, "rear_wing": 24.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 69.511, "susp_source": "silverstone", "bwing": 10.0},
    "monaco": {"circuit_id": "mc-1929_monaco", "front_wing": 38.0, "rear_wing": 42.0, "compound": "C6", "fuel_kg": 20.0, "ref_time": 69.954, "susp_source": "monaco", "bwing": 18.0},
    "suzuka": {"circuit_id": "jp-1962_suzuka", "front_wing": 24.0, "rear_wing": 28.0, "compound": "C3", "fuel_kg": 20.0, "ref_time": 86.995, "susp_source": "silverstone", "bwing": 10.0},
    "silverstone": {"circuit_id": "gb-1948_silverstone", "front_wing": 22.0, "rear_wing": 26.0, "compound": "C5", "fuel_kg": 20.0, "ref_time": 85.010, "susp_source": "silverstone", "bwing": 10.0},
    "zandvoort": {"circuit_id": "nl-1948_zandvoort", "front_wing": 28.0, "rear_wing": 32.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 68.662, "susp_source": "monaco", "bwing": 18.0},
    "budapest": {"circuit_id": "hu-1986_budapest", "front_wing": 28.0, "rear_wing": 32.0, "compound": "C5", "fuel_kg": 20.0, "ref_time": 75.372, "susp_source": "monaco", "bwing": 18.0},
    "monza": {"circuit_id": "it-1922_monza", "front_wing": 8.0, "rear_wing": 10.0, "compound": "C5", "fuel_kg": 20.0, "ref_time": 78.869, "susp_source": "monza", "bwing": 5.0},
    "montreal": {"circuit_id": "ca-1978_montreal", "front_wing": 22.0, "rear_wing": 26.0, "compound": "C6", "fuel_kg": 20.0, "ref_time": 70.899, "susp_source": "silverstone", "bwing": 10.0},
    "imola": {"circuit_id": "it-1953_imola", "front_wing": 18.0, "rear_wing": 22.0, "compound": "C6", "fuel_kg": 20.0, "ref_time": 74.670, "susp_source": "silverstone", "bwing": 10.0},
    "mexico_city": {"circuit_id": "mx-1962_mexico_city", "front_wing": 22.0, "rear_wing": 26.0, "compound": "C5", "fuel_kg": 20.0, "ref_time": 75.586, "susp_source": "silverstone", "bwing": 10.0},
    "miami": {"circuit_id": "us-2022_miami", "front_wing": 18.0, "rear_wing": 22.0, "compound": "C5", "fuel_kg": 20.0, "ref_time": 86.204, "susp_source": "silverstone", "bwing": 10.0},
    "lusail": {"circuit_id": "qa-2004_lusail", "front_wing": 22.0, "rear_wing": 26.0, "compound": "C3", "fuel_kg": 20.0, "ref_time": 79.387, "susp_source": "silverstone", "bwing": 10.0},
    "spielberg": {"circuit_id": "at-1969_spielberg", "front_wing": 18.0, "rear_wing": 22.0, "compound": "C5", "fuel_kg": 20.0, "ref_time": 63.971, "susp_source": "silverstone", "bwing": 10.0},
    "austin": {"circuit_id": "us-2012_austin", "front_wing": 22.0, "rear_wing": 26.0, "compound": "C4", "fuel_kg": 20.0, "ref_time": 92.510, "susp_source": "silverstone", "bwing": 10.0},
    "las_vegas": {"circuit_id": "us-2023_las_vegas", "front_wing": 10.0, "rear_wing": 12.0, "compound": "C5", "fuel_kg": 20.0, "ref_time": 107.934, "susp_source": "monza", "bwing": 5.0},
}

SUSP_SETUPS = {
    "monza": {"spring_front": 25.0, "spring_rear": 33.0, "ARB_front": 8.0, "ARB_rear": 13.0, "ride_height_front": 10.0, "ride_height_rear": 17.0},
    "monaco": {"spring_front": 10.0, "spring_rear": 18.0, "ARB_front": 25.0, "ARB_rear": 30.0, "ride_height_front": 16.0, "ride_height_rear": 23.0},
    "silverstone": {"spring_front": 25.0, "spring_rear": 33.0, "ARB_front": 25.0, "ARB_rear": 30.0, "ride_height_front": 2.0, "ride_height_rear": 9.0},
}

DRIVER = DriverSkill(name="Reference", quali_skill=1.0, race_skill=1.0, braking_skill=1.0, cornering_skill=1.0, throttle_skill=1.0, consistency=1.0, front_wing_offset=0, rear_wing_offset=0, brake_bias_offset=0.0)

AERO_CAL_DIR = ROOT / "data" / "circuits" / "aero_calibration"


def load_aero_cal(circuit_id):
    cal_file = AERO_CAL_DIR / f"{circuit_id}_aero_cal.json"
    if cal_file.exists():
        with open(cal_file) as f:
            return json.load(f)
    return None


def save_aero_cal(circuit_id, data):
    cal_file = AERO_CAL_DIR / f"{circuit_id}_aero_cal.json"
    with open(cal_file, 'w') as f:
        json.dump(data, f, indent=4)


def simulate_with_mu(circuit_id, mu, cfg):
    """Simulate with a specific mu_mechanical value."""
    susp = SUSP_SETUPS[cfg["susp_source"]]
    
    # Load and modify aero calibration
    cal = load_aero_cal(circuit_id)
    if cal:
        cal["grip_data"]["mu_mechanical"] = mu
        cal["grip_data"]["compound"] = cfg["compound"]
        save_aero_cal(circuit_id, cal)
    
    # Clear LRU cache
    try:
        from lap_simulator.physics_v4.calibration.aero_calibration import get_aero_calibration
        get_aero_calibration.cache_clear()
    except:
        pass
    try:
        from calibration.aero_calibration import get_aero_calibration as _get_cal
        _get_cal.cache_clear()
    except:
        pass
    
    setup = PhysicsV4Setup(driver_data=DRIVER, circuit=circuit_id, session="qualifying")
    setup.set_aero(front_wing=cfg["front_wing"], rear_wing=cfg["rear_wing"], bwing=cfg["bwing"])
    setup.set_suspension(**susp)
    setup.set_fuels(fuel_kg=cfg["fuel_kg"], fuel_mix="rich")
    setup.set_tyres(compound=cfg["compound"])
    setup.set_ers_mode("quali_deploy")
    
    r = setup.simulate_lap(verbose=False)
    return r["lap_time_s"]


def calibrate_circuit(name, cfg, target_pct=0.3):
    """Binary search for optimal mu_mechanical."""
    circuit_id = cfg["circuit_id"]
    ref_time = cfg["ref_time"]
    
    # Load current mu
    cal = load_aero_cal(circuit_id)
    current_mu = cal["grip_data"]["mu_mechanical"] if cal else 1.55
    
    # Initial simulation
    sim_time = simulate_with_mu(circuit_id, current_mu, cfg)
    current_pct = abs(sim_time - ref_time) / ref_time * 100
    
    if current_pct < target_pct:
        print(f"  {name:>15s}: mu={current_mu:.3f} → {sim_time:.3f}s ({current_pct:+.2f}%) ✅ già OK")
        return current_mu
    
    # Binary search
    # V6.0: Espandi range a [0.6, 2.5] perché senza v_ref ceiling,
    # il simulatore va più veloce in curva → serve meno mu sui circuiti veloci
    lo, hi = 0.6, 2.5
    best_mu = current_mu
    best_pct = current_pct
    
    for i in range(15):
        mid = (lo + hi) / 2
        sim_time = simulate_with_mu(circuit_id, mid, cfg)
        delta = sim_time - ref_time
        pct = abs(delta) / ref_time * 100
        
        if pct < best_pct:
            best_mu = mid
            best_pct = pct
        
        if delta > 0:  # too slow → need more grip
            lo = mid
        else:  # too fast → need less grip
            hi = mid
        
        if pct < target_pct:
            break
    
    # Save best mu
    cal = load_aero_cal(circuit_id)
    cal["grip_data"]["mu_mechanical"] = best_mu
    save_aero_cal(circuit_id, cal)
    
    # Clear cache and verify
    try:
        from lap_simulator.physics_v4.calibration.aero_calibration import get_aero_calibration
        get_aero_calibration.cache_clear()
    except:
        pass
    
    sim_time = simulate_with_mu(circuit_id, best_mu, cfg)
    final_pct = abs(sim_time - ref_time) / ref_time * 100
    
    flag = "✅" if final_pct < 0.5 else ("🟡" if final_pct < 1.0 else "🔴")
    print(f"  {name:>15s}: mu={current_mu:.3f}→{best_mu:.3f} {ref_time:.3f}s→{sim_time:.3f}s ({final_pct:+.2f}%) {flag}")
    return best_mu


def main():
    import argparse
    parser = argparse.ArgumentParser(description="V5.7 Re-calibration")
    parser.add_argument("--quick", action="store_true", help="Only calibrate 3 reference circuits")
    parser.add_argument("--circuit", type=str, help="Calibrate specific circuit")
    args = parser.parse_args()
    
    if args.circuit:
        circuits = {args.circuit: ALL_CIRCUITS[args.circuit]}
    elif args.quick:
        circuits = {k: v for k, v in ALL_CIRCUITS.items() if k in ["monza", "monaco", "silverstone"]}
    else:
        circuits = ALL_CIRCUITS
    
    print("=" * 80)
    print(f"  V5.7 RE-CALIBRATION — {len(circuits)} circuits")
    print("=" * 80)
    
    for name, cfg in sorted(circuits.items()):
        calibrate_circuit(name, cfg)
    
    print("\n✅ Calibrazione completata. Eseguire validate_v56.py per verificare.")


if __name__ == "__main__":
    main()