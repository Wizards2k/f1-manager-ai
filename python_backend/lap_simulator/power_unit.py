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
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ICE_BASE_POWER_KW = 550.0          # baseline ICE power at 100% map
ERS_MAX_KW = 120.0                  # FIA limit
ERS_MAX_ENERGY_MJ = 4.0            # max battery capacity
ERS_DEPLOY_LIMIT_MJ_PER_LAP = 4.0
ERS_RECOVERY_LIMIT_MJ_PER_LAP = 2.0
FUEL_BASE_BURN_KG_PER_S = 0.035    # ~2.1 kg/min at race pace


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

    # Battery constraint
    ers_energy_needed_mj = (ers_output_raw * dt_estimate_s) / 1000.0
    if pu_state.ers_energy_mj < ers_energy_needed_mj:
        ers_output_raw = (pu_state.ers_energy_mj * 1000.0) / max(dt_estimate_s, 0.01)

    ers_output_kw = ers_output_raw * ers_derating_factor
    pu_state.ers_output_kw = ers_output_kw

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
    ers_consumed_mj = (ers_output_kw * dt_estimate_s) / 1000.0
    # Recovery from braking (simplified: proportional to braking energy)
    ers_recovery_mj = section.braking_energy_mj * 0.3  # ~30% recovery efficiency
    pu_state.ers_energy_mj = clamp(
        pu_state.ers_energy_mj - ers_consumed_mj + ers_recovery_mj,
        0.0,
        ERS_MAX_ENERGY_MJ,
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
