#!/usr/bin/env python3
"""
validate_v5.py — Validazione Physics Engine V5.0 con Speed Trace comparativo.

Genera grafici Speed Trace (velocità vs distanza) confrontando il simulatore
con i dati reali di TracingInsights per i 5 circuiti campioni.

Usage:
    python3 python_backend/scripts/validate_v5.py
    python3 python_backend/scripts/validate_v5.py --circuit monaco
    python3 python_backend/scripts/validate_v5.py --all
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lap_simulator.physics_engine.integrator.waypoint_integrator import integrate_lap_hd
from lap_simulator.physics_engine.calibration.telemetry_bridge import TelemetryBridge, CIRCUIT_MAP

# Output directory
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "circuits" / "validation_reports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Reference lap times (TracingInsights 2025 Qualifying, NOR)
REFERENCE_TIMES = {
    # 5 circuiti originali
    "mc-1929_monaco": 69.954,
    "it-1922_monza": 78.869,
    "jp-1962_suzuka": 86.995,
    "gb-1948_silverstone": 85.010,
    "be-1925_spa_francorchamps": 100.562,
    # 19 circuiti aggiuntivi (V5.1)
    "ae-2009_yas_marina": 82.207,
    "at-1969_spielberg": 63.971,
    "au-1953_melbourne": 75.096,
    "az-2016_baku": 101.117,
    "bh-2002_sakhir": 89.841,
    "br-1940_sao_paulo": 69.511,
    "ca-1978_montreal": 70.899,
    "cn-2004_shanghai": 90.641,
    "es-1991_barcelona": 71.546,
    "hu-1986_budapest": 75.372,
    "it-1953_imola": 74.670,
    "mx-1962_mexico_city": 75.586,
    "nl-1948_zandvoort": 68.662,
    "qa-2004_lusail": 79.387,
    "sa-2021_jeddah": 87.294,
    "sg-2008_singapore": 89.158,
    "us-2012_austin": 92.510,
    "us-2022_miami": 86.204,
    "us-2023_las_vegas": 107.934,
}

CIRCUIT_NAMES = {
    "mc-1929_monaco": "Monaco",
    "it-1922_monza": "Monza",
    "jp-1962_suzuka": "Suzuka",
    "gb-1948_silverstone": "Silverstone",
    "be-1925_spa_francorchamps": "Spa",
    "ae-2009_yas_marina": "Yas Marina",
    "at-1969_spielberg": "Spielberg",
    "au-1953_melbourne": "Melbourne",
    "az-2016_baku": "Baku",
    "bh-2002_sakhir": "Sakhir",
    "br-1940_sao_paulo": "São Paulo",
    "ca-1978_montreal": "Montreal",
    "cn-2004_shanghai": "Shanghai",
    "es-1991_barcelona": "Barcelona",
    "hu-1986_budapest": "Budapest",
    "it-1953_imola": "Imola",
    "mx-1962_mexico_city": "Mexico City",
    "nl-1948_zandvoort": "Zandvoort",
    "qa-2004_lusail": "Lusail",
    "sa-2021_jeddah": "Jeddah",
    "sg-2008_singapore": "Singapore",
    "us-2012_austin": "Austin",
    "us-2022_miami": "Miami",
    "us-2023_las_vegas": "Las Vegas",
}


def run_simulation(circuit_id: str, aero_setup: Dict = None,
                   reference_pull_strength: float = 0.02,
                   pu_lookup_blend: float = 0.0) -> Dict:
    """Esegue la simulazione per un circuito."""
    if aero_setup is None:
        aero_setup = {"front_wing": 20.0, "rear_wing": 22.0}
    
    return integrate_lap_hd(
        circuit_id=circuit_id,
        aero_setup=aero_setup,
        verbose=False,
        reference_pull_strength=reference_pull_strength,
        pu_lookup_blend=pu_lookup_blend,
    )


def generate_speed_trace_report(circuit_id: str) -> Dict:
    """Genera un report completo per un circuito."""
    circuit_name = CIRCUIT_NAMES.get(circuit_id, circuit_id)
    real_time = REFERENCE_TIMES.get(circuit_id, 0.0)
    
    print(f"\n{'='*70}")
    print(f"  VALIDAZIONE V5.0: {circuit_name.upper()} ({circuit_id})")
    print(f"{'='*70}")
    
    # 1. Carica Reference Pull
    ref_pull = TelemetryBridge.load_reference_pull(circuit_id)
    if ref_pull is None:
        print(f"  ❌ Nessun Reference Pull per {circuit_id}")
        bridge = TelemetryBridge()
        ref_pull_obj = bridge.get_reference_pull(circuit_id)
        if ref_pull_obj is None:
            print(f"  ❌ Impossibile scaricare dati")
            return {}
        bridge.save_reference_pull(circuit_id, ref_pull_obj)
        ref_pull = TelemetryBridge.load_reference_pull(circuit_id)
    
    ref_data = ref_pull.get("data", {})
    ref_dist = ref_data.get("dist_m", [])
    ref_speed = ref_data.get("speed_kph", [])
    ref_throttle = ref_data.get("throttle_pct", [])
    ref_brake = ref_data.get("brake_pct", [])
    
    # 2. Esegui simulazioni
    setups = [
        {"name": "Low DF", "setup": {"front_wing": 12.0, "rear_wing": 14.0}},
        {"name": "Neutral", "setup": {"front_wing": 20.0, "rear_wing": 22.0}},
        {"name": "High DF", "setup": {"front_wing": 28.0, "rear_wing": 32.0}},
    ]
    
    results = {}
    for s in setups:
        r = run_simulation(circuit_id, aero_setup=s["setup"],
                           reference_pull_strength=0.02,
                           pu_lookup_blend=0.0)
        results[s["name"]] = {
            "lap_time_s": r["lap_time_s"],
            "v_max_kph": r["v_max_kph"],
            "v_min_kph": r["v_min_kph"],
            "v_avg_kph": r["v_avg_kph"],
            "telemetry": r["telemetry"],
        }
    
    # 3. Calcola errori
    neutral_time = results["Neutral"]["lap_time_s"]
    if real_time > 0:
        error_pct = abs(neutral_time - real_time) / real_time * 100
    else:
        error_pct = float('inf')
    
    print(f"  ⏱️ Tempo reale: {real_time:.3f}s")
    print(f"  🏁 Sim Neutral: {neutral_time:.3f}s (errore: {error_pct:.2f}%)")
    
    for name, r in results.items():
        delta = r["lap_time_s"] - real_time
        print(f"  📊 {name:10s}: {r['lap_time_s']:.3f}s ({delta:+.3f}s) "
              f"V_max={r['v_max_kph']:.0f} V_min={r['v_min_kph']:.0f}")
    
    # 4. Speed Trace comparison
    sim_telemetry = results["Neutral"]["telemetry"]
    sim_dist = [t["distance_m"] for t in sim_telemetry]
    sim_speed = [t["velocity_kph"] for t in sim_telemetry]
    
    # Calcola errore per punto
    if ref_dist and sim_dist:
        # Interpola velocità reale sulla griglia simulata
        ref_speed_interp = np.interp(sim_dist, ref_dist, ref_speed)
        speed_error = np.mean(np.abs(np.array(sim_speed) - ref_speed_interp))
        speed_error_pct = speed_error / np.mean(ref_speed_interp) * 100
        print(f"  📈 Errore medio velocità: {speed_error:.1f} km/h ({speed_error_pct:.1f}%)")
    
    # 5. Salva report JSON
    report = {
        "circuit_id": circuit_id,
        "circuit_name": circuit_name,
        "real_lap_time_s": real_time,
        "sim_lap_time_s": neutral_time,
        "error_pct": round(error_pct, 2),
        "setups": {name: {
            "lap_time_s": r["lap_time_s"],
            "v_max_kph": r["v_max_kph"],
            "v_min_kph": r["v_min_kph"],
        } for name, r in results.items()},
        "reference_pull": {
            "driver": ref_pull.get("driver", "?"),
            "lap_time_s": ref_pull.get("lap_time_s", 0),
            "mu_mechanical": ref_pull.get("mu_mechanical", 0),
            "k_wing_coupling": ref_pull.get("k_wing_coupling", 0),
        },
        "speed_trace": {
            "sim_dist": sim_dist[:100],  # Primi 100 punti per report
            "sim_speed": sim_speed[:100],
            "ref_dist": ref_dist[:100] if ref_dist else [],
            "ref_speed": ref_speed[:100] if ref_speed else [],
        },
    }
    
    report_path = OUTPUT_DIR / f"{circuit_id}_v5_validation.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  📄 Report salvato: {report_path}")
    
    return report


def main():
    parser = argparse.ArgumentParser(description="Validate Physics Engine V5.0")
    parser.add_argument("--circuit", "-c", choices=list(CIRCUIT_MAP.keys()) + ["all"],
                        default="all", help="Circuit to validate")
    parser.add_argument("--all", action="store_true", help="Validate all 5 circuits")
    args = parser.parse_args()
    
    if args.circuit == "all" or args.all:
        circuits = list(CIRCUIT_MAP.keys())
    else:
        circuits = [args.circuit]
    
    all_reports = []
    for key in circuits:
        circuit_id = CIRCUIT_MAP[key]["circuit_id"]
        report = generate_speed_trace_report(circuit_id)
        if report:
            all_reports.append(report)
    
    # Summary
    if all_reports:
        print(f"\n{'='*70}")
        print("  📊 VALIDAZIONE V5.0 - RIEPILOGO")
        print(f"{'='*70}")
        print(f"  {'Circuito':<15} {'Reale':>8} {'Sim':>8} {'Errore':>8} {'Target':>8}")
        print(f"  {'─'*15} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
        
        total_error = 0
        for r in all_reports:
            err = r["error_pct"]
            total_error += err
            target = "✅" if err < 0.5 else "⚠️" if err < 2.0 else "❌"
            print(f"  {r['circuit_name']:<15} {r['real_lap_time_s']:>8.3f} "
                  f"{r['sim_lap_time_s']:>8.3f} {err:>7.2f}% {target:>8}")
        
        avg_error = total_error / len(all_reports)
        print(f"\n  📈 Errore medio globale: {avg_error:.2f}%")
        if avg_error < 0.5:
            print("  ✅ Target < 0.5% RAGGIUNTO!")
        elif avg_error < 2.0:
            print("  ⚠️ Target < 0.5% NON raggiunto, ma entro 2%")
        else:
            print("  ❌ Errore troppo alto")
    
    print(f"\n{'='*70}")
    print("  ✅ Validazione V5.0 completata!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()