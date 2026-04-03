"""
Generic Microsector Calibration for Any F1 Circuit

Strumento generico per calibrare qualsiasi circuito microsettore per microsettore.

Usage:
  python generic_microsector_calibration.py it-1922_monza
  python generic_microsector_calibration.py mc-1929_monaco
  python generic_microsector_calibration.py jp-1962_suzuka
"""

import json
import os
import sys
import math
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# ============================================================================
# CIRCUIT CONFIGURATIONS
# ============================================================================

CIRCUIT_CONFIGS = {
    "it-1922_monza": {
        "name": "Monza",
        "cla": 2.90,
        "cda": 0.90,
        "description": "Ultra-low DF, straight-biased"
    },
    "mc-1929_monaco": {
        "name": "Monaco",
        "cla": 4.60,
        "cda": 1.30,
        "description": "Ultra-high DF, corner-biased"
    },
    "jp-1962_suzuka": {
        "name": "Suzuka",
        "cla": 3.80,
        "cda": 1.05,
        "description": "Medium-high DF, mixed"
    },
}

MASS_KG = 798.0
G = 9.81
RHO = 1.225

# ============================================================================
# DATA STRUCTURE
# ============================================================================

@dataclass
class Microsector:
    idx: int
    start_dist_m: float
    end_dist_m: float
    length_m: float
    v_entry_kph: float
    v_exit_kph: float
    v_min_kph: float
    v_max_kph: float
    v_avg_kph: float
    a_mean_g: float
    radius_m: float
    a_lat_g: float
    drs_active: bool
    throttle_pct: float
    brake_pct: float


# ============================================================================
# FUNCTIONS
# ============================================================================

def load_waypoints(circuit_id: str) -> Optional[List[Dict[str, Any]]]:
    path = f"python_backend/data/circuits/2025/{circuit_id}_HD.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f).get('waypoints', [])


def extract_microsectors(waypoints: List[Dict], step_size: int = 20) -> List[Microsector]:
    microsectors = []

    for i in range(0, len(waypoints) - step_size, step_size):
        micro_wps = waypoints[i:i+step_size+1]
        if len(micro_wps) < 2:
            continue

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

        v_avg_ms = v_avg / 3.6
        dt_s = length_m / v_avg_ms if v_avg_ms > 0.1 else 1.0
        dv_ms = (v_exit - v_entry) / 3.6
        a_mean_g = (dv_ms / dt_s / G) if dt_s > 0.01 else 0

        if radius_values:
            radius_m = radius_values[0]
            v_min_ms = v_min / 3.6
            a_lat_g = (v_min_ms ** 2) / (radius_m * G) if radius_m > 0.1 and v_min_ms > 0.1 else 0
        else:
            radius_m = 0
            a_lat_g = 0

        drs_active = any(wp.get('drs_active', False) for wp in micro_wps)
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


def classify_microsector(micro: Microsector) -> str:
    if micro.radius_m == 0 or micro.a_lat_g < 0.3:
        return 'straight'
    elif micro.a_lat_g > 1.5:
        return 'sharp_corner'
    elif micro.a_lat_g > 0.8:
        return 'medium_corner'
    else:
        return 'corner'


def analyze_circuit(circuit_id: str):
    """Analizza un circuito completo."""

    config = CIRCUIT_CONFIGS.get(circuit_id)
    if not config:
        print(f"❌ Circuit {circuit_id} not in config")
        return

    print("="*100)
    print(f"{circuit_id.upper()} — {config['name']} ({config['description']})")
    print("="*100)

    waypoints = load_waypoints(circuit_id)
    if not waypoints:
        print(f"❌ Waypoints not found")
        return

    print(f"✓ Loaded {len(waypoints)} waypoints")

    microsectors = extract_microsectors(waypoints, step_size=20)
    print(f"✓ Extracted {len(microsectors)} microsectors")

    # Classificazione
    types = {}
    for micro in microsectors:
        mtype = classify_microsector(micro)
        if mtype not in types:
            types[mtype] = []
        types[mtype].append(micro)

    # Statistiche
    v_max = max(m.v_max_kph for m in microsectors)
    v_min = min(m.v_min_kph for m in microsectors)
    a_max = max(m.a_mean_g for m in microsectors)
    a_min = min(m.a_mean_g for m in microsectors)
    a_lat_max = max(m.a_lat_g for m in microsectors)

    print(f"\n[SETUP]")
    print(f"  CLA: {config['cla']:.2f} m²")
    print(f"  CDA: {config['cda']:.3f} m²")

    print(f"\n[MICROSECTORS BY TYPE]")
    for mtype in ['straight', 'corner', 'medium_corner', 'sharp_corner']:
        if mtype in types:
            print(f"  {mtype}: {len(types[mtype])}")

    print(f"\n[CALIBRATION TARGETS]")
    print(f"  v_max: {v_max:.1f} km/h")
    print(f"  v_min: {v_min:.1f} km/h")
    print(f"  a_max: {a_max:.3f}g")
    print(f"  a_min: {a_min:.3f}g")
    print(f"  a_lat_max: {a_lat_max:.3f}g")

    # Microsettori critici
    print(f"\n[CRITICAL MICROSECTORS]")

    accel = sorted([m for m in microsectors if m.a_mean_g > 0.3], key=lambda m: m.a_mean_g, reverse=True)
    if accel:
        m = accel[0]
        print(f"  Max accel [idx {m.idx}]: v {m.v_entry_kph:.0f}→{m.v_exit_kph:.0f} km/h, a={m.a_mean_g:.3f}g")

    decel = sorted([m for m in microsectors if m.a_mean_g < -0.5], key=lambda m: m.a_mean_g)
    if decel:
        m = decel[0]
        print(f"  Max decel [idx {m.idx}]: v {m.v_entry_kph:.0f}→{m.v_exit_kph:.0f} km/h, a={m.a_mean_g:.3f}g")

    lateral = sorted([m for m in microsectors if m.a_lat_g > 0.5], key=lambda m: m.a_lat_g, reverse=True)
    if lateral:
        m = lateral[0]
        print(f"  Max lateral [idx {m.idx}]: v_apex={m.v_min_kph:.0f} km/h, a_lat={m.a_lat_g:.3f}g")

    print()


# ============================================================================
# MAIN
# ============================================================================

def main():
    if len(sys.argv) > 1:
        circuit_id = sys.argv[1]
        if circuit_id in CIRCUIT_CONFIGS:
            analyze_circuit(circuit_id)
        else:
            print(f"❌ Unknown circuit: {circuit_id}")
            print(f"Available: {', '.join(CIRCUIT_CONFIGS.keys())}")
    else:
        # Analizza tutti
        for circuit_id in CIRCUIT_CONFIGS.keys():
            analyze_circuit(circuit_id)
            print()


if __name__ == "__main__":
    main()
