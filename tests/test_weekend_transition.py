"""
Test per Weekend Transition State Machine.

Test deterministici per validare le transizioni tra sessioni del weekend.
"""
import pytest
import sys
import time
from pathlib import Path

# Aggiungi python_backend al path per gli import
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

from utils.weekend_transition_machine import (
    WeekendTransitionMachine,
    WeekendTransitionState,
    TransitionMetrics,
)


class TestWeekendTransitionState:
    """Test per l'enum degli stati."""
    
    def test_states_exist(self):
        """Verifica che tutti gli stati siano definiti."""
        assert WeekendTransitionState.RUNNING.value == "running"
        assert WeekendTransitionState.EXPIRED_GRACE.value == "expired_grace"
        assert WeekendTransitionState.FINALIZING.value == "finalizing"
        assert WeekendTransitionState.NEXT_SESSION.value == "next_session"


class TestTransitionMachineInitialization:
    """Test per l'inizializzazione della state machine."""
    
    def test_default_state_is_running(self):
        """Lo stato iniziale deve essere RUNNING."""
        machine = WeekendTransitionMachine()
        assert machine.state == WeekendTransitionState.RUNNING
    
    def test_default_timeouts(self):
        """I timeout di default devono essere 180s e 60s."""
        machine = WeekendTransitionMachine()
        assert machine.grace_period_timeout_s == 180.0
        assert machine.finalization_timeout_s == 60.0
    
    def test_initial_cars_sets_are_empty(self):
        """I set di auto devono essere vuoti all'inizio."""
        machine = WeekendTransitionMachine()
        assert len(machine.cars_allowed_final_lap) == 0
        assert len(machine.cars_completed_final_lap) == 0
        assert len(machine.cars_in_pit) == 0
    
    def test_initial_timestamps_are_none(self):
        """I timestamp devono essere None all'inizio."""
        machine = WeekendTransitionMachine()
        assert machine.session_expired_at is None
        assert machine.grace_period_started_at is None
        assert machine.finalization_started_at is None


