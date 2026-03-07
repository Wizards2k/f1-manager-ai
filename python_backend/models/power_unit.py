from dataclasses import dataclass
from typing import Dict, Optional

from lap_simulator.data_types import (
    EngineMapName,
    EngineMapParams,
    PUState,
    PUReliabilityParams,
)


@dataclass
class ICE:
    ice_id: int
    nome: str
    potenza_pct: float = 1.0  # 0.0 - 1.2 (0-120%)
    temp_warning_c: float = 130.0
    temp_critical_c: float = 140.0
    wear_coeff: float = 0.0008
    overrev_factor: float = 1.15
    shock_factor: float = 1.10


@dataclass
class MGUK:
    mgu_k_id: int
    nome: str
    max_kw: float
    efficienza: float = 1.0
    temp_warning_c: float = 95.0
    temp_critical_c: float = 110.0
    wear_coeff: float = 0.0012


@dataclass
class MGUH:
    mgu_h_id: int
    nome: str
    base_kw: float
    direct_ratio_default: float = 0.0
    efficienza: float = 1.0
    temp_warning_c: float = 95.0
    temp_critical_c: float = 110.0
    wear_coeff: float = 0.0010


@dataclass
class Battery:
    battery_id: int
    nome: str
    capacity_mj: float = 4.0
    max_charge_kw: float = 120.0
    max_discharge_kw: float = 160.0
    temp_warning_c: float = 60.0
    temp_critical_c: float = 80.0
    wear_coeff: float = 0.0010


@dataclass
class IceMap:
    ice_map_id: int
    nome: str
    engine_map_name: EngineMapName = EngineMapName.RACE
    power_pct: float = 1.0
    heat_load_kw: float = 260.0
    cooling_share: float = 0.5
    deployment_style: str = "balanced"


@dataclass
class ErsMap:
    ers_map_id: int
    nome: str
    engine_map_name: EngineMapName = EngineMapName.RACE
    deploy_budget_mj: float = 4.0
    bucket_primary_pct: float = 0.5
    bucket_secondary_pct: float = 0.35
    bucket_exit_pct: float = 0.15
    defense_reserve_mj: float = 0.2
    ers_output_kw: float = 120.0
    mguh_direct_ratio: float = 0.0
    mguh_power_kw: float = 0.0
    heat_load_kw: float = 260.0
    cooling_share: float = 0.5
    deployment_style: str = "balanced"

    def to_engine_map_params(self, ice_map: IceMap) -> EngineMapParams:
        return EngineMapParams(
            name=self.engine_map_name,
            heat_load_kw=self.heat_load_kw,
            torque_ramp=ice_map.power_pct,
            deployment_style=self.deployment_style,
            cooling_share=self.cooling_share,
            ers_output_kw=self.ers_output_kw,
            mguh_direct_ratio=self.mguh_direct_ratio,
            mguh_power_kw=self.mguh_power_kw,
            bucket_primary_pct=self.bucket_primary_pct,
            bucket_secondary_pct=self.bucket_secondary_pct,
            bucket_exit_pct=self.bucket_exit_pct,
            defense_reserve_mj=self.defense_reserve_mj,
        )


@dataclass
class PowerUnit:
    pu_id: int
    nome: str
    fornitore: str
    anno: int
    spec_version: str
    ice: ICE
    mgu_k: MGUK
    mgu_h: MGUH
    battery: Battery
    ice_maps: Dict[int, IceMap]
    ers_maps: Dict[int, ErsMap]
    reliability: PUReliabilityParams = PUReliabilityParams()
    fuel_tank_capacity_kg: float = 110.0
    deploy_limit_mj_per_lap: float = 4.0
    recovery_limit_mj_per_lap: float = 2.0
    default_ice_map_id: Optional[int] = None
    default_ers_map_id: Optional[int] = None
    regen_profile: Optional[str] = None

    def _resolve_maps(self, ice_map_id: Optional[int], ers_map_id: Optional[int]) -> tuple[IceMap, ErsMap]:
        ice_map = self.ice_maps.get(ice_map_id) if ice_map_id is not None else None
        if ice_map is None:
            ice_map = self.ice_maps.get(self.default_ice_map_id) if self.default_ice_map_id is not None else None
        if ice_map is None and self.ice_maps:
            ice_map = next(iter(self.ice_maps.values()))

        ers_map = self.ers_maps.get(ers_map_id) if ers_map_id is not None else None
        if ers_map is None:
            ers_map = self.ers_maps.get(self.default_ers_map_id) if self.default_ers_map_id is not None else None
        if ers_map is None and self.ers_maps:
            ers_map = next(iter(self.ers_maps.values()))

        if ice_map is None or ers_map is None:
            raise ValueError("PowerUnit missing ICE/ERS map for PUState factory")
        return ice_map, ers_map

    def make_pu_state(self, ice_map_id: Optional[int] = None, ers_map_id: Optional[int] = None) -> tuple[PUState, EngineMapParams]:
        """Create a PUState and EngineMapParams from this PowerUnit configuration."""
        ice_map, ers_map = self._resolve_maps(ice_map_id, ers_map_id)
        map_params = ers_map.to_engine_map_params(ice_map)

        state = PUState(active_map=map_params.name)
        state.fuel_kg = self.fuel_tank_capacity_kg
        state.ers_energy_mj = self.battery.capacity_mj

        # Budget ERS per lap
        state.deploy_budget_total_mj = ers_map.deploy_budget_mj
        state.bucket_primary_total_mj = ers_map.deploy_budget_mj * ers_map.bucket_primary_pct
        state.bucket_secondary_total_mj = ers_map.deploy_budget_mj * ers_map.bucket_secondary_pct
        state.bucket_exit_total_mj = ers_map.deploy_budget_mj * ers_map.bucket_exit_pct
        state.defense_reserve_available_mj = ers_map.defense_reserve_mj

        # MGU-H coupling baseline
        state.mguh_primary_total_mj = 0.0
        state.mguh_secondary_total_mj = 0.0
        state.mguh_exit_total_mj = 0.0

        return state, map_params
