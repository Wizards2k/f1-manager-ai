"""
DriverModel – Step 2 of update_section().

Computes driver intent (pace_factor, aggression, target_line,
brake bias adjustments, ERS/fuel save requests) based on
driver skills, mental state, section type and car state.

Reference: docs/lap-physics-spec-v0.5.md §3.3 Passo 2
"""
from __future__ import annotations

from .data_types import (
    CarState,
    CircuitConfig,
    DriverIntent,
    DriverMentalState,
    DriverSkills,
    EngineMapName,
    EngineMapParams,
    EnvContext,
    SectionContext,
    SectionKind,
    clamp,
)


ERS_MAX_ENERGY_MJ = 4.0
DEFAULT_MAP_PARAMS = EngineMapParams(name=EngineMapName.RACE)

SECTION_PRIORITY_BASE = {
    SectionKind.STRAIGHT: 1.0,
    SectionKind.MEDIUM_STRAIGHT: 0.85,
    SectionKind.ULTRA_FAST_CORNER: 0.75,
    SectionKind.FAST_CORNER: 0.65,
    SectionKind.MEDIUM_CORNER: 0.5,
    SectionKind.SLOW_CORNER: 0.35,
    SectionKind.VERY_SLOW_CORNER: 0.25,
}

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

def compute_inputs(
    skills: DriverSkills,
    mental: DriverMentalState,
    section: SectionContext,
    env: EnvContext,
    car_state: CarState,
    config: CircuitConfig,
    push_level: float = 1.0,
    lap_number: int = 1,
) -> DriverIntent:
    """
    Determine what the driver wants to do in this section.

    Parameters
    ----------
    skills : DriverSkills    – static skill ratings (1-100)
    mental : DriverMentalState – current confidence/fatigue/pressure
    section : SectionContext  – current circuit section
    env : EnvContext           – weather / track conditions
    car_state : CarState       – current car state
    config : CircuitConfig     – circuit parameters
    push_level : float         – player-commanded push (0.8 conserve → 1.1 push)
    """
    # --- Base pace factor ---
    # Skill-based baseline: raw_pace maps 1-100 → 0.92-1.08
    skill_pace = 0.92 + (skills.raw_pace / 100.0) * 0.16

    # Mental modifiers
    confidence_bonus = (mental.confidence - 0.5) * 0.06   # ±0.03
    fatigue_penalty = mental.fatigue * 0.08                # up to -0.08
    pressure_effect = mental.pressure * 0.04               # up to -0.04

    pace_factor = skill_pace + confidence_bonus - fatigue_penalty - pressure_effect
    pace_factor *= push_level

    # Wet conditions: scale by wet_skill
    if env.rain_intensity > 0.1:
        wet_mult = 0.85 + (skills.wet_skill / 100.0) * 0.15
        pace_factor *= wet_mult

    pace_factor = clamp(pace_factor, 0.80, 1.15)

    # --- Aggression curve bonus ---
    # Higher aggression → more speed in corners but more tyre wear
    aggression_norm = skills.aggression / 100.0
    aggression_curve_bonus = 0.0
    is_corner = section.kind in (
        SectionKind.SLOW_CORNER,
        SectionKind.MEDIUM_CORNER,
        SectionKind.FAST_CORNER,
    )
    if is_corner:
        aggression_curve_bonus = aggression_norm * 0.03 * mental.confidence

    # --- Target line ---
    target_line = "optimal"
    if car_state.side_by_side:
        if skills.defending_skill > skills.overtaking_skill:
            target_line = "defensive"
        else:
            target_line = "aggressive"
    elif car_state.attack_cooldown > 0:
        target_line = "defensive"

    # --- Brake bias adjustment ---
    # Skilled drivers adjust bias per section type
    brake_bias_adjust = 0.0
    craft_norm = skills.race_craft / 100.0
    if section.kind == SectionKind.SLOW_CORNER:
        brake_bias_adjust = craft_norm * 0.005   # slightly more front
    elif section.kind == SectionKind.FAST_CORNER:
        brake_bias_adjust = -craft_norm * 0.003  # slightly more rear

    # --- ERS mode heuristics ---
    ers_mode_raw = (getattr(car_state, "ers_mode", "STANDARD") or "STANDARD").lower()
    ers_push_mode = False
    ers_defense_mode = False

    RECHARGE_ALIASES = {"harvest", "recharge", "safety_car"}
    ers_recharge_mode = ers_mode_raw in RECHARGE_ALIASES

    if ers_mode_raw and not ers_recharge_mode:
        # Tutte le modalità ERS diverse da "recharge" devono comportarsi come push
        ers_push_mode = True

    if car_state.overtake_window > 0.55 and car_state.attack_cooldown <= 0:
        ers_push_mode = True

    if car_state.side_by_side or car_state.defense_reset > 0:
        ers_defense_mode = True

    battery_mj = car_state.pu.ers_energy_mj
    soc_pct = clamp(battery_mj / ERS_MAX_ENERGY_MJ, 0.0, 1.0)
    lap_sections = max(len(config.sections), 1)
    lap_progress = clamp(car_state.current_section_idx / lap_sections, 0.0, 1.0)
    active_map = getattr(car_state.pu, "active_map", EngineMapName.RACE) or EngineMapName.RACE
    map_params = config.pu_maps.get(active_map, config.pu_maps.get(EngineMapName.RACE, DEFAULT_MAP_PARAMS))
    if map_params is None:
        map_params = DEFAULT_MAP_PARAMS
    map_budget = _lookup_map_budget(config, active_map)
    target_soc = map_budget.get("target_soc_end_lap")
    
    is_qualy = (active_map == EngineMapName.QUALIFY)
    
    if target_soc is None:
        target_soc = 0.05 if is_qualy else 0.55
        
    min_soc_clamp = 0.02 if is_qualy else 0.2
    target_soc = clamp(target_soc, min_soc_clamp, 0.95)
    
    reserve_soc = clamp(target_soc + 0.1, min_soc_clamp + 0.05, 0.98)
    late_soc_floor = clamp(target_soc - 0.12, 0.02, 0.9)
    dynamic_soc_floor = reserve_soc - (reserve_soc - late_soc_floor) * lap_progress

    if is_qualy and not is_corner:
        ers_push_mode = True

    if car_state and getattr(car_state, "pu", None):
        car_state.pu.soc_floor_dynamic_pct = dynamic_soc_floor
        car_state.pu.soc_target_pct = target_soc

    if not ers_push_mode and not ers_defense_mode:
        if soc_pct < dynamic_soc_floor and lap_progress < 0.92:
            ers_recharge_mode = True

    if ers_defense_mode and soc_pct > 0.18:
        ers_recharge_mode = False

    if ers_recharge_mode and soc_pct > dynamic_soc_floor + 0.05:
        ers_recharge_mode = False

    # --- ERS deploy request ---
    ers_deploy = False
    if not ers_recharge_mode and battery_mj > 0.08:
        priority_score = _estimate_section_priority(section, ers_push_mode, ers_defense_mode)
        mguh_density = _estimate_mguh_density(map_params, section)
        threshold = 0.55
        if ers_push_mode:
            threshold = 0.32
        elif ers_defense_mode:
            threshold = 0.42
        elif section.drs_available:
            threshold = 0.48

        soc_deficit = dynamic_soc_floor - soc_pct
        if soc_deficit > 0 and not ers_push_mode:
            threshold += clamp(soc_deficit * 1.2, 0.02, 0.2)

        threshold -= mguh_density * 0.12
        if lap_progress > 0.85:
            threshold -= 0.05
        if soc_pct > 0.85:
            threshold -= 0.08

        threshold = clamp(threshold, 0.25, 0.85)
        ers_deploy = priority_score >= threshold and (soc_pct > 0.12 or ers_push_mode)
        if ers_deploy and soc_pct < 0.15 and not ers_push_mode:
            ers_deploy = False

    # --- Tyre save mode ---
    tyre_save = False
    mgmt_norm = skills.tyre_management / 100.0
    # Activate if wear is high and driver has good management
    avg_wear = sum(t.wear_pct for t in car_state.tyres.values()) / max(len(car_state.tyres), 1)
    if avg_wear > 60.0 and mgmt_norm > 0.6:
        tyre_save = True
    # Also if push_level is low (conserve mode)
    if push_level < 0.9:
        tyre_save = True

    # --- Fuel save mode ---
    fuel_save = False
    if car_state.pu.fuel_kg < 5.0:
        fuel_save = True
    if push_level < 0.85:
        fuel_save = True

    brake_warmup_active = False
    brake_warmup_target_front_c = 0.0
    brake_warmup_target_rear_c = 0.0
    brake_warmup_intensity = 0.0
    if lap_number <= 1:
        front_target = config.brake_params.fade_threshold_front_c * 1.00
        rear_target = config.brake_params.fade_threshold_rear_c * 1.00
        front_gap = max(front_target - car_state.brakes.temp_front_c, 0.0)
        rear_gap = max(rear_target - car_state.brakes.temp_rear_c, 0.0)
        warmup_gap = max(
            front_gap / max(front_target, 1.0),
            rear_gap / max(rear_target, 1.0),
        )
        if warmup_gap > 0.02:
            brake_warmup_active = True
            brake_warmup_target_front_c = front_target
            brake_warmup_target_rear_c = rear_target
            craft_norm = skills.race_craft / 100.0
            aggression_norm = skills.aggression / 100.0
            brake_warmup_intensity = clamp(
                1.65 + warmup_gap * 2.2 + craft_norm * 0.26 + aggression_norm * 0.18,
                0.0,
                3.8,
            )

    return DriverIntent(
        pace_factor=pace_factor,
        push_level=max(1, min(10, int(round(push_level * 10 if push_level <= 1.5 else push_level)))) if push_level is not None else 10,
        tyre_management_skill=skills.tyre_management,
        aggression_curve_bonus=aggression_curve_bonus,
        target_line=target_line,
        brake_bias_adjust=brake_bias_adjust,
        ers_deploy_request=ers_deploy,
        ers_push_mode=ers_push_mode,
        ers_defense_mode=ers_defense_mode,
        ers_recharge_mode=ers_recharge_mode,
        tyre_save_mode=tyre_save,
        fuel_save_mode=fuel_save,
        brake_warmup_active=brake_warmup_active,
        brake_warmup_target_front_c=brake_warmup_target_front_c,
        brake_warmup_target_rear_c=brake_warmup_target_rear_c,
        brake_warmup_intensity=brake_warmup_intensity,
    )


