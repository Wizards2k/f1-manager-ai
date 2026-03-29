from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional, Tuple


class WeekendSessionType(str, Enum):
    FP1 = "FP1"
    FP2 = "FP2"
    FP3 = "FP3"
    QUALIFYING = "QUALIFYING"
    RACE = "RACE"


_SESSION_TYPE_ALIASES = {
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
    "normalize_weekend_session_type",
]
