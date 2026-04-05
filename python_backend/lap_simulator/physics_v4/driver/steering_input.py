"""
Steering Input - Input Sterzo F1 2025

Modello input sterzo:
- Input sterzo in curva
- Curve di sterzo
- Effetti su handling

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np


@dataclass
class SteeringInputState:
    """Stato input sterzo."""
    steering_angle_deg: float  # ° angolo sterzo
    steering_rate_deg_s: float  # °/s velocità sterzo
    steering_torque_nm: float  # Nm coppia sterzo
    front_wheel_angle_deg: float  # ° angolo ruote frontali
    rear_wheel_angle_deg: float  # ° angolo ruote posteriori (steer rear)


class SteeringInput:
    """
    Input sterzo F1 2025
    
    Calcola input sterzo in curva:
    - Angolo sterzo
    - Velocità sterzo
    - Torque sterzo
    
    Formula:
    steering_angle = f(curve_radius, speed)
    steering_rate = f(steering_angle, time)
    
    Effetti:
    - Sterzo troppo veloce: instabilità
    - Sterzo troppo lento: ingresso lento
    - Input ottimale: ingresso fluido e controllato
    """
    
    def __init__(
        self,
        max_steering_angle_deg: float = 20.0,  # ° angolo massimo
        steering_ratio: float = 12.0,  # rapporto sterzo
        front_steering: bool = True,  # sterzo frontale
        rear_steering: bool = False,  # sterzo posteriore
        rear_steering_angle_deg: float = 2.0,  # ° angolo sterzo posteriore
    ):
        """
        Inizializza modello input sterzo
        
        Args:
            max_steering_angle_deg: ° angolo massimo
            steering_ratio: rapporto sterzo
            front_steering: sterzo frontale
            rear_steering: sterzo posteriore
            rear_steering_angle_deg: ° angolo sterzo posteriore
        """
        self.max_steering_angle_deg = max_steering_angle_deg
        self.steering_ratio = steering_ratio
        self.front_steering = front_steering
        self.rear_steering = rear_steering
        self.rear_steering_angle_deg = rear_steering_angle_deg
        
        # Stato corrente
        self.optimal_steering = self._calculate_optimal_steering()
    
    def _calculate_optimal_steering(self) -> Dict:
        """
        Calcola input sterzo ottimale
        
        Returns:
            Dict con parametri sterzo ottimale
        """
        # Sterzo ottimale = curve sinusoidale
        # Ingresso fluido, uscita fluida
        
        return {
            'steering_type': 'sinusoidal',
            'time_to_max_angle_s': 1.0,  # 1 secondo a angolo massimo
            'max_angle_deg': self.max_steering_angle_deg,
        }
    
    def calculate_steering_input(
        self,
        curve_radius_m: float,
        speed_kph: float,
        curve_progress: float,
        time_elapsed_s: float = 0.0,
    ) -> SteeringInputState:
        """
        Calcola input sterzo
        
        Args:
            curve_radius_m: m raggio curva
            speed_kph: kph velocità
            curve_progress: 0.0-1.0 progressione curva
            time_elapsed_s: s tempo trascorso
        
        Returns:
            SteeringInputState con stato sterzo
        """
        # Calcola angolo sterzo richiesto
        # steering_angle = max_angle × (1 - curve_progress)
        # Meno sterzo alla fine curva
        max_angle = self.max_steering_angle_deg * (1.0 - curve_progress * 0.5)
        max_angle = max(max_angle, self.max_steering_angle_deg * 0.5)
        
        # Curva sterzo sinusoidale
        # angle = max_angle × sin(progress × π/2)
        steering_angle = max_angle * np.sin(curve_progress * np.pi / 2.0)
        
        # Calcola velocità sterzo
        # rate = angle / time
        if time_elapsed_s > 0:
            steering_rate = steering_angle / time_elapsed_s
        else:
            steering_rate = 0.0
        
        # Limita velocità sterzo
        max_rate = 30.0  # °/s
        steering_rate = np.clip(steering_rate, -max_rate, max_rate)
        
        # Calcola coppia sterzo
        # torque = steering_angle × torque_factor
        torque_factor = 0.5  # Nm/deg
        steering_torque = steering_angle * torque_factor
        
        # Calcola angolo ruote
        if self.front_steering:
            front_wheel_angle = steering_angle / self.steering_ratio
        else:
            front_wheel_angle = 0.0
        
        if self.rear_steering:
            rear_wheel_angle = self.rear_steering_angle_deg * (1.0 - curve_progress)
        else:
            rear_wheel_angle = 0.0
        
        return SteeringInputState(
            steering_angle_deg=steering_angle,
            steering_rate_deg_s=steering_rate,
            steering_torque_nm=steering_torque,
            front_wheel_angle_deg=front_wheel_angle,
            rear_wheel_angle_deg=rear_wheel_angle,
        )
    
    def get_steering_at_progress(
        self,
        curve_progress: float,
        curve_radius_m: float,
    ) -> float:
        """
        Calcola angolo sterzo a progressione
        
        Args:
            curve_progress: 0.0-1.0 progressione curva
            curve_radius_m: m raggio curva
        
        Returns:
            ° angolo sterzo
        """
        # Calcola angolo sterzo
        max_angle = self.max_steering_angle_deg * (1.0 - curve_progress * 0.5)
        max_angle = max(max_angle, self.max_steering_angle_deg * 0.5)
        
        # Curva sinusoidale
        steering_angle = max_angle * np.sin(curve_progress * np.pi / 2.0)
        
        return steering_angle
    
    def get_optimal_steering(
        self,
        curve_radius_m: float,
        speed_kph: float,
    ) -> Dict:
        """
        Calcola input sterzo ottimale
        
        Args:
            curve_radius_m: m raggio curva
            speed_kph: kph velocità
        
        Returns:
            Dict con input sterzo ottimale
        """
        # Calcola steering a varie progressioni
        progressions = [0.0, 0.25, 0.5, 0.75, 1.0]
        angles = [self.get_steering_at_progress(p, curve_radius_m) for p in progressions]
        
        return {
            'steering_type': 'sinusoidal',
            'curve_radius_m': curve_radius_m,
            'speed_kph': speed_kph,
            'angles_at_progress': list(zip(progressions, angles)),
        }
    
    def adjust_steering_input(
        self,
        max_angle_adjustment: float,
    ) -> None:
        """
        Regola input sterzo
        
        Args:
            max_angle_adjustment: ° regolazione angolo massimo
        """
        self.max_steering_angle_deg = np.clip(
            self.max_steering_angle_deg + max_angle_adjustment,
            5.0, 30.0
        )
    
    def analyze_steering(
        self,
        curve_radius_m: float,
        speed_kph: float,
        curve_progress: float,
        time_elapsed_s: float = 0.0,
    ) -> Dict:
        """
        Analizza input sterzo
        
        Args:
            curve_radius_m: m raggio curva
            speed_kph: kph velocità
            curve_progress: 0.0-1.0 progressione curva
            time_elapsed_s: s tempo trascorso
        
        Returns:
            Dict con analisi sterzo
        """
        state = self.calculate_steering_input(
            curve_radius_m, speed_kph, curve_progress, time_elapsed_s
        )
        
        return {
            'curve_radius_m': curve_radius_m,
            'speed_kph': speed_kph,
            'curve_progress': curve_progress,
            'steering_angle_deg': state.steering_angle_deg,
            'steering_rate_deg_s': state.steering_rate_deg_s,
            'steering_torque_nm': state.steering_torque_nm,
        }
    
    def get_state(
        self,
        curve_radius_m: float,
        speed_kph: float,
        curve_progress: float,
        time_elapsed_s: float = 0.0,
    ) -> Dict:
        """Restituisce stato input sterzo."""
        state = self.calculate_steering_input(
            curve_radius_m, speed_kph, curve_progress, time_elapsed_s
        )
        
        return {
            'steering_angle_deg': state.steering_angle_deg,
            'steering_rate_deg_s': state.steering_rate_deg_s,
            'steering_torque_nm': state.steering_torque_nm,
            'front_wheel_angle_deg': state.front_wheel_angle_deg,
            'rear_wheel_angle_deg': state.rear_wheel_angle_deg,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo input sterzo."""
        return {
            'max_steering_angle_deg': self.max_steering_angle_deg,
            'steering_ratio': self.steering_ratio,
            'front_steering': self.front_steering,
            'rear_steering': self.rear_steering,
            'optimal_steering': self.optimal_steering,
        }
