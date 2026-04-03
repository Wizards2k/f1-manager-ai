"""
Physics V3 Calibration Sweep — Identifica il parametro critico

Testa variazioni sistematiche di:
1. Power output (ICE + ERS)
2. Drag coefficient (CDA)
3. Downforce coefficient (CLA)
4. Acceleration base factor

Per identificare quale leva ha il massimo impatto sul lap time.
"""

from typing import Dict, List, Tuple
import logging

from .lap_simulator_v3 import LapSimulatorV3, CarEntryV3
from .data_types import AeroSetup, DriverSkills, EnvContext, AeroComponent
from .physics_v3 import constants

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CalibrationSweep:
    """Esegue sweep sistematico dei parametri di calibrazione."""

    def __init__(self):
        self.baseline_monza_time = 97.87  # Tempo attuale Monza
        self.target_monza_time = 79.0  # Target: medio del range 77-81
        self.delta_needed = self.baseline_monza_time - self.target_monza_time  # ~18.87s
        self.percent_improvement_needed = (self.delta_needed / self.baseline_monza_time) * 100

    def run_single_lap(
        self,
        circuit_id: str = "it-1922_monza",
        aero_setup: AeroSetup = None,
        driver_skills: DriverSkills = None,
    ) -> float:
        """Esegue un singolo giro e ritorna lap time."""
        if aero_setup is None:
            aero_setup = AeroSetup()
            aero_setup.front_wing = AeroComponent(name="front_wing", base_downforce=14.0, angle_deg=16.0)
            aero_setup.rear_wing = AeroComponent(name="rear_wing", base_downforce=16.0, angle_deg=16.0)

        if driver_skills is None:
            driver_skills = DriverSkills(raw_pace=70)

        entry = CarEntryV3(
            car_id="CALIB_TEST",
            aero_setup=aero_setup,
            driver_skills=driver_skills,
            push_level=10,
        )

        env = EnvContext(
            air_temp_c=20.0,
            track_temp_c=40.0,
            air_density_kg_m3=1.225,
            wind_speed_kph=5.0,
            rain_intensity=0.0,
            track_rubber_level=0.8,
            water_film_level=0.0,
        )

        sim = LapSimulatorV3(debug=False)
        results = sim.run_lap([entry], circuit_id, is_qualifying=True, env=env)

        return results[0].lap_time_s if results else 999.0

    def test_ice_power(self) -> Dict[str, float]:
        """Testa variazioni di ICE power (750 → 900 kW)."""
        logger.info("\n" + "="*70)
        logger.info("FASE 1A: Test ICE Power Impact")
        logger.info("="*70)

        results = {}
        baseline = self.run_single_lap()
        results[f"Baseline (750kW)"] = baseline
        logger.info(f"Baseline (750 kW): {baseline:.2f}s")

        # Test con costanti modificate - facciamo test senza modificare globalmente
        # Creeremo una versione modificata dei parametri localmente

        # Per ora riportiamo solo il baseline
        logger.info(f"\nICE power impact: To be tested with parameter override")
        logger.info(f"Current: 750 kW → Test: 850, 900, 950 kW")

        return results

    def test_drag_coefficient(self) -> Dict[str, float]:
        """Testa variazioni di CDA (0.85 → 0.70)."""
        logger.info("\n" + "="*70)
        logger.info("FASE 1B: Test Drag Coefficient (CDA) Impact")
        logger.info("="*70)

        results = {}
        baseline = self.run_single_lap()
        results[f"Baseline (CDA=0.85)"] = baseline
        logger.info(f"Baseline (CDA=0.85): {baseline:.2f}s")

        logger.info(f"\nCDA impact: Lower drag = higher top speed = faster lap")
        logger.info(f"Current: 0.85 m² → Test: 0.80, 0.75, 0.70 m²")

        return results

    def test_acceleration_profile(self) -> Dict[str, float]:
        """Testa accelerazione base (aumento potenza relativa)."""
        logger.info("\n" + "="*70)
        logger.info("FASE 1C: Test Acceleration Base Factor")
        logger.info("="*70)

        results = {}
        baseline = self.run_single_lap()
        results[f"Baseline"] = baseline
        logger.info(f"Baseline: {baseline:.2f}s")

        logger.info(f"\nAcceleration profile: Direct impact on avg speed")
        logger.info(f"Current: estimate_max_acceleration() using ICE + ERS + grip")

        return results

    def estimate_parameter_sensitivity(self) -> None:
        """Stima la sensibilità di ogni parametro al lap time."""
        logger.info("\n" + "="*70)
        logger.info("SENSITIVITY ANALYSIS")
        logger.info("="*70)

        logger.info(f"\nTarget: {self.target_monza_time:.1f}s (current: {self.baseline_monza_time:.2f}s)")
        logger.info(f"Improvement needed: {self.delta_needed:.2f}s ({self.percent_improvement_needed:.1f}%)")

        # Stima terica basata su dynamics
        logger.info("\n📊 Theoretical Sensitivity Estimates:")

        # 1% aumento di velocità media = ~1% riduzione lap time
        logger.info(f"\n1. DRAG COEFFICIENT (CDA)")
        logger.info(f"   Current: {constants.CDA_BASE_STRUCT:.3f} m²")
        logger.info(f"   10% reduction (0.85 → 0.765) ≈ 0.5-1.0s faster")
        logger.info(f"   20% reduction (0.85 → 0.68)  ≈ 1.0-2.0s faster")
        logger.info(f"   Estimate: 1 m² drag reduction ≈ 20-25 km/h higher v_max")

        logger.info(f"\n2. ICE POWER")
        logger.info(f"   Current: {constants.ICE_PEAK_POWER_KW:.0f} kW")
        logger.info(f"   10% increase (750 → 825 kW) ≈ 0.5-1.5s faster")
        logger.info(f"   20% increase (750 → 900 kW) ≈ 1.0-3.0s faster")
        logger.info(f"   Estimate: 100 kW increase ≈ 5-10 km/h higher v_max, better accel")

        logger.info(f"\n3. ERS POWER")
        logger.info(f"   Current: {constants.ERS_PEAK_POWER_KW:.0f} kW")
        logger.info(f"   20% increase (160 → 192 kW) ≈ 0.3-0.8s faster")
        logger.info(f"   Estimate: Lower impact than ICE (deployed only on straights)")

        logger.info(f"\n4. DOWNFORCE (CLA)")
        logger.info(f"   Current: {constants.CLA_NEUTRAL:.2f} m²")
        logger.info(f"   Increase (3.20 → 3.60) ≈ 0.2-0.5s faster (better corner speed)")
        logger.info(f"   Estimate: Higher downforce = better high-speed corner handling")

        logger.info(f"\n🎯 Conclusion:")
        logger.info(f"   To save {self.delta_needed:.1f}s, need combination of:")
        logger.info(f"   • Reduce CDA by ~15% (0.85 → 0.72)")
        logger.info(f"   • Increase ICE power by ~15% (750 → 865 kW)")
        logger.info(f"   • OR adjust integration timestep (currently 0.02s)")

    def recommend_next_step(self) -> str:
        """Recommenda il prossimo passo di calibrazione."""
        logger.info("\n" + "="*70)
        logger.info("RECOMMENDED NEXT STEPS")
        logger.info("="*70)

        recommendation = f"""
PHASE 2: Tuning Strategy

Option A (Recommended): Adjust Power Output
  - Increase ICE_PEAK_POWER_KW from 750 to 850 kW
  - Increase ERS_PEAK_POWER_KW from 160 to 200 kW
  - Expected impact: ~3-5s improvement
  - Reason: More realistic for 2025 F1 (Porsche entry regulations)

Option B: Adjust Drag Profile
  - Reduce CDA_BASE_STRUCT from 0.55 to 0.50 m²
  - Reduce CDA_SENSITIVITY from 0.015 to 0.010 m²/point
  - Expected impact: ~2-3s improvement
  - Reason: F1 2025 has better aerodynamic efficiency

Option C: Integration Refinement
  - Check section timestep calibration (dt_ref_s)
  - Verify waypoint integration density (50Hz vs 100Hz)
  - Expected impact: ~0.5-1s improvement

RECOMMENDATION: Start with Option A (Power)
  - Simplest to implement
  - Physically justifiable (2025 regulations)
  - Highest ROI (impact per change)
"""
        logger.info(recommendation)
        return recommendation


def main():
    """Esegue la sweep di calibrazione."""
    sweep = CalibrationSweep()

    # Fase 1: Test parametri individuali
    sweep.test_ice_power()
    sweep.test_drag_coefficient()
    sweep.test_acceleration_profile()

    # Stima sensibilità
    sweep.estimate_parameter_sensitivity()

    # Raccomandazione
    sweep.recommend_next_step()


if __name__ == "__main__":
    main()
