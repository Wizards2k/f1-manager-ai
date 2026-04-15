#!/usr/bin/env python3
"""V5.8 Deep Diagnostic — Dove guadagna LOW-DF su silverstone/monaco?

Per ogni circuito esegue CAL e LOW-DF, poi divide la telemetria in:
  - STRAIGHT  (radius > 250m o radius==0)
  - MEDIUM    (80m < radius <= 250m)
  - SLOW      (radius <= 80m)

Per ogni bucket riporta tempo, distanza, velocità media, v_max.
Mostra dove vince LOW-DF e di quanto.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup, DriverSkill

REFERENCE = {
    "monza":       {"circuit_id": "it-1922_monza",      "fw": 12.0, "rw": 14.0, "compound": "C5", "bwing": 7.0,  "susp": "monza"},
    "monaco":      {"circuit_id": "mc-1929_monaco",     "fw": 38.0, "rw": 42.0, "compound": "C6", "bwing": 18.0, "susp": "monaco"},
    "silverstone": {"circuit_id": "gb-1948_silverstone","fw": 22.0, "rw": 26.0, "compound": "C5", "bwing": 10.0, "susp": "silverstone"},
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
    return setup.simulate_lap(verbose=False)


def bucket_telemetry(telemetry):
    """Divide la telemetria in straight/medium/slow."""
    buckets = {
        "STRAIGHT": {"time_s": 0.0, "dist_m": 0.0, "v_sum": 0.0, "v_max": 0.0, "n": 0},
        "MEDIUM":   {"time_s": 0.0, "dist_m": 0.0, "v_sum": 0.0, "v_max": 0.0, "n": 0},
        "SLOW":     {"time_s": 0.0, "dist_m": 0.0, "v_sum": 0.0, "v_max": 0.0, "n": 0},
    }
    prev = None
    for p in telemetry:
        if prev is None:
            prev = p
            continue
        r = p.get("radius_m", 0)
        if r == 0 or r > 250:
            key = "STRAIGHT"
        elif r > 80:
            key = "MEDIUM"
        else:
            key = "SLOW"
        dt = p["time_s"] - prev["time_s"]
        ddist = p["distance_m"] - prev["distance_m"]
        v = p["velocity_kph"]
        b = buckets[key]
        b["time_s"] += dt
        b["dist_m"] += ddist
        b["v_sum"] += v
        b["v_max"] = max(b["v_max"], v)
        b["n"] += 1
        prev = p
    for b in buckets.values():
        b["v_avg"] = b["v_sum"] / b["n"] if b["n"] > 0 else 0.0
    return buckets


def diag(name, cfg):
    print(f"\n{'='*78}")
    print(f"  {name.upper()}")
    print(f"{'='*78}")

    cal_fw, cal_rw = cfg["fw"], cfg["rw"]
    low_fw, low_rw = max(cal_fw - 6, 4), max(cal_rw - 6, 4)

    res_cal = sim(cfg["circuit_id"], cal_fw, cal_rw, cfg["bwing"], cfg["compound"], cfg["susp"])
    res_low = sim(cfg["circuit_id"], low_fw, low_rw, cfg["bwing"], cfg["compound"], cfg["susp"])

    cal_t = res_cal["lap_time_s"]
    low_t = res_low["lap_time_s"]
    print(f"  CAL    (FW={cal_fw:.0f}/RW={cal_rw:.0f}): {cal_t:.3f}s  Vmax={res_cal['v_max_kph']:.1f}kph")
    print(f"  LOW-DF (FW={low_fw:.0f}/RW={low_rw:.0f}): {low_t:.3f}s  Vmax={res_low['v_max_kph']:.1f}kph")
    print(f"  Δ LOW-CAL = {low_t - cal_t:+.3f}s")

    bk_cal = bucket_telemetry(res_cal["telemetry"])
    bk_low = bucket_telemetry(res_low["telemetry"])

    print(f"\n  {'BUCKET':<10} {'time_cal':>10} {'time_low':>10} {'Δtime':>10}  "
          f"{'dist_cal':>10} {'v_avg_cal':>10} {'v_avg_low':>10}  {'v_max_low':>10}")
    print(f"  {'-'*92}")

    total_dt = 0.0
    for key in ("STRAIGHT", "MEDIUM", "SLOW"):
        bc = bk_cal[key]
        bl = bk_low[key]
        dt = bl["time_s"] - bc["time_s"]
        total_dt += dt
        print(f"  {key:<10} {bc['time_s']:>10.3f} {bl['time_s']:>10.3f} {dt:>+10.3f}  "
              f"{bc['dist_m']:>10.0f} {bc['v_avg']:>10.1f} {bl['v_avg']:>10.1f}  {bl['v_max']:>10.1f}")

    print(f"  {'-'*92}")
    print(f"  {'TOTAL Δ':<10} {'':>10} {'':>10} {total_dt:>+10.3f}")

    # Diagnosi quale bucket spiega il guadagno low-DF
    print(f"\n  → LOW-DF guadagna {low_t - cal_t:+.3f}s totali")
    for key in ("STRAIGHT", "MEDIUM", "SLOW"):
        dt = bk_low[key]["time_s"] - bk_cal[key]["time_s"]
        sign = "GUADAGNA" if dt < 0 else "PERDE"
        print(f"     {key:<10}: {sign} {abs(dt):.3f}s")


def main():
    print("\n" + "█"*78)
    print("  V5.8 DEEP DIAGNOSTIC — dove guadagna LOW-DF?")
    print("█"*78)
    for name, cfg in REFERENCE.items():
        diag(name, cfg)


if __name__ == "__main__":
    main()
