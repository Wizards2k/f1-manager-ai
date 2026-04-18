#!/usr/bin/env python3
"""Test rapido del ribilanciamento DF/DRAG su 5 circuiti rappresentativi."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup
from scripts.calibrate_v57 import ALL_CIRCUITS, SUSP_SETUPS, DRIVER

TEST_CIRCUITS = ["monza", "silverstone", "barcelona", "zandvoort", "monaco"]


def sim(circuit_id, fw, rw, bwing, compound, susp_key):
    setup = PhysicsV4Setup(driver_data=DRIVER, circuit=circuit_id, session="qualifying")
    setup.set_aero(front_wing=fw, rear_wing=rw, bwing=bwing)
    setup.set_suspension(**SUSP_SETUPS[susp_key])
    setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
    setup.set_tyres(compound=compound)
    setup.set_ers_mode("quali_deploy")
    return setup.simulate_lap(verbose=False)["lap_time_s"]


def find_optimum(name, cfg):
    """Grid coarse (step 4°) + fine (step 2°) + very fine (step 1°)."""
    circuit_id = cfg["circuit_id"]
    bwing = cfg["bwing"]
    compound = cfg["compound"]
    susp_key = cfg["susp_source"]

    best_fw, best_rw, best_t = 4, 4, 9999.0

    # Coarse grid
    for fw in range(4, 43, 4):
        for rw in range(4, 46, 4):
            t = sim(circuit_id, fw, rw, bwing, compound, susp_key)
            if t < best_t:
                best_t = t
                best_fw, best_rw = fw, rw

    # Fine refinement (step 2)
    for df in [-2, 0, 2]:
        for dr in [-2, 0, 2]:
            fw = max(4, min(42, best_fw + df))
            rw = max(4, min(45, best_rw + dr))
            t = sim(circuit_id, fw, rw, bwing, compound, susp_key)
            if t < best_t:
                best_t = t
                best_fw, best_rw = fw, rw

    # Very fine (step 1)
    for df in [-1, 0, 1]:
        for dr in [-1, 0, 1]:
            fw = max(4, min(42, best_fw + df))
            rw = max(4, min(45, best_rw + dr))
            t = sim(circuit_id, fw, rw, bwing, compound, susp_key)
            if t < best_t:
                best_t = t
                best_fw, best_rw = fw, rw

    return best_fw, best_rw, best_t


def main():
    print("\n" + "="*90)
    print("  QUICK REBALANCE TEST — K_FW=0.28, K_RW=0.32 (was 0.35/0.40)")
    print("="*90)
    print(f"  {'Circuit':<14} {'Old opt':<10} {'New opt':<10} {'Time (s)':<12} {'Ref (s)':<10} {'Err %':<8}")
    print(f"  {'-'*90}")

    OLD_OPT = {
        "monza": "7/4",
        "silverstone": "10/6",
        "barcelona": "9/5",
        "zandvoort": "12/8",
        "monaco": "18/14",
    }

    for name in TEST_CIRCUITS:
        cfg = ALL_CIRCUITS[name]
        fw, rw, t = find_optimum(name, cfg)
        ref = cfg["ref_time"]
        err = 100 * (t - ref) / ref
        new_opt = f"{fw}/{rw}"
        print(f"  {name:<14} {OLD_OPT[name]:<10} {new_opt:<10} {t:<12.3f} {ref:<10.3f} {err:<+8.2f}")


if __name__ == "__main__":
    main()
