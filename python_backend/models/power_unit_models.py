from dataclasses import dataclass, field
from typing import Dict, Optional

from lap_simulator.data_types import EngineMapName, PUState, PUReliabilityParams


# ---------------------------------------------------------------------------
# Mappe ICE ed ERS (separate)
# ---------------------------------------------------------------------------

@dataclass
class ICEMap:
    ice_map_id: str
    nome: str
    power_pct: float  # 0–120 (%)


@dataclass
class ERSMap:
    ers_map_id: str
    nome: str
    deploy_budget_mj: float
    bucket_primary_pct: float  # 1–120 (%)
    bucket_secondary_pct: float  # 1–120 (%)
    bucket_exit_pct: float  # 1–120 (%)
    defense_reserve_mj: float = 0.0


# ---------------------------------------------------------------------------
# Componenti fisiche della Power Unit
# ---------------------------------------------------------------------------

@dataclass
class ICE:
    ice_id: str
    nome: str
    potenza_tot_cv: float  # potenza massima in CV
    reliability: Optional[PUReliabilityParams] = None
    capacita_termica_kj_per_c: Optional[float] = None


@dataclass
class MGUK:
    mgu_k_id: str
    nome: str
    max_kw: float
    efficiency: float = 1.0
    capacita_termica_kj_per_c: Optional[float] = None


@dataclass
class MGUH:
    mgu_h_id: str
    nome: str
    base_kw: float
    direct_ratio_default: float = 0.3
    efficiency: float = 1.0
    capacita_termica_kj_per_c: Optional[float] = None


@dataclass
class Battery:
    battery_id: str
    nome: str
    capacity_mj: float
    max_charge_kw: float
    max_discharge_kw: float
    capacita_termica_kj_per_c: Optional[float] = None


# ---------------------------------------------------------------------------
# PowerUnit wrapper
# ---------------------------------------------------------------------------

@dataclass
class PowerUnit:
    pu_id: str
    nome: str
    fornitore: str
    anno: int
    spec_version: str
    ice: ICE
    mgu_k: MGUK
    mgu_h: MGUH
    battery: Battery
    ice_maps: Dict[EngineMapName, ICEMap] = field(default_factory=dict)
    ers_maps: Dict[EngineMapName, ERSMap] = field(default_factory=dict)
    reliability: Optional[PUReliabilityParams] = None
    fuel_capacity_kg: float = 110.0
    base_burn_kg_per_s: float = 0.035
    regen_profile: Optional[dict] = None

    def _resolve_ers_map(self, map_name: EngineMapName) -> Optional[ERSMap]:
        if self.ers_maps:
            return self.ers_maps.get(map_name) or next(iter(self.ers_maps.values()))
        return None

    def create_state(
        self,
        fuel_kg: Optional[float] = None,
        map_name: EngineMapName = EngineMapName.STANDARD,
    ) -> PUState:
        """Factory per generare un nuovo PUState coerente con i dati roster."""

        state = PUState()
        state.active_map = map_name
        state.fuel_kg = fuel_kg if fuel_kg is not None else self.fuel_capacity_kg
        state.ers_energy_mj = getattr(self.battery, "capacity_mj", state.ers_energy_mj)
        state.fuel_burn_rate_kg_per_s = self.base_burn_kg_per_s

        ers_map = self._resolve_ers_map(map_name)
        if ers_map:
            deploy_budget = ers_map.deploy_budget_mj
            state.deploy_budget_total_mj = deploy_budget
            state.bucket_primary_total_mj = deploy_budget * (ers_map.bucket_primary_pct / 100.0)
            state.bucket_secondary_total_mj = deploy_budget * (ers_map.bucket_secondary_pct / 100.0)
            state.bucket_exit_total_mj = deploy_budget * (ers_map.bucket_exit_pct / 100.0)
            state.defense_reserve_available_mj = ers_map.defense_reserve_mj

        return state

    def make_pu_state(
        self,
        fuel_kg: Optional[float] = None,
        map_name: EngineMapName = EngineMapName.STANDARD,
    ):
        """Compat helper per i vecchi consumer – ritorna (PUState, None)."""
        state = self.create_state(fuel_kg=fuel_kg, map_name=map_name)
        return state, None
