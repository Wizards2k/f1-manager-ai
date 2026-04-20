#!/usr/bin/env python3
"""V5.5 validation with PU stateful active as default."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.integrator.waypoint_integrator import integrate_lap_hd

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

print("=" * 80)
print("  V5.5 VALIDATION — PU Stateful Active (QUALIFY map)")
print("=" * 80)

results = []
for name, cfg in sorted(ALL_CIRCUITS.items()):
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
    sim_time = r["lap_time_s"]
    ref_time = cfg["ref_time"]
    delta = sim_time - ref_time
    pct = abs(delta) / ref_time * 100
    flag = "OK" if pct < 0.5 else ("WARN" if pct < 1.0 else "FAIL")
    results.append((name, ref_time, sim_time, delta, pct, flag))
    print(f"  {name:>15s}: ref={ref_time:.3f}s sim={sim_time:.3f}s d={delta:+.3f}s ({pct:.2f}%) {flag}")

avg_pct = sum(r[4] for r in results) / len(results)
print(f"\n{'='*80}")
print(f"  Average error: {avg_pct:.2f}%")
print(f"  Under 0.5%: {sum(1 for r in results if r[4] < 0.5)}/{len(results)}")
print(f"  Under 1.0%: {sum(1 for r in results if r[4] < 1.0)}/{len(results)}")
worst = max(results, key=lambda r: r[4])
print(f"  Worst: {worst[0]} ({worst[4]:.2f}%)")
best = min(results, key=lambda r: r[4])
print(f"  Best: {best[0]} ({best[4]:.2f}%)")
print(f"{'='*80}")