class TestExpireSession:
    """Test per la transizione RUNNING → EXPIRED_GRACE."""
    
    def test_expire_session_from_running(self):
        """expire_session() deve transitare a EXPIRED_GRACE."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        
        assert machine.state == WeekendTransitionState.EXPIRED_GRACE
        assert machine.session_expired_at == 1000.0
        assert machine.grace_period_started_at == 1000.0
    
    def test_expire_session_sets_metrics(self):
        """expire_session() deve aggiornare le metriche."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        
        assert machine.metrics.last_update_timestamp == 1000.0
    
    def test_expire_session_from_non_running_does_nothing(self):
        """expire_session() da stato non-RUNNING non deve fare nulla."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.expire_session(timestamp=1001.0)  # Secondo chiamata
        
        assert machine.state == WeekendTransitionState.EXPIRED_GRACE
        assert machine.session_expired_at == 1000.0  # Non cambiato


class TestGracePeriod:
    """Test per il grace period e ultimo giro."""
    
    def test_allow_final_lap_adds_car(self):
        """allow_final_lap() deve aggiungere l'auto al set."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.allow_final_lap("CAR_1")
        
        assert "CAR_1" in machine.cars_allowed_final_lap
    
    def test_mark_car_completed_final_lap_removes_from_allowed(self):
        """mark_car_completed_final_lap() deve rimuovere dall'allowed."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.allow_final_lap("CAR_1")
        machine.mark_car_completed_final_lap("CAR_1")
        
        assert "CAR_1" not in machine.cars_allowed_final_lap
        assert "CAR_1" in machine.cars_completed_final_lap
    
    def test_mark_car_in_pit_completes_lap_implicitly(self):
        """mark_car_in_pit() deve completare implicitamente l'ultimo giro."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.allow_final_lap("CAR_1")
        machine.mark_car_in_pit("CAR_1")
        
        assert "CAR_1" not in machine.cars_allowed_final_lap
        assert "CAR_1" in machine.cars_completed_final_lap
        assert "CAR_1" in machine.cars_in_pit
    
    def test_all_cars_finalized_when_no_allowed_cars(self):
        """_all_cars_finalized() deve essere True quando non ci sono auto allowed."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.allow_final_lap("CAR_1")
        machine.allow_final_lap("CAR_2")
        
        assert not machine._all_cars_finalized()
        
        machine.mark_car_completed_final_lap("CAR_1")
        machine.mark_car_completed_final_lap("CAR_2")
        
        assert machine._all_cars_finalized()


class TestGracePeriodTimeout:
    """Test per il timeout del grace period."""
    
    def test_grace_period_timeout_after_180s(self):
        """Il grace period deve scadere dopo 180 secondi."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.allow_final_lap("CAR_1")
        
        # A 179s, il timeout non è ancora raggiunto
        assert not machine._check_grace_period_timeout(timestamp=1179.0)
        
        # A 180s, il timeout è raggiunto
        assert machine._check_grace_period_timeout(timestamp=1180.0)
    
    def test_grace_period_timeout_forces_transition(self):
        """Il timeout del grace period deve forzare la transizione a FINALIZING."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.allow_final_lap("CAR_1")  # Auto ancora in pista
        
        # Aggiorna a t=1180s (180s dopo)
        machine.update(timestamp=1180.0)
        
        assert machine.state == WeekendTransitionState.FINALIZING
        assert "CAR_1" in machine.cars_completed_final_lap  # Forzata


class TestFinalization:
    """Test per la fase di finalizzazione."""
    
    def test_start_finalization_from_expired_grace(self):
        """start_finalization() deve transitare a FINALIZING."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.start_finalization(timestamp=1001.0)
        
        assert machine.state == WeekendTransitionState.FINALIZING
        assert machine.finalization_started_at == 1001.0
    
    def test_start_finalization_from_wrong_state_does_nothing(self):
        """start_finalization() da stato sbagliato non deve fare nulla."""
        machine = WeekendTransitionMachine()
        machine.start_finalization(timestamp=1000.0)  # Stato RUNNING
        
        assert machine.state == WeekendTransitionState.RUNNING
    
    def test_mark_results_persisted(self):
        """mark_results_persisted() deve settare il flag."""
        machine = WeekendTransitionMachine()
        assert not machine._results_persisted
        
        machine.mark_results_persisted()
        assert machine._results_persisted
    
    def test_can_advance_only_when_finalizing_and_ready(self):
        """can_advance deve essere True solo in FINALIZING con risultati persistiti."""
        machine = WeekendTransitionMachine()
        
        # RUNNING: False
        assert not machine.can_advance
        
        # EXPIRED_GRACE: False
        machine.expire_session(timestamp=1000.0)
        assert not machine.can_advance
        
        # Auto in pista allo scadere del timer
        machine.allow_final_lap("CAR_1")
        assert "CAR_1" in machine.cars_allowed_final_lap
        
        # FINALIZING ma risultati non persistiti: False
        machine.start_finalization(timestamp=1001.0)
        assert not machine.can_advance
        
        # FINALIZING con risultati persistiti ma auto ancora in pista: False
        machine.mark_results_persisted()
        assert not machine.can_advance  # CAR_1 ancora in cars_allowed_final_lap
        
        # FINALIZING con risultati persistiti e tutte le auto finalizzate: True
        machine.mark_car_completed_final_lap("CAR_1")
        assert machine.can_advance
        
        # Nota: se non ci sono auto in pista (sessione vuota), can_advance è True
        # non appena i risultati sono persistiti (comportamento corretto)
        machine2 = WeekendTransitionMachine()
        machine2.expire_session(timestamp=1000.0)
        machine2.start_finalization(timestamp=1001.0)
        machine2.mark_results_persisted()
        assert machine2.can_advance  # Corretto: 0 auto = tutte finalizzate
        assert machine2.can_advance


class TestFinalizationTimeout:
    """Test per il timeout di finalizzazione."""
    
    def test_finalization_timeout_after_60s(self):
        """La finalizzazione deve scadere dopo 60 secondi."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.start_finalization(timestamp=1001.0)
        
        # A 59s, il timeout non è ancora raggiunto
        assert not machine._check_finalization_timeout(timestamp=1060.0)
        
        # A 60s, il timeout è raggiunto
        assert machine._check_finalization_timeout(timestamp=1061.0)
    
    def test_finalization_timeout_forces_transition(self):
        """Il timeout di finalizzazione deve forzare NEXT_SESSION."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.start_finalization(timestamp=1001.0)
        
        # Aggiorna a t=1061s (60s dopo)
        machine.update(timestamp=1061.0)
        
        assert machine.state == WeekendTransitionState.NEXT_SESSION


