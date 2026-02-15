#!/usr/bin/env python3
"""Calibrazione mappe Power Unit per circuito usando Telemetry JSON.

Usage:
    python scripts/powerunit_fit.py --circuit-id jp-1962_suzuka --year 2025
"""
from __future__ import annotations

import argparse
import json
import statistics
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

PU_MAP_TEMPLATE = Path("config/pu/pu_maps_global_default.json")

MAP_TORQUE_OFFSETS = {
    "ECONOMY": -0.08,
    "STANDARD": 0.0,
    "RICH": 0.06,
    "QUALY": 0.12,
    "WET": -0.04,
    "RECHARGE": -0.1,
}

MAP_DEPLOY_INTENT = {
    "ECONOMY": 0.85,
    "STANDARD": 1.0,
    "RICH": 1.08,
    "QUALY": 1.15,
    "WET": 0.9,
    "RECHARGE": 0.45,
}

MAP_HARVEST_INTENT = {
    "ECONOMY": 1.05,
    "STANDARD": 1.0,
    "RICH": 0.9,
    "QUALY": 0.75,
    "WET": 1.1,
    "RECHARGE": 1.4,
}

MAP_MGUH_DIRECT_OFFSETS = {
    "QUALY": 0.12,
    "RICH": 0.06,
    "STANDARD": 0.0,
    "ECONOMY": -0.04,
    "WET": -0.05,
    "RECHARGE": -0.18,
}

MAP_MGUH_POWER_SCALE = {
    "QUALY": 1.1,
    "RICH": 1.05,
    "STANDARD": 1.0,
    "ECONOMY": 0.92,
    "WET": 0.9,
    "RECHARGE": 0.8,
}

MGUH_PROFILES = [
    {
        "name": "high_speed_spec",
        "power_bias_min": 0.6,
        "total_mj": 7.5,
        "direct_mj": 4.5,
        "es_mj": 3.0,
        "notes": "Monza / Spa",
    },
    {
        "name": "balanced_spec",
        "power_bias_min": 0.4,
        "total_mj": 5.5,
        "direct_mj": 3.0,
        "es_mj": 2.5,
        "notes": "Silverstone / Barcelona",
    },
    {
        "name": "low_speed_spec",
        "power_bias_min": 0.0,
        "total_mj": 2.3,
        "direct_mj": 0.5,
        "es_mj": 1.8,
        "notes": "Monaco / Hungaroring",
    },
]

BATTERY_CAPACITY_MJ = 5.5
MGUK_DEPLOY_LIMIT_MJ = 4.0
MGUK_HARVEST_LIMIT_MJ = 2.0


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


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
    raise FileNotFoundError(
        f"Telemetry JSON non trovato. Cercati: {', '.join(str(p) for p in candidates)}"
    )


def compute_stats(sections: List[Dict[str, Any]]) -> Dict[str, float]:
    heat_values = [s.get("heat_factor", 1.0) for s in sections if s.get("heat_factor") is not None]
    heat_mean = statistics.mean(heat_values) if heat_values else 1.0
    heat_peak = max(heat_values) if heat_values else 1.0

    length_total = sum(s.get("length_m", 0.0) for s in sections) or 1.0
    drs_length = sum(s.get("length_m", 0.0) for s in sections if s.get("drs_active"))

    high_speed_length = sum(
        s.get("length_m", 0.0)
        for s in sections
        if (s.get("kind", "").startswith("Straight") or s.get("v_max_kph", 0) >= 280)
    )

    braking_energy = [s.get("braking_energy_mj", 0.0) for s in sections]
    total_brake = sum(braking_energy)
    brake_density = total_brake / max(length_total / 1000.0, 1.0)
    avg_brake_section = statistics.mean(braking_energy) if braking_energy else 0.0
    brake_p25 = percentile(braking_energy, 0.25)
    brake_p75 = percentile(braking_energy, 0.75)
    brake_p90 = percentile(braking_energy, 0.90)
    brake_peak = max(braking_energy) if braking_energy else 0.0

    return {
        "heat_mean": heat_mean,
        "heat_peak": heat_peak,
        "drs_ratio": clamp(drs_length / length_total, 0.0, 1.0),
        "power_bias": clamp(high_speed_length / length_total, 0.0, 1.0),
        "total_brake": total_brake,
        "brake_density": brake_density,
        "avg_brake_section": avg_brake_section,
        "brake_energy_p25": brake_p25,
        "brake_energy_p75": brake_p75,
        "brake_energy_p90": brake_p90,
        "brake_energy_peak": brake_peak,
        "circuit_length_m": length_total,
    }


