"""Lightweight setup evaluation engine for MVP."""
from __future__ import annotations

from typing import Dict, Any

from models import DEFAULT_SETUP_CONFIG
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
    'beam_wing': {
        'label': 'Beam wing',
        'label_short': 'beam wing',
        'optimal': 50,
        'tolerance': 8,
        'range': (35, 70),
        'weight': 0.7,
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
    'antiroll_front': {
        'label': 'Front anti-roll',
        'label_short': 'front anti-roll',
        'optimal': 50,
        'tolerance': 10,
        'range': (20, 80),
        'weight': 0.5,
    },
    'antiroll_rear': {
        'label': 'Rear anti-roll',
        'label_short': 'rear anti-roll',
        'optimal': 50,
        'tolerance': 10,
        'range': (20, 80),
        'weight': 0.5,
    },
    'brake_balance': {
        'label': 'Brake balance',
        'label_short': 'brake balance',
        'optimal': 50,
        'tolerance': 6,
        'range': (40, 60),
        'weight': 0.4,
    },
    'brake_duct': {
        'label': 'Brake duct',
        'label_short': 'brake duct',
        'optimal': 50,
        'tolerance': 10,
        'range': (30, 70),
        'weight': 0.4,
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
    profile_getter = getattr(config, 'get_current_circuit_profile', None)
    try:
        profile = profile_getter() if callable(profile_getter) else {}
    except Exception:
        profile = {}
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


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _compute_indices(setup_values: Dict[str, int]) -> Dict[str, float]:
    front = setup_values.get('front_wing', 50)
    rear = setup_values.get('rear_wing', 50)
    beam = setup_values.get('beam_wing', 50)
    ride_front = setup_values.get('ride_height_front', 50)
    ride_rear = setup_values.get('ride_height_rear', 50)
    susp_rear = setup_values.get('suspension_rear', 50)
    antiroll_rear = setup_values.get('antiroll_rear', 50)

    front_share = front / max(1.0, front + rear + beam * 0.5)
    aero_balance = _clamp(front_share, 0.3, 0.7)

    drag_load = (rear * 0.6 + beam * 0.4) / 100.0
    ride_drag = (ride_front + ride_rear) / 200.0
    drag_index = _clamp(drag_load + ride_drag * 0.4, 0.0, 1.0)

    traction_height = (100 - ride_rear) / 100.0
    traction_susp = susp_rear / 100.0
    traction_antiroll = (100 - antiroll_rear) / 100.0
    traction_index = _clamp(0.5 * traction_height + 0.35 * traction_susp + 0.15 * traction_antiroll, 0.0, 1.0)

    return {
        'aero_balance': round(aero_balance, 3),
        'drag_index': round(drag_index, 3),
        'traction_index': round(traction_index, 3),
    }


def evaluate_setup(setup_values: Dict[str, int]) -> Dict[str, Any]:
    """Return tone/message + per-field guidance for the given setup."""
    evaluated_fields = {}
    total_score = 0.0
    total_weight = 0.0
    issues = []
    warnings = []
    recommended_ranges = {}

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
        recommended_ranges[field] = {
            'min': int(range_min),
            'max': int(range_max),
            'target': int(optimal),
            'tolerance': int(tolerance),
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

    indices = _compute_indices(setup_values)

    return {
        'message': message,
        'tone': tone,
        'score': round(avg_score, 3),
        'fields': evaluated_fields,
        'recommended_ranges': recommended_ranges,
        **indices,
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
    # Get evaluated fields + indices from base evaluation
    base_eval = evaluate_setup(setup_values)
    fields = base_eval['fields']
    aero_balance = base_eval.get('aero_balance', 0.5)
    drag_index = base_eval.get('drag_index', 0.5)
    traction_index = base_eval.get('traction_index', 0.5)
    
    def get_field_score(field: str) -> float:
        """Convert field evaluation to 0-100 score based on proximity to optimal."""
        if field not in fields:
            return 50.0
        delta = abs(fields[field]['delta'])
        params = _resolve_field_params(field)
        tolerance = params.get('tolerance', 10)
        
        if delta <= tolerance:
            # 90-100 range when in optimal window
            return 100.0 - (delta / max(1, tolerance)) * 10.0
        
        # Drops off linearly outside the window
        score = max(0.0, 90.0 - ((delta - tolerance) / max(1, tolerance)) * 40.0)
        return score
    
    # Category 1: Cornering Balance
    c_fields = ['front_wing', 'rear_wing', 'beam_wing']
    cornering_score = sum(get_field_score(f) for f in c_fields) / len(c_fields)
    if cornering_score >= 90:
        cornering_msg = "Excellent cornering balance"
    elif cornering_score >= 70:
        cornering_msg = "Good cornering balance"
    else:
        cornering_msg = "Cornering balance needs fine-tuning"
    
    # Category 2: Straight-line Speed
    s_fields = ['rear_wing', 'beam_wing', 'ride_height_front', 'ride_height_rear']
    speed_score = sum(get_field_score(f) for f in s_fields) / len(s_fields)
    if speed_score >= 90:
        speed_msg = "Optimized for straight-line speed"
    elif speed_score >= 70:
        speed_msg = "Good top speed"
    else:
        speed_msg = "Aero drag affecting top speed"
    
    # Category 3: Traction
    t_fields = ['ride_height_rear', 'suspension_rear', 'antiroll_rear']
    traction_score = sum(get_field_score(f) for f in t_fields) / len(t_fields)
    if traction_score >= 90:
        traction_msg = "Excellent traction on exit"
    elif traction_score >= 70:
        traction_msg = "Strong traction on exit"
    else:
        traction_msg = "Traction could be improved"
    
    # Category 4: Stability
    st_fields = ['brake_balance', 'suspension_front', 'antiroll_front']
    stability_score = sum(get_field_score(f) for f in st_fields) / len(st_fields)
    if stability_score >= 90:
        stability_msg = "Very stable under braking"
    elif stability_score >= 70:
        stability_msg = "Stable under braking"
    else:
        stability_msg = "Stability could be improved"
    
    # Category 5: Braking
    b_fields = ['brake_balance', 'brake_duct']
    braking_score = sum(get_field_score(f) for f in b_fields) / len(b_fields)
    if braking_score >= 90:
        braking_msg = "Brakes perfectly balanced"
    elif braking_score >= 70:
        braking_msg = "Brakes well balanced and cooled"
    else:
        braking_msg = "Braking could be improved"

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
        'braking': {
            'score': round(braking_score, 1),
            'color': score_to_color(braking_score),
            'message': braking_msg,
        },
    }
    
    # Overall assessment
    avg_category_score = sum(c['score'] for c in categories.values()) / 5
    overall_color = score_to_color(avg_category_score)
    
    return {
        'categories': categories,
        'overall_score': round(avg_category_score, 1),
        'overall_color': overall_color,
    }
