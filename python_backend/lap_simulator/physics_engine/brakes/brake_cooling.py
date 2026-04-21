"""
Brake Cooling - Raffreddamento freni F1 2025

Modello fisico cooling:
- Brake ducts (aperti/chiusi)
- Raffreddamento convettivo (aria)
- Trasferimento calore → gomme
- Drag aerodinamico da ducts

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict
import numpy as np


@dataclass
class BrakeDuctConfig:
    """Configurazione brake duct."""
    name: str  # es. "size_3_med"
    opening_pct: float  # % apertura (0-100)
    cooling_rate: float  # coefficiente raffreddamento
    drag_penalty: float  # % drag aggiuntivo
    tyre_heat_transfer: float  # % calore trasferito a gomma (0-1)


class BrakeCooling:
    """
    Raffreddamento freni F1 2025
    
    Brake ducts:
    - Size 1 (closed): cooling 0.5x, drag 0%, tyre heat 0.9x
    - Size 3 (medium): cooling 1.0x, drag 1.5%, tyre heat 0.5x
    - Size 5 (wide): cooling 1.6x, drag 3%, tyre heat 0.2x
    
    Meccanismi:
    - Convezione forzata (aria velocità)
    - Conduzione (disco → cerchio → aria interna gomma)
    - Irraggiamento (disco rosso → aria)
    
    Trasferimento calore alle gomme:
    - Ducts chiusi: gomma riscaldata (utile in piste fredde)
    - Ducts aperti: gomma isolata (utile in piste calde)
    """
    
    # Configurazioni tipiche brake ducts
    DUCT_CONFIGS: Dict[str, BrakeDuctConfig] = {
        'size_1_closed': BrakeDuctConfig(
            name='Size 1 (Closed)',
            opening_pct=0.0,
            cooling_rate=0.5,
            drag_penalty=0.0,
            tyre_heat_transfer=0.9,
        ),
        'size_2_small': BrakeDuctConfig(
            name='Size 2 (Small)',
            opening_pct=25.0,
            cooling_rate=0.75,
            drag_penalty=0.008,
            tyre_heat_transfer=0.7,
        ),
        'size_3_medium': BrakeDuctConfig(
            name='Size 3 (Medium)',
            opening_pct=50.0,
            cooling_rate=1.0,
            drag_penalty=0.015,
            tyre_heat_transfer=0.5,
        ),
        'size_4_large': BrakeDuctConfig(
            name='Size 4 (Large)',
            opening_pct=75.0,
            cooling_rate=1.3,
            drag_penalty=0.022,
            tyre_heat_transfer=0.3,
        ),
        'size_5_wide': BrakeDuctConfig(
            name='Size 5 (Wide)',
            opening_pct=100.0,
            cooling_rate=1.6,
            drag_penalty=0.03,
            tyre_heat_transfer=0.2,
        ),
    }
    
    def __init__(self, duct_config: str = 'size_3_medium'):
        """
        Inizializza sistema cooling
        
        Args:
            duct_config: nome configurazione (size_1_closed ... size_5_wide)
        """
        if duct_config not in self.DUCT_CONFIGS:
            raise ValueError(f"Duct config {duct_config} non valida")
        
        self.config = self.DUCT_CONFIGS[duct_config]
        
        # Parametri fisici
        self.air_density = 1.225  # kg/m³ (livello mare)
        self.ambient_temp = 25.0  # °C
    
    def calculate_convective_cooling(
        self,
        brake_temp_c: float,
        v_car_kph: float,
        dt_s: float
    ) -> float:
        """
        Calcola raffreddamento convettivo
        
        Args:
            brake_temp_c: °C temperatura freno
            v_car_kph: kph velocità vettura
            dt_s: secondi timestep
        
        Returns:
            kJ calore dissipato
        """
        # Velocità aria (m/s)
        v_air_ms = v_car_kph / 3.6
        
        # Coefficiente convezione (dipende da velocità e duct opening)
        # h = k × v^n (n ≈ 0.8 per flusso turbolento)
        h_base = 50.0  # W/m²·K (freno stazionario)
        h = h_base * (1.0 + 0.8 * (v_air_ms / 50.0) ** 0.8)
        
        # Applica duct opening
        h *= self.config.cooling_rate
        
        # Differenza temperatura
        delta_t = max(brake_temp_c - self.ambient_temp, 0.0)
        
        # Area superficiale disco (~0.05 m²)
        area = 0.05
        
        # Q = h × A × ΔT × dt
        q_cool = h * area * delta_t * dt_s / 1000.0  # kJ
        
        return q_cool
    
    def calculate_tyre_heat_transfer(
        self,
        brake_temp_c: float,
        rim_temp_c: float,
        dt_s: float
    ) -> float:
        """
        Calcola trasferimento calore freno → gomma
        
        Args:
            brake_temp_c: °C temperatura freno
            rim_temp_c: °C temperatura cerchio
            dt_s: secondi timestep
        
        Returns:
            kJ calore trasferito
        """
        # Differenza temperatura freno-cerchio
        delta_t_brake_rim = max(brake_temp_c - rim_temp_c, 0.0)
        
        # Coefficiente conduzione (disco → cerchio)
        k_conduction = 15.0  # W/K (metallo)
        
        # Q = k × ΔT × dt × tyre_heat_factor
        q_transfer = (
            k_conduction *
            delta_t_brake_rim *
            self.config.tyre_heat_transfer *
            dt_s / 1000.0
        )  # kJ
        
        return q_transfer
    
    def get_drag_penalty(self) -> float:
        """
        Restituisce penalità drag aerodinamico
        
        Returns:
            float % drag aggiuntivo (0-3%)
        """
        return self.config.drag_penalty
    
    def set_duct_config(self, config_name: str):
        """
        Cambia configurazione brake duct
        
        Args:
            config_name: nome configurazione
        """
        if config_name not in self.DUCT_CONFIGS:
            raise ValueError(f"Duct config {config_name} non valida")
        
        self.config = self.DUCT_CONFIGS[config_name]
    
    def get_optimal_duct_for_temp(self, brake_temp_c: float, v_avg_kph: float) -> str:
        """
        Suggerisce configurazione ottimale in base a temperatura
        
        Args:
            brake_temp_c: °C temperatura freno
            v_avg_kph: kph velocità media pista
        
        Returns:
            str nome configurazione suggerita
        """
        if brake_temp_c > 900.0:
            # Molto caldo: ducts larghi
            return 'size_5_wide'
        elif brake_temp_c > 700.0:
            # Caldo: ducts grandi
            return 'size_4_large'
        elif brake_temp_c > 500.0:
            # Normale: ducts medi
            return 'size_3_medium'
        elif brake_temp_c > 350.0:
            # Freddo: ducts piccoli
            return 'size_2_small'
        else:
            # Molto freddo: ducts chiusi (scalda)
            return 'size_1_closed'
    
    def get_summary(self) -> Dict:
        """Riepilogo sistema cooling."""
        return {
            'config_name': self.config.name,
            'opening_pct': self.config.opening_pct,
            'cooling_rate': self.config.cooling_rate,
            'drag_penalty_pct': self.config.drag_penalty * 100,
            'tyre_heat_transfer': self.config.tyre_heat_transfer,
            'ambient_temp_c': self.ambient_temp,
        }

# ============================================================================
# V6.3: Brake thermal integration (from waypoint_integrator.py)
# ============================================================================
def update_brake_thermal(
    brake_state,
    velocity_ms: float,
    mass_kg: float,
    v_current_ms: float,
    v_target_ms: float,
    setup: Dict,
    dt_step: float,
) -> float:
    """
    Aggiorna lo stato termico dei freni e calcola il fade factor.

    Estratto dal waypoint_integrator.py V6.3 per modularizzazione.

    Args:
        brake_state: oggetto BrakeState con temp_front_c/temp_rear_c
        velocity_ms: velocità corrente [m/s]
        mass_kg: massa auto [kg]
        v_current_ms: velocità prima della frenata [m/s]
        v_target_ms: velocità target dopo frenata [m/s]
        setup: dict con brake_bias e brake_duct
        dt_step: timestep di integrazione [s]

    Returns:
        fade_factor: 0.0-1.0 (1.0 = full fade)
    """
    if brake_state is None or v_current_ms <= v_target_ms:
        return 0.0

    # Joule dissipated
    joules_dissipated = 0.5 * mass_kg * (v_current_ms ** 2 - v_target_ms ** 2)

    # Brake heat distribution
    brake_bias = setup.get('brake_bias', 0.55) if setup else 0.55
    heat_front_kj = (joules_dissipated / 1000.0) * brake_bias
    heat_rear_kj = (joules_dissipated / 1000.0) * (1.0 - brake_bias)

    # Sub-step thermal integration
    SUB_DT = 0.01
    dt_braking = dt_step
    N_SUBSTEPS = max(1, int(dt_braking / SUB_DT))
    heat_per_substep_front = heat_front_kj / max(N_SUBSTEPS, 1)
    heat_per_substep_rear = heat_rear_kj / max(N_SUBSTEPS, 1)

    H_CONV_BASE = 15.0
    C_TH_BRAKE = 2.5
    T_AMBIENT = 20.0
    brake_duct_opening = setup.get('brake_duct', 0.5) if setup else 0.5

    for _ in range(N_SUBSTEPS):
        temp_rise_front = heat_per_substep_front / C_TH_BRAKE
        temp_rise_rear = heat_per_substep_rear / C_TH_BRAKE

        h_conv_front = H_CONV_BASE * velocity_ms * (0.5 + brake_duct_opening)
        q_cool_front_kj = h_conv_front * (brake_state.temp_front_c - T_AMBIENT) * SUB_DT / 1000.0

        h_conv_rear = H_CONV_BASE * velocity_ms * 0.5
        q_cool_rear_kj = h_conv_rear * (brake_state.temp_rear_c - T_AMBIENT) * SUB_DT / 1000.0

        brake_state.temp_front_c = max(T_AMBIENT, brake_state.temp_front_c + temp_rise_front - q_cool_front_kj / C_TH_BRAKE)
        brake_state.temp_rear_c = max(T_AMBIENT, brake_state.temp_rear_c + temp_rise_rear - q_cool_rear_kj / C_TH_BRAKE)

    # Fade factor
    FADE_THRESHOLD_C = 850.0
    FADE_SENSITIVITY_C = 40.0
    worst_brake_temp = max(brake_state.temp_front_c, brake_state.temp_rear_c)
    fade_factor = max(0.0, min(1.0, (worst_brake_temp - FADE_THRESHOLD_C) / FADE_SENSITIVITY_C))

    return fade_factor
