"""Engine ERS catalog and persistence helpers."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class EngineERSService:
    """Load, normalize and persist ERS map catalogs per circuit."""

    BUILTIN_MAP_IDS = {"PRACTICE", "RACE", "QUALIFY", "SAFETY_CAR"}
    DEFAULT_CIRCUIT_ID = "jp-1962_suzuka"

    DEFAULT_BUDGET_ROOT_PAYLOAD: Dict[str, Any] = {
        "battery_capacity_mj": 4.0,
        "deploy_limit_mj": 4.0,
        "harvest_limit_mj": 2.0,
    }

    DEFAULT_MAP_PAYLOAD: Dict[str, Any] = {
        "heat_load_kw": 260.0,
        "torque_ramp": 0.6,
        "deployment_style": "balanced",
        "cooling_share": 0.5,
        "ers_output_kw": 120.0,
        "deploy_mj_per_lap": 4.0,
        "harvest_mj_per_lap": 1.0,
        "target_soc_end_lap": 0.55,
        "torque_bias": 0.0,
        "mguh_power_kw": 0.0,
        "mguh_direct_ratio": 0.45,
        "bucket_primary_pct": 0.5,
        "bucket_secondary_pct": 0.35,
        "bucket_exit_pct": 0.15,
        "bucket_primary_es_deploy_pct": 0.0,
        "bucket_secondary_es_deploy_pct": 0.0,
        "bucket_exit_es_deploy_pct": 0.0,
        "defense_reserve_mj": 0.2,
    }

    DEFAULT_BUDGET_PAYLOAD: Dict[str, Any] = {
        "deploy_mj_per_lap": 4.0,
        "harvest_mj_per_lap": 1.0,
        "target_soc_end_lap": 0.55,
        "mguh_direct_ratio": 0.45,
        "deploy_ratio": 1.0,
        "harvest_ratio": 0.5,
    }

    @classmethod
    def _repo_root(cls) -> Path:
        return Path(__file__).resolve().parents[2]

    @classmethod
    def _load_circuit_profiles(cls) -> Dict[str, Any]:
        profiles_path = cls._repo_root() / "python_backend" / "config" / "circuit_info.json"
        if not profiles_path.exists():
            return {}

        try:
            profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        return profiles if isinstance(profiles, dict) else {}

    @classmethod
    def list_available_circuit_options(cls) -> list[Dict[str, str]]:
        derived_root = cls._repo_root() / "config" / "circuits" / "derived"
        profiles = cls._load_circuit_profiles()
        options: list[Dict[str, str]] = []

        if derived_root.exists():
            for circuit_dir in derived_root.iterdir():
                if not circuit_dir.is_dir():
                    continue
                pu_map_path = circuit_dir / "pu_maps.json"
                if not pu_map_path.exists():
                    continue

                circuit_id = circuit_dir.name
                profile = profiles.get(circuit_id, {}) if isinstance(profiles, dict) else {}
                display_name = str(profile.get("name") or profile.get("circuit_name") or circuit_id.replace("_", " ").title())
                options.append({"id": circuit_id, "label": display_name})

        options.sort(key=lambda item: (item["id"] != cls.DEFAULT_CIRCUIT_ID, item["label"].lower()))
        return options

    @classmethod
    def _config_paths(cls, circuit_id: str) -> Tuple[Path, Path]:
        root = cls._repo_root()
        derived_path = root / "config" / "circuits" / "derived" / circuit_id / "pu_maps.json"
        global_path = root / "config" / "pu" / "pu_maps_global_default.json"
        return derived_path, global_path

    @classmethod
    def _blank_payload(cls, circuit_id: str) -> Dict[str, Any]:
        return {
            "_meta": {
                "version": "1.0",
                "circuit_id": circuit_id,
                "circuit_name": circuit_id or "No Active Circuit",
            },
            "maps": {},
            "regen_profile": {},
            "ers_budget": {
                **copy.deepcopy(cls.DEFAULT_BUDGET_ROOT_PAYLOAD),
                "maps": {},
                "warnings": [],
            },
            "soc_warnings": [],
        }

    @classmethod
    def _read_json(cls, path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}

    @classmethod
    def _write_json(cls, path: Path, data: Dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load_raw_data(cls, circuit_id: Optional[str]) -> Tuple[Path, Dict[str, Any]]:
        circuit_key = str(circuit_id or "").strip()
        derived_path, global_path = cls._config_paths(circuit_key or "default")

        if not circuit_key:
            return derived_path, cls._blank_payload("")

        if derived_path.exists():
            return derived_path, cls._read_json(derived_path)

        if global_path.exists():
            return global_path, cls._read_json(global_path)

        return derived_path, cls._blank_payload(circuit_key)

    @staticmethod
    def _coerce_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @classmethod
    def _merge_payload(
        cls,
        existing: Optional[Dict[str, Any]],
        updates: Optional[Dict[str, Any]],
        defaults: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = copy.deepcopy(existing) if isinstance(existing, dict) else {}
        if not merged:
            merged = copy.deepcopy(defaults)
        else:
            for key, default_value in defaults.items():
                merged.setdefault(key, copy.deepcopy(default_value))

        for key, value in (updates or {}).items():
            if value is None:
                continue
            merged[key] = copy.deepcopy(value)

        for key, default_value in defaults.items():
            current_value = merged.get(key, default_value)
            if isinstance(default_value, str):
                merged[key] = str(current_value if current_value is not None else default_value)
            else:
                merged[key] = cls._coerce_float(current_value, float(default_value))

        return merged

    @classmethod
    def _merge_budget_root(
        cls,
        existing: Optional[Dict[str, Any]],
        updates: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        merged = copy.deepcopy(existing) if isinstance(existing, dict) else {}
        for key, default_value in cls.DEFAULT_BUDGET_ROOT_PAYLOAD.items():
            merged.setdefault(key, copy.deepcopy(default_value))

        for key, value in (updates or {}).items():
            if key not in cls.DEFAULT_BUDGET_ROOT_PAYLOAD or value is None:
                continue
            merged[key] = copy.deepcopy(value)

        for key, default_value in cls.DEFAULT_BUDGET_ROOT_PAYLOAD.items():
            merged[key] = cls._coerce_float(merged.get(key), float(default_value))

        if not isinstance(merged.get("maps"), dict):
            merged["maps"] = {}
        if not isinstance(merged.get("warnings"), list):
            merged["warnings"] = list(merged.get("warnings") or [])

        return merged

    @classmethod
    def _sync_mirrors(
        cls,
        map_payload: Dict[str, Any],
        budget_payload: Dict[str, Any],
        budget_root: Dict[str, Any],
    ) -> None:
        deploy_limit = cls._coerce_float(budget_root.get("deploy_limit_mj"), 4.0)
        harvest_limit = cls._coerce_float(budget_root.get("harvest_limit_mj"), 2.0)
        bucket_es_deploy_keys = (
            "bucket_primary_es_deploy_pct",
            "bucket_secondary_es_deploy_pct",
            "bucket_exit_es_deploy_pct",
        )
        bucket_distribution_keys = (
            "bucket_primary_pct",
            "bucket_secondary_pct", 
            "bucket_exit_pct",
        )

        deploy_mj = cls._coerce_float(budget_payload.get("deploy_mj_per_lap", map_payload.get("deploy_mj_per_lap", 4.0)), 4.0)
        harvest_mj = cls._coerce_float(budget_payload.get("harvest_mj_per_lap", map_payload.get("harvest_mj_per_lap", 1.0)), 1.0)
        target_soc = cls._coerce_float(budget_payload.get("target_soc_end_lap", map_payload.get("target_soc_end_lap", 0.55)), 0.55)
        direct_ratio = cls._coerce_float(budget_payload.get("mguh_direct_ratio", map_payload.get("mguh_direct_ratio", 0.45)), 0.45)

        # Sync ES Deploy percentages
        for key in bucket_es_deploy_keys:
            value = map_payload.get(key)
            if value is None:
                value = budget_payload.get(key, 0.0)
            value = cls._coerce_float(value, 0.0)
            map_payload[key] = value
            budget_payload[key] = value

        # Sync bucket distribution percentages and defense reserve from map to budget
        for key in bucket_distribution_keys:
            value = map_payload.get(key)
            if value is not None:
                budget_payload[key] = cls._coerce_float(value, 0.0)
        
        defense_reserve = map_payload.get("defense_reserve_mj")
        if defense_reserve is not None:
            budget_payload["defense_reserve_mj"] = cls._coerce_float(defense_reserve, 0.0)

        map_payload["deploy_mj_per_lap"] = deploy_mj
        map_payload["harvest_mj_per_lap"] = harvest_mj
        map_payload["target_soc_end_lap"] = target_soc
        map_payload["mguh_direct_ratio"] = direct_ratio

        budget_payload["deploy_mj_per_lap"] = deploy_mj
        budget_payload["harvest_mj_per_lap"] = harvest_mj
        budget_payload["target_soc_end_lap"] = target_soc
        budget_payload["mguh_direct_ratio"] = direct_ratio
        budget_payload["deploy_ratio"] = round(deploy_mj / deploy_limit, 3) if deploy_limit > 0 else 0.0
        budget_payload["harvest_ratio"] = round(harvest_mj / harvest_limit, 3) if harvest_limit > 0 else 0.0

    @classmethod
    def _migrate_legacy_bucket_es_deploy(
        cls,
        map_payload: Dict[str, Any],
        source_payload: Optional[Dict[str, Any]] = None,
        updates: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not isinstance(map_payload, dict):
            return

        source = source_payload if isinstance(source_payload, dict) else {}
        update_keys = set(updates.keys()) if isinstance(updates, dict) else set()
        bucket_keys = (
            "bucket_primary_es_deploy_pct",
            "bucket_secondary_es_deploy_pct",
            "bucket_exit_es_deploy_pct",
        )

        legacy_value = source.get("es_deploy_pct", map_payload.get("es_deploy_pct"))
        if legacy_value is not None:
            legacy_value = cls._coerce_float(legacy_value, 0.0)

        if legacy_value is not None and not any(key in update_keys for key in bucket_keys):
            source_has_bucket_keys = any(key in source for key in bucket_keys)
            if not source_has_bucket_keys:
                for key in bucket_keys:
                    map_payload[key] = legacy_value

        map_payload.pop("es_deploy_pct", None)

    @classmethod
    def validate_map_payload(
        cls,
        map_payload: Dict[str, Any],
        budget_payload: Dict[str, Any],
        budget_root: Dict[str, Any],
    ) -> list[str]:
        errors: list[str] = []

        deploy_limit = cls._coerce_float(budget_root.get("deploy_limit_mj"), 4.0)
        harvest_limit = cls._coerce_float(budget_root.get("harvest_limit_mj"), 2.0)
        battery_capacity = cls._coerce_float(budget_root.get("battery_capacity_mj"), 4.0)

        deploy_mj = cls._coerce_float(budget_payload.get("deploy_mj_per_lap"), 4.0)
        harvest_mj = cls._coerce_float(budget_payload.get("harvest_mj_per_lap"), 1.0)
        target_soc = cls._coerce_float(budget_payload.get("target_soc_end_lap"), 0.55)
        direct_ratio = cls._coerce_float(budget_payload.get("mguh_direct_ratio"), 0.45)
        defense_reserve = cls._coerce_float(map_payload.get("defense_reserve_mj"), 0.2)
        bucket_primary_es_deploy_pct = cls._coerce_float(map_payload.get("bucket_primary_es_deploy_pct"), 0.0)
        bucket_secondary_es_deploy_pct = cls._coerce_float(map_payload.get("bucket_secondary_es_deploy_pct"), 0.0)
        bucket_exit_es_deploy_pct = cls._coerce_float(map_payload.get("bucket_exit_es_deploy_pct"), 0.0)

        bucket_primary = cls._coerce_float(map_payload.get("bucket_primary_pct"), 0.5)
        bucket_secondary = cls._coerce_float(map_payload.get("bucket_secondary_pct"), 0.35)
        bucket_exit = cls._coerce_float(map_payload.get("bucket_exit_pct"), 0.15)
        bucket_sum = bucket_primary + bucket_secondary + bucket_exit

        if battery_capacity <= 0:
            errors.append("battery_capacity_mj must be greater than 0")
        if deploy_limit <= 0:
            errors.append("deploy_limit_mj must be greater than 0")
        if harvest_limit <= 0:
            errors.append("harvest_limit_mj must be greater than 0")
        if abs(bucket_sum - 1.0) > 0.05:
            errors.append("Bucket percentages must sum to 100%")
        if deploy_mj > deploy_limit + 1e-6:
            errors.append(f"deploy_mj_per_lap exceeds limit ({deploy_limit:.3f} MJ)")
        if harvest_mj > 4.0 + 1e-6:
            errors.append("harvest_mj_per_lap exceeds limit (4.000 MJ)")
        if not 0.0 <= bucket_primary_es_deploy_pct <= 1.0:
            errors.append("bucket_primary_es_deploy_pct must be between 0 and 1")
        if not 0.0 <= bucket_secondary_es_deploy_pct <= 1.0:
            errors.append("bucket_secondary_es_deploy_pct must be between 0 and 1")
        if not 0.0 <= bucket_exit_es_deploy_pct <= 1.0:
            errors.append("bucket_exit_es_deploy_pct must be between 0 and 1")
        if deploy_limit > battery_capacity + 1e-6:
            errors.append("deploy_limit_mj cannot exceed battery_capacity_mj")
        if harvest_limit > battery_capacity + 1e-6:
            errors.append("harvest_limit_mj cannot exceed battery_capacity_mj")
        if not 0.0 <= direct_ratio <= 1.0:
            errors.append("mguh_direct_ratio must be between 0 and 1")
        if not 0.0 <= target_soc <= 1.0:
            errors.append("target_soc_end_lap must be between 0 and 1")
        if defense_reserve < 0.0:
            errors.append("defense_reserve_mj must be positive")
        if defense_reserve > deploy_limit + 1e-6:
            errors.append("defense_reserve_mj cannot exceed deploy limit")

        return errors

    @classmethod
    def _build_summary(
        cls,
        map_payload: Dict[str, Any],
        budget_payload: Dict[str, Any],
        budget_root: Dict[str, Any],
    ) -> Dict[str, Any]:
        battery_capacity = cls._coerce_float(budget_root.get("battery_capacity_mj"), 4.0)
        deploy_limit = cls._coerce_float(budget_root.get("deploy_limit_mj"), 4.0)
        harvest_limit = cls._coerce_float(budget_root.get("harvest_limit_mj"), 2.0)

        deploy_mj = cls._coerce_float(budget_payload.get("deploy_mj_per_lap"), 4.0)
        harvest_mj = cls._coerce_float(budget_payload.get("harvest_mj_per_lap"), 1.0)
        target_soc = cls._coerce_float(budget_payload.get("target_soc_end_lap"), 0.55)
        direct_ratio = cls._coerce_float(budget_payload.get("mguh_direct_ratio"), 0.45)

        bucket_primary = cls._coerce_float(map_payload.get("bucket_primary_pct"), 0.5)
        bucket_secondary = cls._coerce_float(map_payload.get("bucket_secondary_pct"), 0.35)
        bucket_exit = cls._coerce_float(map_payload.get("bucket_exit_pct"), 0.15)
        defense_reserve = cls._coerce_float(map_payload.get("defense_reserve_mj"), 0.2)

        return {
            "deploy_mj_per_lap": round(deploy_mj, 3),
            "deploy_pct_of_battery": round((deploy_mj / battery_capacity) * 100.0, 1) if battery_capacity > 0 else 0.0,
            "deploy_pct_of_limit": round((deploy_mj / deploy_limit) * 100.0, 1) if deploy_limit > 0 else 0.0,
            "harvest_mj_per_lap": round(harvest_mj, 3),
            "harvest_pct_of_limit": round((harvest_mj / harvest_limit) * 100.0, 1) if harvest_limit > 0 else 0.0,
            "target_soc_end_lap": round(target_soc, 3),
            "mguh_direct_ratio": round(direct_ratio, 3),
            "mguh_es_ratio": round(max(1.0 - direct_ratio, 0.0), 3),
            "bucket_primary_pct": round(bucket_primary, 3),
            "bucket_secondary_pct": round(bucket_secondary, 3),
            "bucket_exit_pct": round(bucket_exit, 3),
            "bucket_sum_pct": round(bucket_primary + bucket_secondary + bucket_exit, 3),
            "defense_reserve_mj": round(defense_reserve, 3),
        }

    @classmethod
    def _friendly_label(cls, map_id: str) -> str:
        return map_id.replace("_", " ").title()

    @classmethod
    def build_ice_catalog(cls, circuit_id: Optional[str]) -> Dict[str, Any]:
        """Build catalog of ICE maps from circuit config (top-level maps in pu_maps.json)."""
        circuit_key = str(circuit_id or "").strip()
        source_path, raw_data = cls.load_raw_data(circuit_key)
        meta = copy.deepcopy(raw_data.get("_meta") or {}) if isinstance(raw_data, dict) else {}
        # ICE maps are in the top-level "maps" section
        maps_raw = raw_data.get("maps", {}) if isinstance(raw_data, dict) else {}

        if circuit_key:
            meta.setdefault("circuit_id", circuit_key)
            meta.setdefault("circuit_name", meta.get("circuit_name") or circuit_key)
        else:
            meta.setdefault("circuit_name", "No Active Circuit")

        catalog: list[Dict[str, Any]] = []
        if isinstance(maps_raw, dict):
            for order, (map_id, map_entry) in enumerate(maps_raw.items()):
                raw_map_entry = map_entry if isinstance(map_entry, dict) else {}
                map_payload = cls._merge_payload(
                    raw_map_entry,
                    None,
                    cls.DEFAULT_MAP_PAYLOAD,
                )
                cls._migrate_legacy_bucket_es_deploy(map_payload, raw_map_entry)
                catalog.append({
                    "id": map_id,
                    "label": cls._friendly_label(map_id),
                    "order": order,
                    "is_builtin": map_id in cls.BUILTIN_MAP_IDS,
                    "map_data": map_payload,
                    "summary": {
                        "heat_load_kw": map_payload.get("heat_load_kw", 260.0),
                        "power_pct_base": map_payload.get("power_pct_base", 0.85),
                        "ers_output_kw": map_payload.get("ers_output_kw", 120.0),
                        "deployment_style": map_payload.get("deployment_style", "balanced"),
                    },
                })

        errors: list[str] = []
        if not circuit_key:
            errors.append("No active circuit selected")

        return {
            "circuit_id": circuit_key,
            "circuit_name": str(meta.get("circuit_name") or circuit_key or "No Active Circuit"),
            "source_file": str(source_path) if circuit_key else None,
            "source_file_name": source_path.name if circuit_key else None,
            "maps": catalog,
            "errors": errors,
        }

    @classmethod
    def build_catalog(cls, circuit_id: Optional[str], selected_map_id: Optional[str] = None) -> Dict[str, Any]:
        circuit_key = str(circuit_id or "").strip()
        source_path, raw_data = cls.load_raw_data(circuit_key)
        meta = copy.deepcopy(raw_data.get("_meta") or {}) if isinstance(raw_data, dict) else {}
        maps_raw = raw_data.get("maps", {}) if isinstance(raw_data, dict) else {}
        budget_root = raw_data.get("ers_budget", {}) if isinstance(raw_data, dict) else {}
        budget_root = cls._merge_budget_root(budget_root if isinstance(budget_root, dict) else {}, None)
        budget_maps = budget_root.get("maps", {}) if isinstance(budget_root, dict) and isinstance(budget_root.get("maps", {}), dict) else {}

        if circuit_key:
            meta.setdefault("circuit_id", circuit_key)
            meta.setdefault("circuit_name", meta.get("circuit_name") or circuit_key)
        else:
            meta.setdefault("circuit_name", "No Active Circuit")

        battery_capacity = cls._coerce_float(budget_root.get("battery_capacity_mj"), 4.0)
        deploy_limit = cls._coerce_float(budget_root.get("deploy_limit_mj"), 4.0)
        harvest_limit = cls._coerce_float(budget_root.get("harvest_limit_mj"), 2.0)

        catalog: list[Dict[str, Any]] = []
        # Use budget_maps (ers_budget.maps) as the source of truth for ERS maps
        # This ensures we show all ERS maps including RECHARGE, STANDARD, OVERTAKE, DEFENCE
        ers_maps_source = budget_maps if isinstance(budget_maps, dict) and budget_maps else maps_raw
        if isinstance(ers_maps_source, dict):
            for order, (map_id, budget_entry) in enumerate(ers_maps_source.items()):
                # Get the map data from top-level maps if available, otherwise use defaults
                raw_map_entry = maps_raw.get(map_id, {}) if isinstance(maps_raw, dict) else {}
                map_payload = cls._merge_payload(
                    raw_map_entry,
                    None,
                    cls.DEFAULT_MAP_PAYLOAD,
                )
                cls._migrate_legacy_bucket_es_deploy(map_payload, raw_map_entry)
                budget_payload = cls._merge_payload(
                    budget_entry if isinstance(budget_entry, dict) else {},
                    None,
                    cls.DEFAULT_BUDGET_PAYLOAD,
                )
                cls._sync_mirrors(map_payload, budget_payload, budget_root if isinstance(budget_root, dict) else {})
                catalog.append({
                    "id": map_id,
                    "label": cls._friendly_label(map_id),
                    "order": order,
                    "is_builtin": map_id in cls.BUILTIN_MAP_IDS,
                    "map_data": map_payload,
                    "budget_data": budget_payload,
                    "summary": cls._build_summary(map_payload, budget_payload, budget_root if isinstance(budget_root, dict) else {}),
                })

        selected = selected_map_id if selected_map_id and any(item["id"] == selected_map_id for item in catalog) else None
        if selected is None and catalog:
            selected = catalog[0]["id"]
        selected_map = next((item for item in catalog if item["id"] == selected), None)

        errors: list[str] = []
        if not circuit_key:
            errors.append("No active circuit selected")

        return {
            "circuit_id": circuit_key,
            "circuit_name": str(meta.get("circuit_name") or circuit_key or "No Active Circuit"),
            "source_file": str(source_path) if circuit_key else None,
            "source_file_name": source_path.name if circuit_key else None,
            "battery_capacity_mj": battery_capacity,
            "deploy_limit_mj": deploy_limit,
            "harvest_limit_mj": harvest_limit,
            "regen_profile": copy.deepcopy(raw_data.get("regen_profile") or {}),
            "ers_budget": copy.deepcopy(budget_root) if isinstance(budget_root, dict) else {},
            "soc_warnings": list(raw_data.get("soc_warnings") or []),
            "maps": catalog,
            "selected_map_id": selected,
            "selected_map": selected_map,
            "errors": errors,
        }

    @classmethod
    def save_map(
        cls,
        circuit_id: str,
        map_id: str,
        map_updates: Optional[Dict[str, Any]] = None,
        budget_updates: Optional[Dict[str, Any]] = None,
        budget_root_updates: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        circuit_key = str(circuit_id or "").strip()
        if not circuit_key:
            raise ValueError("circuit_id is required")

        derived_path, _ = cls._config_paths(circuit_key)
        _, raw_data = cls.load_raw_data(circuit_key)
        raw_data = copy.deepcopy(raw_data)
        raw_data.setdefault("_meta", {})["circuit_id"] = circuit_key
        raw_data["_meta"].setdefault("circuit_name", circuit_key)

        maps = raw_data.setdefault("maps", {})
        budget_root = cls._merge_budget_root(raw_data.setdefault("ers_budget", {}), budget_root_updates)
        raw_data["ers_budget"] = budget_root
        budget_maps = budget_root.setdefault("maps", {})
        map_key = str(map_id or "").strip()
        if not map_key:
            raise ValueError("map_id is required")

        source_map = maps.get(map_key)
        merged_map = cls._merge_payload(source_map, map_updates, cls.DEFAULT_MAP_PAYLOAD)
        cls._migrate_legacy_bucket_es_deploy(merged_map, source_map if isinstance(source_map, dict) else None, map_updates)
        merged_budget = cls._merge_payload(budget_maps.get(map_key), budget_updates, cls.DEFAULT_BUDGET_PAYLOAD)
        cls._sync_mirrors(merged_map, merged_budget, budget_root)

        validation_errors = cls.validate_map_payload(merged_map, merged_budget, budget_root)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))

        maps[map_key] = merged_map
        budget_maps[map_key] = merged_budget
        cls._write_json(derived_path, raw_data)
        return cls.build_catalog(circuit_key, selected_map_id=map_key)

    @classmethod
    def create_map(
        cls,
        circuit_id: str,
        map_id: str,
        source_map_id: Optional[str] = None,
        map_updates: Optional[Dict[str, Any]] = None,
        budget_updates: Optional[Dict[str, Any]] = None,
        budget_root_updates: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        circuit_key = str(circuit_id or "").strip()
        if not circuit_key:
            raise ValueError("circuit_id is required")

        derived_path, _ = cls._config_paths(circuit_key)
        _, raw_data = cls.load_raw_data(circuit_key)
        raw_data = copy.deepcopy(raw_data)
        raw_data.setdefault("_meta", {})["circuit_id"] = circuit_key
        raw_data["_meta"].setdefault("circuit_name", circuit_key)

        maps = raw_data.setdefault("maps", {})
        budget_root = cls._merge_budget_root(raw_data.setdefault("ers_budget", {}), budget_root_updates)
        raw_data["ers_budget"] = budget_root
        budget_maps = budget_root.setdefault("maps", {})
        map_key = str(map_id or "").strip()
        if not map_key:
            raise ValueError("map_id is required")
        if map_key in maps or map_key in budget_maps:
            raise ValueError(f"ERS map {map_key} already exists")

        source_key = str(source_map_id or "").strip()
        source_map = maps.get(source_key) if source_key else None
        source_budget = budget_maps.get(source_key) if source_key else None

        merged_map = cls._merge_payload(source_map, map_updates, cls.DEFAULT_MAP_PAYLOAD)
        cls._migrate_legacy_bucket_es_deploy(merged_map, source_map if isinstance(source_map, dict) else None, map_updates)
        merged_budget = cls._merge_payload(source_budget, budget_updates, cls.DEFAULT_BUDGET_PAYLOAD)
        cls._sync_mirrors(merged_map, merged_budget, budget_root)

        validation_errors = cls.validate_map_payload(merged_map, merged_budget, budget_root)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))

        maps[map_key] = merged_map
        budget_maps[map_key] = merged_budget
        cls._write_json(derived_path, raw_data)
        return cls.build_catalog(circuit_key, selected_map_id=map_key)

    @classmethod
    def delete_map(cls, circuit_id: str, map_id: str) -> Dict[str, Any]:
        circuit_key = str(circuit_id or "").strip()
        if not circuit_key:
            raise ValueError("circuit_id is required")

        map_key = str(map_id or "").strip()
        if not map_key:
            raise ValueError("map_id is required")
        if map_key in cls.BUILTIN_MAP_IDS:
            raise ValueError("Built-in ERS maps cannot be deleted")

        derived_path, _ = cls._config_paths(circuit_key)
        _, raw_data = cls.load_raw_data(circuit_key)
        raw_data = copy.deepcopy(raw_data)
        maps = raw_data.setdefault("maps", {})
        budget_root = cls._merge_budget_root(raw_data.setdefault("ers_budget", {}), None)
        raw_data["ers_budget"] = budget_root
        budget_maps = budget_root.setdefault("maps", {})
        maps.pop(map_key, None)
        budget_maps.pop(map_key, None)
        cls._write_json(derived_path, raw_data)
        return cls.build_catalog(circuit_key, selected_map_id=next(iter(maps.keys()), None))
