"""
TyreModel – Step 5a of update_section().

Two-layer thermal model (surface + core), grip calculation,
wear, graining/blistering/flatspot detection.

Reference: docs/lap-physics-spec-v0.5.md §3.3 Passo 5
           docs/TyreModel.md
           docs/degradation-and-consumption.md §5.1
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from .data_types import (
    AeroForces,
    AeroSetup,
    CarState,
    CircuitConfig,
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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRONT_WHEELS = {WheelPosition.LF, WheelPosition.RF}
REAR_WHEELS = {WheelPosition.LR, WheelPosition.RR}


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
    aero_setup: AeroSetup | None = None,
) -> List[SectionEvent]:
    """Update thermal state, wear and grip for one tyre. Returns events."""
    events: List[SectionEvent] = []
    is_front = tyre.wheel_pos in FRONT_WHEELS

    # --- Heat generation ---
    # Base heat from section type
    heat_gen = section.heat_factor * driver.pace_factor

    # Axis-specific modifiers (spec §5.1 / degradation doc)
    if is_front:
        heat_gen *= (1.0 + aero.understeer_level)
        # Braking heat on front axle
        heat_gen += section.braking_energy_mj * 0.3
    else:
        heat_gen *= (1.0 + aero.oversteer_level)
        # Traction heat on rear
        torque_ramp_approx = driver.pace_factor * 0.6
        heat_gen *= (1.0 + torque_ramp_approx * 0.3)

    # --- Heat dissipation ---
    air_speed_factor = max(v_kph / 300.0, 0.1)
    convective_cool = (
        params.cooling_coeff
        * air_speed_factor
        * section.cool_factor
        * (1.0 - aero.airflow_penalty)
    )

    # --- Surface temperature ---
    delta_t_surface = (
        (heat_gen - convective_cool * (tyre.surface_temp_c - env.air_temp_c) * 0.01)
        / max(params.thermal_mass_surface, 0.1)
    ) * dt_s

    tyre.surface_temp_c += delta_t_surface

    # Conduction to track
    track_conduction = 0.005 * (tyre.surface_temp_c - env.track_temp_c)
    tyre.surface_temp_c -= track_conduction * dt_s

    # --- Core temperature (higher inertia) ---
    core_exchange = params.conduction_coeff * (tyre.surface_temp_c - tyre.core_temp_c)
    delta_t_core = core_exchange / max(params.thermal_mass_core, 0.1) * dt_s
    tyre.core_temp_c += delta_t_core

    # Clamp temperatures
    tyre.surface_temp_c = clamp(tyre.surface_temp_c, env.air_temp_c - 5.0, 200.0)
    tyre.core_temp_c = clamp(tyre.core_temp_c, env.air_temp_c - 5.0, 180.0)

    # --- Wear ---
    section_km = section.length_m / 1000.0
    wear_rate = params.wear_rate_base_pct_per_km * driver.pace_factor
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
    thermal_factor = clamp(thermal_factor, 0.7, 1.1)

    wear_factor = max(0.5, 1.0 - tyre.wear_pct / 100.0)

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

    tyre.effective_grip = params.base_grip * thermal_factor * wear_factor * setup_bonus

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

    # Graining (understeer + cold surface on front)
    if is_front and aero.understeer_level > 0.3 and tyre.surface_temp_c < params.temp_opt_surface:
        tyre.graining_level += 0.02
        tyre.graining_level = clamp(tyre.graining_level, 0.0, 1.0)

    # Flatspot from kerb + braking
    if aero.kerb_impact > 0 and is_front:
        tyre.flatspot_severity += aero.kerb_severity * 0.01
        tyre.flatspot_severity = clamp(tyre.flatspot_severity, 0.0, 1.0)

    # Blistering (core overheated)
    window_max_core = params.temp_window_core_c[2]
    if tyre.core_temp_c > window_max_core + 5:
        tyre.blistering_level += 0.015
        tyre.blistering_level = clamp(tyre.blistering_level, 0.0, 1.0)

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

    for wp, tyre in car_state.tyres.items():
        params = config.tyre_params.get(tyre.compound)
        if params is None:
            params = config.tyre_params.get(TyreCompound.C3, TyreCompoundParams(compound=TyreCompound.C3))
        evts = _update_single_tyre(tyre, params, section, env, aero, driver, dt_s, v_kph, aero_setup)
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
