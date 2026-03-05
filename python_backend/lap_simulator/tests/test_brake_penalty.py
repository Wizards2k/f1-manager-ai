"""
Test suite for Brake Penalty System.

Tests brake duct and fade penalties on sections with significant braking energy.
"""
import pytest
from python_backend.lap_simulator.brake_penalty import (
    compute_brake_penalty,
    _compute_duct_penalty,
    _compute_fade_penalty,
    validate_brake_coefficient,
    get_brake_penalty_summary,
)
from python_backend.lap_simulator.data_types import (
    BrakeState,
    CarState,
    CircuitConfig,
    SectionContext,
    BrakeSystemParams,
    SectionKind,
)


class TestBrakePenalty:
    """Test brake penalty calculations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.car_state = CarState(car_id="test")
        self.car_state.brakes = BrakeState()
        
        # Create a section with significant braking energy
        self.braking_section = SectionContext(
            section_id="sec_08",
            name="Turn 4",
            kind=SectionKind.SLOW_CORNER,
            length_m=145.1,
            v_base_kph=150,
            v_entry_kph=320,
            v_exit_kph=80,
            braking_energy_mj=2.558,  # High energy braking
        )
        
        # Create a section with minimal braking
        self.straight_section = SectionContext(
            section_id="sec_01",
            name="Main Straight",
            kind=SectionKind.STRAIGHT,
            length_m=500.0,
            v_base_kph=325,
            v_entry_kph=320,
            v_exit_kph=330,
            braking_energy_mj=0.01,  # Minimal braking
        )
        
        # Create circuit config with brake parameters
        self.config = CircuitConfig()
        self.config.brake_params = BrakeSystemParams()
        self.config.brake_profile = {
            "duct_recommendation": {
                "min_open": 0.225,
                "max_open": 0.675,
            }
        }
        self.config.brake_critical_sections = [
            {"id": "sec_08", "name": "Turn 4", "braking_energy_mj": 2.558}
        ]
    
    def test_brake_only_on_significant_sections(self):
        """Test that brake penalty is only applied on sections with significant braking."""
        # Test on braking section
        penalty = compute_brake_penalty(self.car_state, self.braking_section, self.config)
        assert penalty >= 0.0, "Penalty should be non-negative"
        
        # Test on straight section (should be zero)
        penalty = compute_brake_penalty(self.car_state, self.straight_section, self.config)
        assert penalty == 0.0, "Penalty should be zero on sections with minimal braking"
    
    def test_duct_penalty_optimal_range(self):
        """Test that optimal duct opening produces no penalty."""
        # Set duct opening within recommended range
        self.car_state.brakes.duct_opening = 0.4  # Within 0.225-0.675
        
        penalty = _compute_duct_penalty(self.car_state.brakes, self.config)
        assert penalty == 0.0, "Optimal duct opening should produce no penalty"
    
    def test_duct_penalty_too_closed(self):
        """Test penalty for duct opening too closed (overheating risk)."""
        # Set duct opening below minimum
        self.car_state.brakes.duct_opening = 0.1  # Below 0.225
        
        penalty = _compute_duct_penalty(self.car_state.brakes, self.config)
        expected = (0.225 - 0.1) * 0.3  # overheat_coeff = 0.3
        assert abs(penalty - expected) < 0.001, f"Expected {expected}, got {penalty}"
    
    def test_duct_penalty_too_open(self):
        """Test penalty for duct opening too open (aerodynamic drag)."""
        # Set duct opening above maximum
        self.car_state.brakes.duct_opening = 0.8  # Above 0.675
        
        penalty = _compute_duct_penalty(self.car_state.brakes, self.config)
        expected = (0.8 - 0.675) * 0.2  # overcool_coeff = 0.2
        assert abs(penalty - expected) < 0.001, f"Expected {expected}, got {penalty}"
    
    def test_fade_penalty_no_fade(self):
        """Test that temperatures below fade threshold produce no penalty."""
        # Set temperatures below fade thresholds
        self.car_state.brakes.temp_front_c = 800  # Below 850
        self.car_state.brakes.temp_rear_c = 700   # Below 750
        
        penalty = _compute_fade_penalty(self.car_state.brakes, self.config, self.braking_section)
        assert penalty == 0.0, "Temperatures below fade threshold should produce no penalty"
    
    def test_fade_penalty_front_fade(self):
        """Test penalty for front brake fade."""
        # Set front temperature above fade threshold
        self.car_state.brakes.temp_front_c = 920  # 70°C above 850 threshold
        self.car_state.brakes.temp_rear_c = 700   # Below threshold
        
        # Front fade level: 70°C / 15°C per unit = 4.67 units
        # Critical section multiplier: 1.5x
        penalty = _compute_fade_penalty(self.car_state.brakes, self.config, self.braking_section)
        expected = 4.67 * 0.05 * 1.5  # fade_coeff = 0.05, critical multiplier = 1.5
        assert abs(penalty - expected) < 0.01, f"Expected {expected}, got {penalty}"
    
    def test_fade_penalty_rear_fade(self):
        """Test penalty for rear brake fade."""
        # Set rear temperature above fade threshold
        self.car_state.brakes.temp_front_c = 800  # Below threshold
        self.car_state.brakes.temp_rear_c = 820   # 70°C above 750 threshold
        
        # Rear fade level: 70°C / 15°C per unit = 4.67 units
        # Critical section multiplier: 1.5x
        penalty = _compute_fade_penalty(self.car_state.brakes, self.config, self.braking_section)
        expected = 4.67 * 0.05 * 1.5  # fade_coeff = 0.05, critical multiplier = 1.5
        assert abs(penalty - expected) < 0.01, f"Expected {expected}, got {penalty}"
    
    def test_fade_penalty_critical_section_multiplier(self):
        """Test that critical sections have higher fade penalty."""
        # Set temperature above threshold
        self.car_state.brakes.temp_front_c = 920  # 70°C above threshold
        
        # Test on critical section (should have 1.5x multiplier)
        penalty_critical = _compute_fade_penalty(
            self.car_state.brakes, self.config, self.braking_section
        )
        
        # Test on non-critical section
        non_critical_section = SectionContext(
            section_id="sec_99",
            name="Medium Corner",
            kind=SectionKind.MEDIUM_CORNER,
            length_m=100.0,
            v_base_kph=150,
            v_entry_kph=200,
            v_exit_kph=100,
            braking_energy_mj=1.0,
        )
        penalty_normal = _compute_fade_penalty(
            self.car_state.brakes, self.config, non_critical_section
        )
        
        # Critical section should have 1.5x penalty
        assert abs(penalty_critical - penalty_normal * 1.5) < 0.01, \
            f"Critical section penalty should be 1.5x normal penalty"
    
    def test_combined_penalties(self):
        """Test combined duct and fade penalties."""
        # Set both duct and temperature issues
        self.car_state.brakes.duct_opening = 0.1  # Too closed
        self.car_state.brakes.temp_front_c = 920  # Front fade
        
        penalty = compute_brake_penalty(self.car_state, self.braking_section, self.config)
        
        # Should include both duct penalty and fade penalty
        duct_penalty = (0.225 - 0.1) * 0.3  # 0.0375s
        fade_penalty = (920 - 850) / 15 * 0.05 * 1.5  # 0.35s (with critical multiplier)
        expected = duct_penalty + fade_penalty
        
        assert abs(penalty - expected) < 0.01, f"Expected {expected}, got {penalty}"
    
    def test_coefficient_validation(self):
        """Test brake coefficient validation."""
        # Test with correct coefficients
        assert validate_brake_coefficient(
            duct_coeff=0.2,
            fade_coeff=0.05,
            expected_duct_penalty_s=0.02,
            expected_fade_penalty_s=0.05,
        ), "Valid coefficients should pass validation"
        
        # Test with incorrect coefficients
        assert not validate_brake_coefficient(
            duct_coeff=1.0,  # Wrong coefficient
            fade_coeff=0.3,
            expected_duct_penalty_s=0.08,
            expected_fade_penalty_s=0.3,
        ), "Invalid coefficients should fail validation"
    
    def test_penalty_summary(self):
        """Test brake penalty summary for telemetry."""
        # Set both duct and temperature issues
        self.car_state.brakes.duct_opening = 0.1  # Too closed
        self.car_state.brakes.temp_front_c = 920  # Front fade
        
        summary = get_brake_penalty_summary(self.car_state, self.config)
        
        assert "duct_penalty_s" in summary
        assert "fade_penalty_s" in summary
        assert "total_penalty_s" in summary
        
        # Check values
        assert summary["duct_penalty_s"] > 0.0, "Should have duct penalty"
        assert summary["fade_penalty_s"] > 0.0, "Should have fade penalty"
        assert summary["total_penalty_s"] == summary["duct_penalty_s"] + summary["fade_penalty_s"], \
            "Total should equal sum of components"
    
    def test_realistic_baku_scenario(self):
        """Test realistic scenario on Baku critical section."""
        # Baku Turn 4 scenario: aggressive braking with suboptimal setup
        self.car_state.brakes.duct_opening = 0.15  # Too closed for Baku
        self.car_state.brakes.temp_front_c = 880   # Hot front brakes
        self.car_state.brakes.temp_rear_c = 760    # Warm rear brakes
        
        # Use actual Baku critical section
        penalty = compute_brake_penalty(self.car_state, self.braking_section, self.config)
        
        # Should be moderate penalty on critical section
        assert penalty > 0.1, f"Should have moderate penalty on critical section, got {penalty}"
        assert penalty < 1.0, f"Penalty should be reasonable, got {penalty}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
