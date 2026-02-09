"""
BrakeSystem – Step 5b of update_section().

Computes brake temperatures, fade, wear and braking efficiency.

Reference: docs/lap-physics-spec-v0.5.md §3.3 Passo 5
           docs/degradation-and-consumption.md §5.2
"""
from __future__ import annotations

from typing import List, Tuple

from .data_types import (
    AeroForces,
    BrakeState,
    BrakeSystemParams,
    CarState,
    CircuitConfig,
    DriverIntent,
    EnvContext,
    SectionContext,
    SectionEvent,
    clamp,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def update_brakes(
    car_state: CarState,
    section: SectionContext,
    env: EnvContext,
    aero: AeroForces,
    driver: DriverIntent,
    config: CircuitConfig,
    dt_s: float,
    v_kph: float,
) -> Tuple[float, List[SectionEvent]]:
    """
    Update brake thermal state, fade, wear and return braking efficiency.

    Returns
    -------
    braking_efficiency : float  (0.9 – 1.15)
    events : list of SectionEvent
    """
    events: List[SectionEvent] = []
    brakes = car_state.brakes
    bp = config.brake_params

    # --- Energy distribution (front/rear based on bias) ---
    bias_front = brakes.bias_front_pct / 100.0 + driver.brake_bias_adjust
    bias_front = clamp(bias_front, 0.50, 0.62)
    bias_rear = 1.0 - bias_front

    braking_energy = section.braking_energy_mj  # MJ for this section

    energy_front = braking_energy * bias_front
    energy_rear = braking_energy * bias_rear

    # --- Heat generation ---
    # heat_in = energy / heat_capacity (higher capacity → less temp rise)
    heat_in_front = energy_front / max(bp.heat_capacity_front, 0.1)
    heat_in_rear = energy_rear / max(bp.heat_capacity_rear, 0.1)

    # Heat quality: better system disperses heat more efficiently
    heat_in_front *= (2.0 - bp.heat_quality)  # quality 1.0 → factor 1.0
    heat_in_rear *= (2.0 - bp.heat_quality)

    # --- Cooling ---
    duct_cooling = (
        brakes.duct_opening
        * bp.cooling_coeff
        * (1.0 - aero.airflow_penalty)
    )
    air_speed_factor = max(v_kph / 300.0, 0.1)

    cool_front = duct_cooling * air_speed_factor * (brakes.temp_front_c - env.air_temp_c) * 0.002
    cool_rear = duct_cooling * air_speed_factor * (brakes.temp_rear_c - env.air_temp_c) * 0.002

    # --- Temperature update ---
    delta_t_front = (heat_in_front - cool_front) / max(bp.thermal_mass_front, 0.1) * dt_s
    delta_t_rear = (heat_in_rear - cool_rear) / max(bp.thermal_mass_rear, 0.1) * dt_s

    brakes.temp_front_c += delta_t_front
    brakes.temp_rear_c += delta_t_rear

    # Clamp
    brakes.temp_front_c = clamp(brakes.temp_front_c, env.air_temp_c, 1200.0)
    brakes.temp_rear_c = clamp(brakes.temp_rear_c, env.air_temp_c, 1100.0)

    # --- Fade ---
    fade_level = 0.0
    if brakes.temp_front_c > bp.fade_threshold_front_c:
        excess = brakes.temp_front_c - bp.fade_threshold_front_c
        fade_level += excess / max(bp.fade_sensitivity_c_per_unit, 1.0) * 0.01
    if brakes.temp_rear_c > bp.fade_threshold_rear_c:
        excess = brakes.temp_rear_c - bp.fade_threshold_rear_c
        fade_level += excess / max(bp.fade_sensitivity_c_per_unit, 1.0) * 0.005

    brakes.fade_level = clamp(fade_level, 0.0, 1.0)

    # --- Wear ---
    wear_rate_front = energy_front * 0.01  # simplified
    wear_rate_rear = energy_rear * 0.008
    brakes.wear_front_pct += wear_rate_front * dt_s
    brakes.wear_rear_pct += wear_rate_rear * dt_s
    brakes.wear_front_pct = clamp(brakes.wear_front_pct, 0.0, 100.0)
    brakes.wear_rear_pct = clamp(brakes.wear_rear_pct, 0.0, 100.0)

    # --- Braking efficiency (spec §6.1) ---
    # Only meaningful on sections with actual braking
    if braking_energy < 0.05:
        braking_efficiency = 1.0
    else:
        brake_quality = 0.9 + bp.heat_quality / 200.0
        brake_health = 1.0 - clamp(brakes.fade_level + brakes.wear_front_pct / 100.0, 0.0, 0.8)
        driver_brake_skill = 0.5  # neutral; real value from DriverSkills later

        brake_opt_center = bp.fade_threshold_front_c * 0.85
        temp_delta = abs(brakes.temp_front_c - brake_opt_center) / max(brake_opt_center, 1.0)

        # Scale: quality*skill*health gives ~0.05 bonus at best, temp_delta penalises
        braking_efficiency = clamp(
            1.0 + brake_quality * driver_brake_skill * brake_health * 0.1 - temp_delta * 0.4,
            0.9,
            1.15,
        )

    # --- Events ---
    if brakes.fade_level > 0.01:
        events.append(SectionEvent(
            event_type="brake_fade",
            severity=brakes.fade_level,
            message="Brake fade detected",
        ))

    if braking_efficiency > 1.05 and braking_energy >= 0.5:
        events.append(SectionEvent(
            event_type="late_brake_success",
            severity=0.3,
            message="Late braking success",
        ))

    if brakes.temp_front_c > bp.fade_threshold_front_c + 50:
        events.append(SectionEvent(
            event_type="brake_critical",
            severity=0.8,
            message="Front brakes critically hot!",
        ))

    return braking_efficiency, events
