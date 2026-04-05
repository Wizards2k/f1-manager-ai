"""
Driving Line - Traiettoria Guida F1 2025

Modello traiettoria:
- Selezione traiettoria ottimale in curva
- Linea inside/outside/inside
- Effetti su raggio e velocità

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np


@dataclass
class DrivingLineState:
    """Stato traiettoria."""
    line_type: str  # inside/outside/center
    radius_m: float  # m raggio effettivo
    speed_kph: float  # kph velocità consigliata
    distance_saved_m: float  # m distanza risparmiata
    time_saved_s: float  # s tempo risparmiato


class DrivingLine:
    """
    Traiettoria guida F1 2025
    
    Calcola traiettoria ottimale in curva:
    - Inside line: raggio minore, velocità bassa
    - Outside line: raggio maggiore, velocità alta
    - Inside-outside-inside: traiettoria a cappio
    
    Formula:
    v = sqrt(grip × g × radius)
    
    Effetti:
    - Linea inside: raggio piccolo, velocità bassa, curva chiusa
    - Linea outside: raggio grande, velocità alta, curva aperta
    - Inside-outside-inside: ottimale per velocità media
    """
    
    def __init__(
        self,
        track_width_m: float = 15.0,  # m larghezza pista
        tyre_grip: float = 1.7,  # g grip pneumatico
        safety_margin: float = 0.95,  # margine sicurezza
    ):
        """
        Inizializza modello traiettoria
        
        Args:
            track_width_m: m larghezza pista
            tyre_grip: g grip pneumatico
            safety_margin: margine sicurezza (0.0-1.0)
        """
        self.track_width_m = track_width_m
        self.tyre_grip = tyre_grip
        self.safety_margin = safety_margin
        
        # Stato corrente
        self.optimal_line = self._calculate_optimal_line()
    
    def _calculate_optimal_line(self) -> Dict:
        """
        Calcola traiettoria ottimale
        
        Returns:
            Dict con parametri traiettoria ottimale
        """
        # Traiettoria ottimale = inside-outside-inside
        # Raggio ottimale = track_width / 2
        optimal_radius = self.track_width_m / 2.0
        
        # Velocità ottimale
        v_opt = np.sqrt(self.tyre_grip * 9.81 * optimal_radius)
        speed_opt_kph = v_opt * 3.6
        
        return {
            'line_type': 'inside-outside-inside',
            'radius_m': optimal_radius,
            'speed_kph': speed_opt_kph,
            'distance_factor': 1.0,  # raggio pista
        }
    
    def calculate_line(
        self,
        curve_radius_m: float,
        curve_angle_deg: float,
        line_type: str = 'optimal',
    ) -> DrivingLineState:
        """
        Calcola traiettoria in curva
        
        Args:
            curve_radius_m: m raggio curva
            curve_angle_deg: ° angolo curva
            line_type: inside/outside/center/optimal
        
        Returns:
            DrivingLineState con stato traiettoria
        """
        # Calcola raggio effettivo in base alla linea
        if line_type == 'inside':
            # Linea inside = raggio minore
            effective_radius = curve_radius_m * 0.85
            line_type_name = 'inside'
        elif line_type == 'outside':
            # Linea outside = raggio maggiore
            effective_radius = curve_radius_m * 1.15
            line_type_name = 'outside'
        elif line_type == 'center':
            # Linea center = raggio medio
            effective_radius = curve_radius_m * 1.0
            line_type_name = 'center'
        else:  # optimal
            # Linea ottimale = inside-outside-inside
            effective_radius = curve_radius_m * 0.95
            line_type_name = 'inside-outside-inside'
        
        # Calcola velocità massima
        v_max = np.sqrt(self.tyre_grip * 9.81 * effective_radius) * self.safety_margin
        speed_kph = v_max * 3.6
        
        # Calcola distanza risparmiata
        # Distanza = raggio × angolo (in radianti)
        angle_rad = np.deg2rad(curve_angle_deg)
        distance = effective_radius * angle_rad
        
        # Distanza risparmiata rispetto a raggio pista
        track_distance = curve_radius_m * angle_rad
        distance_saved = track_distance - distance
        
        # Tempo risparmiato
        # t = d / v
        time_saved = distance_saved / (v_max * 0.9)  # stima
        time_saved = max(0.0, time_saved)
        
        return DrivingLineState(
            line_type=line_type_name,
            radius_m=effective_radius,
            speed_kph=speed_kph,
            distance_saved_m=distance_saved,
            time_saved_s=time_saved,
        )
    
    def get_line_speed(
        self,
        line_type: str,
        curve_radius_m: float,
    ) -> float:
        """
        Calcola velocità per traiettoria
        
        Args:
            line_type: inside/outside/center/optimal
            curve_radius_m: m raggio curva
        
        Returns:
            kph velocità
        """
        state = self.calculate_line(curve_radius_m, 90.0, line_type)
        return state.speed_kph
    
    def get_optimal_line(
        self,
        curve_radius_m: float,
    ) -> Dict:
        """
        Calcola traiettoria ottimale
        
        Args:
            curve_radius_m: m raggio curva
        
        Returns:
            Dict con parametri traiettoria ottimale
        """
        state = self.calculate_line(curve_radius_m, 90.0, 'optimal')
        
        return {
            'line_type': state.line_type,
            'radius_m': state.radius_m,
            'speed_kph': state.speed_kph,
            'distance_saved_m': state.distance_saved_m,
            'time_saved_s': state.time_saved_s,
        }
    
    def analyze_curve(
        self,
        curve_radius_m: float,
        curve_angle_deg: float,
    ) -> Dict:
        """
        Analizza curva e calcola traiettorie
        
        Args:
            curve_radius_m: m raggio curva
            curve_angle_deg: ° angolo curva
        
        Returns:
            Dict con analisi traiettorie
        """
        lines = ['inside', 'center', 'outside', 'optimal']
        results = {}
        
        for line in lines:
            state = self.calculate_line(curve_radius_m, curve_angle_deg, line)
            results[line] = {
                'radius_m': state.radius_m,
                'speed_kph': state.speed_kph,
                'distance_saved_m': state.distance_saved_m,
                'time_saved_s': state.time_saved_s,
            }
        
        return results
    
    def get_state(
        self,
        curve_radius_m: float,
        curve_angle_deg: float,
        line_type: str = 'optimal',
    ) -> Dict:
        """Restituisce stato traiettoria."""
        state = self.calculate_line(curve_radius_m, curve_angle_deg, line_type)
        
        return {
            'line_type': state.line_type,
            'radius_m': state.radius_m,
            'speed_kph': state.speed_kph,
            'distance_saved_m': state.distance_saved_m,
            'time_saved_s': state.time_saved_s,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo traiettoria."""
        return {
            'track_width': self.track_width_m,
            'tyre_grip': self.tyre_grip,
            'safety_margin': self.safety_margin,
            'optimal_line': self.optimal_line,
        }
