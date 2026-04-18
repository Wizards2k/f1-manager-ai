"""
Physics V4 Test Suite - Test Driver

Test per moduli driver Physics Engine V4.
Esegui con: pytest tests/physics_v4/test_driver.py -v
"""

import pytest
import sys
from pathlib import Path

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

# Import driver modules from driver package directly
import lap_simulator.physics_v4.driver as driver
from driver import DrivingLine, BrakingPoint, ThrottleCurve, SteeringInput


class TestDrivingLine:
    """Test per DrivingLine."""
    
    def test_driving_line_init(self):
        """Test inizializzazione DrivingLine."""
        dl = DrivingLine()
        assert dl is not None
    
    def test_driving_line_optimal(self):
        """Test traiettoria ottimale."""
        dl = DrivingLine()
        state = dl.get_state(100.0, 90.0, "optimal")
        
        assert "line_type" in state
        assert "speed_kph" in state
    
    def test_driving_line_inside(self):
        """Test traiettoria inside."""
        dl = DrivingLine()
        state = dl.get_state(100.0, 90.0, "inside")
        
        assert state["line_type"] == "inside"
    
    def test_driving_line_outside(self):
        """Test traiettoria outside."""
        dl = DrivingLine()
        state = dl.get_state(100.0, 90.0, "outside")
        
        assert state["line_type"] == "outside"


class TestBrakingPoint:
    """Test per BrakingPoint."""
    
    def test_braking_point_init(self):
        """Test inizializzazione BrakingPoint."""
        bp = BrakingPoint()
        assert bp is not None
    
    def test_braking_point_distance(self):
        """Test distanza frenata."""
        bp = BrakingPoint()
        state = bp.get_state(150.0, 60.0, 50.0)
        
        assert "braking_point_m" in state
        assert state["braking_point_m"] > 0
    
    def test_braking_point_max_speed(self):
        """Test velocità massima."""
        bp = BrakingPoint()
        state = bp.get_state(150.0, 60.0, 50.0)
        
        assert "max_speed_kph" in state
        assert state["max_speed_kph"] > 0


class TestThrottleCurve:
    """Test per ThrottleCurve."""
    
    def test_throttle_curve_init(self):
        """Test inizializzazione ThrottleCurve."""
        tc = ThrottleCurve()
        assert tc is not None
    
    def test_throttle_curve_position(self):
        """Test posizione gas."""
        tc = ThrottleCurve()
        state = tc.get_state(0.5, 1.5, 3.0)
        
        assert "throttle_position" in state
        assert 0.0 <= state["throttle_position"] <= 1.0
    
    def test_throttle_curve_power(self):
        """Test potenza."""
        tc = ThrottleCurve()
        state = tc.get_state(0.5, 1.5, 3.0)
        
        assert "power_kw" in state
        assert state["power_kw"] > 0


class TestSteeringInput:
    """Test per SteeringInput."""
    
    def test_steering_input_init(self):
        """Test inizializzazione SteeringInput."""
        si = SteeringInput()
        assert si is not None
    
    def test_steering_input_angle(self):
        """Test angolo sterzo."""
        si = SteeringInput()
        state = si.get_state(100.0, 80.0, 0.5, 1.0)
        
        assert "steering_angle_deg" in state
        assert state["steering_angle_deg"] > 0
    
    def test_steering_input_rate(self):
        """Test velocità sterzo."""
        si = SteeringInput()
        state = si.get_state(100.0, 80.0, 0.5, 1.0)
        
        assert "steering_rate_deg_s" in state


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
