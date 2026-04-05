"""
Tyre Wear - Usura e degradazione gomme F1 2025

Modello fisico di usura:
- Abrasione battistrada (distanza, carico)
- Degradazione termica (overheating)
- Blistering (danno permanente)
- Graining (superficie irregolare)

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict
import numpy as np


@dataclass
class TyreWearState:
    """Stato usura gomma."""
    wear_pct: float  # % usura totale (0-100)
    tread_depth_mm: float  # mm profondità battistrada
    degradation_pct: float  # % perdita performance
    blistering_severity: float  # 0.0-1.0 gravità blistering
    graining_level: float  # 0.0-1.0 livello graining
    flat_spot: bool  # Flag flat spot (pianatura)


class TyreWear:
    """
    Modello usura gomme F1 2025
    
    Meccanismi di usura:
    1. Abrasione meccanica (distanza, carico, asfalto)
    2. Degradazione termica (overheating)
    3. Blistering (bolle da surriscaldamento)
    4. Graining (strappi superficiali)
    5. Flat spot (pianatura da bloccaggio)
    
    Vita utile tipica:
    - Soft (C4-C5): 15-25 giri
    - Medium (C3-C4): 25-35 giri
    - Hard (C1-C2): 35-50 giri
    """
    
    # Soglie usura
    TREAD_NEW_MM = 8.0      # mm battistrada nuovo
    TREAD_WORN_MM = 2.0     # mm battistrada minimo
    WEAR_CRITICAL = 80.0    # % usura critica
    
    def __init__(self, compound: str = 'C3', track_abrasiveness: float = 1.0):
        """
        Inizializza modello usura
        
        Args:
            compound: nome compound (C1-C5)
            track_abrasiveness: 0.5-2.0 (1.0 = normale)
        """
        self.compound = compound
        self.track_abrasiveness = track_abrasiveness
        
        # Stato iniziale
        self.wear_pct = 0.0
        self.tread_depth_mm = self.TREAD_NEW_MM
        self.degradation_pct = 0.0
        self.blistering_severity = 0.0
        self.graining_level = 0.0
        self.flat_spot = False
        
        # Coefficiente usura base (per compound)
        self.wear_coeff = self._get_wear_coefficient()
    
    def _get_wear_coefficient(self) -> float:
        """
        Restituisce coefficiente usura base per compound
        
        Returns:
            float coefficiente usura (0.8-2.0)
        """
        wear_coeffs = {
            'C1': 0.60,  # Hard: usura bassa
            'C2': 0.75,
            'C3': 1.00,  # Medium: usura media
            'C4': 1.30,
            'C5': 1.70,  # Soft: usura alta
            'INTERMEDIATE': 0.50,
            'WET': 0.40,
        }
        
        return wear_coeffs.get(self.compound, 1.0)
    
    def calculate_wear(
        self,
        load_kn: float,
        slip_ratio: float,
        slip_angle_deg: float,
        distance_m: float,
        temp_c: float,
        dt: float
    ) -> float:
        """
        Calcola usura per un timestep
        
        Args:
            load_kn: kN carico verticale
            slip_ratio: % slittamento longitudinale
            slip_angle_deg: gradi slittamento angolare
            distance_m: metri percorsi
            temp_c: °C temperatura gomma
            dt: secondi timestep
        
        Returns:
            % usura generata
        """
        # 1. Usura meccanica (distanza)
        # Usura base: ~0.002% per metro (gomma media)
        base_wear = distance_m * 0.0002
        
        # 2. Usura da carico (sovraccarico)
        # Sopra 12 kN: usura aumenta esponenzialmente
        if load_kn > 12.0:
            overload = load_kn - 12.0
            load_wear = overload * 0.005 * dt
        else:
            load_wear = 0.0
        
        # 3. Usura da slittamento (accelerazione/frenata)
        slip_wear = abs(slip_ratio) * 0.02 * dt
        
        # 4. Usura da slittamento angolare (curva)
        slip_angle_rad = np.radians(slip_angle_deg)
        corner_wear = abs(slip_angle_rad) * 0.01 * dt
        
        # 5. Usura termica (overheating)
        if temp_c > 140.0:
            thermal_excess = temp_c - 140.0
            thermal_wear = thermal_excess * 0.001 * dt
        else:
            thermal_wear = 0.0
        
        # 6. Usura da graining (se presente)
        graining_factor = 1.0 + self.graining_level * 0.5
        
        # 7. Usura da blistering (se presente)
        blistering_factor = 1.0 + self.blistering_severity * 0.8
        
        # Totale usura
        total_wear = (
            base_wear + load_wear + slip_wear + corner_wear + thermal_wear
        ) * graining_factor * blistering_factor
        
        # Applica coefficienti
        total_wear *= self.wear_coeff * self.track_abrasiveness
        
        return total_wear
    
    def update_wear(
        self,
        load_kn: float,
        slip_ratio: float,
        slip_angle_deg: float,
        v_car_kph: float,
        temp_c: float,
        dt: float
    ):
        """
        Aggiorna stato usura
        
        Args:
            load_kn: kN carico verticale
            slip_ratio: % slittamento longitudinale
            slip_angle_deg: gradi slittamento angolare
            v_car_kph: kph velocità vettura
            temp_c: °C temperatura gomma
            dt: secondi timestep
        """
        # Distanza percorsa
        distance_m = v_car_kph * dt / 3.6
        
        # Calcola usura
        wear_increment = self.calculate_wear(
            load_kn, slip_ratio, slip_angle_deg, distance_m, temp_c, dt
        )
        
        # Aggiorna usura totale
        self.wear_pct = np.clip(self.wear_pct + wear_increment, 0.0, 100.0)
        
        # Aggiorna profondità battistrada
        wear_depth = (self.TREAD_NEW_MM - self.TREAD_WORN_MM) * (self.wear_pct / 100.0)
        self.tread_depth_mm = self.TREAD_NEW_MM - wear_depth
        
        # Aggiorna degradazione performance
        # Performance cala linearmente fino a 80%, poi crolla
        if self.wear_pct < 80.0:
            self.degradation_pct = self.wear_pct * 0.5  # -0.5% per 1% usura
        else:
            self.degradation_pct = 40.0 + (self.wear_pct - 80.0) * 3.0  # -3% per 1% usura
        
        # Aggiorna stato
        self._update_damage(temp_c, slip_ratio)
    
    def _update_damage(self, temp_c: float, slip_ratio: float):
        """
        Aggiorna danni (blistering, graining, flat spot)
        
        Args:
            temp_c: °C temperatura gomma
            slip_ratio: % slittamento
        """
        # 1. Blistering (da overheating)
        if temp_c > 150.0:
            # Rischio blistering aumenta
            blistering_rate = (temp_c - 150.0) * 0.005
            self.blistering_severity = np.clip(
                self.blistering_severity + blistering_rate, 0.0, 1.0
            )
        elif temp_c < 130.0:
            # Blistering diminuisce se temperatura scende
            self.blistering_severity = max(0.0, self.blistering_severity - 0.01)
        
        # 2. Graining (da slittamento eccessivo a bassa temperatura)
        if abs(slip_ratio) > 0.15 and temp_c < 90.0:
            graining_rate = abs(slip_ratio) * 0.02
            self.graining_level = np.clip(
                self.graining_level + graining_rate, 0.0, 1.0
            )
        
        # 3. Flat spot (da bloccaggio ruota)
        if slip_ratio < -0.8:  # Bloccaggio > 80%
            self.flat_spot = True
    
    def get_grip_loss(self) -> float:
        """
        Restituisce perdita grip dovuta a usura
        
        Returns:
            float % grip perso (0-50)
        """
        # Grip perso = degradazione + blistering + graining
        grip_loss = (
            self.degradation_pct +
            self.blistering_severity * 15.0 +
            self.graining_level * 10.0
        )
        
        if self.flat_spot:
            grip_loss += 20.0  # Flat spot: -20% grip
        
        return np.clip(grip_loss, 0.0, 50.0)
    
    def get_remaining_life_laps(self, avg_degradation_per_lap: float = None) -> float:
        """
        Stima giri residui
        
        Args:
            avg_degradation_per_lap: % usura media per giro (default: 0.3)
        
        Returns:
            float giri stimati residui
        """
        if avg_degradation_per_lap is None:
            # Stima basata su compound
            avg_degradation_per_lap = self.wear_coeff * 0.3
        
        if avg_degradation_per_lap <= 0:
            return 999.0
        
        wear_remaining = 100.0 - self.wear_pct
        laps_remaining = wear_remaining / avg_degradation_per_lap
        
        return max(0.0, laps_remaining)
    
    def get_state(self) -> 'TyreWearState':
        """Restituisce stato usura."""
        return TyreWearState(
            wear_pct=self.wear_pct,
            tread_depth_mm=self.tread_depth_mm,
            degradation_pct=self.degradation_pct,
            blistering_severity=self.blistering_severity,
            graining_level=self.graining_level,
            flat_spot=self.flat_spot
        )
    
    def reset(self):
        """Resetta usura a gomma nuova."""
        self.wear_pct = 0.0
        self.tread_depth_mm = self.TREAD_NEW_MM
        self.degradation_pct = 0.0
        self.blistering_severity = 0.0
        self.graining_level = 0.0
        self.flat_spot = False
    
    def get_summary(self) -> Dict:
        """Riepilogo stato usura."""
        return {
            'wear_pct': self.wear_pct,
            'tread_depth_mm': self.tread_depth_mm,
            'degradation_pct': self.degradation_pct,
            'grip_loss_pct': self.get_grip_loss(),
            'blistering_severity': self.blistering_severity * 100,
            'graining_level': self.graining_level * 100,
            'flat_spot': self.flat_spot,
            'remaining_life_laps': self.get_remaining_life_laps(),
            'compound': self.compound,
            'wear_coeff': self.wear_coeff,
        }
