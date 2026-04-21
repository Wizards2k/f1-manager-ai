"""
Integrator Physics - Funzioni pure di calcolo fisico per il waypoint integrator.

Estratte dal waypoint_integrator.py per modularizzazione.
"""

import math
from typing import Dict, List, Any, Optional

from aero.aero_assembly import AeroForces
from core.constants import G, RHO_SEA_LEVEL, calculate_air_density


def apply_aero_calibration(aero_forces: AeroForces, aero_calibration: Optional[Dict[str, Any]]) -> AeroForces:
    """Applica un profilo aero calibrato ai coefficienti calcolati dal modello fisico."""
    if not aero_calibration:
        return aero_forces

    def _as_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    drag_scale = _as_float(aero_calibration.get("drag_index"), 1.0) or 1.0
    downforce_scale = _as_float(aero_calibration.get("downforce_index"), 1.0) or 1.0
    balance_target = aero_calibration.get("aero_balance_target")

    if aero_calibration.get("format") == "v5" and "drag_index" not in aero_calibration:
        return aero_forces

    front_share = aero_forces.aero_balance
    if balance_target is not None:
        front_share = max(0.35, min(0.65, 0.5 + _as_float(balance_target, 0.0)))

    total_cla = aero_forces.cla_total * downforce_scale
    total_cda = aero_forces.cda_total * drag_scale
    total_downforce = aero_forces.f_downforce * downforce_scale
    total_drag = aero_forces.f_drag * drag_scale

    aero_forces.cla_total = total_cla
    aero_forces.cda_total = total_cda
    aero_forces.cla_front = total_cla * front_share
    aero_forces.cla_rear = total_cla * (1.0 - front_share)
    aero_forces.f_downforce = total_downforce
    aero_forces.f_downforce_front = total_downforce * front_share
    aero_forces.f_downforce_rear = total_downforce * (1.0 - front_share)
    aero_forces.f_drag = total_drag
    aero_forces.aero_balance = front_share

    return aero_forces


def compute_grip_limit(
    velocity_ms: float,
    radius_m: float,
    mass_kg: float,
    cla: float,
    mu: float
) -> float:
    """Calcola velocità massima in curva dal grip disponibile (equazione implicita)."""
    v_max = math.sqrt(mu * G * radius_m)
    
    for _ in range(3):
        dynamic_pressure = 0.5 * RHO_SEA_LEVEL * v_max ** 2
        f_down = dynamic_pressure * cla
        f_grip = mu * (mass_kg * G + f_down)
        v_max_new = math.sqrt(f_grip * radius_m / mass_kg)
        v_max = 0.7 * v_max_new + 0.3 * v_max
    
    return v_max


def get_circuit_elevation_m(circuit_id: str) -> float:
    """Carica l'elevation di un circuito dai dati di configurazione."""
    from pathlib import Path
    import json

    circuits_file = Path(__file__).resolve().parents[3] / "circuits" / f"{circuit_id}.json"

    if not circuits_file.exists():
        return 0.0

    try:
        with open(circuits_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            props = data.get('properties', {})
            altitude = props.get('altitude', 0)
            return float(altitude)
    except Exception:
        return 0.0


def compute_v_max_corners(
    waypoints: List[Dict],
    aero,
    mu_cal: float,
    mass_kg: float,
    circuit_id: Optional[str] = None,
    suspension_effects: Optional[Dict[str, float]] = None,
    n_iter: int = 3,
) -> List[float]:
    """Calcola v_max_corner (velocità massima fisica) per ogni waypoint."""
    v_max_corner = []
    elevation_m = get_circuit_elevation_m(circuit_id) if circuit_id else 0.0
    air_density = calculate_air_density(elevation_m)

    for wp in waypoints:
        radius_m = wp.get('radius_m', 999999.0)
        is_corner = radius_m < 400.0

        if not is_corner:
            v_max_corner.append(999.0)
            continue

        v_ref_kph = float(wp.get('v_ref_kph', 200.0))
        v_est = v_ref_kph / 3.6

        for _ in range(n_iter):
            aero_forces = aero.compute_forces(
                speed_ms=v_est,
                air_density=air_density
            )
            f_downforce = aero_forces.f_downforce
            f_vertical = mass_kg * G + f_downforce
            load_sensitivity_k = 0.010
            f_vertical_kn = f_vertical / 1000.0
            lat_load_factor = 1.0 - (load_sensitivity_k * f_vertical_kn)
            lat_load_factor = max(0.75, min(1.0, lat_load_factor))
            f_grip = mu_cal * f_vertical * lat_load_factor
            cu = min(0.95, 0.35 + radius_m / 150.0)
            v_est = math.sqrt(max(0.1, f_grip * cu * radius_m / mass_kg))

        v_max_corner.append(v_est)

    return v_max_corner


def gaussian_thermal_multiplier(surface_temp_c: float, core_temp_c: float, compound: str) -> float:
    """V6.3: Gaussian thermal multiplier for grip reduction outside optimal window."""
    optim_data = {
        'C5': {'optim_surf': 100.0, 'sigma_surf': 7.5, 'optim_core': 85.0, 'sigma_core': 6.5},
        'C4': {'optim_surf': 105.0, 'sigma_surf': 8.0, 'optim_core': 90.0, 'sigma_core': 7.0},
        'C3': {'optim_surf': 110.0, 'sigma_surf': 8.5, 'optim_core': 95.0, 'sigma_core': 7.5},
    }

    data = optim_data.get(compound, optim_data['C4'])

    surf_mult = math.exp(-((surface_temp_c - data['optim_surf']) ** 2) /
                         (2 * data['sigma_surf'] ** 2))
    core_mult = math.exp(-((core_temp_c - data['optim_core']) ** 2) /
                         (2 * data['sigma_core'] ** 2))

    return surf_mult * core_mult


def get_optimal_temp(compound: str) -> float:
    """V6.3: Get optimal surface temperature for tire compound."""
    optim_temps = {'C5': 100.0, 'C4': 105.0, 'C3': 110.0}
    return optim_temps.get(compound, 105.0)


def get_sigma(compound: str) -> float:
    """V6.3: Get thermal window width (sigma) for tire compound."""
    sigmas = {'C5': 7.5, 'C4': 8.0, 'C3': 8.5}
    return sigmas.get(compound, 8.0)
