#!/usr/bin/env python3
"""Calibrazione sistema frenante basata sui file Telemetry JSON.

Genera profilo circuito con suggerimenti per rigenerazione, brake migration e cooling.

Esempio d'uso:
    python scripts/brake_calibration.py --circuit-id jp-1962_suzuka --year 2025
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

OUTPUT_DIR_DEFAULT = "config/calibration/brakes"
REPORT_DIR_DEFAULT = "reports/calibration/brakes"

BRAKE_DENSITY_BASE = 3.2  # MJ/km riferimento
REGEN_BASELINE = 0.95
REGEN_SPREAD = 0.18
DUCT_MIN = 0.25
DUCT_MAX = 0.7


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def load_telemetry(circuit_id: str, year: Optional[int], data_dir: Path) -> Dict[str, Any]:
    candidates: List[Path] = []
    if year:
        candidates.append(data_dir / str(year) / f"{circuit_id}_Telemetry.json")
    candidates.append(data_dir / f"{circuit_id}_Telemetry.json")
    for path in candidates:
        if path.exists():
            return load_json(path)
    raise FileNotFoundError(
        f"Telemetry JSON non trovato. Cercati: {', '.join(str(p) for p in candidates)}"
    )


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    pct = clamp(pct, 0.0, 1.0)
    sorted_vals = sorted(values)
    idx = pct * (len(sorted_vals) - 1)
    lower = int(idx)
    upper = min(lower + 1, len(sorted_vals) - 1)
    frac = idx - lower
    return sorted_vals[lower] * (1 - frac) + sorted_vals[upper] * frac


def collect_stats(sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    braking_values = [s.get("braking_energy_mj", 0.0) for s in sections]
    heat_values = [s.get("heat_factor", 1.0) for s in sections if s.get("heat_factor") is not None]
    bump_values = [s.get("bumpiness_factor", 0.0) for s in sections if s.get("bumpiness_factor") is not None]

    total_brake = sum(braking_values)
    length_total = sum(s.get("length_m", 0.0) for s in sections) or 1.0
    brake_density = total_brake / max(length_total / 1000.0, 1.0)

    return {
        "total_brake_mj": total_brake,
        "brake_density": brake_density,
        "avg_brake_section": statistics.mean(braking_values) if braking_values else 0.0,
        "p75_brake_section": percentile(braking_values, 0.75),
        "p90_brake_section": percentile(braking_values, 0.9),
        "peak_brake_section": max(braking_values) if braking_values else 0.0,
        "avg_heat_factor": statistics.mean(heat_values) if heat_values else 1.0,
        "avg_bump_factor": statistics.mean(bump_values) if bump_values else 0.0,
        "length_km": length_total / 1000.0,
    }


def build_brake_profile(stats: Dict[str, Any]) -> Dict[str, Any]:
    density_ratio = stats["brake_density"] / BRAKE_DENSITY_BASE if BRAKE_DENSITY_BASE else 1.0
    regen_base = clamp(REGEN_BASELINE * density_ratio, 0.65, 1.25)
    migration_bias = clamp((regen_base - 1.0) * 1.4, -0.5, 0.6)
    hydraulic_ratio = clamp(1.0 - migration_bias, 0.4, 1.4)

    cooling_delta = stats["avg_heat_factor"] - 1.0
    cooling_front = clamp(0.0 + cooling_delta * 0.6, -0.2, 0.4)
    cooling_rear = clamp(0.0 + cooling_delta * 0.4, -0.2, 0.4)

    duct_min = clamp(DUCT_MIN + cooling_delta * 0.1, 0.2, 0.6)
    duct_max = clamp(DUCT_MAX + cooling_delta * 0.1, 0.5, 0.85)

    regen_range = {
        "min": round(clamp(regen_base - REGEN_SPREAD, 0.4, 1.1), 3),
        "max": round(clamp(regen_base + REGEN_SPREAD, 0.6, 1.4), 3),
    }

    return {
        "regen_brake_base": round(regen_base, 3),
        "regen_migration_bias": round(migration_bias, 3),
        "hydraulic_vs_regen_ratio": round(hydraulic_ratio, 3),
        "cooling_targets": {
            "front_delta": round(cooling_front, 3),
            "rear_delta": round(cooling_rear, 3),
        },
        "duct_recommendation": {
            "min_open": round(duct_min, 3),
            "max_open": round(duct_max, 3),
        },
        "regen_brake_factor_range": regen_range,
        "brake_energy_window": {
            "p75": round(stats["p75_brake_section"], 3),
            "p90": round(stats["p90_brake_section"], 3),
            "peak": round(stats["peak_brake_section"], 3),
        },
    }


def select_critical_sections(sections: List[Dict[str, Any]], top_n: int = 8) -> List[Dict[str, Any]]:
    sorted_sections = sorted(
        sections,
        key=lambda s: s.get("braking_energy_mj", 0.0),
        reverse=True,
    )
    result = []
    for section in sorted_sections[:top_n]:
        result.append(
            {
                "id": section.get("id") or section.get("name"),
                "name": section.get("name", "unknown"),
                "braking_energy_mj": round(section.get("braking_energy_mj", 0.0), 3),
                "heat_factor": round(section.get("heat_factor", 1.0), 3),
                "bumpiness_factor": round(section.get("bumpiness_factor", 0.0), 3),
                "length_m": round(section.get("length_m", 0.0), 1),
            }
        )
    return result


def build_payload(
    circuit_id: str,
    telemetry: Dict[str, Any],
    stats: Dict[str, Any],
    sections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    profile = build_brake_profile(stats)
    payload = {
        "_meta": {
            "version": "0.1",
            "circuit_id": circuit_id,
            "stats": stats,
            "notes": "Derived from telemetry braking energy and thermal factors",
        },
        "brake_profile": profile,
        "critical_sections": select_critical_sections(sections),
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
    profile = payload.get("brake_profile", {})
    sections = payload.get("critical_sections", [])
    lines = [
        f"# Brake calibration – {circuit_id}",
        "",
        "## Track stats",
        f"- brake_density (MJ/km): {stats['brake_density']:.3f}",
        f"- avg_brake_section (MJ): {stats['avg_brake_section']:.3f}",
        f"- p90_brake_section (MJ): {stats['p90_brake_section']:.3f}",
        f"- peak_brake_section (MJ): {stats['peak_brake_section']:.3f}",
        f"- avg_heat_factor: {stats['avg_heat_factor']:.3f}",
        f"- avg_bump_factor: {stats['avg_bump_factor']:.3f}",
        "",
        "## Brake profile",
        f"- regen_brake_base: {profile.get('regen_brake_base')}",
        f"- regen_migration_bias: {profile.get('regen_migration_bias')}",
        f"- hydraulic_vs_regen_ratio: {profile.get('hydraulic_vs_regen_ratio')}",
        f"- cooling_targets: {profile.get('cooling_targets')}",
        f"- duct_recommendation: {profile.get('duct_recommendation')}",
        f"- regen_brake_factor_range: {profile.get('regen_brake_factor_range')}",
        f"- brake_energy_window: {profile.get('brake_energy_window')}",
        "",
        "## Critical sections",
        "| Name | Braking MJ | Heat | Bump | Length (m) |",
        "|------|-----------|------|------|------------|",
    ]
    for section in sections:
        lines.append(
            f"| {section['name']} | {section['braking_energy_mj']} | {section['heat_factor']} | "
            f"{section['bumpiness_factor']} | {section['length_m']} |"
        )
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
        default=OUTPUT_DIR_DEFAULT,
        help="Directory output brake calibration",
    )
    parser.add_argument(
        "--report-dir",
        default=REPORT_DIR_DEFAULT,
        help="Directory per report Markdown",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra risultati senza scrivere file",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    telemetry = load_telemetry(args.circuit_id, args.year, Path(args.data_dir))
    sections = telemetry["geometry"]["sections"]
    stats = collect_stats(sections)
    payload = build_payload(args.circuit_id, telemetry, stats, sections)

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
