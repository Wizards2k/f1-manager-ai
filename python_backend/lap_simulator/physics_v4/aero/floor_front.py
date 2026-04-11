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
            'efficiency': 0.85,    # Efficienza venturi
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Parametri geometrici F1 2025
        self.WIDTH = 1.50   # Larghezza fondo (m)
        self.LENGTH = 1.20  # Lunghezza fondo anteriore (m)
        
        # Area di riferimento (superficie venturi)
        self.A_REF = self.WIDTH * self.LENGTH  # 1.80 m²
        
        # Area riferimento comune per confronto (area frontale auto)
        self.A_REF_COMMON = 1.60  # m²
        
        # Parametri aerodinamici
        self.CL_MAX = 1.20        # Portanza da ground effect
        self.CL_MIN = 0.30        # Minimo ground effect
        self.CL_ALPHA = 8.0       # Sensibilità altezza (CL per m)
        self.CD_BASE = 0.12       # Drag base ground effect (reale F1)
        
        # Sensibilità ground effect
        # Più basso = più portanza (fino a un punto)
        self.GROUND_EFFECT_SENSITIVITY = 25.0  # CL per metro di altezza
        
        # Interferenza con ala anteriore
        self.FRONT_WING_INTERFERENCE = 0.95  # -5% efficienza
        
        # FIX V4.15: Wing-Floor Coupling
        # In F1 reale, le ali condizionano il flusso al diffusore:
        # più angolo ala → flusso più energico → più ground effect.
        # Range: 0.85 (ala minima ~5°) a 1.15 (ala massima ~40°)
        # Default = 1.0 (nessun coupling, retro-compatibile)
        self.wing_coupling = 1.0
        
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
        
        # FIX V4.15: Wing-Floor Coupling
        # Più angolo ala anteriore → flusso più energico → più ground effect
        cl *= self.wing_coupling
        
        # Clamp CL
        cl = np.clip(cl, self.CL_MIN, self.CL_MAX)
        
        # FIX V4.16: Drag da ground effect con coupling
        # Più carico (wing_coupling alto) → più downforce MA anche più drag
        # Il ground effect non è "gratis": flusso più energico = più resistenza
        # K_floor = 0.08 (era 0.02) per L/D floor ~2.5-3.0 (reale F1)
        cd = self.CD_BASE + 0.08 * (cl ** 2)
        
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
        FIX V4.15: Imposta il coupling ala-floor.
        
        In F1 reale, le ali condizionano il flusso al diffusore:
        più angolo ala → flusso più energico sotto l'auto → più ground effect.
        
        Il front wing ha un effetto maggiore sul floor anteriore (flusso diretto),
        il rear wing ha un effetto minore (flusso indiretto tramite beam wing).
        
        Range: 0.85 (ala minima ~5°) a 1.15 (ala massima ~40°)
        """
        # Front wing coupling: effetto diretto sul floor anteriore
        # Formula: coupling = 0.85 + 0.30 * (fw_aoa / 40.0)
        # fw=5° → 0.89, fw=20° → 1.00, fw=38° → 1.14
        fw_coupling = 0.85 + 0.30 * min(front_wing_aoa / 40.0, 1.0)
        
        # Rear wing coupling: effetto indiretto (più debole)
        # Formula: coupling = 0.90 + 0.15 * (rw_aoa / 42.0)
        # rw=10° → 0.94, rw=22° → 0.99, rw=42° → 1.05
        rw_coupling = 0.90 + 0.15 * min(rear_wing_aoa / 42.0, 1.0)
        
        # Il floor anteriore è più influenzato dal front wing
        self.wing_coupling = 0.7 * fw_coupling + 0.3 * rw_coupling
    
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
