"""
Physics V4 Test Suite - Test Suspension

Test per moduli sospensione Physics Engine V4.
Esegui con: pytest tests/physics_v4/test_suspension.py -v
"""

import pytest
import sys
from pathlib import Path

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

from lap_simulator.physics_v4 import (
    SpringDamper, SpringForce,
    AntiRollBar, AntiRollForce,
    RideHeight, RideHeightState,
)


class TestSpringDamper:
    """Test per SpringDamper."""
    
    def test_spring_damper_init(self):
        """Test inizializzazione SpringDamper."""
        sd = SpringDamper()
        assert sd is not None
        assert sd.config['spring_rate'] > 0
        assert sd.config['damping_compression'] > 0
    
    def test_spring_force(self):
        """Test forza molla."""
        sd = SpringDamper()
        displacement_m = 0.05  # 5cm
        force = sd.get_spring_force(displacement_m)
        
        assert force > 0
    
    def test_damper_force(self):
        """Test forza ammortizzatore."""
        sd = SpringDamper()
        velocity_ms = 5.0  # 5 m/s
        force = sd.get_damping_force(velocity_ms)
        
        assert force > 0


class TestAntiRoll:
    """Test per AntiRoll."""
    
    def test_antiroll_init(self):
        """Test inizializzazione AntiRoll."""
        arb = AntiRollBar()
        assert arb is not None
        assert arb.stiffness_nm_rad > 0
    
    def test_antiroll_torque(self):
        """Test coppia ARB."""
        arb = AntiRollBar()
        roll_angle_deg = 2.0  # 2 gradi
        # Convert to radians
        import math
        roll_angle_rad = math.radians(roll_angle_deg)
        torque = arb.calculate_force(roll_angle_rad)
        
        assert torque is not None


class TestRideHeight:
    """Test per RideHeight."""
    
    def test_ride_height_init(self):
        """Test inizializzazione RideHeight."""
        rh = RideHeight()
        assert rh is not None
        assert rh.front > 0
        assert rh.rear > 0
    
    def test_ride_height_adjustment(self):
        """Test regolazione altezza."""
        rh = RideHeight()
        original_front = rh.front
        
        rh.set_ride_height(front=original_front + 0.01, rear=rh.rear)  # +10mm
        assert abs(rh.front - (original_front + 0.01)) < 0.001
    
    def test_ride_height_difference(self):
        """Test differenza altezza."""
        rh = RideHeight()
        state = rh.get_ride_height_state()
        
        assert hasattr(state, 'front')
        assert hasattr(state, 'rear')
        assert hasattr(state, 'rake')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
