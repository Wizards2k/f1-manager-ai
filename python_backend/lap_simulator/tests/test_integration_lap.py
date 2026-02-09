"""
Integration test – full lap simulation on Monza.

Validates that the entire pipeline (ConfigLoader → LapSimulator → LapResult)
produces physically plausible results for a single car.
"""
import pytest
from pathlib import Path

from lap_simulator.config_loader import load_circuit_config
from lap_simulator.data_types import (
    AeroComponent,
    AeroSetup,
    CarState,
    DriverSkills,
    EnvContext,
    SuspensionState,
    TyreCompound,
)
from lap_simulator.lap_simulator import CarEntry, LapSimulator


@pytest.fixture
def project_root():
    return Path(__file__).resolve().parent.parent.parent.parent


@pytest.fixture
def monza_config(project_root):
    return load_circuit_config("it-1922_monza", project_root=project_root)


@pytest.fixture
def env():
    return EnvContext(air_temp_c=25.0, track_temp_c=35.0)


@pytest.fixture
def balanced_aero():
    return AeroSetup(
        front_wing=AeroComponent(name="front_wing", base_downforce=30.0, base_drag=8.0,
                                  angle_deg=14.0, angle_ref_deg=15.0, drs_drag_reduction=0.15),
        rear_wing=AeroComponent(name="rear_wing", base_downforce=28.0, base_drag=10.0,
                                 angle_deg=12.0, angle_ref_deg=15.0, drs_drag_reduction=0.20),
        beam_wing=AeroComponent(name="beam_wing", base_downforce=5.0, base_drag=2.5,
                                 angle_deg=8.0, angle_ref_deg=10.0),
        front_floor=AeroComponent(name="front_floor", base_downforce=12.0, base_drag=2.0),
        rear_floor=AeroComponent(name="rear_floor", base_downforce=12.0, base_drag=2.0),
        sidepods=AeroComponent(name="sidepods", base_downforce=4.0, base_drag=3.0,
                                cooling_contribution=45.0),
        engine_cover=AeroComponent(name="engine_cover", base_downforce=2.0, base_drag=1.0,
                                    cooling_contribution=18.0),
        b_wing=AeroComponent(name="b_wing", base_downforce=3.0, base_drag=1.5),
        suspension_front=SuspensionState(rigidity=0.55, efficiency=0.80),
        suspension_rear=SuspensionState(rigidity=0.55, efficiency=0.80),
        ride_height_front_mm=35.0,
        ride_height_rear_mm=48.0,
        ride_height_optimal_front_mm=35.0,
        ride_height_optimal_rear_mm=48.0,
    )


@pytest.fixture
def driver():
    return DriverSkills(
        raw_pace=85,
        race_craft=80,
        aggression=55,
        consistency=82,
        tyre_management=75,
        overtaking_skill=70,
        defending_skill=65,
        wet_skill=70,
        smoothness=72,
        setup_finding=68,
    )


