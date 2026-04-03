"""
Setup Deduction — Deduce Setup from Telemetry

Problema: La telemetria F1 non contiene l'assetto esatto (CLA, CDA, fuel, etc.)
Soluzione: Dedurre l'assetto dai dati fisici reali (velocità, accelerazioni, grip)

Approccio Inverse Problem:
1. Carica telemetria reale di un circuito
2. Estrai parametri fisici: v_max, corner_speeds, accelerations, etc.
3. Prova diverse combinazioni di setup
4. Trova il setup che riproduce ESATTAMENTE quei parametri
5. Valida che il setup dedotto è realistico per quel circuito

Known Facts per circuito:
- Monza: Ultra-low DF (CLA ~2.8-3.0, CDA ~0.85-0.95)
- Monaco: Ultra-high DF (CLA ~4.5-4.8, CDA ~1.20-1.40)
- Spa: Medium-High DF (CLA ~3.8-4.2, CDA ~1.00-1.10)
- Barcelona: Medium DF (CLA ~3.5-3.8, CDA ~1.05-1.15)
- Suzuka: Medium-High DF (CLA ~3.6-4.0, CDA ~1.00-1.10)
- Silverstone: Low-Medium DF (CLA ~3.0-3.5, CDA ~0.95-1.05)
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

# Conosciute per F1 2025 (da FIA regs + telemetria)
KNOWN_SETUP_RANGES = {
    "it-1922_monza": {
        "name": "Monza (ultra-low DF)",
        "cla_low": 2.80,
        "cla_high": 3.00,
        "cda_low": 0.85,
        "cda_high": 0.95,
        "description": "Straight-oriented, minimal downforce"
    },
    "mc-1929_monaco": {
        "name": "Monaco (ultra-high DF)",
        "cla_low": 4.40,
        "cla_high": 4.80,
        "cda_low": 1.20,
        "cda_high": 1.40,
        "description": "Cornering-oriented, maximum downforce"
    },
    "be-1925_spa": {
        "name": "Spa (medium-high DF)",
        "cla_low": 3.80,
        "cla_high": 4.20,
        "cda_low": 1.00,
        "cda_high": 1.10,
        "description": "Mixed: high-speed corners + long straights"
    },
    "jp-1962_suzuka": {
        "name": "Suzuka (medium-high DF)",
        "cla_low": 3.60,
        "cla_high": 4.00,
        "cda_low": 1.00,
        "cda_high": 1.10,
        "description": "Mixed: technical + demanding corners"
    },
    "gb-1950_silverstone": {
        "name": "Silverstone (low-medium DF)",
        "cla_low": 3.00,
        "cla_high": 3.50,
        "cda_low": 0.95,
        "cda_high": 1.05,
        "description": "Fast, flowing corners + long straights"
    },
}

# ============================================================================
# LOAD AND ANALYZE TELEMETRY
# ============================================================================

def load_telemetry(circuit_id: str) -> Optional[Dict[str, Any]]:
    """Carica telemetria di un circuito."""
    path = f"python_backend/data/circuits/2025/{circuit_id}_Telemetry.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)


def load_hd_waypoints(circuit_id: str) -> Optional[List[Dict[str, Any]]]:
    """Carica waypoints HD di un circuito."""
    path = f"python_backend/data/circuits/2025/{circuit_id}_HD.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        data = json.load(f)
        return data.get('waypoints', [])


def extract_critical_parameters(
    telemetry: Dict[str, Any],
    waypoints: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Estrai parametri fisici critici dalla telemetria.

    Questi parametri devono essere riprodotti ESATTAMENTE dal motore.
    """

    sections = telemetry.get('geometry', {}).get('sections', [])

    # Parametri critici
    v_max_straight = 0
    v_apex_corners = []
    corner_radii = []
    accelerations = []
    decelerations = []

    for section in sections:
        kind = section.get('kind', '')
        v_entry = section.get('v_entry_kph', 0)
        v_exit = section.get('v_exit_kph', 0)
        v_min = section.get('v_min_kph', 0)
        v_max = section.get('v_max_kph', 0)
        radius = section.get('radius_m', 0)
        dt = section.get('dt_ref_s', 0.1)
        length = section.get('length_m', 0)

        # Rettilineo: v_max
        if 'Straight' in kind and v_max > v_max_straight:
            v_max_straight = v_max

        # Curva: v_apex e radius
        if 'Corner' in kind:
            if v_min > 0:
                v_apex_corners.append(v_min)
            if radius and radius > 0.1:
                corner_radii.append(radius)

        # Accelerazione
        if v_exit > v_entry and dt > 0:
            dv_ms = (v_exit - v_entry) / 3.6
            a_g = (dv_ms / dt) / G
            accelerations.append({
                'a_g': a_g,
                'v_entry_kph': v_entry,
                'v_exit_kph': v_exit,
                'length_m': length,
                'section': kind,
            })

        # Decelerazione
        if v_exit < v_entry and dt > 0:
            dv_ms = (v_entry - v_exit) / 3.6
            a_g = (dv_ms / dt) / G
            decelerations.append({
                'a_g': a_g,
                'v_entry_kph': v_entry,
                'v_exit_kph': v_exit,
                'length_m': length,
                'section': kind,
            })

    # Calcola statistiche
    return {
        'v_max_straight_kph': v_max_straight,
        'v_apex_corners_kph': sorted(v_apex_corners),
        'corner_radii_m': sorted(corner_radii),
        'max_acceleration_g': max([a['a_g'] for a in accelerations]) if accelerations else 0,
        'max_deceleration_g': max([a['a_g'] for a in decelerations]) if decelerations else 0,
        'num_accelerations': len(accelerations),
        'num_decelerations': len(decelerations),
        'slow_corners': len([c for c in v_apex_corners if c < 100]),
        'medium_corners': len([c for c in v_apex_corners if 100 <= c < 200]),
        'fast_corners': len([c for c in v_apex_corners if c >= 200]),
    }


