"""Lightweight setup evaluation engine for MVP."""
from __future__ import annotations

from typing import Dict, Any

from python_backend.models.models import DEFAULT_SETUP_CONFIG
import config

BASE_FIELD_PARAMS: Dict[str, Dict[str, Any]] = {
    'front_wing': {
        'label': 'Front wing',
        'label_short': 'front wing',
        'optimal': 52,
        'tolerance': 6,
        'range': (42, 70),
        'weight': 1.1,
    },
    'rear_wing': {
        'label': 'Rear wing',
        'label_short': 'rear wing',
        'optimal': 58,
        'tolerance': 6,
        'range': (45, 75),
        'weight': 1.0,
    },
    'ride_height_front': {
        'label': 'Front ride height',
        'label_short': 'front ride height',
        'optimal': 48,
        'tolerance': 8,
        'range': (30, 70),
        'weight': 0.8,
    },
    'ride_height_rear': {
        'label': 'Rear ride height',
        'label_short': 'rear ride height',
        'optimal': 55,
        'tolerance': 8,
        'range': (35, 75),
        'weight': 0.8,
    },
    'suspension_front': {
        'label': 'Front suspension',
        'label_short': 'front suspension',
        'optimal': 50,
        'tolerance': 10,
        'range': (20, 80),
        'weight': 0.6,
    },
    'suspension_rear': {
        'label': 'Rear suspension',
        'label_short': 'rear suspension',
        'optimal': 50,
        'tolerance': 10,
        'range': (20, 80),
        'weight': 0.6,
    },
}

CIRCUIT_SETUP_OVERRIDES: Dict[str, Dict[str, Dict[str, Any]]] = {
    'monza': {
        'front_wing': {'optimal': 44, 'range': (35, 60)},
        'rear_wing': {'optimal': 52, 'range': (40, 65)},
        'ride_height_front': {'optimal': 52},
        'ride_height_rear': {'optimal': 58},
    },
    'monaco': {
        'front_wing': {'optimal': 64, 'range': (55, 80)},
        'rear_wing': {'optimal': 68, 'range': (55, 85)},
        'ride_height_front': {'optimal': 46},
        'ride_height_rear': {'optimal': 52},
    },
}


def _resolve_field_params(field: str) -> Dict[str, Any]:
    base = {**BASE_FIELD_PARAMS[field]}
    profile = config.get_current_circuit_profile() or {}
    circuit_id = profile.get('circuit_id') or profile.get('id') or profile.get('slug')
    if circuit_id:
        circuit_id = str(circuit_id).lower()
    overrides = CIRCUIT_SETUP_OVERRIDES.get(circuit_id or '', {})
    if field in overrides:
        base.update(overrides[field])
    profile_targets = profile.get('setup_targets', {})
    if isinstance(profile_targets, dict) and field in profile_targets:
        base.update(profile_targets[field])
    return base


def _status_from_delta(delta: float, tolerance: float) -> str:
    diff = abs(delta)
    if diff <= tolerance:
        return 'optimal'
    if diff <= tolerance * 1.8:
        return 'near'
    return 'out'


def evaluate_setup(setup_values: Dict[str, int]) -> Dict[str, Any]:
    """Return tone/message + per-field guidance for the given setup."""
    evaluated_fields = {}
    total_score = 0.0
    total_weight = 0.0
    issues = []
    warnings = []

    for field in DEFAULT_SETUP_CONFIG.keys():
        params = _resolve_field_params(field)
        value = int(setup_values.get(field, DEFAULT_SETUP_CONFIG[field]))
        optimal = params['optimal']
        tolerance = params['tolerance']
        delta = value - optimal
        status = _status_from_delta(delta, tolerance)
        label_short = params['label_short']
        if status == 'out':
            direction = 'high' if delta > 0 else 'low'
            issues.append(f"{label_short} too {direction}")
        elif status == 'near' and abs(delta) > tolerance * 1.3:
            warnings.append(label_short)

        range_min, range_max = params.get('range', (max(1, optimal - 2 * tolerance), min(100, optimal + 2 * tolerance)))
        weight = params.get('weight', 1.0)
        score_delta = max(-2.0, -abs(delta) / max(1, tolerance)) * weight
        total_score += score_delta
        total_weight += weight
        delta_label = 'On target'
        if status != 'optimal':
            sign = '+' if delta > 0 else '-'
            delta_label = f"{params['label']} {('+' if delta > 0 else '-')}{abs(delta):.0f}"
            if delta > 0:
                delta_label = f"Higher than target ({sign}{abs(delta):.0f})"
            else:
                delta_label = f"Lower than target ({sign}{abs(delta):.0f})"

        evaluated_fields[field] = {
            'value': value,
            'optimal': optimal,
            'status': status,
            'delta': delta,
            'delta_label': delta_label,
            'range': {'min': int(range_min), 'max': int(range_max)},
        }

    avg_score = total_score / total_weight if total_weight else 0.0
    if issues:
        tone = 'warning'
        message = '; '.join(issues[:2])
        if len(issues) > 2:
            message += '...'
    elif warnings:
        tone = 'info'
        message = f"Fine-tune {warnings[0]}"
    else:
        tone = 'success'
        message = 'Setup within optimal window.'

    return {
        'message': message,
        'tone': tone,
        'score': round(avg_score, 3),
        'fields': evaluated_fields,
    }


