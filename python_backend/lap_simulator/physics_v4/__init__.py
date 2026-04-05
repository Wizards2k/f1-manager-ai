"""
Physics Engine V4 - Newtonian Physics Simulator for F1 2025

Motore fisico completamente indipendente da V1/V2/V3.
Simula le forze fisiche reali (Newton, kg, m/s²) senza penalty empiriche.

Il tempo sul giro EMERGE dalla simulazione fisica, non è un riferimento + aggiustamenti.
"""

__version__ = "4.0.0"
__author__ = "F1 Manager AI Development Team"

# Core modules
from .core.constants import (
    # Costanti universali
    G,
    RHO_SEA_LEVEL,
    
    # F1 2025 Regolamento
    MASS_DRY_KG,
    MASS_DRIVER_KG,
    FUEL_RACE_START_KG,
    FUEL_QUALY_KG,
    
    # Power Unit
    ICE_PEAK_POWER_KW,
    ERS_PEAK_POWER_KW,
    PU_TOTAL_PEAK_KW,
    DRIVETRAIN_EFFICIENCY,
    ROLLING_RESISTANCE_COEFF,
    
    # Aerodinamica
    CLA_MIN,
    CLA_MAX,
    CLA_NEUTRAL,
    CDA_MIN,
    CDA_MAX,
    CDA_NEUTRAL,
    DRS_DRAG_REDUCTION_FACTOR,
    
    # Gomme
    MU_BASE,
    GRIP_CORNERING_EFFICIENCY,
    KAPPA_LOAD,
    
    # Geometria Auto
    H_CG,
    WHEELBASE,
    TRACK_WIDTH,
    WEIGHT_DIST_FRONT,
)

# Aero modules
from .aero.aero_assembly import AeroAssembly, AeroForces
from .aero.front_wing import FrontWing
from .aero.rear_wing import RearWing
from .aero.floor_front import FloorFront
from .aero.floor_rear import FloorRear
from .aero.sidepods import Sidepods
from .aero.engine_cover import EngineCover
from .aero.bwing import BWing

# Mass modules
from .mass.mass_distribution import MassDistribution, MassState
from .mass.center_of_gravity import CenterOfGravity, CGPosition
from .mass.inertia import MomentOfInertia, InertiaTensor

# Suspension modules
from .suspension.spring_damper import SpringDamper, SpringForce
from .suspension.antiroll import AntiRollBar, AntiRollForce
from .suspension.ride_height import RideHeight, RideHeightState

# Integrator
from .integrator.waypoint_integrator import integrate_lap_hd

# API pubblica
__all__ = [
    # Versione
    "__version__",
    "__author__",
    
    # Core
    'G', 'RHO_SEA_LEVEL',
    'MASS_DRY_KG', 'MASS_DRIVER_KG', 'FUEL_RACE_START_KG', 'FUEL_QUALY_KG',
    'ICE_PEAK_POWER_KW', 'ERS_PEAK_POWER_KW', 'PU_TOTAL_PEAK_KW',
    'CLA_MIN', 'CLA_MAX', 'CDA_MIN', 'CDA_MAX',
    'MU_BASE', 'WHEELBASE', 'TRACK_WIDTH',
    
    # Aero
    'AeroAssembly', 'AeroForces',
    'FrontWing', 'RearWing',
    'FloorFront', 'FloorRear',
    'Sidepods', 'EngineCover', 'BWing',
    
    # Mass
    'MassDistribution', 'MassState',
    'CenterOfGravity', 'CGPosition',
    'MomentOfInertia', 'InertiaTensor',
    
    # Suspension
    'SpringDamper', 'SpringForce',
    'AntiRollBar', 'AntiRollForce',
    'RideHeight', 'RideHeightState',
    
    # Integrator
    'integrate_lap_hd',
]
