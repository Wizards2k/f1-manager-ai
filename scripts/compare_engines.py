#!/usr/bin/env python3
"""
compare_engines.py - Confronto Motore Fisico v1 vs v2

Questo script confronta i risultati del motore fisico v1 (session_bridge.py)
con il motore v2 (session_bridge_v2.py) per validare che v2 produca risultati
fisicamente coerenti.

USO:
    python3 scripts/compare_engines.py --circuit <circuit_id> --n-laps <n>

Esempi:
    python3 scripts/compare_engines.py --circuit it-1922_monza --n-laps 1
    python3 scripts/compare_engines.py --circuit jp-1962_suzuka --n-laps 1
    python3 scripts/compare_engines.py --circuit mc-1929_monaco --n-laps 1

OUTPUT:
    - Confronto microsettore per microsettore
    - Delta tempo per sezione
    - Delta tempo per giro
    - Report CSV/JSON per analisi

Reference: docs/lap-physics-spec-v0.5.md, docs/lap-physics-v2-analysis.md
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Aggiungi il percorso del progetto
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "python_backend"))

# Import v1 (LapSimulator)
try:
    from lap_simulator.lap_simulator import LapSimulator, CarEntry
    from lap_simulator.data_types import CarState, CircuitConfig, EnvContext, DriverSkills, AeroSetup
    from lap_simulator.config_loader import load_circuit_config
    V1_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import v1 modules: {e}")
    V1_AVAILABLE = False

# Import v2 (se disponibile)
try:
    from lap_simulator.lap_simulator_v2 import LapSimulatorV2, CarEntryV2
    V2_AVAILABLE = True
except ImportError:
    V2_AVAILABLE = False
    logger.warning("⚠️  LapSimulatorV2 non disponibile - implementare lap_simulator_v2.py")


def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/compare_engines.log', mode='w'),
        ]
    )


def load_circuit(circuit_id: str) -> Tuple[CircuitConfig, EnvContext]:
    """Load circuit configuration and environment."""
    config = load_circuit_config(circuit_id)
    env = EnvContext()
    return config, env


def create_test_car(
    circuit_config: CircuitConfig,
    team_name: str = "Test Team",
    driver_name: str = "Test Driver",
    is_player: bool = False,
) -> CarEntry:
    """Create a test car for comparison."""
    # Create a minimal car state
    state = CarState()
    state.car_id = "test_car"
    state.team_code = team_name
    state.lap_number = 1
    
    # Create aero setup (neutral)
    aero_setup = AeroSetup()
    
    # Create driver skills
    driver_skills = DriverSkills()
    driver_skills.raw_pace = 50
    driver_skills.race_craft = 50
    driver_skills.consistency = 50
    
    # Create car entry
    car_entry = CarEntry(
        car_id="test_car",
        state=state,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        push_level=10,
        delta_aero=0.0,
        delta_grip=0.0,
        apply_baseline_delta=True,
    )
    
    return car_entry


def run_lap_v1(
    circuit_config: CircuitConfig,
    env: EnvContext,
    car_entry: CarEntry,
    n_laps: int = 1,
) -> Dict[str, Any]:
    """Run lap with v1 engine (LapSimulator)."""
    logger.info("Running lap with v1 engine (LapSimulator)")
    
    sim = LapSimulator(circuit_config, env)
    sim.register_car(car_entry)
    
    results = sim.run_lap()
    
    # Extract results
    lap_result = results.get("test_car")
    if lap_result:
        return {
            "lap_time_s": lap_result.lap_time_s,
            "sector_times_s": lap_result.sector_times_s,
            "section_results": lap_result.section_results,
            "events": lap_result.events,
        }
    else:
        logger.error("Failed to get lap result from v1 engine")
        return {}


def run_lap_v2(
    circuit_config: CircuitConfig,
    env: EnvContext,
    car_entry: CarEntry,
    n_laps: int = 1,
) -> Dict[str, Any]:
    """Run lap with v2 engine (LapSimulatorV2)."""
    logger.warning("⚠️  LapSimulatorV2 non ancora implementato - usare v1 per ora")
    return run_lap_v1(circuit_config, env, car_entry, n_laps)  # Fallback a v1


def compare_results(
    v1_results: Dict[str, Any],
    v2_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare v1 and v2 results."""
    comparison = {
        "lap_time_delta_s": v2_results.get("lap_time_s", 0) - v1_results.get("lap_time_s", 0),
        "sector_deltas_s": [],
        "section_deltas_s": [],
    }
    
    # Compare sector times
    v1_sectors = v1_results.get("sector_times_s", [])
    v2_sectors = v2_results.get("sector_times_s", [])
    for i, (v1_s, v2_s) in enumerate(zip(v1_sectors, v2_sectors)):
        comparison["sector_deltas_s"].append({
            "sector": i + 1,
            "v1_s": v1_s,
            "v2_s": v2_s,
            "delta_s": v2_s - v1_s,
        })
    
    # Compare section times
    v1_sections = v1_results.get("section_results", [])
    v2_sections = v2_results.get("section_results", [])
    for i, (v1_sec, v2_sec) in enumerate(zip(v1_sections, v2_sections)):
        if v1_sec and v2_sec:
            comparison["section_deltas_s"].append({
                "section_idx": i,
                "section_id": getattr(v1_sec, "section_id", f"sec_{i}"),
                "v1_dt_s": getattr(v1_sec, "dt_s", 0),
                "v2_dt_s": getattr(v2_sec, "dt_s", 0),
                "delta_dt_s": getattr(v2_sec, "dt_s", 0) - getattr(v1_sec, "dt_s", 0),
            })
    
    return comparison


