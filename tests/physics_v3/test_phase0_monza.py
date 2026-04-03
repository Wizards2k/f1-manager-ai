"""
Test: Phase 0 — Monza Baseline Calibration

Test end-to-end su Monza con setup baseline.
Target: 79.5s (range 77-81s per tolleranza calibrazione)

Setup baseline Monza:
- Front wing: 16° (low downforce)
- Rear wing: 18° (low downforce)
- Brake balance: 52%
- Brake duct: 45%
- Driver: Average pace (70 raw_pace)
- Conditions: 20°C air, 40°C track, dry

Questo test valida che il motore V3 produce tempi realistici su un circuito veloce.
"""

import pytest
from python_backend.lap_simulator.lap_simulator_v3 import (
    LapSimulatorV3,
    CarEntryV3,
)
from python_backend.lap_simulator.data_types import (
    AeroSetup,
    DriverSkills,
    EnvContext,
    AeroComponent,
)


class TestPhase0Monza:
    """Validazione Fase 0 — Monza."""

    @pytest.fixture
    def monza_setup(self):
        """Setup baseline Monza (low downforce per velocità di punta)."""
        setup = AeroSetup()

        # Ali basse
        setup.front_wing = AeroComponent(
            name="front_wing",
            base_downforce=14.0,  # Basso DF
            base_drag=4.2,
            angle_deg=16.0,
        )
        setup.rear_wing = AeroComponent(
            name="rear_wing",
            base_downforce=18.0,  # Basso DF
            base_drag=3.5,
            angle_deg=18.0,
        )

        # Sospensioni neutre
        setup.ride_height_front_mm = 40.0
        setup.ride_height_rear_mm = 50.0
        setup.ride_height_optimal_front_mm = 40.0
        setup.ride_height_optimal_rear_mm = 50.0
        setup.antiroll_front_rigidity = 0.50
        setup.antiroll_rear_rigidity = 0.50

        return setup

    @pytest.fixture
    def average_driver(self):
        """Driver con abilità medie (pace=70)."""
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

    @pytest.fixture
    def monza_conditions(self):
        """Condizioni standard Monza."""
        return EnvContext(
            air_temp_c=20.0,
            track_temp_c=40.0,
            air_density_kg_m3=1.225,
            wind_speed_kph=5.0,
            rain_intensity=0.0,
            track_rubber_level=0.8,
            water_film_level=0.0,
        )

    def test_monza_lap_time_baseline(self, monza_setup, average_driver, monza_conditions):
        """
        Test: Simula un giro di Monza con setup baseline.
        Verifica che il tempo sia nel range target 77-81s.
        """

        # Crea entry
        entry = CarEntryV3(
            car_id="TEST_CAR",
            aero_setup=monza_setup,
            driver_skills=average_driver,
            push_level=10,  # Push level 1.0 (normalized)
        )

        # Simula
        sim = LapSimulatorV3(debug=False)
        results = sim.run_lap(
            entries=[entry],
            circuit_id="it-1922_monza",
            is_qualifying=True,
            lap_number=1,
            env=monza_conditions,
        )

        assert len(results) == 1
        result = results[0]

        # Logging
        print(f"\nMonza Baseline Test:")
        print(f"  Car ID: {result.car_id}")
        print(f"  Lap time: {result.lap_time_s:.2f}s")
        print(f"  Target: 79.5s (range 77-81s)")
        print(f"  V_max: {result.v_max_kph:.1f} kph")
        print(f"  V_min: {result.v_min_kph:.1f} kph")

        # Assertion: tempo deve essere entro range target (77-81s)
        # Tolleranza ±2s per tuning ancora incompleto
        assert (
            77.0 <= result.lap_time_s <= 81.0
        ), f"Lap time {result.lap_time_s:.2f}s outside target range 77-81s"

        # Assertion aggiuntive
        assert result.v_max_kph > 320  # Monza deve raggiungere >320 kph
        assert result.v_min_kph < 100  # In curva strette <100 kph

    def test_monza_consistency(self, monza_setup, average_driver, monza_conditions):
        """
        Test: Verifica che il motore V3 è deterministico.
        Lo stesso setup produce lo stesso tempo.
        """

        entry = CarEntryV3(
            car_id="TEST_CAR",
            aero_setup=monza_setup,
            driver_skills=average_driver,
            push_level=10,
        )

        sim = LapSimulatorV3(debug=False)

        # Prima simulazione
        results1 = sim.run_lap([entry], "it-1922_monza", env=monza_conditions)
        time1 = results1[0].lap_time_s

        # Seconda simulazione (identica)
        results2 = sim.run_lap([entry], "it-1922_monza", env=monza_conditions)
        time2 = results2[0].lap_time_s

        # Devono essere uguali (deterministico)
        assert (
            abs(time1 - time2) < 0.01
        ), f"Non-deterministic: {time1:.3f}s vs {time2:.3f}s"

        print(f"\nConsistency test: {time1:.3f}s = {time2:.3f}s ✓")

    def test_monza_v_max_realistic(self, monza_setup, average_driver, monza_conditions):
        """
        Test: Verifica che v_max su Monza sia realistica.
        Monza 2025: ~365 kph con DRS.
        """

        entry = CarEntryV3(
            car_id="TEST_CAR",
            aero_setup=monza_setup,
            driver_skills=average_driver,
            push_level=10,
        )

        sim = LapSimulatorV3(debug=False)
        results = sim.run_lap([entry], "it-1922_monza", env=monza_conditions)
        result = results[0]

        # Monza v_max deve essere 350-370 kph
        assert (
            350 <= result.v_max_kph <= 370
        ), f"V_max {result.v_max_kph:.1f} not realistic for Monza"

        print(f"\nMonza V_max: {result.v_max_kph:.1f} kph (expected 350-370)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
