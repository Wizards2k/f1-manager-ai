"""Driver live feedback system for MVP.

Generates real-time driver messages based on:
- Setup characteristics (understeer/oversteer, stability)
- Circuit profile (corner types, braking zones)
- Driver style (ricerca_assetto affects frequency, stile_sottosterzo/sovrasterzo affects messages)
"""
from __future__ import annotations

import random
import time
from typing import Dict, Any, Optional, List

# Message templates by category
CORNERING_MESSAGES = {
    'understeer': [
        "Understeer in high-speed corners",
        "Front-end not biting",
        "Understeer on turn-in",
        "Front washes out mid-corner",
        "Need more front grip",
    ],
    'oversteer': [
        "Rear unstable mid-corner",
        "Oversteer on throttle",
        "Tail slides in traction zones",
        "Rear steps out",
        "Too much oversteer",
    ],
    'balanced': [
        "Good balance through corners",
        "Car rotates well",
        "Happy with cornering",
        "Neutral handling",
    ],
}

BRAKING_MESSAGES = {
    'front_lock': [
        "Front locks under heavy braking",
        "Nose dives under braking",
        "Front-end unstable braking",
        "Locking fronts into Turn 1",
    ],
    'rear_instability': [
        "Rear slides under braking",
        "Rear light on entry",
        "Unstable rear under braking",
        "Back end steps off",
    ],
    'good': [
        "Stable under braking",
        "Good brake balance",
        "Confident on brakes",
        "Braking feels good",
    ],
}

TRACTION_MESSAGES = {
    'wheelspin': [
        "Wheelspin on exits",
        "Can't put power down",
        "Traction issues out of slow corners",
        "Rear breaks away on throttle",
    ],
    'good': [
        "Strong traction out of corners",
        "Good drive out of slow corners",
        "Hooks up well",
        "Traction feels good",
    ],
}

SPEED_MESSAGES = {
    'too_much_drag': [
        "Too much drag on straights",
        "Car hits wall on straights",
        "Losing time on long straights",
    ],
    'good': [
        "Good top speed",
        "Strong on straights",
        "Good straight-line speed",
    ],
}


def calculate_setup_balance_scores(setup: Dict[str, int]) -> Dict[str, float]:
    """Calculate balance scores from setup values."""
    front_wing = setup.get('front_wing', 50)
    rear_wing = setup.get('rear_wing', 50)
    suspension_front = setup.get('suspension_front', 50)
    suspension_rear = setup.get('suspension_rear', 50)
    ride_rear = setup.get('ride_height_rear', 50)
    
    # Wing balance (positive = understeer tendency)
    wing_balance = front_wing - rear_wing
    
    # Suspension balance (positive = front stiffer)
    susp_balance = suspension_front - suspension_rear
    
    # Traction indicator (higher rear ride height = worse traction)
    traction_indicator = ride_rear - 50
    
    return {
        'wing_balance': wing_balance,
        'susp_balance': susp_balance,
        'traction_indicator': traction_indicator,
        'rear_wing': rear_wing,
    }


