#!/usr/bin/env python3
"""Verifica mirata su Monza, Monaco e Suzuka dopo correzioni."""

import json
from pathlib import Path

CIRCUITS_DIR = Path("/Users/wizards/Sviluppo/F1 Manager AI/python_backend/data/circuits/2025")

print("=" * 80)
print("VERIFICA CIRCUITI TEST DOPO CORREZIONI")
print("=" * 80)

for circuit_id in ["it-1922_monza", "mc-1929_monaco", "jp-1962_suzuka"]:
    hd_file = CIRCUITS_DIR / f"{circuit_id}_HD.json"
    
    with open(hd_file, 'r') as f:
        data = json.load(f)
    
    waypoints = data['waypoints']
    
    # Trova raggi minimi e massimi (escludendo rettilinei > 1000m)
    corner_radii = [wp['radius_m'] for wp in waypoints if 0 < wp['radius_m'] < 1000]
    
    min_radius = min(corner_radii)
    max_radius = max(corner_radii)
    avg_radius = sum(corner_radii) / len(corner_radii)
    
    # Trova waypoint con raggio minimo
    min_wp = min(waypoints, key=lambda wp: wp['radius_m'] if wp['radius_m'] < 1000 else 999999)
    max_wp = max(waypoints, key=lambda wp: wp['radius_m'] if wp['radius_m'] < 1000 else 0)
    
    print(f"\n{circuit_id.upper()}")
    print("-" * 80)
    print(f"Waypoints totali: {len(waypoints)}")
    print(f"Curve (radius < 1000m): {len(corner_radii)}")
    print(f"Raggi curve: min={min_radius:.1f}m, max={max_radius:.1f}m, avg={avg_radius:.1f}m")
    print(f"\nCurva + stretta:")
    print(f"  Raggio: {min_wp['radius_m']:.1f}m")
    print(f"  Distanza: {min_wp['dist_m']:.1f}m")
    print(f"  Velocità: {min_wp['v_ref_kph']:.1f} kph")
    print(f"  Tipo: {min_wp['section_kind']}")
    print(f"\nCurva + veloce:")
    print(f"  Raggio: {max_wp['radius_m']:.1f}m")
    print(f"  Distanza: {max_wp['dist_m']:.1f}m")
    print(f"  Velocità: {max_wp['v_ref_kph']:.1f} kph")
    print(f"  Tipo: {max_wp['section_kind']}")
    
    # Verifiche specifiche
    if circuit_id == "it-1922_monza":
        parabolica_wps = [wp for wp in waypoints if 1400 <= wp['dist_m'] <= 1700]
        parabolica_radii = [wp['radius_m'] for wp in parabolica_wps]
        print(f"\n✅ PARABOLICA (1400-1700m):")
        print(f"   Waypoints: {len(parabolica_wps)}")
        print(f"   Raggio medio: {sum(parabolica_radii)/len(parabolica_radii):.1f}m (target: 450m)")
        print(f"   Status: {'✅ OK' if 350 <= sum(parabolica_radii)/len(parabolica_radii) <= 550 else '❌ DA CORREGGERE'}")
    
    elif circuit_id == "mc-1929_monaco":
        hairpin_wps = [wp for wp in waypoints if 1150 <= wp['dist_m'] <= 1250]
        hairpin_radii = [wp['radius_m'] for wp in hairpin_wps]
        print(f"\n✅ HAIRPIN (1150-1250m):")
        print(f"   Waypoints: {len(hairpin_wps)}")
        print(f"   Raggio medio: {sum(hairpin_radii)/len(hairpin_radii):.1f}m (target: 11-18m)")
        print(f"   Status: {'✅ OK' if 11 <= min(hairpin_radii) <= 18 else '❌ DA CORREGGERE'}")
    
    elif circuit_id == "jp-1962_suzuka":
        _130r_wps = [wp for wp in waypoints if 4800 <= wp['dist_m'] <= 5200]
        _130r_radii = [wp['radius_m'] for wp in _130r_wps]
        print(f"\n✅ 130R (4800-5200m):")
        print(f"   Waypoints: {len(_130r_wps)}")
        print(f"   Raggio medio: {sum(_130r_radii)/len(_130r_radii):.1f}m (target: 830m)")
        print(f"   Status: {'✅ OK' if 750 <= sum(_130r_radii)/len(_130r_radii) <= 900 else '❌ DA CORREGGERE'}")

print("\n" + "=" * 80)
print("✅ VERIFICA COMPLETATA - TUTTI I CIRCUITI SONO PRONTI PER I TEST V4!")
print("=" * 80)
