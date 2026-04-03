"""
Test: Aero Mapper

Verifica la conversione AeroSetup → PhysicsAeroParams.
"""

import pytest
from python_backend.lap_simulator.physics_v3.aero_mapper import (
    map_aero_setup,
    analyze_aero_setup,
    PhysicsAeroParams,
)
from python_backend.lap_simulator.physics_v3 import constants
from python_backend.lap_simulator.data_types import AeroSetup, EnvContext


class TestAeroMapper:
    """Test aero mapping pipeline."""

    @pytest.fixture
    def test_env(self):
        """Standard environment."""
        return EnvContext(
            air_temp_c=20.0,
            track_temp_c=40.0,
            air_density_kg_m3=1.225,
            wind_speed_kph=5.0,
            rain_intensity=0.0,
            track_rubber_level=0.8,
            water_film_level=0.0,
        )

    def test_aero_mapper_output_type(self, test_env):
        """Verifica che output è PhysicsAeroParams."""
        setup = AeroSetup()
        result = map_aero_setup(setup, test_env)
        assert isinstance(result, PhysicsAeroParams)

    def test_cla_within_range(self, test_env):
        """CLA deve essere entro range fisico."""
        setup = AeroSetup()
        result = map_aero_setup(setup, test_env)
        assert constants.CLA_MIN <= result.CLA <= constants.CLA_MAX

    def test_cda_within_range(self, test_env):
        """CDA deve essere entro range fisico."""
        setup = AeroSetup()
        result = map_aero_setup(setup, test_env)
        assert constants.CDA_MIN <= result.CDA <= constants.CDA_MAX

    def test_aero_balance(self, test_env):
        """Aero balance deve essere 0.4-0.6."""
        setup = AeroSetup()
        result = map_aero_setup(setup, test_env)
        assert 0.40 <= result.aero_balance <= 0.60

    def test_cla_front_rear_sum(self, test_env):
        """CLA_front + CLA_rear == CLA."""
        setup = AeroSetup()
        result = map_aero_setup(setup, test_env)
        expected_rear = result.CLA * (1.0 - result.aero_balance)
        assert abs(result.CLA_rear - expected_rear) < 0.01

    def test_ground_effect_bonus_range(self, test_env):
        """Ground effect bonus 0.85-1.15."""
        setup = AeroSetup()
        result = map_aero_setup(setup, test_env)
        assert 0.85 <= result.ground_effect_bonus <= 1.15

    def test_grip_penalties_range(self, test_env):
        """Grip penalties 0-1."""
        setup = AeroSetup()
        result = map_aero_setup(setup, test_env)
        assert 0.0 <= result.understeer_grip_penalty <= 1.0
        assert 0.0 <= result.oversteer_grip_penalty <= 1.0

    def test_drs_drag_reduction(self, test_env):
        """DRS drag reduction atteso."""
        setup = AeroSetup()
        result_no_drs = map_aero_setup(setup, test_env, drs_active=False)
        result_drs = map_aero_setup(setup, test_env, drs_active=True)
        # CDA_drs < CDA_normal
        assert result_drs.CDA_drs_open < result_no_drs.CDA
        # Reduction è DRS_DRAG_REDUCTION_FACTOR
        expected_drs = result_no_drs.CDA * (1 - constants.DRS_DRAG_REDUCTION_FACTOR)
        assert abs(result_drs.CDA_drs_open - expected_drs) < 0.05

    def test_analyze_aero_setup(self, test_env):
        """Test analisi setup."""
        setup = AeroSetup()
        physics_aero = map_aero_setup(setup, test_env)
        analysis = analyze_aero_setup(setup, physics_aero)

        assert "balance_quality" in analysis
        assert "ground_effect_quality" in analysis
        assert "grip_penalties" in analysis
        assert "setup_quality_score" in analysis

        assert 0.0 <= analysis["setup_quality_score"] <= 1.0

    def test_setup_quality_neutral(self, test_env):
        """Setup neutro deve avere alta qualità."""
        setup = AeroSetup()
        physics_aero = map_aero_setup(setup, test_env)
        analysis = analyze_aero_setup(setup, physics_aero)

        assert analysis["balance_quality"] == "neutral"
        assert analysis["setup_quality_score"] > 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
