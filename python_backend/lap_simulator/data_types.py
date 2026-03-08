"""
Core data types for the LapSimulator physics engine.

All structures are plain dataclasses (no ORM / Pydantic dependency)
so the module stays lightweight and testable in isolation.

Reference: docs/lap-physics-spec-v0.5.md §3.3 (Passi 1-8)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SectionKind(str, Enum):
    STRAIGHT = "Straight"
    MEDIUM_STRAIGHT = "MediumStraight"
    VERY_SLOW_CORNER = "VerySlowCorner"
    SLOW_CORNER = "SlowCorner"
    MEDIUM_CORNER = "MediumCorner"
    FAST_CORNER = "FastCorner"
    ULTRA_FAST_CORNER = "UltraFastCorner"


class TyreCompound(str, Enum):
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"
    C5 = "C5"
    C6 = "C6"
    INTERMEDIATE = "INTERMEDIATE"
    WET = "WET"


class WheelPosition(str, Enum):
    LF = "LF"
    RF = "RF"
    LR = "LR"
    RR = "RR"


class EngineMapName(str, Enum):
    SAFETY_CAR = "SAFETY_CAR"
    PRACTICE = "PRACTICE"
    RACE = "RACE"
    QUALIFY = "QUALIFY"


class ERSModeName(str, Enum):
    RECHARGE = "RECHARGE"
    STANDARD = "STANDARD"
    OVERTAKE = "OVERTAKE"
    QUALIFY = "QUALIFY"
    DEFENCE = "DEFENCE"
    DEPLOY = "DEPLOY"
    BALANCED = "BALANCED"
    HARVEST = "HARVEST"
    ATTACK = "ATTACK"
    SAFETY_CAR = "SAFETY_CAR"


# ---------------------------------------------------------------------------
# Section & Environment context  (Passo 1 – Input)
# ---------------------------------------------------------------------------

@dataclass
class CurveProfile:
    """Per-section curve geometry."""
    radius_m: Optional[float] = None
    banking_deg: float = 0.0
    curvature_factor: float = 0.0
    complex_corner: bool = False
    apex_ratio: float = 0.5


@dataclass
class Waypoint:
    """HD telemetry waypoint for micro-sector integration."""
    dist_m: float
    v_ref_kph: float
    elevation_m: float
    slope_deg: float
    radius_m: float
    camber_deg: float
    target_g_lat: float
    steering_angle_deg: float
    throttle_pct: int
    brake_pct: int
    drs_active: bool
    surface_type: str
    macro_sector_id: str
    section_kind: str

@dataclass
class SectionContext:
    """Static description of a circuit section (loaded from Telemetry JSON)."""
    section_id: str
    name: str
    kind: SectionKind
    length_m: float
    v_base_kph: float                    # reference avg speed from telemetry
    v_entry_kph: float = 0.0
    v_exit_kph: float = 0.0
    v_min_kph: float = 0.0
    v_max_kph: float = 0.0
    corner_number: int = 0
    curve_profile: CurveProfile = field(default_factory=CurveProfile)
    gradient_pct: float = 0.0            # pendenza media della sezione (positivo = salita)
    # track surface modifiers
    bumpiness_factor: float = 0.0        # 0-1, from pirelli profile
    kerb_severity: float = 0.0           # 0-1
    heat_factor: float = 1.0             # tyre heat generation multiplier
    cool_factor: float = 1.0             # tyre cooling multiplier
    braking_energy_mj: float = 0.0       # reference braking energy for section
    drs_available: bool = False
    dt_ref_s: float = 0.0                # reference time from telemetry integration
    telemetry_mu: float = 0.0            # derived mechanical grip (from HD telemetry)
    waypoints: List[Waypoint] = field(default_factory=list)  # HD waypoints for this section


@dataclass
class EnvContext:
    """Dynamic environment conditions for the current moment."""
    air_temp_c: float = 25.0
    track_temp_c: float = 35.0
    air_density_kg_m3: float = 1.225
    wind_speed_kph: float = 0.0
    wind_direction_deg: float = 0.0
    rain_intensity: float = 0.0          # 0 = dry, 1 = heavy rain
    track_rubber_level: float = 1.0      # 0.8 (green) → 1.2 (rubbered-in)
    water_film_level: float = 0.0        # for INT/WET


# ---------------------------------------------------------------------------
# Tyre state  (Passo 5)
# ---------------------------------------------------------------------------

@dataclass
class TyreCompoundParams:
    """Immutable parameters for a tyre compound (from config JSON)."""
    compound: TyreCompound
    temp_window_surface_c: List[float] = field(default_factory=lambda: [88, 120, 135])
    temp_window_core_c: List[float] = field(default_factory=lambda: [85, 97, 108])
    gaussian_sigma_surface_c: float = 7.0
    gaussian_sigma_core_c: float = 6.0
    base_grip: float = 1.0
    wear_rate_base_pct_per_km: float = 0.13
    degradation_rate_multiplier: float = 1.0   # C1=0.6, C3=1.0, C5=1.6 (spec §3)
    slip_sensitivity: float = 1.0              # C1=0.75, C3=1.0, C5=1.30 (spec §6)
    thermal_mass_surface: float = 1.10
    thermal_mass_core: float = 1.25
    conduction_coeff: float = 0.07
    cooling_coeff: float = 1.0
    heat_cycle_grip_penalty: float = 0.005     # grip loss per heat cycle (tyre-allocation §5)
    heat_cycle_warmup_penalty_s: float = 1.5   # extra warmup seconds per heat cycle
    heat_cycle_eol_threshold: int = 5          # end-of-life after N heat cycles
    graining_time_threshold_s: float = 8.0     # seconds below window before graining triggers
    blistering_time_threshold_s: float = 10.0  # seconds above window before blistering triggers

    @property
    def temp_opt_surface(self) -> float:
        return self.temp_window_surface_c[1]

    @property
    def temp_opt_core(self) -> float:
        return self.temp_window_core_c[1]


@dataclass
class TyreState:
    """Mutable state for a single tyre (per wheel)."""
    wheel_pos: WheelPosition
    compound: TyreCompound
    surface_temp_c: float = 80.0
    core_temp_c: float = 75.0
    wear_pct: float = 0.0
    lap_age: int = 0
    heat_cycles: int = 0                 # incremented each time set is reused
    graining_level: float = 0.0
    blistering_level: float = 0.0
    flatspot_severity: float = 0.0
    puncture_risk: float = 0.0
    overheat_warning: bool = False
    cold_warning: bool = False
    effective_grip: float = 1.0          # computed each section
    graining_time_acc_s: float = 0.0     # accumulated time below surface window
    blistering_time_acc_s: float = 0.0   # accumulated time above surface/core window


# ---------------------------------------------------------------------------
# Brake state  (Passo 5)
# ---------------------------------------------------------------------------

@dataclass
class BrakeSystemParams:
    """Immutable brake system parameters (from config JSON)."""
    heat_capacity_front: float = 1.10
    heat_capacity_rear: float = 1.00
    thermal_mass_front: float = 1.20
    thermal_mass_rear: float = 1.05
    fade_threshold_front_c: float = 850.0
    fade_threshold_rear_c: float = 750.0
    fade_sensitivity_c_per_unit: float = 15.0
    cooling_coeff: float = 1.0
    heat_quality: float = 1.0
    regen_brake_factor: float = 1.0


@dataclass
class BrakeState:
    """Mutable brake state (per car)."""
    temp_front_c: float = 400.0
    temp_rear_c: float = 350.0
    wear_front_pct: float = 0.0
    wear_rear_pct: float = 0.0
    fade_level: float = 0.0              # 0 = no fade, 1 = full fade
    duct_opening: float = 0.5            # 0-1 from setup
    bias_front_pct: float = 55.0         # brake balance
    snapshot: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Power Unit state  (Passo 4)
# ---------------------------------------------------------------------------

@dataclass
class EngineMapParams:
    """Parameters for a single engine map (from config JSON)."""
    name: EngineMapName
    power_pct_min: float = 0.75
    power_pct_max: float = 0.95
    power_pct_base: float = 0.85
    heat_load_kw: float = 260.0
    torque_ramp: float = 0.6
    deployment_style: str = "balanced"
    cooling_share: float = 0.50
    ers_output_kw: float = 120.0
    mguh_direct_ratio: float = 0.0
    mguh_power_kw: float = 0.0
    bucket_primary_pct: float = 0.5
    bucket_secondary_pct: float = 0.35
    bucket_exit_pct: float = 0.15
    defense_reserve_mj: float = 0.2


@dataclass
class PUReliabilityParams:
    """Reliability parameters for ICE/ERS (from config JSON)."""
    ice_wear_coeff: float = 0.0008
    ice_temp_warning_c: float = 130.0
    ice_temp_critical_c: float = 140.0
    ice_overrev_factor: float = 1.15
    ice_shock_factor: float = 1.10
    ers_wear_coeff: float = 0.0012
    ers_temp_warning_c: float = 90.0
    ers_temp_critical_c: float = 100.0
    ers_overrev_factor: float = 1.10
    ers_shock_factor: float = 1.05


@dataclass
class PUState:
    """Mutable power unit state (per car)."""
    active_map: EngineMapName = EngineMapName.RACE
    # ICE
    ice_temp_c: float = 95.0
    ice_wear_pct: float = 0.0
    ice_power_kw: float = 0.0            # computed each section
    ice_derating: bool = False
    # ERS
    ers_temp_c: float = 55.0
    ers_wear_pct: float = 0.0
    ers_energy_mj: float = 4.0           # battery SoC (max ~4 MJ)
    ers_output_kw: float = 0.0           # computed each section
    ers_derating: bool = False
    # Fuel
    fuel_kg: float = 100.0
    fuel_burn_rate_kg_per_s: float = 0.0  # computed each section
    # Per-lap energy tracking
    lap_deploy_mj: float = 0.0
    lap_harvest_mj: float = 0.0
    lap_mguh_direct_mj: float = 0.0
    lap_mguh_harvest_mj: float = 0.0
    energy_trace: List[Dict[str, Any]] = field(default_factory=list)
    runtime_warnings: List[str] = field(default_factory=list)
    lap_deploy_prev_mj: float = 0.0
    lap_harvest_prev_mj: float = 0.0
    lap_mguh_direct_prev_mj: float = 0.0
    lap_mguh_harvest_prev_mj: float = 0.0
    energy_trace_prev: List[Dict[str, Any]] = field(default_factory=list)
    runtime_warnings_prev: List[str] = field(default_factory=list)
    lap_id_current: int = 0
    lap_id_prev: int = 0
    # ERS map budget (per lap)
    bucket_primary_total_mj: float = 0.0
    bucket_secondary_total_mj: float = 0.0
    bucket_exit_total_mj: float = 0.0
    bucket_primary_used_mj: float = 0.0
    bucket_secondary_used_mj: float = 0.0
    bucket_exit_used_mj: float = 0.0
    defense_reserve_available_mj: float = 0.0
    deploy_budget_total_mj: float = 0.0
    mguh_primary_total_mj: float = 0.0
    mguh_secondary_total_mj: float = 0.0
    mguh_exit_total_mj: float = 0.0
    mguh_primary_used_mj: float = 0.0
    mguh_secondary_used_mj: float = 0.0
    mguh_exit_used_mj: float = 0.0
    bucket_budget_initialized: bool = False
    last_priority_score: float = 0.0
    last_bucket_key: str = "primary"
    last_bucket_allocated_mj: float = 0.0
    last_defense_used_mj: float = 0.0
    last_push_mode: bool = False
    last_defense_mode: bool = False
    last_recharge_mode: bool = False
    soc_floor_dynamic_pct: float = 0.5
    soc_target_pct: float = 0.55


# ---------------------------------------------------------------------------
# Aero state  (Passo 3)
# ---------------------------------------------------------------------------

@dataclass
class AeroComponent:
    """Single aero component (wing, floor, sidepod, etc.)."""
    name: str
    base_downforce: float = 0.0
    base_drag: float = 0.0
    angle_deg: float = 0.0
    angle_ref_deg: float = 15.0
    angle_sensitivity: float = 0.04
    drag_sensitivity: float = 0.02
    cooling_contribution: float = 0.0
    damage_factor: float = 1.0           # 1 = undamaged
    drs_drag_reduction: float = 0.0      # only rear wing


@dataclass
class SuspensionState:
    """Suspension parameters (per axis, from setup)."""
    rigidity: float = 0.6
    efficiency: float = 0.8
    df_bonus: float = 0.0


@dataclass
class AeroSetup:
    """Complete aero configuration for a car (from setup sliders → physics)."""
    front_wing: AeroComponent = field(default_factory=lambda: AeroComponent(name="front_wing"))
    rear_wing: AeroComponent = field(default_factory=lambda: AeroComponent(name="rear_wing"))
    beam_wing: AeroComponent = field(default_factory=lambda: AeroComponent(name="beam_wing"))
    front_floor: AeroComponent = field(default_factory=lambda: AeroComponent(name="front_floor"))
    rear_floor: AeroComponent = field(default_factory=lambda: AeroComponent(name="rear_floor"))
    sidepods: AeroComponent = field(default_factory=lambda: AeroComponent(name="sidepods"))
    engine_cover: AeroComponent = field(default_factory=lambda: AeroComponent(name="engine_cover"))
    b_wing: AeroComponent = field(default_factory=lambda: AeroComponent(name="b_wing"))

    suspension_front: SuspensionState = field(default_factory=SuspensionState)
    suspension_rear: SuspensionState = field(default_factory=SuspensionState)

    antiroll_front_rigidity: float = 0.5
    antiroll_rear_rigidity: float = 0.5

    ride_height_front_mm: float = 40.0
    ride_height_rear_mm: float = 50.0
    ride_height_optimal_front_mm: float = 40.0
    ride_height_optimal_rear_mm: float = 50.0


@dataclass
class AeroForces:
    """Output of AeroPackage.compute_forces() — consumed by later steps."""
    df_front_eff: float = 0.0
    df_rear_eff: float = 0.0
    df_total: float = 0.0
    drag_eff: float = 0.0
    aero_balance: float = 0.5            # df_front / df_total
    handling_penalty: float = 0.0
    understeer_level: float = 0.0
    oversteer_level: float = 0.0
    bump_penalty: float = 0.0
    kerb_impact: float = 0.0
    kerb_severity: float = 0.0
    cooling_capacity: float = 0.0
    cooling_margin: float = 0.0
    airflow_penalty: float = 0.0         # dirty air / wake
    drag_ref: float = 30.0               # reference drag for index normalization


# ---------------------------------------------------------------------------
# Driver model  (Passo 2)
# ---------------------------------------------------------------------------

@dataclass
class DriverSkills:
    """Static driver skill ratings (1-100)."""
    raw_pace: int = 70
    race_craft: int = 70
    aggression: int = 50
    consistency: int = 70
    tyre_management: int = 70
    overtaking_skill: int = 60
    defending_skill: int = 60
    wet_skill: int = 60
    smoothness: int = 60
    setup_finding: int = 60


@dataclass
class DriverMentalState:
    """Mutable driver mental state."""
    confidence: float = 0.5              # 0-1
    fatigue: float = 0.0                 # 0-1
    pressure: float = 0.0               # 0-1
    focus: float = 1.0                   # 0-1


@dataclass
class DriverIntent:
    """Output of DriverModel.compute_inputs() — commands for the section."""
    pace_factor: float = 1.0             # 0.8 (conserve) → 1.1 (push)
    push_level: int = 10                 # 1..10 (10 = zero penalty reference)
    aggression_curve_bonus: float = 0.0
    target_line: str = "optimal"         # optimal / defensive / aggressive
    brake_bias_adjust: float = 0.0       # delta from setup
    ers_deploy_request: bool = False
    ers_push_mode: bool = False
    ers_defense_mode: bool = False
    ers_recharge_mode: bool = False
    tyre_save_mode: bool = False
    fuel_save_mode: bool = False


# ---------------------------------------------------------------------------
# Damage state  (Passo 7)
# ---------------------------------------------------------------------------

@dataclass
class DamageCoeffs:
    """Immutable damage coefficients (from config JSON)."""
    # suspension
    susp_shock_threshold: float = 1.0
    susp_grip_drop_per_hit: float = 0.01
    susp_steering_loss_per_hit: float = 0.01
    susp_failure_risk_per_hit: float = 0.002
    # floor/beam
    floor_shock_threshold: float = 1.1
    floor_drag_increase_per_hit: float = 0.005
    floor_df_loss_per_hit: float = 0.006
    floor_failure_risk_per_hit: float = 0.0015
    # gearbox
    gearbox_shock_threshold: float = 0.95
    gearbox_shift_delay_per_hit: float = 0.004
    gearbox_failure_risk_per_hit: float = 0.003
    # steering
    steering_shock_threshold: float = 1.0
    steering_precision_loss_per_hit: float = 0.012
    steering_handling_penalty_per_hit: float = 0.01
    steering_failure_risk_per_hit: float = 0.001
    # scalers
    shock_scaler_bumpiness: float = 0.1
    shock_scaler_kerb_severity: float = 0.15
    recovery_rate_per_lap: float = 0.001


@dataclass
class DamageState:
    """Mutable mechanical damage state (per car)."""
    suspension_damage: float = 0.0       # 0-1
    floor_damage: float = 0.0
    gearbox_damage: float = 0.0
    steering_damage: float = 0.0
    # derived penalties (recomputed)
    grip_mech_drop: float = 0.0
    drag_increase: float = 0.0
    df_loss: float = 0.0
    shift_delay: float = 0.0
    steering_precision_loss: float = 0.0
    handling_penalty_damage: float = 0.0


# ---------------------------------------------------------------------------
# Composite car state  (full mutable state for one car)
# ---------------------------------------------------------------------------

@dataclass
class CarState:
    """Complete mutable state for a single car in the simulation."""
    car_id: str = "car_0"
    team_code: str = ""  # FIA team code for engine CV lookup
    # sub-states
    tyres: Dict[WheelPosition, TyreState] = field(default_factory=dict)
    brakes: BrakeState = field(default_factory=BrakeState)
    pu: PUState = field(default_factory=PUState)
    damage: DamageState = field(default_factory=DamageState)
    driver_mental: DriverMentalState = field(default_factory=DriverMentalState)
    aero_forces: AeroForces = field(default_factory=AeroForces)
    ers_mode: str = "STANDARD"           # RECHARGE / STANDARD / OVERTAKE / QUALIFY / DEFENCE
    # lap tracking
    current_section_idx: int = 0
    section_progress: float = 0.0        # 0-1 within current section
    lap_time_acc_s: float = 0.0
    lap_number: int = 1
    v_current_ms: float = 0.0  # current simulated speed
    telemetry_points_current_lap: List[Dict[str, Any]] = field(default_factory=list)
    # battle signals
    overtake_window: float = 0.0         # 0-1
    attack_cooldown: int = 0             # sections remaining
    defense_reset: int = 0
    side_by_side: bool = False

    def __post_init__(self):
        if not self.tyres:
            for wp in WheelPosition:
                self.tyres[wp] = TyreState(
                    wheel_pos=wp,
                    compound=TyreCompound.C3,
                )


# ---------------------------------------------------------------------------
# Section result  (Passo 8 – Return)
# ---------------------------------------------------------------------------

@dataclass
class SectionEvent:
    """A discrete event that occurred during a section."""
    event_type: str                      # e.g. "overheat", "brake_fade", "late_brake"
    severity: float = 0.0                # 0-1
    message: str = ""                    # human-readable for HUD/radio


@dataclass
class SectionResult:
    """Return value of Car.update_section()."""
    dt_s: float = 0.0                    # time spent in section
    v_exit_kph: float = 0.0              # exit speed
    v_entry_kph: float = 0.0             # entry speed at section start
    v_effective_kph: float = 0.0         # effective speed through section
    v_max_kph: float = 0.0               # peak speed reached during the section
    telemetry_points: List[Dict[str, Any]] = field(default_factory=list)
    events: List[SectionEvent] = field(default_factory=list)
    # signals for BattleResolver
    overtake_window: float = 0.0
    section_progress: float = 1.0
    braking_efficiency: float = 1.0
    late_brake_tag: bool = False
    # aero signals snapshot
    df_available: float = 0.0
    drag_eff: float = 0.0
    power_kw: float = 0.0
    effective_grip_front: float = 1.0
    effective_grip_rear: float = 1.0
    handling_penalty: float = 0.0
    fuel_penalty_s: float = 0.0          # fuel-weight contribution (per section)
    tyre_penalty_s: float = 0.0          # tyre compound/wear/temperature contribution (per section)
    engine_penalty_s: float = 0.0         # engine CV/map contribution (per section)
    brake_penalty_s: float = 0.0          # brake duct/fade contribution (per section)
    setup_penalty_s: float = 0.0          # setup DF/drag penalty contribution (per section)
    df_curve_penalty_s: float = 0.0       # DF curve penalty breakdown
    df_curve_bonus_s: float = 0.0         # DF curve bonus breakdown
    drag_penalty_s: float = 0.0           # drag penalty breakdown
    drag_bonus_s: float = 0.0             # drag bonus breakdown


# ---------------------------------------------------------------------------
# Config bundle  (loaded once per circuit)
# ---------------------------------------------------------------------------

@dataclass
class CircuitConfig:
    """All configuration needed to simulate a circuit."""
    circuit_id: str = ""
    circuit_name: str = ""
    circuit_length_m: float = 5000.0
    sections: List[SectionContext] = field(default_factory=list)
    sector_markers_m: List[float] = field(default_factory=list)
    # per-compound tyre params (keyed by TyreCompound)
    tyre_params: Dict[TyreCompound, TyreCompoundParams] = field(default_factory=dict)
    brake_params: BrakeSystemParams = field(default_factory=BrakeSystemParams)
    pu_maps: Dict[EngineMapName, EngineMapParams] = field(default_factory=dict)
    pu_reliability: PUReliabilityParams = field(default_factory=PUReliabilityParams)
    damage_coeffs: DamageCoeffs = field(default_factory=DamageCoeffs)
    brake_profile: Dict[str, Any] = field(default_factory=dict)
    brake_critical_sections: List[Dict[str, Any]] = field(default_factory=list)
    ers_budget: Dict[str, Any] = field(default_factory=dict)
    regen_profile: Dict[str, Any] = field(default_factory=dict)
    soc_warnings: List[str] = field(default_factory=list)
    # reference values for normalization
    df_ref: float = 70.0
    drag_ref: float = 30.0
    power_ref_kw: float = 450.0
    # global tuning coefficients
    k_df: float = 0.15
    k_drag: float = 0.10
    k_drag_curve: float = 0.05
    k_power: float = 0.12
    k_handling: float = 0.8
    v_min_kph: float = 50.0
    v_cap_kph: float = 370.0
    # dt_ref penalty model coefficients
    baseline_delta: float = 0.07         # +7% baseline, net ~+5.5% after grip bonus
    k_aero_penalty: float = 0.03         # max aero contribution to dt penalty
    k_grip_penalty: float = 0.02         # max grip contribution
    k_brake_penalty: float = 0.015        # max brake fade contribution
    k_fuel_penalty: float = 0.015         # max fuel weight contribution
    k_driver_penalty: float = 0.03       # max driver skill contribution
    fuel_max_kg: float = 110.0           # reference max fuel load
    fuel_reference_kg: float = 10.0      # baseline fuel for penalty model
    fuel_penalty_coeff: float = 0.0      # seconds per kg per lap
    # tyre penalty parameters
    tyre_reference_compound: str = "C3" 
    tyre_compound_deltas: Dict[str, float] = field(default_factory=dict)
    tyre_wear_coeffs: Dict[str, float] = field(default_factory=dict)
    n_curve_sections: int = 10  # Used to distribute per-lap tyre deltas onto corners
    tyre_temp_windows: Dict[str, Dict[str, List[float]]] = field(default_factory=dict)
    pirelli_nomination: Dict[str, str] = field(default_factory=dict)
    reference_lap_time_s: float = 0.0    # from telemetry (sum of dt_ref_s)
    # push penalty parameters
    push_penalty_centers: List[float] = field(default_factory=lambda: [1.60, 1.45, 1.30, 1.15, 1.00, 0.85, 0.70, 0.55, 0.40])
    push_penalty_base_width: float = 0.08  # Base half-width for L1
    push_penalty_width_decay: float = 0.008  # Width reduction per level
    # engine penalty parameters
    engine_reference_cv: float = 1008.0      # Mercedes reference CV
    engine_penalty_coeff: float = 0.00001   # 20 CV = 0.2s baseline
    engine_map_penalties: Dict[str, float] = field(default_factory=dict)  # penalties per engine map
    straight_sections: int = 4              # number of straight sections
    total_straight_length_m: float = 3200.0  # total straight length for scaling
    max_engine_bonus_ms: float = -1.5       # maximum bonus (negative penalty)
    max_engine_penalty_ms: float = 1.0       # maximum penalty
    setup_penalty_config: Optional[Any] = None  # SetupPenaltyConfig (lazy import to avoid circular deps)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def gaussian(temp: float, temp_opt: float, sigma: float) -> float:
    """Gaussian thermal factor centred on optimal temperature."""
    return math.exp(-((temp - temp_opt) ** 2) / (2 * sigma ** 2))


# Heat/cool factors per section kind (from TyreModel.md §6)
SECTION_HEAT_COOL: Dict[SectionKind, tuple] = {
    SectionKind.STRAIGHT:          (0.2, 1.2),
    SectionKind.MEDIUM_STRAIGHT:   (0.4, 1.0),
    SectionKind.VERY_SLOW_CORNER:  (1.5, 0.3),
    SectionKind.SLOW_CORNER:       (1.3, 0.4),
    SectionKind.MEDIUM_CORNER:     (1.0, 0.6),
    SectionKind.FAST_CORNER:       (0.8, 0.8),
    SectionKind.ULTRA_FAST_CORNER: (0.5, 1.0),
}

# Curve factor per section kind (from spec §5)
CURVE_FACTOR: Dict[SectionKind, float] = {
    SectionKind.STRAIGHT:          0.0,
    SectionKind.MEDIUM_STRAIGHT:   0.0,
    SectionKind.VERY_SLOW_CORNER:  0.3,
    SectionKind.SLOW_CORNER:       0.4,
    SectionKind.MEDIUM_CORNER:     0.7,
    SectionKind.FAST_CORNER:       1.0,
    SectionKind.ULTRA_FAST_CORNER: 1.0,
}

# Section kinds that are corners (for penalty model)
CORNER_KINDS = {
    SectionKind.VERY_SLOW_CORNER,
    SectionKind.SLOW_CORNER,
    SectionKind.MEDIUM_CORNER,
    SectionKind.FAST_CORNER,
    SectionKind.ULTRA_FAST_CORNER,
}
