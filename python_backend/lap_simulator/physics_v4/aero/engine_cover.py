"""
Aerodinamica: Cofano Motore (Engine Cover)

Modello fisico del cofano motore F1 2025:
- Flow conditioning
- Drag da superficie
- Effetto venturi superiore
- Interferenza con sidepods
"""

import numpy as np


class EngineCover:
    """
    Cofano motore F1 2025 - Modello Fisico
    
    Parametri:
    - Area superficie
    - Coefficiente drag
    - Effetto flow conditioning
    """
    
    def __init__(self, config=None):
        defaults = {
            'width': 0.70,         # Larghezza (m)
            'height': 0.30,        # Altezza (m)
            'length': 0.80,        # Lunghezza (m)
            'surface_roughness': 0.002,  # Roughness (m)
        }
        
        self.config = {**defaults, **(config or {})}
        
        self.A_REF = self.config['width'] * self.config['length']
        
        # Parametri aerodinamici
        self.CD_BASE = 0.015      # Drag base (superficie liscia)
        self.CL_Venturi = 0.05    # Portanza venturi superiore
        
        # Interferenza
        self.SIDEPODS_INTERFERENCE = 0.98
        
    def calculate_forces(self, rho, v):
        """
        Calcola forze cofano motore
        
        Args:
            rho: Densità aria (kg/m³)
            v: Velocità (m/s)
            
        Returns:
            dict con lift, drag, CL, CD
        """
        # Drag da superficie
        cd = self.CD_BASE
        
        # Effetto venturi
        cl = self.CL_Venturi * self.SIDEPODS_INTERFERENCE
        
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
    
    def set_surface_roughness(self, roughness_m):
        self.config['surface_roughness'] = np.clip(roughness_m, 0.001, 0.010)
        # Più roughness = più drag
        self.config['CD_BASE'] = 0.015 + (roughness_m - 0.002) * 5.0
    
    def get_summary(self):
        return {
            'width_mm': self.config['width'] * 1000,
            'height_mm': self.config['height'] * 1000,
            'length_mm': self.config['length'] * 1000,
        }


if __name__ == '__main__':
    ec = EngineCover()
    
    rho = 1.225
    v = 100
    
    forces = ec.calculate_forces(rho, v)
    print("Engine Cover Forces:")
    print(f"  CL: {forces['CL']:.4f}")
    print(f"  CD: {forces['CD']:.4f}")
    print(f"  Lift: {forces['lift']:.1f} N")
    print(f"  Drag: {forces['drag']:.1f} N")
