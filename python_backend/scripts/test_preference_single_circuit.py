#!/usr/bin/env python3
"""Debug: Test preference test logic on a single circuit."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup, DriverSkill
from scripts.calibrate_v57 import ALL_CIRCUITS, SUSP_SETUPS, DRIVER


def sim(circuit_id, fw, rw, bwing, compound, susp_key):
    setup = PhysicsV4Setup(driver_data=DRIVER, circuit=circuit_id, session="qualifying")
    setup.set_aero(front_wing=fw, rear_wing=rw, bwing=bwing)
    setup.set_suspension(**SUSP_SETUPS[susp_key])
    setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
    setup.set_tyres(compound=compound)
    setup.set_ers_mode("quali_deploy")
    return setup.simulate_lap(verbose=False)["lap_time_s"]


def test_circuit(name, cfg):
    cal_fw = cfg["front_wing"]
    cal_rw = cfg["rear_wing"]
    low_fw = max(cal_fw - 6, 4)
    low_rw = max(cal_rw - 6, 4)
    high_fw = min(cal_fw + 6, 42)
    high_rw = min(cal_rw + 6, 45)

    print(f"\nTesting {name}...")
    print(f"  CAL: FW={cal_fw}, RW={cal_rw}")
    print(f"  LOW: FW={low_fw}, RW={low_rw}")
    print(f"  HIGH: FW={high_fw}, RW={high_rw}")
    print(f"  Compound: {cfg['compound']}, Susp: {cfg['susp_source']}")

    t_low = sim(cfg["circuit_id"], low_fw, low_rw, cfg["bwing"], cfg["compound"], cfg["susp_source"])
    print(f"  LOW time: {t_low:.3f}s")

    t_cal = sim(cfg["circuit_id"], cal_fw, cal_rw, cfg["bwing"], cfg["compound"], cfg["susp_source"])
    print(f"  CAL time: {t_cal:.3f}s")

    t_high = sim(cfg["circuit_id"], high_fw, high_rw, cfg["bwing"], cfg["compound"], cfg["susp_source"])
    print(f"  HIGH time: {t_high:.3f}s")

    d_low = t_low - t_cal
    d_high = t_high - t_cal
    winner = min([("LOW", t_low), ("CAL", t_cal), ("HIGH", t_high)], key=lambda x: x[1])[0]
    ok = winner == "CAL"

    print(f"  Winner: {winner} {'✅' if ok else '❌'}")
    print(f"  Δ LOW: {d_low:+.3f}s, Δ HIGH: {d_high:+.3f}s")

    return {
        "name": name, "cal_fw": cal_fw, "cal_rw": cal_rw,
        "t_low": t_low, "t_cal": t_cal, "t_high": t_high,
        "d_low": d_low, "d_high": d_high,
        "winner": winner, "ok": ok,
    }


if __name__ == "__main__":
    # Test on Austin
    circuit_config = ALL_CIRCUITS["austin"]
    test_circuit("austin", circuit_config)
