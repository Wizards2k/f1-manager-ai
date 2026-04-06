"""
Cornering Limit - Limite Curva F1 2025

Modello fisico limite curva:
- Velocità massima in curva
- Limite grip combinato
- Effetti su lap time

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np

from ..tyres.grip_model import TyreGripModel
from ..core.constants import TYRE_LOAD_REF_KN


@dataclass
class CorneringLimitResult:
    """Risultato limite curva."""
    radius_m: float  # m raggio curva
    max_speed_kph: float  # kph velocità massima
    max_lateral_g: float  # g accelerazione laterale massima
    grip_margin: float  # % margine grip (0-100)
    cornering_force: float  # kN forza laterale


class CorneringLimitCalculator:
    """
    Limite curva F1 2025
    
    Calcola limite velocità in curva:
    - Limite grip combinato
    - Effetti aerodinamici
    - Effetti pneumatici
    
    Formula:
    v_max = sqrt((grip × mass × g × radius) / mass)
    v_max = sqrt(grip × g × radius)
    
    Con grip = f(tyre_grip, downforce, load)
    
    Effetti:
    - Raggio piccolo: velocità bassa
    - Raggio grande: velocità alta
    - Grip alto: velocità alta
    - Downforce alto: velocità alta (ma più drag)
    """
    
    def __init__(
        self,
        tyre_grip: float = 1.7,  # g grip pneumatico
        downforce_factor: float = 2.0,  # g downforce a 100 kph
        mass_kg: float = 800.0,  # kg
        load_factor: float = 1.0,  # fattore carico (0.8-1.2)
        tyre_grip_model: TyreGripModel = None,  # modello grip fisico
    ):
        """
        Inizializza limite curva
        
        Args:
            tyre_grip: g grip pneumatico
            downforce_factor: g downforce a 100 kph
            mass_kg: kg massa
            load_factor: fattore carico (0.8-1.2)
            tyre_grip_model: modello grip fisico (opzionale, se None usa tyre_grip)
        """
        self.tyre_grip = tyre_grip
        self.downforce_factor = downforce_factor
        self.mass_kg = mass_kg
        self.load_factor = load_factor
        self.tyre_grip_model = tyre_grip_model
        
        # Stato corrente
        self.max_lateral_g = self._calculate_max_lateral_g()
    
    def _calculate_max_lateral_g(self) -> float:
        """
        Calcola g laterale massimo
        
        Returns:
            g accelerazione laterale massima
        """
        # Se disponibile, usa il modello grip fisico con load sensitivity corretta
        if self.tyre_grip_model is not None:
            # Calcola grip effettivo dal modello fisico
            # Usa un carico di riferimento proporzionale al load_factor
            load_kn = TYRE_LOAD_REF_KN * self.load_factor
            grip_state = self.tyre_grip_model.calculate_grip(
                load_kn=load_kn,
                slip_ratio=0.0,
                slip_angle_deg=0.0,
                v_car_kph=100.0,
                dt=0.0
            )
            effective_grip = grip_state.mu_effective
        else:
            # Fallback: usa grip base con load sensitivity semplificata
            load_sensitivity = 0.1
            effective_grip = self.tyre_grip * (1.0 - load_sensitivity * (self.load_factor - 1.0))
        
        # Max lateral g = tyre_grip + downforce_factor × load_factor
        max_lateral_g = effective_grip + self.downforce_factor * self.load_factor
        
        return max_lateral_g
    
    def calculate_cornering_limit(
        self,
        radius_m: float,
        speed_kph: float,
    ) -> CorneringLimitResult:
        """
        Calcola limite curva
        
        Args:
            radius_m: m raggio curva
            speed_kph: kph velocità
        
        Returns:
            CorneringLimit con stato curva
        """
        # Calcola g laterale richiesto
        # a_lat = v² / r
        v = speed_kph / 3.6  # m/s
        required_lateral_g = (v ** 2) / (radius_m * 9.81)
        
        # Max g laterale disponibile
        max_lateral_g = self._calculate_max_lateral_g()
        
        # Grip margin = (max - required) / max
        grip_margin = (max_lateral_g - required_lateral_g) / max_lateral_g
        grip_margin_pct = grip_margin * 100.0
        
        # Max speed in curva
        # v_max = sqrt(grip × g × radius)
        v_max = np.sqrt(max_lateral_g * 9.81 * radius_m)
        max_speed_kph = v_max * 3.6
        
        # Cornering force
        # F_lat = m × a_lat
        cornering_force = self.mass_kg * required_lateral_g * 9.81 / 1000.0  # kN
        
        return CorneringLimitResult(
            radius_m=radius_m,
            max_speed_kph=max_speed_kph,
            max_lateral_g=max_lateral_g,
            grip_margin=grip_margin_pct,
            cornering_force=cornering_force,
        )
    
    def get_max_speed(
        self,
        radius_m: float,
    ) -> float:
        """
        Calcola velocità massima in curva
        
        Args:
            radius_m: m raggio curva
        
        Returns:
            kph velocità massima
        """
        max_lateral_g = self._calculate_max_lateral_g()
        
        # v_max = sqrt(grip × g × radius)
        v_max = np.sqrt(max_lateral_g * 9.81 * radius_m)
        max_speed_kph = v_max * 3.6
        
        return max_speed_kph
    
    def get_safe_speed(
        self,
        radius_m: float,
        safety_margin: float = 0.95,
    ) -> float:
        """
        Calcola velocità sicura (con margine)
        
        Args:
            radius_m: m raggio curva
            safety_margin: margine sicurezza (0.0-1.0)
        
        Returns:
            kph velocità sicura
        """
        max_speed = self.get_max_speed(radius_m)
        safe_speed = max_speed * safety_margin
        
        return safe_speed
    
    def is_within_limit(
        self,
        radius_m: float,
        speed_kph: float,
    ) -> bool:
        """
        Verifica se velocità è entro limite
        
        Args:
            radius_m: m raggio curva
            speed_kph: kph velocità
        
        Returns:
            bool True se entro limite
        """
        limit = self.calculate_cornering_limit(radius_m, speed_kph)
        return limit.grip_margin >= 0.0
    
    def get_state(
        self,
        radius_m: float,
        speed_kph: float,
    ) -> Dict:
        """Restituisce stato limite curva."""
        cl = self.calculate_cornering_limit(radius_m, speed_kph)
        
        return {
            'radius_m': cl.radius_m,
            'speed_kph': speed_kph,
            'max_speed_kph': cl.max_speed_kph,
            'max_lateral_g': cl.max_lateral_g,
            'grip_margin_pct': cl.grip_margin,
            'cornering_force_kn': cl.cornering_force,
            'within_limit': cl.grip_margin >= 0.0,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo limite curva."""
        return {
            'tyre_grip': self.tyre_grip,
            'downforce_factor': self.downforce_factor,
            'mass': self.mass_kg,
            'load_factor': self.load_factor,
            'max_lateral_g': self.max_lateral_g,
            'max_speed_30m_radius': self.get_max_speed(30.0),
            'max_speed_100m_radius': self.get_max_speed(100.0),
            'max_speed_300m_radius': self.get_max_speed(300.0),
        }


__all__ = ['CorneringLimitCalculator', 'CorneringLimitResult']
