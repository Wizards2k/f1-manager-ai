"""Tests for data_types module – dataclass creation, helpers, enums."""
import math
import pytest

from lap_simulator.data_types import (
    AeroForces,
    AeroSetup,
    CarState,
    CircuitConfig,
    CURVE_FACTOR,
    DriverIntent,
    DriverSkills,
    EnvContext,
    SECTION_HEAT_COOL,
    SectionContext,
    SectionKind,
    SectionResult,
    TyreCompound,
    TyreCompoundParams,
    TyreState,
    WheelPosition,
    clamp,
    gaussian,
)


class TestClamp:
    def test_within_range(self):
        assert clamp(5.0, 0.0, 10.0) == 5.0

    def test_below_min(self):
        assert clamp(-1.0, 0.0, 10.0) == 0.0

    def test_above_max(self):
        assert clamp(15.0, 0.0, 10.0) == 10.0

    def test_at_boundary(self):
        assert clamp(0.0, 0.0, 10.0) == 0.0
        assert clamp(10.0, 0.0, 10.0) == 10.0


class TestGaussian:
    def test_peak_at_optimal(self):
        assert gaussian(120.0, 120.0, 7.0) == pytest.approx(1.0)

    def test_symmetric(self):
        g_plus = gaussian(127.0, 120.0, 7.0)
        g_minus = gaussian(113.0, 120.0, 7.0)
        assert g_plus == pytest.approx(g_minus)

    def test_one_sigma_value(self):
        val = gaussian(127.0, 120.0, 7.0)
        expected = math.exp(-0.5)
        assert val == pytest.approx(expected)

    def test_far_from_optimal(self):
        val = gaussian(160.0, 120.0, 7.0)
        assert val < 0.01


class TestEnums:
    def test_section_kind_values(self):
        assert SectionKind.STRAIGHT.value == "Straight"
        assert SectionKind.SLOW_CORNER.value == "SlowCorner"

    def test_tyre_compound_values(self):
        assert TyreCompound.C3.value == "C3"
        assert TyreCompound.INTERMEDIATE.value == "INTERMEDIATE"

    def test_wheel_positions(self):
        assert len(WheelPosition) == 4


class TestSectionContext:
    def test_default_creation(self):
        s = SectionContext(
            section_id="s01",
            name="Main Straight",
            kind=SectionKind.STRAIGHT,
            length_m=500.0,
            v_base_kph=300.0,
        )
        assert s.length_m == 500.0
        assert s.heat_factor == 1.0
        assert s.bumpiness_factor == 0.0


class TestTyreCompoundParams:
    def test_optimal_temps(self):
        p = TyreCompoundParams(
            compound=TyreCompound.C3,
            temp_window_surface_c=[88, 120, 135],
            temp_window_core_c=[85, 97, 108],
        )
        assert p.temp_opt_surface == 120
        assert p.temp_opt_core == 97


class TestCarState:
    def test_default_tyres_created(self):
        cs = CarState()
        assert len(cs.tyres) == 4
        assert WheelPosition.LF in cs.tyres
        assert WheelPosition.RR in cs.tyres

    def test_default_compound(self):
        cs = CarState()
        for t in cs.tyres.values():
            assert t.compound == TyreCompound.C3


class TestLookupTables:
    def test_heat_cool_all_kinds(self):
        for kind in SectionKind:
            assert kind in SECTION_HEAT_COOL

    def test_curve_factor_all_kinds(self):
        for kind in SectionKind:
            assert kind in CURVE_FACTOR

    def test_straight_curve_factor_zero(self):
        assert CURVE_FACTOR[SectionKind.STRAIGHT] == 0.0

    def test_fast_corner_curve_factor_one(self):
        assert CURVE_FACTOR[SectionKind.FAST_CORNER] == 1.0
