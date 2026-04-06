"""
Physics Engine V4 - Aero Calibration Loader

Carica i profili di calibrazione aerodinamica generati da `scripts/aero_fit.py`
e salvati in `config/calibration/aero/<circuit_id>.json`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional
import json


_REPO_ROOT = Path(__file__).resolve().parents[4]
_AERO_CALIBRATION_DIR = _REPO_ROOT / "config" / "calibration" / "aero"


def normalize_circuit_id(circuit_id: Optional[str]) -> str:
    """Normalizza l'ID del circuito per il lookup file-system."""
    return (circuit_id or "").strip().lower()


def _resolve_calibration_path(circuit_id: str) -> Optional[Path]:
    circuit_key = normalize_circuit_id(circuit_id)
    if not circuit_key:
        return None

    candidate = _AERO_CALIBRATION_DIR / f"{circuit_key}.json"
    if candidate.exists():
        return candidate

    matches = sorted(_AERO_CALIBRATION_DIR.glob(f"*_{circuit_key}.json"))
    if matches:
        return matches[0]

    return None


@lru_cache(maxsize=None)
def get_aero_calibration(circuit_id: str) -> Optional[Dict[str, Any]]:
    """Restituisce il profilo aero per il circuito richiesto, se presente."""
    path = _resolve_calibration_path(circuit_id)
    if path is None:
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    aero = payload.get("aero")
    if not isinstance(aero, dict):
        return None

    calibration = dict(aero)
    calibration["circuit_id"] = normalize_circuit_id(circuit_id)
    calibration["source_file"] = str(path)
    return calibration


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_aero_setup_bias(circuit_id: str) -> Optional[Dict[str, Any]]:
    """Deriva un piccolo bias di setup dai profili aero calibrati del circuito."""
    calibration = get_aero_calibration(circuit_id)
    if not calibration:
        return None

    drag_index = _as_float(calibration.get("drag_index"), 1.0)
    downforce_index = _as_float(calibration.get("downforce_index"), 1.0)
    aero_balance_target = _as_float(calibration.get("aero_balance_target"), 0.0)

    efficiency_ratio = downforce_index / max(drag_index, 0.1)
    load_bias = max(-4, min(4, int(round((efficiency_ratio - 0.7) * 8))))
    split_bias = max(-2, min(2, int(round(aero_balance_target * 8))))

    adjustments = {
        "front_wing": load_bias + split_bias,
        "rear_wing": load_bias - split_bias,
        "beam_wing": int(round(load_bias * 0.5)),
    }

    return {
        "circuit_id": normalize_circuit_id(circuit_id),
        "calibration": calibration,
        "efficiency_ratio": round(efficiency_ratio, 3),
        "load_bias": load_bias,
        "split_bias": split_bias,
        "adjustments": adjustments,
    }


def apply_aero_setup_bias(
    setup_values: Dict[str, Any],
    circuit_id: str,
    clamp_min: float = 0.0,
    clamp_max: float = 100.0,
) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Applica il bias aero ai target setup senza mutare il dizionario originale."""
    bias = compute_aero_setup_bias(circuit_id)
    if not bias:
        return dict(setup_values), None

    adjusted = dict(setup_values)
    applied_fields: list[str] = []
    for field, delta in bias["adjustments"].items():
        current = adjusted.get(field)
        if not isinstance(current, (int, float)):
            continue

        new_value = max(clamp_min, min(clamp_max, current + delta))
        if isinstance(current, int) and not isinstance(current, bool):
            adjusted[field] = int(round(new_value))
        elif isinstance(current, float):
            adjusted[field] = float(new_value)
        else:
            adjusted[field] = new_value
        applied_fields.append(field)

    bias["applied_fields"] = applied_fields
    return adjusted, bias
