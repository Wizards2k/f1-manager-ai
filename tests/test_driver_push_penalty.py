"""
Test suite for driver push penalty system.

Validates:
- Monotonicity across push levels
- Skill modulation effects
- Quali vs Race differences
- Band width vs costanza relationship
- Determinism of RNG
"""
import pytest
from python_backend.lap_simulator.push_penalty import compute_push_penalty, PENALTY_CENTERS, MIN_GAP_BETWEEN_LEVELS
from python_backend.lap_simulator.data_types import CircuitConfig


class TestPushPenalty:
    """Test driver push penalty calculation."""
    
    def setup_method(self):
        """Set up test configuration."""
        self.config = CircuitConfig(
            circuit_length_m=5000.0,
            push_penalty_centers=PENALTY_CENTERS,
            push_penalty_base_width=0.08,
            push_penalty_width_decay=0.008
        )
    
    def test_monotonicity_decreasing_penalty(self):
        """Test that penalty decreases monotonically from push=1 to push=10."""
        # Verstappen skills (high)
        penalty_1 = compute_push_penalty(
            1, 96, 96, 95, True, "suzuka", "verstappen", 1, self.config
        )
        penalty_5 = compute_push_penalty(
            5, 96, 96, 95, True, "suzuka", "verstappen", 1, self.config
        )
        penalty_9 = compute_push_penalty(
            9, 96, 96, 95, True, "suzuka", "verstappen", 1, self.config
        )
        penalty_10 = compute_push_penalty(
            10, 96, 96, 95, True, "suzuka", "verstappen", 1, self.config
        )
        
        assert penalty_1 > penalty_5 > penalty_9 > penalty_10 == 0.0
    
    def test_minimum_gap_between_levels(self):
        """Test that adjacent levels have minimum gap in centers."""
        # Due to floating point precision, use slightly smaller threshold
        min_gap = MIN_GAP_BETWEEN_LEVELS - 0.0001
        
        for level in range(1, 9):
            center_current = self.config.push_penalty_centers[level - 1]
            center_next = self.config.push_penalty_centers[level]
            assert abs(center_current - center_next) >= min_gap
    
    def test_skill_modulation_qualifying(self):
        """Test that higher qualification skill reduces penalty in quali."""
        # Low skill driver
        penalty_low = compute_push_penalty(
            5, 70, 80, 80, True, "test", "low_skill", 1, self.config
        )
        
        # High skill driver
        penalty_high = compute_push_penalty(
            5, 95, 80, 80, True, "test", "high_skill", 1, self.config
        )
        
        # High skill driver should have less penalty
        assert penalty_high < penalty_low
    
    def test_skill_modulation_race(self):
        """Test that higher race skill reduces penalty in race."""
        # Low skill driver
        penalty_low = compute_push_penalty(
            5, 80, 70, 80, False, "test", "low_skill", 1, self.config
        )
        
        # High skill driver
        penalty_high = compute_push_penalty(
            5, 80, 95, 80, False, "test", "high_skill", 1, self.config
        )
        
        # High skill driver should have less penalty
        assert penalty_high < penalty_low
    
    def test_quali_vs_race_difference(self):
        """Test that quali and race modes use different skills."""
        # Use a driver with more dramatic skill difference to overcome random variation
        # High quali skill, low race skill
        quali_higher_count = 0
        for lap in range(1, 11):  # More samples
            q = compute_push_penalty(
                5, 95, 60, 80, True, "test", "driver", lap, self.config
            )
            r = compute_push_penalty(
                5, 95, 60, 80, False, "test", "driver", lap, self.config
            )
            if r > q:
                quali_higher_count += 1
        
        # At least 6 out of 10 should show race > quali
        assert quali_higher_count >= 6
    
    def test_costanza_band_width(self):
        """Test that higher costanza produces tighter bands."""
        # Low costanza driver (inconsistent)
        penalty_low_consistency = []
        for lap in range(1, 11):  # More laps to get better statistical measure
            penalty = compute_push_penalty(
                3, 80, 80, 60, True, "test", "low_consistency", lap, self.config
            )
            penalty_low_consistency.append(penalty)
        
        # High costanza driver (consistent)
        penalty_high_consistency = []
        for lap in range(1, 11):
            penalty = compute_push_penalty(
                3, 80, 80, 95, True, "test", "high_consistency", lap, self.config
            )
            penalty_high_consistency.append(penalty)
        
        # High consistency driver should have less variation on average
        var_low = max(penalty_low_consistency) - min(penalty_low_consistency)
        var_high = max(penalty_high_consistency) - min(penalty_high_consistency)
        
        # Allow for some randomness, but expect trend
        # Test that average variation is smaller for high consistency
        avg_var_low = sum(abs(p - sum(penalty_low_consistency)/len(penalty_low_consistency)) 
                         for p in penalty_low_consistency) / len(penalty_low_consistency)
        avg_var_high = sum(abs(p - sum(penalty_high_consistency)/len(penalty_high_consistency)) 
                          for p in penalty_high_consistency) / len(penalty_high_consistency)
        
        assert avg_var_low > avg_var_high
    
    def test_determinism_same_inputs(self):
        """Test that same inputs produce identical results."""
        penalty1 = compute_push_penalty(
            5, 85, 85, 85, True, "monza", "test_driver", 3, self.config
        )
        penalty2 = compute_push_penalty(
            5, 85, 85, 85, True, "monza", "test_driver", 3, self.config
        )
        
        assert penalty1 == penalty2
    
    def test_determinism_different_laps(self):
        """Test that different lap numbers produce different results within expected range."""
        penalty_lap1 = compute_push_penalty(
            5, 85, 85, 85, True, "monza", "test_driver", 1, self.config
        )
        penalty_lap2 = compute_push_penalty(
            5, 85, 85, 85, True, "monza", "test_driver", 2, self.config
        )
        
        # Should be different but within reasonable range of each other
        assert penalty_lap1 != penalty_lap2
        assert abs(penalty_lap1 - penalty_lap2) < 0.1  # Should be close
    
    def test_push_level_10_zero_penalty(self):
        """Test that push level 10 always produces zero penalty."""
        penalty = compute_push_penalty(
            10, 50, 50, 50, True, "test", "driver", 1, self.config
        )
        
        assert penalty == 0.0
    
    def test_invalid_push_level(self):
        """Test that invalid push levels raise errors."""
        with pytest.raises(ValueError):
            compute_push_penalty(
                0, 80, 80, 80, True, "test", "driver", 1, self.config
            )
        
        with pytest.raises(ValueError):
            compute_push_penalty(
                11, 80, 80, 80, True, "test", "driver", 1, self.config
            )
    
    def test_verstappen_vs_rookie_comparison(self):
        """Test realistic penalty difference between top driver and rookie."""
        # Verstappen (top skills)
        penalty_verstappen = compute_push_penalty(
            3, 96, 96, 95, True, "suzuka", "verstappen", 1, self.config
        )
        
        # Rookie (lower skills)
        penalty_rookie = compute_push_penalty(
            3, 75, 80, 65, True, "suzuka", "rookie", 1, self.config
        )
        
        # Verstappen should have significantly less penalty
        assert penalty_verstappen < penalty_rookie
        # Allow for some random variation, but expect meaningful difference
        assert (penalty_rookie - penalty_verstappen) > 0.05  # At least 0.05s difference


if __name__ == "__main__":
    pytest.main([__file__])
