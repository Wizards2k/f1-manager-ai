"""
ERS Deploy - Gestione strategica energia ERS (Physics V4)

Modello semplificato per integrazione su HD waypoints:
- Deploy batteria (4 MJ/giro max)
- Harvest da frenata (2 MJ/giro max)
- MGU-H direct drive (illimitato)
- Priority score per rettilineo/curva

NOTA: Modulo V4 standalone, non dipende da power_unit.py V1
"""

from dataclasses import dataclass
from typing import Dict, List
import numpy as np


@dataclass
class ERSEnergyState:
    """Stato energia ERS."""
    soc_mj: float  # MJ carica batteria corrente
    soc_pct: float  # % stato di carica (0-100)
    lap_deploy_mj: float  # MJ deployati nel giro corrente
    lap_harvest_mj: float  # MJ recuperati nel giro corrente
    lap_mguh_direct_mj: float  # MJ MGU-H direct nel giro
    deploy_remaining_mj: float  # MJ deploy residui (budget 4MJ)
    harvest_remaining_mj: float  # MJ harvest residui (budget 2MJ)


@dataclass
class DeployRequest:
    """Richiesta deploy per un waypoint."""
    battery_power_kw: float  # kW da batteria
    mguh_direct_kw: float  # kW da MGU-H direct
    total_ers_kw: float  # kW totale ERS
    priority_score: float  # 0.0-1.0 priorità sezione
    bucket_key: str  # 'primary', 'secondary', 'exit'


