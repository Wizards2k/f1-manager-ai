from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional, Tuple

from .qualifying_session import (
    QualifyingLapRecord,
    QualifyingPhase,
    QualifyingPhaseState,
    QualifyingSessionState,
    normalize_qualifying_phase,
)
from .race_session import (
    RaceDriverState,
    RaceLapRecord,
    RaceSessionState,
)


class WeekendSessionType(str, Enum):
    FP1 = "FP1"
    FP2 = "FP2"
    FP3 = "FP3"
    QUALIFYING = "QUALIFYING"
    RACE = "RACE"


_SESSION_TYPE_ALIASES = {
    "Q": "QUALIFYING",
    "QUALI": "QUALIFYING",
    "QUALY": "QUALIFYING",
    "QUALIFY": "QUALIFYING",
}


DEFAULT_WEEKEND_SEQUENCE: Tuple[WeekendSessionType, ...] = (
    WeekendSessionType.FP1,
    WeekendSessionType.FP2,
    WeekendSessionType.FP3,
    WeekendSessionType.QUALIFYING,
    WeekendSessionType.RACE,
)


def normalize_weekend_session_type(value: Any) -> WeekendSessionType:
    if isinstance(value, WeekendSessionType):
        return value

    if value is None:
        raise ValueError("Weekend session type cannot be None")

    normalized = str(value).strip().upper()
    normalized = _SESSION_TYPE_ALIASES.get(normalized, normalized)

    for session_type in WeekendSessionType:
        if session_type.value == normalized:
            return session_type

    raise ValueError(f"Unsupported weekend session type: {value}")


def _build_default_sessions() -> List["WeekendSessionState"]:
    return [WeekendSessionState(session_type=session_type) for session_type in DEFAULT_WEEKEND_SEQUENCE]


