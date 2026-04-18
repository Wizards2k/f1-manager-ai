#!/usr/bin/env python3
"""V5.8 Setup Preference Test — verifica se il motore preferisce il setup calibrato.

Per ogni circuito di riferimento (monza/monaco/silverstone) simula 3 setup:
  - LOW-DF:  cal_FW - 6, cal_RW - 6
  - CAL:     setup calibrato (V5.7 baseline)
  - HIGH-DF: cal_FW + 6, cal_RW + 6

Il setup CAL deve essere il più veloce. Se LOW o HIGH vince, il motore è incongruente.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup, DriverSkill

REFERENCE = {
    "monza":       {"circuit_id": "it-1922_monza",      "fw": 12.0, "rw": 14.0, "compound": "C5", "bwing": 7.0,  "susp": "monza",      "ref": 78.869},
    "monaco":      {"circuit_id": "mc-1929_monaco",     "fw": 38.0, "rw": 42.0, "compound": "C6", "bwing": 18.0, "susp": "monaco",     "ref": 69.954},
    "silverstone": {"circuit_id": "gb-1948_silverstone","fw": 22.0, "rw": 26.0, "compound": "C5", "bwing": 10.0, "susp": "silverstone","ref": 85.010},
}

SUSP = {
    "monza":       {"spring_front": 25.0, "spring_rear": 33.0, "ARB_front": 8.0,  "ARB_rear": 13.0, "ride_height_front": 10.0, "ride_height_rear": 17.0},
    "monaco":      {"spring_front": 10.0, "spring_rear": 18.0, "ARB_front": 25.0, "ARB_rear": 30.0, "ride_height_front": 16.0, "ride_height_rear": 23.0},
    "silverstone": {"spring_front": 25.0, "spring_rear": 33.0, "ARB_front": 25.0, "ARB_rear": 30.0, "ride_height_front": 2.0,  "ride_height_rear": 9.0},
}

DRIVER = DriverSkill(name="Ref", quali_skill=1.0, race_skill=1.0, braking_skill=1.0,
                     cornering_skill=1.0, throttle_skill=1.0, consistency=1.0,
                     front_wing_offset=0, rear_wing_offset=0, brake_bias_offset=0.0)


def sim(circuit_id, fw, rw, bwing, compound, susp_key):
    setup = PhysicsV4Setup(driver_data=DRIVER, circuit=circuit_id, session="qualifying")
    setup.set_aero(front_wing=fw, rear_wing=rw, bwing=bwing)
    setup.set_suspension(**SUSP[susp_key])
    setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
    setup.set_tyres(compound=compound)
    setup.set_ers_mode("quali_deploy")
    return setup.simulate_lap(verbose=False)["lap_time_s"]


def test_circuit(name, cfg):
    print(f"\n{'='*70}")
    print(f"  {name.upper()} (cal FW={cfg['fw']:.0f}/RW={cfg['rw']:.0f})")
    print(f"{'='*70}")

    setups = {
        "LOW-DF":  (max(cfg["fw"] - 6, 4),  max(cfg["rw"] - 6, 4)),
        "CAL":     (cfg["fw"], cfg["rw"]),
        "HIGH-DF": (cfg["fw"] + 6, cfg["rw"] + 6),
    }

    times = {}
    for label, (fw, rw) in setups.items():
        t = sim(cfg["circuit_id"], fw, rw, cfg["bwing"], cfg["compound"], cfg["susp"])
        times[label] = (fw, rw, t)
        print(f"  {label:<8} FW={fw:>4.0f}/RW={rw:>4.0f}  →  {t:.3f}s")

    winner = min(times, key=lambda k: times[k][2])
    cal_t = times["CAL"][2]
    delta_low = times["LOW-DF"][2] - cal_t
    delta_high = times["HIGH-DF"][2] - cal_t

    flag = "✅ CONGRUENTE" if winner == "CAL" else f"❌ INCONGRUENTE (vince {winner})"
    print(f"\n  Δ LOW-CAL: {delta_low:+.3f}s   Δ HIGH-CAL: {delta_high:+.3f}s")
    print(f"  {flag}")
    return winner == "CAL"


def main():
    print("\n" + "█"*70)
    print("  V5.8 SETUP PREFERENCE TEST — clamp 0.55")
    print("█"*70)

    results = {}
    for name, cfg in REFERENCE.items():
        results[name] = test_circuit(name, cfg)

    print(f"\n{'='*70}")
    print("  RIEPILOGO")
    print(f"{'='*70}")
    n_ok = sum(results.values())
    for name, ok in results.items():
        print(f"  {name:<14} {'✅' if ok else '❌'}")
    print(f"\n  Congruenti: {n_ok}/{len(results)}")


if __name__ == "__main__":
    main()
