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
    CORNER_KINDS,
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
    
    # Store aero_forces in car_state for UI and telemetry
    car_state.aero_forces = aero_forces

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
        aero_setup=aero_setup,
    )
    all_events.extend(tyre_events)

    braking_efficiency, brake_events, brake_snapshot = update_brakes(
        car_state=car_state,
        section=section,
        env=env,
        aero=aero_forces,
        driver=driver_intent,
        config=config,
        dt_s=dt_estimate,
        v_kph=v_estimate,
        driver_skills=driver_skills,
    )
    car_state.brakes.snapshot = brake_snapshot
    all_events.extend(brake_events)

    # ===================================================================
    # STEP 6 – Section time via dt_ref penalty model (Passo 6)
    # ===================================================================
    is_corner = section.kind in CORNER_KINDS

    if section.dt_ref_s > 0:
        # ---------------------------------------------------------------
        # dt_ref penalty model: dt = dt_ref × (1 + baseline + Σ penalties)
        # ---------------------------------------------------------------

        # Δ_aero: aero contribution (corners: more DF = faster; straights: more drag = slower)
        df_available = aero_forces.df_front_eff + aero_forces.df_rear_eff
        if is_corner:
            delta_aero = config.k_aero_penalty * (1.0 - df_available / max(config.df_ref, 1.0))
        else:
            delta_aero = config.k_aero_penalty * (aero_forces.drag_eff / max(config.drag_ref, 1.0) - 1.0)
        delta_aero -= config.k_aero_penalty * aero_forces.handling_penalty

        # Δ_grip: tyre grip contribution (§6.8 tuned)
        # Reference grip ~0.7 = neutral (new tyres at operating temp).
        # Only penalise when grip drops below reference; reward when above.
        grip_avg = (eff_grip_front + eff_grip_rear) / 2.0
        grip_ref = 0.70
        delta_grip = config.k_grip_penalty * (grip_ref - grip_avg) / grip_ref

        # Δ_brake: brake fade (only on sections with braking)
        if section.braking_energy_mj > 0.05:
            delta_brake = config.k_brake_penalty * (1.0 - braking_efficiency)
        else:
            delta_brake = 0.0

        # Δ_fuel: fuel weight penalty (§6.7)
        # Heavier car is slower everywhere, but corners suffer more (mass → less cornering grip)
        fuel_ratio = car_state.pu.fuel_kg / max(config.fuel_max_kg, 1.0)
        corner_fuel_mult = 1.3 if is_corner else 1.0  # corners penalised 30% more
        delta_fuel = config.k_fuel_penalty * fuel_ratio * corner_fuel_mult

        # Δ_driver: driver skill (pace_factor 1.0 = VER level = no penalty)
        delta_driver = config.k_driver_penalty * (1.0 - driver_intent.pace_factor)

        # Δ_power: power deficit on straights
        if not is_corner:
            delta_power = config.k_aero_penalty * (1.0 - total_power_kw / max(config.power_ref_kw, 1.0))
        else:
            delta_power = 0.0

        # DRS bonus on straights (reduces time by ~0.3s per DRS zone)
        drs_active = section.drs_available and not car_state.side_by_side
        delta_drs = -0.005 if drs_active else 0.0

        # Event penalties
        delta_events = 0.0
        for evt in all_events:
            if evt.event_type == "tyre_overheat":
                delta_events += 0.02
            if evt.event_type == "ice_derating":
                delta_events += 0.01

        # Traffic constraint
        delta_traffic = 0.0
        if traffic_v_max_kph > 0 and v_base > 0:
            traffic_ratio = traffic_v_max_kph / v_base
            if traffic_ratio < 1.0:
                delta_traffic = (1.0 / max(traffic_ratio, 0.5)) - 1.0

        # Total penalty
        total_penalty = (
            config.baseline_delta
            + delta_aero
            + delta_grip
            + delta_brake
            + delta_fuel
            + delta_driver
            + delta_power
            + delta_drs
            + delta_events
            + delta_traffic
        )

        # Clamp total penalty to reasonable range (-0.05 to +0.30)
        total_penalty = clamp(total_penalty, -0.05, 0.30)

        dt_s = section.dt_ref_s * (1.0 + total_penalty)
        v_effective = (section.length_m / max(dt_s, 0.01)) * 3.6  # back-compute for reporting

    else:
        # ---------------------------------------------------------------
        # Fallback: old v_effective model (for sections without dt_ref)
        # ---------------------------------------------------------------
        curve_factor = CURVE_FACTOR.get(section.kind, 0.0)

        if is_corner:
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

            drag_curve_penalty = config.k_drag_curve * (aero_forces.drag_eff - config.drag_ref)
            v_curve = (v_curve * braking_efficiency) - drag_curve_penalty

            grip_axis = eff_grip_front if curve_factor >= 0.5 else eff_grip_rear
            v_grip_limited = v_curve * grip_axis
            v_effective = min(v_grip_limited, config.v_cap_kph)
        else:
            delta_power = config.k_power * (total_power_kw - config.power_ref_kw)
            delta_drag = config.k_drag * (aero_forces.drag_eff - config.drag_ref)
            v_straight = min(v_base + delta_power - delta_drag, config.v_cap_kph)
            v_effective = v_straight

        if traffic_v_max_kph > 0:
            v_effective = min(v_effective, traffic_v_max_kph)
        v_effective = max(v_effective, config.v_min_kph)

        for evt in all_events:
            if evt.event_type == "tyre_overheat":
                v_effective *= 0.98
            if evt.event_type == "ice_derating":
                v_effective *= 0.99

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

    # --- Overtake window (§6.10) ---
    # Base opportunity from section type (straights = easy, slow corners = possible, fast corners = hard)
    _OW_SECTION_BASE = {
        SectionKind.STRAIGHT: 0.6,
        SectionKind.MEDIUM_STRAIGHT: 0.4,
        SectionKind.VERY_SLOW_CORNER: 0.15,
        SectionKind.SLOW_CORNER: 0.10,
        SectionKind.MEDIUM_CORNER: 0.05,
        SectionKind.FAST_CORNER: 0.02,
        SectionKind.ULTRA_FAST_CORNER: 0.01,
    }
    ow_base = _OW_SECTION_BASE.get(section.kind, 0.1)

    # DRS bonus
    ow_drs = 0.15 if (section.drs_available and not car_state.side_by_side) else 0.0

    # Driver overtaking skill (0-100 → 0.0-0.15 bonus)
    ow_driver = driver_skills.overtaking_skill / 100.0 * 0.15

    # Tyre grip advantage (better grip = more overtake potential)
    grip_avg = (eff_grip_front + eff_grip_rear) / 2.0
    ow_grip = clamp((grip_avg - 0.85) * 0.5, -0.1, 0.1)

    # Braking zone bonus (late braking = overtake opportunity)
    ow_brake = 0.0
    if section.braking_energy_mj > 0.5:
        ow_brake = 0.1 * braking_efficiency  # better brakes = more chance

    # Aggression bonus
    ow_aggression = driver_intent.aggression_curve_bonus * 0.05

    car_state.overtake_window = clamp(
        ow_base + ow_drs + ow_driver + ow_grip + ow_brake + ow_aggression,
        0.0, 1.0,
    )

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
