#!/usr/bin/env python3
"""Test: ri-ottimizza Barcelona con diversi k_wing_coupling per spostare
l'ottimo verso HIGH wings (categoria slow)."""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_v4.calibration.aero_calibration import get_aero_calibration
from scripts.calibrate_v57 import ALL_CIRCUITS, SUSP_SETUPS, DRIVER

BARCELONA_JSON = ROOT / "data/circuits/aero_calibration/es-1991_barcelona_aero_cal.json"


def sim(circuit_id, fw, rw, bwing, compound, susp_key):
    setup = PhysicsV4Setup(driver_data=DRIVER, circuit=circuit_id, session="qualifying")
    setup.set_aero(front_wing=fw, rear_wing=rw, bwing=bwing)
    setup.set_suspension(**SUSP_SETUPS[susp_key])
    setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
    setup.set_tyres(compound=compound)
    setup.set_ers_mode("quali_deploy")
    return setup.simulate_lap(verbose=False)["lap_time_s"]


def patch_k(k_val):
    with open(BARCELONA_JSON) as f:
        data = json.load(f)
    data["floor_data"]["k_wing_coupling"] = k_val
    with open(BARCELONA_JSON, 'w') as f:
        json.dump(data, f, indent=4)
    get_aero_calibration.cache_clear()


def find_optimum(cfg):
    """Grid coarse + fine search."""
    best_fw, best_rw, best_t = 4, 4, 9999.0
    for fw in range(4, 43, 4):
        for rw in range(4, 46, 4):
            t = sim(cfg["circuit_id"], fw, rw, cfg["bwing"], cfg["compound"], cfg["susp_source"])
            if t < best_t:
                best_t = t; best_fw = fw; best_rw = rw
    for df in [-2, 0, 2]:
        for dr in [-2, 0, 2]:
            fw = max(4, min(42, best_fw + df))
            rw = max(4, min(45, best_rw + dr))
            t = sim(cfg["circuit_id"], fw, rw, cfg["bwing"], cfg["compound"], cfg["susp_source"])
            if t < best_t:
                best_t = t; best_fw = fw; best_rw = rw
    return best_fw, best_rw, best_t


def main():
    cfg = ALL_CIRCUITS["barcelona"]
    original_k = 0.045

    print("\n" + "="*70)
    print("  BARCELONA k_wing_coupling SENSITIVITY TEST")
    print("="*70)
    print(f"  {'k_coupling':<12} {'Optimal FW/RW':<14} {'Time (s)':<10}")
    print(f"  {'-'*70}")

    results = []
    for k in [0.045, 0.10, 0.15, 0.20, 0.30, 0.40]:
        patch_k(k)
        fw, rw, t = find_optimum(cfg)
        results.append((k, fw, rw, t))
        print(f"  {k:<12.3f} {fw:>3d}/{rw:<3d}          {t:<10.3f}")

    # Restore original
    patch_k(original_k)
    print(f"\n  Restored k={original_k}")


if __name__ == "__main__":
    main()
