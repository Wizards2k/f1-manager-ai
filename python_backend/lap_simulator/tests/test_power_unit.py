"""Tests for power_unit – generate_output()."""
import pytest

from lap_simulator.power_unit import generate_output, ICE_BASE_POWER_KW
from lap_simulator.data_types import (
    AeroForces,
    CarState,
    CircuitConfig,
    DriverIntent,
    EngineMapName,
    EngineMapParams,
    EnvContext,
    PUReliabilityParams,
    PUState,
    SectionContext,
    SectionKind,
)


@pytest.fixture
def default_env():
    return EnvContext()


@pytest.fixture
def default_section():
    return SectionContext(
        section_id="s01", name="Straight", kind=SectionKind.STRAIGHT,
        length_m=800.0, v_base_kph=300.0, braking_energy_mj=0.5,
    )


@pytest.fixture
def default_aero():
    return AeroForces(cooling_capacity=50.0)


@pytest.fixture
def default_config():
    cfg = CircuitConfig()
    cfg.pu_maps = {
        EngineMapName.ECONOMY: EngineMapParams(
            name=EngineMapName.ECONOMY, heat_load_kw=220, torque_ramp=0.4,
            cooling_share=0.55, ers_output_kw=80,
        ),
        EngineMapName.STANDARD: EngineMapParams(
            name=EngineMapName.STANDARD, heat_load_kw=260, torque_ramp=0.6,
            cooling_share=0.50, ers_output_kw=120,
        ),
        EngineMapName.RICH: EngineMapParams(
            name=EngineMapName.RICH, heat_load_kw=300, torque_ramp=0.75,
            cooling_share=0.45, ers_output_kw=150,
        ),
        EngineMapName.QUALY: EngineMapParams(
            name=EngineMapName.QUALY, heat_load_kw=330, torque_ramp=0.9,
            cooling_share=0.40, ers_output_kw=170,
        ),
    }
    return cfg


class TestPowerOutput:
    def test_standard_map_produces_power(self, default_section, default_env, default_aero, default_config):
        pu = PUState(active_map=EngineMapName.STANDARD)
        driver = DriverIntent()
        pu, events = generate_output(pu, driver, default_aero, default_section, default_env, default_config, dt_estimate_s=2.0)
        assert pu.ice_power_kw > 0
        assert pu.ers_output_kw > 0

    def test_qualy_more_power_than_economy(self, default_section, default_env, default_aero, default_config):
        pu_eco = PUState(active_map=EngineMapName.ECONOMY)
        pu_qly = PUState(active_map=EngineMapName.QUALY)
        driver = DriverIntent()
        pu_eco, _ = generate_output(pu_eco, driver, default_aero, default_section, default_env, default_config, dt_estimate_s=2.0)
        pu_qly, _ = generate_output(pu_qly, driver, default_aero, default_section, default_env, default_config, dt_estimate_s=2.0)
        assert pu_qly.ice_power_kw > pu_eco.ice_power_kw
        assert pu_qly.ers_output_kw > pu_eco.ers_output_kw


class TestFuelBurn:
    def test_fuel_decreases(self, default_section, default_env, default_aero, default_config):
        pu = PUState(fuel_kg=50.0)
        driver = DriverIntent()
        pu, _ = generate_output(pu, driver, default_aero, default_section, default_env, default_config, dt_estimate_s=2.0)
        assert pu.fuel_kg < 50.0

    def test_fuel_save_mode_burns_less(self, default_section, default_env, default_aero, default_config):
        pu1 = PUState(fuel_kg=50.0)
        pu2 = PUState(fuel_kg=50.0)
        driver_normal = DriverIntent(fuel_save_mode=False)
        driver_save = DriverIntent(fuel_save_mode=True)
        pu1, _ = generate_output(pu1, driver_normal, default_aero, default_section, default_env, default_config, dt_estimate_s=2.0)
        pu2, _ = generate_output(pu2, driver_save, default_aero, default_section, default_env, default_config, dt_estimate_s=2.0)
        assert pu2.fuel_kg > pu1.fuel_kg  # save mode burns less


class TestERSBattery:
    def test_ers_depletes_battery(self, default_section, default_env, default_aero, default_config):
        pu = PUState(ers_energy_mj=4.0)
        driver = DriverIntent()
        pu, _ = generate_output(pu, driver, default_aero, default_section, default_env, default_config, dt_estimate_s=2.0)
        assert pu.ers_energy_mj < 4.0

    def test_empty_battery_limits_output(self, default_section, default_env, default_aero, default_config):
        pu = PUState(ers_energy_mj=0.01)
        driver = DriverIntent()
        pu, _ = generate_output(pu, driver, default_aero, default_section, default_env, default_config, dt_estimate_s=2.0)
        assert pu.ers_output_kw < 120  # limited by battery


class TestThermalDerating:
    def test_ice_derating_at_high_temp(self, default_section, default_env, default_aero, default_config):
        pu = PUState(ice_temp_c=135.0)  # above warning (130)
        driver = DriverIntent()
        pu, events = generate_output(pu, driver, default_aero, default_section, default_env, default_config, dt_estimate_s=2.0)
        assert pu.ice_derating is True
        assert any(e.event_type == "ice_derating" for e in events)

    def test_ers_derating_at_high_temp(self, default_section, default_env, default_aero, default_config):
        pu = PUState(ers_temp_c=95.0)  # above warning (90)
        driver = DriverIntent()
        pu, events = generate_output(pu, driver, default_aero, default_section, default_env, default_config, dt_estimate_s=2.0)
        assert pu.ers_derating is True
        assert any(e.event_type == "ers_derating" for e in events)

    def test_no_derating_at_normal_temp(self, default_section, default_env, default_aero, default_config):
        pu = PUState(ice_temp_c=95.0, ers_temp_c=55.0)
        driver = DriverIntent()
        pu, events = generate_output(pu, driver, default_aero, default_section, default_env, default_config, dt_estimate_s=2.0)
        assert pu.ice_derating is False
        assert pu.ers_derating is False


class TestCriticalEvents:
    def test_fuel_critical_event(self, default_section, default_env, default_aero, default_config):
        pu = PUState(fuel_kg=0.3)
        driver = DriverIntent()
        pu, events = generate_output(pu, driver, default_aero, default_section, default_env, default_config, dt_estimate_s=2.0)
        assert any(e.event_type == "fuel_critical" for e in events)
