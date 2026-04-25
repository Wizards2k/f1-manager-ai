"""
Physics Engine V6.4 - Newtonian Physics Simulator for F1 2025

Motore fisico completamente indipendente da V1/V2/V3.
Simula le forze fisiche reali (Newton, kg, m/s²) senza penalty empiriche.

Il tempo sul giro EMERGE dalla simulazione fisica, non è un riferimento + aggiustamenti.
"""

__version__ = "6.4.0"
__author__ = "F1 Manager AI Development Team"

# Core modules
from .core.constants import (
    # Costanti universali
    G,
    RHO_SEA_LEVEL,
    
    # F1 2025 Regolamento
    MASS_DRY_KG,
    MASS_DRIVER_KG,
    FUEL_RACE_START_KG,
    FUEL_QUALY_KG,
    
    # Power Unit
    ICE_PEAK_POWER_KW,
    ERS_PEAK_POWER_KW,
    PU_TOTAL_PEAK_KW,
    DRIVETRAIN_EFFICIENCY,
    ROLLING_RESISTANCE_COEFF,
    
    # Aerodinamica
    CLA_MIN,
    CLA_MAX,
    CLA_NEUTRAL,
    CDA_MIN,
    CDA_MAX,
    CDA_NEUTRAL,
    DRS_DRAG_REDUCTION_FACTOR,
    
    # Gomme
    MU_BASE,
    GRIP_CORNERING_EFFICIENCY,
    KAPPA_LOAD,
    
    # Geometria Auto
    H_CG,
    WHEELBASE,
    TRACK_WIDTH,
    WEIGHT_DIST_FRONT,
)

# Team & Driver Data
from .core.team_driver_data import (
    TeamDriverLoader,
    TeamData,
    DriverSkill,
    TeamAeroParams,
    get_team_data,
    get_driver_data,
)

# Car Setup
from .core.car_setup import (
    PhysicsV6Setup,
    PhysicsV4Setup,  # Backward-compatible alias for PhysicsV6Setup
    CarSetup,
    AeroSetup,
    SuspensionSetup,
    PowerUnitSetup,
    TyreSetup,
    BrakeSetup,
    FuelSetup,
)

# Aero modules
from .aero.aero_assembly import AeroAssembly, AeroForces
from .aero.front_wing import FrontWing
from .aero.rear_wing import RearWing
from .aero.floor_front import FloorFront
from .aero.floor_rear import FloorRear
from .aero.sidepods import Sidepods
from .aero.engine_cover import EngineCover
from .aero.bwing import BWing

# Mass modules
from .mass.mass_distribution import MassDistribution, MassState
from .mass.center_of_gravity import CenterOfGravity, CGPosition
from .mass.inertia import MomentOfInertia, InertiaTensor

# Suspension modules
from .suspension.spring_damper import SpringDamper, SpringForce
from .suspension.antiroll import AntiRollBar, AntiRollForce
from .suspension.ride_height import RideHeight, RideHeightState

# Tyres
from .tyres.tyre_construction import TyreConstruction, TyreCompoundParams, TyreState
from .tyres.tyre_thermal import TyreThermal, TyreThermalState
from .tyres.tyre_wear import TyreWear, TyreWearState
from .tyres.grip_model import TyreGripModel, GripState

# Brakes
from .brakes.brake_material import BrakeMaterial
from .brakes.brake_cooling import BrakeCooling
from .brakes.brake_bias import BrakeBias
from .brakes.brake_wear import BrakeWear

# Vehicle
from .vehicle.load_transfer import LoadTransfer, LoadTransferState
from .vehicle.kamm_circle import KammCircle, FrictionCircle
from .vehicle.handling import HandlingModel, HandlingState
from .vehicle.balance import VehicleBalance, BalanceState
from .vehicle.cornering_limit import CorneringLimitCalculator, CorneringLimitResult

