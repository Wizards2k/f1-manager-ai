"""
Mass package - Gestione massa, baricentro e inerzie vettura F1 2025

Moduli:
- mass_distribution: Massa totale e distribuzione front/rear
- center_of_gravity: Posizione baricentro (CG)
- inertia: Momenti di inerzia (roll, pitch, yaw)
"""

from .mass_distribution import MassDistribution, MassState
from .center_of_gravity import CenterOfGravity, CGPosition
from .inertia import MomentOfInertia, InertiaTensor

__all__ = [
    # Mass Distribution
    'MassDistribution',
    'MassState',
    
    # Center of Gravity
    'CenterOfGravity',
    'CGPosition',
    
    # Moment of Inertia
    'MomentOfInertia',
    'InertiaTensor',
]
