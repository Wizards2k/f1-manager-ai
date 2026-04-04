"""
Aerodinamica: Fondo Posteriore (Diffusore)

Modello fisico del diffusore F1 2025:
- Espansione flusso sotto l'auto
- Effetto Venturi posteriore
- Sensibilità altezza da suolo
- Interferenza con ala posteriore
"""

import numpy as np


class FloorRear:
    """
    Fondo posteriore/Diffusore F1 2025 - Modello Fisico
    
    Parametri:
    - Area diffusore
    - Coefficiente portanza (CL)
    - Efficienza espansione
    - Sensibilità altezza da suolo
    """
    
    def __init__(self, config=None):
        defaults = {
            'height': 0.07,        # Altezza da suolo ottimale (m)
            'width': 1.40,         # Larghezza fondo (m)
            'length': 1.50,        # Lunghezza diffusore (m)
            'diffuser_angle': 7.0, # Angolo diffusore (gradi)
            'efficiency': 0.90,    # Efficienza diffusore
        }
        
        self.config = {**defaults, **(config or {})}
        
        self.A_REF = self.config['width'] * self.config['length']
        
        # Parametri aerodinamici
        self.CL_MAX = 1.80        # Portanza da ground effect
        self.CL_MIN = 0.50        # Minimo ground effect
        self.CL_ALPHA = 12.0      # Sensibilità altezza
        
        # Sensibilità ground effect
        self.GROUND_EFFECT_SENSITIVITY = 30.0
        
        # Interferenza con ala posteriore
        self.REAR_WING_INTERFERENCE = 0.93  # -7% efficienza
        
    def calculate_forces(self, rho, v, ride_height=None):
        """
        Calcola forze da ground effect fondo posteriore
        
        Args:
            rho: Densità aria (kg/m³)
            v: Velocità (m/s)
            ride_height: Altezza da suolo (m)
            
        Returns:
            dict con lift, drag, CL
        """
        if ride_height is None:
            ride_height = self.config['height']
        
        ride_height = np.clip(ride_height, 0.04, 0.15)
        
        # Calcola CL da ground effect
        # Diffusore più efficace con altezza bassa
        ratio = ride_height / self.config['height']
        cl_base = self.CL_MAX * (1.0 - 0.6 * (ratio ** 2))
        
        cl = cl_base * self.REAR_WING_INTERFERENCE
        cl = np.clip(cl, self.CL_MIN, self.CL_MAX)
        
        # Drag da ground effect
        cd = 0.008 + 0.003 * (cl ** 2)
        
        # Forze
        q = 0.5 * rho * (v ** 2)
        lift = cl * q * self.A_REF
        drag = cd * q * self.A_REF
        
        return {
            'lift': lift,
            'drag': drag,
            'CL': cl,
            'CD': cd,
        }
    
    def set_ride_height(self, height_m):
        self.config['height'] = np.clip(height_m, 0.04, 0.15)
    
    def get_summary(self):
        return {
            'height_mm': self.config['height'] * 1000,
            'width_mm': self.config['width'] * 1000,
            'length_mm': self.config['length'] * 1000,
            'diffuser_angle': self.config['diffuser_angle'],
        }


if __name__ == '__main__':
    fr = FloorRear()
    
    rho = 1.225
    v = 100
    
    for h in [0.04, 0.06, 0.08, 0.10]:
        forces = fr.calculate_forces(rho, v, h)
        print(f"Height {h*1000:.0f}mm: CL={forces['CL']:.3f}, Lift={forces['lift']:.0f}N")
