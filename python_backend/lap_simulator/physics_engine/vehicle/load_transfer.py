"""
Load Transfer - Trasferimento carico F1 2025

Modello fisico load transfer:
- Longitudinale (accelerazione/frenata)
- Laterale (curva)
- Effetti su grip e handling
- Roll stiffness distribution

NOTA: Modulo V4 standalone, non dipende da codice V1
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np


@dataclass
class LoadTransferState:
    """Stato trasferimento carico."""
    longitudinal_transfer_kn: float  # kN trasferimento longitudinale
    lateral_transfer_kn: float  # kN trasferimento laterale
    load_front_left_kn: float  # kN carico ruota LF
    load_front_right_kn: float  # kN carico ruota RF
    load_rear_left_kn: float  # kN carico ruota LR
    load_rear_right_kn: float  # kN carico ruota RR


class LoadTransfer:
    """
    Trasferimento carico F1 2025
    
    Meccanismi:
    1. Longitudinale: accelerazione/frenata sposta carico front↔rear
    2. Laterale: curva sposta carico left↔right
    3. Geometrico: altezza CG, wheelbase, track width
    4. Sospensioni: roll stiffness, antiroll bars
    
    Effetti:
    - Ruota esterna in curva: +carico, +grip (ma load sensitivity)
    - Ruota interna in curva: -carico, -grip (può sollevare)
    - Frenata: +carico anteriore, -carico posteriore
    - Accelerazione: -carico anteriore, +carico posteriore
    """
    
    def __init__(
        self,
        mass_kg: float = 878.0,
        wheelbase_m: float = 3.60,
        track_front_m: float = 1.60,
        track_rear_m: float = 1.50,
        cg_height_m: float = 0.28,
        cg_x_pct: float = 0.47,  # 47% da front axle
        roll_stiffness_front: float = 0.55,  # 55% roll stiffness anteriore
    ):
        """
        Inizializza modello load transfer
        
        Args:
            mass_kg: kg massa totale
            wheelbase_m: m passo vettura
            track_front_m: m carreggiata anteriore
            track_rear_m: m carreggiata posteriore
            cg_height_m: m altezza baricentro
            cg_x_pct: % posizione CG longitudinale (da front axle)
            roll_stiffness_front: % roll stiffness anteriore
        """
        self.mass_kg = mass_kg
        self.wheelbase_m = wheelbase_m
        self.track_front_m = track_front_m
        self.track_rear_m = track_rear_m
        self.cg_height_m = cg_height_m
        self.cg_x_m = wheelbase_m * cg_x_pct  # m da front axle
        self.cg_rear_m = wheelbase_m - self.cg_x_m  # m da rear axle
        self.roll_stiffness_front = roll_stiffness_front
        self.roll_stiffness_rear = 1.0 - roll_stiffness_front
        
        # Peso statico (G = 9.81 m/s²)
        G = 9.81
        weight_total = mass_kg * G
        self.static_load_front = weight_total * (self.cg_rear_m / wheelbase_m)
        self.static_load_rear = weight_total * (self.cg_x_m / wheelbase_m)
        
        # Stato corrente
        self.state = LoadTransferState(
            longitudinal_transfer_kn=0.0,
            lateral_transfer_kn=0.0,
            load_front_left_kn=self.static_load_front / 2.0 / 1000.0,
            load_front_right_kn=self.static_load_front / 2.0 / 1000.0,
            load_rear_left_kn=self.static_load_rear / 2.0 / 1000.0,
            load_rear_right_kn=self.static_load_rear / 2.0 / 1000.0,
        )
    
    def calculate_longitudinal_transfer(
        self,
        acceleration_ms2: float,
        is_braking: bool = False
    ) -> float:
        """
        Calcola trasferimento carico longitudinale
        
        Args:
            acceleration_ms2: m/s² accelerazione (negativa = frenata)
            is_braking: True se frenata
        
        Returns:
            kN trasferimento (front→rear se positivo)
        """
        # ΔLoad = (mass × acc × cg_height) / wheelbase
        delta_load = (self.mass_kg * abs(acceleration_ms2) * self.cg_height_m) / self.wheelbase_m
        
        # Converti a kN
        delta_load_kn = delta_load / 1000.0
        
        # Frenata: carico va anteriore
        # Accelerazione: carico va posteriore
        if is_braking:
            return delta_load_kn  # Positivo = anteriore
        else:
            return -delta_load_kn  # Negativo = posteriore
    
    def calculate_lateral_transfer(
        self,
        lateral_g: float,
        is_left_turn: bool = True
    ) -> Tuple[float, float]:
        """
        Calcola trasferimento carico laterale (front e rear)
        
        Args:
            lateral_g: g accelerazione laterale
            is_left_turn: True se curva a sinistra
        
        Returns:
            (front_transfer_kn, rear_transfer_kn)
        """
        # Carico laterale totale
        lateral_force = self.mass_kg * lateral_g * 9.81
        
        # Distribuzione front/rear in base a roll stiffness
        front_transfer = lateral_force * self.roll_stiffness_front * (self.cg_height_m / self.track_front_m)
        rear_transfer = lateral_force * self.roll_stiffness_rear * (self.cg_height_m / self.track_rear_m)
        
        # Converti a kN
        front_transfer_kn = front_transfer / 1000.0
        rear_transfer_kn = rear_transfer / 1000.0
        
        return front_transfer_kn, rear_transfer_kn
    
    def calculate_wheel_loads(
        self,
        longitudinal_g: float,
        lateral_g: float,
        is_braking: bool = False,
        is_left_turn: bool = True
    ) -> 'LoadTransferState':
        """
        Calcola carico su ciascuna ruota
        
        Args:
            longitudinal_g: g accelerazione longitudinale
            lateral_g: g accelerazione laterale
            is_braking: True se frenata
            is_left_turn: True se curva a sinistra
        
        Returns:
            LoadTransferState con carichi ruota
        """
        # Trasferimento longitudinale
        long_transfer = self.calculate_longitudinal_transfer(
            abs(longitudinal_g) * 9.81,
            is_braking
        )
        
        # Trasferimento laterale
        lat_front, lat_rear = self.calculate_lateral_transfer(lateral_g, is_left_turn)
        
        # Carichi statici (kN)
        static_front = self.static_load_front / 1000.0 / 2.0  # Per ruota
        static_rear = self.static_load_rear / 1000.0 / 2.0  # Per ruota
        
        # Carichi dinamici
        # Frenata: +front, -rear
        # Curva sinistra: +right, -left
        if is_braking:
            load_front = static_front + long_transfer / 2.0
            load_rear = static_rear - long_transfer / 2.0
        else:
            load_front = static_front - long_transfer / 2.0
            load_rear = static_rear + long_transfer / 2.0
        
        # Laterale (curva sinistra → +right, -left)
        if is_left_turn:
            self.state.load_front_left = load_front - lat_front
            self.state.load_front_right = load_front + lat_front
            self.state.load_rear_left = load_rear - lat_rear
            self.state.load_rear_right = load_rear + lat_rear
        else:
            self.state.load_front_left = load_front + lat_front
            self.state.load_front_right = load_front - lat_front
            self.state.load_rear_left = load_rear + lat_rear
            self.state.load_rear_right = load_rear - lat_rear
        
        # Aggiorna stato
        self.state.longitudinal_transfer_kn = long_transfer
        self.state.lateral_transfer_kn = lat_front + lat_rear
        
        return self.state
    
    def get_load_sensitivity_factor(self, load_kn: float) -> float:
        """
        Calcola fattore load sensitivity
        
        Il grip non scala linearmente col carico:
        - Basso carico: grip efficiente
        - Alto carico: grip meno efficiente (mu diminuisce)
        
        Args:
            load_kn: kN carico ruota
        
        Returns:
            float fattore (0.8-1.2)
        """
        # Formula semplificata: mu_eff = mu_0 × (load/load_ref)^(-0.1)
        load_ref = 5.0  # kN riferimento
        exponent = -0.1
        
        factor = (load_kn / load_ref) ** exponent
        
        return np.clip(factor, 0.8, 1.2)
    
    def get_state(
        self,
        longitudinal_g: float = 0.0,
        lateral_g: float = 0.0,
        is_braking: bool = False,
        is_left_turn: bool = True
    ) -> Dict:
        """Restituisce stato corrente come dict."""
        # Calcola carichi
        state = self.calculate_wheel_loads(longitudinal_g, lateral_g, is_braking, is_left_turn)
        
        # Calcola percentuali
        total_load = state.load_front_left + state.load_front_right + state.load_rear_left + state.load_rear_right
        front_load_pct = (state.load_front_left + state.load_front_right) / total_load * 100.0
        rear_load_pct = (state.load_rear_left + state.load_rear_right) / total_load * 100.0
        
        return {
            'longitudinal_transfer_kn': state.longitudinal_transfer_kn,
            'lateral_transfer_kn': state.lateral_transfer_kn,
            'front_load_pct': front_load_pct,
            'rear_load_pct': rear_load_pct,
            'load_front_left_kn': state.load_front_left,
            'load_front_right_kn': state.load_front_right,
            'load_rear_left_kn': state.load_rear_left,
            'load_rear_right_kn': state.load_rear_right,
        }
    
    def get_summary(self) -> Dict:
        """Riepilogo load transfer."""
        return {
            'mass_kg': self.mass_kg,
            'wheelbase_m': self.wheelbase_m,
            'cg_height_m': self.cg_height_m,
            'cg_x_pct': (self.cg_x_m / self.wheelbase_m) * 100,
            'roll_stiffness_front': self.roll_stiffness_front * 100,
            'roll_stiffness_rear': self.roll_stiffness_rear * 100,
            'static_load_front_kn': self.static_load_front / 1000.0,
            'static_load_rear_kn': self.static_load_rear / 1000.0,
            'current_state': {
                'longitudinal_transfer_kn': self.state.longitudinal_transfer_kn,
                'lateral_transfer_kn': self.state.lateral_transfer_kn,
                'load_front_left_kn': self.state.load_front_left,
                'load_front_right_kn': self.state.load_front_right,
                'load_rear_left_kn': self.state.load_rear_left,
                'load_rear_right_kn': self.state.load_rear_right,
            }
        }

# ============================================================================
# V6.3: Per-wheel load calculation (from waypoint_integrator.py)
# ============================================================================
def calculate_per_wheel_loads(
    velocity_ms: float,
    radius_m: float,
    mass_kg: float,
    f_downforce: float,
    v_target_ms: float,
    dt_step: float,
    front_wing: float = 18.0,
    rear_wing: float = 11.0,
    circuit_id: str = "",
) -> Dict[str, float]:
    """
    V6.3: Calculate per-wheel vertical load distribution.

    Accounts for:
    - Static load distribution (45% front, 55% rear)
    - Downforce distribution (setup-dependent via wing angles)
    - Lateral load transfer (cornering g-forces)
    - Brake load transfer (deceleration)

    Args:
        velocity_ms: Current velocity [m/s]
        radius_m: Corner radius [m], 999999 for straight
        mass_kg: Total car mass [kg]
        f_downforce: Aero downforce [N]
        v_target_ms: Target velocity from corner model [m/s]
        dt_step: Integration timestep [s]
        front_wing: Front wing angle (lower = oversteer, reduces front DF)
        rear_wing: Rear wing angle
        circuit_id: Circuit ID for left-bias detection

    Returns:
        Dict with per-wheel loads [kN]: {'FL': ..., 'FR': ..., 'RL': ..., 'RR': ...}
    """
    # V6.3.5: Physically-realistic downforce distribution based on wing setup
    wing_ratio = front_wing / max(1.0, rear_wing)
    df_front_frac = 0.45 + 0.28 * (wing_ratio - 1.64)
    df_front_frac = max(0.25, min(0.70, df_front_frac))
    df_rear_frac = 1.0 - df_front_frac

    # Static load per axle
    static_load_front_kn = (mass_kg * 9.81 * 0.45) / 1000.0
    static_load_rear_kn = (mass_kg * 9.81 * 0.55) / 1000.0

    # Downforce distribution
    df_front_kn = (f_downforce * df_front_frac) / 1000.0
    df_rear_kn = (f_downforce * df_rear_frac) / 1000.0

    # Lateral load transfer
    lat_accel_g = (velocity_ms ** 2) / (radius_m * 9.81) if radius_m < 9999 else 0.0
    lat_accel_g = min(3.5, lat_accel_g)
    total_load_kn = (static_load_front_kn + static_load_rear_kn + (f_downforce / 1000.0))
    H_CG_OVER_TRACK = 0.19
    load_transfer_lateral_kn = (total_load_kn * lat_accel_g * H_CG_OVER_TRACK) / 2.0

    # Brake load transfer
    decel_g = 0.0
    if v_target_ms < velocity_ms and dt_step > 0.001:
        delta_v_ms = velocity_ms - v_target_ms
        decel_g = (delta_v_ms / dt_step) / 9.81
    decel_g = min(5.0, decel_g)
    H_CG_OVER_L = 0.083
    load_transfer_brake_kn = (total_load_kn * decel_g * H_CG_OVER_L) / 2.0

    # Circuit-specific load transfer direction
    is_left_bias = "monza" in circuit_id.lower()
    lat_sign = -1.0 if is_left_bias else 1.0

    # Per-wheel loads
    load_fl_kn = (static_load_front_kn / 2.0 + df_front_kn / 2.0
                  + lat_sign * load_transfer_lateral_kn + load_transfer_brake_kn)
    load_fr_kn = (static_load_front_kn / 2.0 + df_front_kn / 2.0
                  - lat_sign * load_transfer_lateral_kn + load_transfer_brake_kn)
    load_rl_kn = (static_load_rear_kn / 2.0 + df_rear_kn / 2.0
                  + lat_sign * load_transfer_lateral_kn - load_transfer_brake_kn)
    load_rr_kn = (static_load_rear_kn / 2.0 + df_rear_kn / 2.0
                  - lat_sign * load_transfer_lateral_kn - load_transfer_brake_kn)

    return {
        'FL': max(0.1, load_fl_kn),
        'FR': max(0.1, load_fr_kn),
        'RL': max(0.1, load_rl_kn),
        'RR': max(0.1, load_rr_kn),
    }
