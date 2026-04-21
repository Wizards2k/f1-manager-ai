"""
PhysicsState - Stato fisico dell'auto durante l'integrazione.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class PhysicsState:
    """Stato fisico dell'auto durante l'integrazione."""
    
    # Cinematica
    distance_m: float = 0.0  # distanza percorsa [m]
    velocity_ms: float = 0.0  # velocità [m/s]
    acceleration_ms2: float = 0.0  # accelerazione [m/s²]
    time_s: float = 0.0  # tempo trascorso [s]
    
    # Forze
    f_engine: float = 0.0  # N forza motrice
    f_drag: float = 0.0  # N forza drag
    f_downforce: float = 0.0  # N forza downforce
    f_gravity: float = 0.0  # N forza gravità (pendenza)
    f_centripetal: float = 0.0  # N forza centripeta
    
    # Stati
    is_braking: bool = False
    is_throttle: bool = False
    is_drs_active: bool = False

    # V5.5: Brake state commitment (anti-chatter hysteresis)
    # Quando il lookahead decide di frenare, salva la velocità target.
    # La frenata resta attiva finché velocity_ms <= brake_target_v_ms + EPS,
    # ignorando le decisioni per-step. Eliminato il chatter brake/throttle
    # vicino alla velocità target (Monaco: 174 → ~12 transizioni).
    brake_target_v_ms: Optional[float] = None

    # V6.3: Tire thermal state (per-wheel independent)
    tires_state: Optional['TiresState'] = None

    # V6.3: Brake thermal state (front/rear)
    brake_state: Optional['BrakeState'] = None

    # V6.3: Telemetry fields for brake fade
    brake_fade_factor: float = 0.0  # Fade factor [0-1], 1=full fade
    brake_temp_front_c: float = 20.0  # Front brake temperature
    brake_temp_rear_c: float = 20.0  # Rear brake temperature

    # Telemetria
    telemetry_points: List[Dict] = None

    def __post_init__(self):
        if self.telemetry_points is None:
            self.telemetry_points = []
        if self.tires_state is None:
            # Import TiresState directly from module to avoid __init__ side effects
            from lap_simulator.physics_engine.tyres.tyre_thermal import TiresState as TiresStateClass
            self.tires_state = TiresStateClass()  # Initialize with default FL/FR/RL/RR
        if self.brake_state is None:
            from lap_simulator.physics_engine.tyres.tyre_thermal import BrakeState as BrakeStateClass
            self.brake_state = BrakeStateClass()  # Initialize with temp_front=20°C, temp_rear=20°C
