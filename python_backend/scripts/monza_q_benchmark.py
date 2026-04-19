#!/usr/bin/env python3
"""Monza Q baseline benchmark with 13-microsector telemetry comparison.

This CLI runs the reusable Physics V4 initial calibration benchmark for Monza,
then compares the simulated lap against the reference telemetry section by
section. The report makes the physical objective explicit:

- simulate a telemetry-aligned qualifying lap on Monza
- keep the qualifying run plan traceable (push, ICE map, ERS mode)
- validate the physics response on each of the 13 telemetry microsectors
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON_BACKEND_ROOT = SCRIPT_DIR.parent
if str(PYTHON_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_BACKEND_ROOT))

from lap_simulator.physics_engine.calibration.reference_calibration import (  # noqa: E402
    DEFAULT_CALIBRATION_CIRCUIT_ID,
    DEFAULT_CALIBRATION_DRIVER_NAME,
    DEFAULT_CALIBRATION_ENGINE_MAP,
    DEFAULT_CALIBRATION_ERS_MODE,
    DEFAULT_CALIBRATION_ICE_MODE,
    DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT,
    DEFAULT_CALIBRATION_OBJECTIVE,
    DEFAULT_CALIBRATION_PHYSICS_ERS_MODE,
    DEFAULT_CALIBRATION_PUSH_LEVEL,
    DEFAULT_CALIBRATION_SESSION,
    DEFAULT_CALIBRATION_TEAM_NAME,
    DEFAULT_CALIBRATION_TYRE_COMPOUND,
    DEFAULT_CALIBRATION_WEATHER,
    InitialCalibrationSpec,
    run_initial_calibration_benchmark,
)


TelemetryPoint = Dict[str, Any]
SectionRow = Dict[str, Any]


def _load_reference_payload(circuit_id: str) -> Dict[str, Any]:
    telemetry_path = (
        PYTHON_BACKEND_ROOT
        / "data"
        / "circuits"
        / "2025"
        / f"{circuit_id}_Telemetry.json"
    )
    if not telemetry_path.exists():
        raise FileNotFoundError(f"Telemetry file not found for circuit: {circuit_id}")
    return json.loads(telemetry_path.read_text(encoding="utf-8"))


def _normalize_telemetry_points(raw_points: List[Dict[str, Any]]) -> List[TelemetryPoint]:
    normalized: List[TelemetryPoint] = []
    for point in raw_points:
        distance = point.get("distance_m", point.get("distance", 0.0))
        time_s = point.get("time_s", point.get("time", 0.0))
        speed_kph = point.get("velocity_kph")
        if speed_kph is None:
            speed_kph = point.get("speed_kph")
        if speed_kph is None and point.get("velocity_ms") is not None:
            speed_kph = float(point["velocity_ms"]) * 3.6
        if distance is None or time_s is None:
            continue
        normalized.append(
            {
                "distance_m": float(distance),
                "time_s": float(time_s),
                "speed_kph": float(speed_kph or 0.0),
            }
        )

    normalized.sort(key=lambda item: item["distance_m"])

    deduplicated: List[TelemetryPoint] = []
    for point in normalized:
        if deduplicated and abs(point["distance_m"] - deduplicated[-1]["distance_m"]) < 1e-9:
            deduplicated[-1] = point
        else:
            deduplicated.append(point)

    if deduplicated and deduplicated[0]["distance_m"] > 0.0:
        deduplicated.insert(
            0,
            {
                "distance_m": 0.0,
                "time_s": 0.0,
                "speed_kph": deduplicated[0]["speed_kph"],
            },
        )

    if not deduplicated:
        raise ValueError("Simulated telemetry is empty")
    return deduplicated


def _interpolate_metric(trace: List[TelemetryPoint], distance_m: float, key: str) -> float:
    if distance_m <= trace[0]["distance_m"]:
        return float(trace[0][key])
    if distance_m >= trace[-1]["distance_m"]:
        return float(trace[-1][key])

    for left, right in zip(trace, trace[1:]):
        left_distance = left["distance_m"]
        right_distance = right["distance_m"]
        if distance_m > right_distance:
            continue
        span = right_distance - left_distance
        if span <= 0.0:
            return float(right[key])
        fraction = (distance_m - left_distance) / span
        return float(left[key]) + fraction * (float(right[key]) - float(left[key]))

    return float(trace[-1][key])


def _extract_raw_driver_profile(driver_name: str) -> Optional[Dict[str, Any]]:
    try:
        from data.pilots import PILOTS  # noqa: WPS433
    except Exception:
        return None

    surname = driver_name.split()[-1].upper()
    pilot = PILOTS.get(surname)
    if pilot is None:
        return None

    return {
        "nome": pilot.nome,
        "cognome": pilot.cognome,
        "nome_completo": pilot.nome_completo,
        "nazionalita": getattr(pilot.nazionalita, "value", str(pilot.nazionalita)),
        "eta": pilot.eta,
        "numero_di_gara": pilot.numero_di_gara,
        "velocita": pilot.velocita,
        "consumo_gomme": pilot.consumo_gomme,
        "qualifica": pilot.qualifica,
        "sorpasso": pilot.sorpasso,
        "aggressivita": pilot.aggressivita,
        "ricerca_assetto": pilot.ricerca_assetto,
        "stile_sottosterzo": pilot.stile_sottosterzo,
        "stile_sovrasterzo": pilot.stile_sovrasterzo,
        "costanza": pilot.costanza,
        "gara": pilot.gara,
        "gestione_carburante": pilot.gestione_carburante,
        "perfezionismo": pilot.perfezionismo,
        "abbreviazione": pilot.abbreviazione,
    }


def _section_rows(reference_payload: Dict[str, Any], telemetry: List[TelemetryPoint]) -> List[SectionRow]:
    sections = (((reference_payload or {}).get("geometry") or {}).get("sections") or [])
    rows: List[SectionRow] = []

    for section in sections:
        start_m = float(section.get("start_m", 0.0))
        end_m = float(section.get("end_m", 0.0))
        length_m = float(section.get("length_m", max(end_m - start_m, 0.0)))
        ref_dt = float(section.get("dt_ref_s", 0.0))
        ref_avg = float(section.get("avg_speed", 0.0))
        ref_v_entry = float(section.get("v_entry_kph", 0.0))
        ref_v_exit = float(section.get("v_exit_kph", 0.0))
        ref_v_min = float(section.get("v_min_kph", 0.0))
        ref_v_max = float(section.get("v_max_kph", 0.0))
        sim_start_t = _interpolate_metric(telemetry, start_m, "time_s")
        sim_end_t = _interpolate_metric(telemetry, end_m, "time_s")
        sim_dt = max(sim_end_t - sim_start_t, 0.0)
        sim_avg = (length_m / sim_dt * 3.6) if sim_dt > 0.0 else 0.0
        sim_v_entry = _interpolate_metric(telemetry, start_m, "speed_kph")
        sim_v_exit = _interpolate_metric(telemetry, end_m, "speed_kph")
        section_speeds = [
            point["speed_kph"]
            for point in telemetry
            if start_m <= point["distance_m"] <= end_m
        ]
        if not section_speeds:
            section_speeds = [sim_v_entry, sim_v_exit]
        sim_v_min = min(section_speeds)
        sim_v_max = max(section_speeds)

        rows.append(
            {
                "section_id": section.get("id", ""),
                "name": section.get("name", section.get("id", "Section")),
                "kind": section.get("kind", ""),
                "length_m": length_m,
                "reference": {
                    "dt_s": ref_dt,
                    "avg_speed_kph": ref_avg,
                    "v_entry_kph": ref_v_entry,
                    "v_exit_kph": ref_v_exit,
                    "v_min_kph": ref_v_min,
                    "v_max_kph": ref_v_max,
                    "start_m": start_m,
                    "end_m": end_m,
                },
                "simulated": {
                    "dt_s": sim_dt,
                    "avg_speed_kph": sim_avg,
                    "v_entry_kph": sim_v_entry,
                    "v_exit_kph": sim_v_exit,
                    "v_min_kph": sim_v_min,
                    "v_max_kph": sim_v_max,
                    "start_m": start_m,
                    "end_m": end_m,
                },
                "delta": {
                    "dt_s": sim_dt - ref_dt,
                    "avg_speed_kph": sim_avg - ref_avg,
                    "v_entry_kph": sim_v_entry - ref_v_entry,
                    "v_exit_kph": sim_v_exit - ref_v_exit,
                    "v_min_kph": sim_v_min - ref_v_min,
                    "v_max_kph": sim_v_max - ref_v_max,
                },
                "time_margin_pct": abs(sim_dt - ref_dt) / ref_dt if ref_dt > 0.0 else 0.0,
            }
        )

    return rows


def _validate_microsector_margins(
    rows: List[SectionRow],
    threshold_pct: float = DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT,
) -> Dict[str, Any]:
    over_threshold = [row for row in rows if row.get("time_margin_pct", 0.0) > threshold_pct]
    worst_row = max(rows, key=lambda row: row.get("time_margin_pct", 0.0)) if rows else None
    return {
        "threshold_pct": threshold_pct,
        "max_margin_pct": worst_row.get("time_margin_pct", 0.0) if worst_row else 0.0,
        "worst_section": worst_row,
        "all_sections_within_threshold": not over_threshold,
        "sections_over_threshold": [row["section_id"] for row in over_threshold],
        "sections_over_threshold_count": len(over_threshold),
    }


def build_monza_comparison_report(result: Dict[str, Any], reference_payload: Dict[str, Any]) -> Dict[str, Any]:
    telemetry = _normalize_telemetry_points(result.get("telemetry") or result.get("telemetry_points") or [])
    rows = _section_rows(reference_payload, telemetry)
    validation = _validate_microsector_margins(rows)
    reference_lap = (reference_payload or {}).get("reference_lap", {})
    geometry = (reference_payload or {}).get("geometry", {})
    circuit_length = float(geometry.get("circuit_length", 0.0))
    ref_lap_time = float(reference_lap.get("lap_time", sum(row["reference"]["dt_s"] for row in rows)))
    sim_lap_time = float(result.get("lap_time_s", 0.0))
    ref_avg_speed = (circuit_length / ref_lap_time * 3.6) if ref_lap_time > 0.0 else 0.0
    sim_avg_speed = (circuit_length / sim_lap_time * 3.6) if sim_lap_time > 0.0 else 0.0
    lap_delta_s = sim_lap_time - ref_lap_time
    lap_delta_pct = (lap_delta_s / ref_lap_time) if ref_lap_time > 0.0 else 0.0
    max_abs_delta = max(rows, key=lambda row: abs(row["delta"]["dt_s"])) if rows else None
    best_match = min(rows, key=lambda row: abs(row["delta"]["dt_s"])) if rows else None
    max_margin_section = validation.get("worst_section")

    return {
        "summary": {
            "circuit_id": reference_payload.get("metadata", {}).get("circuit_id"),
            "circuit_name": reference_payload.get("metadata", {}).get("circuit_name"),
            "circuit_length_m": circuit_length,
            "reference_lap_time_s": ref_lap_time,
            "simulated_lap_time_s": sim_lap_time,
            "lap_delta_s": lap_delta_s,
            "lap_delta_pct": lap_delta_pct,
            "microsector_margin_threshold_pct": validation["threshold_pct"],
            "max_microsector_margin_pct": validation["max_margin_pct"],
            "reference_avg_speed_kph": ref_avg_speed,
            "simulated_avg_speed_kph": sim_avg_speed,
            "largest_abs_delta_section": max_abs_delta,
            "largest_margin_section": max_margin_section,
            "smallest_abs_delta_section": best_match,
        },
        "sections": rows,
        "validation": validation,
    }


def _format_float(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def _format_setup_line(label: str, value: Any, indent: str = "  ") -> str:
    if isinstance(value, float):
        return f"{indent}{label}: {value:.3f}"
    return f"{indent}{label}: {value}"


def _format_section_table(rows: List[SectionRow]) -> str:
    header = (
        f"{'Section':<10} {'Kind':<16} {'Ref dt':>8} {'Sim dt':>8} {'Δdt':>8} {'Err %':>8} "
        f"{'Ref avg':>8} {'Sim avg':>8} {'Δavg':>8}"
    )
    lines = [header, "-" * len(header)]
    for row in rows:
        lines.append(
            f"{row['section_id']:<10} "
            f"{str(row['kind'])[:16]:<16} "
            f"{row['reference']['dt_s']:8.3f} "
            f"{row['simulated']['dt_s']:8.3f} "
            f"{row['delta']['dt_s']:8.3f} "
            f"{row['time_margin_pct'] * 100:7.2f}% "
            f"{row['reference']['avg_speed_kph']:8.1f} "
            f"{row['simulated']['avg_speed_kph']:8.1f} "
            f"{row['delta']['avg_speed_kph']:8.1f}"
        )
    return "\n".join(lines)


def format_report(result: Dict[str, Any], comparison: Dict[str, Any], raw_driver_profile: Optional[Dict[str, Any]]) -> str:
    benchmark = result.get("initial_calibration", {})
    benchmark_context = benchmark.get("benchmark_context", {})
    run_plan = benchmark_context.get("run_plan", {})
    acceptance_criteria = benchmark_context.get("acceptance_criteria", {})
    physics_modes = benchmark_context.get("physics_modes", {})
    car_configuration = benchmark.get("car_configuration", {})
    setup_base = benchmark.get("setup_base", {})
    setup_applied = benchmark.get("setup_applied", {})
    driver_skill = benchmark.get("driver_skill", {})
    team_data = benchmark.get("team_data", {})
    summary = comparison["summary"]
    sections = comparison["sections"]

    lines: List[str] = []
    lines.append("== Physics V4 Monza Q Baseline ==")
    lines.append(f"Objective: {benchmark_context.get('objective', DEFAULT_CALIBRATION_OBJECTIVE)}")
    lines.append(
        f"Circuit: {summary['circuit_id']} | Session: {benchmark.get('session', DEFAULT_CALIBRATION_SESSION)} | "
        f"Tyre: {benchmark.get('tyre_compound', DEFAULT_CALIBRATION_TYRE_COMPOUND)}"
    )
    lines.append(
        f"Team: {benchmark.get('resolved_team_name', DEFAULT_CALIBRATION_TEAM_NAME)} | "
        f"Driver: {benchmark.get('resolved_driver_name', DEFAULT_CALIBRATION_DRIVER_NAME)}"
    )
    lines.append(
        f"Run plan: push={run_plan.get('push_level', DEFAULT_CALIBRATION_PUSH_LEVEL):.1f} | "
        f"engine_map={run_plan.get('engine_map', DEFAULT_CALIBRATION_ENGINE_MAP)} | "
        f"ers_mode={run_plan.get('ers_mode', DEFAULT_CALIBRATION_ERS_MODE)} | "
        f"ice_mode={physics_modes.get('ice_mode', DEFAULT_CALIBRATION_ICE_MODE)} | "
        f"physics_ers_mode={physics_modes.get('ers_deploy_mode', DEFAULT_CALIBRATION_PHYSICS_ERS_MODE)}"
    )
    if acceptance_criteria:
        lines.append(
            f"Acceptance: microsector time margin <= {acceptance_criteria.get('microsector_margin_pct_max', DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT):.2%} | "
            f"basis={acceptance_criteria.get('microsector_margin_basis', 'abs((sim_dt - ref_dt) / ref_dt)')}"
        )
    lines.append(
        f"Lap time: ref {_format_float(summary['reference_lap_time_s'])} s | "
        f"sim {_format_float(summary['simulated_lap_time_s'])} s | "
        f"delta {_format_float(summary['lap_delta_s'])} s ({summary['lap_delta_pct']:+.2%})"
    )
    lines.append(
        f"Avg speed: ref {_format_float(summary['reference_avg_speed_kph'])} kph | "
        f"sim {_format_float(summary['simulated_avg_speed_kph'])} kph"
    )
    lines.append("")
    lines.append("Driver skill (Physics V4):")
    for key in (
        "name",
        "quali_skill",
        "race_skill",
        "braking_skill",
        "cornering_skill",
        "throttle_skill",
        "consistency",
        "front_wing_offset",
        "rear_wing_offset",
        "brake_bias_offset",
    ):
        if key in driver_skill:
            lines.append(_format_setup_line(key, driver_skill[key]))
    if raw_driver_profile:
        lines.append("Raw driver profile (source data):")
        for key in (
            "nome_completo",
            "nazionalita",
            "eta",
            "numero_di_gara",
            "velocita",
            "consumo_gomme",
            "qualifica",
            "sorpasso",
            "aggressivita",
            "ricerca_assetto",
            "stile_sottosterzo",
            "stile_sovrasterzo",
            "costanza",
            "gara",
            "gestione_carburante",
            "perfezionismo",
        ):
            if key in raw_driver_profile:
                lines.append(_format_setup_line(key, raw_driver_profile[key]))
    lines.append("")
    lines.append("Team data (Physics V4):")
    for key in ("team_id", "name", "suspension_efficiency", "pu_provider"):
        if key in team_data:
            lines.append(_format_setup_line(key, team_data[key]))
    lines.append("")
    lines.append("Car setup snapshot:")
    if setup_base:
        aero = setup_base.get("aero", {})
        suspension = setup_base.get("suspension", {})
        tyres = setup_base.get("tyres", {})
        lines.append(
            f"  base aero: FW {aero.get('front_wing')} | RW {aero.get('rear_wing')} | "
            f"CLA {aero.get('cla_total')} | CDA {aero.get('cda_total')}"
        )
        lines.append(
            f"  base suspension: SF {suspension.get('spring_front_slider', suspension.get('spring_front'))} "
            f"| SR {suspension.get('spring_rear_slider', suspension.get('spring_rear'))} "
            f"| ARB F {suspension.get('arb_front_slider', suspension.get('arb_front'))} "
            f"| ARB R {suspension.get('arb_rear_slider', suspension.get('arb_rear'))}"
        )
        lines.append(
            f"  base tyres: compound {tyres.get('compound')} | PF {tyres.get('pressure_front')} | PR {tyres.get('pressure_rear')}"
        )
        lines.append(
            f"  base mass/fuel: mass {setup_base.get('mass_kg')} kg | fuel {setup_base.get('fuel_kg')} kg | ERS {setup_base.get('ers_mode')}"
        )
    if setup_applied:
        aero = setup_applied.get("aero", {})
        suspension = setup_applied.get("suspension", {})
        tyres = setup_applied.get("tyres", {})
        lines.append(
            f"  applied aero: FW {aero.get('front_wing')} | RW {aero.get('rear_wing')} | "
            f"CLA {aero.get('cla_total')} | CDA {aero.get('cda_total')}"
        )
        lines.append(
            f"  applied suspension: SF {suspension.get('spring_front_slider', suspension.get('spring_front'))} "
            f"| SR {suspension.get('spring_rear_slider', suspension.get('spring_rear'))} "
            f"| ARB F {suspension.get('arb_front_slider', suspension.get('arb_front'))} "
            f"| ARB R {suspension.get('arb_rear_slider', suspension.get('arb_rear'))}"
        )
        lines.append(
            f"  applied tyres: compound {tyres.get('compound')} | PF {tyres.get('pressure_front')} | PR {tyres.get('pressure_rear')}"
        )
        lines.append(
            f"  applied mass/fuel: mass {setup_applied.get('mass_kg')} kg | fuel {setup_applied.get('fuel_kg')} kg | ERS {setup_applied.get('ers_mode')}"
        )
    if car_configuration:
        power_unit = car_configuration.get("power_unit", {})
        lines.append(
            f"  power unit: ICE {power_unit.get('ice_mode')} | ERS deploy {power_unit.get('ers_deploy_mode')} | "
            f"deploy_per_km {power_unit.get('deploy_per_km')}"
        )
    lines.append("")
    lines.append("Microsector comparison (13 telemetry sections):")
    lines.append(_format_section_table(sections))
    lines.append("")

    validation = comparison.get("validation", {})
    if validation:
        threshold_pct = float(validation.get("threshold_pct", DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT))
        status = "PASS" if validation.get("all_sections_within_threshold") else "FAIL"
        lines.append(f"Validation: microsector time margin <= {threshold_pct:.2%} | {status}")
        worst = validation.get("worst_section")
        if worst:
            lines.append(
                f"Worst margin: {worst['section_id']} ({worst['name']}) -> {worst['time_margin_pct']:.2%}"
            )
        over_threshold = validation.get("sections_over_threshold") or []
        if over_threshold:
            lines.append("Over-threshold sections: " + ", ".join(over_threshold))

    gap_section = summary.get("largest_abs_delta_section")
    if gap_section:
        lines.append(
            "Largest time delta: "
            f"{gap_section['section_id']} ({gap_section['name']}) -> {gap_section['delta']['dt_s']:+.3f} s"
        )
    smallest_section = summary.get("smallest_abs_delta_section")
    if smallest_section:
        lines.append(
            "Closest section: "
            f"{smallest_section['section_id']} ({smallest_section['name']}) -> {smallest_section['delta']['dt_s']:+.3f} s"
        )

    lines.append("")
    lines.append("Use --json-out to save the full structured report.")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Physics V4 Monza Q baseline and compare it with the 13 microsectors telemetry.",
    )
    parser.add_argument("--circuit", default=DEFAULT_CALIBRATION_CIRCUIT_ID, help="Circuit telemetry ID")
    parser.add_argument("--team", default=DEFAULT_CALIBRATION_TEAM_NAME, help="Team name for the benchmark")
    parser.add_argument("--driver", default=DEFAULT_CALIBRATION_DRIVER_NAME, help="Driver name for the benchmark")
    parser.add_argument("--session", default=DEFAULT_CALIBRATION_SESSION, help="Session type (default: qualifying)")
    parser.add_argument("--weather", default=DEFAULT_CALIBRATION_WEATHER, help="Weather preset (default: dry)")
    parser.add_argument("--tyre-compound", default=DEFAULT_CALIBRATION_TYRE_COMPOUND, help="Tyre compound for the benchmark")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional path to write the full JSON report")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose lap simulation output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = InitialCalibrationSpec(
        circuit_id=args.circuit,
        team_name=args.team,
        driver_name=args.driver,
        session=args.session,
        weather=args.weather,
        tyre_compound=args.tyre_compound,
    )
    result = run_initial_calibration_benchmark(spec=spec, verbose=args.verbose)
    reference_payload = _load_reference_payload(args.circuit)
    comparison = build_monza_comparison_report(result, reference_payload)
    raw_driver_profile = _extract_raw_driver_profile(args.driver)

    full_report = {
        "benchmark": result.get("initial_calibration", {}),
        "lap_result": {
            "lap_time_s": result.get("lap_time_s"),
            "v_max_kph": result.get("v_max_kph"),
            "v_min_kph": result.get("v_min_kph"),
            "v_avg_kph": result.get("v_avg_kph"),
        },
        "comparison": comparison,
        "validation": comparison.get("validation", {}),
        "raw_driver_profile": raw_driver_profile,
    }

    print(format_report(result, comparison, raw_driver_profile))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        with args.json_out.expanduser().resolve().open("w", encoding="utf-8") as handle:
            json.dump(full_report, handle, indent=2, ensure_ascii=False)

    validation = comparison.get("validation", {})
    return 0 if validation.get("all_sections_within_threshold", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
