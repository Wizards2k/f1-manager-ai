#!/usr/bin/env python3
"""Backfill ERS mode-specific budgets into circuit pu_maps.json files."""

from __future__ import annotations

import argparse
import copy
import importlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DERIVED_DIR = REPO_ROOT / "config" / "circuits" / "derived"
CALIBRATION_DIR = REPO_ROOT / "config" / "calibration" / "pu"
SUZUKA_TEMPLATE_CIRCUIT_ID = "jp-1962_suzuka"
SUZUKA_TEMPLATE_PATH = DERIVED_DIR / SUZUKA_TEMPLATE_CIRCUIT_ID / "pu_maps.json"

PYTHON_BACKEND_DIR = REPO_ROOT / "python_backend"
PYTHON_BACKEND_SCRIPTS = PYTHON_BACKEND_DIR / "scripts"
for extra_path in (PYTHON_BACKEND_DIR, PYTHON_BACKEND_SCRIPTS):
    extra = str(extra_path)
    if extra not in sys.path:
        sys.path.insert(0, extra)

from lap_simulator.config_loader import load_circuit_config
from lap_simulator.data_types import (
    AeroComponent,
    AeroSetup,
    CarState,
    DriverSkills,
    EngineMapName,
    EnvContext,
    SuspensionState,
    TyreCompound,
    clamp,
)
from lap_simulator.update_section import update_section

lap_simulator_runtime = importlib.import_module("lap_simulator.lap_simulator")
if not hasattr(lap_simulator_runtime, "DEBUG_PENALTIES"):
    lap_simulator_runtime.DEBUG_PENALTIES = False

ENGINE_MAP_ALIASES = {
    "STANDARD": "RACE",
    "QUALITY": "QUALIFY",
}


def _round_if_number(value):
    if isinstance(value, (int, float)):
        return round(float(value), 3)
    return value


def load_ers_budget_template(template_path: Path = SUZUKA_TEMPLATE_PATH) -> Dict[str, Dict[str, Any]]:
    if not template_path.exists():
        raise FileNotFoundError(f"Suzuka ERS template not found: {template_path}")

    data = json.loads(template_path.read_text())
    budget = data.get("ers_budget")
    if not isinstance(budget, dict):
        raise ValueError(f"Suzuka ERS template {template_path} is missing an ers_budget object")

    template_maps = budget.get("maps")
    if not isinstance(template_maps, dict) or not template_maps:
        raise ValueError(f"Suzuka ERS template {template_path} has no ers_budget.maps entries")

    return copy.deepcopy(template_maps)


def process_file(path: Path, template_maps: Dict[str, Dict[str, Any]], dry_run: bool = False) -> bool:
    data = json.loads(path.read_text())
    budget = data.get("ers_budget")
    if not isinstance(budget, dict):
        return False

    current_maps = budget.get("maps")
    if current_maps == template_maps:
        return False

    budget["maps"] = copy.deepcopy(template_maps)
    if not dry_run:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return True


MGUH_DIRECT_RATIO_BASELINE = 0.45
MGUK_HARVEST_LIMIT_MJ = 2.0
TARGET_DOC_PATH = REPO_ROOT / "docs" / "Ers-Deploy-Sim.md"
ENERGY_DOC_PATH = REPO_ROOT / "docs" / "PU-Engine-MGU-H.md"

TARGET_LABEL_BY_CIRCUIT_ID = {
    "ae-2009_yas_marina": "Abu Dhabi",
    "at-1969_spielberg": "Austria",
    "au-1953_melbourne": "Australia",
    "az-2016_baku": "Azerbaijan",
    "be-1925_spa_francorchamps": "Belgium (Spa)",
    "bh-2002_sakhir": "Bahrain",
    "br-1940_sao_paulo": "Brazil",
    "ca-1978_montreal": "Canada",
    "cn-2004_shanghai": "China",
    "es-1991_barcelona": "Spain",
    "gb-1948_silverstone": "Great Britain",
    "hu-1986_budapest": "Hungary",
    "it-1922_monza": "Italy (Monza)",
    "it-1953_imola": "Emilia-Romagna",
    "jp-1962_suzuka": "Japan (Suzuka)",
    "mc-1929_monaco": "Monaco",
    "mx-1962_mexico_city": "Mexico",
    "nl-1948_zandvoort": "Netherlands",
    "qa-2004_lusail": "Qatar",
    "sa-2021_jeddah": "Saudi Arabia",
    "sg-2008_singapore": "Singapore",
    "us-2012_austin": "USA (Austin)",
    "us-2022_miami": "Miami",
    "us-2023_las_vegas": "Las Vegas",
}

