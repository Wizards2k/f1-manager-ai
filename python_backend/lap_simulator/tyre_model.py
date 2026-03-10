"""
TyreModel – Step 5a of update_section().

Two-layer thermal model (surface + core), grip calculation,
wear, graining/blistering/flatspot detection.

Reference: docs/lap-physics-spec-v0.5.md §3.3 Passo 5
           docs/TyreModel.md
           docs/degradation-and-consumption.md §5.1
"""
from __future__ import annotations

from typing import Dict, List, Tuple, Optional

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
from utils.tyre_debug_logger import is_tyre_debug_enabled, log_tyre_debug


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRONT_WHEELS = {WheelPosition.LF, WheelPosition.RF}
REAR_WHEELS = {WheelPosition.LR, WheelPosition.RR}
STRAIGHT_KINDS = {SectionKind.STRAIGHT, SectionKind.MEDIUM_STRAIGHT}

_TYRE_DEBUG_ENABLED = is_tyre_debug_enabled()


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
    brake_state: BrakeState | None = None,
    aero_setup: AeroSetup | None = None,
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

    # --- Heat generation ---
    # Base heat from section type
    base_heat = section.heat_factor * driver.pace_factor
    if low_push_steps > 0:
        base_heat *= low_push_heat_multiplier

    section_time_heat_factor = 1.0
    if section.kind in CORNER_KINDS:
        section_time_heat_factor = 0.75 + min(0.35, dt_s / 8.0)

    cornering_heat = base_heat * section_time_heat_factor
    instability_heat = 0.0
    mech_instability_heat = 0.0
    traction_heat = 0.0
    brake_contact_heat = 0.0
    brake_transfer_heat = 0.0

    # Axis-specific modifiers (spec §5.1 / degradation doc)
    if is_front:
        axis_multiplier = 1.0
        if section.kind in CORNER_KINDS:
            instability_heat = base_heat * aero.understeer_level * 0.28
        front_brake_temp_c = getattr(brake_state, "temp_front_c", 400.0) if brake_state is not None else 400.0
        brake_duct_opening = getattr(brake_state, "duct_opening", 0.5) if brake_state is not None else 0.5
        brake_bias_front_pct = getattr(brake_state, "bias_front_pct", 55.0) if brake_state is not None else 55.0
        brake_contact_heat = section.braking_energy_mj * (0.11 + max(0.0, (brake_bias_front_pct - 54.0)) * 0.002)
        brake_temp_excess = max(0.0, front_brake_temp_c - 560.0)
        duct_transfer_factor = 0.55 - brake_duct_opening * 0.12
        brake_transfer_heat = (brake_temp_excess / 1800.0) * duct_transfer_factor
        if section.kind in STRAIGHT_KINDS:
            brake_transfer_heat *= 0.12
        elif section.kind in CORNER_KINDS:
            brake_transfer_heat *= 0.18 + min(0.08, dt_s / 14.0)
        brake_heat = brake_contact_heat + brake_transfer_heat
        heat_gen = cornering_heat + brake_heat + instability_heat
        rear_instability_multiplier = 1.0
        traction_multiplier = 1.0
    else:
        axis_multiplier = 1.0
        # Traction heat on rear
        torque_ramp_approx = driver.pace_factor * 0.6 if section.kind in CORNER_KINDS else 0.0
        traction_multiplier = 1.0
        if section.kind in CORNER_KINDS:
            if section.kind.name == "SLOW_CORNER":
                traction_section_factor = 1.0
            elif section.kind.name == "MEDIUM_CORNER":
                traction_section_factor = 0.8
            else:
                traction_section_factor = 0.45
            traction_heat = base_heat * torque_ramp_approx * 0.24 * traction_section_factor
            instability_heat = base_heat * aero.oversteer_level * 0.30
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
            mech_instability_heat = base_heat * mech_rear_bias * 0.22
        heat_gen = cornering_heat + traction_heat + instability_heat + mech_instability_heat
        brake_heat = 0.0
        front_brake_temp_c = getattr(brake_state, "temp_front_c", None) if brake_state is not None else None
        brake_duct_opening = getattr(brake_state, "duct_opening", None) if brake_state is not None else None
        brake_bias_front_pct = getattr(brake_state, "bias_front_pct", None) if brake_state is not None else None

    # --- Heat dissipation ---
    air_speed_factor = max(v_kph / 280.0, 0.12)
    corner_cooling_factor = 1.0
    if section.kind in CORNER_KINDS:
        corner_cooling_factor += min(0.16, dt_s / 20.0)
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
        convective_cool *= straight_cooling_multiplier
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
    core_exchange = params.conduction_coeff * 0.72 * (tyre.surface_temp_c - tyre.core_temp_c)
    delta_t_core = core_exchange / max(params.thermal_mass_core, 0.1) * dt_s
    tyre.core_temp_c += delta_t_core
    core_track_dissipation = 0.0016 * (tyre.core_temp_c - env.track_temp_c)
    tyre.core_temp_c -= core_track_dissipation * dt_s

    # Clamp temperatures
    tyre.surface_temp_c = clamp(tyre.surface_temp_c, env.air_temp_c - 5.0, 200.0)
    tyre.core_temp_c = clamp(tyre.core_temp_c, env.air_temp_c - 5.0, 180.0)

    if _TYRE_DEBUG_ENABLED and debug_ctx:
        log_tyre_debug({
            **debug_ctx,
            "wheel": tyre.wheel_pos.name,
            "section_kind": section.kind.name,
            "push_level": push_level,
            "pace_factor": driver.pace_factor,
            "base_heat": base_heat,
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

    wear_factor = max(0.5, 1.0 - tyre.wear_pct / 100.0)

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
    if tyre.surface_temp_c < window_min_surface and aero.understeer_level > 0.15:
        tyre.graining_time_acc_s += dt_s
    else:
        tyre.graining_time_acc_s = max(0.0, tyre.graining_time_acc_s - dt_s * 0.5)

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
    window_max_core = params.temp_window_core_c[2]
    is_overheated = (
        tyre.surface_temp_c > window_max_surface + 3
        or tyre.core_temp_c > window_max_core + 3
    )
    if is_overheated:
        tyre.blistering_time_acc_s += dt_s
    else:
        tyre.blistering_time_acc_s = max(0.0, tyre.blistering_time_acc_s - dt_s * 0.5)

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
    if _TYRE_DEBUG_ENABLED:
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

    for wp, tyre in car_state.tyres.items():
        params = config.tyre_params.get(tyre.compound)
        if params is None:
            params = config.tyre_params.get(TyreCompound.C3, TyreCompoundParams(compound=TyreCompound.C3))
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
            car_state.brakes,
            aero_setup,
            debug_ctx,
        )
        all_events.extend(evts)

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
