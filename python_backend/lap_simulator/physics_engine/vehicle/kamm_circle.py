"""
Kamm Circle - Cerchio di Kamm F1 2025

Modello fisico cerchio di Kamm:
- Grip combinato longitudinale/laterale
- Limite friction circle
- Effetti su handling e stabilità

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np


@dataclass
class FrictionCircle:
    """Cerchio di attrito."""
    radius: float  # g raggio cerchio
    current_g_long: float  # g accelerazione longitudinale
    current_g_lat: float  # g accelerazione laterale
    utilization_pct: float  # % utilizzo cerchio (0-100)
    margin: float  # g margine rimanente


class KammCircle:
    """
    Cerchio di Kamm F1 2025
    
    Il cerchio di Kamm rappresenta il limite di grip combinato:
    - Raggio = grip massimo (g)
    - Coordinate = g_long, g_lat
    - Punto interno = utilizzo < 100%
    - Punto sul bordo = utilizzo = 100% (limite)
    
    Formula:
    (g_long / radius)² + (g_lat / radius)² ≤ 1
    
    Effetti:
    - A bassa velocità: cerchio piccolo (poco grip)
    - A alta velocità: cerchio grande (più grip aerodinamico)
    - Frenata: cerchio allungato in longitudinale
    - Curva: cerchio allungato in laterale
    """
    
    def __init__(
        self,
        base_grip: float = 2.5,  # g grip base (senza aero)
        aero_bonus: float = 1.5,  # g bonus da downforce
        load_sensitivity: float = 0.1,  # sensibilità carico
    ):
        """
        Inizializza cerchio di Kamm
        
        Args:
            base_grip: g grip base (senza aero)
            aero_bonus: g bonus da downforce
            load_sensitivity: sensibilità carico (0.05-0.2)
        """
        self.base_grip = base_grip
        self.aero_bonus = aero_bonus
        self.load_sensitivity = load_sensitivity
        
        # Stato corrente
        self.radius = self._calculate_radius()
    
    def _calculate_radius(self, load_kn: float = 6.0) -> float:
        """
        Calcola raggio cerchio in base al carico
        
        Args:
            load_kn: kN carico ruota
        
        Returns:
            g raggio cerchio
        """
        # Raggio = grip_base + aero_bonus × (1 - load_sensitivity)
        # Più carico = grip meno efficiente (load sensitivity)
        load_factor = 1.0 - self.load_sensitivity * (load_kn - 5.0)
        load_factor = np.clip(load_factor, 0.8, 1.2)
        
        radius = self.base_grip + self.aero_bonus * load_factor
        
        return radius
    
    def calculate_utilization(
        self,
        g_long: float,
        g_lat: float,
        load_kn: float = 6.0
    ) -> FrictionCircle:
        """
        Calcola utilizzo cerchio di Kamm
        
        Args:
            g_long: g accelerazione longitudinale
            g_lat: g accelerazione laterale
            load_kn: kN carico ruota
        
        Returns:
            FrictionCircle con utilizzo
        """
        # Raggio corrente
        radius = self._calculate_radius(load_kn)
        
        # Utilizzo = sqrt((g_long/radius)² + (g_lat/radius)²)
        utilization = np.sqrt((g_long / radius) ** 2 + (g_lat / radius) ** 2)
        
        # Margine rimanente
        margin = radius * (1.0 - utilization)
        
        return FrictionCircle(
            radius=radius,
            current_g_long=g_long,
            current_g_lat=g_lat,
            utilization_pct=min(utilization * 100, 100),
            margin=margin,
        )
    
    def get_max_g_lat(self, g_long: float, load_kn: float = 6.0) -> float:
        """
        Calcola g laterale massimo dato g longitudinale
        
        Args:
            g_long: g accelerazione longitudinale
            load_kn: kN carico ruota
        
        Returns:
            g laterale massimo
        """
        radius = self._calculate_radius(load_kn)
        
        # (g_lat/radius)² = 1 - (g_long/radius)²
        g_lat_max = radius * np.sqrt(max(0.0, 1.0 - (g_long / radius) ** 2))
        
        return g_lat_max
    
    def get_max_g_long(self, g_lat: float, load_kn: float = 6.0) -> float:
        """
        Calcola g longitudinale massimo dato g laterale
        
        Args:
            g_lat: g accelerazione laterale
            load_kn: kN carico ruota
        
        Returns:
            g longitudinale massimo
        """
        radius = self._calculate_radius(load_kn)
        
        # (g_long/radius)² = 1 - (g_lat/radius)²
        g_long_max = radius * np.sqrt(max(0.0, 1.0 - (g_lat / radius) ** 2))
        
        return g_long_max
    
    def is_within_limit(self, g_long: float, g_lat: float, load_kn: float = 6.0) -> bool:
        """
        Verifica se punto è dentro cerchio
        
        Args:
            g_long: g accelerazione longitudinale
            g_lat: g accelerazione laterale
            load_kn: kN carico ruota
        
        Returns:
            bool True se dentro cerchio
        """
        utilization = self.calculate_utilization(g_long, g_lat, load_kn)
        return utilization.utilization_pct <= 100.0
    
    def get_state(self, g_long: float, g_lat: float, load_kn: float = 6.0) -> Dict:
        """Restituisce stato cerchio."""
        fc = self.calculate_utilization(g_long, g_lat, load_kn)
        
        return {
            'radius': fc.radius,
            'g_long': fc.current_g_long,
            'g_lat': fc.current_g_lat,
            'utilization_pct': fc.utilization_pct,
            'margin_g': fc.margin,
            'within_limit': fc.utilization_pct <= 100.0,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo cerchio di Kamm."""
        return {
            'base_grip': self.base_grip,
            'aero_bonus': self.aero_bonus,
            'load_sensitivity': self.load_sensitivity,
            'current_radius': self.radius,
            'max_g_long_at_1g_lat': self.get_max_g_long(1.0),
            'max_g_lat_at_1g_long': self.get_max_g_lat(1.0),
        }
