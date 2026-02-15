"""
PowerUnit – Step 4 of update_section().

Computes ICE + ERS power output, fuel burn, thermal state,
derating and wear for the current section.

Reference: docs/lap-physics-spec-v0.5.md §3.3 Passo 4
           docs/degradation-and-consumption.md §5.4
"""
from __future__ import annotations

from .data_types import (
    AeroForces,
    CarState,
    CircuitConfig,
    DriverIntent,
    EngineMapName,
    EngineMapParams,
    EnvContext,
    PUReliabilityParams,
    PUState,
    SectionContext,
    SectionEvent,
    clamp,
)
from typing import Dict
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ICE_BASE_POWER_KW = 550.0          # baseline ICE power at 100% map
ERS_MAX_KW = 120.0                 # FIA limit (MGU-K output)
ERS_MAX_ENERGY_MJ = 4.0            # max battery capacity
ERS_DEPLOY_LIMIT_MJ_PER_LAP = 4.0
ERS_RECOVERY_LIMIT_MJ_PER_LAP = 2.0
FUEL_BASE_BURN_KG_PER_S = 0.035    # ~2.1 kg/min at race pace

# Section kind impact on MGU-H generation (lookup via section.kind.value)
SECTION_MGUH_FACTORS = {
    "Straight": 1.00,
    "MediumStraight": 0.9,
    "UltraFastCorner": 0.85,
    "FastCorner": 0.75,
    "MediumCorner": 0.6,
    "SlowCorner": 0.45,
    "VerySlowCorner": 0.35,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_output(
    pu_state: PUState,
    driver_intent: DriverIntent,
    aero_forces: AeroForces,
    section: SectionContext,
    env: EnvContext,
    config: CircuitConfig,
    dt_estimate_s: float = 1.0,
) -> Tuple[PUState, List[SectionEvent]]:
    """
    Compute PU output for the current section and update PU state in-place.

    Returns the updated PUState and a list of events.
    """
    events: List[SectionEvent] = []
    rel = config.pu_reliability

    # --- Resolve active map params ---
    map_params: EngineMapParams = config.pu_maps.get(
        pu_state.active_map,
        config.pu_maps.get(EngineMapName.STANDARD, EngineMapParams(name=EngineMapName.STANDARD)),
    )

    map_budget = _map_budget(config, pu_state.active_map)

    # --- ICE power ---
    ice_wear_factor = 1.0 - pu_state.ice_wear_pct * 0.002
    ice_power_raw = ICE_BASE_POWER_KW * map_params.torque_ramp * ice_wear_factor

    # Derating from temperature
    ice_derating_factor = 1.0
    if pu_state.ice_temp_c > rel.ice_temp_warning_c:
        excess = pu_state.ice_temp_c - rel.ice_temp_warning_c
        range_c = max(rel.ice_temp_critical_c - rel.ice_temp_warning_c, 1.0)
        ice_derating_factor = clamp(1.0 - (excess / range_c) * 0.4, 0.6, 1.0)
        pu_state.ice_derating = True
        events.append(SectionEvent(
            event_type="ice_derating",
            severity=1.0 - ice_derating_factor,
            message="ICE overheating – power reduced",
        ))
    else:
        pu_state.ice_derating = False

    # Fuel save mode
    fuel_mix_mult = 1.0
    if driver_intent.fuel_save_mode:
        fuel_mix_mult = 0.85

    ice_power_kw = ice_power_raw * ice_derating_factor * fuel_mix_mult
    pu_state.ice_power_kw = ice_power_kw

    # --- ERS output ---
    ers_output_raw = map_params.ers_output_kw
    if driver_intent.ers_deploy_request:
        ers_output_raw = min(ers_output_raw * 1.2, ERS_MAX_KW)

    # Pre-compute MGU-H availability before battery constraints
    mguh_power_kw = _estimate_mguh_power_kw(map_params, section, aero_forces, config)
    dt_safe = max(dt_estimate_s, 0.01)
    mguh_energy_available_mj = (mguh_power_kw * dt_safe) / 1000.0
    direct_bias, es_bias = _resolve_mguh_bias(map_params, pu_state, map_budget)
    mguh_direct_capacity_mj = mguh_energy_available_mj * direct_bias
    mguh_es_capacity_mj = mguh_energy_available_mj * es_bias

    # ERS derating from temperature
    ers_derating_factor = 1.0
    if pu_state.ers_temp_c > rel.ers_temp_warning_c:
        excess = pu_state.ers_temp_c - rel.ers_temp_warning_c
        range_c = max(rel.ers_temp_critical_c - rel.ers_temp_warning_c, 1.0)
        ers_derating_factor = clamp(1.0 - (excess / range_c) * 0.5, 0.5, 1.0)
        pu_state.ers_derating = True
        events.append(SectionEvent(
            event_type="ers_derating",
            severity=1.0 - ers_derating_factor,
            message="ERS overheating – output reduced",
        ))
    else:
        pu_state.ers_derating = False

    # Battery constraint + per-lap deploy limit (after MGU-H split)
    deploy_budget = map_budget.get("deploy_mj_per_lap")
    harvest_budget = map_budget.get("harvest_mj_per_lap")
    deploy_remaining = None

    ers_energy_requested_mj = (ers_output_raw * dt_safe) / 1000.0
    mguh_direct_used_mj = min(mguh_direct_capacity_mj, ers_energy_requested_mj)
    battery_energy_needed_mj = max(ers_energy_requested_mj - mguh_direct_used_mj, 0.0)

    if deploy_budget is not None:
        deploy_remaining = max(deploy_budget - pu_state.lap_deploy_mj, 0.0)
        if deploy_remaining < battery_energy_needed_mj:
            battery_energy_needed_mj = deploy_remaining
            if deploy_remaining <= 0.0:
                pu_state.runtime_warnings.append("deploy_limit_hit")

    battery_energy_allocated_mj = min(battery_energy_needed_mj, pu_state.ers_energy_mj)
    if battery_energy_allocated_mj < battery_energy_needed_mj - 1e-5:
        # Battery depleted before satisfying demand
        if pu_state.ers_energy_mj <= 1e-5:
            pu_state.runtime_warnings.append("battery_empty")
    if mguh_direct_capacity_mj > 1e-5 and mguh_direct_used_mj >= mguh_direct_capacity_mj - 1e-5 and ers_energy_requested_mj > mguh_direct_capacity_mj:
        pu_state.runtime_warnings.append("mguh_clip")

    battery_output_kw = (battery_energy_allocated_mj * 1000.0) / dt_safe
    mguh_direct_kw = (mguh_direct_used_mj * 1000.0) / dt_safe
    ers_output_pre_derate_kw = battery_output_kw + mguh_direct_kw
    if ers_output_pre_derate_kw > ERS_MAX_KW:
        scale = ERS_MAX_KW / ers_output_pre_derate_kw
        battery_output_kw *= scale
        mguh_direct_kw *= scale
        ers_output_pre_derate_kw = ERS_MAX_KW

    ers_output_kw = ers_output_pre_derate_kw * ers_derating_factor
    if ers_output_pre_derate_kw > 1e-5:
        derate_scale = ers_output_kw / ers_output_pre_derate_kw
        battery_output_kw *= derate_scale
        mguh_direct_kw *= derate_scale
    pu_state.ers_output_kw = ers_output_kw

    battery_energy_used_mj = (battery_output_kw * dt_safe) / 1000.0
    mguh_direct_energy_mj = (mguh_direct_kw * dt_safe) / 1000.0

    # --- Total power ---
    total_power_kw = ice_power_kw + ers_output_kw

    # --- Thermal update ---
    # ICE: heat in from map, cooling from aero
    heat_in_ice = map_params.heat_load_kw * dt_estimate_s / 1000.0  # simplified kJ
    cooling_ice = aero_forces.cooling_capacity * map_params.cooling_share * dt_estimate_s
    ice_thermal_mass = 8.0  # simplified thermal mass
    delta_t_ice = (heat_in_ice - cooling_ice) / max(ice_thermal_mass, 0.1)
    pu_state.ice_temp_c += delta_t_ice
    pu_state.ice_temp_c = clamp(pu_state.ice_temp_c, env.air_temp_c, 200.0)

    # ERS: heat from output, cooling shared
    heat_in_ers = ers_output_kw * dt_estimate_s / 2000.0
    cooling_ers = aero_forces.cooling_capacity * (1.0 - map_params.cooling_share) * dt_estimate_s * 0.5
    ers_thermal_mass = 4.0
    delta_t_ers = (heat_in_ers - cooling_ers) / max(ers_thermal_mass, 0.1)
    pu_state.ers_temp_c += delta_t_ers
    pu_state.ers_temp_c = clamp(pu_state.ers_temp_c, env.air_temp_c, 150.0)

    # --- Battery SoC ---
    ers_consumed_mj = battery_energy_used_mj
    # Recovery from braking (simplified: proportional to braking energy)
    regen_profile = config.regen_profile or {}
    brake_profile = config.brake_profile or {}
    regen_eff = regen_profile.get("base_factor", 0.3)
    regen_bias = brake_profile.get("regen_migration_bias", 0.0)
    regen_cap = regen_profile.get("potential_mj_per_lap")
    regen_section_cap = clamp(regen_profile.get("regen_limit_per_section", 0.5), 0.1, 2.0)
    base_recovery = section.braking_energy_mj * clamp(regen_eff, 0.1, 0.6)
    # Apply bias: positive bias means shift more to front (more regen), negative less
    bias_scale = clamp(1.0 + regen_bias, 0.3, 1.7)
    ers_recovery_mj = clamp(base_recovery * bias_scale, 0.0, regen_section_cap)
    if regen_cap:
        per_section_remaining = max(regen_cap - pu_state.lap_harvest_mj, 0.0)
        if per_section_remaining < ers_recovery_mj:
            ers_recovery_mj = per_section_remaining
    hydraulic_mj = max(section.braking_energy_mj - ers_recovery_mj, 0.0)
    if harvest_budget is not None:
        harvest_remaining = max(harvest_budget - pu_state.lap_harvest_mj, 0.0)
        if harvest_remaining < ers_recovery_mj:
            ers_recovery_mj = harvest_remaining
            if harvest_remaining <= 0.0:
                pu_state.runtime_warnings.append("harvest_limit_hit")
    soc_after_deploy = clamp(pu_state.ers_energy_mj - battery_energy_used_mj, 0.0, ERS_MAX_ENERGY_MJ)
    soc_after_regen = clamp(soc_after_deploy + ers_recovery_mj, 0.0, ERS_MAX_ENERGY_MJ)

    mguh_remaining_mj = max(mguh_energy_available_mj - mguh_direct_used_mj, 0.0)
    mguh_harvest_potential_mj = min(mguh_es_capacity_mj, mguh_remaining_mj)
    mguh_es_headroom = max(ERS_MAX_ENERGY_MJ - soc_after_regen, 0.0)
    mguh_es_used_mj = min(mguh_harvest_potential_mj, mguh_es_headroom)

    pu_state.ers_energy_mj = clamp(soc_after_regen + mguh_es_used_mj, 0.0, ERS_MAX_ENERGY_MJ)
    pu_state.lap_deploy_mj += battery_energy_used_mj
    pu_state.lap_harvest_mj += ers_recovery_mj
    pu_state.lap_mguh_direct_mj += mguh_direct_energy_mj
    pu_state.lap_mguh_harvest_mj += mguh_es_used_mj
    regen_vs_hydraulic = hydraulic_mj / max(ers_recovery_mj, 0.001)
    pu_state.energy_trace.append(
        {
            "section_id": section.section_id,
            "deploy_mj": round(battery_energy_used_mj, 4),
            "harvest_mj": round(ers_recovery_mj, 4),
            "hydraulic_mj": round(hydraulic_mj, 4),
            "regen_vs_hydraulic": round(regen_vs_hydraulic, 3),
            "mguh_direct_mj": round(mguh_direct_energy_mj, 4),
            "mguh_es_mj": round(mguh_es_used_mj, 4),
        }
    )

    # --- Fuel burn ---
    fuel_burn_rate = FUEL_BASE_BURN_KG_PER_S * map_params.torque_ramp * fuel_mix_mult
    fuel_burned = fuel_burn_rate * dt_estimate_s
    pu_state.fuel_kg = max(0.0, pu_state.fuel_kg - fuel_burned)
    pu_state.fuel_burn_rate_kg_per_s = fuel_burn_rate

    # --- Wear ---
    # Over-rev factor: high torque_ramp maps stress the ICE/ERS more
    overrev_ice = rel.ice_overrev_factor if map_params.torque_ramp > 0.85 else 1.0
    overrev_ers = rel.ers_overrev_factor if map_params.torque_ramp > 0.85 else 1.0
    # Shock factor: kerb impacts and bumps cause extra mechanical stress
    shock_level = aero_forces.kerb_severity + aero_forces.bump_penalty
    shock_ice = 1.0 + (rel.ice_shock_factor - 1.0) * shock_level
    shock_ers = 1.0 + (rel.ers_shock_factor - 1.0) * shock_level

    pu_state.ice_wear_pct += rel.ice_wear_coeff * ice_power_kw * dt_estimate_s * overrev_ice * shock_ice / 100.0
    pu_state.ers_wear_pct += rel.ers_wear_coeff * ers_output_kw * dt_estimate_s * overrev_ers * shock_ers / 100.0

    # --- Cooling margin (for AeroForces update) ---
    cooling_demand = map_params.heat_load_kw / 1000.0
    cooling_available = aero_forces.cooling_capacity
    # Store margin for downstream use
    # (positive = headroom, negative = overheating risk)

    # --- Critical events ---
    if pu_state.ice_temp_c > rel.ice_temp_critical_c:
        events.append(SectionEvent(
            event_type="ice_critical",
            severity=0.9,
            message="ICE CRITICAL – risk of failure!",
        ))
    if pu_state.ers_temp_c > rel.ers_temp_critical_c:
        events.append(SectionEvent(
            event_type="ers_critical",
            severity=0.9,
            message="ERS CRITICAL – risk of failure!",
        ))
    if pu_state.fuel_kg <= 0.5:
        events.append(SectionEvent(
            event_type="fuel_critical",
            severity=0.8,
            message="Fuel critically low!",
        ))

    return pu_state, events


def _map_budget(config: CircuitConfig, map_name: EngineMapName) -> Dict[str, float]:
    """Return per-map ERS budget (deploy/harvest) if configured."""
    if not config or not config.ers_budget:
        return {}
    maps = config.ers_budget.get("maps") or {}
    map_key = map_name.value if isinstance(map_name, EngineMapName) else map_name
    return maps.get(map_key, {})


def _estimate_mguh_power_kw(
    map_params: EngineMapParams,
    section: SectionContext,
    aero: AeroForces,
    config: CircuitConfig,
) -> float:
    """Estimate instantaneous MGU-H power produced in the current section."""
    base_kw = max(map_params.mguh_power_kw or 0.0, 0.0)
    section_factor = SECTION_MGUH_FACTORS.get(section.kind.value, 0.6)
    drs_bonus = 0.12 if getattr(section, "drs_available", False) else 0.0
    v_ref = section.v_max_kph or section.v_base_kph or 250.0
    v_factor = clamp(v_ref / 360.0, 0.45, 1.1)
    airflow_penalty = getattr(aero, "airflow_penalty", 0.0) or 0.0
    dirty_penalty = clamp(1.0 - airflow_penalty * 0.6, 0.75, 1.0)
    cool_factor = getattr(section, "cool_factor", 1.0) or 1.0
    thermal_penalty = clamp(0.9 + min(cool_factor, 1.4) * 0.08, 0.75, 1.05)
    mguh_kw = base_kw * section_factor * (1.0 + drs_bonus) * v_factor * dirty_penalty * thermal_penalty
    return clamp(mguh_kw, 0.0, 120.0)


def _resolve_mguh_bias(
    map_params: EngineMapParams,
    pu_state: PUState,
    map_budget: Dict[str, float],
) -> Tuple[float, float]:
    """Return (direct_bias, es_bias) for distributing MGU-H energy."""
    base_direct = clamp(map_params.mguh_direct_ratio or 0.3, 0.05, 0.9)
    base_es = 1.0 - base_direct

    target_soc = map_budget.get("target_soc_end_lap")
    current_soc = clamp(pu_state.ers_energy_mj / ERS_MAX_ENERGY_MJ, 0.0, 1.0)
    if target_soc is not None:
        soc_gap = target_soc - current_soc
        if soc_gap > 0.05:
            shift = clamp(soc_gap * 0.6, 0.0, 0.4)
            base_direct = clamp(base_direct - shift, 0.05, 0.9)
        elif soc_gap < -0.05:
            shift = clamp(abs(soc_gap) * 0.4, 0.0, 0.3)
            base_direct = clamp(base_direct + shift, 0.05, 0.9)
        base_es = 1.0 - base_direct

    total = max(base_direct + base_es, 1e-6)
    return base_direct / total, base_es / total
