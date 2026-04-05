"""
Tyre Construction - Costruzione e compound gomme F1 2025

Modello fisico della gomma:
- 5 compound Pirelli (C1-C5, da hard a soft)
- Struttura: carcassa, battistrada, sidewall
- Grip base in funzione del compound
- Sensibilità temperatura

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, List
import numpy as np


@dataclass
class TyreCompound:
    """Definizione compound gomma."""
    name: str  # es. "C3", "MEDIUM"
    grip_coefficient: float  # mu base (1.0-2.0)
    optimal_temp_min_c: float  # °C temperatura ottimale minima
    optimal_temp_max_c: float  # °C temperatura ottimale massima
    degradation_rate: float  # % grip perso per giro
    warmup_laps: int  # giri per warmup completo
    durability_laps: int  # giri vita utile


@dataclass
class TyreState:
    """Stato corrente gomma."""
    temp_c: float  # °C temperatura superficiale
    temp_core_c: float  # °C temperatura nucleo
    wear_pct: float  # % usura (0 = nuovo, 100 = distrutto)
    grip_pct: float  # % grip residuo (100 = max)
    pressure_bar: float  # bar pressione
    compound: str  # compound attuale


class TyreConstruction:
    """
    Costruzione gomme F1 2025 - Pirelli
    
    Compound disponibili:
    - C1: Hard (durata, grip basso)
    - C2: Medium-Hard (bilanciato)
    - C3: Medium (compromesso)
    - C4: Medium-Soft (performance)
    - C5: Soft (grip max, durata bassa)
    
    Intermedi:
    - Green: Intermediate (pioggia leggera)
    - Blue: Wet (pioggia pesante)
    """
    
    # Compound slick Pirelli F1 2025
    COMPOUNDS: Dict[str, TyreCompound] = {
        'C1': TyreCompound(
            name='C1',
            grip_coefficient=1.45,
            optimal_temp_min_c=90.0,
            optimal_temp_max_c=110.0,
            degradation_rate=0.15,  # % per giro
            warmup_laps=2,
            durability_laps=45
        ),
        'C2': TyreCompound(
            name='C2',
            grip_coefficient=1.55,
            optimal_temp_min_c=95.0,
            optimal_temp_max_c=115.0,
            degradation_rate=0.20,
            warmup_laps=2,
            durability_laps=38
        ),
        'C3': TyreCompound(
            name='C3',
            grip_coefficient=1.65,
            optimal_temp_min_c=100.0,
            optimal_temp_max_c=120.0,
            degradation_rate=0.28,
            warmup_laps=1,
            durability_laps=30
        ),
        'C4': TyreCompound(
            name='C4',
            grip_coefficient=1.78,
            optimal_temp_min_c=105.0,
            optimal_temp_max_c=125.0,
            degradation_rate=0.38,
            warmup_laps=1,
            durability_laps=22
        ),
        'C5': TyreCompound(
            name='C5',
            grip_coefficient=1.92,
            optimal_temp_min_c=110.0,
            optimal_temp_max_c=130.0,
            degradation_rate=0.50,
            warmup_laps=1,
            durability_laps=15
        ),
        'INTERMEDIATE': TyreCompound(
            name='Intermediate',
            grip_coefficient=1.40,  # su bagnato
            optimal_temp_min_c=70.0,
            optimal_temp_max_c=90.0,
            degradation_rate=0.10,
            warmup_laps=1,
            durability_laps=50
        ),
        'WET': TyreCompound(
            name='Wet',
            grip_coefficient=1.35,  # su bagnato
            optimal_temp_min_c=65.0,
            optimal_temp_max_c=85.0,
            degradation_rate=0.08,
            warmup_laps=1,
            durability_laps=60
        ),
    }
    
    # Grip relativo tra compound (normalizzato a C3=1.0)
    Grip_RELATIVE = {
        'C1': 0.88,
        'C2': 0.94,
        'C3': 1.00,
        'C4': 1.08,
        'C5': 1.16,
    }
    
    def __init__(self, compound: str = 'C3'):
        """
        Inizializza gomma
        
        Args:
            compound: nome compound (C1-C5, INTERMEDIATE, WET)
        """
        if compound not in self.COMPOUNDS:
            raise ValueError(f"Compound {compound} non valido. Usa: {list(self.COMPOUNDS.keys())}")
        
        self.compound = compound
        self.compound_data = self.COMPOUNDS[compound]
        
        # Stato iniziale (gomma nuova)
        self.state = TyreState(
            temp_c=25.0,  # Temperatura ambiente
            temp_core_c=25.0,
            wear_pct=0.0,
            grip_pct=100.0,
            pressure_bar=2.3,  # Pressione ottimale
            compound=compound
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
        mu_base = self.compound_data.grip_coefficient
        
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
        temp = self.state.temp_c
        t_min = self.compound_data.optimal_temp_min_c
        t_max = self.compound_data.optimal_temp_max_c
        t_optimal = (t_min + t_max) / 2.0
        
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
        cooling = (self.state.temp_c - ambient_temp) * 0.02  # kJ/s
        
        # Variazione temperatura superficiale
        delta_temp = (friction_heat + flex_heat - cooling) * dt / 2.0  # Capacità termica
        
        # Riscaldamento nucleo (più lento)
        delta_core = (self.state.temp_c - self.state.temp_core_c) * 0.01 * dt
        
        # Aggiorna temperature
        self.state.temp_c = np.clip(self.state.temp_c + delta_temp, ambient_temp, 180.0)
        self.state.temp_core_c = np.clip(self.state.temp_core_c + delta_core, ambient_temp, 150.0)
    
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
        total_wear = (base_wear + slip_wear + load_wear) * self.compound_data.degradation_rate
        
        # Aggiorna usura
        self.state.wear_pct = np.clip(self.state.wear_pct + total_wear, 0.0, 100.0)
        
        # Aggiorna grip residuo
        self.state.grip_pct = 100.0 - (self.state.wear_pct * 0.15)
    
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
        return self.compound_data.optimal_temp_min_c <= self.state.temp_c <= self.compound_data.optimal_temp_max_c
    
    def get_warmup_progress(self) -> float:
        """
        Restituisce progresso warmup
        
        Returns:
            float 0.0-1.0 (1.0 = warmup completo)
        """
        if self.state.temp_c < self.compound_data.optimal_temp_min_c:
            return (self.state.temp_c - 25.0) / (self.compound_data.optimal_temp_min_c - 25.0)
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
