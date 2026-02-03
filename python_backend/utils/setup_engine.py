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
