"""
Physics V4 Test Suite - __init__

Suite di test completa per Physics Engine V4.
Esegui con: pytest tests/physics_v4 -v --cov=lap_simulator/physics_v4
"""

# Test suite metadata
__version__ = "1.0.0"
__author__ = "F1 Manager AI Team"
__description__ = "Physics Engine V4 Test Suite"

# Import test modules
from .test_aero import *
from .test_mass import *
from .test_suspension import *
from .test_power_unit import *
from .test_tyres import *
from .test_brakes import *
from .test_vehicle import *
from .test_driver import *
from .test_setup import *
from .test_integration import *

__all__ = [
    # Aero
    "test_aero_forces",
    "test_aero_coefficients",
    "test_aero_components",
    # Mass
    "test_mass_distribution",
    "test_center_of_gravity",
    "test_inertia",
    # Suspension
    "test_spring_damper",
    "test_antiroll",
    "test_ride_height",
    # Power Unit
    "test_ice_engine",
    "test_thermal_model",
    "test_ers_deploy",
    # Tyres
    "test_tyre_construction",
    "test_tyre_thermal",
    "test_tyre_wear",
    "test_grip_model",
    # Brakes
    "test_brake_material",
    "test_brake_cooling",
    "test_brake_bias",
    "test_brake_wear",
    # Vehicle
    "test_load_transfer",
    "test_kamm_circle",
    "test_handling",
    "test_balance",
    "test_cornering_limit",
    # Driver
    "test_driving_line",
    "test_braking_point",
    "test_throttle_curve",
    "test_steering_input",
    # Setup
    "test_slider_to_physics",
    "test_default_setups",
    "test_optimizer",
    # Integration
    "test_lap_simulation",
    "test_circuit_calibration",
]