ENERGY_TABLE_TARGET_LABEL_BY_CIRCUIT_ID = {
    **TARGET_LABEL_BY_CIRCUIT_ID,
    "gb-1948_silverstone": "Silverstone",
    "it-1953_imola": "Imola",
}


@dataclass(frozen=True)
class MguhTarget:
    label: str
    min_mj: float
    max_mj: float


@dataclass
class MguhFitResult:
    circuit_id: str
    circuit_name: str
    map_name: str
    target_label: str
    target_min_mj: float
    target_max_mj: float
    start_total_mj: float
    start_sim_mj: float
    best_total_mj: float
    best_sim_mj: float
    best_power_kw: float
    iterations: int
    converged: bool


@dataclass(frozen=True)
class EnergyTableTarget:
    label: str
    mguk_min_mj: float
    mguk_max_mj: float
    mguh_min_mj: float
    mguh_max_mj: float
    total_min_mj: float
    total_max_mj: float


@dataclass(frozen=True)
class RuntimeLapResult:
    mguh_total_mj: float
    harvest_mj: float
    lap_time_s: float
    deploy_mj: float


@dataclass(frozen=True)
class EnergyValidationResult:
    circuit_id: str
    circuit_name: str
    map_name: str
    target_label: str
    mguk_target_min_mj: float
    mguk_target_max_mj: float
    mguh_target_min_mj: float
    mguh_target_max_mj: float
    total_target_min_mj: float
    total_target_max_mj: float
    runtime_harvest_mj: float
    runtime_mguh_mj: float
    runtime_total_mj: float
    lap_time_s: float
    deploy_mj: float
    mguk_ok: bool
    mguh_ok: bool
    total_ok: bool
    harvest_limit_ok: bool


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _resolve_engine_map_name(raw_name: str) -> EngineMapName:
    candidate = ENGINE_MAP_ALIASES.get((raw_name or "").upper(), raw_name or "")
    try:
        return EngineMapName[candidate.upper()]
    except KeyError as exc:
        raise ValueError(f"Unknown engine map '{raw_name}'") from exc


def load_doc_targets(doc_path: Path = TARGET_DOC_PATH) -> Dict[str, MguhTarget]:
    text = doc_path.read_text(encoding="utf-8")
    targets: Dict[str, MguhTarget] = {}
    in_table = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if in_table:
                break
            continue
        if line.startswith("Round,Circuito,Recupero MGU-H (MJ)"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("Round,"):
            continue

        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        label = parts[1]
        match = re.match(r"([0-9.]+)\s*-\s*([0-9.]+)", parts[2])
        if not match:
            continue
        min_mj, max_mj = map(float, match.groups())
        targets[_normalize_key(label)] = MguhTarget(label=label, min_mj=min_mj, max_mj=max_mj)

    if not targets:
        raise ValueError(f"No MGU-H targets could be parsed from {doc_path}")
    return targets


def _resolve_target_for_circuit(circuit_id: str, doc_targets: Dict[str, MguhTarget]) -> Optional[MguhTarget]:
    label = TARGET_LABEL_BY_CIRCUIT_ID.get(circuit_id)
    if label is None:
        return None
    return doc_targets.get(_normalize_key(label))


def _resolve_energy_target_for_circuit(
    circuit_id: str,
    doc_targets: Dict[str, EnergyTableTarget],
) -> Optional[EnergyTableTarget]:
    label = ENERGY_TABLE_TARGET_LABEL_BY_CIRCUIT_ID.get(circuit_id)
    if label is None:
        return None
    return doc_targets.get(_normalize_key(label))


def _strip_md_markup(value: str) -> str:
    return re.sub(r"[*_`]+", "", (value or "")).strip()


def _parse_energy_cell(cell: str) -> Tuple[float, float]:
    cleaned = _strip_md_markup(cell).replace("MJ", "")
    numbers = re.findall(r"[0-9]+(?:\.[0-9]+)?", cleaned)
    if not numbers:
        raise ValueError(f"Cannot parse energy cell '{cell}'")
    if len(numbers) == 1:
        value = float(numbers[0])
        return value, value
    return float(numbers[0]), float(numbers[1])


def load_energy_table_targets(doc_path: Path = ENERGY_DOC_PATH) -> Dict[str, EnergyTableTarget]:
    text = doc_path.read_text(encoding="utf-8")
    targets: Dict[str, EnergyTableTarget] = {}
    in_table = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if in_table:
                break
            continue
        if line.startswith("| Round | Circuito |") and "MGU-K" in line and "MGU-H" in line:
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("| :---"):
            continue
        if not line.startswith("|"):
            break

        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) < 5:
            continue

        label = _strip_md_markup(parts[1])
        try:
            mguk_min_mj, mguk_max_mj = _parse_energy_cell(parts[2])
            mguh_min_mj, mguh_max_mj = _parse_energy_cell(parts[3])
            total_min_mj, total_max_mj = _parse_energy_cell(parts[4])
        except ValueError:
            continue

        targets[_normalize_key(label)] = EnergyTableTarget(
            label=label,
            mguk_min_mj=mguk_min_mj,
            mguk_max_mj=mguk_max_mj,
            mguh_min_mj=mguh_min_mj,
            mguh_max_mj=mguh_max_mj,
            total_min_mj=total_min_mj,
            total_max_mj=total_max_mj,
        )

    if not targets:
        raise ValueError(f"No energy targets could be parsed from {doc_path}")
    return targets


