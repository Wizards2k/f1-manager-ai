"""
Brake Wear - Usura freni F1 2025

Modello fisico usura:
- Usura meccanica (pressione, attrito)
- Usura termica (ossidazione >1000°C)
- Usura da fatica termica (cicli caldo/freddo)
- Wear sensors (100% = sostituzione)

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict
import numpy as np


@dataclass
class BrakeWearState:
    """Stato usura freno."""
    wear_pct: float  # % usura totale (0-100)
    thickness_mm: float  # mm spessore residuo
    oxidation_wear_pct: float  # % usura da ossidazione
    mechanical_wear_pct: float  # % usura meccanica
    thermal_fatigue_cycles: int  # numero cicli termici
    replacement_needed: bool  # Flag sostituzione necessaria


class BrakeWear:
    """
    Usura freni F1 2025
    
    Meccanismi usura:
    1. Meccanica: pressione × attrito × distanza
    2. Termica: ossidazione >1000°C (esponenziale)
    3. Fatica termica: cicli riscaldamento/raffreddamento
    
    Vita utile:
    - Gara: 1-2 gare (usura 30-50%)
    - Qualifica: usura minima (<5%)
    - Sostituzione: >80% usura
    
    Spessore:
    - Nuovo: 28 mm
    - Minimo: 20 mm
    - Usura max: 8 mm
    """
    
    # Parametri fisici
    THICKNESS_NEW_MM = 28.0    # mm spessore nuovo
    THICKNESS_MIN_MM = 20.0    # mm spessore minimo
    MAX_WEAR_MM = 8.0          # mm usura massima
    
    # Soglie usura
    WEAR_WARNING = 70.0        # % warning
    WEAR_CRITICAL = 80.0       # % critico (sostituzione)
    WEAR_MAX = 100.0           # % massimo (rottura)
    
    def __init__(self, is_front: bool = True):
        """
        Inizializza usura freno
        
        Args:
            is_front: True = anteriore, False = posteriore
        """
        self.is_front = is_front
        
        # Stato iniziale (freno nuovo)
        self.state = BrakeWearState(
            wear_pct=0.0,
            thickness_mm=self.THICKNESS_NEW_MM,
            oxidation_wear_pct=0.0,
            mechanical_wear_pct=0.0,
            thermal_fatigue_cycles=0,
            replacement_needed=False,
        )
        
        # Coefficienti usura (anteriori si usurano di più)
        self.mechanical_wear_coeff = 0.0001 if is_front else 0.00008
        self.oxidation_coeff = 0.001 if is_front else 0.0012
    
    def calculate_mechanical_wear(
        self,
        brake_pressure_bar: float,
        friction_coeff: float,
        distance_m: float,
        dt_s: float
    ) -> float:
        """
        Calcola usura meccanica
        
        Args:
            brake_pressure_bar: bar pressione frenante
            friction_coeff: coefficiente attrito
            distance_m: metri percorsi
            dt_s: secondi timestep
        
        Returns:
            % usura meccanica
        """
        # Usura base (pressione × attrito × distanza)
        # Formula semplificata: wear = k × P × mu × d
        wear = (
            self.mechanical_wear_coeff *
            brake_pressure_bar *
            friction_coeff *
            distance_m / 1000.0  # Normalizza
        )
        
        # Fattore velocità (più veloce = più usura)
        # wear *= (1.0 + 0.1 * v_car_kph / 300.0)
        
        return wear
    
    def calculate_oxidation_wear(self, brake_temp_c: float, dt_s: float) -> float:
        """
        Calcola usura da ossidazione (solo >1000°C)
        
        Args:
            brake_temp_c: °C temperatura freno
            dt_s: secondi timestep
        
        Returns:
            % usura da ossidazione
        """
        if brake_temp_c < 1000.0:
            return 0.0
        
        # Ossidazione aumenta esponenzialmente
        excess_temp = brake_temp_c - 1000.0
        oxidation_factor = 1.0 + (excess_temp / 100.0) ** 1.5
        
        # Usura = coeff × factor × dt
        wear = self.oxidation_coeff * oxidation_factor * dt_s
        
        return wear
    
    def calculate_thermal_fatigue(self, temp_c: float, dt_s: float) -> int:
        """
        Calcola cicli di fatica termica
        
        Args:
            temp_c: °C temperatura freno
            dt_s: secondi timestep
        
        Returns:
            numero cicli accumulati
        """
        # Conta cicli >800°C → <200°C
        if temp_c > 800.0:
            # Riscaldamento: conta mezzo ciclo
            return 0
        elif temp_c < 200.0:
            # Raffreddamento: conta mezzo ciclo
            return 1
        else:
            return 0
    
    def update_wear(
        self,
        brake_pressure_bar: float,
        friction_coeff: float,
        v_car_kph: float,
        brake_temp_c: float,
        dt_s: float
    ):
        """
        Aggiorna usura totale
        
        Args:
            brake_pressure_bar: bar pressione frenante
            friction_coeff: coefficiente attrito
            v_car_kph: kph velocità vettura
            brake_temp_c: °C temperatura freno
            dt_s: secondi timestep
        """
        # Distanza percorsa
        distance_m = v_car_kph * dt_s / 3.6
        
        # 1. Usura meccanica
        mech_wear = self.calculate_mechanical_wear(
            brake_pressure_bar, friction_coeff, distance_m, dt_s
        )
        
        # 2. Usura da ossidazione
        ox_wear = self.calculate_oxidation_wear(brake_temp_c, dt_s)
        
        # 3. Fatica termica
        fatigue_cycles = self.calculate_thermal_fatigue(brake_temp_c, dt_s)
        
        # Aggiorna stato
        self.state.mechanical_wear_pct += mech_wear
        self.state.oxidation_wear_pct += ox_wear
        self.state.thermal_fatigue_cycles += fatigue_cycles
        
        # Usura totale
        self.state.wear_pct = self.state.mechanical_wear_pct + self.state.oxidation_wear_pct
        
        # Spessore residuo
        wear_mm = (self.state.wear_pct / 100.0) * self.MAX_WEAR_MM
        self.state.thickness_mm = self.THICKNESS_NEW_MM - wear_mm
        
        # Flag sostituzione
        self.state.replacement_needed = self.state.wear_pct >= self.WEAR_CRITICAL
        
        # Clamp
        self.state.wear_pct = np.clip(self.state.wear_pct, 0.0, self.WEAR_MAX)
        self.state.thickness_mm = np.clip(self.state.thickness_mm, 0.0, self.THICKNESS_NEW_MM)
    
    def get_remaining_life_laps(self, avg_wear_per_lap: float = None) -> float:
        """
        Stima giri residui
        
        Args:
            avg_wear_per_lap: % usura media per giro (default: 0.5)
        
        Returns:
            float giri stimati residui
        """
        if avg_wear_per_lap is None:
            # Stima basata su usura attuale
            avg_wear_per_lap = 0.5 if self.is_front else 0.4
        
        if avg_wear_per_lap <= 0:
            return 999.0
        
        wear_remaining = self.WEAR_CRITICAL - self.state.wear_pct
        laps_remaining = wear_remaining / avg_wear_per_lap
        
        return max(0.0, laps_remaining)
    
    def get_state(self) -> 'BrakeWearState':
        """Restituisce stato corrente."""
        return self.state
    
    def reset(self):
        """Resetta usura a freno nuovo."""
        self.state = BrakeWearState(
            wear_pct=0.0,
            thickness_mm=self.THICKNESS_NEW_MM,
            oxidation_wear_pct=0.0,
            mechanical_wear_pct=0.0,
            thermal_fatigue_cycles=0,
            replacement_needed=False,
        )
    
    def get_summary(self) -> Dict:
        """Riepilogo usura."""
        return {
            'is_front': self.is_front,
            'wear_pct': self.state.wear_pct,
            'thickness_mm': self.state.thickness_mm,
            'mechanical_wear_pct': self.state.mechanical_wear_pct,
            'oxidation_wear_pct': self.state.oxidation_wear_pct,
            'thermal_fatigue_cycles': self.state.thermal_fatigue_cycles,
            'replacement_needed': self.state.replacement_needed,
            'remaining_life_laps': self.get_remaining_life_laps(),
        }
