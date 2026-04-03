"""
MONZA Microsector-by-Microsector Calibration

Calibra il motore sezione per sezione usando i dati reali di telemetria Monza.

Approccio:
1. Carica waypoints HD (5m) di Monza
2. Raggruppa in microsettori (100m circa)
3. Per ogni microsettore:
   - Estrai dati reali (v_entry, v_exit, a_mean, etc.)
   - Simula con il motore fisico
   - Confronta: simulazione vs realtà
   - Se non corrisponde: identifica quale parametro del motore è sbagliato
4. Quando TUTTI i microsettori corrispondono → Monza calibrato

Source of Truth: Telemetria reale F1 2025 Monza
Setup: CLA=2.90, CDA=0.90 (ultra-low downforce)
"""

import json
import os
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# ============================================================================
# CONSTANTS
# ============================================================================

MASS_KG = 798.0
G = 9.81
RHO = 1.225
DRIVETRAIN_EFF = 0.895

# Setup noto per Monza
MONZA_SETUP = {
    'cla': 2.90,      # Ultra-low downforce
    'cda': 0.90,      # Minimal drag
    'fuel_kg': 5.0,
    'tyre': 'C3',
    'grip_base': 1.70,  # C3 compound
}

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Microsector:
    """Microsettore: piccolo segmento di pista (100-200m)."""
    idx: int
    start_dist_m: float
    end_dist_m: float
    length_m: float

    # Real telemetry
    v_entry_kph: float
    v_exit_kph: float
    v_min_kph: float
    v_max_kph: float
    v_avg_kph: float

    # Physics
    a_mean_g: float
    radius_m: float
    a_lat_g: float

    # Setup
    drs_active: bool
    throttle_pct: float
    brake_pct: float


# ============================================================================
# LOAD DATA
# ============================================================================

def load_monza_waypoints() -> Optional[List[Dict[str, Any]]]:
    """Carica waypoints HD di Monza."""
    path = "python_backend/data/circuits/2025/it-1922_monza_HD.json"
    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        return None

    with open(path, 'r') as f:
        data = json.load(f)
        return data.get('waypoints', [])


def load_monza_telemetry() -> Optional[Dict[str, Any]]:
    """Carica telemetria macro di Monza."""
    path = "python_backend/data/circuits/2025/it-1922_monza_Telemetry.json"
    if not os.path.exists(path):
        return None

    with open(path, 'r') as f:
        return json.load(f)


# ============================================================================
# EXTRACT MICROSECTORS
# ============================================================================

def extract_microsectors(waypoints: List[Dict[str, Any]], step_size: int = 20) -> List[Microsector]:
    """
    Estrai microsettori da waypoints (raggruppa ogni ~100m).

    Args:
        waypoints: Lista di waypoint HD (ogni 5m)
        step_size: Numero di waypoints per microsettore (20 = ~100m)

    Returns:
        Lista di Microsector oggetti
    """

    microsectors = []

    for i in range(0, len(waypoints) - step_size, step_size):
        micro_wps = waypoints[i:i+step_size+1]

        if len(micro_wps) < 2:
            continue

        # Estrai dati
        v_values = [wp.get('v_ref_kph', 0) for wp in micro_wps]
        throttle_values = [wp.get('throttle_pct', 0) for wp in micro_wps]
        brake_values = [wp.get('brake_pct', 0) for wp in micro_wps]
        radius_values = [wp.get('radius_m', 0) for wp in micro_wps if wp.get('radius_m', 0) > 0.1]

        v_entry = v_values[0]
        v_exit = v_values[-1]
        v_min = min(v_values)
        v_max = max(v_values)
        v_avg = sum(v_values) / len(v_values)

        start_dist = micro_wps[0].get('dist_m', 0)
        end_dist = micro_wps[-1].get('dist_m', 0)
        length_m = end_dist - start_dist

        # Velocità media per tempo
        v_avg_ms = v_avg / 3.6
        dt_s = length_m / v_avg_ms if v_avg_ms > 0.1 else 1.0

        # Accelerazione media
        dv_ms = (v_exit - v_entry) / 3.6
        a_mean_g = (dv_ms / dt_s / G) if dt_s > 0.01 else 0

        # G laterali (se curva)
        if radius_values:
            radius_m = radius_values[0]
            v_min_ms = v_min / 3.6
            if radius_m > 0.1 and v_min_ms > 0.1:
                a_lat_g = (v_min_ms ** 2) / (radius_m * G)
            else:
                a_lat_g = 0
        else:
            radius_m = 0
            a_lat_g = 0

        # DRS
        drs_active = any(wp.get('drs_active', False) for wp in micro_wps)

        # Throttle/brake medie
        throttle_pct = sum(throttle_values) / len(throttle_values) if throttle_values else 0
        brake_pct = sum(brake_values) / len(brake_values) if brake_values else 0

        micro = Microsector(
            idx=i // step_size,
            start_dist_m=start_dist,
            end_dist_m=end_dist,
            length_m=length_m,
            v_entry_kph=v_entry,
            v_exit_kph=v_exit,
            v_min_kph=v_min,
            v_max_kph=v_max,
            v_avg_kph=v_avg,
            a_mean_g=a_mean_g,
            radius_m=radius_m,
            a_lat_g=a_lat_g,
            drs_active=drs_active,
            throttle_pct=throttle_pct,
            brake_pct=brake_pct,
        )

        microsectors.append(micro)

    return microsectors


# ============================================================================
# CLASSIFY MICROSECTORS
# ============================================================================

def classify_microsector(micro: Microsector) -> str:
    """Classifica il microsettore per tipo."""

    if micro.radius_m == 0 or micro.a_lat_g < 0.3:
        return 'straight'
    elif micro.a_lat_g > 1.5:
        return 'sharp_corner'
    elif micro.a_lat_g > 0.8:
        return 'medium_corner'
    else:
        return 'corner'


