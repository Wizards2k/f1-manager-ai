#!/usr/bin/env python3
"""Helpers to load custom simulation scenarios from JSON snapshots."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "python_backend") not in sys.path:
    sys.path.append(str(REPO_ROOT / "python_backend"))

from lap_simulator.lap_simulator import CarEntry  # type: ignore  # noqa: E402
from lap_simulator.data_types import (  # type: ignore  # noqa: E402
    AeroComponent,
    AeroSetup,
    BrakeState,
    CarState,
    DriverSkills,
    EnvContext,
    EngineMapName,
    PUState,
    SuspensionState,
    TyreCompound,
    TyreState,
    WheelPosition,
)


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Scenario file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Scenario file is not valid JSON: {path}\n{exc}") from exc


def _coerce_compound(raw: Any) -> TyreCompound:
    if isinstance(raw, TyreCompound):
        return raw
    if not raw:
        return TyreCompound.C3
    key = str(raw).upper()
    try:
        return TyreCompound[key]
    except KeyError:
        # Allow shorthand like "SOFT" → map to closest dry compound
        mapping = {
            "SOFT": TyreCompound.C5,
            "MEDIUM": TyreCompound.C3,
            "HARD": TyreCompound.C1,
        }
        return mapping.get(key, TyreCompound.C3)


def _build_tyre_state(wp: WheelPosition, payload: Dict[str, Any]) -> TyreState:
    tyre = TyreState(wheel_pos=wp, compound=_coerce_compound(payload.get("compound")))
    tyre.surface_temp_c = float(payload.get("surface_temp_c", tyre.surface_temp_c))
    tyre.core_temp_c = float(payload.get("core_temp_c", tyre.core_temp_c))
    tyre.wear_pct = float(payload.get("wear_pct", tyre.wear_pct))
    tyre.age_laps = int(payload.get("lap_age", payload.get("age_laps", tyre.age_laps)))
    tyre.heat_cycles = int(payload.get("heat_cycles", tyre.heat_cycles))
    return tyre


def _populate_pu_state(pu: PUState, payload: Dict[str, Any]) -> None:
    map_raw = payload.get("active_map")
    if map_raw:
        try:
            pu.active_map = EngineMapName[str(map_raw).upper()]
        except KeyError:
            pass
    for field in (
        "fuel_kg",
        "ers_energy_mj",
        "ice_temp_c",
        "ers_temp_c",
    ):
        if field in payload:
            setattr(pu, field, float(payload[field]))


def _populate_brakes(brakes: BrakeState, payload: Dict[str, Any]) -> None:
    for field in (
        "temp_front_c",
        "temp_rear_c",
        "bias_front_pct",
        "duct_opening",
    ):
        if field in payload:
            setattr(brakes, field, float(payload[field]))


def _update_component(component: AeroComponent, payload: Dict[str, Any]) -> None:
    for field in (
        "base_downforce",
        "base_drag",
        "angle_deg",
        "angle_ref_deg",
        "angle_sensitivity",
        "drag_sensitivity",
        "cooling_contribution",
        "damage_factor",
        "drs_drag_reduction",
    ):
        if field in payload:
            setattr(component, field, float(payload[field]))


def _populate_suspension(susp: SuspensionState, payload: Dict[str, Any]) -> None:
    for field in ("rigidity", "efficiency", "df_bonus"):
        if field in payload:
            setattr(susp, field, float(payload[field]))


def _build_aero_setup(payload: Dict[str, Any]) -> AeroSetup:
    aero = AeroSetup()
    comps = {
        "front_wing": aero.front_wing,
        "rear_wing": aero.rear_wing,
        "beam_wing": aero.beam_wing,
        "front_floor": aero.front_floor,
        "rear_floor": aero.rear_floor,
        "sidepods": aero.sidepods,
        "engine_cover": aero.engine_cover,
        "b_wing": aero.b_wing,
    }
    for key, component in comps.items():
        if key in payload:
            _update_component(component, payload[key])
    if "suspension_front" in payload:
        _populate_suspension(aero.suspension_front, payload["suspension_front"])
    if "suspension_rear" in payload:
        _populate_suspension(aero.suspension_rear, payload["suspension_rear"])
    for field in (
        "antiroll_front_rigidity",
        "antiroll_rear_rigidity",
        "ride_height_front_mm",
        "ride_height_rear_mm",
        "ride_height_optimal_front_mm",
        "ride_height_optimal_rear_mm",
    ):
        if field in payload:
            setattr(aero, field, float(payload[field]))
    return aero


def _build_driver_skills(payload: Dict[str, Any]) -> DriverSkills:
    default = DriverSkills()
    for field in default.__dataclass_fields__:  # type: ignore[attr-defined]
        if field in payload:
            setattr(default, field, int(payload[field]))
    return default


def load_scenario(snapshot_path: Path) -> Tuple[EnvContext, CarEntry, Dict[str, Any]]:
    """Load scenario JSON and return EnvContext + CarEntry."""
    data = _load_json(snapshot_path)
    env_data = data.get("env", {})
    env = EnvContext(
        air_temp_c=float(env_data.get("air_temp_c", 25.0)),
        track_temp_c=float(env_data.get("track_temp_c", 35.0)),
        air_density_kg_m3=float(env_data.get("air_density_kg_m3", EnvContext.air_density_kg_m3)),
        wind_speed_kph=float(env_data.get("wind_speed_kph", 0.0)),
        wind_direction_deg=float(env_data.get("wind_direction_deg", 0.0)),
        rain_intensity=float(env_data.get("rain_intensity", 0.0)),
        track_rubber_level=float(env_data.get("track_rubber_level", 1.0)),
        water_film_level=float(env_data.get("water_film_level", 0.0)),
    )

    car_cfg = data.get("car", {})
    state_cfg = car_cfg.get("state", {})

    car_state = CarState(car_id=car_cfg.get("car_id", "SIM_SCENARIO"))
    car_state.team_code = car_cfg.get("team_code", "SIM")
    car_state.ers_mode = state_cfg.get("ers_mode", car_state.ers_mode)

    tyres_cfg = state_cfg.get("tyres", {})
    tyres: Dict[WheelPosition, TyreState] = {}
    for wp in WheelPosition:
        tyre_payload = tyres_cfg.get(wp.name, {})
        tyres[wp] = _build_tyre_state(wp, tyre_payload)
    car_state.tyres = tyres

    _populate_pu_state(car_state.pu, state_cfg.get("pu", {}))
    _populate_brakes(car_state.brakes, state_cfg.get("brakes", {}))

    aero_setup = _build_aero_setup(car_cfg.get("aero_setup", {}))
    driver_skills = _build_driver_skills(car_cfg.get("driver_skills", {}))

    entry = CarEntry(
        car_id=car_state.car_id,
        state=car_state,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        push_level=float(car_cfg.get("push_level", 5.0)),
        delta_aero=float(car_cfg.get("delta_aero", 0.0)),
        delta_grip=float(car_cfg.get("delta_grip", 0.0)),
        apply_baseline_delta=bool(car_cfg.get("apply_baseline_delta", True)),
        setup_sliders=car_cfg.get("setup_sliders", {}),
        ideal_setup_sliders=car_cfg.get("ideal_setup_sliders", {}),
    )

    return env, entry, data.get("meta", {})


__all__ = ["load_scenario"]