class ERSDeployManager:
    """
    Gestore deploy ERS per Physics V4
    
    Strategia semplificata per HD waypoints:
    - Budget per giro: 4 MJ batteria, 2 MJ harvest
    - MGU-H direct: illimitato (ma limitato da potenza)
    - 3 bucket: Primary (50%), Secondary (35%), Exit (15%)
    
    Il deploy è distribuito in base alla priorità:
    - Rettilinei DRS: priority 1.0 (primary bucket)
    - Curve veloci: priority 0.6-0.75 (secondary)
    - Curve lente: priority 0.25-0.35 (exit)
    """
    
    # Limiti regolamentari FIA 2025
    DEPLOY_LIMIT_MJ = 4.0       # Max deploy batteria per giro
    HARVEST_LIMIT_MJ = 2.0      # Max harvest da frenata per giro
    ERS_MAX_POWER_KW = 120.0    # Potenza max MGU-K
    
    # Capacità batteria
    BATTERY_CAPACITY_MJ = 4.0   # MJ utilizzabili (reale: 5-6 MJ)
    
    def __init__(self, config=None):
        """
        Inizializza gestore ERS
        
        Args:
            config: dict con parametri personalizzati
        """
        defaults = {
            'bucket_primary_pct': 0.50,    # 50% budget su primary
            'bucket_secondary_pct': 0.35,  # 35% su secondary
            'bucket_exit_pct': 0.15,       # 15% su exit
            'target_soc_end_lap': 0.55,    # 55% SOC a fine giro
            'mguh_direct_ratio': 0.45,     # 45% energia da MGU-H direct
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Stato energia
        self.soc_mj = self.BATTERY_CAPACITY_MJ  # Inizio giro: batteria carica
        self.lap_deploy_mj = 0.0
        self.lap_harvest_mj = 0.0
        self.lap_mguh_direct_mj = 0.0
        
        # Conta settori per bucket
        self.bucket_sections = {
            'primary': 0,
            'secondary': 0,
            'exit': 0,
        }
        self.bucket_sections_remaining = {
            'primary': 0,
            'secondary': 0,
            'exit': 0,
        }
    
    def reset_lap(self, initial_soc_mj: float = None):
        """
        Resetta stato per nuovo giro
        
        Args:
            initial_soc_mj: MJ carica iniziale (default: full)
        """
        if initial_soc_mj is not None:
            self.soc_mj = np.clip(initial_soc_mj, 0.0, self.BATTERY_CAPACITY_MJ)
        else:
            self.soc_mj = self.BATTERY_CAPACITY_MJ
        
        self.lap_deploy_mj = 0.0
        self.lap_harvest_mj = 0.0
        self.lap_mguh_direct_mj = 0.0
        
        # Resetta conteggio settori
        self.bucket_sections_remaining = self.bucket_sections.copy()
    
    def get_energy_state(self) -> 'ERSEnergyState':
        """Restituisce stato energia corrente."""
        deploy_remaining = max(self.DEPLOY_LIMIT_MJ - self.lap_deploy_mj, 0.0)
        harvest_remaining = max(self.HARVEST_LIMIT_MJ - self.lap_harvest_mj, 0.0)
        
        return ERSEnergyState(
            soc_mj=self.soc_mj,
            soc_pct=(self.soc_mj / self.BATTERY_CAPACITY_MJ) * 100,
            lap_deploy_mj=self.lap_deploy_mj,
            lap_harvest_mj=self.lap_harvest_mj,
            lap_mguh_direct_mj=self.lap_mguh_direct_mj,
            deploy_remaining_mj=deploy_remaining,
            harvest_remaining_mj=harvest_remaining
        )
    
    def calculate_deploy_request(
        self,
        section_priority: float,
        section_length_m: float,
        v_car_kph: float,
        dt: float,
        is_drs: bool = False,
        is_corner: bool = False,
    ) -> 'DeployRequest':
        """
        Calcola richiesta deploy per un waypoint/segmento
        
        Args:
            section_priority: 0.0-1.0 priorità sezione
            section_length_m: m lunghezza segmento
            v_car_kph: kph velocità vettura
            dt: secondi timestep
            is_drs: flag DRS attivo
            is_corner: flag curva
        
        Returns:
            DeployRequest con potenze richieste
        """
        # Determina bucket
        if is_drs or (section_priority > 0.8 and not is_corner):
            bucket_key = 'primary'
        elif section_priority > 0.5:
            bucket_key = 'secondary'
        else:
            bucket_key = 'exit'
        
        # Calcola cap per sezione
        sections_remaining = max(self.bucket_sections_remaining[bucket_key], 1)
        bucket_pct = self.config[f'bucket_{bucket_key}_pct']
        bucket_total_mj = self.DEPLOY_LIMIT_MJ * bucket_pct
        cap_per_section = bucket_total_mj / sections_remaining
        
        # Energia richiedibile (batteria)
        target_soc_mj = self.config['target_soc_end_lap'] * self.BATTERY_CAPACITY_MJ
        available_battery = max(self.soc_mj - target_soc_mj, 0.0)
        deploy_remaining = max(self.DEPLOY_LIMIT_MJ - self.lap_deploy_mj, 0.0)
        
        # Limita a cap sezione e disponibilità
        battery_request_mj = min(cap_per_section, available_battery, deploy_remaining)
        
        # MGU-H direct (illimitato, ma limitato da potenza)
        # Stima: 45% dell'energia totale viene da MGU-H
        mguh_ratio = self.config['mguh_direct_ratio']
        total_request_mj = battery_request_mj / (1.0 - mguh_ratio) if mguh_ratio < 1.0 else battery_request_mj
        mguh_request_mj = total_request_mj * mguh_ratio
        
        # Converte MJ → kW (potenza istantanea)
        battery_kw = (battery_request_mj * 1000.0) / max(dt, 0.01)
        mguh_kw = (mguh_request_mj * 1000.0) / max(dt, 0.01)
        
        # Limita a potenza max ERS
        total_kw = battery_kw + mguh_kw
        if total_kw > self.ERS_MAX_POWER_KW:
            scale = self.ERS_MAX_POWER_KW / total_kw
            battery_kw *= scale
            mguh_kw *= scale
        
        return DeployRequest(
            battery_power_kw=battery_kw,
            mguh_direct_kw=mguh_kw,
            total_ers_kw=battery_kw + mguh_kw,
            priority_score=section_priority,
            bucket_key=bucket_key
        )
    
    def consume_energy(self, battery_mj: float, mguh_mj: float, harvest_mj: float = 0.0):
        """
        Consuma/recupera energia
        
        Args:
            battery_mj: MJ consumati da batteria (positivo = consumo)
            mguh_mj: MJ da MGU-H direct (positivo = consumo)
            harvest_mj: MJ recuperati da frenata (positivo = ricarica)
        """
        # Consumo batteria
        self.soc_mj = max(self.soc_mj - battery_mj, 0.0)
        self.lap_deploy_mj += battery_mj
        
        # Consumo MGU-H direct
        self.lap_mguh_direct_mj += mguh_mj
        
        # Recupero da frenata
        harvest_available = max(self.HARVEST_LIMIT_MJ - self.lap_harvest_mj, 0.0)
        harvest_actual = min(harvest_mj, harvest_available, self.BATTERY_CAPACITY_MJ - self.soc_mj)
        self.soc_mj = min(self.soc_mj + harvest_actual, self.BATTERY_CAPACITY_MJ)
        self.lap_harvest_mj += harvest_actual
        
        # Decrementa settori rimanenti
        # (chiamato alla fine di ogni sezione)
    
    def decrement_section(self, bucket_key: str):
        """Decrementa contatore settori per bucket."""
        if bucket_key in self.bucket_sections_remaining:
            self.bucket_sections_remaining[bucket_key] = max(
                self.bucket_sections_remaining[bucket_key] - 1, 0
            )
    
    def set_section_counts(self, primary: int, secondary: int, exit: int):
        """
        Imposta conteggio settori per giro
        
        Args:
            primary: numero settori primary
            secondary: numero settori secondary
            exit: numero settori exit
        """
        self.bucket_sections = {
            'primary': primary,
            'secondary': secondary,
            'exit': exit,
        }
        self.bucket_sections_remaining = {
            'primary': primary,
            'secondary': secondary,
            'exit': exit,
        }
    
    def get_priority_score(self, is_straight: bool, is_drs: bool, v_kph: float) -> float:
        """
        Calcola priority score per sezione
        
        Args:
            is_straight: flag rettilineo
            is_drs: flag DRS
            v_kph: kph velocità
        
        Returns:
            float 0.0-1.0
        """
        if is_drs:
            return 1.0
        
        if is_straight:
            return 0.85
        
        # Curve: priorità dipende da velocità
        if v_kph > 200:
            return 0.75  # Curve veloci
        elif v_kph > 100:
            return 0.50  # Curve medie
        else:
            return 0.35  # Curve lente
    
    def get_summary(self) -> Dict:
        """Riepilogo stato ERS."""
        return {
            'soc_mj': self.soc_mj,
            'soc_pct': (self.soc_mj / self.BATTERY_CAPACITY_MJ) * 100,
            'lap_deploy_mj': self.lap_deploy_mj,
            'lap_harvest_mj': self.lap_harvest_mj,
            'lap_mguh_direct_mj': self.lap_mguh_direct_mj,
            'deploy_limit_mj': self.DEPLOY_LIMIT_MJ,
            'harvest_limit_mj': self.HARVEST_LIMIT_MJ,
            'battery_capacity_mj': self.BATTERY_CAPACITY_MJ,
            'bucket_primary_pct': self.config['bucket_primary_pct'] * 100,
            'bucket_secondary_pct': self.config['bucket_secondary_pct'] * 100,
            'bucket_exit_pct': self.config['bucket_exit_pct'] * 100,
        }
