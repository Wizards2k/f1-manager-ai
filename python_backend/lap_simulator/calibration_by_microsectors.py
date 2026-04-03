"""
Calibration by Microsectors — Calibra il motore sezione per sezione

Approccio:
1. Carica telemetria reale di UN circuito (Monza)
2. Per ogni microsettore (segmento da 5m), estrai parametri fisici reali
3. Simula quel microsettore e confronta: simulazione vs realtà
4. Se non corrisponde, il modello fisico ha un errore
5. Correggi il modello finché ogni microsettore non è perfetto

Source of Truth: Telemetria reale F1 2025
Obiettivo: Riprodurre ESATTAMENTE il comportamento microsettore per microsettore
"""

import json
import os
import math
from typing import Dict, List, Any, Tuple, Optional

# ============================================================================
# CONSTANTS
# ============================================================================

MASS_KG = 798.0
G = 9.81
RHO = 1.225
ROLLING_RESISTANCE = 0.011
DRIVETRAIN_EFF = 0.895

# ============================================================================
# LOAD TELEMETRY
# ============================================================================

def load_circuit_telemetry(circuit_id: str = "it-1922_monza") -> Optional[Dict[str, Any]]:
    """Carica la telemetria completa di un circuito."""
    path = f"python_backend/data/circuits/2025/{circuit_id}_Telemetry.json"

    if not os.path.exists(path):
        print(f"❌ File non trovato: {path}")
        return None

    with open(path, 'r') as f:
        return json.load(f)


def load_circuit_hd_waypoints(circuit_id: str = "it-1922_monza") -> Optional[List[Dict[str, Any]]]:
    """Carica i waypoints HD (5m) di un circuito se disponibili."""
    path = f"python_backend/data/circuits/2025/{circuit_id}_HD.json"

    if not os.path.exists(path):
        print(f"⚠️  Waypoints HD non trovati: {path}")
        return None

    with open(path, 'r') as f:
        data = json.load(f)
        return data.get('waypoints', [])


# ============================================================================
# EXTRACT PHYSICS FROM MICROSECTORS
# ============================================================================

def extract_microsector_physics(waypoints: List[Dict], start_idx: int, end_idx: int) -> Dict[str, Any]:
    """
    Estrai parametri fisici da un microsettore (range di waypoints).

    Calcola:
    - Velocità media, min, max
    - Accelerazione media
    - Raggio di curvatura
    - G laterali
    - G di frenata
    - Grip utilizzato (stimato)
    """

    if start_idx >= end_idx or end_idx > len(waypoints):
        return {}

    micro = waypoints[start_idx:end_idx+1]

    # Velocità
    v_values = [wp.get('v_kph', 0) for wp in micro]
    v_entry = v_values[0]
    v_exit = v_values[-1]
    v_min = min(v_values)
    v_max = max(v_values)
    v_avg = sum(v_values) / len(v_values) if v_values else 0

    # Distanza totale
    dist_m = micro[-1].get('dist_m', 0) - micro[0].get('dist_m', 0)

    # Tempo (assumendo velocità media costante)
    v_avg_ms = v_avg / 3.6
    dt_s = dist_m / v_avg_ms if v_avg_ms > 0.1 else 0.1

    # Accelerazione media
    v_entry_ms = v_entry / 3.6
    v_exit_ms = v_exit / 3.6
    dv_ms = v_exit_ms - v_entry_ms
    a_mean_g = (dv_ms / dt_s) / G if dt_s > 0.01 else 0

    # Raggio di curvatura (da waypoint se disponibile)
    radius_values = [wp.get('radius_m', 0) for wp in micro if wp.get('radius_m')]
    radius_m = radius_values[0] if radius_values else 0

    # G laterali all'apex (v_min)
    if radius_m > 0.1 and v_min > 0.1:
        v_min_ms = v_min / 3.6
        a_lat_g = (v_min_ms ** 2) / (radius_m * G)
    else:
        a_lat_g = 0

    # Grip utilizzato (da accelerazione laterale)
    mu_estimated = a_lat_g if a_lat_g > 0 else abs(a_mean_g)

    # DRS (da waypoint se disponibile)
    drs_active = any(wp.get('drs_active', False) for wp in micro)

    return {
        'start_idx': start_idx,
        'end_idx': end_idx,
        'length_m': dist_m,
        'dt_s': dt_s,
        'v_entry_kph': v_entry,
        'v_exit_kph': v_exit,
        'v_min_kph': v_min,
        'v_max_kph': v_max,
        'v_avg_kph': v_avg,
        'dv_kph': v_exit - v_entry,
        'a_mean_g': a_mean_g,
        'radius_m': radius_m,
        'a_lat_g': a_lat_g,
        'mu_estimated': mu_estimated,
        'drs_active': drs_active,
    }


