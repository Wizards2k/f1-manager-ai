"""
LapSimulator – runtime loop for a single lap.

Orchestrates: InputMixer → update_section × N → StateCommit → OutputBus
for one or more cars traversing all sections of a circuit.

Reference: docs/lap-physics-spec-v0.5.md §3.3.1
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

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

logger = logging.getLogger(__name__)


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

    def __init__(self, config: CircuitConfig, env: EnvContext):
        self.config = config
        self.env = env
        self.cars: Dict[str, CarEntry] = {}

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
        Multi-car: based on gap to car ahead in same section.
        """
        # TODO: implement multi-car proximity logic
        return 0.0

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

        Returns a dict of car_id → LapResult.
        """
        results: Dict[str, LapResult] = {}
        for car_id, entry in self.cars.items():
            results[car_id] = self._run_lap_single(entry)
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
