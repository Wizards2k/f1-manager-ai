"""Omni-comprehensive penalty stack regression tests."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Sequence

import pytest

from python_backend.lap_simulator.config_loader import load_circuit_config
from python_backend.lap_simulator.data_types import (
    AeroComponent,
    AeroSetup,
    CarState,
    DriverSkills,
    EngineMapName,
    EnvContext,
    SuspensionState,
    TyreCompound,
)
from python_backend.lap_simulator.lap_simulator import CarEntry, LapSimulator


def _build_baseline_entry(car_id: str) -> CarEntry:
    state = CarState(car_id=car_id)
    state.team_code = "MCL"
    state.pu.fuel_kg = 10.0
    state.pu.active_map = EngineMapName.QUALIFY
    for tyre in state.tyres.values():
        tyre.compound = TyreCompound.C5
        tyre.surface_temp_c = 95.0
        tyre.core_temp_c = 85.0
        tyre.wear_pct = 0.5
    state.brakes.duct_opening = 0.45
    state.brakes.temp_front_c = 700
    state.brakes.temp_rear_c = 650

    aero_setup = AeroSetup(
        front_wing=AeroComponent(name="front_wing", base_downforce=30.0, base_drag=8.0, angle_deg=14.0, angle_ref_deg=15.0),
        rear_wing=AeroComponent(name="rear_wing", base_downforce=28.0, base_drag=10.0, angle_deg=12.0, angle_ref_deg=15.0),
        beam_wing=AeroComponent(name="beam_wing", base_downforce=5.0, base_drag=2.5, angle_deg=8.0, angle_ref_deg=10.0),
        front_floor=AeroComponent(name="front_floor", base_downforce=12.0, base_drag=2.0),
        rear_floor=AeroComponent(name="rear_floor", base_downforce=12.0, base_drag=2.0),
        sidepods=AeroComponent(name="sidepods", base_downforce=4.0, base_drag=3.0, cooling_contribution=45.0),
        engine_cover=AeroComponent(name="engine_cover", base_downforce=2.0, base_drag=1.0, cooling_contribution=18.0),
        b_wing=AeroComponent(name="b_wing", base_downforce=3.0, base_drag=1.5),
        suspension_front=SuspensionState(rigidity=0.55, efficiency=0.80),
        suspension_rear=SuspensionState(rigidity=0.55, efficiency=0.80),
        ride_height_front_mm=35.0,
        ride_height_rear_mm=48.0,
        ride_height_optimal_front_mm=35.0,
        ride_height_optimal_rear_mm=48.0,
    )

    entry = CarEntry(
        car_id=car_id,
        state=state,
        aero_setup=aero_setup,
        driver_skills=DriverSkills(
            raw_pace=95,
            race_craft=92,
            aggression=85,
            consistency=94,
            tyre_management=92,
            overtaking_skill=90,
            defending_skill=88,
            wet_skill=85,
            smoothness=92,
            setup_finding=90,
        ),
        push_level=1.12,
        setup_sliders={
            "front_wing": 50,
            "rear_wing": 50,
            "antiroll_front": 50,
            "antiroll_rear": 50,
            "ride_height_front": 50,
            "ride_height_rear": 50,
        },
        ideal_setup_sliders={
            "front_wing": 50,
            "rear_wing": 50,
            "antiroll_front": 50,
            "antiroll_rear": 50,
            "ride_height_front": 50,
            "ride_height_rear": 50,
        },
    )
    return entry


def _apply_fuel_penalty(entry: CarEntry) -> None:
    entry.state.pu.fuel_kg = 100.0


def _apply_tyre_penalty(entry: CarEntry) -> None:
    for tyre in entry.state.tyres.values():
        tyre.compound = TyreCompound.C1
        tyre.wear_pct = 65.0
        tyre.surface_temp_c = 60.0
        tyre.core_temp_c = 55.0


def _apply_push_penalty(entry: CarEntry) -> None:
    entry.push_level = 0.82


def _apply_engine_penalty(entry: CarEntry) -> None:
    entry.state.team_code = "ALP"
    entry.state.pu.active_map = EngineMapName.RACE


def _apply_brake_penalty(entry: CarEntry) -> None:
    entry.state.brakes.duct_opening = 0.1
    entry.state.brakes.temp_front_c = 920
    entry.state.brakes.temp_rear_c = 860


def _apply_setup_penalty(entry: CarEntry) -> None:
    entry.setup_sliders = {
        "front_wing": 95,
        "rear_wing": 10,
        "antiroll_front": 90,
        "antiroll_rear": 15,
        "ride_height_front": 90,
        "ride_height_rear": 10,
    }


def _apply_all(entry: CarEntry) -> None:
    for fn in (
        _apply_fuel_penalty,
        _apply_tyre_penalty,
        _apply_push_penalty,
        _apply_engine_penalty,
        _apply_brake_penalty,
        _apply_setup_penalty,
    ):
        fn(entry)


@dataclass
class PenaltyScenario:
    name: str
    adjustments: Sequence[Callable[[CarEntry], None]]
    penalty_expectations: Dict[str, float]
    min_lap_delta_s: float


SCENARIOS = [
    PenaltyScenario("baseline", [], {}, 0.0),
    PenaltyScenario("fuel", [_apply_fuel_penalty], {"fuel_penalty_s": 0.0025}, 0.0025),
    PenaltyScenario("tyre", [_apply_tyre_penalty], {"tyre_penalty_s": 1.2}, 1.2),
    PenaltyScenario("push", [_apply_push_penalty], {}, 0.5),
    PenaltyScenario("engine", [_apply_engine_penalty], {"engine_penalty_s": -1.0}, -1.5),
    PenaltyScenario("brake", [_apply_brake_penalty], {"brake_penalty_s": 6.0}, 5.0),
    PenaltyScenario("setup", [_apply_setup_penalty], {"setup_penalty_s": 0.05}, 0.05),
    PenaltyScenario(
        "all",
        [_apply_all],
        {
            "fuel_penalty_s": 0.0025,
            "tyre_penalty_s": 1.2,
            "engine_penalty_s": -1.0,
            "brake_penalty_s": 6.0,
            "setup_penalty_s": 0.05,
        },
        6.0,
    ),
]


@pytest.fixture(scope="module")
def monza_config():
    return load_circuit_config("it-1922_monza")


@pytest.fixture(scope="module")
def env():
    return EnvContext(air_temp_c=25.0, track_temp_c=35.0)


def _run_scenario(config, env, scenario: PenaltyScenario):
    entry = _build_baseline_entry(car_id=f"pen_{scenario.name}")
    for fn in scenario.adjustments:
        fn(entry)
    sim = LapSimulator(config, env)
    sim.register_car(entry)
    lap = sim.run_lap()[entry.car_id]
    return lap


def _aggregate_penalty(lap, attr: str) -> float:
    return sum(getattr(section, attr, 0.0) for section in lap.section_results)


@pytest.fixture(scope="module")
def baseline_lap(monza_config, env):
    return _run_scenario(monza_config, env, SCENARIOS[0])


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_penalty_stack_progression(monza_config, env, baseline_lap, scenario: PenaltyScenario):
    lap = _run_scenario(monza_config, env, scenario)

    if scenario.name == "baseline":
        for attr in ("fuel_penalty_s", "tyre_penalty_s", "engine_penalty_s", "brake_penalty_s", "setup_penalty_s"):
            baseline_value = _aggregate_penalty(baseline_lap, attr)
            scenario_value = _aggregate_penalty(lap, attr)
            assert pytest.approx(baseline_value, abs=1e-6) == scenario_value
        return

    lap_delta = lap.lap_time_s - baseline_lap.lap_time_s
    if scenario.min_lap_delta_s >= 0:
        assert lap_delta >= scenario.min_lap_delta_s, (
            f"Lap delta troppo basso per scenario {scenario.name}: {lap_delta:.3f}s"
        )
    else:
        assert lap_delta <= scenario.min_lap_delta_s, (
            f"Lap delta troppo alto (atteso bonus) per scenario {scenario.name}: {lap_delta:.3f}s"
        )

    for attr, threshold in scenario.penalty_expectations.items():
        baseline_value = _aggregate_penalty(baseline_lap, attr)
        scenario_value = _aggregate_penalty(lap, attr)
        delta = scenario_value - baseline_value
        if threshold >= 0:
            assert delta >= threshold, (
                f"{attr} non è aumentato come atteso per scenario {scenario.name}: {scenario_value:.3f} vs {baseline_value:.3f}"
            )
        else:
            assert delta <= threshold, (
                f"{attr} non è diminuito (bonus) come atteso per scenario {scenario.name}: {scenario_value:.3f} vs {baseline_value:.3f}"
            )
