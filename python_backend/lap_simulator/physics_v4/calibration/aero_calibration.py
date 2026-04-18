"""
Physics Engine V4 - Aero Calibration Loader

Carica i profili di calibrazione aerodinamica generati da `scripts/sync_telemetry_2025.py`
e salvati in `data/circuits/aero_calibration/<circuit_id>_aero_cal.json`.

V5.0: Supporta il nuovo formato con:
- grip_data.mu_mechanical: grip meccanico a bassa velocità (senza downforce)
- floor_data.k_wing_coupling: quanto l'angolo ala influenza il floor downforce
- floor_data.mu_by_speed: grip per fascia di velocità
- floor_data.cla_floor_dynamic: coefficiente floor dinamico
- aero.drag_index, aero.downforce_index, aero.aero_balance_target (formato legacy)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional
import json


_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON_BACKEND_ROOT = Path(__file__).resolve().parents[3]  # python_backend/

# V5.0: Nuovo percorso con formato esteso (mu_mechanical, k_wing_coupling, mu_by_speed)
_AERO_CALIBRATION_DIR_NEW = _PYTHON_BACKEND_ROOT / "data" / "circuits" / "aero_calibration"
# Legacy: vecchio percorso con formato aero-only (drag_index, downforce_index, aero_balance_target)
_AERO_CALIBRATION_DIR_OLD = _REPO_ROOT / "config" / "calibration" / "aero"


def normalize_circuit_id(circuit_id: Optional[str]) -> str:
    """Normalizza l'ID del circuito per il lookup file-system."""
    return (circuit_id or "").strip().lower()


def _resolve_calibration_path(circuit_id: str) -> Optional[Path]:
    """Cerca il file di calibrazione aero, preferendo il nuovo formato V5.0."""
    circuit_key = normalize_circuit_id(circuit_id)
    if not circuit_key:
        return None

    # V5.0: Cerca nel nuovo percorso con suffisso _aero_cal
    candidate_new = _AERO_CALIBRATION_DIR_NEW / f"{circuit_key}_aero_cal.json"
    if candidate_new.exists():
        return candidate_new

    # Fallback: cerca per pattern nel nuovo percorso
    matches_new = sorted(_AERO_CALIBRATION_DIR_NEW.glob(f"*_{circuit_key}_aero_cal.json"))
    if matches_new:
        return matches_new[0]

    # Legacy: cerca nel vecchio percorso
    candidate_old = _AERO_CALIBRATION_DIR_OLD / f"{circuit_key}.json"
    if candidate_old.exists():
        return candidate_old

    matches_old = sorted(_AERO_CALIBRATION_DIR_OLD.glob(f"*_{circuit_key}.json"))
    if matches_old:
        return matches_old[0]

    return None


@lru_cache(maxsize=None)
def get_aero_calibration(circuit_id: str) -> Optional[Dict[str, Any]]:
    """Restituisce il profilo aero per il circuito richiesto, se presente.
    
    V5.0: Supporta sia il nuovo formato (con mu_mechanical, k_wing_coupling)
    sia il formato legacy (con drag_index, downforce_index, aero_balance_target).
    
    Il dizionario restituito contiene sempre:
    - circuit_id: ID normalizzato del circuito
    - source_file: percorso del file caricato
    - Formato V5.0: mu_mechanical, k_wing_coupling, mu_by_speed, cla_floor_dynamic
    - Formato legacy: drag_index, downforce_index, aero_balance_target
    """
    path = _resolve_calibration_path(circuit_id)
    if path is None:
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    # V5.0: Nuovo formato con grip_data e floor_data
    grip_data = payload.get("grip_data", {})
    floor_data = payload.get("floor_data", {})
    
    if isinstance(grip_data, dict) and isinstance(floor_data, dict):
        # Nuovo formato V5.0
        calibration = {
            "circuit_id": normalize_circuit_id(circuit_id),
            "source_file": str(path),
            "format": "v5",
            # Grip data
            "mu_mechanical": _as_float(grip_data.get("mu_mechanical"), None),
            "mu_aero_contribution": _as_float(grip_data.get("mu_aero_contribution"), 0.0),
            "c_aero": _as_float(grip_data.get("c_aero"), None),
            "compound": grip_data.get("compound", "C3"),
            "cla_estimated": _as_float(grip_data.get("cla_estimated"), None),
            # Floor data
            "k_wing_coupling": _as_float(floor_data.get("k_wing_coupling"), 0.0),
            "cla_floor_dynamic": _as_float(floor_data.get("cla_floor_dynamic"), 0.0),
            "mu_by_speed": floor_data.get("mu_by_speed", {}),
        }
        # Aggiungi campi legacy se presenti nel payload
        aero = payload.get("aero", {})
        if isinstance(aero, dict):
            calibration["drag_index"] = _as_float(aero.get("drag_index"), 1.0)
            calibration["downforce_index"] = _as_float(aero.get("downforce_index"), 1.0)
            calibration["aero_balance_target"] = _as_float(aero.get("aero_balance_target"), 0.0)
        return calibration

    # Legacy: vecchio formato con solo "aero"
    aero = payload.get("aero")
    if not isinstance(aero, dict):
        return None

    calibration = dict(aero)
    calibration["circuit_id"] = normalize_circuit_id(circuit_id)
    calibration["source_file"] = str(path)
    calibration["format"] = "legacy"
    return calibration


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Converte un valore in float, ritorna default se non possibile."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_aero_setup_bias(circuit_id: str) -> Optional[Dict[str, Any]]:
    """Deriva un piccolo bias di setup dai profili aero calibrati del circuito."""
    calibration = get_aero_calibration(circuit_id)
    if not calibration:
        return None

    # V5.0: I campi legacy potrebbero non esserci nel nuovo formato
    drag_index = _as_float(calibration.get("drag_index"), 1.0) or 1.0
    downforce_index = _as_float(calibration.get("downforce_index"), 1.0) or 1.0
    aero_balance_target = _as_float(calibration.get("aero_balance_target"), 0.0) or 0.0

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
