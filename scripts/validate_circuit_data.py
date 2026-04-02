#!/usr/bin/env python3
"""
validate_circuit_data.py - Validazione Dati HD Telemetry per LapSimulator

Analizza la qualità dei dati HD telemetry e calcola raggi di curvatura mancanti.

USO:
    python3 scripts/validate_circuit_data.py <circuit_id>

Esempi:
    python3 scripts/validate_circuit_data.py jp-1962_suzuka
    python3 scripts/validate_circuit_data.py it-1922_monza
    python3 scripts/validate_circuit_data.py mc-1929_monaco

OUTPUT:
    - Report console con metriche qualità dati
    - JSON in logs/<circuit_id>_validation.json
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Aggiungi il percorso del progetto
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def load_circuit_data(circuit_id: str) -> Dict[str, Any]:
    """Load circuit HD telemetry data."""
    project_root = Path(__file__).resolve().parent.parent
    hd_file = project_root / "python_backend" / "data" / "circuits" / "2025" / f"{circuit_id}_HD.json"
    
    if not hd_file.exists():
        raise FileNotFoundError(f"HD telemetry file not found: {hd_file}")
    
    with open(hd_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_waypoints(waypoints: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate waypoints data quality."""
    results = {
        "total_waypoints": len(waypoints),
        "valid_radius": 0,
        "missing_radius": 0,
        "missing_radius_percentage": 0.0,
        "valid_g_lat": 0,
        "missing_g_lat": 0,
        "missing_g_lat_percentage": 0.0,
        "radius_range": (None, None),
        "g_lat_range": (None, None),
        "section_kinds": {},
    }
    
    for wp in waypoints:
        # Check radius
        radius = wp.get('radius_m', 0)
        if radius > 0 and radius < 999999:
            results["valid_radius"] += 1
            if results["radius_range"][0] is None:
                results["radius_range"] = (radius, radius)
            else:
                results["radius_range"] = (
                    min(results["radius_range"][0], radius),
                    max(results["radius_range"][1], radius)
                )
        else:
            results["missing_radius"] += 1
        
        # Check g_lat
        g_lat = wp.get('target_g_lat', 0)
        if g_lat is not None and g_lat > 0.001:
            results["valid_g_lat"] += 1
            if results["g_lat_range"][0] is None:
                results["g_lat_range"] = (g_lat, g_lat)
            else:
                results["g_lat_range"] = (
                    min(results["g_lat_range"][0], g_lat),
                    max(results["g_lat_range"][1], g_lat)
                )
        else:
            results["missing_g_lat"] += 1
        
        # Count section kinds
        section_kind = wp.get('section_kind', 'Unknown')
        results["section_kinds"][section_kind] = results["section_kinds"].get(section_kind, 0) + 1
    
    # Calculate percentages
    total = len(waypoints)
    if total > 0:
        results["missing_radius_percentage"] = 100 * results["missing_radius"] / total
        results["missing_g_lat_percentage"] = 100 * results["missing_g_lat"] / total
    
    return results


def calculate_radius_from_g_lat(g_lat: float, v_kph: float, 
                                   df_ref: float = 180.0, drag_ref: float = 30.0,
                                   mass_kg: float = 798.0) -> float:
    """
    Calculate radius from target_g_lat and v_kph.
    
    Formula:
    F_lat = mass * g_lat * 9.81
    F_lat = 0.5 * RHO * v² * CLA_REF + (mass² * g²) / radius
    radius = (mass * 9.81) / (F_lat - 0.5 * RHO * v² * CLA_REF)
    
    dove:
    - F_lat = mass * g_lat * 9.81
    - CLA_REF = df_ref * 0.020
    """
    RHO = 1.225  # kg/m³
    
    v_ms = v_kph / 3.6
    CLA_REF = df_ref * 0.020
    
    F_lat = mass_kg * g_lat * 9.81
    F_df = 0.5 * RHO * (v_ms ** 2) * CLA_REF
    
    denominator = F_lat - F_df
    if denominator <= 0:
        return 999999  # No corner (straight)
    
    radius = (mass_kg * 9.81) / denominator
    
    return radius


def calculate_missing_radius(v_min_kph: float, telemetry_mu: float = 1.6, 
                                df_ref: float = 180.0, drag_ref: float = 30.0,
                                mass_kg: float = 798.0) -> float:
    """
    Calculate missing radius from v_min_kph and telemetry_mu.
    
    Formula:
    radius = (mass * 9.81) / ((mass / v_min_ms²) + (0.5 * RHO * CLA_REF))
    
    dove:
    - v_min_ms = v_min_kph / 3.6
    - RHO = 1.225 (air density)
    - CLA_REF = df_ref * 0.020 (downforce coefficient)
    """
    RHO = 1.225  # kg/m³
    
    v_min_ms = v_min_kph / 3.6
    CLA_REF = df_ref * 0.020
    
    term1 = (mass_kg * 9.81) / (v_min_ms ** 2)
    term2 = 0.5 * RHO * CLA_REF
    
    radius = mass_kg / (term1 + term2)
    
    return radius