def get_driver_feedback(
    car,
    circuit_profile: Optional[Dict[str, Any]] = None,
    sector: Optional[str] = None,
) -> Optional[str]:
    """
    Generate driver feedback message based on car state and circuit.
    
    Args:
        car: RaceCar instance
        circuit_profile: Circuit configuration dict
        sector: Current sector being entered ('sector1', 'sector2', 'sector3')
    
    Returns:
        Message string or None if no feedback generated
    """
    if not car.is_player_controlled:
        return None
    
    pilot = car.pilot
    if not pilot:
        return None
    
    # Check cooldown
    current_time = time.time()
    if current_time - car.driver_feedback_timestamp < car.driver_feedback_cooldown:
        return None
    
    # Check ricerca_assetto - higher = more frequent feedback
    # Base probability: 20%, +1% per point of ricerca_assetto
    feedback_chance = 0.20 + (pilot.ricerca_assetto / 100.0) * 0.30
    if random.random() > feedback_chance:
        return None
    
    # Get setup values
    setup = car.player_config.get('setup', {})
    scores = calculate_setup_balance_scores(setup)
    
    # Get circuit characteristics
    surface = circuit_profile.get('surface', {}) if circuit_profile else {}
    corner_speed_mult = surface.get('corner_speed_multiplier', 1.0)
    braking_mult = surface.get('braking_multiplier', 1.0)
    
    # Determine context based on sector and circuit
    messages = []
    
    # Sector 1: Often has heavy braking zones (T1)
    if sector == 'sector1' or braking_mult < 0.98:
        # Check braking stability
        susp_balance = scores['susp_balance']
        if susp_balance > 12:
            messages.extend(BRAKING_MESSAGES['front_lock'])
        elif susp_balance < -12:
            messages.extend(BRAKING_MESSAGES['rear_instability'])
        elif susp_balance > 6:
            messages.extend(BRAKING_MESSAGES['front_lock'])
        elif susp_balance < -6:
            messages.extend(BRAKING_MESSAGES['rear_instability'])
        else:
            messages.extend(BRAKING_MESSAGES['good'])
    
    # Sector 2 & 3: Cornering and traction
    if sector in ('sector2', 'sector3') or corner_speed_mult < 1.0:
        wing_balance = scores['wing_balance']
        
        # Adjust for driver style
        understeer_tolerance = pilot.stile_sottosterzo / 100.0  # 0-1
        oversteer_tolerance = pilot.stile_sovrasterzo / 100.0   # 0-1
        
        # Understeer detection
        if wing_balance > 8:
            if understeer_tolerance < 0.6:  # Driver doesn't like understeer
                messages.extend(CORNERING_MESSAGES['understeer'])
        elif wing_balance > 4:
            if understeer_tolerance < 0.4:
                messages.extend(CORNERING_MESSAGES['understeer'])
        
        # Oversteer detection
        if wing_balance < -8:
            if oversteer_tolerance < 0.6:  # Driver doesn't like oversteer
                messages.extend(CORNERING_MESSAGES['oversteer'])
        elif wing_balance < -4:
            if oversteer_tolerance < 0.4:
                messages.extend(CORNERING_MESSAGES['oversteer'])
        
        # If no issues, add positive feedback
        if abs(wing_balance) <= 4:
            messages.extend(CORNERING_MESSAGES['balanced'])
        
        # Traction in slow corners
        traction_indicator = scores['traction_indicator']
        if traction_indicator > 10:
            messages.extend(TRACTION_MESSAGES['wheelspin'])
        elif traction_indicator > 5:
            if random.random() < 0.5:
                messages.extend(TRACTION_MESSAGES['wheelspin'])
        else:
            messages.extend(TRACTION_MESSAGES['good'])
    
    # Straight-line speed check (any sector)
    rear_wing = scores['rear_wing']
    drag_indicator = surface.get('aerodynamic_drag', 90)
    if rear_wing > 60 and drag_indicator > 85:
        messages.extend(SPEED_MESSAGES['too_much_drag'])
    elif rear_wing < 50 and drag_indicator > 85:
        messages.extend(SPEED_MESSAGES['good'])
    
    if not messages:
        return None
    
    # Select message (avoid repeats if possible)
    message = random.choice(messages)
    if message == car.last_driver_feedback and len(messages) > 1:
        # Try to pick different message
        alternatives = [m for m in messages if m != message]
        if alternatives:
            message = random.choice(alternatives)
    
    # Update car state
    car.last_driver_feedback = message
    car.driver_feedback_timestamp = current_time
    
    return message


def should_trigger_feedback(car, event_type: str) -> bool:
    """Check if driver should give feedback for a specific event."""
    if not car.is_player_controlled:
        return False
    
    pilot = car.pilot
    if not pilot:
        return False
    
    # Different events have different probabilities
    event_probabilities = {
        'sector_entry': 0.25,
        'braking_zone': 0.35,
        'corner_exit': 0.20,
        'straight': 0.15,
    }
    
    base_prob = event_probabilities.get(event_type, 0.20)
    ricerca_bonus = (pilot.ricerca_assetto / 100.0) * 0.25
    
    return random.random() < (base_prob + ricerca_bonus)