@dataclass
class WeekendSessionState:
    session_type: WeekendSessionType
    status: str = "scheduled"
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    summary: Dict[str, Any] = field(default_factory=dict)

    def activate(self, timestamp: Optional[float] = None) -> None:
        now = timestamp if timestamp is not None else time.time()
        self.status = "active"
        if self.started_at is None:
            self.started_at = now
        self.finished_at = None

    def complete(
        self,
        summary: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
        merge: bool = True,
    ) -> None:
        now = timestamp if timestamp is not None else time.time()
        if summary:
            if merge:
                self.summary.update(summary)
            else:
                self.summary = dict(summary)
        if self.started_at is None:
            self.started_at = now
        self.status = "completed"
        self.finished_at = now

    def record_snapshot(self, snapshot: Optional[Dict[str, Any]] = None, merge: bool = True) -> None:
        if not snapshot:
            return
        if merge:
            self.summary.update(snapshot)
        else:
            self.summary = dict(snapshot)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_type": self.session_type.value,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeekendSessionState":
        session_type = normalize_weekend_session_type(data.get("session_type", WeekendSessionType.FP1.value))
        return cls(
            session_type=session_type,
            status=data.get("status", "scheduled"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            summary=dict(data.get("summary", {}) or {}),
        )


@dataclass
class WeekendOrchestrator:
    circuit_id: Optional[str] = None
    status: str = "idle"
    current_index: int = 0
    sessions: List[WeekendSessionState] = field(default_factory=_build_default_sessions)
    qualifying_state: Optional[QualifyingSessionState] = None
    race_state: Optional[RaceSessionState] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def _ensure_sessions(self) -> None:
        if not self.sessions:
            self.sessions = _build_default_sessions()

    def _index_for_session(self, session_type: Any) -> int:
        normalized = normalize_weekend_session_type(session_type)
        for index, session in enumerate(self.sessions):
            if session.session_type == normalized:
                return index
        raise ValueError(f"Session type {normalized.value} is not part of the weekend sequence")

    def _touch(self, timestamp: Optional[float] = None) -> None:
        self.updated_at = timestamp if timestamp is not None else time.time()

    def start(
        self,
        circuit_id: Optional[str] = None,
        session_type: Any = WeekendSessionType.FP1,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "WeekendOrchestrator":
        if circuit_id is not None:
            self.circuit_id = circuit_id
        if metadata:
            self.metadata.update(metadata)

        self.sessions = _build_default_sessions()
        self.qualifying_state = None
        self.race_state = None
        self.current_index = self._index_for_session(session_type)
        now = time.time()
        self.created_at = now
        self.updated_at = now
        self.status = "active"
        self.sessions[self.current_index].activate(now)
        return self

    @property
    def current_session(self) -> Optional[WeekendSessionState]:
        self._ensure_sessions()
        if 0 <= self.current_index < len(self.sessions):
            return self.sessions[self.current_index]
        return None

    @property
    def current_session_type(self) -> Optional[str]:
        session = self.current_session
        return session.session_type.value if session else None

    @property
    def next_session_type(self) -> Optional[str]:
        self._ensure_sessions()
        next_index = self.current_index + 1
        if 0 <= next_index < len(self.sessions):
            return self.sessions[next_index].session_type.value
        return None

    @property
    def is_complete(self) -> bool:
        return self.status == "completed" or all(session.status == "completed" for session in self.sessions)

    def get_session(self, session_type: Any) -> Optional[WeekendSessionState]:
        normalized = normalize_weekend_session_type(session_type)
        for session in self.sessions:
            if session.session_type == normalized:
                return session
        return None

    def set_current_session(self, session_type: Any, activate: bool = True, timestamp: Optional[float] = None) -> WeekendSessionState:
        self._ensure_sessions()
        self.current_index = self._index_for_session(session_type)
        now = timestamp if timestamp is not None else time.time()
        session = self.sessions[self.current_index]
        if activate:
            session.activate(now)
            self.status = "active"
        else:
            self.status = "idle"
        self._touch(now)
        return session

    def mark_current_session_completed(
        self,
        summary: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
        merge: bool = True,
    ) -> Optional[WeekendSessionState]:
        session = self.current_session
        if session is None:
            return None
        now = timestamp if timestamp is not None else time.time()
        session.complete(summary=summary, timestamp=now, merge=merge)
        self.status = "completed" if self.next_session_type is None else "idle"
        self._touch(now)
        return session

    def advance_to_next_session(
        self,
        summary: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
        merge: bool = True,
    ) -> Optional[WeekendSessionState]:
        self.mark_current_session_completed(summary=summary, timestamp=timestamp, merge=merge)
        next_type = self.next_session_type
        if next_type is None:
            self.status = "completed"
            self._touch(timestamp)
            return None
        return self.set_current_session(next_type, activate=True, timestamp=timestamp)

    def record_session_snapshot(
        self,
        session_type: Any,
        snapshot: Optional[Dict[str, Any]] = None,
        merge: bool = True,
    ) -> None:
        session = self.get_session(session_type)
        if session is None:
            return
        session.record_snapshot(snapshot, merge=merge)
        self._touch()

    def start_qualifying(
        self,
        participants: List[Any],
        metadata: Optional[Dict[str, Any]] = None,
        session_elapsed_s: float = 0.0,
    ) -> QualifyingSessionState:
        qualifying = QualifyingSessionState()
        qualifying.start(
            participants=participants,
            circuit_id=self.circuit_id,
            metadata=metadata,
            started_at_s=session_elapsed_s,
        )
        self.qualifying_state = qualifying
        self.record_session_snapshot(WeekendSessionType.QUALIFYING, qualifying.summary(), merge=False)
        self._touch(session_elapsed_s)
        return qualifying

    def record_qualifying_lap(
        self,
        car_id: Any,
        lap_time_s: float,
        lap_number: int,
        phase: Optional[Any] = None,
        timestamp_s: Optional[float] = None,
        sector_times: Optional[Dict[str, Any]] = None,
        is_competitive: bool = True,
        tyre_set_id: Optional[str] = None,
        tyre_compound: Optional[str] = None,
        tyre_condition_pct: Optional[float] = None,
        tyre_is_q3_reserve: bool = False,
    ) -> Optional[QualifyingLapRecord]:
        if self.qualifying_state is None:
            return None

        phase_to_use = phase or self.qualifying_state.current_phase
        record = self.qualifying_state.record_lap(
            car_id=car_id,
            lap_time_s=lap_time_s,
            lap_number=lap_number,
            phase=phase_to_use,
            timestamp_s=timestamp_s,
            sector_times=sector_times,
            is_competitive=is_competitive,
            tyre_set_id=tyre_set_id,
            tyre_compound=tyre_compound,
            tyre_condition_pct=tyre_condition_pct,
            tyre_is_q3_reserve=tyre_is_q3_reserve,
        )
        self.record_session_snapshot(WeekendSessionType.QUALIFYING, self.qualifying_state.summary(), merge=False)
        self._touch(timestamp_s)
        return record

    def advance_qualifying_phase(self, current_elapsed_s: float) -> List[str]:
        if self.qualifying_state is None:
            return []

        completed = self.qualifying_state.advance_if_elapsed(current_elapsed_s)
        if completed:
            self.record_session_snapshot(WeekendSessionType.QUALIFYING, self.qualifying_state.summary(), merge=False)
        self._touch(current_elapsed_s)
        return completed

    def finalize_qualifying(self, finished_at_s: Optional[float] = None) -> List[Dict[str, Any]]:
        if self.qualifying_state is None:
            return []

        grid = self.qualifying_state.finalize_session(finished_at_s=finished_at_s)
        self.record_session_snapshot(WeekendSessionType.QUALIFYING, self.qualifying_state.summary(), merge=False)
        self._touch(finished_at_s)
        return grid

    def get_qualifying_summary(self) -> Optional[Dict[str, Any]]:
        if self.qualifying_state is None:
            return None
        return self.qualifying_state.summary()

    def is_qualifying_driver_active(self, car_id: Any) -> bool:
        if self.qualifying_state is None:
            return False
        return self.qualifying_state.is_car_active(car_id)

    def start_race(
        self,
        participants: List[Any],
        metadata: Optional[Dict[str, Any]] = None,
        starting_grid: Optional[List[Dict[str, Any]]] = None,
        session_elapsed_s: float = 0.0,
    ) -> RaceSessionState:
        race = RaceSessionState()
        race.start(
            participants=participants,
            circuit_id=self.circuit_id,
            metadata=metadata,
            starting_grid=starting_grid,
            started_at_s=session_elapsed_s,
        )
        self.race_state = race
        self.record_session_snapshot(WeekendSessionType.RACE, race.summary(), merge=False)
        self._touch(session_elapsed_s)
        return race

    def record_race_lap(
        self,
        car_id: Any,
        lap_time_s: float,
        lap_number: int,
        timestamp_s: Optional[float] = None,
        sector_times: Optional[Dict[str, Any]] = None,
        is_competitive: bool = True,
        tyre_set_id: Optional[str] = None,
        tyre_compound: Optional[str] = None,
        tyre_condition_pct: Optional[float] = None,
        tyre_is_q3_reserve: bool = False,
        stint_target_laps: Optional[int] = None,
        stint_laps_remaining: Optional[int] = None,
        position: Optional[int] = None,
    ) -> Optional[RaceLapRecord]:
        if self.race_state is None:
            return None

        record = self.race_state.record_lap(
            car_id=car_id,
            lap_time_s=lap_time_s,
            lap_number=lap_number,
            timestamp_s=timestamp_s,
            sector_times=sector_times,
            is_competitive=is_competitive,
            tyre_set_id=tyre_set_id,
            tyre_compound=tyre_compound,
            tyre_condition_pct=tyre_condition_pct,
            tyre_is_q3_reserve=tyre_is_q3_reserve,
            stint_target_laps=stint_target_laps,
            stint_laps_remaining=stint_laps_remaining,
            position=position,
        )
        self.record_session_snapshot(WeekendSessionType.RACE, self.race_state.summary(), merge=False)
        self._touch(timestamp_s)
        return record

    def record_race_pit_stop(
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
    ) -> Optional[Dict[str, Any]]:
        if self.race_state is None:
            return None

        pit_stop = self.race_state.record_pit_stop(
            car_id=car_id,
            timestamp_s=timestamp_s,
            reason=reason,
            tyre_set_id=tyre_set_id,
            tyre_compound=tyre_compound,
            tyre_condition_pct=tyre_condition_pct,
            tyre_is_q3_reserve=tyre_is_q3_reserve,
            stint_target_laps=stint_target_laps,
            stint_laps_remaining=stint_laps_remaining,
        )
        self.record_session_snapshot(WeekendSessionType.RACE, self.race_state.summary(), merge=False)
        self._touch(timestamp_s)
        return pit_stop

    def finalize_race(self, finished_at_s: Optional[float] = None) -> List[Dict[str, Any]]:
        if self.race_state is None:
            return []

        classification = self.race_state.finalize_session(finished_at_s=finished_at_s)
        self.record_session_snapshot(WeekendSessionType.RACE, self.race_state.summary(), merge=False)
        self._touch(finished_at_s)
        return classification

    def get_race_summary(self) -> Optional[Dict[str, Any]]:
        if self.race_state is None:
            return None
        return self.race_state.summary()

    def is_race_driver_active(self, car_id: Any) -> bool:
        if self.race_state is None:
            return False
        participant = self.race_state.participants.get(str(car_id))
        return participant is not None and participant.status not in {"retired", "finished"}

    def to_dict(self) -> Dict[str, Any]:
        self._ensure_sessions()
        return {
            "version": 1,
            "circuit_id": self.circuit_id,
            "status": self.status,
            "current_index": self.current_index,
            "current_session_type": self.current_session_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "sessions": [session.to_dict() for session in self.sessions],
            "qualifying_state": self.qualifying_state.to_dict() if self.qualifying_state else None,
            "race_state": self.race_state.to_dict() if self.race_state else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeekendOrchestrator":
        sessions_data = data.get("sessions") or []
        sessions = [WeekendSessionState.from_dict(item) for item in sessions_data]
        if not sessions:
            sessions = _build_default_sessions()

        orchestrator = cls(
            circuit_id=data.get("circuit_id"),
            status=data.get("status", "idle"),
            current_index=int(data.get("current_index", 0) or 0),
            sessions=sessions,
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=dict(data.get("metadata", {}) or {}),
        )

        qualifying_state_data = data.get("qualifying_state")
        if qualifying_state_data:
            orchestrator.qualifying_state = QualifyingSessionState.from_dict(qualifying_state_data)

        race_state_data = data.get("race_state")
        if race_state_data:
            orchestrator.race_state = RaceSessionState.from_dict(race_state_data)

        current_session_type = data.get("current_session_type")
        if current_session_type is not None:
            try:
                orchestrator.current_index = orchestrator._index_for_session(current_session_type)
            except ValueError:
                orchestrator.current_index = max(0, min(orchestrator.current_index, len(orchestrator.sessions) - 1))
        else:
            orchestrator.current_index = max(0, min(orchestrator.current_index, len(orchestrator.sessions) - 1))

        return orchestrator


__all__ = [
    "DEFAULT_WEEKEND_SEQUENCE",
    "WeekendOrchestrator",
    "WeekendSessionState",
    "WeekendSessionType",
    "QualifyingLapRecord",
    "QualifyingPhase",
    "QualifyingPhaseState",
    "QualifyingSessionState",
    "RaceDriverState",
    "RaceLapRecord",
    "RaceSessionState",
    "normalize_qualifying_phase",
    "normalize_weekend_session_type",
]
