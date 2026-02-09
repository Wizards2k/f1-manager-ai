"""Tests for brake_system – update_brakes()."""
import pytest

from lap_simulator.brake_system import update_brakes
from lap_simulator.data_types import (
    AeroForces,
    BrakeState,
    BrakeSystemParams,
    CarState,
    CircuitConfig,
    DriverIntent,
    EnvContext,
    SectionContext,
    SectionKind,
)


@pytest.fixture
def default_env():
    return EnvContext()


@pytest.fixture
def default_config():
    return CircuitConfig()


@pytest.fixture
def heavy_brake_section():
    return SectionContext(
        section_id="s02", name="Turn 1", kind=SectionKind.SLOW_CORNER,
        length_m=100.0, v_base_kph=80.0, braking_energy_mj=2.5,
    )


@pytest.fixture
def light_brake_section():
    return SectionContext(
        section_id="s01", name="Straight", kind=SectionKind.STRAIGHT,
        length_m=800.0, v_base_kph=300.0, braking_energy_mj=0.1,
    )


class TestBrakeTemperature:
    def test_heavy_braking_heats_brakes(self, heavy_brake_section, default_env, default_config):
        car = CarState()
        car.brakes.temp_front_c = 400.0
        car.brakes.temp_rear_c = 350.0
        aero = AeroForces()
        driver = DriverIntent()
        initial_front = car.brakes.temp_front_c
        _, _ = update_brakes(car, heavy_brake_section, default_env, aero, driver, default_config, dt_s=1.5, v_kph=80.0)
        assert car.brakes.temp_front_c > initial_front

    def test_light_braking_less_heat(self, light_brake_section, default_env, default_config):
        car1 = CarState()
        car1.brakes.temp_front_c = 400.0
        car2 = CarState()
        car2.brakes.temp_front_c = 400.0
        aero = AeroForces()
        driver = DriverIntent()
        heavy_section = SectionContext(
            section_id="s02", name="Turn 1", kind=SectionKind.SLOW_CORNER,
            length_m=100.0, v_base_kph=80.0, braking_energy_mj=2.5,
        )
        update_brakes(car1, light_brake_section, default_env, aero, driver, default_config, dt_s=2.0, v_kph=300.0)
        update_brakes(car2, heavy_section, default_env, aero, driver, default_config, dt_s=1.5, v_kph=80.0)
        # Heavy braking should produce more heat
        assert car2.brakes.temp_front_c > car1.brakes.temp_front_c


class TestBrakeFade:
    def test_fade_at_high_temp(self, heavy_brake_section, default_env, default_config):
        car = CarState()
        car.brakes.temp_front_c = 900.0  # above fade threshold (850)
        car.brakes.temp_rear_c = 800.0   # above rear threshold (750)
        aero = AeroForces()
        driver = DriverIntent()
        _, events = update_brakes(car, heavy_brake_section, default_env, aero, driver, default_config, dt_s=1.5, v_kph=80.0)
        assert car.brakes.fade_level > 0
        assert any(e.event_type == "brake_fade" for e in events)

    def test_no_fade_at_normal_temp(self, heavy_brake_section, default_env, default_config):
        car = CarState()
        car.brakes.temp_front_c = 500.0
        car.brakes.temp_rear_c = 400.0
        aero = AeroForces()
        driver = DriverIntent()
        _, events = update_brakes(car, heavy_brake_section, default_env, aero, driver, default_config, dt_s=1.5, v_kph=80.0)
        assert car.brakes.fade_level == 0.0


class TestBrakingEfficiency:
    def test_efficiency_in_range(self, heavy_brake_section, default_env, default_config):
        car = CarState()
        aero = AeroForces()
        driver = DriverIntent()
        eff, _ = update_brakes(car, heavy_brake_section, default_env, aero, driver, default_config, dt_s=1.5, v_kph=80.0)
        assert 0.9 <= eff <= 1.15

    def test_duct_opening_affects_cooling(self, heavy_brake_section, default_env, default_config):
        car_open = CarState()
        car_open.brakes.duct_opening = 0.7
        car_open.brakes.temp_front_c = 600.0
        car_closed = CarState()
        car_closed.brakes.duct_opening = 0.25
        car_closed.brakes.temp_front_c = 600.0
        aero = AeroForces()
        driver = DriverIntent()
        update_brakes(car_open, heavy_brake_section, default_env, aero, driver, default_config, dt_s=1.5, v_kph=80.0)
        update_brakes(car_closed, heavy_brake_section, default_env, aero, driver, default_config, dt_s=1.5, v_kph=80.0)
        # More open duct → better cooling → lower temp
        assert car_open.brakes.temp_front_c < car_closed.brakes.temp_front_c


class TestBrakeWear:
    def test_wear_increases(self, heavy_brake_section, default_env, default_config):
        car = CarState()
        aero = AeroForces()
        driver = DriverIntent()
        update_brakes(car, heavy_brake_section, default_env, aero, driver, default_config, dt_s=1.5, v_kph=80.0)
        assert car.brakes.wear_front_pct > 0
        assert car.brakes.wear_rear_pct > 0
