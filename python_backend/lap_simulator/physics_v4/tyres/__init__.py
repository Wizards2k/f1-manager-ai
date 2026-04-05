"""
Tyres package - Gomme e grip F1 2025 (Physics V4)

Moduli:
- tyre_construction: Costruzione, compound, grip base
- tyre_thermal: Modello termico (riscaldamento/raffreddamento)
- tyre_wear: Usura, degradazione, blistering, graining
- grip_model: Integrazione completa (mu effettivo)

NOTA: Moduli V4 standalone, non dipendono da codice V1
"""

from .tyre_construction import TyreConstruction, TyreCompound, TyreState
from .tyre_thermal import TyreThermal, TyreThermalState
from .tyre_wear import TyreWear, TyreWearState
from .grip_model import TyreGripModel, GripState

__all__ = [
    # Tyre Construction
    'TyreConstruction',
    'TyreCompound',
    'TyreState',
    
    # Tyre Thermal
    'TyreThermal',
    'TyreThermalState',
    
    # Tyre Wear
    'TyreWear',
    'TyreWearState',
    
    # Grip Model
    'TyreGripModel',
    'GripState',
]
