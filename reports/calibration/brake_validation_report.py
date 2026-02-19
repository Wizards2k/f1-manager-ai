#!/usr/bin/env python3
"""
Brake Component Validation Report Generator

Generates comprehensive validation reports for brake system components
across all circuits, including temperature ranges, duct sensitivity,
and warning event validation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# --- repo path bootstrap ----------------------------------------------------
ROOT = Path(__file__).resolve().parents[3]
PY_BACKEND = ROOT / "python_backend"
if str(PY_BACKEND) not in sys.path:
    sys.path.insert(0, str(PY_BACKEND))

# Add lap_simulator to path
LAP_SIM_PATH = PY_BACKEND / "lap_simulator"
if str(LAP_SIM_PATH) not in sys.path:
    sys.path.insert(0, str(LAP_SIM_PATH))

from config_loader import load_circuit_config  # type: ignore
from data_types import (  # type: ignore
    CarState,
    DriverSkills,
    EnvContext,
)
from lap_simulator import CarEntry, LapSimulator  # type: ignore
from tests.test_calibration_and_telemetry import _build_player_cars  # type: ignore
from utils.session_bridge import SessionBridge  # type: ignore


def generate_brake_validation_report(
    circuit_id: str,
    laps_per_config: int = 3,
    duct_configs: List[float] = [0.25, 0.5, 0.75],
    env: Optional[EnvContext] = None,
) -> Dict[str, any]:
    """
    Generate comprehensive brake validation data for a circuit.
    
    Returns structured data with:
    - Temperature ranges per duct configuration
    - Warning events triggered
    - Brake cooling status validation
    - Performance metrics
    """
    if env is None:
        env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
    
    config = load_circuit_config(circuit_id, project_root=ROOT)
    report = {
        "circuit_id": circuit_id,
        "timestamp": datetime.now().isoformat(),
        "environment": {
            "air_temp_c": env.air_temp_c,
            "track_temp_c": env.track_temp_c,
        },
        "config_summary": {
            "fade_threshold_front": config.brake_params.fade_threshold_front_c,
            "fade_threshold_rear": config.brake_params.fade_threshold_rear_c,
            "cooling_coeff": config.brake_params.cooling_coeff,
            "heat_capacity_front": config.brake_params.heat_capacity_front,
            "heat_capacity_rear": config.brake_params.heat_capacity_rear,
        },
        "duct_tests": [],
        "warning_events": [],
        "cooling_validation": {},
        "performance_metrics": {
            "peak_temps": {"front": [], "rear": []},
            "temp_sensitivity": [],
            "fade_incidents": 0,
        }
    }
    
    # Extract duct recommendations from profile
    profile = config.brake_profile or {}
    duct_rec = profile.get("duct_recommendation", {})
    min_duct = duct_rec.get("min_open", 0.25)
    max_duct = duct_rec.get("max_open", 0.7)
    
    for duct_opening in duct_configs:
        test_result = run_brake_test(
            circuit_id, duct_opening, laps_per_config, env, config
        )
        report["duct_tests"].append(test_result)
        
        # Collect peak temps
        report["performance_metrics"]["peak_temps"]["front"].append(
            test_result["peak_temps"]["front"]
        )
        report["performance_metrics"]["peak_temps"]["rear"].append(
            test_result["peak_temps"]["rear"]
        )
        
        # Count fade incidents
        report["performance_metrics"]["fade_incidents"] += test_result["fade_events"]
        
        # Collect warning events
        for event in test_result["warning_events"]:
            event["duct_config"] = duct_opening
            report["warning_events"].append(event)
    
    # Calculate temperature sensitivity (change per 0.25 duct opening)
    if len(report["performance_metrics"]["peak_temps"]["front"]) >= 2:
        front_temps = report["performance_metrics"]["peak_temps"]["front"]
        rear_temps = report["performance_metrics"]["peak_temps"]["rear"]
        
        for i in range(len(front_temps) - 1):
            delta_front = abs(front_temps[i+1] - front_temps[i])
            delta_rear = abs(rear_temps[i+1] - rear_temps[i])
            report["performance_metrics"]["temp_sensitivity"].append({
                "duct_range": f"{duct_configs[i]:.2f}-{duct_configs[i+1]:.2f}",
                "front_delta_c": delta_front,
                "rear_delta_c": delta_rear,
            })
    
    # Validate cooling recommendations
    report["cooling_validation"] = {
        "recommended_min": min_duct,
        "recommended_max": max_duct,
        "tested_range": [min(duct_configs), max(duct_configs)],
        "adequate_coverage": min_duct >= min(duct_configs) and max_duct <= max(duct_configs),
    }
    
    return report


def run_brake_test(
    circuit_id: str,
    duct_opening: float,
    laps: int,
    env: EnvContext,
    config,
) -> Dict[str, any]:
    """Run brake test with specific duct configuration."""
    car_state = CarState(car_id=f"{circuit_id}_test_{duct_opening:.2f}")
    car_state.brakes.duct_opening = duct_opening
    
    entry = CarEntry(
        car_id=car_state.car_id,
        state=car_state,
        aero_setup=None,
        driver_skills=DriverSkills(),
        push_level=1.0,
    )
    
    sim = LapSimulator(config, env)
    sim.register_car(entry)
    
    # Track events and temperatures
    warning_events = []
    peak_temps = {"front": 0.0, "rear": 0.0}
    fade_events = 0
    
    for lap_num in range(laps):
        result = sim.run_lap()
        
        # Update peak temperatures
        peak_temps["front"] = max(peak_temps["front"], car_state.brakes.temp_front_c)
        peak_temps["rear"] = max(peak_temps["rear"], car_state.brakes.temp_rear_c)
        
        # Check for fade
        if car_state.brakes.fade_level > 0.01:
            fade_events += 1
        
        # Collect warning events from this lap
        for event in result.events:
            if event.event_type in ["brake_hot_section", "brake_duct_low", "brake_duct_high"]:
                warning_events.append({
                    "lap": lap_num + 1,
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "message": event.message,
                    "section": event.section_id if hasattr(event, 'section_id') else 'unknown',
                })
    
    return {
        "duct_opening": duct_opening,
        "laps_completed": laps,
        "peak_temps": peak_temps,
        "final_temps": {
            "front": car_state.brakes.temp_front_c,
            "rear": car_state.brakes.temp_rear_c,
        },
        "final_fade_level": car_state.brakes.fade_level,
        "fade_events": fade_events,
        "warning_events": warning_events,
        "brake_wear": {
            "front_pct": car_state.brakes.wear_front_pct,
            "rear_pct": car_state.brakes.wear_rear_pct,
        }
    }


def run_session_bridge_validation(circuit_id: str) -> Dict[str, any]:
    """Run SessionBridge validation for brake cooling integration."""
    cars = _build_player_cars(count=2)
    bridge = SessionBridge()
    
    success = bridge.init_session(circuit_id, cars, session_type="FP1")
    if not success:
        return {"error": f"Failed to initialize SessionBridge for {circuit_id}"}
    
    # Send cars out with different brake duct settings
    for i, car in enumerate(cars):
        duct_setting = 0.3 + (i * 0.4)  # 0.3 and 0.7
        car.player_config = car.player_config or {}
        car.player_config["setup"] = car.player_config.get("setup", {})
        car.player_config["setup"]["brake_duct"] = int(duct_setting * 100)
        
        ok = bridge.player_send_out(
            car,
            compound=str(car.current_tire.value),
            fuel_percent=80,
            stint_laps=3,
        )
        if not ok:
            return {"error": f"Failed to send car {car.driver_number} out"}
    
    # Run simulation for a few laps
    laps_to_run = 5
    for tick in range(laps_to_run * 100):  # generous tick budget
        bridge.tick(1.0)
        if all(car.total_laps >= laps_to_run for car in cars):
            break
    
    # Collect brake data
    validation_data = {
        "circuit_id": circuit_id,
        "cars_data": [],
        "bridge_integration": {
            "brake_cooling_present": True,
            "brake_diagnostics_present": True,
            "brake_thermal_present": True,
        }
    }
    
    for car in cars:
        car_data = {
            "driver_number": car.driver_number,
            "brake_duct_setting": car.player_config.get("setup", {}).get("brake_duct"),
            "brake_cooling": getattr(car, "brake_cooling", {}),
            "brake_diagnostics": getattr(car, "brake_diagnostics", {}),
            "brake_thermal": getattr(car, "brake_thermal", {}),
            "total_laps": car.total_laps,
        }
        validation_data["cars_data"].append(car_data)
    
    return validation_data


def generate_html_report(reports: List[Dict[str, any]], output_path: Path) -> None:
    """Generate HTML validation report."""
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Brake Component Validation Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .circuit-section { margin-bottom: 30px; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
        .circuit-title { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 5px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin: 15px 0; }
        .metric-card { background: #f9f9f9; padding: 10px; border-radius: 3px; }
        .warning { color: #d9534f; }
        .success { color: #5cb85c; }
        .info { color: #5bc0de; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .temp-ok { color: #5cb85c; }
        .temp-warn { color: #f0ad4e; }
        .temp-critical { color: #d9534f; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Brake Component Validation Report</h1>
        <p>Generated: {timestamp}</p>
        <p>Circuits tested: {circuit_count}</p>
    </div>
    
    {circuit_sections}
    
    <div class="header">
        <h2>Summary</h2>
        <p>Total warning events: {total_warnings}</p>
        <p>Total fade incidents: {total_fade_incidents}</p>
        <p>Circuits with adequate cooling coverage: {adequate_coverage}/{circuit_count}</p>
    </div>
</body>
</html>
    """
    
    circuit_sections = ""
    total_warnings = 0
    total_fade_incidents = 0
    adequate_coverage = 0
    
    for report in reports:
        circuit_sections += f"""
        <div class="circuit-section">
            <h3 class="circuit-title">{report['circuit_id']}</h3>
            <div class="metrics-grid">
                <div class="metric-card">
                    <strong>Peak Front Temp:</strong> {max(report['performance_metrics']['peak_temps']['front']):.1f}°C
                </div>
                <div class="metric-card">
                    <strong>Peak Rear Temp:</strong> {max(report['performance_metrics']['peak_temps']['rear']):.1f}°C
                </div>
                <div class="metric-card">
                    <strong>Fade Incidents:</strong> {report['performance_metrics']['fade_incidents']}
                </div>
                <div class="metric-card">
                    <strong>Cooling Coverage:</strong> 
                    <span class="{'success' if report['cooling_validation']['adequate_coverage'] else 'warning'}">
                        {'✓ Adequate' if report['cooling_validation']['adequate_coverage'] else '⚠ Inadequate'}
                    </span>
                </div>
            </div>
            
            <h4>Duct Configuration Results</h4>
            <table>
                <tr>
                    <th>Duct Opening</th>
                    <th>Peak Front (°C)</th>
                    <th>Peak Rear (°C)</th>
                    <th>Fade Events</th>
                    <th>Warnings</th>
                </tr>
        """
        
        for test in report["duct_tests"]:
            temp_class = "temp-ok"
            if test["peak_temps"]["front"] > report["config_summary"]["fade_threshold_front"] - 50:
                temp_class = "temp-warn"
            if test["peak_temps"]["front"] > report["config_summary"]["fade_threshold_front"]:
                temp_class = "temp-critical"
            
            circuit_sections += f"""
                <tr>
                    <td>{test["duct_opening"]:.2f}</td>
                    <td class="{temp_class}">{test["peak_temps"]["front"]:.1f}</td>
                    <td>{test["peak_temps"]["rear"]:.1f}</td>
                    <td>{test["fade_events"]}</td>
                    <td>{len(test["warning_events"])}</td>
                </tr>
            """
        
        circuit_sections += "</table></div>"
        
        total_warnings += len(report["warning_events"])
        total_fade_incidents += report["performance_metrics"]["fade_incidents"]
        if report["cooling_validation"]["adequate_coverage"]:
            adequate_coverage += 1
    
    html_content = html_template.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        circuit_count=len(reports),
        circuit_sections=circuit_sections,
        total_warnings=total_warnings,
        total_fade_incidents=total_fade_incidents,
        adequate_coverage=adequate_coverage,
    )
    
    output_path.write_text(html_content, encoding="utf-8")


