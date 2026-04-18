"""
Physics V4 Test Suite - Test Mass

Test per moduli massa Physics Engine V4.
Esegui con: pytest tests/physics_v4/test_mass.py -v
"""

import pytest
import sys
from pathlib import Path

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

from lap_simulator.physics_v4 import (
    MassDistribution, MassState,
    CenterOfGravity, CGPosition,
    MomentOfInertia, InertiaTensor,
)


class TestMassDistribution:
    """Test per MassDistribution."""
    
    def test_mass_distribution_init(self):
        """Test inizializzazione MassDistribution."""
        md = MassDistribution()
        assert md is not None
        assert md.mass_total > 0
    
    def test_mass_distribution_components(self):
        """Test componenti massa."""
        md = MassDistribution()
        # La massa totale include driver, fuel, etc.
        assert md.mass_driver > 0
        assert md.mass_fuel_current >= 0
    
    def test_mass_distribution_total(self):
        """Test massa totale."""
        md = MassDistribution()
        total = md.mass_total
        
        assert total > 0
        assert abs(total - (md.mass_dry + md.mass_driver + md.mass_fuel_current)) < 0.01


class TestCenterOfGravity:
    """Test per CenterOfGravity."""
    
    def test_center_of_gravity_init(self):
        """Test inizializzazione CenterOfGravity."""
        cog = CenterOfGravity()
        assert cog is not None
    
    def test_center_of_gravity_position(self):
        """Test posizione CG."""
        cog = CenterOfGravity()
        position = cog.get_cg_position()
        
        assert position.x > 0
        assert hasattr(position, 'y')
        assert hasattr(position, 'z')
    
    def test_center_of_gravity_front_rear(self):
        """Test distribuzione front/rear CG."""
        cog = CenterOfGravity()
        front_pct = cog.get_cg_from_rear_axle()
        rear_pct = cog.get_cg_from_front_axle()
        
        assert front_pct > 0
        assert rear_pct > 0


class TestInertia:
    """Test per Inertia."""
    
    def test_inertia_init(self):
        """Test inizializzazione Inertia."""
        inertia_obj = MomentOfInertia()
        assert inertia_obj is not None
    
    def test_inertia_moments(self):
        """Test momenti d'inerzia."""
        inertia_obj = MomentOfInertia()
        ixx = inertia_obj.ixx_dry
        iyy = inertia_obj.iyy_dry
        izz = inertia_obj.izz_dry
        
        assert ixx > 0
        assert iyy > 0
        assert izz > 0
    
    def test_inertia_tensor(self):
        """Test tensore d'inerzia."""
        inertia_obj = MomentOfInertia()
        tensor = inertia_obj.get_inertia()
        
        assert hasattr(tensor, 'ixx')
        assert hasattr(tensor, 'iyy')
        assert hasattr(tensor, 'izz')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
