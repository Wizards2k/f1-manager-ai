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
            'diffuser_angle': 7.0, # Angolo diffusore (gradi)
            'efficiency': 0.90,    # Efficienza diffusore
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Parametri geometrici F1 2025
        self.WIDTH = 1.40   # Larghezza diffusore (m)
        self.LENGTH = 1.50  # Lunghezza diffusore (m)
        
        # Area di riferimento (superficie diffusore)
        self.A_REF = self.WIDTH * self.LENGTH  # 2.10 m²
        
        # Area riferimento comune per confronto (area frontale auto)
        self.A_REF_COMMON = 1.60  # m²
        
        # Parametri aerodinamici
        # FIX V5.2: CL_MAX aumentato da 1.80 a 2.50 per permettere al diffusore
        # di generare la maggior parte del downforce (target F1 reale: 60-65% floor).
        # Il diffusore è il componente aero più importante di una F1.
        self.CL_MAX = 2.50        # Portanza da ground effect (era 1.80, poi 3.00)
        self.CL_MIN = 0.50        # Minimo ground effect
        self.CL_ALPHA = 12.0      # Sensibilità altezza
        self.CD_BASE = 0.15       # Drag base diffusore (reale F1)
        
        # Sensibilità ground effect
        self.GROUND_EFFECT_SENSITIVITY = 30.0
        
        # Interferenza con ala posteriore
        self.REAR_WING_INTERFERENCE = 0.93  # -7% efficienza
        
        # FIX V4.15: Wing-Floor Coupling
        # In F1 reale, le ali condizionano il flusso al diffusore:
        # più angolo ala → flusso più energico → più ground effect.
        # Range: 0.85 (ala minima ~5°) a 1.15 (ala massima ~40°)
        # Default = 1.0 (nessun coupling, retro-compatibile)
        self.wing_coupling = 1.0
        
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
        
        # Applica interferenza
        cl = cl_base * self.REAR_WING_INTERFERENCE
        
        # FIX V4.15: Wing-Floor Coupling
        # Più angolo ala → flusso più energico → più ground effect
        cl *= self.wing_coupling
        
        # Clamp CL
        cl = np.clip(cl, self.CL_MIN, self.CL_MAX)
        
        # FIX V5.2: Drag da diffusore con coupling
        # Più carico (wing_coupling alto) → più downforce MA anche più drag
        # Il diffusore non è "gratis": estrazione più forte = più resistenza
        # K_floor = 0.18 (era 0.10) per L/D diffusore ~3.0-3.5 (reale F1)
        # Compromesso: abbastanza drag per setup variati, non troppo per Monza
        cd = self.CD_BASE + 0.18 * (cl ** 2)
        
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
    
    def set_wing_coupling(self, front_wing_aoa: float, rear_wing_aoa: float):
        """
        FIX V5.2: Coupling ala-diffusore dinamico.
        
        In F1 reale, le ali condizionano il flusso al diffusore:
        più angolo ala → flusso più energico sotto l'auto → più ground effect.
        
        Il diffusore genera la maggior parte del downforce e scala
        significativamente con l'angolo dell'ala.
        Range coupling: 0.70 (ala minima) a 1.40 (ala massima).
        
        Il rear wing ha un effetto maggiore sul diffusore (beam wing + estrazione),
        il front wing ha un effetto minore (flusso indiretto).
        """
        # Rear wing coupling: effetto diretto sul diffusore (beam wing + estrazione)
        # Range: 0.70 (rw=0°) a 1.40 (rw=42°)
        # rw=14° → 0.87, rw=22° → 1.01, rw=32° → 1.17
        rw_coupling = 0.70 + 0.70 * min(rear_wing_aoa / 42.0, 1.0)
        
        # Front wing coupling: effetto indiretto sul diffusore (più debole)
        # Range: 0.80 (fw=0°) a 1.20 (fw=40°)
        # fw=12° → 0.91, fw=20° → 1.05, fw=28° → 1.19
        fw_coupling = 0.80 + 0.40 * min(front_wing_aoa / 40.0, 1.0)
        
        # Il diffusore è più influenzato dal rear wing (estrazione diretta)
        self.wing_coupling = 0.3 * fw_coupling + 0.7 * rw_coupling
    
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
