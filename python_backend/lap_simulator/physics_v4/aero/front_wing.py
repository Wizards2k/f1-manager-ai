"""
Aerodinamica: Ala Anteriore

Modello fisico completo dell'ala anteriore F1 2025:
- Coefficiente portanza (CL) vs angolo attacco
- Coefficiente drag (CD) vs CL
- Effetto DRS (Drag Reduction System)
- Sensibilità al ground effect (altezza da suolo)
- Effetto di interferenza con sidepods
"""

import numpy as np


class FrontWing:
    """
    Ala anteriore F1 2025 - Modello Fisico Dettagliato
    
    Parametri fisici:
    - Area frontale (A_ref)
    - Coefficiente portanza (CL)
    - Coefficiente drag (CD)
    - Angolo attacco (AoA)
    - Effetto DRS
    - Ground effect
    """
    
    def __init__(self, config=None):
        """
        Inizializza ala anteriore con configurazione
        
        Args:
            config: dict con parametri personalizzati
                - aoa: angolo attacco (gradi)
                - drs_active: DRS attivo (bool)
                - ground_effect: altezza da suolo (m)
        """
        defaults = {
            'aoa': 20.0,           # Angolo attacco (gradi)
            'drs_active': False,   # DRS disattivato
            'ground_effect': 0.05, # Altezza da suolo (m)
        }
        
        self.config = {**defaults, **(config or {})}
        
        # Parametri geometrici F1 2025
        self.SPAN = 1.80   # Apertura ala anteriore (m) - larghezza massima F1
        self.CHORD = 0.45  # Corda media (m) - profondità ala
        
        # Area di riferimento (superficie alare)
        self.A_REF = self.SPAN * self.CHORD  # 0.81 m²
        
        # Area riferimento comune per confronto (area frontale auto)
        self.A_REF_COMMON = 1.60  # m²
        
        # Parametri aerodinamici base (senza DRS)
        # FIX V4.14: cl_alpha abbassato per avere range operativo fino a ~40°
        # senza saturazione prematura.
        self.CL_MAX = 2.50        # Portanza massima (stallo) - multi-element F1
        self.CL_MIN = -0.50       # Portanza negativa (inverted wing)
        self.CD_MIN = 0.025       # Drag minimo (profili ottimizzati)
        # FIX V5.7: K_FACTOR aumentato da 0.200 a 0.35 per rendere il drag
        # più sensibile all'angolo dell'ala. Il V5.2 (K=0.200) dava L/D troppo
        # alto a bassi angoli (7.06 a 8°), rendendo High-DF sempre conveniente
        # anche a Monza. In F1 reale, L/D range è ~5.0 (Low-DF) a ~3.0 (High-DF).
        # K=0.35 dà: L/D@8°=5.21, L/D@20°=3.09, L/D@38°=1.74 — realistico.
        # NOTA: Il fix principale per Monza è nel floor drag (vedi floor_front.py).
        self.K_FACTOR = 0.350     # Induced drag: L/D range realistico F1
        
        # Parametri DRS
        self.DRS_CL_BOOST = 0.35  # Incremento portanza con DRS
        self.DRS_CD_BOOST = 0.020 # Incremento drag con DRS
        
        # Sensibilità ground effect (wing-ground interaction only, NOT floor effect)
        # Floor effect is handled by floor modules; wing GE is ~5-8% enhancement
        self.GROUND_EFFECT_SENSITIVITY = 0.03  # +3% CL per ogni mm sotto ottimale
        
        # Interferenza con sidepods (riduzione efficienza)
        self.SIDEPODS_INTERFERENCE = 0.96  # -4% efficienza
        
    def calculate_forces(self, rho, v):
        """
        Calcola forze aerodinamiche ala anteriore
        
        Args:
            rho: Densità aria (kg/m³)
            v: Velocità (m/s)
            
        Returns:
            dict con lift, drag, CL, CD
        """
        # Angolo attacco effettivo (DRS modifica AoA)
        aoa = self.config['aoa']
        if self.config['drs_active']:
            aoa -= 3.0  # DRS riduce AoA di 3 gradi
        
        # Clamp AoA al range operativo F1 (multi-element fino a ~45°)
        aoa = np.clip(aoa, 0, 45)

        # Calcola CL (lineare fino a stallo)
        # FIX V5.2: cl_alpha ridotto da 0.055 a 0.042 per spostare il bilanciamento
        # del downforce verso il fondo (target: 60-65% floor, 35-40% wings).
        # Le ali F1 generano meno downforce per grado rispetto al modello precedente,
        # ma il floor compensa con coupling dinamico più forte.
        cl_alpha = 0.042  # Pendenza CL vs aoa (per grado) - F1 multi-element (era 0.055, poi 0.040)
        cl_base = cl_alpha * aoa
        
        # Ground effect (se altezza < ottimale)
        ground_effect_factor = 1.0
        if self.config['ground_effect'] < 0.07:  # < 70mm
            deficit = (0.07 - self.config['ground_effect']) * 1000  # mm
            ground_effect_factor = 1.0 + (deficit * self.GROUND_EFFECT_SENSITIVITY / 10)
        
        cl = cl_base * ground_effect_factor * self.SIDEPODS_INTERFERENCE
        
        # Clamp CL
        cl = np.clip(cl, self.CL_MIN, self.CL_MAX)
        
        # Calcola CD (drag parassita + indotto)
        cd = self.CD_MIN + self.K_FACTOR * (cl ** 2)
        
        # DRS aumenta sia CL che CD
        if self.config['drs_active']:
            cl += self.DRS_CL_BOOST
            cd += self.DRS_CD_BOOST
        
        # Forze
        q = 0.5 * rho * (v ** 2)  # Pressione dinamica
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
        """Imposta angolo attacco"""
        self.config['aoa'] = np.clip(angle_deg, 0, 25)
    
    def set_drs(self, active):
        """Attiva/disattiva DRS"""
        self.config['drs_active'] = active
    
    def set_ground_effect(self, height_m):
        """Imposta altezza da suolo"""
        self.config['ground_effect'] = np.clip(height_m, 0.02, 0.15)
    
    def get_summary(self):
        """Riepilogo configurazione"""
        return {
            'aoa': self.config['aoa'],
            'drs': self.config['drs_active'],
            'ground_effect_mm': self.config['ground_effect'] * 1000,
            'width_mm': self.config['width'] * 1000,
            'height_mm': self.config['height'] * 1000,
        }


