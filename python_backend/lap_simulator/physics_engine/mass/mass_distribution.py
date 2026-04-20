"""
Mass Distribution - Gestione massa vettura F1 2025

Modello fisico della distribuzione di massa:
- Massa totale (dry + fuel + driver)
- Distribuzione front/rear (45-55% tipico)
- Variazione con consumo carburante
- Effetti su inerzia e handling
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class MassState:
    """Stato corrente della massa vettura."""
    mass_total: float  # kg massa totale attuale
    mass_dry: float  # kg massa a secco (senza fuel/driver)
    mass_fuel: float  # kg carburante residuo
    mass_driver: float  # kg pilota + equipaggiamento
    front_percentage: float  # % massa sull'asse anteriore
    rear_percentage: float  # % massa sull'asse posteriore


class MassDistribution:
    """
    Gestione massa vettura F1 2025
    
    La massa varia durante la gara per:
    - Consumo carburante (~0.3 kg/giro)
    - Usura gomme (~0.5 kg/giro)
    - Danni aerodinamici (rimozione componenti)
    
    La distribuzione front/rear influenza:
    - Handling in frenata/accelerazione
    - Carico su ciascun asse
    - Efficienza frenante
    """
    
    def __init__(self, config=None):
        """
        Inizializza distribuzione massa F1 2025
        
        Args:
            config: dict con parametri personalizzati
        """
        defaults = {
            'mass_dry': 798.0,      # kg massa minima F1 2025 (regolamento)
            'mass_driver': 80.0,    # kg pilota + casco + tuta
            'mass_fuel_max': 110.0, # kg carburante massimo (110L * 0.75 kg/L)
            'mass_fuel_start': 100.0,  # kg carburante iniziale tipico
            'front_percentage_base': 0.46,  # 46% massa anteriore base
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Stato iniziale
        self.mass_fuel_current = self.config['mass_fuel_start']
        self.mass_dry = self.config['mass_dry']
        self.mass_driver = self.config['mass_driver']
        
        # Calcola massa totale iniziale
        self.mass_total = self.mass_dry + self.mass_driver + self.mass_fuel_current
        
        # Distribuzione front/rear
        self.front_percentage = self.config['front_percentage_base']
        self.rear_percentage = 1.0 - self.front_percentage
    
    def get_mass_state(self) -> 'MassState':
        """Restituisce stato corrente della massa."""
        return MassState(
            mass_total=self.mass_total,
            mass_dry=self.mass_dry,
            mass_fuel=self.mass_fuel_current,
            mass_driver=self.mass_driver,
            front_percentage=self.front_percentage,
            rear_percentage=self.rear_percentage
        )
    
    def consume_fuel(self, fuel_kg: float):
        """
        Consuma carburante durante il giro
        
        Args:
            fuel_kg: kg carburante consumato (positivo)
        """
        self.mass_fuel_current = max(0.0, self.mass_fuel_current - fuel_kg)
        self._update_mass_total()
    
    def _update_mass_total(self):
        """Aggiorna massa totale dopo consumo."""
        self.mass_total = self.mass_dry + self.mass_driver + self.mass_fuel_current
        
        # La distribuzione front/rear cambia leggermente con il carburante
        # Il serbatoio è centrale/posteriore, quindi meno fuel = meno massa rear
        fuel_reduction = (self.config['mass_fuel_start'] - self.mass_fuel_current) / self.config['mass_fuel_start']
        
        # Sposta ~2% della massa in meno verso il posteriore
        self.front_percentage = self.front_percentage_base + (fuel_reduction * 0.02)
        self.rear_percentage = 1.0 - self.front_percentage
    
    def get_mass_front(self) -> float:
        """Massa sull'asse anteriore (kg)."""
        return self.mass_total * self.front_percentage
    
    def get_mass_rear(self) -> float:
        """Massa sull'asse posteriore (kg)."""
        return self.mass_total * self.rear_percentage
    
    def get_weight_front(self) -> float:
        """Peso (forza) sull'asse anteriore (N)."""
        from ..core.constants import G
        return self.get_mass_front() * G
    
    def get_weight_rear(self) -> float:
        """Peso (forza) sull'asse posteriore (N)."""
        from ..core.constants import G
        return self.get_mass_rear() * G
    
    def reset_to_start(self):
        """Resetta massa a inizio giro (per simulazione)."""
        self.mass_fuel_current = self.config['mass_fuel_start']
        self._update_mass_total()
    
    def get_summary(self) -> Dict:
        """Riepilogo distribuzione massa."""
        return {
            'mass_total_kg': self.mass_total,
            'mass_dry_kg': self.mass_dry,
            'mass_fuel_kg': self.mass_fuel_current,
            'mass_driver_kg': self.mass_driver,
            'front_percentage': self.front_percentage * 100,
            'rear_percentage': self.rear_percentage * 100,
            'mass_front_kg': self.get_mass_front(),
            'mass_rear_kg': self.get_mass_rear(),
        }
