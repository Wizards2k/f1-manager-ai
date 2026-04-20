"""
Thermal Model - Modello termico Power Unit (Physics V4)

Implementa il thermal clipping secondo ERS-ThermalClipping.md:
- Riscaldamento Joule (quadratico in potenza)
- Raffreddamento convettivo (dipende da velocità)
- Derating progressivo (102°C - 122°C)

NOTA: Modulo V4 standalone, non dipende da power_unit.py V1
"""

from dataclasses import dataclass
from typing import Dict
import numpy as np


@dataclass
class ThermalState:
    """Stato termico componenti PU."""
    ice_temp_c: float  # °C temperatura ICE
    ers_temp_c: float  # °C temperatura ERS
    ice_derating: float  # 0.0-1.0 fattore derating ICE
    ers_derating: float  # 0.0-1.0 fattore derating ERS
    ers_clipping_active: bool  # Flag clipping attivo


class ThermalModel:
    """
    Modello termico F1 2025
    
    Specifiche da ERS-ThermalClipping.md:
    
    ICE:
    - T_warning: 130°C
    - T_critical: 140°C
    - Derating: 40% riduzione tra warning e critical
    
    ERS:
    - T_limit: 102°C (inizio clipping)
    - T_max: 122°C (shutdown totale)
    - Derating: lineare tra 102-122°C
    
    Equazioni:
    - q_gen = k_joule × P² (riscaldamento Joule)
    - q_cool = h_v × v × (T - T_amb) (raffreddamento convettivo)
    - ΔT = (q_gen - q_cool) / C_th (variazione temperatura)
    """
    
    # Costanti termiche ERS (da ERS-ThermalClipping.md)
    ERS_T_LIMIT = 102.0       # °C inizio clipping
    ERS_T_MAX = 122.0         # °C shutdown totale
    ERS_K_JOULE = 0.000045    # Coefficiente Joule
    ERS_H_V = 0.0025          # Coeff. raffreddamento convettivo
    ERS_C_TH = 18.0           # kJ/K capacità termica
    
    # Costanti termiche ICE
    ICE_T_WARNING = 130.0     # °C warning
    ICE_T_CRITICAL = 140.0    # °C critical
    ICE_K_JOULE = 0.000035    # Coefficiente Joule (leggermente inferiore)
    ICE_H_V = 0.0030          # Coeff. raffreddamento (migliore cooling)
    ICE_C_TH = 25.0           # kJ/K capacità termica (più massa)
    
    def __init__(self, ambient_temp: float = 25.0):
        """
        Inizializza modello termico
        
        Args:
            ambient_temp: °C temperatura ambiente
        """
        self.ambient_temp = ambient_temp
        
        # Temperature iniziali (ambiente)
        self.ice_temp = ambient_temp
        self.ers_temp = ambient_temp
    
    def calculate_ers_derating(self, ers_power_kw: float, v_car_kph: float, dt: float) -> float:
        """
        Calcola derating ERS per thermal clipping
        
        Args:
            ers_power_kw: kW potenza ERS erogata
            v_car_kph: kph velocità vettura
            dt: secondi timestep
        
        Returns:
            float fattore derating (0.0-1.0)
        """
        # Riscaldamento Joule (quadratico in potenza)
        q_gen = self.ERS_K_JOULE * (ers_power_kw ** 2)  # kW → kJ/s
        
        # Raffreddamento convettivo (dipende da velocità)
        delta_t = max(self.ers_temp - self.ambient_temp, 0.0)
        v_factor = v_car_kph / 360.0  # Normalizza a ~360 kph max
        q_cool = self.ERS_H_V * v_factor * delta_t  # kJ/s
        
        # Variazione temperatura
        delta_temp = ((q_gen - q_cool) / self.ERS_C_TH) * dt
        
        # Aggiorna temperatura
        self.ers_temp = np.clip(self.ers_temp + delta_temp, self.ambient_temp, 150.0)
        
        # Calcola fattore derating
        if self.ers_temp < self.ERS_T_LIMIT:
            # Zona safe: nessun derating
            return 1.0
        elif self.ers_temp >= self.ERS_T_MAX:
            # Shutdown totale
            return 0.0
        else:
            # Derating lineare tra 102-122°C
            derating = 1.0 - (self.ers_temp - self.ERS_T_LIMIT) / (self.ERS_T_MAX - self.ERS_T_LIMIT)
            return np.clip(derating, 0.0, 1.0)
    
    def calculate_ice_derating(self, ice_power_kw: float, v_car_kph: float, dt: float) -> float:
        """
        Calcola derating ICE per surriscaldamento
        
        Args:
            ice_power_kw: kW potenza ICE erogata
            v_car_kph: kph velocità vettura
            dt: secondi timestep
        
        Returns:
            float fattore derating (0.0-1.0)
        """
        # Riscaldamento (proporzionale a potenza)
        q_gen = self.ICE_K_JOULE * ice_power_kw  # kJ/s
        
        # Raffreddamento convettivo
        delta_t = max(self.ice_temp - self.ambient_temp, 0.0)
        v_factor = v_car_kph / 360.0
        q_cool = self.ICE_H_V * v_factor * delta_t  # kJ/s
        
        # Variazione temperatura
        delta_temp = ((q_gen - q_cool) / self.ICE_C_TH) * dt
        
        # Aggiorna temperatura
        self.ice_temp = np.clip(self.ice_temp + delta_temp, self.ambient_temp, 200.0)
        
        # Calcola fattore derating
        if self.ice_temp < self.ICE_T_WARNING:
            # Zona safe
            return 1.0
        elif self.ice_temp >= self.ICE_T_CRITICAL:
            # Critical: 60% potenza residua
            return 0.6
        else:
            # Derating lineare tra 130-140°C
            excess = self.ice_temp - self.ICE_T_WARNING
            range_c = self.ICE_T_CRITICAL - self.ICE_T_WARNING
            derating = 1.0 - (excess / range_c) * 0.4
            return np.clip(derating, 0.6, 1.0)
    
    def get_thermal_state(self, ers_power_kw: float, ice_power_kw: float, v_car_kph: float) -> 'ThermalState':
        """
        Restituisce stato termico corrente
        
        Args:
            ers_power_kw: kW potenza ERS
            ice_power_kw: kW potenza ICE
            v_car_kph: kph velocità vettura
        
        Returns:
            ThermalState con temperature e derating
        """
        # Nota: derating già calcolato negli update precedenti
        ice_derating = self.calculate_ice_derating(ice_power_kw, v_car_kph, 0.0)
        ers_derating = self.calculate_ers_derating(ers_power_kw, v_car_kph, 0.0)
        
        return ThermalState(
            ice_temp_c=self.ice_temp,
            ers_temp_c=self.ers_temp,
            ice_derating=ice_derating,
            ers_derating=ers_derating,
            ers_clipping_active=(ers_derating < 0.95)
        )
    
    def reset(self, ambient_temp: float = None):
        """
        Resetta temperature a ambiente
        
        Args:
            ambient_temp: °C nuova temperatura ambiente (opzionale)
        """
        if ambient_temp is not None:
            self.ambient_temp = ambient_temp
        
        self.ice_temp = self.ambient_temp
        self.ers_temp = self.ambient_temp
    
    def set_ambient_temp(self, temp_c: float):
        """Imposta temperatura ambiente."""
        self.ambient_temp = temp_c
    
    def get_summary(self) -> Dict:
        """Riepilogo parametri termici."""
        return {
            'ers_t_limit_c': self.ERS_T_LIMIT,
            'ers_t_max_c': self.ERS_T_MAX,
            'ice_t_warning_c': self.ICE_T_WARNING,
            'ice_t_critical_c': self.ICE_T_CRITICAL,
            'ambient_temp_c': self.ambient_temp,
            'current_ice_temp_c': self.ice_temp,
            'current_ers_temp_c': self.ers_temp,
        }
