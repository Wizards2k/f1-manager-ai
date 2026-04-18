#!/usr/bin/env python3
"""Audit rapido HD waypoints - versione diretta."""

import json
from pathlib import Path

# Percorso assoluto diretto
CIRCUITS_DIR = Path("/Users/wizards/Sviluppo/F1 Manager AI/python_backend/data/circuits/2025")

# Circuiti critici
CRITICAL_CHECKS = {
    "mc-1929_monaco": {"type": "hairpin", "min": 11.0, "max": 18.0},
    "jp-1962_suzuka": {"type": "130R", "min": 750.0, "max": 900.0},
    "it-1922_monza": {"type": "parabolica", "min": 350.0, "max": 550.0},
}

print("=" * 80)
print("AUDIT HD WAYPOINTS - F1 2025")
print("=" * 80)
print(f"\n📁 Directory circuiti: {CIRCUITS_DIR}")
print(f"   Esiste: {CIRCUITS_DIR.exists()}")
print("")

# Lista file HD
hd_files = sorted(CIRCUITS_DIR.glob("*_HD.json"))
print(f"📋 File HD trovati: {len(hd_files)}")
print("")

# Analizza primi 5 file per test
for hd_file in hd_files[:5]:
    circuit_id = hd_file.stem.replace("_HD", "")
    print(f"Analizzando {circuit_id}...")
    
    with open(hd_file, 'r') as f:
        data = json.load(f)
    
    waypoints = data.get("waypoints", [])  # Campo corretto!
    print(f"  Waypoints totali: {len(waypoints)}")
    
    # Estrai raggi
    radii = [wp.get("radius_m") for wp in waypoints if wp.get("radius_m") and wp.get("radius_m") > 0]
    print(f"  Raggi validi: {len(radii)}")
    
    if radii:
        min_r = min(radii)
        max_r = max(radii)
        avg_r = sum(radii) / len(radii)
        print(f"  Raggi: min={min_r:.1f}m, max={max_r:.1f}m, avg={avg_r:.1f}m")
        
        # Check critico
        if circuit_id in CRITICAL_CHECKS:
            check = CRITICAL_CHECKS[circuit_id]
            if check["type"] == "hairpin":
                if min_r > check["max"]:
                    print(f"  ⚠️  {check['type']}: {min_r:.1f}m (DOVREBBE essere {check['min']}-{check['max']}m)")
                else:
                    print(f"  ✅ {check['type']}: {min_r:.1f}m (OK)")
            
            elif check["type"] == "130R":
                if max_r < check["min"]:
                    print(f"  ⚠️  {check['type']}: {max_r:.1f}m (DOVREBBE essere {check['min']}-{check['max']}m)")
                else:
                    print(f"  ✅ {check['type']}: {max_r:.1f}m (OK)")
    
    print("")

print("\n✅ Test completato!")
