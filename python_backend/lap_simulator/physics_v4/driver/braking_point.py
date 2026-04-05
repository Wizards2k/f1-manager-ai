"""
Braking Point - Punto Frenata F1 2025

Modello punto frenata:
- Individuazione punto di frenata ottimale
- Effetti su tempo giro
- Adattamento a condizioni

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np


@dataclass
class BrakingPointState:
    """Stato punto frenata."""
    braking_point_m: float  # m distanza da curva
    braking_distance_m: float  # m distanza frenata
    max_speed_kph: float  # kph velocità massima
    target_speed_kph: float  # kph velocità target
    braking_time_s: float  # s tempo frenata
    deceleration_ms2: float  # m/s² decelerazione


class BrakingPoint:
    """
    Punto frenata F1 2025
    
    Calcola punto di frenata ottimale:
    - Distanza da curva
    - Velocità massima
    - Decelerazione richiesta
    
    Formula:
    d = (v² - v_target²) / (2 × a)
    
    Effetti:
    - Punto tardi: velocità alta, rischio understeer
    - Punto presto: velocità bassa, tempo perso
    - Punto ottimale: velocità massima entro limite
    """
    
    def __init__(
        self,
        deceleration_ms2: float = 12.0,  # m/s² decelerazione massima
        safety_margin: float = 0.95,  # margine sicurezza
        brake_bias: float = 0.55,  # 0.0-1.0 bias frenata frontale
    ):
        """
        Inizializza modello punto frenata
        
        Args:
            deceleration_ms2: m/s² decelerazione massima
            safety_margin: margine sicurezza (0.0-1.0)
            brake_bias: 0.0-1.0 bias frenata frontale
        """
        self.deceleration_ms2 = deceleration_ms2
        self.safety_margin = safety_margin
        self.brake_bias = brake_bias
        
        # Stato corrente
        self.optimal_braking_point = None
    
    def calculate_braking_point(
        self,
        entry_speed_kph: float,
        target_speed_kph: float,
        curve_radius_m: float,
    ) -> BrakingPointState:
        """
        Calcola punto di frenata ottimale
        
        Args:
            entry_speed_kph: kph velocità in ingresso
            target_speed_kph: kph velocità target in curva
            curve_radius_m: m raggio curva
        
        Returns:
            BrakingPointState con stato frenata
        """
        # Converti velocità in m/s
        v_entry = entry_speed_kph / 3.6
        v_target = target_speed_kph / 3.6
        
        # Calcola distanza frenata
        # d = (v² - v_target²) / (2 × a)
        braking_distance = (v_entry ** 2 - v_target ** 2) / (2.0 * self.deceleration_ms2)
        
        # Calcola tempo frenata
        # t = (v - v_target) / a
        braking_time = (v_entry - v_target) / self.deceleration_ms2
        
        # Calcola decelerazione effettiva (con margine)
        actual_deceleration = self.deceleration_ms2 * self.safety_margin
        
        # Calcola velocità massima entro limite
        # v_max = sqrt(grip × g × r)
        grip = 1.7  # g grip pneumatico
        v_max = np.sqrt(grip * 9.81 * curve_radius_m)
        max_speed_kph = v_max * 3.6
        
        # Limita a velocità entry
        max_speed_kph = min(max_speed_kph, entry_speed_kph)
        
        return BrakingPointState(
            braking_point_m=braking_distance,
            braking_distance_m=braking_distance,
            max_speed_kph=max_speed_kph,
            target_speed_kph=target_speed_kph,
            braking_time_s=braking_time,
            deceleration_ms2=actual_deceleration,
        )
    
    def calculate_braking_zone(
        self,
        entry_speed_kph: float,
        target_speed_kph: float,
        curve_radius_m: float,
        braking_zones: List[Tuple[float, float]] = None,
    ) -> Dict:
        """
        Calcola zona di frenata
        
        Args:
            entry_speed_kph: kph velocità in ingresso
            target_speed_kph: kph velocità target
            curve_radius_m: m raggio curva
            braking_zones: Lista [(start_m, end_m)] zone frenata
        
        Returns:
            Dict con zona frenata
        """
        state = self.calculate_braking_point(entry_speed_kph, target_speed_kph, curve_radius_m)
        
        # Calcola zona frenata
        braking_start = state.braking_point_m
        braking_end = 0.0  # Inizia da curva
        
        # Aggiungi zona a lista se fornita
        if braking_zones is not None:
            braking_zones.append((braking_start, braking_end))
        
        return {
            'braking_start_m': braking_start,
            'braking_end_m': braking_end,
            'braking_distance_m': state.braking_distance_m,
            'max_speed_kph': state.max_speed_kph,
            'target_speed_kph': state.target_speed_kph,
            'braking_time_s': state.braking_time_s,
        }
    
    def get_optimal_braking_point(
        self,
        entry_speed_kph: float,
        target_speed_kph: float,
        curve_radius_m: float,
    ) -> Dict:
        """
        Calcola punto frenata ottimale
        
        Args:
            entry_speed_kph: kph velocità in ingresso
            target_speed_kph: kph velocità target
            curve_radius_m: m raggio curva
        
        Returns:
            Dict con punto frenata ottimale
        """
        state = self.calculate_braking_point(entry_speed_kph, target_speed_kph, curve_radius_m)
        
        return {
            'braking_point_m': state.braking_point_m,
            'braking_distance_m': state.braking_distance_m,
            'max_speed_kph': state.max_speed_kph,
            'target_speed_kph': state.target_speed_kph,
            'braking_time_s': state.braking_time_s,
            'deceleration_ms2': state.deceleration_ms2,
        }
    
    def adjust_braking_point(
        self,
        braking_point_m: float,
        adjustment: float,
    ) -> float:
        """
        Regola punto frenata
        
        Args:
            braking_point_m: m punto frenata corrente
            adjustment: m regolazione (+/-)
        
        Returns:
            m nuovo punto frenata
        """
        new_point = braking_point_m + adjustment
        return max(0.0, new_point)  # Non prima di curva
    
    def analyze_braking(
        self,
        entry_speed_kph: float,
        target_speed_kph: float,
        curve_radius_m: float,
        braking_points: List[float] = None,
    ) -> Dict:
        """
        Analizza frenata
        
        Args:
            entry_speed_kph: kph velocità in ingresso
            target_speed_kph: kph velocità target
            curve_radius_m: m raggio curva
            braking_points: Lista punti frenata
        
        Returns:
            Dict con analisi frenata
        """
        state = self.calculate_braking_point(entry_speed_kph, target_speed_kph, curve_radius_m)
        
        # Aggiungi punto a lista se fornita
        if braking_points is not None:
            braking_points.append(state.braking_point_m)
        
        return {
            'entry_speed_kph': entry_speed_kph,
            'target_speed_kph': target_speed_kph,
            'curve_radius_m': curve_radius_m,
            'braking_point_m': state.braking_point_m,
            'braking_distance_m': state.braking_distance_m,
            'max_speed_kph': state.max_speed_kph,
            'braking_time_s': state.braking_time_s,
        }
    
    def get_state(
        self,
        entry_speed_kph: float,
        target_speed_kph: float,
        curve_radius_m: float,
    ) -> Dict:
        """Restituisce stato punto frenata."""
        state = self.calculate_braking_point(entry_speed_kph, target_speed_kph, curve_radius_m)
        
        return {
            'braking_point_m': state.braking_point_m,
            'braking_distance_m': state.braking_distance_m,
            'max_speed_kph': state.max_speed_kph,
            'target_speed_kph': state.target_speed_kph,
            'braking_time_s': state.braking_time_s,
            'deceleration_ms2': state.deceleration_ms2,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo punto frenata."""
        return {
            'deceleration_ms2': self.deceleration_ms2,
            'safety_margin': self.safety_margin,
            'brake_bias': self.brake_bias,
            'optimal_braking_point': self.optimal_braking_point,
        }