def _estimate_mguh_power_kw(total_mj: float, lap_time_s: float) -> float:
    lap_time = max(lap_time_s, 1.0)
    return round(clamp((total_mj / lap_time) * 1000.0, 8.0, 100.0), 3)


RUNTIME_ENV = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
RUNTIME_DEFAULT_FUEL_KG = 80.0
RUNTIME_DEFAULT_PUSH_LEVEL = 5
RUNTIME_CAR_ID = "mguh_fit"
ENERGY_TABLE_TOLERANCE_MJ = 0.005


def _build_runtime_aero_setup() -> AeroSetup:
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


def _build_runtime_driver_skills() -> DriverSkills:
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


def _build_runtime_car_state(map_name: EngineMapName, fuel_kg: float = RUNTIME_DEFAULT_FUEL_KG) -> CarState:
    state = CarState(car_id=RUNTIME_CAR_ID)
    state.pu.fuel_kg = fuel_kg
    state.pu.active_map = map_name
    state.ers_mode = "QUALIFY" if map_name == EngineMapName.QUALIFY else "STANDARD"
    for tyre in state.tyres.values():
        tyre.compound = TyreCompound.C4
        tyre.surface_temp_c = 95.0
        tyre.core_temp_c = 85.0
    return state


def _run_runtime_lap(
    config: Any,
    map_name: EngineMapName,
    push_level: int,
    fuel_kg: float = RUNTIME_DEFAULT_FUEL_KG,
) -> RuntimeLapResult:
    sections = list(getattr(config, "sections", []) or [])
    if not sections:
        return RuntimeLapResult(mguh_total_mj=0.0, harvest_mj=0.0, lap_time_s=0.0, deploy_mj=0.0)

    car_state = _build_runtime_car_state(map_name, fuel_kg=fuel_kg)
    aero_setup = _build_runtime_aero_setup()
    driver_skills = _build_runtime_driver_skills()

    start_speed_kph = sections[0].v_entry_kph or sections[0].v_base_kph or 200.0
    car_state.v_current_ms = max(start_speed_kph / 3.6, 1.0)

    for idx, section in enumerate(sections):
        car_state.current_section_idx = idx
        car_state.section_progress = 0.0
        update_section(
            car_state=car_state,
            aero_setup=aero_setup,
            driver_skills=driver_skills,
            section=section,
            env=RUNTIME_ENV,
            config=config,
            push_level=push_level,
            delta_aero=0.0,
            delta_grip=0.0,
            apply_baseline_delta=True,
            is_qualifying=(map_name == EngineMapName.QUALIFY),
            circuit_id=getattr(config, "circuit_id", "mguh_fit"),
            driver_id=car_state.car_id,
            lap_number=car_state.lap_number,
        )

    total_mguh = round(car_state.pu.lap_mguh_direct_mj + car_state.pu.lap_mguh_harvest_mj, 4)
    lap_time = round(car_state.lap_time_acc_s, 4)
    deploy = round(car_state.pu.lap_deploy_mj, 4)
    harvest = round(car_state.pu.lap_harvest_mj, 4)
    return RuntimeLapResult(
        mguh_total_mj=total_mguh,
        harvest_mj=harvest,
        lap_time_s=lap_time,
        deploy_mj=deploy,
    )


