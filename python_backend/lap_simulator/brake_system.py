"""
BrakeSystem – Step 5b of update_section().

Computes brake temperatures, fade, wear and braking efficiency.

Reference: docs/lap-physics-spec-v0.5.md §3.3 Passo 5
           docs/degradation-and-consumption.md §5.2
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .data_types import (
    AeroForces,
    BrakeState,
    BrakeSystemParams,
    CarState,
    CircuitConfig,
    DriverIntent,
    DriverSkills,
    EnvContext,
    SectionContext,
    SectionEvent,
    clamp,
)


# Calibrated multipliers to align heat build-up / dissipation with telemetry window
HEAT_GAIN_MULTIPLIER = 6.5
COOLING_GAIN_MULTIPLIER = 0.45


def _format_temp_snapshot(brakes: BrakeState, config: CircuitConfig) -> Dict[str, Any]:
    profile = config.brake_profile or {}
    fade = profile.get("fade_threshold", {})
    params = config.brake_params
    return {
        "front": brakes.temp_front_c,
        "rear": brakes.temp_rear_c,
        "thresholds": {
            "front_c": fade.get("front_c", params.fade_threshold_front_c if params else 850.0),
            "rear_c": fade.get("rear_c", params.fade_threshold_rear_c if params else 750.0),
        },
    }


def _find_critical_section(config: CircuitConfig, section_id: str) -> Dict[str, Any]:
    for entry in config.brake_critical_sections or []:
        if entry.get("id") == section_id:
            return entry
    return {}


def _compute_regen_factor(brake_profile: Dict[str, Any], section: SectionContext) -> float | None:
    if not brake_profile:
        return None
    base = brake_profile.get("regen_brake_base")
    if base is None:
        return None
    energy = section.braking_energy_mj
    energy_window = brake_profile.get("brake_energy_window", {})
    regen_range = brake_profile.get("regen_brake_factor_range", {})
    min_factor = regen_range.get("min", max(0.0, base - 0.3))
    max_factor = regen_range.get("max", min(0.95, base + 0.3))
    factor = base
    p75 = energy_window.get("p75")
    p90 = energy_window.get("p90")
    if p90 and energy >= p90:
        factor = max(min_factor, base - 0.15)
    elif p75 and energy <= p75 * 0.9:
        factor = min(max_factor, base + 0.1)
    return clamp(factor, min_factor, max_factor)


def _format_section_name(critical: Dict[str, Any], section: SectionContext) -> str:
    return critical.get("name") or section.name or section.section_id


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
    driver_skills: DriverSkills | None = None,
) -> Tuple[float, List[SectionEvent], Dict[str, Any]]:
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
    brake_profile = config.brake_profile or {}
    critical_section = _find_critical_section(config, section.section_id)

    # --- Energy distribution (front/rear based on bias) ---
    bias_front = brakes.bias_front_pct / 100.0 + driver.brake_bias_adjust
    bias_front = clamp(bias_front, 0.50, 0.62)
    bias_rear = 1.0 - bias_front

    braking_energy = section.braking_energy_mj  # MJ for this section

    energy_front = braking_energy * bias_front
    energy_rear = braking_energy * bias_rear

    # Apply regen split (mostly rear axle) from calibration profile
    regen_factor = _compute_regen_factor(brake_profile, section)
    regen_cap = 0.6
    ratio = brake_profile.get("hydraulic_vs_regen_ratio") if brake_profile else None
    if isinstance(ratio, (int, float)) and ratio > 0:
        regen_cap = clamp(1.0 / (ratio + 1.0), 0.1, 0.8)
    regen_energy = 0.0
    if regen_factor is not None and braking_energy > 0.05:
        regen_share = clamp(regen_factor, 0.0, regen_cap)
        regen_energy = energy_rear * regen_share
        energy_rear *= (1.0 - regen_share)
        if regen_energy > 0.0:
            events.append(SectionEvent(
                event_type="regen_split",
                severity=regen_share,
                message=f"Regen brake active ({regen_share:.0%})",
            ))

    # --- Heat generation ---
    # heat_in = energy / heat_capacity (higher capacity → less temp rise)
    heat_in_front = (energy_front / max(bp.heat_capacity_front, 0.1)) * HEAT_GAIN_MULTIPLIER
    heat_in_rear = (energy_rear / max(bp.heat_capacity_rear, 0.1)) * HEAT_GAIN_MULTIPLIER

    if critical_section:
        crit_factor = max(critical_section.get("heat_factor", 1.0), 1.0)
        heat_in_front *= crit_factor
        heat_in_rear *= crit_factor

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

    base_cooling = duct_cooling * air_speed_factor * 0.002 * COOLING_GAIN_MULTIPLIER
    temp_delta_front = max(brakes.temp_front_c - env.air_temp_c, 0.0)
    temp_delta_rear = max(brakes.temp_rear_c - env.air_temp_c, 0.0)
    cool_front = base_cooling * temp_delta_front
    cool_rear = base_cooling * temp_delta_rear

    duct_rec = brake_profile.get("duct_recommendation", {})
    if duct_rec and braking_energy >= 1.0:
        min_open = duct_rec.get("min_open")
        max_open = duct_rec.get("max_open")
        if isinstance(min_open, (int, float)) and brakes.duct_opening + 1e-3 < min_open:
            events.append(SectionEvent(
                event_type="brake_duct_low",
                severity=min(1.0, (min_open - brakes.duct_opening) * 2),
                message="Brake ducts too closed for current braking load",
            ))
        if isinstance(max_open, (int, float)) and brakes.duct_opening - 1e-3 > max_open:
            events.append(SectionEvent(
                event_type="brake_duct_high",
                severity=min(1.0, (brakes.duct_opening - max_open) * 2),
                message="Brake ducts more open than recommended",
            ))

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
        if driver_skills is not None:
            driver_brake_skill = (driver_skills.race_craft + driver_skills.aggression) / 200.0
        else:
            driver_brake_skill = 0.5

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

    if critical_section and braking_energy >= 1.0:
        section_name = _format_section_name(critical_section, section)
        if brakes.temp_front_c > bp.fade_threshold_front_c - 10:
            events.append(SectionEvent(
                event_type="brake_hot_section",
                severity=min(1.0, (brakes.temp_front_c - (bp.fade_threshold_front_c - 10)) / 100.0),
                message=f"{section_name}: front brakes near critical temp",
            ))
        if regen_energy > 0.0 and critical_section.get("braking_energy_mj", 0) > 1.5:
            events.append(SectionEvent(
                event_type="regen_limit",
                severity=min(1.0, regen_energy / max(braking_energy, 0.01)),
                message=f"{section_name}: regen limit reached",
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

    return braking_efficiency, events, _format_temp_snapshot(brakes, config)
