#!/usr/bin/env python3
from __future__ import annotations
"""
Validate V5.6 calibration — simulate all 24 circuits and check error.

NON-REGRESSION REFERENCE SCRIPT
================================
This script is the official reference for validating the V5.6 physics engine.
It MUST be run after any change to the physics engine to verify that the
calibration is still within the target error (<0.5% average).

V5.6 uses the FULL PhysicsV4Setup pipeline with all car components:
  - AeroSetup: front_wing, rear_wing, bwing (slider 1-20°)
  - SuspensionSetup: spring_front/rear, arb_front/rear, ride_height_front/rear (slider values)
  - PowerUnitSetup: ERS mode "quali_deploy" (full 4 MJ/lap)
  - TyreSetup: per-circuit SOFT compound (from pirelli_package.nomination.soft)
  - FuelSetup: 20kg (qualifying)
  - DriverSkill: quali_skill=1.0 (average driver, no bonus/penalty)
  - Push level: 10 (zero penalty — qualifying reference)

Parameters calibrated:
  - Aero: front_wing, rear_wing (per circuit)
  - Bwing: 10° default (per circuit, not yet individually calibrated)
  - Suspension: spring_front/rear, arb_front/rear, ride_height_front/rear
    (3 categories: low-DF/Monza, high-DF/Monaco, medium-DF/Silverstone)
  - mu_mechanical: per-circuit grip calibration
  - Compound: per-circuit SOFT compound (calibration reference)
    V5.6: The soft is the calibration reference — mu_mechanical is calibrated
    for the soft compound of each circuit. Other compounds scale via MU_BASE ratio.
  - Fuel: 20kg (qualifying)

NOT calibrated (fixed values):
  - driver_skill = 1.0 (average driver, no bonus/penalty)
  - push_level = 10 (zero penalty — qualifying reference)
  - ers_power_fraction = 1.0 (full ERS deployment via "quali_deploy")
  - reference_pull_strength = 0.0 (disabled)

Architecture:
  PhysicsV4Setup.simulate_lap()
    → integrate_lap_hd() → optimal lap time (push=10, driver_skill=1.0)
    + push_penalty (push_level < 10) → final lap time with driver conservatism
    + driver_skill (< 1.0) → slower lap time due to less grip/power

Usage:
    python validate_v56.py              # Full validation (24 circuits)
    python validate_v56.py --quick       # Quick validation (3 reference circuits)
    python validate_v56.py --driver 1.05 # Test with driver_skill=1.05 (+5%)
    python validate_v56.py --push 8      # Test with push_level=8 (adds penalty)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup, DriverSkill
from lap_simulator.push_penalty import compute_push_penalty
from lap_simulator.data_types import CircuitConfig

# All 24 circuits with optimal setups
ALL_CIRCUITS = {
    "baku": {
        "circuit_id": "az-2016_baku",
        "front_wing": 12.0, "rear_wing": 14.0,
        "compound": "C6", "fuel_kg": 20.0,
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
        "compound": "C3", "fuel_kg": 20.0,
        "ref_time": 89.841,
        "susp_source": "monza",
    },
    "melbourne": {
        "circuit_id": "au-1953_melbourne",
        "front_wing": 18.0, "rear_wing": 22.0,
        "compound": "C5", "fuel_kg": 20.0,
        "ref_time": 75.096,
        "susp_source": "silverstone",
    },
    "yas_marina": {
        "circuit_id": "ae-2009_yas_marina",
        "front_wing": 18.0, "rear_wing": 22.0,
        "compound": "C5", "fuel_kg": 20.0,
        "ref_time": 82.207,
        "susp_source": "silverstone",
    },
    "barcelona": {
        "circuit_id": "es-1991_barcelona",
        "front_wing": 22.0, "rear_wing": 26.0,
        "compound": "C3", "fuel_kg": 20.0,
        "ref_time": 71.546,
        "susp_source": "silverstone",
    },
    "jeddah": {
        "circuit_id": "sa-2021_jeddah",
        "front_wing": 12.0, "rear_wing": 14.0,
        "compound": "C5", "fuel_kg": 20.0,
        "ref_time": 87.294,
        "susp_source": "monza",
    },
    "singapore": {
        "circuit_id": "sg-2008_singapore",
        "front_wing": 34.0, "rear_wing": 38.0,
        "compound": "C5", "fuel_kg": 20.0,
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
        "compound": "C5", "fuel_kg": 20.0,
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
        "compound": "C5", "fuel_kg": 20.0,
        "ref_time": 75.372,
        "susp_source": "monaco",
    },
    "monza": {
        "circuit_id": "it-1922_monza",
        "front_wing": 12.0, "rear_wing": 14.0,
        "compound": "C5", "fuel_kg": 20.0,
        "ref_time": 78.869,
        "susp_source": "monza",
    },
    "montreal": {
        "circuit_id": "ca-1978_montreal",
        "front_wing": 22.0, "rear_wing": 26.0,
        "compound": "C6", "fuel_kg": 20.0,
        "ref_time": 70.899,
        "susp_source": "silverstone",
    },
    "imola": {
        "circuit_id": "it-1953_imola",
        "front_wing": 18.0, "rear_wing": 22.0,
        "compound": "C6", "fuel_kg": 20.0,
        "ref_time": 74.670,
        "susp_source": "silverstone",
    },
    "mexico_city": {
        "circuit_id": "mx-1962_mexico_city",
        "front_wing": 22.0, "rear_wing": 26.0,
        "compound": "C5", "fuel_kg": 20.0,
        "ref_time": 75.586,
        "susp_source": "silverstone",
    },
    "miami": {
        "circuit_id": "us-2022_miami",
        "front_wing": 18.0, "rear_wing": 22.0,
        "compound": "C5", "fuel_kg": 20.0,
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
        "compound": "C5", "fuel_kg": 20.0,
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
        "compound": "C5", "fuel_kg": 20.0,
        "ref_time": 107.934,
        "susp_source": "monza",
    },
}

# Optimal suspension setups (SLIDER values)
# These are the same values used in calibration — they map to real F1 values
# via slider_to_real() in car_setup.py
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

# Default bwing per circuit category (not yet individually calibrated)
BWING_DEFAULTS = {
    "monza": 5.0,       # Low DF — minimal bwing
    "monaco": 18.0,     # High DF — maximum bwing
    "silverstone": 10.0, # Medium DF — balanced bwing
}


def _get_push_penalty(push_level: int, circuit_id: str) -> float:
    """Compute push penalty for a given push level.
    
    push_level=10 → 0.0s (qualifying reference)
    push_level<10 → additive penalty
    """
    if push_level >= 10:
        return 0.0
    
    # Use default CircuitConfig for penalty calculation
    config = CircuitConfig()
    penalty = compute_push_penalty(
        push_level=push_level,
        driver_qualifica=50,   # Average driver
        driver_gara=50,
        driver_costanza=50,
        is_qualifying=True,
        circuit_id=circuit_id,
        driver_id="reference",
        lap_number=1,
        config=config,
    )
    return penalty


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate V5.6 calibration")
    parser.add_argument("--quick", action="store_true", help="Only validate 3 reference circuits")
    parser.add_argument("--driver", type=float, default=1.0, help="Driver skill factor (default: 1.0)")
    parser.add_argument("--push", type=int, default=10, help="Push level 1-10 (default: 10 = qualifying)")
    args = parser.parse_args()

    circuits = ALL_CIRCUITS
    if args.quick:
        circuits = {k: v for k, v in ALL_CIRCUITS.items() if k in ["monza", "monaco", "silverstone"]}

    print("=" * 90)
    print(f"  VALIDAZIONE V5.6 — {len(circuits)} Circuiti con Pipeline Completa")
    print(f"  Pipeline: PhysicsV4Setup → integrate_lap_hd + push_penalty")
    if args.driver != 1.0:
        print(f"  ⚠️  driver_skill = {args.driver} (non-standard)")
    if args.push != 10:
        print(f"  ⚠️  push_level = {args.push} (non-standard, ref is push=10)")
    print("=" * 90)

    # Create a generic driver with the requested skill
    driver = DriverSkill(
        name="Reference",
        quali_skill=args.driver,
        race_skill=args.driver,
        braking_skill=1.0,
        cornering_skill=1.0,
        throttle_skill=1.0,
        consistency=1.0,
        front_wing_offset=0,
        rear_wing_offset=0,
        brake_bias_offset=0.0,
    )

    results = []
    total_pct = 0
    max_pct = 0
    max_name = ""
    min_pct = 999
    min_name = ""

    for name, cfg in sorted(circuits.items()):
        susp = SUSP_SETUPS[cfg["susp_source"]]
        bwing = BWING_DEFAULTS[cfg["susp_source"]]

        # Build full car setup via PhysicsV4Setup
        setup = PhysicsV4Setup(
            driver_data=driver,
            circuit=cfg["circuit_id"],
            session="qualifying",
        )

        # Apply calibrated aero
        setup.set_aero(
            front_wing=cfg["front_wing"],
            rear_wing=cfg["rear_wing"],
            bwing=bwing,
        )

        # Apply calibrated suspension (slider values)
        setup.set_suspension(
            spring_front=susp["spring_front"],
            spring_rear=susp["spring_rear"],
            ARB_front=susp["arb_front"],
            ARB_rear=susp["arb_rear"],
            ride_height_front=susp["ride_height_front"],
            ride_height_rear=susp["ride_height_rear"],
        )

        # Apply calibrated fuel
        setup.set_fuels(fuel_kg=cfg["fuel_kg"], fuel_mix="rich")

        # Apply calibrated tyres (soft compound)
        setup.set_tyres(compound=cfg["compound"])

        # Apply ERS mode (quali_deploy = full 4 MJ/lap)
        setup.set_ers_mode("quali_deploy")

        # Simulate lap via full pipeline
        r = setup.simulate_lap(verbose=False)

        # Physics lap time from integrate_lap_hd
        physics_time = r["lap_time_s"]

        # Add push penalty (0.0 for push=10)
        push_penalty = _get_push_penalty(args.push, cfg["circuit_id"])
        sim_time = physics_time + push_penalty

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
        push_str = f" push={push_penalty:.3f}s" if push_penalty > 0 else ""
        results.append((name, ref_time, sim_time, delta, pct, flag, cfg["compound"]))
        print(f"  {name:>15s} ({cfg['compound']}): ref={ref_time:.3f}s sim={sim_time:.3f}s Δ={delta:+.3f}s ({pct:.2f}%) {flag}{push_str}")

    avg_pct = total_pct / len(results)
    print(f"\n{'='*90}")
    print(f"  📊 ERRORE MEDIO: {avg_pct:.2f}%")
    print(f"  📊 MIGLIORE: {min_name} ({min_pct:.2f}%)")
    print(f"  📊 PEGGIORE: {max_name} ({max_pct:.2f}%)")
    print(f"  📊 SOTTO 0.5%: {sum(1 for r in results if r[4] < 0.5)}/{len(results)}")
    print(f"  📊 SOTTO 1.0%: {sum(1 for r in results if r[4] < 1.0)}/{len(results)}")
    if args.driver != 1.0:
        print(f"  ⚠️  driver_skill = {args.driver} (non-standard, ref times are for driver_skill=1.0)")
    if args.push != 10:
        print(f"  ⚠️  push_level = {args.push} (non-standard, ref times are for push=10)")
    print(f"{'='*90}")

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


if __name__ == "__main__":
    sys.exit(main())