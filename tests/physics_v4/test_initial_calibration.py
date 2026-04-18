from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYTHON_BACKEND = ROOT / "python_backend"
if str(PYTHON_BACKEND) not in sys.path:
    sys.path.insert(0, str(PYTHON_BACKEND))

from lap_simulator.physics_v4 import (  # noqa: E402
    DEFAULT_CALIBRATION_CIRCUIT_ID,
    DEFAULT_CALIBRATION_DRIVER_NAME,
    DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT,
    DEFAULT_CALIBRATION_SESSION,
    DEFAULT_CALIBRATION_TEAM_NAME,
    DEFAULT_CALIBRATION_TYRE_COMPOUND,
    DEFAULT_CALIBRATION_WEATHER,
    build_initial_calibration_setup,
    run_initial_calibration_benchmark,
)


class TestInitialCalibrationBenchmark:
    """Regression test per il benchmark iniziale McLaren/Norris."""

    def test_build_initial_calibration_setup_uses_reference_defaults(self):
        setup = build_initial_calibration_setup()

        assert setup.spec.circuit_id == DEFAULT_CALIBRATION_CIRCUIT_ID
        assert setup.spec.team_name == DEFAULT_CALIBRATION_TEAM_NAME
        assert setup.spec.driver_name == DEFAULT_CALIBRATION_DRIVER_NAME
        assert setup.spec.session == DEFAULT_CALIBRATION_SESSION
        assert setup.spec.weather == DEFAULT_CALIBRATION_WEATHER
        assert setup.spec.tyre_compound == DEFAULT_CALIBRATION_TYRE_COMPOUND
        assert setup.physics_setup.session == DEFAULT_CALIBRATION_SESSION
        assert setup.physics_setup.car.tyres.compound == DEFAULT_CALIBRATION_TYRE_COMPOUND
        assert setup.team is not None
        assert setup.driver is not None
        assert setup.reference_setup["front_wing"] > 0
        assert setup.reference_setup["rear_wing"] > 0

    def test_run_initial_calibration_benchmark_returns_traceable_result(self):
        result = run_initial_calibration_benchmark(verbose=False)

        assert result["lap_time_s"] > 0.0
        assert result["session"] == DEFAULT_CALIBRATION_SESSION
        assert result["driver"] == DEFAULT_CALIBRATION_DRIVER_NAME
        assert result["setup"]["tyres"]["compound"] == DEFAULT_CALIBRATION_TYRE_COMPOUND
        assert result["aero_calibration"] is not None
        assert result["initial_calibration"]["resolved_driver_name"] == DEFAULT_CALIBRATION_DRIVER_NAME
        assert result["initial_calibration"]["resolved_team_name"]
        assert result["initial_calibration"]["reference_setup"]["front_wing"] > 0
        assert result["initial_calibration"]["benchmark_context"]["run_plan"]["push_level"] == 10.0
        assert result["initial_calibration"]["benchmark_context"]["run_plan"]["engine_map"] == "QUALIFY"
        assert result["initial_calibration"]["benchmark_context"]["run_plan"]["ers_mode"] == "OVERTAKE"
        assert result["initial_calibration"]["benchmark_context"]["physics_modes"]["ice_mode"] == "aggressive"
        assert result["initial_calibration"]["benchmark_context"]["physics_modes"]["ers_deploy_mode"] == "quali_deploy"
        assert result["initial_calibration"]["driver_skill"]["quali_skill"] >= 1.0
        assert result["initial_calibration"]["car_configuration"]["power_unit"]["ice_mode"] == "aggressive"
        assert result["initial_calibration"]["car_configuration"]["power_unit"]["ers_deploy_mode"] == "quali_deploy"

    def test_monza_microsector_report_has_thirteen_sections(self):
        from scripts.monza_q_benchmark import _load_reference_payload, build_monza_comparison_report  # noqa: E402

        result = run_initial_calibration_benchmark(verbose=False)
        reference_payload = _load_reference_payload(DEFAULT_CALIBRATION_CIRCUIT_ID)
        report = build_monza_comparison_report(result, reference_payload)

        assert report["summary"]["circuit_id"] == DEFAULT_CALIBRATION_CIRCUIT_ID
        assert len(report["sections"]) == 13
        assert report["summary"]["reference_lap_time_s"] > 0.0
        assert report["summary"]["simulated_lap_time_s"] > report["summary"]["reference_lap_time_s"]
        assert report["summary"]["microsector_margin_threshold_pct"] == pytest.approx(
            DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT
        )
        assert report["validation"]["threshold_pct"] == pytest.approx(DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT)
        assert all("time_margin_pct" in section for section in report["sections"])
        assert report["summary"]["largest_abs_delta_section"]["section_id"] == "sec_02"

    def test_microsector_validation_uses_two_percent_threshold(self):
        from scripts.monza_q_benchmark import _validate_microsector_margins  # noqa: E402

        rows = [
            {"section_id": "sec_01", "name": "Section 1", "time_margin_pct": 0.01},
            {"section_id": "sec_02", "name": "Section 2", "time_margin_pct": 0.03},
        ]

        validation = _validate_microsector_margins(rows)

        assert validation["threshold_pct"] == pytest.approx(DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT)
        assert validation["all_sections_within_threshold"] is False
        assert validation["sections_over_threshold"] == ["sec_02"]
        assert validation["worst_section"]["section_id"] == "sec_02"

    def test_benchmark_spec_can_be_overridden(self):
        from lap_simulator.physics_v4 import InitialCalibrationSpec  # noqa: E402

        spec = InitialCalibrationSpec(circuit_id="mc-1929_monaco", tyre_compound="C3")
        setup = build_initial_calibration_setup(spec)

        assert setup.spec.circuit_id == "mc-1929_monaco"
        assert setup.physics_setup.circuit == "mc-1929_monaco"
        assert setup.physics_setup.car.tyres.compound == "C3"
        assert setup.reference_setup["front_wing"] != 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
