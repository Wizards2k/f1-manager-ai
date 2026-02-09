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
    EnvContext,
    SectionContext,
    SectionKind,
    clamp,
)


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

    # --- ERS deploy request ---
    ers_deploy = False
    # Deploy on straights when battery is available
    if section.kind in (SectionKind.STRAIGHT, SectionKind.MEDIUM_STRAIGHT):
        if car_state.pu.ers_energy_mj > 0.5:
            ers_deploy = True
    # Also deploy if attacking
    if car_state.overtake_window > 0.5 and car_state.pu.ers_energy_mj > 0.3:
        ers_deploy = True

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

    return DriverIntent(
        pace_factor=pace_factor,
        aggression_curve_bonus=aggression_curve_bonus,
        target_line=target_line,
        brake_bias_adjust=brake_bias_adjust,
        ers_deploy_request=ers_deploy,
        tyre_save_mode=tyre_save,
        fuel_save_mode=fuel_save,
    )


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
