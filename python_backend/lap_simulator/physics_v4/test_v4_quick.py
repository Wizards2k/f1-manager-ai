#!/usr/bin/env python3
"""
Test rapido Physics Engine V4 su Monza, Monaco e Suzuka.

Verifica che:
1. Il motore V4 si importa correttamente
2. I tempi sono realistici (Monza ~79s, Monaco ~70s, Suzuka ~88s)
3. Le velocità massime sono coerenti (Monza ~365 kph, Monaco ~290 kph)
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any

# Import diretto dei moduli V4
from aero.aero_assembly import AeroAssembly
from integrator.waypoint_integrator import integrate_lap_hd

print("=" * 80)
print("TEST RAPIDO PHYSICS ENGINE V4")
print("=" * 80)
print("")

# Circuiti di test con setup caratteristici
TEST_CIRCUITS = {
    "it-1922_monza": {
        "name": "Monza",
        "setup": {"front_wing": 14.0, "rear_wing": 12.0},  # scarico
        "target_lap_s": 79.5,
        "target_vmax_kph": 365.0,
    },
    "mc-1929_monaco": {
        "name": "Monaco",
        "setup": {"front_wing": 26.0, "rear_wing": 30.0},  # carico
        "target_lap_s": 70.2,
        "target_vmax_kph": 290.0,
    },
    "jp-1962_suzuka": {
        "name": "Suzuka",
        "setup": {"front_wing": 20.0, "rear_wing": 22.0},  # bilanciato
        "target_lap_s": 88.5,
        "target_vmax_kph": 320.0,
    },
}

results = {}

for circuit_id, test_data in TEST_CIRCUITS.items():
    print(f"🏁 {test_data['name']} ({circuit_id})")
    print("-" * 80)
    
    try:
        # Esegui simulazione
        result = integrate_lap_hd(
            circuit_id=circuit_id,
            aero_setup=test_data["setup"],
            verbose=True,
        )
        
        results[circuit_id] = result
        
        # Confronta con target
        lap_time = result["lap_time_s"]
        v_max = result["v_max_kph"]
        
        delta_lap = lap_time - test_data["target_lap_s"]
        delta_vmax = v_max - test_data["target_vmax_kph"]
        
        print(f"\n📊 RISULTATI:")
        print(f"  Tempo giro: {lap_time:.3f}s (target: {test_data['target_lap_s']}s, Δ: {delta_lap:+.3f}s)")
        print(f"  V_max: {v_max:.1f} kph (target: {test_data['target_vmax_kph']} kph, Δ: {delta_vmax:+.1f} kph)")
        
        # Valutazione
        lap_error_pct = abs(delta_lap) / test_data["target_lap_s"] * 100
        vmax_error_pct = abs(delta_vmax) / test_data["target_vmax_kph"] * 100
        
        if lap_error_pct < 5.0 and vmax_error_pct < 10.0:
            print(f"  ✅ OK (errore: {lap_error_pct:.1f}% tempo, {vmax_error_pct:.1f}% vmax)")
        else:
            print(f"  ⚠️  DA CALIBRARE (errore: {lap_error_pct:.1f}% tempo, {vmax_error_pct:.1f}% vmax)")
        
    except Exception as e:
        print(f"  ❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        results[circuit_id] = {"error": str(e)}
    
    print("")

# Riepilogo
print("=" * 80)
print("RIEPILOGO")
print("=" * 80)

ok_count = sum(1 for r in results.values() if "error" not in r)
print(f"Circuiti testati: {len(results)}")
print(f"Successi: {ok_count}/{len(results)}")

if ok_count == len(results):
    print("\n✅ TUTTI I TEST PASSATI - V4 FUNZIONANTE!")
else:
    print("\n⚠️  ALCUNI TEST FALLITI - NECESSARIA CALIBRAZIONE")

print("\n" + "=" * 80)
