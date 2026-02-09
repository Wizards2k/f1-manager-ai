"""SetupEngineService v0: validate, map slider -> physics, evaluate setup."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import json

from python_backend.models.models import DEFAULT_SETUP_CONFIG
from python_backend.utils.setup_engine import evaluate_setup, evaluate_setup_categories


_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAPPING_PATH = _REPO_ROOT / "config" / "setup" / "setup_mapping_v2.json"
_TEAM_OFFSETS_PATH = _REPO_ROOT / "config" / "setup" / "team_offsets.json"


@dataclass
class SetupValidationResult:
    ok: bool
    errors: list[str]
    sanitized: Dict[str, int]
    physics: Dict[str, Any]
    constraints: Dict[str, Any]
    circuit_key: str


class SetupEngineService:
    _mapping_cache: Optional[Dict[str, Any]] = None
    _team_offsets_cache: Optional[Dict[str, Any]] = None

    @classmethod
    def _load_mapping(cls) -> Dict[str, Any]:
        if cls._mapping_cache is None:
            with _MAPPING_PATH.open("r", encoding="utf-8") as handle:
                cls._mapping_cache = json.load(handle)
        return cls._mapping_cache

    @classmethod
    def _load_team_offsets(cls) -> Dict[str, Any]:
        if cls._team_offsets_cache is None:
            try:
                with _TEAM_OFFSETS_PATH.open("r", encoding="utf-8") as handle:
                    cls._team_offsets_cache = json.load(handle)
            except FileNotFoundError:
                cls._team_offsets_cache = {}
        return cls._team_offsets_cache

    @classmethod
    def _merge_mapping(cls, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for key, value in base.items():
            if key in override and isinstance(value, dict) and isinstance(override[key], dict):
                merged[key] = cls._merge_mapping(value, override[key])
            else:
                merged[key] = override.get(key, value)
        for key, value in override.items():
            if key not in merged:
                merged[key] = value
        return merged

    @classmethod
    def get_circuit_mapping(cls, circuit_id: Optional[str]) -> Tuple[str, Dict[str, Any]]:
        mapping = cls._load_mapping()
        key = (circuit_id or "default").lower()
        if key in mapping:
            entry = mapping[key]
        else:
            entry = None
            for entry_key, entry_value in mapping.items():
                metadata = entry_value.get("metadata", {}) if isinstance(entry_value, dict) else {}
                if metadata.get("circuit_id", "").lower() == key:
                    entry = entry_value
                    key = entry_key
                    break
        default = mapping.get("default", {})
        if entry:
            return key, cls._merge_mapping(default, entry)
        return "default", default

    @classmethod
    def _sanitize_setup(cls, setup: Dict[str, Any]) -> Tuple[Dict[str, int], list[str]]:
        if not isinstance(setup, dict):
            return {}, ["setup payload must be an object"]
        errors: list[str] = []
        sanitized: Dict[str, int] = {}
        for field in setup.keys():
            if field not in DEFAULT_SETUP_CONFIG:
                errors.append(f"Unknown setup field: {field}")
        for field in DEFAULT_SETUP_CONFIG.keys():
            if field not in setup:
                continue
            try:
                value = int(setup[field])
            except (TypeError, ValueError):
                errors.append(f"{field} must be an integer")
                continue
            if value < 0 or value > 100:
                errors.append(f"{field} must be between 0 and 100")
                continue
            sanitized[field] = value
        if not sanitized and not errors:
            errors.append("Provide at least one setup field")
        return sanitized, errors

    @classmethod
    def map_slider_to_physics(cls, setup: Dict[str, int], mapping: Dict[str, Any]) -> Dict[str, Any]:
        def lerp(min_v: float, max_v: float, slider: int) -> float:
            return min_v + (max_v - min_v) * (slider / 100.0)

        def apply_step(value: float, step: Optional[float]) -> float:
            if not step:
                return value
            return round(value / step) * step

        physics: Dict[str, Any] = {}
        if "front_wing" in setup:
            cfg = mapping["front_wing"]
            value = lerp(cfg["min_deg"], cfg["max_deg"], setup["front_wing"])
            physics["front_wing_deg"] = apply_step(value, cfg.get("step_deg"))
        if "rear_wing" in setup:
            cfg = mapping["rear_wing"]
            value = lerp(cfg["min_deg"], cfg["max_deg"], setup["rear_wing"])
            physics["rear_wing_deg"] = apply_step(value, cfg.get("step_deg"))
        if "beam_wing" in setup:
            cfg = mapping["beam_wing"]
            value = lerp(cfg["min_deg"], cfg["max_deg"], setup["beam_wing"])
            physics["beam_wing_deg"] = apply_step(value, cfg.get("step_deg"))
        if "ride_height_front" in setup:
            cfg = mapping["ride_height_front"]
            physics["ride_height_front_mm"] = lerp(cfg["min_mm"], cfg["max_mm"], setup["ride_height_front"])
        if "ride_height_rear" in setup:
            cfg = mapping["ride_height_rear"]
            physics["ride_height_rear_mm"] = lerp(cfg["min_mm"], cfg["max_mm"], setup["ride_height_rear"])
        if "suspension_front" in setup:
            cfg = mapping["suspension_front"]
            physics["suspension_front_rigidity"] = lerp(cfg["rigidity"]["min"], cfg["rigidity"]["max"], setup["suspension_front"])
            physics["suspension_front_efficiency"] = lerp(cfg["efficiency"]["min"], cfg["efficiency"]["max"], setup["suspension_front"])
        if "suspension_rear" in setup:
            cfg = mapping["suspension_rear"]
            physics["suspension_rear_rigidity"] = lerp(cfg["rigidity"]["min"], cfg["rigidity"]["max"], setup["suspension_rear"])
            physics["suspension_rear_efficiency"] = lerp(cfg["efficiency"]["min"], cfg["efficiency"]["max"], setup["suspension_rear"])
        if "antiroll_front" in setup:
            cfg = mapping["antiroll_front"]
            physics["antiroll_front_rigidity"] = lerp(cfg["rigidity"]["min"], cfg["rigidity"]["max"], setup["antiroll_front"])
        if "antiroll_rear" in setup:
            cfg = mapping["antiroll_rear"]
            physics["antiroll_rear_rigidity"] = lerp(cfg["rigidity"]["min"], cfg["rigidity"]["max"], setup["antiroll_rear"])
        if "brake_balance" in setup:
            cfg = mapping["brake_balance"]
            physics["brake_balance_pct"] = lerp(cfg["min_pct"], cfg["max_pct"], setup["brake_balance"])
        if "brake_duct" in setup:
            cfg = mapping["brake_duct"]
            physics["brake_duct_open"] = lerp(cfg["min_open"], cfg["max_open"], setup["brake_duct"])

        if "ride_height_front_mm" in physics and "ride_height_rear_mm" in physics:
            physics["rake_mm"] = physics["ride_height_rear_mm"] - physics["ride_height_front_mm"]
        return physics

    @classmethod
    def validate_setup(cls, setup: Dict[str, Any], circuit_id: Optional[str]) -> SetupValidationResult:
        sanitized, errors = cls._sanitize_setup(setup)
        circuit_key, mapping = cls.get_circuit_mapping(circuit_id)
        constraints = mapping.get("constraints", {}) if isinstance(mapping, dict) else {}
        physics = cls.map_slider_to_physics(sanitized, mapping) if not errors else {}

        if not errors:
            rake = physics.get("rake_mm")
            rake_constraints = constraints.get("rake_mm", {})
            if rake is not None and rake_constraints:
                if rake < rake_constraints.get("min", rake) or rake > rake_constraints.get("max", rake):
                    errors.append("Rake out of bounds")
            limit = constraints.get("suspension_delta_limit")
            front_rig = physics.get("suspension_front_rigidity")
            rear_rig = physics.get("suspension_rear_rigidity")
            if limit is not None and front_rig is not None and rear_rig is not None:
                if abs(front_rig - rear_rig) > limit:
                    errors.append("Suspension delta too high")
        return SetupValidationResult(ok=not errors, errors=errors, sanitized=sanitized, physics=physics, constraints=constraints, circuit_key=circuit_key)

    @classmethod
    def build_ranges_payload(cls, circuit_id: Optional[str]) -> Dict[str, Any]:
        circuit_key, mapping = cls.get_circuit_mapping(circuit_id)
        payload = {"circuit_key": circuit_key, "mapping": {}, "constraints": mapping.get("constraints", {})}
        for field, config in mapping.items():
            if field.startswith("_"):
                continue
            if field in {"constraints", "metadata", "energy_profile", "cooling_guidance", "cluster_context", "pirelli_context"}:
                payload[field] = config
                continue
            payload["mapping"][field] = config
        return payload

    @classmethod
    def evaluate(cls, setup: Dict[str, int]) -> Dict[str, Any]:
        base = evaluate_setup(setup)
        categories = evaluate_setup_categories(setup)
        base["categories"] = categories
        return base

    @classmethod
    def build_ideal_setup(cls, circuit_id: Optional[str], car: Any) -> Dict[str, int]:
        # Baseline da setup_ranges
        circuit_key, _ = cls.get_circuit_mapping(circuit_id)
        ranges_dir = _REPO_ROOT / "config" / "setup" / "setup_ranges"
        baseline_path = ranges_dir / f"{circuit_id or circuit_key}.json"
        if not baseline_path.exists():
            baseline_path = ranges_dir / f"{circuit_key}.json"
        baseline_target = {}
        if baseline_path.exists():
            with baseline_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
                ranges = data.get("ranges", {})
                for field, cfg in ranges.items():
                    baseline_target[field] = int(cfg.get("target", 50))
        else:
            baseline_target = {field: 50 for field in DEFAULT_SETUP_CONFIG.keys()}

        team_offsets = cls._load_team_offsets()
        team_entry = team_offsets.get(getattr(car, "team_name", "")) or {}
        team_delta = team_entry.get("team", {})
        driver_entry = team_entry.get("drivers", {}).get(getattr(car, "driver_name", ""), {})

        ideal: Dict[str, int] = {}
        for field in DEFAULT_SETUP_CONFIG.keys():
            base_value = baseline_target.get(field, 50)
            delta = int(team_delta.get(field, 0)) + int(driver_entry.get(field, 0))
            ideal[field] = max(0, min(100, base_value + delta))
        return ideal
