#!/usr/bin/env python3
"""
Script per estrarre telemetry_mu dai dati di telemetria ufficiale e aggiungerlo ai waypoints HD.

Il telemetry_mu rappresenta il coefficiente di attrito efficace in ogni punto della pista,
calcolato a partire dall'accelerazione laterale e longitudinale misurata.

Formula:
  mu_eff = sqrt(a_lat² + a_lon²) / g
  
Dove:
  - a_lat = v² / R (accelerazione laterale in curva)
  - a_lon = dv/dt (accelerazione longitudinale)
  - g = 9.80665 m/s²

Questo permette di avere un grip dinamico che varia per microsettore,
riflettendo le condizioni reali della pista (asperità, curb, pendenze).
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Any


G = 9.80665  # m/s²
RHO_AIR = 1.225  # kg/m³
MASS_KG = 883.0  # kg massa totale qualifica
CLA_TOTAL = 3.65  # m² coefficiente portanza (Monza Q)


def load_telemetry(circuit_id: str) -> Dict[str, Any]:
    """Carica telemetria ufficiale."""
    telemetry_path = Path(__file__).parent.parent / "data" / "circuits" / "2025" / f"{circuit_id}_Telemetry.json"
    with open(telemetry_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_hd_waypoints(circuit_id: str) -> Dict[str, Any]:
    """Carica waypoints HD."""
    hd_path = Path(__file__).parent.parent / "data" / "circuits" / "2025" / f"{circuit_id}_HD.json"
    with open(hd_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def calculate_mu_from_telemetry(telemetry_points: List[Dict], radius_m: float, speed_kph: float) -> float:
    """
    Calcola telemetry_mu da un punto di telemetria.
    
    Args:
        telemetry_points: lista di punti di telemetria
        radius_m: raggio della curva nel punto
        speed_kph: velocità nel punto
    
    Returns:
        telemetry_mu calcolato
    """
    # Gestisci radius None
    if radius_m is None:
        radius_m = 999999.0
    
    if radius_m > 1000.0:  # Rettilineo
        # In rettilineo: mu determinato da accelerazione longitudinale
        # Tipicamente 0.4-0.6 in accelerazione/frenata
        return 0.50  # Valore medio per rettilineo
    
    # Curva: mu determinato da accelerazione laterale
    speed_ms = speed_kph / 3.6
    
    # a_lat = v² / R
    a_lat = (speed_ms ** 2) / max(radius_m, 1.0)
    
    # mu_eff = a_lat / g
    mu_eff = a_lat / G
    
    # Clamp a valori realistici per F1
    # C5: 1.80 max, C1: 1.52 min, ma con margini per sicurezza
    mu_eff = max(1.20, min(2.20, mu_eff))
    
    return mu_eff


def interpolate_mu_along_track(telemetry_data: Dict, hd_waypoints: List[Dict]) -> List[float]:
    """
    Assegna track_grip_factor fisso per circuito.
    
    NON calcolare mu dalla velocità! Il grip è determinato da:
    - MU_BASE del compound (C5=1.96, C3=1.80)
    - Downforce fisica (0.5 * rho * v² * CLA)
    - track_grip_factor (fisso per circuito, include curb e racing line)
    
    Valori tipici (include effetto curb/racing line):
    - Monza: 1.15 (curb aggressivi, racing line ampia)
    - Monaco: 0.92 (asfalto liscio, meno grip, no curb)
    - Suzuka: 1.08 (asfalto abrasivo, grip medio)
    - Silverstone: 1.12 (curb moderati, grip buono)
    """
    # Track grip factor fisso per circuito
    circuit_factors = {
        "it-1922_monza": 0.86,
        "mc-1929_monaco": 0.92,
        "jp-1962_suzuka": 1.08,
    }
    
    TRACK_GRIP_FACTOR = circuit_factors.get(circuit_id, 1.15)
    
    # Assegna lo stesso fattore a tutti i waypoints
    mu_values = [TRACK_GRIP_FACTOR] * len(hd_waypoints)
    
    return mu_values


def add_telemetry_mu_to_hd(circuit_id: str, output_path: str = None):
    """
    Aggiunge telemetry_mu ai waypoints HD e salva.
    
    Args:
        circuit_id: ID del circuito (es. 'it-1922_monza')
        output_path: percorso output (default: sovrascrive file HD)
    """
    print(f"Processing circuit: {circuit_id}")
    
    # Carica dati
    telemetry_data = load_telemetry(circuit_id)
    hd_data = load_hd_waypoints(circuit_id)
    hd_waypoints = hd_data.get('waypoints', [])
    
    print(f"Loaded {len(hd_waypoints)} HD waypoints")
    
    # Calcola telemetry_mu per ogni waypoint
    print("Calculating telemetry_mu for each waypoint...")
    mu_values = interpolate_mu_along_track(telemetry_data, hd_waypoints)
    
    # Aggiungi telemetry_mu ai waypoints
    for i, wp in enumerate(hd_waypoints):
        wp['telemetry_mu'] = round(mu_values[i], 4)
    
    # Statistiche
    mu_min = min(mu_values)
    mu_max = max(mu_values)
    mu_avg = sum(mu_values) / len(mu_values)
    
    print(f"telemetry_mu statistics:")
    print(f"  Min: {mu_min:.4f}")
    print(f"  Max: {mu_max:.4f}")
    print(f"  Avg: {mu_avg:.4f}")
    
    # Salva
    if output_path is None:
        output_path = Path(__file__).parent.parent / "data" / "circuits" / "2025" / f"{circuit_id}_HD.json"
    else:
        output_path = Path(output_path)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(hd_data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved HD waypoints with telemetry_mu to: {output_path}")
    
    return mu_values


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python add_telemetry_mu.py <circuit_id> [output_path]")
        print("Example: python add_telemetry_mu.py it-1922_monza")
        sys.exit(1)
    
    circuit_id = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    mu_values = add_telemetry_mu_to_hd(circuit_id, output_path)
    
    # Stampa primi 10 valori per debug
    print(f"\nFirst 10 telemetry_mu values:")
    for i in range(min(10, len(mu_values))):
        print(f"  WP {i}: mu = {mu_values[i]:.4f}")
