"""
BattleResolver 2.0 – Multi-car interaction resolution.

Determines overtake outcomes, dirty air penalties, side-by-side battles,
and collision risks for cars in the same section.

This module sits BETWEEN LapSimulator physics (per-car) and the
session orchestrator (ordering/events).

Flow:
  1. LapSimulator runs update_section() for each car independently.
  2. BattleResolver receives all SectionResults + CarStates.
  3. Detects proximity pairs, applies dirty air, resolves battles.
  4. Returns updated ordering + events for HUD/telemetry.

Reference: docs/BattleResolver.md
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .data_types import (
    CarState,
    CORNER_KINDS,
    DriverSkills,
    SectionContext,
    SectionEvent,
    SectionKind,
    SectionResult,
    clamp,
)
from .lap_simulator import CarEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BattleOutcome(str, Enum):
    """Outcome of a battle attempt (spec §4)."""
    NO_BATTLE = "no_battle"
    ATTEMPT = "attempt"
    SIDE_BY_SIDE = "side_by_side"
    OVERTAKE_SUCCESS = "overtake_success"
    BLOCKED = "blocked"
    COLLISION = "collision"


class ScenarioTag(str, Enum):
    """Section scenario for battle context (spec §4bis)."""
    STRAIGHT = "straight"
    HEAVY_BRAKING = "heavy_braking"
    CORNER = "corner"
    CORNER_EXIT = "corner_exit"
    START_RESTART = "start_restart"
    BLUE_FLAG = "blue_flag"
    TEAM_ORDER = "team_order"


# ---------------------------------------------------------------------------
# Constants (spec §6, §6bis)
# ---------------------------------------------------------------------------

# Proximity thresholds (gap in metres)
PROXIMITY_GAP_STRAIGHT_M = 60.0      # max gap to trigger on straight
PROXIMITY_GAP_BRAKING_M = 25.0       # max gap for heavy braking zone
PROXIMITY_GAP_CORNER_M = 10.0        # max gap in corner
PROXIMITY_GAP_EXIT_M = 20.0          # max gap at corner exit

# Delta-v thresholds (km/h) for attempt trigger
DELTA_V_STRAIGHT_MIN = 3.0
DELTA_V_BRAKING_MIN = 5.0
DELTA_V_CORNER_MIN = 8.0             # very hard to pass in corner
DELTA_V_EXIT_MIN = 2.0

# Dirty air penalty (spec §5.3)
DIRTY_AIR_MAX_PENALTY = 0.15         # max aero penalty when right behind
DIRTY_AIR_DECAY_M = 40.0             # penalty decays over this distance
DIRTY_AIR_CORNER_MULTIPLIER = 1.5    # worse in corners (high DF sections)
DIRTY_AIR_STRAIGHT_MULTIPLIER = 0.3  # minimal on straights

# Blocked penalty (spec §6)
BLOCKED_TIME_PENALTY_S = 0.10        # time lost on failed attempt
BLOCKED_PROGRESSION_PENALTY = 0.02   # section progression lost

# Collision risk
COLLISION_BASE_RISK = 0.02           # base probability per attempt
COLLISION_AGGRESSION_SCALE = 0.03    # extra risk per aggression unit above 50

# Side-by-side
SIDE_BY_SIDE_CHANCE_THRESHOLD = 0.4  # chance above this → side-by-side
OVERTAKE_CHANCE_THRESHOLD = 0.65     # chance above this → overtake success


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class BattlePair:
    """A pair of cars in proximity for potential battle."""
    attacker_id: str
    defender_id: str
    gap_m: float = 0.0                # distance between cars
    delta_v_kph: float = 0.0          # speed advantage of attacker
    scenario: ScenarioTag = ScenarioTag.STRAIGHT
    attack_chance: float = 0.0        # 0-1, computed chance of success
    outcome: BattleOutcome = BattleOutcome.NO_BATTLE
    dirty_air_penalty: float = 0.0    # applied to attacker's aero


@dataclass
class BattleEvent:
    """Event emitted by BattleResolver for HUD/telemetry/QA."""
    event_type: str = ""              # battle_attempt, overtake_success, etc.
    attacker_id: str = ""
    defender_id: str = ""
    section_id: str = ""
    scenario: str = ""
    outcome: str = ""
    delta_v_kph: float = 0.0
    gap_m: float = 0.0
    attack_chance: float = 0.0
    message: str = ""                 # radio message for HUD


@dataclass
class BattleResult:
    """Result of resolving all battles in one section."""
    pairs: List[BattlePair] = field(default_factory=list)
    events: List[BattleEvent] = field(default_factory=list)
    dirty_air_penalties: Dict[str, float] = field(default_factory=dict)
    ordering_changes: List[Tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scenario tagging (spec §4bis)
# ---------------------------------------------------------------------------

def tag_scenario(
    section: SectionContext,
    is_start: bool = False,
    is_blue_flag: bool = False,
    is_team_order: bool = False,
) -> ScenarioTag:
    """Determine the battle scenario for a section."""
    if is_start:
        return ScenarioTag.START_RESTART
    if is_blue_flag:
        return ScenarioTag.BLUE_FLAG
    if is_team_order:
        return ScenarioTag.TEAM_ORDER

    # Heavy braking zone
    if section.braking_energy_mj > 0.5:
        return ScenarioTag.HEAVY_BRAKING

    # Corner types
    if section.kind in CORNER_KINDS:
        return ScenarioTag.CORNER

    # Straight (default)
    return ScenarioTag.STRAIGHT


def _proximity_threshold(scenario: ScenarioTag) -> float:
    """Max gap (m) for a battle to be considered."""
    return {
        ScenarioTag.STRAIGHT: PROXIMITY_GAP_STRAIGHT_M,
        ScenarioTag.HEAVY_BRAKING: PROXIMITY_GAP_BRAKING_M,
        ScenarioTag.CORNER: PROXIMITY_GAP_CORNER_M,
        ScenarioTag.CORNER_EXIT: PROXIMITY_GAP_EXIT_M,
        ScenarioTag.START_RESTART: PROXIMITY_GAP_BRAKING_M,
        ScenarioTag.BLUE_FLAG: PROXIMITY_GAP_STRAIGHT_M,
        ScenarioTag.TEAM_ORDER: PROXIMITY_GAP_STRAIGHT_M,
    }.get(scenario, PROXIMITY_GAP_STRAIGHT_M)


def _delta_v_threshold(scenario: ScenarioTag) -> float:
    """Min delta-v (km/h) for an attempt to trigger."""
    return {
        ScenarioTag.STRAIGHT: DELTA_V_STRAIGHT_MIN,
        ScenarioTag.HEAVY_BRAKING: DELTA_V_BRAKING_MIN,
        ScenarioTag.CORNER: DELTA_V_CORNER_MIN,
        ScenarioTag.CORNER_EXIT: DELTA_V_EXIT_MIN,
        ScenarioTag.START_RESTART: DELTA_V_BRAKING_MIN,
        ScenarioTag.BLUE_FLAG: 0.0,       # forced pass
        ScenarioTag.TEAM_ORDER: 0.0,       # forced pass
    }.get(scenario, DELTA_V_STRAIGHT_MIN)


# ---------------------------------------------------------------------------
# Dirty air calculation (spec §5.3)
# ---------------------------------------------------------------------------

def compute_dirty_air(
    gap_m: float,
    section: SectionContext,
) -> float:
    """
    Compute dirty air penalty for the following car.

    Penalty decays linearly with distance. Worse in corners (high DF),
    minimal on straights.

    Returns: penalty 0.0 (clean air) to DIRTY_AIR_MAX_PENALTY.
    """
    if gap_m <= 0 or gap_m > DIRTY_AIR_DECAY_M * 2:
        return 0.0

    # Linear decay with distance
    proximity_factor = clamp(1.0 - gap_m / DIRTY_AIR_DECAY_M, 0.0, 1.0)

    # Section multiplier
    if section.kind in CORNER_KINDS:
        section_mult = DIRTY_AIR_CORNER_MULTIPLIER
    elif section.kind in {SectionKind.STRAIGHT, SectionKind.MEDIUM_STRAIGHT}:
        section_mult = DIRTY_AIR_STRAIGHT_MULTIPLIER
    else:
        section_mult = 1.0

    penalty = DIRTY_AIR_MAX_PENALTY * proximity_factor * section_mult
    return clamp(penalty, 0.0, DIRTY_AIR_MAX_PENALTY)


# ---------------------------------------------------------------------------
# Proximity detection
# ---------------------------------------------------------------------------

def detect_proximity_pairs(
    cars_in_section: List[Tuple[str, float, float]],
    section: SectionContext,
    scenario: ScenarioTag,
) -> List[BattlePair]:
    """
    Detect pairs of cars close enough for a potential battle.

    Parameters
    ----------
    cars_in_section : list of (car_id, gap_to_leader_m, v_effective_kph)
        Sorted by position (leader first). gap_to_leader_m is the gap
        to the car immediately ahead (0 for the leader).
    section : SectionContext
    scenario : ScenarioTag

    Returns
    -------
    List of BattlePair with gap, delta_v, scenario, dirty_air filled in.
    """
    pairs: List[BattlePair] = []
    threshold = _proximity_threshold(scenario)

    for i in range(1, len(cars_in_section)):
        behind_id, behind_gap, behind_v = cars_in_section[i]
        ahead_id, _, ahead_v = cars_in_section[i - 1]

        if behind_gap > threshold:
            continue

        delta_v = behind_v - ahead_v  # positive = attacker faster

        dirty_air = compute_dirty_air(behind_gap, section)

        pairs.append(BattlePair(
            attacker_id=behind_id,
            defender_id=ahead_id,
            gap_m=behind_gap,
            delta_v_kph=delta_v,
            scenario=scenario,
            dirty_air_penalty=dirty_air,
        ))

    return pairs


# ---------------------------------------------------------------------------
# Attack chance calculation (spec §5)
# ---------------------------------------------------------------------------

def compute_attack_chance(
    pair: BattlePair,
    attacker_skills: DriverSkills,
    defender_skills: DriverSkills,
    attacker_result: SectionResult,
    defender_result: SectionResult,
    attacker_state: CarState,
) -> float:
    """
    Compute the probability of a successful overtake attempt.

    Combines delta-v, grip advantage, DRS, driver skills, and scenario.
    Returns 0-1 chance.
    """
    scenario = pair.scenario

    # --- Base from delta-v ---
    dv_threshold = _delta_v_threshold(scenario)

    # Blue flag / team order: forced pass
    if scenario in (ScenarioTag.BLUE_FLAG, ScenarioTag.TEAM_ORDER):
        return 0.95

    # No overtake window from physics → no attempt
    if attacker_state.overtake_window <= 0.01:
        return 0.0

    # Delta-v contribution (0-0.3)
    if pair.delta_v_kph < dv_threshold:
        dv_score = 0.0
    else:
        dv_score = clamp((pair.delta_v_kph - dv_threshold) / 15.0, 0.0, 0.3)

    # --- Grip advantage (0-0.15) ---
    grip_att = (attacker_result.effective_grip_front + attacker_result.effective_grip_rear) / 2.0
    grip_def = (defender_result.effective_grip_front + defender_result.effective_grip_rear) / 2.0
    grip_score = clamp((grip_att - grip_def) * 0.5, -0.1, 0.15)

    # --- DRS bonus (0-0.15) ---
    drs_score = 0.0
    if attacker_result.overtake_window > 0.5:
        drs_score = 0.10
    if attacker_result.late_brake_tag:
        drs_score += 0.05

    # --- Driver skill (0-0.2) ---
    skill_att = attacker_skills.overtaking_skill / 100.0
    skill_def = defender_skills.defending_skill / 100.0
    skill_score = clamp((skill_att - skill_def) * 0.4, -0.1, 0.2)

    # --- Scenario modifier ---
    scenario_mod = {
        ScenarioTag.STRAIGHT: 1.0,
        ScenarioTag.HEAVY_BRAKING: 0.9,
        ScenarioTag.CORNER: 0.3,          # very hard to pass in corner
        ScenarioTag.CORNER_EXIT: 0.7,
        ScenarioTag.START_RESTART: 0.8,
    }.get(scenario, 1.0)

    # --- Dirty air penalty on attacker ---
    dirty_air_malus = pair.dirty_air_penalty * 0.5  # reduces chance

    # --- Overtake window from physics ---
    ow_bonus = attacker_state.overtake_window * 0.15

    # --- Combine ---
    raw_chance = (
        dv_score
        + grip_score
        + drs_score
        + skill_score
        + ow_bonus
        - dirty_air_malus
    ) * scenario_mod

    return clamp(raw_chance, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Battle resolution (spec §5)
# ---------------------------------------------------------------------------

def resolve_pair(
    pair: BattlePair,
    attacker_skills: DriverSkills,
    defender_skills: DriverSkills,
    attacker_result: SectionResult,
    defender_result: SectionResult,
    attacker_state: CarState,
    defender_state: CarState,
) -> BattlePair:
    """
    Resolve a single battle pair: compute chance, determine outcome.

    Mutates attacker/defender CarState (cooldowns, side_by_side).
    Returns the pair with outcome filled in.
    """
    # Skip if attacker on cooldown
    if attacker_state.attack_cooldown > 0:
        pair.outcome = BattleOutcome.NO_BATTLE
        return pair

    # Compute chance
    chance = compute_attack_chance(
        pair, attacker_skills, defender_skills,
        attacker_result, defender_result, attacker_state,
    )
    pair.attack_chance = chance

    # No attempt if chance too low
    if chance < 0.05:
        pair.outcome = BattleOutcome.NO_BATTLE
        return pair

    pair.outcome = BattleOutcome.ATTEMPT

    # --- Collision check ---
    collision_risk = COLLISION_BASE_RISK
    avg_aggression = (attacker_skills.aggression + defender_skills.aggression) / 2.0
    if avg_aggression > 50:
        collision_risk += (avg_aggression - 50) / 100.0 * COLLISION_AGGRESSION_SCALE
    # Wet / low grip increases risk
    grip_avg = (attacker_result.effective_grip_front + attacker_result.effective_grip_rear) / 2.0
    if grip_avg < 0.7:
        collision_risk *= 1.5

    if random.random() < collision_risk:
        pair.outcome = BattleOutcome.COLLISION
        # Apply damage cooldown
        attacker_state.attack_cooldown = 5
        defender_state.defense_reset = 3
        attacker_state.side_by_side = False
        defender_state.side_by_side = False
        return pair

    # --- Determine outcome from chance ---
    if chance >= OVERTAKE_CHANCE_THRESHOLD:
        pair.outcome = BattleOutcome.OVERTAKE_SUCCESS
        attacker_state.attack_cooldown = 2  # brief cooldown after pass
        attacker_state.side_by_side = False
        defender_state.side_by_side = False
    elif chance >= SIDE_BY_SIDE_CHANCE_THRESHOLD:
        pair.outcome = BattleOutcome.SIDE_BY_SIDE
        attacker_state.side_by_side = True
        defender_state.side_by_side = True
    else:
        pair.outcome = BattleOutcome.BLOCKED
        attacker_state.attack_cooldown = 3  # cooldown after failed attempt
        attacker_state.side_by_side = False
        defender_state.side_by_side = False

    return pair


# ---------------------------------------------------------------------------
# Event generation (spec §7, §8)
# ---------------------------------------------------------------------------

_RADIO_MESSAGES = {
    BattleOutcome.OVERTAKE_SUCCESS: {
        ScenarioTag.STRAIGHT: ("Overtake complete on the straight", "He's faster on the straight"),
        ScenarioTag.HEAVY_BRAKING: ("Late braking worked", "Locked up defending"),
        ScenarioTag.CORNER: ("Switchback worked", "Going wide, he cut back"),
        ScenarioTag.CORNER_EXIT: ("Got him on traction", "Struggling for traction"),
    },
    BattleOutcome.BLOCKED: {
        ScenarioTag.STRAIGHT: ("Need more top speed", "Holding him with DRS"),
        ScenarioTag.HEAVY_BRAKING: ("Couldn't dive, brakes fading", "Covered inside line"),
        ScenarioTag.CORNER: ("Too much dirty air", "Holding the apex"),
        ScenarioTag.CORNER_EXIT: ("Need more traction on exit", "Battery empty, can't cover"),
    },
    BattleOutcome.SIDE_BY_SIDE: {
        ScenarioTag.STRAIGHT: ("Side by side!", "He's alongside!"),
        ScenarioTag.HEAVY_BRAKING: ("Into the braking zone together!", "Wheel to wheel!"),
    },
    BattleOutcome.COLLISION: {
        ScenarioTag.STRAIGHT: ("Contact!", "Contact!"),
        ScenarioTag.HEAVY_BRAKING: ("Contact at the braking zone!", "Contact at the braking zone!"),
        ScenarioTag.CORNER: ("Contact in the corner!", "Contact in the corner!"),
    },
}


def _get_radio(outcome: BattleOutcome, scenario: ScenarioTag) -> Tuple[str, str]:
    """Get (attacker_msg, defender_msg) for an outcome+scenario."""
    msgs = _RADIO_MESSAGES.get(outcome, {})
    return msgs.get(scenario, msgs.get(ScenarioTag.STRAIGHT, ("", "")))


def emit_battle_event(pair: BattlePair, section: SectionContext) -> BattleEvent:
    """Create a BattleEvent from a resolved pair."""
    att_msg, _ = _get_radio(pair.outcome, pair.scenario)
    return BattleEvent(
        event_type=f"battle_{pair.outcome.value}",
        attacker_id=pair.attacker_id,
        defender_id=pair.defender_id,
        section_id=section.section_id,
        scenario=pair.scenario.value,
        outcome=pair.outcome.value,
        delta_v_kph=round(pair.delta_v_kph, 1),
        gap_m=round(pair.gap_m, 1),
        attack_chance=round(pair.attack_chance, 3),
        message=att_msg,
    )


# ---------------------------------------------------------------------------
# BattleResolver – main class
# ---------------------------------------------------------------------------

class BattleResolver:
    """
    Resolves multi-car interactions for one section at a time.

    Usage:
        resolver = BattleResolver()
        result = resolver.resolve_section(
            cars_in_section, section, car_entries, section_results
        )
    """

    def __init__(self):
        self.total_overtakes: int = 0
        self.total_collisions: int = 0
        self.total_blocked: int = 0

    def resolve_section(
        self,
        cars_in_section: List[Tuple[str, float, float]],
        section: SectionContext,
        car_entries: Dict[str, CarEntry],
        section_results: Dict[str, SectionResult],
        is_start: bool = False,
        blue_flag_cars: Optional[List[str]] = None,
        team_order_pairs: Optional[List[Tuple[str, str]]] = None,
    ) -> BattleResult:
        """
        Resolve all battles in a section.

        Parameters
        ----------
        cars_in_section : list of (car_id, gap_to_ahead_m, v_effective_kph)
            Sorted by position (leader first).
        section : SectionContext
        car_entries : dict of car_id → CarEntry
        section_results : dict of car_id → SectionResult
        is_start : bool – start/restart scenario
        blue_flag_cars : list of car_ids under blue flag
        team_order_pairs : list of (yielder_id, beneficiary_id)

        Returns
        -------
        BattleResult with pairs, events, dirty_air_penalties, ordering_changes.
        """
        blue_flags = set(blue_flag_cars or [])
        team_orders = {y: b for y, b in (team_order_pairs or [])}

        result = BattleResult()

        # --- Step 1: Compute dirty air for all following cars ---
        for i in range(1, len(cars_in_section)):
            car_id, gap, _ = cars_in_section[i]
            penalty = compute_dirty_air(gap, section)
            if penalty > 0:
                result.dirty_air_penalties[car_id] = penalty

        # --- Step 2: Detect proximity pairs ---
        # Determine scenario per pair (may differ for blue flag / team order)
        base_scenario = tag_scenario(section, is_start=is_start)

        pairs = detect_proximity_pairs(cars_in_section, section, base_scenario)

        # Override scenario for special cases
        for pair in pairs:
            if pair.defender_id in blue_flags:
                pair.scenario = ScenarioTag.BLUE_FLAG
            elif pair.defender_id in team_orders and team_orders[pair.defender_id] == pair.attacker_id:
                pair.scenario = ScenarioTag.TEAM_ORDER

        # --- Step 3: Resolve each pair ---
        for pair in pairs:
            att_entry = car_entries.get(pair.attacker_id)
            def_entry = car_entries.get(pair.defender_id)
            att_result = section_results.get(pair.attacker_id)
            def_result = section_results.get(pair.defender_id)

            if not all([att_entry, def_entry, att_result, def_result]):
                continue

            resolved = resolve_pair(
                pair,
                att_entry.driver_skills,
                def_entry.driver_skills,
                att_result,
                def_result,
                att_entry.state,
                def_entry.state,
            )

            if resolved.outcome == BattleOutcome.NO_BATTLE:
                continue

            result.pairs.append(resolved)
            result.events.append(emit_battle_event(resolved, section))

            # Track stats
            if resolved.outcome == BattleOutcome.OVERTAKE_SUCCESS:
                self.total_overtakes += 1
                result.ordering_changes.append(
                    (resolved.attacker_id, resolved.defender_id)
                )
            elif resolved.outcome == BattleOutcome.BLOCKED:
                self.total_blocked += 1
            elif resolved.outcome == BattleOutcome.COLLISION:
                self.total_collisions += 1

        return result
