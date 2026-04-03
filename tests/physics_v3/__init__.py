"""
Physics V3 Test Suite

Test framework per validare Physics Engine V3 secondo spec.

Organizzazione:
- test_constants.py: Validazione costanti
- test_aero_mapper.py: Unit test aero mapper
- test_balance_model.py: Unit test balance model
- test_corner_solver.py: Unit test corner solver
- test_phase0_monza.py: End-to-end Monza (target 79.5s)
- test_phase0_monaco.py: End-to-end Monaco (target 70.2s)
- validate_phases.py: Validation tests Fase 0-6

Version: 1.0
Date: 2026-04-02
"""

import pytest


@pytest.fixture
def test_env():
    """Standard test environment."""
    from python_backend.lap_simulator.data_types import EnvContext

    return EnvContext(
        air_temp_c=20.0,
        track_temp_c=40.0,
        air_density_kg_m3=1.225,
        wind_speed_kph=5.0,
        rain_intensity=0.0,
        track_rubber_level=0.8,
        water_film_level=0.0,
    )


@pytest.fixture
def test_aero_setup():
    """Standard test aero setup."""
    from python_backend.lap_simulator.data_types import AeroSetup

    return AeroSetup()


@pytest.fixture
def test_driver_skills():
    """Standard test driver (average pace)."""
    from python_backend.lap_simulator.data_types import DriverSkills

    return DriverSkills(
        raw_pace=70,
        race_craft=70,
        aggression=50,
        consistency=70,
        tyre_management=70,
        overtaking_skill=60,
        defending_skill=60,
        wet_skill=60,
        smoothness=60,
        setup_finding=60,
    )
