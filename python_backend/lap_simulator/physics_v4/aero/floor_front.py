"""
Aerodinamica: Fondo Anteriore (Ground Effect)

Modello fisico del fondo anteriore F1 2025:
- Effetto venturi anteriores
- Pressione bassa sotto l'auto
- Sensibilità altezza da suolo
- Interferenza con ala anteriore
"""

import numpy as np


class FloorFront:
    """
    Fondo anteriore F1 2025 - Ground Effect Model
    
    Parametri:
    - Area venturi anteriores
    - Coefficiente portanza (CL)
    - Sensibilità altezza da suolo
    - Interferenza con ala anteriore
    """
    
    def __init__(self, config=None):
        defaults = {
            'height': 0.08,        # Altezza da suolo ottimale (m)
            'width': 1.50,         # Larghezza fondo (m)
            'length': 1.20,        # Lunghezza fondo anteriore (m)
            'efficiency': 0.85,    # Efficienza venturi
        }
        
        self.config = {**defaults, **(config or {})}
        
        self.A_REF = self.config['width'] * self.config['length']
        
        # Parametri aerodinamici
        self.CL_MAX = 1.20        # Portanza da ground effect
        self.CL_MIN = 0.30        # Minimo ground effect
        self.CL_ALPHA = 8.0       # Sensibilità altezza (CL per m)
        
        # Sensibilità ground effect
        # Più basso = più portanza (fino a un punto)
        self.GROUND_EFFECT_SENSITIVITY = 25.0  # CL per metro di altezza
        
        # Interferenza con ala anteriore
        self.FRONT_WING_INTERFERENCE = 0.95  # -5% efficienza
        
    def calculate_forces(self, rho, v, ride_height=None):
        """
        Calcola forze da ground effect fondo anteriore
        
        Args:
            rho: Densità aria (kg/m³)
            v: Velocità (m/s)
            ride_height: Altezza da suolo (m), default config
            
        Returns:
            dict con lift, drag, CL
        """
        if ride_height is None:
            ride_height = self.config['height']
        
        # Clamp ride height
        ride_height = np.clip(ride_height, 0.04, 0.15)
        
        # Calcola CL da ground effect
        # CL = CL_max * (1 - (ride_height / h_opt)^2)
        # Più basso = più portanza (fino a stallo)
        
        ratio = ride_height / self.config['height']
        cl_base = self.CL_MAX * (1.0 - 0.5 * (ratio ** 2))
        
        # Sensibilità lineare per range operativo
        cl = cl_base * self.FRONT_WING_INTERFERENCE
        
        # Clamp CL
        cl = np.clip(cl, self.CL_MIN, self.CL_MAX)
        
        # Drag da ground effect (piccolo)
        cd = 0.005 + 0.002 * (cl ** 2)
        
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
        }


if __name__ == '__main__':
    ff = FloorFront()
    
    rho = 1.225
    v = 100
    
    for h in [0.04, 0.06, 0.08, 0.10, 0.12]:
        forces = ff.calculate_forces(rho, v, h)
        print(f"Height {h*1000:.0f}mm: CL={forces['CL']:.3f}, Lift={forces['lift']:.0f}N")
