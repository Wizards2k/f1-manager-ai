#!/usr/bin/env python3
"""Corregge i raggi delle curve nei waypoints HD basandosi sulla velocità di riferimento.

Formula: radius_m = v_ref² / (g_lat × 3.6²)

Dove g_lat è l'accelerazione laterale target:
- VerySlowCorner: 4.5g (curve strette, frenata)
- SlowCorner: 4.8g
- MediumCorner: 5.0g
- FastCorner: 5.2g (curve veloci, grip alto)
"""

import json
from pathlib import Path

# Mappatura g_lat per tipo di curva
# Valori calibrati su telemetria F1 2025
G_LAT_MAP = {
    'VerySlowCorner': 3.2,  # Curve strette (Variante, Chicane) - F1 frena molto!
    'SlowCorner': 3.8,      # Curve lente (Curione, Lesmo)
    'MediumCorner': 4.5,    # Curve medie (Ascari)
    'FastCorner': 5.0,      # Curve veloci (Parabolica)
}

def correct_radius(v_ref_kph: float, section_kind: str) -> float:
    """Calcola raggio corretto dalla velocità di riferimento."""
    if section_kind not in G_LAT_MAP:
        return 999999.0  # Rettilineo
    
    g_lat = G_LAT_MAP[section_kind]
    radius = (v_ref_kph ** 2) / (g_lat * 9.81 * 3.6 ** 2)
    return radius

def fix_hd_waypoints(circuit_id: str):
    """Corregge i raggi per un circuito HD."""
    hd_path = Path(f'python_backend/data/circuits/2025/{circuit_id}_HD.json')
    
    if not hd_path.exists():
        print(f"❌ File non trovato: {hd_path}")
        return
    
    with open(hd_path, 'r') as f:
        hd_data = json.load(f)
    
    modified = 0
    for wp in hd_data['waypoints']:
        section_kind = wp.get('section_kind', 'Straight')
        if section_kind in G_LAT_MAP:
            v_ref = wp.get('v_ref_kph', 100)
            radius_old = wp.get('radius_m', 999999)
            radius_new = correct_radius(v_ref, section_kind)
            
            # Aggiorna solo se il raggio è irrealistico (< 50m per curve non lentissime)
            if radius_old < 50 and section_kind != 'VerySlowCorner':
                wp['radius_m'] = radius_new
                modified += 1
            elif radius_old < 30 and section_kind == 'VerySlowCorner':
                wp['radius_m'] = radius_new
                modified += 1
    
    # Salva file corretto
    with open(hd_path, 'w') as f:
        json.dump(hd_data, f, indent=2)
    
    print(f"✅ {circuit_id}: {modified} waypoints correggi")

if __name__ == '__main__':
    # Correggi Monza
    fix_hd_waypoints('it-1922_monza')
    print("✅ Monza HD waypoints corretti!")
