"""
Ride Height - Gestione altezza da suolo F1 2025

Modello fisico dell'altezza da suolo:
- Ride height anteriore e posteriore
- Effetto su ground effect e aero
- Rake (angolo assetto)
- Contatto con plank (legno)
- Limiti regolamento F1
"""

from dataclasses import dataclass
from typing import Dict
import numpy as np


@dataclass
class RideHeightState:
    """Stato altezza da suolo."""
    front: float  # m altezza anteriore
    rear: float   # m altezza posteriore
    rake: float   # rad angolo di rake (positivo = muso basso)
    plank_gap: float  # m gap tra plank e suolo


class RideHeight:
    """
    Gestione altezza da suolo F1 2025
    
    Il ride height influenza:
    - Ground effect (floor downforce)
    - Aero balance front/rear
    - Rischio contatto plank/sterzo
    - Drag aerodinamico
    
    Limiti regolamento F1:
    - Plank thickness: 10mm (min 9mm dopo usura)
    - Ride height min: ~50mm (antere), ~70mm (posteriore)
    - Rake massimo: ~2-3 gradi
    
    Setup tipico:
    - Front: 40-60mm
    - Rear: 50-80mm
    - Rake: 1-2 gradi (muso basso per ground effect)
    """
    
    def __init__(self, config=None):
        """
        Inizializza gestione ride height
        
        Args:
            config: dict con parametri personalizzati
        """
        defaults = {
            'front_target': 0.050,  # m altezza anteriore target (50mm)
            'rear_target': 0.070,   # m altezza posteriore target (70mm)
            'plank_thickness': 0.010,  # m spessore plank (10mm)
            'plank_gap_base': 0.005,   # m gap plank-base (5mm)
            'wheelbase': 3.60,        # m passo vettura
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Stato corrente (inizializzato a target)
        self.front = self.config['front_target']
        self.rear = self.config['rear_target']
        
        # Calcola rake
        self._update_rake()
    
    def _update_rake(self):
        """Aggiorna angolo di rake da front/rear."""
        # Rake = arctan((rear - front) / wheelbase)
        delta_h = self.rear - self.front
        self.rake = np.arctan2(delta_h, self.config['wheelbase'])
    
    def get_ride_height_state(self) -> 'RideHeightState':
        """Restituisce stato corrente."""
        return RideHeightState(
            front=self.front,
            rear=self.rear,
            rake=self.rake,
            plank_gap=self.get_plank_gap()
        )
    
    def get_plank_gap(self) -> float:
        """
        Calcola gap tra plank e suolo
        
        Il plank è al centro della vettura, leggermente più basso del fondo.
        Gap minimo = 0 (contatto)
        
        Returns:
            m gap residuo (positivo = nessun contatto)
        """
        # Plank è approssimativamente all'altezza del fondo centrale
        # Interpolazione tra front e rear
        wheelbase = self.config['wheelbase']
        plank_x = wheelbase * 0.5  # Plank al centro
        
        # Altezza fondo al centro
        front_h = self.front
        rear_h = self.rear
        center_h = front_h + (rear_h - front_h) * (plank_x / wheelbase)
        
        # Plank è sotto il fondo di plank_gap_base
        plank_height = center_h - self.config['plank_gap_base']
        
        return plank_height
    
    def set_ride_height(self, front: float, rear: float):
        """
        Imposta altezza da suolo
        
        Args:
            front: m altezza anteriore (tipicamente 0.040-0.080)
            rear: m altezza posteriore (tipicamente 0.050-0.100)
        """
        self.front = np.clip(front, 0.030, 0.150)
        self.rear = np.clip(rear, 0.030, 0.150)
        self._update_rake()
    
    def get_rake_deg(self) -> float:
        """Angolo di rake in gradi."""
        return np.degrees(self.rake)
    
    def check_plank_contact(self) -> bool:
        """Verifica se c'è contatto plank (penalty potenziale)."""
        return self.get_plank_gap() <= 0.0
    
    def get_ground_effect_factor(self) -> float:
        """
        Calcola fattore di efficienza ground effect
        
        Ground effect è massimo con ride height basso (ma senza contatto).
        
        Returns:
            float fattore 0.0-1.5 (1.0 = ottimale)
        """
        # Ground effect ottimale con front ~40-50mm
        front_optimal = 0.045
        
        # Calcola deviazione dall'ottimale
        delta = abs(self.front - front_optimal)
        
        # Fattore: 1.0 a ottimale, diminuisce con delta
        # Se troppo basso (<30mm): perdita efficienza (contatto)
        # Se troppo alto (>80mm): perdita ground effect
        
        if self.front < 0.030:
            # Troppo basso - contatto, perdita totale
            return 0.5
        elif self.front < 0.040:
            # Molto basso - alto rischio
            return 1.2 + (0.040 - self.front) * 10
        elif self.front < 0.060:
            # Range ottimale
            return 1.0 + (front_optimal - self.front) * 5
        else:
            # Troppo alto - perdita ground effect
            return max(0.5, 1.0 - (self.front - 0.060) * 10)
    
    def get_aero_sensitivity(self) -> Dict[str, float]:
        """
        Sensibilità aerodinamica al ride height
        
        Returns:
            Dict con sensibilità CLA e CDA
        """
        # Ground effect aumenta CLA ma anche CDA
        ge_factor = self.get_ground_effect_factor()
        
        cla_sensitivity = ge_factor * 0.15  # +15% CLA per ground effect
        cda_sensitivity = ge_factor * 0.05  # +5% CDA per ground effect
        
        return {
            'cla_bonus': cla_sensitivity,
            'cda_penalty': cda_sensitivity,
            'ge_efficiency': ge_factor,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo stato ride height."""
        return {
            'front_mm': self.front * 1000,
            'rear_mm': self.rear * 1000,
            'rake_deg': self.get_rake_deg(),
            'rake_rad': self.rake,
            'plank_gap_mm': self.get_plank_gap() * 1000,
            'plank_contact': self.check_plank_contact(),
            'ge_factor': self.get_ground_effect_factor(),
        }
