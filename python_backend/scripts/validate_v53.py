#!/usr/bin/env python3
from __future__ import annotations
"""
Validate V5.3 calibration — simulate all 24 circuits and check error.

NON-REGRESSION REFERENCE SCRIPT
================================
This script is the official reference for validating the V5.3 physics engine.
It MUST be run after any change to the physics engine to verify that the
calibration is still within the target error (<0.5% average).

Parameters calibrated:
  - Aero: front_wing, rear_wing (per circuit)
  - Suspension: spring_front/rear, arb_front/rear, ride_height_front/rear
    (3 categories: low-DF/Monza, high-DF/Monaco, medium-DF/Silverstone)
  - mu_mechanical: per-circuit grip calibration (17 circuits adjusted)
  - Compound: per-circuit tyre compound
  - Fuel: 20kg (qualifying)

NOT calibrated (fixed values):
  - driver_skill = 1.0 (average driver, no bonus/penalty)
  - push_level = NOT used in integrate_lap_hd (applied externally via push_penalty)
  - ers_power_fraction = 1.0 (full ERS deployment)
  - reference_pull_strength = 0.0 (disabled)

Note on driver_skill vs push_level:
  - driver_skill: multiplier on grip (mu_base) and power. 1.0 = average.
    Values >1.0 = better driver (more grip, more power).
    Values <1.0 = worse driver (less grip, less power).
    This is passed to integrate_lap_hd and AFFECTS the physics simulation.
  - push_level: integer 1-10 from DriverIntent. 10 = zero penalty (max push).
    Lower values add per-lap time penalties via push_penalty.py.
    This is NOT passed to integrate_lap_hd — it's applied as an ADDITIVE
    penalty on top of the physics lap time. This is by design:
    push_level does NOT change the physics, it adds a time penalty that
    represents the driver not pushing to the limit (braking earlier,
    accelerating later, suboptimal lines).
    This means our calibration (which uses push=10, zero penalty) remains
    valid regardless of the push_level the user selects in the game.

Architecture:
  Physics Engine (integrate_lap_hd) → optimal lap time (push=10, driver_skill=1.0)
  + push_penalty (push_level < 10) → final lap time with driver conservatism
  + driver_skill (< 1.0) → slower lap time due to less grip/power

Usage:
    python validate_v53.py              # Full validation (24 circuits)
    python validate_v53.py --quick       # Quick validation (3 reference circuits)
    python validate_v53.py --driver 1.05 # Test with driver_skill=1.05 (+5%)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.integrator.waypoint_integrator import integrate_lap_hd

# All 24 circuits with optimal setups
ALL_CIRCUITS = {
    "baku": {
        "circuit_id": "az-2016_baku",
        "front_wing": 12.0, "rear_wing": 14.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 101.117,
        "susp_source": "monza",
    },
    "spa": {
        "circuit_id": "be-1925_spa_francorchamps",
        "front_wing": 10.0, "rear_wing": 12.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 100.562,
        "susp_source": "monza",
    },
    "shanghai": {
        "circuit_id": "cn-2004_shanghai",
        "front_wing": 20.0, "rear_wing": 24.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 90.641,
        "susp_source": "silverstone",
    },
    "sakhir": {
        "circuit_id": "bh-2002_sakhir",
        "front_wing": 14.0, "rear_wing": 16.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 89.841,
        "susp_source": "monza",
    },
    "melbourne": {
        "circuit_id": "au-1953_melbourne",
        "front_wing": 18.0, "rear_wing": 22.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 75.096,
        "susp_source": "silverstone",
    },
    "yas_marina": {
        "circuit_id": "ae-2009_yas_marina",
        "front_wing": 18.0, "rear_wing": 22.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 82.207,
        "susp_source": "silverstone",
    },
    "barcelona": {
        "circuit_id": "es-1991_barcelona",
        "front_wing": 22.0, "rear_wing": 26.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 71.546,
        "susp_source": "silverstone",
    },
    "jeddah": {
        "circuit_id": "sa-2021_jeddah",
        "front_wing": 12.0, "rear_wing": 14.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 87.294,
        "susp_source": "monza",
    },
    "singapore": {
        "circuit_id": "sg-2008_singapore",
        "front_wing": 34.0, "rear_wing": 38.0,
        "compound": "C6", "fuel_kg": 20.0,
        "ref_time": 89.158,
        "susp_source": "monaco",
    },
    "sao_paulo": {
        "circuit_id": "br-1940_sao_paulo",
        "front_wing": 20.0, "rear_wing": 24.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 69.511,
        "susp_source": "silverstone",
    },
    "monaco": {
        "circuit_id": "mc-1929_monaco",
        "front_wing": 38.0, "rear_wing": 42.0,
        "compound": "C6", "fuel_kg": 20.0,
        "ref_time": 69.954,
        "susp_source": "monaco",
    },
    "suzuka": {
        "circuit_id": "jp-1962_suzuka",
        "front_wing": 24.0, "rear_wing": 28.0,
        "compound": "C3", "fuel_kg": 20.0,
        "ref_time": 86.995,
        "susp_source": "silverstone",
    },
    "silverstone": {
        "circuit_id": "gb-1948_silverstone",
        "front_wing": 22.0, "rear_wing": 26.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 85.010,
        "susp_source": "silverstone",
    },
    "zandvoort": {
        "circuit_id": "nl-1948_zandvoort",
        "front_wing": 28.0, "rear_wing": 32.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 68.662,
        "susp_source": "monaco",
    },
    "budapest": {
        "circuit_id": "hu-1986_budapest",
        "front_wing": 28.0, "rear_wing": 32.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 75.372,
        "susp_source": "monaco",
    },
    "monza": {
        "circuit_id": "it-1922_monza",
        "front_wing": 8.0, "rear_wing": 10.0,
        "compound": "C5", "fuel_kg": 20.0,
        "ref_time": 78.869,
        "susp_source": "monza",
    },
    "montreal": {
        "circuit_id": "ca-1978_montreal",
        "front_wing": 22.0, "rear_wing": 26.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 70.899,
        "susp_source": "silverstone",
    },
    "imola": {
        "circuit_id": "it-1953_imola",
        "front_wing": 18.0, "rear_wing": 22.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 74.670,
        "susp_source": "silverstone",
    },
    "mexico_city": {
        "circuit_id": "mx-1962_mexico_city",
        "front_wing": 22.0, "rear_wing": 26.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 75.586,
        "susp_source": "silverstone",
    },
    "miami": {
        "circuit_id": "us-2022_miami",
        "front_wing": 18.0, "rear_wing": 22.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 86.204,
        "susp_source": "silverstone",
    },
    "lusail": {
        "circuit_id": "qa-2004_lusail",
        "front_wing": 22.0, "rear_wing": 26.0,
        "compound": "C3", "fuel_kg": 20.0,
        "ref_time": 79.387,
        "susp_source": "silverstone",
    },
    "spielberg": {
        "circuit_id": "at-1969_spielberg",
        "front_wing": 18.0, "rear_wing": 22.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 63.971,
        "susp_source": "silverstone",
    },
    "austin": {
        "circuit_id": "us-2012_austin",
        "front_wing": 22.0, "rear_wing": 26.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 92.510,
        "susp_source": "silverstone",
    },
    "las_vegas": {
        "circuit_id": "us-2023_las_vegas",
        "front_wing": 10.0, "rear_wing": 12.0,
        "compound": "C4", "fuel_kg": 20.0,
        "ref_time": 107.934,
        "susp_source": "monza",
    },
}

# Optimal suspension setups from Phase 1 (with fine grid)
SUSP_SETUPS = {
    "monza": {
        "spring_front": 25.0, "spring_rear": 33.0,
        "arb_front": 8.0, "arb_rear": 13.0,
        "ride_height_front": 10.0, "ride_height_rear": 17.0,
    },
    "monaco": {
        "spring_front": 10.0, "spring_rear": 18.0,
        "arb_front": 25.0, "arb_rear": 30.0,
        "ride_height_front": 16.0, "ride_height_rear": 23.0,
    },
    "silverstone": {
        "spring_front": 25.0, "spring_rear": 33.0,
        "arb_front": 25.0, "arb_rear": 30.0,
        "ride_height_front": 2.0, "ride_height_rear": 9.0,
    },
}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate V5.3 calibration")
    parser.add_argument("--quick", action="store_true", help="Only validate 3 reference circuits")
    parser.add_argument("--driver", type=float, default=1.0, help="Driver skill factor (default: 1.0)")
    args = parser.parse_args()

    circuits = ALL_CIRCUITS
    if args.quick:
        circuits = {k: v for k, v in ALL_CIRCUITS.items() if k in ["monza", "monaco", "silverstone"]}

    print("=" * 80)
    print(f"  VALIDAZIONE V5.3 — {len(circuits)} Circuiti con Calibrazione Completa")
    if args.driver != 1.0:
        print(f"  ⚠️  driver_skill = {args.driver} (non-standard)")
    print("=" * 80)

    results = []
    total_pct = 0
    max_pct = 0
    max_name = ""
    min_pct = 999
    min_name = ""

    for name, cfg in sorted(circuits.items()):
        susp = SUSP_SETUPS[cfg["susp_source"]]

        r = integrate_lap_hd(
            circuit_id=cfg["circuit_id"],
            aero_setup={"front_wing": cfg["front_wing"], "rear_wing": cfg["rear_wing"]},
            mass_kg=798 + cfg["fuel_kg"],
            tyre_compound=cfg["compound"],
            driver_skill=args.driver,
            suspension_setup=susp,
            verbose=False,
        )

        sim_time = r["lap_time_s"]
        ref_time = cfg["ref_time"]
        delta = sim_time - ref_time
        pct = abs(delta) / ref_time * 100

        total_pct += pct
        if pct > max_pct:
            max_pct = pct
            max_name = name
        if pct < min_pct:
            min_pct = pct
            min_name = name

        flag = "✅" if pct < 0.5 else ("🟡" if pct < 1.0 else "🔴")
        results.append((name, ref_time, sim_time, delta, pct, flag))
        print(f"  {name:>15s}: ref={ref_time:.3f}s sim={sim_time:.3f}s Δ={delta:+.3f}s ({pct:.2f}%) {flag}")

    avg_pct = total_pct / len(results)
    print(f"\n{'='*80}")
    print(f"  📊 ERRORE MEDIO: {avg_pct:.2f}%")
    print(f"  📊 MIGLIORE: {min_name} ({min_pct:.2f}%)")
    print(f"  📊 PEGGIORE: {max_name} ({max_pct:.2f}%)")
    print(f"  📊 SOTTO 0.5%: {sum(1 for r in results if r[4] < 0.5)}/{len(results)}")
    print(f"  📊 SOTTO 1.0%: {sum(1 for r in results if r[4] < 1.0)}/{len(results)}")
    if args.driver != 1.0:
        print(f"  ⚠️  driver_skill = {args.driver} (non-standard, ref times are for driver_skill=1.0)")
    print(f"{'='*80}")

    # Return exit code based on result
    if avg_pct > 0.5:
        print("\n❌ FAILED: Average error > 0.5%")
        return 1
    elif avg_pct > 0.3:
        print("\n⚠️  WARNING: Average error > 0.3% but < 0.5%")
        return 0
    else:
        print("\n✅ PASSED: Average error < 0.3%")
        return 0