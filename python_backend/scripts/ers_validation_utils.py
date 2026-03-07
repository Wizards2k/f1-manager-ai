#!/usr/bin/env python3
"""Shared helpers for ERS bonus validation CLI tools."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence, Tuple

from lap_simulator.config_loader import load_circuit_config
from lap_simulator.data_types import (
    AeroComponent,
    AeroSetup,
    CarState,
    CircuitConfig,
    DriverSkills,
    EngineMapName,
    EnvContext,
    SectionContext,
    SuspensionState,
    TyreCompound,
    clamp,
)
from lap_simulator.engine_penalty import STRAIGHT_KINDS
from lap_simulator.lap_simulator import CarEntry, LapResult, LapSimulator

DEFAULT_ENV = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
DEFAULT_TYRE_COMPOUND = TyreCompound.C4
DEFAULT_FUEL_KG = 80.0
DEFAULT_CIRCUITS = (
    "it-1922_monza",
    "az-2016_baku",
    "jp-1962_suzuka",
    "mc-1929_monaco",
)
DEFAULT_PUSH_LEVELS = (0.90, 1.00, 1.10)


@dataclass
class SectionStat:
    index: int
    section_id: str
    name: str
    kind: str
    length_m: float
    ers_bonus_s: float
    cap_s: float
    is_straight: bool
    clamped: bool


@dataclass
class LapSummary:
    lap_time_s: float
    total_ers_bonus_s: float
    straight_sections: int
    clamp_hits: int
    deploy_mj: float
    mguh_direct_mj: float
    mguh_harvest_mj: float
    fuel_remaining_kg: float
    tyre_wear_pct: float
    tyre_temp_c: float


def build_default_aero_setup() -> AeroSetup:
    return AeroSetup(
        front_wing=AeroComponent(
            name="front_wing",
            base_downforce=30.0,
            base_drag=8.0,
            angle_deg=14.0,
            angle_ref_deg=15.0,
            drs_drag_reduction=0.15,
        ),
        rear_wing=AeroComponent(
            name="rear_wing",
            base_downforce=28.0,
            base_drag=10.0,
            angle_deg=12.0,
            angle_ref_deg=15.0,
            drs_drag_reduction=0.20,
        ),
        beam_wing=AeroComponent(
            name="beam_wing",
            base_downforce=5.0,
            base_drag=2.5,
            angle_deg=8.0,
            angle_ref_deg=10.0,
        ),
        front_floor=AeroComponent(name="front_floor", base_downforce=12.0, base_drag=2.0),
        rear_floor=AeroComponent(name="rear_floor", base_downforce=12.0, base_drag=2.0),
        sidepods=AeroComponent(
            name="sidepods",
            base_downforce=4.0,
            base_drag=3.0,
            cooling_contribution=45.0,
        ),
        engine_cover=AeroComponent(
            name="engine_cover",
            base_downforce=2.0,
            base_drag=1.0,
            cooling_contribution=18.0,
        ),
        b_wing=AeroComponent(name="b_wing", base_downforce=3.0, base_drag=1.5),
        suspension_front=SuspensionState(rigidity=0.55, efficiency=0.80),
        suspension_rear=SuspensionState(rigidity=0.55, efficiency=0.80),
        ride_height_front_mm=35.0,
        ride_height_rear_mm=48.0,
        ride_height_optimal_front_mm=35.0,
        ride_height_optimal_rear_mm=48.0,
    )


def build_default_driver_skills() -> DriverSkills:
    return DriverSkills(
        raw_pace=85,
        race_craft=80,
        aggression=55,
        consistency=82,
        tyre_management=75,
        overtaking_skill=70,
        defending_skill=65,
        wet_skill=70,
        smoothness=72,
        setup_finding=68,
    )


def build_car_entry(
    car_id: str,
    push_level: float,
    map_name: EngineMapName,
    fuel_kg: float = DEFAULT_FUEL_KG,
) -> CarEntry:
    state = CarState(car_id=car_id)
    state.pu.fuel_kg = fuel_kg
    state.pu.active_map = map_name
    for tyre in state.tyres.values():
        tyre.compound = DEFAULT_TYRE_COMPOUND
        tyre.surface_temp_c = 100.0
        tyre.core_temp_c = 88.0
    return CarEntry(
        car_id=car_id,
        state=state,
        aero_setup=build_default_aero_setup(),
        driver_skills=build_default_driver_skills(),
        push_level=push_level,
    )


def clone_config_without_ers(config: CircuitConfig, map_name: EngineMapName) -> CircuitConfig:
    clone = copy.deepcopy(config)
    map_params = clone.pu_maps.get(map_name)
    if map_params:
        map_params.ers_output_kw = 0.0
        map_params.mguh_power_kw = 0.0
        map_params.mguh_direct_ratio = 0.0
    clone.ers_budget.setdefault("maps", {})
    clone.ers_budget["maps"].setdefault(map_name.value, {})
    clone.ers_budget["maps"][map_name.value].update(
        {
            "deploy_mj_per_lap": 0.0,
            "mguh_direct_mj_per_lap": 0.0,
            "bucket_primary_pct": 1.0,
            "bucket_secondary_pct": 0.0,
            "bucket_exit_pct": 0.0,
            "defense_reserve_mj": 0.0,
            "target_soc_end_lap": 0.0,
        }
    )
    return clone


def simulate_laps(
    config: CircuitConfig,
    env: EnvContext,
    push_level: float,
    laps: int,
    map_name: EngineMapName,
    car_suffix: str,
) -> Tuple[List[LapResult], CarEntry]:
    car_id = f"ers_cli_{car_suffix}"
    entry = build_car_entry(car_id=car_id, push_level=push_level, map_name=map_name)
    sim = LapSimulator(config, env)
    sim.register_car(entry)
    if laps <= 1:
        lap = sim.run_lap()[car_id]
        lap_results = [lap]
    else:
        lap_results = sim.run_laps(laps)[car_id]
    return lap_results, entry


def _section_cap(section: SectionContext, config: CircuitConfig) -> float:
    total_straight = max(config.total_straight_length_m, 1.0)
    section_fraction = clamp(section.length_m / total_straight, 0.0, 1.0)
    max_bonus_total_s = config.max_engine_bonus_ms / 1000.0
    if max_bonus_total_s < 0.0 and section.kind in STRAIGHT_KINDS:
        return max_bonus_total_s * section_fraction
    return 0.0


def extract_section_stats(
    config: CircuitConfig,
    lap: LapResult,
    tolerance: float = 5e-5,
) -> Tuple[List[SectionStat], Dict[str, Any]]:
    stats: List[SectionStat] = []
    straight_sections = 0
    clamp_hits = 0
    total_bonus = 0.0
    straight_only_ok = True
    for idx, (section, result) in enumerate(zip(config.sections, lap.section_results)):
        is_straight = section.kind in STRAIGHT_KINDS
        cap_s = _section_cap(section, config)
        bonus = result.ers_bonus_s
        total_bonus += bonus
        if not is_straight and abs(bonus) > tolerance:
            straight_only_ok = False
        if is_straight:
            straight_sections += 1
            if cap_s < 0.0 and bonus >= cap_s - tolerance:
                clamp_hits += 1
        stats.append(
            SectionStat(
                index=idx,
                section_id=section.section_id or f"s{idx:02d}",
                name=section.name or section.section_id or f"Section {idx+1}",
                kind=section.kind.value,
                length_m=section.length_m,
                ers_bonus_s=bonus,
                cap_s=cap_s,
                is_straight=is_straight,
                clamped=is_straight and cap_s < 0.0 and bonus >= cap_s - tolerance,
            )
        )
    meta = {
        "total_bonus_s": total_bonus,
        "straight_only_ok": straight_only_ok,
        "straight_sections": straight_sections,
        "clamp_hits": clamp_hits,
    }
    return stats, meta


def summarize_lap(lap: LapResult, pu_entry: CarEntry, meta: Dict[str, Any]) -> LapSummary:
    pu_state = pu_entry.state.pu
    return LapSummary(
        lap_time_s=lap.lap_time_s,
        total_ers_bonus_s=meta["total_bonus_s"],
        straight_sections=meta["straight_sections"],
        clamp_hits=meta["clamp_hits"],
        deploy_mj=getattr(pu_state, "lap_deploy_mj", 0.0),
        mguh_direct_mj=getattr(pu_state, "lap_mguh_direct_mj", 0.0),
        mguh_harvest_mj=getattr(pu_state, "lap_mguh_harvest_mj", 0.0),
        fuel_remaining_kg=pu_state.fuel_kg,
        tyre_wear_pct=lap.avg_tyre_wear_pct,
        tyre_temp_c=lap.avg_tyre_temp_surface_c,
    )


def run_validation(
    circuit_id: str,
    map_name: str = "STANDARD",
    push_level: float = 1.0,
    laps: int = 1,
    compare_ers_off: bool = False,
    env: Optional[EnvContext] = None,
    tolerance: float = 5e-5,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    if laps < 1:
        raise ValueError("laps must be >= 1")

    env_ctx = env or DEFAULT_ENV
    config = load_circuit_config(circuit_id, project_root=project_root)
    try:
        map_enum = EngineMapName[map_name.upper()]
    except KeyError as exc:
        raise ValueError(f"Unknown engine map '{map_name}'") from exc

    laps_on, entry_on = simulate_laps(config, env_ctx, push_level, laps, map_enum, car_suffix="on")
    lap_on = laps_on[-1]
    sections_on, meta_on = extract_section_stats(config, lap_on, tolerance=tolerance)
    summary_on = summarize_lap(lap_on, entry_on, meta_on)

    checks = [
        {
            "name": "straight_sections_only",
            "ok": meta_on["straight_only_ok"],
            "details": "ERS bonus deve essere applicato solo sui rettilinei",
        },
        {
            "name": "total_bonus_negative",
            "ok": summary_on.total_ers_bonus_s <= -tolerance,
            "details": "La somma dei bonus deve essere negativa (tempo guadagnato)",
        },
        {
            "name": "deploy_within_budget",
            "ok": summary_on.deploy_mj <= config.battery_deploy_limit_mj + 0.05,
            "details": f"Deploy usato {summary_on.deploy_mj:.2f} MJ su limite {config.battery_deploy_limit_mj:.2f} MJ",
        },
    ]

    compare_block: Optional[Dict[str, Any]] = None
    if compare_ers_off:
        config_off = clone_config_without_ers(config, map_enum)
        laps_off, entry_off = simulate_laps(
            config_off,
            env_ctx,
            push_level,
            laps,
            map_enum,
            car_suffix="off",
        )
        lap_off = laps_off[-1]
        delta = lap_on.lap_time_s - lap_off.lap_time_s
        compare_block = {
            "lap_time_s": lap_off.lap_time_s,
            "lap_delta_s": delta,
            "lap_delta_pct": delta / lap_off.lap_time_s if lap_off.lap_time_s else 0.0,
            "avg_speed_delta_kph": mean(sr.v_effective_kph for sr in lap_on.section_results)
            - mean(sr.v_effective_kph for sr in lap_off.section_results),
        }
        checks.append(
            {
                "name": "ers_on_faster_than_off",
                "ok": delta <= tolerance,
                "details": f"Delta lap ERS ON - OFF = {delta:+.4f}s",
            }
        )

    return {
        "circuit_id": config.circuit_id,
        "circuit_name": config.circuit_name,
        "map": map_enum.value,
        "push_level": push_level,
        "laps": laps,
        "lap_times_s": [lap.lap_time_s for lap in laps_on],
        "lap_summary": summary_on.__dict__,
        "section_stats": [stat.__dict__ for stat in sections_on],
        "checks": checks,
        "ers_off": compare_block,
    }


def format_validation_report(result: Dict[str, Any]) -> str:
    lines = []
    lines.append("== ERS Validation ==")
    lines.append(
        f"Circuito: {result['circuit_name'] or result['circuit_id']} | Map: {result['map']} | Push: {result['push_level']:.2f}"
    )
    lines.append(
        f"Lap finale: {result['lap_summary']['lap_time_s']:.3f}s | Bonus tot: {result['lap_summary']['total_ers_bonus_s']:.4f}s"
    )
    lines.append(
        "Deploy: {deploy:.2f} MJ | MGU-H direct: {direct:.2f} MJ | Fuel rimasto: {fuel:.1f} kg".format(
            deploy=result["lap_summary"]["deploy_mj"],
            direct=result["lap_summary"]["mguh_direct_mj"],
            fuel=result["lap_summary"]["fuel_remaining_kg"],
        )
    )
    clamp_ratio = 0.0
    straight_sections = result["lap_summary"]["straight_sections"]
    if straight_sections:
        clamp_ratio = result["lap_summary"]["clamp_hits"] / straight_sections
    lines.append(
        f"Clamp hits: {result['lap_summary']['clamp_hits']} / {straight_sections} straight ({clamp_ratio:.1%})"
    )
    if result.get("ers_off"):
        cmp_block = result["ers_off"]
        lines.append(
            f"ERS OFF lap: {cmp_block['lap_time_s']:.3f}s | Delta (ON-OFF): {cmp_block['lap_delta_s']:+.4f}s ({cmp_block['lap_delta_pct']:+.2%})"
        )
    lines.append("-- Checks --")
    for check in result["checks"]:
        status = "OK" if check["ok"] else "FAIL"
        lines.append(f"[{status}] {check['name']}: {check['details']}")
    lines.append("-- Sezioni con bonus --")
    for stat in result["section_stats"]:
        if not stat["is_straight"]:
            continue
        lines.append(
            f"#{stat['index']:02d} {stat['name']:<28} bonus {stat['ers_bonus_s']:+.4f}s | cap {stat['cap_s']:+.4f}s | clamped={stat['clamped']}"
        )
    return "\n".join(lines)


def write_json_report(result: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2)


__all__ = [
    "DEFAULT_CIRCUITS",
    "DEFAULT_PUSH_LEVELS",
    "run_validation",
    "format_validation_report",
    "write_json_report",
]
