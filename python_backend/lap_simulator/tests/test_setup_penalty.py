"""
Unit tests for setup_penalty module.

Tests cover:
  - Penalty/bonus calculation for curves and straights
  - Capping logic per circuit
  - Fallback to defaults when penalty_profile is missing
"""
import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lap_simulator.setup_penalty import (
    SetupPenaltyConfig,
    SetupPenaltyResult,
    load_setup_penalty_config,
    compute_slider_delta,
    compute_curve_penalty,
    compute_drag_penalty,
    clamp_setup_penalties,
    DEFAULT_SETUP_PENALTY_CONFIG,
)


class TestLoadSetupPenaltyConfig:
    """Test config loading with fallback to defaults."""

    def test_load_from_empty_penalty_profile(self):
        """When penalty_profile has no setup_penalty block, use defaults."""
        penalty_profile = {}
        config = load_setup_penalty_config(penalty_profile)
        
        assert config.circuit_category == "balanced"
        assert config.curve_coeffs["fast"] == DEFAULT_SETUP_PENALTY_CONFIG["curve_coeffs"]["fast"]
        assert config.drag_coeff == DEFAULT_SETUP_PENALTY_CONFIG["drag_coeff"]

    def test_load_from_penalty_profile_with_setup_penalty_block(self):
        """When penalty_profile has setup_penalty block, use it."""
        penalty_profile = {
            "setup_penalty": {
                "curve_caps": {"high_df": 2.0, "balanced": 1.2, "low_drag": 0.8},
                "curve_coeffs": {"fast": 0.040, "medium": 0.025, "slow": 0.012},
                "bonus_coeffs": {"fast": -0.008, "medium": -0.006, "slow": -0.004},
                "drag_coeff": 0.005,
                "drag_bonus_coeff": -0.004,
                "drag_caps": {"monza": {"penalty": 1.0, "bonus": -0.10}},
            },
            "setup_penalty_category": "high_df",
        }
        config = load_setup_penalty_config(penalty_profile)
        
        assert config.circuit_category == "high_df"
        assert config.curve_coeffs["fast"] == 0.040
        assert config.drag_coeff == 0.005


class TestComputeSliderDelta:
    """Test slider delta computation."""

    def test_positive_delta(self):
        """Current > ideal → positive delta."""
        delta = compute_slider_delta(current_slider=60, ideal_slider=50)
        assert delta == 10

    def test_negative_delta(self):
        """Current < ideal → negative delta."""
        delta = compute_slider_delta(current_slider=40, ideal_slider=50)
        assert delta == -10

    def test_zero_delta(self):
        """Current == ideal → zero delta."""
        delta = compute_slider_delta(current_slider=50, ideal_slider=50)
        assert delta == 0


