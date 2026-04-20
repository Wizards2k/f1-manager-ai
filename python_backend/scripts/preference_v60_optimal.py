#!/usr/bin/env python3
"""V6.0 Setup Preference Test — usando gli assetti OTTIMALI per circuito.

Legge optimal_wings_v60.json (risultato di calibrate_v60_optimal_wings.py)
e testa LOW/CAL/HIGH dove CAL = ottimo trovato, LOW = CAL-6°, HIGH = CAL+6°.

Se l'ottimo è un vero minimo locale, LOW e HIGH dovrebbero entrambi essere
più lenti di CAL → congruenza raggiunta.
"""
import sys
import json
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


def test_circuit(name, cfg, optimal_fw, optimal_rw):
    """Test CAL (optimal), LOW (-6°), HIGH (+6°)."""
    cal_fw = optimal_fw
    cal_rw = optimal_rw
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
        "name": name,
        "cal_fw": cal_fw, "cal_rw": cal_rw,
        "low_fw": low_fw, "low_rw": low_rw,
        "high_fw": high_fw, "high_rw": high_rw,
        "t_low": t_low, "t_cal": t_cal, "t_high": t_high,
        "d_low": d_low, "d_high": d_high,
        "winner": winner, "ok": ok,
    }


def main():
    # Load optimal wings
    opt_file = ROOT / "optimal_wings_v60.json"
    if not opt_file.exists():
        print(f"❌ File not found: {opt_file}")
        print("   Run calibrate_v60_optimal_wings.py first.")
        return

    with open(opt_file) as f:
        optimal = json.load(f)

    print("\n" + "█"*95)
    print("  V6.0 PREFERENCE TEST — using circuit-optimal CAL setups")
    print("█"*95)
    print(f"  {'Circuito':<14} {'CAL FW/RW':>10}  {'LOW':>9} {'CAL':>9} {'HIGH':>9}  "
          f"{'ΔLOW':>7} {'ΔHIGH':>7}  winner")
    print(f"  {'-'*95}")

    results = []
    for name, cfg in sorted(ALL_CIRCUITS.items()):
        if name not in optimal:
            print(f"  {name:<14} ⚠️ skipped (no optimal data)")
            continue

        opt = optimal[name]
        r = test_circuit(name, cfg, opt["optimal_fw"], opt["optimal_rw"])
        results.append(r)
        flag = "✅" if r["ok"] else "❌"
        print(f"  {name:<14} {int(r['cal_fw']):>4d}/{int(r['cal_rw']):<3d}  "
              f"{r['t_low']:>9.3f} {r['t_cal']:>9.3f} {r['t_high']:>9.3f}  "
              f"{r['d_low']:>+7.3f} {r['d_high']:>+7.3f}  {r['winner']:<4} {flag}")

    print(f"  {'-'*95}")
    ok_count = sum(1 for r in results if r["ok"])
    total = len(results)
    print(f"\n  CONGRUENTI: {ok_count}/{total}")

    # Show incongruent cases
    incogr = [r for r in results if not r["ok"]]
    if incogr:
        print(f"\n  Incongruenti ({len(incogr)}):")
        for r in incogr:
            print(f"    {r['name']:<14} vince {r['winner']:<5} "
                  f"(ΔLOW={r['d_low']:+.3f}s, ΔHIGH={r['d_high']:+.3f}s)")

    # Summary stats
    if results:
        avg_d_low = sum(r['d_low'] for r in results) / len(results)
        avg_d_high = sum(r['d_high'] for r in results) / len(results)
        print(f"\n  Avg ΔLOW:  {avg_d_low:+.3f}s (LOW è {'più lenta' if avg_d_low > 0 else 'più veloce'})")
        print(f"  Avg ΔHIGH: {avg_d_high:+.3f}s (HIGH è {'più lenta' if avg_d_high > 0 else 'più veloce'})")


if __name__ == "__main__":
    main()
