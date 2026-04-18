"""
Physics V4 Test Suite - Configuration

Suite di test completa per Physics Engine V4:
- Test unitari per tutti i moduli
- Test di integrazione
- Test di calibrazione
- Coverage reporting
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Test directories
TESTS_DIR = BASE_DIR / "tests"
PHYSICS_V4_DIR = TESTS_DIR / "physics_v4"

# Output directories
COVERAGE_DIR = TESTS_DIR / "coverage"
REPORTS_DIR = TESTS_DIR / "reports"

# Create directories if not exist
for dir_path in [COVERAGE_DIR, REPORTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Test configuration
TEST_CONFIG = {
    # Coverage settings
    "coverage": {
        "source": ["python_backend/lap_simulator/physics_v4"],
        "omit": [
            "*/__init__.py",
            "*/tests/*",
            "*/mockups/*",
        ],
        "branch": True,
        "include": ["*.py"],
    },
    
    # Test timeout (seconds)
    "timeout": 300,
    
    # Test markers
    "markers": {
        "unit": "unit tests",
        "integration": "integration tests",
        "calibration": "calibration tests",
        "slow": "slow tests (>10s)",
        "fast": "fast tests (<1s)",
    },
    
    # Coverage thresholds
    "coverage_thresholds": {
        "aero": 80,
        "mass": 80,
        "suspension": 80,
        "power_unit": 80,
        "tyres": 80,
        "brakes": 80,
        "vehicle": 80,
        "driver": 80,
        "setup": 80,
        "overall": 75,
    },
    
    # Test execution order
    "execution_order": [
        "test_aero",
        "test_mass",
        "test_suspension",
        "test_power_unit",
        "test_tyres",
        "test_brakes",
        "test_vehicle",
        "test_driver",
        "test_setup",
        "test_integration",
    ],
}

# Circuit test data
CIRCUIT_TEST_DATA = {
    "monza": {
        "target_lap_time": 79.5,
        "target_max_speed": 360.0,
        "target_braking_zones": 5,
    },
    "monaco": {
        "target_lap_time": 70.2,
        "target_max_speed": 290.0,
        "target_braking_zones": 12,
    },
    "suzuka": {
        "target_lap_time": 88.5,
        "target_max_speed": 330.0,
        "target_braking_zones": 8,
    },
}

# Physics validation targets
PHYSICS_VALIDATION = {
    "aero": {
        "target_CLA": 3.83,  # m²
        "target_CDA": 0.90,  # m²
        "target_L_D": 4.26,
    },
    "tyres": {
        "target_grip": 1.7,  # g
        "target_window": 20.0,  # °C
        "target_wear": 0.01,  # %/lap
    },
    "brakes": {
        "target_temp_range": (400.0, 900.0),  # °C
        "target_mgu_k": 120.0,  # kW
        "target_migration": 0.04,  # ±4%
    },
    "ers": {
        "target_deploy": 4.0,  # MJ/lap
        "target_harvest": 2.0,  # MJ/lap
        "target_mgu_k_power": 120.0,  # kW
    },
}

# Debug mode
DEBUG = os.environ.get("DEBUG_TESTS", "false").lower() == "true"
