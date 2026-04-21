"""
Drag Force Calculator - Aerodinamica + Rolling + Steering + Brake Duct.
"""

from typing import Dict, Any

from core.constants import RHO_SEA_LEVEL, ROLLING_RESISTANCE_COEFF, G
from aero.aero_assembly import AeroForces


def compute_total_drag(
    aero_forces: AeroForces,
    mass_kg: float,
    velocity_ms: float,
    waypoint: Dict[str, Any],
    setup: Dict[str, Any],
) -> float:
    """
    Calcola la forza di drag totale per un singolo waypoint.

    Include:
    - Drag aerodinamico (da AeroAssembly)
    - Rolling resistance
    - Steering induced drag (con deadzone)
    - Brake duct aerodynamic drag penalty
    """
    # Drag aerodinamico + rolling resistance
    f_drag = aero_forces.f_drag
    f_rolling = ROLLING_RESISTANCE_COEFF * mass_kg * G
    f_drag += f_rolling

    # ============================================================
    # PHYSICS FIX V4.2 #1: Steering Induced Drag (Deadzone)
    # ============================================================
    # Deadzone: Se steering_angle < 2 gradi, nessun drag aggiuntivo
    # Questo evita resistenza parassita sui rettilinei (Monza)
    steering_angle_deg = abs(waypoint.get('steering_angle_deg', 0.0))
    if steering_angle_deg >= 2.0 and velocity_ms > 1.0:  # Deadzone: ignora < 2 gradi
        v_kph = velocity_ms * 3.6
        v_ref_kph = 100.0  # Velocità di riferimento per calibrazione
        steer_drag_coeff = 45.0  # N/degree base a 100 km/h

        # Fattore non-lineare: più effetto a basse velocità (Monaco)
        if v_kph < 60.0:
            velocity_factor = 2.0  # Raddoppia effetto a < 60 km/h
        elif v_kph > 200.0:
            velocity_factor = 0.5  # Dimezza effetto a > 200 km/h
        else:
            velocity_factor = 1.0  # Normale tra 60-200 km/h

        f_steer_drag = steer_drag_coeff * steering_angle_deg * ((v_kph / v_ref_kph) ** 2) * velocity_factor
        f_drag += f_steer_drag

    # V6.3: Brake duct aerodynamic drag penalty (Modulo D)
    # Brake duct opening adds drag: max 0.005 c_da at 100% opening
    brake_duct_opening = setup.get('brake_duct', 0.5) if setup else 0.5
    c_da_brake_duct = 0.005 * brake_duct_opening  # Adds up to 0.005 to c_da
    f_drag_brake_duct = 0.5 * RHO_SEA_LEVEL * (velocity_ms ** 2) * c_da_brake_duct
    f_drag += f_drag_brake_duct

    return f_drag
