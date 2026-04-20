#!/usr/bin/env python3
"""Test DF/DRAG rebalance: scan wing angles su 5 circuiti rappresentativi.

Obiettivo: verificare che riducendo K_FACTOR (induced drag) gli ottimi si
spostino verso angoli più alti sui circuiti tecnici (barcelona, zandvoort)
SENZA spostare in alto Monza (fast).
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_engine.aero.front_wing import FrontWing
from lap_simulator.physics_engine.aero.rear_wing import RearWing
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


def set_k_factors(k_fw, k_rw):
    """Patch K_FACTOR in FrontWing e RearWing default constructor."""
    FrontWing._OVERRIDE_K = k_fw
    RearWing._OVERRIDE_K = k_rw

    # Monkeypatch __init__ per applicare l'override
    orig_fw_init = FrontWing.__init__
    orig_rw_init = RearWing.__init__

    if not hasattr(FrontWing, '_ORIG_INIT'):
        FrontWing._ORIG_INIT = orig_fw_init
        RearWing._ORIG_INIT = orig_rw_init

    def fw_init(self, config=None):
        FrontWing._ORIG_INIT(self, config)
        self.K_FACTOR = FrontWing._OVERRIDE_K

    def rw_init(self, config=None):
        RearWing._ORIG_INIT(self, config)
        self.K_FACTOR = RearWing._OVERRIDE_K

    FrontWing.__init__ = fw_init
    RearWing.__init__ = rw_init


def find_optimum(circuit_name, cfg):
    """Grid coarse (step 4°) + fine (step 2°) per trovare ottimo wings."""
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

    # Fine refinement
    for df in [-2, 0, 2]:
        for dr in [-2, 0, 2]:
            fw = max(4, min(42, best_fw + df))
            rw = max(4, min(45, best_rw + dr))
            t = sim(circuit_id, fw, rw, bwing, compound, susp_key)
            if t < best_t:
                best_t = t
                best_fw, best_rw = fw, rw

    return best_fw, best_rw, best_t


def main():
    # Baseline values
    K_SETS = [
        ("BASE (0.35/0.40)", 0.350, 0.400),
        ("MED  (0.30/0.35)", 0.300, 0.350),
        ("LOW  (0.25/0.30)", 0.250, 0.300),
        ("VLOW (0.20/0.25)", 0.200, 0.250),
    ]

    print("\n" + "="*90)
    print("  DF/DRAG REBALANCE TEST — wing optima vs K_FACTOR")
    print("="*90)

    results = {}

    for label, k_fw, k_rw in K_SETS:
        print(f"\n  {label}  (K_FW={k_fw}, K_RW={k_rw})")
        print(f"  {'-'*80}")
        set_k_factors(k_fw, k_rw)

        row = {}
        for name in TEST_CIRCUITS:
            cfg = ALL_CIRCUITS[name]
            fw, rw, t = find_optimum(name, cfg)
            row[name] = (fw, rw, t)
            ref = cfg["ref_time"]
            err = 100 * (t - ref) / ref
            print(f"    {name:<14} optimal FW={fw:>3d}/RW={rw:<3d}  t={t:.3f}s  (ref={ref:.3f}, err={err:+.2f}%)")

        results[label] = row

    # Summary comparison
    print("\n" + "="*90)
    print("  SUMMARY — FW/RW optimal shift")
    print("="*90)
    print(f"  {'Circuit':<14} " + "  ".join(f"{label:>18}" for label, _, _ in K_SETS))
    for name in TEST_CIRCUITS:
        row = f"  {name:<14} "
        for label, _, _ in K_SETS:
            fw, rw, t = results[label][name]
            row += f"     {fw:>3d}/{rw:<3d} ({t:.2f})"
        print(row)


if __name__ == "__main__":
    main()