# Driver
from .driver.driving_line import DrivingLine, DrivingLineState
from .driver.braking_point import BrakingPoint, BrakingPointState
from .driver.throttle_curve import ThrottleCurve, ThrottleCurveState
from .driver.steering_input import SteeringInput, SteeringInputState

# Setup
from .setup.slider_to_physics import SliderToPhysics
from .setup.default_setups import DefaultSetups
from .setup.optimizer import SetupOptimizer

# Integrator
from .integrator.waypoint_integrator import integrate_lap_hd

# Calibration helpers
from .calibration.reference_calibration import (
    DEFAULT_CALIBRATION_CIRCUIT_ID,
    DEFAULT_CALIBRATION_DRIVER_NAME,
    DEFAULT_CALIBRATION_SESSION,
    DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT,
    DEFAULT_CALIBRATION_TEAM_NAME,
    DEFAULT_CALIBRATION_TYRE_COMPOUND,
    DEFAULT_CALIBRATION_WEATHER,
    InitialCalibrationSetup,
    InitialCalibrationSpec,
    build_initial_calibration_setup,
    run_initial_calibration_benchmark,
)

# API pubblica
__all__ = [
    # Versione
    "__version__",
    "__author__",
    
    # Core
    'G', 'RHO_SEA_LEVEL',
    'MASS_DRY_KG', 'MASS_DRIVER_KG', 'FUEL_RACE_START_KG', 'FUEL_QUALY_KG',
    'ICE_PEAK_POWER_KW', 'ERS_PEAK_POWER_KW', 'PU_TOTAL_PEAK_KW',
    'CLA_MIN', 'CLA_MAX', 'CDA_MIN', 'CDA_MAX',
    'MU_BASE', 'WHEELBASE', 'TRACK_WIDTH',
    
    # Aero
    'AeroAssembly', 'AeroForces',
    'FrontWing', 'RearWing',
    'FloorFront', 'FloorRear',
    'Sidepods', 'EngineCover', 'BWing',
    
    # Mass
    'MassDistribution', 'MassState',
    'CenterOfGravity', 'CGPosition',
    'MomentOfInertia', 'InertiaTensor',
    
    # Suspension
    'SpringDamper', 'SpringForce',
    'AntiRollBar', 'AntiRollForce',
    'RideHeight', 'RideHeightState',
    
    # Tyres
    'TyreConstruction', 'TyreCompoundParams', 'TyreState',
    'TyreThermal', 'TyreThermalState',
    'TyreWear', 'TyreWearState',
    'TyreGripModel', 'GripState',
    
    # Brakes
    'BrakeMaterial', 'BrakeCooling', 'BrakeBias', 'BrakeWear',
    
    # Vehicle
    'LoadTransfer', 'LoadTransferState',
    'KammCircle', 'FrictionCircle',
    'HandlingModel', 'HandlingState',
    'VehicleBalance', 'BalanceState',
    'CorneringLimitCalculator', 'CorneringLimitResult',
    
    # Driver
    'DrivingLine', 'DrivingLineState',
    'BrakingPoint', 'BrakingPointState',
    'ThrottleCurve', 'ThrottleCurveState',
    'SteeringInput', 'SteeringInputState',
    
    # Setup
    'SliderToPhysics',
    'DefaultSetups',
    'SetupOptimizer',
    
    # Integrator
    'integrate_lap_hd',

    # Calibration helpers
    'DEFAULT_CALIBRATION_CIRCUIT_ID',
    'DEFAULT_CALIBRATION_TEAM_NAME',
    'DEFAULT_CALIBRATION_DRIVER_NAME',
    'DEFAULT_CALIBRATION_SESSION',
    'DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT',
    'DEFAULT_CALIBRATION_WEATHER',
    'DEFAULT_CALIBRATION_TYRE_COMPOUND',
    'InitialCalibrationSpec',
    'InitialCalibrationSetup',
    'build_initial_calibration_setup',
    'run_initial_calibration_benchmark',
]
