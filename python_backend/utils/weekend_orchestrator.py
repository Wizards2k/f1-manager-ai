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
from .weekend_transition_machine import (
    WeekendTransitionMachine,
    WeekendTransitionState,
)


class WeekendSessionType(str, Enum):
    FP1 = "FP1"
    FP2 = "FP2"
    FP3 = "FP3"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    RACE = "RACE"


_SESSION_TYPE_ALIASES = {
    "Q": "Q1",  # Default a Q1 se non specificato
    "Q1": "Q1",
    "Q2": "Q2",
    "Q3": "Q3",
    "QUALIFYING": "Q1",  # Backward compatibility: old saves use QUALIFYING
    "QUALI": "Q1",
    "QUALY": "Q1",
    "QUALIFY": "Q1",
}


DEFAULT_WEEKEND_SEQUENCE: Tuple[WeekendSessionType, ...] = (
    WeekendSessionType.FP1,
    WeekendSessionType.FP2,
    WeekendSessionType.FP3,
    WeekendSessionType.Q1,
    WeekendSessionType.Q2,
    WeekendSessionType.Q3,
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
    transition_machine: WeekendTransitionMachine = field(default_factory=WeekendTransitionMachine)
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
        # Applica logica di eliminazione per Q1 e Q2
        current_type = self.current_session_type
        if current_type == "Q1":
            self._apply_q1_elimination(summary)
        elif current_type == "Q2":
            self._apply_q2_elimination(summary)
        
        self.mark_current_session_completed(summary=summary, timestamp=timestamp, merge=merge)
        next_type = self.next_session_type
        if next_type is None:
            self.status = "completed"
            self._touch(timestamp)
            return None
        return self.set_current_session(next_type, activate=True, timestamp=timestamp)

    def _apply_q1_elimination(self, summary: Optional[Dict[str, Any]] = None) -> None:
        """
        Applica eliminazione Q1: 20 auto → 15 ammesse (eliminate ultime 5).
        
        La griglia di Q1 determina quali auto avanzano a Q2.
        Le ultime 5 posizioni (16-20) sono eliminate e non partecipano a Q2/Q3.
        
        Args:
            summary: Dizionario con risultati Q1 (deve contenere 'classification' o 'results')
        """
        if not summary:
            return
        
        # Estrai classifiche dai risultati
        classification = summary.get("classification") or summary.get("results", [])
        if not classification:
            return
        
        # Ordina per tempo/miglior giro
        sorted_cars = sorted(classification, key=lambda x: x.get("best_lap_time", float("inf")))
        
        # Determina auto eliminate (ultime 5) e ammesse (prime 15)
        eliminated = sorted_cars[15:]  # Posizioni 16-20
        admitted = sorted_cars[:15]    # Posizioni 1-15
        
        # Aggiungi info eliminazione al summary
        summary["q1_elimination"] = {
            "admitted_count": len(admitted),
            "eliminated_count": len(eliminated),
            "admitted_car_numbers": [car.get("car_number") for car in admitted],
            "eliminated_car_numbers": [car.get("car_number") for car in eliminated],
            "cutoff_position": 15,
        }

    def _apply_q2_elimination(self, summary: Optional[Dict[str, Any]] = None) -> None:
        """
        Applica eliminazione Q2: 15 auto → 10 ammesse (eliminate ultime 5).
        
        La griglia di Q2 determina quali auto avanzano a Q3.
        Le ultime 5 posizioni (11-15) sono eliminate e non partecipano a Q3.
        
        Args:
            summary: Dizionario con risultati Q2 (deve contenere 'classification' o 'results')
        """
        if not summary:
            return
        
        # Estrai classifiche dai risultati
        classification = summary.get("classification") or summary.get("results", [])
        if not classification:
            return
        
        # Ordina per tempo/miglior giro
        sorted_cars = sorted(classification, key=lambda x: x.get("best_lap_time", float("inf")))
        
        # Determina auto eliminate (ultime 5) e ammesse (prime 10)
        eliminated = sorted_cars[10:]  # Posizioni 11-15
        admitted = sorted_cars[:10]    # Posizioni 1-10
        
        # Aggiungi info eliminazione al summary
        summary["q2_elimination"] = {
            "admitted_count": len(admitted),
            "eliminated_count": len(eliminated),
            "admitted_car_numbers": [car.get("car_number") for car in admitted],
            "eliminated_car_numbers": [car.get("car_number") for car in eliminated],
            "cutoff_position": 10,
        }

    # ── Transition Machine Integration ──

    def expire_current_session(self, timestamp: Optional[float] = None) -> None:
        """
        Marca la sessione corrente come scaduta (timer = 0).
        
        Transizione: RUNNING → EXPIRED_GRACE
        
        Args:
            timestamp: Timestamp dell'evento (default: time.time())
        """
        self.transition_machine.expire_session(timestamp)
        self._touch(timestamp)

    def allow_final_lap(self, car_id: str) -> None:
        """
        Autorizza un'auto a completare l'ultimo giro.
        
        Da chiamare quando un'auto è in pista allo scadere del timer.
        
        Args:
            car_id: Identificativo dell'auto
        """
        self.transition_machine.allow_final_lap(car_id)

    def mark_car_completed_final_lap(self, car_id: str) -> None:
        """
        Marca un'auto come avente completato l'ultimo giro.
        
        Args:
            car_id: Identificativo dell'auto
        """
        self.transition_machine.mark_car_completed_final_lap(car_id)

    def mark_car_in_pit(self, car_id: str) -> None:
        """
        Marca un'auto come rientrata ai box.
        
        Args:
            car_id: Identificativo dell'auto
        """
        self.transition_machine.mark_car_in_pit(car_id)

    def update_transition(
        self,
        timestamp: Optional[float] = None,
    ) -> WeekendTransitionState:
        """
        Aggiorna la state machine delle transizioni.
        
        Da chiamare ad ogni tick del loop principale.
        
        Args:
            timestamp: Timestamp corrente (default: time.time())
        
        Returns:
            Stato corrente dopo l'aggiornamento
        """
        state = self.transition_machine.update(timestamp)
        
        # Se la transizione è completa, avanza automaticamente
        if state == WeekendTransitionState.NEXT_SESSION:
            self.advance_to_next_session(timestamp=timestamp)
            # Resetta la transition machine per la nuova sessione
            self.transition_machine.reset()
        
        self._touch(timestamp)
        return state

    def get_transition_state(self) -> WeekendTransitionState:
        """Restituisce lo stato corrente della transizione."""
        return self.transition_machine.state

    def get_transition_metrics(self) -> Dict[str, Any]:
        """Restituisce le metriche correnti della transizione."""
        return self.transition_machine.metrics.to_dict()

    def can_advance_to_next_session(self) -> bool:
        """
        Verifica se la sessione corrente può avanzare alla prossima.
        
        Returns:
            True se la state machine permette l'avanzamento
        """
        return self.transition_machine.can_advance

    def persist_session_results(self, summary: Optional[Dict[str, Any]] = None) -> None:
        """
        Persiste i risultati della sessione corrente e marca come completato.
        
        Args:
            summary: Riepilogo della sessione da persistere
        """
        if summary:
            self.mark_current_session_completed(summary=summary)
        self.transition_machine.mark_results_persisted()
        self._touch()

    def to_dict(self) -> Dict[str, Any]:
        """Serializza l'orchestrator per il salvataggio."""
        return {
            "circuit_id": self.circuit_id,
            "status": self.status,
            "current_index": self.current_index,
            "sessions": [s.to_dict() for s in self.sessions],
            "qualifying_state": self.qualifying_state.to_dict() if self.qualifying_state else None,
            "race_state": self.race_state.to_dict() if self.race_state else None,
            "transition_machine": self.transition_machine.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeekendOrchestrator":
        """Deserializza l'orchestrator da un salvataggio."""
        orchestrator = cls()
        orchestrator.circuit_id = data.get("circuit_id")
        orchestrator.status = data.get("status", "idle")
        orchestrator.current_index = int(data.get("current_index", 0))
        orchestrator.sessions = [
            WeekendSessionState.from_dict(s) for s in data.get("sessions", [])
        ]
        
        # Deserializza stati specializzati
        qualifying_data = data.get("qualifying_state")
        if qualifying_data:
            orchestrator.qualifying_state = QualifyingSessionState.from_dict(qualifying_data)
        
        race_data = data.get("race_state")
        if race_data:
            orchestrator.race_state = RaceSessionState.from_dict(race_data)
        
        # Deserializza transition machine
        transition_data = data.get("transition_machine")
        if transition_data:
            orchestrator.transition_machine = WeekendTransitionMachine.from_dict(transition_data)
        
        orchestrator.created_at = float(data.get("created_at", time.time()))
        orchestrator.updated_at = float(data.get("updated_at", time.time()))
        orchestrator.metadata = dict(data.get("metadata", {}))
        
        return orchestrator
