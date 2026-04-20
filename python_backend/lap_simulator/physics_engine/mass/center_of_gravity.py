"""
Center of Gravity - Calcolo baricentro vettura F1 2025

Modello fisico del baricentro (CG):
- Posizione CG (x, y, z) nel riferimento vettura
- Variazione con consumo carburante
- Effetti su load transfer e handling
- Limiti regolamento F1 (altezza minima CG)
"""

from dataclasses import dataclass
from typing import Dict
import numpy as np


@dataclass
class CGPosition:
    """Posizione del baricentro."""
    x: float  # m posizione longitudinale (positivo = avanti)
    y: float  # m posizione laterale (0 = centro)
    z: float  # m altezza da suolo


class CenterOfGravity:
    """
    Calcolo baricentro vettura F1 2025
    
    Il CG influenza:
    - Load transfer in frenata/accelerazione
    - Momento di beccheggio (pitch)
    - Momento di rollio (roll)
    - Stabilità generale
    
    Posizione tipica F1:
    - x: 45-50% del passo (wheelbase)
    - y: 0 (simmetrico)
    - z: 250-300mm da suolo (regolamento: min 240mm)
    """
    
    def __init__(self, config=None):
        """
        Inizializza calcolo baricentro
        
        Args:
            config: dict con parametri personalizzati
        """
        defaults = {
            'wheelbase': 3.60,       # m passo vettura F1 2025
            'cg_x_percentage': 0.47, # 47% wheelbase (leggermente posteriore)
            'cg_z_base': 0.280,      # m altezza CG base (280mm)
            'cg_z_fuel_effect': 0.0005,  # m CG sale per kg fuel consumato
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Posizione CG base
        self.cg_x = self.config['cg_x_percentage'] * self.config['wheelbase']
        self.cg_y = 0.0  # Centro (simmetrico)
        self.cg_z = self.config['cg_z_base']
        
        # Riferimenti
        self.wheelbase = self.config['wheelbase']
    
    def get_cg_position(self, fuel_mass: float = 100.0) -> 'CGPosition':
        """
        Calcola posizione CG corrente
        
        Args:
            fuel_mass: kg carburante residuo
        
        Returns:
            CGPosition con coordinate (x, y, z)
        """
        # Il carburante è nel serbatoio (centrale/basso)
        # Quando si consuma, il CG si alza leggermente
        fuel_effect = (110.0 - fuel_mass) * self.config['cg_z_fuel_effect']
        
        cg_z_current = self.cg_z + fuel_effect
        
        # Il CG x si sposta leggermente con il fuel (serbatoio centrale)
        # Effetto minimo, trascurabile per ora
        cg_x_current = self.cg_x
        
        return CGPosition(
            x=cg_x_current,
            y=self.cg_y,
            z=cg_z_current
        )
    
    def get_cg_from_front_axle(self, fuel_mass: float = 100.0) -> float:
        """
        Distanza CG dall'asse anteriore (m)
        
        Utile per calcoli di load transfer.
        """
        cg = self.get_cg_position(fuel_mass)
        
        # CG è a cg_x dal muso, wheelbase è la distanza tra gli assi
        # Distanza da front axle = cg_x (se origine è front axle)
        return cg.x
    
    def get_cg_from_rear_axle(self, fuel_mass: float = 100.0) -> float:
        """
        Distanza CG dall'asse posteriore (m)
        """
        cg = self.get_cg_position(fuel_mass)
        return self.wheelbase - cg.x
    
    def get_height_above_ground(self, ride_height_front: float, ride_height_rear: float) -> float:
        """
        Altezza CG effettiva da suolo (m)
        
        Considera l'assetto vettura (rake).
        
        Args:
            ride_height_front: m altezza anteriore
            ride_height_rear: m altezza posteriore
        """
        # Calcola altezza del piano vettura al CG
        # Interpolazione lineare tra front e rear
        x_percentage = self.cg_x / self.wheelbase
        
        chassis_height_at_cg = ride_height_front + (ride_height_rear - ride_height_front) * x_percentage
        
        # CG è sopra il piano vettura
        # Stima: CG è ~150mm sopra il fondo vettura
        cg_above_chassis = 0.150
        
        return chassis_height_at_cg + cg_above_chassis
    
    def set_cg_x_percentage(self, percentage: float):
        """
        Imposta posizione longitudinale CG
        
        Args:
            percentage: 0.0-1.0 (tipicamente 0.45-0.50)
        """
        self.config['cg_x_percentage'] = np.clip(percentage, 0.40, 0.60)
        self.cg_x = self.config['cg_x_percentage'] * self.wheelbase
    
    def get_summary(self, fuel_mass: float = 100.0) -> Dict:
        """Riepilogo posizione CG."""
        cg = self.get_cg_position(fuel_mass)
        
        return {
            'cg_x_m': cg.x,
            'cg_y_m': cg.y,
            'cg_z_m': cg.z,
            'cg_x_from_front_pct': (cg.x / self.wheelbase) * 100,
            'cg_x_from_rear_m': self.wheelbase - cg.x,
            'wheelbase_m': self.wheelbase,
        }
