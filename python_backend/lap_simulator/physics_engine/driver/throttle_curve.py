"""
Throttle Curve - Curva Gas F1 2025

Modello curva gas:
- Curva gas in uscita curva
- Progressione gas
- Effetti su uscita curva

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np


@dataclass
class ThrottleCurveState:
    """Stato curva gas."""
    throttle_position: float  # 0.0-1.0 posizione gas
    torque_nm: float  # Nm coppia
    power_kw: float  # kW potenza
    acceleration_ms2: float  # m/s² accelerazione
    time_to_full_throttle_s: float  # s tempo a gas pieno


class ThrottleCurve:
    """
    Curva gas F1 2025
    
    Calcola curva gas in uscita curva:
    - Progressione gas
    - Torque curve
    - Accelerazione
    
    Formula:
    throttle = f(time, curve_exit)
    torque = f(throttle, rpm)
    power = torque × rpm
    
    Effetti:
    - Gas troppo presto: spin, perdita controllo
    - Gas troppo tardi: uscita lenta
    - Progressione ottimale: uscita veloce e controllata
    """
    
    def __init__(
        self,
        max_torque_nm: float = 500.0,  # Nm coppia massima
        max_power_kw: float = 750.0,  # kW potenza massima
        rpm_range: Tuple[float, float] = (8000.0, 15000.0),  # min/max rpm
        throttle_response: float = 0.8,  # 0.0-1.0 risposta gas
    ):
        """
        Inizializza modello curva gas
        
        Args:
            max_torque_nm: Nm coppia massima
            max_power_kw: kW potenza massima
            rpm_range: (min, max) rpm
            throttle_response: 0.0-1.0 risposta gas
        """
        self.max_torque_nm = max_torque_nm
        self.max_power_kw = max_power_kw
        self.rpm_range = rpm_range
        self.throttle_response = throttle_response
        
        # Stato corrente
        self.optimal_curve = self._calculate_optimal_curve()
    
    def _calculate_optimal_curve(self) -> Dict:
        """
        Calcola curva gas ottimale
        
        Returns:
            Dict con parametri curva gas ottimale
        """
        # Curva gas ottimale = progressione esponenziale
        # Gas lento all'inizio, veloce alla fine
        
        return {
            'curve_type': 'exponential',
            'time_to_full_s': 2.0,  # 2 secondi a gas pieno
            'throttle_at_50_pct_s': 0.3,  # 30% a metà curva
            'throttle_at_75_pct_s': 0.7,  # 70% a 3/4 curva
        }
    
    def calculate_throttle_curve(
        self,
        curve_progress: float,
        time_elapsed_s: float,
        max_time_s: float = 3.0,
    ) -> ThrottleCurveState:
        """
        Calcola curva gas
        
        Args:
            curve_progress: 0.0-1.0 progressione curva
            time_elapsed_s: s tempo trascorso
            max_time_s: s tempo totale curva
        
        Returns:
            ThrottleCurveState con stato gas
        """
        # Normalizza tempo
        if max_time_s > 0:
            normalized_time = time_elapsed_s / max_time_s
        else:
            normalized_time = 0.0
        
        normalized_time = np.clip(normalized_time, 0.0, 1.0)
        
        # Curva gas esponenziale
        # throttle = (normalized_time)^response
        throttle = normalized_time ** (1.0 / self.throttle_response)
        throttle = np.clip(throttle, 0.0, 1.0)
        
        # Calcola coppia
        # Torque = max_torque × throttle
        torque = self.max_torque_nm * throttle
        
        # Calcola potenza
        # Power = torque × rpm × 2π/60
        avg_rpm = (self.rpm_range[0] + self.rpm_range[1]) / 2.0
        power = torque * avg_rpm * 2.0 * np.pi / 60.0 / 1000.0  # kW
        power = np.clip(power, 0.0, self.max_power_kw)
        
        # Calcola accelerazione
        # a = F/m = (torque × gear_ratio) / (radius × mass)
        # Semplificato: a = power / (mass × v)
        mass_kg = 800.0  # massa F1
        v = 50.0  # velocità media (m/s)
        acceleration = power * 1000.0 / (mass_kg * v)  # m/s²
        
        # Tempo a gas pieno
        time_to_full_s = max_time_s * (1.0 - normalized_time)
        
        return ThrottleCurveState(
            throttle_position=throttle,
            torque_nm=torque,
            power_kw=power,
            acceleration_ms2=acceleration,
            time_to_full_throttle_s=time_to_full_s,
        )
    
    def get_throttle_at_progress(
        self,
        curve_progress: float,
    ) -> float:
        """
        Calcola posizione gas a progressione
        
        Args:
            curve_progress: 0.0-1.0 progressione curva
        
        Returns:
            0.0-1.0 posizione gas
        """
        # Curva gas esponenziale
        throttle = curve_progress ** (1.0 / self.throttle_response)
        return np.clip(throttle, 0.0, 1.0)
    
    def get_optimal_curve(
        self,
        max_time_s: float = 3.0,
    ) -> Dict:
        """
        Calcola curva gas ottimale
        
        Args:
            max_time_s: s tempo totale curva
        
        Returns:
            Dict con parametri curva gas ottimale
        """
        # Calcola throttle a varie progressioni
        progressions = [0.25, 0.5, 0.75, 1.0]
        throttle_values = [self.get_throttle_at_progress(p) for p in progressions]
        
        return {
            'curve_type': 'exponential',
            'max_time_s': max_time_s,
            'throttle_at_25_pct': throttle_values[0],
            'throttle_at_50_pct': throttle_values[1],
            'throttle_at_75_pct': throttle_values[2],
            'throttle_at_100_pct': throttle_values[3],
        }
    
    def adjust_throttle_curve(
        self,
        throttle_response: float,
    ) -> None:
        """
        Regola curva gas
        
        Args:
            throttle_response: 0.0-1.0 risposta gas
        """
        self.throttle_response = np.clip(throttle_response, 0.1, 2.0)
    
    def analyze_throttle(
        self,
        curve_progress: float,
        time_elapsed_s: float,
        max_time_s: float = 3.0,
    ) -> Dict:
        """
        Analizza curva gas
        
        Args:
            curve_progress: 0.0-1.0 progressione curva
            time_elapsed_s: s tempo trascorso
            max_time_s: s tempo totale curva
        
        Returns:
            Dict con analisi gas
        """
        state = self.calculate_throttle_curve(curve_progress, time_elapsed_s, max_time_s)
        
        return {
            'curve_progress': curve_progress,
            'time_elapsed_s': time_elapsed_s,
            'throttle_position': state.throttle_position,
            'torque_nm': state.torque_nm,
            'power_kw': state.power_kw,
            'acceleration_ms2': state.acceleration_ms2,
        }
    
    def get_state(
        self,
        curve_progress: float,
        time_elapsed_s: float,
        max_time_s: float = 3.0,
    ) -> Dict:
        """Restituisce stato curva gas."""
        state = self.calculate_throttle_curve(curve_progress, time_elapsed_s, max_time_s)
        
        return {
            'throttle_position': state.throttle_position,
            'torque_nm': state.torque_nm,
            'power_kw': state.power_kw,
            'acceleration_ms2': state.acceleration_ms2,
            'time_to_full_throttle_s': state.time_to_full_throttle_s,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo curva gas."""
        return {
            'max_torque_nm': self.max_torque_nm,
            'max_power_kw': self.max_power_kw,
            'rpm_range': self.rpm_range,
            'throttle_response': self.throttle_response,
            'optimal_curve': self.optimal_curve,
        }
