"""
Vehicle Balance - Bilanciamento Veicolo F1 2025

Modello fisico bilanciamento:
- Distribuzione carico fronte/rear
- Effetti su grip e handling
- Regolazione in curva

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np


@dataclass
class BalanceState:
    """Stato bilanciamento."""
    front_load_pct: float  # % carico frontale
    rear_load_pct: float  # % carico posteriore
    balance_ratio: float  # rapporto front/rear
    load_transfer_pct: float  # % trasferimento carico
    grip_efficiency: float  # efficienza grip (0.0-1.0)


class VehicleBalance:
    """
    Bilanciamento veicolo F1 2025
    
    Calcola distribuzione carico:
    - Carico statico: basato su CG position
    - Carico dinamico: trasferimento longitudinale/laterale
    - Effetti su grip e handling
    
    Formula:
    Front Load = (weight_rear × L_rear) / L_wheelbase
    Rear Load = (weight_front × L_front) / L_wheelbase
    
    Dynamic Load Transfer:
    - Longitudinale: f(acceleration, braking)
    - Lateral: f(lateral_g, roll_stiffness)
    
    Effetti:
    - Troppo front load: understeer
    - Troppo rear load: oversteer
    - Bilanciamento ottimale: grip massimo
    """
    
    def __init__(
        self,
        mass_kg: float = 800.0,  # kg massa totale
        wheelbase: float = 3.6,  # m
        cg_to_front: float = 1.8,  # m
        cg_to_rear: float = 1.8,  # m
        track_width_front: float = 1.8,  # m
        track_width_rear: float = 1.8,  # m
        roll_stiffness_front: float = 100.0,  # kN/rad
        roll_stiffness_rear: float = 100.0,  # kN/rad
    ):
        """
        Inizializza bilanciamento veicolo
        
        Args:
            mass_kg: kg massa totale
            wheelbase: m wheelbase
            cg_to_front: m distanza CG da frontale
            cg_to_rear: m distanza CG da posteriore
            track_width_front: m track frontale
            track_width_rear: m track posteriore
            roll_stiffness_front: kN/rad roll stiffness frontale
            roll_stiffness_rear: kN/rad roll stiffness posteriore
        """
        self.mass_kg = mass_kg
        self.wheelbase = wheelbase
        self.cg_to_front = cg_to_front
        self.cg_to_rear = cg_to_rear
        self.track_width_front = track_width_front
        self.track_width_rear = track_width_rear
        self.roll_stiffness_front = roll_stiffness_front
        self.roll_stiffness_rear = roll_stiffness_rear
        
        # Stato corrente
        self.static_balance = self._calculate_static_balance()
    
    def _calculate_static_balance(self) -> Tuple[float, float]:
        """
        Calcola bilanciamento statico
        
        Returns:
            (front_load_pct, rear_load_pct)
        """
        # Static balance = (weight_rear × L_rear) / L_wheelbase
        # weight = mass × g
        g = 9.81
        
        # Carico frontale statico
        front_load = (self.mass_kg * g * self.cg_to_rear) / self.wheelbase
        
        # Carico posteriore statico
        rear_load = (self.mass_kg * g * self.cg_to_front) / self.wheelbase
        
        # Percentuali
        total_load = front_load + rear_load
        front_load_pct = (front_load / total_load) * 100.0
        rear_load_pct = (rear_load / total_load) * 100.0
        
        return front_load_pct, rear_load_pct
    
    def calculate_balance(
        self,
        acceleration_ms2: float = 0.0,
        lateral_g: float = 0.0,
    ) -> BalanceState:
        """
        Calcola bilanciamento dinamico
        
        Args:
            acceleration_ms2: m/s² accelerazione longitudinale
            lateral_g: g accelerazione laterale
        
        Returns:
            BalanceState con stato bilanciamento
        """
        # Carico statico
        front_static_pct, rear_static_pct = self.static_balance
        
        # Trasferimento carico longitudinale
        # ΔF_long = (m × a × h) / L
        g = 9.81
        cg_height_m = 0.4  # Altezza CG da terra (typical F1)
        
        delta_long = (self.mass_kg * abs(acceleration_ms2) * cg_height_m) / self.wheelbase
        delta_long_pct = (delta_long / (self.mass_kg * g)) * 100.0
        
        # Trasferimento carico laterale
        # ΔF_lat = (m × a_lat × h) / track
        delta_lat = (self.mass_kg * lateral_g * g * cg_height_m) / self.track_width_front
        delta_lat_pct = (delta_lat / (self.mass_kg * g)) * 100.0
        
        # Bilanciamento dinamico
        # Frenata: più carico frontale (+)
        # Accelerazione: più carico posteriore (-)
        # Curva sinistra: più carico destro
        # Curva destra: più carico sinistro
        
        if acceleration_ms2 < 0:  # Frenata
            front_load_pct = front_static_pct + delta_long_pct * 0.5
            rear_load_pct = rear_static_pct - delta_long_pct * 0.5
        elif acceleration_ms2 > 0:  # Accelerazione
            front_load_pct = front_static_pct - delta_long_pct * 0.5
            rear_load_pct = rear_static_pct + delta_long_pct * 0.5
        else:
            front_load_pct = front_static_pct
            rear_load_pct = rear_static_pct
        
        # Limita a 0-100%
        front_load_pct = np.clip(front_load_pct, 0.0, 100.0)
        rear_load_pct = np.clip(rear_load_pct, 0.0, 100.0)
        
        # Ratio front/rear
        balance_ratio = front_load_pct / max(rear_load_pct, 0.001)
        
        # Load transfer %
        load_transfer_pct = delta_long_pct + delta_lat_pct
        
        # Grip efficiency = f(balance, load_transfer)
        # Ottimale = 50/50, peggio se squilibrato
        balance_error = abs(front_load_pct - 50.0) + abs(rear_load_pct - 50.0)
        grip_efficiency = 1.0 - (balance_error / 100.0)
        grip_efficiency = np.clip(grip_efficiency, 0.5, 1.0)
        
        return BalanceState(
            front_load_pct=front_load_pct,
            rear_load_pct=rear_load_pct,
            balance_ratio=balance_ratio,
            load_transfer_pct=load_transfer_pct,
            grip_efficiency=grip_efficiency,
        )
    
    def get_optimal_balance(self) -> Tuple[float, float]:
        """
        Calcola bilanciamento ottimale
        
        Returns:
            (front_load_pct, rear_load_pct) ottimali
        """
        # Bilanciamento ottimale = 50/50 per grip massimo
        # Ma F1 2025 tipicamente leggero understeer → 52/48
        return 52.0, 48.0
    
    def adjust_balance(
        self,
        front_bias: float,
    ) -> None:
        """
        Regola bilanciamento (brake bias)
        
        Args:
            front_bias: 0.0-1.0 (50% frontale)
        """
        # Regola CG position virtuale
        # Più bias frontale = CG si sposta in avanti
        adjustment = (front_bias - 0.5) * 0.1  # ±10% CG
        self.cg_to_front += adjustment
        self.cg_to_rear -= adjustment
        
        # Ricalcola static balance
        self.static_balance = self._calculate_static_balance()
    
    def get_state(
        self,
        acceleration_ms2: float = 0.0,
        lateral_g: float = 0.0,
    ) -> Dict:
        """Restituisce stato bilanciamento."""
        bs = self.calculate_balance(acceleration_ms2, lateral_g)
        
        return {
            'front_load_pct': bs.front_load_pct,
            'rear_load_pct': bs.rear_load_pct,
            'balance_ratio': bs.balance_ratio,
            'load_transfer_pct': bs.load_transfer_pct,
            'grip_efficiency': bs.grip_efficiency,
            'static_balance': self.static_balance,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo bilanciamento."""
        front_opt, rear_opt = self.get_optimal_balance()
        
        return {
            'mass': self.mass_kg,
            'wheelbase': self.wheelbase,
            'cg_to_front': self.cg_to_front,
            'cg_to_rear': self.cg_to_rear,
            'track_front': self.track_width_front,
            'track_rear': self.track_width_rear,
            'roll_stiffness_front': self.roll_stiffness_front,
            'roll_stiffness_rear': self.roll_stiffness_rear,
            'static_balance': self.static_balance,
            'optimal_balance': (front_opt, rear_opt),
        }
