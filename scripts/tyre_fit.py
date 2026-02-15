#!/usr/bin/env python3
"""Calibrazione gomme per circuito usando Telemetry JSON e seed globali.

Usage:
    python scripts/tyre_fit.py --circuit-id jp-1962_suzuka --year 2025
"""
from __future__ import annotations

import argparse
import json
import statistics
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

GLOBAL_TYRE_TEMPLATE = Path("config/tyres/tyre_params_global_default.json")
BASE_TEMP_SHIFT = 5.0  # °C per (heat_factor - 1)
BASE_WEAR_COEFF = 0.08  # scaling per unit heat/bump contribution


class TelemetryNotFound(Exception):
    pass


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def load_telemetry(circuit_id: str, year: Optional[int], data_dir: Path) -> Dict[str, Any]:
    candidates: List[Path] = []
    if year:
        candidates.append(data_dir / str(year) / f"{circuit_id}_Telemetry.json")
    candidates.append(data_dir / f"{circuit_id}_Telemetry.json")
    for c in candidates:
        if c.exists():
            return load_json(c)
    raise TelemetryNotFound(
        f"Telemetry JSON non trovato. Cercati: {', '.join(str(p) for p in candidates)}"
    )


def get_section_stats(sections: List[Dict[str, Any]], circuit_length: float) -> Dict[str, float]:
    heat = [s.get("heat_factor", 1.0) for s in sections if s.get("heat_factor") is not None]
    bump = [s.get("bumpiness_factor", 0.0) for s in sections if s.get("bumpiness_factor") is not None]
    braking = [s.get("braking_energy_mj", 0.0) for s in sections]

    avg_heat = statistics.mean(heat) if heat else 1.0
    avg_bump = statistics.mean(bump) if bump else 0.0
    avg_brake = statistics.mean(braking) if braking else 0.0
    total_brake = sum(braking)
    brake_density = total_brake / max(circuit_length / 1000.0, 1.0)

    return {
        "avg_heat": avg_heat,
        "avg_bump": avg_bump,
        "avg_brake": avg_brake,
        "total_brake": total_brake,
        "brake_density": brake_density,
    }


def adjust_temp_window(values: List[float], shift: float) -> List[float]:
    return [round(v + shift, 2) for v in values]


def calibrate_compounds(
    base_compounds: Dict[str, Dict[str, float]],
    stats: Dict[str, float],
    circuit_length: float,
) -> Dict[str, Dict[str, float]]:
    avg_heat = stats["avg_heat"]
    avg_bump = stats["avg_bump"]
    brake_density = stats["total_brake"] / max(circuit_length, 1.0)

    wear_multiplier = 1.0 + BASE_WEAR_COEFF * ((avg_heat - 1.0) + 0.5 * avg_bump + 0.3 * brake_density)
    wear_multiplier = max(0.6, min(wear_multiplier, 1.8))
    temp_shift = (avg_heat - 1.0) * BASE_TEMP_SHIFT

    compounds = {}
    for name, params in base_compounds.items():
        updated = deepcopy(params)
        if "wear_rate_base_pct_per_km" in updated:
            updated["wear_rate_base_pct_per_km"] = round(
                updated["wear_rate_base_pct_per_km"] * wear_multiplier,
                6,
            )
        if "temp_window_surface_c" in updated:
            updated["temp_window_surface_c"] = adjust_temp_window(
                updated["temp_window_surface_c"], temp_shift
            )
        if "temp_window_core_c" in updated:
            updated["temp_window_core_c"] = adjust_temp_window(
                updated["temp_window_core_c"], temp_shift * 0.6
            )
        # Raffreddamento: aumentare leggermente se heat elevato
        if "cooling_coeff" in updated:
            updated["cooling_coeff"] = round(
                updated["cooling_coeff"] * (1.0 + (avg_bump * 0.02)),
                4,
            )
        compounds[name] = updated

    return compounds


def build_payload(
    circuit_id: str,
    telemetry: Dict[str, Any],
    compounds: Dict[str, Dict[str, float]],
    stats: Dict[str, float],
) -> Dict[str, Any]:
    meta = telemetry.get("metadata", {})
    payload = {
        "_meta": {
            "version": "0.1",
            "circuit_id": circuit_id,
            "source_year": meta.get("year"),
            "session_type": meta.get("session_type"),
            "description": meta.get("description"),
            "stats": stats,
        },
        "compounds": compounds,
        "brake_heat_proxy": {
            "brake_density_mj_per_km": round(stats.get("brake_density", 0.0), 3),
            "avg_brake_section_mj": round(stats.get("avg_brake", 0.0), 3),
        },
    }
    return payload


def write_output(payload: Dict[str, Any], circuit_id: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{circuit_id}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out_path


def write_report(payload: Dict[str, Any], circuit_id: str, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    stats = payload["_meta"]["stats"]
    lines = [
        f"# Tyre calibration – {circuit_id}",
        "",
        "## Track stats",
        f"- avg_heat: {stats['avg_heat']:.3f}",
        f"- avg_bump: {stats['avg_bump']:.3f}",
        f"- total_brake_mj: {stats['total_brake']:.3f}",
        f"- brake_density_mj_per_km: {stats['brake_density']:.3f}",
        "",
        "## Compounds",
    ]
    for name, params in payload["compounds"].items():
        lines.append(f"### {name}")
        lines.append("| Parametro | Valore |")
        lines.append("|-----------|--------|")
        for key, value in params.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")
    out_path = report_dir / f"{circuit_id}.md"
    out_path.write_text("\n".join(lines))
    return out_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--circuit-id", required=True, help="ID circuito (es. jp-1962_suzuka)")
    parser.add_argument("--year", type=int, help="Anno Telemetry (cartella data/circuits/<year>)")
    parser.add_argument(
        "--data-dir",
        default="python_backend/data/circuits",
        help="Directory base Telemetry JSON",
    )
    parser.add_argument(
        "--output-dir",
        default="config/calibration/tyres",
        help="Directory output calibrations",
    )
    parser.add_argument(
        "--report-dir",
        help="Directory per report Markdown",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra dati senza scrivere file",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    telemetry = load_telemetry(args.circuit_id, args.year, Path(args.data_dir))
    template = load_json(GLOBAL_TYRE_TEMPLATE)
    sections = telemetry["geometry"]["sections"]
    circuit_length = telemetry["geometry"].get("circuit_length", 5000.0)
    stats = get_section_stats(sections, circuit_length)
    compounds = calibrate_compounds(template["compounds"], stats, circuit_length)
    payload = build_payload(args.circuit_id, telemetry, compounds, stats)

    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("Dry-run attivo: nessun file scritto.")
        return

    out_path = write_output(payload, args.circuit_id, Path(args.output_dir))
    print(f"📝 Salvato: {out_path}")
    if args.report_dir:
        report_path = write_report(payload, args.circuit_id, Path(args.report_dir))
        print(f"📄 Report: {report_path}")


if __name__ == "__main__":
    main()