def select_mguh_profile(stats: Dict[str, float]) -> Dict[str, Any]:
    power_bias = stats.get("power_bias", 0.5)
    selected = MGUH_PROFILES[-1]
    for profile in sorted(MGUH_PROFILES, key=lambda p: p["power_bias_min"], reverse=True):
        if power_bias >= profile.get("power_bias_min", 0.0) - 1e-6:
            selected = profile
            break
    total_mj = max(selected.get("total_mj", 4.5), 0.1)
    direct_mj = clamp(selected.get("direct_mj", total_mj * 0.6), 0.0, total_mj)
    es_mj = clamp(selected.get("es_mj", total_mj - direct_mj), 0.0, total_mj)
    direct_bias = clamp(direct_mj / total_mj, 0.05, 0.95)
    es_bias = clamp(es_mj / total_mj, 0.05, 0.95)
    enriched = dict(selected)
    enriched["direct_bias"] = direct_bias
    enriched["es_bias"] = es_bias
    return enriched


def estimate_lap_time(sections: List[Dict[str, Any]], reference: Optional[Dict[str, Any]]) -> float:
    if reference:
        lap_time = reference.get("lap_time") or reference.get("lap_time_s")
        if isinstance(lap_time, (int, float)) and lap_time > 0:
            return float(lap_time)
    dt_sum = 0.0
    for section in sections or []:
        dt_ref = section.get("dt_ref_s")
        if isinstance(dt_ref, (int, float)) and dt_ref > 0:
            dt_sum += dt_ref
        else:
            length = section.get("length_m", 0.0)
            avg_speed = section.get("avg_speed_kph", section.get("v_base_kph", 200.0))
            avg_ms = max(avg_speed / 3.6, 1.0)
            dt_sum += length / avg_ms
    return max(dt_sum, 60.0)


def adjust_map(
    map_name: str,
    base: Dict[str, Any],
    stats: Dict[str, float],
    mguh_profile: Dict[str, Any],
    lap_time_s: float,
) -> Dict[str, Any]:
    heat_mean = stats["heat_mean"]
    heat_peak = stats["heat_peak"]
    drs_ratio = stats["drs_ratio"]
    brake_density = stats["brake_density"]
    power_bias = stats["power_bias"]

    updated = deepcopy(base)

    heat_scale = 1.0 + 0.25 * (heat_mean - 1.0) + 0.08 * (heat_peak - 1.0)
    updated["heat_load_kw"] = round(clamp(base.get("heat_load_kw", 260) * heat_scale, 200, 380), 2)

    cooling_base = base.get("cooling_share", 0.5)
    cooling_adj = cooling_base + 0.2 * (heat_mean - 1.0)
    updated["cooling_share"] = round(clamp(cooling_adj, 0.35, 0.65), 3)

    torque_base = base.get("torque_ramp", 0.6)
    torque_adj = torque_base + MAP_TORQUE_OFFSETS.get(map_name, 0.0) + (power_bias - 0.5) * 0.12
    updated["torque_ramp"] = round(clamp(torque_adj, 0.35, 1.0), 4)

    ers_base = base.get("ers_output_kw", 120)
    ers_scale = 1.0 + 0.45 * drs_ratio + 0.18 * clamp(brake_density / 5.0, -0.2, 1.0)
    updated["ers_output_kw"] = round(clamp(ers_base * ers_scale, 70, 200), 2)

    deploy_base = base.get("deploy_mj_per_lap", 3.0)
    deploy_factor = MAP_DEPLOY_INTENT.get(map_name, 1.0)
    deploy_dynamic = 1.0 + 0.35 * (power_bias - 0.5) + 0.2 * (heat_mean - 1.0)
    deploy_value = clamp(
        deploy_base * deploy_factor * deploy_dynamic,
        0.5,
        MGUK_DEPLOY_LIMIT_MJ,
    )
    updated["deploy_mj_per_lap"] = round(deploy_value, 3)

    harvest_base = base.get("harvest_mj_per_lap", 1.5)
    harvest_factor = MAP_HARVEST_INTENT.get(map_name, 1.0)
    harvest_dynamic = 1.0 + 0.4 * clamp((brake_density / 3.5) - 1.0, -0.6, 0.8)
    harvest_value = clamp(harvest_base * harvest_factor * harvest_dynamic, 0.3, MGUK_HARVEST_LIMIT_MJ)
    updated["harvest_mj_per_lap"] = round(harvest_value, 3)

    profile_direct = mguh_profile.get("direct_bias", 0.5)
    mguh_base = base.get("mguh_direct_ratio", profile_direct)
    offset = MAP_MGUH_DIRECT_OFFSETS.get(map_name.upper(), 0.0)
    mguh_adj = profile_direct + offset + 0.15 * (drs_ratio - 0.4)
    updated["mguh_direct_ratio"] = round(clamp(mguh_adj, 0.05, 0.9), 3)

    total_mj = mguh_profile.get("total_mj", 4.5)
    power_scale = MAP_MGUH_POWER_SCALE.get(map_name.upper(), 1.0)
    lap_time = max(lap_time_s, 60.0)
    base_kw = (total_mj / lap_time) * 1000.0
    updated["mguh_power_kw"] = round(clamp(base_kw * power_scale, 20.0, 120.0), 2)

    torque_bias = base.get("torque_bias", 0.0) + (power_bias - 0.5) * 0.1
    updated["torque_bias"] = round(clamp(torque_bias, -0.2, 0.2), 4)

    target_soc = base.get("target_soc_end_lap", 0.6)
    soc_delta = (harvest_value - deploy_value) * 0.15
    if map_name.upper() == "QUALY":
        soc_delta -= 0.2
    if map_name.upper() == "RECHARGE":
        soc_delta += 0.25
    updated["target_soc_end_lap"] = round(clamp(target_soc + soc_delta, 0.05, 0.98), 3)

    limit_flags = {
        "deploy_limit_hit": deploy_value >= MGUK_DEPLOY_LIMIT_MJ - 0.05,
        "harvest_limit_hit": harvest_value >= MGUK_HARVEST_LIMIT_MJ - 0.05,
    }

    updated["notes"] = {
        "map": map_name,
        "heat_scale": round(heat_scale, 3),
        "cooling_target": updated["cooling_share"],
        "torque_bias_delta": round((power_bias - 0.5) * 0.1, 4),
        "drs_ratio": round(drs_ratio, 3),
        "deploy_dynamic": round(deploy_dynamic, 3),
        "harvest_dynamic": round(harvest_dynamic, 3),
        **limit_flags,
    }
    return updated


