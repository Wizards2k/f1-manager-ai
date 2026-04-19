"""
Moment of Inertia - Calcolo inerzie vettura F1 2025

Modello fisico dei momenti di inerzia:
- Inerzia longitudinale (roll, Ixx)
- Inerzia trasversale (pitch, Iyy)
- Inerzia verticale (yaw, Izz)
- Variazione con consumo carburante
- Effetti su dinamica veicolo
"""

from dataclasses import dataclass
from typing import Dict
import numpy as np


@dataclass
class InertiaTensor:
    """Tensore di inerzia vettura."""
    ixx: float  # kg·m² inerzia roll (longitudinale)
    iyy: float  # kg·m² inerzia pitch (trasversale)
    izz: float  # kg·m² inerzia yaw (verticale)
    ixy: float = 0.0  # kg·m² prodotto di inerzia (simmetria = 0)
    ixz: float = 0.0  # kg·m² prodotto di inerzia (simmetria = 0)
    iyz: float = 0.0  # kg·m² prodotto di inerzia (simmetria = 0)


class MomentOfInertia:
    """
    Calcolo momenti di inerzia F1 2025
    
    I momenti di inerzia determinano:
    - Risposta al rollio (curva)
    - Risposta al beccheggio (frenata/accelerazione)
    - Risposta all'imbardata (cambi direzione)
    
    Valori tipici F1:
    - Ixx (roll): ~500-700 kg·m²
    - Iyy (pitch): ~1200-1600 kg·m²
    - Izz (yaw): ~1400-1800 kg·m²
    
    Il carburante contribuisce significativamente:
    - ~100 kg di fuel = +15-20% inerzia
    """
    
    def __init__(self, config=None):
        """
        Inizializza calcolo inerzie
        
        Args:
            config: dict con parametri personalizzati
        """
        defaults = {
            'mass_dry': 798.0,       # kg massa a secco
            'mass_fuel_max': 110.0,  # kg carburante massimo
            'wheelbase': 3.60,       # m passo vettura
            'track_front': 1.60,     # m carreggiata anteriore
            'track_rear': 1.50,      # m carreggiata posteriore
            'cg_height': 0.280,      # m altezza baricentro
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Masse di riferimento
        self.mass_dry = self.config['mass_dry']
        self.mass_fuel_max = self.config['mass_fuel_max']
        
        # Dimensioni vettura
        self.wheelbase = self.config['wheelbase']
        self.track_front = self.config['track_front']
        self.track_rear = self.config['track_rear']
        self.cg_height = self.config['cg_height']
        
        # Calcola inerzie base (a secco)
        self._calculate_base_inertia()
    
    def _calculate_base_inertia(self):
        """Calcola inerzie base (a secco, senza fuel)."""
        # Modello semplificato: vettura come scatola rettangolare
        # I = (1/12) * m * (dimensione1² + dimensione2²)
        
        # Ixx (roll) - rotazione attorno asse longitudinale
        # Dipende da massa, carreggiata, altezza CG
        self.ixx_dry = (1/12) * self.mass_dry * (
            self.track_front ** 2 + 
            self.track_rear ** 2 + 
            12 * self.cg_height ** 2
        )
        
        # Iyy (pitch) - rotazione attorno asse trasversale
        # Dipende da massa, wheelbase, altezza CG
        self.iyy_dry = (1/12) * self.mass_dry * (
            self.wheelbase ** 2 + 
            12 * self.cg_height ** 2
        )
        
        # Izz (yaw) - rotazione attorno asse verticale
        # Dipende da massa, wheelbase, carreggiata
        self.izz_dry = (1/12) * self.mass_dry * (
            self.wheelbase ** 2 + 
            (self.track_front ** 2 + self.track_rear ** 2) / 2
        )
    
    def get_inertia(self, fuel_mass: float = 100.0) -> 'InertiaTensor':
        """
        Calcola momenti di inerzia correnti
        
        Args:
            fuel_mass: kg carburante residuo
        
        Returns:
            InertiaTensor con Ixx, Iyy, Izz
        """
        # Il carburante aggiunge inerzia
        # Modello: fuel è concentrato nel serbatoio (centrale)
        fuel_ratio = fuel_mass / self.mass_fuel_max
        
        # Fattori di scala per inerzia con fuel
        # Il fuel aumenta l'inerzia più della massa (è distribuito)
        ixx_fuel_factor = 1.0 + 0.15 * fuel_ratio  # +15% max
        iyy_fuel_factor = 1.0 + 0.18 * fuel_ratio  # +18% max
        izz_fuel_factor = 1.0 + 0.20 * fuel_ratio  # +20% max
        
        # Inerzie totali
        ixx = self.ixx_dry * ixx_fuel_factor
        iyy = self.iyy_dry * iyy_fuel_factor
        izz = self.izz_dry * izz_fuel_factor
        
        return InertiaTensor(
            ixx=ixx,
            iyy=iyy,
            izz=izz,
            ixy=0.0,  # Simmetria laterale
            ixz=0.0,  # Simmetria laterale
            iyz=0.0   # Simmetria laterale
        )
    
    def get_inertia_normalized(self, fuel_mass: float = 100.0) -> Dict[str, float]:
        """
        Restituisce inerzie normalizzate (per analisi)
        
        Args:
            fuel_mass: kg carburante residuo
        
        Returns:
            Dict con inerzie normalizzate rispetto alla massa totale
        """
        inertia = self.get_inertia(fuel_mass)
        mass_total = self.mass_dry + fuel_mass + 80.0  # +80kg pilota
        
        return {
            'ixx_norm': inertia.ixx / mass_total,  # m²
            'iyy_norm': inertia.iyy / mass_total,  # m²
            'izz_norm': inertia.izz / mass_total,  # m²
        }
    
    def get_roll_inertia(self, fuel_mass: float = 100.0) -> float:
        """Momento di inerzia al rollio (kg·m²)."""
        return self.get_inertia(fuel_mass).ixx
    
    def get_pitch_inertia(self, fuel_mass: float = 100.0) -> float:
        """Momento di inerzia al beccheggio (kg·m²)."""
        return self.get_inertia(fuel_mass).iyy
    
    def get_yaw_inertia(self, fuel_mass: float = 100.0) -> float:
        """Momento di inerzia all'imbardata (kg·m²)."""
        return self.get_inertia(fuel_mass).izz
    
    def get_summary(self, fuel_mass: float = 100.0) -> Dict:
        """Riepilogo momenti di inerzia."""
        inertia = self.get_inertia(fuel_mass)
        
        return {
            'ixx_kg_m2': inertia.ixx,
            'iyy_kg_m2': inertia.iyy,
            'izz_kg_m2': inertia.izz,
            'fuel_mass_kg': fuel_mass,
            'mass_total_kg': self.mass_dry + fuel_mass + 80.0,
            'wheelbase_m': self.wheelbase,
            'track_front_m': self.track_front,
            'track_rear_m': self.track_rear,
        }
