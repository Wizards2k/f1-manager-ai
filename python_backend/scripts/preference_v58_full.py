#!/usr/bin/env python3
"""V5.8 Setup Preference Test — FULL 24 circuiti.

Usa gli stessi setup di calibrate_v57.py. Per ogni circuito testa LOW/CAL/HIGH.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup, DriverSkill
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

    t_low = sim(cfg["circuit_id"], low_fw, low_rw, cfg["bwing"], cfg["compound"], cfg["susp_source"])
    t_cal = sim(cfg["circuit_id"], cal_fw, cal_rw, cfg["bwing"], cfg["compound"], cfg["susp_source"])
    t_high = sim(cfg["circuit_id"], high_fw, high_rw, cfg["bwing"], cfg["compound"], cfg["susp_source"])

    d_low = t_low - t_cal
    d_high = t_high - t_cal
    winner = min([("LOW", t_low), ("CAL", t_cal), ("HIGH", t_high)], key=lambda x: x[1])[0]
    ok = winner == "CAL"
    return {
        "name": name, "cal_fw": cal_fw, "cal_rw": cal_rw,
        "t_low": t_low, "t_cal": t_cal, "t_high": t_high,
        "d_low": d_low, "d_high": d_high,
        "winner": winner, "ok": ok,
    }


def main():
    print("\n" + "█"*85)
    print("  V5.8 FULL PREFERENCE TEST — 24 circuits (K_FACTOR=0.30/0.35)")
    print("█"*85)
    print(f"  {'Circuito':<14} {'FW/RW':>8}  {'LOW':>9} {'CAL':>9} {'HIGH':>9}  "
          f"{'ΔLOW':>7} {'ΔHIGH':>7}  winner")
    print(f"  {'-'*85}")

    results = []
    for name, cfg in sorted(ALL_CIRCUITS.items()):
        r = test_circuit(name, cfg)
        results.append(r)
        flag = "✅" if r["ok"] else "❌"
        print(f"  {name:<14} {r['cal_fw']:>3.0f}/{r['cal_rw']:>3.0f}  "
              f"{r['t_low']:>9.3f} {r['t_cal']:>9.3f} {r['t_high']:>9.3f}  "
              f"{r['d_low']:>+7.3f} {r['d_high']:>+7.3f}  {r['winner']:<4} {flag}")

    print(f"  {'-'*85}")
    ok_count = sum(1 for r in results if r["ok"])
    print(f"\n  CONGRUENTI: {ok_count}/24")
    incogr = [r for r in results if not r["ok"]]
    if incogr:
        print(f"\n  Incongruenti:")
        for r in incogr:
            print(f"    {r['name']:<14} vince {r['winner']:<5} "
                  f"(ΔLOW={r['d_low']:+.3f}s, ΔHIGH={r['d_high']:+.3f}s)")


if __name__ == "__main__":
    main()
