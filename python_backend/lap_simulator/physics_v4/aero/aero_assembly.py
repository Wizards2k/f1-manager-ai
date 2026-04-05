"""
AeroAssembly - Calcolo forze aerodinamiche da componenti individuali.

Nel V4, ogni componente aerodinamica contribuisce fisicamente:
- Front Wing: downforce anteriore + drag
- Rear Wing: downforce posteriore + drag (con DRS)
- Floor (Front/Rear): ground effect + downforce
- Sidepods: drag + cooling contribution
- Engine Cover: flow conditioning
- B-Wing: mini-ala posteriore

Il downforce totale e il drag sono la SOMMA dei contributi individuali.
NON ci sono moltiplicatori magici o penalty empiriche.

VERSIONE FISICA: Usa moduli individuali per calcolo preciso.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import math

# Import moduli fisici individuali
from .front_wing import FrontWing
from .rear_wing import RearWing
from .floor_front import FloorFront
from .floor_rear import FloorRear
from .sidepods import Sidepods
from .engine_cover import EngineCover
from .bwing import BWing


@dataclass
class AeroComponent:
    """
    Singola componente aerodinamica.
    
    Ogni componente ha:
    - CLA: coefficiente di portanza (downforce)
    - CDA: coefficiente di resistenza (drag)
    - Contributi percentuali agli assi (front/rear)
    """
    name: str
    cla_base: float  # m² coefficiente lift base
    cda_base: float  # m² coefficiente drag base
    angle_deg: float  # gradi inclinazione attuale
    angle_ref_deg: float  # gradi riferimento
    angle_sensitivity: float  # variazione CLA/CDA per grado
    front_rear_ratio: float = 0.5  # 0.0=tutto rear, 1.0=tutto front
    drs_reduction: float = 0.0  # riduzione drag se DRS (solo rear wing)
    stall_angle_deg: float = 15.0  # angolo stallo aerodinamico


@dataclass
class AeroForces:
    """
    Forze aerodinamiche risultanti.
    
    Output del calcolo aero, usato dal vehicle dynamics.
    """
    cla_total: float  # m² coefficiente lift totale
    cda_total: float  # m² coefficiente drag totale
    cla_front: float  # m² lift anteriore
    cla_rear: float  # m² lift posteriore
    aero_balance: float  # cla_front / cla_total (target 0.45-0.55)
    
    # Forze fisiche a velocità v
    f_downforce: float = 0.0  # N forza downforce totale
    f_drag: float = 0.0  # N forza drag totale
    f_downforce_front: float = 0.0  # N downforce anteriore
    f_downforce_rear: float = 0.0  # N downforce posteriore
    
    # Effetti dinamici
    ground_effect_bonus: float = 1.0  # moltiplicatore da ride height
    drs_active: bool = False
    
    # Forze per componente (debug/test)
    component_forces: Dict = None  # dict con forze per ogni modulo


class AeroAssembly:
    """
    Combina tutte le componenti aerodinamiche per calcolare forze totali.
    
    Usa moduli fisici individuali per calcolo preciso:
    - FrontWing: modello CL/CD con DRS e ground effect
    - RearWing: modello CL/CD con DRS e beam wing
    - FloorFront: ground effect anteriore
    - FloorRear: diffusore posteriore
    - Sidepods: drag + venturi
    - EngineCover: flow conditioning
    - BWing: mini-ala
    """
    
    def __init__(self):
        """Inizializza moduli aerodinamici individuali."""
        
        # Moduli fisici individuali
        self.front_wing = FrontWing()
        self.rear_wing = RearWing()
        self.floor_front = FloorFront()
        self.floor_rear = FloorRear()
        self.sidepods = Sidepods()
        self.engine_cover = EngineCover()
        self.bwing = BWing()
        
        # Ground effect parameters
        self.ride_height_optimal_front = 0.040  # 40mm
        self.ride_height_optimal_rear = 0.050  # 50mm
        self.ground_effect_sensitivity = 0.010  # +1% CLA per mm sotto ottimale
    
    def set_component_angles(self, angles: Dict[str, float]):
        """Imposta angoli componenti."""
        if 'front_wing' in angles:
            self.front_wing.set_aoa(angles['front_wing'])
        if 'rear_wing' in angles:
            self.rear_wing.set_aoa(angles['rear_wing'])
        if 'b_wing' in angles:
            self.bwing.set_aoa(angles['b_wing'])
    
    def set_drs(self, active: bool):
        """Attiva/disattiva DRS."""
        self.front_wing.set_drs(active)
        self.rear_wing.set_drs(active)
    
    def set_ride_height(self, front: float, rear: float):
        """Imposta altezza da suolo."""
        self.floor_front.set_ride_height(front)
        self.floor_rear.set_ride_height(rear)
    
    def compute_forces(
        self,
        speed_ms: float,
        air_density: float = 1.225,
        ride_height_front: float = 0.040,
        ride_height_rear: float = 0.050,
        drs_active: bool = False
    ) -> 'AeroForces':
        """
        Calcola tutte le forze aerodinamiche usando moduli fisici.
        
        Args:
          speed_ms: velocità [m/s]
          air_density: densità aria [kg/m³]
          ride_height_front: altezza anteriore [m]
          ride_height_rear: altezza posteriore [m]
          drs_active: DRS aperto
        
        Returns:
          AeroForces con tutti i coefficienti e forze
        """
        # Aggiorna DRS
        self.set_drs(drs_active)
        self.set_ride_height(ride_height_front, ride_height_rear)
        
        # Calcola forze per ogni modulo
        forces = {}
        
        forces['front_wing'] = self.front_wing.calculate_forces(air_density, speed_ms)
        forces['rear_wing'] = self.rear_wing.calculate_forces(air_density, speed_ms)
        forces['floor_front'] = self.floor_front.calculate_forces(air_density, speed_ms, ride_height_front)
        forces['floor_rear'] = self.floor_rear.calculate_forces(air_density, speed_ms, ride_height_rear)
        forces['sidepods'] = self.sidepods.calculate_forces(air_density, speed_ms)
        forces['engine_cover'] = self.engine_cover.calculate_forces(air_density, speed_ms)
        forces['bwing'] = self.bwing.calculate_forces(air_density, speed_ms)
        
        # Calcola totali SOMMANDO LE FORZE IN NEWTON (non coefficienti)
        # Questo è il metodo fisicamente corretto: ogni modulo calcola la sua forza
        f_down_total = sum(f['lift'] for f in forces.values())
        f_drag_total = sum(f['drag'] for f in forces.values())
        
        # Deriviamo CLA e CDA dalle forze totali usando l'area frontale della F1
        A_REF_F1 = 1.60  # m² area frontale tipica F1
        q = 0.5 * air_density * speed_ms ** 2  # pressione dinamica
        
        # CLA = F_down / (q * A_ref), CDA = F_drag / (q * A_ref)
        cla_total = f_down_total / max(q * A_REF_F1, 0.01)
        cda_total = f_drag_total / max(q * A_REF_F1, 0.01)
        
        # Distribuisci front/rear SOMMANDO le forze (non coefficienti)
        f_down_front = (
            forces['front_wing']['lift'] +
            forces['floor_front']['lift'] +
            forces['sidepods']['lift'] * 0.5 +
            forces['engine_cover']['lift'] * 0.3
        )
        f_down_rear = (
            forces['rear_wing']['lift'] +
            forces['floor_rear']['lift'] +
            forces['sidepods']['lift'] * 0.5 +
            forces['bwing']['lift']
        )
        
        # Deriva CLA front/rear dalle forze
        cla_front = f_down_front / max(q * A_REF_F1, 0.01)
        cla_rear = f_down_rear / max(q * A_REF_F1, 0.01)
        
        # Calcola aero balance
        aero_balance = cla_front / max(cla_total, 0.01)
        
        return AeroForces(
            cla_total=cla_total,
            cda_total=cda_total,
            cla_front=cla_front,
            cla_rear=cla_rear,
            aero_balance=aero_balance,
            f_downforce=f_down_total,
            f_drag=f_drag_total,
            f_downforce_front=f_down_front,
            f_downforce_rear=f_down_rear,
            ground_effect_bonus=1.0,  # Gestito dai moduli individuali
            drs_active=drs_active,
            component_forces=forces
        )
    
    def get_aero_efficiency(self) -> float:
        """Calcola efficienza aerodinamica (L/D ratio) dalle forze totali."""
        # Calcola forze a 100 m/s (~360 kph) con aria standard
        test_speed = 100.0
        test_density = 1.225
        
        forces = {}
        forces['front_wing'] = self.front_wing.calculate_forces(test_density, test_speed)
        forces['rear_wing'] = self.rear_wing.calculate_forces(test_density, test_speed)
        forces['floor_front'] = self.floor_front.calculate_forces(test_density, test_speed, 0.040)
        forces['floor_rear'] = self.floor_rear.calculate_forces(test_density, test_speed, 0.050)
        forces['sidepods'] = self.sidepods.calculate_forces(test_density, test_speed)
        forces['engine_cover'] = self.engine_cover.calculate_forces(test_density, test_speed)
        forces['bwing'] = self.bwing.calculate_forces(test_density, test_speed)
        
        # Somma forze in Newton
        total_lift = sum(f['lift'] for f in forces.values())
        total_drag = sum(f['drag'] for f in forces.values())
        
        # L/D ratio = portanza / resistenza
        return total_lift / max(total_drag, 0.01)
