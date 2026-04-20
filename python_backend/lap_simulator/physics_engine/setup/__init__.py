"""
Setup Package - F1 2025 Physics Engine V4

Moduli:
- slider_to_physics: Conversione slider a fisica
- default_setups: Configurazioni default
- optimizer: Ottimizzazione setup

NOTA: Moduli V4 standalone, non dipendono da codice V1
"""

from .slider_to_physics import SliderToPhysics
from .default_setups import DefaultSetups
from .optimizer import SetupOptimizer

__all__ = ['SliderToPhysics', 'DefaultSetups', 'SetupOptimizer']
