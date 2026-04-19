"""
Power Unit package - Motore ibrido F1 2025 (Physics V4)

Moduli:
- ice_engine: Motore termico (torque curve, fuel flow)
- ers_deploy: Gestione energia ERS (batteria, MGU-H)
- thermal_model: Modello termico (clipping, derating)
- pu_physics: Integrazione completa PU

NOTA: Moduli V4 standalone, non dipendono da power_unit.py V1
"""

from .ice_engine import ICEEngine, ICEState, ICE_BASE_POWER_KW
from .ers_deploy import ERSDeployManager, DeployRequest, ERSEnergyState
from .thermal_model import ThermalModel, ThermalState
from .pu_physics import PUPhysics, PUOutput

__all__ = [
    # ICE Engine
    'ICEEngine',
    'ICEState',
    'ICE_BASE_POWER_KW',
    
    # ERS Deploy
    'ERSDeployManager',
    'DeployRequest',
    'ERSEnergyState',
    
    # Thermal Model
    'ThermalModel',
    'ThermalState',
    
    # PU Physics (integrazione)
    'PUPhysics',
    'PUOutput',
]
