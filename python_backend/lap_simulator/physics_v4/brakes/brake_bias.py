"""
Brake Bias - Ripartizione frenata e brake migration F1 2025

Modello fisico brake bias:
- Brake balance statico (55-60% anteriore)
- Brake migration dinamico (pressione pedale)
- MGU-K harvest (freno elettrico posteriore)
- Brake-by-wire

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np


@dataclass
class BrakeBiasState:
    """Stato brake bias."""
    bias_front_pct: float  # % frenata anteriore
    bias_rear_pct: float  # % frenata posteriore
    migration_offset: float  # % offset migration
    mguk_harvest_active: bool  # Flag harvest attivo
    mguk_harvest_kw: float  # kW harvest corrente


class BrakeBias:
    """
    Brake Bias & Migration F1 2025
    
    Brake balance:
    - Base: 55-60% anteriore (dipende da circuito)
    - Migration: ±4% dinamico con pressione pedale
    - MGU-K harvest: fino a 120 kW (freno elettrico posteriore)
    
    Brake migration:
    - Alta pressione (>80%): +2-4% anteriore (stabilità)
    - Media pressione (40-80%): 0% (base)
    - Bassa pressione (<40%): -1-3% posteriore (rotazione)
    
    Brake-by-wire:
    - Gestisce harvest posteriore
    - Compensa quando batteria piena
    - Previene bloccaggio posteriore
    """
    
    # Limiti fisici
    BIAS_MIN_FRONT = 50.0  # % minimo anteriore
    BIAS_MAX_FRONT = 65.0  # % massimo anteriore
    MIGRATION_MAX = 4.0    # % migration massima
    
    # MGU-K harvest
    MGUK_MAX_KW = 120.0    # kW potenza max harvest
    MGUK_MAX_MJ_PER_LAP = 2.0  # MJ harvest per giro (limite FIA)
    
    def __init__(self, base_bias_front: float = 57.0):
        """
        Inizializza brake bias
        
        Args:
            base_bias_front: % frenata anteriore base (tipicamente 55-60%)
        """
        self.base_bias_front = np.clip(base_bias_front, self.BIAS_MIN_FRONT, self.BIAS_MAX_FRONT)
        self.base_bias_rear = 100.0 - self.base_bias_front
        
        # Stato corrente
        self.state = BrakeBiasState(
            bias_front_pct=self.base_bias_front,
            bias_rear_pct=self.base_bias_rear,
            migration_offset=0.0,
            mguk_harvest_active=False,
            mguk_harvest_kw=0.0,
        )
        
        # Mappe migration (da brake-integration-gemini.md)
        self.migration_maps = {
            'map_1_stable': {
                'pressure_0_pct': -1.0,
                'pressure_50_pct': 1.5,
                'pressure_100_pct': 4.5,
            },
            'map_2_agile': {
                'pressure_0_pct': -3.5,
                'pressure_50_pct': 0.0,
                'pressure_100_pct': 2.0,
            },
            'map_3_neutral': {
                'pressure_0_pct': 0.0,
                'pressure_50_pct': 0.0,
                'pressure_100_pct': 0.0,
            },
        }
        
        self.active_migration_map = 'map_3_neutral'
    
    def calculate_migration_offset(self, pedal_pressure_pct: float) -> float:
        """
        Calcola offset migration in base a pressione pedale
        
        Args:
            pedal_pressure_pct: % pressione pedale (0-100)
        
        Returns:
            float % offset migration (-4 a +4)
        """
        # Recupera mappa attiva
        map_data = self.migration_maps[self.active_migration_map]
        
        # Interpolazione lineare
        if pedal_pressure_pct <= 0:
            offset = map_data['pressure_0_pct']
        elif pedal_pressure_pct <= 50:
            # Interpolazione 0-50%
            ratio = pedal_pressure_pct / 50.0
            offset = map_data['pressure_0_pct'] + (map_data['pressure_50_pct'] - map_data['pressure_0_pct']) * ratio
        elif pedal_pressure_pct <= 100:
            # Interpolazione 50-100%
            ratio = (pedal_pressure_pct - 50.0) / 50.0
            offset = map_data['pressure_50_pct'] + (map_data['pressure_100_pct'] - map_data['pressure_50_pct']) * ratio
        else:
            offset = map_data['pressure_100_pct']
        
        # Clamp a limiti fisici
        offset = np.clip(offset, -self.MIGRATION_MAX, self.MIGRATION_MAX)
        
        return offset
    
    def calculate_effective_bias(
        self,
        pedal_pressure_pct: float,
        v_car_kph: float,
        mguk_available: bool = True
    ) -> Tuple[float, float]:
        """
        Calcola brake bias effettivo (con migration e harvest)
        
        Args:
            pedal_pressure_pct: % pressione pedale
            v_car_kph: kph velocità vettura
            mguk_available: True se MGU-K può harvestare
        
        Returns:
            (bias_front_pct, bias_rear_pct)
        """
        # 1. Calcola migration offset
        migration_offset = self.calculate_migration_offset(pedal_pressure_pct)
        
        # 2. Bias effettivo (base + migration)
        effective_front = self.base_bias_front + migration_offset
        effective_rear = 100.0 - effective_front
        
        # 3. MGU-K harvest (solo posteriore, solo se disponibile)
        mguk_contribution = 0.0
        if mguk_available and pedal_pressure_pct > 20.0 and v_car_kph > 50.0:
            # Harvest riduce carico freni idraulici posteriori
            # Max harvest a 100% pedal, diminuisce con velocità
            harvest_factor = (pedal_pressure_pct / 100.0) * min(1.0, v_car_kph / 200.0)
            mguk_contribution = self.MGUK_MAX_KW * harvest_factor / 1000.0  # Converti a % approssimativa
        
        # Aggiorna stato
        self.state.bias_front_pct = np.clip(effective_front, self.BIAS_MIN_FRONT, self.BIAS_MAX_FRONT)
        self.state.bias_rear_pct = 100.0 - self.state.bias_front_pct
        self.state.migration_offset = migration_offset
        self.state.mguk_harvest_active = mguk_contribution > 0.0
        self.state.mguk_harvest_kw = mguk_contribution * 1000.0  # kW
        
        return self.state.bias_front_pct, self.state.bias_rear_pct
    
    def calculate_brake_force_distribution(
        self,
        total_brake_force_kn: float,
        pedal_pressure_pct: float,
        v_car_kph: float,
        mguk_available: bool = True
    ) -> Tuple[float, float, float]:
        """
        Calcola distribuzione forze frenanti
        
        Args:
            total_brake_force_kn: kN forza frenante totale
            pedal_pressure_pct: % pressione pedale
            v_car_kph: kph velocità vettura
            mguk_available: True se MGU-K disponibile
        
        Returns:
            (front_force_kn, rear_hydraulic_kn, rear_mguk_kn)
        """
        # Bias effettivo
        bias_front, bias_rear = self.calculate_effective_bias(pedal_pressure_pct, v_car_kph, mguk_available)
        
        # Forza totale
        front_force = total_brake_force_kn * (bias_front / 100.0)
        rear_total = total_brake_force_kn * (bias_rear / 100.0)
        
        # Contributo MGU-K (solo posteriore)
        mguk_force = 0.0
        if self.state.mguk_harvest_active:
            # MGU-K contribuisce al posteriore
            mguk_force = rear_total * 0.3  # ~30% da elettrico
            rear_hydraulic = rear_total - mguk_force
        else:
            rear_hydraulic = rear_total
        
        return front_force, rear_hydraulic, mguk_force
    
    def set_migration_map(self, map_name: str):
        """
        Cambia mappa migration
        
        Args:
            map_name: nome mappa (map_1_stable, map_2_agile, map_3_neutral)
        """
        if map_name not in self.migration_maps:
            raise ValueError(f"Migration map {map_name} non valida")
        
        self.active_migration_map = map_name
    
    def set_base_bias(self, bias_front_pct: float):
        """
        Imposta brake bias base
        
        Args:
            bias_front_pct: % frenata anteriore (50-65%)
        """
        self.base_bias_front = np.clip(bias_front_pct, self.BIAS_MIN_FRONT, self.BIAS_MAX_FRONT)
        self.base_bias_rear = 100.0 - self.base_bias_front
    
    def get_state(self) -> 'BrakeBiasState':
        """Restituisce stato corrente."""
        return self.state
    
    def get_summary(self) -> Dict:
        """Riepilogo brake bias."""
        return {
            'base_bias_front': self.base_bias_front,
            'base_bias_rear': self.base_bias_rear,
            'active_migration_map': self.active_migration_map,
            'current_bias_front': self.state.bias_front_pct,
            'current_bias_rear': self.state.bias_rear_pct,
            'migration_offset': self.state.migration_offset,
            'mguk_harvest_active': self.state.mguk_harvest_active,
            'mguk_harvest_kw': self.state.mguk_harvest_kw,
        }