def _build_candidate_config(
    config: Any,
    map_name: EngineMapName,
    total_mj: float,
    direct_ratio: float = MGUH_DIRECT_RATIO_BASELINE,
) -> Tuple[Any, float]:
    candidate = copy.deepcopy(config)
    map_params = candidate.pu_maps.get(map_name)
    if map_params is None:
        raise KeyError(f"Engine map {map_name.value} not found in circuit config")

    power_kw = _estimate_mguh_power_kw(total_mj, candidate.reference_lap_time_s or 90.0)
    map_params.mguh_power_kw = power_kw
    map_params.mguh_direct_ratio = direct_ratio

    ers_maps = candidate.ers_budget.setdefault("maps", {})
    budget_map = ers_maps.setdefault(map_name.value, {})
    budget_map["mguh_direct_ratio"] = round(direct_ratio, 3)
    return candidate, power_kw


def _evaluate_candidate(
    config: Any,
    map_name: EngineMapName,
    total_mj: float,
    push_level: int,
) -> Tuple[float, MguhFitResult, float]:
    candidate, power_kw = _build_candidate_config(config, map_name, total_mj)
    runtime = _run_runtime_lap(candidate, map_name, push_level)
    total = runtime.mguh_total_mj
    result = MguhFitResult(
        circuit_id=candidate.circuit_id,
        circuit_name=candidate.circuit_name,
        map_name=map_name.value,
        target_label="",
        target_min_mj=0.0,
        target_max_mj=0.0,
        start_total_mj=total_mj,
        start_sim_mj=total,
        best_total_mj=total_mj,
        best_sim_mj=total,
        best_power_kw=power_kw,
        iterations=1,
        converged=False,
    )
    # Store the runtime lap time in the target label field temporarily for debugging if needed.
    # The caller prints the runtime total only; lap_time/deploy are retained by the harness via local variables.
    return total, result, power_kw


def _validate_energy_table_entry(
    path: Path,
    map_name: EngineMapName,
    doc_targets: Dict[str, EnergyTableTarget],
    push_level: int,
) -> Optional[EnergyValidationResult]:
    data = json.loads(path.read_text())
    meta = data.get("_meta") if isinstance(data.get("_meta"), dict) else {}
    circuit_id = meta.get("circuit_id") or path.parent.name
    target = _resolve_energy_target_for_circuit(circuit_id, doc_targets)
    if target is None:
        print(f"[skip] {circuit_id}: no energy-table target available")
        return None

    config = load_circuit_config(circuit_id, project_root=REPO_ROOT)
    runtime = _run_runtime_lap(config, map_name, push_level)
    runtime_total = round(runtime.harvest_mj + runtime.mguh_total_mj, 4)
    harvest_limit_ok = runtime.harvest_mj <= MGUK_HARVEST_LIMIT_MJ + 1e-6

    mguk_ok = (target.mguk_min_mj - ENERGY_TABLE_TOLERANCE_MJ) <= runtime.harvest_mj <= (target.mguk_max_mj + ENERGY_TABLE_TOLERANCE_MJ)
    mguh_ok = (target.mguh_min_mj - ENERGY_TABLE_TOLERANCE_MJ) <= runtime.mguh_total_mj <= (target.mguh_max_mj + ENERGY_TABLE_TOLERANCE_MJ)
    total_ok = (target.total_min_mj - ENERGY_TABLE_TOLERANCE_MJ) <= runtime_total <= (target.total_max_mj + ENERGY_TABLE_TOLERANCE_MJ)

    return EnergyValidationResult(
        circuit_id=circuit_id,
        circuit_name=meta.get("circuit_name", circuit_id),
        map_name=map_name.value,
        target_label=target.label,
        mguk_target_min_mj=target.mguk_min_mj,
        mguk_target_max_mj=target.mguk_max_mj,
        mguh_target_min_mj=target.mguh_min_mj,
        mguh_target_max_mj=target.mguh_max_mj,
        total_target_min_mj=target.total_min_mj,
        total_target_max_mj=target.total_max_mj,
        runtime_harvest_mj=round(runtime.harvest_mj, 4),
        runtime_mguh_mj=round(runtime.mguh_total_mj, 4),
        runtime_total_mj=runtime_total,
        lap_time_s=round(runtime.lap_time_s, 4),
        deploy_mj=round(runtime.deploy_mj, 4),
        mguk_ok=mguk_ok,
        mguh_ok=mguh_ok,
        total_ok=total_ok,
        harvest_limit_ok=harvest_limit_ok,
    )