def compute_regen_profile(stats: Dict[str, float]) -> Dict[str, float]:
    brake_density = stats["brake_density"]
    avg_brake_section = stats["avg_brake_section"]
    regen_factor = clamp(0.78 + 0.1 * min(brake_density / 3.5, 1.5), 0.6, 1.25)
    regen_limit_nm = clamp(280.0 + 35.0 * brake_density, 240.0, 520.0)
    regen_mj_per_lap = clamp(avg_brake_section * 0.3 * (stats["circuit_length_m"] / 1000.0), 0.3, 2.2)
    migration_bias = clamp((regen_factor - 1.0) * 1.6, -0.6, 0.6)
    brake_window = {
        "min_mj": round(stats.get("brake_energy_p25", avg_brake_section), 3),
        "max_mj": round(stats.get("brake_energy_p90", avg_brake_section), 3),
    }
    return {
        "base_factor": round(regen_factor, 3),
        "limit_nm": round(regen_limit_nm, 1),
        "potential_mj_per_lap": round(regen_mj_per_lap, 3),
        "regen_migration_bias": round(migration_bias, 3),
        "brake_energy_window": brake_window,
    }


def build_ers_budget(calibrated_maps: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    warnings: List[str] = []
    for name, params in calibrated_maps.items():
        deploy = params.get("deploy_mj_per_lap", 0.0)
        harvest = params.get("harvest_mj_per_lap", 0.0)
        target_soc = params.get("target_soc_end_lap", 0.6)
        deploy_ratio = deploy / MGUK_DEPLOY_LIMIT_MJ if MGUK_DEPLOY_LIMIT_MJ else 0.0
        harvest_ratio = harvest / MGUK_HARVEST_LIMIT_MJ if MGUK_HARVEST_LIMIT_MJ else 0.0
        summary[name] = {
            "deploy_mj_per_lap": deploy,
            "harvest_mj_per_lap": harvest,
            "target_soc_end_lap": target_soc,
            "deploy_ratio": round(deploy_ratio, 3),
            "harvest_ratio": round(harvest_ratio, 3),
        }
        if deploy_ratio >= 0.95:
            warnings.append(f"{name}: deploy at {deploy_ratio * 100:.0f}% of MGU-K limit")
        if harvest_ratio <= 0.35 and deploy_ratio >= 0.8:
            warnings.append(f"{name}: harvest insufficient vs deploy (ratio {harvest_ratio:.2f})")
        if target_soc <= 0.2:
            warnings.append(f"{name}: SOC target very low ({target_soc:.2f}) – plan recharge lap")
    return {
        "battery_capacity_mj": BATTERY_CAPACITY_MJ,
        "deploy_limit_mj": MGUK_DEPLOY_LIMIT_MJ,
        "harvest_limit_mj": MGUK_HARVEST_LIMIT_MJ,
        "maps": summary,
        "warnings": warnings,
    }


def build_payload(
    circuit_id: str,
    telemetry: Dict[str, Any],
    template: Dict[str, Any],
    stats: Dict[str, float],
) -> Dict[str, Any]:
    meta = telemetry.get("metadata", {})
    maps = template.get("maps", {})
    sections = telemetry.get("geometry", {}).get("sections", [])
    lap_time_s = estimate_lap_time(sections, telemetry.get("reference_lap"))
    mguh_profile = select_mguh_profile(stats)
    calibrated_maps = {
        name: adjust_map(name, params, stats, mguh_profile, lap_time_s)
        for name, params in maps.items()
    }
    ers_budget = build_ers_budget(calibrated_maps)
    payload = {
        "_meta": {
            "version": "0.1",
            "circuit_id": circuit_id,
            "source_year": meta.get("year"),
            "session_type": meta.get("session_type"),
            "description": meta.get("description"),
            "stats": stats,
            "mguh_profile": mguh_profile,
            "lap_time_s": lap_time_s,
        },
        "maps": calibrated_maps,
        "regen_profile": compute_regen_profile(stats),
        "ers_budget": ers_budget,
        "soc_warnings": ers_budget.get("warnings", []),
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
    regen = payload.get("regen_profile", {})
    ers_budget = payload.get("ers_budget", {})
    budget_maps = ers_budget.get("maps", {})
    lines = [
        f"# PowerUnit calibration – {circuit_id}",
        "",
        "## Track stats",
        f"- heat_mean: {stats['heat_mean']:.3f}",
        f"- heat_peak: {stats['heat_peak']:.3f}",
        f"- drs_ratio: {stats['drs_ratio']:.3f}",
        f"- brake_density (MJ/km): {stats['brake_density']:.3f}",
        f"- power_bias: {stats['power_bias']:.3f}",
        f"- circuit_length_km: {stats['circuit_length_m'] / 1000.0:.3f}",
        "",
        "## Regen profile",
        f"- base_factor: {regen.get('base_factor', 'n/a')}",
        f"- limit_nm: {regen.get('limit_nm', 'n/a')}",
        f"- potential_mj_per_lap: {regen.get('potential_mj_per_lap', 'n/a')}",
        f"- regen_migration_bias: {regen.get('regen_migration_bias', 'n/a')}",
        f"- brake_energy_window: {regen.get('brake_energy_window', {})}",
        "",
        "## ERS budget",
        f"- battery_capacity_mj: {ers_budget.get('battery_capacity_mj', 'n/a')}",
        f"- deploy_limit_mj: {ers_budget.get('deploy_limit_mj', 'n/a')}",
        f"- harvest_limit_mj: {ers_budget.get('harvest_limit_mj', 'n/a')}",
        "",
        "| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |",
        "|-----|-------------|--------------|------------|--------------|---------------|",
    ]
    for name, summary in budget_maps.items():
        lines.append(
            f"| {name} | {summary['deploy_mj_per_lap']} | {summary['harvest_mj_per_lap']} | "
            f"{summary['target_soc_end_lap']} | {summary['deploy_ratio']} | {summary['harvest_ratio']} |"
        )
    lines.append("")
    warnings = payload.get("soc_warnings", [])
    if warnings:
        lines.append("## SOC warnings")
        for warn in warnings:
            lines.append(f"- {warn}")
        lines.append("")
    lines.append("## Maps")
    for name, params in payload["maps"].items():
        lines.append(f"### {name}")
        lines.append("| Parametro | Valore |")
        lines.append("|-----------|--------|")
        for key, value in params.items():
            if key == "notes":
                continue
            lines.append(f"| {key} | {value} |")
        notes = params.get("notes")
        if notes:
            lines.append("")
            lines.append("Notes:")
            for n_key, n_val in notes.items():
                lines.append(f"- {n_key}: {n_val}")
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
        default="config/calibration/pu",
        help="Directory output PU maps calibrate",
    )
    parser.add_argument(
        "--report-dir",
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
    template = load_json(PU_MAP_TEMPLATE)
    sections = telemetry["geometry"]["sections"]
    stats = compute_stats(sections)
    payload = build_payload(args.circuit_id, telemetry, template, stats)

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
