"""
Brakes package - Sistema frenante F1 2025 (Physics V4)

Moduli:
- brake_material: Materiale carbon-carbon, attrito vs temperatura
- brake_cooling: Brake ducts, raffreddamento, trasferimento calore
- brake_bias: Brake balance, migration, MGU-K harvest
- brake_wear: Usura meccanica/termica, fatica, sostituzione

NOTA: Moduli V4 standalone, non dipendono da codice V1
"""

from .brake_material import BrakeMaterial, BrakeMaterialParams, BrakeState
from .brake_cooling import BrakeCooling, BrakeDuctConfig
from .brake_bias import BrakeBias, BrakeBiasState
from .brake_wear import BrakeWear, BrakeWearState

__all__ = [
    # Brake Material
    'BrakeMaterial',
    'BrakeMaterialParams',
    'BrakeState',
    
    # Brake Cooling
    'BrakeCooling',
    'BrakeDuctConfig',
    
    # Brake Bias
    'BrakeBias',
    'BrakeBiasState',
    
    # Brake Wear
    'BrakeWear',
    'BrakeWearState',
]
