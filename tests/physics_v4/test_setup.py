"""
Physics V4 Test Suite - Test Setup

Test per moduli setup Physics Engine V4.
Esegui con: pytest tests/physics_v4/test_setup.py -v
"""

import pytest
import sys
from pathlib import Path

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

# Import setup modules from setup package directly
import lap_simulator.physics_v4.setup as setup
from setup import SliderToPhysics, DefaultSetups, SetupOptimizer
from lap_simulator.physics_v4.calibration.aero_calibration import (
    compute_aero_setup_bias,
    get_aero_calibration,
)
from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_v4.integrator.waypoint_integrator import integrate_lap_hd
from lap_simulator.setup_penalty_v2 import build_ideal_setup as build_ideal_setup_v2
from services.setup_engine_service import SetupEngineService


class TestSliderToPhysics:
    """Test per SliderToPhysics."""
    
    def test_slider_to_physics_init(self):
        """Test inizializzazione SliderToPhysics."""
        stp = SliderToPhysics()
        assert stp is not None
    
    def test_slider_to_physics_conversion(self):
        """Test conversione slider."""
        stp = SliderToPhysics()
        sc = stp.convert_slider(50.0, "front_wing")
        
        assert sc.physics_value > 0
        assert sc.physics_unit == "deg"
    
    def test_slider_to_physics_all(self):
        """Test conversione tutti gli slider."""
        stp = SliderToPhysics()
        sliders = {
            "front_wing": 50.0,
            "rear_wing": 60.0,
            "brake_bias": 55.0,
        }
        conversions = stp.convert_all_sliders(sliders)
        
        assert len(conversions) == len(sliders)


class TestDefaultSetups:
    """Test per DefaultSetups."""
    
    def test_default_setups_init(self):
        """Test inizializzazione DefaultSetups."""
        ds = DefaultSetups()
        assert ds is not None
    
    def test_default_setups_monza(self):
        """Test setup Monza."""
        ds = DefaultSetups()
        setup = ds.get_default_setup("monza", "dry", "C3")
        
        assert "front_wing" in setup
        assert "rear_wing" in setup
    
    def test_default_setups_monaco(self):
        """Test setup Monaco."""
        ds = DefaultSetups()
        setup = ds.get_default_setup("monaco", "dry", "C3")
        
        assert setup["front_wing"] > 10.0  # High downforce

    def test_default_setups_physics_v4_circuit_id_alias(self):
        """Test normalizzazione circuit_id Physics V4."""
        ds = DefaultSetups()
        monaco_setup = ds.get_default_setup("monaco", "dry", "C3")
        alias_setup = ds.get_default_setup("mc-1929_monaco", "dry", "C3")

        assert alias_setup["front_wing"] == monaco_setup["front_wing"]
        assert alias_setup["rear_wing"] == monaco_setup["rear_wing"]
        assert alias_setup["brake_bias"] == monaco_setup["brake_bias"]


class TestSetupOptimizer:
    """Test per SetupOptimizer."""
    
    def test_optimizer_init(self):
        """Test inizializzazione SetupOptimizer."""
        so = SetupOptimizer()
        assert so is not None
    
    def test_optimizer_optimize(self):
        """Test ottimizzazione."""
        so = SetupOptimizer()
        result = so.optimize("monza", "dry", "C3")
        
        assert result.sliders is not None
        assert len(result.sliders) > 0
    
    def test_optimizer_multiple(self):
        """Test ottimizzazione multipla."""
        so = SetupOptimizer()
        results = so.optimize_multiple(["monza", "monaco"], "dry", "C3")
        
        assert len(results) == 2


class TestPhysicsV4SetupIntegration:
    """Test integrazione runtime Physics V4."""

    def test_aero_calibration_loader_supports_aliases(self):
        """Test caricamento calibrazione aero da alias circuito e id completo."""
        full_id = get_aero_calibration("mc-1929_monaco")
        alias_id = get_aero_calibration("monaco")

        assert full_id is not None
        assert alias_id is not None
        assert alias_id["CdA"] == pytest.approx(full_id["CdA"])
        assert alias_id["ClA"] == pytest.approx(full_id["ClA"])

    def test_setup_ranges_payload_exposes_aero_calibration(self):
        """Test che il payload setup esponga il profilo aero usato dal runtime."""
        payload = SetupEngineService.build_ranges_payload("mc-1929_monaco")

        assert payload["circuit_key"] == "monaco"
        assert payload["aero_calibration"] is not None
        assert payload["aero_calibration"]["CdA"] == pytest.approx(1.6973)
        assert payload["aero_setup_bias"] is not None
        assert payload["aero_setup_bias"]["adjustments"]["front_wing"] == 1
        assert payload["aero_setup_bias"]["adjustments"]["rear_wing"] == 1

    def test_shared_aero_bias_matches_setup_builders(self):
        """Test che il bias aero condiviso produca gli stessi target nei due builder."""
        class DummyCar:
            def __init__(self):
                self.team_name = ""
                self.driver_name = ""
                self.player_config = {}

        bias = compute_aero_setup_bias("jp-1962_suzuka")
        assert bias is not None
        assert bias["adjustments"]["front_wing"] == 3
        assert bias["adjustments"]["rear_wing"] == 1

        service_ideal = SetupEngineService.build_ideal_setup("jp-1962_suzuka", DummyCar())
        penalty_ideal = build_ideal_setup_v2("jp-1962_suzuka")

        assert penalty_ideal.aero_bias is not None
        assert penalty_ideal.aero_bias["adjustments"]["front_wing"] == 3
        assert penalty_ideal.aero_bias["adjustments"]["rear_wing"] == 1
        assert service_ideal["front_wing"] == penalty_ideal.ideal_sliders["front_wing"]
        assert service_ideal["rear_wing"] == penalty_ideal.ideal_sliders["rear_wing"]

    def test_simulate_lap_is_deterministic(self):
        """Test che il setup non accumula offset tra run successive."""
        sim = PhysicsV4Setup(circuit="mc-1929_monaco", session="qualifying")

        first = sim.simulate_lap(verbose=False)
        second = sim.simulate_lap(verbose=False)

        assert first["lap_time_s"] == second["lap_time_s"]
        assert first["v_max_kph"] == second["v_max_kph"]
        assert first["v_min_kph"] == second["v_min_kph"]
        assert first["aero_calibration"] is not None
        assert first["aero_calibration"]["CdA"] == pytest.approx(1.6973)

    def test_integrate_lap_uses_aero_calibration(self):
        """Test che la calibrazione aero modifichi il risultato del giro."""
        calibrated = get_aero_calibration("mc-1929_monaco")
        assert calibrated is not None

        neutral = dict(calibrated)
        neutral.update(
            {
                "CdA": 1.45,
                "ClA": 4.85,
                "drag_index": 1.0,
                "downforce_index": 1.0,
                "aero_balance_target": 0.0,
            }
        )

        baseline = integrate_lap_hd(
            circuit_id="mc-1929_monaco",
            aero_setup={"front_wing": 20.0, "rear_wing": 22.0},
            aero_calibration=neutral,
        )
        tuned = integrate_lap_hd(
            circuit_id="mc-1929_monaco",
            aero_setup={"front_wing": 20.0, "rear_wing": 22.0},
            aero_calibration=calibrated,
        )

        assert baseline["lap_time_s"] != tuned["lap_time_s"]
        assert baseline["v_max_kph"] != tuned["v_max_kph"]
        assert tuned["aero_calibration"]["source_file"].endswith("mc-1929_monaco.json")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
