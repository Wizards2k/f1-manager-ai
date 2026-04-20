"""
Tyre Thermal - Modello termico gomme F1 2025

Gestione temperature gomme:
- Riscaldamento da attrito (slip, carico)
- Raffreddamento convettivo (aria, velocità)
- Gradiente superficiale/nucleo
- Overheating e blistering

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass, field
from typing import Dict
import numpy as np


@dataclass
class TireState:
	"""Tire state for SINGLE WHEEL (FL, FR, RL, RR each have separate instance) - V6.3."""
	surface_temp_c: float = 85.0  # °C, reactive to friction/cooling
	core_temp_c: float = 75.0     # °C, inertial, slower change
	wear_pct: float = 0.0         # Cumulative wear [0-100]
	is_graining: bool = False     # Graining flag
	is_blistering: bool = False   # Blistering flag


@dataclass
class TiresState:
	"""Container for all 4 wheels tire state (V6.3) - per-wheel independent tracking."""
	fl: TireState = field(default_factory=TireState)  # Front Left
	fr: TireState = field(default_factory=TireState)  # Front Right
	rl: TireState = field(default_factory=TireState)  # Rear Left
	rr: TireState = field(default_factory=TireState)  # Rear Right

	def reset_at_pit_stop(self):
		"""Reset all tires at pit stop (new tires)."""
		self.fl = TireState(surface_temp_c=85.0, core_temp_c=75.0, wear_pct=0.0)
		self.fr = TireState(surface_temp_c=85.0, core_temp_c=75.0, wear_pct=0.0)
		self.rl = TireState(surface_temp_c=85.0, core_temp_c=75.0, wear_pct=0.0)
		self.rr = TireState(surface_temp_c=85.0, core_temp_c=75.0, wear_pct=0.0)


@dataclass
class BrakeState:
	"""V6.3: Brake thermal state (front/rear separated)."""
	temp_front_c: float = 20.0  # °C initial (cold)
	temp_rear_c: float = 20.0   # °C initial (cold)
	heat_accumulated_kj: float = 0.0  # Accumulator for sub-step thermal integration


@dataclass
class TyreThermalState:
    """Stato termico gomma."""
    surface_temp_c: float  # °C temperatura superficiale
    core_temp_c: float  # °C temperatura nucleo
    temp_gradient_c: float  # °C differenza superficie-nucleo
    overheating: bool  # Flag overheating attivo
    blistering_risk: float  # 0.0-1.0 rischio blistering


class TyreThermal:
    """
    Modello termico gomme F1 2025
    
    Temperature critiche:
    - < 70°C: freddo, grip ridotto
    - 90-130°C: window ottimale (dipende compound)
    - > 140°C: overheating, degradation
    - > 160°C: blistering, danno permanente
    
    Meccanismi:
    - Riscaldamento: attrito, flessione, frenata
    - Raffreddamento: convezione aria, conduzione nucleo
    """
    
    # Soglie termiche
    TEMP_COLD = 70.0        # °C gomma fredda
    TEMP_HOT_WARNING = 140.0  # °C warning overheating
    TEMP_HOT_CRITICAL = 160.0  # °C blistering
    
    # Parametri fisici
    MASS_SURFACE_KG = 2.5   # kg massa battistrada
    MASS_CORE_KG = 8.0      # kg massa nucleo
    CP_SURFACE = 1800.0     # J/kg·K capacità termica superficie
    CP_CORE = 2000.0        # J/kg·K capacità termica nucleo
    
    def __init__(self, ambient_temp: float = 25.0):
        """
        Inizializza modello termico
        
        Args:
            ambient_temp: °C temperatura ambiente/pista
        """
        self.ambient_temp = ambient_temp
        self.track_temp = ambient_temp + 15.0  # Pista più calda
        
        # Temperature iniziali
        self.surface_temp = ambient_temp
        self.core_temp = ambient_temp
        
        # Stato
        self.overheating = False
        self.blistering_risk = 0.0
    
    def calculate_heating(
        self,
        load_kn: float,
        slip_ratio: float,
        slip_angle_deg: float,
        v_car_kph: float,
        dt: float
    ) -> float:
        """
        Calcola riscaldamento gomma
        
        Args:
            load_kn: kN carico verticale
            slip_ratio: % slittamento longitudinale
            slip_angle_deg: gradi slittamento angolare
            v_car_kph: kph velocità vettura
            dt: secondi timestep
        
        Returns:
            kJ calore generato
        """
        # 1. Riscaldamento da slip longitudinale (accelerazione/frenata)
        # Q = F × slip × dt
        f_long = load_kn * slip_ratio  # kN forza longitudinale
        q_slip_long = f_long * slip_ratio * 1000.0 * dt  # J
        
        # 2. Riscaldamento da slip angolare (curva)
        slip_angle_rad = np.radians(slip_angle_deg)
        f_lat = load_kn * np.sin(slip_angle_rad)  # kN forza laterale
        q_slip_lat = f_lat * slip_angle_rad * 1000.0 * dt  # J
        
        # 3. Riscaldamento da flessione sidewall
        # Proporzionale a carico e distanza percorsa
        distance_m = v_car_kph * dt / 3.6
        q_flex = load_kn * distance_m * 50.0  # J (50 J/m per kN)
        
        # 4. Riscaldamento da frenata (brake drag)
        # Trascurabile in accelerazione
        
        # Totale calore generato
        q_total = q_slip_long + q_slip_lat + q_flex
        
        return q_total / 1000.0  # kJ
    
    def calculate_cooling(self, v_car_kph: float, dt: float) -> float:
        """
        Calcola raffreddamento gomma
        
        Args:
            v_car_kph: kph velocità vettura
            dt: secondi timestep
        
        Returns:
            kJ calore dissipato
        """
        # 1. Raffreddamento convettivo (aria)
        # h = coefficiente convezione (dipende da velocità)
        h = 10.0 + 0.5 * v_car_kph  # W/m²·K
        
        # Area superficiale gomma (~0.5 m²)
        area = 0.5
        
        # Differenza temperatura
        delta_t = max(self.surface_temp - self.ambient_temp, 0.0)
        
        # Q = h × A × ΔT × dt
        q_conv = h * area * delta_t * dt  # J
        
        # 2. Raffreddamento per irraggiamento
        # Trascurabile rispetto a convezione
        
        # 3. Conduzione verso nucleo (se superficie più calda)
        if self.surface_temp > self.core_temp:
            q_conduction = (self.surface_temp - self.core_temp) * 50.0 * dt  # J
        else:
            q_conduction = 0.0
        
        # Totale calore dissipato
        q_total = q_conv + q_conduction
        
        return q_total / 1000.0  # kJ
    
    def update_temperatures(
        self,
        load_kn: float,
        slip_ratio: float,
        slip_angle_deg: float,
        v_car_kph: float,
        dt: float
    ):
        """
        Aggiorna temperature gomma
        
        Args:
            load_kn: kN carico verticale
            slip_ratio: % slittamento longitudinale
            slip_angle_deg: gradi slittamento angolare
            v_car_kph: kph velocità vettura
            dt: secondi timestep
        """
        # Calore generato
        q_gen = self.calculate_heating(load_kn, slip_ratio, slip_angle_deg, v_car_kph, dt)
        
        # Calore dissipato
        q_cool = self.calculate_cooling(v_car_kph, dt)
        
        # Bilancio termico superficie
        # ΔT = Q / (m × cp)
        net_energy_surface = q_gen * 0.7 - q_cool  # 70% calore va in superficie
        delta_t_surface = (net_energy_surface * 1000.0) / (self.MASS_SURFACE_KG * self.CP_SURFACE)
        
        # Bilancio termico nucleo
        # Riscaldamento più lento (inerzia termica)
        net_energy_core = q_gen * 0.3  # 30% calore va nel nucleo
        delta_t_core = (net_energy_core * 1000.0) / (self.MASS_CORE_KG * self.CP_CORE)
        
        # Aggiorna temperature
        self.surface_temp = np.clip(self.surface_temp + delta_t_surface, self.ambient_temp, 200.0)
        self.core_temp = np.clip(self.core_temp + delta_t_core, self.ambient_temp, 180.0)
        
        # Aggiorna stato
        self._update_state()
    
    def _update_state(self):
        """Aggiorna stato termico (overheating, blistering)."""
        # Overheating
        self.overheating = self.surface_temp > self.TEMP_HOT_WARNING
        
        # Blistering risk
        if self.surface_temp > self.TEMP_HOT_CRITICAL:
            # Rischio aumenta esponenzialmente
            excess = self.surface_temp - self.TEMP_HOT_CRITICAL
            self.blistering_risk = np.clip(excess / 20.0, 0.0, 1.0)
        else:
            # Diminuisce gradualmente
            self.blistering_risk = max(0.0, self.blistering_risk - 0.01)
    
    def get_thermal_state(self) -> 'TyreThermalState':
        """Restituisce stato termico."""
        return TyreThermalState(
            surface_temp_c=self.surface_temp,
            core_temp_c=self.core_temp,
            temp_gradient_c=self.surface_temp - self.core_temp,
            overheating=self.overheating,
            blistering_risk=self.blistering_risk
        )
    
    def reset(self, ambient_temp: float = None):
        """
        Resetta temperature a ambiente
        
        Args:
            ambient_temp: °C nuova temperatura ambiente
        """
        if ambient_temp is not None:
            self.ambient_temp = ambient_temp
            self.track_temp = ambient_temp + 15.0
        
        self.surface_temp = self.ambient_temp
        self.core_temp = self.ambient_temp
        self.overheating = False
        self.blistering_risk = 0.0
    
    def get_summary(self) -> Dict:
        """Riepilogo stato termico."""
        return {
            'surface_temp_c': self.surface_temp,
            'core_temp_c': self.core_temp,
            'temp_gradient_c': self.surface_temp - self.core_temp,
            'overheating': self.overheating,
            'blistering_risk': self.blistering_risk * 100,
            'ambient_temp_c': self.ambient_temp,
            'track_temp_c': self.track_temp,
        }
