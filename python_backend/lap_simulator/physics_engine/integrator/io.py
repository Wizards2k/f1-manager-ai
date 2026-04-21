"""
Integrator I/O - Funzioni di caricamento dati per il waypoint integrator.

Estratte dal waypoint_integrator.py per modularizzazione.
"""

from pathlib import Path
from typing import Dict, List, Any
import json


def load_hd_waypoints(circuit_id: str) -> List[Dict]:
    """
    Carica waypoints HD per un circuito.
    
    I file sono in: python_backend/data/circuits/2025/{circuit_id}_HD.json
    
    Returns:
      Lista di waypoints con: dist_m, v_ref_kph, radius_m, slope_deg, etc.
    
    FIX V5.1: Deduplicate boundary waypoints. The HD data contains duplicate
    entries at section boundaries (same dist_m, different macro_sector_id).
    The boundary waypoint from the incoming section often carries the apex
    minimum radius (e.g. 40.6m) instead of the actual radius at that track
    position (e.g. ~1260m at corner entry). This causes catastrophic speed
    drops when the integrator uses the apex radius at a point where the car
    is still on the straight. We keep the waypoint with the LARGER radius,
    which corresponds to the outgoing/entry side of the boundary.
    """
    circuits_dir = Path(__file__).resolve().parents[3] / "data" / "circuits" / "2025"
    hd_file = circuits_dir / f"{circuit_id}_HD.json"
    
    if not hd_file.exists():
        raise FileNotFoundError(f"HD file non trovato: {hd_file}")
    
    with open(hd_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    raw_waypoints = data.get("waypoints", [])
    
    # FIX V5.2-offset: Handle duplicate waypoints at section boundaries.
    if len(raw_waypoints) > 1:
        deduped = [raw_waypoints[0]]
        for idx, wp in enumerate(raw_waypoints[1:], start=1):
            prev_dist = deduped[-1].get('dist_m', -999)
            wp_dist = wp.get('dist_m', -998)
            if abs(wp_dist - prev_dist) < 0.01:
                wp_copy = dict(wp)
                wp_copy['dist_m'] = prev_dist + 0.01
                r_out = deduped[-1].get('radius_m', 999999.0)
                r_in = wp_copy.get('radius_m', 999999.0)
                r_next = 999999.0
                if idx + 1 < len(raw_waypoints):
                    r_next = raw_waypoints[idx + 1].get('radius_m', 999999.0)
                if r_in < 100 and r_out > 400 and r_next > 400:
                    wp_copy['radius_m'] = r_out
                deduped.append(wp_copy)
            else:
                deduped.append(wp)
        raw_waypoints = deduped
    
    return raw_waypoints


def load_reference_sections(circuit_id: str) -> Dict[str, Dict[str, Any]]:
    """Carica le sezioni di riferimento della telemetria per il circuito."""
    circuits_dir = Path(__file__).resolve().parents[3] / "data" / "circuits" / "2025"
    telemetry_file = circuits_dir / f"{circuit_id}_Telemetry.json"

    if not telemetry_file.exists():
        return {}

    with open(telemetry_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    sections = (((data or {}).get("geometry") or {}).get("sections") or [])
    return {
        str(section.get("id")): section
        for section in sections
        if section.get("id")
    }


def find_section_id_by_distance(reference_sections: Dict[str, Dict[str, Any]], distance_m: float) -> str:
    """Trova la sezione telemetria che contiene una data distanza."""
    for sid, section in reference_sections.items():
        start = section.get('start_m', 0.0)
        end = section.get('end_m', 0.0)
        if start <= distance_m < end:
            return sid
    return ''


def load_soft_compound(circuit_id: str) -> str:
    """Carica la mescola SOFT dal file Telemetry del circuito.
    
    La telemetria di qualifica usa sempre la gomma SOFT, che varia per circuito
    (es. C3 a Sakhir, C4 a Spa, C5 a Monza, C6 a Monaco).
    Questo è il compound di riferimento per la calibrazione mu_mechanical.
    
    Returns:
      Compound ID (es. "C5") oppure "C3" come fallback.
    """
    circuits_dir = Path(__file__).resolve().parents[3] / "data" / "circuits" / "2025"
    telemetry_file = circuits_dir / f"{circuit_id}_Telemetry.json"
    
    if not telemetry_file.exists():
        return "C3"
    
    try:
        with open(telemetry_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        nomination = (((data or {}).get("tyres") or {}).get("pirelli_package") or {}).get("nomination") or {}
        soft = nomination.get("soft")
        if soft:
            return soft
        
        dry_compounds = (((data or {}).get("tyre_allocation") or {}).get("dry_compounds") or {})
        soft = dry_compounds.get("soft")
        if soft:
            return soft
        
        return "C3"
    except (json.JSONDecodeError, KeyError, TypeError):
        return "C3"
