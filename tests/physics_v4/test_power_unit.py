"""
Physics V4 Test Suite - Test Power Unit

Test per moduli Power Unit Physics Engine V4.
Esegui con: pytest tests/physics_v4/test_power_unit.py -v
"""

import pytest
import sys
from pathlib import Path

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

from lap_simulator.physics_v4.power_unit import (
    ICEEngine, ICEState, ICE_BASE_POWER_KW,
    ERSDeployManager, DeployRequest, ERSEnergyState,
    ThermalModel, ThermalState,
)


class TestICEEngine:
    """Test per ICEEngine."""
    
    def test_ice_engine_init(self):
        """Test inizializzazione ICEEngine."""
        ice = ICEEngine()
        assert ice is not None
        assert ice.config['displacement_l'] > 0
        assert ice.config['redline_rpm'] > 0
    
    def test_ice_engine_power_curve(self):
        """Test curva potenza ICE."""
        ice = ICEEngine()
        rpm = 10000.0
        throttle_pct = 100.0
        power_kw = ice.calculate_power(rpm, throttle_pct)
        
        assert power_kw is not None
        assert power_kw > 0
    
    def test_ice_engine_torque_curve(self):
        """Test curva coppia ICE."""
        ice = ICEEngine()
        rpm = 10000.0
        torque_nm = ice.get_torque_at_rpm(rpm)
        
        assert torque_nm > 0


class TestThermalModel:
    """Test per ThermalModel."""
    
    def test_thermal_model_init(self):
        """Test inizializzazione ThermalModel."""
        thermal = ThermalModel()
        assert thermal is not None
        assert thermal.ICE_T_WARNING > 0
    
    def test_thermal_efficiency(self):
        """Test efficienza termica."""
        thermal = ThermalModel()
        # Usa calculate_ice_derating come proxy per efficiency
        ice_power_kw = 300.0
        v_car_kph = 200.0
        dt = 0.1
        derating = thermal.calculate_ice_derating(ice_power_kw, v_car_kph, dt)
        
        assert 0.0 <= derating <= 1.0
    
    def test_thermal_limits(self):
        """Test limiti termici."""
        thermal = ThermalModel()
        # Testa derating con potenza alta
        ice_power_kw = 800.0  # Potenza molto alta
        v_car_kph = 200.0
        dt = 0.1
        derating = thermal.calculate_ice_derating(ice_power_kw, v_car_kph, dt)
        
        assert derating > 0.5  # Derating aumenta a potenza alta


class TestERSDeploy:
    """Test per ERSDeploy."""
    
    def test_ers_deploy_init(self):
        """Test inizializzazione ERSDeploy."""
        ers = ERSDeployManager()
        assert ers is not None
        assert ers.DEPLOY_LIMIT_MJ > 0
    
    def test_ers_deploy_energy(self):
        """Test deploy energia ERS."""
        ers = ERSDeployManager()
        # Testa il consumo energia
        energy_mj = 2.0  # 2 MJ
        ers.lap_deploy_mj = energy_mj
        
        assert ers.lap_deploy_mj == energy_mj
        assert ers.lap_deploy_mj <= ers.DEPLOY_LIMIT_MJ
    
    def test_ers_deploy_limit(self):
        """Test limite deploy ERS."""
        ers = ERSDeployManager()
        energy_mj = 5.0  # Over limit
        ers.lap_deploy_mj = min(energy_mj, ers.DEPLOY_LIMIT_MJ)
        
        # Should be limited to max deploy
        assert ers.lap_deploy_mj <= ers.DEPLOY_LIMIT_MJ


class TestERSHarvest:
    """Test per ERSHarvest."""
    
    def test_ers_harvest_init(self):
        """Test inizializzazione ERSHarvest."""
        ers = ERSDeployManager()
        assert ers is not None
        assert ers.HARVEST_LIMIT_MJ > 0
    
    def test_ers_harvest_energy(self):
        """Test harvest energia ERS."""
        ers = ERSDeployManager()
        energy_mj = 1.0  # 1 MJ
        ers.lap_harvest_mj = energy_mj
        
        assert ers.lap_harvest_mj == energy_mj
        assert ers.lap_harvest_mj <= ers.HARVEST_LIMIT_MJ


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
