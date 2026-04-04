"""
Physics Engine V4 - Newtonian Physics Simulator for F1 2025

Motore fisico completamente indipendente da V1/V2/V3.
Simula le forze fisiche reali (Newton, kg, m/s²) senza penalty empiriche.

Il tempo sul giro EMERGE dalla simulazione fisica, non è un riferimento + aggiustamenti.
"""

__version__ = "4.0.0"
__author__ = "F1 Manager AI Development Team"

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
    
    # Freni
    BRAKE_TEMP_OPTIMAL_MIN_C,
    BRAKE_TEMP_OPTIMAL_MAX_C,
    BRAKE_TEMP_FADE_C,
    BRAKE_MU_PEAK,
    
    # Limiti accelerazione
    MAX_LATERAL_G,
    MAX_BRAKE_DECEL_G,
)

from .integrator.waypoint_integrator import integrate_lap_hd
from .aero.aero_assembly import AeroAssembly, AeroForces

__all__ = [
    # Versione
    "__version__",
    
    # Costanti
    "G",
    "RHO_SEA_LEVEL",
    "MASS_DRY_KG",
    "MASS_DRIVER_KG",
    "FUEL_RACE_START_KG",
    "FUEL_QUALY_KG",
    "ICE_PEAK_POWER_KW",
    "ERS_PEAK_POWER_KW",
    "PU_TOTAL_PEAK_KW",
    "DRIVETRAIN_EFFICIENCY",
    "ROLLING_RESISTANCE_COEFF",
    "CLA_MIN",
    "CLA_MAX",
    "CLA_NEUTRAL",
    "CDA_MIN",
    "CDA_MAX",
    "CDA_NEUTRAL",
    "DRS_DRAG_REDUCTION_FACTOR",
    "MU_BASE",
    "GRIP_CORNERING_EFFICIENCY",
    "KAPPA_LOAD",
    "H_CG",
    "WHEELBASE",
    "TRACK_WIDTH",
    "WEIGHT_DIST_FRONT",
    "BRAKE_TEMP_OPTIMAL_MIN_C",
    "BRAKE_TEMP_OPTIMAL_MAX_C",
    "BRAKE_TEMP_FADE_C",
    "BRAKE_MU_PEAK",
    "MAX_LATERAL_G",
    "MAX_BRAKE_DECEL_G",
    
    # Integratore
    "integrate_lap_hd",
    
    # Aero
    "AeroAssembly",
    "AeroForces",
]