class TestComputeCurvePenalty:
    """Test curve penalty/bonus calculation."""

    def test_penalty_for_excess_df(self):
        """More DF than ideal → penalty."""
        config = SetupPenaltyConfig(
            curve_caps={"high_df": 1.5, "balanced": 1.0, "low_drag": 0.6},
            curve_coeffs={"fast": 0.030, "medium": 0.020, "slow": 0.010},
            bonus_coeffs={"fast": -0.007, "medium": -0.005, "slow": -0.003},
            drag_coeff=0.004,
            drag_bonus_coeff=-0.003,
            drag_caps={"default": {"penalty": 0.6, "bonus": -0.04}},
        )
        
        penalty, bonus = compute_curve_penalty(
            df_delta_slider=10,
            curve_speed_category="fast",
            section_weight=0.1,
            config=config,
        )
        
        # 0.030 * 10 * 0.1 = 0.03
        assert penalty == pytest.approx(0.03, abs=1e-6)
        assert bonus == 0.0

    def test_bonus_for_deficit_df(self):
        """Less DF than ideal → bonus (negative penalty)."""
        config = SetupPenaltyConfig(
            curve_caps={"high_df": 1.5, "balanced": 1.0, "low_drag": 0.6},
            curve_coeffs={"fast": 0.030, "medium": 0.020, "slow": 0.010},
            bonus_coeffs={"fast": -0.007, "medium": -0.005, "slow": -0.003},
            drag_coeff=0.004,
            drag_bonus_coeff=-0.003,
            drag_caps={"default": {"penalty": 0.6, "bonus": -0.04}},
        )
        
        penalty, bonus = compute_curve_penalty(
            df_delta_slider=-10,
            curve_speed_category="fast",
            section_weight=0.1,
            config=config,
        )
        
        # -0.007 * 10 * 0.1 = -0.007
        assert penalty == 0.0
        assert bonus == pytest.approx(-0.007, abs=1e-6)

    def test_zero_delta_no_penalty(self):
        """Zero delta → no penalty or bonus."""
        config = SetupPenaltyConfig(
            curve_caps={"high_df": 1.5, "balanced": 1.0, "low_drag": 0.6},
            curve_coeffs={"fast": 0.030, "medium": 0.020, "slow": 0.010},
            bonus_coeffs={"fast": -0.007, "medium": -0.005, "slow": -0.003},
            drag_coeff=0.004,
            drag_bonus_coeff=-0.003,
            drag_caps={"default": {"penalty": 0.6, "bonus": -0.04}},
        )
        
        penalty, bonus = compute_curve_penalty(
            df_delta_slider=0,
            curve_speed_category="fast",
            section_weight=0.1,
            config=config,
        )
        
        assert penalty == 0.0
        assert bonus == 0.0

    def test_medium_corner_coeff(self):
        """Medium corner uses different coefficient."""
        config = SetupPenaltyConfig(
            curve_caps={"high_df": 1.5, "balanced": 1.0, "low_drag": 0.6},
            curve_coeffs={"fast": 0.030, "medium": 0.020, "slow": 0.010},
            bonus_coeffs={"fast": -0.007, "medium": -0.005, "slow": -0.003},
            drag_coeff=0.004,
            drag_bonus_coeff=-0.003,
            drag_caps={"default": {"penalty": 0.6, "bonus": -0.04}},
        )
        
        penalty, bonus = compute_curve_penalty(
            df_delta_slider=10,
            curve_speed_category="medium",
            section_weight=0.1,
            config=config,
        )
        
        # 0.020 * 10 * 0.1 = 0.02
        assert penalty == pytest.approx(0.02, abs=1e-6)


class TestComputeDragPenalty:
    """Test drag penalty/bonus calculation."""

    def test_penalty_for_excess_drag(self):
        """More drag than ideal → penalty."""
        config = SetupPenaltyConfig(
            curve_caps={"high_df": 1.5, "balanced": 1.0, "low_drag": 0.6},
            curve_coeffs={"fast": 0.030, "medium": 0.020, "slow": 0.010},
            bonus_coeffs={"fast": -0.007, "medium": -0.005, "slow": -0.003},
            drag_coeff=0.004,
            drag_bonus_coeff=-0.003,
            drag_caps={"default": {"penalty": 0.6, "bonus": -0.04}},
        )
        
        penalty, bonus = compute_drag_penalty(
            drag_delta_slider=10,
            straight_weight=0.1,
            config=config,
        )
        
        # 0.004 * 10 * 0.1 = 0.004
        assert penalty == pytest.approx(0.004, abs=1e-6)
        assert bonus == 0.0

    def test_bonus_for_deficit_drag(self):
        """Less drag than ideal → bonus."""
        config = SetupPenaltyConfig(
            curve_caps={"high_df": 1.5, "balanced": 1.0, "low_drag": 0.6},
            curve_coeffs={"fast": 0.030, "medium": 0.020, "slow": 0.010},
            bonus_coeffs={"fast": -0.007, "medium": -0.005, "slow": -0.003},
            drag_coeff=0.004,
            drag_bonus_coeff=-0.003,
            drag_caps={"default": {"penalty": 0.6, "bonus": -0.04}},
        )
        
        penalty, bonus = compute_drag_penalty(
            drag_delta_slider=-10,
            straight_weight=0.1,
            config=config,
        )
        
        # -0.003 * 10 * 0.1 = -0.003
        assert penalty == 0.0
        assert bonus == pytest.approx(-0.003, abs=1e-6)


