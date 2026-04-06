"""
Physics V4 Test Suite - Conftest

Configurazione pytest per Physics Engine V4.
Esegui con: pytest tests/physics_v4 -v --cov=lap_simulator/physics_v4
"""

import pytest
import sys
from pathlib import Path

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

# Import Physics V4 modules
from lap_simulator.physics_v4 import (
    # Aero
    AeroAssembly, AeroForces,
    FrontWing, RearWing,
    FloorFront, FloorRear,
    Sidepods, EngineCover, BWing,
    # Mass
    MassDistribution, MassState,
    CenterOfGravity, CGPosition,
    MomentOfInertia, InertiaTensor,
    # Suspension
    SpringDamper, SpringForce,
    AntiRollBar, AntiRollForce,
    RideHeight, RideHeightState,
    # Integrator
    integrate_lap_hd,
)


@pytest.fixture(scope="session")
def physics_v4_modules():
    """Fixture per moduli Physics V4."""
    return {
        # Aero
        "aero_assembly": AeroAssembly,
        "front_wing": FrontWing,
        "rear_wing": RearWing,
        "floor_front": FloorFront,
        "floor_rear": FloorRear,
        "sidepods": Sidepods,
        "engine_cover": EngineCover,
        "bwing": BWing,
        # Mass
        "mass_distribution": MassDistribution,
        "center_of_gravity": CenterOfGravity,
        "inertia": MomentOfInertia,
        # Suspension
        "spring_damper": SpringDamper,
        "antiroll": AntiRollBar,
        "ride_height": RideHeight,
        # Integrator
        "lap_integrator": integrate_lap_hd,
    }


@pytest.fixture(scope="session")
def test_config():
    """Fixture per configurazione test."""
    from tests.physics_v4_config import TEST_CONFIG
    return TEST_CONFIG


@pytest.fixture(scope="session")
def circuit_test_data():
    """Fixture per dati test circuiti."""
    from tests.physics_v4_config import CIRCUIT_TEST_DATA
    return CIRCUIT_TEST_DATA


@pytest.fixture(scope="session")
def physics_validation():
    """Fixture per target validazione fisica."""
    from tests.physics_v4_config import PHYSICS_VALIDATION
    return PHYSICS_VALIDATION


@pytest.fixture
def aero_components():
    """Fixture per componenti aero."""
    return {
        "front_wing": FrontWing(),
        "rear_wing": RearWing(),
        "floor_front": FloorFront(),
        "floor_rear": FloorRear(),
        "sidepods": Sidepods(),
        "engine_cover": EngineCover(),
        "bwing": BWing(),
    }


@pytest.fixture
def vehicle_components():
    """Fixture per componenti veicolo."""
    return {
        "load_transfer": load_transfer.LoadTransfer(),
        "kamm_circle": kamm_circle.KammCircle(),
        "handling": handling.HandlingModel(),
        "balance": balance.VehicleBalance(),
        "cornering_limit": cornering_limit.CorneringLimitCalculator(),
    }


@pytest.fixture
def driver_components():
    """Fixture per componenti driver."""
    return {
        "driving_line": driving_line.DrivingLine(),
        "braking_point": braking_point.BrakingPoint(),
        "throttle_curve": throttle_curve.ThrottleCurve(),
        "steering_input": steering_input.SteeringInput(),
    }


@pytest.fixture
def setup_components():
    """Fixture per componenti setup."""
    return {
        "slider_to_physics": slider_to_physics.SliderToPhysics(),
        "default_setups": default_setups.DefaultSetups(),
        "optimizer": optimizer.SetupOptimizer(),
    }


# Markers
def pytest_configure(config):
    """Configurazione markers pytest."""
    config.addinivalue_line(
        "markers", "unit: unit tests (default)"
    )
    config.addinivalue_line(
        "markers", "integration: integration tests"
    )
    config.addinivalue_line(
        "markers", "calibration: calibration tests"
    )
    config.addinivalue_line(
        "markers", "slow: slow tests (>10s)"
    )
    config.addinivalue_line(
        "markers", "fast: fast tests (<1s)"
    )


# Coverage configuration
def pytest_report_header(config):
    """Header report pytest."""
    return [
        "Physics Engine V4 Test Suite v1.0.0",
        "Run with: pytest tests/physics_v4 -v --cov=lap_simulator/physics_v4",
    ]
