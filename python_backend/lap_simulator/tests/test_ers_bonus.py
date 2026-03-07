"""Unit tests for ERS bonus and per-section energy tracking."""
import math

import pytest

from python_backend.lap_simulator.engine_penalty import compute_ers_bonus
from python_backend.lap_simulator.power_unit import generate_output
from python_backend.lap_simulator.data_types import (
    AeroForces,
    CircuitConfig,
    DriverIntent,
    EngineMapName,
    EngineMapParams,
    EnvContext,
    PUState,
    SectionContext,
    SectionKind,
)


@pytest.fixture
def straight_section():
    return SectionContext(
        section_id="s01",
        name="Main Straight",
        kind=SectionKind.STRAIGHT,
        length_m=800.0,
        v_base_kph=320.0,
        braking_energy_mj=0.1,
    )


@pytest.fixture
def corner_section():
    return SectionContext(
        section_id="c01",
        name="Chicane",
        kind=SectionKind.MEDIUM_CORNER,
        length_m=150.0,
        v_base_kph=180.0,
        braking_energy_mj=1.2,
    )


@pytest.fixture
def base_config():
    cfg = CircuitConfig(
        total_straight_length_m=4000.0,
        max_engine_bonus_ms=-1.5,
        ers_power_coeff=0.02,
        estimated_direct_drive_mj=4.0,
        battery_deploy_limit_mj=4.0,
    )
    cfg.pu_maps = {
        EngineMapName.STANDARD: EngineMapParams(
            name=EngineMapName.STANDARD,
            heat_load_kw=260.0,
            torque_ramp=0.6,
            cooling_share=0.5,
            ers_output_kw=140.0,
            mguh_direct_ratio=0.5,
            mguh_power_kw=70.0,
        )
    }
    return cfg


@pytest.fixture
def default_env():
    return EnvContext()


@pytest.fixture
def default_aero():
    return AeroForces(cooling_capacity=50.0)


class TestComputeERSBonus:
    def test_returns_zero_on_corner(self, corner_section, base_config):
        pu = PUState()
        pu.last_section_mguh_direct_mj = 1.0
        pu.last_section_battery_mj = 0.5
        assert compute_ers_bonus(pu, corner_section, base_config) == 0.0

    def test_negative_bonus_scaled_by_energy(self, straight_section, base_config):
        pu = PUState()
        pu.last_section_mguh_direct_mj = 1.0
        pu.last_section_battery_mj = 0.5
        bonus = compute_ers_bonus(pu, straight_section, base_config)
        expected_raw = -(1.5) * base_config.ers_power_coeff
        section_fraction = straight_section.length_m / base_config.total_straight_length_m
        expected = max(
            expected_raw,
            (base_config.max_engine_bonus_ms / 1000.0) * section_fraction,
        )
        assert math.isclose(bonus, expected, rel_tol=1e-6)

    def test_bonus_clamped_by_section_fraction(self, straight_section, base_config):
        pu = PUState()
        straight_section.length_m = 200.0  # 5% of total straight length
        pu.last_section_mguh_direct_mj = 5.0
        pu.last_section_battery_mj = 5.0
        unclamped = -(10.0) * base_config.ers_power_coeff
        section_fraction = straight_section.length_m / base_config.total_straight_length_m
        max_bonus = (base_config.max_engine_bonus_ms / 1000.0) * section_fraction
        result = compute_ers_bonus(pu, straight_section, base_config)
        assert result > unclamped  # clamp makes it less negative
        assert math.isclose(result, max_bonus, rel_tol=1e-6)

    def test_zero_when_no_energy_used(self, straight_section, base_config):
        pu = PUState()
        bonus = compute_ers_bonus(pu, straight_section, base_config)
        assert bonus == 0.0


class TestPowerUnitSectionTracking:
    def test_last_section_fields_populated(self, straight_section, base_config, default_env, default_aero):
        pu = PUState(active_map=EngineMapName.STANDARD, ers_energy_mj=4.0)
        driver = DriverIntent()
        pu, _ = generate_output(
            pu_state=pu,
            driver_intent=driver,
            aero_forces=default_aero,
            section=straight_section,
            env=default_env,
            config=base_config,
            dt_estimate_s=2.0,
        )
        assert pu.last_section_driver_request_mj > 0.0
        assert pu.last_section_mguh_direct_mj >= 0.0
        assert pu.last_section_battery_mj >= 0.0
        total_used = pu.last_section_mguh_direct_mj + pu.last_section_battery_mj
        assert total_used <= pu.last_section_driver_request_mj + 1e-6

    def test_recharge_map_uses_mguh_only(self, straight_section, base_config, default_env, default_aero):
        base_config.pu_maps[EngineMapName.RECHARGE] = EngineMapParams(
            name=EngineMapName.RECHARGE,
            heat_load_kw=200.0,
            torque_ramp=0.4,
            cooling_share=0.55,
            ers_output_kw=40.0,
            mguh_direct_ratio=0.8,
            mguh_power_kw=50.0,
        )
        pu = PUState(active_map=EngineMapName.RECHARGE, ers_energy_mj=0.2)
        driver = DriverIntent(ers_deploy_request=True)
        pu, _ = generate_output(
            pu_state=pu,
            driver_intent=driver,
            aero_forces=default_aero,
            section=straight_section,
            env=default_env,
            config=base_config,
            dt_estimate_s=2.0,
        )
        # Recharge map should avoid draining the battery when SOC is low
        assert pu.last_section_battery_mj <= pu.last_section_mguh_direct_mj
        assert pu.last_section_driver_request_mj >= pu.last_section_mguh_direct_mj
