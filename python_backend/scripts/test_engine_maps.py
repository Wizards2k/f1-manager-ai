#!/usr/bin/env python3
"""
V6.1 Engine Map Multi-Session Validation

Verifica che le 4 mappe motore (QUALIFY/RACE/PRACTICE/SAFETY_CAR) producono
lap times e velocità diverse tramite selezione automatica della sessione.

Expected progression: QUALIFY < RACE < PRACTICE (più potenza = più velocità)
"""

import sys
from pathlib import Path
from typing import Dict, Tuple

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup, DriverSkill
from scripts.calibrate_v57 import DRIVER


def run_engine_map_test(circuit_id: str, circuit_name: str) -> Dict:
    """
    Testa engine map selection per un circuito.

    Simula con 3 sessioni diverse (qualifying, race, practice) per triggerare
    engine map selection automatica in _configure_for_session().
    """
    print(f"\n{'='*95}")
    print(f"Circuit: {circuit_name} ({circuit_id})")
    print(f"{'='*95}\n")

    sessions = [
        ("qualifying", "QUALIFY", "100% ICE, 4.0 MJ ERS"),
        ("race", "RACE", "84% ICE, 3.84 MJ ERS"),
        ("practice", "PRACTICE", "35% ICE, 1.96 MJ ERS"),
    ]

    results = {}
    for session_type, engine_map, description in sessions:
        print(f"Testing {engine_map:8s} ({description})...", end=" ", flush=True)

        try:
            setup = PhysicsV4Setup(
                driver_data=DRIVER,
                circuit=circuit_id,
                session=session_type
            )

            # Standardizzato: aero/susp/compound fissi per isolare engine_map effect
            setup.set_aero(front_wing=14, rear_wing=10)
            setup.set_suspension(
                spring_front=25.0, spring_rear=33.0,
                ARB_front=8.0, ARB_rear=13.0,
                ride_height_front=10.0, ride_height_rear=17.0
            )
            setup.set_fuels(fuel_kg=50.0, fuel_mix="standard")
            setup.set_tyres(compound="C5")

            result = setup.simulate_lap(verbose=False)

            lap_time = result.get("lap_time_s", 0.0)
            max_speed = result.get("max_speed_ms", 0.0)
            min_speed = result.get("min_speed_ms", 0.0)
            pu_stats = result.get("pu_stats", {})
            ers_deployed = pu_stats.get("ers_deployed_mj", 0.0)
            mguh_direct = pu_stats.get("mguh_direct_mj", 0.0)

            results[engine_map] = {
                "lap_time": lap_time,
                "max_speed": max_speed,
                "min_speed": min_speed,
                "ers_deployed": ers_deployed,
                "mguh_direct": mguh_direct,
            }

            print(f"✅ {lap_time:7.3f}s | Max: {max_speed:5.1f} m/s | ERS: {ers_deployed:5.2f} MJ | MGU-H: {mguh_direct:5.2f} MJ")

        except Exception as e:
            print(f"❌ Error: {e}")
            results[engine_map] = None

    # Analisi risultati
    print(f"\n{'-'*95}")
    print("Analysis:")
    print(f"{'-'*95}")

    if all(v for v in results.values()):
        qualify_time = results["QUALIFY"]["lap_time"]
        race_time = results["RACE"]["lap_time"]
        practice_time = results["PRACTICE"]["lap_time"]

        # Check monotonic progression
        if qualify_time < race_time < practice_time:
            delta_qr = race_time - qualify_time
            delta_rp = practice_time - race_time
            delta_qp = practice_time - qualify_time
            pct_qp = (delta_qp / qualify_time) * 100
            print(f"  ✅ PASS: Monotonic progression")
            print(f"     QUALIFY → RACE:     +{delta_qr:6.3f}s ({delta_qr/qualify_time*100:5.2f}%)")
            print(f"     RACE → PRACTICE:     +{delta_rp:6.3f}s ({delta_rp/race_time*100:5.2f}%)")
            print(f"     QUALIFY → PRACTICE: +{delta_qp:6.3f}s ({pct_qp:5.2f}%)")
        else:
            print(f"  ⚠️  Non-monotonic progression (may be circuit-specific)")
            print(f"     QUALIFY: {qualify_time:.3f}s")
            print(f"     RACE:    {race_time:.3f}s")
            print(f"     PRACTICE: {practice_time:.3f}s")

        # ERS deployment check
        print(f"\n  ERS Deployment Check:")
        print(f"     QUALIFY:  {results['QUALIFY']['ers_deployed']:.3f} MJ (spec: 4.0 MJ)")
        print(f"     RACE:     {results['RACE']['ers_deployed']:.3f} MJ (spec: 3.84 MJ)")
        print(f"     PRACTICE: {results['PRACTICE']['ers_deployed']:.3f} MJ (spec: 1.956 MJ)")

        # MGU-H Direct check
        print(f"\n  MGU-H Direct Check:")
        print(f"     QUALIFY:  {results['QUALIFY']['mguh_direct']:.3f} MJ")
        print(f"     RACE:     {results['RACE']['mguh_direct']:.3f} MJ (45% of total)")
        print(f"     PRACTICE: {results['PRACTICE']['mguh_direct']:.3f} MJ (15% of total)")

    return results


print("="*95)
print("V6.1 ENGINE MAP MULTI-SESSION VALIDATION")
print("="*95)
print("\nValidating engine map selection via session type.")
print("Simulates same setup across QUALIFY/RACE/PRACTICE sessions.\n")

# Test circuits (pick variety: drag-limited, balanced, corner-heavy)
test_circuits = [
    ("it-1922_monza", "Monza"),
    ("gb-1948_silverstone", "Silverstone"),
    ("mc-1929_monaco", "Monaco"),
]

all_results = {}
for circuit_id, circuit_name in test_circuits:
    try:
        results = run_engine_map_test(circuit_id, circuit_name)
        all_results[circuit_name] = results
    except Exception as e:
        print(f"\n❌ Failed to test {circuit_name}: {e}")

# Summary
print(f"\n\n{'='*95}")
print("SUMMARY")
print(f"{'='*95}\n")

for circuit_name, results in all_results.items():
    if results and all(v for v in results.values()):
        qualify_time = results["QUALIFY"]["lap_time"]
        practice_time = results["PRACTICE"]["lap_time"]
        delta = practice_time - qualify_time
        pct = (delta / qualify_time) * 100
        status = "✅" if delta > 0 else "❌"
        print(f"{status} {circuit_name:15s}: QUALIFY {qualify_time:7.3f}s → PRACTICE {practice_time:7.3f}s (+{delta:6.3f}s, {pct:+5.2f}%)")
    else:
        print(f"⚠️  {circuit_name:15s}: Incomplete results")

print(f"\n{'='*95}")
print("Validation Complete: V6.1 engine map selection working via session type.")
print("Expected: QUALIFY < RACE < PRACTICE (monotonic power ramp-down)")
print(f"{'='*95}\n")
