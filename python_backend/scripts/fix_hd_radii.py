#!/usr/bin/env python3
"""
Script per correggere i raggi delle curve nei waypoints HD.

Problema: alcuni raggi sono irrealisticamente bassi (es. 27.9m a Monza sec_02).
Soluzione: forzare un raggio minimo di 85m per le curve molto lente.

Questo allinea i dati HD alla realtà fisica del circuito.
"""

import json
from pathlib import Path
from typing import Dict, List


def fix_curve_radii(circuit_id: str, min_radius_m: float = 85.0):
    """
    Corregge i raggi delle curve nei waypoints HD.
    
    Args:
        circuit_id: ID del circuito (es. 'it-1922_monza')
        min_radius_m: raggio minimo consentito (default 85m)
    """
    hd_path = Path(__file__).parent.parent / "data" / "circuits" / "2025" / f"{circuit_id}_HD.json"
    
    with open(hd_path, 'r', encoding='utf-8') as f:
        hd_data = json.load(f)
    
    waypoints = hd_data.get('waypoints', [])
    
    print(f"Processing {circuit_id}: {len(waypoints)} waypoints")
    
    # Conta correzioni
    corrections = 0
    total_corrected = 0.0
    
    for wp in waypoints:
        radius_m = wp.get('radius_m', 999999.0)
        section_kind = wp.get('section_kind', 'Straight')
        macro_sector = wp.get('macro_sector_id', '')
        # Determine actual min radius to apply for this waypoint
        current_min_radius = min_radius_m
        if circuit_id == 'mc-1929_monaco':
            if macro_sector == 'sec_08':
                current_min_radius = max(min_radius_m, 16.0) # Hairpin needs to be slow but not too tight
            elif macro_sector == 'sec_11':
                current_min_radius = max(min_radius_m, 22.0) # Portier/Mirabeau
            elif macro_sector == 'sec_17':
                current_min_radius = max(min_radius_m, 28.0) # Rascasse/Anthony Noghes
        elif circuit_id == 'jp-1962_suzuka':
            if macro_sector == 'sec_08':
                current_min_radius = max(min_radius_m, 55.0) # Hairpin
            elif macro_sector == 'sec_13':
                current_min_radius = max(min_radius_m, 75.0) # Casio Triangle
        
        # Applica correzione solo alle curve (non rettilinei)
        if section_kind != 'Straight' and radius_m < current_min_radius:
            old_radius = radius_m
            wp['radius_m'] = current_min_radius
            corrections += 1
            total_corrected += (current_min_radius - old_radius)
    
    print(f"Corrected {corrections} waypoints")
    print(f"Total radius increase: {total_corrected:.1f}m")
    print(f"Average correction: {total_corrected/corrections:.2f}m" if corrections > 0 else "No corrections")
    
    # Salva file corretto
    with open(hd_path, 'w', encoding='utf-8') as f:
        json.dump(hd_data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved corrected HD waypoints to: {hd_path}")
    
    return corrections


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python fix_hd_radii.py <circuit_id> [min_radius_m]")
        print("Example: python fix_hd_radii.py it-1922_monza 85.0")
        sys.exit(1)
    
    circuit_id = sys.argv[1]
    min_radius = float(sys.argv[2]) if len(sys.argv) > 2 else 85.0
    
    fix_curve_radii(circuit_id, min_radius)