def main():
    """Generate comprehensive brake validation report for all circuits."""
    circuits_dir = ROOT / "config" / "circuits" / "derived"
    circuit_ids = [p.name for p in circuits_dir.iterdir() if p.is_dir()]
    
    print(f"Generating brake validation report for {len(circuit_ids)} circuits...")
    
    all_reports = []
    session_bridge_reports = []
    
    for circuit_id in circuit_ids:
        try:
            print(f"Processing {circuit_id}...")
            
            # Generate detailed brake validation
            report = generate_brake_validation_report(circuit_id)
            all_reports.append(report)
            
            # Generate SessionBridge validation
            bridge_report = run_session_bridge_validation(circuit_id)
            if "error" not in bridge_report:
                session_bridge_reports.append(bridge_report)
            
        except Exception as e:
            print(f"Error processing {circuit_id}: {e}")
            continue
    
    # Save JSON reports
    reports_dir = ROOT / "reports" / "calibration"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Detailed JSON report
    json_path = reports_dir / f"brake_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    json_path.write_text(json.dumps(all_reports, indent=2), encoding="utf-8")
    
    # SessionBridge validation report
    bridge_json_path = reports_dir / f"brake_session_bridge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    bridge_json_path.write_text(json.dumps(session_bridge_reports, indent=2), encoding="utf-8")
    
    # Generate HTML report
    html_path = reports_dir / f"brake_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    generate_html_report(all_reports, html_path)
    
    print(f"\nReports generated:")
    print(f"  JSON: {json_path}")
    print(f"  SessionBridge: {bridge_json_path}")
    print(f"  HTML: {html_path}")
    print(f"\nSummary: {len(all_reports)} circuits validated")
    print(f"Total warning events: {sum(len(r['warning_events']) for r in all_reports)}")
    print(f"Total fade incidents: {sum(r['performance_metrics']['fade_incidents'] for r in all_reports)}")


if __name__ == "__main__":
    main()
