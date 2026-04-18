"""
Spring & Damper - Modellazione molle e ammortizzatori F1 2025

Modello fisico delle sospensioni:
- Costante elastica molla (spring rate)
- Smorzamento (compression/rebound)
- Forza molla vs compressione
- Effetti su grip e handling
"""

from dataclasses import dataclass
from typing import Dict
import numpy as np


@dataclass
class SpringForce:
    """Forza generata dalla molla."""
    force: float  # N forza molla (positivo = compressione)
    displacement: float  # m compressione/estensione
    velocity: float  # m/s velocità movimento


class SpringDamper:
    """
    Modello molla + ammortizzatore F1 2025
    
    Le sospensioni F1 sono estremamente rigide:
    - Spring rate: 200-400 N/mm (anteriore)
    - Spring rate: 300-600 N/mm (posteriore)
    - Damping: asimmetrico (compression vs rebound)
    
    Funzioni:
    - Controllare movimento verticale ruota
    - Mantenere contatto con asfalto
    - Gestire load transfer dinamico
    """
    
    def __init__(self, config=None):
        """
        Inizializza molla + ammortizzatore
        
        Args:
            config: dict con parametri personalizzati
        """
        defaults = {
            'spring_rate': 300000.0,  # N/m (300 N/mm) tipico F1
            'damping_compression': 8000.0,  # N·s/m compressione
            'damping_rebound': 12000.0,    # N·s/m estensione (rebound)
            'max_travel': 0.050,  # m corsa massima (50mm)
            'preload': 0.010,     # m precarico molla (10mm)
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Stato corrente
        self.displacement = 0.0  # m compressione attuale
        self.velocity = 0.0      # m/s velocità movimento
    
    def calculate_force(self, displacement: float, velocity: float) -> 'SpringForce':
        """
        Calcola forza molla + ammortizzatore
        
        Args:
            displacement: m spostamento (positivo = compressione)
            velocity: m/s velocità (positivo = compressione)
        
        Returns:
            SpringForce con forza totale
        """
        # Forza molla (legge di Hooke)
        # F_spring = k * x
        spring_force = self.config['spring_rate'] * (displacement + self.config['preload'])
        
        # Forza ammortizzatore (dipende da velocità)
        # Asimmetrico: compression vs rebound
        if velocity > 0:  # Compressione
            damping_force = self.config['damping_compression'] * velocity
        else:  # Estensione (rebound)
            damping_force = self.config['damping_rebound'] * velocity
        
        # Forza totale
        total_force = spring_force + damping_force
        
        # Clamp a corsa massima
        if abs(displacement) > self.config['max_travel']:
            # Bottoming out - forza aggiuntiva (bump stop)
            bump_travel = abs(displacement) - self.config['max_travel']
            bump_stiffness = 1000000.0  # N/m molto rigido
            total_force += bump_stiffness * bump_travel
        
        return SpringForce(
            force=total_force,
            displacement=displacement,
            velocity=velocity
        )
    
    def get_spring_force(self, displacement: float) -> float:
        """Forza della sola molla (N)."""
        return self.config['spring_rate'] * (displacement + self.config['preload'])
    
    def get_damping_force(self, velocity: float) -> float:
        """Forza del solo ammortizzatore (N)."""
        if velocity > 0:
            return self.config['damping_compression'] * velocity
        else:
            return self.config['damping_rebound'] * velocity
    
    def set_spring_rate(self, rate: float):
        """
        Imposta costante elastica molla
        
        Args:
            rate: N/m (tipicamente 200000-600000 per F1)
        """
        self.config['spring_rate'] = np.clip(rate, 50000, 1000000)
    
    def set_damping(self, compression: float, rebound: float):
        """
        Imposta smorzamento
        
        Args:
            compression: N·s/m compressione
            rebound: N·s/m estensione
        """
        self.config['damping_compression'] = np.clip(compression, 1000, 50000)
        self.config['damping_rebound'] = np.clip(rebound, 1000, 50000)
    
    def get_summary(self) -> Dict:
        """Riepilogo parametri sospensione."""
        return {
            'spring_rate_N_mm': self.config['spring_rate'] / 1000,
            'damping_compression_Ns_m': self.config['damping_compression'],
            'damping_rebound_Ns_m': self.config['damping_rebound'],
            'max_travel_mm': self.config['max_travel'] * 1000,
            'preload_mm': self.config['preload'] * 1000,
        }
