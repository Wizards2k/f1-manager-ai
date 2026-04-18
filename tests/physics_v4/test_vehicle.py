"""
Physics V4 Test Suite - Test Vehicle

Test per moduli veicolo Physics Engine V4.
Esegui con: pytest tests/physics_v4/test_vehicle.py -v
"""

import pytest
import sys
from pathlib import Path

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

# Import vehicle modules from vehicle package directly
import lap_simulator.physics_v4.vehicle as vehicle
from vehicle import LoadTransfer, KammCircle, HandlingModel, VehicleBalance, CorneringLimitCalculator


class TestLoadTransfer:
    """Test per LoadTransfer."""
    
    def test_load_transfer_init(self):
        """Test inizializzazione LoadTransfer."""
        lt = LoadTransfer()
        assert lt is not None
        assert lt.mass_kg > 0
    
    def test_load_transfer_longitudinal(self):
        """Test trasferimento longitudinale."""
        lt = LoadTransfer()
        acceleration = -8.0  # m/s² (frenata)
        transfer = lt.calculate_longitudinal_transfer(acceleration, is_braking=True)
        
        assert transfer > 0  # Carico va anteriore
    
    def test_load_transfer_lateral(self):
        """Test trasferimento laterale."""
        lt = LoadTransfer()
        lateral_g = 2.0
        front, rear = lt.calculate_lateral_transfer(lateral_g, is_left_turn=True)
        
        assert front > 0
        assert rear > 0
    
    def test_load_transfer_state(self):
        """Test stato trasferimento."""
        lt = LoadTransfer()
        state = lt.get_state(longitudinal_g=-0.8, lateral_g=2.0, is_braking=True, is_left_turn=True)
        
        assert "front_load_pct" in state
        assert "rear_load_pct" in state


class TestKammCircle:
    """Test per KammCircle."""
    
    def test_kamm_circle_init(self):
        """Test inizializzazione KammCircle."""
        kc = KammCircle()
        assert kc is not None
    
    def test_kamm_circle_utilization(self):
        """Test utilizzo cerchio."""
        kc = KammCircle()
        fc = kc.calculate_utilization(1.5, 1.5)
        
        assert fc.utilization_pct <= 100.0
    
    def test_kamm_circle_max_lat(self):
        """Test g laterale massimo."""
        kc = KammCircle()
        max_lat = kc.get_max_g_lat(1.0)
        
        assert max_lat > 0
    
    def test_kamm_circle_within_limit(self):
        """Test limite cerchio."""
        kc = KammCircle()
        within = kc.is_within_limit(1.0, 1.0)
        
        assert within
    def test_handling_model_init(self):
        """Test inizializzazione HandlingModel."""
        hm = HandlingModel()
        assert hm is not None
    
    def test_handling_model_understeer(self):
        """Test understeer."""
        hm = HandlingModel()
        state = hm.get_state(100.0, 10.0, 2.0)
        
        assert "understeer_pct" in state
    
    def test_handling_model_balance(self):
        """Test bilanciamento."""
        hm = HandlingModel()
        state = hm.get_state(100.0, 10.0, 2.0)
        
        assert "balance" in state
        assert 0.0 <= state["balance"] <= 1.0


class TestVehicleBalance:
    """Test per VehicleBalance."""
    
    def test_vehicle_balance_init(self):
        """Test inizializzazione VehicleBalance."""
        vb = VehicleBalance()
        assert vb is not None
    
    def test_vehicle_balance_static(self):
        """Test bilanciamento statico."""
        vb = VehicleBalance()
        state = vb.get_state()
        
        assert "front_load_pct" in state
        assert "rear_load_pct" in state
    
    def test_vehicle_balance_dynamic(self):
        """Test bilanciamento dinamico."""
        vb = VehicleBalance()
        state = vb.get_state(acceleration_ms2=-8.0, lateral_g=2.0)
        
        assert "load_transfer_pct" in state


class TestCorneringLimit:
    """Test per CorneringLimit."""
    
    def test_cornering_limit_init(self):
        """Test inizializzazione CorneringLimit."""
        cl = CorneringLimitCalculator()
        assert cl is not None
    
    def test_cornering_limit_speed(self):
        """Test velocità in curva."""
        cl = CorneringLimitCalculator()
        cs = cl.get_state(100.0, 80.0)
        
        assert "max_speed_kph" in cs
        assert cs["max_speed_kph"] > 0
    
    def test_cornering_limit_margin(self):
        """Test margine grip."""
        cl = CorneringLimitCalculator()
        cs = cl.get_state(100.0, 80.0)
        
        assert "grip_margin_pct" in cs
        assert cs["grip_margin_pct"] >= 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