def estimate_setup_from_physics(
    circuit_id: str,
    telemetry: Dict[str, Any],
    waypoints: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Deduce l'assetto dal comportamento fisico estratto dalla telemetria.

    Logic:
    - v_max_straight alta → CDA basso (rettilineo veloce)
    - v_apex_slow bassa → CLA alto (grip buono in curva lenta)
    - Mix dipende dal circuito noto
    """

    params = extract_critical_parameters(telemetry, waypoints)

    # Conosci il setup noto per il circuito
    known = KNOWN_SETUP_RANGES.get(circuit_id, {})

    # Analisi
    analysis = {
        'circuit_id': circuit_id,
        'circuit_name': known.get('name', 'Unknown'),
        'description': known.get('description', ''),
        'extracted_physics': params,
    }

    # Stima CLA da corner speeds
    v_apex_slow = min(params['v_apex_corners_kph']) if params['v_apex_corners_kph'] else 0
    if v_apex_slow > 0 and params['corner_radii_m']:
        # v_apex ≈ sqrt(CLA * g * R)
        # CLA ≈ v_apex² / (g * R)
        slow_radius = min(params['corner_radii_m'])
        v_apex_slow_ms = v_apex_slow / 3.6
        cla_estimated = (v_apex_slow_ms ** 2) / (G * slow_radius) if slow_radius > 0.1 else 0
    else:
        cla_estimated = 0

    # Stima CDA da v_max (equilibrio forza/drag)
    # A v_max: P_available = F_drag * v_max
    # Assumendo P ≈ 800 kW (cruise power) e F_rolling ≈ 86 N
    v_max_straight = params['v_max_straight_kph']
    if v_max_straight > 200:
        v_max_ms = v_max_straight / 3.6
        # Inverse: CDA ≈ (P - F_rolling*v) / (0.5 * rho * v³)
        # Assumendo P ≈ 800 kW
        p_available_w = 800000
        f_rolling = 0.011 * MASS_KG * G
        try:
            cda_estimated = (p_available_w / v_max_ms - f_rolling) / (0.5 * RHO * v_max_ms ** 2)
        except:
            cda_estimated = 1.0
    else:
        cda_estimated = 1.0

    analysis['estimated_cla'] = cla_estimated
    analysis['estimated_cda'] = cda_estimated
    analysis['known_cla_range'] = (known.get('cla_low'), known.get('cla_high'))
    analysis['known_cda_range'] = (known.get('cda_low'), known.get('cda_high'))

    return analysis


# ============================================================================
# MAIN
# ============================================================================

def main():
    circuits = list(KNOWN_SETUP_RANGES.keys())

    print("="*100)
    print("SETUP DEDUCTION FROM TELEMETRY")
    print("="*100)

    for circuit_id in circuits:
        print(f"\n[{circuit_id}]")
        print("-"*100)

        telemetry = load_telemetry(circuit_id)
        waypoints = load_hd_waypoints(circuit_id)

        if not telemetry:
            print(f"❌ Telemetry not found")
            continue

        analysis = estimate_setup_from_physics(circuit_id, telemetry, waypoints)

        print(f"Circuit: {analysis['circuit_name']}")
        print(f"Description: {analysis['description']}")

        params = analysis['extracted_physics']
        print(f"\nExtracted Physics Parameters:")
        print(f"  v_max straight:      {params['v_max_straight_kph']:.1f} km/h")
        print(f"  Corners (slow/med/fast): {params['slow_corners']}/{params['medium_corners']}/{params['fast_corners']}")
        if params['v_apex_corners_kph']:
            print(f"  v_apex range:         {min(params['v_apex_corners_kph']):.0f} - {max(params['v_apex_corners_kph']):.0f} km/h")
        if params['corner_radii_m']:
            print(f"  Radius range:         {min(params['corner_radii_m']):.0f} - {max(params['corner_radii_m']):.0f} m")
        print(f"  Max acceleration:     {params['max_acceleration_g']:.3f}g")
        print(f"  Max deceleration:     {params['max_deceleration_g']:.3f}g")

        print(f"\nEstimated Setup:")
        print(f"  CLA estimated:        {analysis['estimated_cla']:.2f}")
        print(f"  CLA known range:      {analysis['known_cla_range'][0]:.2f} - {analysis['known_cla_range'][1]:.2f}")
        print(f"  CDA estimated:        {analysis['estimated_cda']:.3f}")
        print(f"  CDA known range:      {analysis['known_cda_range'][0]:.3f} - {analysis['known_cda_range'][1]:.3f}")

        # Validazione
        cla_valid = analysis['known_cla_range'][0] <= analysis['estimated_cla'] <= analysis['known_cla_range'][1]
        cda_valid = analysis['known_cda_range'][0] <= analysis['estimated_cda'] <= analysis['known_cda_range'][1]

        print(f"\nValidation:")
        print(f"  CLA: {'✓ VALID' if cla_valid else '❌ OUTSIDE RANGE'}")
        print(f"  CDA: {'✓ VALID' if cda_valid else '❌ OUTSIDE RANGE'}")

    print("\n" + "="*100)
    print("NEXT STEP: Use these deduced setups to calibrate the universal motor model")
    print("="*100)


if __name__ == "__main__":
    main()
