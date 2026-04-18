"""
Physics V4 Test Suite - Test Brakes

Test per moduli freni Physics Engine V4.
Esegui con: pytest tests/physics_v4/test_brakes.py -v
"""

import pytest
import sys
from pathlib import Path

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

# Import brake modules from brakes package directly
import lap_simulator.physics_v4.brakes as brakes
from brakes import BrakeMaterial, BrakeCooling, BrakeBias, BrakeWear


class TestBrakeMaterial:
    """Test per BrakeMaterial."""
    
    def test_brake_material_init(self):
        """Test inizializzazione BrakeMaterial."""
        bm = BrakeMaterial()
        assert bm is not None
        assert bm.params.optimal_temp_min_c > 0
        assert bm.params.optimal_temp_max_c > 0
    
    def test_brake_material_friction(self):
        """Test coefficiente di attrito."""
        bm = BrakeMaterial()
        temp_c = 800.0
        bm.update_friction_coeff(temp_c)
        mu = bm.state.friction_coeff
        
        assert 0.1 < mu < 0.6
    
    def test_brake_material_oxidation(self):
        """Test ossidazione freni."""
        bm = BrakeMaterial()
        temp_c = 1200.0
        oxidation_rate = bm.calculate_oxidation_wear(temp_c, 1.0)
        
        assert oxidation_rate > 0


class TestBrakeCooling:
    """Test per BrakeCooling."""
    
    def test_brake_cooling_init(self):
        """Test inizializzazione BrakeCooling."""
        bc = BrakeCooling()
        assert bc is not None
    
    def test_brake_cooling_ducts(self):
        """Test configurazioni duct."""
        bc = BrakeCooling()
        ducts = bc.DUCT_CONFIGS
        
        assert "size_1_closed" in ducts
        assert "size_5_wide" in ducts
    
    def test_brake_cooling_cooling(self):
        """Test raffreddamento."""
        bc = BrakeCooling()
        temp_c = 800.0
        v_car_kph = 200.0
        dt = 0.1
        cooling = bc.calculate_convective_cooling(temp_c, v_car_kph, dt)
        
        assert cooling > 0


class TestBrakeBias:
    """Test per BrakeBias."""
    
    def test_brake_bias_init(self):
        """Test inizializzazione BrakeBias."""
        bb = BrakeBias()
        assert bb is not None
        assert 54.0 < bb.base_bias_front < 60.0
    
    def test_brake_bias_migration(self):
        """Test migrazione frenata."""
        bb = BrakeBias()
        migration = bb.calculate_migration_offset(100.0)
        
        assert -0.05 < migration < 0.05
    
    def test_brake_bias_distribution(self):
        """Test distribuzione frenata."""
        bb = BrakeBias()
        total_force = 10.0  # kN
        front, rear, mguk = bb.calculate_brake_force_distribution(total_force, 100.0, 200.0)
        
        # Check sum is approximately equal (floating point tolerance)
        assert abs((front + rear + mguk) - total_force) < 0.01


class TestBrakeWear:
    """Test per BrakeWear."""
    
    def test_brake_wear_init(self):
        """Test inizializzazione BrakeWear."""
        bw = BrakeWear()
        assert bw is not None
    
    def test_brake_wear_mechanical(self):
        """Test usura meccanica."""
        bw = BrakeWear()
        distance_km = 10.0
        wear_pct = bw.calculate_mechanical_wear(5.0, 0.5, distance_km * 1000, 0.1)
        
        assert wear_pct > 0
    
    def test_brake_wear_oxidation(self):
        """Test usura ossidazione."""
        bw = BrakeWear()
        temp_c = 1200.0
        wear_pct = bw.calculate_oxidation_wear(temp_c, 1.0)
        
        assert wear_pct > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