def score_to_color(score: float) -> str:
    """Convert 0-100 score to 5-level color system."""
    if score >= 95:
        return 'fuchsia'  # Near perfect
    elif score >= 80:
        return 'green'    # Good
    elif score >= 60:
        return 'yellow'   # Acceptable
    elif score >= 40:
        return 'orange'   # Bad
    else:
        return 'red'      # Wrong direction


def evaluate_setup_categories(setup_values: Dict[str, int]) -> Dict[str, Any]:
    """
    Evaluate setup by 4 categories with 5-level color scoring.
    
    Categories:
    - cornering: Front vs rear wing balance (understeer/oversteer)
    - speed: Straight-line speed (drag from rear wing and ride height)
    - traction: Grip out of slow corners (ride height + suspension)
    - stability: Braking stability (suspension balance)
    """
    # Get evaluated fields from base evaluation
    base_eval = evaluate_setup(setup_values)
    fields = base_eval['fields']
    
    def get_field_score(field: str) -> float:
        """Convert field evaluation to 0-100 score."""
        if field not in fields:
            return 50.0
        delta = abs(fields[field]['delta'])
        params = _resolve_field_params(field)
        tolerance = params.get('tolerance', 10)
        # Score decreases as delta increases from optimal
        score = max(0, 100 - (delta / tolerance) * 50)
        return score
    
    # Category 1: Cornering Balance (front_wing vs rear_wing)
    front_score = get_field_score('front_wing')
    rear_score = get_field_score('rear_wing')
    front_val = setup_values.get('front_wing', 50)
    rear_val = setup_values.get('rear_wing', 50)
    wing_balance = front_val - rear_val  # Positive = more front wing = understeer tendency
    
    cornering_score = (front_score + rear_score) / 2
    # Penalize if balance is way off
    balance_penalty = abs(wing_balance) * 2  # Max ~40 penalty
    cornering_score = max(0, cornering_score - balance_penalty)
    
    if cornering_score >= 90:
        cornering_msg = "Neutral balance, good rotation"
    elif wing_balance > 8:
        cornering_msg = "Slight understeer in high-speed corners"
    elif wing_balance < -8:
        cornering_msg = "Rear unstable mid-corner"
    elif wing_balance > 4:
        cornering_msg = "Front-end could be sharper"
    elif wing_balance < -4:
        cornering_msg = "Tail slides on throttle"
    else:
        cornering_msg = "Good balance, minor fine-tuning possible"
    
    # Category 2: Straight-line Speed (rear_wing, ride_height_rear)
    rear_wing_score = get_field_score('rear_wing')
    ride_rear_score = get_field_score('ride_height_rear')
    speed_score = (rear_wing_score + ride_rear_score) / 2
    
    # Higher rear wing = more drag = lower top speed
    rear_wing_val = setup_values.get('rear_wing', 50)
    if rear_wing_val > 65:
        speed_msg = "Too much drag on straights"
    elif rear_wing_val < 45:
        speed_msg = "Good top speed, watch rear grip"
    elif speed_score >= 85:
        speed_msg = "Good top speed"
    else:
        speed_msg = "Aero drag affecting straight-line speed"
    
    # Category 3: Traction (ride heights + suspension)
    ride_front_score = get_field_score('ride_height_front')
    ride_rear_score = get_field_score('ride_height_rear')
    susp_front_score = get_field_score('suspension_front')
    susp_rear_score = get_field_score('suspension_rear')
    traction_score = (ride_front_score + ride_rear_score + susp_front_score + susp_rear_score) / 4
    
    # Lower rear ride height = better traction
    ride_rear_val = setup_values.get('ride_height_rear', 50)
    if ride_rear_val > 65:
        traction_msg = "Wheelspin on exits"
    elif traction_score >= 85:
        traction_msg = "Strong traction out of slow corners"
    else:
        traction_msg = "Traction could be improved"
    
    # Category 4: Stability (suspension balance)
    susp_front_val = setup_values.get('suspension_front', 50)
    susp_rear_val = setup_values.get('suspension_rear', 50)
    susp_balance = susp_front_val - susp_rear_val
    stability_score = (susp_front_score + susp_rear_score) / 2
    # Penalize extreme splits
    stability_score = max(0, stability_score - abs(susp_balance) * 1.5)
    
    if stability_score >= 85:
        stability_msg = "Stable under braking"
    elif susp_balance > 15:
        stability_msg = "Front locks under heavy braking"
    elif susp_balance < -15:
        stability_msg = "Rear slides under braking"
    elif susp_balance > 8:
        stability_msg = "Nose dives under braking"
    elif susp_balance < -8:
        stability_msg = "Rear light on entry"
    else:
        stability_msg = "Acceptable stability"
    
    categories = {
        'cornering': {
            'score': round(cornering_score, 1),
            'color': score_to_color(cornering_score),
            'message': cornering_msg,
        },
        'speed': {
            'score': round(speed_score, 1),
            'color': score_to_color(speed_score),
            'message': speed_msg,
        },
        'traction': {
            'score': round(traction_score, 1),
            'color': score_to_color(traction_score),
            'message': traction_msg,
        },
        'stability': {
            'score': round(stability_score, 1),
            'color': score_to_color(stability_score),
            'message': stability_msg,
        },
    }
    
    # Overall assessment
    avg_category_score = sum(c['score'] for c in categories.values()) / 4
    overall_color = score_to_color(avg_category_score)
    
    return {
        'categories': categories,
        'overall_score': round(avg_category_score, 1),
        'overall_color': overall_color,
    }
