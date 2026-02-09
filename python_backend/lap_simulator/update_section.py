"""
Car.update_section() – orchestrates Steps 1-8 of the physics loop.

This is the core function that computes the time a single car takes
to traverse one circuit section, updating all internal state.

Reference: docs/lap-physics-spec-v0.5.md §3.3 (Passi 1-8)
"""
from __future__ import annotations

from typing import List

from .aero_package import compute_forces
from .brake_system import update_brakes
from .data_types import (
    AeroForces,
    AeroSetup,
    CarState,
    CircuitConfig,
    CURVE_FACTOR,
    DriverIntent,
    DriverSkills,
    EnvContext,
    SectionContext,
    SectionEvent,
    SectionKind,
    SectionResult,
    clamp,
)
from .driver_model import compute_inputs, update_mental_state
from .power_unit import generate_output
from .tyre_model import update_tyres


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def update_section(
    car_state: CarState,
    aero_setup: AeroSetup,
    driver_skills: DriverSkills,
    section: SectionContext,
    env: EnvContext,
    config: CircuitConfig,
    push_level: float = 1.0,
    airflow_penalty: float = 0.0,
    traffic_v_max_kph: float = 0.0,
) -> SectionResult:
    """
    Compute the physics for one car traversing one section.

    Parameters
    ----------
    car_state : CarState       – mutable state (updated in-place)
    aero_setup : AeroSetup     – car's aero configuration
    driver_skills : DriverSkills – static driver ratings
    section : SectionContext    – current circuit section
    env : EnvContext            – environmental conditions
    config : CircuitConfig      – circuit + tuning parameters
    push_level : float          – player push command (0.8-1.1)
    airflow_penalty : float     – dirty air (0-1)
    traffic_v_max_kph : float   – speed constraint from car ahead (0 = none)
    """
    all_events: List[SectionEvent] = []

    # ===================================================================
    # STEP 1 – Input & initial state (Passo 1)
    # ===================================================================
    v_base = section.v_base_kph
    v_estimate = v_base  # initial speed estimate for calculations

    # ===================================================================
    # STEP 2 – Driver decision (Passo 2)
    # ===================================================================
    driver_intent = compute_inputs(
        skills=driver_skills,
        mental=car_state.driver_mental,
        section=section,
        env=env,
        car_state=car_state,
        config=config,
        push_level=push_level,
    )

    # ===================================================================
    # STEP 3 – Aero forces (Passo 3)
    # ===================================================================
    drs_active = section.drs_available and not car_state.side_by_side
    aero_forces = compute_forces(
        aero=aero_setup,
        section=section,
        env=env,
        car_state=car_state,
        config=config,
        v_kph=v_estimate,
        airflow_penalty=airflow_penalty,
        drs_active=drs_active,
    )

    # ===================================================================
    # STEP 4 – Power Unit (Passo 4)
    # ===================================================================
    dt_estimate = section.length_m / max(v_estimate / 3.6, 1.0)

    car_state.pu, pu_events = generate_output(
        pu_state=car_state.pu,
        driver_intent=driver_intent,
        aero_forces=aero_forces,
        section=section,
        env=env,
        config=config,
        dt_estimate_s=dt_estimate,
    )
    all_events.extend(pu_events)

    # Update cooling margin now that PU demand is known
    pu_map = config.pu_maps.get(car_state.pu.active_map)
    if pu_map:
        cooling_demand = pu_map.heat_load_kw / 1000.0
        aero_forces.cooling_margin = aero_forces.cooling_capacity - cooling_demand

    total_power_kw = car_state.pu.ice_power_kw + car_state.pu.ers_output_kw

    # ===================================================================
    # STEP 5 – Tyres & Brakes (Passo 5)
    # ===================================================================
    eff_grip_front, eff_grip_rear, tyre_events = update_tyres(
        car_state=car_state,
        section=section,
        env=env,
        aero=aero_forces,
        driver=driver_intent,
        config=config,
        dt_s=dt_estimate,
        v_kph=v_estimate,
    )
    all_events.extend(tyre_events)

    braking_efficiency, brake_events = update_brakes(
        car_state=car_state,
        section=section,
        env=env,
        aero=aero_forces,
        driver=driver_intent,
        config=config,
        dt_s=dt_estimate,
        v_kph=v_estimate,
    )
    all_events.extend(brake_events)

    # ===================================================================
    # STEP 6 – Effective speed & dt (Passo 6)
    # ===================================================================
    curve_factor = CURVE_FACTOR.get(section.kind, 0.0)
    is_corner = section.kind in (
        SectionKind.SLOW_CORNER,
        SectionKind.MEDIUM_CORNER,
        SectionKind.FAST_CORNER,
    )

    if is_corner:
        # --- Corner speed ---
        curvature_factor = section.curve_profile.curvature_factor
        if curvature_factor == 0.0:
            curvature_factor = curve_factor

        df_available = aero_forces.df_front_eff + aero_forces.df_rear_eff
        v_curve = v_base * (
            1.0 + curvature_factor * config.k_df
            * (df_available - config.df_ref) / max(config.df_ref, 1.0)
        )
        v_curve *= (1.0 - aero_forces.handling_penalty)
        v_curve *= 1.0 + (driver_intent.pace_factor - 1.0) * driver_intent.aggression_curve_bonus

        # Braking efficiency
        drag_curve_penalty = config.k_drag_curve * (aero_forces.drag_eff - config.drag_ref)
        v_curve = (v_curve * braking_efficiency) - drag_curve_penalty

        # Grip limit
        grip_axis = eff_grip_front if curve_factor >= 0.5 else eff_grip_rear
        v_grip_limited = v_curve * grip_axis

        v_effective = min(v_grip_limited, config.v_cap_kph)
    else:
        # --- Straight speed ---
        delta_power = config.k_power * (total_power_kw - config.power_ref_kw)
        delta_drag = config.k_drag * (aero_forces.drag_eff - config.drag_ref)
        v_straight = min(v_base + delta_power - delta_drag, config.v_cap_kph)

        v_effective = v_straight

    # Traffic constraint
    if traffic_v_max_kph > 0:
        v_effective = min(v_effective, traffic_v_max_kph)

    # Floor
    v_effective = max(v_effective, config.v_min_kph)

    # --- Penalty events ---
    for evt in all_events:
        if evt.event_type == "tyre_overheat":
            v_effective *= 0.98
        if evt.event_type == "ice_derating":
            # Power already reduced in PU step; small additional speed penalty
            v_effective *= 0.99

    # --- Section time ---
    v_ms = max(v_effective / 3.6, 1.0)
    dt_s = section.length_m / v_ms

    # ===================================================================
    # STEP 7 – Internal state update (Passo 7)
    # ===================================================================
    # Fuel already updated in PU step
    # ERS already updated in PU step
    # Tyres already updated in tyre step
    # Brakes already updated in brake step

    # Driver mental state
    expected_dt = section.length_m / max(v_base / 3.6, 1.0)
    section_performance = dt_s / max(expected_dt, 0.01)
    events_severity = sum(e.severity for e in all_events)

    update_mental_state(
        mental=car_state.driver_mental,
        skills=driver_skills,
        section_performance=section_performance,
        events_severity=events_severity,
    )

    # Lap tracking
    car_state.lap_time_acc_s += dt_s
    car_state.section_progress = 1.0  # completed this section

    # Battle cooldowns
    if car_state.attack_cooldown > 0:
        car_state.attack_cooldown -= 1
    if car_state.defense_reset > 0:
        car_state.defense_reset -= 1

    # ===================================================================
    # STEP 8 – Return (Passo 8)
    # ===================================================================
    late_brake = any(e.event_type == "late_brake_success" for e in all_events)

    return SectionResult(
        dt_s=dt_s,
        v_exit_kph=v_effective,
        v_effective_kph=v_effective,
        events=all_events,
        overtake_window=car_state.overtake_window,
        section_progress=1.0,
        braking_efficiency=braking_efficiency,
        late_brake_tag=late_brake,
        df_available=aero_forces.df_total,
        drag_eff=aero_forces.drag_eff,
        power_kw=total_power_kw,
        effective_grip_front=eff_grip_front,
        effective_grip_rear=eff_grip_rear,
        handling_penalty=aero_forces.handling_penalty,
    )
