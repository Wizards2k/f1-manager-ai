"""
Tyre Construction - Costruzione e compound gomme F1 2025 (Physics V4)

Modello fisico completo basato su tyre_model.py V1:
- 5 compound Pirelli (C1-C5) + C6 hyper-soft
- Struttura: carcassa, battistrada, sidewall
- Grip base con gaussian thermal factor
- Sensibilità temperatura, usura, setup
- Graining/blistering con time accumulator

NOTA: Modulo V4 standalone, non dipende da tyre_model.py V1
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np


def gaussian(value: float, center: float, sigma: float) -> float:
    """Curva gaussiana per thermal factor."""
    if sigma <= 0:
        return 0.0
    return np.exp(-((value - center) ** 2) / (2 * sigma ** 2))


@dataclass
class TyreCompoundParams:
    """Parametri completi compound gomma (da V1 tyre_model.py)."""
    name: str
    base_grip: float  # Grip base (1.0 = C3)
    temp_opt_surface: float  # °C temperatura ottimale superficie
    temp_opt_core: float  # °C temperatura ottimale nucleo
    gaussian_sigma_surface_c: float  # σ superficie (~6-8°C)
    gaussian_sigma_core_c: float  # σ nucleo (~5-7°C)
    temp_window_surface_c: Tuple[float, float, float]  # (min, opt, max) superficie
    temp_window_core_c: Tuple[float, float, float]  # (min, opt, max) nucleo
    wear_rate_base_pct_per_km: float  # % usura per km
    degradation_rate_multiplier: float  # 0.6x (C1) ... 1.8x (C6)
    heat_cycle_grip_penalty: float  # % grip perso per heat cycle
    slip_sensitivity: float  # sensibilità grip in curva
    cooling_coeff: float  # coefficiente raffreddamento
    conduction_coeff: float  # coefficiente conduzione surface→core
    thermal_mass_surface: float  # kJ/°C massa termica superficie
    thermal_mass_core: float  # kJ/°C massa termica nucleo
    graining_time_threshold_s: float  # secondi per graining trigger
    blistering_time_threshold_s: float  # secondi per blistering trigger


@dataclass
class TyreState:
    """Stato completo gomma (da V1 data_types.py)."""
    wheel_pos: str  # LF, RF, LR, RR
    compound: str  # C1-C6, INTERMEDIATE, WET
    surface_temp_c: float  # °C temperatura superficiale
    core_temp_c: float  # °C temperatura nucleo
    wear_pct: float  # % usura (0-100)
    effective_grip: float  # grip effettivo (calcolato)
    heat_cycles: int  # numero cicli termici
    graining_level: float  # 0.0-1.0 livello graining
    graining_time_acc_s: float  # secondi accumulati graining
    blistering_level: float  # 0.0-1.0 livello blistering
    blistering_time_acc_s: float  # secondi accumulati blistering
    flatspot_severity: float  # 0.0-1.0 gravità flat spot
    puncture_risk: float  # 0.0-1.0 rischio foratura
    overheat_warning: bool  # Flag overheating
    cold_warning: bool  # Flag gomma fredda


class TyreConstruction:
    """
    Costruzione gomme F1 2025 - Pirelli (basato su V1 tyre_model.py)
    
    Compound disponibili:
    - C1: Hard (durata, grip basso)
    - C2: Medium-Hard (bilanciato)
    - C3: Medium (baseline)
    - C4: Medium-Soft (performance)
    - C5: Soft (grip max, durata bassa)
    - C6: Hyper-soft (Monaco/Imola, grip max, durata minima)
    
    Intermedi:
    - Green: Intermediate (pioggia leggera)
    - Blue: Wet (pioggia pesante)
    """
    
    # Compound slick Pirelli F1 2025 (dati da V1 + docs/TyreModel.md)
    COMPOUNDS: Dict[str, TyreCompoundParams] = {
        'C1': TyreCompoundParams(
            name='C1',
            base_grip=0.92,
            temp_opt_surface=125.0,
            temp_opt_core=102.0,
            gaussian_sigma_surface_c=7.5,
            gaussian_sigma_core_c=6.5,
            temp_window_surface_c=(110.0, 125.0, 140.0),
            temp_window_core_c=(90.0, 102.0, 115.0),
            wear_rate_base_pct_per_km=0.09,
            degradation_rate_multiplier=0.6,
            heat_cycle_grip_penalty=0.008,
            slip_sensitivity=0.75,
            cooling_coeff=1.25,
            conduction_coeff=0.42,
            thermal_mass_surface=1.25,
            thermal_mass_core=3.8,
            graining_time_threshold_s=45.0,
            blistering_time_threshold_s=60.0,
        ),
        'C2': TyreCompoundParams(
            name='C2',
            base_grip=0.95,
            temp_opt_surface=122.0,
            temp_opt_core=99.0,
            gaussian_sigma_surface_c=7.2,
            gaussian_sigma_core_c=6.3,
            temp_window_surface_c=(110.0, 122.0, 135.0),
            temp_window_core_c=(88.0, 99.0, 110.0),
            wear_rate_base_pct_per_km=0.11,
            degradation_rate_multiplier=0.8,
            heat_cycle_grip_penalty=0.010,
            slip_sensitivity=0.80,
            cooling_coeff=1.18,
            conduction_coeff=0.45,
            thermal_mass_surface=1.18,
            thermal_mass_core=3.5,
            graining_time_threshold_s=42.0,
            blistering_time_threshold_s=55.0,
        ),
        'C3': TyreCompoundParams(
            name='C3',
            base_grip=1.00,
            temp_opt_surface=120.0,
            temp_opt_core=96.0,
            gaussian_sigma_surface_c=7.0,
            gaussian_sigma_core_c=6.0,
            temp_window_surface_c=(105.0, 120.0, 135.0),
            temp_window_core_c=(85.0, 96.0, 108.0),
            wear_rate_base_pct_per_km=0.13,
            degradation_rate_multiplier=1.0,
            heat_cycle_grip_penalty=0.012,
            slip_sensitivity=1.00,
            cooling_coeff=1.10,
            conduction_coeff=0.48,
            thermal_mass_surface=1.10,
            thermal_mass_core=3.2,
            graining_time_threshold_s=40.0,
            blistering_time_threshold_s=50.0,
        ),
        'C4': TyreCompoundParams(
            name='C4',
            base_grip=1.06,
            temp_opt_surface=105.0,
            temp_opt_core=90.0,
            gaussian_sigma_surface_c=6.5,
            gaussian_sigma_core_c=5.5,
            temp_window_surface_c=(90.0, 105.0, 120.0),
            temp_window_core_c=(80.0, 90.0, 100.0),
            wear_rate_base_pct_per_km=0.16,
            degradation_rate_multiplier=1.3,
            heat_cycle_grip_penalty=0.015,
            slip_sensitivity=1.15,
            cooling_coeff=0.98,
            conduction_coeff=0.52,
            thermal_mass_surface=0.98,
            thermal_mass_core=2.8,
            graining_time_threshold_s=35.0,
            blistering_time_threshold_s=45.0,
        ),
        'C5': TyreCompoundParams(
            name='C5',
            base_grip=1.12,
            temp_opt_surface=100.0,
            temp_opt_core=85.0,
            gaussian_sigma_surface_c=6.0,
            gaussian_sigma_core_c=5.0,
            temp_window_surface_c=(85.0, 100.0, 115.0),
            temp_window_core_c=(75.0, 85.0, 95.0),
            wear_rate_base_pct_per_km=0.19,
            degradation_rate_multiplier=1.6,
            heat_cycle_grip_penalty=0.018,
            slip_sensitivity=1.30,
            cooling_coeff=0.90,
            conduction_coeff=0.55,
            thermal_mass_surface=0.90,
            thermal_mass_core=2.5,
            graining_time_threshold_s=30.0,
            blistering_time_threshold_s=40.0,
        ),
        'C6': TyreCompoundParams(
            name='C6',
            base_grip=1.18,
            temp_opt_surface=92.0,
            temp_opt_core=80.0,
            gaussian_sigma_surface_c=5.5,
            gaussian_sigma_core_c=4.5,
            temp_window_surface_c=(80.0, 92.0, 105.0),
            temp_window_core_c=(70.0, 80.0, 90.0),
            wear_rate_base_pct_per_km=0.22,
            degradation_rate_multiplier=1.8,
            heat_cycle_grip_penalty=0.020,
            slip_sensitivity=1.45,
            cooling_coeff=0.82,
            conduction_coeff=0.58,
            thermal_mass_surface=0.82,
            thermal_mass_core=2.2,
            graining_time_threshold_s=28.0,
            blistering_time_threshold_s=35.0,
        ),
        'INTERMEDIATE': TyreCompoundParams(
            name='Intermediate',
            base_grip=1.15,  # su bagnato
            temp_opt_surface=80.0,
            temp_opt_core=70.0,
            gaussian_sigma_surface_c=5.0,
            gaussian_sigma_core_c=4.0,
            temp_window_surface_c=(70.0, 80.0, 90.0),
            temp_window_core_c=(60.0, 70.0, 80.0),
            wear_rate_base_pct_per_km=0.10,
            degradation_rate_multiplier=0.5,
            heat_cycle_grip_penalty=0.005,
            slip_sensitivity=0.90,
            cooling_coeff=1.35,
            conduction_coeff=0.40,
            thermal_mass_surface=1.05,
            thermal_mass_core=3.0,
            graining_time_threshold_s=50.0,
            blistering_time_threshold_s=70.0,
        ),
        'WET': TyreCompoundParams(
            name='Wet',
            base_grip=1.10,  # su bagnato
            temp_opt_surface=75.0,
            temp_opt_core=65.0,
            gaussian_sigma_surface_c=4.5,
            gaussian_sigma_core_c=3.5,
            temp_window_surface_c=(65.0, 75.0, 85.0),
            temp_window_core_c=(55.0, 65.0, 75.0),
            wear_rate_base_pct_per_km=0.08,
            degradation_rate_multiplier=0.4,
            heat_cycle_grip_penalty=0.004,
            slip_sensitivity=0.85,
            cooling_coeff=1.40,
            conduction_coeff=0.38,
            thermal_mass_surface=1.00,
            thermal_mass_core=2.8,
            graining_time_threshold_s=55.0,
            blistering_time_threshold_s=80.0,
        ),
    }
    
    def __init__(self, compound: str = 'C3', wheel_pos: str = 'LF'):
        """
        Inizializza gomma
        
        Args:
            compound: nome compound (C1-C6, INTERMEDIATE, WET)
            wheel_pos: posizione ruota (LF, RF, LR, RR)
        """
        if compound not in self.COMPOUNDS:
            raise ValueError(f"Compound {compound} non valido. Usa: {list(self.COMPOUNDS.keys())}")
        
        self.compound = compound
        self.wheel_pos = wheel_pos
        self.params = self.COMPOUNDS[compound]
        
        # Stato iniziale (gomma nuova, temperature ambiente)
        ambient_temp = 25.0
        self.state = TyreState(
            wheel_pos=wheel_pos,
            compound=compound,
            surface_temp_c=ambient_temp,
            core_temp_c=ambient_temp,
            wear_pct=0.0,
            effective_grip=self.params.base_grip,
            heat_cycles=0,
            graining_level=0.0,
            graining_time_acc_s=0.0,
            blistering_level=0.0,
            blistering_time_acc_s=0.0,
            flatspot_severity=0.0,
            puncture_risk=0.0,
            overheat_warning=False,
            cold_warning=True,  # Inizialmente fredda
        )
    
    def get_grip_coefficient(self) -> float:
        """
        Restituisce coefficiente di grip attuale
        
        Considera:
        - Grip base del compound
        - Temperatura (window ottimale)
        - Usura
        
        Returns:
            float mu effettivo (0.5-2.5)
        """
        # Grip base
        mu_base = self.params.base_grip
        
        # Penalità temperatura (fuori window)
        temp_factor = self._calculate_temp_factor()
        
        # Penalità usura
        wear_factor = 1.0 - (self.state.wear_pct / 100.0) * 0.15  # -15% a gomma distrutta
        
        # Grip effettivo
        mu_effective = mu_base * temp_factor * wear_factor
        
        return np.clip(mu_effective, 0.5, 2.5)
    
    def _calculate_temp_factor(self) -> float:
        """
        Calcola fattore grip in funzione temperatura
        
        Returns:
            float 0.5-1.0 (1.0 = window ottimale)
        """
        temp = self.state.surface_temp_c
        t_min = self.params.temp_window_surface_c[0]
        t_max = self.params.temp_window_surface_c[2]
        t_optimal = self.params.temp_opt_surface
        
        if t_min <= temp <= t_max:
            # Window ottimale: grip max
            return 1.0
        elif temp < t_min:
            # Freddo: grip ridotto (warmup necessario)
            delta = t_min - temp
            return max(0.6, 1.0 - delta / 50.0)
        else:
            # Caldo: degradation (overheating)
            delta = temp - t_max
            return max(0.5, 1.0 - delta / 40.0)
    
    def update_temperature(self, ambient_temp: float, load_kn: float, slip_ratio: float, dt: float):
        """
        Aggiorna temperatura gomma
        
        Args:
            ambient_temp: °C temperatura ambiente/pista
            load_kn: kN carico verticale
            slip_ratio: % slittamento
            dt: secondi timestep
        """
        # Riscaldamento da attrito (slip)
        friction_heat = load_kn * slip_ratio * 0.5  # kJ/s
        
        # Riscaldamento da flessione sidewall
        flex_heat = load_kn * 0.05  # kJ/s
        
        # Raffreddamento convettivo (aria)
        cooling = (self.state.surface_temp_c - ambient_temp) * 0.02  # kJ/s
        
        # Variazione temperatura superficiale
        delta_temp = (friction_heat + flex_heat - cooling) * dt / 2.0  # Capacità termica
        
        # Riscaldamento nucleo (più lento)
        delta_core = (self.state.surface_temp_c - self.state.core_temp_c) * 0.01 * dt
        
        # Aggiorna temperature
        self.state.surface_temp_c = np.clip(self.state.surface_temp_c + delta_temp, ambient_temp, 180.0)
        self.state.core_temp_c = np.clip(self.state.core_temp_c + delta_core, ambient_temp, 150.0)
    
    def update_wear(self, load_kn: float, slip_ratio: float, distance_m: float):
        """
        Aggiorna usura gomma
        
        Args:
            load_kn: kN carico verticale
            slip_ratio: % slittamento
            distance_m: metri percorsi
        """
        # Usura base (distanza)
        base_wear = distance_m * 0.0001  # % per metro
        
        # Usura da slittamento (accelerazione/frenata)
        slip_wear = slip_ratio * 0.05  # % per unità slip
        
        # Usura da carico (sovraccarico)
        load_wear = max(0.0, (load_kn - 10.0) * 0.002)  # % per kN sopra 10kN
        
        # Usura totale
        total_wear = (base_wear + slip_wear + load_wear) * self.params.degradation_rate_multiplier
        
        # Aggiorna usura
        self.state.wear_pct = np.clip(self.state.wear_pct + total_wear, 0.0, 100.0)
        
        # Aggiorna grip residuo
        self.state.effective_grip = self.params.base_grip * (1.0 - (self.state.wear_pct / 100.0) * 0.15)
    
    def update_pressure(self, temp_c: float):
        """
        Aggiorna pressione in funzione temperatura
        
        Legge dei gas ideali: P/T = costante
        
        Args:
            temp_c: °C temperatura attuale
        """
        # Pressione di riferimento a 25°C
        p_ref = 2.3  # bar
        t_ref = 25.0 + 273.15  # K
        
        # Temperatura attuale (K)
        t_current = temp_c + 273.15
        
        # Nuova pressione
        p_new = p_ref * (t_current / t_ref)
        
        self.state.pressure_bar = np.clip(p_new, 1.8, 3.0)
    
    def get_state(self) -> 'TyreState':
        """Restituisce stato corrente."""
        return self.state
    
    def is_in_window(self) -> bool:
        """Verifica se gomma in window ottimale."""
        return self.params.temp_window_surface_c[0] <= self.state.surface_temp_c <= self.params.temp_window_surface_c[2]
    
    def get_warmup_progress(self) -> float:
        """
        Restituisce progresso warmup
        
        Returns:
            float 0.0-1.0 (1.0 = warmup completo)
        """
        if self.state.surface_temp_c < self.params.temp_window_surface_c[0]:
            return (self.state.surface_temp_c - 25.0) / (self.params.temp_window_surface_c[0] - 25.0)
        return 1.0
    
    def get_summary(self) -> Dict:
        """Riepilogo gomma."""
        return {
            'compound': self.compound,
            'grip_coefficient': self.get_grip_coefficient(),
            'temp_c': self.state.temp_c,
            'temp_core_c': self.state.temp_core_c,
            'wear_pct': self.state.wear_pct,
            'grip_pct': self.state.grip_pct,
            'pressure_bar': self.state.pressure_bar,
            'in_window': self.is_in_window(),
            'warmup_progress': self.get_warmup_progress(),
        }
