from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RaceLapRecord:
    car_id: str
    lap_number: int = 0
    lap_time_s: float = 0.0
    timestamp_s: Optional[float] = None
    sector_times: Dict[str, float] = field(default_factory=dict)
    is_competitive: bool = True
    tyre_set_id: Optional[str] = None
    tyre_compound: Optional[str] = None
    tyre_condition_pct: Optional[float] = None
    tyre_is_q3_reserve: bool = False
    stint_target_laps: Optional[int] = None
    stint_laps_remaining: Optional[int] = None
    position: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "car_id": self.car_id,
            "lap_number": self.lap_number,
            "lap_time_s": self.lap_time_s,
            "timestamp_s": self.timestamp_s,
            "sector_times": dict(self.sector_times),
            "is_competitive": self.is_competitive,
            "tyre_set_id": self.tyre_set_id,
            "tyre_compound": self.tyre_compound,
            "tyre_condition_pct": self.tyre_condition_pct,
            "tyre_is_q3_reserve": self.tyre_is_q3_reserve,
            "stint_target_laps": self.stint_target_laps,
            "stint_laps_remaining": self.stint_laps_remaining,
            "position": self.position,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RaceLapRecord":
        return cls(
            car_id=str(data.get("car_id", "")),
            lap_number=int(data.get("lap_number", 0) or 0),
            lap_time_s=float(data.get("lap_time_s", 0.0) or 0.0),
            timestamp_s=data.get("timestamp_s"),
            sector_times={str(key): float(value) for key, value in (data.get("sector_times", {}) or {}).items()},
            is_competitive=bool(data.get("is_competitive", True)),
            tyre_set_id=data.get("tyre_set_id"),
            tyre_compound=data.get("tyre_compound"),
            tyre_condition_pct=data.get("tyre_condition_pct"),
            tyre_is_q3_reserve=bool(data.get("tyre_is_q3_reserve", False)),
            stint_target_laps=data.get("stint_target_laps"),
            stint_laps_remaining=data.get("stint_laps_remaining"),
            position=data.get("position"),
        )


@dataclass
class RaceDriverState:
    car_id: str
    driver_name: str = ""
    team_name: str = ""
    is_player: bool = False
    starting_position: Optional[int] = None
    current_position: Optional[int] = None
    laps_completed: int = 0
    total_time_s: float = 0.0
    best_lap_s: float = 0.0
    last_lap_s: float = 0.0
    last_lap_number: int = 0
    status: str = "running"
    pit_stops: int = 0
    current_stint_number: int = 1
    stint_target_laps: Optional[int] = None
    stint_laps_remaining: Optional[int] = None
    tyre_set_id: Optional[str] = None
    tyre_compound: Optional[str] = None
    tyre_condition_pct: Optional[float] = None
    tyre_is_q3_reserve: bool = False
    finish_position: Optional[int] = None
    finished_at_s: Optional[float] = None
    retirement_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {**self.__dict__}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RaceDriverState":
        return cls(
            car_id=str(data.get("car_id", "")),
            driver_name=str(data.get("driver_name", "") or ""),
            team_name=str(data.get("team_name", "") or ""),
            is_player=bool(data.get("is_player", False)),
            starting_position=data.get("starting_position"),
            current_position=data.get("current_position"),
            laps_completed=int(data.get("laps_completed", 0) or 0),
            total_time_s=float(data.get("total_time_s", 0.0) or 0.0),
            best_lap_s=float(data.get("best_lap_s", 0.0) or 0.0),
            last_lap_s=float(data.get("last_lap_s", 0.0) or 0.0),
            last_lap_number=int(data.get("last_lap_number", 0) or 0),
            status=str(data.get("status", "running") or "running"),
            pit_stops=int(data.get("pit_stops", 0) or 0),
            current_stint_number=int(data.get("current_stint_number", 1) or 1),
            stint_target_laps=data.get("stint_target_laps"),
            stint_laps_remaining=data.get("stint_laps_remaining"),
            tyre_set_id=data.get("tyre_set_id"),
            tyre_compound=data.get("tyre_compound"),
            tyre_condition_pct=data.get("tyre_condition_pct"),
            tyre_is_q3_reserve=bool(data.get("tyre_is_q3_reserve", False)),
            finish_position=data.get("finish_position"),
            finished_at_s=data.get("finished_at_s"),
            retirement_reason=str(data.get("retirement_reason", "") or ""),
        )


