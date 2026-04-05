"""
Aerodinamica: B-Wing (Mini Ala Posteriore)

Modello fisico del B-wing F1 2025:
- Mini ala sopra il diffusore
- Effetto beam wing
- Interferenza con ala posteriore
"""

import numpy as np


class BWing:
    """
    B-Wing F1 2025 - Modello Fisico
    
    Parametri:
    - Area ala
    - Coefficiente portanza
    - Effetto beam wing
    """
    
    def __init__(self, config=None):
        defaults = {
            'aoa': 10.0,           # Angolo attacco (gradi)
            'active': True,        # B-wing attivo
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Parametri geometrici F1 2025
        self.SPAN = 1.20   # Apertura B-wing (m)
        self.CHORD = 0.25  # Corda media (m)
        
        # Area di riferimento (superficie alare)
        self.A_REF = self.SPAN * self.CHORD  # 0.30 m²
        
        # Area riferimento comune per confronto (area frontale auto)
        self.A_REF_COMMON = 1.60  # m²
        
        # Parametri aerodinamici
        self.CL_MAX = 0.80
        self.CD_MIN = 0.020
        self.K_FACTOR = 0.080
        
        # Effetto beam wing
        self.BEAM_WING_CL_BOOST = 0.25
        self.BEAM_WING_CD_BOOST = 0.015
        
    def calculate_forces(self, rho, v):
        """
        Calcola forze B-wing
        
        Args:
            rho: Densità aria (kg/m³)
            v: Velocità (m/s)
            
        Returns:
            dict con lift, drag, CL, CD
        """
        if not self.config['active']:
            return {'lift': 0, 'drag': 0, 'CL': 0, 'CD': 0}
        
        aoa = np.clip(self.config['aoa'], 0, 20)
        
        # Calcola CL
        cl_alpha = 0.10
        cl = cl_alpha * aoa
        
        # Clamp CL
        cl = np.clip(cl, 0, self.CL_MAX)
        
        # Calcola CD
        cd = self.CD_MIN + self.K_FACTOR * (cl ** 2)
        
        # Effetto beam wing
        cl += self.BEAM_WING_CL_BOOST
        cd += self.BEAM_WING_CD_BOOST
        
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
    
    def set_aoa(self, angle_deg):
        self.config['aoa'] = np.clip(angle_deg, 0, 20)
    
    def set_active(self, active):
        self.config['active'] = active
    
    def get_summary(self):
        return {
            'aoa': self.config['aoa'],
            'active': self.config['active'],
            'width_mm': self.config['width'] * 1000,
        }


if __name__ == '__main__':
    bw = BWing()
    
    rho = 1.225
    v = 100
    
    forces = bw.calculate_forces(rho, v)
    print("B-Wing Forces:")
    print(f"  CL: {forces['CL']:.3f}")
    print(f"  CD: {forces['CD']:.3f}")
    print(f"  Lift: {forces['lift']:.1f} N")
    print(f"  Drag: {forces['drag']:.1f} N")
    
    bw.set_active(False)
    forces_off = bw.calculate_forces(rho, v)
    print(f"\nB-Wing OFF: Lift={forces_off['lift']:.1f}N, Drag={forces_off['drag']:.1f}N")
