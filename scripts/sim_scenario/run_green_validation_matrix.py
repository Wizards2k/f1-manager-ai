#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "scripts" / "sim_scenario" / "scenarios"
OUTPUT_DIR = REPO_ROOT / "tmp" / "tyre_validation_matrix"
TYRE_DEBUG_LOG = REPO_ROOT / "python_backend" / "logs" / "tyre_heat_debug.jsonl"
PIRELLI_PROFILE_PATH = REPO_ROOT / "config" / "tyres" / "pirelli_track_profile_2025.json"
BUILD_VARIANTS_PATH = REPO_ROOT / "scripts" / "sim_scenario" / "build_variants.py"
RUN_SCENARIO_PATH = REPO_ROOT / "scripts" / "sim_scenario" / "run_sim_scenario.py"

CIRCUITS: List[Tuple[str, str, str]] = [
    ("jp-1962_suzuka", "Suzuka", "suzuka_leclerc_setup_green"),
    ("it-1922_monza", "Monza", "monza_leclerc_setup_green"),
    ("mc-1929_monaco", "Monte Carlo", "monaco_leclerc_setup_green"),
    ("es-1991_barcelona", "Barcelona", "barcelona_leclerc_setup_green"),
    ("be-1925_spa_francorchamps", "Spa-Francorchamps", "spa_leclerc_setup_green"),
    ("gb-1948_silverstone", "Silverstone", "silverstone_leclerc_setup_green"),
]

LAPS_BY_SLOT = {"S": 10, "M": 15, "H": 15}
VALIDATION_PUSH_LEVEL = 7


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_green_scenarios() -> None:
    circuits = [circuit_id for circuit_id, _, _ in CIRCUITS]
    cmd = [
        sys.executable,
        str(BUILD_VARIANTS_PATH),
        "--green-only",
        "--base",
        str(SCENARIO_DIR / "monza_leclerc_setup_green.json"),
        "--output-dir",
        str(SCENARIO_DIR),
        "--circuits",
        *circuits,
    ]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def _load_nominations() -> Dict[str, Dict[str, str]]:
    payload = _load_json(PIRELLI_PROFILE_PATH)
    by_circuit: Dict[str, Dict[str, str]] = {}
    for entry in payload.get("calendar", []):
        by_circuit[str(entry.get("circuit", ""))] = dict(entry.get("nomination", {}))
    return by_circuit


