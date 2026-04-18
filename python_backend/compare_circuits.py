#!/usr/bin/env python3
"""
Analisi Comparativa Circuiti - Physics V4

Confronta performance su 5 circuiti con setup ottimale vs tutto errato.
Mostra:
- Tempo giro per circuito
- Delta setup
- Sensibilità del circuito all'assetto
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple

# Aggiungi root al path
sys.path.insert(0, str(Path(__file__).parent))

from lap_simulator.physics_v4.core.car_setup import (
    PhysicsV4Setup, AeroSetup, SuspensionSetup, TyreSetup
)
from lap_simulator.physics_v4.core.team_driver_data import get_team_data, get_driver_data


def setup_optimal() -> Dict:
    """Setup ottimale generico."""
    return {
        "aero": {"front_wing": 20.0, "rear_wing": 22.0},
        "suspension": {"spring_front": 15.0, "spring_rear": 18.0, "arb_front": 4.0, "arb_rear": 6.0},
        "tyres": {"compound": "C2", "pressure_front": 2.3, "pressure_rear": 2.1},
    }


def setup_terrible() -> Dict:
    """Setup terribile - tutto errato."""
    return {
        "aero": {"front_wing": 5.0, "rear_wing": 8.0},  # Troppo basso
        "suspension": {"spring_front": 5.0, "spring_rear": 8.0, "arb_front": 1.0, "arb_rear": 2.0},  # Troppo morbido
        "tyres": {"compound": "C6", "pressure_front": 1.8, "pressure_rear": 1.6},  # Pressione bassa
    }


def apply_setup(setup_config: PhysicsV4Setup, setup_dict: Dict) -> None:
    """Applica setup alla configurazione."""
    # Aero
    aero = setup_dict["aero"]
    setup_config.car.aero.front_wing = aero["front_wing"]
    setup_config.car.aero.rear_wing = aero["rear_wing"]

    # Suspension
    susp = setup_dict["suspension"]
    setup_config.car.suspension.spring_front = susp["spring_front"]
    setup_config.car.suspension.spring_rear = susp["spring_rear"]
    setup_config.car.suspension.arb_front = susp["arb_front"]
    setup_config.car.suspension.arb_rear = susp["arb_rear"]

    # Tyres
    tyre = setup_dict["tyres"]
    setup_config.car.tyres.compound = tyre["compound"]
    setup_config.car.tyres.pressure_front = tyre["pressure_front"]
    setup_config.car.tyres.pressure_rear = tyre["pressure_rear"]


def simulate_circuit(circuit_id: str, setup_dict: Dict, setup_name: str = "Setup") -> Dict:
    """Simula un circuito con un setup specifico."""
    try:
        # Carica dati team/driver
        team_data = get_team_data("mclaren")
        driver_data = get_driver_data("Lando Norris")

        # Crea setup
        setup_config = PhysicsV4Setup(
            team_data=team_data,
            driver_data=driver_data,
            circuit=circuit_id,
            session="qualifying"
        )

        # Applica setup
        apply_setup(setup_config, setup_dict)

        # Simula
        result = setup_config.simulate_lap(verbose=False)

        return {
            "circuit": circuit_id,
            "setup": setup_name,
            "lap_time_s": result.get("lap_time_s", 0),
            "sector_times": result.get("sector_times", [0, 0, 0]),
            "v_max": result.get("v_max_kph", 0),
            "v_min": result.get("v_min_kph", 0),
        }
    except Exception as e:
        return {
            "circuit": circuit_id,
            "setup": setup_name,
            "error": str(e),
            "lap_time_s": None,
        }


def main():
    """Analizza 5 circuiti."""
    circuits = [
        "it-1922_monza",
        "mc-1929_monaco",
        "jp-1962_suzuka",
        "gb-1948_silverstone",
        "be-1925_spa_francorchamps",
    ]

    circuit_names = {
        "it-1922_monza": "Monza",
        "mc-1929_monaco": "Monaco",
        "jp-1962_suzuka": "Suzuka",
        "gb-1948_silverstone": "Silverstone",
        "be-1925_spa_francorchamps": "Spa",
    }

    print("=" * 100)
    print("ANALISI COMPARATIVA CIRCUITI - PHYSICS V4")
    print("=" * 100)

    results = []

    for circuit in circuits:
        circuit_name = circuit_names.get(circuit, circuit)
        print(f"\n📍 {circuit_name}")
        print("-" * 100)

        # Simula setup ottimale
        print(f"  Simulando setup OTTIMALE...")
        result_opt = simulate_circuit(circuit, setup_optimal(), "OPTIMAL")
        results.append(result_opt)

        if result_opt.get("lap_time_s"):
            print(f"    ✅ Tempo: {result_opt['lap_time_s']:.3f}s")
            print(f"       Settori: {result_opt['sector_times'][0]:.3f}s / {result_opt['sector_times'][1]:.3f}s / {result_opt['sector_times'][2]:.3f}s")
            print(f"       V_max: {result_opt['v_max']:.1f} kph | V_min: {result_opt['v_min']:.1f} kph")
        else:
            print(f"    ❌ Errore: {result_opt.get('error', 'Unknown')}")

        # Simula setup terribile
        print(f"  Simulando setup TERRIBILE...")
        result_ter = simulate_circuit(circuit, setup_terrible(), "TERRIBLE")
        results.append(result_ter)

        if result_ter.get("lap_time_s"):
            print(f"    ✅ Tempo: {result_ter['lap_time_s']:.3f}s")
            print(f"       Settori: {result_ter['sector_times'][0]:.3f}s / {result_ter['sector_times'][1]:.3f}s / {result_ter['sector_times'][2]:.3f}s")
            print(f"       V_max: {result_ter['v_max']:.1f} kph | V_min: {result_ter['v_min']:.1f} kph")

            # Calcola delta
            if result_opt.get("lap_time_s"):
                delta_s = result_ter["lap_time_s"] - result_opt["lap_time_s"]
                delta_pct = (delta_s / result_opt["lap_time_s"]) * 100
                print(f"\n    🔴 DELTA: +{delta_s:.3f}s (+{delta_pct:.2f}%)")
        else:
            print(f"    ❌ Errore: {result_ter.get('error', 'Unknown')}")

    # Sommario finale
    print("\n" + "=" * 100)
    print("SOMMARIO FINALE")
    print("=" * 100)

    summary_data = {}
    for circuit in circuits:
        circuit_name = circuit_names.get(circuit, circuit)
        opt_results = [r for r in results if r["circuit"] == circuit and r["setup"] == "OPTIMAL"]
        ter_results = [r for r in results if r["circuit"] == circuit and r["setup"] == "TERRIBLE"]

        if opt_results and ter_results:
            opt = opt_results[0]
            ter = ter_results[0]

            if opt.get("lap_time_s") and ter.get("lap_time_s"):
                delta = ter["lap_time_s"] - opt["lap_time_s"]
                delta_pct = (delta / opt["lap_time_s"]) * 100

                summary_data[circuit_name] = {
                    "optimal_s": opt["lap_time_s"],
                    "terrible_s": ter["lap_time_s"],
                    "delta_s": delta,
                    "delta_pct": delta_pct,
                }

                print(f"{circuit_name:15} │ Ottimale: {opt['lap_time_s']:7.3f}s │ Terribile: {ter['lap_time_s']:7.3f}s │ Δ: +{delta:6.3f}s (+{delta_pct:5.2f}%)")

    print("=" * 100)

    # Stampa statistiche
    if summary_data:
        deltas = [v["delta_s"] for v in summary_data.values()]
        deltas_pct = [v["delta_pct"] for v in summary_data.values()]

        print(f"\n📊 STATISTICHE:")
        print(f"   Media delta: {sum(deltas) / len(deltas):6.3f}s ({sum(deltas_pct) / len(deltas_pct):5.2f}%)")
        print(f"   Max delta: {max(deltas):6.3f}s ({max(deltas_pct):5.2f}%)")
        print(f"   Min delta: {min(deltas):6.3f}s ({min(deltas_pct):5.2f}%)")


if __name__ == "__main__":
    main()
