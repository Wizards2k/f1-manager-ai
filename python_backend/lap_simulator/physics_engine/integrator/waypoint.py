"""
Waypoint Integrator - Integrazione fisica per un singolo waypoint.
"""

import math
from typing import Dict, List, Any, Optional

import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from core.constants import (
    G,
    RHO_SEA_LEVEL,
    MU_BASE,
    MAX_BRAKE_DECEL_G,
    MAX_LATERAL_G,
)

from aero.aero_assembly import AeroAssembly
from integrator.physics import apply_aero_calibration, gaussian_thermal_multiplier, get_optimal_temp, get_sigma
from integrator.engine_force import compute_engine_force
from integrator.drag import compute_total_drag
from integrator.grip import compute_grip_forces
from integrator.state import PhysicsState


def integrate_waypoint(
    state: PhysicsState,
    waypoint: Dict,
    next_waypoint: Dict,
    aero: AeroAssembly,
    setup: Dict,
    mass_kg: float,
    tyre_compound: str = "C3",
    driver_skill: float = 1.0,
    mu_base: Optional[Dict[str, float]] = None,
    max_brake_decel_g: Optional[float] = None,
    max_lateral_g: Optional[float] = None,
    aero_calibration: Optional[Dict[str, Any]] = None,
    section_guidance: Optional[Dict[str, Any]] = None,
    section_exit_guidance: Optional[Dict[str, Any]] = None,
    section_speed_scale: float = 1.0,
    section_entry_guidance: Optional[Dict[str, Any]] = None,
    waypoints: List[Dict] = None,
    waypoint_idx: int = 0,
    suspension_effects: Optional[Dict[str, float]] = None,
    ers_power_fraction: float = 1.0,
    reference_pull: Optional[Dict] = None,
    reference_pull_strength: float = 0.0,
    pu_lookup_interpolator: Optional[Any] = None,  # V5.0: PU Lookup interpolator (legacy, unused)
    pu_lookup_blend: float = 0.0,
    pu_config: Optional[Dict] = None,
    pu_ctx: Optional[Any] = None,
    v_max_corner_array: Optional[List[float]] = None,
    brake_needed: Optional[List[bool]] = None,
    air_density: float = 1.225,
    tires_state: Optional['TiresState'] = None,
    slip_per_wheel: Optional[Dict[str, float]] = None,
    circuit_id: str = "",
) -> PhysicsState:
    """
    Integra fisica per un singolo waypoint.
    """
    
    # Usa parametri locali o default
    if mu_base is None:
        mu_base = MU_BASE
    if max_brake_decel_g is None:
        max_brake_decel_g = MAX_BRAKE_DECEL_G
    if max_lateral_g is None:
        max_lateral_g = MAX_LATERAL_G
    
    # Distanza tra waypoint (tipicamente 5m)
    dist_step = next_waypoint['dist_m'] - waypoint['dist_m']
    if dist_step <= 0:
        return state
    
    # Estrai dati waypoint
    source_waypoint = next_waypoint or waypoint
    radius_m = source_waypoint.get('radius_m', waypoint.get('radius_m', 999999.0))
    slope_deg = source_waypoint.get('slope_deg', waypoint.get('slope_deg', 0.0))
    v_ref_kph = source_waypoint.get('v_ref_kph', waypoint.get('v_ref_kph', 200.0))
    throttle_pct = source_waypoint.get('throttle_pct', waypoint.get('throttle_pct', 0))
    brake_pct = source_waypoint.get('brake_pct', waypoint.get('brake_pct', 0))
    drs_active = source_waypoint.get('drs_active', waypoint.get('drs_active', False))
    section_kind = str((section_guidance or {}).get('kind') or '')
    if section_guidance:
        section_radius_m = section_guidance.get('radius_m')
        if section_radius_m is not None and section_kind in {'VerySlowCorner', 'SlowCorner'}:
            try:
                section_radius_m = float(section_radius_m)
                if radius_m < section_radius_m * 2.5:
                    blend_weight = 0.60 if section_kind == 'VerySlowCorner' else 0.45
                    radius_m = (max(radius_m, 1.0) ** (1.0 - blend_weight)) * (max(section_radius_m, 1.0) ** blend_weight)
            except (TypeError, ValueError):
                pass
    
    v_ref_ms_for_radius = v_ref_kph / 3.6
    r_min_from_vref = v_ref_ms_for_radius ** 2 / (max_lateral_g * G)
    if r_min_from_vref > radius_m * 1.5:
        radius_m = r_min_from_vref

    is_corner = radius_m < 1000.0
    
    # Calcola forze aerodinamiche
    susp_fx_dict = suspension_effects or {}
    rh_front_m = susp_fx_dict.get('ride_height_front_m', 0.040)
    rh_rear_m = susp_fx_dict.get('ride_height_rear_m', 0.050)
    rh_front_m = max(0.015, min(0.10, rh_front_m))
    rh_rear_m = max(0.015, min(0.10, rh_rear_m))
    
    aero_forces = aero.compute_forces(
        speed_ms=state.velocity_ms,
        air_density=air_density,
        ride_height_front=rh_front_m,
        ride_height_rear=rh_rear_m,
        drs_active=drs_active
    )
    aero_forces = apply_aero_calibration(aero_forces, aero_calibration)
    
    rh_aero_factor = susp_fx_dict.get('ride_height_aero_factor', 1.0)
    if rh_aero_factor < 1.0:
        floor_fraction = 0.68
        aero_forces.f_downforce *= (1.0 - floor_fraction * (1.0 - rh_aero_factor))
    
    # 1. POTENZA MOTORE
    f_engine = compute_engine_force(
        velocity_ms=state.velocity_ms,
        distance_m=state.distance_m,
        waypoint=waypoint,
        next_waypoint=next_waypoint,
        mass_kg=mass_kg,
        tyre_compound=tyre_compound,
        driver_skill=driver_skill,
        mu_base=mu_base,
        throttle_pct=throttle_pct,
        is_corner=is_corner,
        radius_m=radius_m,
        ers_power_fraction=ers_power_fraction,
        reference_pull=reference_pull,
        reference_pull_strength=reference_pull_strength,
        pu_lookup_blend=pu_lookup_blend,
        pu_ctx=pu_ctx,
        waypoints=waypoints,
        waypoint_idx=waypoint_idx,
    )
    state.f_engine = f_engine
    state.is_throttle = throttle_pct > 0

    # Compute dt for this step
    dt_step = max(0.001, (next_waypoint.get("dist_m", waypoint.get("dist_m", 0) + 5) - waypoint.get("dist_m", 0)) / max(state.velocity_ms, 1.0))

    # 2. FORZA DRAG
    state.f_drag = compute_total_drag(
        aero_forces=aero_forces,
        mass_kg=mass_kg,
        velocity_ms=state.velocity_ms,
        waypoint=waypoint,
        setup=setup,
    )

    # 3. FORZA GRAVITÀ
    slope_rad = math.radians(slope_deg)
    state.f_gravity = mass_kg * G * math.sin(slope_rad)
    
    # 4. GRIP TOTALE
    grip_result = compute_grip_forces(
        velocity_ms=state.velocity_ms,
        mass_kg=mass_kg,
        tyre_compound=tyre_compound,
        driver_skill=driver_skill,
        mu_base=mu_base,
        aero_forces=aero_forces,
        aero_calibration=aero_calibration,
        reference_pull=reference_pull,
        suspension_effects=suspension_effects,
        waypoint=waypoint,
        is_corner=is_corner,
        radius_m=radius_m,
        is_throttle=state.is_throttle,
        is_braking=state.is_braking,
    )
    mu_base_val = grip_result["mu_base_val"]
    f_grip_total_lateral = grip_result["f_grip_total_lateral"]
    f_grip_total_longitudinal = grip_result["f_grip_total_longitudinal"]
    f_grip_total = grip_result["f_grip_total"]
    v_max_corner_ms = grip_result["v_max_corner_ms"]
    longitudinal_traction_bonus = grip_result["longitudinal_traction_bonus"]
    
    # 6. FRENATA
    if v_max_corner_array is not None and 0 <= waypoint_idx < len(v_max_corner_array):
        v_target_ms = v_max_corner_array[waypoint_idx]
    else:
        v_target_ms = v_ref_kph / 3.6

    if section_speed_scale > 0.0:
        v_target_ms *= section_speed_scale

    # V6.3: Calculate per-wheel load distribution
    front_wing = float(setup.get("front_wing", 18.0))
    rear_wing = float(setup.get("rear_wing", 11.0))

    import importlib
    parent_pkg = 'lap_simulator.physics_engine'
    lt = importlib.import_module(f"{parent_pkg}.vehicle.load_transfer")
    wheels_load = lt.calculate_per_wheel_loads(
        velocity_ms=state.velocity_ms,
        radius_m=radius_m,
        mass_kg=mass_kg,
        f_downforce=aero_forces.f_downforce,
        v_target_ms=v_target_ms,
        dt_step=dt_step,
        front_wing=front_wing,
        rear_wing=rear_wing,
        circuit_id=circuit_id,
    )

    # V6.3: Calculate per-wheel slip and apply thermal multiplier + wear
    if state.tires_state is None:
        from lap_simulator.physics_engine.tyres.tyre_thermal import TiresState as TiresStateClass
        state.tires_state = TiresStateClass()

    target_g_lat = source_waypoint.get('target_g_lat', 1.0)
    f_grip_required_total_kn = (mass_kg * 9.81 / 1000.0) * target_g_lat
    total_load_kn = sum(wheels_load.values())

    wheels_slip = {}
    for wheel_name in ['FL', 'FR', 'RL', 'RR']:
        wheel_attr = wheel_name.lower()
        tire_state = getattr(state.tires_state, wheel_attr)

        thermal_mult = gaussian_thermal_multiplier(
            tire_state.surface_temp_c,
            tire_state.core_temp_c,
            tyre_compound
        )

        wear_factor = (100.0 - tire_state.wear_pct) / 100.0
        mu_tyre_wheel = mu_base.get(tyre_compound, 1.3) * thermal_mult * wear_factor
        f_grip_available = wheels_load[wheel_name] * mu_tyre_wheel
        load_fraction = wheels_load[wheel_name] / max(0.1, total_load_kn)
        f_grip_required_wheel = f_grip_required_total_kn * load_fraction
        slip = max(0.0, 1.0 - (f_grip_available / max(0.1, f_grip_required_wheel)))
        wheels_slip[wheel_name] = slip

    # V6.3: Update tire thermal state
    K_SURFACE_FRIC = 0.95
    K_HYSTERESIS_CORE = 0.35
    K_BRAKING_TRANSFER = 0.25
    brake_bias = setup.get('brake_bias', 0.55)

    for wheel_name in ['FL', 'FR', 'RL', 'RR']:
        wheel_attr = wheel_name.lower()
        tire_state = getattr(state.tires_state, wheel_attr)
        load_kn = wheels_load[wheel_name]
        slip = wheels_slip[wheel_name]

        friction_heat = K_SURFACE_FRIC * load_kn * slip * state.velocity_ms * dt_step

        brake_heat = 0.0
        if state.is_braking and brake_pct > 5:
            braking_energy_mj = 0.5 * mass_kg * state.velocity_ms ** 2 / 1e6
            if wheel_name in ['FL', 'FR']:
                brake_heat = K_BRAKING_TRANSFER * braking_energy_mj * brake_bias / 2.0 * dt_step
            else:
                brake_heat = K_BRAKING_TRANSFER * braking_energy_mj * (1.0 - brake_bias) / 2.0 * dt_step

        tire_state.surface_temp_c += (friction_heat + brake_heat)
        core_heat = K_HYSTERESIS_CORE * load_kn * state.velocity_ms * dt_step
        tire_state.core_temp_c += core_heat

        h_conv_base = 15.0
        brake_duct_opening = setup.get('brake_duct', 0.5)

        if wheel_name in ['FL', 'FR']:
            h_conv = h_conv_base * state.velocity_ms * (0.5 + brake_duct_opening)
        else:
            h_conv = h_conv_base * state.velocity_ms * 0.5

        q_cool = h_conv * (tire_state.surface_temp_c - 25.0) * dt_step / 1000.0
        tire_state.surface_temp_c -= q_cool

        temp_dev = abs(tire_state.surface_temp_c - get_optimal_temp(tyre_compound))
        sigma = get_sigma(tyre_compound)

        if temp_dev < sigma:
            severity = 1.0
        else:
            severity = 1.0 + ((temp_dev - sigma) / sigma) ** 1.5

        k_rolling = 0.0001
        k_friction = {'C5': 0.00095, 'C4': 0.0009, 'C3': 0.00085}.get(tyre_compound, 0.0009)
        rolling_component = k_rolling * load_kn
        friction_component = k_friction * severity * slip * load_kn
        wear_per_km = rolling_component + friction_component
        wear_delta = wear_per_km * (dist_step / 1000.0)
        tire_state.wear_pct += wear_delta

        tire_state.surface_temp_c = max(20.0, min(150.0, tire_state.surface_temp_c))
        tire_state.core_temp_c = max(20.0, min(130.0, tire_state.core_temp_c))
        tire_state.wear_pct = min(100.0, tire_state.wear_pct)

    # V6.0: Braking decision
    must_brake = False
    if brake_needed is not None and 0 <= waypoint_idx < len(brake_needed):
        if brake_needed[waypoint_idx] and state.velocity_ms > v_target_ms + 0.1:
            must_brake = True

    # V6.3: Brake fade thermal integration
    if must_brake and state.brake_state is not None and state.velocity_ms > v_target_ms:
        dt_braking = dist_step / max(state.velocity_ms, 1.0)
        decel_required = max(0.0, (state.velocity_ms - v_target_ms) / dt_braking)
        joules_dissipated = 0.5 * mass_kg * (state.velocity_ms ** 2 - v_target_ms ** 2)
        brake_bias = setup.get('brake_bias', 0.55) if setup else 0.55
        heat_front_kj = (joules_dissipated / 1000.0) * brake_bias
        heat_rear_kj = (joules_dissipated / 1000.0) * (1.0 - brake_bias)

        SUB_DT = 0.01
        N_SUBSTEPS = max(1, int(dt_braking / SUB_DT))
        heat_per_substep_front = heat_front_kj / max(N_SUBSTEPS, 1)
        heat_per_substep_rear = heat_rear_kj / max(N_SUBSTEPS, 1)

        H_CONV_BASE = 15.0
        C_TH_BRAKE = 2.5
        T_AMBIENT = 20.0
        brake_duct_opening = setup.get('brake_duct', 0.5) if setup else 0.5

        for _ in range(N_SUBSTEPS):
            temp_rise_front = heat_per_substep_front / C_TH_BRAKE
            temp_rise_rear = heat_per_substep_rear / C_TH_BRAKE

            h_conv_front = H_CONV_BASE * state.velocity_ms * (0.5 + brake_duct_opening)
            q_cool_front_kj = h_conv_front * (state.brake_state.temp_front_c - T_AMBIENT) * SUB_DT / 1000.0

            h_conv_rear = H_CONV_BASE * state.velocity_ms * 0.5
            q_cool_rear_kj = h_conv_rear * (state.brake_state.temp_rear_c - T_AMBIENT) * SUB_DT / 1000.0

            state.brake_state.temp_front_c = max(T_AMBIENT, state.brake_state.temp_front_c + temp_rise_front - q_cool_front_kj / C_TH_BRAKE)
            state.brake_state.temp_rear_c = max(T_AMBIENT, state.brake_state.temp_rear_c + temp_rise_rear - q_cool_rear_kj / C_TH_BRAKE)

    # FIX V4.7: Use longitudinal grip for braking decel limit
    max_brake_decel_phys = f_grip_total_longitudinal / mass_kg
    max_brake_decel = min(max_brake_decel_g * G, max_brake_decel_phys)

    # V6.3: Apply brake fade factor
    if must_brake and state.brake_state is not None:
        FADE_THRESHOLD_C = 850.0
        FADE_SENSITIVITY_C = 40.0
        worst_brake_temp = max(state.brake_state.temp_front_c, state.brake_state.temp_rear_c)
        fade_factor = max(0.0, min(1.0, (worst_brake_temp - FADE_THRESHOLD_C) / FADE_SENSITIVITY_C))
        max_brake_decel = max_brake_decel * (1.0 - fade_factor)
        state.brake_fade_factor = fade_factor
        state.brake_temp_front_c = state.brake_state.temp_front_c
        state.brake_temp_rear_c = state.brake_state.temp_rear_c
    else:
        state.brake_fade_factor = 0.0
        state.brake_temp_front_c = state.brake_state.temp_front_c if state.brake_state else 20.0
        state.brake_temp_rear_c = state.brake_state.temp_rear_c if state.brake_state else 20.0

    # V6.0: Applicazione frenata
    if must_brake:
        state.is_braking = True
        f_target_decel = mass_kg * max_brake_decel
        state.f_engine = -f_target_decel + state.f_drag + state.f_gravity
        state.f_engine = max(state.f_engine, -f_grip_total)
    else:
        state.is_braking = False
    
    # 7. ACCELERAZIONE NETTA
    f_net = state.f_engine - state.f_drag - state.f_gravity
    state.acceleration_ms2 = f_net / mass_kg
    
    # 8. LIMITI FISICI
    if is_corner:
        a_lat = state.velocity_ms ** 2 / radius_m
        a_lat_g = a_lat / G
        if a_lat_g > max_lateral_g:
            v_max_safe_ms = math.sqrt(max_lateral_g * G * radius_m)
            v_target_ms = min(v_target_ms, v_max_safe_ms)
    
    v_target_ms = min(v_target_ms, v_max_corner_ms)
    
    # 9. INTEGRA CINEMATICA
    v_squared_new = state.velocity_ms ** 2 + 2 * state.acceleration_ms2 * dist_step
    v_squared_new = max(0.0, v_squared_new)
    v_new_ms = math.sqrt(v_squared_new)
    v_new_ms = min(v_new_ms, v_max_corner_ms)
    v_new_ms = min(v_new_ms, v_target_ms)

    # FIX V5.4.3: Limit speed drop at section boundary transitions
    is_boundary_transition = False
    if dist_step < 1.0 and waypoints is not None and waypoint_idx > 0:
        prev_wp = waypoints[waypoint_idx - 1]
        prev_radius = prev_wp.get('radius_m', 9999.0)
        if radius_m < prev_radius * 0.2 and prev_radius > 100:
            is_boundary_transition = True
    if dist_step < 0.02:
        is_boundary_transition = True
    if is_boundary_transition:
        max_drop_ms = 30.0 / 3.6
        v_new_ms = max(v_new_ms, state.velocity_ms - max_drop_ms)
    
    v_new_ms = max(v_new_ms, 1.0)
    
    # 10. CALCOLO TEMPO STEP
    v_avg_ms = (state.velocity_ms + v_new_ms) / 2.0
    if v_avg_ms > 1.0:
        dt = dist_step / v_avg_ms
    else:
        dt = dist_step / 1.0
    
    # 11. AGGIORNA STATO
    new_state = PhysicsState(
        distance_m=state.distance_m + dist_step,
        velocity_ms=v_new_ms,
        acceleration_ms2=state.acceleration_ms2,
        time_s=state.time_s + dt,
        f_engine=state.f_engine,
        f_drag=state.f_drag,
        f_downforce=aero_forces.f_downforce,
        f_gravity=state.f_gravity,
        f_centripetal=mass_kg * v_new_ms ** 2 / radius_m if is_corner else 0.0,
        is_braking=state.is_braking,
        is_throttle=state.is_throttle,
        is_drs_active=drs_active,
        brake_target_v_ms=state.brake_target_v_ms,
        telemetry_points=state.telemetry_points
    )

    if state.tires_state is not None:
        new_state.tires_state = state.tires_state

    # Salva telemetria
    telemetry_entry = {
        'distance_m': new_state.distance_m,
        'velocity_ms': new_state.velocity_ms,
        'velocity_kph': new_state.velocity_ms * 3.6,
        'acceleration_ms2': new_state.acceleration_ms2,
        'time_s': new_state.time_s,
        'radius_m': radius_m,
        'is_braking': new_state.is_braking,
        'is_throttle': new_state.is_throttle,
        'drs_active': new_state.is_drs_active,
    }

    if new_state.tires_state is not None:
        telemetry_entry.update({
            'tires_fl_temp_surface_c': new_state.tires_state.fl.surface_temp_c,
            'tires_fl_temp_core_c': new_state.tires_state.fl.core_temp_c,
            'tires_fl_wear_pct': new_state.tires_state.fl.wear_pct,
            'tires_fr_temp_surface_c': new_state.tires_state.fr.surface_temp_c,
            'tires_fr_temp_core_c': new_state.tires_state.fr.core_temp_c,
            'tires_fr_wear_pct': new_state.tires_state.fr.wear_pct,
            'tires_rl_temp_surface_c': new_state.tires_state.rl.surface_temp_c,
            'tires_rl_temp_core_c': new_state.tires_state.rl.core_temp_c,
            'tires_rl_wear_pct': new_state.tires_state.rl.wear_pct,
            'tires_rr_temp_surface_c': new_state.tires_state.rr.surface_temp_c,
            'tires_rr_temp_core_c': new_state.tires_state.rr.core_temp_c,
            'tires_rr_wear_pct': new_state.tires_state.rr.wear_pct,
        })

    telemetry_entry.update({
        'brake_temp_front_c': new_state.brake_temp_front_c,
        'brake_temp_rear_c': new_state.brake_temp_rear_c,
        'brake_fade_factor': new_state.brake_fade_factor,
    })

    new_state.telemetry_points.append(telemetry_entry)
    
    return new_state