class TestSingleLapMonza:
    def test_lap_completes(self, monza_config, env, balanced_aero, driver):
        sim = LapSimulator(monza_config, env)
        car_state = CarState(car_id="car_01")
        # Set tyres to C4 (Monza soft)
        for t in car_state.tyres.values():
            t.compound = TyreCompound.C4
            t.surface_temp_c = 95.0
            t.core_temp_c = 85.0
        car_state.pu.fuel_kg = 80.0

        entry = CarEntry(
            car_id="car_01",
            state=car_state,
            aero_setup=balanced_aero,
            driver_skills=driver,
            push_level=1.0,
        )
        sim.register_car(entry)
        results = sim.run_lap()

        assert "car_01" in results
        lap = results["car_01"]
        assert lap.lap_time_s > 0

    def test_lap_time_plausible(self, monza_config, env, balanced_aero, driver):
        """Monza lap time should be roughly 80-130s."""
        sim = LapSimulator(monza_config, env)
        car_state = CarState(car_id="car_01")
        for t in car_state.tyres.values():
            t.compound = TyreCompound.C4
            t.surface_temp_c = 100.0
            t.core_temp_c = 88.0
        car_state.pu.fuel_kg = 80.0

        entry = CarEntry(
            car_id="car_01", state=car_state,
            aero_setup=balanced_aero, driver_skills=driver,
        )
        sim.register_car(entry)
        results = sim.run_lap()
        lap = results["car_01"]

        assert 70.0 < lap.lap_time_s < 140.0, (
            f"Lap time {lap.lap_time_s:.2f}s outside plausible range for Monza"
        )

    def test_all_sections_simulated(self, monza_config, env, balanced_aero, driver):
        sim = LapSimulator(monza_config, env)
        car_state = CarState(car_id="car_01")
        for t in car_state.tyres.values():
            t.compound = TyreCompound.C4
            t.surface_temp_c = 100.0
            t.core_temp_c = 88.0

        entry = CarEntry(
            car_id="car_01", state=car_state,
            aero_setup=balanced_aero, driver_skills=driver,
        )
        sim.register_car(entry)
        results = sim.run_lap()
        lap = results["car_01"]

        assert len(lap.section_results) == len(monza_config.sections)

    def test_section_times_positive(self, monza_config, env, balanced_aero, driver):
        sim = LapSimulator(monza_config, env)
        car_state = CarState(car_id="car_01")
        for t in car_state.tyres.values():
            t.compound = TyreCompound.C4
            t.surface_temp_c = 100.0
            t.core_temp_c = 88.0

        entry = CarEntry(
            car_id="car_01", state=car_state,
            aero_setup=balanced_aero, driver_skills=driver,
        )
        sim.register_car(entry)
        results = sim.run_lap()
        lap = results["car_01"]

        for i, sr in enumerate(lap.section_results):
            assert sr.dt_s > 0, f"Section {i} has non-positive dt"
            assert sr.v_effective_kph > 0, f"Section {i} has non-positive speed"

    def test_fuel_consumed(self, monza_config, env, balanced_aero, driver):
        sim = LapSimulator(monza_config, env)
        car_state = CarState(car_id="car_01")
        car_state.pu.fuel_kg = 80.0
        for t in car_state.tyres.values():
            t.compound = TyreCompound.C4
            t.surface_temp_c = 100.0
            t.core_temp_c = 88.0

        entry = CarEntry(
            car_id="car_01", state=car_state,
            aero_setup=balanced_aero, driver_skills=driver,
        )
        sim.register_car(entry)
        results = sim.run_lap()
        lap = results["car_01"]

        assert lap.fuel_kg < 80.0, "Fuel should have been consumed"

    def test_tyre_wear_increases(self, monza_config, env, balanced_aero, driver):
        sim = LapSimulator(monza_config, env)
        car_state = CarState(car_id="car_01")
        for t in car_state.tyres.values():
            t.compound = TyreCompound.C4
            t.surface_temp_c = 100.0
            t.core_temp_c = 88.0

        entry = CarEntry(
            car_id="car_01", state=car_state,
            aero_setup=balanced_aero, driver_skills=driver,
        )
        sim.register_car(entry)
        results = sim.run_lap()
        lap = results["car_01"]

        assert lap.avg_tyre_wear_pct > 0, "Tyres should have worn"

    def test_sector_times_sum_to_lap(self, monza_config, env, balanced_aero, driver):
        sim = LapSimulator(monza_config, env)
        car_state = CarState(car_id="car_01")
        for t in car_state.tyres.values():
            t.compound = TyreCompound.C4
            t.surface_temp_c = 100.0
            t.core_temp_c = 88.0

        entry = CarEntry(
            car_id="car_01", state=car_state,
            aero_setup=balanced_aero, driver_skills=driver,
        )
        sim.register_car(entry)
        results = sim.run_lap()
        lap = results["car_01"]

        sector_sum = sum(lap.sector_times_s)
        assert abs(sector_sum - lap.lap_time_s) < 0.01, (
            f"Sector sum {sector_sum:.3f} != lap time {lap.lap_time_s:.3f}"
        )


class TestMultiLap:
    def test_five_laps(self, monza_config, env, balanced_aero, driver):
        sim = LapSimulator(monza_config, env)
        car_state = CarState(car_id="car_01")
        car_state.pu.fuel_kg = 100.0
        for t in car_state.tyres.values():
            t.compound = TyreCompound.C4
            t.surface_temp_c = 90.0
            t.core_temp_c = 82.0

        entry = CarEntry(
            car_id="car_01", state=car_state,
            aero_setup=balanced_aero, driver_skills=driver,
        )
        sim.register_car(entry)
        all_results = sim.run_laps(5)

        laps = all_results["car_01"]
        assert len(laps) == 5

        # Lap times should all be plausible
        for i, lap in enumerate(laps):
            assert 70.0 < lap.lap_time_s < 140.0, (
                f"Lap {i+1} time {lap.lap_time_s:.2f}s outside range"
            )

        # Fuel should decrease monotonically
        fuels = [lap.fuel_kg for lap in laps]
        for i in range(1, len(fuels)):
            assert fuels[i] < fuels[i-1], f"Fuel not decreasing at lap {i+1}"

        # Tyre wear should increase monotonically
        wears = [lap.avg_tyre_wear_pct for lap in laps]
        for i in range(1, len(wears)):
            assert wears[i] > wears[i-1], f"Wear not increasing at lap {i+1}"

    def test_push_vs_conserve(self, monza_config, env, balanced_aero, driver):
        """Push mode should produce faster laps but more wear."""
        sim_push = LapSimulator(monza_config, env)
        sim_conserve = LapSimulator(monza_config, env)

        state_push = CarState(car_id="push")
        state_conserve = CarState(car_id="conserve")
        for s in (state_push, state_conserve):
            s.pu.fuel_kg = 80.0
            for t in s.tyres.values():
                t.compound = TyreCompound.C4
                t.surface_temp_c = 100.0
                t.core_temp_c = 88.0

        sim_push.register_car(CarEntry("push", state_push, balanced_aero, driver, push_level=1.1))
        sim_conserve.register_car(CarEntry("conserve", state_conserve, balanced_aero, driver, push_level=0.85))

        res_push = sim_push.run_lap()["push"]
        res_conserve = sim_conserve.run_lap()["conserve"]

        # Push should be faster
        assert res_push.lap_time_s < res_conserve.lap_time_s
        # Push should wear tyres more
        assert res_push.avg_tyre_wear_pct > res_conserve.avg_tyre_wear_pct
