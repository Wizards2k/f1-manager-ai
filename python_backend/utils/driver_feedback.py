"""Driver live feedback system for MVP.

Generates real-time driver messages based on:
- Setup characteristics (understeer/oversteer, stability)
- Circuit profile (corner types, braking zones)
- Driver style (ricerca_assetto affects max feedback/giro, cooldown, quality)

Feedback limits by ricerca_assetto rating:
- 0-40: No feedback (driver too inexperienced)
- 41-60: Max 1/giro, 20s cooldown, vague quality
- 61-75: Max 2/giro, 15s cooldown, zone-specific
- 76-90: Max 2/giro, 12s cooldown, problem-specific
- 91-100: Max 3/giro, 10s cooldown, detailed + suggestion
"""
from __future__ import annotations

import random
import time
from typing import Dict, Any, Optional, List, Tuple

from models.models import CarState

# Feedback configuration by ricerca_assetto rating
FEEDBACK_CONFIG: Dict[str, Dict[str, Any]] = {
    'none': {
        'min_rating': 0,
        'max_rating': 40,
        'max_per_lap': 0,
        'cooldown': 0,
        'quality': 'none',
    },
    'poor': {
        'min_rating': 41,
        'max_rating': 60,
        'max_per_lap': 1,
        'cooldown': 20,
        'quality': 'vague',
    },
    'good': {
        'min_rating': 61,
        'max_rating': 75,
        'max_per_lap': 2,
        'cooldown': 15,
        'quality': 'zone_specific',
    },
    'very_good': {
        'min_rating': 76,
        'max_rating': 90,
        'max_per_lap': 2,
        'cooldown': 12,
        'quality': 'problem_specific',
    },
    'excellent': {
        'min_rating': 91,
        'max_rating': 100,
        'max_per_lap': 3,
        'cooldown': 10,
        'quality': 'detailed',
    },
}


def get_feedback_config(ricerca_assetto: int) -> Tuple[str, Dict[str, Any]]:
    """Get feedback configuration based on driver rating."""
    for level, config in FEEDBACK_CONFIG.items():
        if config['min_rating'] <= ricerca_assetto <= config['max_rating']:
            return level, config
    return 'none', FEEDBACK_CONFIG['none']


# Message templates by category and quality level
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

# Vague messages for poor drivers (quality: 'poor')
VAGUE_MESSAGES = [
    "Car feels unbalanced",
    "Something feels off",
    "Not happy with the handling",
    "Car could be better",
]