def create_front_wing_from_setup(setup_config):
    """
    Crea ala anteriore da setup UI
    
    Args:
        setup_config: dict da UI (slider values)
            - front_wing_angle: 0-30 (angolo)
            - front_wing_drs: bool (DRS)
            - front_wing_ground_effect: 20-70 (mm)
    
    Returns:
        FrontWing instance
    """
    config = {
        'aoa': setup_config.get('front_wing_angle', 20.0),
        'drs_active': setup_config.get('front_wing_drs', False),
        'ground_effect': setup_config.get('front_wing_ground_effect', 50) / 1000,
    }
    return FrontWing(config)


# Test
if __name__ == '__main__':
    fw = FrontWing()
    
    # Test conditions
    rho = 1.225  # Sea level
    v = 100      # 100 m/s = 360 kph
    
    forces = fw.calculate_forces(rho, v)
    print("Front Wing Forces:")
    print(f"  CL: {forces['CL']:.3f}")
    print(f"  CD: {forces['CD']:.3f}")
    print(f"  Lift: {forces['lift']:.1f} N")
    print(f"  Drag: {forces['drag']:.1f} N")
    print(f"  L/D: {forces['L/D']:.2f}")
    
    # Test DRS
    fw.set_drs(True)
    forces_drs = fw.calculate_forces(rho, v)
    print("\nWith DRS:")
    print(f"  CL: {forces_drs['CL']:.3f} (+{forces_drs['CL']-forces['CL']:.3f})")
    print(f"  CD: {forces_drs['CD']:.3f} (+{forces_drs['CD']-forces['CD']:.3f})")
