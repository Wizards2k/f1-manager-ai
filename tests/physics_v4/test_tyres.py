"""
Physics V4 Test Suite - Test Tyres

Test per moduli pneumatici Physics Engine V4.
Esegui con: pytest tests/physics_v4/test_tyres.py -v
"""

import pytest
import sys
from pathlib import Path

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

# Import tyre modules from tyres package directly
import lap_simulator.physics_v4.tyres as tyres
from tyres import TyreConstruction, TyreThermal, TyreWear, TyreGripModel


class TestTyreConstruction:
    """Test per TyreConstruction."""
    
    def test_tyre_construction_init(self):
        """Test inizializzazione TyreConstruction."""
        tc = TyreConstruction()
        assert tc is not None
        assert tc.compound == "C3"
        assert tc.wheel_pos == "LF"
    
    def test_tyre_construction_compound(self):
        """Test compound pneumatico."""
        tc = TyreConstruction()
        compounds = tc.COMPOUNDS
        
        assert "C1" in compounds
        assert "C6" in compounds
    
    def test_tyre_construction_params(self):
        """Test parametri compound."""
        tc = TyreConstruction()
        params = tc.params
        
        assert params is not None
        assert params.name == "C3"


class TestTyreThermal:
    """Test per TyreThermal."""
    
    def test_tyre_thermal_init(self):
        """Test inizializzazione TyreThermal."""
        tt = TyreThermal()
        assert tt is not None
    
    def test_tyre_thermal_gaussian(self):
        """Test fattore gaussiano termico."""
        tt = TyreThermal()
        # Riscalda la gomma prima di testare il raffreddamento
        tt.surface_temp = 80.0
        v_car_kph = 100.0
        dt = 0.1
        factor = tt.calculate_cooling(v_car_kph, dt)
        
        assert 0.0 < factor <= 1.0
    
    def test_tyre_thermal_window(self):
        """Test finestra termica."""
        # Usa TyreGripModel.is_in_optimal_window
        from lap_simulator.physics_v4.tyres.grip_model import TyreGripModel
        gm = TyreGripModel()
        in_window = gm.is_in_optimal_window()
        
        assert isinstance(in_window, bool)


class TestTyreWear:
    """Test per TyreWear."""
    
    def test_tyre_wear_init(self):
        """Test inizializzazione TyreWear."""
        tw = TyreWear()
        assert tw is not None
    
    def test_tyre_wear_mechanical(self):
        """Test usura meccanica."""
        tw = TyreWear()
        distance_km = 10.0
        # Usa update_wear con parametri corretti
        tw.update_wear(5.0, 0.1, 0.0, 100.0, 100.0, 0.1)
        wear_pct = tw.wear_pct
        
        assert wear_pct > 0
    
    def test_tyre_wear_thermal(self):
        """Test usura termica."""
        tw = TyreWear()
        temp_c = 1200.0
        # Usa update_wear con temperatura alta
        tw.update_wear(5.0, 0.1, 0.0, 100.0, 1200.0, 0.1)
        wear_pct = tw.wear_pct
        
        assert wear_pct > 0


class TestGripModel:
    """Test per GripModel."""
    
    def test_grip_model_init(self):
        """Test inizializzazione GripModel."""
        gm = TyreGripModel()
        assert gm is not None
    
    def test_grip_model_mu(self):
        """Test coefficiente di attrito."""
        gm = TyreGripModel()
        temp_c = 100.0
        load_kn = 5.0
        # Usa calculate_grip con parametri corretti
        grip = gm.calculate_grip(load_kn, 0.0, 0.0, 100.0, 0.1)
        
        assert 0.5 < grip.mu_effective < 2.0
    
    def test_grip_model_load_sensitivity(self):
        """Test sensibilità carico."""
        gm = TyreGripModel()
        # Usa calculate_grip con carichi diversi
        grip_low = gm.calculate_grip(3.0, 0.0, 0.0, 100.0, 0.1)
        grip_high = gm.calculate_grip(8.0, 0.0, 0.0, 100.0, 0.1)
        
        # Load sensitivity: grip decreases with load
        assert grip_low.mu_effective > grip_high.mu_effective


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
