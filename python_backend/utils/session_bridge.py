"""
Session Bridge v2 – per-section tick loop.

Architecture (see docs/race-engine-integration-spec.md §2):
  Every tick (100ms × game_speed):
    FASE 1: advance time (PSO clock, AI scheduling, pitlane release)
    FASE 2: move cars (accumulate dt per section, call update_section on completion)
    FASE 3: BattleResolver (detect proximity, resolve duels)
    FASE 4: state commit (sync to RaceCar, emit events)

Fase C: Race Engine Integration
"""
from __future__ import annotations

import logging
import random
import os
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lap_simulator.ai_data_types import (
    AIDriverConfig,
    AITeamConfig,
    RunProgram,
    RUN_PROGRAM_DEFAULTS,
    SessionType,
)
from utils.ai_setup_search import AISetupState
from lap_simulator.ai_driver_engine import AIDriverEngine
from lap_simulator.config_loader import load_circuit_config
from lap_simulator.data_types import (
    AeroSetup,
    CarState as SimCarState,
    CircuitConfig,
    EnvContext,
    SectionContext,
    SectionResult,
    TyreCompound,
    EngineMapName,
)
from lap_simulator.update_section import update_section
from lap_simulator.battle_resolver import (
    BattleEvent,
    BattleOutcome,
    BattleResolver,
    BattleResult,
)
from lap_simulator.practice_session import (
    CarPhase,
    PracticeEventType,
    PracticeSessionOrchestrator,
    SessionFlag,
)

from utils.adapter import (
    game_compound_to_sim,
    pilot_to_driver_skills,
    racecar_to_car_entry,
    set_racecar_phase,
    sim_compound_to_game,
)
from utils.microsector_logger import log_microsector
from utils.driver_feedback import (
    get_driver_feedback,
    should_trigger_feedback,
    emit_thermal_feedback,
)
from config import get_current_circuit_profile
from services.tyre_inventory_service import TyreInventoryService
from models.models import TireCompound as GameTireCompound
from debug_log import log_debug_event

logger = logging.getLogger(__name__)


def _chip_color(percent: float) -> str:
    if percent >= 100.0:
        return "ready"
    if percent >= 80.0:
        return "green"
    if percent >= 40.0:
        return "yellow"
    return "red"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_DURATION_S = 3600
OUT_LAP_SPEED_FACTOR = 0.65     # out lap ~65% of reference speed
IN_LAP_SPEED_FACTOR = 0.70      # in lap ~70% of reference speed
SLOW_LAP_SPEED_FACTOR = 0.75    # slow/cooldown lap
MIN_CAR_GAP_M = 40.0            # minimum gap between cars on track (metres)
BLUE_FLAG_CLEAR_TICKS = 5
BLUE_FLAG_PROXIMITY_THRESHOLD_M = 250.0

BRAKE_WARN_TOLERANCE = 0.05
BRAKE_WARN_BLINK_WINDOW_S = 3.0

# Session categorization for blue flag policy
PRACTICE_SESSION_KINDS = {"FP1", "FP2", "FP3", "P1", "P2", "P3", "Q", "QUALI", "QUALIFYING"}
RACE_SESSION_KINDS = {"RACE", "GP", "GRAND_PRIX"}

ICE_MODE_TO_ENGINE_MAP = {
    "PRACTICE": EngineMapName.PRACTICE,
    "RACE": EngineMapName.RACE,
    "QUALIFY": EngineMapName.QUALIFY,
}

ERS_MODE_CANONICAL = {
    "RECHARGE": "RECHARGE",
    "STANDARD": "STANDARD",
    "OVERTAKE": "OVERTAKE",
    "QUALIFY": "QUALIFY",
    "DEFENCE": "DEFENCE",
}


# ---------------------------------------------------------------------------
# CarTrackState – per-car state in the tick loop (spec §2.3)
# ---------------------------------------------------------------------------

class LapPhase:
    OUT_LAP = "out_lap"
    HOT_LAP = "hot_lap"
    IN_LAP = "in_lap"
    SLOW_LAP = "slow_lap"


@dataclass
class CarTrackState:
    """Tracks one car's position within the section grid."""
    car_id: str
    car_entry: Any                          # CarEntry from LapSimulator
    current_section_idx: int = 0            # index into circuit sections
    section_time_acc: float = 0.0           # time accumulated in current section
    lap_section_results: List[SectionResult] = field(default_factory=list)
    lap_number: int = 1
    distance_in_lap: float = 0.0           # metres along circuit (for map)
    laps_done_in_run: int = 0
    laps_planned: int = 5
    is_player: bool = False
    lap_phase: str = LapPhase.OUT_LAP       # current lap type
    pit_exit_delay_s: float = 0.0           # stagger delay before going on track
    pit_exit_waited_s: float = 0.0          # time waited so far
    current_sector: int = 0                 # 0=S1, 1=S2, 2=S3
    sector_dt_acc: float = 0.0             # accumulated dt_s in current sector
    setup_data_complete: bool = False       # AI: has enough setup info → head back in
    tyre_set_id: Optional[str] = None
    tyre_set: Optional['TyreSet'] = None


# Lap phases that should yield under blue flag during practice/quali when a HOT LAP approaches
PRACTICE_SLOW_LAP_PHASES = {
    LapPhase.OUT_LAP,
    LapPhase.IN_LAP,
    LapPhase.SLOW_LAP,
}


# ---------------------------------------------------------------------------
# Team Session Plan (spec: practice-session-orchestrator.md §3.4)
# ---------------------------------------------------------------------------

# Batch scheduling constants (no tier differentiation)
_FIRST_EXIT_WINDOW = (10, 60)         # all cars: first run within 10-60s
_BATCH_STAGGER_S = 8.0                # seconds between consecutive batches
_TEAMMATE_OFFSET = (3, 8)             # offset between teammates in same batch
_INTER_RUN_GAP_RANGE = (75, 150)      # gap between consecutive runs (same car)
_BATCH_SIZE = 8                       # cars per batch (matches MAX_PITLANE_SLOTS)


@dataclass
class ScheduledRun:
    """A single scheduled AI run with a target start time."""
    car_id: str
    planned_start_s: float       # session time at which this run should start
    dispatched: bool = False     # True once we've sent the car out


@dataclass
class TeamSessionPlan:
    """Randomized work plan for one AI team in a session."""
    team_id: str
    tier: str
    scheduled_runs: list = field(default_factory=list)  # List[ScheduledRun]


def _build_team_plans(
    ai_engines: Dict[str, AIDriverEngine],
    teams_cars: Dict[str, List[str]],
) -> Dict[str, TeamSessionPlan]:
    """
    Generate randomized batch-based scheduling for all AI cars.

    All cars are shuffled into random batches of _BATCH_SIZE.
    Each batch gets a staggered start time within _FIRST_EXIT_WINDOW.
    Teammates within the same batch get a small offset (_TEAMMATE_OFFSET).
    Subsequent runs are scheduled based on estimated run duration + inter-run gap.
    """
    # Collect all car_ids with their team
    all_cars: List[tuple] = []  # (car_id, team_name)
    for team_name, car_ids in teams_cars.items():
        for cid in car_ids:
            if cid in ai_engines:
                all_cars.append((cid, team_name))

    # Shuffle all cars randomly
    random.shuffle(all_cars)

    # Split into batches of _BATCH_SIZE
    batches: List[List[tuple]] = []
    for i in range(0, len(all_cars), _BATCH_SIZE):
        batches.append(all_cars[i:i + _BATCH_SIZE])

    # Assign first-run start times per batch
    # Each batch starts at a base time, cars within batch get small jitter
    per_car_first_start: Dict[str, float] = {}
    seen_teams_in_batch: Dict[int, Dict[str, str]] = {}  # batch_idx → {team → first_car_id}

    for batch_idx, batch in enumerate(batches):
        batch_base = random.uniform(*_FIRST_EXIT_WINDOW) + batch_idx * _BATCH_STAGGER_S
        for slot_idx, (car_id, team_name) in enumerate(batch):
            jitter = random.uniform(0, 3.0)
            start = batch_base + slot_idx * 3.0 + jitter

            # If teammate already in this batch, add offset
            if batch_idx not in seen_teams_in_batch:
                seen_teams_in_batch[batch_idx] = {}
            if team_name in seen_teams_in_batch[batch_idx]:
                start += random.uniform(*_TEAMMATE_OFFSET)
            seen_teams_in_batch[batch_idx][team_name] = car_id

            per_car_first_start[car_id] = max(10.0, start)

    # Build per-team plans with all scheduled runs
    plans: Dict[str, TeamSessionPlan] = {}

    for team_name, car_ids in teams_cars.items():
        tier = _get_team_tier(team_name)
        scheduled: List[ScheduledRun] = []

        for car_id in car_ids:
            engine = ai_engines.get(car_id)
            if engine is None:
                continue
            n_runs = len(engine.session_plan.runs)
            inter_gap = random.uniform(*_INTER_RUN_GAP_RANGE)

            for run_idx in range(n_runs):
                if run_idx == 0:
                    start_s = per_car_first_start.get(car_id, 30.0)
                else:
                    prev_run = engine.session_plan.runs[run_idx - 1]
                    est_run_duration = prev_run.laps_planned * 100.0 + 30.0
                    pilot_runs = [r for r in scheduled if r.car_id == car_id]
                    prev_start = pilot_runs[-1].planned_start_s if pilot_runs else 30.0
                    start_s = prev_start + est_run_duration + inter_gap + random.uniform(-15, 15)

                scheduled.append(ScheduledRun(
                    car_id=car_id,
                    planned_start_s=max(10.0, start_s),
                ))

        # Sort by planned start time
        scheduled.sort(key=lambda r: r.planned_start_s)

        # Anti-collision: ensure no two runs start within 5s of each other
        for i in range(1, len(scheduled)):
            if scheduled[i].planned_start_s - scheduled[i-1].planned_start_s < 5.0:
                scheduled[i].planned_start_s = scheduled[i-1].planned_start_s + random.uniform(5.0, 8.0)

        plans[team_name] = TeamSessionPlan(
            team_id=team_name,
            tier=tier,
            scheduled_runs=scheduled,
        )

    return plans


# ---------------------------------------------------------------------------
# Team tier mapping
# ---------------------------------------------------------------------------

_TEAM_TIERS = {
    "Oracle Red Bull Racing": "top",
    "Scuderia Ferrari": "top",
    "Mercedes-AMG PETRONAS": "top",
    "McLaren F1 Team": "top",
    "Aston Martin Aramco": "midfield",
    "BWT Alpine F1 Team": "midfield",
    "Williams Racing": "midfield",
    "Visa Cash App RB": "midfield",
    "Stake F1 Team Kick Sauber": "backmarker",
    "MoneyGram Haas F1 Team": "backmarker",
}

# Substring fallback keywords
_TIER_KEYWORDS = {
    "top": ["red bull", "ferrari", "mercedes", "mclaren"],
    "midfield": ["aston", "alpine", "williams", "rb"],
    "backmarker": ["sauber", "haas", "kick"],
}


def _get_team_tier(team_name: str) -> str:
    tier = _TEAM_TIERS.get(team_name)
    if tier:
        return tier
    lower = team_name.lower()
    for t, keywords in _TIER_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return t
    return "midfield"


def _ai_setup_target(sim_efficiency: int) -> float:
    """Compute setup info target for AI cars based on team simulation quality.

    Top teams have better simulators → initial setup closer to optimal
    → less on-track data needed.  Results (at gain ≈ 35 pts/hot-lap):
      top  (sim_eff=85) → target ≈ 212 → ~6 hot laps → 2-3 runs
      mid  (sim_eff=70) → target ≈ 325 → ~9 hot laps → 3-4 runs
      back (sim_eff=55) → target ≈ 438 → ~12 hot laps → 4-5 runs
    """
    factor = 1.0 - (sim_efficiency / 100.0)
    return round(100.0 + factor * 750.0, 1)


# ---------------------------------------------------------------------------
# Session Bridge
# ---------------------------------------------------------------------------

THERMAL_FEEDBACK_EVENTS = {
    "tyre_overheat",
    "tyre_blistering",
    "brake_hot_section",
    "brake_fade",
    "brake_critical",
}


