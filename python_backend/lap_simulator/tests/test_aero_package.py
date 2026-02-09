"""Tests for aero_package – compute_forces()."""
import pytest

from lap_simulator.aero_package import compute_forces
from lap_simulator.data_types import (
    AeroComponent,
    AeroSetup,
    CarState,
    CircuitConfig,
    CurveProfile,
    EnvContext,
    SectionContext,
    SectionKind,
    SuspensionState,
)


@pytest.fixture
def default_env():
    return EnvContext()


@pytest.fixture
def default_config():
    return CircuitConfig()


@pytest.fixture
def straight_section():
    return SectionContext(
        section_id="s01",
        name="Main Straight",
        kind=SectionKind.STRAIGHT,
        length_m=800.0,
        v_base_kph=300.0,
    )


@pytest.fixture
def slow_corner():
    return SectionContext(
        section_id="s02",
        name="Turn 1",
        kind=SectionKind.SLOW_CORNER,
        length_m=100.0,
        v_base_kph=80.0,
        bumpiness_factor=0.3,
        kerb_severity=0.4,
    )


@pytest.fixture
def balanced_aero():
    """Aero setup with equal front/rear contribution."""
    return AeroSetup(
        front_wing=AeroComponent(name="front_wing", base_downforce=35.0, base_drag=10.0),
        rear_wing=AeroComponent(name="rear_wing", base_downforce=35.0, base_drag=12.0),
        beam_wing=AeroComponent(name="beam_wing", base_downforce=5.0, base_drag=3.0),
        front_floor=AeroComponent(name="front_floor", base_downforce=10.0, base_drag=2.0),
        rear_floor=AeroComponent(name="rear_floor", base_downforce=10.0, base_drag=2.0),
        sidepods=AeroComponent(name="sidepods", base_downforce=6.0, base_drag=4.0, cooling_contribution=50.0),
        engine_cover=AeroComponent(name="engine_cover", base_downforce=2.0, base_drag=1.0, cooling_contribution=20.0),
        b_wing=AeroComponent(name="b_wing", base_downforce=3.0, base_drag=1.5),
        suspension_front=SuspensionState(rigidity=0.6, efficiency=0.8),
        suspension_rear=SuspensionState(rigidity=0.6, efficiency=0.8),
    )


class TestComputeForces:
    def test_returns_aero_forces(self, balanced_aero, straight_section, default_env, default_config):
        car = CarState()
        forces = compute_forces(balanced_aero, straight_section, default_env, car, default_config, v_kph=300.0)
        assert forces.df_total > 0
        assert forces.drag_eff > 0

    def test_df_increases_with_speed(self, balanced_aero, straight_section, default_env, default_config):
        car = CarState()
        forces_slow = compute_forces(balanced_aero, straight_section, default_env, car, default_config, v_kph=100.0)
        forces_fast = compute_forces(balanced_aero, straight_section, default_env, car, default_config, v_kph=300.0)
        assert forces_fast.df_total > forces_slow.df_total

    def test_balanced_aero_near_50(self, balanced_aero, straight_section, default_env, default_config):
        car = CarState()
        forces = compute_forces(balanced_aero, straight_section, default_env, car, default_config, v_kph=250.0)
        assert 0.35 < forces.aero_balance < 0.65

    def test_handling_penalty_low_when_balanced(self, balanced_aero, straight_section, default_env, default_config):
        car = CarState()
        forces = compute_forces(balanced_aero, straight_section, default_env, car, default_config, v_kph=250.0)
        assert forces.handling_penalty < 0.15

    def test_dirty_air_increases_drag(self, balanced_aero, straight_section, default_env, default_config):
        car = CarState()
        clean = compute_forces(balanced_aero, straight_section, default_env, car, default_config, v_kph=250.0, airflow_penalty=0.0)
        dirty = compute_forces(balanced_aero, straight_section, default_env, car, default_config, v_kph=250.0, airflow_penalty=0.5)
        assert dirty.drag_eff > clean.drag_eff

    def test_bump_penalty_on_bumpy_section(self, balanced_aero, slow_corner, default_env, default_config):
        car = CarState()
        forces = compute_forces(balanced_aero, slow_corner, default_env, car, default_config, v_kph=80.0)
        assert forces.bump_penalty > 0

    def test_kerb_impact_on_kerb_section(self, balanced_aero, slow_corner, default_env, default_config):
        car = CarState()
        forces = compute_forces(balanced_aero, slow_corner, default_env, car, default_config, v_kph=80.0)
        assert forces.kerb_impact > 0

    def test_cooling_capacity(self, balanced_aero, straight_section, default_env, default_config):
        car = CarState()
        forces = compute_forces(balanced_aero, straight_section, default_env, car, default_config, v_kph=250.0)
        assert forces.cooling_capacity > 0

    def test_damage_reduces_df(self, balanced_aero, straight_section, default_env, default_config):
        car_clean = CarState()
        car_damaged = CarState()
        car_damaged.damage.df_loss = 0.2
        car_damaged.damage.drag_increase = 0.1

        f_clean = compute_forces(balanced_aero, straight_section, default_env, car_clean, default_config, v_kph=250.0)
        f_damaged = compute_forces(balanced_aero, straight_section, default_env, car_damaged, default_config, v_kph=250.0)
        assert f_damaged.df_total < f_clean.df_total
        assert f_damaged.drag_eff > f_clean.drag_eff


class TestDRS:
    def test_drs_reduces_drag(self, balanced_aero, default_env, default_config):
        balanced_aero.rear_wing.drs_drag_reduction = 0.20
        drs_section = SectionContext(
            section_id="s_drs", name="DRS Zone", kind=SectionKind.STRAIGHT,
            length_m=600.0, v_base_kph=310.0, drs_available=True,
        )
        car = CarState()
        f_no_drs = compute_forces(balanced_aero, drs_section, default_env, car, default_config, v_kph=300.0, drs_active=False)
        f_drs = compute_forces(balanced_aero, drs_section, default_env, car, default_config, v_kph=300.0, drs_active=True)
        assert f_drs.drag_eff < f_no_drs.drag_eff
