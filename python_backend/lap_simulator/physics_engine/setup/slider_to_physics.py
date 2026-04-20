"""
Slider to Physics - Conversione Slider F1 2025

Modello conversione slider:
- Slider setup a parametri fisici
- Mappatura slider a fisica
- Effetti su performance

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np


@dataclass
class SliderConversion:
    """Conversione slider."""
    slider_value: float  # 0.0-100.0 valore slider
    physics_value: float  # valore fisico
    physics_unit: str  # unità fisica
    effect: str  # effetto su performance


class SliderToPhysics:
    """
    Conversione slider F1 2025
    
    Converte slider setup a parametri fisici:
    - Slider 0-100
    - Parametri fisici (kg, Nm, °, etc)
    - Effetti su performance
    
    Formula:
    physics = slider × (max - min) / 100 + min
    
    Effetti:
    - Slider front wing: downforce, drag
    - Slider rear wing: downforce, drag
    - Slider brake bias: front/rear load
    - Slider suspension: ride height, stiffness
    """
    
    def __init__(
        self,
        slider_range: Tuple[float, float] = (0.0, 100.0),
    ):
        """
        Inizializza conversione slider
        
        Args:
            slider_range: (min, max) range slider
        """
        self.slider_range = slider_range
        
        # Mappature slider a fisica
        self.mappings = self._create_mappings()
    
    def _create_mappings(self) -> Dict:
        """
        Crea mappature slider a fisica
        
        Returns:
            Dict con mappature
        """
        return {
            'front_wing': {
                'min': 0.0,  # ° angolo
                'max': 15.0,
                'unit': 'deg',
                'effect': 'downforce, drag',
            },
            'rear_wing': {
                'min': 0.0,
                'max': 20.0,
                'unit': 'deg',
                'effect': 'downforce, drag',
            },
            'brake_bias': {
                'min': 45.0,  # % frontale
                'max': 65.0,
                'unit': 'pct',
                'effect': 'load distribution',
            },
            'ride_height': {
                'min': 30.0,  # mm
                'max': 100.0,
                'unit': 'mm',
                'effect': 'aero, handling',
            },
            'front_suspension': {
                'min': 100.0,  # kN/m
                'max': 300.0,
                'unit': 'kN/m',
                'effect': 'stiffness, ride',
            },
            'rear_suspension': {
                'min': 100.0,
                'max': 300.0,
                'unit': 'kN/m',
                'effect': 'stiffness, ride',
            },
            'front_arb': {
                'min': 0.0,  # Nm/deg
                'max': 5000.0,
                'unit': 'Nm/deg',
                'effect': 'roll stiffness',
            },
            'rear_arb': {
                'min': 0.0,
                'max': 5000.0,
                'unit': 'Nm/deg',
                'effect': 'roll stiffness',
            },
        }
    
    def convert_slider(
        self,
        slider_value: float,
        parameter: str,
    ) -> SliderConversion:
        """
        Converte slider a fisica
        
        Args:
            slider_value: 0.0-100.0 valore slider
            parameter: nome parametro
        
        Returns:
            SliderConversion con conversione
        """
        if parameter not in self.mappings:
            raise ValueError(f"Parametro sconosciuto: {parameter}")
        
        mapping = self.mappings[parameter]
        min_val = mapping['min']
        max_val = mapping['max']
        
        # Linear interpolation
        physics_value = slider_value * (max_val - min_val) / 100.0 + min_val
        
        return SliderConversion(
            slider_value=slider_value,
            physics_value=physics_value,
            physics_unit=mapping['unit'],
            effect=mapping['effect'],
        )
    
    def convert_all_sliders(
        self,
        sliders: Dict[str, float],
    ) -> Dict[str, SliderConversion]:
        """
        Converte tutti gli slider
        
        Args:
            sliders: Dict {parameter: slider_value}
        
        Returns:
            Dict {parameter: SliderConversion}
        """
        results = {}
        for parameter, slider_value in sliders.items():
            results[parameter] = self.convert_slider(slider_value, parameter)
        
        return results
    
    def get_slider_range(
        self,
        parameter: str,
    ) -> Tuple[float, float]:
        """
        Ottieni range slider per parametro
        
        Args:
            parameter: nome parametro
        
        Returns:
            (min, max) range slider
        """
        if parameter not in self.mappings:
            raise ValueError(f"Parametro sconosciuto: {parameter}")
        
        mapping = self.mappings[parameter]
        return mapping['min'], mapping['max']
    
    def get_slider_effect(
        self,
        parameter: str,
    ) -> str:
        """
        Ottieni effetto slider
        
        Args:
            parameter: nome parametro
        
        Returns:
            effetto su performance
        """
        if parameter not in self.mappings:
            raise ValueError(f"Parametro sconosciuto: {parameter}")
        
        return self.mappings[parameter]['effect']
    
    def analyze_sliders(
        self,
        sliders: Dict[str, float],
    ) -> Dict:
        """
        Analizza slider
        
        Args:
            sliders: Dict {parameter: slider_value}
        
        Returns:
            Dict con analisi slider
        """
        conversions = self.convert_all_sliders(sliders)
        
        analysis = {}
        for parameter, conversion in conversions.items():
            analysis[parameter] = {
                'slider_value': conversion.slider_value,
                'physics_value': conversion.physics_value,
                'physics_unit': conversion.physics_unit,
                'effect': conversion.effect,
            }
        
        return analysis
    
    def get_state(
        self,
        slider_value: float,
        parameter: str,
    ) -> Dict:
        """Restituisce stato conversione slider."""
        conversion = self.convert_slider(slider_value, parameter)
        
        return {
            'slider_value': conversion.slider_value,
            'physics_value': conversion.physics_value,
            'physics_unit': conversion.physics_unit,
            'effect': conversion.effect,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo conversione slider."""
        return {
            'slider_range': self.slider_range,
            'parameters': list(self.mappings.keys()),
            'mappings': self.mappings,
        }
