"""
Lap HD Simulator - Simula giro completo su circuito HD.
"""

import math
from typing import Dict, List, Any, Optional

import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from core.constants import (
    G,
    calculate_air_density,
    MASS_TOTAL_QUALY_KG,
    MU_BASE,
    MAX_BRAKE_DECEL_G,
    MAX_LATERAL_G,
)

from aero.aero_assembly import AeroAssembly
from calibration.aero_calibration import get_aero_calibration
from calibration.circuit_calibration import get_circuit_calibration
from calibration.pu_lookup import load_pu_lookup, PULookupInterpolator
from calibration.telemetry_bridge import TelemetryBridge
from suspension.setup_effects import compute_suspension_effects
from driver.braking_point import compute_braking_zones_v6, analyze_circuit_profile, get_safety_factor_v6
from integrator.io import load_hd_waypoints, load_reference_sections, find_section_id_by_distance, load_soft_compound
from integrator.physics import get_circuit_elevation_m, compute_v_max_corners
from integrator.pu_stateful_v2 import (
    PU_Context,
    init_pu_context,
    BATTERY_CAPACITY_MJ,
)
from integrator.state import PhysicsState
from integrator.waypoint import integrate_waypoint


def integrate_lap_hd(
    circuit_id: str,
    aero_setup: Optional[Dict] = None,
    mass_kg: float = MASS_TOTAL_QUALY_KG,
    tyre_compound: str = "C3",
    driver_skill: float = 1.0,
    push_level: int = 10,
    verbose: bool = False,
    mu_override: Optional[Dict[str, float]] = None,
    max_brake_decel_g_override: Optional[float] = None,
    max_lateral_g_override: Optional[float] = None,
    aero_calibration: Optional[Dict[str, Any]] = None,
    suspension_setup: Optional[Dict] = None,
    sector_boundaries: Optional[List[float]] = None,
    ers_power_fraction: float = 1.0,
    reference_pull_strength: float = 0.0,
    pu_lookup_blend: float = 0.0,
    pu_config: Optional[Dict] = None,
    initial_tire_temps: Optional[Dict[str, float]] = None,
    cumulative_tire_wear: Optional[Dict[str, float]] = None,
    # V6.4: Fuel carryover for multi-lap stints
    initial_fuel_kg: Optional[float] = None,
    # V6.4: DRS activation logic
    drs_enabled: bool = True,
    drs_gap_ahead_s: Optional[float] = None,
    lap_number: int = 1,
    is_safety_car: bool = False,
) -> Dict[str, Any]:
    """
    Simula giro completo su circuito HD.
    """
    
    if verbose:
        print(f"🏁 Caricamento {circuit_id}...")
    
    waypoints = load_hd_waypoints(circuit_id)
    reference_sections = load_reference_sections(circuit_id)
    
    reference_pull = TelemetryBridge.load_reference_pull(circuit_id)
    if reference_pull and verbose:
        print(f"  📡 Reference Pull caricato: {reference_pull.get('driver', '?')} "
              f"{reference_pull.get('lap_time_s', 0):.3f}s")
    
    pu_lookup_interpolator = None
    if pu_lookup_blend > 0.0:
        pu_lookup_data = load_pu_lookup(circuit_id)
        if pu_lookup_data:
            pu_lookup_interpolator = PULookupInterpolator(pu_lookup_data)
            if verbose:
                speed_min, speed_max = pu_lookup_interpolator.speed_range
                print(f"  🔋 PU Lookup caricato: {pu_lookup_interpolator.num_entries} punti, "
                      f"speed {speed_min:.0f}-{speed_max:.0f} kph, blend={pu_lookup_blend:.2f}")
        elif verbose:
            print(f"  ⚠️ PU Lookup non trovato per {circuit_id}, blend disabilitato")
    
    pu_ctx = None
    if pu_config is not None:
        engine_map = pu_config.get("engine_map", "QUALIFY")
        pu_ctx = init_pu_context(circuit_id, engine_map)
    else:
        pu_ctx = init_pu_context(circuit_id, "QUALIFY")
    if verbose and pu_ctx is not None:
        print(f"  ⚡ V5.5 PU Stateful: map={pu_ctx.engine_map}, "
              f"deploy={pu_ctx.deploy_mj_per_lap:.2f} MJ, "
              f"harvest={pu_ctx.harvest_mj_per_lap:.2f} MJ, "
              f"mguh_power={pu_ctx.mguh_power_kw:.1f} kW, "
              f"ers_output={pu_ctx.ers_output_kw:.1f} kW")
    
    if not waypoints:
        raise ValueError(f"Nessun waypoint trovato per {circuit_id}")
    
    if verbose:
        print(f"  Waypoints: {len(waypoints)}")
        print(f"  Lunghezza: {waypoints[-1]['dist_m']:.1f}m")
    
    aero = AeroAssembly()
    
    if aero_setup is None:
        aero_setup = {
            "front_wing": 20.0,
            "rear_wing": 22.0,
            "b_wing": 10.0,
        }
    
    aero.set_component_angles(aero_setup)
    
    initial_velocity_kph = float(waypoints[0].get('v_ref_kph', 180.0))
    initial_velocity_ms = max(1.0, initial_velocity_kph / 3.6)
    state = PhysicsState(
        distance_m=0.0,
        velocity_ms=initial_velocity_ms,
        acceleration_ms2=0.0,
        time_s=0.0,
    )

    if initial_tire_temps:
        state.tires_state.fl.surface_temp_c = initial_tire_temps.get("FL", 85.0)
        state.tires_state.fr.surface_temp_c = initial_tire_temps.get("FR", 85.0)
        state.tires_state.rl.surface_temp_c = initial_tire_temps.get("RL", 85.0)
        state.tires_state.rr.surface_temp_c = initial_tire_temps.get("RR", 85.0)

    if cumulative_tire_wear:
        state.tires_state.fl.wear_pct = cumulative_tire_wear.get("FL", 0.0)
        state.tires_state.fr.wear_pct = cumulative_tire_wear.get("FR", 0.0)
        state.tires_state.rl.wear_pct = cumulative_tire_wear.get("RL", 0.0)
        state.tires_state.rr.wear_pct = cumulative_tire_wear.get("RR", 0.0)

    if sector_boundaries:
        sector_times = [0.0] * len(sector_boundaries)
        boundaries = sector_boundaries
    else:
        sector_times = [0.0, 0.0, 0.0]
        boundaries = [
            waypoints[-1]['dist_m'] / 3,
            waypoints[-1]['dist_m'] * 2 / 3,
            waypoints[-1]['dist_m'],
        ]
    sector_idx = 0
    
    v_max_ms = 0.0
    v_min_ms = 999.0
    
    circuit_calibration = get_circuit_calibration(circuit_id)
    if circuit_calibration:
        if mu_override is None and circuit_calibration.get("mu_override") is not None:
            mu_override = circuit_calibration["mu_override"]
        if max_brake_decel_g_override is None and circuit_calibration.get("max_brake_decel_g") is not None:
            max_brake_decel_g_override = circuit_calibration["max_brake_decel_g"]
        if max_lateral_g_override is None and circuit_calibration.get("max_lateral_g") is not None:
            max_lateral_g_override = circuit_calibration["max_lateral_g"]
        section_speed_scales = circuit_calibration.get("section_speed_scales") or {}
    else:
        section_speed_scales = {}

    if aero_calibration is None:
        aero_calibration = get_aero_calibration(circuit_id)

    calibration_compound = load_soft_compound(circuit_id)
    if aero_calibration is not None:
        aero_calibration["calibration_compound"] = calibration_compound
    else:
        aero_calibration = {"calibration_compound": calibration_compound}

    if aero_calibration is not None:
        k_wing_coupling = aero_calibration.get("k_wing_coupling")
        if k_wing_coupling is not None:
            try:
                k_wing_coupling = float(k_wing_coupling)
                if k_wing_coupling > 0:
                    aero.set_k_wing_coupling(k_wing_coupling)
            except (TypeError, ValueError):
                pass

    mu_base_local = MU_BASE.copy()
    if mu_override:
        mu_base_local.update(mu_override)
    
    max_brake_decel_g_local = max_brake_decel_g_override if max_brake_decel_g_override else MAX_BRAKE_DECEL_G
    max_lateral_g_local = max_lateral_g_override if max_lateral_g_override else MAX_LATERAL_G
    
    if verbose:
        print("🚀 Integrazione...")
        if circuit_calibration:
            print(f"  Circuit calibration loaded: {circuit_id}")
        if aero_calibration:
            cda = aero_calibration.get("CdA")
            cla = aero_calibration.get("ClA")
            aero_message = "  Aero calibration loaded:"
            if isinstance(cda, (int, float)):
                aero_message += f" CdA={cda:.4f}"
            if isinstance(cla, (int, float)):
                aero_message += f" ClA={cla:.4f}"
            mu_mech = aero_calibration.get("mu_mechanical")
            k_wc = aero_calibration.get("k_wing_coupling")
            if mu_mech is not None:
                aero_message += f" mu_mech={float(mu_mech):.3f}"
            if k_wc is not None:
                aero_message += f" k_wing_coupling={float(k_wc):.4f}"
            print(aero_message)
        if mu_override:
            print(f"  MU override: {mu_override}")
        if max_brake_decel_g_override:
            print(f"  Brake override: {max_brake_decel_g_override}g")
        if max_lateral_g_override:
            print(f"  Lateral override: {max_lateral_g_override}g")
    
    lap_elevation_m = get_circuit_elevation_m(circuit_id)
    lap_air_density = calculate_air_density(lap_elevation_m)
    if verbose:
        print(f"  🌄 Altitude: {lap_elevation_m:.0f}m → air_density: {lap_air_density:.4f} kg/m³ "
              f"({100*(lap_air_density/1.225 - 1):+.2f}% vs sea level)")

    susp_effects = compute_suspension_effects(suspension_setup)

    # V6.0: PRE-COMPUTE v_max_corner AND BRAKING ZONES
    v_max_corner_array = []
    try:
        v_max_corner_array = compute_v_max_corners(
            waypoints=waypoints,
            aero=aero,
            mu_cal=aero_calibration.get("mu_mechanical", 1.55) if aero_calibration else 1.55,
            mass_kg=mass_kg,
            circuit_id=circuit_id,
            suspension_effects=susp_effects,
            n_iter=3,
        )
        if verbose:
            print(f"  ✓ V6.0 v_max_corner computed: {len(v_max_corner_array)} waypoints")
            print(f"    Min: {min(v_max_corner_array):.1f} m/s, Max: {max(v_max_corner_array):.1f} m/s, "
                  f"Avg: {sum(v_max_corner_array)/len(v_max_corner_array):.1f} m/s")
    except Exception as e:
        if verbose:
            print(f"  ⚠️ V6.0 v_max_corner failed: {e}, falling back to None")
        v_max_corner_array = None

    if v_max_corner_array is not None:
        try:
            circuit_type = analyze_circuit_profile(waypoints)
            safety_factor = get_safety_factor_v6(circuit_type, circuit_id)
            push_pace_factor = 0.95 + (max(1, min(10, push_level)) / 10.0) * 0.05
            v_max_corner_array = [v * safety_factor * push_pace_factor for v in v_max_corner_array]
            if verbose:
                print(f"  ✓ V6.0 safety factor applied: {circuit_type} → {safety_factor:.2f} (Push={push_level})")
                print(f"    After safety: Min: {min(v_max_corner_array):.1f} m/s, "
                      f"Max: {max(v_max_corner_array):.1f} m/s")
        except Exception as e:
            if verbose:
                print(f"  ⚠️ V6.0 safety factor failed: {e}")

    brake_needed = []
    try:
        brake_needed = compute_braking_zones_v6(
            waypoints=waypoints,
            v_max_corner=v_max_corner_array if v_max_corner_array else [200/3.6] * len(waypoints),
            max_brake_decel_g=max_brake_decel_g_local,
        )
        brake_count = sum(brake_needed)
        if verbose:
            print(f"  ✓ V6.0 braking zones computed: {brake_count}/{len(brake_needed)} waypoints need braking "
                  f"({100*brake_count/len(brake_needed):.1f}%)")
    except Exception as e:
        if verbose:
            print(f"  ⚠️ V6.0 braking zones failed: {e}, falling back to None")
        brake_needed = None

    # V6.1 Degradation Modulo A: Peso dinamico carburante
    # V6.4: If initial_fuel_kg is provided, compute mass from dry weight + fuel
    # This enables multi-lap carryover where fuel decreases each lap.
    # If not provided, use the legacy mass_kg parameter directly.
    DRY_MASS_KG = 798.0  # F1 2025 minimum dry weight (no driver, no fuel)
    if initial_fuel_kg is not None:
        current_mass_kg = DRY_MASS_KG + initial_fuel_kg
        fuel_at_lap_start_kg = initial_fuel_kg
    else:
        current_mass_kg = mass_kg
        fuel_at_lap_start_kg = None
    total_fuel_consumed_kg = 0.0
    
    flow_map_multiplier = 1.0
    if pu_ctx:
        map_name = getattr(pu_ctx, 'engine_map', 'QUALIFY').upper()
        if map_name == "RACE":
            flow_map_multiplier = 0.90
        elif map_name == "PRACTICE":
            flow_map_multiplier = 0.85
        elif map_name == "ECONOMY":
            flow_map_multiplier = 0.75
        elif map_name == "SAFETY_CAR":
            flow_map_multiplier = 0.40

    max_flow_kg_ps = 0.0277

    for i in range(len(waypoints) - 1):
        wp = waypoints[i]
        wp_next = waypoints[i + 1]
        current_section_id = find_section_id_by_distance(reference_sections, wp.get('dist_m', 0.0))
        next_section_id = find_section_id_by_distance(reference_sections, wp_next.get('dist_m', 0.0))
        section_guidance = reference_sections.get(current_section_id)
        section_exit_guidance = section_guidance if current_section_id and current_section_id != next_section_id else None
        section_entry_guidance = reference_sections.get(next_section_id) if current_section_id and current_section_id != next_section_id else None
        section_speed_scale = 1.0
        scale_key = next_section_id or current_section_id
        if isinstance(section_speed_scales, dict) and scale_key:
            try:
                section_speed_scale = float(section_speed_scales.get(scale_key, 1.0) or 1.0)
            except (TypeError, ValueError):
                section_speed_scale = 1.0
        
        prev_time_s = state.time_s
        state = integrate_waypoint(
            state=state,
            waypoint=wp,
            next_waypoint=wp_next,
            aero=aero,
            setup=aero_setup,
            mass_kg=current_mass_kg,
            tyre_compound=tyre_compound,
            driver_skill=driver_skill,
            mu_base=mu_base_local,
            max_brake_decel_g=max_brake_decel_g_local,
            max_lateral_g=max_lateral_g_local,
            aero_calibration=aero_calibration,
            section_guidance=section_guidance,
            section_exit_guidance=section_exit_guidance,
            section_speed_scale=section_speed_scale,
            section_entry_guidance=section_entry_guidance,
            waypoints=waypoints,
            waypoint_idx=i,
            suspension_effects=susp_effects,
            ers_power_fraction=ers_power_fraction,
            reference_pull=reference_pull,
            reference_pull_strength=reference_pull_strength,
            pu_lookup_interpolator=pu_lookup_interpolator,
            pu_lookup_blend=pu_lookup_blend,
            pu_config=pu_config,
            pu_ctx=pu_ctx,
            v_max_corner_array=v_max_corner_array,
            brake_needed=brake_needed,
            air_density=lap_air_density,
            circuit_id=circuit_id,
            # V6.4: DRS activation
            drs_enabled=drs_enabled,
            drs_gap_ahead_s=drs_gap_ahead_s,
            lap_number=lap_number,
            is_safety_car=is_safety_car,
        )
        
        dt_s_step = state.time_s - prev_time_s
        if dt_s_step > 0:
            throttle_pace_eff = 0.85 + (max(1, min(10, push_level)) / 10.0) * 0.15
            raw_throttle = float(wp.get('throttle_pct', 0)) / 100.0
            
            if getattr(state, 'is_throttle', False):
                throttle_intensity = throttle_pace_eff * raw_throttle
                throttle_intensity = max(0.1, throttle_intensity)
            else:
                throttle_intensity = 0.05
                
            delta_fuel = max_flow_kg_ps * throttle_intensity * flow_map_multiplier * dt_s_step
            current_mass_kg -= delta_fuel
            total_fuel_consumed_kg += delta_fuel
        
        v_max_ms = max(v_max_ms, state.velocity_ms)
        v_min_ms = min(v_min_ms, state.velocity_ms)
        
        if sector_idx < len(boundaries) and state.distance_m >= boundaries[sector_idx]:
            sector_times[sector_idx] = state.time_s
            sector_idx += 1
    
    if sector_idx == len(boundaries):
        if len(boundaries) >= 3 and not sector_boundaries:
            sector_times[2] = state.time_s - sum(sector_times[:2])
    
    lap_time_s = state.time_s
    v_max_kph = v_max_ms * 3.6
    v_min_kph = v_min_ms * 3.6
    v_avg_kph = (waypoints[-1]['dist_m'] / lap_time_s) * 3.6
    
    if verbose:
        print(f"✅ Giro completato!")
        print(f"  Tempo: {lap_time_s:.3f}s")
        print(f"  Settori ({len(sector_times)}): {[f'{t:.3f}' for t in sector_times]}")
        print(f"  V_max: {v_max_kph:.1f} kph")
        print(f"  V_min: {v_min_kph:.1f} kph")
        print(f"  V_avg: {v_avg_kph:.1f} kph")
        if pu_ctx is not None:
            print(f"  ⚡ PU V5.4: deploy={pu_ctx.lap_deploy_mj:.3f} MJ, "
                  f"harvest={pu_ctx.lap_harvest_mj:.3f} MJ, "
                  f"mguh_direct={pu_ctx.lap_mguh_direct_mj:.3f} MJ, "
                  f"soc_end={pu_ctx.soc_mj:.3f} MJ ({pu_ctx.soc_mj/BATTERY_CAPACITY_MJ*100:.1f}%), "
                  f"ers_temp={pu_ctx.ers_temp_c:.1f}°C")
    
    result = {
        "lap_time_s": lap_time_s,
        "sector_times": sector_times,
        "v_max_kph": v_max_kph,
        "v_min_kph": v_min_kph,
        "v_avg_kph": v_avg_kph,
        "telemetry": state.telemetry_points,
        "waypoints_count": len(waypoints),
        "circuit_id": circuit_id,
        "aero_setup": aero_setup,
        "aero_calibration": aero_calibration,
        "fuel_consumed_kg": total_fuel_consumed_kg,
        # V6.4: Fuel carryover — fuel remaining at end of lap
        "fuel_remaining_kg": (fuel_at_lap_start_kg - total_fuel_consumed_kg) if fuel_at_lap_start_kg is not None else None,
    }
    
    if pu_ctx is not None:
        zones_summary = []
        for z in pu_ctx.deployment_zones:
            zones_summary.append({
                "name": z.name,
                "type": z.zone_type,
                "start_m": round(z.start_m, 1),
                "end_m": round(z.end_m, 1),
                "allocated_mj": round(z.allocated_mj, 3),
                "remaining_mj": round(z.remaining_mj, 3),
                "target_power_kw": round(z.target_power_kw, 1),
            })

        result["pu_v54"] = {
            "engine_map": pu_ctx.engine_map,
            "lap_deploy_mj": round(pu_ctx.lap_deploy_mj, 4),
            "lap_harvest_mj": round(pu_ctx.lap_harvest_mj, 4),
            "lap_mguh_direct_mj": round(pu_ctx.lap_mguh_direct_mj, 4),
            "soc_end_mj": round(pu_ctx.soc_mj, 4),
            "soc_end_pct": round(pu_ctx.soc_mj / BATTERY_CAPACITY_MJ * 100, 1),
            "ers_temp_end_c": round(pu_ctx.ers_temp_c, 1),
            "deployment_zones": zones_summary,
            "energy_trace": pu_ctx.energy_trace,
        }

    if state.tires_state:
        result["final_tire_temps"] = {
            "FL": state.tires_state.fl.surface_temp_c,
            "FR": state.tires_state.fr.surface_temp_c,
            "RL": state.tires_state.rl.surface_temp_c,
            "RR": state.tires_state.rr.surface_temp_c,
        }
        result["cumulative_tire_wear"] = {
            "FL": state.tires_state.fl.wear_pct,
            "FR": state.tires_state.fr.wear_pct,
            "RL": state.tires_state.rl.wear_pct,
            "RR": state.tires_state.rr.wear_pct,
        }

    return result
