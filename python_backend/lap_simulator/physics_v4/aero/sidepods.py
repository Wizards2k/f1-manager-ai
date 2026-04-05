"""
Aerodinamica: Sidepods

Modello fisico dei sidepods F1 2025:
- Drag da cooling (aria in ingresso)
- Effetto venturi laterali
- Interferenza con ala anteriore e posteriore
- Effetto ground effect laterale
"""

import numpy as np


class Sidepods:
    """
    Sidepods F1 2025 - Modello Fisico
    
    Parametri:
    - Area frontale (A_ref)
    - Coefficiente drag (CD)
    - Effetto venturi laterali (portanza)
    - Interferenza con altre componenti
    """
    
    def __init__(self, config=None):
        defaults = {
            'cooling_efficiency': 0.85, # Efficienza raffreddamento
            'venturi_effect': 0.03,    # Effetto venturi laterale
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Parametri geometrici F1 2025
        self.WIDTH = 0.85   # Larghezza sidepod (m)
        self.HEIGHT = 0.90  # Altezza sidepod (m)
        self.LENGTH = 1.20  # Lunghezza sidepod (m)
        
        # Area frontale (per drag da cooling)
        self.A_REF_FRONT = self.WIDTH * self.HEIGHT  # 0.765 m² (per lato)
        self.A_REF = 2 * self.A_REF_FRONT  # 1.53 m² (entrambi i lati)
        
        # Area riferimento comune per confronto (area frontale auto)
        self.A_REF_COMMON = 1.60  # m²
        
        # Parametri aerodinamici
        self.CD_BASE = 0.25       # Drag base cooling (reale F1, significativo)
        self.CL_VENTURI = 0.08    # Portanza da venturi
        self.CL_ALPHA = 5.0       # Sensibilità angolo
        
        # Interferenze
        self.FRONT_WING_INTERFERENCE = 0.97  # -3% con ala anteriore
        self.REAR_WING_INTERFERENCE = 0.95   # -5% con ala posteriore
        
    def calculate_forces(self, rho, v):
        """
        Calcola forze sidepods
        
        Args:
            rho: Densità aria (kg/m³)
            v: Velocità (m/s)
            
        Returns:
            dict con lift, drag, CL, CD
        """
        # Drag da cooling (dominante)
        cd = self.CD_BASE
        
        # Effetto venturi (portanza laterale)
        cl_venturi = self.CL_VENTURI * self.config['venturi_effect']
        
        # Interferenze
        cl = cl_venturi * self.FRONT_WING_INTERFERENCE * self.REAR_WING_INTERFERENCE
        
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
    
    def set_cooling(self, efficiency):
        """Imposta efficienza raffreddamento"""
        self.config['cooling_efficiency'] = np.clip(efficiency, 0.70, 0.95)
        # Più cooling = più drag
        self.config['CD_BASE'] = 0.045 + (0.95 - efficiency) * 0.03
    
    def get_summary(self):
        return {
            'width_mm': self.config['width'] * 1000,
            'height_mm': self.config['height'] * 1000,
            'length_mm': self.config['length'] * 1000,
            'cooling_eff': self.config['cooling_efficiency'],
        }


if __name__ == '__main__':
    sp = Sidepods()
    
    rho = 1.225
    v = 100
    
    forces = sp.calculate_forces(rho, v)
    print("Sidepods Forces:")
    print(f"  CL: {forces['CL']:.4f}")
    print(f"  CD: {forces['CD']:.4f}")
    print(f"  Lift: {forces['lift']:.1f} N")
    print(f"  Drag: {forces['drag']:.1f} N")
