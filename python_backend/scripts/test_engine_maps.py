#!/usr/bin/env python3
"""V6.1-2b: Test engine maps (QUALIFY/RACE/PRACTICE) — verifica che
simulazioni su diverse mappe motore producono tempi e velocità coerenti.

Expected: t_QUALIFY < t_RACE < t_PRACTICE
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup
from scripts.calibrate_v57 import ALL_CIRCUITS, SUSP_SETUPS, DRIVER

# Test su 3 circuiti rappresentativi
TEST_CIRCUITS = ["monza", "silverstone", "monaco"]

# Mappe da testare in ordine
MAPS = ["QUALIFY", "RACE", "PRACTICE"]


def test_circuit_maps(circuit_name, verbose=True):
    """Testa tutte le mappe per un circuito."""
    if circuit_name not in ALL_CIRCUITS:
        print(f"  ❌ Circuito non trovato: {circuit_name}")
        return None

    cfg = ALL_CIRCUITS[circuit_name]
    circuit_id = cfg["circuit_id"]

    if verbose:
        print(f"\n{'='*70}")
        print(f"  {circuit_name.upper()} — Engine Map Test")
        print(f"{'='*70}")
        print(f"  {'Map':<12} {'Lap Time':<12} {'Max Speed':<12} {'ERS Deploy':<12}")
        print(f"  {'-'*70}")

    results = {}

    for engine_map_name in MAPS:
        # Crea setup con sessione qualifica
        setup = PhysicsV4Setup(driver_data=DRIVER, circuit=circuit_id, session="qualifying")

        # Configura aero/susp/tyres standard
        setup.set_aero(front_wing=20.0, rear_wing=22.0, bwing=10.0)
        setup.set_suspension(**SUSP_SETUPS[cfg["susp_source"]])
        setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
        setup.set_tyres(compound=cfg["compound"])

        # Setta engine map via set_ers_mode (V6.1 wiring)
        mode_map = {
            "QUALIFY": "quali_deploy",
            "RACE": "balanced",
            "PRACTICE": "race_save",
        }
        setup.set_ers_mode(mode_map.get(engine_map_name, "quali_deploy"))

        # Simula
        result = setup.simulate_lap(verbose=False)

        lap_time = result.get("lap_time_s", 0)
        max_speed = result.get("max_speed", 0)
        energy_trace = result.get("energy_trace", [])

        # Calcola ERS deploy da energy trace
        ers_deploy_total = 0.0
        for step in energy_trace:
            ers_deploy_total += step.get("mj_deploy", 0)

        results[engine_map_name] = {
            "lap_time": lap_time,
            "max_speed": max_speed,
            "ers_deploy": ers_deploy_total,
        }

        if verbose:
            print(f"  {engine_map_name:<12} {lap_time:<12.3f} {max_speed:<12.2f} {ers_deploy_total:<12.2f}")

    # Verifica ordinamento
    times = [results[m]["lap_time"] for m in MAPS]
    is_monotonic = all(times[i] <= times[i+1] for i in range(len(times)-1))

    if verbose:
        status = "✅" if is_monotonic else "❌"
        ordering_str = " < ".join([f"{m}({results[m]['lap_time']:.2f}s)" for m in MAPS])
        print(f"  {status} Ordinamento: {ordering_str}")

    return {
        "circuit": circuit_name,
        "results": results,
        "monotonic": is_monotonic,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--circuit", type=str, help="Test solo un circuito")
    parser.add_argument("--all", action="store_true", help="Test tutti i 24 circuiti (lento)")
    args = parser.parse_args()

    if args.circuit:
        circuits = [args.circuit]
    elif args.all:
        circuits = list(ALL_CIRCUITS.keys())
    else:
        circuits = TEST_CIRCUITS

    print("\n" + "="*70)
    print(f"  V6.1-2b: Engine Maps Test ({len(circuits)} circuiti)")
    print("="*70)

    results = []
    for circuit in circuits:
        r = test_circuit_maps(circuit, verbose=True)
        if r:
            results.append(r)

    # Summary
    print("\n" + "="*70)
    print(f"  SUMMARY ({len(results)} circuiti)")
    print("="*70)
    print(f"  {'Circuit':<16} {'QUALIFY':<12} {'RACE':<12} {'PRACTICE':<12} {'Status':<8}")
    print("  " + "-"*70)

    monotonic_count = 0
    for r in results:
        t_q = r["results"]["QUALIFY"]["lap_time"]
        t_r = r["results"]["RACE"]["lap_time"]
        t_p = r["results"]["PRACTICE"]["lap_time"]
        is_mono = r["monotonic"]
        monotonic_count += is_mono

        status = "✅" if is_mono else "❌"
        print(f"  {r['circuit']:<16} {t_q:<12.3f} {t_r:<12.3f} {t_p:<12.3f} {status:<8}")

    print("  " + "-"*70)
    print(f"\n  Monotonic: {monotonic_count}/{len(results)} (expected: t_QUALIFY < t_RACE < t_PRACTICE)")
    print(f"\n  ✅ Test PASSED" if monotonic_count == len(results) else f"\n  ⚠️  {len(results)-monotonic_count} circuito(i) non monotonica(i)")

    # Salva report
    report_path = ROOT / "engine_maps_test_report.json"
    with open(report_path, "w") as f:
        json.dump(
            {
                "test_circuits": circuits,
                "results": results,
                "monotonic_count": monotonic_count,
                "total": len(results),
            },
            f,
            indent=2,
        )
    print(f"\n  Report salvato: {report_path}")


if __name__ == "__main__":
    main()