def _lookup_map_budget(config: CircuitConfig, active_map: EngineMapName) -> dict:
    budget = config.ers_budget or {}
    maps = budget.get("maps") or {}
    key = active_map.value if isinstance(active_map, EngineMapName) else str(active_map)
    return maps.get(key, {})


def _estimate_section_priority(section: SectionContext, push_mode: bool, defense_mode: bool) -> float:
    base = SECTION_PRIORITY_BASE.get(section.kind, 0.4)
    length_factor = clamp(section.length_m / 350.0, 0.5, 1.3)
    score = base * length_factor
    if section.drs_available:
        score += 0.12
    if push_mode:
        score = score * 1.2 + 0.1
    elif defense_mode and section.kind not in (SectionKind.STRAIGHT, SectionKind.MEDIUM_STRAIGHT):
        score *= 1.05
    return clamp(score, 0.05, 1.2)


def _estimate_mguh_density(map_params: EngineMapParams, section: SectionContext) -> float:
    base_kw = max(map_params.mguh_power_kw or 0.0, 0.0)
    factor = SECTION_MGUH_FACTORS.get(section.kind.value, 0.6)
    dt_ref = section.dt_ref_s or _estimate_section_dt(section)
    mguh_mj = clamp((base_kw * factor * dt_ref) / 1000.0, 0.0, 0.25)
    # normalize ~0.15 MJ window
    return clamp(mguh_mj / 0.15, 0.0, 1.0)


