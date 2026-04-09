"""
Aerodinamica: Ala Posteriore

Modello fisico completo dell'ala posteriore F1 2025:
- Coefficiente portanza (CL) vs angolo attacco
- Coefficiente drag (CD) vs CL
- Effetto DRS (Drag Reduction System)
- Effetto beam wing
- Sensibilità al ground effect
"""

import numpy as np


class RearWing:
    """
    Ala posteriore F1 2025 - Modello Fisico Dettagliato
    
    Parametri fisici:
    - Area frontale (A_ref)
    - Coefficiente portanza (CL)
    - Coefficiente drag (CD)
    - Angolo attacco (AoA)
    - Effetto DRS
    - Effetto beam wing
    """
    
    def __init__(self, config=None):
        """
        Inizializza ala posteriore con configurazione
        
        Args:
            config: dict con parametri personalizzati
                - aoa: angolo attacco (gradi)
                - drs_active: DRS attivo (bool)
                - ground_effect: altezza da suolo (m)
                - beam_wing_active: beam wing attivo (bool)
        """
        defaults = {
            'aoa': 12.0,           # Angolo attacco (gradi)
            'drs_active': False,   # DRS disattivato
            'ground_effect': 0.05, # Altezza da suolo (m)
            'beam_wing_active': True,  # Beam wing attivo
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Parametri geometrici F1 2025
        self.SPAN = 1.60   # Apertura ala posteriore (m)
        self.CHORD = 0.50  # Corda media (m)
        
        # Area di riferimento (superficie alare)
        self.A_REF = self.SPAN * self.CHORD  # 0.80 m²
        
        # Area riferimento comune per confronto (area frontale auto)
        self.A_REF_COMMON = 1.60  # m²
        
        # Parametri aerodinamici base (senza DRS)
        # Valori calibrati F1 2025: cl_alpha=0.07/° satura a CL_MAX=1.95 intorno a 28°
        # Range operativo utile: 8-35° (Monza ~8-12°, Monaco ~30-35°)
        self.CL_MAX = 1.95        # Portanza massima (stallo) - multi-element F1
        self.CL_MIN = -0.80       # Portanza negativa
        self.CD_MIN = 0.035       # Drag minimo (profili ottimizzati)
        self.K_FACTOR = 0.080     # Induced drag factor (lower AR → higher K)
        
        # Parametri DRS
        self.DRS_CL_BOOST = 0.50  # Incremento portanza con DRS
        self.DRS_CD_BOOST = 0.035 # Incremento drag con DRS
        
        # Sensibilità ground effect (wing-ground interaction only)
        self.GROUND_EFFECT_SENSITIVITY = 0.03  # +3% CL per ogni mm sotto ottimale
        
        # Effetto beam wing
        self.BEAM_WING_CL_BOOST = 0.15  # +15% CL da beam wing
        self.BEAM_WING_CD_BOOST = 0.020 # +20% CD da beam wing
        
    def calculate_forces(self, rho, v):
        """
        Calcola forze aerodinamiche ala posteriore
        
        Args:
            rho: Densità aria (kg/m³)
            v: Velocità (m/s)
            
        Returns:
            dict con lift, drag, CL, CD
        """
        # Angolo attacco effettivo
        aoa = self.config['aoa']
        if self.config['drs_active']:
            aoa -= 2.0  # DRS riduce AoA
        
        aoa = np.clip(aoa, 0, 40)

        # Calcola CL
        # cl_alpha = 0.055/° → range utile 8-33° senza saturazione
        # Lower AR + longer chord = flatter lift slope than front wing
        cl_alpha = 0.055  # Pendenza CL vs aoa (per grado) - F1 lower AR
        cl_base = cl_alpha * aoa
        
        # Ground effect
        ground_effect_factor = 1.0
        if self.config['ground_effect'] < 0.07:
            deficit = (0.07 - self.config['ground_effect']) * 1000
            ground_effect_factor = 1.0 + (deficit * self.GROUND_EFFECT_SENSITIVITY / 10)
        
        cl = cl_base * ground_effect_factor
        
        # Clamp CL
        cl = np.clip(cl, self.CL_MIN, self.CL_MAX)
        
        # Calcola CD
        cd = self.CD_MIN + self.K_FACTOR * (cl ** 2)
        
        # DRS
        if self.config['drs_active']:
            cl += self.DRS_CL_BOOST
            cd += self.DRS_CD_BOOST
        
        # Beam wing
        if self.config['beam_wing_active']:
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
            'L/D': lift / drag if drag > 0 else 0,
        }
    
    def set_aoa(self, angle_deg):
        self.config['aoa'] = np.clip(angle_deg, 0, 40)
    
    def set_drs(self, active):
        self.config['drs_active'] = active
    
    def set_ground_effect(self, height_m):
        self.config['ground_effect'] = np.clip(height_m, 0.02, 0.15)
    
    def set_beam_wing(self, active):
        self.config['beam_wing_active'] = active
    
    def get_summary(self):
        return {
            'aoa': self.config['aoa'],
            'drs': self.config['drs_active'],
            'ground_effect_mm': self.config['ground_effect'] * 1000,
            'beam_wing': self.config['beam_wing_active'],
        }


def create_rear_wing_from_setup(setup_config):
    """
    Crea ala posteriore da setup UI
    """
    config = {
        'aoa': setup_config.get('rear_wing_angle', 12.0),
        'drs_active': setup_config.get('rear_wing_drs', False),
        'ground_effect': setup_config.get('rear_wing_ground_effect', 50) / 1000,
        'beam_wing_active': setup_config.get('rear_wing_beam_wing', True),
    }
    return RearWing(config)


if __name__ == '__main__':
    rw = RearWing()
    
    rho = 1.225
    v = 100
    
    forces = rw.calculate_forces(rho, v)
    print("Rear Wing Forces:")
    print(f"  CL: {forces['CL']:.3f}")
    print(f"  CD: {forces['CD']:.3f}")
    print(f"  Lift: {forces['lift']:.1f} N")
    print(f"  Drag: {forces['drag']:.1f} N")
    print(f"  L/D: {forces['L/D']:.2f}")
    
    rw.set_drs(True)
    forces_drs = rw.calculate_forces(rho, v)
    print("\nWith DRS:")
    print(f"  CL: {forces_drs['CL']:.3f} (+{forces_drs['CL']-forces['CL']:.3f})")
    print(f"  CD: {forces_drs['CD']:.3f} (+{forces_drs['CD']-forces['CD']:.3f})")
