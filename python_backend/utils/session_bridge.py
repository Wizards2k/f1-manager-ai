"""
Session Bridge – connects the new LapSimulator engine to the existing game loop.

Wraps PracticeSessionOrchestrator + LapSimulator + AIDriverEngine + BattleResolver
into a single interface that game_logic.py and f1_manager_ai.py can call.

Fase C: Race Engine Integration
"""
from __future__ import annotations

import logging
import random
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
    CircuitConfig,
    EnvContext,
    TyreCompound,
)
from lap_simulator.lap_simulator import CarEntry, LapResult, LapSimulator
from lap_simulator.practice_session import (
    CarPhase,
    PracticeEventType,
    PracticeSessionOrchestrator,
    SessionFlag,
)

from utils.adapter import (
    apply_lap_result_to_racecar,
    game_compound_to_sim,
    pilot_to_driver_skills,
    racecar_to_car_entry,
    set_racecar_phase,
    sim_compound_to_game,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_DURATION_S = 3600  # 60 min
AI_RUN_INTERVAL_S = 30     # AI checks for new run every 30s sim time
LAP_TIME_ESTIMATE_S = 100  # rough estimate for scheduling
OUT_LAP_FACTOR = 1.15      # out lap is ~15% slower


# ---------------------------------------------------------------------------
# Team tier mapping (from game team data)
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

    Usage:
        bridge = SessionBridge()
        bridge.init_session(circuit_id, race_cars, session_type="FP1")
        # In the game loop:
        bridge.tick(dt)  # advances simulation
        # bridge populates race_cars in-place
    """

    def __init__(self):
        self.active = False
        self.circuit_config: Optional[CircuitConfig] = None
        self.env = EnvContext()
        self.pso: Optional[PracticeSessionOrchestrator] = None
        self.sim: Optional[LapSimulator] = None
        self.ai_engines: Dict[str, AIDriverEngine] = {}
        self.race_cars_map: Dict[str, Any] = {}  # car_id → RaceCar
        self.car_entries: Dict[str, CarEntry] = {}
        self._ai_last_check_s: float = 0.0
        self._cars_on_track: Dict[str, dict] = {}  # car_id → {laps_done, laps_planned, entry}
        self._accumulated_time_s: float = 0.0
        self._lap_progress: Dict[str, dict] = {}  # car_id → {start_time, est_lap_s, circuit_m}

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def init_session(
        self,
        circuit_id: str,
        race_cars: list,
        session_type: str = "FP1",
    ) -> bool:
        """
        Initialize a new practice session with the LapSimulator engine.

        Args:
            circuit_id: Circuit identifier (e.g. "it-1922_monza").
            race_cars: List of game RaceCar objects.
            session_type: "FP1", "FP2", or "FP3".

        Returns True if initialization succeeded.
        """
        try:
            self.circuit_config = load_circuit_config(circuit_id)
        except Exception as e:
            logger.error("Failed to load circuit config for %s: %s", circuit_id, e)
            return False

        st = SessionType(session_type)

        # Create PSO
        self.pso = PracticeSessionOrchestrator(st, duration_s=SESSION_DURATION_S)

        # Group cars by team
        teams: Dict[str, List] = {}
        for car in race_cars:
            team_name = car.team_name
            teams.setdefault(team_name, []).append(car)

        # Register teams and create AI engines
        self.ai_engines = {}
        self.race_cars_map = {}

        # Default tyre allocation per team
        alloc = {
            TyreCompound.C2: 2,
            TyreCompound.C3: 3,
            TyreCompound.C4: 3,
            TyreCompound.C5: 8,
            TyreCompound.INTERMEDIATE: 4,
            TyreCompound.WET: 3,
        }

        for team_name, cars in teams.items():
            car_ids = [str(c.driver_number) for c in cars]
            driver_names = [c.driver_name for c in cars]
            player_car_id = None
            for c in cars:
                if c.is_player_controlled:
                    player_car_id = str(c.driver_number)

            self.pso.register_team(
                team_id=team_name,
                car_ids=car_ids,
                driver_names=driver_names,
                player_car_id=player_car_id,
                allocation=alloc,
            )

            # Create AI engines for non-player cars
            tier = _get_team_tier(team_name)
            team_cfg = AITeamConfig(
                team_id=team_name,
                budget_tier=tier,
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
                        self.circuit_config, team_cfg, driver_cfg, skills
                    )
                    engine.start_session(st)
                    self.ai_engines[car_id] = engine

        # Create LapSimulator with battles
        self.sim = LapSimulator(self.circuit_config, self.env, enable_battles=True)

        # Start PSO
        self.pso.start_session()
        self.active = True
        self._accumulated_time_s = 0.0
        self._ai_last_check_s = 0.0
        self._cars_on_track = {}

        logger.info(
            "SessionBridge initialized: %s on %s (%d cars, %d AI)",
            session_type, circuit_id, len(race_cars), len(self.ai_engines),
        )
        return True

    # ------------------------------------------------------------------
    # Tick (called from game loop)
    # ------------------------------------------------------------------

    def tick(self, dt: float) -> None:
        """
        Advance the session by dt seconds (real time, scaled by game speed).

        This is called from the main game loop instead of update_car_position().
        """
        if not self.active or self.pso is None:
            return

        self._accumulated_time_s += dt

        # 1. Schedule AI runs (puts cars in PIT_QUEUE)
        if self._accumulated_time_s - self._ai_last_check_s >= AI_RUN_INTERVAL_S:
            self._schedule_ai_runs()
            self._ai_last_check_s = self._accumulated_time_s

        # 2. Advance PSO clock (releases cars from PIT_QUEUE → ON_TRACK)
        self.pso.tick(dt)

        if self.pso.is_finished:
            self._finish_session()
            return

        # 3. Process cars on track: simulate laps
        self._process_on_track_cars()

        # 4. Interpolate car positions for smooth map movement
        self._interpolate_positions(dt)

        # 5. Sync phases back to RaceCar objects
        self._sync_phases()

    # ------------------------------------------------------------------
    # Player commands
    # ------------------------------------------------------------------

    def player_send_out(
        self,
        car,
        compound: str = "medium",
        fuel_percent: int = 100,
        stint_laps: int = 5,
    ) -> bool:
        """
        Send a player car out on track.

        Returns True if the car was successfully queued.
        """
        if not self.active or self.pso is None:
            return False

        car_id = str(car.driver_number)
        if not self.pso.car_can_run(car_id):
            return False

        sim_compound = game_compound_to_sim(compound)
        fuel_kg = 110.0 * (fuel_percent / 100.0)

        record = self.pso.request_run(
            car_id=car_id,
            program=RunProgram.SETUP_VALIDATION,  # player runs are generic
            compound=sim_compound,
            fuel_kg=fuel_kg,
            laps_planned=stint_laps,
        )

        if record is None:
            return False

        # Create CarEntry for LapSimulator
        entry = racecar_to_car_entry(car)
        entry.car_id = car_id
        entry.state.car_id = car_id
        self.car_entries[car_id] = entry
        self._cars_on_track[car_id] = {
            "laps_done": 0,
            "laps_planned": stint_laps,
            "entry": entry,
            "is_player": True,
        }

        return True

    def player_box_now(self, car) -> None:
        """Force a player car to come in at end of current lap."""
        car_id = str(car.driver_number)
        track_info = self._cars_on_track.get(car_id)
        if track_info:
            track_info["laps_planned"] = track_info["laps_done"]  # finish after current

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def session_time_remaining(self) -> float:
        if self.pso:
            return self.pso.clock.remaining_s
        return 0.0

    @property
    def is_finished(self) -> bool:
        return self.pso.is_finished if self.pso else True

    def get_leaderboard(self) -> list:
        if self.pso:
            return self.pso.leaderboard()
        return []

    def get_session_summary(self) -> dict:
        if self.pso:
            return self.pso.session_summary()
        return {}

    # ------------------------------------------------------------------
    # Internal: AI scheduling
    # ------------------------------------------------------------------

    def _schedule_ai_runs(self) -> None:
        """Check each AI car and start a new run if ready."""
        if self.pso is None or self.circuit_config is None:
            return

        for car_id, engine in self.ai_engines.items():
            # Skip if already on track or not ready
            if car_id in self._cars_on_track:
                continue
            if not self.pso.car_can_run(car_id):
                continue
            if not engine.has_next_run():
                continue

            # Configure run from AI engine
            car_entry = engine.configure_current_run()
            if car_entry is None:
                continue

            # Override car_id to match bridge/PSO key (driver_number)
            car_entry.car_id = car_id
            car_entry.state.car_id = car_id

            # Get the run plan (current_run_idx not yet advanced)
            run_idx = engine.current_run_idx
            if run_idx >= len(engine.session_plan.runs):
                continue
            run_plan = engine.session_plan.runs[run_idx]

            # Request via PSO
            record = self.pso.request_run(
                car_id=car_id,
                program=run_plan.program,
                compound=run_plan.compound,
                fuel_kg=run_plan.fuel_kg,
                laps_planned=run_plan.laps_planned,
            )

            if record is not None:
                self.car_entries[car_id] = car_entry
                self._cars_on_track[car_id] = {
                    "laps_done": 0,
                    "laps_planned": run_plan.laps_planned,
                    "entry": car_entry,
                    "is_player": False,
                }
                logger.debug("AI %s: starting %s run", car_id, run_plan.program.value)

    # ------------------------------------------------------------------
    # Internal: simulate laps for on-track cars
    # ------------------------------------------------------------------

    def _process_on_track_cars(self) -> None:
        """Run laps for cars that are on track."""
        if not self._cars_on_track or self.sim is None:
            return

        # Check which cars in PSO are actually ON_TRACK
        ready_cars = {}
        for car_id, info in list(self._cars_on_track.items()):
            pso_car = self.pso.cars.get(car_id) if self.pso else None
            if pso_car and pso_car.phase == CarPhase.ON_TRACK:
                ready_cars[car_id] = info

        if not ready_cars:
            return

        # Register all ready cars in a fresh simulator for this batch
        batch_sim = LapSimulator(self.circuit_config, self.env, enable_battles=True)
        for car_id, info in ready_cars.items():
            batch_sim.register_car(info["entry"])

        # Run 1 lap
        try:
            lap_results = batch_sim.run_lap()
        except Exception as e:
            logger.error("LapSimulator error: %s", e)
            return

        # Process results
        completed_cars = []
        for car_id, info in ready_cars.items():
            result = lap_results.get(car_id)
            if result is None:
                continue

            info["laps_done"] += 1

            # Update RaceCar with lap data
            race_car = self.race_cars_map.get(car_id)
            if race_car:
                apply_lap_result_to_racecar(
                    race_car, result,
                    circuit_length_m=self.circuit_config.circuit_length_m,
                )
                # Set state to HOT_LAP while on track
                set_racecar_phase(race_car, "hot_lap")
                race_car.last_lap_type = race_car.state

            # Check if run is complete
            if info["laps_done"] >= info["laps_planned"]:
                completed_cars.append(car_id)

        # Complete finished runs
        for car_id in completed_cars:
            self._complete_car_run(car_id)

    def _complete_car_run(self, car_id: str) -> None:
        """Complete a run for a car (return to pits)."""
        info = self._cars_on_track.pop(car_id, None)
        if info is None:
            return

        race_car = self.race_cars_map.get(car_id)
        laps_done = info["laps_done"]
        best_lap = 0.0
        if race_car and race_car.lap_times:
            recent = race_car.lap_times[-laps_done:] if laps_done > 0 else []
            best_lap = min(recent) if recent else 0.0

        km_driven = 0.0
        if self.circuit_config:
            km_driven = self.circuit_config.circuit_length_m * laps_done / 1000.0

        # Complete in PSO
        if self.pso:
            self.pso.complete_run(
                car_id=car_id,
                laps_completed=laps_done,
                best_lap_s=best_lap,
                km_driven=km_driven,
                pit_work_duration_s=30.0,  # basic pit work
            )

        # Complete in AI engine
        if car_id in self.ai_engines:
            engine = self.ai_engines[car_id]
            # Build LapResult list from recent lap times (simplified)
            # The AI engine needs LapResult objects
            entry = info.get("entry")
            if entry and self.circuit_config:
                try:
                    mini_sim = LapSimulator(self.circuit_config, self.env)
                    mini_sim.register_car(entry)
                    fake_results = mini_sim.run_laps(max(1, laps_done))
                    engine.complete_run(fake_results.get(car_id, []))
                except Exception as e:
                    logger.warning("AI complete_run failed for %s: %s", car_id, e)

        # Update RaceCar state
        if race_car:
            set_racecar_phase(race_car, "box")
            race_car.stint_laps_remaining = 0

        # Remove from simulator entries
        self.car_entries.pop(car_id, None)

    # ------------------------------------------------------------------
    # Internal: interpolate positions for map
    # ------------------------------------------------------------------

    def _interpolate_positions(self, dt: float) -> None:
        """
        Update distance_traveled and speed for on-track cars each tick.

        The LapSimulator runs whole laps instantly, but the frontend needs
        smooth position updates. We interpolate based on estimated lap time.
        """
        if self.circuit_config is None:
            return

        circuit_m = self.circuit_config.circuit_length_m

        for car_id, info in self._cars_on_track.items():
            race_car = self.race_cars_map.get(car_id)
            if race_car is None:
                continue

            prog = self._lap_progress.get(car_id)
            if prog is None:
                # First tick for this car: initialize progress
                est_lap = LAP_TIME_ESTIMATE_S
                if race_car.lap_times:
                    est_lap = race_car.lap_times[-1]
                # Out lap is slower
                if info["laps_done"] == 0:
                    est_lap *= OUT_LAP_FACTOR
                prog = {
                    "elapsed": 0.0,
                    "est_lap_s": max(est_lap, 60.0),
                    "circuit_m": circuit_m,
                }
                self._lap_progress[car_id] = prog

            prog["elapsed"] += dt
            fraction = min(prog["elapsed"] / prog["est_lap_s"], 1.0)

            # Update distance (wraps around circuit)
            race_car.distance_traveled = fraction * circuit_m

            # Update speed (m/s) for animation
            avg_speed = circuit_m / prog["est_lap_s"]
            race_car.speed = avg_speed

    def _reset_lap_progress(self, car_id: str) -> None:
        """Reset lap progress after a lap is completed (restart interpolation)."""
        self._lap_progress.pop(car_id, None)

    # ------------------------------------------------------------------
    # Internal: sync phases
    # ------------------------------------------------------------------

    def _sync_phases(self) -> None:
        """Sync PSO car phases back to game RaceCar objects."""
        if self.pso is None:
            return

        for car_id, pso_car in self.pso.cars.items():
            race_car = self.race_cars_map.get(car_id)
            if race_car is None:
                continue

            # Only sync if car is NOT on track (on-track is managed by lap sim)
            if car_id not in self._cars_on_track:
                set_racecar_phase(race_car, pso_car.phase.value)

    def _finish_session(self) -> None:
        """Handle session end."""
        # Complete any remaining on-track cars
        for car_id in list(self._cars_on_track.keys()):
            self._complete_car_run(car_id)

        # Set all cars to BOX
        for car_id, race_car in self.race_cars_map.items():
            set_racecar_phase(race_car, "box")

        self.active = False
        logger.info("Session finished. Runs: %d", len(self.pso.run_log) if self.pso else 0)