def _estimate_section_dt(section: SectionContext) -> float:
    v_base = max(section.v_base_kph or 180.0, 60.0)
    v_ms = v_base / 3.6
    return clamp(section.length_m / max(v_ms, 1.0), 0.25, 6.0)


# ---------------------------------------------------------------------------
# Mental state update (called after section)
# ---------------------------------------------------------------------------

def update_mental_state(
    mental: DriverMentalState,
    skills: DriverSkills,
    section_performance: float,
    events_severity: float = 0.0,
) -> DriverMentalState:
    """
    Update driver mental state after a section.

    Parameters
    ----------
    section_performance : float  – ratio of actual vs expected time (< 1 = good)
    events_severity : float      – sum of event severities in section
    """
    # Confidence: good performance increases, bad decreases
    if section_performance < 0.98:
        mental.confidence += 0.01 * (skills.consistency / 100.0)
    elif section_performance > 1.03:
        mental.confidence -= 0.015

    # Events reduce confidence
    mental.confidence -= events_severity * 0.02

    # Fatigue: slowly increases, consistency slows it
    mental.fatigue += 0.001 * (1.0 - skills.consistency / 200.0)

    # Pressure: increases when behind, decreases when ahead
    # (simplified: based on events)
    mental.pressure += events_severity * 0.01
    mental.pressure -= 0.002  # natural decay

    # Clamp all
    mental.confidence = clamp(mental.confidence, 0.1, 0.95)
    mental.fatigue = clamp(mental.fatigue, 0.0, 1.0)
    mental.pressure = clamp(mental.pressure, 0.0, 1.0)
    mental.focus = clamp(1.0 - mental.fatigue * 0.3 - mental.pressure * 0.2, 0.3, 1.0)

    return mental
