"""
PU Physics - Power Unit fisica integrata (Physics V4)

Integra tutti i componenti PU per V4:
- ICE engine (torque curve, fuel flow)
- ERS deploy (batteria, MGU-H direct)
- Thermal model (clipping, derating)

Output: potenza totale in kW per l'integratore

NOTA: Modulo V4 standalone, non dipende da power_unit.py V1
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np

from .ice_engine import ICEEngine, ICEState, ICE_BASE_POWER_KW
from .ers_deploy import ERSDeployManager, DeployRequest, ERSEnergyState
from .thermal_model import ThermalModel, ThermalState


@dataclass
class PUOutput:
    """Output Power Unit per un timestep."""
    ice_power_kw: float  # kW potenza ICE
    ers_power_kw: float  # kW potenza ERS
    total_power_kw: float  # kW potenza totale
    fuel_flow_kg_s: float  # kg/s consumo istantaneo
    ice_derating: float  # 0.0-1.0 fattore derating ICE
    ers_derating: float  # 0.0-1.0 fattore derating ERS
    ice_temp_c: float  # °C temperatura ICE
    ers_temp_c: float  # °C temperatura ERS
    soc_pct: float  # % stato carica batteria


class PUPhysics:
    """
    Power Unit integrata per Physics V4
    
    Combina:
    - ICEEngine: coppia, potenza, consumo
    - ERSDeployManager: gestione energia strategica
    - ThermalModel: derating termico
    
    Utilizzo tipico nell'integratore V4:
    ```python
    pu = PUPhysics()
    for waypoint in waypoints:
        output = pu.step(
            throttle=driver.throttle,
            rpm=car.rpm,
            v_kph=car.v_kph,
            priority=waypoint.priority,
            dt=dt
        )
        # Usa output.total_power_kw per accelerazione
    ```
    """
    
    def __init__(self, config=None):
        """
        Inizializza Power Unit V4
        
        Args:
            config: dict con parametri personalizzati
        """
        # Componenti
        self.ice_engine = ICEEngine()
        self.ers_manager = ERSDeployManager(config)
        self.thermal_model = ThermalModel()
        
        # Configurazione
        defaults = {
            'ice_base_power_kw': ICE_BASE_POWER_KW,
            'ers_max_power_kw': 120.0,
            'fuel_save_mode': False,
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Output ultimo step
        self.last_output = None
    
    def step(
        self,
        throttle_pct: float,
        rpm: float,
        v_kph: float,
        section_priority: float,
        is_drs: bool,
        is_corner: bool,
        dt: float,
    ) -> PUOutput:
        """
        Calcola output PU per un timestep
        
        Args:
            throttle_pct: % apertura farfalla (0-100)
            rpm: giri/min motore
            v_kph: kph velocità vettura
            section_priority: 0.0-1.0 priorità sezione
            is_drs: flag DRS attivo
            is_corner: flag curva
            dt: secondi timestep
        
        Returns:
            PUOutput con potenze e stati
        """
        # 1. Calcola richiesta ERS
        ers_request = self.ers_manager.calculate_deploy_request(
            section_priority=section_priority,
            section_length_m=v_kph * dt / 3.6,  # metri percorsi
            v_car_kph=v_kph,
            dt=dt,
            is_drs=is_drs,
            is_corner=is_corner
        )
        
        # 2. Calcola potenza ICE (senza derating)
        ice_power_raw = self.ice_engine.calculate_power(rpm, throttle_pct)
        
        # 3. Calcola derating termici
        ice_derating = self.thermal_model.calculate_ice_derating(
            ice_power_kw=ice_power_raw,
            v_car_kph=v_kph,
            dt=dt
        )
        
        ers_derating = self.thermal_model.calculate_ers_derating(
            ers_power_kw=ers_request.total_ers_kw,
            v_car_kph=v_kph,
            dt=dt
        )
        
        # 4. Applica derating
        ice_power_kw = ice_power_raw * ice_derating
        ers_power_kw = ers_request.total_ers_kw * ers_derating
        
        # 5. Fuel save mode (opzionale)
        if self.config['fuel_save_mode']:
            ice_power_kw *= 0.85
        
        # 6. Potenza totale
        total_power_kw = ice_power_kw + ers_power_kw
        
        # 7. Consumo carburante
        fuel_flow = self.ice_engine.calculate_fuel_flow(ice_power_kw)
        
        # 8. Aggiorna stato ICE
        self.ice_engine.update_state(rpm, throttle_pct, dt)
        
        # 9. Consuma energia ERS
        battery_mj = (ers_request.battery_power_kw * dt) / 1000.0
        mguh_mj = (ers_request.mguh_direct_kw * dt) / 1000.0
        
        # Harvest da frenata (se brake > 0)
        harvest_mj = 0.0
        if throttle_pct < 1.0:  # Rilascio acceleratore
            # Stima semplificata: recupero proporzionale a decelerazione
            brake_intensity = 1.0 - (throttle_pct / 100.0)
            harvest_mj = brake_intensity * 0.05  # ~0.05 MJ per frenata media
        
        self.ers_manager.consume_energy(battery_mj, mguh_mj, harvest_mj)
        
        # 10. Crea output
        energy_state = self.ers_manager.get_energy_state()
        
        self.last_output = PUOutput(
            ice_power_kw=ice_power_kw,
            ers_power_kw=ers_power_kw,
            total_power_kw=total_power_kw,
            fuel_flow_kg_s=fuel_flow,
            ice_derating=ice_derating,
            ers_derating=ers_derating,
            ice_temp_c=self.thermal_model.ice_temp,
            ers_temp_c=self.thermal_model.ers_temp,
            soc_pct=energy_state.soc_pct
        )
        
        return self.last_output
    
    def get_ice_state(self) -> ICEState:
        """Restituisce stato motore ICE."""
        return self.ice_engine.state
    
    def get_ers_state(self) -> 'ERSEnergyState':
        """Restituisce stato energia ERS."""
        return self.ers_manager.get_energy_state()
    
    def get_thermal_state(self) -> ThermalState:
        """Restituisce stato termico."""
        if self.last_output:
            return ThermalState(
                ice_temp_c=self.last_output.ice_temp_c,
                ers_temp_c=self.last_output.ers_temp_c,
                ice_derating=self.last_output.ice_derating,
                ers_derating=self.last_output.ers_derating,
                ers_clipping_active=(self.last_output.ers_derating < 0.95)
            )
        return self.thermal_model.get_thermal_state(0.0, 0.0, 0.0)
    
    def reset(self, ambient_temp: float = 25.0):
        """Resetta tutti gli stati per nuovo giro."""
        self.ice_engine.state.temp_c = ambient_temp
        self.ers_manager.reset_lap()
        self.thermal_model.reset(ambient_temp)
        self.last_output = None
    
    def set_fuel_save_mode(self, enabled: bool):
        """Attiva/disattiva modalità risparmio carburante."""
        self.config['fuel_save_mode'] = enabled
    
    def set_ambient_temp(self, temp_c: float):
        """Imposta temperatura ambiente."""
        self.thermal_model.set_ambient_temp(temp_c)
    
    def get_summary(self) -> Dict:
        """Riepilogo stato PU."""
        return {
            'ice': self.ice_engine.get_summary(),
            'ers': self.ers_manager.get_summary(),
            'thermal': self.thermal_model.get_summary(),
            'config': self.config,
        }
