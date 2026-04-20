"""
Handling Model - Modello Handling F1 2025

Modello fisico handling:
- Sotto/sovra sterzo
- Differenziale e bilanciamento
- Effetti su traiettoria e velocità

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np


@dataclass
class HandlingState:
    """Stato handling."""
    understeer: float  # % sotto sterzo (-100 a +100)
    oversteer: float  # % sovra sterzo (-100 a +100)
    balance: float  # bilanciamento (0.0-1.0)
    cornering_force_ratio: float  # rapporto forze (front/rear)
    stability: float  # stabilità (0.0-1.0)


class HandlingModel:
    """
    Modello handling F1 2025
    
    Calcola comportamento handling in curva:
    - Understeer: fronta non segue, curva aperta
    - Oversteer: posteriore scivola, curva chiusa
    - Balance: distribuzione fronte/rear
    - Stability: stabilità dinamica
    
    Formula:
    Understeer = (K_front - K_rear) × v² / L
    - K = cornering stiffness
    - v = velocità
    - L = wheelbase
    
    Effetti:
    - Understeer: curva aperta, velocità ridotta
    - Oversteer: curva chiusa, rischio spin
    - Balance: influenza traiettoria e velocità
    """
    
    def __init__(
        self,
        cornering_stiffness_front: float = 150.0,  # kN/rad
        cornering_stiffness_rear: float = 140.0,  # kN/rad
        wheelbase: float = 3.6,  # m
        mass_kg: float = 800.0,  # kg
        cg_to_front: float = 1.8,  # m
        cg_to_rear: float = 1.8,  # m
    ):
        """
        Inizializza modello handling
        
        Args:
            cornering_stiffness_front: kN/rad stiffness frontale
            cornering_stiffness_rear: kN/rad stiffness posteriore
            wheelbase: m wheelbase
            mass_kg: kg massa totale
            cg_to_front: m distanza CG da frontale
            cg_to_rear: m distanza CG da posteriore
        """
        self.cornering_stiffness_front = cornering_stiffness_front
        self.cornering_stiffness_rear = cornering_stiffness_rear
        self.wheelbase = wheelbase
        self.mass_kg = mass_kg
        self.cg_to_front = cg_to_front
        self.cg_to_rear = cg_to_rear
        
        # Stato corrente
        self.understeer_gradient = self._calculate_understeer_gradient()
    
    def _calculate_understeer_gradient(self) -> float:
        """
        Calcola understeer gradient
        
        Formula:
        K = (K_rear × L²) - (K_front × a × b) / (m × v²)
        
        Returns:
            understeer gradient (deg/deg/g²)
        """
        a = self.cg_to_front
        b = self.cg_to_rear
        L = self.wheelbase
        
        # K = (K_rear × L² - K_front × a × b) / (m × v²)
        # Per semplicità, assumiamo v = 100 kph (27.78 m/s)
        v = 27.78  # m/s
        
        numerator = (self.cornering_stiffness_rear * 1000.0) * (L ** 2) - \
                    (self.cornering_stiffness_front * 1000.0) * a * b
        denominator = self.mass_kg * (v ** 2)
        
        K = numerator / denominator
        
        # Converti in deg/deg/g²
        K_deg = K * 57.3  # 180/π
        
        return K_deg
    
    def calculate_handling(
        self,
        speed_kph: float,
        steering_angle_deg: float,
        lateral_g: float,
    ) -> HandlingState:
        """
        Calcola stato handling
        
        Args:
            speed_kph: kph velocità
            steering_angle_deg: ° angolo sterzo
            lateral_g: g accelerazione laterale
        
        Returns:
            HandlingState con stato handling
        """
        # Converti velocità in m/s
        v = speed_kph / 3.6
        
        # Calcola understeer gradient a questa velocità
        K = self.understeer_gradient * (v / 27.78) ** 2
        
        # Understeer = K × v² (in deg)
        understeer_deg = K * (v ** 2) / 57.3
        
        # Converti in %
        understeer_pct = understeer_deg * 100.0 / 57.3
        
        # Oversteer = -understeer (semplice modello)
        oversteer_pct = -understeer_pct
        
        # Balance = cornering stiffness ratio
        balance = self.cornering_stiffness_front / \
                  (self.cornering_stiffness_front + self.cornering_stiffness_rear)
        
        # Cornering force ratio
        front_force = self.cornering_stiffness_front * steering_angle_deg
        rear_force = self.cornering_stiffness_rear * steering_angle_deg
        cornering_force_ratio = front_force / max(rear_force, 0.001)
        
        # Stability = f(understeer, oversteer, lateral_g)
        # Più stabile se understeer positivo, meno se oversteer
        stability = 1.0 - abs(understeer_pct) / 100.0 - abs(oversteer_pct) / 100.0
        stability = np.clip(stability, 0.0, 1.0)
        
        return HandlingState(
            understeer=understeer_pct,
            oversteer=oversteer_pct,
            balance=balance,
            cornering_force_ratio=cornering_force_ratio,
            stability=stability,
        )
    
    def get_optimal_balance(self) -> float:
        """
        Calcola bilanciamento ottimale
        
        Returns:
            float bilanciamento ottimale (0.0-1.0)
        """
        # Bilanciamento ottimale = 0.5 (neutro)
        # Ma F1 2025 tipicamente understeer leggero
        optimal_balance = 0.48  # Leggermente più grip frontale
        
        return optimal_balance
    
    def adjust_handling(
        self,
        balance_adjustment: float,
    ) -> None:
        """
        Regola handling modificando cornering stiffness
        
        Args:
            balance_adjustment: -0.1 a +0.1 (riduce/aumenta grip frontale)
        """
        # Riduci/aumenta cornering stiffness frontale
        self.cornering_stiffness_front *= (1.0 - balance_adjustment * 10.0)
        
        # Ricalcola gradient
        self.understeer_gradient = self._calculate_understeer_gradient()
    
    def get_state(
        self,
        speed_kph: float,
        steering_angle_deg: float,
        lateral_g: float,
    ) -> Dict:
        """Restituisce stato handling."""
        hs = self.calculate_handling(speed_kph, steering_angle_deg, lateral_g)
        
        return {
            'understeer_pct': hs.understeer,
            'oversteer_pct': hs.oversteer,
            'balance': hs.balance,
            'cornering_force_ratio': hs.cornering_force_ratio,
            'stability': hs.stability,
            'understeer_gradient': self.understeer_gradient,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo handling model."""
        return {
            'cornering_stiffness_front': self.cornering_stiffness_front,
            'cornering_stiffness_rear': self.cornering_stiffness_rear,
            'wheelbase': self.wheelbase,
            'mass': self.mass_kg,
            'understeer_gradient': self.understeer_gradient,
            'optimal_balance': self.get_optimal_balance(),
        }
