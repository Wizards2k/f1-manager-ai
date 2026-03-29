from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple


class QualifyingPhase(str, Enum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"


DEFAULT_QUALIFYING_PHASE_SEQUENCE: Tuple[QualifyingPhase, ...] = (
    QualifyingPhase.Q1,
    QualifyingPhase.Q2,
    QualifyingPhase.Q3,
)

DEFAULT_QUALIFYING_PHASE_DURATIONS_S: Dict[str, float] = {
    "Q1": 18 * 60.0,
    "Q2": 15 * 60.0,
    "Q3": 12 * 60.0,
}

DEFAULT_QUALIFYING_CUTOFFS: Dict[str, int] = {
    "Q1": 5,
    "Q2": 5,
    "Q3": 0,
}


def normalize_qualifying_phase(value: Any) -> QualifyingPhase:
    if isinstance(value, QualifyingPhase):
        return value

    if value is None:
        raise ValueError("Qualifying phase cannot be None")

    normalized = str(value).strip().upper()
    for phase in QualifyingPhase:
        if phase.value == normalized:
            return phase

    raise ValueError(f"Unsupported qualifying phase: {value}")


def _phase_duration(phase: QualifyingPhase) -> float:
    return float(DEFAULT_QUALIFYING_PHASE_DURATIONS_S[phase.value])


def _phase_cutoff_count(phase: QualifyingPhase) -> int:
    return int(DEFAULT_QUALIFYING_CUTOFFS[phase.value])


def _build_default_phases() -> List["QualifyingPhaseState"]:
    return [
        QualifyingPhaseState(
            phase=phase,
            duration_s=_phase_duration(phase),
            cutoff_count=_phase_cutoff_count(phase),
        )
        for phase in DEFAULT_QUALIFYING_PHASE_SEQUENCE
    ]


def _normalize_participant_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        data = dict(payload)
    else:
        data = {
            "car_id": getattr(payload, "car_id", None)
            or getattr(payload, "driver_number", None)
            or getattr(payload, "driver_id", None),
            "driver_name": getattr(payload, "driver_name", None)
            or getattr(payload, "name", None)
            or getattr(getattr(payload, "pilot", None), "nome", None)
            or getattr(getattr(payload, "pilot", None), "nome_cognome", None),
            "team_name": getattr(payload, "team_name", None)
            or getattr(getattr(payload, "team", None), "team_name", None)
            or getattr(getattr(payload, "team", None), "name", None),
            "is_player": bool(
                getattr(payload, "is_player", False)
                or getattr(payload, "is_player_controlled", False)
            ),
        }

    car_id = data.get("car_id")
    if car_id is None:
        car_id = data.get("driver_number") or data.get("driver_id")

    driver_name = data.get("driver_name") or data.get("name") or data.get("driver") or ""
    team_name = data.get("team_name") or data.get("team") or ""
    is_player = bool(data.get("is_player") or data.get("is_player_controlled") or data.get("player"))

    return {
        "car_id": str(car_id) if car_id is not None else "",
        "driver_name": str(driver_name) if driver_name is not None else "",
        "team_name": str(team_name) if team_name is not None else "",
        "is_player": is_player,
    }


@dataclass
class QualifyingLapRecord:
    car_id: str
    phase: str
    lap_number: int
    lap_time_s: float
    timestamp_s: Optional[float] = None
    is_competitive: bool = True
    driver_name: str = ""
    team_name: str = ""
    is_player: bool = False
    sector_times: Dict[str, float] = field(default_factory=dict)
    tyre_set_id: Optional[str] = None
    tyre_compound: Optional[str] = None
    tyre_condition_pct: Optional[float] = None
    tyre_is_q3_reserve: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "car_id": self.car_id,
            "phase": self.phase,
            "lap_number": self.lap_number,
            "lap_time_s": self.lap_time_s,
            "timestamp_s": self.timestamp_s,
            "is_competitive": self.is_competitive,
            "driver_name": self.driver_name,
            "team_name": self.team_name,
            "is_player": self.is_player,
            "sector_times": dict(self.sector_times),
            "tyre_set_id": self.tyre_set_id,
            "tyre_compound": self.tyre_compound,
            "tyre_condition_pct": self.tyre_condition_pct,
            "tyre_is_q3_reserve": self.tyre_is_q3_reserve,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualifyingLapRecord":
        return cls(
            car_id=str(data.get("car_id", "")),
            phase=str(data.get("phase", QualifyingPhase.Q1.value)),
            lap_number=int(data.get("lap_number", 0) or 0),
            lap_time_s=float(data.get("lap_time_s", 0.0) or 0.0),
            timestamp_s=data.get("timestamp_s"),
            is_competitive=bool(data.get("is_competitive", True)),
            driver_name=str(data.get("driver_name", "") or ""),
            team_name=str(data.get("team_name", "") or ""),
            is_player=bool(data.get("is_player", False)),
            sector_times=dict(data.get("sector_times", {}) or {}),
            tyre_set_id=data.get("tyre_set_id"),
            tyre_compound=data.get("tyre_compound"),
            tyre_condition_pct=data.get("tyre_condition_pct"),
            tyre_is_q3_reserve=bool(data.get("tyre_is_q3_reserve", False)),
        )


@dataclass
class QualifyingDriverState:
    car_id: str
    driver_name: str = ""
    team_name: str = ""
    is_player: bool = False
    status: str = "active"
    best_lap_s: Optional[float] = None
    best_lap_phase: Optional[str] = None
    best_lap_tyre_set_id: Optional[str] = None
    best_lap_tyre_compound: Optional[str] = None
    best_lap_tyre_condition_pct: Optional[float] = None
    best_lap_tyre_is_q3_reserve: bool = False
    phase_best_laps: Dict[str, float] = field(default_factory=dict)
    last_lap_s: Optional[float] = None
    last_tyre_set_id: Optional[str] = None
    last_tyre_compound: Optional[str] = None
    last_tyre_condition_pct: Optional[float] = None
    last_tyre_is_q3_reserve: bool = False
    best_sector_times: Dict[str, float] = field(default_factory=dict)
    last_sector_times: Dict[str, float] = field(default_factory=dict)
    lap_count: int = 0
    grid_position: Optional[int] = None
    eliminated_in_phase: Optional[str] = None
    pole_position: bool = False

    def record_lap(
        self,
        phase: QualifyingPhase,
        lap_time_s: float,
        sector_times: Optional[Dict[str, float]] = None,
        is_competitive: bool = True,
        tyre_set_id: Optional[str] = None,
        tyre_compound: Optional[str] = None,
        tyre_condition_pct: Optional[float] = None,
        tyre_is_q3_reserve: bool = False,
    ) -> None:
        self.lap_count += 1
        self.last_lap_s = lap_time_s
        self.last_tyre_set_id = tyre_set_id
        self.last_tyre_compound = tyre_compound
        self.last_tyre_condition_pct = tyre_condition_pct
        self.last_tyre_is_q3_reserve = tyre_is_q3_reserve
        if sector_times:
            self.last_sector_times = dict(sector_times)

        if not is_competitive:
            return

        phase_key = phase.value
        previous = self.phase_best_laps.get(phase_key)
        if previous is None or lap_time_s < previous:
            self.phase_best_laps[phase_key] = lap_time_s

        if self.best_lap_s is None or lap_time_s < self.best_lap_s:
            self.best_lap_s = lap_time_s
            self.best_lap_phase = phase_key
            self.best_lap_tyre_set_id = tyre_set_id
            self.best_lap_tyre_compound = tyre_compound
            self.best_lap_tyre_condition_pct = tyre_condition_pct
            self.best_lap_tyre_is_q3_reserve = tyre_is_q3_reserve

        if sector_times:
            for key, value in sector_times.items():
                best = self.best_sector_times.get(key)
                if best is None or value < best:
                    self.best_sector_times[key] = value

    def best_time_for_phase(self, phase: QualifyingPhase) -> Optional[float]:
        return self.phase_best_laps.get(phase.value)

    def best_available_time(self) -> Optional[float]:
        for phase_name in ("Q3", "Q2", "Q1"):
            value = self.phase_best_laps.get(phase_name)
            if value is not None:
                return value
        return self.best_lap_s

    def to_dict(self) -> Dict[str, Any]:
        return {
            "car_id": self.car_id,
            "driver_name": self.driver_name,
            "team_name": self.team_name,
            "is_player": self.is_player,
            "status": self.status,
            "best_lap_s": self.best_lap_s,
            "best_lap_phase": self.best_lap_phase,
            "best_lap_tyre_set_id": self.best_lap_tyre_set_id,
            "best_lap_tyre_compound": self.best_lap_tyre_compound,
            "best_lap_tyre_condition_pct": self.best_lap_tyre_condition_pct,
            "best_lap_tyre_is_q3_reserve": self.best_lap_tyre_is_q3_reserve,
            "phase_best_laps": dict(self.phase_best_laps),
            "last_lap_s": self.last_lap_s,
            "last_tyre_set_id": self.last_tyre_set_id,
            "last_tyre_compound": self.last_tyre_compound,
            "last_tyre_condition_pct": self.last_tyre_condition_pct,
            "last_tyre_is_q3_reserve": self.last_tyre_is_q3_reserve,
            "best_sector_times": dict(self.best_sector_times),
            "last_sector_times": dict(self.last_sector_times),
            "lap_count": self.lap_count,
            "grid_position": self.grid_position,
            "eliminated_in_phase": self.eliminated_in_phase,
            "pole_position": self.pole_position,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualifyingDriverState":
        return cls(
            car_id=str(data.get("car_id", "")),
            driver_name=str(data.get("driver_name", "") or ""),
            team_name=str(data.get("team_name", "") or ""),
            is_player=bool(data.get("is_player", False)),
            status=str(data.get("status", "active") or "active"),
            best_lap_s=data.get("best_lap_s"),
            best_lap_phase=data.get("best_lap_phase"),
            best_lap_tyre_set_id=data.get("best_lap_tyre_set_id"),
            best_lap_tyre_compound=data.get("best_lap_tyre_compound"),
            best_lap_tyre_condition_pct=data.get("best_lap_tyre_condition_pct"),
            best_lap_tyre_is_q3_reserve=bool(data.get("best_lap_tyre_is_q3_reserve", False)),
            phase_best_laps=dict(data.get("phase_best_laps", {}) or {}),
            last_lap_s=data.get("last_lap_s"),
            last_tyre_set_id=data.get("last_tyre_set_id"),
            last_tyre_compound=data.get("last_tyre_compound"),
            last_tyre_condition_pct=data.get("last_tyre_condition_pct"),
            last_tyre_is_q3_reserve=bool(data.get("last_tyre_is_q3_reserve", False)),
            best_sector_times=dict(data.get("best_sector_times", {}) or {}),
            last_sector_times=dict(data.get("last_sector_times", {}) or {}),
            lap_count=int(data.get("lap_count", 0) or 0),
            grid_position=data.get("grid_position"),
            eliminated_in_phase=data.get("eliminated_in_phase"),
            pole_position=bool(data.get("pole_position", False)),
        )


@dataclass
class QualifyingPhaseState:
    phase: QualifyingPhase
    duration_s: float
    cutoff_count: int = 0
    status: str = "scheduled"
    started_at_s: Optional[float] = None
    finished_at_s: Optional[float] = None
    participants: List[str] = field(default_factory=list)
    classification: List[Dict[str, Any]] = field(default_factory=list)
    eliminated_car_ids: List[str] = field(default_factory=list)
    qualified_car_ids: List[str] = field(default_factory=list)
    best_lap_by_car: Dict[str, float] = field(default_factory=dict)
    lap_count: int = 0

    def activate(self, participants: Iterable[str], started_at_s: float) -> None:
        self.status = "active"
        self.started_at_s = started_at_s
        self.finished_at_s = None
        self.participants = [str(car_id) for car_id in participants]
        self.classification = []
        self.eliminated_car_ids = []
        self.qualified_car_ids = []
        self.best_lap_by_car = {}
        self.lap_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "duration_s": self.duration_s,
            "cutoff_count": self.cutoff_count,
            "status": self.status,
            "started_at_s": self.started_at_s,
            "finished_at_s": self.finished_at_s,
            "participants": list(self.participants),
            "classification": list(self.classification),
            "eliminated_car_ids": list(self.eliminated_car_ids),
            "qualified_car_ids": list(self.qualified_car_ids),
            "best_lap_by_car": dict(self.best_lap_by_car),
            "lap_count": self.lap_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualifyingPhaseState":
        phase = normalize_qualifying_phase(data.get("phase", QualifyingPhase.Q1.value))
        return cls(
            phase=phase,
            duration_s=float(data.get("duration_s", _phase_duration(phase)) or _phase_duration(phase)),
            cutoff_count=int(data.get("cutoff_count", _phase_cutoff_count(phase)) or 0),
            status=str(data.get("status", "scheduled") or "scheduled"),
            started_at_s=data.get("started_at_s"),
            finished_at_s=data.get("finished_at_s"),
            participants=[str(item) for item in data.get("participants", []) or []],
            classification=[dict(item) for item in data.get("classification", []) or []],
            eliminated_car_ids=[str(item) for item in data.get("eliminated_car_ids", []) or []],
            qualified_car_ids=[str(item) for item in data.get("qualified_car_ids", []) or []],
            best_lap_by_car={str(key): float(value) for key, value in (data.get("best_lap_by_car", {}) or {}).items()},
            lap_count=int(data.get("lap_count", 0) or 0),
        )


@dataclass
class QualifyingSessionState:
    session_type: str = "QUALIFYING"
    circuit_id: Optional[str] = None
    status: str = "idle"
    current_phase_index: int = 0
    phases: List[QualifyingPhaseState] = field(default_factory=_build_default_phases)
    participants: Dict[str, QualifyingDriverState] = field(default_factory=dict)
    lap_records: List[QualifyingLapRecord] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    final_grid: List[Dict[str, Any]] = field(default_factory=list)

    def _touch(self, timestamp: Optional[float] = None) -> None:
        self.updated_at = timestamp if timestamp is not None else time.time()

    def _ensure_phases(self) -> None:
        if not self.phases:
            self.phases = _build_default_phases()

    def _phase_index_for(self, phase: Any) -> int:
        normalized = normalize_qualifying_phase(phase)
        for index, phase_state in enumerate(self.phases):
            if phase_state.phase == normalized:
                return index
        raise ValueError(f"Phase {normalized.value} is not part of the qualifying sequence")

    def _participant_order_key(self, participant: QualifyingDriverState, phase: QualifyingPhase) -> Tuple[float, str, str]:
        lap_time = participant.best_time_for_phase(phase)
        sort_time = lap_time if lap_time is not None else math.inf
        return (sort_time, participant.driver_name.lower(), participant.car_id)

    def _sort_phase_participants(self, phase_state: QualifyingPhaseState) -> List[QualifyingDriverState]:
        participants = [
            self.participants[car_id]
            for car_id in phase_state.participants
            if car_id in self.participants
        ]
        participants.sort(key=lambda item: self._participant_order_key(item, phase_state.phase))
        return participants

    def _build_final_grid(self) -> List[Dict[str, Any]]:
        self._ensure_phases()
        ranking: List[Tuple[int, float, QualifyingDriverState, str]] = []

        for participant in self.participants.values():
            if participant.eliminated_in_phase == "Q1":
                phase_priority = ["Q1"]
                bucket = 2
            elif participant.eliminated_in_phase == "Q2":
                phase_priority = ["Q2", "Q1"]
                bucket = 1
            else:
                phase_priority = ["Q3", "Q2", "Q1"]
                bucket = 0

            best_phase = None
            best_time = None
            for candidate_phase in phase_priority:
                candidate_time = participant.phase_best_laps.get(candidate_phase)
                if candidate_time is not None:
                    best_phase = candidate_phase
                    best_time = candidate_time
                    break

            if best_time is None:
                best_phase = participant.best_lap_phase or phase_priority[0]
                best_time = participant.best_available_time()
            ranking.append((bucket, best_time if best_time is not None else math.inf, participant, best_phase))

        ranking.sort(key=lambda item: (item[0], item[1], item[2].driver_name.lower(), item[2].car_id))

        grid: List[Dict[str, Any]] = []
        for position, (_, best_time, participant, best_phase) in enumerate(ranking, start=1):
            status = "qualified"
            pole = False
            if participant.eliminated_in_phase is not None:
                status = "eliminated"
            elif position == 1:
                status = "pole"
                pole = True

            participant.grid_position = position
            participant.status = status
            participant.pole_position = pole

            grid.append(
                {
                    "position": position,
                    "car_id": participant.car_id,
                    "driver_name": participant.driver_name,
                    "team_name": participant.team_name,
                    "best_lap_s": None if math.isinf(best_time) else best_time,
                    "best_phase": best_phase,
                    "status": status,
                    "eliminated_in_phase": participant.eliminated_in_phase,
                    "is_player": participant.is_player,
                    "best_lap_tyre_set_id": participant.best_lap_tyre_set_id,
                    "best_lap_tyre_compound": participant.best_lap_tyre_compound,
                    "best_lap_tyre_condition_pct": participant.best_lap_tyre_condition_pct,
                    "best_lap_tyre_is_q3_reserve": participant.best_lap_tyre_is_q3_reserve,
                }
            )

        return grid

    @property
    def current_phase_state(self) -> Optional[QualifyingPhaseState]:
        self._ensure_phases()
        if 0 <= self.current_phase_index < len(self.phases):
            return self.phases[self.current_phase_index]
        return None

    @property
    def current_phase(self) -> Optional[str]:
        phase_state = self.current_phase_state
        return phase_state.phase.value if phase_state else None

    @property
    def next_phase(self) -> Optional[str]:
        self._ensure_phases()
        next_index = self.current_phase_index + 1
        if 0 <= next_index < len(self.phases):
            return self.phases[next_index].phase.value
        return None

    @property
    def active_car_ids(self) -> List[str]:
        phase_state = self.current_phase_state
        if not phase_state:
            return []
        return list(phase_state.participants)

    @property
    def is_complete(self) -> bool:
        return self.status == "completed"

    def start(
        self,
        participants: Iterable[Any],
        circuit_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        started_at_s: float = 0.0,
    ) -> "QualifyingSessionState":
        if circuit_id is not None:
            self.circuit_id = circuit_id
        if metadata:
            self.metadata.update(metadata)

        normalized = [_normalize_participant_payload(item) for item in participants]
        self.participants = {
            item["car_id"]: QualifyingDriverState(
                car_id=item["car_id"],
                driver_name=item["driver_name"],
                team_name=item["team_name"],
                is_player=item["is_player"],
            )
            for item in normalized
            if item["car_id"]
        }

        self._ensure_phases()
        self.current_phase_index = 0
        self.status = "active"
        self.lap_records = []
        self.final_grid = []

        first_phase = self.current_phase_state
        if first_phase is not None:
            first_phase.activate(self.participants.keys(), started_at_s=started_at_s)

        self._touch(started_at_s)
        return self

    def get_participant(self, car_id: Any) -> Optional[QualifyingDriverState]:
        return self.participants.get(str(car_id))

    def is_car_active(self, car_id: Any) -> bool:
        participant = self.get_participant(car_id)
        if participant is None or participant.status == "eliminated":
            return False
        phase_state = self.current_phase_state
        if phase_state is None:
            return False
        return str(car_id) in phase_state.participants

    def record_lap(
        self,
        car_id: Any,
        lap_time_s: float,
        lap_number: int,
        phase: Optional[Any] = None,
        timestamp_s: Optional[float] = None,
        sector_times: Optional[Dict[str, float]] = None,
        is_competitive: bool = True,
        tyre_set_id: Optional[str] = None,
        tyre_compound: Optional[str] = None,
        tyre_condition_pct: Optional[float] = None,
        tyre_is_q3_reserve: bool = False,
    ) -> Optional[QualifyingLapRecord]:
        participant = self.get_participant(car_id)
        if participant is None:
            return None

        phase_state = self.current_phase_state if phase is None else self.get_phase(phase)
        if phase_state is None:
            return None

        normalized_phase = phase_state.phase
        record = QualifyingLapRecord(
            car_id=participant.car_id,
            phase=normalized_phase.value,
            lap_number=int(lap_number),
            lap_time_s=float(lap_time_s),
            timestamp_s=timestamp_s,
            is_competitive=bool(is_competitive),
            driver_name=participant.driver_name,
            team_name=participant.team_name,
            is_player=participant.is_player,
            sector_times=dict(sector_times or {}),
            tyre_set_id=tyre_set_id,
            tyre_compound=tyre_compound,
            tyre_condition_pct=tyre_condition_pct,
            tyre_is_q3_reserve=tyre_is_q3_reserve,
        )
        self.lap_records.append(record)
        participant.record_lap(
            normalized_phase,
            float(lap_time_s),
            sector_times=sector_times,
            is_competitive=is_competitive,
            tyre_set_id=tyre_set_id,
            tyre_compound=tyre_compound,
            tyre_condition_pct=tyre_condition_pct,
            tyre_is_q3_reserve=tyre_is_q3_reserve,
        )
        phase_state.lap_count += 1
        if is_competitive:
            best = phase_state.best_lap_by_car.get(participant.car_id)
            if best is None or lap_time_s < best:
                phase_state.best_lap_by_car[participant.car_id] = float(lap_time_s)
        self._touch(timestamp_s)
        return record

    def get_phase(self, phase: Any) -> Optional[QualifyingPhaseState]:
        try:
            index = self._phase_index_for(phase)
        except ValueError:
            return None
        if 0 <= index < len(self.phases):
            return self.phases[index]
        return None

    def complete_current_phase(self, finished_at_s: Optional[float] = None) -> Optional[QualifyingPhaseState]:
        phase_state = self.current_phase_state
        if phase_state is None:
            return None

        if phase_state.status == "completed":
            return phase_state

        finished_at_s = finished_at_s if finished_at_s is not None else time.time()
        ordered = self._sort_phase_participants(phase_state)
        total_participants = len(ordered)
        cutoff_count = max(0, phase_state.cutoff_count)
        survivors_count = total_participants if cutoff_count == 0 else max(0, total_participants - cutoff_count)

        qualified = ordered[:survivors_count]
        eliminated = ordered[survivors_count:]

        eliminated_ids = {item.car_id for item in eliminated}
        classification: List[Dict[str, Any]] = []
        for position, participant in enumerate(ordered, start=1):
            best_time = participant.best_time_for_phase(phase_state.phase)
            status = "qualified"
            if participant.car_id in eliminated_ids:
                status = "eliminated"
            elif phase_state.phase == QualifyingPhase.Q3 and position == 1:
                status = "pole"
            classification.append(
                {
                    "position": position,
                    "car_id": participant.car_id,
                    "driver_name": participant.driver_name,
                    "team_name": participant.team_name,
                    "best_lap_s": best_time,
                    "lap_count": participant.lap_count,
                    "status": status,
                    "best_lap_tyre_set_id": participant.best_lap_tyre_set_id,
                    "best_lap_tyre_compound": participant.best_lap_tyre_compound,
                    "best_lap_tyre_condition_pct": participant.best_lap_tyre_condition_pct,
                    "best_lap_tyre_is_q3_reserve": participant.best_lap_tyre_is_q3_reserve,
                }
            )

        phase_state.classification = classification
        phase_state.qualified_car_ids = [participant.car_id for participant in qualified]
        phase_state.eliminated_car_ids = [participant.car_id for participant in eliminated]
        phase_state.best_lap_by_car = {
            participant.car_id: participant.best_time_for_phase(phase_state.phase)
            for participant in ordered
            if participant.best_time_for_phase(phase_state.phase) is not None
        }
        phase_state.status = "completed"
        phase_state.finished_at_s = finished_at_s

        eliminated_ids = set(phase_state.eliminated_car_ids)
        for participant in self.participants.values():
            if participant.car_id in eliminated_ids:
                participant.status = "eliminated"
                participant.eliminated_in_phase = phase_state.phase.value
                participant.pole_position = False
            elif participant.car_id in phase_state.qualified_car_ids:
                participant.status = "qualified"
                if phase_state.phase == QualifyingPhase.Q3:
                    participant.eliminated_in_phase = None
                    participant.pole_position = participant.car_id == phase_state.qualified_car_ids[0]

        next_index = self.current_phase_index + 1
        if 0 <= next_index < len(self.phases):
            self.current_phase_index = next_index
            next_phase = self.current_phase_state
            if next_phase is not None:
                next_phase.activate(phase_state.qualified_car_ids, started_at_s=finished_at_s)
            self.status = "active"
        else:
            self.final_grid = self._build_final_grid()
            self.status = "completed"

        self._touch(finished_at_s)
        return phase_state

    def advance_if_elapsed(self, current_elapsed_s: float) -> List[str]:
        completed_phases: List[str] = []
        while True:
            phase_state = self.current_phase_state
            if phase_state is None or phase_state.status != "active" or phase_state.started_at_s is None:
                break
            elapsed = float(current_elapsed_s) - float(phase_state.started_at_s)
            if elapsed < phase_state.duration_s:
                break
            completed = self.complete_current_phase(finished_at_s=current_elapsed_s)
            if completed is None:
                break
            completed_phases.append(completed.phase.value)
            if self.is_complete:
                break
        return completed_phases

    def finalize_session(self, finished_at_s: Optional[float] = None) -> List[Dict[str, Any]]:
        finished_at_s = finished_at_s if finished_at_s is not None else time.time()
        phase_state = self.current_phase_state
        if phase_state is not None and phase_state.status == "active":
            self.complete_current_phase(finished_at_s=finished_at_s)
        if not self.final_grid:
            self.final_grid = self._build_final_grid()
        self.status = "completed"
        self._touch(finished_at_s)
        return list(self.final_grid)

    def summary(self) -> Dict[str, Any]:
        return {
            "session_type": self.session_type,
            "status": self.status,
            "circuit_id": self.circuit_id,
            "current_phase": self.current_phase,
            "next_phase": self.next_phase,
            "participants": len(self.participants),
            "active_car_ids": list(self.active_car_ids),
            "phases": [phase.to_dict() for phase in self.phases],
            "participants_state": {car_id: participant.to_dict() for car_id, participant in self.participants.items()},
            "lap_records": [record.to_dict() for record in self.lap_records],
            "final_grid": list(self.final_grid),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_type": self.session_type,
            "circuit_id": self.circuit_id,
            "status": self.status,
            "current_phase_index": self.current_phase_index,
            "phases": [phase.to_dict() for phase in self.phases],
            "participants": {car_id: participant.to_dict() for car_id, participant in self.participants.items()},
            "lap_records": [record.to_dict() for record in self.lap_records],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
            "final_grid": list(self.final_grid),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualifyingSessionState":
        phases_data = data.get("phases") or []
        phases = [QualifyingPhaseState.from_dict(item) for item in phases_data]
        if not phases:
            phases = _build_default_phases()

        state = cls(
            session_type=str(data.get("session_type", "QUALIFYING") or "QUALIFYING"),
            circuit_id=data.get("circuit_id"),
            status=str(data.get("status", "idle") or "idle"),
            current_phase_index=int(data.get("current_phase_index", 0) or 0),
            phases=phases,
            participants={
                str(car_id): QualifyingDriverState.from_dict(participant)
                for car_id, participant in (data.get("participants", {}) or {}).items()
            },
            lap_records=[QualifyingLapRecord.from_dict(item) for item in data.get("lap_records", []) or []],
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=dict(data.get("metadata", {}) or {}),
            final_grid=[dict(item) for item in data.get("final_grid", []) or []],
        )

        current_phase_state = state.current_phase_state
        if current_phase_state is not None and current_phase_state.status == "scheduled" and state.status == "active":
            current_phase_state.status = "active"

        return state


__all__ = [
    "DEFAULT_QUALIFYING_CUTOFFS",
    "DEFAULT_QUALIFYING_PHASE_DURATIONS_S",
    "DEFAULT_QUALIFYING_PHASE_SEQUENCE",
    "QualifyingDriverState",
    "QualifyingLapRecord",
    "QualifyingPhase",
    "QualifyingPhaseState",
    "QualifyingSessionState",
    "normalize_qualifying_phase",
]
