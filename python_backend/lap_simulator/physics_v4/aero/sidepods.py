"""
Aerodinamica: Sidepods

Modello fisico dei sidepods F1 2025:
- Ground effect laterale (canali Venturi)
- Drag da cooling e forma
- Interferenza con ala anteriore e posteriore
- Sensibilità all'altezza da suolo

In F1 reale, i sidepods producono downforce significativo tramite
i canali Venturi laterali che accelerano il flusso sotto il fondo.
Il L/D tipico è ~3-4, con ~5-8% del downforce totale e ~8-12% del drag.
"""

import numpy as np


class Sidepods:
    """
    Sidepods F1 2025 - Modello Fisico
    
    Parametri:
    - Area venturi laterali (A_ref)
    - Area frontale per drag (A_ref_drag)
    - Ground effect laterale (CL dipendente da altezza)
    - Wing coupling (sensibilità all'angolo ala)
    """
    
    def __init__(self, config=None):
        defaults = {
            'cooling_efficiency': 0.85,    # Efficienza raffreddamento
            'ride_height': 0.05,           # Altezza da suolo (m)
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Parametri geometrici F1 2025
        self.WIDTH = 0.85   # Larghezza sidepod (m)
        self.HEIGHT = 0.90  # Altezza sidepod (m)
        self.LENGTH = 1.20  # Lunghezza sidepod (m)
        
        # Area di riferimento per downforce (superficie venturi laterali)
        # I sidepods hanno una superficie inferiore che genera ground effect
        self.A_REF = self.WIDTH * self.LENGTH  # 1.02 m² (superficie Venturi)
        
        # Area frontale per drag (forma + cooling)
        # Non tutta la superficie frontale genera drag: il flusso interno
        # è guidato dai canali Venturi. Il drag effettivo è ~35% della frontale.
        self.A_REF_FRONT = self.WIDTH * self.HEIGHT  # 0.765 m² (per lato)
        self.A_REF_DRAG = 2 * self.A_REF_FRONT * 0.35  # 0.536 m² (drag effettivo)
        
        # Area riferimento comune per confronto (area frontale auto)
        self.A_REF_COMMON = 1.60  # m²
        
        # Parametri aerodinamici
        # FIX V4.16b: Sidepods con ground effect realistico.
        # In F1 reale i sidepods producono downforce significativo tramite
        # canali Venturi laterali (L/D ~3-4). Il modello precedente aveva
        # CL_VENTURI=0.30 * venturi_effect=0.03 = CL_eff=0.009, quasi zero.
        # Nuovo modello: CL dipende da altezza da suolo (come il floor),
        # con wing coupling per sensibilità all'angolo dell'ala.
        # Target: ~5-8% del downforce totale, ~8-12% del drag totale, L/D ~3.5
        self.CL_MAX = 0.45        # Portanza massima da ground effect laterale
        self.CL_MIN = 0.10        # Portanza minima (sempre positivo, forma)
        self.CD_BASE = 0.08       # Drag base (forma)
        self.CD_COOLING = 0.04    # Drag aggiuntivo da cooling (aperture)
        self.K_FACTOR = 0.06      # Drag indotto (piccolo, L/D alto)
        
        # Sensibilità ground effect
        self.RIDE_HEIGHT_OPTIMAL = 0.04  # Altezza ottimale (m)
        
        # Interferenze con ali
        self.FRONT_WING_INTERFERENCE = 0.97  # -3% con ala anteriore
        self.REAR_WING_INTERFERENCE = 0.95   # -5% con ala posteriore
        
        # FIX V4.16b: Wing coupling (come floor)
        # Le ali condizionano il flusso ai sidepods:
        # più angolo ala → flusso più energico → più ground effect laterale
        self.wing_coupling = 1.0
        
    def calculate_forces(self, rho, v, ride_height=None):
        """
        Calcola forze sidepods
        
        Args:
            rho: Densità aria (kg/m³)
            v: Velocità (m/s)
            ride_height: Altezza da suolo (m), default config
            
        Returns:
            dict con lift, drag, CL, CD
        """
        if ride_height is None:
            ride_height = self.config.get('ride_height', 0.05)
        
        ride_height = np.clip(ride_height, 0.03, 0.15)
        
        # Ground effect laterale: più basso = più downforce
        ratio = ride_height / self.RIDE_HEIGHT_OPTIMAL
        cl_base = self.CL_MAX * (1.0 - 0.4 * (ratio ** 2))
        
        # Wing coupling: più angolo ala → flusso più energico ai Venturi
        cl = cl_base * self.wing_coupling
        
        # Interferenze
        cl *= self.FRONT_WING_INTERFERENCE * self.REAR_WING_INTERFERENCE
        
        # Clamp CL
        cl = np.clip(cl, self.CL_MIN, self.CL_MAX)
        
        # Drag: forma + cooling + indotto
        cd = self.CD_BASE + self.CD_COOLING + self.K_FACTOR * (cl ** 2)
        
        # Forze (downforce su superficie Venturi, drag su area frontale)
        q = 0.5 * rho * (v ** 2)
        lift = cl * q * self.A_REF
        drag = cd * q * self.A_REF_DRAG
        
        return {
            'lift': lift,
            'drag': drag,
            'CL': cl,
            'CD': cd,
        }
    
    def set_ride_height(self, height_m):
        """Imposta altezza da suolo"""
        self.config['ride_height'] = np.clip(height_m, 0.03, 0.15)
    
    def set_wing_coupling(self, front_wing_aoa: float, rear_wing_aoa: float):
        """
        FIX V4.16b: Imposta il coupling ala-sidepods.
        
        Le ali condizionano il flusso ai sidepods:
        più angolo ala → flusso più energico → più ground effect laterale.
        Range: 0.90 (ala minima ~5°) a 1.10 (ala massima ~40°)
        """
        # Front wing ha effetto diretto sul flusso ai sidepods
        fw_coupling = 0.90 + 0.20 * min(front_wing_aoa / 40.0, 1.0)
        # Rear wing ha effetto indiretto (estrazione)
        rw_coupling = 0.95 + 0.10 * min(rear_wing_aoa / 42.0, 1.0)
        
        # I sidepods sono più influenzati dal front wing (flusso diretto)
        self.wing_coupling = 0.6 * fw_coupling + 0.4 * rw_coupling
    
    def set_cooling(self, efficiency):
        """Imposta efficienza raffreddamento"""
        self.config['cooling_efficiency'] = np.clip(efficiency, 0.70, 0.95)
        # Più cooling = più drag (aperture più grandi)
        self.CD_COOLING = 0.02 + (0.95 - efficiency) * 0.04
    
    def get_summary(self):
        return {
            'ride_height_mm': self.config.get('ride_height', 0.05) * 1000,
            'cooling_eff': self.config['cooling_efficiency'],
        }


if __name__ == '__main__':
    sp = Sidepods()
    
    rho = 1.225
    v = 80
    
    for h in [0.03, 0.04, 0.05, 0.07, 0.10]:
        sp.set_ride_height(h)
        forces = sp.calculate_forces(rho, v)
        ld = forces['lift'] / forces['drag'] if forces['drag'] > 0 else 0
        print(f"Height {h*1000:.0f}mm: CL={forces['CL']:.3f}, CD={forces['CD']:.4f}, "
              f"Lift={forces['lift']:.0f}N, Drag={forces['drag']:.0f}N, L/D={ld:.2f}")