# ============================================================================
# MAIN ANALYSIS
# ============================================================================

def main():
    print("="*100)
    print("MONZA MICROSECTOR-BY-MICROSECTOR CALIBRATION")
    print("="*100)

    # Carica dati
    print(f"\n[1] Loading Monza telemetry data...")
    waypoints = load_monza_waypoints()
    telemetry = load_monza_telemetry()

    if not waypoints:
        print("❌ Failed to load waypoints")
        return

    print(f"✓ Loaded {len(waypoints)} HD waypoints (5m spacing)")

    # Estrai microsettori
    print(f"\n[2] Extracting microsectors (step=20 waypoints ≈ 100m)...")
    microsectors = extract_microsectors(waypoints, step_size=20)
    print(f"✓ Extracted {len(microsectors)} microsectors")

    # Analizza per tipo
    print(f"\n[3] MICROSECTOR CLASSIFICATION")
    print("-"*100)

    types = {}
    for micro in microsectors:
        mtype = classify_microsector(micro)
        if mtype not in types:
            types[mtype] = []
        types[mtype].append(micro)

    for mtype in ['straight', 'corner', 'medium_corner', 'sharp_corner']:
        if mtype in types:
            micros = types[mtype]
            print(f"\n{mtype.upper()}: {len(micros)} microsectors")
            print(f"{'Idx':<5} {'Dist':<10} {'v_entry':<10} {'v_exit':<10} {'Δv':<8} {'a_g':<8} {'a_lat':<8} {'DRS':<5}")
            print("-"*80)

            for micro in micros[:5]:
                drs = "✓" if micro.drs_active else ""
                print(
                    f"{micro.idx:<5} "
                    f"{micro.start_dist_m:<10.0f} "
                    f"{micro.v_entry_kph:<10.1f} "
                    f"{micro.v_exit_kph:<10.1f} "
                    f"{micro.v_exit_kph - micro.v_entry_kph:<8.1f} "
                    f"{micro.a_mean_g:<8.3f} "
                    f"{micro.a_lat_g:<8.3f} "
                    f"{drs:<5}"
                )

    # Identifica microsettori critici
    print(f"\n[4] CRITICAL MICROSECTORS FOR CALIBRATION")
    print("-"*100)

    # 1. Max acceleration
    accel = [m for m in microsectors if m.a_mean_g > 0.3]
    if accel:
        accel_sorted = sorted(accel, key=lambda m: m.a_mean_g, reverse=True)
        print(f"\nMax Acceleration: {len(accel)} microsectors")
        m = accel_sorted[0]
        print(f"  Idx {m.idx}: v {m.v_entry_kph:.0f}→{m.v_exit_kph:.0f} km/h, a={m.a_mean_g:.3f}g, len={m.length_m:.0f}m, DRS={m.drs_active}")

    # 2. Max deceleration
    decel = [m for m in microsectors if m.a_mean_g < -0.5]
    if decel:
        decel_sorted = sorted(decel, key=lambda m: m.a_mean_g)
        print(f"\nMax Deceleration: {len(decel)} microsectors")
        m = decel_sorted[0]
        print(f"  Idx {m.idx}: v {m.v_entry_kph:.0f}→{m.v_exit_kph:.0f} km/h, a={m.a_mean_g:.3f}g, len={m.length_m:.0f}m")

    # 3. Max lateral
    lateral = [m for m in microsectors if m.a_lat_g > 0.5]
    if lateral:
        lateral_sorted = sorted(lateral, key=lambda m: m.a_lat_g, reverse=True)
        print(f"\nMax Lateral G: {len(lateral)} microsectors")
        m = lateral_sorted[0]
        print(f"  Idx {m.idx}: v_apex={m.v_min_kph:.0f} km/h, radius={m.radius_m:.0f}m, a_lat={m.a_lat_g:.3f}g")

    # Statistiche globali
    print(f"\n[5] GLOBAL STATISTICS")
    print("-"*100)

    v_max = max(m.v_max_kph for m in microsectors)
    v_min = min(m.v_min_kph for m in microsectors)
    a_max = max(m.a_mean_g for m in microsectors)
    a_min = min(m.a_mean_g for m in microsectors)
    a_lat_max = max(m.a_lat_g for m in microsectors)

    print(f"Velocities:")
    print(f"  v_max: {v_max:.1f} km/h (theoretical v_max on straights)")
    print(f"  v_min: {v_min:.1f} km/h (apex speed)")
    print(f"\nAccelerations:")
    print(f"  a_max: {a_max:.3f}g (max acceleration)")
    print(f"  a_min: {a_min:.3f}g (max deceleration)")
    print(f"\nLateral:")
    print(f"  a_lat_max: {a_lat_max:.3f}g (max lateral G in corners)")

    print(f"\n" + "="*100)
    print("CALIBRATION TARGETS")
    print("="*100)
    print(f"""
Setup: Monza ultra-low downforce
  CLA: {MONZA_SETUP['cla']} m²
  CDA: {MONZA_SETUP['cda']} m²

The motor MUST reproduce EXACTLY:
  • v_max = {v_max:.1f} km/h on straights
  • v_apex = {v_min:.1f} km/h in slow corners
  • a_max = {a_max:.3f}g in acceleration
  • a_lat_max = {a_lat_max:.3f}g in cornering

For EVERY microsector, both average velocity and acceleration must match within:
  • ±1-2 km/h
  • ±0.05g

If motor can't reproduce these → there's a physical model error.
""")

    print(f"\nNext: Implement simulation loop and compare each microsector...")


if __name__ == "__main__":
    main()
