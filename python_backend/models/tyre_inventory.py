"""Tyre inventory models for per-driver allocation tracking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


COMPOUND_LABELS = {
    "soft": "S",
    "medium": "M",
    "hard": "H",
    "intermediate": "I",
    "wet": "W",
}


def _normalize_compound(compound: Optional[str]) -> str:
    if not compound:
        return "unknown"
    compound = str(compound).lower().strip()
    return compound if compound in COMPOUND_LABELS else compound


@dataclass
class TyreSet:
    """Represents a single tyre set assigned to a driver."""

    set_id: str
    compound: str
    condition: float = 100.0  # percentage 0-100
    heat_cycles: int = 0
    laps_completed: int = 0
    is_available: bool = True
    is_q3_reserve: bool = False
    # Graining/blistering state (reset when set becomes available)
    graining_level: float = 0.0
    blistering_level: float = 0.0
    graining_time_acc_s: float = 0.0
    blistering_time_acc_s: float = 0.0

    def apply_usage(self, laps: int, wear_factor: float = 1.0) -> None:
        """Apply wear to the set after a session run."""

        laps = max(0, int(laps))
        wear_factor = max(0.1, float(wear_factor))
        if laps == 0:
            return

        wear_delta = laps * wear_factor * 1.5
        self.condition = max(0.0, self.condition - wear_delta)
        self.heat_cycles += 1
        self.laps_completed += laps
        if self.condition <= 0.0:
            self.is_available = False

    def reset_graining_blistering(self) -> None:
        """Reset graining/blistering accumulators and levels."""
        self.graining_level = 0.0
        self.blistering_level = 0.0
        self.graining_time_acc_s = 0.0
        self.blistering_time_acc_s = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "set_id": self.set_id,
            "compound": self.compound,
            "condition": round(self.condition, 2),
            "heat_cycles": self.heat_cycles,
            "laps_completed": self.laps_completed,
            "is_available": self.is_available,
            "is_q3_reserve": self.is_q3_reserve,
            "graining_level": round(self.graining_level, 3),
            "blistering_level": round(self.blistering_level, 3),
            "graining_time_acc_s": round(self.graining_time_acc_s, 1),
            "blistering_time_acc_s": round(self.blistering_time_acc_s, 1),
        }

    @staticmethod
    def from_dict(payload: Dict[str, object]) -> "TyreSet":
        return TyreSet(
            set_id=str(payload.get("set_id")),
            compound=_normalize_compound(payload.get("compound")),
            condition=float(payload.get("condition", 100.0)),
            heat_cycles=int(payload.get("heat_cycles", 0)),
            laps_completed=int(payload.get("laps_completed", 0)),
            is_available=bool(payload.get("is_available", True)),
            is_q3_reserve=bool(payload.get("is_q3_reserve", False)),
            graining_level=float(payload.get("graining_level", 0.0)),
            blistering_level=float(payload.get("blistering_level", 0.0)),
            graining_time_acc_s=float(payload.get("graining_time_acc_s", 0.0)),
            blistering_time_acc_s=float(payload.get("blistering_time_acc_s", 0.0)),
        )


@dataclass
class DriverTyreInventory:
    """Complete tyre inventory state for a driver on a given circuit."""

    driver_id: str
    circuit_id: str
    allocation: Dict[str, object]
    sets: List[TyreSet] = field(default_factory=list)

    @staticmethod
    def _build_sets_from_allocation(allocation: Dict[str, object]) -> List[TyreSet]:
        sets: List[TyreSet] = []
        dry_allocation = allocation.get("dry_allocation", {}) or {}
        wet_allocation = allocation.get("wet_allocation", {}) or {}

        def _create_sets(compound: str, count: int) -> List[TyreSet]:
            compound = _normalize_compound(compound)
            prefix = COMPOUND_LABELS.get(compound, compound[:1].upper())
            created: List[TyreSet] = []
            for idx in range(1, count + 1):
                set_id = f"{prefix}{idx}"
                created.append(TyreSet(set_id=set_id, compound=compound))
            return created

        for compound, count in dry_allocation.items():
            sets.extend(_create_sets(compound, int(count)))

        for compound, count in wet_allocation.items():
            sets.extend(_create_sets(compound, int(count)))

        # Mark Q3 reserve on final soft set if present
        soft_sets = [s for s in sets if s.compound == "soft"]
        if soft_sets and allocation.get("special_rules", {}).get("q3_soft_reserve", False):
            soft_sets[-1].is_q3_reserve = True

        return sets

    @classmethod
    def create(cls, driver_id: str, circuit_id: str, allocation: Dict[str, object]) -> "DriverTyreInventory":
        sets = cls._build_sets_from_allocation(allocation)
        return cls(driver_id=driver_id, circuit_id=circuit_id, allocation=allocation, sets=sets)

    def to_dict(self) -> Dict[str, object]:
        return {
            "driver_id": self.driver_id,
            "circuit_id": self.circuit_id,
            "allocation": self.allocation,
            "sets": [s.to_dict() for s in self.sets],
        }

    @staticmethod
    def from_dict(payload: Dict[str, object]) -> "DriverTyreInventory":
        inventory = DriverTyreInventory(
            driver_id=str(payload.get("driver_id")),
            circuit_id=str(payload.get("circuit_id")),
            allocation=payload.get("allocation", {}),
            sets=[],
        )
        for s in payload.get("sets", []):
            inventory.sets.append(TyreSet.from_dict(s))
        return inventory

    def find_set(self, set_id: str) -> Optional[TyreSet]:
        for tyre_set in self.sets:
            if tyre_set.set_id == set_id:
                return tyre_set
        return None