def save_comparison(
    comparison: Dict[str, Any],
    circuit_id: str,
    output_dir: Path = Path("reports/compare_engines"),
) -> None:
    """Save comparison results to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().isoformat()
    output_file = output_dir / f"{circuit_id}_comparison_{timestamp}.json"
    
    output_data = {
        "timestamp": timestamp,
        "circuit_id": circuit_id,
        "comparison": comparison,
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Comparison saved to {output_file}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Confronto motore fisico v1 vs v2 per validazione"
    )
    parser.add_argument(
        "--circuit",
        required=True,
        help="Circuit ID (e.g., it-1922_monza, jp-1962_suzuka, mc-1929_monaco)"
    )
    parser.add_argument(
        "--n-laps",
        type=int,
        default=1,
        help="Number of laps to simulate (default: 1)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports/compare_engines",
        help="Output directory for comparison results"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    logger.info("=" * 80)
    logger.info("CONFRONTO MOTORI FISICI v1 vs v2")
    logger.info("=" * 80)
    logger.info(f"Circuit: {args.circuit}")
    logger.info(f"Laps: {args.n_laps}")
    logger.info(f"Output dir: {args.output_dir}")
    
    # Load circuit
    try:
        circuit_config, env = load_circuit(args.circuit)
        logger.info(f"Circuit loaded: {circuit_config.circuit_id}, {len(circuit_config.sections)} sections")
    except Exception as e:
        logger.error(f"Failed to load circuit: {e}")
        sys.exit(1)
    
    # Create test car
    car_entry = create_test_car(circuit_config)
    logger.info("Test car created")
    
    # Run v1
    v1_results = run_lap_v1(circuit_config, env, car_entry, args.n_laps)
    if not v1_results:
        logger.error("Failed to run v1 engine")
        sys.exit(1)
    
    logger.info(f"V1 lap time: {v1_results['lap_time_s']:.3f}s")
    
    # Run v2 (se disponibile)
    logger.warning("⚠️  V2 engine non ancora implementato - usare v1 per ora")
    v2_results = run_lap_v1(circuit_config, env, car_entry, args.n_laps)  # Fallback a v1
    
    logger.info(f"V2 lap time: {v2_results['lap_time_s']:.3f}s")
    
    # Compare
    comparison = compare_results(v1_results, v2_results)
    
    logger.info(f"Lap time delta: {comparison['lap_time_delta_s']:+.3f}s")
    
    # Save comparison
    save_comparison(comparison, args.circuit, Path(args.output_dir))
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"V1 lap time: {v1_results['lap_time_s']:.3f}s")
    print(f"V2 lap time: {v2_results['lap_time_s']:.3f}s")
    print(f"Delta: {comparison['lap_time_delta_s']:+.3f}s")
    
    if comparison['sector_deltas_s']:
        print("\nSector deltas:")
        for sector in comparison['sector_deltas_s']:
            print(f"  Sector {sector['sector']}: V1={sector['v1_s']:.3f}s, V2={sector['v2_s']:.3f}s, Δ={sector['delta_s']:+.3f}s")
    
    if comparison['section_deltas_s']:
        print("\nSection deltas (first 5):")
        for section in comparison['section_deltas_s'][:5]:
            print(f"  {section['section_id']}: V1={section['v1_dt_s']:.4f}s, V2={section['v2_dt_s']:.4f}s, Δ={section['delta_dt_s']:+.4f}s")
    
    print("\n" + "=" * 80)
    print("CONFRONTO COMPLETATO")
    print("=" * 80)


if __name__ == "__main__":
    main()
