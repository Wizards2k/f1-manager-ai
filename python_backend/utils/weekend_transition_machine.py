"""
Weekend Transition State Machine — gestisce le transizioni tra sessioni del weekend.

Implementa i criteri operativi approvati per Fase-G punto 3:
- Transizioni automatiche basate su timer e stato auto
- Grace period 180s per ultimi giri (regolamento F1)
- Timeout finalizzazione 60s per auto bloccate
- Nessuna conferma utente richiesta

Documentazione correlata:
- docs/Fase-G.md §3 (Criteri operativi di transizione)
- docs/practice-session-orchestrator.md
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class WeekendTransitionState(str, Enum):
    """
    Stati della transizione tra sessioni.
    
    Flusso:
    RUNNING → EXPIRED_GRACE → FINALIZING → NEXT_SESSION
    """
    RUNNING = "running"
    """Sessione in corso, timer attivo"""
    
    EXPIRED_GRACE = "expired_grace"
    """Timer scaduto, auto in pista completano ultimo giro (max 180s)"""
    
    FINALIZING = "finalizing"
    """Tutte le auto ai box, consolidamento risultati (max 60s)"""
    
    NEXT_SESSION = "next_session"
    """Transizione in corso, avvio nuova sessione"""


@dataclass
class TransitionMetrics:
    """Metriche correnti della transizione."""
    cars_on_track: int = 0
    cars_in_pit: int = 0
    cars_completed_final_lap: int = 0
    grace_period_elapsed_s: float = 0.0
    finalization_elapsed_s: float = 0.0
    last_update_timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cars_on_track": self.cars_on_track,
            "cars_in_pit": self.cars_in_pit,
            "cars_completed_final_lap": self.cars_completed_final_lap,
            "grace_period_elapsed_s": round(self.grace_period_elapsed_s, 2),
            "finalization_elapsed_s": round(self.finalization_elapsed_s, 2),
            "last_update_timestamp": self.last_update_timestamp,
        }


@dataclass
class WeekendTransitionMachine:
    """
    State machine per le transizioni tra sessioni del weekend.
    
    Criteri di transizione:
    - RUNNING → EXPIRED_GRACE: timer sessione = 0
    - EXPIRED_GRACE → FINALIZING: tutte le auto ai box O timeout 180s
    - FINALIZING → NEXT_SESSION: risultati persistiti O timeout 60s
    
    Timeout configurabili:
    - grace_period_timeout_s: 180s (3 minuti) per ultimi giri
    - finalization_timeout_s: 60s (1 minuto) per auto bloccate
    """
    
    state: WeekendTransitionState = WeekendTransitionState.RUNNING
    grace_period_timeout_s: float = 180.0
    finalization_timeout_s: float = 60.0
    
    # Timestamp di riferimento
    session_expired_at: Optional[float] = None
    grace_period_started_at: Optional[float] = None
    finalization_started_at: Optional[float] = None
    
    # Tracking auto
    cars_allowed_final_lap: Set[str] = field(default_factory=set)
    cars_completed_final_lap: Set[str] = field(default_factory=set)
    cars_in_pit: Set[str] = field(default_factory=set)
    
    # Metriche correnti
    metrics: TransitionMetrics = field(default_factory=TransitionMetrics)
    
    # Flag di controllo
    _results_persisted: bool = False
    _ui_notified: bool = False
    
    @property
    def is_session_expired(self) -> bool:
        """Verifica se il timer della sessione è scaduto."""
        return self.session_expired_at is not None
    
    @property
    def is_grace_period_active(self) -> bool:
        """Verifica se il grace period è attivo."""
        return self.state == WeekendTransitionState.EXPIRED_GRACE
    
    @property
    def is_finalizing(self) -> bool:
        """Verifica se la sessione è in finalizzazione."""
        return self.state == WeekendTransitionState.FINALIZING
    
    @property
    def is_ready_for_next_session(self) -> bool:
        """Verifica se la transizione alla prossima sessione è pronta."""
        return self.state == WeekendTransitionState.NEXT_SESSION
    
    @property
    def can_advance(self) -> bool:
        """
        Verifica se la state machine permette l'avanzamento.
        
        True solo quando:
        - Stato == FINALIZING
        - Tutte le auto hanno completato l'ultimo giro O sono ai box
        - Risultati persistiti
        """
        if self.state != WeekendTransitionState.FINALIZING:
            return False
        
        # Tutte le auto devono aver completato l'ultimo giro o essere ai box
        all_cars_finalized = (
            len(self.cars_completed_final_lap) + len(self.cars_in_pit)
        ) >= (len(self.cars_allowed_final_lap) + len(self.cars_in_pit))
        
        return all_cars_finalized and self._results_persisted
    
    def expire_session(self, timestamp: Optional[float] = None) -> None:
        """
        Marca la sessione come scaduta (timer = 0).
        
        Transizione: RUNNING → EXPIRED_GRACE
        
        Args:
            timestamp: Timestamp dell'evento (default: time.time())
        """
        if self.state != WeekendTransitionState.RUNNING:
            return
        
        now = timestamp if timestamp is not None else time.time()
        self.session_expired_at = now
        self.state = WeekendTransitionState.EXPIRED_GRACE
        self.grace_period_started_at = now
        self.metrics.last_update_timestamp = now
        
        # Reset per la nuova sessione
        self.cars_allowed_final_lap.clear()
        self.cars_completed_final_lap.clear()
        self.cars_in_pit.clear()
        self._results_persisted = False
        self._ui_notified = False
    
    def allow_final_lap(self, car_id: str) -> None:
        """
        Autorizza un'auto a completare l'ultimo giro.
        
        Da chiamare quando un'auto è in pista allo scadere del timer.
        
        Args:
            car_id: Identificativo dell'auto
        """
        if self.state == WeekendTransitionState.EXPIRED_GRACE:
            self.cars_allowed_final_lap.add(car_id)
    
    def mark_car_completed_final_lap(self, car_id: str) -> None:
        """
        Marca un'auto come avente completato l'ultimo giro.
        
        Args:
            car_id: Identificativo dell'auto
        """
        self.cars_completed_final_lap.add(car_id)
        if car_id in self.cars_allowed_final_lap:
            self.cars_allowed_final_lap.discard(car_id)
    
    def mark_car_in_pit(self, car_id: str) -> None:
        """
        Marca un'auto come rientrata ai box.
        
        Args:
            car_id: Identificativo dell'auto
        """
        self.cars_in_pit.add(car_id)
        # Se l'auto era autorizzata all'ultimo giro, la rimuoviamo
        if car_id in self.cars_allowed_final_lap:
            self.cars_allowed_final_lap.discard(car_id)
            self.cars_completed_final_lap.add(car_id)
    
    def _update_metrics(self, timestamp: Optional[float] = None) -> None:
        """Aggiorna le metriche correnti."""
        now = timestamp if timestamp is not None else time.time()
        self.metrics.last_update_timestamp = now
        
        # Calcola tempi elapsed
        if self.grace_period_started_at is not None:
            self.metrics.grace_period_elapsed_s = max(
                0.0, now - self.grace_period_started_at
            )
        
        if self.finalization_started_at is not None:
            self.metrics.finalization_elapsed_s = max(
                0.0, now - self.finalization_started_at
            )
        
        # Conta auto
        self.metrics.cars_on_track = len(self.cars_allowed_final_lap)
        self.metrics.cars_in_pit = len(self.cars_in_pit)
        self.metrics.cars_completed_final_lap = len(self.cars_completed_final_lap)
    
    def _check_grace_period_timeout(self, timestamp: Optional[float] = None) -> bool:
        """
        Verifica se il grace period è scaduto per timeout.
        
        Returns:
            True se il timeout di 180s è stato raggiunto
        """
        if self.grace_period_started_at is None:
            return False
        
        now = timestamp if timestamp is not None else time.time()
        elapsed = now - self.grace_period_started_at
        return elapsed >= self.grace_period_timeout_s
    
    def _check_finalization_timeout(self, timestamp: Optional[float] = None) -> bool:
        """
        Verifica se la finalizzazione è scaduta per timeout.
        
        Returns:
            True se il timeout di 60s è stato raggiunto
        """
        if self.finalization_started_at is None:
            return False
        
        now = timestamp if timestamp is not None else time.time()
        elapsed = now - self.finalization_started_at
        return elapsed >= self.finalization_timeout_s
    
    def _all_cars_finalized(self) -> bool:
        """
        Verifica se tutte le auto hanno completato l'ultimo giro o sono ai box.
        
        Returns:
            True se tutte le auto autorizzate hanno finalizzato
        """
        # Non ci devono essere auto ancora autorizzate all'ultimo giro
        return len(self.cars_allowed_final_lap) == 0
    
    def start_finalization(self, timestamp: Optional[float] = None) -> None:
        """
        Avvia la fase di finalizzazione.
        
        Transizione: EXPIRED_GRACE → FINALIZING
        
        Args:
            timestamp: Timestamp dell'evento
        """
        if self.state != WeekendTransitionState.EXPIRED_GRACE:
            return
        
        now = timestamp if timestamp is not None else time.time()
        self.state = WeekendTransitionState.FINALIZING
        self.finalization_started_at = now
        self.metrics.last_update_timestamp = now
    
    def mark_results_persisted(self) -> None:
        """Marca i risultati come persistiti."""
        self._results_persisted = True
    
    def notify_ui(self) -> None:
        """Marca la UI come notificata."""
        self._ui_notified = True
    
    def complete_transition(self) -> None:
        """
        Completa la transizione alla prossima sessione.
        
        Transizione: FINALIZING → NEXT_SESSION
        
        Da chiamare quando tutti i criteri sono soddisfatti.
        """
        if self.state != WeekendTransitionState.FINALIZING:
            return
        
        self.state = WeekendTransitionState.NEXT_SESSION
        self.metrics.last_update_timestamp = time.time()
    
    def update(
        self,
        timestamp: Optional[float] = None,
    ) -> WeekendTransitionState:
        """
        Aggiorna la state machine e applica le transizioni automatiche.
        
        Da chiamare ad ogni tick del loop principale.
        
        Args:
            timestamp: Timestamp corrente (default: time.time())
        
        Returns:
            Stato corrente dopo l'aggiornamento
        """
        now = timestamp if timestamp is not None else time.time()
        self._update_metrics(now)
        
        if self.state == WeekendTransitionState.EXPIRED_GRACE:
            # Controlla se tutte le auto sono rientrate
            if self._all_cars_finalized():
                self.start_finalization(now)
            # Controlla timeout grace period
            elif self._check_grace_period_timeout(now):
                # Forza tutte le auto come finalizzate
                for car_id in list(self.cars_allowed_final_lap):
                    self.cars_completed_final_lap.add(car_id)
                self.cars_allowed_final_lap.clear()
                self.start_finalization(now)
        
        elif self.state == WeekendTransitionState.FINALIZING:
            # Controlla se possiamo avanzare
            if self._results_persisted and self._all_cars_finalized():
                self.complete_transition()
            # Controlla timeout finalizzazione
            elif self._check_finalization_timeout(now):
                # Forza completamento anche se ci sono problemi
                self.complete_transition()
        
        return self.state
    
    def reset(self) -> None:
        """
        Resetta la state machine per una nuova sessione.
        
        Da chiamare quando si avvia una nuova sessione del weekend.
        """
        self.state = WeekendTransitionState.RUNNING
        self.session_expired_at = None
        self.grace_period_started_at = None
        self.finalization_started_at = None
        self.cars_allowed_final_lap.clear()
        self.cars_completed_final_lap.clear()
        self.cars_in_pit.clear()
        self.metrics = TransitionMetrics()
        self._results_persisted = False
        self._ui_notified = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializza lo stato corrente per il salvataggio o invio alla UI."""
        return {
            "state": self.state.value,
            "grace_period_timeout_s": self.grace_period_timeout_s,
            "finalization_timeout_s": self.finalization_timeout_s,
            "session_expired_at": self.session_expired_at,
            "grace_period_started_at": self.grace_period_started_at,
            "finalization_started_at": self.finalization_started_at,
            "cars_allowed_final_lap": list(self.cars_allowed_final_lap),
            "cars_completed_final_lap": list(self.cars_completed_final_lap),
            "cars_in_pit": list(self.cars_in_pit),
            "metrics": self.metrics.to_dict(),
            "_results_persisted": self._results_persisted,
            "_ui_notified": self._ui_notified,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeekendTransitionMachine":
        """Deserializza la state machine da un dizionario."""
        machine = cls()
        machine.state = WeekendTransitionState(data.get("state", "running"))
        machine.grace_period_timeout_s = float(
            data.get("grace_period_timeout_s", 180.0)
        )
        machine.finalization_timeout_s = float(
            data.get("finalization_timeout_s", 60.0)
        )
        machine.session_expired_at = data.get("session_expired_at")
        machine.grace_period_started_at = data.get("grace_period_started_at")
        machine.finalization_started_at = data.get("finalization_started_at")
        machine.cars_allowed_final_lap = set(
            data.get("cars_allowed_final_lap", [])
        )
        machine.cars_completed_final_lap = set(
            data.get("cars_completed_final_lap", [])
        )
        machine.cars_in_pit = set(data.get("cars_in_pit", []))
        machine._results_persisted = bool(
            data.get("_results_persisted", False)
        )
        machine._ui_notified = bool(data.get("_ui_notified", False))
        
        # Ricostruisci metrics se presente
        if "metrics" in data:
            metrics_data = data["metrics"]
            machine.metrics = TransitionMetrics(
                cars_on_track=int(metrics_data.get("cars_on_track", 0)),
                cars_in_pit=int(metrics_data.get("cars_in_pit", 0)),
                cars_completed_final_lap=int(
                    metrics_data.get("cars_completed_final_lap", 0)
                ),
                grace_period_elapsed_s=float(
                    metrics_data.get("grace_period_elapsed_s", 0.0)
                ),
                finalization_elapsed_s=float(
                    metrics_data.get("finalization_elapsed_s", 0.0)
                ),
                last_update_timestamp=float(
                    metrics_data.get("last_update_timestamp", time.time())
                ),
            )
        else:
            # Ricalcola metrics dai set di auto se non presenti
            machine._update_metrics()
        
        return machine


__all__ = [
    "WeekendTransitionState",
    "TransitionMetrics",
    "WeekendTransitionMachine",
]
