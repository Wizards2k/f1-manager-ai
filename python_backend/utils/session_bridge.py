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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from lap_simulator.ai_data_types import (
    AIDriverConfig,
    AITeamConfig,
    RunProgram,
    SessionType,
)
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
)
from lap_simulator.update_section import update_section
from lap_simulator.practice_session import (
    CarPhase,
    PracticeEventType,
    PracticeSessionOrchestrator,
)

from utils.adapter import (
    game_compound_to_sim,
    pilot_to_driver_skills,
    racecar_to_car_entry,
    set_racecar_phase,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_DURATION_S = 3600
AI_RUN_INTERVAL_S = 30
OUT_LAP_SPEED_FACTOR = 0.65     # out lap ~65% of reference speed
IN_LAP_SPEED_FACTOR = 0.70      # in lap ~70% of reference speed
SLOW_LAP_SPEED_FACTOR = 0.75    # slow/cooldown lap
MIN_CAR_GAP_M = 40.0            # minimum gap between cars on track (metres)


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


# ---------------------------------------------------------------------------
# Team tier mapping
# ---------------------------------------------------------------------------

_TEAM_TIERS = {
    "Ferrari": "top", "Red Bull Racing": "top", "McLaren": "top",
    "Mercedes": "top", "Aston Martin": "midfield", "Alpine": "midfield",
    "Williams": "midfield", "RB": "midfield",
    "Kick Sauber": "backmarker", "Haas": "backmarker",
}


def _get_team_tier(team_name: str) -> str:
    return _TEAM_TIERS.get(team_name, "midfield")


# ---------------------------------------------------------------------------
# Session Bridge
# ---------------------------------------------------------------------------

class SessionBridge:
    """
    Bridges the new LapSimulator engine with the existing game backend.

    Uses a per-section tick loop: every tick, each on-track car accumulates
    sim_dt in its current section. When the accumulated time reaches dt_ref_s,
    update_section() is called to compute the physics for that section.
    """

    def __init__(self):
        self.active = False
        self.circuit_config: Optional[CircuitConfig] = None
        self.sections: List[SectionContext] = []
        self.env = EnvContext()
        self.pso: Optional[PracticeSessionOrchestrator] = None
        self.ai_engines: Dict[str, AIDriverEngine] = {}
        self.race_cars_map: Dict[str, Any] = {}
        self._track_states: Dict[str, CarTrackState] = {}
        self._ai_last_check_s: float = 0.0
        self._accumulated_time_s: float = 0.0
        self._stagger_counter: int = 0  # increments per car scheduled, for stagger

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def init_session(
        self,
        circuit_id: str,
        race_cars: list,
        session_type: str = "FP1",
    ) -> bool:
        try:
            self.circuit_config = load_circuit_config(circuit_id)
        except Exception as e:
            logger.error("Failed to load circuit config for %s: %s", circuit_id, e)
            return False

        self.sections = self.circuit_config.sections
        if not self.sections:
            logger.error("No sections in circuit config for %s", circuit_id)
            return False

        st = SessionType(session_type)
        self.pso = PracticeSessionOrchestrator(st, duration_s=SESSION_DURATION_S)

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
            player_car_id = None
            for c in cars:
                if c.is_player_controlled:
                    player_car_id = str(c.driver_number)

            self.pso.register_team(
                team_id=team_name, car_ids=car_ids,
                driver_names=driver_names, player_car_id=player_car_id,
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

        self.pso.start_session()
        self.active = True
        self._accumulated_time_s = 0.0
        self._ai_last_check_s = 0.0
        self._track_states = {}

        logger.info(
            "SessionBridge v2 initialized: %s on %s (%d cars, %d AI, %d sections)",
            session_type, circuit_id, len(race_cars),
            len(self.ai_engines), len(self.sections),
        )
        return True

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
        if self._accumulated_time_s - self._ai_last_check_s >= AI_RUN_INTERVAL_S:
            self._schedule_ai_runs()
            self._ai_last_check_s = self._accumulated_time_s

        self.pso.tick(sim_dt)

        if self.pso.is_finished:
            self._finish_session()
            return

        # ── FASE 2: MOVE CARS (per-section) ──
        self._move_cars(sim_dt)

        # ── FASE 3: SEPARATION / BATTLE ──
        self._enforce_separation()

        # ── FASE 4: STATE COMMIT ──
        self._sync_phases()

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
            section_start_m = sum(
                s.length_m for s in self.sections[:ts.current_section_idx]
            )
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
                    )
                except Exception as e:
                    logger.error("update_section error for %s: %s", car_id, e)
                    result = SectionResult(dt_s=dt_ref, v_exit_kph=speed_kph)

                ts.lap_section_results.append(result)

                # Update RaceCar with section data
                self._apply_section_to_racecar(race_car, entry, result)

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

                    # Update lap phase for next lap
                    if ts.laps_done_in_run >= ts.laps_planned:
                        completed_runs.append(car_id)
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

        # Best lap
        if not hasattr(race_car, "best_lap_time") or lap_time < getattr(race_car, "best_lap_time", float("inf")):
            race_car.best_lap_time = lap_time

        # Sector times (split section results by sector markers)
        sector_times = self._compute_sector_times(ts.lap_section_results)
        if len(sector_times) >= 3:
            race_car.current_lap_sectors = {
                "sector1": sector_times[0],
                "sector2": sector_times[1],
                "sector3": sector_times[2],
            }
            race_car.last_sector_times = dict(race_car.current_lap_sectors)
            for key, val in race_car.current_lap_sectors.items():
                best = race_car.best_sectors.get(key)
                if best is None or val < best:
                    race_car.best_sectors[key] = val
            if lap_time <= getattr(race_car, "best_lap_time", float("inf")):
                race_car.best_lap_sectors = dict(race_car.current_lap_sectors)

        race_car.last_lap_type = GameCarState.HOT_LAP
        race_car.distance_traveled = 0

        # Update session bests (for timing panel colors)
        update_session_bests(race_car)

        # Reset section results for next lap
        ts.lap_section_results = []

        logger.debug(
            "%s lap %d: %.1fs (sections: %d)",
            car_id, ts.lap_number - 1, lap_time, len(self.sections),
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

    def _apply_section_to_racecar(self, race_car, entry, result: SectionResult) -> None:
        """Update RaceCar with per-section data (tyre, fuel, etc.)."""
        # Tyre wear (average across wheels)
        from lap_simulator.data_types import WheelPosition
        total_wear = sum(
            entry.state.tyres[wp].wear_pct
            for wp in WheelPosition
        ) / 4.0
        race_car.tire_wear = total_wear / 100.0

        # Tyre temps
        temps = {}
        wp_map = {
            WheelPosition.LF: "fl", WheelPosition.RF: "fr",
            WheelPosition.LR: "rl", WheelPosition.RR: "rr",
        }
        for wp, key in wp_map.items():
            temps[key] = entry.state.tyres[wp].surface_temp_c
        race_car.tire_temps = temps

        # Fuel
        fuel_max_kg = 110.0
        race_car.fuel_percent = max(1.0, (entry.state.pu.fuel_kg / fuel_max_kg) * 100.0)
        if hasattr(race_car, "player_config"):
            race_car.player_config["fuel_percent"] = int(round(race_car.fuel_percent))

    # ------------------------------------------------------------------
    # Player commands
    # ------------------------------------------------------------------

    def player_send_out(
        self, car, compound: str = "medium",
        fuel_percent: int = 100, stint_laps: int = 5,
    ) -> bool:
        if not self.active or self.pso is None:
            return False

        car_id = str(car.driver_number)
        if not self.pso.car_can_run(car_id):
            return False

        sim_compound = game_compound_to_sim(compound)
        fuel_kg = 110.0 * (fuel_percent / 100.0)

        record = self.pso.request_run(
            car_id=car_id, program=RunProgram.SETUP_VALIDATION,
            compound=sim_compound, fuel_kg=fuel_kg, laps_planned=stint_laps,
        )
        if record is None:
            return False

        entry = racecar_to_car_entry(car)
        entry.car_id = car_id
        entry.state.car_id = car_id

        self._track_states[car_id] = CarTrackState(
            car_id=car_id, car_entry=entry,
            laps_planned=stint_laps, is_player=True,
            pit_exit_delay_s=2.0,  # player gets short delay
        )
        return True

    def player_box_now(self, car) -> None:
        car_id = str(car.driver_number)
        ts = self._track_states.get(car_id)
        if ts:
            ts.laps_planned = ts.laps_done_in_run

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def session_time_remaining(self) -> float:
        return self.pso.clock.remaining_s if self.pso else 0.0

    @property
    def is_finished(self) -> bool:
        return self.pso.is_finished if self.pso else True

    def get_leaderboard(self) -> list:
        return self.pso.leaderboard() if self.pso else []

    def get_session_summary(self) -> dict:
        return self.pso.session_summary() if self.pso else {}

    # ------------------------------------------------------------------
    # Internal: AI scheduling
    # ------------------------------------------------------------------

    def _schedule_ai_runs(self) -> None:
        if self.pso is None or self.circuit_config is None:
            return

        self._stagger_counter = 0  # reset per scheduling batch

        for car_id, engine in self.ai_engines.items():
            if car_id in self._track_states:
                continue
            if not self.pso.car_can_run(car_id):
                continue
            if not engine.has_next_run():
                continue

            car_entry = engine.configure_current_run()
            if car_entry is None:
                continue

            car_entry.car_id = car_id
            car_entry.state.car_id = car_id

            run_idx = engine.current_run_idx
            if run_idx >= len(engine.session_plan.runs):
                continue
            run_plan = engine.session_plan.runs[run_idx]

            record = self.pso.request_run(
                car_id=car_id, program=run_plan.program,
                compound=run_plan.compound, fuel_kg=run_plan.fuel_kg,
                laps_planned=run_plan.laps_planned,
            )

            if record is not None:
                # Stagger delay: 3-8s base + 5s per car in this batch
                stagger = 3.0 + self._stagger_counter * 5.0 + random.uniform(0, 3.0)
                self._stagger_counter += 1
                self._track_states[car_id] = CarTrackState(
                    car_id=car_id, car_entry=car_entry,
                    laps_planned=run_plan.laps_planned,
                    pit_exit_delay_s=stagger,
                )
                logger.debug("AI %s: starting %s run (stagger %.1fs)", car_id, run_plan.program.value, stagger)

    # ------------------------------------------------------------------
    # Internal: complete run
    # ------------------------------------------------------------------

    def _complete_car_run(self, car_id: str) -> None:
        ts = self._track_states.pop(car_id, None)
        if ts is None:
            return

        race_car = self.race_cars_map.get(car_id)
        laps_done = ts.laps_done_in_run
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
            set_racecar_phase(race_car, "box")
            race_car.stint_laps_remaining = 0
            race_car.distance_traveled = 0

    # ------------------------------------------------------------------
    # FASE 3: Separation & proximity
    # ------------------------------------------------------------------

    def _enforce_separation(self) -> None:
        """Prevent cars from overlapping on track by enforcing minimum gap."""
        if not self._track_states or self.circuit_config is None:
            return

        circuit_m = self.circuit_config.circuit_length_m

        # Build sorted list of on-track cars by distance
        on_track = []
        for car_id, ts in self._track_states.items():
            race_car = self.race_cars_map.get(car_id)
            if race_car and race_car.distance_traveled > 0:
                on_track.append((car_id, race_car.distance_traveled, ts))

        if len(on_track) < 2:
            return

        on_track.sort(key=lambda x: x[1])

        # Enforce minimum gap: if car behind is too close, slow it down
        for i in range(1, len(on_track)):
            _, dist_ahead, _ = on_track[i - 1]
            car_id_behind, dist_behind, ts_behind = on_track[i]

            gap = dist_behind - dist_ahead
            # Handle wrap-around
            if gap < 0:
                gap += circuit_m

            if gap < MIN_CAR_GAP_M:
                # Push the car behind back slightly
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
            if car_id not in self._track_states:
                set_racecar_phase(race_car, pso_car.phase.value)

    def _finish_session(self) -> None:
        for car_id in list(self._track_states.keys()):
            self._complete_car_run(car_id)
        for car_id, race_car in self.race_cars_map.items():
            set_racecar_phase(race_car, "box")
        self.active = False
        logger.info("Session finished. Runs: %d", len(self.pso.run_log) if self.pso else 0)
