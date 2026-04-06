"""
Setup Optimizer - Ottimizzazione Setup F1 2025

Modello ottimizzazione:
- Ottimizzazione setup per circuito
- Algoritmi di ottimizzazione
- Effetti su performance

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import optimize

from .default_setups import DefaultSetups, normalize_circuit_name


@dataclass
class OptimizationResult:
    """Risultato ottimizzazione."""
    sliders: Dict[str, float]  # {parameter: slider_value}
    objective_value: float  # valore obiettivo (min)
    iterations: int  # numero iterazioni
    convergence: bool  # convergenza raggiunta


class SetupOptimizer:
    """
    Ottimizzazione setup F1 2025
    
    Ottimizza setup per:
    - Minimo lap time
    - Massimo grip
    - Bilanciamento ottimale
    
    Formula:
    objective = f(setup, circuit, conditions)
    
    Effetti:
    - Setup ottimale per circuito
    - Adattamento a condizioni
    - Miglioramento performance
    """
    
    def __init__(
        self,
        slider_range: Dict[str, Tuple[float, float]] = None,
        objective_weights: Dict[str, float] = None,
    ):
        """
        Inizializza ottimizzatore
        
        Args:
            slider_range: Dict {parameter: (min, max)}
            objective_weights: Dict {metric: weight}
        """
        # Range slider
        self.slider_range = slider_range or {
            'front_wing': (5.0, 15.0),
            'rear_wing': (8.0, 20.0),
            'brake_bias': (45.0, 65.0),
            'ride_height': (30.0, 100.0),
            'front_suspension': (100.0, 300.0),
            'rear_suspension': (100.0, 300.0),
            'front_arb': (0.0, 5000.0),
            'rear_arb': (0.0, 5000.0),
        }
        
        # Pesi obiettivo
        self.objective_weights = objective_weights or {
            'lap_time': 0.6,
            'grip': 0.2,
            'balance': 0.1,
            'wear': 0.1,
        }
        
        # Stato corrente
        self.best_setup = None
        self.default_setups = DefaultSetups()
    
    def _objective_function(
        self,
        sliders: np.ndarray,
        circuit: str,
        weather: str,
        tire_compound: str,
    ) -> float:
        """
        Funzione obiettivo
        
        Args:
            sliders: array di slider values
            circuit: nome circuito
            weather: weather condition
            tire_compound: Pirelli compound
        
        Returns:
            float valore obiettivo (min)
        """
        # Converti sliders a dict
        slider_names = list(self.slider_range.keys())
        slider_dict = {
            name: value for name, value in zip(slider_names, sliders)
        }
        
        # Calcola metriche (semplificato)
        # In implementazione reale, userebbe lap simulator
        lap_time = self._estimate_lap_time(slider_dict, circuit)
        grip = self._estimate_grip(slider_dict, circuit)
        balance = self._estimate_balance(slider_dict, circuit)
        wear = self._estimate_wear(slider_dict, circuit)
        
        # Calcola obiettivo
        objective = (
            self.objective_weights['lap_time'] * lap_time +
            self.objective_weights['grip'] * (1.0 - grip) +
            self.objective_weights['balance'] * (1.0 - balance) +
            self.objective_weights['wear'] * wear
        )
        
        return objective
    
    def _estimate_lap_time(
        self,
        sliders: Dict[str, float],
        circuit: str,
    ) -> float:
        """
        Stima lap time
        
        Args:
            sliders: Dict {parameter: slider_value}
            circuit: nome circuito
        
        Returns:
            float lap time (s)
        """
        # Stima semplificata
        # Dipende da downforce, grip, balance
        
        front_wing = sliders.get('front_wing', 11.0)
        rear_wing = sliders.get('rear_wing', 14.0)
        brake_bias = sliders.get('brake_bias', 53.0)
        ride_height = sliders.get('ride_height', 55.0)
        
        # Lap time base per circuito
        circuit_times = {
            'monza': 79.5,
            'monaco': 70.2,
            'suzuka': 88.5,
            'silverstone': 82.0,
            'spa': 84.0,
        }
        
        base_time = circuit_times.get(normalize_circuit_name(circuit), 80.0)
        
        # Effetto setup
        # Low downforce = faster (Monza)
        # High downforce = slower (Monaco)
        downforce_factor = (front_wing + rear_wing) / 25.0
        time_penalty = (downforce_factor - 1.0) * 2.0
        
        # Effetto ride height
        # Low ride = faster (aero) ma più rischio
        ride_factor = (ride_height - 50.0) / 50.0
        time_penalty += ride_factor * 0.5
        
        # Effetto brake bias
        # Too front/rear = slower
        bias_factor = abs(brake_bias - 52.0) / 10.0
        time_penalty += bias_factor * 0.3
        
        lap_time = base_time + time_penalty
        
        return lap_time
    
    def _estimate_grip(
        self,
        sliders: Dict[str, float],
        circuit: str,
    ) -> float:
        """
        Stima grip
        
        Args:
            sliders: Dict {parameter: slider_value}
            circuit: nome circuito
        
        Returns:
            float grip (0.0-1.0)
        """
        # Stima grip
        # Dipende da ride height, suspension, ARB
        
        ride_height = sliders.get('ride_height', 55.0)
        front_susp = sliders.get('front_suspension', 220.0)
        rear_susp = sliders.get('rear_suspension', 220.0)
        front_arb = sliders.get('front_arb', 2500.0)
        rear_arb = sliders.get('rear_arb', 2500.0)
        
        # Low ride height = more grip (aero)
        grip = 1.0 - (ride_height - 30.0) / 70.0 * 0.2
        
        # Stiff suspension = more grip
        avg_susp = (front_susp + rear_susp) / 2.0
        grip += (avg_susp - 100.0) / 200.0 * 0.1
        
        # Stiff ARB = more grip
        avg_arb = (front_arb + rear_arb) / 2.0
        grip += (avg_arb - 0.0) / 5000.0 * 0.1
        
        grip = np.clip(grip, 0.5, 1.0)
        
        return grip
    
    def _estimate_balance(
        self,
        sliders: Dict[str, float],
        circuit: str,
    ) -> float:
        """
        Stima balance
        
        Args:
            sliders: Dict {parameter: slider_value}
            circuit: nome circuito
        
        Returns:
            float balance (0.0-1.0)
        """
        # Stima balance
        # 1.0 = perfetto, 0.0 = pessimo
        
        brake_bias = sliders.get('brake_bias', 53.0)
        front_arb = sliders.get('front_arb', 2500.0)
        rear_arb = sliders.get('rear_arb', 2500.0)
        
        # Brake bias ottimale = 52-54
        bias_error = abs(brake_bias - 53.0)
        balance = 1.0 - bias_error / 10.0
        
        # ARB balance
        arb_ratio = front_arb / max(rear_arb, 0.001)
        arb_error = abs(arb_ratio - 1.0)
        balance -= arb_error * 0.2
        
        balance = np.clip(balance, 0.0, 1.0)
        
        return balance
    
    def _estimate_wear(
        self,
        sliders: Dict[str, float],
        circuit: str,
    ) -> float:
        """
        Stima wear
        
        Args:
            sliders: Dict {parameter: slider_value}
            circuit: nome circuito
        
        Returns:
            float wear (0.0-1.0)
        """
        # Stima wear
        # 0.0 = zero wear, 1.0 = massimo wear
        
        ride_height = sliders.get('ride_height', 55.0)
        front_susp = sliders.get('front_suspension', 220.0)
        rear_susp = sliders.get('rear_suspension', 220.0)
        
        # Low ride height = more wear
        wear = (ride_height - 30.0) / 70.0 * 0.5
        
        # Stiff suspension = more wear
        avg_susp = (front_susp + rear_susp) / 2.0
        wear += (avg_susp - 100.0) / 200.0 * 0.3
        
        wear = np.clip(wear, 0.0, 1.0)
        
        return wear
    
    def optimize(
        self,
        circuit: str,
        weather: str = 'dry',
        tire_compound: str = 'C3',
        method: str = 'Nelder-Mead',
        maxiter: int = 100,
    ) -> OptimizationResult:
        """
        Ottimizza setup
        
        Args:
            circuit: nome circuito
            weather: weather condition
            tire_compound: Pirelli compound
            method: metodo ottimizzazione
            maxiter: max iterazioni
        
        Returns:
            OptimizationResult con risultato
        """
        # Initial guess = defaults
        slider_names = list(self.slider_range.keys())
        default_setup = self.default_setups.get_default_setup(circuit, weather, tire_compound)
        initial_sliders = np.array([
            default_setup.get(
                name,
                (self.slider_range[name][0] + self.slider_range[name][1]) / 2.0,
            )
            for name in slider_names
        ])
        
        # Bounds
        bounds = [self.slider_range[name] for name in slider_names]
        
        # Optimize
        result = optimize.minimize(
            self._objective_function,
            initial_sliders,
            args=(circuit, weather, tire_compound),
            method=method,
            bounds=bounds,
            options={'maxiter': maxiter}
        )
        
        # Converti risultato a dict
        optimal_sliders = {
            name: value for name, value in zip(slider_names, result.x)
        }
        
        self.best_setup = optimal_sliders
        
        return OptimizationResult(
            sliders=optimal_sliders,
            objective_value=result.fun,
            iterations=result.nit,
            convergence=result.success,
        )
    
    def optimize_multiple(
        self,
        circuits: List[str],
        weather: str = 'dry',
        tire_compound: str = 'C3',
    ) -> Dict[str, OptimizationResult]:
        """
        Ottimizza setup per multiple circuiti
        
        Args:
            circuits: lista nomi circuiti
            weather: weather condition
            tire_compound: Pirelli compound
        
        Returns:
            Dict {circuit: OptimizationResult}
        """
        results = {}
        for circuit in circuits:
            results[circuit] = self.optimize(circuit, weather, tire_compound)
        
        return results
    
    def get_optimal_setup(
        self,
        circuit: str,
        weather: str = 'dry',
        tire_compound: str = 'C3',
    ) -> Dict[str, float]:
        """
        Ottieni setup ottimale
        
        Args:
            circuit: nome circuito
            weather: weather condition
            tire_compound: Pirelli compound
        
        Returns:
            Dict {parameter: slider_value}
        """
        result = self.optimize(circuit, weather, tire_compound)
        return result.sliders
    
    def get_state(
        self,
        circuit: str,
        weather: str = 'dry',
        tire_compound: str = 'C3',
    ) -> Dict:
        """Restituisce stato ottimizzazione."""
        result = self.optimize(circuit, weather, tire_compound)
        
        return {
            'circuit': circuit,
            'weather': weather,
            'tire_compound': tire_compound,
            'sliders': result.sliders,
            'objective_value': result.objective_value,
            'iterations': result.iterations,
            'convergence': result.convergence,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo ottimizzazione."""
        return {
            'slider_range': self.slider_range,
            'objective_weights': self.objective_weights,
            'best_setup': self.best_setup,
        }
