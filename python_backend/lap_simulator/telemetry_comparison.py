"""
Telemetry Comparison — Physics V3 vs Real F1 2025 Data

Confronta i dati simulati (microsettori) con i dati reali di telemetria
per identificare divergenze significative nel modello.
"""

import json
import os
from typing import Dict, List, Tuple, Any
import logging

from .lap_simulator_v3 import LapSimulatorV3, CarEntryV3
from .data_types import AeroSetup, DriverSkills, EnvContext, AeroComponent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TelemetryComparison:
    """Compara dati simulati vs telemetria reale."""

    def __init__(self, circuit_id: str = "it-1922_monza"):
        self.circuit_id = circuit_id
        self.sim_data = None
        self.real_data = None

    def load_real_telemetry(self, filepath: str) -> Dict[str, Any]:
        """Carica dati telemetria reale da JSON."""
        if not os.path.exists(filepath):
            logger.warning(f"Real telemetry file not found: {filepath}")
            return {}

        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading telemetry: {e}")
            return {}

    def simulate_lap(self) -> List[Dict[str, float]]:
        """Esegue simulazione e estrae i dati di telemetria."""
        aero_setup = AeroSetup()
        aero_setup.front_wing = AeroComponent(name='front_wing', base_downforce=14.0, angle_deg=16.0)
        aero_setup.rear_wing = AeroComponent(name='rear_wing', base_downforce=16.0, angle_deg=16.0)

        driver = DriverSkills(raw_pace=70)
        env = EnvContext(air_temp_c=20.0, track_temp_c=40.0)

        entry = CarEntryV3(
            car_id="TELEMETRY_TEST",
            aero_setup=aero_setup,
            driver_skills=driver,
            push_level=10,
        )

        sim = LapSimulatorV3(debug=False)
        results = sim.run_lap([entry], self.circuit_id, is_qualifying=True, env=env)

        if not results:
            logger.error("Simulation failed")
            return []

        # Estrai tutti i telemetry points
        all_points = []
        for section_result in results[0].section_results:
            all_points.extend(section_result.telemetry_points)

        return all_points

    def extract_real_telemetry_points(self, real_data: Dict) -> List[Dict[str, float]]:
        """Estrae i dati dalla telemetria reale (sezioni macro)."""
        if not real_data or 'geometry' not in real_data:
            logger.warning("No geometry in real data")
            return []

        sections = real_data.get('geometry', {}).get('sections', [])
        if not sections:
            logger.warning("No sections in geometry")
            return []

        points = []
        dist_m = 0.0
        for section in sections:
            # Estrai i dati dalla sezione
            section_length = section.get('length_m', 0)
            v_entry = section.get('v_entry_kph', 0)
            v_exit = section.get('v_exit_kph', 0)
            v_avg = section.get('avg_speed', 0)

            # Usa v_avg come velocità di riferimento per la sezione
            if v_avg > 0:
                points.append({
                    'dist_m': dist_m + section_length / 2,  # Centro della sezione
                    'v_kph': v_avg,
                    'v_entry_kph': v_entry,
                    'v_exit_kph': v_exit,
                    'section_length_m': section_length,
                    'radius_m': section.get('radius_m', 0) or 0,
                })

            dist_m += section_length

        logger.info(f"Extracted {len(points)} real telemetry points from {len(sections)} sections")
        return points

    def compare_data(self, sim_points: List[Dict], real_points: List[Dict]) -> Dict[str, Any]:
        """Confronta i due dataset e identifica differenze."""
        if not sim_points or not real_points:
            return {
                'status': 'insufficient_data',
                'sim_points': len(sim_points),
                'real_points': len(real_points),
            }

        # Per ogni punto reale (sezione), trova il corrispondente sim_point
        diffs = []

        for real_pt in real_points:
            real_dist = real_pt['dist_m']
            real_v = real_pt['v_kph']

            # Trova il sim_point più vicino
            closest_sim = min(sim_points, key=lambda p: abs(p['dist_m'] - real_dist))
            sim_dist = closest_sim['dist_m']
            sim_v = closest_sim['v_kph']

            delta = sim_v - real_v

            diffs.append({
                'dist_m': real_dist,
                'sim_dist_m': sim_dist,
                'sim_v_kph': sim_v,
                'real_v_kph': real_v,
                'delta_v_kph': delta,
                'delta_pct': (delta / real_v * 100) if real_v > 0 else 0,
                'section': real_pt.get('section_length_m', 0),
            })

        # Analisi
        avg_delta = sum(d['delta_v_kph'] for d in diffs) / len(diffs) if diffs else 0
        max_delta = max(abs(d['delta_v_kph']) for d in diffs) if diffs else 0

        # Conta sezioni dove sim è più veloce
        faster_count = sum(1 for d in diffs if d['delta_v_kph'] > 5)
        slower_count = sum(1 for d in diffs if d['delta_v_kph'] < -5)

        return {
            'status': 'success',
            'num_comparison_points': len(diffs),
            'avg_delta_v_kph': avg_delta,
            'max_delta_v_kph': max_delta,
            'avg_delta_pct': (avg_delta / 250 * 100) if avg_delta != 0 else 0,  # % vs ~250 kph avg
            'faster_sections': faster_count,
            'slower_sections': slower_count,
            'diffs': diffs,
        }

    def _interpolate_on_grid(self, points: List[Dict], grid: List[float], key: str) -> List[float]:
        """Interpola linearly i dati su una griglia di distanze."""
        values = []
        for grid_dist in grid:
            # Trova i due punti più vicini
            closest = min(points, key=lambda p: abs(p['dist_m'] - grid_dist))
            values.append(closest.get(key, 0))

        return values

    def generate_report(self) -> str:
        """Genera un report di comparazione."""
        logger.info("="*70)
        logger.info("TELEMETRY COMPARISON REPORT")
        logger.info("="*70)

        # Simula
        logger.info("\n[1] Running simulation...")
        sim_points = self.simulate_lap()
        logger.info(f"    Simulation completed: {len(sim_points)} telemetry points")

        # Carica dati reali
        real_telemetry_path = f"python_backend/data/circuits/2025/{self.circuit_id}_Telemetry.json"
        logger.info(f"\n[2] Loading real telemetry from {real_telemetry_path}...")
        real_data = self.load_real_telemetry(real_telemetry_path)
        real_points = self.extract_real_telemetry_points(real_data)
        logger.info(f"    Real telemetry loaded: {len(real_points)} waypoints")

        # Compara
        logger.info("\n[3] Comparing data...")
        comparison = self.compare_data(sim_points, real_points)

        # Report
        logger.info("\n" + "="*70)
        logger.info("RESULTS")
        logger.info("="*70)

        if comparison['status'] == 'success':
            logger.info(f"\nAverage velocity delta: {comparison['avg_delta_v_kph']:.2f} km/h ({comparison['avg_delta_pct']:.1f}%)")
            logger.info(f"Max velocity delta:     {comparison['max_delta_v_kph']:.2f} km/h")
            logger.info(f"Sections where sim FASTER: {comparison['faster_sections']} (>5 km/h)")
            logger.info(f"Sections where sim SLOWER: {comparison['slower_sections']} (<-5 km/h)")

            # Mostra i 10 punti con maggior divergenza
            diffs = comparison['diffs']
            diffs_sorted = sorted(diffs, key=lambda d: abs(d['delta_v_kph']), reverse=True)

            logger.info("\nTop 10 divergence sections:")
            logger.info("Distance | Sim Speed | Real Speed | Delta(km/h) | Delta(%)")
            logger.info("-"*70)
            for d in diffs_sorted[:10]:
                logger.info(f"{d['dist_m']:7.0f}m | {d['sim_v_kph']:8.1f} | {d['real_v_kph']:9.1f} | {d['delta_v_kph']:+8.1f} | {d['delta_pct']:+6.1f}%")

            # Analisi sistematica
            if comparison['avg_delta_v_kph'] > 5:
                logger.warning(f"\n⚠️  SIM TOO FAST: Simulation is {abs(comparison['avg_delta_v_kph']):.1f} km/h faster than reality")
                logger.warning("   → Likely causes: drag too low, grip too high, corner speeds too optimistic")
            elif comparison['avg_delta_v_kph'] < -5:
                logger.warning(f"\n⚠️  SIM TOO SLOW: Simulation is {abs(comparison['avg_delta_v_kph']):.1f} km/h slower than reality")
                logger.warning("   → Likely causes: drag too high, grip too low, corner speeds too conservative")
            else:
                logger.info("\n✓ Simulation velocity profile matches reality well (within ±5 km/h)")

        else:
            logger.error(f"Comparison failed: {comparison['status']}")
            logger.error(f"Sim points: {comparison.get('sim_points', 0)}, Real points: {comparison.get('real_points', 0)}")

        return f"Report generated for {self.circuit_id}"


def main():
    """Main entry point."""
    comparator = TelemetryComparison(circuit_id="it-1922_monza")
    report = comparator.generate_report()
    print(report)


if __name__ == "__main__":
    main()
