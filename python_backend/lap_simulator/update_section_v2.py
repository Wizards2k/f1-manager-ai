"""
update_section_v2.py - Physics Engine Parallelo per Validazione LapSimulator v2

Questo modulo implementa una versione parallela di update_section che usa
fisica pura (senza baseline telemetry come target) per calcolare i tempi
microsettore.

Il motore v2 è completamente indipendente da v1 e viene usato SOLO per:
1. Confronto con v1 microsettore per microsettore
2. Validazione contro telemetria Q3
3. Verifica che setup diversi producano tempi diversi in modo fisicamente coerente

USO:
- update_section.py = motore v1 (produzione)
- update_section_v2.py = motore v2 (validazione parallela)
- scripts/compare_engines.py = confronto v1 vs v2

Reference: docs/lap-physics-spec-v0.5.md, docs/lap-physics-v2-analysis.md

FISICA V2 - PRINCIPI:
1. Assetto sbilanciato (sottosterzo/sovrasterzo) → perde tempo in curva
2. Ali alte → drag in rettilineo (v_max bassa), ma velocità migliore in curva
3. Ali basse → drag basso (v_max alta), ma meno grip in curva
4. Mescole gomme → incidono sul grip in curva e uscita
5. Sospensioni → fisica realistica per assetto
6. Altezza da terra → influisce su DF e grip
7. Bilanciamento frenate → spazi di frenata realistici
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from lap_simulator.data_types import (
    AeroSetup,
    CarState,
    CircuitConfig,
    EnvContext,
    MicrosectorConfig,
    SectionContext,
    SectionKind,
    SectionResult,
    TyreCompound,
    WheelPosition,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------   
# Physics Constants
# ---------------------------------------------------------------------------   

# Physical constants
GRAVITY = 9.81  # m/s^2
CAR_MASS_KG = 798.0  # F1 2025 minimum weight
DRAG_COEFFICIENT = 0.8  # C_d (approximate)
AIR_DENSITY = 1.225  # kg/m^3
FRONTAL_AREA = 1.6  # m^2 (approximate F1 car)

# Tyre grip factors per compound
TYRE_Grip_FACTOR = {
    "C1": 1.15,   # HyperSoft
    "C2": 1.10,   # Soft
    "C3": 1.00,   # Medium (reference)
    "C4": 0.95,   # Hard
    "C5": 0.90,   # SuperHard
    "C6": 0.85,   # UltraHard
    "INTERMEDIATE": 0.75,
    "WET": 0.65,
}

# Brake efficiency factors
BRAKE_EFFICIENCY = {
    "cold": 0.8,
    "optimal": 1.0,
    "hot": 0.9,
    "faded": 0.7,
}


# ---------------------------------------------------------------------------   
# Physics Calculations
# ---------------------------------------------------------------------------   

def calculate_braking_distance(
    initial_speed_ms: float,
    final_speed_ms: float,
    deceleration_ms2: float,
) -> float:
    """
    Calculate braking distance from initial to final speed
    
    s = (v1² - v2²) / (2 * a)
    """
    if deceleration_ms2 <= 0:
        return 0.0
    return (initial_speed_ms ** 2 - final_speed_ms ** 2) / (2 * deceleration_ms2)


def calculate_max_speed(
    power_w: float,
    drag_coefficient: float = DRAG_COEFFICIENT,
    frontal_area: float = FRONTAL_AREA,
    air_density: float = AIR_DENSITY,
) -> float:
    """
    Calculate max speed from power and drag
    
    P = 0.5 * C_d * A * rho * v³
    v = (P / (0.5 * C_d * A * rho))^(1/3)
    """
    if power_w <= 0:
        return 0.0
    return (power_w / (0.5 * drag_coefficient * frontal_area * air_density)) ** (1/3)


def calculate_acceleration(
    power_w: float,
    speed_ms: float,
    mass_kg: float,
    efficiency: float = 0.85,
) -> float:
    """
    Calculate acceleration from power and speed
    
    P = F * v
    F = m * a
    a = P / (v * m)
    """
    if speed_ms <= 0:
        return 10.0  # Max acceleration at standstill
    return (power_w * efficiency) / (speed_ms * mass_kg)


def calculate_lateral_g_force(
    speed_ms: float,
    corner_radius_m: float,
) -> float:
    """
    Calculate lateral g-force in a corner
    
    g_lat = v² / (r * g)
    """
    if corner_radius_m <= 0:
        return 0.0
    return (speed_ms ** 2) / (corner_radius_m * GRAVITY)


def calculate_aero_forces(
    aero_setup: AeroSetup,
    speed_ms: float,
    env_context: EnvContext,
) -> Tuple[float, float, float, float]:
    """
    Calculate aero forces from setup
    
    Returns: (df_front, df_rear, drag_total, aero_balance)
    """
    # Dynamic pressure
    dyn_pressure = 0.5 * env_context.air_density_kg_m3 * (speed_ms ** 2)
    
    # Front wing
    df_front = aero_setup.front_wing.base_downforce * dyn_pressure * aero_setup.front_wing.angle_sensitivity
    drag_front = aero_setup.front_wing.base_drag * dyn_pressure * aero_setup.front_wing.drag_sensitivity
    
    # Rear wing
    df_rear = aero_setup.rear_wing.base_downforce * dyn_pressure * aero_setup.rear_wing.angle_sensitivity
    drag_rear = aero_setup.rear_wing.base_drag * dyn_pressure * aero_setup.rear_wing.drag_sensitivity
    
    # Sidepods (50% to front, 50% to rear)
    df_sidepods = aero_setup.sidepods.base_downforce * dyn_pressure * 0.5
    drag_sidepods = aero_setup.sidepods.base_drag * dyn_pressure
    
    # Total
    df_total = df_front + df_rear + df_sidepods
    drag_total = drag_front + drag_rear + drag_sidepods
    
    # Aero balance (target 0.50)
    aero_balance = df_front / df_total if df_total > 0 else 0.5
    
    return df_front, df_rear, drag_total, aero_balance


def calculate_tyre_grip(
    tyre_compound: TyreCompound,
    tyre_state: Any,
    aero_balance: float,
    balance_error: float,
) -> float:
    """
    Calculate effective tyre grip based on compound, temperature, and balance
    
    grip = base_grip * thermal_factor * wear_factor * balance_factor
    """
    # Base grip from compound
    base_grip = TYRE_Grip_FACTOR.get(tyre_compound.name, 1.0)
    
    # Thermal factor (gaussian around optimal temp)
    temp_opt = 100.0  # Optimal tyre temp
    temp_actual = tyre_state.surface_temp_c if hasattr(tyre_state, 'surface_temp_c') else 100.0
    thermal_factor = math.exp(-((temp_actual - temp_opt) ** 2) / (2 * 7 ** 2))
    
    # Wear factor
    wear_pct = tyre_state.wear_pct if hasattr(tyre_state, 'wear_pct') else 0.0
    wear_factor = max(0.5, 1 - wear_pct / 100)
    
    # Balance factor (suspension/ride height effect)
    balance_factor = 1.0 - abs(balance_error) * 0.3
    
    return base_grip * thermal_factor * wear_factor * balance_factor


def calculate_brake_deceleration(
    brake_state: Any,
    aero_balance: float,
    balance_error: float,
) -> float:
    """
    Calculate brake deceleration based on brake state and balance
    
    Deceleration depends on:
    - Brake temperature (fade at high temps)
    - Brake balance (front/rear distribution)
    - Handling penalty (balance error)
    """
    # Base deceleration
    base_deceleration = 12.0  # m/s² (typical F1 braking)
    
    # Temperature factor
    temp_front = brake_state.temp_front_c if hasattr(brake_state, 'temp_front_c') else 400.0
    temp_rear = brake_state.temp_rear_c if hasattr(brake_state, 'temp_rear_c') else 350.0
    
    fade_front = 1.0
    fade_rear = 1.0
    
    if temp_front > 850:
        fade_front = max(0.7, 1.0 - (temp_front - 850) / 200)
    if temp_rear > 750:
        fade_rear = max(0.7, 1.0 - (temp_rear - 750) / 150)
    
    # Balance factor
    bias_front = brake_state.bias_front_pct if hasattr(brake_state, 'bias_front_pct') else 55.0
    balance_factor = 1.0 - abs(balance_error) * 0.2
    
    return base_deceleration * fade_front * fade_rear * balance_factor


def calculate_handling_penalty(
    aero_balance: float,
    target_balance: float = 0.50,
    driver_skills: Any = None,
) -> Tuple[float, float]:
    """
    Calculate handling penalty from aero balance error
    
    Penalty increases with balance error:
    - Sottosterzo (aero_balance > 0.50) → penalità ingresso curva
    - Sovrasterzo (aero_balance < 0.50) → penalità uscita curva
    """
    balance_error = aero_balance - target_balance
    
    # Base penalty
    penalty = abs(balance_error) * 0.30
    
    # Driver compensation (skill can reduce penalty)
    if driver_skills:
        if balance_error > 0:  # Sottosterzo
            driver_comp = driver_skills.understeer_preference / 100 if hasattr(driver_skills, 'understeer_preference') else 0.5
        else:  # Sovrasterzo
            driver_comp = driver_skills.oversteer_preference / 100 if hasattr(driver_skills, 'oversteer_preference') else 0.5
        penalty *= (1 - 0.5 * driver_comp)
    
    return penalty, balance_error


def calculate_curve_speed(
    v_base_kph: float,
    df_front: float,
    df_rear: float,
    drag_total: float,
    corner_radius_m: float,
    handling_penalty: float,
    balance_error: float,
    circuit_config: CircuitConfig,
) -> float:
    """
    Calculate speed through a curve based on DF, drag, and grip
    
    v_curve = v_base * (1 + k_df * ΔDF/DF_ref) * (1 - handling_penalty) * (1 - k_drag_curve * Δdrag/drag_ref)
    """
    df_ref = circuit_config.df_ref if hasattr(circuit_config, 'df_ref') else 70.0
    drag_ref = circuit_config.drag_ref if hasattr(circuit_config, 'drag_ref') else 30.0
    k_df = circuit_config.k_df if hasattr(circuit_config, 'k_df') else 0.15
    k_drag_curve = circuit_config.k_drag_curve if hasattr(circuit_config, 'k_drag_curve') else 0.05
    
    # Downforce effect (higher DF = higher speed in corners)
    df_eff = df_front if balance_error > 0 else df_rear  # Use limiting axis
    df_delta = (df_eff - df_ref) / df_ref
    df_bonus = k_df * df_delta
    
    # Drag effect in corners
    drag_delta = (drag_total - drag_ref) / drag_ref
    drag_penalty = k_drag_curve * drag_delta
    
    # Final speed
    v_curve_factor = 1 + df_bonus - handling_penalty - drag_penalty
    v_curve_kph = v_base_kph * max(0.5, v_curve_factor)
    
    return v_curve_kph


def calculate_straight_speed(
    v_base_kph: float,
    power_kw: float,
    drag_total: float,
    circuit_config: CircuitConfig,
) -> float:
    """
    Calculate speed on straight based on power and drag
    
    v_straight = v_base + Δpower - k_drag * Δdrag
    """
    power_ref = circuit_config.power_ref_kw if hasattr(circuit_config, 'power_ref_kw') else 450.0
    drag_ref = circuit_config.drag_ref if hasattr(circuit_config, 'drag_ref') else 30.0
    k_power = circuit_config.k_power if hasattr(circuit_config, 'k_power') else 0.12
    k_drag = circuit_config.k_drag if hasattr(circuit_config, 'k_drag') else 0.10
    
    # Power effect
    power_delta = (power_kw - power_ref) / power_ref
    power_bonus = k_power * power_delta * 100  # Convert to kph
    
    # Drag effect
    drag_delta = (drag_total - drag_ref) / drag_ref
    drag_penalty = k_drag * drag_delta * 100
    
    # Final speed
    v_straight_kph = v_base_kph + power_bonus - drag_penalty
    
    return v_straight_kph


def calculate_braking_zone(
    v_entry_kph: float,
    v_apex_kph: float,
    brake_deceleration_ms2: float,
    curve_radius_m: float,
) -> Tuple[float, float]:
    """
    Calculate braking zone: distance and point
    
    Returns: (braking_distance_m, braking_start_m)
    """
    v_entry_ms = v_entry_kph / 3.6
    v_apex_ms = v_apex_kph / 3.6
    
    # Braking distance
    braking_distance = calculate_braking_distance(v_entry_ms, v_apex_ms, brake_deceleration_ms2)
    
    return braking_distance, braking_distance


# ---------------------------------------------------------------------------   
# Update Section V2 - Main Physics Loop
# ---------------------------------------------------------------------------   

def update_section_v2(
    section_context: SectionContext,
    initial_state: CarState,
    aero_setup: AeroSetup,
    tyre_compound: TyreCompound,
    env_context: EnvContext,
    circuit_config: CircuitConfig,
    driver_skills: Any = None,
    push_level: int = 10,
) -> Tuple[SectionResult, CarState]:
    """
    Update section with v2 physics engine (pure physics, no baseline telemetry)
    
    FISICA V2 - PRINCIPI:
    1. Assetto sbilanciato (sottosterzo/sovrasterzo) → perde tempo in curva
    2. Ali alte → drag in rettilineo (v_max bassa), ma velocità migliore in curva
    3. Ali basse → drag basso (v_max alta), ma meno grip in curva
    4. Mescole gomme → incidono sul grip in curva e uscita
    5. Sospensioni → fisica realistica per assetto
    6. Altezza da terra → influisce su DF e grip
    7. Bilanciamento frenate → spazi di frenata realistici
    
    Args:
        section_context: Microsector configuration
        initial_state: Starting state
        aero_setup: Aero setup
        tyre_compound: Tyre compound
        env_context: Environment context
        circuit_config: Circuit configuration
        driver_skills: Driver skill ratings
        push_level: Driver push command (1..10)
        
    Returns:
        Tuple of (section_result, final_state)
    """
    logger.debug(f"update_section_v2: section={section_context.section_id}, "
                 f"speed={initial_state.v_current_ms * 3.6:.1f} kph")
    
    # ===================================================================
    # STEP 1 – Input & initial state
    # ===================================================================
    v_entry_kph = initial_state.v_current_ms * 3.6
    v_entry_ms = v_entry_kph / 3.6
    
    # ===================================================================
    # STEP 2 – Calculate aero forces
    # ===================================================================
    df_front, df_rear, drag_total, aero_balance = calculate_aero_forces(
        aero_setup, initial_state.v_current_ms, env_context
    )
    
    # ===================================================================
    # STEP 3 – Calculate handling penalty and balance error
    # ===================================================================
    handling_penalty, balance_error = calculate_handling_penalty(
        aero_balance, target_balance=0.50, driver_skills=driver_skills
    )
    
    # ===================================================================
    # STEP 4 – Calculate brake deceleration
    # ===================================================================
    brake_deceleration = calculate_brake_deceleration(
        initial_state.brakes, aero_balance, balance_error
    )
    
    # ===================================================================
    # STEP 5 – Calculate tyre grip
    # ===================================================================
    # Get front and rear tyre grip
    tyre_front = initial_state.tyres.get(WheelPosition.LF, initial_state.tyres.get(WheelPosition.RF))
    tyre_rear = initial_state.tyres.get(WheelPosition.LR, initial_state.tyres.get(WheelPosition.RR))
    
    grip_front = calculate_tyre_grip(tyre_compound, tyre_front, aero_balance, balance_error)
    grip_rear = calculate_tyre_grip(tyre_compound, tyre_rear, aero_balance, balance_error)
    
    # ===================================================================
    # STEP 6 – Calculate speeds based on section type
    # ===================================================================
    v_base_kph = section_context.v_base_kph
    curve_radius = section_context.curve_profile.radius_m
    
    if section_context.kind in [SectionKind.STRAIGHT, SectionKind.MEDIUM_STRAIGHT]:
        # ===================================================================
        # STRAIGHT: Power vs Drag
        # ===================================================================
        # Calculate power (placeholder - use circuit_config.power_ref_kw)
        power_kw = circuit_config.power_ref_kw if hasattr(circuit_config, 'power_ref_kw') else 450.0
        
        # Apply push level
        push_factor = 1 + (push_level - 5) * 0.02  # ±10% from push 5
        power_kw *= push_factor
        
        # Calculate straight speed
        v_straight_kph = calculate_straight_speed(v_base_kph, power_kw, drag_total, circuit_config)
        
        # Apply drag penalty from high DF
        drag_penalty_factor = 1 - abs(balance_error) * 0.1
        v_straight_kph *= drag_penalty_factor
        
        v_eff_kph = v_straight_kph
        
    else:
        # ===================================================================
        # CORNER: DF vs Grip vs Handling
        # ===================================================================
        # Calculate curve speed
        v_curve_kph = calculate_curve_speed(
            v_base_kph, df_front, df_rear, drag_total, curve_radius,
            handling_penalty, balance_error, circuit_config
        )
        
        # Apply grip limit
        grip_axis = grip_front if balance_error > 0 else grip_rear
        v_grip_limited = v_curve_kph * grip_axis
        
        # Apply handling penalty
        v_eff_kph = v_grip_limited * (1 - handling_penalty * 0.5)
    
    # ===================================================================
    # STEP 7 – Calculate dt and update state
    # ===================================================================
    v_eff_ms = v_eff_kph / 3.6
    dt_s = section_context.length_m / max(v_eff_ms, 1.0)
    
    # ===================================================================
    # STEP 8 – Update car state
    # ===================================================================
    final_state = CarState()
    final_state.v_current_ms = v_eff_ms
    final_state.lap_time_acc_s = initial_state.lap_time_acc_s + dt_s
    final_state.section_progress = 1.0
    
    # ===================================================================
    # STEP 9 – Return result
    # ===================================================================
    section_result = SectionResult(
        dt_s=dt_s,
        v_entry_kph=v_entry_kph,
        v_exit_kph=v_eff_kph,
        v_effective_kph=v_eff_kph,
        v_max_kph=v_eff_kph,
        events=[],
        overtake_window=0.0,
        section_progress=1.0,
        braking_efficiency=1.0,
        late_brake_tag=False,
        df_available=df_front if balance_error > 0 else df_rear,
        drag_eff=drag_total,
        power_kw=circuit_config.power_ref_kw if hasattr(circuit_config, 'power_ref_kw') else 450.0,
        effective_grip_front=grip_front,
        effective_grip_rear=grip_rear,
        handling_penalty=handling_penalty,
        df_curve_penalty_s=0.0,
        df_curve_bonus_s=0.0,
        drag_penalty_s=0.0,
        drag_bonus_s=0.0,
        ers_bonus_s=0.0,
    )
    
    return section_result, final_state


# ---------------------------------------------------------------------------   
# Helper Functions
# ---------------------------------------------------------------------------   

def get_brake_deceleration(
    brake_pressure: float,
    brake_temperature: float,
    weight_transfer: float,
) -> float:
    """
    Calculate brake deceleration based on pressure, temperature, and weight transfer
    """
    base_deceleration = 12.0  # m/s^2 (typical F1 braking)
    
    # Temperature factor
    temp_factor = BRAKE_EFFICIENCY["optimal"]
    if brake_temperature < 500:
        temp_factor = BRAKE_EFFICIENCY["cold"]
    elif brake_temperature > 1000:
        temp_factor = BRAKE_EFFICIENCY["hot"]
    if brake_temperature > 1200:
        temp_factor = BRAKE_EFFICIENCY["faded"]
    
    # Pressure factor
    pressure_factor = min(brake_pressure / 100.0, 1.0)
    
    # Weight transfer factor
    weight_factor = 1.0 + (weight_transfer * 0.1)
    
    return base_deceleration * temp_factor * pressure_factor * weight_factor


def get_tyre_grip(
    tyre_compound: TyreCompound,
    tyre_temperature: float,
    load: float,
) -> float:
    """
    Calculate tyre grip based on compound, temperature, and load
    """
    base_grip = TYRE_Grip_FACTOR.get(tyre_compound.name, 1.0)
    
    # Temperature factor (optimal ~100°C)
    temp_factor = 1.0
    if tyre_temperature < 80:
        temp_factor = 0.8
    elif tyre_temperature > 120:
        temp_factor = 0.9
    
    # Load factor (downforce increases with speed)
    load_factor = 1.0 + (load * 0.01)
    
    return base_grip * temp_factor * load_factor