def analyze_circuit(circuit_id: str) -> Dict[str, Any]:
    """Analyze circuit data quality and provide recommendations."""
    data = load_circuit_data(circuit_id)
    
    waypoints = data.get('waypoints', [])
    sections = data.get('sections', [])
    
    # Validate waypoints
    wp_results = validate_waypoints(waypoints)
    
    # Analyze sections
    section_results = {
        "total_sections": len(sections),
        "corner_sections": 0,
        "straight_sections": 0,
        "v_min_kph": [],
        "v_max_kph": [],
    }
    
    for sec in sections:
        if sec.get('kind', '').lower().startswith('straight'):
            section_results["straight_sections"] += 1
        else:
            section_results["corner_sections"] += 1
            if 'v_min_kph' in sec:
                section_results["v_min_kph"].append(sec['v_min_kph'])
            if 'v_max_kph' in sec:
                section_results["v_max_kph"].append(sec['v_max_kph'])
    
    # Calculate missing radii
    missing_radii = []
    for i, wp in enumerate(waypoints):
        if wp.get('radius_m', 0) >= 999999:
            # Check if this is a corner
            g_lat = wp.get('target_g_lat', 0)
            v_kph = wp.get('v_ref_kph', 0)
            
            if g_lat > 0.01 and v_kph > 50:
                # This is a corner, calculate radius
                radius = calculate_radius_from_g_lat(g_lat, v_kph)
                missing_radii.append({
                    "index": i,
                    "dist_m": wp.get('dist_m', 0),
                    "v_kph": v_kph,
                    "g_lat": g_lat,
                    "calculated_radius": radius
                })
    
    return {
        "circuit_id": circuit_id,
        "waypoint_analysis": wp_results,
        "section_analysis": section_results,
        "missing_radii": missing_radii[:10],  # First 10 for preview
        "total_missing_radii": len(missing_radii),
    }


def print_analysis(analysis: Dict[str, Any]) -> None:
    """Print analysis results."""
    print(f"\n{'='*80}")
    print(f"CIRCUIT ANALYSIS: {analysis['circuit_id']}")
    print(f"{'='*80}\n")
    
    # Waypoint analysis
    wp = analysis['waypoint_analysis']
    print("WAYPOINT ANALYSIS:")
    print(f"  Total waypoints: {wp['total_waypoints']}")
    print(f"  Valid radius: {wp['valid_radius']} ({100-wp['missing_radius_percentage']:.1f}%)")
    print(f"  Missing radius: {wp['missing_radius']} ({wp['missing_radius_percentage']:.1f}%)")
    if wp['radius_range'][0] is not None:
        print(f"  Radius range: {wp['radius_range'][0]:.0f} - {wp['radius_range'][1]:.0f} m")
    print(f"  Valid g_lat: {wp['valid_g_lat']} ({100-wp['missing_g_lat_percentage']:.1f}%)")
    print(f"  Missing g_lat: {wp['missing_g_lat']} ({wp['missing_g_lat_percentage']:.1f}%)")
    if wp['g_lat_range'][0] is not None:
        print(f"  g_lat range: {wp['g_lat_range'][0]:.3f} - {wp['g_lat_range'][1]:.3f} g")
    
    # Section analysis
    sec = analysis['section_analysis']
    print(f"\nSECTION ANALYSIS:")
    print(f"  Total sections: {sec['total_sections']}")
    print(f"  Corner sections: {sec['corner_sections']}")
    print(f"  Straight sections: {sec['straight_sections']}")
    if sec['v_min_kph']:
        print(f"  V_min range: {min(sec['v_min_kph']):.1f} - {max(sec['v_min_kph']):.1f} kph")
    if sec['v_max_kph']:
        print(f"  V_max range: {min(sec['v_max_kph']):.1f} - {max(sec['v_max_kph']):.1f} kph")
    
    # Missing radii
    print(f"\nMISSING RADIUS ANALYSIS:")
    print(f"  Total missing: {analysis['total_missing_radii']}")
    if analysis['missing_radii']:
        print(f"  Sample calculations (first 10):")
        for mr in analysis['missing_radii'][:5]:
            print(f"    dist={mr['dist_m']:.0f}m, v={mr['v_kph']:.0f}kph, g_lat={mr['g_lat']:.3f} → R={mr['calculated_radius']:.0f}m")
    
    # Recommendations
    print(f"\nRECOMMENDATIONS:")
    if wp['missing_radius'] > 0:
        print(f"  ⚠️  {wp['missing_radius']} waypoints missing radius_m")
        print(f"     → Use calculate_radius_from_g_lat() or calculate_missing_radius()")
    if wp['missing_g_lat'] > 0:
        print(f"  ⚠️  {wp['missing_g_lat']} waypoints missing target_g_lat")
        print(f"     → Estimate from telemetry_mu or v_min_kph")
    
    # Section kind breakdown
    print(f"\nSECTION KIND BREAKDOWN:")
    for kind, count in sorted(wp['section_kinds'].items(), key=lambda x: -x[1]):
        pct = 100 * count / wp['total_waypoints']
        print(f"  {kind}: {count} ({pct:.1f}%)")


def save_analysis(analysis: Dict[str, Any], output_dir: Path = Path("logs")) -> None:
    """Save analysis results to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().isoformat()
    output_file = output_dir / f"{analysis['circuit_id']}_validation.json"
    
    output_data = {
        "analysis_timestamp": timestamp,
        "circuit_id": analysis['circuit_id'],
        "waypoint_analysis": analysis['waypoint_analysis'],
        "section_analysis": analysis['section_analysis'],
        "missing_radii": analysis['missing_radii'],
        "total_missing_radii": analysis['total_missing_radii'],
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Analysis saved to {output_file}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Validazione dati HD telemetry per LapSimulator"
    )
    parser.add_argument(
        "circuit_id",
        help="Circuit ID (e.g., jp-1962_suzuka, it-1922_monza, mc-1929_monaco)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="logs",
        help="Output directory for analysis JSON (default: logs)"
    )
    
    args = parser.parse_args()
    
    try:
        analysis = analyze_circuit(args.circuit_id)
        print_analysis(analysis)
        save_analysis(analysis, Path(args.output_dir))
        
        print(f"\n{'='*80}")
        print("VALIDATION COMPLETE")
        print(f"{'='*80}")
        
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
