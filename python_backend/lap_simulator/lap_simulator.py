"""
LapSimulator – runtime loop for a single lap.

Orchestrates: InputMixer → update_section × N → StateCommit → OutputBus
for one or more cars traversing all sections of a circuit.

Reference: docs/lap-physics-spec-v0.5.md §3.3.1
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .data_types import (
    AeroSetup,
    CarState,
    CircuitConfig,
    DriverSkills,
    EnvContext,
    SectionEvent,
    SectionResult,
)
from .update_section import update_section

PENALTY_LOGGER_NAME = "lap_simulator.penalties"
logger = logging.getLogger(__name__)
penalty_logger = logging.getLogger(PENALTY_LOGGER_NAME)
# Disabled by default; enable explicitly for penalty investigations
DEBUG_PENALTIES = os.getenv("DEBUG_PENALTIES", "0").lower() in {"1", "true", "yes", "on"}
if DEBUG_PENALTIES:
    _penalty_log_path = Path("logs/penalties.log")
    _penalty_log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Reset file on startup
    with _penalty_log_path.open("w", encoding="utf-8") as fh:
        fh.write("")  # Create empty file
    
    if not any(getattr(h, "_penalty_debug", False) for h in penalty_logger.handlers):
        handler = logging.FileHandler(_penalty_log_path)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        handler._penalty_debug = True
        penalty_logger.addHandler(handler)
    penalty_logger.setLevel(logging.DEBUG)
    penalty_logger.info("[PEN] DEBUG_PENALTIES attivo in LapSimulator")

_LAP_LOG_FILE = Path("logs/lap_times_debug.log")
_LAP_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Lazy import to avoid circular dependency
_BattleResolver = None

def _get_battle_resolver_class():
    global _BattleResolver
    if _BattleResolver is None:
        from .battle_resolver import BattleResolver as BR
        _BattleResolver = BR
    return _BattleResolver


# ---------------------------------------------------------------------------
# Car entry – bundles immutable config with mutable state
# ---------------------------------------------------------------------------

@dataclass
class CarEntry:
    """A car registered in the LapSimulator."""
    car_id: str
    state: CarState
    aero_setup: AeroSetup
    driver_skills: DriverSkills
    push_level: float = 1.0              # player / AI commanded push
    delta_aero: float = 0.0
    delta_grip: float = 0.0
    apply_baseline_delta: bool = True
    setup_sliders: Dict[str, int] = field(default_factory=dict)  # current setup (0-100 per slider)
    ideal_setup_sliders: Dict[str, int] = field(default_factory=dict)  # ideal setup for circuit


# ---------------------------------------------------------------------------
# Lap result
# ---------------------------------------------------------------------------

@dataclass
class LapResult:
    """Result of simulating one full lap for a car."""
    car_id: str
    lap_number: int
    lap_time_s: float = 0.0
    sector_times_s: List[float] = field(default_factory=list)
    section_results: List[SectionResult] = field(default_factory=list)
    events: List[SectionEvent] = field(default_factory=list)
    battle_events: list = field(default_factory=list)  # BattleEvent list
    # final state snapshot
    fuel_kg: float = 0.0
    ers_energy_mj: float = 0.0
    avg_tyre_wear_pct: float = 0.0
    avg_tyre_temp_surface_c: float = 0.0


# ---------------------------------------------------------------------------
# LapSimulator
# ---------------------------------------------------------------------------

class LapSimulator:
    """
    Simulates one lap for one or more cars on a given circuit.

    Usage
    -----
    ```python
    sim = LapSimulator(config, env)
    sim.register_car(car_entry)
    results = sim.run_lap()
    ```
    """

    def __init__(self, config: CircuitConfig, env: EnvContext, enable_battles: bool = False):
        self.config = config
        self.env = env
        self.cars: Dict[str, CarEntry] = {}
        self.battle_resolver = None
        self._dirty_air_cache: Dict[str, float] = {}
        if enable_battles:
            BR = _get_battle_resolver_class()
            self.battle_resolver = BR()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_car(self, entry: CarEntry) -> None:
        self.cars[entry.car_id] = entry

    def register_cars(self, entries: List[CarEntry]) -> None:
        for e in entries:
            self.register_car(e)

    # ------------------------------------------------------------------
    # InputMixer (§3.3.1 block 1)
    # ------------------------------------------------------------------

    def _compute_airflow_penalty(self, car_id: str) -> float:
        """
        Compute dirty-air penalty based on proximity to car ahead.

        For single-car simulation this returns 0.
        Multi-car: uses dirty_air_cache populated by BattleResolver.
        """
        return self._dirty_air_cache.get(car_id, 0.0)

    def _compute_traffic_constraint(self, car_id: str) -> float:
        """
        Compute speed constraint from car ahead.

        Returns 0 if no constraint (free air).
        """
        # TODO: implement multi-car traffic logic
        return 0.0

    # ------------------------------------------------------------------
    # Single-car lap
    # ------------------------------------------------------------------

    def _run_lap_single(self, entry: CarEntry) -> LapResult:
        """Simulate one full lap for a single car."""
        state = entry.state
        state.lap_time_acc_s = 0.0
        state.current_section_idx = 0
        # Reset per-lap PU energy tracking
        pu_state = state.pu
        pu_state.lap_id_prev = pu_state.lap_id_current
        pu_state.energy_trace_prev = list(pu_state.energy_trace)
        pu_state.runtime_warnings_prev = list(pu_state.runtime_warnings)
        pu_state.lap_deploy_prev_mj = pu_state.lap_deploy_mj
        pu_state.lap_harvest_prev_mj = pu_state.lap_harvest_mj
        pu_state.lap_mguh_direct_prev_mj = pu_state.lap_mguh_direct_mj
        pu_state.lap_mguh_harvest_prev_mj = pu_state.lap_mguh_harvest_mj
        pu_state.lap_id_current += 1
        pu_state.lap_deploy_mj = 0.0
        pu_state.lap_harvest_mj = 0.0
        pu_state.lap_mguh_direct_mj = 0.0
        pu_state.lap_mguh_harvest_mj = 0.0
        pu_state.energy_trace = []
        pu_state.runtime_warnings = []
        pu_state.bucket_primary_used_mj = 0.0
        pu_state.bucket_secondary_used_mj = 0.0
        pu_state.bucket_exit_used_mj = 0.0
        pu_state.bucket_primary_total_mj = 0.0
        pu_state.bucket_secondary_total_mj = 0.0
        pu_state.bucket_exit_total_mj = 0.0
        pu_state.mguh_primary_total_mj = 0.0
        pu_state.mguh_secondary_total_mj = 0.0
        pu_state.mguh_exit_total_mj = 0.0
        pu_state.mguh_primary_used_mj = 0.0
        pu_state.mguh_secondary_used_mj = 0.0
        pu_state.mguh_exit_used_mj = 0.0
        pu_state.bucket_budget_initialized = False

        section_results: List[SectionResult] = []
        all_events: List[SectionEvent] = []

        # Sector time tracking
        sector_times: List[float] = []
        current_sector_start = 0.0
        sector_idx = 0
        distance_acc = 0.0

        sections = self.config.sections
        if not sections:
            logger.warning("No sections defined for circuit %s", self.config.circuit_id)
            return LapResult(car_id=entry.car_id, lap_number=state.lap_number)

        for i, section in enumerate(sections):
            state.current_section_idx = i

            # InputMixer
            airflow = self._compute_airflow_penalty(entry.car_id)
            traffic = self._compute_traffic_constraint(entry.car_id)

            # Physics step
            result = update_section(
                car_state=state,
                aero_setup=entry.aero_setup,
                driver_skills=entry.driver_skills,
                section=section,
                env=self.env,
                config=self.config,
                push_level=entry.push_level,
                airflow_penalty=airflow,
                traffic_v_max_kph=traffic,
                delta_aero=entry.delta_aero,
                delta_grip=entry.delta_grip,
                setup_sliders=entry.setup_sliders if entry.setup_sliders else None,
                ideal_setup_sliders=entry.ideal_setup_sliders if entry.ideal_setup_sliders else None,
            )

            section_results.append(result)
            all_events.extend(result.events)

            # Sector tracking
            distance_acc += section.length_m
            if (sector_idx < len(self.config.sector_markers_m) - 1
                    and distance_acc >= self.config.sector_markers_m[sector_idx + 1]):
                sector_time = state.lap_time_acc_s - current_sector_start
                sector_times.append(sector_time)
                current_sector_start = state.lap_time_acc_s
                sector_idx += 1

        # Final sector
        final_sector = state.lap_time_acc_s - current_sector_start
        sector_times.append(final_sector)

        # Tyre stats
        tyre_wears = [t.wear_pct for t in state.tyres.values()]
        tyre_temps = [t.surface_temp_c for t in state.tyres.values()]
        avg_wear = sum(tyre_wears) / max(len(tyre_wears), 1)
        avg_temp = sum(tyre_temps) / max(len(tyre_temps), 1)

        # Increment lap age for all tyres
        for t in state.tyres.values():
            t.lap_age += 1

        lap_result = LapResult(
            car_id=entry.car_id,
            lap_number=state.lap_number,
            lap_time_s=state.lap_time_acc_s,
            sector_times_s=sector_times,
            section_results=section_results,
            events=all_events,
            fuel_kg=state.pu.fuel_kg,
            ers_energy_mj=state.pu.ers_energy_mj,
            avg_tyre_wear_pct=avg_wear,
            avg_tyre_temp_surface_c=avg_temp,
        )

        state.lap_number += 1
        return lap_result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_lap(self) -> Dict[str, LapResult]:
        """
        Run one lap for all registered cars.

        If battle_resolver is enabled and >1 car, runs multi-car mode
        with per-section battle resolution. Otherwise single-car mode.

        Returns a dict of car_id → LapResult.
        """
        if self.battle_resolver and len(self.cars) > 1:
            return self._run_lap_multi()
        results: Dict[str, LapResult] = {}
        for car_id, entry in self.cars.items():
            results[car_id] = self._run_lap_single(entry)
        self._log_lap_times(results)
        return results

    def _log_lap_times(self, results: Dict[str, LapResult]) -> None:
        timestamp = datetime.utcnow().isoformat()
        lines: List[str] = [f"{timestamp} | Lap Results:"]
        for car_id, lr in results.items():
            entry = self.cars.get(car_id)
            delta_aero = entry.delta_aero if entry else 0.0
            delta_grip = entry.delta_grip if entry else 0.0
            push_level = entry.push_level if entry else 1.0
            apply_baseline = entry.apply_baseline_delta if entry else True
            sectors = ",".join(f"{s:.3f}" for s in lr.sector_times_s)
            lines.append(
                f"{lr.car_id} | Lap {lr.lap_number} | {lr.lap_time_s:.3f}s | sectors[{sectors}] | "
                f"delta_aero={delta_aero:.4f} delta_grip={delta_grip:.4f} push={push_level:.2f} baseline={apply_baseline} | "
                f"fuel={lr.fuel_kg:.1f}kg ers={lr.ers_energy_mj:.2f}MJ"
            )
        try:
            with _LAP_LOG_FILE.open("a", encoding="utf-8") as fp:
                fp.write("\n".join(lines) + "\n")
        except OSError as exc:
            logger.warning("Failed to write lap debug log: %s", exc)

    def _run_lap_multi(self) -> Dict[str, LapResult]:
        """
        Run one lap for all cars with BattleResolver per section.

        Each section: physics for all cars → BattleResolver → apply outcomes.
        """
        from .battle_resolver import BattleEvent

        # Init per-car accumulators
        car_section_results: Dict[str, List[SectionResult]] = {cid: [] for cid in self.cars}
        car_events: Dict[str, List[SectionEvent]] = {cid: [] for cid in self.cars}
        car_battle_events: Dict[str, list] = {cid: [] for cid in self.cars}

        # Reset lap state
        for entry in self.cars.values():
            entry.state.lap_time_acc_s = 0.0
            entry.state.current_section_idx = 0

        # Sector tracking per car
        sector_data: Dict[str, dict] = {
            cid: {"times": [], "start": 0.0, "idx": 0, "dist": 0.0}
            for cid in self.cars
        }

        sections = self.config.sections
        if not sections:
            return {
                cid: LapResult(car_id=cid, lap_number=entry.state.lap_number)
                for cid, entry in self.cars.items()
            }

        # Ordering: sorted by lap_time_acc (fastest = leader)
        ordering = list(self.cars.keys())

        for i, section in enumerate(sections):
            section_results: Dict[str, SectionResult] = {}

            # Phase 1: physics for each car
            for car_id in ordering:
                entry = self.cars[car_id]
                entry.state.current_section_idx = i

                airflow = self._compute_airflow_penalty(car_id)
                traffic = self._compute_traffic_constraint(car_id)

                result = update_section(
                    car_state=entry.state,
                    aero_setup=entry.aero_setup,
                    driver_skills=entry.driver_skills,
                    section=section,
                    env=self.env,
                    config=self.config,
                    push_level=entry.push_level,
                    airflow_penalty=airflow,
                    traffic_v_max_kph=traffic,
                    delta_aero=entry.delta_aero,
                    delta_grip=entry.delta_grip,
                    apply_baseline_delta=entry.apply_baseline_delta,
                )
                section_results[car_id] = result
                car_section_results[car_id].append(result)
                car_events[car_id].extend(result.events)

            # Phase 2: BattleResolver
            # Build cars_in_section sorted by position (leader first)
            # Gap = difference in lap_time_acc converted to distance
            times = [(cid, self.cars[cid].state.lap_time_acc_s) for cid in ordering]
            times.sort(key=lambda x: x[1])  # fastest first = leader

            cars_in_section = []
            for j, (cid, t) in enumerate(times):
                if j == 0:
                    gap_m = 0.0
                else:
                    dt = t - times[j - 1][1]
                    v_avg = section_results[cid].v_effective_kph / 3.6
                    gap_m = max(dt * v_avg, 0.0)
                v_eff = section_results[cid].v_effective_kph
                cars_in_section.append((cid, gap_m, v_eff))

            battle_result = self.battle_resolver.resolve_section(
                cars_in_section, section, self.cars, section_results
            )

            # Apply dirty air for next section
            self._dirty_air_cache = battle_result.dirty_air_penalties

            # Collect battle events per car
            for evt in battle_result.events:
                car_battle_events.setdefault(evt.attacker_id, []).append(evt)
                car_battle_events.setdefault(evt.defender_id, []).append(evt)

            # Apply ordering changes
            for attacker, defender in battle_result.ordering_changes:
                if attacker in ordering and defender in ordering:
                    ai = ordering.index(attacker)
                    di = ordering.index(defender)
                    if ai > di:  # attacker was behind, now ahead
                        ordering[ai], ordering[di] = ordering[di], ordering[ai]

            # Sector tracking
            for cid, entry in self.cars.items():
                sd = sector_data[cid]
                sd["dist"] += section.length_m
                if (sd["idx"] < len(self.config.sector_markers_m) - 1
                        and sd["dist"] >= self.config.sector_markers_m[sd["idx"] + 1]):
                    sector_time = entry.state.lap_time_acc_s - sd["start"]
                    sd["times"].append(sector_time)
                    sd["start"] = entry.state.lap_time_acc_s
                    sd["idx"] += 1

        # Build results
        results: Dict[str, LapResult] = {}
        for cid, entry in self.cars.items():
            state = entry.state
            sd = sector_data[cid]
            sd["times"].append(state.lap_time_acc_s - sd["start"])

            tyre_wears = [t.wear_pct for t in state.tyres.values()]
            tyre_temps = [t.surface_temp_c for t in state.tyres.values()]

            for t in state.tyres.values():
                t.lap_age += 1

            results[cid] = LapResult(
                car_id=cid,
                lap_number=state.lap_number,
                lap_time_s=state.lap_time_acc_s,
                sector_times_s=sd["times"],
                section_results=car_section_results[cid],
                events=car_events[cid],
                battle_events=car_battle_events.get(cid, []),
                fuel_kg=state.pu.fuel_kg,
                ers_energy_mj=state.pu.ers_energy_mj,
                avg_tyre_wear_pct=sum(tyre_wears) / max(len(tyre_wears), 1),
                avg_tyre_temp_surface_c=sum(tyre_temps) / max(len(tyre_temps), 1),
            )
            state.lap_number += 1

        return results

    def run_laps(self, n_laps: int) -> Dict[str, List[LapResult]]:
        """
        Run multiple laps for all registered cars.

        Returns a dict of car_id → list of LapResult (one per lap).
        """
        all_results: Dict[str, List[LapResult]] = {
            cid: [] for cid in self.cars
        }
        for lap_i in range(n_laps):
            lap_results = self.run_lap()
            for cid, lr in lap_results.items():
                all_results[cid].append(lr)
        return all_results
