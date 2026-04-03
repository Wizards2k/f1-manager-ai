"""PowerUnit step – compute ICE/ERS output and state evolution for a section."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
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
    SectionKind,
    SectionEvent,
    clamp,
)
from typing import Dict
from typing import List, Tuple


PACE_FACTOR_MIN = 0.80
PACE_FACTOR_MAX = 1.12


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ICE_BASE_POWER_KW = 950.0          # F1 2025 ICE ~950kW (calibrated for 2025 realistic)
ICE_MAX_POWER_KW = 1100.0          # cap after boosts and ERS
ERS_MAX_ENERGY_MJ = 4.0            # max battery capacity
ERS_DEPLOY_LIMIT_MJ_PER_LAP = 4.0
ERS_RECOVERY_LIMIT_MJ_PER_LAP = 2.0
FUEL_BASE_BURN_KG_PER_S = 0.035    # ~2.1 kg/min at race pace
PACE_FACTOR_MIN = 0.80
PACE_FACTOR_MAX = 1.12

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

PRIORITY_BASE = {
    SectionKind.STRAIGHT: 1.0,
    SectionKind.MEDIUM_STRAIGHT: 0.85,
    SectionKind.ULTRA_FAST_CORNER: 0.75,
    SectionKind.FAST_CORNER: 0.65,
    SectionKind.MEDIUM_CORNER: 0.5,
    SectionKind.SLOW_CORNER: 0.35,
    SectionKind.VERY_SLOW_CORNER: 0.25,
}

PRIMARY_BUCKET_KINDS = {SectionKind.STRAIGHT, SectionKind.MEDIUM_STRAIGHT}
SECONDARY_BUCKET_KINDS = {SectionKind.ULTRA_FAST_CORNER, SectionKind.FAST_CORNER}


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
        config.pu_maps.get(EngineMapName.RACE, EngineMapParams(name=EngineMapName.RACE)),
    )

    map_budget = _map_budget(config, pu_state.active_map)
    _initialize_bucket_budget(pu_state, map_params, map_budget, config, config.sections)

    # --- ICE power ---
    ice_wear_factor = 1.0 - pu_state.ice_wear_pct * 0.002
    ice_power_pct = _compute_ice_power_pct(map_params, driver_intent)
    ice_power_raw = ICE_BASE_POWER_KW * ice_power_pct * ice_wear_factor

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
    priority_score = _section_priority(section, driver_intent)
    if not driver_intent.ers_deploy_request:
        priority_score *= 0.25
    priority_score = clamp(priority_score, 0.0, 1.0)
    pu_state.last_priority_score = priority_score

    ers_output_raw = map_params.ers_output_kw * priority_score
    bucket_key = _resolve_bucket(section)
    pu_state.last_bucket_key = bucket_key

    # Pre-compute MGU-H availability before battery constraints
    mguh_power_kw = _estimate_mguh_power_kw(map_params, section, aero_forces, config)
    dt_safe = max(dt_estimate_s, 0.01)
    mguh_energy_available_mj = (mguh_power_kw * dt_safe) / 1000.0
    mguh_lap_total = _estimate_mguh_lap_energy(map_params, config)
    mguh_direct_bias, mguh_es_bias = _resolve_mguh_bias(map_params, pu_state, map_budget)
    mguh_es_budget_total = map_budget.get("mguh_es_mj", mguh_lap_total * mguh_es_bias)
    mguh_es_remaining_mj = max(mguh_es_budget_total - pu_state.lap_mguh_harvest_mj, 0.0)

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

    bucket_section_cap_mj = _compute_bucket_section_cap(pu_state, bucket_key)
    bucket_es_deploy_pct = _resolve_bucket_es_deploy_pct(map_budget, bucket_key)

    ers_energy_requested_raw_mj = (ers_output_raw * dt_safe) / 1000.0
    ers_energy_requested_mj = bucket_section_cap_mj
    if ers_energy_requested_raw_mj > 1e-5 and bucket_section_cap_mj <= 1e-5:
        pu_state.runtime_warnings.append(f"bucket_exhausted:{bucket_key}")
    mguh_direct_section_mj = _allocate_mguh_direct(
        pu_state,
        mguh_energy_available_mj * mguh_direct_bias,
    )
    mguh_remaining_mj = max(mguh_energy_available_mj - mguh_direct_section_mj, 0.0)
    if pu_state.ers_energy_mj >= ERS_MAX_ENERGY_MJ - 1e-6:
        mguh_direct_section_mj += mguh_remaining_mj
        mguh_es_used_mj = 0.0
    else:
        mguh_es_used_mj = min(mguh_remaining_mj, mguh_es_remaining_mj)
    if bucket_es_deploy_pct > 1e-6:
        battery_energy_needed_mj = ers_energy_requested_mj * bucket_es_deploy_pct
    else:
        battery_energy_needed_mj = max(ers_energy_requested_mj - mguh_direct_section_mj, 0.0)

    target_soc = map_budget.get("target_soc_end_lap")
    if target_soc is not None:
        min_soc_mj = clamp(target_soc, 0.0, 1.0) * ERS_MAX_ENERGY_MJ
        available_for_deploy = max(pu_state.ers_energy_mj - min_soc_mj, 0.0)
        battery_energy_needed_mj = min(battery_energy_needed_mj, available_for_deploy + 1e-4)

    if deploy_budget is not None:
        deploy_remaining = max(deploy_budget - pu_state.lap_deploy_mj, 0.0)
        if deploy_remaining < battery_energy_needed_mj:
            battery_energy_needed_mj = deploy_remaining
            if deploy_remaining <= 0.0:
                pu_state.runtime_warnings.append("deploy_limit_hit")
                pu_state.runtime_warnings.append("bucket_exhausted")

    battery_energy_needed_mj = _apply_bucket_allocation(
        pu_state,
        bucket_key,
        battery_energy_needed_mj,
        driver_intent,
    )

    pu_state.last_push_mode = bool(driver_intent.ers_push_mode)
    pu_state.last_defense_mode = bool(driver_intent.ers_defense_mode)
    pu_state.last_recharge_mode = bool(driver_intent.ers_recharge_mode)

    battery_energy_allocated_mj = min(battery_energy_needed_mj, pu_state.ers_energy_mj)
    if battery_energy_allocated_mj < battery_energy_needed_mj - 1e-5:
        # Battery depleted before satisfying demand
        if pu_state.ers_energy_mj <= 1e-5:
            pu_state.runtime_warnings.append("battery_empty")

    battery_output_kw = (battery_energy_allocated_mj * 1000.0) / dt_safe
    mguh_direct_kw = (mguh_direct_section_mj * 1000.0) / dt_safe
    ers_output_pre_derate_kw = battery_output_kw + mguh_direct_kw

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

    # ERS: thermal clipping model (doc-spec: ERS-ThermalClipping.md)
    # q_gen = k_joule * P_ers^2  (Joule heating, quadratic in power)
    # q_cool = h_v * v_car * (T_ers - T_amb)  (convective cooling, speed-dependent)
    # C_th = 18.0 kJ/K  (thermal inertia)
    ERS_T_LIMIT = 102.0          # clipping onset (°C)
    ERS_T_MAX = 122.0            # full shutdown (°C)
    ERS_K_JOULE = 0.000045       # Joule coefficient
    ERS_H_V = 0.0025             # convective cooling coefficient
    ERS_C_TH = 18.0              # thermal mass (kJ/K)
    v_section_kph = clamp(section.v_base_kph or 200.0, 30.0, 370.0)
    t_amb = clamp(env.air_temp_c, 10.0, 50.0)
    q_gen_ers = ERS_K_JOULE * (ers_output_kw ** 2)
    q_cool_ers = ERS_H_V * v_section_kph * max(pu_state.ers_temp_c - t_amb, 0.0)
    delta_t_ers = ((q_gen_ers - q_cool_ers) / max(ERS_C_TH, 0.1)) * dt_estimate_s
    pu_state.ers_temp_c += delta_t_ers
    pu_state.ers_temp_c = clamp(pu_state.ers_temp_c, t_amb, 150.0)
    # Compute thermal eta and update PUState
    if pu_state.ers_temp_c < ERS_T_LIMIT:
        pu_state.ers_thermal_eta = 1.0
    elif pu_state.ers_temp_c >= ERS_T_MAX:
        pu_state.ers_thermal_eta = 0.0
        if "ers_thermal_shutdown" not in pu_state.runtime_warnings:
            pu_state.runtime_warnings.append("ers_thermal_shutdown")
    else:
        pu_state.ers_thermal_eta = clamp(
            1.0 - (pu_state.ers_temp_c - ERS_T_LIMIT) / (ERS_T_MAX - ERS_T_LIMIT),
            0.0, 1.0,
        )
        if pu_state.ers_thermal_eta < 0.95 and "ers_thermal_clipping" not in pu_state.runtime_warnings:
            pu_state.runtime_warnings.append("ers_thermal_clipping")

    # --- Battery SoC ---
    ers_consumed_mj = battery_energy_used_mj
    # Recovery from braking (simplified: proportional to braking energy)
    regen_profile = config.regen_profile or {}
    brake_profile = config.brake_profile or {}
    regen_eff = clamp(regen_profile.get("base_factor", 0.3), 0.05, 0.8)
    regen_bias = brake_profile.get("regen_migration_bias", 0.0)
    hydraulic_ratio = brake_profile.get("hydraulic_vs_regen_ratio")
    regen_base = brake_profile.get("regen_brake_base")
    regen_fraction = regen_eff
    if hydraulic_ratio is not None and hydraulic_ratio >= 0:
        regen_fraction = clamp(1.0 / max(1.0 + hydraulic_ratio, 1e-3), 0.05, 0.95)
    elif regen_base is not None:
        regen_fraction = clamp(regen_base, 0.05, 0.95)

    bias_scale = clamp(1.0 + regen_bias, 0.3, 1.7)
    regen_fraction = clamp(regen_fraction * bias_scale, 0.05, 0.95)

    regen_target_mj = section.braking_energy_mj * regen_fraction
    regen_cap = regen_profile.get("potential_mj_per_lap")
    regen_section_cap = clamp(regen_profile.get("regen_limit_per_section", 0.5), 0.1, 2.0)
    ers_recovery_mj = clamp(regen_target_mj, 0.0, regen_section_cap)
    if regen_cap:
        per_section_remaining = max(regen_cap - pu_state.lap_harvest_mj, 0.0)
        if per_section_remaining < ers_recovery_mj:
            ers_recovery_mj = per_section_remaining
    if harvest_budget is not None:
        harvest_remaining = max(harvest_budget - pu_state.lap_harvest_mj, 0.0)
        if harvest_remaining < ers_recovery_mj:
            ers_recovery_mj = harvest_remaining
            if harvest_remaining <= 0.0:
                pu_state.runtime_warnings.append("harvest_limit_hit")
    soc_after_deploy = clamp(pu_state.ers_energy_mj - battery_energy_used_mj, 0.0, ERS_MAX_ENERGY_MJ)

    regen_clamped_soc = False
    soc_headroom = max(ERS_MAX_ENERGY_MJ - soc_after_deploy, 0.0)
    if soc_headroom < ers_recovery_mj:
        regen_clamped_soc = True
        ers_recovery_mj = soc_headroom

    if regen_clamped_soc:
        pu_state.runtime_warnings.append("brake_migration_disabled_soc")

    hydraulic_mj = max(section.braking_energy_mj - ers_recovery_mj, 0.0)
    soc_after_regen = clamp(soc_after_deploy + ers_recovery_mj, 0.0, ERS_MAX_ENERGY_MJ)

    pu_state.ers_energy_mj = clamp(soc_after_regen + mguh_es_used_mj, 0.0, ERS_MAX_ENERGY_MJ)
    pu_state.lap_deploy_mj += battery_energy_used_mj
    pu_state.lap_harvest_mj += ers_recovery_mj
    pu_state.lap_mguh_direct_mj += mguh_direct_energy_mj
    pu_state.lap_mguh_harvest_mj += mguh_es_used_mj
    regen_vs_hydraulic = hydraulic_mj / max(ers_recovery_mj, 0.001)
    trace_entry = {
        "section_id": section.section_id,
        "deploy_mj": round(battery_energy_used_mj, 4),
        "harvest_mj": round(ers_recovery_mj, 4),
        "hydraulic_mj": round(hydraulic_mj, 4),
        "regen_vs_hydraulic": round(regen_vs_hydraulic, 3),
        "mguh_direct_mj": round(mguh_direct_energy_mj, 4),
        "mguh_es_mj": round(mguh_es_used_mj, 4),
    }
    pu_state.energy_trace.append(trace_entry)

    # --- Fuel burn ---
    fuel_burn_rate = FUEL_BASE_BURN_KG_PER_S * ice_power_pct * fuel_mix_mult
    fuel_burned = fuel_burn_rate * dt_estimate_s
    pu_state.fuel_kg = max(0.0, pu_state.fuel_kg - fuel_burned)
    pu_state.fuel_burn_rate_kg_per_s = fuel_burn_rate

    # --- Wear ---
    # Over-rev factor: high torque_ramp maps stress the ICE/ERS more
    overrev_threshold = max(map_params.power_pct_base, map_params.torque_ramp)
    overrev_ice = rel.ice_overrev_factor if ice_power_pct > overrev_threshold else 1.0
    overrev_ers = rel.ers_overrev_factor if ice_power_pct > overrev_threshold else 1.0
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
    # Decrement section count after processing
    _decrement_section_count(pu_state, bucket_key)
    
    # Telemetry logging is handled by SessionBridge only.
    
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


def _compute_ice_power_pct(map_params: EngineMapParams, intent: DriverIntent) -> float:
    pct_min = clamp(map_params.power_pct_min, 0.2, 1.5)
    pct_max = clamp(map_params.power_pct_max, pct_min, 1.5)
    pct_base = clamp(map_params.power_pct_base, pct_min, pct_max)

    pace = clamp(getattr(intent, "pace_factor", 1.0), PACE_FACTOR_MIN, PACE_FACTOR_MAX)
    pace_norm = (pace - PACE_FACTOR_MIN) / max(PACE_FACTOR_MAX - PACE_FACTOR_MIN, 1e-6)

    push_level = getattr(intent, "push_level", 10)
    push_norm = clamp((push_level - 1) / 9.0, 0.0, 1.0)

    intent_weight = 0.55 * push_norm + 0.45 * pace_norm
    pct = pct_min + (pct_max - pct_min) * intent_weight

    # Bias toward base to avoid extreme oscillations
    pct = pct * 0.65 + pct_base * 0.35

    if intent.fuel_save_mode or intent.tyre_save_mode:
        pct = min(pct, pct_base)
    if intent.ers_push_mode and not intent.fuel_save_mode:
        pct += (pct_max - pct) * 0.12

    return clamp(pct, pct_min, pct_max)


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
    _map_params: EngineMapParams,
    _pu_state: PUState,
    map_budget: Dict[str, float],
) -> Tuple[float, float]:
    """Return (direct_bias, es_bias) for distributing MGU-H energy."""
    raw_direct = map_budget.get("mguh_direct_ratio")
    if raw_direct is None:
        raw_direct = 0.45

    base_direct = clamp(float(raw_direct), 0.0, 1.0)
    base_es = clamp(1.0 - base_direct, 0.0, 1.0)

    total = max(base_direct + base_es, 1e-6)
    return base_direct / total, base_es / total


def _estimate_mguh_lap_energy(
    map_params: EngineMapParams,
    config: CircuitConfig,
) -> float:
    """Coarse estimate of total MGU-H energy produced over a lap (MJ)."""
    base_kw = max(map_params.mguh_power_kw or 0.0, 0.0)
    if base_kw <= 0.0:
        return 0.0
    lap_time = config.reference_lap_time_s or 90.0
    avg_section_factor = 0.72  # approximate mean of SECTION_MGUH_FACTORS
    return clamp((base_kw * avg_section_factor * lap_time) / 1000.0, 0.0, 12.0)


def _initialize_bucket_budget(
    pu_state: PUState,
    map_params: EngineMapParams,
    map_budget: Dict[str, Any],
    config: CircuitConfig,
    sections: List[SectionContext],
) -> None:
    if pu_state.bucket_budget_initialized:
        return

    deploy_total = map_budget.get("deploy_mj_per_lap")
    if deploy_total is None:
        deploy_total = ERS_DEPLOY_LIMIT_MJ_PER_LAP
    deploy_total = clamp(deploy_total, 0.0, ERS_DEPLOY_LIMIT_MJ_PER_LAP)

    primary_pct = map_budget.get("bucket_primary_pct", map_params.bucket_primary_pct)
    secondary_pct = map_budget.get("bucket_secondary_pct", map_params.bucket_secondary_pct)
    exit_pct = map_budget.get("bucket_exit_pct", map_params.bucket_exit_pct)
    pct_sum = max(primary_pct + secondary_pct + exit_pct, 1e-6)

    defense_reserve = map_budget.get("defense_reserve_mj", map_params.defense_reserve_mj)
    if pu_state.active_map == EngineMapName.QUALIFY:
        defense_reserve = 0.0
    defense_reserve = clamp(defense_reserve, 0.0, deploy_total * 0.6)
    available = max(deploy_total - defense_reserve, 0.0)

    primary_share = primary_pct / pct_sum
    secondary_share = secondary_pct / pct_sum
    exit_share = exit_pct / pct_sum

    pu_state.bucket_primary_total_mj = available * primary_share
    pu_state.bucket_secondary_total_mj = available * secondary_share
    pu_state.bucket_exit_total_mj = available * exit_share
    pu_state.defense_reserve_available_mj = defense_reserve
    pu_state.deploy_budget_total_mj = deploy_total

    # Conta settori per tipo nel giro
    primary_count = sum(1 for s in sections if _resolve_bucket(s) == "primary")
    secondary_count = sum(1 for s in sections if _resolve_bucket(s) == "secondary")
    exit_count = sum(1 for s in sections if _resolve_bucket(s) == "exit")
    
    pu_state.primary_sections_count = primary_count
    pu_state.secondary_sections_count = secondary_count
    pu_state.exit_sections_count = exit_count
    pu_state.primary_sections_remaining = primary_count
    pu_state.secondary_sections_remaining = secondary_count
    pu_state.exit_sections_remaining = exit_count

    pu_state.bucket_budget_initialized = True


def _section_priority(section: SectionContext, intent: DriverIntent) -> float:
    if intent.ers_recharge_mode:
        return 0.05

    base = PRIORITY_BASE.get(section.kind, 0.4)
    length_factor = clamp(section.length_m / 350.0, 0.5, 1.3)
    score = base * length_factor

    if section.drs_available:
        score += 0.12

    if intent.ers_push_mode:
        score = score * 1.25 + 0.1
    elif intent.ers_defense_mode and section.kind not in PRIMARY_BUCKET_KINDS:
        score *= 1.1

    return clamp(score, 0.05, 1.2)


def _resolve_bucket(section: SectionContext) -> str:
    if section.kind in PRIMARY_BUCKET_KINDS:
        return "primary"
    if section.kind in SECONDARY_BUCKET_KINDS:
        return "secondary"
    return "exit"


def _resolve_bucket_es_deploy_pct(map_budget: Dict[str, float], bucket_key: str) -> float:
    if bucket_key == "primary":
        key = "bucket_primary_es_deploy_pct"
    elif bucket_key == "secondary":
        key = "bucket_secondary_es_deploy_pct"
    else:
        key = "bucket_exit_es_deploy_pct"
    return clamp(float(map_budget.get(key, 0.0) or 0.0), 0.0, 1.0)


def _apply_bucket_allocation(
    pu_state: PUState,
    bucket_key: str,
    requested_mj: float,
    intent: DriverIntent,
) -> float:
    remaining_sections = _get_remaining_sections(pu_state, bucket_key)
    total_sections = _get_total_sections(pu_state, bucket_key)
    total_attr, used_attr = _bucket_attrs(bucket_key)
    total = getattr(pu_state, total_attr, 0.0)
    used = getattr(pu_state, used_attr, 0.0)
    remaining_bucket = max(total - used, 0.0)
    if remaining_sections > 0:
        cap_per_section = remaining_bucket / remaining_sections
    elif total_sections <= 0:
        cap_per_section = remaining_bucket
    else:
        cap_per_section = 0.0

    pu_state.last_bucket_cap_mj = cap_per_section

    if requested_mj <= 1e-6:
        pu_state.last_bucket_allocated_mj = 0.0
        pu_state.last_defense_used_mj = 0.0
        return 0.0
    if intent.ers_recharge_mode:
        pu_state.last_bucket_allocated_mj = 0.0
        pu_state.last_defense_used_mj = 0.0
        return 0.0

    allocated = 0.0
    remaining_request = requested_mj
    defense_used = 0.0

    # Defense buffer
    if intent.ers_defense_mode and pu_state.defense_reserve_available_mj > 1e-6:
        defense_take = min(remaining_request, pu_state.defense_reserve_available_mj)
        pu_state.defense_reserve_available_mj -= defense_take
        allocated += defense_take
        remaining_request -= defense_take
        defense_used = defense_take

    # Usa bucket con cap per settore
    bucket_available = remaining_request
    consumed = _consume_bucket(pu_state, bucket_key, bucket_available)
    allocated += consumed
    remaining_request -= consumed

    if remaining_request > 1e-5:
        pu_state.runtime_warnings.append(f"bucket_cap_hit:{bucket_key}")
        pu_state.runtime_warnings.append(f"bucket_exhausted:{bucket_key}")

    pu_state.last_bucket_allocated_mj = allocated
    pu_state.last_defense_used_mj = defense_used

    return allocated


def _consume_bucket(pu_state: PUState, bucket_key: str, amount: float) -> float:
    if amount <= 1e-6:
        return 0.0
    total_attr, used_attr = _bucket_attrs(bucket_key)
    total = getattr(pu_state, total_attr, 0.0)
    used = getattr(pu_state, used_attr, 0.0)
    remaining = max(total - used, 0.0)
    take = min(amount, remaining)
    if take > 0.0:
        setattr(pu_state, used_attr, used + take)
    return take


def _get_remaining_sections(pu_state: PUState, bucket_key: str) -> int:
    """Get remaining sections count for bucket type."""
    if bucket_key == "primary":
        return pu_state.primary_sections_remaining
    elif bucket_key == "secondary":
        return pu_state.secondary_sections_remaining
    else:
        return pu_state.exit_sections_remaining


def _compute_bucket_section_cap(pu_state: PUState, bucket_key: str) -> float:
    remaining_sections = _get_remaining_sections(pu_state, bucket_key)
    total_sections = _get_total_sections(pu_state, bucket_key)
    total_attr, used_attr = _bucket_attrs(bucket_key)
    total = getattr(pu_state, total_attr, 0.0)
    used = getattr(pu_state, used_attr, 0.0)
    remaining_bucket = max(total - used, 0.0)
    if remaining_sections > 0:
        return remaining_bucket / remaining_sections
    if total_sections <= 0:
        return remaining_bucket
    return 0.0


def _get_total_sections(pu_state: PUState, bucket_key: str) -> int:
    """Get total section count for bucket type."""
    if bucket_key == "primary":
        return pu_state.primary_sections_count
    if bucket_key == "secondary":
        return pu_state.secondary_sections_count
    return pu_state.exit_sections_count


def _decrement_section_count(pu_state: PUState, bucket_key: str) -> None:
    """Decrement remaining sections count after processing a section."""
    if bucket_key == "primary":
        pu_state.primary_sections_remaining = max(pu_state.primary_sections_remaining - 1, 0)
    elif bucket_key == "secondary":
        pu_state.secondary_sections_remaining = max(pu_state.secondary_sections_remaining - 1, 0)
    else:
        pu_state.exit_sections_remaining = max(pu_state.exit_sections_remaining - 1, 0)


def _bucket_attrs(bucket_key: str) -> Tuple[str, str]:
    if bucket_key == "primary":
        return "bucket_primary_total_mj", "bucket_primary_used_mj"
    if bucket_key == "secondary":
        return "bucket_secondary_total_mj", "bucket_secondary_used_mj"
    return "bucket_exit_total_mj", "bucket_exit_used_mj"


def _allocate_mguh_direct(
    pu_state: PUState,
    requested_mj: float,
) -> float:
    return max(requested_mj, 0.0)


def _consume_mguh_bucket(pu_state: PUState, bucket_key: str, amount: float) -> float:
    return 0.0


def _mguh_bucket_attrs(bucket_key: str) -> Tuple[str, str]:
    return "", ""
