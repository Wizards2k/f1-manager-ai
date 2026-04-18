"""
Physics V4 Test Suite - Test Aero

Test per moduli aerodinamici Physics Engine V4.
Esegui con: pytest tests/physics_v4/test_aero.py -v
"""

import pytest
import sys
from pathlib import Path

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

# Import aero modules from aero package directly
import lap_simulator.physics_v4.aero as aero
from aero import FrontWing, RearWing, FloorFront, FloorRear, Sidepods, EngineCover, BWing, AeroAssembly


class TestFrontWing:
    """Test per FrontWing."""
    
    def test_front_wing_init(self):
        """Test inizializzazione FrontWing."""
        fw = FrontWing()
        assert fw is not None
        assert fw.A_REF > 0
        assert fw.CD_MIN > 0
    
    def test_front_wing_forces(self):
        """Test forze FrontWing."""
        fw = FrontWing()
        v = 100.0 / 3.6  # m/s
        rho = 1.225  # kg/m³
        forces = fw.calculate_forces(rho, v)
        
        assert "lift" in forces
        assert "drag" in forces
        assert forces["lift"] > 0
        assert forces["drag"] > 0
    
    def test_front_wing_coefficients(self):
        """Test coefficienti FrontWing."""
        fw = FrontWing()
        aa = AeroAssembly()
        forces = aa.compute_forces(100.0 / 3.6)
        
        # Usa component forces da AeroAssembly
        assert "CL" in forces.component_forces["front_wing"]
        assert "CD" in forces.component_forces["front_wing"]
        assert "L/D" in forces.component_forces["front_wing"]


class TestRearWing:
    """Test per RearWing."""
    
    def test_rear_wing_init(self):
        """Test inizializzazione RearWing."""
        rw = RearWing()
        assert rw is not None
        assert rw.A_REF > 0
    
    def test_rear_wing_forces(self):
        """Test forze RearWing."""
        rw = RearWing()
        v = 100.0 / 3.6  # m/s
        rho = 1.225  # kg/m³
        forces = rw.calculate_forces(rho, v)
        
        assert "lift" in forces
        assert "drag" in forces


class TestFloorFront:
    """Test per FloorFront."""
    
    def test_floor_front_init(self):
        """Test inizializzazione FloorFront."""
        ff = FloorFront()
        assert ff is not None
    
    def test_floor_front_forces(self):
        """Test forze FloorFront."""
        ff = FloorFront()
        v = 100.0 / 3.6  # m/s
        rho = 1.225  # kg/m³
        forces = ff.calculate_forces(rho, v)
        
        assert "lift" in forces
        assert "drag" in forces


class TestFloorRear:
    """Test per FloorRear."""
    
    def test_floor_rear_init(self):
        """Test inizializzazione FloorRear."""
        fr = FloorRear()
        assert fr is not None
    
    def test_floor_rear_forces(self):
        """Test forze FloorRear."""
        fr = FloorRear()
        v = 100.0 / 3.6  # m/s
        rho = 1.225  # kg/m³
        forces = fr.calculate_forces(rho, v)
        
        assert "lift" in forces
        assert "drag" in forces


class TestSidepods:
    """Test per Sidepods."""
    
    def test_sidepods_init(self):
        """Test inizializzazione Sidepods."""
        sp = Sidepods()
        assert sp is not None
    
    def test_sidepods_forces(self):
        """Test forze Sidepods."""
        sp = Sidepods()
        v = 100.0 / 3.6  # m/s
        rho = 1.225  # kg/m³
        forces = sp.calculate_forces(rho, v)
        
        assert "drag" in forces


class TestEngineCover:
    """Test per EngineCover."""
    
    def test_engine_cover_init(self):
        """Test inizializzazione EngineCover."""
        ec = EngineCover()
        assert ec is not None
    
    def test_engine_cover_forces(self):
        """Test forze EngineCover."""
        ec = EngineCover()
        v = 100.0 / 3.6  # m/s
        rho = 1.225  # kg/m³
        forces = ec.calculate_forces(rho, v)
        
        assert "drag" in forces


class TestBWing:
    """Test per BWing."""
    
    def test_bwing_init(self):
        """Test inizializzazione BWing."""
        bw = BWing()
        assert bw is not None
    
    def test_bwing_forces(self):
        """Test forze BWing."""
        bw = BWing()
        v = 100.0 / 3.6  # m/s
        rho = 1.225  # kg/m³
        forces = bw.calculate_forces(rho, v)
        
        assert "lift" in forces
        assert "drag" in forces


class TestAeroAssembly:
    """Test per AeroAssembly."""
    
    def test_aero_assembly_init(self):
        """Test inizializzazione AeroAssembly."""
        aa = AeroAssembly()
        assert aa is not None
    
    def test_aero_assembly_forces(self):
        """Test forze AeroAssembly."""
        aa = AeroAssembly()
        v = 100.0 / 3.6  # m/s
        forces = aa.compute_forces(v)
        
        assert forces.f_downforce > 0
        assert forces.f_drag > 0
    
    def test_aero_assembly_coefficients(self):
        """Test coefficienti AeroAssembly."""
        aa = AeroAssembly()
        efficiency = aa.get_aero_efficiency()
        
        assert efficiency > 0
    
    def test_aero_assembly_sum_forces(self):
        """Test somma forze AeroAssembly."""
        aa = AeroAssembly()
        v = 100.0 / 3.6  # m/s
        forces = aa.compute_forces(v)
        
        # Verifica che le forze siano calcolate correttamente
        assert forces.cla_total > 0
        assert forces.cda_total > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