def _print_energy_validation_results(results: List[EnergyValidationResult], push_level: int) -> None:
    if not results:
        print("No energy table validation results.")
        return

    print("\nEnergy table validation results:")
    for result in results:
        status = "OK" if (result.mguk_ok and result.mguh_ok and result.total_ok and result.harvest_limit_ok) else "CHECK"
        print(
            f"  - [{status}] {result.circuit_id} ({result.circuit_name}) | {result.map_name} | push {push_level} | "
            f"K {result.runtime_harvest_mj:.3f} MJ / target {result.mguk_target_min_mj:.2f}-{result.mguk_target_max_mj:.2f} MJ | "
            f"H {result.runtime_mguh_mj:.3f} MJ / target {result.mguh_target_min_mj:.2f}-{result.mguh_target_max_mj:.2f} MJ | "
            f"total {result.runtime_total_mj:.3f} MJ / target {result.total_target_min_mj:.2f}-{result.total_target_max_mj:.2f} MJ | "
            f"harvest_limit={'OK' if result.harvest_limit_ok else 'HIT'}"
        )

    failures = [r for r in results if not (r.mguk_ok and r.mguh_ok and r.total_ok and r.harvest_limit_ok)]
    if failures:
        print(f"Summary: {len(results) - len(failures)}/{len(results)} circuits fully within target ranges.")
    else:
        print(f"Summary: all {len(results)} circuits are within target ranges.")


def _distance_to_range(value: float, target_min: float, target_max: float) -> float:
    if value < target_min:
        return target_min - value
    if value > target_max:
        return value - target_max
    return 0.0


