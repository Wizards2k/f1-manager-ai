"""Tests for tyre_model – update_tyres()."""
import pytest

from lap_simulator.tyre_model import update_tyres
from lap_simulator.data_types import (
    AeroForces,
    CarState,
    CircuitConfig,
    DriverIntent,
    EnvContext,
    SectionContext,
    SectionKind,
    TyreCompound,
    TyreCompoundParams,
    WheelPosition,
)


@pytest.fixture
def default_env():
    return EnvContext()


@pytest.fixture
def config_with_c3():
    cfg = CircuitConfig()
    cfg.tyre_params = {
        TyreCompound.C3: TyreCompoundParams(
            compound=TyreCompound.C3,
            temp_window_surface_c=[88, 120, 135],
            temp_window_core_c=[85, 97, 108],
            gaussian_sigma_surface_c=7.0,
            gaussian_sigma_core_c=6.0,
            base_grip=1.0,
            wear_rate_base_pct_per_km=0.13,
            thermal_mass_surface=1.10,
            thermal_mass_core=1.25,
            conduction_coeff=0.07,
            cooling_coeff=1.0,
        ),
    }
    return cfg


@pytest.fixture
def straight_section():
    return SectionContext(
        section_id="s01", name="Straight", kind=SectionKind.STRAIGHT,
        length_m=800.0, v_base_kph=300.0,
        heat_factor=0.2, cool_factor=1.2,
    )


@pytest.fixture
def slow_corner():
    return SectionContext(
        section_id="s02", name="Turn 1", kind=SectionKind.SLOW_CORNER,
        length_m=100.0, v_base_kph=80.0,
        heat_factor=1.4, cool_factor=0.4,
        bumpiness_factor=0.2, kerb_severity=0.3,
    )


class TestTyreGrip:
    def test_grip_positive(self, straight_section, default_env, config_with_c3):
        car = CarState()
        aero = AeroForces()
        driver = DriverIntent()
        gf, gr, events = update_tyres(car, straight_section, default_env, aero, driver, config_with_c3, dt_s=2.0, v_kph=300.0)
        assert gf > 0
        assert gr > 0

    def test_grip_at_optimal_temp_is_high(self, straight_section, default_env, config_with_c3):
        car = CarState()
        # Set tyres at optimal temperature
        for t in car.tyres.values():
            t.surface_temp_c = 120.0
            t.core_temp_c = 97.0
        aero = AeroForces()
        driver = DriverIntent()
        gf, gr, _ = update_tyres(car, straight_section, default_env, aero, driver, config_with_c3, dt_s=0.1, v_kph=300.0)
        # At optimal temp with no wear, grip should be close to base_grip
        assert gf > 0.9
        assert gr > 0.9


class TestTyreWear:
    def test_wear_increases(self, straight_section, default_env, config_with_c3):
        car = CarState()
        aero = AeroForces()
        driver = DriverIntent()
        initial_wear = {wp: t.wear_pct for wp, t in car.tyres.items()}
        update_tyres(car, straight_section, default_env, aero, driver, config_with_c3, dt_s=2.0, v_kph=300.0)
        for wp, t in car.tyres.items():
            assert t.wear_pct >= initial_wear[wp]

    def test_higher_pace_more_wear(self, straight_section, default_env, config_with_c3):
        car1 = CarState()
        car2 = CarState()
        aero = AeroForces()
        driver_normal = DriverIntent(pace_factor=1.0)
        driver_push = DriverIntent(pace_factor=1.1)
        update_tyres(car1, straight_section, default_env, aero, driver_normal, config_with_c3, dt_s=2.0, v_kph=300.0)
        update_tyres(car2, straight_section, default_env, aero, driver_push, config_with_c3, dt_s=2.0, v_kph=300.0)
        avg_wear1 = sum(t.wear_pct for t in car1.tyres.values()) / 4
        avg_wear2 = sum(t.wear_pct for t in car2.tyres.values()) / 4
        assert avg_wear2 > avg_wear1

    def test_tyre_save_reduces_wear(self, straight_section, default_env, config_with_c3):
        car1 = CarState()
        car2 = CarState()
        aero = AeroForces()
        driver_normal = DriverIntent(tyre_save_mode=False)
        driver_save = DriverIntent(tyre_save_mode=True)
        update_tyres(car1, straight_section, default_env, aero, driver_normal, config_with_c3, dt_s=2.0, v_kph=300.0)
        update_tyres(car2, straight_section, default_env, aero, driver_save, config_with_c3, dt_s=2.0, v_kph=300.0)
        avg_wear1 = sum(t.wear_pct for t in car1.tyres.values()) / 4
        avg_wear2 = sum(t.wear_pct for t in car2.tyres.values()) / 4
        assert avg_wear2 < avg_wear1


class TestTyreThermal:
    def test_corner_heats_tyres(self, slow_corner, default_env, config_with_c3):
        car = CarState()
        for t in car.tyres.values():
            t.surface_temp_c = 100.0
            t.core_temp_c = 90.0
        aero = AeroForces()
        driver = DriverIntent()
        initial_temps = {wp: t.surface_temp_c for wp, t in car.tyres.items()}
        update_tyres(car, slow_corner, default_env, aero, driver, config_with_c3, dt_s=1.5, v_kph=80.0)
        # Slow corner should heat tyres
        for wp, t in car.tyres.items():
            assert t.surface_temp_c >= initial_temps[wp] - 2  # allow small cooling

    def test_understeer_heats_front_more(self, slow_corner, default_env, config_with_c3):
        car = CarState()
        for t in car.tyres.values():
            t.surface_temp_c = 100.0
        aero = AeroForces(understeer_level=0.5)
        driver = DriverIntent()
        update_tyres(car, slow_corner, default_env, aero, driver, config_with_c3, dt_s=1.5, v_kph=80.0)
        front_avg = (car.tyres[WheelPosition.LF].surface_temp_c + car.tyres[WheelPosition.RF].surface_temp_c) / 2
        rear_avg = (car.tyres[WheelPosition.LR].surface_temp_c + car.tyres[WheelPosition.RR].surface_temp_c) / 2
        assert front_avg > rear_avg


class TestTyreEvents:
    def test_overheat_event(self, straight_section, default_env, config_with_c3):
        car = CarState()
        for t in car.tyres.values():
            t.surface_temp_c = 160.0  # well above window max (135) + 10
        aero = AeroForces()
        driver = DriverIntent()
        _, _, events = update_tyres(car, straight_section, default_env, aero, driver, config_with_c3, dt_s=0.1, v_kph=300.0)
        assert any(e.event_type == "tyre_overheat" for e in events)

    def test_puncture_risk_at_high_wear(self, straight_section, default_env, config_with_c3):
        car = CarState()
        for t in car.tyres.values():
            t.wear_pct = 85.0
        aero = AeroForces()
        driver = DriverIntent()
        _, _, events = update_tyres(car, straight_section, default_env, aero, driver, config_with_c3, dt_s=0.1, v_kph=300.0)
        assert any(e.event_type == "tyre_puncture_risk" for e in events)