def _find_nomination(circuit_name: str, nominations: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    aliases = {circuit_name}
    if circuit_name == "Monte Carlo":
        aliases.add("Monaco")
    for alias in aliases:
        if alias in nominations:
            return nominations[alias]
    raise SystemExit(f"Pirelli nomination not found for circuit '{circuit_name}'")


def _load_windows(circuit_id: str) -> Dict[str, Dict[str, List[float]]]:
    path = REPO_ROOT / "config" / "circuits" / "derived" / circuit_id / "tyre_params.json"
    payload = _load_json(path)
    return dict(payload.get("compounds", {}))


def _parse_debug_log() -> List[Dict[str, Any]]:
    if not TYRE_DEBUG_LOG.exists():
        return []
    return [json.loads(line) for line in TYRE_DEBUG_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]


def _analyze_window(rows: List[Dict[str, Any]], compound: str, windows: Dict[str, Dict[str, List[float]]]) -> Dict[str, Any]:
    compound_cfg = windows[compound]
    surface_low, _, surface_high = compound_cfg["temp_window_surface_c"]
    core_low, _, core_high = compound_cfg["temp_window_core_c"]

    def first_violation(items: List[Dict[str, Any]], field: str, low: float, high: float) -> Dict[str, Any] | None:
        if not items:
            return None
        item = items[0]
        value = float(item[field])
        return {
            "lap": int(item.get("lap_number", 0)),
            "section": item.get("section_id"),
            "wheel": item.get("wheel"),
            "value": round(value, 2),
            "delta_low": round(value - low, 2),
            "delta_high": round(value - high, 2),
        }

    wheel_rows: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        wheel = str(row.get("wheel", ""))
        if not wheel or wheel == "allocator":
            continue
        wheel_rows.setdefault(wheel, []).append(row)

    wheel_summaries: Dict[str, Dict[str, Any]] = {}
    all_surface_values: List[float] = []
    all_core_values: List[float] = []
    surface_ok = True
    core_ok = True

    for wheel, wheel_specific_rows in sorted(wheel_rows.items()):
        surface_values = [float(r["surface_temp_after"]) for r in wheel_specific_rows]
        core_values = [float(r["core_temp_after"]) for r in wheel_specific_rows]
        all_surface_values.extend(surface_values)
        all_core_values.extend(core_values)

        surface_violations = [
            r for r in wheel_specific_rows
            if float(r["surface_temp_after"]) < surface_low or float(r["surface_temp_after"]) > surface_high
        ]
        core_violations = [
            r for r in wheel_specific_rows
            if float(r["core_temp_after"]) < core_low or float(r["core_temp_after"]) > core_high
        ]

        wheel_summary = {
            "surface_min_c": round(min(surface_values), 2),
            "surface_max_c": round(max(surface_values), 2),
            "core_min_c": round(min(core_values), 2),
            "core_max_c": round(max(core_values), 2),
            "surface_ok": not surface_violations,
            "core_ok": not core_violations,
            "surface_first_violation": first_violation(surface_violations, "surface_temp_after", surface_low, surface_high),
            "core_first_violation": first_violation(core_violations, "core_temp_after", core_low, core_high),
        }
        wheel_summaries[wheel] = wheel_summary
        surface_ok = surface_ok and wheel_summary["surface_ok"]
        core_ok = core_ok and wheel_summary["core_ok"]

    if not all_surface_values or not all_core_values:
        raise SystemExit("Tyre debug log missing per-wheel data")

    return {
        "surface_window_c": [surface_low, surface_high],
        "core_window_c": [core_low, core_high],
        "surface_min_c": round(min(all_surface_values), 2),
        "surface_max_c": round(max(all_surface_values), 2),
        "core_min_c": round(min(all_core_values), 2),
        "core_max_c": round(max(all_core_values), 2),
        "surface_ok": surface_ok,
        "core_ok": core_ok,
        "surface_first_violation": next(
            (summary["surface_first_violation"] for summary in wheel_summaries.values() if summary["surface_first_violation"] is not None),
            None,
        ),
        "core_first_violation": next(
            (summary["core_first_violation"] for summary in wheel_summaries.values() if summary["core_first_violation"] is not None),
            None,
        ),
        "wheels": wheel_summaries,
    }


def _run_one(circuit_id: str, scenario_name: str, compound: str, laps: int) -> Dict[str, Any]:
    output_path = OUTPUT_DIR / f"{scenario_name}_{compound.lower()}_{laps}laps.json"
    cmd = [
        sys.executable,
        str(RUN_SCENARIO_PATH),
        "--snapshot",
        str(SCENARIO_DIR / f"{scenario_name}.json"),
        "--circuit",
        circuit_id,
        "--laps",
        str(laps),
        "--push",
        str(VALIDATION_PUSH_LEVEL),
        "--compound",
        compound,
        "--output-json",
        str(output_path),
    ]
    env = dict(**__import__("os").environ)
    env["TYRE_DEBUG"] = "1"
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or proc.stdout)
    rows = _parse_debug_log()
    if not rows:
        raise SystemExit(f"No tyre debug rows found for {scenario_name} {compound}")
    lap_summary = _load_json(output_path)
    event_counts: Dict[str, int] = {}
    for lap in lap_summary.get("laps", []):
        for event_name in lap.get("events", []):
            event_counts[event_name] = event_counts.get(event_name, 0) + 1
    return {
        "output_json": str(output_path.relative_to(REPO_ROOT)),
        "stdout": proc.stdout,
        "event_counts": event_counts,
        "rows": rows,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _build_green_scenarios()
    nominations = _load_nominations()
    report: Dict[str, Any] = {"runs": []}

    for circuit_id, circuit_name, scenario_name in CIRCUITS:
        windows = _load_windows(circuit_id)
        nomination = _find_nomination(circuit_name, nominations)
        for slot in ("S", "M", "H"):
            compound = nomination[slot]
            laps = LAPS_BY_SLOT[slot]
            result = _run_one(circuit_id, scenario_name, compound, laps)
            analysis = _analyze_window(result["rows"], compound, windows)
            report["runs"].append(
                {
                    "circuit_id": circuit_id,
                    "circuit": circuit_name,
                    "scenario": scenario_name,
                    "slot": slot,
                    "compound": compound,
                    "laps": laps,
                    "surface_ok": analysis["surface_ok"],
                    "core_ok": analysis["core_ok"],
                    "surface_window_c": analysis["surface_window_c"],
                    "core_window_c": analysis["core_window_c"],
                    "surface_min_c": analysis["surface_min_c"],
                    "surface_max_c": analysis["surface_max_c"],
                    "core_min_c": analysis["core_min_c"],
                    "core_max_c": analysis["core_max_c"],
                    "surface_first_violation": analysis["surface_first_violation"],
                    "core_first_violation": analysis["core_first_violation"],
                    "wheels": analysis["wheels"],
                    "event_counts": result["event_counts"],
                    "output_json": result["output_json"],
                }
            )
            status = "PASS" if analysis["surface_ok"] and analysis["core_ok"] else "FAIL"
            print(
                f"[{status}] {circuit_name} {slot}/{compound} {laps} laps | "
                f"surface {analysis['surface_min_c']:.1f}-{analysis['surface_max_c']:.1f} "
                f"window {analysis['surface_window_c'][0]:.1f}-{analysis['surface_window_c'][1]:.1f} | "
                f"core {analysis['core_min_c']:.1f}-{analysis['core_max_c']:.1f} "
                f"window {analysis['core_window_c'][0]:.1f}-{analysis['core_window_c'][1]:.1f}"
            )

    report_path = OUTPUT_DIR / "green_validation_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