# ============================================================================
# COMPARE WITH SIMULATION
# ============================================================================

def simulate_microsector(
    v_entry_kph: float,
    params: Dict[str, Any],
    length_m: float,
) -> Dict[str, Any]:
    """
    Simula un microsettore usando il modello fisico attuale.

    Restituisce: velocità exit, accelerazione, etc.
    """

    # Placeholder - da implementare con modello fisico vero
    # Per ora ritorna valori fittizi per mostrare l'approccio

    return {
        'v_exit_kph': v_entry_kph + 5,  # Placeholder
        'a_mean_g': 0.1,  # Placeholder
    }


# ============================================================================
# MAIN ANALYSIS
# ============================================================================

def main():
    circuit_id = "it-1922_monza"

    print("="*100)
    print(f"CALIBRATION BY MICROSECTORS — {circuit_id.upper()}")
    print("="*100)

    # Carica telemetria
    print(f"\n[1] Loading telemetry for {circuit_id}...")
    telemetry = load_circuit_telemetry(circuit_id)

    if not telemetry:
        return

    sections = telemetry.get('geometry', {}).get('sections', [])
    print(f"✓ Loaded {len(sections)} macro sections")

    # Carica waypoints HD
    print(f"\n[2] Loading HD waypoints...")
    waypoints = load_circuit_hd_waypoints(circuit_id)

    if not waypoints:
        print("⚠️  No HD waypoints available - analyzing macro sections only")

        # Analizza sezioni macro
        print(f"\n[3] ANALYSIS OF MACRO SECTIONS")
        print("="*100)
        print(f"{'Section':<25} {'Type':<20} {'v_entry':<10} {'v_exit':<10} {'Δv':<8} {'a_g':<8} {'a_lat':<8} {'DRS':<5}")
        print("-"*100)

        for i, section in enumerate(sections[:10]):
            name = section.get('name', f'Section {i}')
            kind = section.get('kind', 'Unknown')
            v_entry = section.get('v_entry_kph', 0)
            v_exit = section.get('v_exit_kph', 0)
            v_min = section.get('v_min_kph', 0)
            radius = section.get('radius_m', 0)
            drs = "✓" if section.get('drs_active', False) else ""

            # Calcola parametri
            v_entry_ms = v_entry / 3.6
            v_exit_ms = v_exit / 3.6
            v_min_ms = v_min / 3.6
            dt = section.get('dt_ref_s', 0.1)

            dv_ms = v_exit_ms - v_entry_ms
            a_g = (dv_ms / dt / G) if dt > 0 else 0

            if radius and radius > 0.1 and v_min_ms > 0.1:
                a_lat_g = (v_min_ms ** 2) / (radius * G)
            else:
                a_lat_g = 0

            print(f"{name:<25} {kind:<20} {v_entry:<10.1f} {v_exit:<10.1f} {v_exit-v_entry:<8.1f} {a_g:<8.3f} {a_lat_g:<8.3f} {drs:<5}")

        return

    print(f"✓ Loaded {len(waypoints)} HD waypoints")

    # Analizza microsettori
    print(f"\n[3] MICROSECTOR ANALYSIS")
    print("="*100)

    # Raggruppa per sezione macro
    microsectors = []
    current_section_idx = 0

    for i in range(len(waypoints) - 20):  # Step di 20 waypoints (~100m)
        micro = extract_microsector_physics(waypoints, i, i + 20)

        if micro:
            microsectors.append(micro)

    print(f"✓ Extracted {len(microsectors)} microsectors")

    # Mostra microsettori critici
    print(f"\n[4] CRITICAL MICROSECTORS FOR CALIBRATION")
    print("="*100)

    # 1. Microsettori a massima accelerazione (rettilineo + potenza)
    accel_microsectors = sorted(
        [m for m in microsectors if m['dv_kph'] > 5],
        key=lambda x: x['dv_kph'],
        reverse=True
    )

    if accel_microsectors:
        print(f"\n[A] MAXIMUM ACCELERATION MICROSECTORS")
        print(f"{'Idx':<5} {'v_entry':<10} {'v_exit':<10} {'Δv':<8} {'a_g':<8} {'len_m':<8} {'DRS':<5}")
        print("-"*50)
        for m in accel_microsectors[:5]:
            drs = "✓" if m['drs_active'] else ""
            print(
                f"{m['start_idx']:<5} "
                f"{m['v_entry_kph']:<10.1f} "
                f"{m['v_exit_kph']:<10.1f} "
                f"{m['dv_kph']:<8.1f} "
                f"{m['a_mean_g']:<8.3f} "
                f"{m['length_m']:<8.1f} "
                f"{drs:<5}"
            )

    # 2. Microsettori a massima decelerazione (frenata)
    decel_microsectors = sorted(
        [m for m in microsectors if m['dv_kph'] < -5],
        key=lambda x: x['dv_kph'],
    )

    if decel_microsectors:
        print(f"\n[B] MAXIMUM DECELERATION MICROSECTORS (BRAKING)")
        print(f"{'Idx':<5} {'v_entry':<10} {'v_exit':<10} {'Δv':<8} {'a_g':<8} {'len_m':<8}")
        print("-"*50)
        for m in decel_microsectors[:5]:
            print(
                f"{m['start_idx']:<5} "
                f"{m['v_entry_kph']:<10.1f} "
                f"{m['v_exit_kph']:<10.1f} "
                f"{m['dv_kph']:<8.1f} "
                f"{m['a_mean_g']:<8.3f} "
                f"{m['length_m']:<8.1f} "
            )

    # 3. Microsettori a massima laterale (curva)
    lateral_microsectors = sorted(
        [m for m in microsectors if m['a_lat_g'] > 0.5],
        key=lambda x: x['a_lat_g'],
        reverse=True
    )

    if lateral_microsectors:
        print(f"\n[C] MAXIMUM LATERAL G MICROSECTORS (CORNERING)")
        print(f"{'Idx':<5} {'v_apex':<10} {'radius':<10} {'a_lat_g':<8} {'mu_est':<8} {'len_m':<8}")
        print("-"*50)
        for m in lateral_microsectors[:5]:
            print(
                f"{m['start_idx']:<5} "
                f"{m['v_min_kph']:<10.1f} "
                f"{m['radius_m']:<10.1f} "
                f"{m['a_lat_g']:<8.3f} "
                f"{m['mu_estimated']:<8.3f} "
                f"{m['length_m']:<8.1f} "
            )

    # --- COMPARISON SIMULATION VS REALITY ---
    print(f"\n[5] SIMULATION VS REALITY COMPARISON")
    print("="*100)
    print("\nSelecting critical microsector for detailed analysis...")

    # Prendi il primo microsettore di accelerazione critica
    if accel_microsectors:
        critical = accel_microsectors[0]
        print(f"\nCritical microsector: idx {critical['start_idx']}-{critical['end_idx']}")
        print(f"  Real telemetry:")
        print(f"    v_entry: {critical['v_entry_kph']:.1f} km/h")
        print(f"    v_exit:  {critical['v_exit_kph']:.1f} km/h")
        print(f"    Δv:      {critical['dv_kph']:+.1f} km/h")
        print(f"    a_mean:  {critical['a_mean_g']:.3f}g")
        print(f"    length:  {critical['length_m']:.1f} m")
        print(f"    DRS:     {'ACTIVE' if critical['drs_active'] else 'off'}")

        print(f"\n  What simulation must reproduce:")
        print(f"    Given v_entry={critical['v_entry_kph']:.1f} km/h and {critical['length_m']:.0f}m of straight")
        print(f"    With DRS {'ACTIVE' if critical['drs_active'] else 'OFF'}")
        print(f"    Must reach v_exit = {critical['v_exit_kph']:.1f} km/h")
        print(f"    And achieve a_mean = {critical['a_mean_g']:.3f}g")
        print(f"\n  This is a HARD CONSTRAINT for the motor model")

    print(f"\n" + "="*100)
    print("NEXT STEP: Implement simulation and compare for each microsector")
    print("="*100)


if __name__ == "__main__":
    main()