class SessionBridge:
    """
    Bridges the new LapSimulator engine with the existing game backend.

    Uses a per-section tick loop: every tick, each on-track car accumulates
    sim_dt in its current section. When the accumulated time reaches dt_ref_s,
    update_section() is called to compute the physics for that section.
    """

    def __init__(self):
        self.active = False
        self.circuit_id: Optional[str] = None
        self.circuit_config: Optional[CircuitConfig] = None
        self.circuit_profile: Optional[Dict[str, Any]] = None
        self.telemetry_store = None
        self.sections: List[SectionContext] = []
        self.env = EnvContext()
        self.pso: Optional[PracticeSessionOrchestrator] = None
        self.ai_engines: Dict[str, AIDriverEngine] = {}
        self.race_cars_map: Dict[str, Any] = {}
        self.ai_setup_plan_lookup: Dict[str, Dict[str, Any]] = {}
        self._accumulated_time_s: float = 0.0
        self._last_tick_real_time: float = time.time()
        self._sector_end_m: List[float] = []
        self.battle_events: List[BattleEvent] = []
        self._ai_teams_cars: Dict[str, List[str]] = {}  # team_name → [car_ids]
        self.battle_resolver = BattleResolver()
        self.battle_events: List[BattleEvent] = []       # events from last tick
        self._battle_cooldown: set = set()               # car_ids protected from min-gap this tick
        self._ai_setup_states: Dict[str, AISetupState] = {}  # car_id → AI setup search state
        self.session_kind: str = "FP1"
        self._ai_report_enabled = os.getenv("F1_AI_SETUP_REPORT", "0").lower() in {"1", "true", "yes"}
        self._event_feed: List[Dict[str, Any]] = []
        self.tyre_inventory_service = TyreInventoryService()
        self._player_runtime_state: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def init_session(
        self,
        circuit_id: str,
        race_cars: list,
        session_type: str = "FP1",
    ) -> bool:
        self.circuit_id = circuit_id
        try:
            self.circuit_config = load_circuit_config(circuit_id)
        except Exception as e:
            logger.error("Failed to load circuit config for %s: %s", circuit_id, e)
            return False

        self.sections = self.circuit_config.sections
        if not self.sections:
            logger.error("No sections in circuit config for %s", circuit_id)
            return False

        try:
            self.circuit_profile = get_current_circuit_profile()
        except Exception:
            self.circuit_profile = None

        self.session_kind = (session_type or "FP1").upper()
        try:
            st = SessionType(self.session_kind)
        except ValueError:
            logger.warning("Unsupported session_type %s, defaulting to FP1 for PSO", session_type)
            st = SessionType.FP1

        self.pso = PracticeSessionOrchestrator(st, duration_s=SESSION_DURATION_S)
        if self.circuit_config:
            self.pso.set_circuit_calibration(
                energy_guidance=self.circuit_config.ers_budget,
                regen_profile=self.circuit_config.regen_profile,
                brake_profile=self.circuit_config.brake_profile,
            )

        teams: Dict[str, List] = {}
        for car in race_cars:
            teams.setdefault(car.team_name, []).append(car)

        self.ai_engines = {}
        self.race_cars_map = {}

        alloc = {
            TyreCompound.C2: 2, TyreCompound.C3: 3, TyreCompound.C4: 3,
            TyreCompound.C5: 8, TyreCompound.INTERMEDIATE: 4, TyreCompound.WET: 3,
        }

        for team_name, cars in teams.items():
            car_ids = [str(c.driver_number) for c in cars]
            driver_names = [c.driver_name for c in cars]
            player_car_ids = {str(c.driver_number) for c in cars if c.is_player_controlled}

            self.pso.register_team(
                team_id=team_name, car_ids=car_ids,
                driver_names=driver_names, player_car_ids=player_car_ids,
                allocation=alloc,
            )

            tier = _get_team_tier(team_name)
            team_cfg = AITeamConfig(
                team_id=team_name, budget_tier=tier,
                simulation_efficiency=85 if tier == "top" else 70 if tier == "midfield" else 55,
            )

            for car in cars:
                car_id = str(car.driver_number)
                self.race_cars_map[car_id] = car

                if not car.is_player_controlled:
                    driver_cfg = AIDriverConfig(
                        driver_id=car.driver_name,
                        sim_affinity=getattr(car.pilot, "velocita", 50),
                        mechanical_sympathy=getattr(car.pilot, "ricerca_assetto", 50),
                    )
                    skills = pilot_to_driver_skills(car.pilot)
                    engine = AIDriverEngine(
                        self.circuit_config, team_cfg, driver_cfg, skills,
                    )
                    engine.start_session(st)
                    self.ai_engines[car_id] = engine
                    self._ai_teams_cars.setdefault(team_name, []).append(car_id)

                    # AI Setup Search: create state with baseline from simulator_quality
                    team_obj = getattr(car, 'team', None)
                    sim_q = getattr(team_obj, 'simulator_quality', None) if team_obj else None
                    if sim_q is None:
                        # Fallback: derive from tier
                        sim_q = 88 if tier == 'top' else 72 if tier == 'midfield' else 58
                    ric_ass = getattr(car.pilot, 'ricerca_assetto', 50) if hasattr(car, 'pilot') else 50
                    perf = getattr(car.pilot, 'perfezionismo', 50) if hasattr(car, 'pilot') else 50
                    ai_ss = AISetupState(
                        car_id=car_id,
                        driver_name=car.driver_name,
                        team_name=team_name,
                        simulator_quality=sim_q,
                        ricerca_assetto=ric_ass,
                        perfezionismo=perf,
                    )
                    ai_ss.initialize(seed=hash(car_id) & 0xFFFFFFFF)
                    self._ai_setup_states[car_id] = ai_ss
                    logger.info(
                        "AI %s setup baseline: score=%.2f, threshold=%.2f (sim_q=%d, ric=%d, perf=%d)",
                        car_id, ai_ss.setup_score, ai_ss.threshold,
                        sim_q, ric_ass, perf,
                    )

        # Seed PU/brake telemetry so frontend has configuration data before first lap
        for car_id, car in self.race_cars_map.items():
            try:
                entry = racecar_to_car_entry(car)
                entry.car_id = car_id
                entry.state.car_id = car_id
                car.pu_stats = self._build_pu_stats(entry)
                car.brake_diagnostics = self._build_brake_diagnostics(None)
                car.brake_cooling = self._build_brake_cooling(entry, car)
            except Exception as exc:
                logger.warning("Failed to seed PU stats for %s: %s", car_id, exc)

        # Precompute section cumulative distances for fast lookup
        self._section_end_m = []
        cum = 0.0
        for s in self.sections:
            cum += s.length_m
            self._section_end_m.append(cum)

        # Precompute sector boundaries from sector_markers_m
        # sector_markers_m = [0, S1_end_m, S2_end_m] → S3 ends at circuit_length
        markers = self.circuit_config.sector_markers_m
        if len(markers) >= 2:
            self._sector_end_m = [markers[1], markers[2] if len(markers) > 2 else self.circuit_config.circuit_length_m, self.circuit_config.circuit_length_m]
        else:
            third = self.circuit_config.circuit_length_m / 3.0
            self._sector_end_m = [third, third * 2, self.circuit_config.circuit_length_m]

        self.pso.start_session()
        self.active = True
        self._accumulated_time_s = 0.0
        self._track_states = {}
        if self.telemetry_store is not None:
            self.telemetry_store.reset(circuit_id=circuit_id)

        # Generate randomized team session plans
        self._team_plans = _build_team_plans(self.ai_engines, self._ai_teams_cars)
        total_scheduled = sum(len(p.scheduled_runs) for p in self._team_plans.values())
        logger.info("Generated %d team plans with %d scheduled runs", len(self._team_plans), total_scheduled)
        for tn, plan in self._team_plans.items():
            for sr in plan.scheduled_runs:
                logger.debug("  %s car %s: planned at %.0fs", tn, sr.car_id, sr.planned_start_s)

        logger.info(
            "SessionBridge v2 initialized: %s on %s (%d cars, %d AI, %d sections)",
            session_type, circuit_id, len(race_cars),
            len(self.ai_engines), len(self.sections),
        )
        return True

    def _resolve_game_compound_label(self, sim_compound) -> str:
        """Return soft/medium/hard based on circuit nomination, fallback to default mapping."""
        sim_value = sim_compound.value if hasattr(sim_compound, "value") else str(sim_compound)
        nomination = getattr(self.circuit_config, "pirelli_nomination", None)
        if nomination:
            for role, compound in nomination.items():
                if compound == sim_value:
                    return role.lower()
        return sim_compound_to_game(sim_compound)

    def _resolve_program_compound_label(self, run_plan) -> str:
        """Resolve intended game-level compound for a run without overfitting to event nomination."""

        defaults = RUN_PROGRAM_DEFAULTS.get(getattr(run_plan, 'program', None), {})
        default_compound = defaults.get('compound')
        if default_compound is not None:
            return sim_compound_to_game(default_compound)
        return sim_compound_to_game(getattr(run_plan, 'compound', None))

    def _get_ai_tyre_fallback_compounds(self, preferred_compound: str) -> list[str]:
        preferred = str(preferred_compound or '').strip().lower()
        dry_order = ['soft', 'medium', 'hard']
        wet_order = ['intermediate', 'wet']
        if preferred in wet_order:
            return [compound for compound in wet_order if compound != preferred]
        return [compound for compound in dry_order if compound != preferred]

    def _reserve_ai_tyre_set(self, car_id: str, run_plan) -> Optional['TyreSet']:
        if not self.circuit_id:
            return None
        race_car = self.race_cars_map.get(str(car_id))
        preferred_set_id = None
        if race_car and hasattr(race_car, 'player_config'):
            preferred_set_id = race_car.player_config.get('tyre_set_id')
        compound_label = self._resolve_program_compound_label(run_plan)
        fallback_compounds = self._get_ai_tyre_fallback_compounds(compound_label)
        tyre_set = self.tyre_inventory_service.reserve_best_available_set_with_fallback(
            driver_id=str(car_id),
            circuit_id=self.circuit_id,
            compound=compound_label,
            fallback_compounds=fallback_compounds,
            preferred_set_id=preferred_set_id,
            minimum_condition=40.0,
        )
        reused = bool(preferred_set_id and tyre_set.set_id == preferred_set_id)
        log_debug_event(
            'ai_tyre_reserved',
            car_id=str(car_id),
            circuit_id=self.circuit_id,
            compound_requested=compound_label,
            preferred_set_id=preferred_set_id,
            tyre_set_id=tyre_set.set_id,
            reused=reused,
            tyre_compound=tyre_set.compound,
            condition=round(tyre_set.condition, 2),
            heat_cycles=tyre_set.heat_cycles,
            laps_completed=tyre_set.laps_completed,
            is_q3_reserve=tyre_set.is_q3_reserve,
            fallback_used=tyre_set.compound != compound_label,
        )
        return tyre_set

    # ------------------------------------------------------------------
    # Tick — the main loop (spec §2.1)
    # ------------------------------------------------------------------

    def tick(self, sim_dt: float) -> None:
        """
        Advance the session by sim_dt seconds of simulation time.

        Called from f1_manager_ai.py: sim_dt = 0.1 × game_speed.
        """
        if not self.active or self.pso is None:
            return

        self._accumulated_time_s += sim_dt

        # ── FASE 1: ADVANCE TIME ──
        self._schedule_ai_runs()

        self.pso.tick(sim_dt)

        if self.pso.is_finished:
            self._finish_session()
            return

        # ── FASE 2: MOVE CARS (per-section) ──
        self._move_cars(sim_dt)

        # ── FASE 3: SEPARATION / BATTLE ──
        self._resolve_battles()

        # ── FASE 4: STATE COMMIT ──
        self._sync_phases()

    def _emit_driver_tyre_inventory(self, driver_id: str, overrides: Optional[Dict[str, Any]] = None) -> None:
        """Push the up-to-date tyre inventory for a specific driver to the UI."""
        if not driver_id or not self.circuit_id:
            return
        try:
            inventory = self.tyre_inventory_service.get_inventory(driver_id, self.circuit_id)
        except Exception as exc:
            logger.warning("tyre inventory: failed to load inventory for driver %s: %s", driver_id, exc)
            return

        inventory_dict = inventory.to_dict()
        if overrides:
            override_set_id = overrides.get("set_id")
            if override_set_id:
                for tyre in inventory_dict.get("sets", []):
                    if tyre.get("set_id") == override_set_id:
                        for key, value in overrides.items():
                            if key == "set_id":
                                continue
                            tyre[key] = value
                        break

        payload = {
            "driver_id": driver_id,
            "circuit_id": self.circuit_id,
            "inventory": inventory_dict,
        }
        self._queue_event_feed(
            event_type="tyre_inventory_update",
            car_id=driver_id,
            payload=payload,
            ui_targets=["socket", "tyre_panel", "garage"],
        )

    def _compute_live_tyre_condition_pct(self, race_car) -> Optional[float]:
        if not race_car:
            return None
        tyre_states = getattr(race_car, "tyre_states", {}) or {}
        wear_samples: List[float] = []
        for state in tyre_states.values():
            wear = state.get("wear_pct") if isinstance(state, dict) else None
            if wear is not None:
                wear_samples.append(float(wear))
        if wear_samples:
            avg_wear_pct = sum(wear_samples) / len(wear_samples)
            return max(0.0, min(100.0, 100.0 - avg_wear_pct))
        current_pct = getattr(race_car, "current_tyre_condition_pct", None)
        if isinstance(current_pct, (int, float)):
            try:
                return max(0.0, min(100.0, float(current_pct)))
            except (TypeError, ValueError):
                pass
        live_ratio = getattr(race_car, "tire_wear", None)
        if isinstance(live_ratio, (int, float)):
            return max(0.0, min(100.0, 100.0 - (float(live_ratio) * 100.0)))
        return None

    # ------------------------------------------------------------------
    # FASE 2: Move cars
    # ------------------------------------------------------------------

    def _move_cars(self, sim_dt: float) -> None:
        """
        For each on-track car:
        1. Accumulate sim_dt in current section
        2. Interpolate position (every tick)
        3. If section completed → call update_section(), advance
        4. If lap completed → commit lap
        """
        if not self.sections or self.circuit_config is None:
            return

        n_sections = len(self.sections)
        circuit_m = self.circuit_config.circuit_length_m

        completed_runs = []

        for car_id, ts in list(self._track_states.items()):
            # Check PSO phase
            pso_car = self.pso.cars.get(car_id) if self.pso else None
            if not pso_car or pso_car.phase != CarPhase.ON_TRACK:
                continue

            race_car = self.race_cars_map.get(car_id)
            if race_car is None:
                continue

            # ── Stagger delay: wait before entering track ──
            if ts.pit_exit_delay_s > 0 and ts.pit_exit_waited_s < ts.pit_exit_delay_s:
                ts.pit_exit_waited_s += sim_dt
                continue

            section = self.sections[ts.current_section_idx]

            # ── Speed factor based on lap phase ──
            if ts.lap_phase == LapPhase.OUT_LAP:
                speed_factor = OUT_LAP_SPEED_FACTOR
            elif ts.lap_phase == LapPhase.IN_LAP:
                speed_factor = IN_LAP_SPEED_FACTOR
            elif ts.lap_phase == LapPhase.SLOW_LAP:
                speed_factor = SLOW_LAP_SPEED_FACTOR
            else:
                speed_factor = 1.0

            # Accumulate time (slower laps take longer per section)
            dt_ref = section.dt_ref_s if section.dt_ref_s > 0 else 3.0
            effective_dt_ref = dt_ref / speed_factor  # slower = more time per section
            ts.section_time_acc += sim_dt

            # ── Interpolate position (every tick) ──
            fraction = min(ts.section_time_acc / effective_dt_ref, 1.0)

            dist_in_section = fraction * section.length_m
            section_start_m = self._section_end_m[ts.current_section_idx] - section.length_m if ts.current_section_idx < len(self._section_end_m) else 0
            ts.distance_in_lap = section_start_m + dist_in_section

            # Speed interpolation (v_entry → v_exit) scaled by phase
            v_entry = section.v_entry_kph if section.v_entry_kph > 0 else 200.0
            v_exit = section.v_exit_kph if section.v_exit_kph > 0 else v_entry
            speed_kph = (v_entry + fraction * (v_exit - v_entry)) * speed_factor

            race_car.distance_traveled = ts.distance_in_lap % circuit_m
            race_car.speed = max(speed_kph / 3.6, 1.0)

            # Set RaceCar state based on lap phase
            set_racecar_phase(race_car, ts.lap_phase)

            # ── Check section completion ──
            if ts.section_time_acc >= effective_dt_ref:
                overflow = ts.section_time_acc - effective_dt_ref

                # Call update_section() for physics
                entry = ts.car_entry
                try:
                    result = update_section(
                        car_state=entry.state,
                        aero_setup=entry.aero_setup,
                        driver_skills=entry.driver_skills,
                        section=section,
                        env=self.env,
                        config=self.circuit_config,
                        push_level=entry.push_level,
                        delta_aero=getattr(entry, 'delta_aero', 0.0),
                        delta_grip=getattr(entry, 'delta_grip', 0.0),
                        apply_baseline_delta=getattr(entry, 'apply_baseline_delta', True),
                    )
                except Exception as e:
                    logger.error("update_section error for %s: %s", car_id, e)
                    result = None

                if result is None:
                    logger.error("update_section returned None for %s; using fallback section result", car_id)
                    result = SectionResult(dt_s=dt_ref, v_exit_kph=speed_kph)

                # Apply out lap / in lap penalty to the recorded dt_s
                from dataclasses import replace as _dc_replace
                lap_speed_factor = 1.0
                if ts.lap_phase == LapPhase.OUT_LAP:
                    lap_speed_factor = OUT_LAP_SPEED_FACTOR
                elif ts.lap_phase == LapPhase.IN_LAP:
                    lap_speed_factor = IN_LAP_SPEED_FACTOR
                elif ts.lap_phase == LapPhase.SLOW_LAP:
                    lap_speed_factor = SLOW_LAP_SPEED_FACTOR

                if lap_speed_factor != 1.0:
                    scaled_points = []
                    for point in getattr(result, 'telemetry_points', []) or []:
                        scaled_point = dict(point)
                        if scaled_point.get('speed_kph') is not None:
                            scaled_point['speed_kph'] = round(float(scaled_point['speed_kph']) * lap_speed_factor, 3)
                        if scaled_point.get('dt_s') is not None:
                            scaled_point['dt_s'] = round(float(scaled_point['dt_s']) / lap_speed_factor, 4)
                        scaled_points.append(scaled_point)

                    result = _dc_replace(
                        result,
                        dt_s=result.dt_s / lap_speed_factor,
                        v_exit_kph=result.v_exit_kph * lap_speed_factor,
                        v_entry_kph=result.v_entry_kph * lap_speed_factor,
                        v_effective_kph=result.v_effective_kph * lap_speed_factor,
                        v_max_kph=result.v_max_kph * lap_speed_factor,
                        telemetry_points=scaled_points,
                    )

                try:
                    tyres_payload: Dict[str, Dict[str, Any]] = {}
                    tyre_wear_vals: List[float] = []
                    tyre_temp_vals: List[float] = []
                    for wp, tyre in getattr(entry.state, 'tyres', {}).items():
                        compound = getattr(getattr(tyre, 'compound', None), 'value', None)
                        tyres_payload[wp.name] = {
                            'compound': compound,
                            'wear_pct': getattr(tyre, 'wear_pct', None),
                            'surface_temp_c': getattr(tyre, 'surface_temp_c', None),
                            'age_laps': getattr(tyre, 'lap_age', None),
                        }
                        if getattr(tyre, 'wear_pct', None) is not None:
                            tyre_wear_vals.append(tyre.wear_pct)
                        if getattr(tyre, 'surface_temp_c', None) is not None:
                            tyre_temp_vals.append(tyre.surface_temp_c)

                    pu_state = getattr(entry.state, 'pu', None)
                    log_microsector({
                        'car_id': entry.car_id,
                        'lap': ts.lap_number,
                        'section_id': section.section_id,
                        'section_index': ts.current_section_idx,
                        'section_kind': section.kind.name,
                        'section_length_m': section.length_m,
                        'dt_s': result.dt_s,
                        'v_entry_kph': result.v_entry_kph,
                        'v_exit_kph': result.v_exit_kph,
                        'v_max_kph': result.v_max_kph,
                        'v_effective_kph': result.v_effective_kph,
                        'penalties': {
                            'fuel_s': result.fuel_penalty_s,
                            'tyre_s': result.tyre_penalty_s,
                            'push_s': result.push_penalty_s,
                            'engine_s': result.engine_penalty_s,
                            'brake_s': result.brake_penalty_s,
                            'setup_s': result.setup_penalty_s,
                            'df_curve_penalty_s': result.df_curve_penalty_s,
                            'df_curve_bonus_s': result.df_curve_bonus_s,
                            'drag_penalty_s': result.drag_penalty_s,
                            'drag_bonus_s': result.drag_bonus_s,
                            'handling_penalty': result.handling_penalty,
                        },
                        'push_level': entry.push_level,
                        'delta_aero': getattr(entry, 'delta_aero', 0.0),
                        'delta_grip': getattr(entry, 'delta_grip', 0.0),
                        'apply_baseline_delta': getattr(entry, 'apply_baseline_delta', True),
                        'setup_sliders': getattr(entry, 'setup_sliders', {}),
                        'ideal_setup_sliders': getattr(entry, 'ideal_setup_sliders', {}),
                        'tyres': tyres_payload,
                        'tyre_avg_wear_pct': sum(tyre_wear_vals) / len(tyre_wear_vals) if tyre_wear_vals else None,
                        'tyre_avg_temp_c': sum(tyre_temp_vals) / len(tyre_temp_vals) if tyre_temp_vals else None,
                        'fuel_kg': getattr(pu_state, 'fuel_kg', None),
                        'ers_energy_mj': getattr(pu_state, 'ers_energy_mj', None),
                        'ers_mode': getattr(entry.state, 'ers_mode', None),
                        'engine_map': getattr(getattr(pu_state, 'active_map', None), 'value', None),
                        'overtake_window': result.overtake_window,
                        'braking_efficiency': result.braking_efficiency,
                        'power_kw': result.power_kw,
                        'events': [evt.event_type for evt in result.events],
                        'lap_phase': str(ts.lap_phase),
                    })
                except Exception:
                    logger.debug('microsector logging failed for %s', entry.car_id, exc_info=True)

                ts.lap_section_results.append(result)

                # Track sector time accumulation
                ts.sector_dt_acc += result.dt_s

                # Check sector crossing
                section_end_m = self._section_end_m[ts.current_section_idx] if ts.current_section_idx < len(self._section_end_m) else 0
                if ts.current_sector < len(self._sector_end_m) and section_end_m >= self._sector_end_m[ts.current_sector]:
                    sector_key = f"sector{ts.current_sector + 1}"
                    sector_index = ts.current_sector
                    sector_time = ts.sector_dt_acc
                    if not hasattr(race_car, 'current_lap_sectors') or race_car.current_lap_sectors is None:
                        race_car.current_lap_sectors = {}
                    race_car.current_lap_sectors[sector_key] = sector_time
                    # Update personal best sectors live (only during HOT_LAP)
                    if ts.lap_phase == LapPhase.HOT_LAP:
                        best = race_car.best_sectors.get(sector_key)
                        if best is None or sector_time < best:
                            race_car.best_sectors[sector_key] = sector_time
                        # Update session bests immediately so frontend can show purple/green
                        from utils.game_logic import update_session_bests
                        update_session_bests(race_car)
                    ts.current_sector += 1
                    ts.sector_dt_acc = 0.0

                # Update RaceCar with section data/telemetry
                for ev in result.events:
                    self._update_brake_warning(race_car, ev.event_type)
                    if (
                        ts.is_player
                        and ts.lap_phase == LapPhase.HOT_LAP
                        and ev.event_type in THERMAL_FEEDBACK_EVENTS
                    ):
                        emit_thermal_feedback(race_car, ev.event_type, getattr(ev, "message", None))
                self._apply_section_to_racecar(race_car, entry, result, section)

                # Advance to next section
                ts.current_section_idx += 1
                ts.section_time_acc = overflow
                entry.state.current_section_idx = ts.current_section_idx

                # ── Check lap completion ──
                if ts.current_section_idx >= n_sections:
                    self._commit_lap(car_id, ts, race_car)
                    ts.current_section_idx = 0
                    entry.state.current_section_idx = 0
                    ts.section_time_acc = 0.0

                    # Reset sector tracking for next lap
                    ts.current_sector = 0
                    ts.sector_dt_acc = 0.0
                    race_car.current_lap_sectors = {}

                    # Update lap phase for next lap
                    if ts.laps_done_in_run >= ts.laps_planned:
                        completed_runs.append(car_id)
                    elif ts.setup_data_complete and not ts.is_player:
                        ts.lap_phase = LapPhase.IN_LAP
                    elif ts.laps_done_in_run >= ts.laps_planned - 1:
                        ts.lap_phase = LapPhase.IN_LAP
                    else:
                        ts.lap_phase = LapPhase.HOT_LAP

        # Complete finished runs
        for car_id in completed_runs:
            self._complete_car_run(car_id)

    # ------------------------------------------------------------------
    # Lap commit
    # ------------------------------------------------------------------

    def _commit_lap(self, car_id: str, ts: CarTrackState, race_car) -> None:
        """Commit a completed lap: update RaceCar with lap time, sectors, etc."""
        from models import CarState as GameCarState
        from utils.game_logic import update_session_bests

        lap_time = sum(r.dt_s for r in ts.lap_section_results)
        ts.laps_done_in_run += 1
        ts.lap_number += 1

        
        # Append lap time
        race_car.lap_times.append(lap_time)
        race_car.total_laps += 1
        race_car.total_session_laps += 1
        race_car.tire_age += 1
        race_car.stint_laps_remaining = max(0, race_car.stint_laps_remaining - 1)

        is_competitive = (ts.lap_phase == LapPhase.HOT_LAP)

        # Best lap (only competitive laps)
        if is_competitive:
            if not hasattr(race_car, "best_lap_time") or lap_time < getattr(race_car, "best_lap_time", float("inf")):
                race_car.best_lap_time = lap_time

        # Flush remaining sector time (S3 ends at finish line, not at a sector marker)
        if ts.sector_dt_acc > 0 and ts.current_sector < 3:
            sector_key = f"sector{ts.current_sector + 1}"
            if not hasattr(race_car, 'current_lap_sectors') or race_car.current_lap_sectors is None:
                race_car.current_lap_sectors = {}
            race_car.current_lap_sectors[sector_key] = ts.sector_dt_acc
            if is_competitive:
                best = race_car.best_sectors.get(sector_key)
                if best is None or ts.sector_dt_acc < best:
                    race_car.best_sectors[sector_key] = ts.sector_dt_acc

        # Use live-tracked sector times
        sectors = getattr(race_car, 'current_lap_sectors', {}) or {}
        if sectors:
            race_car.last_sector_times = dict(sectors)
            if is_competitive:
                for key, val in sectors.items():
                    best = race_car.best_sectors.get(key)
                    if best is None or val < best:
                        race_car.best_sectors[key] = val
                if lap_time <= getattr(race_car, "best_lap_time", float("inf")):
                    race_car.best_lap_sectors = dict(sectors)

        # Set last_lap_type to actual phase
        phase_to_state = {
            LapPhase.OUT_LAP: GameCarState.OUT_LAP,
            LapPhase.HOT_LAP: GameCarState.HOT_LAP,
            LapPhase.IN_LAP: GameCarState.IN_LAP,
        }
        race_car.last_lap_type = phase_to_state.get(ts.lap_phase, GameCarState.HOT_LAP)
        race_car.distance_traveled = 0

        lap_points = []
        for result in ts.lap_section_results:
            for point in getattr(result, 'telemetry_points', []) or []:
                lap_points.append(point)

        lap_telemetry = {
            'lap_number': ts.lap_number - 1,
            'lap_time_s': round(lap_time, 3),
            'lap_phase': ts.lap_phase,
            'is_competitive': bool(is_competitive),
            'points': lap_points,
        }
        if self.telemetry_store is not None:
            self.telemetry_store.append_lap(
                car_id=car_id,
                lap_number=lap_telemetry['lap_number'],
                lap_time_s=lap_telemetry['lap_time_s'],
                lap_phase=lap_telemetry['lap_phase'],
                is_competitive=lap_telemetry['is_competitive'],
                points=lap_points,
            )

        # Accumulate setup info points (player only — AI uses ai_setup_search)
        ai_ready_for_box = False
        if is_competitive and ts.is_player and hasattr(race_car, '_accumulate_setup_info'):
            race_car._accumulate_setup_info(GameCarState.HOT_LAP)

        # Update session bests (only competitive laps)
        if is_competitive:
            update_session_bests(race_car)

        # Reset PU state for next lap (same logic as LapSimulator._run_lap_single)
        pu_state = ts.car_entry.state.pu
        pu_state.lap_id_prev = pu_state.lap_id_current
        pu_state.energy_trace_prev = list(pu_state.energy_trace)
        pu_state.runtime_warnings_prev = list(pu_state.runtime_warnings)
        pu_state.lap_deploy_prev_mj = pu_state.lap_deploy_mj
        pu_state.lap_harvest_prev_mj = pu_state.lap_harvest_mj
        pu_state.lap_id_current += 1
        pu_state.lap_deploy_mj = 0.0
        pu_state.lap_harvest_mj = 0.0
        pu_state.energy_trace = []
        pu_state.runtime_warnings = []

        # Reset section results for next lap
        ts.lap_section_results = []

        logger.debug(
            "%s lap %d: %.1fs (sections: %d)",
            car_id, ts.lap_number - 1, lap_time, len(self.sections),
        )

        if race_car and getattr(race_car, "is_player_controlled", False):
            tyre_set_id = race_car.player_config.get('tyre_set_id') if hasattr(race_car, 'player_config') else None
            live_condition = self._compute_live_tyre_condition_pct(race_car)
            if tyre_set_id and live_condition is not None:
                self._emit_driver_tyre_inventory(
                    str(car_id),
                    overrides={
                        "set_id": str(tyre_set_id),
                        "condition": round(live_condition, 2),
                    },
                )

    def _compute_sector_times(self, section_results: List[SectionResult]) -> List[float]:
        """Split section dt_s into 3 sectors using circuit sector_markers_m."""
        if not self.circuit_config or not section_results:
            return []

        markers = self.circuit_config.sector_markers_m
        if len(markers) < 2:
            # No markers: split evenly into 3
            n = len(section_results)
            third = max(n // 3, 1)
            s1 = sum(r.dt_s for r in section_results[:third])
            s2 = sum(r.dt_s for r in section_results[third:2*third])
            s3 = sum(r.dt_s for r in section_results[2*third:])
            return [s1, s2, s3]

        # Use sector markers
        sector_times = []
        current_sector = 0
        sector_dt = 0.0
        section_end_m = 0.0

        for i, result in enumerate(section_results):
            section = self.sections[i] if i < len(self.sections) else None
            section_end_m += section.length_m if section else 0
            sector_dt += result.dt_s

            if current_sector < len(markers) and section_end_m >= markers[current_sector]:
                sector_times.append(sector_dt)
                sector_dt = 0.0
                current_sector += 1

        # Last sector
        if sector_dt > 0:
            sector_times.append(sector_dt)

        return sector_times

    def _apply_section_to_racecar(self, race_car, entry, result: SectionResult, section: SectionContext) -> None:
        """Update RaceCar with per-section data (tyre, fuel, etc.)."""
        # Tyre wear (average across wheels)
        from lap_simulator.data_types import WheelPosition
        total_wear = sum(
            entry.state.tyres[wp].wear_pct
            for wp in WheelPosition
        ) / 4.0
        race_car.tire_wear = total_wear / 100.0
        race_car.current_tyre_condition_pct = max(0.0, min(100.0, 100.0 - total_wear))
        race_car.current_tyre_heat_cycles = max(
            race_car.current_tyre_heat_cycles,
            max((tyre_state.heat_cycles for tyre_state in entry.state.tyres.values()), default=0)
        )
        race_car.current_tyre_laps_completed = max(
            race_car.current_tyre_laps_completed,
            max((getattr(tyre_state, "age_laps", 0) for tyre_state in entry.state.tyres.values()), default=0)
        )

        # Tyre temps (surface + core)
        temps = {}
        core_temps = {}
        tyre_states = {}
        wp_map = {
            WheelPosition.LF: "fl", WheelPosition.RF: "fr",
            WheelPosition.LR: "rl", WheelPosition.RR: "rr",
        }
        for wp, key in wp_map.items():
            tyre_state = entry.state.tyres[wp]
            temps[key] = tyre_state.surface_temp_c
            core_temps[key] = tyre_state.core_temp_c
            tyre_states[key] = {
                "wear_pct": tyre_state.wear_pct,
                "graining": tyre_state.graining_level > 0.1,
                "blistering": tyre_state.blistering_level > 0.1,
                "surface_temp": tyre_state.surface_temp_c,
                "core_temp": tyre_state.core_temp_c,
            }
        race_car.tire_temps = temps
        race_car.tire_core_temps = core_temps
        race_car.tyre_states = tyre_states

        # Fuel
        fuel_max_kg = 110.0
        race_car.fuel_percent = max(1.0, (entry.state.pu.fuel_kg / fuel_max_kg) * 100.0)
        if hasattr(race_car, "player_config"):
            race_car.player_config["fuel_percent"] = int(round(race_car.fuel_percent))
        # Fuel penalty telemetry
        race_car.fuel_penalty_s = result.fuel_penalty_s
        if hasattr(race_car, "player_config"):
            race_car.player_config["fuel_penalty_s"] = round(result.fuel_penalty_s, 4)
        # Tyre penalty telemetry
        race_car.tyre_penalty_s = result.tyre_penalty_s
        if hasattr(race_car, "player_config"):
            race_car.player_config["tyre_penalty_s"] = round(result.tyre_penalty_s, 4)

        # Power unit / ERS telemetry block
        race_car.pu_stats = self._build_pu_stats(entry)

        # Brake diagnostics (per section + circuit profile)
        race_car.brake_diagnostics = self._build_brake_diagnostics(section)
        race_car.brake_cooling = self._build_brake_cooling(entry, race_car)
        race_car.brake_thermal = getattr(entry.state.brakes, "snapshot", None) or {}

        # Aero package data for UI
        if hasattr(entry.state, 'aero_forces') and entry.state.aero_forces:
            aero_forces = entry.state.aero_forces
            race_car.aero_balance = aero_forces.aero_balance
            # Normalize drag index relative to reference drag (typically ~30.0)
            drag_ref = getattr(aero_forces, 'drag_ref', 30.0)
            race_car.drag_index = aero_forces.drag_eff / drag_ref if drag_ref > 0 else 0.0
            race_car.cooling_margin = aero_forces.cooling_margin

    def _build_pu_stats(self, entry) -> Dict[str, Any]:
        if not self.circuit_config:
            return {}
        budget = self.circuit_config.ers_budget or {}
        maps_budget = budget.get("maps", {})
        active_map = entry.state.pu.active_map.value if entry.state.pu.active_map else "STANDARD"
        map_budget = maps_budget.get(active_map, {})
        capacity = budget.get("battery_capacity_mj", 4.0) or 4.0
        soc_mj = entry.state.pu.ers_energy_mj
        deploy_limit = budget.get("deploy_limit_mj", 4.0)
        harvest_limit = budget.get("harvest_limit_mj", 2.0)
        pu_state = entry.state.pu
        energy_trace = (pu_state.energy_trace or [])[-20:]
        energy_trace_prev = (pu_state.energy_trace_prev or [])[-20:]
        runtime_warnings = (pu_state.runtime_warnings or [])[-5:]
        runtime_warnings_prev = (pu_state.runtime_warnings_prev or [])[-5:]
        primary_pct_cfg = map_budget.get("bucket_primary_pct")
        secondary_pct_cfg = map_budget.get("bucket_secondary_pct")
        exit_pct_cfg = map_budget.get("bucket_exit_pct")
        defense_reserve_cfg = map_budget.get("defense_reserve_mj")
        deploy_budget_cfg = map_budget.get("deploy_mj_per_lap")
        mguh_direct_cfg_total = map_budget.get("mguh_direct_mj_per_lap")
        bucket_cfg = {"primary": None, "secondary": None, "exit": None}
        mguh_bucket_cfg = {"primary": None, "secondary": None, "exit": None}
        pct_sum = max(
            (primary_pct_cfg or 0.0) + (secondary_pct_cfg or 0.0) + (exit_pct_cfg or 0.0),
            1e-6,
        )
        if deploy_budget_cfg is not None and (primary_pct_cfg or secondary_pct_cfg or exit_pct_cfg):
            available_cfg = max(deploy_budget_cfg - (defense_reserve_cfg or 0.0), 0.0)
            bucket_cfg = {
                "primary": available_cfg * ((primary_pct_cfg or 0.0) / pct_sum),
                "secondary": available_cfg * ((secondary_pct_cfg or 0.0) / pct_sum),
                "exit": available_cfg * ((exit_pct_cfg or 0.0) / pct_sum),
            }
        if mguh_direct_cfg_total is not None and (primary_pct_cfg or secondary_pct_cfg or exit_pct_cfg):
            mguh_bucket_cfg = {
                "primary": mguh_direct_cfg_total * ((primary_pct_cfg or 0.0) / pct_sum),
                "secondary": mguh_direct_cfg_total * ((secondary_pct_cfg or 0.0) / pct_sum),
                "exit": mguh_direct_cfg_total * ((exit_pct_cfg or 0.0) / pct_sum),
            }

        bucket_primary_total = pu_state.bucket_primary_total_mj if pu_state.bucket_primary_total_mj > 1e-6 else (bucket_cfg["primary"] or 0.0)
        bucket_secondary_total = pu_state.bucket_secondary_total_mj if pu_state.bucket_secondary_total_mj > 1e-6 else (bucket_cfg["secondary"] or 0.0)
        bucket_exit_total = pu_state.bucket_exit_total_mj if pu_state.bucket_exit_total_mj > 1e-6 else (bucket_cfg["exit"] or 0.0)
        deploy_budget_total = pu_state.deploy_budget_total_mj if pu_state.deploy_budget_total_mj > 1e-6 else (deploy_budget_cfg or deploy_limit)
        defense_reserve_available = pu_state.defense_reserve_available_mj if pu_state.defense_reserve_available_mj > 1e-6 else (defense_reserve_cfg or 0.0)
        mguh_primary_total = pu_state.mguh_primary_total_mj if pu_state.mguh_primary_total_mj > 1e-6 else (mguh_bucket_cfg["primary"] or 0.0)
        mguh_secondary_total = pu_state.mguh_secondary_total_mj if pu_state.mguh_secondary_total_mj > 1e-6 else (mguh_bucket_cfg["secondary"] or 0.0)
        mguh_exit_total = pu_state.mguh_exit_total_mj if pu_state.mguh_exit_total_mj > 1e-6 else (mguh_bucket_cfg["exit"] or 0.0)
        mguh_direct_total = mguh_primary_total + mguh_secondary_total + mguh_exit_total
        mguh_primary_used = pu_state.mguh_primary_used_mj
        mguh_secondary_used = pu_state.mguh_secondary_used_mj
        mguh_exit_used = pu_state.mguh_exit_used_mj
        mguh_direct_used = mguh_primary_used + mguh_secondary_used + mguh_exit_used

        return {
            "map": active_map,
            "soc_mj": round(soc_mj, 3),
            "soc_pct": round((soc_mj / capacity) * 100.0, 1),
            "capacity_mj": capacity,
            "deploy_limit_mj": deploy_limit,
            "harvest_limit_mj": harvest_limit,
            "deploy_mj_per_lap": map_budget.get("deploy_mj_per_lap"),
            "harvest_mj_per_lap": map_budget.get("harvest_mj_per_lap"),
            "target_soc_end_lap": map_budget.get("target_soc_end_lap"),
            "deploy_ratio": map_budget.get("deploy_ratio"),
            "harvest_ratio": map_budget.get("harvest_ratio"),
            "bucket_primary_pct": primary_pct_cfg,
            "bucket_secondary_pct": secondary_pct_cfg,
            "bucket_exit_pct": exit_pct_cfg,
            "bucket_primary_config_mj": None if bucket_cfg["primary"] is None else round(bucket_cfg["primary"], 4),
            "bucket_secondary_config_mj": None if bucket_cfg["secondary"] is None else round(bucket_cfg["secondary"], 4),
            "bucket_exit_config_mj": None if bucket_cfg["exit"] is None else round(bucket_cfg["exit"], 4),
            "defense_reserve_mj_config": defense_reserve_cfg,
            "warnings": budget.get("warnings", []),
            "warnings_runtime": runtime_warnings,
            "warnings_runtime_prev": runtime_warnings_prev,
            "lap_deploy_mj": round(entry.state.pu.lap_deploy_mj, 3),
            "lap_harvest_mj": round(entry.state.pu.lap_harvest_mj, 3),
            "lap_mguh_direct_mj": round(entry.state.pu.lap_mguh_direct_mj, 3),
            "lap_mguh_harvest_mj": round(entry.state.pu.lap_mguh_harvest_mj, 3),
            "lap_deploy_prev_mj": round(entry.state.pu.lap_deploy_prev_mj, 3),
            "lap_harvest_prev_mj": round(entry.state.pu.lap_harvest_prev_mj, 3),
            "lap_mguh_direct_prev_mj": round(entry.state.pu.lap_mguh_direct_prev_mj, 3),
            "lap_mguh_harvest_prev_mj": round(entry.state.pu.lap_mguh_harvest_prev_mj, 3),
            "lap_id_current": entry.state.pu.lap_id_current,
            "lap_id_prev": entry.state.pu.lap_id_prev,
            "energy_trace": energy_trace,
            "energy_trace_prev": energy_trace_prev,
            "bucket_primary_total_mj": round(bucket_primary_total, 4),
            "bucket_secondary_total_mj": round(bucket_secondary_total, 4),
            "bucket_exit_total_mj": round(bucket_exit_total, 4),
            "bucket_primary_used_mj": round(pu_state.bucket_primary_used_mj, 4),
            "bucket_secondary_used_mj": round(pu_state.bucket_secondary_used_mj, 4),
            "bucket_exit_used_mj": round(pu_state.bucket_exit_used_mj, 4),
            "deploy_budget_total_mj": round(deploy_budget_total, 4),
            "defense_reserve_available_mj": round(defense_reserve_available, 4),
            "soc_floor_dynamic_pct": round(getattr(pu_state, "soc_floor_dynamic_pct", 0.0), 4),
            "soc_target_pct": round(getattr(pu_state, "soc_target_pct", 0.0), 4),
            "mguh_primary_total_mj": round(mguh_primary_total, 4),
            "mguh_secondary_total_mj": round(mguh_secondary_total, 4),
            "mguh_exit_total_mj": round(mguh_exit_total, 4),
            "mguh_primary_used_mj": round(mguh_primary_used, 4),
            "mguh_secondary_used_mj": round(mguh_secondary_used, 4),
            "mguh_exit_used_mj": round(mguh_exit_used, 4),
            "mguh_direct_total_mj": round(mguh_direct_total, 4),
            "mguh_direct_used_mj": round(mguh_direct_used, 4),
            "mguh_direct_remaining_mj": round(max(mguh_direct_total - mguh_direct_used, 0.0), 4),
            "mguh_primary_config_mj": None if mguh_bucket_cfg["primary"] is None else round(mguh_bucket_cfg["primary"], 4),
            "mguh_secondary_config_mj": None if mguh_bucket_cfg["secondary"] is None else round(mguh_bucket_cfg["secondary"], 4),
            "mguh_exit_config_mj": None if mguh_bucket_cfg["exit"] is None else round(mguh_bucket_cfg["exit"], 4),
            "mguh_direct_config_total_mj": None if mguh_direct_cfg_total is None else round(mguh_direct_cfg_total, 4),
            "last_priority_score": round(pu_state.last_priority_score, 3),
            "last_bucket_key": pu_state.last_bucket_key,
            "last_bucket_allocated_mj": round(pu_state.last_bucket_allocated_mj, 4),
            "last_defense_used_mj": round(pu_state.last_defense_used_mj, 4),
            "last_push_mode": bool(pu_state.last_push_mode),
            "last_defense_mode": bool(pu_state.last_defense_mode),
            "last_recharge_mode": bool(pu_state.last_recharge_mode),
        }

    def _build_brake_diagnostics(self, section: SectionContext) -> Dict[str, Any]:
        if not self.circuit_config:
            return {}
        profile = self.circuit_config.brake_profile or {}
        diagnostics = {
            "regen_brake_base": profile.get("regen_brake_base"),
            "regen_migration_bias": profile.get("regen_migration_bias"),
            "hydraulic_vs_regen_ratio": profile.get("hydraulic_vs_regen_ratio"),
            "cooling_targets": profile.get("cooling_targets"),
            "duct_recommendation": profile.get("duct_recommendation"),
            "brake_energy_window": profile.get("brake_energy_window"),
            "critical_sections": self.circuit_config.brake_critical_sections,
        }
        if section is not None:
            diagnostics.update(
                {
                    "current_section_id": section.section_id,
                    "current_section_name": section.name,
                    "current_braking_energy_mj": section.braking_energy_mj,
                }
            )
        return diagnostics

    def _update_brake_warning(self, race_car, event_type: str) -> None:
        axis = {
            "brake_hot_section": "front",
            "brake_duct_low": "front",
            "brake_duct_high": "front",
        }.get(event_type)
        if axis is None:
            return
        if not hasattr(race_car, "brake_cooling_warnings"):
            race_car.brake_cooling_warnings = {"front": None, "rear": None}
        race_car.brake_cooling_warnings[axis] = time.time()

    def _build_brake_cooling(self, entry, race_car) -> Dict[str, Any]:
        if not self.circuit_config:
            return {}
        profile = self.circuit_config.brake_profile or {}
        duct = profile.get("duct_recommendation") or {}
        min_open = duct.get("min_open") if isinstance(duct.get("min_open"), (int, float)) else None
        max_open = duct.get("max_open") if isinstance(duct.get("max_open"), (int, float)) else None
        warnings = getattr(race_car, "brake_cooling_warnings", {"front": None, "rear": None})

        def _status(value: Optional[float], low: Optional[float], high: Optional[float]) -> str:
            if value is None or low is None or high is None:
                return "na"
            if low <= value <= high:
                return "ok"
            pad_low = max(0.0, low - BRAKE_WARN_TOLERANCE)
            pad_high = min(1.0, high + BRAKE_WARN_TOLERANCE)
            if pad_low <= value <= pad_high:
                return "warn"
            return "bad"

        cooling = {}
        blink_until = {}
        current = getattr(entry.state.brakes, "duct_opening", None)
        for axis in ("front", "rear"):
            last_warning = warnings.get(axis)
            cooling[axis] = {
                "current_open": current,
                "min_open": min_open,
                "max_open": max_open,
                "status": _status(current, min_open, max_open),
                "last_warning_time": last_warning,
            }
            blink_until[axis] = (
                last_warning + BRAKE_WARN_BLINK_WINDOW_S if last_warning is not None else None
            )
            cooling[axis]["blink_until"] = blink_until[axis]

        return {
            "front": cooling["front"],
            "rear": cooling["rear"],
        }

    def _maybe_emit_driver_feedback(self, race_car, sector_index: int) -> None:
        if not race_car or not getattr(race_car, "is_player_controlled", False):
            return

        event_map = {
            0: ("braking_zone", "sector1"),
            1: ("sector_entry", "sector2"),
            2: ("corner_exit", "sector3"),
        }
        event = event_map.get(sector_index)
        if event is None:
            return

        event_type, sector_name = event
        if not should_trigger_feedback(race_car, event_type):
            return

        feedback = get_driver_feedback(race_car, self.circuit_profile, sector_name)
        if feedback:
            race_car.last_driver_feedback = feedback

    # ------------------------------------------------------------------
    # Player commands
    # ------------------------------------------------------------------

    def player_send_out(
        self, car, compound: str = "medium",
        fuel_percent: int = 100, stint_laps: int = 5,
    ) -> bool:
        if not self.active or self.pso is None:
            logger.warning("player_send_out: bridge not active or no PSO")
            return False

        car_id = str(car.driver_number)
        css = self.pso.cars.get(car_id)
        if css is None:
            logger.warning("player_send_out: car %s not registered in PSO", car_id)
            return False

        # Relaxed check for player: allow during YELLOW, only block on RED
        allowed_phases = (CarPhase.IN_GARAGE, CarPhase.PIT_WORK)
        if css.phase not in allowed_phases:
            logger.warning(
                "player_send_out: car %s phase=%s (need IN_GARAGE)",
                car_id, css.phase,
            )
            # Car is already queued or on track — not an error, just ignore
            return True if css.phase in (CarPhase.PIT_QUEUE, CarPhase.PIT_EXIT, CarPhase.ON_TRACK) else False
        if self.pso.clock.is_finished:
            logger.warning("player_send_out: session finished")
            return False
        if self.pso.clock.flag == SessionFlag.RED:
            logger.warning("player_send_out: RED flag active")
            return False

        # Resolve tyre set from inventory if possible, auto-reserving if needed
        active_tyre_set = None
        tyre_set_id = None
        inventory = None
        try:
            tyre_set_id = str(car.player_config.get('tyre_set_id') or '').strip()
            if self.circuit_id:
                inventory = self.tyre_inventory_service.get_inventory(car_id, self.circuit_id)
                if tyre_set_id:
                    active_tyre_set = inventory.find_set(tyre_set_id)
        except Exception as exc:
            logger.warning("player_send_out: failed to resolve tyre set %s for car %s: %s", tyre_set_id, car_id, exc)

        if (active_tyre_set is None or not active_tyre_set.is_available) and self.circuit_id:
            try:
                reserved = self.tyre_inventory_service.reserve_best_available_set(
                    driver_id=car_id,
                    circuit_id=self.circuit_id,
                    compound=compound,
                    preferred_set_id=tyre_set_id or None,
                    minimum_condition=40.0,
                )
                active_tyre_set = reserved
                car.player_config['tyre_set_id'] = reserved.set_id
                car.player_config['tyre_compound'] = reserved.compound
                compound = reserved.compound
                self._emit_driver_tyre_inventory(car_id)
                logger.info(
                    "player_send_out: auto-reserved tyre set %s (%s) for car %s",
                    reserved.set_id,
                    reserved.compound,
                    car_id,
                )
            except ValueError as exc:
                logger.warning(
                    "player_send_out: unable to auto-reserve tyres for car %s (compound=%s): %s",
                    car_id,
                    compound,
                    exc,
                )

        if active_tyre_set is None:
            logger.warning(
                "player_send_out: no valid tyre set found for car %s, compound %s",
                car_id,
                compound,
            )
        else:
            car.apply_tyre_set(active_tyre_set, preserve_temps=True)
            compound = car.player_config.get('tyre_compound', compound)
        sim_compound = game_compound_to_sim(compound)
        fuel_kg = 110.0 * (fuel_percent / 100.0)

        record = self.pso.request_run(
            car_id=car_id, program=RunProgram.SETUP_VALIDATION,
            compound=sim_compound, fuel_kg=fuel_kg, laps_planned=stint_laps,
        )
        if record is None:
            logger.warning(
                "player_send_out: PSO request_run returned None for %s "
                "(compound=%s, fuel=%.0f, laps=%d)",
                car_id, sim_compound, fuel_kg, stint_laps,
            )
            return False

        entry = racecar_to_car_entry(car)
        entry.car_id = car_id
        entry.state.car_id = car_id
        # Prime race_car telemetry with the same tyre snapshot the simulator is about to use.
        try:
            from lap_simulator.data_types import WheelPosition
            temps = {}
            core_temps = {}
            tyre_states = {}
            for wp in WheelPosition:
                tyre_state = entry.state.tyres.get(wp)
                if tyre_state is None:
                    continue
                key = wp.name.lower()
                temps[key] = tyre_state.surface_temp_c
                core_temps[key] = tyre_state.core_temp_c
                tyre_states[key] = {
                    "wear_pct": tyre_state.wear_pct,
                    "graining": tyre_state.graining_level > 0.1,
                    "blistering": tyre_state.blistering_level > 0.1,
                    "surface_temp": tyre_state.surface_temp_c,
                    "core_temp": tyre_state.core_temp_c,
                    "heat_cycles": tyre_state.heat_cycles,
                    "age_laps": tyre_state.age_laps,
                }
            car.tire_temps = temps
            car.tire_core_temps = core_temps
            car.tyre_states = tyre_states
            if active_tyre_set:
                active_tyre_set.update_runtime_snapshot(tyre_states)
        except Exception:
            pass

        # Preserve PU state from previous stint if it exists
        prev_track_state = self._track_states.get(car_id)
        if prev_track_state and prev_track_state.car_entry:
            prev_pu = prev_track_state.car_entry.state.pu
            # Copy PU state fields that should persist across stints
            entry.state.pu.lap_id_current = prev_pu.lap_id_current
            entry.state.pu.lap_id_prev = prev_pu.lap_id_prev
            entry.state.pu.lap_deploy_prev_mj = prev_pu.lap_deploy_prev_mj
            entry.state.pu.lap_harvest_prev_mj = prev_pu.lap_harvest_prev_mj
            entry.state.pu.energy_trace_prev = list(prev_pu.energy_trace_prev)
            entry.state.pu.runtime_warnings_prev = list(prev_pu.runtime_warnings_prev)
            # Also preserve battery SOC
            entry.state.pu.ers_energy_mj = prev_pu.ers_energy_mj

        self._track_states[car_id] = CarTrackState(
            car_id=car_id,
            car_entry=entry,
            laps_planned=stint_laps,
            is_player=True,
            pit_exit_delay_s=2.0,  # player gets short delay
            tyre_set_id=(active_tyre_set.set_id if active_tyre_set else (tyre_set_id or None)),
            tyre_set=active_tyre_set,
        )
        return True

    def player_box_now(self, car) -> None:
        car_id = str(car.driver_number)
        ts = self._track_states.get(car_id)
        if ts:
            ts.laps_planned = ts.laps_done_in_run

    # ------------------------------------------------------------------
    # Runtime player config propagation
    # ------------------------------------------------------------------

    def update_player_runtime_config(
        self,
        driver_number: int,
        *,
        pace_level: Optional[int] = None,
        ice_mode: Optional[str] = None,
        ers_mode: Optional[str] = None,
    ) -> None:
        """Apply runtime config changes to the live CarEntry if on track."""
        car_id = str(driver_number)
        ts = self._track_states.get(car_id)
        if not ts or not ts.is_player:
            return

        entry = ts.car_entry
        if pace_level is not None:
            new_push = max(1, min(10, int(pace_level)))
            entry.push_level = new_push
        if ice_mode:
            canonical = str(ice_mode).strip().upper()
            engine_map = ICE_MODE_TO_ENGINE_MAP.get(canonical)
            if engine_map:
                entry.state.pu.active_map = engine_map
        if ers_mode:
            canonical = ERS_MODE_CANONICAL.get(str(ers_mode).strip().upper())
            if canonical:
                entry.state.ers_mode = canonical


    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def session_time_remaining(self) -> float:
        return self.pso.clock.remaining_s if self.pso else 0.0

    @property
    def session_flag(self) -> str:
        """Current session flag state: 'green', 'yellow', or 'red'."""
        return self.pso.clock.flag.value if self.pso else "green"

    def get_car_blue_flag(self, car_id: str) -> bool:
        """Return True if the given car is under blue flag."""
        if self.pso is None:
            return False
        css = self.pso.cars.get(car_id)
        return css.blue_flag if css else False

    def get_car_phase(self, car_id: str) -> Optional[str]:
        """Expose the PracticeSessionOrchestrator phase for UI/telemetry."""
        if self.pso is None:
            return None
        css = self.pso.cars.get(car_id)
        return css.phase.value if css else None

    @property
    def is_finished(self) -> bool:
        return self.pso.is_finished if self.pso else True

    def get_leaderboard(self) -> list:
        return self.pso.leaderboard() if self.pso else []

    def get_session_summary(self) -> dict:
        return self.pso.session_summary() if self.pso else {}

    def pop_event_feed(self) -> List[Dict[str, Any]]:
        events = list(self._event_feed)
        self._event_feed.clear()
        return events

    # ------------------------------------------------------------------
    # Internal: AI scheduling
    # ------------------------------------------------------------------

    def _schedule_ai_runs(self) -> None:
        """Check TeamSessionPlans and dispatch runs whose planned_start_s has arrived."""
        if self.pso is None or self.circuit_config is None:
            return

        session_time = self._accumulated_time_s

        for plan in self._team_plans.values():
            for sr in plan.scheduled_runs:
                if sr.dispatched:
                    continue
                if session_time < sr.planned_start_s:
                    continue

                car_id = sr.car_id
                if car_id in self._track_states:
                    continue
                engine = self.ai_engines.get(car_id)
                if engine is None or not engine.has_next_run():
                    sr.dispatched = True  # skip, no more runs
                    continue
                if not self.pso.car_can_run(car_id):
                    continue

                race_car = self.race_cars_map.get(car_id)
                if race_car is None:
                    logger.warning("AI dispatch: missing RaceCar for %s", car_id)
                    continue

                try:
                    base_entry = racecar_to_car_entry(race_car)
                    base_entry.car_id = car_id
                    base_entry.state.car_id = car_id
                except Exception as exc:
                    logger.warning("AI dispatch: failed to build base entry for %s: %s", car_id, exc)
                    continue

                car_entry = engine.configure_current_run(base_entry=base_entry)
                if car_entry is None:
                    sr.dispatched = True
                    continue

                car_entry.car_id = car_id
                car_entry.state.car_id = car_id

                run_idx = engine.current_run_idx
                if run_idx >= len(engine.session_plan.runs):
                    sr.dispatched = True
                    continue
                run_plan = engine.session_plan.runs[run_idx]

                try:
                    reserved_tyre = self._reserve_ai_tyre_set(car_id, run_plan)
                except Exception as exc:
                    log_debug_event(
                        'ai_tyre_reserve_failed',
                        car_id=str(car_id),
                        circuit_id=self.circuit_id,
                        compound_requested=self._resolve_program_compound_label(run_plan),
                        error=str(exc),
                    )
                    logger.warning("AI dispatch: failed to reserve tyre set for %s: %s", car_id, exc)
                    sr.dispatched = True
                    continue

                reserved_set = reserved_tyre
                if reserved_set is None:
                    logger.warning("AI dispatch: no tyre set returned for %s", car_id)
                    sr.dispatched = True
                    continue

                reserved_set_id = reserved_set.set_id
                reserved_compound = reserved_set.compound

                # Sync RaceCar/current_tire so frontend badges mirror actual compound
                try:
                    game_compound = GameTireCompound(reserved_compound)
                    race_car.apply_tyre_set(reserved_set, compound=game_compound, preserve_temps=True)
                except Exception as exc:
                    logger.warning("AI dispatch: failed to sync tyre compound for %s: %s", car_id, exc)

                record = self.pso.request_run(
                    car_id=car_id, program=run_plan.program,
                    compound=run_plan.compound, fuel_kg=run_plan.fuel_kg,
                    laps_planned=run_plan.laps_planned,
                )

                if record is not None:
                    sr.dispatched = True
                    # Small pit exit delay (pitlane traversal)
                    pit_exit = random.uniform(2.0, 5.0)
                    car_state = CarTrackState(
                        car_id=car_id,
                        car_entry=car_entry,
                        laps_planned=run_plan.laps_planned,
                        pit_exit_delay_s=pit_exit,
                        tyre_set_id=reserved_set_id,
                        tyre_set=reserved_set,
                    )
                    self._track_states[car_id] = car_state
                    self._emit_run_started_event(
                        car_id,
                        program=run_plan.program.value,
                        laps_planned=run_plan.laps_planned,
                        fuel_load=run_plan.fuel_kg,
                        compound=getattr(run_plan.compound, "value", str(run_plan.compound)),
                        engine_map=getattr(run_plan.engine_map, "value", str(run_plan.engine_map)),
                        ers_mode=getattr(run_plan.ers_mode, "value", str(run_plan.ers_mode)),
                    )
                else:
                    # Release reserved tyre set if dispatch failed
                    if reserved_set_id and self.circuit_id:
                        try:
                            self.tyre_inventory_service.mark_availability(
                                str(car_id),
                                self.circuit_id,
                                reserved_set_id,
                                available=True,
                            )
                            log_debug_event(
                                'ai_tyre_released',
                                car_id=str(car_id),
                                circuit_id=self.circuit_id,
                                tyre_set_id=reserved_set_id,
                                reason='dispatch_failed',
                            )
                        except Exception as exc:
                            logger.warning("AI dispatch: failed to release tyre set %s for %s: %s", reserved_set_id, car_id, exc)

    # ------------------------------------------------------------------
    # Internal: complete run
    # ------------------------------------------------------------------

    def _complete_car_run(self, car_id: str) -> None:
        ts = self._track_states.pop(car_id, None)
        if ts is None:
            return

        # Clear blue flag when car returns to box
        if self.pso:
            css = self.pso.cars.get(car_id)
            if css and css.blue_flag:
                self.pso.set_blue_flag(car_id, False)

        race_car = self.race_cars_map.get(car_id)
        laps_done = getattr(ts, 'laps_done_in_run', 0) or 0
        best_lap = 0.0
        if race_car and race_car.lap_times:
            recent = race_car.lap_times[-laps_done:] if laps_done > 0 else []
            best_lap = min(recent) if recent else 0.0

        km_driven = 0.0
        if self.circuit_config:
            km_driven = self.circuit_config.circuit_length_m * laps_done / 1000.0

        if self.pso:
            self.pso.complete_run(
                car_id=car_id, laps_completed=laps_done,
                best_lap_s=best_lap, km_driven=km_driven,
                pit_work_duration_s=30.0,
            )

        final_condition_pct: Optional[float] = self._compute_live_tyre_condition_pct(race_car)

        if race_car and self.circuit_id:
            tyre_set_id = None
            active_set = getattr(ts, 'tyre_set', None)
            if active_set:
                tyre_set_id = active_set.set_id
            elif hasattr(race_car, 'current_tyre_set') and race_car.current_tyre_set:
                active_set = race_car.current_tyre_set
                tyre_set_id = active_set.set_id
            elif hasattr(race_car, 'player_config'):
                tyre_set_id = race_car.player_config.get('tyre_set_id')

            if active_set:
                try:
                    active_set.sync_from_sim_state(ts.car_entry.state.tyres)
                    active_set.laps_completed += max(0, int(laps_done))
                    active_set.heat_cycles += 1
                    if final_condition_pct is not None:
                        active_set.condition = max(0.0, min(100.0, float(final_condition_pct)))
                    active_set.is_available = active_set.condition >= 40.0
                    if active_set.is_available:
                        active_set.reset_graining_blistering()
                    inventory = self.tyre_inventory_service.get_inventory(str(car_id), self.circuit_id)
                    inventory_set = inventory.find_set(active_set.set_id)
                    if inventory_set is not active_set:
                        # Replace reference inside inventory with latest state
                        for idx, inv_set in enumerate(inventory.sets):
                            if inv_set.set_id == active_set.set_id:
                                inventory.sets[idx] = active_set
                                break
                    log_debug_event(
                        'ai_tyre_stint_completed',
                        car_id=str(car_id),
                        circuit_id=self.circuit_id,
                        tyre_set_id=str(tyre_set_id),
                        tyre_compound=getattr(race_car.current_tire, 'value', None),
                        laps_done=laps_done,
                        best_lap_s=round(best_lap, 3) if best_lap else 0.0,
                        km_driven=round(km_driven, 3),
                        condition_after=round(active_set.condition, 2),
                        heat_cycles_after=active_set.heat_cycles,
                        laps_completed_after=active_set.laps_completed,
                    )
                    overrides = {
                        "set_id": str(active_set.set_id),
                        "condition": round(active_set.condition, 2),
                        "heat_cycles": active_set.heat_cycles,
                        "laps_completed": active_set.laps_completed,
                        "runtime": active_set.get_runtime_snapshot(),
                    }
                    self._emit_driver_tyre_inventory(str(car_id), overrides=overrides)
                except Exception as exc:
                    log_debug_event(
                        'ai_tyre_stint_update_failed',
                        car_id=str(car_id),
                        circuit_id=self.circuit_id,
                        tyre_set_id=str(tyre_set_id),
                        laps_done=laps_done,
                        error=str(exc),
                    )
                    logger.warning("AI stint completion: failed to update tyre set %s for %s: %s", tyre_set_id, car_id, exc)

        # AI Setup Search: process run → adjust sliders → check convergence
        ai_ss = self._ai_setup_states.get(car_id)
        if ai_ss:
            run_plan_program = 'SETUP_VALIDATION'
            engine = self.ai_engines.get(car_id)
            if engine and engine.current_run_idx > 0:
                idx = engine.current_run_idx - 1
                if idx < len(engine.session_plan.runs):
                    run_plan_program = engine.session_plan.runs[idx].program.value
            session_name = getattr(getattr(self.pso, 'session_type', None), 'value', None) if self.pso else None
            if not session_name:
                session_name = 'FP1'
            was_complete = ai_ss.setup_complete
            result = ai_ss.process_run(session_name, run_plan_program)
            
            run_outcome = "success"
            if laps_done < max(getattr(ts, 'laps_planned', laps_done), 1):
                run_outcome = "partial"
            if best_lap <= 0.0:
                run_outcome = "aborted"

            self._emit_run_completed_event(
                car_id,
                program=result.program,
                laps_done=laps_done,
                best_lap=best_lap,
                outcome=run_outcome,
                slider_changes=result.slider_changes,
            )

            # Map AI progress to RaceCar.setup_info_percent for frontend chips
            race_car = self.race_cars_map.get(car_id)
            if race_car and not race_car.is_player_controlled:
                before_points = race_car.setup_info_points
                before_percent = race_car.setup_info_percent
                before_color = _chip_color(before_percent)

                race_car.apply_ai_progress_result(
                    slider_changes=result.slider_changes,
                    setup_complete=result.setup_complete,
                    score_before=result.score_before,
                    score_after=result.score_after,
                    score_threshold=result.threshold,
                )
                race_car.update_ai_setup_snapshot(
                    setup_snapshot=result.setup_snapshot,
                )

                after_points = race_car.setup_info_points
                after_percent = race_car.setup_info_percent
                after_color = _chip_color(after_percent)

                log_debug_event(
                    'ai_chip_run',
                    driver=race_car.driver_number,
                    car_id=car_id,
                    run_index=result.run_index,
                    session=result.session,
                    program=result.program,
                    setup_complete=result.setup_complete,
                    slider_changes=result.slider_changes,
                    points_before=round(before_points, 2),
                    points_after=round(after_points, 2),
                    percent_before=round(before_percent, 1),
                    percent_after=round(after_percent, 1),
                    color_before=before_color,
                    color_after=after_color,
                    color_changed=before_color != after_color,
                    threshold_percent={'yellow': 40, 'green': 80},
                )

            if result.slider_changes:
                self._queue_event_feed(
                    event_type="ai_setup_adjustment",
                    car_id=car_id,
                    payload={"changes": result.slider_changes, "program": result.program},
                    ui_targets=["notification_bar", "timeline"],
                )

            if result.setup_complete and not was_complete:
                targets = ["notification_bar", "timeline"]
                if race_car and race_car.is_player_controlled:
                    targets.insert(0, "hud_overlay")
                self._queue_event_feed(
                    event_type="ai_setup_converged",
                    car_id=car_id,
                    payload={
                        "threshold_reached": True,
                        "final_score": result.score_after,
                        "threshold": result.threshold,
                        "run_index": result.run_index,
                    },
                    ui_targets=targets,
                )

        # Complete in AI engine (simplified — pass empty results)
        if car_id in self.ai_engines:
            engine = self.ai_engines[car_id]
            from lap_simulator.lap_simulator import LapResult
            fake_results = [
                LapResult(car_id=car_id, lap_number=i+1, lap_time_s=t)
                for i, t in enumerate(race_car.lap_times[-laps_done:])
            ] if race_car and laps_done > 0 else []
            try:
                engine.complete_run(fake_results)
            except Exception as e:
                logger.warning("AI complete_run failed for %s: %s", car_id, e)

        if race_car:
            if race_car.is_player_controlled and hasattr(race_car, 'enter_box'):
                race_car.enter_box()
            set_racecar_phase(race_car, "box")
            race_car.stint_laps_remaining = 0
            race_car.distance_traveled = 0

    # ------------------------------------------------------------------
    # FASE 3: BattleResolver & separation
    # ------------------------------------------------------------------

    def _resolve_battles(self) -> None:
        """
        Run BattleResolver on cars sharing the same section, then enforce
        minimum gap for remaining overlaps.
        """
        self.battle_events = []

        if not self._track_states or self.circuit_config is None:
            return
        if self.pso and self.pso.clock.flag != SessionFlag.GREEN:
            # No battles under yellow/red
            return

        circuit_m = self.circuit_config.circuit_length_m
        n_sections = len(self.sections)

        # ── Group on-track cars by current section ──
        section_cars: Dict[int, List[tuple]] = {}
        for car_id, ts in self._track_states.items():
            pso_car = self.pso.cars.get(car_id) if self.pso else None
            if not pso_car or pso_car.phase != CarPhase.ON_TRACK:
                continue
            race_car = self.race_cars_map.get(car_id)
            if not race_car:
                continue
            sec_idx = ts.current_section_idx % n_sections
            section_cars.setdefault(sec_idx, []).append((car_id, ts, race_car))

        # ── Detect lapped cars (blue flag candidates) ──
        blue_flag_car_ids: List[str] = []
        blue_flag_info: Dict[str, Dict[str, Any]] = {}
        on_track_ids: set[str] = set()
        on_track_progress: List[Tuple[str, CarTrackState, float]] = []

        session_kind = getattr(self, 'session_kind', 'FP1') or 'FP1'
        session_kind = session_kind.upper()
        is_practice_session = session_kind in PRACTICE_SESSION_KINDS or session_kind.startswith('FP')
        is_race_session = session_kind in RACE_SESSION_KINDS

        for car_id, ts in self._track_states.items():
            css = self.pso.cars.get(car_id) if self.pso else None
            if css and css.phase in (CarPhase.ON_TRACK, CarPhase.PIT_ENTRY):
                total_progress = ts.lap_number * circuit_m + ts.distance_in_lap
                on_track_ids.add(car_id)
                on_track_progress.append((car_id, ts, total_progress))
            elif css and css.blue_flag:
                # Ensure any off-track car has blue flag cleared immediately
                self.pso.set_blue_flag(car_id, False)

        # Player/AI receives blue flag based on session-specific policy
        for car_id, ts, progress in on_track_progress:
            for other_id, other_ts, other_progress in on_track_progress:
                if other_id == car_id:
                    continue
                lap_diff = other_ts.lap_number - ts.lap_number
                raw_delta = other_progress - progress
                gap_forward = raw_delta if raw_delta > 0 else raw_delta + circuit_m
                css = self.pso.cars.get(car_id) if self.pso else None

                reason = None
                gap_to_use = gap_forward

                if is_practice_session:
                    defender_phase = ts.lap_phase
                    leader_phase = other_ts.lap_phase
                    same_lap_candidate = (
                        lap_diff == 0
                        and defender_phase in PRACTICE_SLOW_LAP_PHASES
                        and leader_phase == LapPhase.HOT_LAP
                        and raw_delta > 0
                    )
                    if same_lap_candidate:
                        gap_to_use = raw_delta
                        if 0 < gap_to_use <= BLUE_FLAG_PROXIMITY_THRESHOLD_M:
                            reason = 'practice_same_lap'
                        else:
                            log_debug_event(
                                'blue_flag_skip',
                                car_id=car_id,
                                leader=other_id,
                                gap_m=round(gap_to_use, 1),
                                lap_diff=lap_diff,
                                phase=str(css.phase) if css else None,
                                lap_phase=defender_phase,
                                leader_phase=leader_phase,
                                reason='gap_out_of_range',
                            )

                else:
                    if lap_diff >= 1 and is_race_session:
                        reason = 'race_lapped'
                    elif lap_diff >= 1:
                        reason = 'lapped'

                if not reason or gap_to_use <= 0 or gap_to_use > BLUE_FLAG_PROXIMITY_THRESHOLD_M:
                    if css and css.phase == CarPhase.PIT_ENTRY and lap_diff == 0:
                        log_debug_event(
                            'blue_flag_skip',
                            car_id=car_id,
                            leader=other_id,
                            gap_m=round(gap_to_use, 1),
                            lap_diff=lap_diff,
                            phase=str(css.phase),
                            reason='gap_out_of_range' if gap_to_use <= 0 or gap_to_use > BLUE_FLAG_PROXIMITY_THRESHOLD_M else 'unknown',
                        )
                    continue

                if 0 < gap_to_use <= BLUE_FLAG_PROXIMITY_THRESHOLD_M:
                    blue_flag_car_ids.append(car_id)
                    prev_gap = blue_flag_info.get(car_id, {}).get('gap_m', None)
                    if prev_gap is None or gap_to_use < prev_gap:
                        blue_flag_info[car_id] = {
                            'leader': other_id,
                            'lap_diff': lap_diff,
                            'gap_m': round(gap_to_use, 1),
                            'car_lap': ts.lap_number,
                            'leader_lap': other_ts.lap_number,
                            'reason': reason,
                        }
                    break

        # Update PSO blue flags (only cars currently on track can receive blue flags)
        if self.pso:
            for car_id in on_track_ids:
                is_blue = car_id in blue_flag_car_ids
                css = self.pso.cars.get(car_id)
                if css and css.blue_flag != is_blue:
                    info = blue_flag_info.get(car_id, {})
                    log_debug_event(
                        'blue_flag_set',
                        car_id=car_id,
                        is_blue=is_blue,
                        lap=css.lap_number if hasattr(css, 'lap_number') else getattr(self._track_states.get(car_id), 'lap_number', None),
                        phase=str(css.phase),
                        leader=info.get('leader'),
                        lap_diff=info.get('lap_diff'),
                        gap_m=info.get('gap_m'),
                        leader_lap=info.get('leader_lap'),
                        car_lap=info.get('car_lap'),
                        reason=info.get('reason'),
                    )
                    self.pso.set_blue_flag(car_id, is_blue)

        # ── Resolve battles per section ──
        for sec_idx, cars_list in section_cars.items():
            if len(cars_list) < 2:
                continue

            section = self.sections[sec_idx]

            # Sort by distance (leader first = furthest along in section)
            cars_list.sort(key=lambda x: x[1].distance_in_lap, reverse=True)

            # Build input: (car_id, gap_to_ahead_m, v_effective_kph)
            cars_in_section = []
            for i, (car_id, ts, race_car) in enumerate(cars_list):
                if i == 0:
                    gap = 0.0
                else:
                    leader_dist = cars_list[i - 1][1].distance_in_lap
                    gap = abs(leader_dist - ts.distance_in_lap)
                    if gap > circuit_m / 2:
                        gap = circuit_m - gap

                v_kph = race_car.speed * 3.6 if race_car.speed else 200.0
                cars_in_section.append((car_id, gap, v_kph))

            # Build car_entries and section_results dicts
            car_entries = {}
            section_results = {}
            for car_id, ts, _ in cars_list:
                car_entries[car_id] = ts.car_entry
                # Use last section result if available, else create a minimal one
                if ts.lap_section_results:
                    section_results[car_id] = ts.lap_section_results[-1]
                else:
                    section_results[car_id] = SectionResult(
                        dt_s=section.dt_ref_s if section.dt_ref_s > 0 else 3.0,
                        v_exit_kph=200.0,
                    )

            result: BattleResult = self.battle_resolver.resolve_section(
                cars_in_section=cars_in_section,
                section=section,
                car_entries=car_entries,
                section_results=section_results,
                blue_flag_cars=blue_flag_car_ids,
            )

            # ── Apply outcomes ──
            # Overtakes: NO distance manipulation — let the faster car
            # naturally overtake over subsequent ticks (visual overlap is OK).
            # Only BLOCKED and COLLISION have physical effects.
            for pair in result.pairs:
                if pair.outcome == BattleOutcome.OVERTAKE_SUCCESS:
                    # Event-only: the attacker is already faster and will
                    # pass the defender naturally in the next ticks.
                    self._battle_cooldown.add(pair.attacker_id)
                    self._battle_cooldown.add(pair.defender_id)

                elif pair.outcome == BattleOutcome.BLOCKED:
                    # Small time penalty: attacker loses ~1m
                    ts_att = self._track_states.get(pair.attacker_id)
                    rc_att = self.race_cars_map.get(pair.attacker_id)
                    if ts_att and rc_att:
                        ts_att.distance_in_lap = max(0, ts_att.distance_in_lap - 1.0)
                        rc_att.distance_traveled = max(0, rc_att.distance_traveled - 1.0)
                    self._battle_cooldown.add(pair.attacker_id)

                elif pair.outcome == BattleOutcome.COLLISION:
                    # Trigger yellow flag (red for severe — future: check damage)
                    if self.pso:
                        self.pso.set_session_flag(SessionFlag.YELLOW)
                    logger.warning(
                        "COLLISION: %s vs %s in section %s",
                        pair.attacker_id, pair.defender_id, section.section_id,
                    )
                    self._battle_cooldown.add(pair.attacker_id)
                    self._battle_cooldown.add(pair.defender_id)

            # Store events
            self.battle_events.extend(result.events)
            self._queue_battle_events(result.events)

        # Cooldown no longer needed (no gap enforcement)
        self._battle_cooldown.clear()

    # ------------------------------------------------------------------
    # Internal: event feed helpers
    # ------------------------------------------------------------------

    def _emit_run_started_event(
        self,
        car_id: str,
        *,
        program: str,
        laps_planned: int,
        fuel_load: float,
        compound: str,
        engine_map: Optional[str] = None,
        ers_mode: Optional[str] = None,
    ) -> None:
        payload = {
            "program": program,
            "laps_planned": laps_planned,
            "fuel_load": round(fuel_load, 1),
            "compound": compound,
            "engine_map": engine_map,
            "ers_mode": ers_mode,
        }
        self._queue_event_feed(
            "ai_run_started",
            car_id=car_id,
            payload=payload,
            ui_targets=["notification_bar", "timeline"],
        )

    def _emit_run_completed_event(
        self,
        car_id: str,
        *,
        program: str,
        laps_done: int,
        best_lap: float,
        outcome: str,
        slider_changes: Dict[str, float],
    ) -> None:
        payload = {
            "program": program,
            "laps_done": laps_done,
            "best_lap_s": round(best_lap, 3) if best_lap else 0.0,
            "outcome": outcome,
            "delta_setup": slider_changes,
        }
        self._queue_event_feed(
            "ai_run_completed",
            car_id=car_id,
            payload=payload,
            ui_targets=["notification_bar", "timeline"],
        )

    def _queue_battle_events(self, events: List[BattleEvent]) -> None:
        if not events:
            return
        for ev in events:
            attacker = self.race_cars_map.get(ev.attacker_id)
            defender = self.race_cars_map.get(ev.defender_id)
            player_involved = (
                (attacker and attacker.is_player_controlled)
                or (defender and defender.is_player_controlled)
            )
            if not player_involved:
                continue
            focus_car = attacker if attacker and attacker.is_player_controlled else defender
            focus_id = str(getattr(focus_car, "driver_number", ev.attacker_id)) if focus_car else ev.attacker_id
            payload = {
                "attacker_id": ev.attacker_id,
                "attacker_name": attacker.driver_name if attacker else "",
                "defender_id": ev.defender_id,
                "defender_name": defender.driver_name if defender else "",
                "section": ev.section_id,
                "scenario": ev.scenario,
                "outcome": ev.outcome,
                "message": ev.message,
                "delta_v_kph": ev.delta_v_kph,
                "gap_m": ev.gap_m,
                "attack_chance": ev.attack_chance,
            }
            targets = ["hud_overlay", "timeline"]
            if ev.event_type.endswith("collision"):
                targets.insert(0, "notification_bar")
            self._queue_event_feed(
                event_type=ev.event_type,
                car_id=str(focus_id),
                payload=payload,
                ui_targets=targets,
                driver_name=focus_car.driver_name if focus_car else None,
                team_name=focus_car.team_name if focus_car else None,
            )

    def _queue_event_feed(
        self,
        event_type: str,
        *,
        car_id: str,
        payload: Dict[str, Any],
        ui_targets: Optional[List[str]] = None,
        driver_name: Optional[str] = None,
        team_name: Optional[str] = None,
    ) -> None:
        race_car = self.race_cars_map.get(str(car_id))
        if race_car:
            driver_name = driver_name or race_car.driver_name
            team_name = team_name or race_car.team_name
        targets: List[str]
        if ui_targets is not None:
            targets = ui_targets
        else:
            targets = ["timeline"]
            if race_car and race_car.is_player_controlled:
                targets.insert(0, "notification_bar")
        event = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": self.session_kind,
            "car_id": str(car_id),
            "team_name": team_name,
            "driver_name": driver_name,
            "payload": payload,
            "ui_targets": targets,
        }
        self._event_feed.append(event)

    def _enforce_min_gap(self) -> None:
        """Push overlapping cars apart (safety net after battle resolution)."""
        if not self._track_states or self.circuit_config is None:
            return

        circuit_m = self.circuit_config.circuit_length_m

        on_track = []
        for car_id, ts in self._track_states.items():
            race_car = self.race_cars_map.get(car_id)
            if race_car and race_car.distance_traveled > 0:
                on_track.append((car_id, race_car.distance_traveled, ts))

        if len(on_track) < 2:
            return

        on_track.sort(key=lambda x: x[1])

        for i in range(1, len(on_track)):
            car_id_ahead, dist_ahead, _ = on_track[i - 1]
            car_id_behind, dist_behind, ts_behind = on_track[i]

            # Skip cars recently involved in battle resolution
            if car_id_behind in self._battle_cooldown or car_id_ahead in self._battle_cooldown:
                continue

            gap = dist_behind - dist_ahead
            if gap < 0:
                gap += circuit_m

            if gap < MIN_CAR_GAP_M:
                race_car = self.race_cars_map.get(car_id_behind)
                if race_car:
                    new_dist = dist_ahead - MIN_CAR_GAP_M
                    if new_dist < 0:
                        new_dist += circuit_m
                    race_car.distance_traveled = new_dist
                    ts_behind.distance_in_lap = new_dist

    # ------------------------------------------------------------------
    # Internal: sync phases
    # ------------------------------------------------------------------

    def _sync_phases(self) -> None:
        if self.pso is None:
            return
        for car_id, pso_car in self.pso.cars.items():
            race_car = self.race_cars_map.get(car_id)
            if race_car is None:
                continue
            if pso_car.phase != CarPhase.ON_TRACK:
                set_racecar_phase(race_car, pso_car.phase.value)
                continue
            if car_id not in self._track_states:
                set_racecar_phase(race_car, pso_car.phase.value)

    def _finish_session(self) -> None:
        for car_id in list(self._track_states.keys()):
            self._complete_car_run(car_id)
        for car_id, race_car in self.race_cars_map.items():
            set_racecar_phase(race_car, "box")
        if self._ai_report_enabled:
            self._generate_ai_setup_report()
        self.active = False
        logger.info("Session finished. Runs: %d", len(self.pso.run_log) if self.pso else 0)

    def _generate_ai_setup_report(self) -> None:
        if not self.ai_engines:
            return
        rows: List[str] = []
        rows.append("<table class=\"setup-report\">")
        rows.append(
            "<thead><tr><th>Team</th><th>Pilota</th><th>Runs (done/req)</th><th>Score (cur/target)</th><th>Best Lap (s)</th><th>Setup Chip</th><th>Status</th><th>Programs</th></tr></thead>"
        )
        rows.append("<tbody>")

        for car_id, engine in sorted(self.ai_engines.items()):
            summary = engine.session_summary()
            race_car = self.race_cars_map.get(car_id)
            state = self._ai_setup_states.get(car_id)
            score = state.setup_score if state else 0.0
            threshold = state.threshold if state else 0.0
            runs_done = state.total_runs if state else summary["runs_completed"]
            runs_req = getattr(state, "min_runs_required", summary["runs_planned"])
            score_label = f"{score:.2f}/{threshold:.2f}" if threshold > 0 else "–"
            raw_percent = 0.0
            if threshold > 0:
                raw_percent = max(0.0, min(100.0, (score / threshold) * 100.0))
            progress_factor = 1.0
            if runs_req > 0:
                progress_factor = min(1.0, runs_done / runs_req)
            percent = raw_percent * progress_factor
            is_ready = bool(state and state.setup_complete)
            if not is_ready:
                percent = min(percent, 90.0)
            chip_class = _chip_color(percent)
            chip_label = f"{percent:.0f}%"
            programs = ", ".join(run.program.value for run in engine.session_plan.runs) if engine.session_plan else ""
            status_label = "Ready" if is_ready else "Collecting"
            runs_label = f"{runs_done}/{runs_req}"
            rows.append(
                "<tr>"
                f"<td>{engine.team_config.team_id}</td>"
                f"<td>{engine.driver_config.driver_id}</td>"
                f"<td>{runs_label}</td>"
                f"<td>{score_label}</td>"
                f"<td>{summary['best_lap_s']:.3f}</td>"
                f"<td class=\"chip {chip_class}\">{chip_label}</td>"
                f"<td>{status_label}</td>"
                f"<td>{programs}</td>"
                "</tr>"
            )

        rows.append("</tbody></table>")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        session = getattr(self.pso, "session_type", None)
        session_name = session.value if session else "FP"
        report_dir = Path("tmp")
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"ai_setup_report_{session_name}_{timestamp}.html"
        html = [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head>",
            "<meta charset=\"utf-8\" />",
            f"<title>AI Setup Report – {session_name}</title>",
            "<style>",
            "body{background:#05060a;color:#f4f5ff;font-family:'Inter','Roboto','Helvetica Neue',sans-serif;padding:32px;}",
            "h1{margin-top:0;font-size:24px;color:#ffffff;}",
            "p{color:#c5c8ff;font-size:13px;margin-bottom:16px;}",
            ".setup-report{width:100%;border-collapse:collapse;font-family:'Roboto Mono','SFMono-Regular',Consolas,monospace;font-size:13px;table-layout:fixed;color:#f4f5ff;}",
            ".setup-report th,.setup-report td{border:1px solid #262a40;padding:8px 10px;vertical-align:top;background:#0c0f1a;}",
            ".setup-report thead th{background:#12162a;color:#fdfdfd;}",
            ".setup-report tbody tr:nth-child(odd) td{background:#0e1222;}",
            ".setup-report tbody tr:nth-child(even) td{background:#0c0f1a;}",
            ".setup-report .chip{font-weight:600;text-align:center;border-radius:999px;padding:4px 10px;display:inline-block;min-width:64px;}",
            ".setup-report .chip.red{background:#39121d;color:#ff7a7a;}",
            ".setup-report .chip.yellow{background:#3c2a11;color:#ffd166;}",
            ".setup-report .chip.green{background:#1c3725;color:#6fffb0;}",
            ".setup-report .chip.ready{background:#15373b;color:#80ffeb;}",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>AI Setup Report – {session_name}</h1>",
            f"<p>Generato: {datetime.utcnow().isoformat()} UTC</p>",
            *rows,
            "</body></html>",
        ]
        report_path.write_text("\n".join(html), encoding="utf-8")
        logger.info("AI setup report written to %s", report_path)