# Thermal alerts for tyres and brakes
THERMAL_MESSAGES = {
    'tyre_overheat': [
        "Tyre temps are spiking, need to cool them down",
        "Losing grip from tyre overheating",
        "Tyres are cooking, pace will drop",
    ],
    'tyre_blistering': [
        "Blistering on the tyres, grip falling off",
        "Tyres are blistering badly",
    ],
    'brake_hot_section': [
        "Brakes are too hot through that section",
        "Brake temps are climbing, need more cooling",
    ],
    'brake_fade': [
        "Brakes are fading from temperature",
        "Struggling to slow the car, brakes are cooked",
    ],
    'brake_critical': [
        "Brake temps critical, need to back off",
        "Brakes on the limit, can't keep this up",
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
    
    Feedback limits by ricerca_assetto:
    - 0-40: No feedback
    - 41-60: Max 1/giro, 20s cooldown, vague messages
    - 61-75: Max 2/giro, 15s cooldown, zone-specific
    - 76-90: Max 2/giro, 12s cooldown, problem-specific  
    - 91-100: Max 3/giro, 10s cooldown, detailed
    
    Max 1 feedback per zone per lap.
    
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

    # Require car to be in a Hot Lap (no feedback on OUT/IN laps or in garage)
    if getattr(car, 'state', None) != CarState.HOT_LAP and getattr(car, 'last_lap_type', None) != CarState.HOT_LAP:
        return None
    
    # Get driver feedback configuration based on rating
    level, config = get_feedback_config(pilot.ricerca_assetto)
    
    # No feedback for poor drivers (0-40)
    if config['max_per_lap'] == 0:
        return None
    
    # Update lap tracking if needed
    current_lap = car.total_session_laps
    if current_lap != car.current_lap_for_feedback:
        car.current_lap_for_feedback = current_lap
        car.feedback_count_this_lap = 0
        car.feedback_zones_used_this_lap.clear()
    
    # Check per-lap limit
    if car.feedback_count_this_lap >= config['max_per_lap']:
        return None
    
    # Check per-zone limit (max 1 per zone per lap)
    zone_key = sector or 'general'
    if zone_key in car.feedback_zones_used_this_lap:
        return None
    
    # Check cooldown (rating-based)
    current_time = time.time()
    cooldown = config['cooldown']
    if current_time - car.driver_feedback_timestamp < cooldown:
        return None
    
    # Probability check (rating-based, 15-30% chance)
    base_chance = 0.15 + (pilot.ricerca_assetto / 100.0) * 0.15
    if random.random() > base_chance:
        return None
    
    # Generate message based on quality level
    quality = config['quality']
    
    if quality == 'vague':
        # Poor drivers give vague feedback
        message = random.choice(VAGUE_MESSAGES)
    else:
        # Get setup values for specific feedback
        setup = car.player_config.get('setup', {})
        scores = calculate_setup_balance_scores(setup)
        surface = circuit_profile.get('surface', {}) if circuit_profile else {}
        corner_speed_mult = surface.get('corner_speed_multiplier', 1.0)
        braking_mult = surface.get('braking_multiplier', 1.0)
        
        messages = []
        
        # Zone-specific feedback
        if sector == 'sector1' or braking_mult < 0.98:
            # Braking zone feedback
            susp_balance = scores['susp_balance']
            if susp_balance > 10:
                messages.extend(BRAKING_MESSAGES['front_lock'])
            elif susp_balance < -10:
                messages.extend(BRAKING_MESSAGES['rear_instability'])
            elif abs(susp_balance) <= 6:
                messages.extend(BRAKING_MESSAGES['good'])
        
        if sector in ('sector2', 'sector3') or corner_speed_mult < 1.0:
            # Cornering feedback
            wing_balance = scores['wing_balance']
            understeer_tolerance = pilot.stile_sottosterzo / 100.0
            oversteer_tolerance = pilot.stile_sovrasterzo / 100.0
            
            # Understeer detection with driver tolerance
            if wing_balance > 8 and understeer_tolerance < 0.5:
                messages.extend(CORNERING_MESSAGES['understeer'])
            elif wing_balance < -8 and oversteer_tolerance < 0.5:
                messages.extend(CORNERING_MESSAGES['oversteer'])
            elif abs(wing_balance) <= 4:
                messages.extend(CORNERING_MESSAGES['balanced'])
            
            # Traction feedback
            traction_indicator = scores['traction_indicator']
            if traction_indicator > 12:
                messages.extend(TRACTION_MESSAGES['wheelspin'])
            elif traction_indicator <= 5:
                messages.extend(TRACTION_MESSAGES['good'])
        
        # Speed feedback (any sector, low probability)
        if random.random() < 0.3:
            rear_wing = scores['rear_wing']
            drag_indicator = surface.get('aerodynamic_drag', 90)
            if rear_wing > 60 and drag_indicator > 85:
                messages.extend(SPEED_MESSAGES['too_much_drag'])
            elif rear_wing < 45:
                messages.extend(SPEED_MESSAGES['good'])
        
        if not messages:
            return None
        
        message = random.choice(messages)
    
    # Update car state
    car.last_driver_feedback = message
    car.driver_feedback_timestamp = current_time
    car.feedback_count_this_lap += 1
    car.feedback_zones_used_this_lap.add(zone_key)
    
    return message


def emit_direct_feedback(car, message: str, zone_key: Optional[str] = 'general') -> bool:
    """Emit a deterministic driver feedback message, bypassing probability checks."""
    if not car or not getattr(car, 'is_player_controlled', False):
        return False

    pilot = getattr(car, 'pilot', None)
    if not pilot:
        return False

    _, config = get_feedback_config(pilot.ricerca_assetto)
    if config['max_per_lap'] == 0:
        return False

    current_lap = car.total_session_laps
    if current_lap != car.current_lap_for_feedback:
        car.current_lap_for_feedback = current_lap
        car.feedback_count_this_lap = 0
        car.feedback_zones_used_this_lap.clear()

    if zone_key and zone_key in car.feedback_zones_used_this_lap:
        return False

    if car.feedback_count_this_lap >= config['max_per_lap']:
        return False

    car.last_driver_feedback = message
    car.driver_feedback_timestamp = time.time()
    car.feedback_count_this_lap += 1
    if zone_key:
        car.feedback_zones_used_this_lap.add(zone_key)
    return True


def _build_thermal_message(event_type: str, detail: Optional[str]) -> Optional[str]:
    options = THERMAL_MESSAGES.get(event_type)
    if not options and not detail:
        return None
    base = random.choice(options) if options else None
    if detail and base:
        return f"{detail}. {base}"
    return detail or base


def emit_thermal_feedback(car, event_type: str, detail: Optional[str] = None) -> bool:
    message = _build_thermal_message(event_type, detail)
    if not message:
        return False
    zone_key = f"thermal:{event_type}"
    return emit_direct_feedback(car, message, zone_key=zone_key)


def should_trigger_feedback(car, event_type: str) -> bool:
    """Check if driver should give feedback for a specific event."""
    if not car.is_player_controlled:
        return False
    
    pilot = car.pilot
    if not pilot:
        return False
    
    # Get config to check if driver can give feedback at all
    level, config = get_feedback_config(pilot.ricerca_assetto)
    if config['max_per_lap'] == 0:
        return False
    
    # Update lap tracking
    current_lap = car.total_session_laps
    if current_lap != car.current_lap_for_feedback:
        car.current_lap_for_feedback = current_lap
        car.feedback_count_this_lap = 0
        car.feedback_zones_used_this_lap.clear()
    
    # Check per-lap limit
    if car.feedback_count_this_lap >= config['max_per_lap']:
        return False
    
    # Simple probability based on event type and rating
    event_probs = {
        'braking_zone': 0.40,
        'sector_entry': 0.30,
        'corner_exit': 0.25,
        'straight': 0.15,
    }
    base_prob = event_probs.get(event_type, 0.25)
    rating_bonus = (pilot.ricerca_assetto - 40) / 100.0 * 0.20  # 0 to ~0.12
    
    return random.random() < (base_prob + rating_bonus)
