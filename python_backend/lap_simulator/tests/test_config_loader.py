"""Tests for config_loader – loading circuit configs from JSON files."""
import pytest
from pathlib import Path

from lap_simulator.config_loader import load_circuit_config
from lap_simulator.data_types import (
    SectionKind,
    TyreCompound,
    EngineMapName,
)


@pytest.fixture
def project_root():
    return Path(__file__).resolve().parent.parent.parent.parent


@pytest.fixture
def monza_config(project_root):
    return load_circuit_config("it-1922_monza", project_root=project_root)


class TestCircuitLoading:
    def test_circuit_id(self, monza_config):
        assert monza_config.circuit_id == "it-1922_monza"

    def test_circuit_name(self, monza_config):
        assert "Monza" in monza_config.circuit_name

    def test_sections_loaded(self, monza_config):
        assert len(monza_config.sections) >= 10

    def test_section_kinds(self, monza_config):
        kinds = {s.kind for s in monza_config.sections}
        assert SectionKind.STRAIGHT in kinds
        assert SectionKind.FAST_CORNER in kinds or SectionKind.SLOW_CORNER in kinds

    def test_section_lengths_positive(self, monza_config):
        for s in monza_config.sections:
            assert s.length_m > 0, f"Section {s.section_id} has non-positive length"

    def test_section_v_base_positive(self, monza_config):
        for s in monza_config.sections:
            assert s.v_base_kph > 0, f"Section {s.section_id} has non-positive v_base"

    def test_circuit_length(self, monza_config):
        assert monza_config.circuit_length_m > 5000

    def test_sector_markers(self, monza_config):
        assert len(monza_config.sector_markers_m) >= 2


class TestTyreParamsLoading:
    def test_compounds_loaded(self, monza_config):
        assert len(monza_config.tyre_params) >= 6

    def test_c3_exists(self, monza_config):
        assert TyreCompound.C3 in monza_config.tyre_params

    def test_c3_base_grip(self, monza_config):
        c3 = monza_config.tyre_params[TyreCompound.C3]
        assert c3.base_grip == pytest.approx(1.0)

    def test_c5_higher_grip_than_c1(self, monza_config):
        c1 = monza_config.tyre_params[TyreCompound.C1]
        c5 = monza_config.tyre_params[TyreCompound.C5]
        assert c5.base_grip > c1.base_grip

    def test_thermal_windows_ordered(self, monza_config):
        for tc, params in monza_config.tyre_params.items():
            assert params.temp_window_surface_c[0] < params.temp_window_surface_c[1]
            assert params.temp_window_surface_c[1] < params.temp_window_surface_c[2]


class TestBrakeParamsLoading:
    def test_fade_thresholds(self, monza_config):
        bp = monza_config.brake_params
        assert bp.fade_threshold_front_c > 700
        assert bp.fade_threshold_rear_c > 600

    def test_front_higher_capacity(self, monza_config):
        bp = monza_config.brake_params
        assert bp.heat_capacity_front >= bp.heat_capacity_rear


class TestPULoading:
    def test_maps_loaded(self, monza_config):
        assert len(monza_config.pu_maps) >= 4

    def test_race_map(self, monza_config):
        race = monza_config.pu_maps[EngineMapName.RACE]
        assert race.heat_load_kw > 0
        assert race.ers_output_kw > 0

    def test_qualify_more_power(self, monza_config):
        race = monza_config.pu_maps[EngineMapName.RACE]
        qual = monza_config.pu_maps[EngineMapName.QUALIFY]
        assert qual.torque_ramp > race.torque_ramp

    def test_reliability_params(self, monza_config):
        rel = monza_config.pu_reliability
        assert rel.ice_temp_warning_c < rel.ice_temp_critical_c
        assert rel.ers_temp_warning_c < rel.ers_temp_critical_c


class TestDamageLoading:
    def test_damage_coeffs(self, monza_config):
        dc = monza_config.damage_coeffs
        assert dc.susp_shock_threshold > 0
        assert dc.floor_shock_threshold > 0


class TestFallbackToGlobal:
    def test_unknown_circuit_uses_global(self, project_root):
        """A non-existent circuit should still load with global defaults."""
        cfg = load_circuit_config("xx-0000_nonexistent", project_root=project_root)
        # No sections (no telemetry), but params should be loaded
        assert len(cfg.tyre_params) >= 6
        assert len(cfg.pu_maps) >= 4
