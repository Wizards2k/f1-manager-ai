"""
TyreModel – Step 5a of update_section().

Two-layer thermal model (surface + core), grip calculation,
wear, graining/blistering/flatspot detection.

Reference: docs/lap-physics-spec-v0.5.md §3.3 Passo 5
           docs/TyreModel.md
           docs/degradation-and-consumption.md §5.1
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

from .data_types import (
    AeroForces,
    AeroSetup,
    BrakeState,
    CarState,
    CircuitConfig,
    CORNER_KINDS,
    DriverIntent,
    EnvContext,
    SectionContext,
    SectionEvent,
    SectionKind,
    TyreCompound,
    TyreCompoundParams,
    TyreState,
    WheelPosition,
    clamp,
    gaussian,
)
from .setup_penalty_v2 import is_setup_within_window
try:
    from python_backend.utils.tyre_debug_logger import is_tyre_debug_enabled, log_tyre_debug
except Exception:
    def is_tyre_debug_enabled() -> bool:
        return False

    def log_tyre_debug(payload: Dict[str, Any]) -> None:
        return None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRONT_WHEELS = {WheelPosition.LF, WheelPosition.RF}
REAR_WHEELS = {WheelPosition.LR, WheelPosition.RR}
STRAIGHT_KINDS = {SectionKind.STRAIGHT, SectionKind.MEDIUM_STRAIGHT}

_ASYM_INTENSITY_MIN = 0.10
_ASYM_INTENSITY_FULL = 0.35
_ASYM_BIAS_MAX_FRONT = 0.16
_ASYM_BIAS_MAX_REAR = 0.14
_ASYM_MIXED_DIRECTION_CAP = 0.30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_asymmetric_gate(section: SectionContext) -> float:
    if section.kind not in CORNER_KINDS:
        return 0.0
    intensity = clamp(getattr(section, "corner_intensity", 0.0) or 0.0, 0.0, 1.0)
    if intensity <= _ASYM_INTENSITY_MIN:
        return 0.0
    if intensity >= _ASYM_INTENSITY_FULL:
        gate = 1.0
    else:
        gate = (intensity - _ASYM_INTENSITY_MIN) / max(_ASYM_INTENSITY_FULL - _ASYM_INTENSITY_MIN, 1e-6)
    if getattr(section, "is_mixed_direction", False):
        gate *= _ASYM_MIXED_DIRECTION_CAP
    return clamp(gate, 0.0, 1.0)


def _get_lateral_biases(section: SectionContext) -> Tuple[float, float]:
    gate = _compute_asymmetric_gate(section)
    direction = (getattr(section, "curve_direction", "straight") or "straight").lower()
    if gate <= 0.0 or direction not in {"left", "right"}:
        return 0.0, 0.0
    dir_sign = -1.0 if direction == "left" else 1.0
    return dir_sign * _ASYM_BIAS_MAX_FRONT * gate, dir_sign * _ASYM_BIAS_MAX_REAR * gate


def _redistribute_axle_temperature_delta(
    left_tyre: TyreState,
    right_tyre: TyreState,
    before_left: Tuple[float, float],
    before_right: Tuple[float, float],
    bias: float,
) -> None:
    left_surface_before, left_core_before = before_left
    right_surface_before, right_core_before = before_right

    delta_surface_left = left_tyre.surface_temp_c - left_surface_before
    delta_surface_right = right_tyre.surface_temp_c - right_surface_before
    delta_core_left = left_tyre.core_temp_c - left_core_before
    delta_core_right = right_tyre.core_temp_c - right_core_before

    total_surface_delta = delta_surface_left + delta_surface_right
    total_core_delta = delta_core_left + delta_core_right

    left_share = clamp(0.5 + bias, 0.0, 1.0)
    right_share = 1.0 - left_share

    left_tyre.surface_temp_c = left_surface_before + total_surface_delta * left_share
    right_tyre.surface_temp_c = right_surface_before + total_surface_delta * right_share
    left_tyre.core_temp_c = left_core_before + total_core_delta * left_share
    right_tyre.core_temp_c = right_core_before + total_core_delta * right_share


def _refresh_tyre_effective_grip(
    tyre: TyreState,
    params: TyreCompoundParams,
    section: SectionContext,
    aero_setup: AeroSetup | None = None,
) -> None:
    thermal_factor_surface = gaussian(
        tyre.surface_temp_c,
        params.temp_opt_surface,
        params.gaussian_sigma_surface_c,
    )
    thermal_factor_core = gaussian(
        tyre.core_temp_c,
        params.temp_opt_core,
        params.gaussian_sigma_core_c,
    )
    thermal_factor = 0.6 * thermal_factor_surface + 0.4 * thermal_factor_core
    thermal_factor = clamp(thermal_factor, 0.82, 1.1)
    # Ridurre drasticamente l'impatto fisico diretto dell'usura (dal 30% al 12%)
    # L'usura pesa solo il 12% sul grip fisico per evitare crolli di 3s
    wear_factor = max(0.5, 1.0 - (tyre.wear_pct / 100.0) * 0.12)
    heat_cycle_factor = max(0.85, 1.0 - tyre.heat_cycles * params.heat_cycle_grip_penalty)
    slip_factor = 1.0
    if section.kind in CORNER_KINDS:
        slip_factor = 1.0 + (params.slip_sensitivity - 1.0) * 0.1

    setup_bonus = 1.0
    is_front = tyre.wheel_pos in FRONT_WHEELS
    if aero_setup is not None:
        if is_front:
            susp = aero_setup.suspension_front
            rh_dev = abs(aero_setup.ride_height_front_mm - aero_setup.ride_height_optimal_front_mm)
            antiroll = aero_setup.antiroll_front_rigidity
        else:
            susp = aero_setup.suspension_rear
            rh_dev = abs(aero_setup.ride_height_rear_mm - aero_setup.ride_height_optimal_rear_mm)
            antiroll = aero_setup.antiroll_rear_rigidity
        susp_bonus = (susp.efficiency - 0.8) * 0.15
        rh_penalty = rh_dev * 0.001
        antiroll_penalty = abs(antiroll - 0.5) * 0.02
        setup_bonus = clamp(1.0 + susp_bonus - rh_penalty - antiroll_penalty, 0.92, 1.05)

    tyre.effective_grip = (
        params.base_grip
        * thermal_factor
        * wear_factor
        * heat_cycle_factor
        * slip_factor
        * setup_bonus
    )


# ---------------------------------------------------------------------------
# Single-tyre thermal update
# ---------------------------------------------------------------------------

def _update_single_tyre(
    tyre: TyreState,
    params: TyreCompoundParams,
    section: SectionContext,
    env: EnvContext,
    aero: AeroForces,
    driver: DriverIntent,
    dt_s: float,
    v_kph: float,
    fuel_kg: float = 100.0,
    fuel_max_kg: float = 110.0,
    brake_state: BrakeState | None = None,
    aero_setup: AeroSetup | None = None,
    circuit_id: Optional[str] = None,
    setup_sliders: Optional[Dict[str, int]] = None,
    debug_ctx: Optional[Dict[str, str]] = None,
) -> List[SectionEvent]:
    """Update thermal state, wear and grip for one tyre. Returns events."""
    events: List[SectionEvent] = []
    is_front = tyre.wheel_pos in FRONT_WHEELS
    push_level = max(1, min(10, int(getattr(driver, "push_level", 10) or 10)))
    low_push_steps = max(0, 5 - push_level)
    low_push_heat_multiplier = max(0.72, 1.0 - low_push_steps * 0.06)
    low_push_cooling_bonus = 1.0 + low_push_steps * 0.08
    tyre_management_skill = max(0, min(100, int(getattr(driver, "tyre_management_skill", 70) or 70)))
    tyre_management_bonus = max(0.0, (tyre_management_skill - 85) / 15.0)
    push_five_cooling_bonus = 1.0
    if push_level == 5 and tyre_management_bonus > 0:
        push_five_cooling_bonus += min(0.06, tyre_management_bonus * 0.03)
    fuel_load_ratio = clamp(fuel_kg / max(fuel_max_kg, 1.0), 0.0, 1.0)
    fuel_heat_multiplier = 1.0 - fuel_load_ratio * 0.012
    fuel_straight_cooling_bonus = 1.0 + fuel_load_ratio * 0.01
    if driver.fuel_save_mode:
        fuel_heat_multiplier *= 0.99
        fuel_straight_cooling_bonus += 0.01

    # --- Heat generation ---
    # Base heat from section type
    base_heat = section.heat_factor * driver.pace_factor
    if low_push_steps > 0:
        base_heat *= low_push_heat_multiplier
    base_heat *= fuel_heat_multiplier

    section_time_heat_factor = 1.0
    if section.kind in CORNER_KINDS:
        section_time_heat_factor = 0.73 + min(0.33, dt_s / 8.0)

    cornering_heat = base_heat * section_time_heat_factor
    if section.kind.name == "VERY_SLOW_CORNER":
        cornering_heat *= 0.78
    elif section.kind.name == "SLOW_CORNER":
        cornering_heat *= 0.86
    instability_heat = 0.0
    mech_instability_heat = 0.0
    traction_heat = 0.0
    brake_contact_heat = 0.0
    brake_transfer_heat = 0.0
    surface_overtemp_pre_c = max(0.0, tyre.surface_temp_c - params.temp_opt_surface)
    core_overtemp_pre_c = max(0.0, tyre.core_temp_c - params.temp_opt_core)
    thermal_overtemp_factor = min(
        1.0,
        max(
            core_overtemp_pre_c / 8.0,
            surface_overtemp_pre_c / 10.0,
        ),
    )
    core_undertemp_pre_c = max(0.0, params.temp_opt_core - tyre.core_temp_c)
    compound_softness_factor = max(0.0, params.degradation_rate_multiplier - 1.0)
    compound_hardness_factor = max(0.0, 1.0 - params.degradation_rate_multiplier)
    green_balance_factor = 0.0
    if circuit_id and setup_sliders:
        try:
            green_balance_factor = 1.0 if is_setup_within_window(setup_sliders, circuit_id) else 0.0
        except Exception:
            green_balance_factor = 0.0
    slow_corner_overtemp_mitigation = 1.0
    if section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER"} and thermal_overtemp_factor > 0.0:
        slow_corner_overtemp_mitigation -= 0.08 * thermal_overtemp_factor
        slow_corner_overtemp_mitigation -= min(0.08, compound_softness_factor * 0.10 * thermal_overtemp_factor)
    if section.kind.name == "FAST_CORNER" and thermal_overtemp_factor > 0.0 and section.braking_energy_mj > 0.18:
        slow_corner_overtemp_mitigation -= min(0.06, thermal_overtemp_factor * 0.07 + compound_softness_factor * 0.03)
    cornering_heat *= slow_corner_overtemp_mitigation
    if green_balance_factor > 0.0 and section.kind in CORNER_KINDS:
        green_corner_heat_bonus = 0.08
        if section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER"}:
            green_corner_heat_bonus = 0.18
        elif section.kind.name == "MEDIUM_CORNER":
            green_corner_heat_bonus = 0.14
        cornering_heat *= 1.0 - green_balance_factor * green_corner_heat_bonus
    heavy_brake_overtemp_factor = 0.0
    if section.braking_energy_mj > 0.55 and thermal_overtemp_factor > 0.0:
        heavy_brake_overtemp_factor = min(1.0, thermal_overtemp_factor * (0.75 + min(0.25, section.braking_energy_mj / 2.0)))
    severe_heat_section_factor = 0.0
    if (
        section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER", "MEDIUM_CORNER"}
        and section.braking_energy_mj > 1.2
        and section.cool_factor <= 0.6
    ):
        severe_heat_section_factor = min(
            1.0,
            (thermal_overtemp_factor * 0.6)
            + compound_softness_factor * 0.5
            + min(0.3, dt_s / 12.0),
        )
    fast_brake_corner_factor = 0.0
    if section.kind.name == "FAST_CORNER" and section.braking_energy_mj > 0.18 and section.cool_factor <= 0.8:
        fast_brake_corner_factor = min(
            1.0,
            thermal_overtemp_factor * 0.45
            + compound_softness_factor * 0.35
            + min(0.18, max(0.0, getattr(section, "braking_energy_mj", 0.0) - 0.18) * 0.25),
        )

    # Axis-specific modifiers (spec §5.1 / degradation doc)
    if is_front:
        axis_multiplier = 1.0
        if section.kind in CORNER_KINDS:
            instability_heat = base_heat * aero.understeer_level * 0.26
        front_brake_temp_c = getattr(brake_state, "temp_front_c", 400.0) if brake_state is not None else 400.0
        brake_duct_opening = getattr(brake_state, "duct_opening", 0.5) if brake_state is not None else 0.5
        brake_bias_front_pct = getattr(brake_state, "bias_front_pct", 55.0) if brake_state is not None else 55.0
        brake_contact_heat = section.braking_energy_mj * (0.11 + max(0.0, (brake_bias_front_pct - 54.0)) * 0.002)
        if section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER"} and thermal_overtemp_factor > 0.0:
            brake_contact_heat *= 1.0 - 0.10 * thermal_overtemp_factor
        if heavy_brake_overtemp_factor > 0.0:
            brake_contact_heat *= 1.0 - 0.08 * heavy_brake_overtemp_factor
        if severe_heat_section_factor > 0.0:
            brake_contact_heat *= 1.0 - 0.12 * severe_heat_section_factor
        if fast_brake_corner_factor > 0.0:
            brake_contact_heat *= 1.0 - 0.10 * fast_brake_corner_factor
        brake_temp_excess = max(0.0, front_brake_temp_c - 560.0)
        duct_transfer_factor = 0.55 - brake_duct_opening * 0.12
        brake_transfer_heat = (brake_temp_excess / 1800.0) * duct_transfer_factor
        if section.kind in STRAIGHT_KINDS:
            brake_transfer_heat *= 0.12
        elif section.kind in CORNER_KINDS:
            brake_transfer_heat *= 0.18 + min(0.08, dt_s / 14.0)
            if section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER"} and thermal_overtemp_factor > 0.0:
                brake_transfer_heat *= 1.0 - 0.18 * thermal_overtemp_factor
            if heavy_brake_overtemp_factor > 0.0:
                brake_transfer_heat *= 1.0 - 0.14 * heavy_brake_overtemp_factor
            if severe_heat_section_factor > 0.0:
                brake_transfer_heat *= 1.0 - 0.18 * severe_heat_section_factor
            if fast_brake_corner_factor > 0.0:
                brake_transfer_heat *= 1.0 - 0.08 * fast_brake_corner_factor
        brake_heat = brake_contact_heat + brake_transfer_heat
        heat_gen = cornering_heat + brake_heat + instability_heat
        rear_instability_multiplier = 1.0
        traction_multiplier = 1.0
    else:
        axis_multiplier = 1.0
        # Traction heat on rear
        torque_ramp_approx = driver.pace_factor * 0.6 if section.kind in CORNER_KINDS else 0.0
        traction_multiplier = 1.0
        rear_core_overtemp_c = max(0.0, tyre.core_temp_c - params.temp_opt_core)
        rear_core_overtemp_factor = min(1.0, rear_core_overtemp_c / 8.0)
        if section.kind in CORNER_KINDS:
            if section.kind.name == "SLOW_CORNER":
                traction_section_factor = 0.78
            elif section.kind.name == "MEDIUM_CORNER":
                traction_section_factor = 0.60
            else:
                traction_section_factor = 0.34
            traction_heat = base_heat * torque_ramp_approx * 0.16 * traction_section_factor
            traction_heat *= 1.0 - 0.18 * rear_core_overtemp_factor
            if green_balance_factor > 0.0:
                green_traction_heat_bonus = 0.10
                if section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER"}:
                    green_traction_heat_bonus = 0.24
                elif section.kind.name == "MEDIUM_CORNER":
                    green_traction_heat_bonus = 0.16
                traction_heat *= 1.0 - green_balance_factor * green_traction_heat_bonus
            instability_heat = base_heat * aero.oversteer_level * 0.18
            instability_heat *= 1.0 - 0.12 * rear_core_overtemp_factor
            if section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER"} and thermal_overtemp_factor > 0.0:
                traction_heat *= 1.0 - 0.14 * thermal_overtemp_factor
                instability_heat *= 1.0 - 0.10 * thermal_overtemp_factor
        rear_instability_multiplier = 1.0
        if section.kind in CORNER_KINDS and aero_setup is not None:
            front_mech_balance = (
                aero_setup.suspension_front.rigidity
                + aero_setup.antiroll_front_rigidity
            )
            rear_mech_balance = (
                aero_setup.suspension_rear.rigidity
                + aero_setup.antiroll_rear_rigidity
            )
            mech_rear_bias = max(0.0, rear_mech_balance - front_mech_balance)
            mech_instability_heat = base_heat * mech_rear_bias * 0.13
            mech_instability_heat *= 1.0 - 0.10 * rear_core_overtemp_factor
            if section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER"} and thermal_overtemp_factor > 0.0:
                mech_instability_heat *= 1.0 - 0.10 * thermal_overtemp_factor
        heat_gen = cornering_heat + traction_heat + instability_heat + mech_instability_heat
        brake_heat = 0.0
        front_brake_temp_c = getattr(brake_state, "temp_front_c", None) if brake_state is not None else None
        brake_duct_opening = getattr(brake_state, "duct_opening", None) if brake_state is not None else None
        brake_bias_front_pct = getattr(brake_state, "bias_front_pct", None) if brake_state is not None else None

    # --- Heat dissipation ---
    air_speed_factor = max(v_kph / 280.0, 0.12)
    corner_cooling_factor = 1.0
    if section.kind in CORNER_KINDS:
        corner_cooling_factor += min(0.20, dt_s / 18.0)
    convective_cool_raw = (
        params.cooling_coeff
        * air_speed_factor
        * section.cool_factor
        * corner_cooling_factor
        * (1.0 - aero.airflow_penalty)
    )
    convective_cool = convective_cool_raw
    straight_cooling_multiplier = 1.0
    if section.kind in STRAIGHT_KINDS:
        straight_time_factor = min(1.0, dt_s / 8.0)
        straight_cooling_multiplier += 0.38 + straight_time_factor * 0.34
        surface_overtemp_c = max(0.0, tyre.surface_temp_c - params.temp_opt_surface)
        if surface_overtemp_c > 0.0:
            straight_surface_overtemp_factor = min(1.0, surface_overtemp_c / 10.0)
            straight_cooling_multiplier += (0.08 if is_front else 0.05) * straight_surface_overtemp_factor
        straight_cooling_multiplier *= fuel_straight_cooling_bonus
        convective_cool *= straight_cooling_multiplier
    if section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER", "MEDIUM_CORNER"}:
        surface_overtemp_pre_c = max(0.0, tyre.surface_temp_c - params.temp_opt_surface)
        if surface_overtemp_pre_c > 0.0 and section.cool_factor < 0.78:
            dense_surface_cooling_boost = min(0.18, surface_overtemp_pre_c * 0.012)
            if section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER"}:
                dense_surface_cooling_boost += 0.04
            if section.braking_energy_mj > 1.0:
                dense_surface_cooling_boost += min(0.05, (section.braking_energy_mj - 1.0) * 0.03)
            dense_surface_cooling_boost += min(0.04, max(0.0, 0.78 - section.cool_factor) * 0.20)
            convective_cool *= 1.0 + min(0.24, dense_surface_cooling_boost)
    if low_push_steps > 0:
        convective_cool *= low_push_cooling_bonus
    if push_level == 5:
        convective_cool *= push_five_cooling_bonus

    # --- Surface temperature ---
    delta_t_surface = (
        (heat_gen - convective_cool * (tyre.surface_temp_c - env.air_temp_c) * 0.01)
        / max(params.thermal_mass_surface, 0.1)
    ) * dt_s

    surface_temp_before = tyre.surface_temp_c
    core_temp_before = tyre.core_temp_c

    tyre.surface_temp_c += delta_t_surface

    # Conduction to track
    track_conduction = 0.005 * (tyre.surface_temp_c - env.track_temp_c)
    tyre.surface_temp_c -= track_conduction * dt_s

    # --- Core temperature (higher inertia) ---
    # Direct hysteresis/bulk heating inspired by docs/TyreModel_Thermal_Gemini
    hysteresis_severity = 0.0
    straight_overtemp_factor = 0.0
    if section.kind in STRAIGHT_KINDS:
        hysteresis_severity = 0.35 + min(0.25, dt_s / 10.0)
        straight_overtemp_factor = min(1.0, max(0.0, tyre.core_temp_c - params.temp_opt_core) / 10.0)
        if straight_overtemp_factor > 0.0:
            hysteresis_severity *= max(0.4, 1.0 - 0.45 * straight_overtemp_factor)
    elif section.kind in CORNER_KINDS:
        hysteresis_severity = 0.20 + min(0.18, v_kph / 600.0)
        if section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER"} and thermal_overtemp_factor > 0.0:
            hysteresis_severity *= 1.0 - 0.16 * thermal_overtemp_factor
    hysteresis_heat_core = (
        hysteresis_severity
        * driver.pace_factor
        * (0.4 + fuel_load_ratio * 0.6)
        * params.conduction_coeff
    )
    compound_is_soft_medium = params.degradation_rate_multiplier >= 0.8
    compound_is_hard = params.degradation_rate_multiplier <= 0.7
    compound_core_transfer_factor = 1.0
    if compound_is_soft_medium:
        compound_core_transfer_factor = 0.76 - compound_softness_factor * 0.18
    elif compound_is_hard:
        compound_core_transfer_factor = 0.92 + compound_hardness_factor * 0.14
    core_exchange = (
        params.conduction_coeff
        * 0.72
        * compound_core_transfer_factor
        * (tyre.surface_temp_c - tyre.core_temp_c)
    )
    core_overtemp_buffer_c = max(0.0, tyre.core_temp_c - (params.temp_opt_core - 0.5))
    soft_core_guard = 0.0
    if compound_softness_factor > 0.0:
        soft_core_guard = min(1.0, core_overtemp_buffer_c / 6.0)
    if tyre.surface_temp_c > tyre.core_temp_c:
        core_near_opt_factor = min(1.0, max(0.0, tyre.core_temp_c - (params.temp_opt_core - 1.0)) / 6.0)
        surface_core_gap_c = max(0.0, tyre.surface_temp_c - tyre.core_temp_c)
        if core_near_opt_factor > 0.0 and surface_core_gap_c > 6.0:
            transfer_trim = min(0.18, surface_core_gap_c * 0.01) * core_near_opt_factor
            if section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER"}:
                transfer_trim *= 1.15
            if severe_heat_section_factor > 0.0:
                transfer_trim += min(0.12, severe_heat_section_factor * 0.10)
            if compound_softness_factor > 0.0 and section.braking_energy_mj > 1.0:
                transfer_trim += min(0.08, compound_softness_factor * 0.08)
            surface_overtemp_c = max(0.0, tyre.surface_temp_c - params.temp_opt_surface)
            core_overtemp_pre_c = max(0.0, tyre.core_temp_c - params.temp_opt_core)
            dense_heat_section_factor = 0.0
            if section.kind.name in {"VERY_SLOW_CORNER", "SLOW_CORNER", "MEDIUM_CORNER"}:
                dense_heat_section_factor += 0.08
            if section.cool_factor < 0.75:
                dense_heat_section_factor += min(0.10, (0.75 - section.cool_factor) * 0.18)
            if section.braking_energy_mj > 1.0:
                dense_heat_section_factor += min(0.10, (section.braking_energy_mj - 1.0) * 0.06)
            if surface_overtemp_c > 0.0:
                transfer_trim += min(0.16, surface_overtemp_c * 0.012) * (0.45 + core_near_opt_factor * 0.55)
            if core_overtemp_pre_c > 0.0:
                transfer_trim += min(0.12, core_overtemp_pre_c * 0.015)
            transfer_trim += dense_heat_section_factor
            if core_overtemp_pre_c > 0.0 and surface_core_gap_c > 10.0:
                transfer_trim += min(0.10, (surface_core_gap_c - 10.0) * 0.01)
            if soft_core_guard > 0.0:
                transfer_trim += min(0.10, soft_core_guard * (0.05 + compound_softness_factor * 0.06))
            transfer_trim = min(0.46, transfer_trim)
            core_exchange *= 1.0 - transfer_trim
    if soft_core_guard > 0.0:
        soft_hysteresis_trim = min(0.16, soft_core_guard * (0.10 + compound_softness_factor * 0.12))
        if section.kind in CORNER_KINDS:
            soft_hysteresis_trim += min(0.06, soft_core_guard * 0.05)
        if compound_is_soft_medium:
            soft_hysteresis_trim += min(0.14, soft_core_guard * (0.08 + compound_softness_factor * 0.10))
        hysteresis_heat_core *= 1.0 - min(0.32, soft_hysteresis_trim)
    if compound_is_hard and tyre.surface_temp_c < params.temp_opt_surface:
        hard_surface_gap_c = min(18.0, params.temp_opt_surface - tyre.surface_temp_c)
        hard_core_gap_c = max(0.0, params.temp_opt_core - tyre.core_temp_c)
        hard_surface_hold = min(0.30, hard_surface_gap_c * 0.018)
        if section.kind in STRAIGHT_KINDS:
            hard_surface_hold += min(0.12, hard_core_gap_c * 0.012)
        tyre.surface_temp_c += hard_surface_hold * dt_s
    if core_undertemp_pre_c > 0.0 and tyre.surface_temp_c > tyre.core_temp_c:
        cold_recovery_factor = min(1.0, core_undertemp_pre_c / 6.0)
        compound_recovery_bias = 1.0 + max(0.0, 1.0 - params.degradation_rate_multiplier) * 0.35
        if params.degradation_rate_multiplier <= 0.7:
            compound_recovery_bias += 0.12
            if section.kind in STRAIGHT_KINDS or section.cool_factor >= 0.8:
                compound_recovery_bias += 0.08 + compound_hardness_factor * 0.05
        core_exchange *= 1.0 + cold_recovery_factor * 0.15 * compound_recovery_bias
    if (
        params.degradation_rate_multiplier <= 0.7
        and section.kind in STRAIGHT_KINDS
        and tyre.core_temp_c < params.temp_opt_core
    ):
        hard_compound_retention = min(0.12, (params.temp_opt_core - tyre.core_temp_c) * 0.02)
        if section.length_m >= 250.0:
            hard_compound_retention += min(0.08, section.length_m / 5000.0)
        hysteresis_heat_core *= 1.0 + hard_compound_retention
    straight_core_cooling_boost = 0.0
    straight_length_factor = 1.0
    if section.kind in STRAIGHT_KINDS:
        core_overtemp_c = max(0.0, tyre.core_temp_c - params.temp_opt_core)
        surface_overtemp_c = max(0.0, tyre.surface_temp_c - params.temp_opt_surface)
        if core_overtemp_c > 0.0:
            core_overtemp_factor = min(1.0, core_overtemp_c / 8.0)
            surface_support_factor = min(1.0, surface_overtemp_c / 12.0)
            straight_time_factor = 0.32 + min(0.48, dt_s / 10.0)
            axle_cooling_factor = 0.18 if is_front else 0.07
            temp_excess_vs_track = max(0.0, tyre.core_temp_c - env.track_temp_c)
            straight_length_factor = 0.82 + min(0.95, section.length_m / 1100.0)
            rear_cooling_balance = 1.0 if is_front else 0.32
            rear_length_factor = straight_length_factor if is_front else (0.76 + min(0.28, section.length_m / 2200.0))
            thermal_gradient_factor = 0.008 + min(0.020, temp_excess_vs_track * 0.00035)
            straight_core_cooling_boost = (
                params.conduction_coeff
                * air_speed_factor
                * straight_time_factor
                * fuel_straight_cooling_bonus
                * axle_cooling_factor
                * core_overtemp_c
                * (0.75 + surface_support_factor * 0.25)
                * thermal_gradient_factor
                * (1.0 + rear_length_factor * 0.24 * rear_cooling_balance)
            )
            if core_overtemp_c > 6.0 and temp_excess_vs_track > 18.0:
                track_pull = (
                    (core_overtemp_c - 6.0)
                    * (temp_excess_vs_track - 18.0)
                    * (0.00045 + rear_length_factor * 0.00022 * rear_cooling_balance)
                    * straight_time_factor
                )
                straight_core_cooling_boost += track_pull
            if compound_softness_factor > 0.0:
                soft_core_cooling_bonus = min(
                    0.18,
                    (0.05 + compound_softness_factor * 0.10)
                    * min(1.0, core_overtemp_c / 6.0),
                )
                straight_core_cooling_boost *= 1.0 + soft_core_cooling_bonus
            if compound_is_soft_medium:
                compound_overtemp_guard = min(1.0, max(0.0, tyre.core_temp_c - (params.temp_opt_core - 0.5)) / 5.0)
                if compound_overtemp_guard > 0.0:
                    straight_core_cooling_boost *= 1.0 + min(0.50, 0.22 + compound_overtemp_guard * 0.28)
    if compound_is_hard and tyre.surface_temp_c < params.temp_opt_surface and section.kind in STRAIGHT_KINDS:
        hard_surface_support = min(0.35, (params.temp_opt_surface - tyre.surface_temp_c) * 0.018)
        if section.length_m >= 180.0:
            hard_surface_support += min(0.12, section.length_m / 3000.0)
        tyre.surface_temp_c += hard_surface_support * dt_s
    delta_t_core = (
        core_exchange + hysteresis_heat_core - straight_core_cooling_boost
    ) / max(params.thermal_mass_core, 0.1) * dt_s
    tyre.core_temp_c += delta_t_core
    core_track_dissipation = 0.0016 * (tyre.core_temp_c - env.track_temp_c)
    tyre.core_temp_c -= core_track_dissipation * dt_s

    # Clamp temperatures
    tyre.surface_temp_c = clamp(tyre.surface_temp_c, env.air_temp_c - 5.0, 200.0)
    tyre.core_temp_c = clamp(tyre.core_temp_c, env.air_temp_c - 5.0, 180.0)

    if is_tyre_debug_enabled() and debug_ctx:
        log_tyre_debug({
            **debug_ctx,
            "wheel": tyre.wheel_pos.name,
            "section_kind": section.kind.name,
            "push_level": push_level,
            "pace_factor": driver.pace_factor,
            "base_heat": base_heat,
            "fuel_kg": fuel_kg,
            "fuel_load_ratio": fuel_load_ratio,
            "fuel_heat_multiplier": fuel_heat_multiplier,
            "fuel_straight_cooling_bonus": fuel_straight_cooling_bonus,
            "section_time_heat_factor": section_time_heat_factor,
            "cornering_heat": cornering_heat,
            "instability_heat": instability_heat,
            "mech_instability_heat": mech_instability_heat,
            "heat_low_push_multiplier": low_push_heat_multiplier if low_push_steps > 0 else 1.0,
            "axis_multiplier": axis_multiplier if 'axis_multiplier' in locals() else 1.0,
            "traction_multiplier": traction_multiplier if not is_front else 1.0,
            "rear_instability_multiplier": rear_instability_multiplier if not is_front else 1.0,
            "brake_contact_heat": brake_contact_heat,
            "brake_transfer_heat": brake_transfer_heat,
            "brake_heat": brake_heat,
            "front_brake_temp_c_local": front_brake_temp_c,
            "brake_duct_opening": brake_duct_opening,
            "brake_bias_front_pct": brake_bias_front_pct,
            "traction_heat": traction_heat,
            "hysteresis_heat_core": hysteresis_heat_core,
            "straight_core_cooling_boost": straight_core_cooling_boost,
            "straight_overtemp_factor": straight_overtemp_factor,
            "heat_gen_total": heat_gen,
            "convective_cool_raw": convective_cool_raw,
            "convective_cool": convective_cool,
            "corner_cooling_factor": corner_cooling_factor,
            "straight_cooling_multiplier": straight_cooling_multiplier,
            "surface_temp_before": surface_temp_before,
            "surface_temp_after": tyre.surface_temp_c,
            "core_temp_before": core_temp_before,
            "core_temp_after": tyre.core_temp_c,
            "air_speed_factor": air_speed_factor,
            "section_heat_factor": section.heat_factor,
            "section_cool_factor": section.cool_factor,
        })

    # --- Wear ---
    section_km = section.length_m / 1000.0
    wear_rate = params.wear_rate_base_pct_per_km * driver.pace_factor
    # Compound degradation multiplier (C1=0.6x ... C6=1.8x)
    wear_rate *= params.degradation_rate_multiplier
    # Multipliers from degradation spec
    wear_rate *= (1.0 + aero.bump_penalty + aero.kerb_severity)
    wear_rate *= (1.0 + aero.handling_penalty + 0.0)  # fade_level added by brake step
    if not is_front:
        wear_rate *= (1.0 + driver.pace_factor * 0.25)  # torque ramp effect

    # Tyre save mode
    if driver.tyre_save_mode:
        wear_rate *= 0.85

    tyre.wear_pct += wear_rate * section_km
    tyre.wear_pct = clamp(tyre.wear_pct, 0.0, 100.0)

    # --- Grip calculation ---
    thermal_factor_surface = gaussian(
        tyre.surface_temp_c,
        params.temp_opt_surface,
        params.gaussian_sigma_surface_c,
    )
    thermal_factor_core = gaussian(
        tyre.core_temp_c,
        params.temp_opt_core,
        params.gaussian_sigma_core_c,
    )
    # Combined thermal factor (surface-weighted)
    thermal_factor = 0.6 * thermal_factor_surface + 0.4 * thermal_factor_core
    thermal_factor = clamp(thermal_factor, 0.82, 1.1)

    # Ridurre l'impatto fisico diretto dell'usura (12%)
    wear_factor = max(0.5, 1.0 - (tyre.wear_pct / 100.0) * 0.12)

    # Heat-cycle penalty (tyre-allocation §5)
    heat_cycle_factor = max(0.85, 1.0 - tyre.heat_cycles * params.heat_cycle_grip_penalty)

    # Slip sensitivity: amplifies grip loss in corners (spec §6)
    slip_factor = 1.0
    if section.kind in CORNER_KINDS:
        slip_factor = 1.0 + (params.slip_sensitivity - 1.0) * 0.1

    # Setup bonus from suspension/antiroll/ride_height (§6.8)
    setup_bonus = 1.0
    if aero_setup is not None:
        if is_front:
            susp = aero_setup.suspension_front
            rh_dev = abs(aero_setup.ride_height_front_mm - aero_setup.ride_height_optimal_front_mm)
            antiroll = aero_setup.antiroll_front_rigidity
        else:
            susp = aero_setup.suspension_rear
            rh_dev = abs(aero_setup.ride_height_rear_mm - aero_setup.ride_height_optimal_rear_mm)
            antiroll = aero_setup.antiroll_rear_rigidity

        # Suspension efficiency: 0.8 default → 1.0 perfect → bonus up to +3%
        susp_bonus = (susp.efficiency - 0.8) * 0.15  # 0.8→0, 1.0→+0.03
        # Ride height: deviation from optimal penalises grip (10mm off → -1%)
        rh_penalty = rh_dev * 0.001
        # Antiroll: 0.5 = balanced, deviation penalises (too soft or stiff)
        antiroll_penalty = abs(antiroll - 0.5) * 0.02

        setup_bonus = clamp(1.0 + susp_bonus - rh_penalty - antiroll_penalty, 0.92, 1.05)

    tyre.effective_grip = (
        params.base_grip
        * thermal_factor
        * wear_factor
        * heat_cycle_factor
        * slip_factor
        * setup_bonus
    )

    # --- Health flags & events ---
    window_max_surface = params.temp_window_surface_c[2]
    window_min_surface = params.temp_window_surface_c[0]

    # Overheat
    if tyre.surface_temp_c > window_max_surface + 10:
        tyre.overheat_warning = True
        events.append(SectionEvent(
            event_type="tyre_overheat",
            severity=0.6,
            message=f"{tyre.wheel_pos.value} tyre overheating",
        ))
    else:
        tyre.overheat_warning = False

    # Cold
    if tyre.surface_temp_c < window_min_surface - 5:
        tyre.cold_warning = True
    else:
        tyre.cold_warning = False

    # Puncture risk
    if tyre.wear_pct > 80.0:
        tyre.puncture_risk += driver.pace_factor * 0.01
        events.append(SectionEvent(
            event_type="tyre_puncture_risk",
            severity=tyre.puncture_risk,
            message=f"{tyre.wheel_pos.value} tyre wear critical",
        ))

    # Graining: temporal trigger (spec §8 — accumulate time below window)
    window_min_core = params.temp_window_core_c[0]
    window_max_core = params.temp_window_core_c[2]
    if tyre.surface_temp_c < window_min_surface and aero.understeer_level > 0.15:
        tyre.graining_time_acc_s += dt_s
    else:
        tyre.graining_time_acc_s = max(0.0, tyre.graining_time_acc_s - dt_s * 0.5)

    # In-track cleaning: if tyre stays in optimal window, reduce graining
    window_tolerance = 2.0  # ±2°C from optimal window
    in_optimal_window = (
        window_min_surface - window_tolerance <= tyre.surface_temp_c <= window_max_surface + window_tolerance
        and window_min_core - window_tolerance <= tyre.core_temp_c <= window_max_core + window_tolerance
    )
    if in_optimal_window and tyre.graining_level > 0.0:
        # Clean graining when in optimal window for 60+ seconds
        tyre.graining_time_acc_s = max(0.0, tyre.graining_time_acc_s - dt_s * 2.0)  # Faster decay
        if tyre.graining_time_acc_s <= 0.0:
            tyre.graining_level = max(0.0, tyre.graining_level - dt_s * 0.1)  # Gradual cleaning

    if tyre.graining_time_acc_s >= params.graining_time_threshold_s:
        tyre.graining_level += 0.02 * (tyre.graining_time_acc_s / params.graining_time_threshold_s)
        tyre.graining_level = clamp(tyre.graining_level, 0.0, 1.0)
        if tyre.graining_level > 0.3:
            events.append(SectionEvent(
                event_type="tyre_graining",
                severity=tyre.graining_level,
                message=f"{tyre.wheel_pos.value} tyre graining",
            ))

    # Flatspot from kerb + braking
    if aero.kerb_impact > 0 and is_front:
        tyre.flatspot_severity += aero.kerb_severity * 0.01
        tyre.flatspot_severity = clamp(tyre.flatspot_severity, 0.0, 1.0)

    # Blistering: temporal trigger (spec §8 — accumulate time above window)
    is_overheated = (
        tyre.surface_temp_c > window_max_surface + 3
        or tyre.core_temp_c > window_max_core + 3
    )
    if is_overheated:
        tyre.blistering_time_acc_s += dt_s
    else:
        tyre.blistering_time_acc_s = max(0.0, tyre.blistering_time_acc_s - dt_s * 0.5)

    # In-track cleaning: if tyre stays in optimal window, reduce blistering
    if in_optimal_window and tyre.blistering_level > 0.0:
        # Clean blistering when in optimal window for 60+ seconds
        tyre.blistering_time_acc_s = max(0.0, tyre.blistering_time_acc_s - dt_s * 2.0)  # Faster decay
        if tyre.blistering_time_acc_s <= 0.0:
            tyre.blistering_level = max(0.0, tyre.blistering_level - dt_s * 0.05)  # Gradual cleaning

    if tyre.blistering_time_acc_s >= params.blistering_time_threshold_s:
        tyre.blistering_level += 0.015 * (tyre.blistering_time_acc_s / params.blistering_time_threshold_s)
        tyre.blistering_level = clamp(tyre.blistering_level, 0.0, 1.0)
        if tyre.blistering_level > 0.3:
            events.append(SectionEvent(
                event_type="tyre_blistering",
                severity=tyre.blistering_level,
                message=f"{tyre.wheel_pos.value} tyre blistering",
            ))

    return events


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def update_tyres(
    car_state: CarState,
    section: SectionContext,
    env: EnvContext,
    aero: AeroForces,
    driver: DriverIntent,
    config: CircuitConfig,
    dt_s: float,
    v_kph: float,
    aero_setup: AeroSetup | None = None,
    setup_sliders: Optional[Dict[str, int]] = None,
) -> Tuple[float, float, List[SectionEvent]]:
    """
    Update all four tyres and return effective grip per axis.

    Returns
    -------
    effective_grip_front : float
    effective_grip_rear : float
    events : list of SectionEvent
    """
    all_events: List[SectionEvent] = []
    debug_ctx_base: Optional[Dict[str, Any]] = None
    if is_tyre_debug_enabled():
        brakes = getattr(car_state, "brakes", None)
        debug_ctx_base = {
            "car_id": getattr(car_state, "car_id", "car"),
            "lap_number": getattr(car_state, "lap_number", 0),
            "section_id": getattr(section, "section_id", "unknown"),
            "section_index": getattr(car_state, "current_section_idx", -1),
            "section_length_m": section.length_m,
            "dt_s": dt_s,
            "v_kph": v_kph,
            "air_temp_c": env.air_temp_c,
            "track_temp_c": env.track_temp_c,
            "brake_temp_front_c": getattr(brakes, "temp_front_c", None),
            "brake_temp_rear_c": getattr(brakes, "temp_rear_c", None),
        }

    tyre_temps_before: Dict[WheelPosition, Tuple[float, float]] = {
        wp: (tyre.surface_temp_c, tyre.core_temp_c)
        for wp, tyre in car_state.tyres.items()
    }
    tyre_params_by_wp: Dict[WheelPosition, TyreCompoundParams] = {}

    for wp, tyre in car_state.tyres.items():
        params = config.tyre_params.get(tyre.compound)
        if params is None:
            params = config.tyre_params.get(TyreCompound.C3, TyreCompoundParams(compound=TyreCompound.C3))
        tyre_params_by_wp[wp] = params
        debug_ctx = None
        if debug_ctx_base is not None:
            debug_ctx = {
                **debug_ctx_base,
                "wheel": wp.name,
                "tyre_surface_temp_c": tyre.surface_temp_c,
                "tyre_core_temp_c": tyre.core_temp_c,
                "tyre_wear_pct": tyre.wear_pct,
            }
        evts = _update_single_tyre(
            tyre,
            params,
            section,
            env,
            aero,
            driver,
            dt_s,
            v_kph,
            car_state.pu.fuel_kg,
            config.fuel_max_kg,
            car_state.brakes,
            aero_setup,
            config.circuit_id,
            setup_sliders,
            debug_ctx,
        )
        all_events.extend(evts)

    front_bias, rear_bias = _get_lateral_biases(section)
    left_front = car_state.tyres.get(WheelPosition.LF)
    right_front = car_state.tyres.get(WheelPosition.RF)
    left_rear = car_state.tyres.get(WheelPosition.LR)
    right_rear = car_state.tyres.get(WheelPosition.RR)

    if left_front is not None and right_front is not None and front_bias != 0.0:
        _redistribute_axle_temperature_delta(
            left_front,
            right_front,
            tyre_temps_before[WheelPosition.LF],
            tyre_temps_before[WheelPosition.RF],
            front_bias,
        )
    if left_rear is not None and right_rear is not None and rear_bias != 0.0:
        _redistribute_axle_temperature_delta(
            left_rear,
            right_rear,
            tyre_temps_before[WheelPosition.LR],
            tyre_temps_before[WheelPosition.RR],
            rear_bias,
        )

    for wp, tyre in car_state.tyres.items():
        params = tyre_params_by_wp.get(wp)
        if params is None:
            continue
        _refresh_tyre_effective_grip(
            tyre,
            params,
            section,
            aero_setup,
        )

    if is_tyre_debug_enabled() and debug_ctx_base:
        log_tyre_debug({
            **debug_ctx_base,
            "wheel": "allocator",
            "curve_direction": getattr(section, "curve_direction", "straight"),
            "corner_intensity": getattr(section, "corner_intensity", 0.0),
            "is_mixed_direction": getattr(section, "is_mixed_direction", False),
            "front_bias": front_bias,
            "rear_bias": rear_bias,
        })

    # Average grip per axis
    front_grips = [
        car_state.tyres[wp].effective_grip
        for wp in FRONT_WHEELS
        if wp in car_state.tyres
    ]
    rear_grips = [
        car_state.tyres[wp].effective_grip
        for wp in REAR_WHEELS
        if wp in car_state.tyres
    ]

    eff_grip_front = sum(front_grips) / max(len(front_grips), 1)
    eff_grip_rear = sum(rear_grips) / max(len(rear_grips), 1)

    return eff_grip_front, eff_grip_rear, all_events


# ---------------------------------------------------------------------------
# Initial temperature setup
# ---------------------------------------------------------------------------

def set_optimal_initial_temperatures(
    car_state: CarState,
    circuit_id: str,
    env: EnvContext | None = None,
) -> None:
    """
    Imposta le temperature iniziali delle gomme nella finestra ottimale
    per il compound specifico e il circuito.
    
    Args:
        car_state: Stato dell'auto con le gomme da inizializzare
        circuit_id: ID del circuito (es. "mc-1929_monaco")
        env: Contesto ambientale (opzionale, per log di debug)
    """
    from .config_loader import load_circuit_config
    
    try:
        config = load_circuit_config(circuit_id)
        
        for tyre in car_state.tyres.values():
            compound_params = config.tyre_params[tyre.compound]
            
            # Usa il valore centrale della finestra come temperatura ottimale
            optimal_surface = compound_params.temp_window_surface_c[1]  # [min, optimal, max]
            optimal_core = compound_params.temp_window_core_c[1]        # [min, optimal, max]
            
            # Imposta le temperature ottimali
            tyre.surface_temp_c = optimal_surface
            tyre.core_temp_c = optimal_core
                
    except Exception:
        # Fallback: se qualcosa va storto, mantieni le temperature esistenti
        pass
