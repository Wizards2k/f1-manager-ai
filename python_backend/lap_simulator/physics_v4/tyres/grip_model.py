"""
Tyre Grip Model - Modello grip gomme F1 2025

Integra tutti i fattori grip:
- Compound base
- Temperatura (window ottimale)
- Usura e degradazione
- Carico verticale (load sensitivity)
- Slip angle/ratio (friction circle)

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np

from .tyre_construction import TyreConstruction, TyreCompoundParams
from .tyre_thermal import TyreThermal
from .tyre_wear import TyreWear
from ..core.constants import TYRE_LOAD_SENSITIVITY_EXP, TYRE_LOAD_REF_KN


def gaussian(value: float, center: float, sigma: float) -> float:
    """Curva gaussiana per thermal factor (da V1 tyre_model.py)."""
    if sigma <= 0:
        return 0.0
    return np.exp(-((value - center) ** 2) / (2 * sigma ** 2))


@dataclass
class GripState:
    """Stato grip gomma."""
    mu_effective: float  # coefficiente attrito effettivo
    mu_peak: float  # coefficiente attrito di picco
    grip_pct: float  # % grip residuo (0-100)
    in_window: bool  # flag temperatura ottimale
    load_sensitivity: float  # fattore sensibilità carico


class TyreGripModel:
    """
    Modello grip gomme F1 2025
    
    Il grip è determinato da:
    1. Compound base (C1-C5): mu = 1.45-1.92
    2. Temperatura: window 90-130°C (grip max)
    3. Usura: -15% grip a gomma distrutta
    4. Carico: grip diminuisce con carico (load sensitivity)
    5. Slip: friction circle (combinazione longitudinale/laterale)
    
    Equazione grip:
    mu_eff = mu_base × f_temp × f_wear × f_load × f_slip
    """
    
    def __init__(
        self,
        compound: str = 'C3',
        ambient_temp: float = 25.0,
        track_abrasiveness: float = 1.0
    ):
        """
        Inizializza modello grip
        
        Args:
            compound: nome compound (C1-C5)
            ambient_temp: °C temperatura ambiente
            track_abrasiveness: 0.5-2.0 abrasività pista
        """
        # Componenti
        self.construction = TyreConstruction(compound)
        self.thermal = TyreThermal(ambient_temp)
        self.wear = TyreWear(compound, track_abrasiveness)
        
        # Parametri
        self.compound = compound
        # Load sensitivity: grip diminuisce con carico secondo legge di potenza
        # μ(Fz) = μ₀ × (Fz / Fz_ref)^(-α), α = 0.25 per F1
        self.load_sensitivity_exp = TYRE_LOAD_SENSITIVITY_EXP
        self.load_ref_kn = TYRE_LOAD_REF_KN
    
    def calculate_grip(
        self,
        load_kn: float,
        slip_ratio: float,
        slip_angle_deg: float,
        v_car_kph: float,
        dt: float
    ) -> 'GripState':
        """
        Calcola grip effettivo per condizioni date
        
        Args:
            load_kn: kN carico verticale
            slip_ratio: % slittamento longitudinale
            slip_angle_deg: gradi slittamento angolare
            v_car_kph: kph velocità vettura
            dt: secondi timestep
        
        Returns:
            GripState con grip effettivo
        """
        # 1. Aggiorna temperature
        self.thermal.update_temperatures(load_kn, slip_ratio, slip_angle_deg, v_car_kph, dt)
        
        # 2. Aggiorna usura
        self.wear.update_wear(load_kn, slip_ratio, slip_angle_deg, v_car_kph, self.thermal.surface_temp, dt)
        
        # 3. Aggiorna construction (pressione, grip)
        self.construction.state.temp_c = self.thermal.surface_temp
        self.construction.state.temp_core_c = self.thermal.core_temp
        self.construction.update_pressure(self.thermal.surface_temp)
        
        # 4. Calcola grip effettivo
        mu_effective = self._calculate_effective_mu(load_kn, slip_ratio, slip_angle_deg)
        
        # 5. Calcola grip di picco (per friction circle)
        mu_peak = self._calculate_peak_mu()
        
        # 6. Stato grip
        grip_pct = 100.0 - self.wear.get_grip_loss()
        in_window = self.construction.is_in_window()
        
        return GripState(
            mu_effective=mu_effective,
            mu_peak=mu_peak,
            grip_pct=grip_pct,
            in_window=in_window,
            load_sensitivity=self.load_sensitivity
        )
    
    def _calculate_effective_mu(self, load_kn: float, slip_ratio: float, slip_angle_deg: float) -> float:
        """
        Calcola coefficiente attrito effettivo
        
        Args:
            load_kn: kN carico verticale
            slip_ratio: % slittamento
            slip_angle_deg: gradi slip angolare
        
        Returns:
            float mu effettivo
        """
        # 1. Grip base da compound (include temperatura)
        mu_base = self.construction.get_grip_coefficient()
        
        # 2. Penalità usura
        wear_factor = 1.0 - (self.wear.get_grip_loss() / 100.0)
        
        # 3. Penalità carico (load sensitivity) - FISICAMENTE CORRETTA
        # Formula: μ(Fz) = μ₀ × (Fz / Fz_ref)^(-α)
        # Grip diminuisce con carico secondo legge di potenza (non lineare)
        # α = 0.25 per gomme F1 (sperimentalmente determinato)
        load_ratio = load_kn / self.load_ref_kn
        load_factor = load_ratio ** (-self.load_sensitivity_exp)
        
        # 4. Penalità slip (friction circle)
        # Grip disponibile diminuisce con slip elevato
        slip_magnitude = np.sqrt(slip_ratio ** 2 + np.radians(slip_angle_deg) ** 2)
        slip_factor = 1.0 - min(slip_magnitude * 0.3, 0.3)  # Max -30%
        
        # Grip effettivo
        mu_effective = mu_base * wear_factor * load_factor * slip_factor
        
        return np.clip(mu_effective, 0.3, 2.5)
    
    def _calculate_peak_mu(self) -> float:
        """
        Calcola grip di picco (condizioni ideali)
        
        Returns:
            float mu di picco
        """
        # Grip base (senza penalità)
        mu_base = self.construction.params.base_grip
        
        # Penalità usura (solo degradazione, non temperatura)
        wear_factor = 1.0 - (self.wear.wear_pct / 100.0) * 0.15
        
        return np.clip(mu_base * wear_factor, 0.5, 2.5)
    
    def get_max_lateral_g(self, load_kn: float) -> float:
        """
        Calcola accelerazione laterale massima (g)
        
        Args:
            load_kn: kN carico verticale
        
        Returns:
            float g laterali massime
        """
        mu_peak = self._calculate_peak_mu()
        
        # F_max = mu × F_load
        # a_max = F_max / m = mu × g
        from ..core.constants import G
        
        max_lateral_g = mu_peak * G / G  # Normalizzato a g
        
        return max_lateral_g
    
    def get_max_longitudinal_g(self, load_kn: float, is_braking: bool = True) -> float:
        """
        Calcola accelerazione/decelerazione massima (g)
        
        Args:
            load_kn: kN carico verticale
            is_braking: True = frenata, False = accelerazione
        
        Returns:
            float g massime
        """
        mu_peak = self._calculate_peak_mu()
        
        # Frenata: grip leggermente superiore (pneumatici ottimizzati)
        if is_braking:
            mu_braking = mu_peak * 1.05
        else:
            mu_braking = mu_peak * 0.95  # Trazione: grip inferiore
        
        from ..core.constants import G
        max_long_g = mu_braking * G / G
        
        return max_long_g
    
    def get_friction_circle_radius(self, load_kn: float) -> float:
        """
        Calcola raggio friction circle (g)
        
        Il friction circle definisce il grip combinato:
        sqrt(g_lat² + g_lon²) ≤ radius
        
        Args:
            load_kn: kN carico verticale
        
        Returns:
            float raggio friction circle (g)
        """
        mu_peak = self._calculate_peak_mu()
        
        # Raggio = mu_peak (in g)
        return mu_peak
    
    def is_in_optimal_window(self) -> bool:
        """Verifica se gomma in window ottimale."""
        return self.construction.is_in_window()
    
    def get_warmup_progress(self) -> float:
        """Restituisce progresso warmup."""
        return self.construction.get_warmup_progress()
    
    def get_state(self) -> Dict:
        """Restituisce stato completo gomma."""
        grip_state = self.calculate_grip(10.0, 0.0, 0.0, 0.0, 0.0)
        
        return {
            'compound': self.compound,
            'mu_effective': grip_state.mu_effective,
            'mu_peak': grip_state.mu_peak,
            'grip_pct': grip_state.grip_pct,
            'in_window': grip_state.in_window,
            'temp_surface_c': self.thermal.surface_temp,
            'temp_core_c': self.thermal.core_temp,
            'wear_pct': self.wear.wear_pct,
            'tread_depth_mm': self.wear.tread_depth_mm,
            'pressure_bar': self.construction.state.pressure_bar,
            'overheating': self.thermal.overheating,
            'blistering_risk': self.thermal.blistering_risk * 100,
            'graining_level': self.wear.graining_level * 100,
            'flat_spot': self.wear.flat_spot,
        }
    
    def reset(self, ambient_temp: float = None):
        """Resetta gomma a stato nuovo."""
        if ambient_temp is not None:
            self.thermal.reset(ambient_temp)
        else:
            self.thermal.reset()
        
        self.wear.reset()
        self.construction.state.temp_c = self.thermal.surface_temp
        self.construction.state.temp_core_c = self.thermal.core_temp
        self.construction.state.wear_pct = 0.0
        self.construction.state.grip_pct = 100.0
    
    def get_summary(self) -> Dict:
        """Riepilogo completo gomma."""
        return {
            'construction': self.construction.get_summary(),
            'thermal': self.thermal.get_summary(),
            'wear': self.wear.get_summary(),
            'current_state': self.get_state(),
        }
