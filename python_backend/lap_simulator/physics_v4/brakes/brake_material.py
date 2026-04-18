"""
Brake Material - Materiale e proprietà freni F1 2025

Modello fisico freni carbon-carbon:
- Finestra operativa: 400-900°C
- Coefficiente attrito vs temperatura
- Ossidazione >1100°C
- Massa termica e capacità

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np


@dataclass
class BrakeMaterialParams:
    """Parametri materiale freni."""
    name: str  # es. "Carbon-Carbon Front"
    mass_kg: float  # kg massa disco
    specific_heat_j_kgk: float  # J/kg·K capacità termica
    optimal_temp_min_c: float  # °C temperatura ottimale minima
    optimal_temp_max_c: float  # °C temperatura ottimale massima
    critical_temp_c: float  # °C temperatura critica
    friction_coeff_peak: float  # coefficiente attrito di picco
    oxidation_rate: float  # % massa persa per ora >1000°C


@dataclass
class BrakeState:
    """Stato corrente freno."""
    temp_c: float  # °C temperatura disco
    wear_pct: float  # % usura (0-100)
    friction_coeff: float  # coefficiente attrito attuale
    overheat_warning: bool  # Flag surriscaldamento
    cold_warning: bool  # Flag freddo (glazing)


class BrakeMaterial:
    """
    Materiale freni F1 2025 - Carbon-Carbon
    
    Proprietà:
    - Massa: 1.5 kg (anteriore), 0.8 kg (posteriore)
    - Calore specifico: ~1000 J/kg·K
    - Finestra ottimale: 500-900°C
    - Critico: >1100°C (ossidazione)
    - Friction coeff: 0.4-0.6 (dipende da temperatura)
    
    Comportamento:
    - <300°C: glazing, attrito basso (~0.15)
    - 400-600°C: attrito crescente (0.3→0.5)
    - 600-900°C: attrito ottimale (~0.52)
    - >1000°C: ossidazione, attrito cala (~0.4)
    - >1200°C: fading, rischio rottura
    """
    
    # Parametri freni anteriori e posteriori
    FRONT_PARAMS = BrakeMaterialParams(
        name='Carbon-Carbon Front',
        mass_kg=1.5,
        specific_heat_j_kgk=1000.0,
        optimal_temp_min_c=400.0,
        optimal_temp_max_c=900.0,
        critical_temp_c=1100.0,
        friction_coeff_peak=0.52,
        oxidation_rate=0.001,  # % per ora >1000°C
    )
    
    REAR_PARAMS = BrakeMaterialParams(
        name='Carbon-Carbon Rear',
        mass_kg=0.8,
        specific_heat_j_kgk=1000.0,
        optimal_temp_min_c=350.0,
        optimal_temp_max_c=850.0,
        critical_temp_c=1050.0,
        friction_coeff_peak=0.48,
        oxidation_rate=0.0012,
    )
    
    def __init__(self, is_front: bool = True):
        """
        Inizializza freno
        
        Args:
            is_front: True = anteriore, False = posteriore
        """
        self.is_front = is_front
        self.params = self.FRONT_PARAMS if is_front else self.REAR_PARAMS
        
        # Stato iniziale
        ambient_temp = 25.0
        self.state = BrakeState(
            temp_c=ambient_temp,
            wear_pct=0.0,
            friction_coeff=self._get_friction_coeff_at_temp(ambient_temp),
            overheat_warning=False,
            cold_warning=True,
        )
    
    def _get_friction_coeff_at_temp(self, temp_c: float) -> float:
        """
        Restituisce coefficiente attrito a temperatura data
        
        Args:
            temp_c: °C temperatura disco
        
        Returns:
            float mu (0.15-0.52)
        """
        # Tabella frizione vs temperatura (da brake-integration-gemini.md)
        if temp_c < 300.0:
            # Freddo: glazing, attrito basso
            mu = 0.15 + (temp_c - 25.0) / 300.0 * 0.25
        elif temp_c < 500.0:
            # Riscaldamento: attrito crescente
            mu = 0.40 + (temp_c - 300.0) / 200.0 * 0.12
        elif temp_c < 800.0:
            # Ottimale: attrito stabile
            mu = self.params.friction_coeff_peak
        elif temp_c < 1000.0:
            # Sovraccarico: attrito cala leggermente
            mu = self.params.friction_coeff_peak - (temp_c - 800.0) / 200.0 * 0.08
        else:
            # Ossidazione: attrito cala drasticamente
            mu = max(0.25, self.params.friction_coeff_peak - 0.12 - (temp_c - 1000.0) / 200.0 * 0.15)
        
        return np.clip(mu, 0.15, 0.55)
    
    def update_friction_coeff(self, temp_c: float):
        """
        Aggiorna coefficiente attrito in funzione temperatura
        
        Args:
            temp_c: °C temperatura disco
        """
        self.state.friction_coeff = self._get_friction_coeff_at_temp(temp_c)
        
        # Aggiorna warning
        self.state.overheat_warning = temp_c > self.params.optimal_temp_max_c + 50.0
        self.state.cold_warning = temp_c < self.params.optimal_temp_min_c - 100.0
    
    def get_thermal_capacity(self) -> float:
        """
        Restituisce capacità termica totale
        
        Returns:
            kJ/K capacità termica
        """
        # C = m × cp
        capacity = self.params.mass_kg * self.params.specific_heat_j_kgk / 1000.0
        return capacity
    
    def get_braking_energy_capacity(self) -> float:
        """
        Restituisce energia frenante massima assorbibile
        
        Returns:
            MJ energia massima
        """
        # Energia per scaldare da 25°C a critical_temp
        delta_t_max = self.params.critical_temp_c - 25.0
        energy_mj = self.get_thermal_capacity() * delta_t_max / 1000.0
        return energy_mj
    
    def calculate_oxidation_wear(self, temp_c: float, dt_s: float) -> float:
        """
        Calcola usura da ossidazione (solo >1000°C)
        
        Args:
            temp_c: °C temperatura disco
            dt_s: secondi timestep
        
        Returns:
            % usura da ossidazione
        """
        if temp_c < 1000.0:
            return 0.0
        
        # Ossidazione aumenta esponenzialmente con temperatura
        excess_temp = temp_c - 1000.0
        oxidation_factor = 1.0 + excess_temp / 100.0
        
        # Usura = rate × factor × dt (converti ore → secondi)
        wear_pct = self.params.oxidation_rate * oxidation_factor * (dt_s / 3600.0) * 100.0
        
        return wear_pct
    
    def get_state(self) -> 'BrakeState':
        """Restituisce stato corrente."""
        return self.state
    
    def get_summary(self) -> Dict:
        """Riepilogo freno."""
        return {
            'name': self.params.name,
            'is_front': self.is_front,
            'mass_kg': self.params.mass_kg,
            'thermal_capacity_kjk': self.get_thermal_capacity(),
            'optimal_temp_range': (self.params.optimal_temp_min_c, self.params.optimal_temp_max_c),
            'critical_temp_c': self.params.critical_temp_c,
            'current_temp_c': self.state.temp_c,
            'friction_coeff': self.state.friction_coeff,
            'wear_pct': self.state.wear_pct,
            'overheat_warning': self.state.overheat_warning,
            'cold_warning': self.state.cold_warning,
        }