class TestCompleteTransition:
    """Test per il completamento della transizione."""
    
    def test_complete_transition_from_finalizing(self):
        """complete_transition() deve transitare a NEXT_SESSION."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.start_finalization(timestamp=1001.0)
        machine.complete_transition()
        
        assert machine.state == WeekendTransitionState.NEXT_SESSION
    
    def test_complete_transition_from_wrong_state_does_nothing(self):
        """complete_transition() da stato sbagliato non deve fare nulla."""
        machine = WeekendTransitionMachine()
        machine.complete_transition()  # Stato RUNNING
        
        assert machine.state == WeekendTransitionState.RUNNING


class TestReset:
    """Test per il reset della state machine."""
    
    def test_reset_clears_all_state(self):
        """reset() deve riportare la machine allo stato iniziale."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.allow_final_lap("CAR_1")
        machine.start_finalization(timestamp=1001.0)
        machine.mark_results_persisted()
        
        machine.reset()
        
        assert machine.state == WeekendTransitionState.RUNNING
        assert machine.session_expired_at is None
        assert machine.grace_period_started_at is None
        assert machine.finalization_started_at is None
        assert len(machine.cars_allowed_final_lap) == 0
        assert len(machine.cars_completed_final_lap) == 0
        assert len(machine.cars_in_pit) == 0
        assert not machine._results_persisted


