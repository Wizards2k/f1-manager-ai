"""
Brake Penalty System - Step 5b extension

Computes brake penalties based on duct opening and brake fade.
Applied only on sections with significant braking energy.

Reference: docs/penalty-overhaul-spec.md Wave 2
"""
from __future__ import annotations

from typing import Dict, Optional

from .data_types import (
    BrakeState,
    CarState,
    CircuitConfig,
    SectionContext,
    clamp,
)


def get_brake_cv_for_team(team_code: str) -> float:
    """Get brake system performance coefficient for team (placeholder for future use)."""
    # Currently all teams use same brake systems - can be extended later
    return 1.0


def compute_brake_penalty(
    car_state: CarState,
    section: SectionContext,
    config: CircuitConfig,
) -> float:
    """
    Compute brake penalty for a car on a section.
    
    Applied only on sections with significant braking energy (>= 0.05 MJ).
    
    Parameters
    ----------
    car_state : CarState
        Car state with brake information
    section : SectionContext
        Current circuit section
    config : CircuitConfig
        Circuit configuration with brake parameters
        
    Returns
    -------
    float
        Brake penalty in seconds (0.0 if no penalty)
    """
    # Apply only on sections with significant braking
    if section.braking_energy_mj < 0.05:
        return 0.0
    
    brakes = car_state.brakes
    penalty_s = 0.0
    
    # 1. Brake Duct Penalty
    duct_penalty = _compute_duct_penalty(brakes, config)
    penalty_s += duct_penalty
    
    # 2. Brake Fade Penalty
    fade_penalty = _compute_fade_penalty(brakes, config, section)
    penalty_s += fade_penalty
    
    return penalty_s


def _compute_duct_penalty(brakes: BrakeState, config: CircuitConfig) -> float:
    """
    Compute penalty for incorrect duct opening.
    
    - Too closed: overheating risk (fade penalty)
    - Too open: aerodynamic drag penalty
    """
    profile = config.brake_profile or {}
    duct_recommendation = profile.get("duct_recommendation", {})
    
    # Get recommended range from circuit profile
    min_open = duct_recommendation.get("min_open", 0.225)
    max_open = duct_recommendation.get("max_open", 0.675)
    
    duct_opening = brakes.duct_opening
    
    # Base coefficients (reduced for realistic penalties)
    overcool_coeff = 0.2  # s per unit of over-cooling (was 0.8)
    overheat_coeff = 0.3  # s per unit of over-heating (was 1.2)
    
    penalty_s = 0.0
    
    if duct_opening < min_open:
        # Too closed → overheating risk
        delta = min_open - duct_opening
        penalty_s = delta * overheat_coeff
    elif duct_opening > max_open:
        # Too open → aerodynamic drag
        delta = duct_opening - max_open
        penalty_s = delta * overcool_coeff
    
    return penalty_s


def _compute_fade_penalty(brakes: BrakeState, config: CircuitConfig, section: SectionContext) -> float:
    """
    Compute penalty for brake fade based on temperature.
    
    Penalty increases with temperature above fade threshold.
    Critical sections have higher penalty multiplier.
    """
    params = config.brake_params
    if not params:
        return 0.0
    
    # Get fade thresholds
    front_threshold = params.fade_threshold_front_c
    rear_threshold = params.fade_threshold_rear_c
    fade_sensitivity = params.fade_sensitivity_c_per_unit
    
    # Current temperatures
    front_temp = brakes.temp_front_c
    rear_temp = brakes.temp_rear_c
    
    # Calculate fade levels
    front_fade = max(0.0, (front_temp - front_threshold) / fade_sensitivity)
    rear_fade = max(0.0, (rear_temp - rear_threshold) / fade_sensitivity)
    
    # Use worst axle
    fade_level = max(front_fade, rear_fade)
    
    if fade_level <= 0.0:
        return 0.0
    
    # Base fade penalty coefficient (reduced for realistic penalties)
    fade_coeff = 0.05  # s per fade unit (was 0.3)
    
    # Check if this is a critical section
    is_critical = False
    critical_sections = config.brake_critical_sections or []
    for cs in critical_sections:
        if cs.get("id") == section.section_id:
            is_critical = True
            break
    
    # Higher penalty on critical sections
    if is_critical:
        fade_coeff *= 1.5
    
    penalty_s = fade_level * fade_coeff
    
    return penalty_s


def validate_brake_coefficient(
    duct_coeff: float,
    fade_coeff: float,
    expected_duct_delta: float = 0.1,
    expected_fade_delta: float = 1.0,
    expected_duct_penalty_s: float = 0.08,
    expected_fade_penalty_s: float = 0.3,
) -> bool:
    """
    Validate brake penalty coefficients produce expected penalties.
    
    Parameters
    ----------
    duct_coeff : float
        Duct penalty coefficient
    fade_coeff : float
        Fade penalty coefficient
    expected_duct_delta : float
        Expected duct opening deviation
    expected_fade_delta : float
        Expected fade level
    expected_duct_penalty_s : float
        Expected penalty for duct deviation
    expected_fade_penalty_s : float
        Expected penalty for fade level
        
    Returns
    -------
    bool
        True if coefficients produce expected penalties
    """
    duct_tolerance = 0.01
    fade_tolerance = 0.05
    
    actual_duct_penalty = expected_duct_delta * duct_coeff
    actual_fade_penalty = expected_fade_delta * fade_coeff
    
    duct_ok = abs(actual_duct_penalty - expected_duct_penalty_s) <= duct_tolerance
    fade_ok = abs(actual_fade_penalty - expected_fade_penalty_s) <= fade_tolerance
    
    return duct_ok and fade_ok


def get_brake_penalty_summary(car_state: CarState, config: CircuitConfig) -> Dict[str, float]:
    """
    Get summary of brake penalty components for telemetry.
    
    Returns
    -------
    Dict[str, float]
        Summary with duct_penalty, fade_penalty, total_penalty
    """
    profile = config.brake_profile or {}
    duct_recommendation = profile.get("duct_recommendation", {})
    
    min_open = duct_recommendation.get("min_open", 0.225)
    max_open = duct_recommendation.get("max_open", 0.675)
    
    # Current duct penalty (using updated coefficients)
    duct_opening = car_state.brakes.duct_opening
    duct_penalty = 0.0
    if duct_opening < min_open:
        duct_penalty = (min_open - duct_opening) * 0.3  # Updated coefficient
    elif duct_opening > max_open:
        duct_penalty = (duct_opening - max_open) * 0.2  # Updated coefficient
    
    # Current fade penalty
    params = config.brake_params
    fade_penalty = 0.0
    if params:
        front_threshold = params.fade_threshold_front_c
        rear_threshold = params.fade_threshold_rear_c
        fade_sensitivity = params.fade_sensitivity_c_per_unit
        
        front_fade = max(0.0, (car_state.brakes.temp_front_c - front_threshold) / fade_sensitivity)
        rear_fade = max(0.0, (car_state.brakes.temp_rear_c - rear_threshold) / fade_sensitivity)
        fade_level = max(front_fade, rear_fade)
        
        if fade_level > 0.0:
            fade_penalty = fade_level * 0.05  # Updated coefficient
    
    return {
        "duct_penalty_s": duct_penalty,
        "fade_penalty_s": fade_penalty,
        "total_penalty_s": duct_penalty + fade_penalty,
    }