class TestClampSetupPenalties:
    """Test clamping of penalties/bonuses per circuit."""

    def test_clamp_curve_penalty_balanced(self):
        """Curve penalty clamped to balanced cap (1.0s)."""
        config = SetupPenaltyConfig(
            curve_caps={"high_df": 1.5, "balanced": 1.0, "low_drag": 0.6},
            curve_coeffs={"fast": 0.030, "medium": 0.020, "slow": 0.010},
            bonus_coeffs={"fast": -0.007, "medium": -0.005, "slow": -0.003},
            drag_coeff=0.004,
            drag_bonus_coeff=-0.003,
            drag_caps={"default": {"penalty": 0.6, "bonus": -0.04}},
            circuit_category="balanced",
        )
        
        result = clamp_setup_penalties(
            df_curve_penalty=2.0,  # Over cap
            df_curve_bonus=0.0,
            drag_penalty=0.0,
            drag_bonus=0.0,
            config=config,
            circuit_id="default",
        )
        
        assert result.df_curve_penalty_s == pytest.approx(1.0, abs=1e-6)
        assert result.setup_penalty_s == pytest.approx(1.0, abs=1e-6)

    def test_clamp_drag_penalty_monza(self):
        """Drag penalty clamped to Monza cap (0.9s)."""
        config = SetupPenaltyConfig(
            curve_caps={"high_df": 1.5, "balanced": 1.0, "low_drag": 0.6},
            curve_coeffs={"fast": 0.030, "medium": 0.020, "slow": 0.010},
            bonus_coeffs={"fast": -0.007, "medium": -0.005, "slow": -0.003},
            drag_coeff=0.004,
            drag_bonus_coeff=-0.003,
            drag_caps={
                "monza": {"penalty": 0.9, "bonus": -0.08},
                "default": {"penalty": 0.6, "bonus": -0.04},
            },
            circuit_category="balanced",
        )
        
        result = clamp_setup_penalties(
            df_curve_penalty=0.0,
            df_curve_bonus=0.0,
            drag_penalty=1.5,  # Over Monza cap
            drag_bonus=0.0,
            config=config,
            circuit_id="monza",
        )
        
        assert result.drag_penalty_s == pytest.approx(0.9, abs=1e-6)
        assert result.setup_penalty_s == pytest.approx(0.9, abs=1e-6)

    def test_combined_penalties_and_bonuses(self):
        """Combined penalties and bonuses are summed and clamped."""
        config = SetupPenaltyConfig(
            curve_caps={"high_df": 1.5, "balanced": 1.0, "low_drag": 0.6},
            curve_coeffs={"fast": 0.030, "medium": 0.020, "slow": 0.010},
            bonus_coeffs={"fast": -0.007, "medium": -0.005, "slow": -0.003},
            drag_coeff=0.004,
            drag_bonus_coeff=-0.003,
            drag_caps={"default": {"penalty": 0.6, "bonus": -0.04}},
            circuit_category="balanced",
        )
        
        result = clamp_setup_penalties(
            df_curve_penalty=0.5,
            df_curve_bonus=-0.05,
            drag_penalty=0.3,
            drag_bonus=-0.02,
            config=config,
            circuit_id="default",
        )
        
        # Total = 0.5 - 0.05 + 0.3 - 0.02 = 0.73
        assert result.setup_penalty_s == pytest.approx(0.73, abs=1e-6)

    def test_high_df_circuit_cap(self):
        """High DF circuits use higher cap (1.5s)."""
        config = SetupPenaltyConfig(
            curve_caps={"high_df": 1.5, "balanced": 1.0, "low_drag": 0.6},
            curve_coeffs={"fast": 0.030, "medium": 0.020, "slow": 0.010},
            bonus_coeffs={"fast": -0.007, "medium": -0.005, "slow": -0.003},
            drag_coeff=0.004,
            drag_bonus_coeff=-0.003,
            drag_caps={"default": {"penalty": 0.6, "bonus": -0.04}},
            circuit_category="high_df",
        )
        
        result = clamp_setup_penalties(
            df_curve_penalty=2.0,
            df_curve_bonus=0.0,
            drag_penalty=0.0,
            drag_bonus=0.0,
            config=config,
            circuit_id="default",
        )
        
        assert result.df_curve_penalty_s == pytest.approx(1.5, abs=1e-6)

    def test_low_drag_circuit_cap(self):
        """Low drag circuits use lower cap (0.6s)."""
        config = SetupPenaltyConfig(
            curve_caps={"high_df": 1.5, "balanced": 1.0, "low_drag": 0.6},
            curve_coeffs={"fast": 0.030, "medium": 0.020, "slow": 0.010},
            bonus_coeffs={"fast": -0.007, "medium": -0.005, "slow": -0.003},
            drag_coeff=0.004,
            drag_bonus_coeff=-0.003,
            drag_caps={"default": {"penalty": 0.6, "bonus": -0.04}},
            circuit_category="low_drag",
        )
        
        result = clamp_setup_penalties(
            df_curve_penalty=1.0,
            df_curve_bonus=0.0,
            drag_penalty=0.0,
            drag_bonus=0.0,
            config=config,
            circuit_id="default",
        )
        
        assert result.df_curve_penalty_s == pytest.approx(0.6, abs=1e-6)
