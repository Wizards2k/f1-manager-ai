"""Service layer for driver-specific tyre inventories."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from models.tyre_inventory import DriverTyreInventory, TyreSet


class TyreInventoryService:
    """Handles loading, persisting, and updating driver tyre inventories."""

    def __init__(self, data_root: Optional[Path] = None):
        base_path = data_root or Path(__file__).resolve().parents[1]
        self._telemetry_dir = base_path / "data" / "circuits" / "2025"
        self._store_path = base_path / "data" / "tyre_inventories.json"
        self._store_cache: Optional[Dict[str, Dict[str, object]]] = None
        self._inventory_cache: Dict[str, DriverTyreInventory] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_store(self) -> Dict[str, Dict[str, object]]:
        if self._store_cache is not None:
            return self._store_cache

        if self._store_path.exists():
            self._store_cache = json.loads(self._store_path.read_text(encoding="utf-8"))
        else:
            self._store_cache = {}
        return self._store_cache

    def _save_store(self) -> None:
        if self._store_cache is None:
            return
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(
            json.dumps(self._store_cache, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _inventory_key(self, driver_id: str, circuit_id: str) -> str:
        return f"{driver_id}:{circuit_id}"

    def _load_telemetry_allocation(self, circuit_id: str) -> Dict[str, object]:
        file_path = self._telemetry_dir / f"{circuit_id}_Telemetry.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Telemetry file not found for circuit {circuit_id}")

        telemetry = json.loads(file_path.read_text(encoding="utf-8"))
        allocation = telemetry.get("tyre_allocation")
        if not allocation:
            raise ValueError(f"Circuit {circuit_id} is missing tyre_allocation data")
        return allocation

    def _persist_inventory(self, inventory: DriverTyreInventory) -> None:
        store = self._load_store()
        store[self._inventory_key(inventory.driver_id, inventory.circuit_id)] = inventory.to_dict()
        self._save_store()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_inventory(self, driver_id: str, circuit_id: str) -> DriverTyreInventory:
        key = self._inventory_key(driver_id, circuit_id)
        if key in self._inventory_cache:
            return self._inventory_cache[key]

        store = self._load_store()
        if key in store:
            inventory = DriverTyreInventory.from_dict(store[key])
        else:
            allocation = self._load_telemetry_allocation(circuit_id)
            inventory = DriverTyreInventory.create(driver_id, circuit_id, allocation)
            store[key] = inventory.to_dict()
            self._save_store()

        self._inventory_cache[key] = inventory
        return inventory

    def apply_usage(
        self,
        driver_id: str,
        circuit_id: str,
        set_id: str,
        laps: int,
        wear_factor: float = 1.0,
    ) -> TyreSet:
        inventory = self.get_inventory(driver_id, circuit_id)
        tyre_set = inventory.find_set(set_id)
        if tyre_set is None:
            raise ValueError(f"Tyre set {set_id} not found for driver {driver_id}")

        tyre_set.apply_usage(laps=laps, wear_factor=wear_factor)
        self._persist_inventory(inventory)
        return tyre_set

    def mark_availability(
        self,
        driver_id: str,
        circuit_id: str,
        set_id: str,
        *,
        available: bool,
    ) -> TyreSet:
        """Toggle availability (e.g. when reserving a set for a stint)."""

        inventory = self.get_inventory(driver_id, circuit_id)
        tyre_set = inventory.find_set(set_id)
        if tyre_set is None:
            raise ValueError(f"Tyre set {set_id} not found for driver {driver_id}")

        tyre_set.is_available = bool(available)
        self._persist_inventory(inventory)
        return tyre_set

    def reserve_best_available_set(
        self,
        driver_id: str,
        circuit_id: str,
        compound: str,
        preferred_set_id: Optional[str] = None,
        minimum_condition: float = 40.0,
    ) -> TyreSet:
        """Reserve the best currently available set for the requested compound."""

        inventory = self.get_inventory(driver_id, circuit_id)
        compound_key = str(compound or "").strip().lower()
        candidates = [
            tyre_set for tyre_set in inventory.sets
            if tyre_set.compound == compound_key
            and tyre_set.is_available
            and float(tyre_set.condition or 0.0) >= float(minimum_condition)
        ]
        if not candidates:
            raise ValueError(
                f"No available tyre sets for driver {driver_id} compound {compound_key}"
            )

        candidates.sort(
            key=lambda tyre_set: (
                tyre_set.set_id != preferred_set_id,
                tyre_set.is_q3_reserve,
                -(tyre_set.condition or 0.0),
                tyre_set.heat_cycles,
                tyre_set.laps_completed,
                tyre_set.set_id,
            )
        )
        tyre_set = candidates[0]
        tyre_set.is_available = False
        self._persist_inventory(inventory)
        return tyre_set

    def complete_stint(
        self,
        driver_id: str,
        circuit_id: str,
        set_id: str,
        laps: int,
        wear_factor: float = 1.0,
    ) -> TyreSet:
        """Apply stint usage and make the set available again for future runs."""

        inventory = self.get_inventory(driver_id, circuit_id)
        tyre_set = inventory.find_set(set_id)
        if tyre_set is None:
            raise ValueError(f"Tyre set {set_id} not found for driver {driver_id}")

        tyre_set.apply_usage(laps=laps, wear_factor=wear_factor)
        if tyre_set.condition >= 40.0:
            tyre_set.is_available = True
        else:
            tyre_set.is_available = False
        self._persist_inventory(inventory)
        return tyre_set