@dataclass
class RaceSessionState:
    session_type: str = "RACE"
    circuit_id: Optional[str] = None
    status: str = "idle"
    started_at_s: Optional[float] = None
    finished_at_s: Optional[float] = None
    participants: Dict[str, RaceDriverState] = field(default_factory=dict)
    starting_grid: List[Dict[str, Any]] = field(default_factory=list)
    running_order: List[Dict[str, Any]] = field(default_factory=list)
    lap_records: List[RaceLapRecord] = field(default_factory=list)
    pit_stops: List[Dict[str, Any]] = field(default_factory=list)
    classification: List[Dict[str, Any]] = field(default_factory=list)
    leader_car_id: Optional[str] = None
    is_complete: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def _get_field(source: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(source, dict):
            return source.get(field_name, default)
        return getattr(source, field_name, default)

    def _ensure_participant(self, car_id: Any) -> RaceDriverState:
        key = str(car_id)
        participant = self.participants.get(key)
        if participant is None:
            participant = RaceDriverState(car_id=key)
            self.participants[key] = participant
        return participant

    def _ordered_participants(self) -> List[RaceDriverState]:
        return sorted(
            self.participants.values(),
            key=lambda participant: (
                participant.current_position if participant.current_position is not None else 10_000,
                participant.starting_position if participant.starting_position is not None else 10_000,
                participant.car_id,
            ),
        )

    def _update_running_order(self) -> None:
        ordered = self._ordered_participants()
        self.running_order = [participant.to_dict() for participant in ordered]
        self.leader_car_id = ordered[0].car_id if ordered else None

    def start(
        self,
        participants: List[Any],
        circuit_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        starting_grid: Optional[List[Dict[str, Any]]] = None,
        started_at_s: Optional[float] = None,
    ) -> "RaceSessionState":
        self.circuit_id = circuit_id or self.circuit_id
        if metadata:
            self.metadata.update(metadata)

        self.started_at_s = started_at_s
        self.finished_at_s = None
        self.status = "active"
        self.is_complete = False
        self.classification = []
        self.lap_records = []
        self.pit_stops = []
        self.running_order = []
        self.leader_car_id = None

        grid_lookup: Dict[str, Dict[str, Any]] = {}
        ordered_grid: List[Dict[str, Any]] = []
        if starting_grid:
            for index, row in enumerate(starting_grid, start=1):
                normalized_row = dict(row or {})
                car_id = str(normalized_row.get("car_id", ""))
                if not car_id:
                    continue
                normalized_row["car_id"] = car_id
                position = normalized_row.get("position", normalized_row.get("grid_position", index))
                normalized_row["position"] = int(position or index)
                ordered_grid.append(normalized_row)
                grid_lookup[car_id] = normalized_row

        for index, participant in enumerate(participants, start=1):
            car_id = str(self._get_field(participant, "car_id", self._get_field(participant, "driver_number", "")))
            if not car_id:
                continue

            participant_row = {
                "car_id": car_id,
                "driver_name": str(self._get_field(participant, "driver_name", "") or ""),
                "team_name": str(self._get_field(participant, "team_name", "") or ""),
                "is_player": bool(self._get_field(participant, "is_player", False)),
            }
            already_in_grid = car_id in grid_lookup
            grid_row = dict(grid_lookup.get(car_id, {}))
            grid_row.update(participant_row)
            if "position" not in grid_row:
                grid_row["position"] = index
            grid_lookup[car_id] = grid_row
            if not already_in_grid:
                ordered_grid.append(grid_row)

            state = RaceDriverState(
                car_id=car_id,
                driver_name=grid_row["driver_name"],
                team_name=grid_row["team_name"],
                is_player=grid_row["is_player"],
                starting_position=int(grid_row.get("position", index) or index),
                current_position=int(grid_row.get("position", index) or index),
                tyre_set_id=self._get_field(participant, "tyre_set_id", grid_row.get("tyre_set_id")),
                tyre_compound=self._get_field(participant, "tyre_compound", grid_row.get("tyre_compound")),
                tyre_condition_pct=self._get_field(participant, "tyre_condition_pct", grid_row.get("tyre_condition_pct")),
                tyre_is_q3_reserve=bool(self._get_field(participant, "tyre_is_q3_reserve", grid_row.get("tyre_is_q3_reserve", False))),
                stint_target_laps=self._get_field(participant, "stint_target_laps", grid_row.get("stint_target_laps")),
                stint_laps_remaining=self._get_field(participant, "stint_laps_remaining", grid_row.get("stint_laps_remaining")),
            )
            self.participants[car_id] = state

        self.starting_grid = sorted(
            ordered_grid,
            key=lambda row: (int(row.get("position", 10_000) or 10_000), str(row.get("car_id", ""))),
        )
        self._update_running_order()
        return self

    def record_lap(
        self,
        car_id: Any,
        lap_time_s: float,
        lap_number: int,
        timestamp_s: Optional[float] = None,
        sector_times: Optional[Dict[str, float]] = None,
        is_competitive: bool = True,
        tyre_set_id: Optional[str] = None,
        tyre_compound: Optional[str] = None,
        tyre_condition_pct: Optional[float] = None,
        tyre_is_q3_reserve: bool = False,
        stint_target_laps: Optional[int] = None,
        stint_laps_remaining: Optional[int] = None,
        position: Optional[int] = None,
    ) -> RaceLapRecord:
        participant = self._ensure_participant(car_id)
        participant.laps_completed += 1
        participant.total_time_s += float(lap_time_s)
        participant.last_lap_s = float(lap_time_s)
        participant.last_lap_number = int(lap_number)
        if participant.best_lap_s <= 0 or float(lap_time_s) < participant.best_lap_s:
            participant.best_lap_s = float(lap_time_s)
        if position is not None:
            participant.current_position = int(position)
        if tyre_set_id is not None:
            participant.tyre_set_id = str(tyre_set_id)
        if tyre_compound is not None:
            participant.tyre_compound = str(tyre_compound)
        if tyre_condition_pct is not None:
            participant.tyre_condition_pct = float(tyre_condition_pct)
        participant.tyre_is_q3_reserve = bool(tyre_is_q3_reserve)
        if stint_target_laps is not None:
            participant.stint_target_laps = int(stint_target_laps)
        if stint_laps_remaining is not None:
            participant.stint_laps_remaining = int(stint_laps_remaining)
        if participant.status == "scheduled":
            participant.status = "running"

        record = RaceLapRecord(
            car_id=str(car_id),
            lap_number=int(lap_number),
            lap_time_s=float(lap_time_s),
            timestamp_s=timestamp_s,
            sector_times=dict(sector_times or {}),
            is_competitive=bool(is_competitive),
            tyre_set_id=participant.tyre_set_id,
            tyre_compound=participant.tyre_compound,
            tyre_condition_pct=participant.tyre_condition_pct,
            tyre_is_q3_reserve=participant.tyre_is_q3_reserve,
            stint_target_laps=participant.stint_target_laps,
            stint_laps_remaining=participant.stint_laps_remaining,
            position=participant.current_position,
        )
        self.lap_records.append(record)
        self._update_running_order()
        return record

    def record_pit_stop(
        self,
        car_id: Any,
        timestamp_s: Optional[float] = None,
        reason: Optional[str] = None,
        tyre_set_id: Optional[str] = None,
        tyre_compound: Optional[str] = None,
        tyre_condition_pct: Optional[float] = None,
        tyre_is_q3_reserve: bool = False,
        stint_target_laps: Optional[int] = None,
        stint_laps_remaining: Optional[int] = None,
    ) -> Dict[str, Any]:
        participant = self._ensure_participant(car_id)
        participant.pit_stops += 1
        participant.current_stint_number += 1
        participant.status = "pit"
        if tyre_set_id is not None:
            participant.tyre_set_id = str(tyre_set_id)
        if tyre_compound is not None:
            participant.tyre_compound = str(tyre_compound)
        if tyre_condition_pct is not None:
            participant.tyre_condition_pct = float(tyre_condition_pct)
        participant.tyre_is_q3_reserve = bool(tyre_is_q3_reserve)
        if stint_target_laps is not None:
            participant.stint_target_laps = int(stint_target_laps)
        if stint_laps_remaining is not None:
            participant.stint_laps_remaining = int(stint_laps_remaining)

        pit_stop = {
            "car_id": str(car_id),
            "timestamp_s": timestamp_s,
            "reason": reason,
            "pit_stops": participant.pit_stops,
            "current_stint_number": participant.current_stint_number,
            "tyre_set_id": participant.tyre_set_id,
            "tyre_compound": participant.tyre_compound,
            "tyre_condition_pct": participant.tyre_condition_pct,
            "tyre_is_q3_reserve": participant.tyre_is_q3_reserve,
            "stint_target_laps": participant.stint_target_laps,
            "stint_laps_remaining": participant.stint_laps_remaining,
        }
        self.pit_stops.append(pit_stop)
        self._update_running_order()
        return pit_stop

    def set_running_order(self, order: List[Any], timestamp_s: Optional[float] = None) -> None:
        for index, car_id in enumerate(order, start=1):
            participant = self._ensure_participant(car_id)
            participant.current_position = index
        self._update_running_order()
        if timestamp_s is not None:
            self.finished_at_s = self.finished_at_s if self.finished_at_s is not None else None

    def mark_retired(self, car_id: Any, reason: str = "", timestamp_s: Optional[float] = None) -> None:
        participant = self._ensure_participant(car_id)
        participant.status = "retired"
        participant.retirement_reason = reason
        participant.finished_at_s = timestamp_s
        self._update_running_order()

    def finalize_session(self, finished_at_s: Optional[float] = None) -> List[Dict[str, Any]]:
        self.finished_at_s = finished_at_s
        ordered = sorted(
            self.participants.values(),
            key=lambda participant: (
                -int(participant.laps_completed),
                participant.total_time_s if participant.total_time_s > 0 else 10**9,
                participant.best_lap_s if participant.best_lap_s > 0 else 10**9,
                participant.starting_position if participant.starting_position is not None else 10**6,
                participant.car_id,
            ),
        )

        classification: List[Dict[str, Any]] = []
        leader_laps = ordered[0].laps_completed if ordered else 0
        leader_time = ordered[0].total_time_s if ordered else 0.0
        previous_same_lap_time: Optional[float] = None

        for position, participant in enumerate(ordered, start=1):
            if participant.status != "retired":
                participant.status = "finished"
            participant.finish_position = position
            if participant.finished_at_s is None:
                participant.finished_at_s = finished_at_s

            laps_behind = max(0, leader_laps - participant.laps_completed)
            gap_to_leader_s: Optional[float] = None
            if laps_behind == 0:
                gap_to_leader_s = round(max(0.0, participant.total_time_s - leader_time), 3)

            interval_to_ahead_s: Optional[float] = None
            if previous_same_lap_time is not None and participant.laps_completed == leader_laps:
                interval_to_ahead_s = round(max(0.0, participant.total_time_s - previous_same_lap_time), 3)
            elif participant.laps_completed == leader_laps:
                interval_to_ahead_s = 0.0

            previous_same_lap_time = participant.total_time_s if participant.laps_completed == leader_laps else previous_same_lap_time

            classification.append(
                {
                    "position": position,
                    "car_id": participant.car_id,
                    "driver_name": participant.driver_name,
                    "team_name": participant.team_name,
                    "is_player": participant.is_player,
                    "status": participant.status,
                    "starting_position": participant.starting_position,
                    "current_position": participant.current_position,
                    "laps_completed": participant.laps_completed,
                    "total_time_s": round(participant.total_time_s, 3),
                    "best_lap_s": round(participant.best_lap_s, 3) if participant.best_lap_s > 0 else 0.0,
                    "last_lap_s": round(participant.last_lap_s, 3) if participant.last_lap_s > 0 else 0.0,
                    "last_lap_number": participant.last_lap_number,
                    "pit_stops": participant.pit_stops,
                    "current_stint_number": participant.current_stint_number,
                    "stint_target_laps": participant.stint_target_laps,
                    "stint_laps_remaining": participant.stint_laps_remaining,
                    "tyre_set_id": participant.tyre_set_id,
                    "tyre_compound": participant.tyre_compound,
                    "tyre_condition_pct": participant.tyre_condition_pct,
                    "tyre_is_q3_reserve": participant.tyre_is_q3_reserve,
                    "finish_position": participant.finish_position,
                    "finished_at_s": participant.finished_at_s,
                    "retirement_reason": participant.retirement_reason,
                    "gap_to_leader_laps": laps_behind,
                    "gap_to_leader_s": gap_to_leader_s,
                    "interval_to_ahead_s": interval_to_ahead_s,
                }
            )

        self.classification = classification
        self.is_complete = True
        self.status = "completed"
        self.leader_car_id = classification[0]["car_id"] if classification else None
        self._update_running_order()
        return classification

    def summary(self) -> Dict[str, Any]:
        return {
            "session_type": self.session_type,
            "status": self.status,
            "circuit_id": self.circuit_id,
            "started_at_s": self.started_at_s,
            "finished_at_s": self.finished_at_s,
            "participants": len(self.participants),
            "participants_state": {car_id: participant.to_dict() for car_id, participant in self.participants.items()},
            "starting_grid": list(self.starting_grid),
            "running_order": list(self.running_order),
            "lap_records": [record.to_dict() for record in self.lap_records],
            "pit_stops": list(self.pit_stops),
            "classification": list(self.classification),
            "leader_car_id": self.leader_car_id,
            "is_complete": self.is_complete,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_type": self.session_type,
            "circuit_id": self.circuit_id,
            "status": self.status,
            "started_at_s": self.started_at_s,
            "finished_at_s": self.finished_at_s,
            "participants": {car_id: participant.to_dict() for car_id, participant in self.participants.items()},
            "starting_grid": list(self.starting_grid),
            "running_order": list(self.running_order),
            "lap_records": [record.to_dict() for record in self.lap_records],
            "pit_stops": list(self.pit_stops),
            "classification": list(self.classification),
            "leader_car_id": self.leader_car_id,
            "is_complete": self.is_complete,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RaceSessionState":
        return cls(
            session_type=str(data.get("session_type", "RACE") or "RACE"),
            circuit_id=data.get("circuit_id"),
            status=str(data.get("status", "idle") or "idle"),
            started_at_s=data.get("started_at_s"),
            finished_at_s=data.get("finished_at_s"),
            participants={
                str(car_id): RaceDriverState.from_dict(participant)
                for car_id, participant in (data.get("participants", {}) or {}).items()
            },
            starting_grid=[dict(item) for item in data.get("starting_grid", []) or []],
            running_order=[dict(item) for item in data.get("running_order", []) or []],
            lap_records=[RaceLapRecord.from_dict(item) for item in data.get("lap_records", []) or []],
            pit_stops=[dict(item) for item in data.get("pit_stops", []) or []],
            classification=[dict(item) for item in data.get("classification", []) or []],
            leader_car_id=data.get("leader_car_id"),
            is_complete=bool(data.get("is_complete", False)),
            metadata=dict(data.get("metadata", {}) or {}),
        )


__all__ = [
    "RaceDriverState",
    "RaceLapRecord",
    "RaceSessionState",
]
