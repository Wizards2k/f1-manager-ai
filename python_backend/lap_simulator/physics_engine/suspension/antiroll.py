"""
Anti-Roll Bar - Modellazione barre antirollio F1 2025

Modello fisico delle barre antirollio:
- Rigidezza torsionale
- Trasferimento carico laterale
- Effetti su grip e handling
- Regolazione setup (stiffness)
"""

from dataclasses import dataclass
from typing import Dict
import numpy as np


@dataclass
class AntiRollForce:
    """Forza generata dalla barra antirollio."""
    force: float  # N forza trasferita
    roll_angle: float  # rad angolo di rollio
    roll_rate: float  # rad/s velocità di rollio


class AntiRollBar:
    """
    Barra antirollio F1 2025
    
    Le barre antirollio:
    - Collegano le sospensioni left/right
    - Resistono al rollio della vettura
    - Trasferiscono carico dalla ruota interna all'esterna
    - Influenzano il grip in curva
    
    Setup tipico F1:
    - Anteriore: 200-400 Nm/deg
    - Posteriore: 150-350 Nm/deg
    - Più rigido = meno rollio, ma meno grip meccanico
    """
    
    def __init__(self, config=None):
        """
        Inizializza barra antirollio
        
        Args:
            config: dict con parametri personalizzati
        """
        defaults = {
            'stiffness': 300.0,  # Nm/deg rigidezza torsionale
            'max_roll_deg': 3.0,  # deg angolo di rollio massimo
            'preload': 0.0,      # deg precarico (setup)
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Converti stiffness in Nm/rad per calcoli fisici
        self.stiffness_nm_rad = self.config['stiffness'] * (180.0 / np.pi)
    
    def calculate_force(self, roll_angle: float, roll_rate: float = 0.0, 
                       track_width: float = 1.60) -> 'AntiRollForce':
        """
        Calcola forza trasferita dalla barra antirollio
        
        Args:
            roll_angle: rad angolo di rollio (positivo = rollio a destra)
            roll_rate: rad/s velocità di rollio
            track_width: m carreggiata (distanza tra ruote)
        
        Returns:
            AntiRollForce con forza trasferita
        """
        # Forza torsionale dalla barra
        # T = k * theta (coppia)
        torque = self.stiffness_nm_rad * roll_angle
        
        # Forza verticale sulle ruote
        # F = T / (track_width / 2)
        # La barra trasferisce forza dalla ruota interna all'esterna
        force = torque / (track_width / 2.0)
        
        # Damping opzionale (dipende da roll_rate)
        # In F1 reale, c'è un piccolo effetto damping
        damping_coefficient = 50.0  # Nm·s/rad
        damping_torque = damping_coefficient * roll_rate
        force += damping_torque / (track_width / 2.0)
        
        return AntiRollForce(
            force=force,
            roll_angle=roll_angle,
            roll_rate=roll_rate
        )
    
    def get_load_transfer(self, roll_angle: float, track_width: float = 1.60) -> float:
        """
        Calcola trasferimento di carico laterale (N)
        
        Args:
            roll_angle: rad angolo di rollio
            track_width: m carreggiata
        
        Returns:
            N trasferiti dalla ruota interna all'esterna
        """
        torque = self.stiffness_nm_rad * roll_angle
        return torque / (track_width / 2.0)
    
    def set_stiffness(self, stiffness_nm_deg: float):
        """
        Imposta rigidezza barra antirollio
        
        Args:
            stiffness_nm_deg: Nm/deg (tipicamente 150-400 per F1)
        """
        self.config['stiffness'] = np.clip(stiffness_nm_deg, 50, 1000)
        self.stiffness_nm_rad = self.config['stiffness'] * (180.0 / np.pi)
    
    def get_stiffness_nm_deg(self) -> float:
        """Rigidezza in Nm/deg."""
        return self.config['stiffness']
    
    def get_roll_angle_from_force(self, force: float, track_width: float = 1.60) -> float:
        """
        Calcola angolo di rollio da forza applicata
        
        Args:
            force: N forza applicata
            track_width: m carreggiata
        
        Returns:
            rad angolo di rollio
        """
        torque = force * (track_width / 2.0)
        return torque / self.stiffness_nm_rad
    
    def get_summary(self) -> Dict:
        """Riepilogo parametri barra antirollio."""
        return {
            'stiffness_Nm_deg': self.config['stiffness'],
            'stiffness_Nm_rad': self.stiffness_nm_rad,
            'max_roll_deg': self.config['max_roll_deg'],
            'preload_deg': self.config['preload'],
        }