class TestSerialization:
    """Test per serializzazione e deserializzazione."""
    
    def test_to_dict_contains_all_fields(self):
        """to_dict() deve includere tutti i campi rilevanti."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.allow_final_lap("CAR_1")
        
        data = machine.to_dict()
        
        assert data["state"] == "expired_grace"
        assert data["session_expired_at"] == 1000.0
        assert data["grace_period_started_at"] == 1000.0
        assert "CAR_1" in data["cars_allowed_final_lap"]
    
    def test_from_dict_restores_state(self):
        """from_dict() deve ripristinare lo stato correttamente."""
        data = {
            "state": "finalizing",
            "session_expired_at": 1000.0,
            "grace_period_started_at": 1000.0,
            "finalization_started_at": 1001.0,
            "cars_allowed_final_lap": ["CAR_1", "CAR_2"],
            "cars_completed_final_lap": ["CAR_3"],
            "cars_in_pit": ["CAR_4"],
            "_results_persisted": True,
            "_ui_notified": False,
            "metrics": {
                "cars_on_track": 2,
                "cars_in_pit": 1,
                "cars_completed_final_lap": 1,
                "grace_period_elapsed_s": 1.0,
                "finalization_elapsed_s": 0.5,
                "last_update_timestamp": 1001.5,
            },
        }
        
        machine = WeekendTransitionMachine.from_dict(data)
        
        assert machine.state == WeekendTransitionState.FINALIZING
        assert machine.session_expired_at == 1000.0
        assert "CAR_1" in machine.cars_allowed_final_lap
        assert "CAR_3" in machine.cars_completed_final_lap
        assert machine._results_persisted is True
    
    def test_roundtrip_serialization(self):
        """Un roundtrip to_dict -> from_dict deve preservare lo stato."""
        original = WeekendTransitionMachine()
        original.expire_session(timestamp=1000.0)
        original.allow_final_lap("CAR_1")
        original.allow_final_lap("CAR_2")
        original.mark_car_completed_final_lap("CAR_1")
        original.start_finalization(timestamp=1001.0)
        original.mark_results_persisted()
        
        data = original.to_dict()
        restored = WeekendTransitionMachine.from_dict(data)
        
        assert restored.state == original.state
        assert restored.session_expired_at == original.session_expired_at
        assert restored.cars_allowed_final_lap == original.cars_allowed_final_lap
        assert restored.cars_completed_final_lap == original.cars_completed_final_lap
        assert restored._results_persisted == original._results_persisted


class TestMetrics:
    """Test per le metriche di transizione."""
    
    def test_metrics_update_cars_on_track(self):
        """Le metriche devono aggiornare il numero di auto in pista."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.allow_final_lap("CAR_1")
        machine.allow_final_lap("CAR_2")
        machine.update(timestamp=1001.0)
        
        assert machine.metrics.cars_on_track == 2
    
    def test_metrics_update_cars_in_pit(self):
        """Le metriche devono aggiornare il numero di auto ai box."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.mark_car_in_pit("CAR_1")
        machine.mark_car_in_pit("CAR_2")
        machine.mark_car_in_pit("CAR_3")
        machine.update(timestamp=1001.0)
        
        assert machine.metrics.cars_in_pit == 3
    
    def test_metrics_update_elapsed_times(self):
        """Le metriche devono aggiornare i tempi elapsed."""
        machine = WeekendTransitionMachine()
        machine.expire_session(timestamp=1000.0)
        machine.update(timestamp=1050.0)
        
        assert machine.metrics.grace_period_elapsed_s == 50.0
        
        machine.start_finalization(timestamp=1050.0)
        machine.update(timestamp=1080.0)
        
        assert machine.metrics.finalization_elapsed_s == 30.0


class TestIntegration:
    """Test di integrazione per il flusso completo."""
    
    def test_full_transition_flow_all_cars_pit(self):
        """Flusso completo: tutte le auto rientrano ai box."""
        machine = WeekendTransitionMachine()
        
        # Sessione in corso
        assert machine.state == WeekendTransitionState.RUNNING
        
        # Timer scaduto
        machine.expire_session(timestamp=1000.0)
        assert machine.state == WeekendTransitionState.EXPIRED_GRACE
        
        # 3 auto in pista, 17 ai box
        machine.allow_final_lap("CAR_1")
        machine.allow_final_lap("CAR_2")
        machine.allow_final_lap("CAR_3")
        for i in range(4, 21):
            machine.mark_car_in_pit(f"CAR_{i}")
        
        # Auto 1 e 2 completano l'ultimo giro
        machine.mark_car_completed_final_lap("CAR_1")
        machine.mark_car_completed_final_lap("CAR_2")
        
        # Aggiorna: ancora in EXPIRED_GRACE (CAR_3 ancora in pista)
        machine.update(timestamp=1010.0)
        assert machine.state == WeekendTransitionState.EXPIRED_GRACE
        
        # Anche CAR_3 completa
        machine.mark_car_completed_final_lap("CAR_3")
        
        # Aggiorna: transizione a FINALIZING
        machine.update(timestamp=1020.0)
        assert machine.state == WeekendTransitionState.FINALIZING
        
        # Persisti risultati
        machine.mark_results_persisted()
        
        # Aggiorna: transizione a NEXT_SESSION
        machine.update(timestamp=1030.0)
        assert machine.state == WeekendTransitionState.NEXT_SESSION
    
    def test_full_transition_flow_grace_timeout(self):
        """Flusso completo: grace period scaduto per timeout."""
        machine = WeekendTransitionMachine()
        
        # Timer scaduto
        machine.expire_session(timestamp=1000.0)
        
        # 1 auto bloccata in pista
        machine.allow_final_lap("CAR_1")
        
        # Aspetta 180s
        machine.update(timestamp=1180.0)
        
        # Deve essere in FINALIZING con CAR_1 forzata
        assert machine.state == WeekendTransitionState.FINALIZING
        assert "CAR_1" in machine.cars_completed_final_lap
        
        # Persisti risultati
        machine.mark_results_persisted()
        
        # Aspetta 60s
        machine.update(timestamp=1240.0)
        
        # Deve essere in NEXT_SESSION
        assert machine.state == WeekendTransitionState.NEXT_SESSION
    
    def test_full_transition_flow_finalization_timeout(self):
        """Flusso completo: finalizzazione scaduta per timeout."""
        machine = WeekendTransitionMachine()
        
        # Timer scaduto
        machine.expire_session(timestamp=1000.0)
        
        # Tutte le auto rientrano subito
        for i in range(1, 21):
            machine.mark_car_in_pit(f"CAR_{i}")
        
        # Transita a FINALIZING
        machine.update(timestamp=1010.0)
        assert machine.state == WeekendTransitionState.FINALIZING
        
        # Risultati NON persistiti (problema tecnico)
        # Aspetta 60s di timeout
        machine.update(timestamp=1070.0)
        
        # Deve essere in NEXT_SESSION comunque
        assert machine.state == WeekendTransitionState.NEXT_SESSION


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
