"""
Test: Phase 0 — Monaco Baseline Calibration

Test end-to-end su Monaco con setup baseline.
Target: 70.2s (range 69-73s per tolleranza calibrazione)

Setup baseline Monaco:
- Front wing: 28° (high downforce)
- Rear wing: 32° (high downforce)
- Brake balance: 54%
- Brake duct: 65%
- Driver: Average pace (70 raw_pace)
- Conditions: 20°C air, 35°C track (più fresco che Monza), dry

Monaco è un circuito "grip-limited" dove:
- Downforce è critico per velocità in curva
- Frenate lunghe
- Poco rettilineo (no v_max importante)
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
    SuspensionState,
)


class TestPhase0Monaco:
    """Validazione Fase 0 — Monaco."""

    @pytest.fixture
    def monaco_setup(self):
        """Setup baseline Monaco (high downforce per grip in curva)."""
        setup = AeroSetup()

        # Ali alte
        setup.front_wing = AeroComponent(
            name="front_wing",
            base_downforce=26.0,  # Alto DF
            base_drag=6.8,
            angle_deg=28.0,
        )
        setup.rear_wing = AeroComponent(
            name="rear_wing",
            base_downforce=32.0,  # Alto DF
            base_drag=8.2,
            angle_deg=32.0,
        )

        # Sospensioni neutre ma con ride_height leggermente più alto (Monaco ha strada liscia)
        setup.ride_height_front_mm = 42.0
        setup.ride_height_rear_mm = 52.0
        setup.ride_height_optimal_front_mm = 42.0
        setup.ride_height_optimal_rear_mm = 52.0
        setup.antiroll_front_rigidity = 0.50
        setup.antiroll_rear_rigidity = 0.50

        # Brake balance più anteriore (frenate critiche)
        setup.suspension_front = SuspensionState(rigidity=0.6, efficiency=0.85, df_bonus=0.02)
        setup.suspension_rear = SuspensionState(rigidity=0.6, efficiency=0.85, df_bonus=0.02)

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
    def monaco_conditions(self):
        """Condizioni Monaco (più fresco che Monza, pista liscia)."""
        return EnvContext(
            air_temp_c=20.0,
            track_temp_c=35.0,  # Più fresco (no sole diretto, tunnel)
            air_density_kg_m3=1.225,
            wind_speed_kph=3.0,  # Meno vento (riparato)
            rain_intensity=0.0,
            track_rubber_level=0.8,
            water_film_level=0.0,
        )

    def test_monaco_lap_time_baseline(self, monaco_setup, average_driver, monaco_conditions):
        """
        Test: Simula un giro di Monaco con setup baseline.
        Verifica che il tempo sia nel range target 69-73s.
        """

        entry = CarEntryV3(
            car_id="TEST_CAR_MONACO",
            aero_setup=monaco_setup,
            driver_skills=average_driver,
            push_level=10,
        )

        sim = LapSimulatorV3(debug=False)
        results = sim.run_lap(
            entries=[entry],
            circuit_id="mc-1929_monaco",
            is_qualifying=True,
            lap_number=1,
            env=monaco_conditions,
        )

        assert len(results) == 1
        result = results[0]

        print(f"\nMonaco Baseline Test:")
        print(f"  Car ID: {result.car_id}")
        print(f"  Lap time: {result.lap_time_s:.2f}s")
        print(f"  Target: 70.2s (range 69-73s)")
        print(f"  V_max: {result.v_max_kph:.1f} kph")
        print(f"  V_min: {result.v_min_kph:.1f} kph")

        # Assertion: tempo entro range target (69-73s)
        # Tolleranza ±2s per tuning ancora incompleto
        assert (
            69.0 <= result.lap_time_s <= 73.0
        ), f"Lap time {result.lap_time_s:.2f}s outside target range 69-73s"

        # Assertion aggiuntive
        assert result.v_max_kph < 290  # Monaco max speed ~290 kph (in Sainte-Dévote)
        assert result.v_min_kph < 80  # In hairpin < 80 kph

    def test_monaco_vs_monza_characteristics(self, monaco_setup, average_driver, monaco_conditions):
        """
        Test: Verifica che Monaco ha caratteristiche diverse da Monza.
        Monaco:
        - Tempo totale LUNGO (più curve, più frenate)
        - V_max BASSO (no rettilineo)
        - V_average BASSO (più lento)
        Monza:
        - Tempo totale più breve
        - V_max ALTO
        - V_average ALTO
        """

        entry = CarEntryV3(
            car_id="TEST_MONACO",
            aero_setup=monaco_setup,
            driver_skills=average_driver,
            push_level=10,
        )

        sim = LapSimulatorV3(debug=False)
        results = sim.run_lap([entry], "mc-1929_monaco", env=monaco_conditions)
        result_monaco = results[0]

        # Monaco caratteristiche
        print(f"\nMonaco Characteristics:")
        print(f"  Lap time: {result_monaco.lap_time_s:.2f}s")
        print(f"  V_max: {result_monaco.v_max_kph:.1f} kph")
        print(f"  V_min: {result_monaco.v_min_kph:.1f} kph")

        # Monaco deve avere v_max basso
        assert result_monaco.v_max_kph < 300, "Monaco v_max too high"
        # Monaco deve avere v_min basso (hairpin)
        assert result_monaco.v_min_kph < 90, "Monaco v_min too high"

    def test_monaco_high_df_setup_impact(self, average_driver, monaco_conditions):
        """
        Test: Verifica che high-DF setup è veloce su Monaco (contrasto con Monza).
        Crea due setup:
        1. HIGH_DF (ali alte) — veloce su Monaco
        2. LOW_DF (ali basse) — lento su Monaco
        """

        # High DF setup
        setup_high_df = AeroSetup()
        setup_high_df.front_wing = AeroComponent(
            name="front_wing",
            base_downforce=28.0,  # Molto alto
            angle_deg=28.0,
        )
        setup_high_df.rear_wing = AeroComponent(
            name="rear_wing",
            base_downforce=34.0,  # Molto alto
            angle_deg=32.0,
        )

        # Low DF setup
        setup_low_df = AeroSetup()
        setup_low_df.front_wing = AeroComponent(
            name="front_wing",
            base_downforce=14.0,  # Basso
            angle_deg=16.0,
        )
        setup_low_df.rear_wing = AeroComponent(
            name="rear_wing",
            base_downforce=16.0,  # Basso
            angle_deg=18.0,
        )

        sim = LapSimulatorV3(debug=False)

        result_high = sim.run_lap(
            [CarEntryV3("HIGH_DF", setup_high_df, average_driver, push_level=10)],
            "mc-1929_monaco",
            env=monaco_conditions,
        )[0]

        result_low = sim.run_lap(
            [CarEntryV3("LOW_DF", setup_low_df, average_driver, push_level=10)],
            "mc-1929_monaco",
            env=monaco_conditions,
        )[0]

        print(f"\nMonaco High-DF vs Low-DF:")
        print(f"  High-DF: {result_high.lap_time_s:.2f}s (v_max={result_high.v_max_kph:.0f})")
        print(f"  Low-DF:  {result_low.lap_time_s:.2f}s (v_max={result_low.v_max_kph:.0f})")
        print(f"  Delta: {result_low.lap_time_s - result_high.lap_time_s:.2f}s (expected positive)")

        # Su Monaco, high-DF deve essere più veloce
        assert (
            result_high.lap_time_s < result_low.lap_time_s
        ), f"High-DF should be faster on Monaco: {result_high.lap_time_s:.2f}s vs {result_low.lap_time_s:.2f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