def _apply_mguh_profile(
    data: Dict[str, Any],
    map_name: EngineMapName,
    total_mj: float,
    power_kw: float,
    direct_ratio: float = MGUH_DIRECT_RATIO_BASELINE,
) -> None:
    meta = data.setdefault("_meta", {})
    profile = meta.setdefault("mguh_profile", {})
    direct_mj = round(total_mj * direct_ratio, 3)
    es_mj = round(max(total_mj - direct_mj, 0.0), 3)

    profile["total_mj"] = round(total_mj, 3)
    profile["direct_mj"] = direct_mj
    profile["es_mj"] = es_mj
    profile["direct_bias"] = round(direct_ratio, 3)
    profile["es_bias"] = round(1.0 - direct_ratio, 3)

    maps = data.setdefault("maps", {})
    map_entry = maps.setdefault(map_name.value, {})
    map_entry["mguh_power_kw"] = round(power_kw, 3)
    map_entry["mguh_direct_ratio"] = round(direct_ratio, 3)

    ers_budget = data.setdefault("ers_budget", {})
    budget_maps = ers_budget.setdefault("maps", {})
    if map_name.value in budget_maps:
        budget_maps[map_name.value]["mguh_direct_ratio"] = round(direct_ratio, 3)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def tune_file(
    path: Path,
    map_name: EngineMapName,
    doc_targets: Dict[str, MguhTarget],
    max_iterations: int,
    push_level: int,
    dry_run: bool = False,
    mirror_calibration: bool = False,
) -> Optional[MguhFitResult]:
    data = json.loads(path.read_text())
    meta = data.get("_meta") if isinstance(data.get("_meta"), dict) else {}
    circuit_id = meta.get("circuit_id") or path.parent.name
    target = _resolve_target_for_circuit(circuit_id, doc_targets)
    if target is None:
        print(f"[skip] {circuit_id}: no doc target available")
        return None

    config = load_circuit_config(circuit_id, project_root=REPO_ROOT)
    profile = meta.setdefault("mguh_profile", {})
    start_total_mj = float(profile.get("total_mj") or 0.0)
    if start_total_mj <= 0.0:
        map_params = config.pu_maps.get(map_name)
        start_total_mj = round((getattr(map_params, "mguh_power_kw", 0.0) or 0.0) * (config.reference_lap_time_s or 90.0) / 1000.0, 3)
    if start_total_mj <= 0.0:
        start_total_mj = round((target.min_mj + target.max_mj) / 2.0, 3)

    best_total_mj = start_total_mj
    best_sim_mj = float("inf")
    best_power_kw = 0.0
    best_distance = float("inf")
    converged = False
    iterations = 0
    current_total_mj = start_total_mj

    def _consider(candidate_total_mj: float) -> float:
        nonlocal best_total_mj, best_sim_mj, best_power_kw, best_distance, iterations
        sim_total, _result, power_kw = _evaluate_candidate(config, map_name, candidate_total_mj, push_level)
        distance = _distance_to_range(sim_total, target.min_mj, target.max_mj)
        iterations += 1
        if distance < best_distance:
            best_distance = distance
            best_total_mj = candidate_total_mj
            best_sim_mj = sim_total
            best_power_kw = power_kw
        return sim_total

    current_sim_mj = _consider(current_total_mj)
    if target.min_mj <= current_sim_mj <= target.max_mj:
        converged = True
    else:
        low_total = current_total_mj
        high_total = current_total_mj
        low_sim = current_sim_mj
        high_sim = current_sim_mj

        if current_sim_mj > target.max_mj:
            high_total = current_total_mj
            high_sim = current_sim_mj
            low_total = max(current_total_mj * 0.75, 0.2)
            for _ in range(8):
                low_sim = _consider(low_total)
                if low_sim <= target.max_mj:
                    break
                high_total = low_total
                high_sim = low_sim
                low_total = max(low_total * 0.75, 0.2)
        else:
            low_total = current_total_mj
            low_sim = current_sim_mj
            high_total = max(current_total_mj * 1.25, current_total_mj + 0.25)
            for _ in range(8):
                high_sim = _consider(high_total)
                if high_sim >= target.min_mj:
                    break
                low_total = high_total
                low_sim = high_sim
                high_total = min(high_total * 1.25, 20.0)

        for _ in range(max_iterations):
            if low_total > high_total:
                low_total, high_total = high_total, low_total
                low_sim, high_sim = high_sim, low_sim
            mid_total = round((low_total + high_total) / 2.0, 4)
            mid_sim = _consider(mid_total)
            if target.min_mj <= mid_sim <= target.max_mj:
                best_total_mj = mid_total
                best_sim_mj = mid_sim
                best_power_kw = _estimate_mguh_power_kw(mid_total, config.reference_lap_time_s or 90.0)
                converged = True
                break
            if mid_sim > target.max_mj:
                high_total = mid_total
                high_sim = mid_sim
            else:
                low_total = mid_total
                low_sim = mid_sim

    if best_sim_mj == float("inf"):
        best_sim_mj = current_sim_mj
        best_power_kw = _estimate_mguh_power_kw(best_total_mj, config.reference_lap_time_s or 90.0)

    if not dry_run:
        _apply_mguh_profile(data, map_name, best_total_mj, best_power_kw)
        _write_json(path, data)
        if mirror_calibration:
            calibration_path = CALIBRATION_DIR / f"{circuit_id}.json"
            if calibration_path.exists():
                calibration_data = json.loads(calibration_path.read_text())
                _apply_mguh_profile(calibration_data, map_name, best_total_mj, best_power_kw)
                _write_json(calibration_path, calibration_data)

    return MguhFitResult(
        circuit_id=circuit_id,
        circuit_name=meta.get("circuit_name", circuit_id),
        map_name=map_name.value,
        target_label=target.label,
        target_min_mj=target.min_mj,
        target_max_mj=target.max_mj,
        start_total_mj=start_total_mj,
        start_sim_mj=current_sim_mj,
        best_total_mj=best_total_mj,
        best_sim_mj=best_sim_mj,
        best_power_kw=best_power_kw,
        iterations=iterations,
        converged=converged,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill ERS mode budgets for circuit PU maps")
    parser.add_argument(
        "--circuit",
        help="Circuit ID (folder name under config/circuits/derived) to process in MGU-H fit mode",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--fit-mguh",
        action="store_true",
        help="Iteratively tune mguh_profile.total_mj against docs/Ers-Deploy-Sim.md",
    )
    mode_group.add_argument(
        "--validate-energy-table",
        action="store_true",
        help="Validate MGU-K harvest and MGU-H totals against docs/PU-Engine-MGU-H.md",
    )
    parser.add_argument(
        "--map-name",
        default="RACE",
        help="Engine map to tune in fit mode (default: RACE)",
    )
    parser.add_argument(
        "--target-doc",
        type=Path,
        default=TARGET_DOC_PATH,
        help="Reference doc containing the MGU-H target table",
    )
    parser.add_argument(
        "--energy-doc",
        type=Path,
        default=ENERGY_DOC_PATH,
        help="Reference doc containing the MGU-K / MGU-H energy table",
    )
    parser.add_argument(
        "--energy-circuits",
        default="jp-1962_suzuka,mc-1929_monaco,it-1922_monza",
        help="Comma-separated circuit IDs to validate against the energy table",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=12,
        help="Maximum binary-search iterations per circuit when fitting",
    )
    parser.add_argument(
        "--push-level",
        type=int,
        default=RUNTIME_DEFAULT_PUSH_LEVEL,
        help="Runtime push level baseline for the update_section harness (default: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write JSON files; only report the fitted values",
    )
    parser.add_argument(
        "--mirror-calibration",
        action="store_true",
        help="Also write the fitted MGU-H values to config/calibration/pu/<cid>.json",
    )
    args = parser.parse_args()

    try:
        map_enum = _resolve_engine_map_name(args.map_name)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if args.validate_energy_table:
        doc_targets = load_energy_table_targets(args.energy_doc)
        circuit_ids = [c.strip() for c in args.energy_circuits.split(",") if c.strip()]
        results: List[EnergyValidationResult] = []
        for circuit_id in circuit_ids:
            candidate = DERIVED_DIR / circuit_id / "pu_maps.json"
            if not candidate.exists():
                print(f"[skip] {circuit_id}: no pu_maps.json found")
                continue
            result = _validate_energy_table_entry(candidate, map_enum, doc_targets, args.push_level)
            if result is not None:
                results.append(result)
        _print_energy_validation_results(results, args.push_level)
        return

    try:
        template_maps = load_ers_budget_template()
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    if args.circuit:
        candidate = DERIVED_DIR / args.circuit / "pu_maps.json"
        paths = [candidate] if candidate.exists() else []
        if not paths:
            print(f"No pu_maps.json found for circuit '{args.circuit}'")
            return
    else:
        paths = sorted(DERIVED_DIR.glob("*/pu_maps.json"))

    updated_files = []
    fitted_results: List[MguhFitResult] = []
    doc_targets = load_doc_targets(args.target_doc) if args.fit_mguh else {}
    for pu_map in paths:
        if process_file(pu_map, template_maps, dry_run=args.dry_run):
            updated_files.append(str(pu_map.relative_to(REPO_ROOT)))
        if args.fit_mguh:
            fitted = tune_file(
                pu_map,
                map_name=map_enum,
                doc_targets=doc_targets,
                max_iterations=args.max_iterations,
                push_level=args.push_level,
                dry_run=args.dry_run,
                mirror_calibration=args.mirror_calibration,
            )
            if fitted is not None:
                fitted_results.append(fitted)

    if updated_files:
        header = "Would update ERS modes in:" if args.dry_run else "Updated ERS modes in:"
        print(header)
        for rel in updated_files:
            print(f"  - {rel}")
    else:
        print("No ERS budget changes necessary.")

    if fitted_results:
        print("\nMGU-H tuning results:")
        for result in fitted_results:
            status = "OK" if result.converged else "BEST"
            print(
                f"  - [{status}] {result.circuit_id} ({result.circuit_name}) | {result.map_name} | "
                f"push {args.push_level} | "
                f"target {result.target_min_mj:.2f}-{result.target_max_mj:.2f} MJ | "
                f"start {result.start_sim_mj:.3f} MJ | best {result.best_sim_mj:.3f} MJ | "
                f"total_mj {result.best_total_mj:.3f} | mguh_power_kw {result.best_power_kw:.3f} | "
                f"iters {result.iterations}"
            )


if __name__ == "__main__":
    main()
