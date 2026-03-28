"""Registry ufficiale delle Power Unit 2025.

Le istanze qui definite sono la controparte "promossa" dei dati sandbox
(`tmp_data/power_units_2025.py`). Ogni Team otterrà una `PowerUnit` con i
componenti fisici (ICE, MGUs, Battery) e le mappe ICE/ERS predefinite.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Dict, Optional

from lap_simulator.data_types import EngineMapName, EngineMapParams, PUReliabilityParams
from models.power_unit_models import (
    Battery,
    ERSMap,
    ICE,
    ICEMap,
    MGUK,
    MGUH,
    PowerUnit,
)

# ---------------------------------------------------------------------------
# Parametri base per fornitore – rappresentano il profilo "medio"
# della PU prima di applicare i fattori specifici del team.
# ---------------------------------------------------------------------------

_SUPPLIER_SPECS = {
    "honda": {
        "nome": "Honda RBPT HRC",
        "ice_cv": 1015.0,
        "mguk_kw": 162.0,
        "mguh_kw": 92.0,
        "battery_capacity": 4.05,
        "max_charge_kw": 180.0,
        "max_discharge_kw": 165.0,
        "base_burn": 0.0345,
        "reliability": PUReliabilityParams(
            ice_wear_coeff=0.00078,
            ice_temp_warning_c=128.0,
            ice_temp_critical_c=140.0,
            ice_overrev_factor=1.12,
            ice_shock_factor=1.08,
            ers_wear_coeff=0.00115,
            ers_temp_warning_c=88.0,
            ers_temp_critical_c=98.0,
            ers_overrev_factor=1.08,
            ers_shock_factor=1.04,
        ),
    },
    "mercedes": {
        "nome": "Mercedes-AMG HPP",
        "ice_cv": 1008.0,
        "mguk_kw": 160.0,
        "mguh_kw": 90.0,
        "battery_capacity": 4.0,
        "max_charge_kw": 175.0,
        "max_discharge_kw": 162.0,
        "base_burn": 0.034,
        "reliability": PUReliabilityParams(
            ice_wear_coeff=0.00075,
            ice_temp_warning_c=130.0,
            ice_temp_critical_c=142.0,
            ice_overrev_factor=1.10,
            ice_shock_factor=1.06,
            ers_wear_coeff=0.00110,
            ers_temp_warning_c=89.0,
            ers_temp_critical_c=100.0,
            ers_overrev_factor=1.07,
            ers_shock_factor=1.04,
        ),
    },
    "ferrari": {
        "nome": "Ferrari 066/11",
        "ice_cv": 1002.0,
        "mguk_kw": 159.0,
        "mguh_kw": 88.0,
        "battery_capacity": 4.0,
        "max_charge_kw": 172.0,
        "max_discharge_kw": 160.0,
        "base_burn": 0.0348,
        "reliability": PUReliabilityParams(
            ice_wear_coeff=0.00082,
            ice_temp_warning_c=127.0,
            ice_temp_critical_c=138.0,
            ice_overrev_factor=1.13,
            ice_shock_factor=1.08,
            ers_wear_coeff=0.00120,
            ers_temp_warning_c=87.0,
            ers_temp_critical_c=97.0,
            ers_overrev_factor=1.09,
            ers_shock_factor=1.05,
        ),
    },
    "renault": {
        "nome": "Renault E-Tech RE25",
        "ice_cv": 995.0,
        "mguk_kw": 158.0,
        "mguh_kw": 86.0,
        "battery_capacity": 3.95,
        "max_charge_kw": 168.0,
        "max_discharge_kw": 158.0,
        "base_burn": 0.0355,
        "reliability": PUReliabilityParams(
            ice_wear_coeff=0.0009,
            ice_temp_warning_c=125.0,
            ice_temp_critical_c=136.0,
            ice_overrev_factor=1.14,
            ice_shock_factor=1.08,
            ers_wear_coeff=0.00125,
            ers_temp_warning_c=86.0,
            ers_temp_critical_c=96.0,
            ers_overrev_factor=1.10,
            ers_shock_factor=1.05,
        ),
    },
}

# ---------------------------------------------------------------------------
# Fattori per team (derivati dalla distribuzione gap 25% sulle PU)
# ---------------------------------------------------------------------------

_TEAM_POWER_FACTORS = {
    "RBR": {"supplier": "honda", "ice": 1.020, "ers": 1.015},
    "RB": {"supplier": "honda", "ice": 0.990, "ers": 0.985},
    "MCL": {"supplier": "mercedes", "ice": 1.000, "ers": 1.000},
    "MER": {"supplier": "mercedes", "ice": 1.010, "ers": 1.005},
    "AST": {"supplier": "mercedes", "ice": 0.988, "ers": 0.985},
    "WIL": {"supplier": "mercedes", "ice": 0.980, "ers": 0.978},
    "FER": {"supplier": "ferrari", "ice": 1.005, "ers": 1.002},
    "SAU": {"supplier": "ferrari", "ice": 0.980, "ers": 0.978},
    "HAAS": {"supplier": "ferrari", "ice": 0.975, "ers": 0.976},
    "ALP": {"supplier": "renault", "ice": 0.965, "ers": 0.970},
}

# ---------------------------------------------------------------------------
# Helper per mappe ICE/ERS e componenti fisici
# ---------------------------------------------------------------------------

_ICE_MAP_TEMPLATE = {
    EngineMapName.SAFETY_CAR: {"min": 0.40, "max": 0.40, "base": 0.40},
    EngineMapName.PRACTICE: {"min": 0.75, "max": 0.85, "base": 0.80},
    EngineMapName.RACE: {"min": 0.90, "max": 1.00, "base": 0.95},
    EngineMapName.QUALIFY: {"min": 1.08, "max": 1.12, "base": 1.10},
}

_ERS_MAP_TEMPLATE = {
    EngineMapName.SAFETY_CAR: {"deploy_mj": 0.6, "harvest_mj": 2.2, "bucket_primary": 34, "bucket_secondary": 36, "bucket_exit": 30},
    EngineMapName.PRACTICE: {"deploy_mj": 2.6, "harvest_mj": 1.8, "bucket_primary": 40, "bucket_secondary": 35, "bucket_exit": 25},
    EngineMapName.RACE: {"deploy_mj": 3.4, "harvest_mj": 1.3, "bucket_primary": 45, "bucket_secondary": 35, "bucket_exit": 20},
    EngineMapName.QUALIFY: {"deploy_mj": 4.0, "harvest_mj": 0.8, "bucket_primary": 55, "bucket_secondary": 30, "bucket_exit": 15},
}

_DEFENSE_RESERVE_MJ = {
    EngineMapName.SAFETY_CAR: 0.60,
    EngineMapName.PRACTICE: 0.40,
    EngineMapName.RACE: 0.45,
    EngineMapName.QUALIFY: 0.00,
}

_REGEN_PROFILE = {
    "potential_mj_per_lap": 2.2,
    "regen_limit_per_section": 0.45,
    "base_factor": 0.32,
}


def _build_ice(pu_id: str, supplier: str, ice_factor: float) -> ICE:
    spec = _SUPPLIER_SPECS[supplier]
    return ICE(
        ice_id=f"{pu_id}_ice",
        nome=f"{spec['nome']} ICE",
        potenza_tot_cv=spec["ice_cv"] * ice_factor,
        reliability=spec["reliability"],
        capacita_termica_kj_per_c=14.0,
    )


def _build_mguk(pu_id: str, supplier: str, ers_factor: float) -> MGUK:
    spec = _SUPPLIER_SPECS[supplier]
    return MGUK(
        mgu_k_id=f"{pu_id}_mguk",
        nome=f"{spec['nome']} MGU-K",
        max_kw=spec["mguk_kw"] * ers_factor,
        efficiency=0.97,
        capacita_termica_kj_per_c=6.0,
    )


def _build_mguh(pu_id: str, supplier: str, ers_factor: float) -> MGUH:
    spec = _SUPPLIER_SPECS[supplier]
    return MGUH(
        mgu_h_id=f"{pu_id}_mguh",
        nome=f"{spec['nome']} MGU-H",
        base_kw=spec["mguh_kw"] * ers_factor,
        direct_ratio_default=0.34,
        efficiency=0.95,
        capacita_termica_kj_per_c=5.0,
    )


def _build_battery(pu_id: str, supplier: str) -> Battery:
    spec = _SUPPLIER_SPECS[supplier]
    return Battery(
        battery_id=f"{pu_id}_battery",
        nome=f"{spec['nome']} Battery",
        capacity_mj=spec["battery_capacity"],
        max_charge_kw=spec["max_charge_kw"],
        max_discharge_kw=spec["max_discharge_kw"],
        capacita_termica_kj_per_c=8.0,
    )


def _build_ice_maps(pu_id: str, ice_factor: float) -> Dict[EngineMapName, ICEMap]:
    maps: Dict[EngineMapName, ICEMap] = {}
    for map_name, cfg in _ICE_MAP_TEMPLATE.items():
        maps[map_name] = ICEMap(
            ice_map_id=f"{pu_id}_{map_name.value.lower()}_ice",
            nome=f"{map_name.value.title()} ICE",
            power_pct=cfg["base"] * ice_factor,
        )
    return maps


def _build_ers_maps(pu_id: str, ers_factor: float) -> Dict[EngineMapName, ERSMap]:
    maps: Dict[EngineMapName, ERSMap] = {}
    for map_name, cfg in _ERS_MAP_TEMPLATE.items():
        deploy_budget = cfg["deploy_mj"] * ers_factor
        maps[map_name] = ERSMap(
            ers_map_id=f"{pu_id}_{map_name.value.lower()}_ers",
            nome=f"{map_name.value.title()} ERS",
            deploy_budget_mj=deploy_budget,
            bucket_primary_pct=cfg["bucket_primary"],
            bucket_secondary_pct=cfg["bucket_secondary"],
            bucket_exit_pct=cfg["bucket_exit"],
            defense_reserve_mj=_DEFENSE_RESERVE_MJ.get(map_name, 0.0),
            mguh_direct_ratio=0.45,
        )
    return maps


def _build_reliability(base: PUReliabilityParams, ice_factor: float) -> PUReliabilityParams:
    # Leggero scaling: più potenza → coeff usura maggiore
    wear_scale = 1.0 + (ice_factor - 1.0) * 0.35
    return replace(
        base,
        ice_wear_coeff=base.ice_wear_coeff * wear_scale,
        ers_wear_coeff=base.ers_wear_coeff * wear_scale,
    )


# ---------------------------------------------------------------------------
# Costruzione roster ufficiale
# ---------------------------------------------------------------------------

POWER_UNITS: Dict[str, PowerUnit] = {}

for team_code, cfg in _TEAM_POWER_FACTORS.items():
    supplier = cfg["supplier"]
    spec = _SUPPLIER_SPECS[supplier]
    pu_id = f"PU_{team_code}"
    ice_factor = cfg["ice"]
    ers_factor = cfg["ers"]

    POWER_UNITS[pu_id] = PowerUnit(
        pu_id=pu_id,
        nome=f"{spec['nome']} {team_code}",
        fornitore=supplier.title(),
        anno=2025,
        spec_version="v1.0",
        ice=_build_ice(pu_id, supplier, ice_factor),
        mgu_k=_build_mguk(pu_id, supplier, ers_factor),
        mgu_h=_build_mguh(pu_id, supplier, ers_factor),
        battery=_build_battery(pu_id, supplier),
        ice_maps=_build_ice_maps(pu_id, ice_factor),
        ers_maps=_build_ers_maps(pu_id, ers_factor),
        reliability=_build_reliability(spec["reliability"], ice_factor),
        fuel_capacity_kg=110.0,
        base_burn_kg_per_s=spec["base_burn"],
        regen_profile=_REGEN_PROFILE,
    )


TEAM_POWER_UNIT_ID: Dict[str, str] = {team: f"PU_{team}" for team in _TEAM_POWER_FACTORS.keys()}


def get_power_unit(team_code: str) -> Optional[PowerUnit]:
    """Restituisce la Power Unit assegnata alla scuderia (sigla FIA)."""
    pu_id = TEAM_POWER_UNIT_ID.get(team_code.upper())
    if not pu_id:
        return None
    return POWER_UNITS[pu_id]


def list_power_units() -> Dict[str, PowerUnit]:
    """Copia del roster completo (key = pu_id)."""
    return POWER_UNITS.copy()


__all__ = ["get_power_unit", "list_power_units", "POWER_UNITS", "TEAM_POWER_UNIT_ID"]
