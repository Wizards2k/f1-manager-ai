"""
ConfigLoader – loads circuit and global JSON configs into CircuitConfig.

Reads:
  - Telemetry JSON  (python_backend/data/circuits/<id>_Telemetry.json)
  - Derived profiles (config/circuits/derived/<id>/*.json)
  - Global defaults  (config/tyres|brakes|pu|damage/*_global_default.json)

Reference: docs/config-spec.md
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .data_types import (
    BrakeSystemParams,
    CircuitConfig,
    CurveProfile,
    DamageCoeffs,
    EngineMapName,
    EngineMapParams,
    PUReliabilityParams,
    SECTION_HEAT_COOL,
    SectionContext,
    SectionKind,
    TyreCompound,
    TyreCompoundParams,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _project_root() -> Path:
    """Return the project root (F1 Manager AI/)."""
    return Path(__file__).resolve().parent.parent.parent


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        logger.warning("Config file not found: %s", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

_KIND_MAP = {
    "Straight":         SectionKind.STRAIGHT,
    "MediumStraight":   SectionKind.MEDIUM_STRAIGHT,
    "VerySlowCorner":   SectionKind.VERY_SLOW_CORNER,
    "SlowCorner":       SectionKind.SLOW_CORNER,
    "MediumCorner":     SectionKind.MEDIUM_CORNER,
    "FastCorner":       SectionKind.FAST_CORNER,
    "UltraFastCorner":  SectionKind.ULTRA_FAST_CORNER,
}


def _parse_section(raw: Dict[str, Any]) -> SectionContext:
    kind = _KIND_MAP.get(raw.get("kind", "Straight"), SectionKind.STRAIGHT)
    start = raw.get("start_m", 0)
    end = raw.get("end_m", 0)
    length = max(end - start, 1.0)

    heat_f, cool_f = SECTION_HEAT_COOL.get(kind, (1.0, 1.0))

    radius = raw.get("radius_m")
    curvature_factor = 0.0
    if radius and radius > 0:
        curvature_factor = 1.0 / radius * 100  # normalised

    v_entry = raw.get("v_entry_kph", raw.get("v_entry", 0.0))
    v_exit = raw.get("v_exit_kph", raw.get("v_exit", 0.0))
    v_min = raw.get("v_min_kph", raw.get("v_min", 0.0))
    v_max = raw.get("v_max_kph", raw.get("v_max", 0.0))
    avg_speed = raw.get("avg_speed_kph", raw.get("avg_speed", 200))
    braking_energy = raw.get("braking_energy_mj", raw.get("braking_energy", 0.0))
    bumpiness = raw.get("bumpiness_factor", raw.get("bumpiness", 0.0)) or 0.0
    kerb = raw.get("kerb_severity", raw.get("kerb", 0.0)) or 0.0
    dt_ref = raw.get("dt_ref_s", 0.0)
    if dt_ref <= 0:
        # fallback: approximate from length / avg_speed
        avg_ms = max(avg_speed / 3.6, 1.0)
        dt_ref = length / avg_ms

    return SectionContext(
        section_id=raw.get("id", ""),
        name=raw.get("name", ""),
        kind=kind,
        length_m=length,
        v_base_kph=avg_speed,
        v_entry_kph=v_entry,
        v_exit_kph=v_exit,
        v_min_kph=v_min,
        v_max_kph=v_max,
        corner_number=int(raw.get("corner_number", 0) or 0),
        curve_profile=CurveProfile(
            radius_m=radius,
            curvature_factor=curvature_factor,
        ),
        bumpiness_factor=bumpiness,
        kerb_severity=kerb,
        heat_factor=raw.get("heat_factor", heat_f),
        cool_factor=raw.get("cool_factor", cool_f),
        braking_energy_mj=braking_energy,
        drs_available=raw.get("drs_active", raw.get("drs_available", False)),
        dt_ref_s=dt_ref,
    )


# ---------------------------------------------------------------------------
# Compound loader
# ---------------------------------------------------------------------------

_COMPOUND_MAP = {
    "C1": TyreCompound.C1,
    "C2": TyreCompound.C2,
    "C3": TyreCompound.C3,
    "C4": TyreCompound.C4,
    "C5": TyreCompound.C5,
    "C6": TyreCompound.C6,
    "INTERMEDIATE": TyreCompound.INTERMEDIATE,
    "WET": TyreCompound.WET,
}


def _parse_tyre_params(data: Dict[str, Any]) -> Dict[TyreCompound, TyreCompoundParams]:
    compounds_raw = data.get("compounds", {})
    result: Dict[TyreCompound, TyreCompoundParams] = {}
    for key, vals in compounds_raw.items():
        tc = _COMPOUND_MAP.get(key)
        if tc is None:
            continue
        result[tc] = TyreCompoundParams(
            compound=tc,
            temp_window_surface_c=vals.get("temp_window_surface_c", [88, 120, 135]),
            temp_window_core_c=vals.get("temp_window_core_c", [85, 97, 108]),
            gaussian_sigma_surface_c=vals.get("gaussian_sigma_surface_c", 7.0),
            gaussian_sigma_core_c=vals.get("gaussian_sigma_core_c", 6.0),
            base_grip=vals.get("base_grip", 1.0),
            wear_rate_base_pct_per_km=vals.get("wear_rate_base_pct_per_km", 0.13),
            degradation_rate_multiplier=vals.get("degradation_rate_multiplier", 1.0),
            slip_sensitivity=vals.get("slip_sensitivity", 1.0),
            thermal_mass_surface=vals.get("thermal_mass_surface", 1.10),
            thermal_mass_core=vals.get("thermal_mass_core", 1.25),
            conduction_coeff=vals.get("conduction_coeff", 0.07),
            cooling_coeff=vals.get("cooling_coeff", 1.0),
        )
    return result


# ---------------------------------------------------------------------------
# Brake loader
# ---------------------------------------------------------------------------

def _parse_brake_params(
    data: Dict[str, Any],
    system: str = "base",
    regen_factor: Optional[float] = None,
) -> BrakeSystemParams:
    systems = data.get("systems", {})
    s = systems.get(system, systems.get("base", {}))
    hc = s.get("heat_capacity", {})
    tm = s.get("thermal_mass", {})
    ft = s.get("fade_threshold_c", {})
    return BrakeSystemParams(
        heat_capacity_front=hc.get("front", 1.10),
        heat_capacity_rear=hc.get("rear", 1.00),
        thermal_mass_front=tm.get("front", 1.20),
        thermal_mass_rear=tm.get("rear", 1.05),
        fade_threshold_front_c=ft.get("front", 850.0),
        fade_threshold_rear_c=ft.get("rear", 750.0),
        fade_sensitivity_c_per_unit=s.get("fade_sensitivity_c_per_unit", 15.0),
        cooling_coeff=s.get("cooling_coeff", 1.0),
        heat_quality=s.get("heat_quality", 1.0),
        regen_brake_factor=regen_factor if regen_factor is not None else s.get("regen_brake_factor", 1.0),
    )


# ---------------------------------------------------------------------------
# PU loader
# ---------------------------------------------------------------------------

_MAP_NAME = {
    "ECONOMY":  EngineMapName.ECONOMY,
    "STANDARD": EngineMapName.STANDARD,
    "RICH":     EngineMapName.RICH,
    "QUALY":    EngineMapName.QUALY,
    "WET":      EngineMapName.WET,
    "RECHARGE": EngineMapName.RECHARGE,
}


def _parse_pu_maps(data: Dict[str, Any]) -> Dict[EngineMapName, EngineMapParams]:
    maps_raw = data.get("maps", {})
    result: Dict[EngineMapName, EngineMapParams] = {}
    for key, vals in maps_raw.items():
        mn = _MAP_NAME.get(key)
        if mn is None:
            continue
        result[mn] = EngineMapParams(
            name=mn,
            heat_load_kw=vals.get("heat_load_kw", 260),
            torque_ramp=vals.get("torque_ramp", 0.6),
            deployment_style=vals.get("deployment_style", "balanced"),
            cooling_share=vals.get("cooling_share", 0.50),
            ers_output_kw=vals.get("ers_output_kw", 120),
            mguh_direct_ratio=vals.get("mguh_direct_ratio", 0.0),
            mguh_power_kw=vals.get("mguh_power_kw", vals.get("ers_output_kw", 120) * 0.65),
            bucket_primary_pct=vals.get("bucket_primary_pct", 0.5),
            bucket_secondary_pct=vals.get("bucket_secondary_pct", 0.35),
            bucket_exit_pct=vals.get("bucket_exit_pct", 0.15),
            defense_reserve_mj=vals.get("defense_reserve_mj", 0.2),
        )
    return result


def _parse_pu_reliability(data: Dict[str, Any]) -> PUReliabilityParams:
    ice = data.get("ice", {})
    ers = data.get("ers", {})
    return PUReliabilityParams(
        ice_wear_coeff=ice.get("wear_coeff", 0.0008),
        ice_temp_warning_c=ice.get("temp_warning_c", 130),
        ice_temp_critical_c=ice.get("temp_critical_c", 140),
        ice_overrev_factor=ice.get("overrev_factor", 1.15),
        ice_shock_factor=ice.get("shock_factor", 1.10),
        ers_wear_coeff=ers.get("wear_coeff", 0.0012),
        ers_temp_warning_c=ers.get("temp_warning_c", 90),
        ers_temp_critical_c=ers.get("temp_critical_c", 100),
        ers_overrev_factor=ers.get("overrev_factor", 1.10),
        ers_shock_factor=ers.get("shock_factor", 1.05),
    )


# ---------------------------------------------------------------------------
# Damage loader
# ---------------------------------------------------------------------------

def _parse_damage_coeffs(data: Dict[str, Any]) -> DamageCoeffs:
    comps = data.get("components", {})
    defs = data.get("defaults", {})
    sus = comps.get("suspension", {})
    flr = comps.get("floor_beam", {})
    gbx = comps.get("gearbox", {})
    steer = comps.get("steering", {})
    return DamageCoeffs(
        susp_shock_threshold=sus.get("shock_threshold", 1.0),
        susp_grip_drop_per_hit=sus.get("grip_mech_drop_per_hit", 0.01),
        susp_steering_loss_per_hit=sus.get("steering_precision_loss_per_hit", 0.01),
        susp_failure_risk_per_hit=sus.get("failure_risk_per_hit", 0.002),
        floor_shock_threshold=flr.get("shock_threshold", 1.1),
        floor_drag_increase_per_hit=flr.get("drag_increase_per_hit", 0.005),
        floor_df_loss_per_hit=flr.get("downforce_loss_per_hit", 0.006),
        floor_failure_risk_per_hit=flr.get("failure_risk_per_hit", 0.0015),
        gearbox_shock_threshold=gbx.get("shock_threshold", 0.95),
        gearbox_shift_delay_per_hit=gbx.get("shift_delay_per_hit", 0.004),
        gearbox_failure_risk_per_hit=gbx.get("failure_risk_per_hit", 0.003),
        steering_shock_threshold=steer.get("shock_threshold", 1.0),
        steering_precision_loss_per_hit=steer.get("steering_precision_loss_per_hit", 0.012),
        steering_handling_penalty_per_hit=steer.get("handling_penalty_per_hit", 0.01),
        steering_failure_risk_per_hit=steer.get("failure_risk_per_hit", 0.001),
        shock_scaler_bumpiness=defs.get("shock_scaler_bumpiness", 0.1),
        shock_scaler_kerb_severity=defs.get("shock_scaler_kerb_severity", 0.15),
        recovery_rate_per_lap=defs.get("recovery_rate_per_lap", 0.001),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_circuit_config(
    circuit_id: str,
    brake_system: str = "base",
    project_root: Optional[Path] = None,
) -> CircuitConfig:
    """
    Load a complete CircuitConfig for the given circuit.

    Tries derived profiles first; falls back to global defaults.
    """
    root = project_root or _project_root()
    derived_dir = root / "config" / "circuits" / "derived" / circuit_id
    global_tyres = root / "config" / "tyres" / "tyre_params_global_default.json"
    global_brakes = root / "config" / "brakes" / "brake_params_global_default.json"
    global_pu_maps = root / "config" / "pu" / "pu_maps_global_default.json"
    global_pu_rel = root / "config" / "pu" / "pu_reliability_global_default.json"
    global_damage = root / "config" / "damage" / "damage_coeffs_global_default.json"
    telemetry_path = root / "python_backend" / "data" / "circuits" / "2025" / f"{circuit_id}_Telemetry.json"

    # --- Telemetry (sections) ---
    telem = _load_json(telemetry_path)
    geometry = telem.get("geometry", {})
    sections_raw = geometry.get("sections", [])
    sections = [_parse_section(s) for s in sections_raw]
    sector_markers = geometry.get("sector_markers", [])
    circuit_length = geometry.get("circuit_length", sum(s.length_m for s in sections))
    meta = telem.get("metadata", {})

    # --- Tyres ---
    tyre_path = derived_dir / "tyre_params.json" if derived_dir.exists() else global_tyres
    tyre_data = _load_json(tyre_path) if tyre_path.exists() else _load_json(global_tyres)
    tyre_params = _parse_tyre_params(tyre_data)

    # --- Brakes ---
    brake_path = derived_dir / "brake_params.json" if derived_dir.exists() else global_brakes
    brake_data = _load_json(brake_path) if brake_path.exists() else _load_json(global_brakes)
    brake_calibration = brake_data.pop("_calibration", None)
    brake_profile = {}
    brake_sections = []
    regen_factor = None
    if brake_calibration:
        brake_profile = brake_calibration.get("brake_profile", {})
        brake_sections = brake_calibration.get("critical_sections", [])
        regen_factor = brake_profile.get("regen_brake_base")
    brake_params = _parse_brake_params(brake_data, system=brake_system, regen_factor=regen_factor)

    # --- PU ---
    pu_map_path = derived_dir / "pu_maps.json" if derived_dir.exists() else global_pu_maps
    pu_map_data = _load_json(pu_map_path) if pu_map_path.exists() else _load_json(global_pu_maps)
    pu_maps = _parse_pu_maps(pu_map_data)

    ers_budget = pu_map_data.get("ers_budget", {})
    regen_profile = pu_map_data.get("regen_profile", {})
    soc_warnings = pu_map_data.get("soc_warnings", [])

    pu_rel_data = _load_json(global_pu_rel)
    pu_reliability = _parse_pu_reliability(pu_rel_data)

    # --- Damage ---
    dmg_path = derived_dir / "damage_coeffs.json" if derived_dir.exists() else global_damage
    dmg_data = _load_json(dmg_path) if dmg_path.exists() else _load_json(global_damage)
    damage_coeffs = _parse_damage_coeffs(dmg_data)

    ref_lap_time = telem.get("reference_lap", {}).get("lap_time", 0.0)
    sum_dt_ref = sum(s.dt_ref_s for s in sections)

    return CircuitConfig(
        circuit_id=circuit_id,
        circuit_name=meta.get("circuit_name", circuit_id),
        circuit_length_m=circuit_length,
        sections=sections,
        sector_markers_m=sector_markers,
        tyre_params=tyre_params,
        brake_params=brake_params,
        pu_maps=pu_maps,
        pu_reliability=pu_reliability,
        damage_coeffs=damage_coeffs,
        brake_profile=brake_profile,
        brake_critical_sections=brake_sections,
        ers_budget=ers_budget,
        regen_profile=regen_profile,
        soc_warnings=soc_warnings,
        reference_lap_time_s=sum_dt_ref # Force 2025 telemetry sum,
    )
