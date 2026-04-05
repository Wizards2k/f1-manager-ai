"""
ICE Engine - Motore termico F1 2025 (Physics V4)

Modello fisico del motore endotermico per V4:
- Torque curve da lookup table (RPM → Nm)
- Fuel flow limit (100kg/h → potenza max)
- Consumo carburante (1.35-1.5 kg/giro)
- Engine braking (freno motore)
- Derating termico

NOTA: Modulo V4 standalone, non dipende da power_unit.py V1
"""

from dataclasses import dataclass
from typing import Dict, List
import numpy as np


@dataclass
class ICEState:
    """Stato corrente motore termico."""
    rpm: float  # giri/min
    torque_nm: float  # Nm coppia erogata
    power_kw: float  # kW potenza erogata
    fuel_flow_kg_s: float  # kg/s consumo istantaneo
    throttle_pct: float  # % apertura farfalla
    temp_c: float  # °C temperatura motore


class ICEEngine:
    """
    Motore termico F1 2025 - 1.6L V6 Turbo
    
    Specifiche:
    - Potenza max: ~850 CV (630 kW) a 12000 RPM
    - Coppia max: ~600 Nm a 8000 RPM
    - Fuel flow limit: 100 kg/h (regolamento FIA)
    - Redline: 15000 RPM (cambio a 12000-12500)
    
    La curva di coppia include il torque fill dell'MGU-K
    per simulare l'erogazione combinata.
    """
    
    def __init__(self, config=None):
        """
        Inizializza motore termico
        
        Args:
            config: dict con parametri personalizzati
        """
        # Lookup table coppia (RPM → Nm) - dati reali F1 2025
        self.torque_table = [
            (0, 0),           # Spento
            (1500, 180),      # Turbo spooling
            (4000, 480),      # Uscita curve lente
            (6500, 590),      # Peak acceleration
            (8500, 610),      # Max coppia ICE
            (10500, 575),     # Fuel flow limit
            (11500, 525),     # Optimal shift
            (12500, 480),     # Power dropoff
            (13500, 400),     # Over-rev (inutile)
        ]
        
        defaults = {
            'displacement_l': 1.6,      # L cilindrata
            'cylinders': 6,             # V6
            'turbo': True,              # Turbocharger
            'fuel_flow_limit_kg_h': 100.0,  # kg/h limite FIA
            'idle_rpm': 4500,           # giri/min minimo
            'redline_rpm': 15000,       # giri/min massimo
            'shift_rpm': 12500,         # giri/min cambio marcia
            'bsfc_kg_kwh': 0.250,       # kg/kWh consumo specifico
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Stato corrente
        self.state = ICEState(
            rpm=0.0,
            torque_nm=0.0,
            power_kw=0.0,
            fuel_flow_kg_s=0.0,
            throttle_pct=0.0,
            temp_c=90.0  # Temperatura operativa
        )
    
    def get_torque_at_rpm(self, rpm: float) -> float:
        """
        Restituisce coppia motore a un dato RPM
        
        Args:
            rpm: giri/min
        
        Returns:
            Nm coppia (interpolata linearmente)
        """
        rpm = np.clip(rpm, 0, self.config['redline_rpm'])
        
        # Interpolazione lineare nella lookup table
        for i in range(len(self.torque_table) - 1):
            rpm_low, torque_low = self.torque_table[i]
            rpm_high, torque_high = self.torque_table[i + 1]
            
            if rpm_low <= rpm <= rpm_high:
                # Interpolazione
                ratio = (rpm - rpm_low) / (rpm_high - rpm_low)
                torque = torque_low + (torque_high - torque_low) * ratio
                return torque
        
        # Fuori range (oltre redline)
        return self.torque_table[-1][1]
    
    def calculate_power(self, rpm: float, throttle_pct: float) -> float:
        """
        Calcola potenza motore
        
        Args:
            rpm: giri/min
            throttle_pct: % apertura farfalla (0-100)
        
        Returns:
            kW potenza erogata
        """
        # Coppia base da RPM
        torque_base = self.get_torque_at_rpm(rpm)
        
        # Applica apertura farfalla
        torque = torque_base * (throttle_pct / 100.0)
        
        # Potenza = Coppia × Velocità angolare
        # P (kW) = T (Nm) × ω (rad/s) / 1000
        omega_rad_s = rpm * 2 * np.pi / 60
        power_kw = (torque * omega_rad_s) / 1000
        
        return power_kw
    
    def calculate_fuel_flow(self, power_kw: float) -> float:
        """
        Calcola consumo carburante
        
        Args:
            power_kw: kW potenza erogata
        
        Returns:
            kg/s consumo istantaneo
        """
        # BSFC (Brake Specific Fuel Consumption)
        # F1 2025: ~0.250 kg/kWh (efficienza ~50%)
        bsfc = self.config['bsfc_kg_kwh']
        
        # Consumo = Potenza × BSFC
        # kg/h = kW × kg/kWh
        fuel_flow_kg_h = power_kw * bsfc
        
        # Clamp a fuel flow limit FIA
        fuel_flow_kg_h = min(fuel_flow_kg_h, self.config['fuel_flow_limit_kg_h'])
        
        # Converte a kg/s
        return fuel_flow_kg_h / 3600.0
    
    def get_engine_braking_torque(self, rpm: float) -> float:
        """
        Coppia di freno motore (quando throttle = 0)
        
        Args:
            rpm: giri/min
        
        Returns:
            Nm coppia frenante (negativa)
        """
        # Freno motore: ~15-20% della coppia max
        torque_base = self.get_torque_at_rpm(rpm)
        
        # Freno motore aumenta con RPM
        rpm_factor = rpm / self.config['shift_rpm']
        
        # Tipicamente -50 a -150 Nm
        braking_torque = -torque_base * 0.15 * rpm_factor
        
        return np.clip(braking_torque, -200, 0)
    
    def update_state(
        self,
        rpm: float,
        throttle_pct: float,
        dt: float,
        ambient_temp: float = 25.0
    ) -> ICEState:
        """
        Aggiorna stato motore
        
        Args:
            rpm: giri/min
            throttle_pct: % apertura farfalla
            dt: secondi timestep
            ambient_temp: °C temperatura ambiente
        
        Returns:
            ICEState aggiornato
        """
        # Calcola potenza
        power_kw = self.calculate_power(rpm, throttle_pct)
        
        # Calcola consumo
        fuel_flow = self.calculate_fuel_flow(power_kw)
        
        # Aggiorna temperatura (semplificato)
        # Riscaldamento: proporzionale a potenza
        # Raffreddamento: proporzionale a differenza con ambiente
        heat_gen = power_kw * 0.35  # 35% energia → calore
        heat_diss = (self.state.temp_c - ambient_temp) * 0.05
        
        delta_temp = (heat_gen - heat_diss) * dt / 10.0  # Capacità termica
        new_temp = np.clip(self.state.temp_c + delta_temp, ambient_temp, 120.0)
        
        # Aggiorna stato
        self.state = ICEState(
            rpm=rpm,
            torque_nm=self.get_torque_at_rpm(rpm) * (throttle_pct / 100.0),
            power_kw=power_kw,
            fuel_flow_kg_s=fuel_flow,
            throttle_pct=throttle_pct,
            temp_c=new_temp
        )
        
        return self.state
    
    def get_fuel_consumed_per_lap(self, lap_time_s: float, avg_power_kw: float) -> float:
        """
        Stima consumo carburante per giro
        
        Args:
            lap_time_s: secondi tempo giro
            avg_power_kw: kW potenza media
        
        Returns:
            kg carburante consumato
        """
        fuel_flow = self.calculate_fuel_flow(avg_power_kw)
        return fuel_flow * lap_time_s
    
    def get_summary(self) -> Dict:
        """Riepilogo specifiche motore."""
        return {
            'displacement_l': self.config['displacement_l'],
            'cylinders': self.config['cylinders'],
            'turbo': self.config['turbo'],
            'fuel_flow_limit_kg_h': self.config['fuel_flow_limit_kg_h'],
            'idle_rpm': self.config['idle_rpm'],
            'redline_rpm': self.config['redline_rpm'],
            'shift_rpm': self.config['shift_rpm'],
            'max_power_kw': ICE_BASE_POWER_KW,
            'max_torque_nm': 610,
        }


# Costante potenza base ICE
ICE_BASE_POWER_KW = 630.0  # ~850 CV
