"""
Default Setups - Configurazioni Default F1 2025

Modello configurazioni default:
- Setups default per circuito
- Setups weather
- Setups tire compound

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np


@dataclass
class DefaultSetup:
    """Configurazione default."""
    circuit: str  # nome circuito
    weather: str  # weather condition
    tire_compound: str  # Pirelli compound (C1-C6)
    sliders: Dict[str, float]  # {parameter: slider_value}
    description: str  # descrizione setup


class DefaultSetups:
    """
    Configurazioni default F1 2025
    
    Fornisce configurazioni default per:
    - Ogni circuito
    - Ogni weather condition
    - Ogni tire compound
    
    Effetti:
    - Setup ottimale per circuito
    - Adattamento a weather
    - Adattamento a compound
    """
    
    def __init__(
        self,
    ):
        """
        Inizializza configurazioni default
        """
        # Setups default per circuito
        self.circuit_defaults = self._create_circuit_defaults()
        
        # Setups per weather
        self.weather_defaults = self._create_weather_defaults()
        
        # Setups per compound
        self.compound_defaults = self._create_compound_defaults()
    
    def _create_circuit_defaults(self) -> Dict:
        """
        Crea configurazioni default per circuito
        
        Returns:
            Dict {circuit: {parameter: slider_value}}
        """
        return {
            'monza': {
                'front_wing': 10.0,  # Low downforce
                'rear_wing': 12.0,
                'brake_bias': 52.0,
                'ride_height': 60.0,
                'front_suspension': 200.0,
                'rear_suspension': 200.0,
                'front_arb': 2000.0,
                'rear_arb': 2000.0,
            },
            'monaco': {
                'front_wing': 12.0,  # High downforce
                'rear_wing': 18.0,
                'brake_bias': 56.0,
                'ride_height': 80.0,
                'front_suspension': 250.0,
                'rear_suspension': 250.0,
                'front_arb': 3000.0,
                'rear_arb': 3000.0,
            },
            'suzuka': {
                'front_wing': 11.0,  # Medium downforce
                'rear_wing': 14.0,
                'brake_bias': 54.0,
                'ride_height': 55.0,
                'front_suspension': 220.0,
                'rear_suspension': 220.0,
                'front_arb': 2500.0,
                'rear_arb': 2500.0,
            },
            'silverstone': {
                'front_wing': 11.0,
                'rear_wing': 14.0,
                'brake_bias': 53.0,
                'ride_height': 50.0,
                'front_suspension': 230.0,
                'rear_suspension': 230.0,
                'front_arb': 2800.0,
                'rear_arb': 2800.0,
            },
            'spa': {
                'front_wing': 10.0,
                'rear_wing': 13.0,
                'brake_bias': 52.0,
                'ride_height': 55.0,
                'front_suspension': 210.0,
                'rear_suspension': 210.0,
                'front_arb': 2600.0,
                'rear_arb': 2600.0,
            },
        }
    
    def _create_weather_defaults(self) -> Dict:
        """
        Crea configurazioni default per weather
        
        Returns:
            Dict {weather: {parameter: slider_value}}
        """
        return {
            'dry': {
                'ride_height': 50.0,  # Low ride height
                'front_suspension': 220.0,
                'rear_suspension': 220.0,
                'front_arb': 2500.0,
                'rear_arb': 2500.0,
            },
            'cloudy': {
                'ride_height': 55.0,
                'front_suspension': 210.0,
                'rear_suspension': 210.0,
                'front_arb': 2400.0,
                'rear_arb': 2400.0,
            },
            'rain': {
                'ride_height': 70.0,  # High ride height
                'front_suspension': 180.0,
                'rear_suspension': 180.0,
                'front_arb': 2000.0,
                'rear_arb': 2000.0,
            },
        }
    
    def _create_compound_defaults(self) -> Dict:
        """
        Crea configurazioni default per compound
        
        Returns:
            Dict {compound: {parameter: slider_value}}
        """
        return {
            'C1': {
                'brake_bias': 54.0,  # More front (harder tires)
                'ride_height': 50.0,
                'front_suspension': 230.0,
                'rear_suspension': 230.0,
            },
            'C2': {
                'brake_bias': 53.0,
                'ride_height': 52.0,
                'front_suspension': 220.0,
                'rear_suspension': 220.0,
            },
            'C3': {
                'brake_bias': 52.0,
                'ride_height': 55.0,
                'front_suspension': 210.0,
                'rear_suspension': 210.0,
            },
            'C4': {
                'brake_bias': 51.0,
                'ride_height': 58.0,
                'front_suspension': 200.0,
                'rear_suspension': 200.0,
            },
            'C5': {
                'brake_bias': 50.0,  # More rear (softer tires)
                'ride_height': 60.0,
                'front_suspension': 190.0,
                'rear_suspension': 190.0,
            },
        }
    
    def get_default_setup(
        self,
        circuit: str,
        weather: str = 'dry',
        tire_compound: str = 'C3',
    ) -> Dict[str, float]:
        """
        Ottieni configurazione default
        
        Args:
            circuit: nome circuito
            weather: weather condition
            tire_compound: Pirelli compound
        
        Returns:
            Dict {parameter: slider_value}
        """
        # Ottieni setup circuito
        if circuit in self.circuit_defaults:
            setup = self.circuit_defaults[circuit].copy()
        else:
            # Default generic
            setup = {
                'front_wing': 11.0,
                'rear_wing': 14.0,
                'brake_bias': 53.0,
                'ride_height': 55.0,
                'front_suspension': 220.0,
                'rear_suspension': 220.0,
                'front_arb': 2500.0,
                'rear_arb': 2500.0,
            }
        
        # Adatta a weather
        if weather in self.weather_defaults:
            weather_setup = self.weather_defaults[weather]
            for param, value in weather_setup.items():
                setup[param] = value
        
        # Adatta a compound
        if tire_compound in self.compound_defaults:
            compound_setup = self.compound_defaults[tire_compound]
            for param, value in compound_setup.items():
                setup[param] = value
        
        return setup
    
    def get_all_defaults(
        self,
        circuit: str,
    ) -> Dict[str, Dict[str, float]]:
        """
        Ottieni tutti i defaults per circuito
        
        Args:
            circuit: nome circuito
        
        Returns:
            Dict {weather: {compound: setup}}
        """
        results = {}
        
        for weather in self.weather_defaults.keys():
            results[weather] = {}
            for compound in self.compound_defaults.keys():
                results[weather][compound] = self.get_default_setup(
                    circuit, weather, compound
                )
        
        return results
    
    def create_setup(
        self,
        circuit: str,
        weather: str = 'dry',
        tire_compound: str = 'C3',
        adjustments: Optional[Dict[str, float]] = None,
    ) -> DefaultSetup:
        """
        Crea configurazione
        
        Args:
            circuit: nome circuito
            weather: weather condition
            tire_compound: Pirelli compound
            adjustments: Dict {parameter: adjustment}
        
        Returns:
            DefaultSetup con configurazione
        """
        setup = self.get_default_setup(circuit, weather, tire_compound)
        
        # Applica adjustments
        if adjustments:
            for param, adjustment in adjustments.items():
                if param in setup:
                    setup[param] += adjustment
        
        # Crea descrizione
        description = f"{circuit} - {weather} - {tire_compound}"
        
        return DefaultSetup(
            circuit=circuit,
            weather=weather,
            tire_compound=tire_compound,
            sliders=setup,
            description=description,
        )
    
    def get_state(
        self,
        circuit: str,
        weather: str = 'dry',
        tire_compound: str = 'C3',
    ) -> Dict:
        """Restituisce stato configurazione."""
        setup = self.get_default_setup(circuit, weather, tire_compound)
        
        return {
            'circuit': circuit,
            'weather': weather,
            'tire_compound': tire_compound,
            'sliders': setup,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo configurazioni default."""
        return {
            'circuits': list(self.circuit_defaults.keys()),
            'weather_conditions': list(self.weather_defaults.keys()),
            'tire_compounds': list(self.compound_defaults.keys()),
        }
