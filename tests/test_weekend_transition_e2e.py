"""
Test end-to-end per la Weekend Transition State Machine.

Simula scenari reali di transizione tra sessioni del weekend.
"""
import pytest
import sys
from pathlib import Path

# Aggiungi python_backend al path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

from utils.weekend_orchestrator import WeekendOrchestrator, WeekendSessionType
from utils.weekend_transition_machine import WeekendTransitionState


class TestEndToEndSessionTransition:
    """Test end-to-end per transizioni complete tra sessioni."""
    
    def test_fp1_to_fp2_transition_all_cars_pit(self):
        """Transizione FP1→FP2 con tutte le auto che rientrano ai box."""
        orchestrator = WeekendOrchestrator()
        orchestrator.start(circuit_id="MONZA", session_type=WeekendSessionType.FP1)
        
        # Verifica stato iniziale
        assert orchestrator.current_session_type == "FP1"
        assert orchestrator.transition_machine.state == WeekendTransitionState.RUNNING
        
        # Simula scadenza timer FP1
        orchestrator.expire_current_session(timestamp=1000.0)
        assert orchestrator.transition_machine.state == WeekendTransitionState.EXPIRED_GRACE
        
        # 20 auto in pista allo scadere del timer
        for i in range(1, 21):
            orchestrator.allow_final_lap(f"CAR_{i:02d}")
        
        # Verifica che ci siano auto autorizzate all'ultimo giro
        assert len(orchestrator.transition_machine.cars_allowed_final_lap) == 20
        
        # Auto rientrano ai box gradualmente
        for i in range(1, 21):
            orchestrator.mark_car_in_pit(f"CAR_{i:02d}")
        
        # Aggiorna la transition machine
        orchestrator.update_transition(timestamp=1010.0)
        
        # Deve essere in FINALIZING (tutte le auto rientrate)
        assert orchestrator.transition_machine.state == WeekendTransitionState.FINALIZING
        
        # Persisti i risultati
        orchestrator.persist_session_results({
            "session_type": "FP1",
            "best_lap": 92.5,
            "total_laps": 45,
        })
        
        # Aggiorna per completare la transizione
        orchestrator.update_transition(timestamp=1020.0)
        
        # Ora dovrebbe essere in NEXT_SESSION e aver avanzato a FP2
        assert orchestrator.current_session_type == "FP2"
        assert orchestrator.transition_machine.state == WeekendTransitionState.RUNNING
    
    def test_fp1_to_fp2_transition_grace_timeout(self):
        """Transizione FP1→FP2 con grace period scaduto per timeout."""
        orchestrator = WeekendOrchestrator()
        orchestrator.start(circuit_id="MONZA", session_type=WeekendSessionType.FP1)
        
        # Simula scadenza timer FP1
        orchestrator.expire_current_session(timestamp=1000.0)
        
        # 1 auto bloccata in pista (non rientra)
        orchestrator.allow_final_lap("CAR_01")
        
        # Aspetta 180s di grace period
        orchestrator.update_transition(timestamp=1180.0)
        
        # Deve essere in FINALIZING con auto forzata
        assert orchestrator.transition_machine.state == WeekendTransitionState.FINALIZING
        assert "CAR_01" in orchestrator.transition_machine.cars_completed_final_lap
        
        # Persisti risultati
        orchestrator.persist_session_results({"session_type": "FP1"})
        
        # Aspetta 60s di finalization timeout
        orchestrator.update_transition(timestamp=1240.0)
        
        # Deve aver avanzato a FP2
        assert orchestrator.current_session_type == "FP2"
    
    def test_qualifying_to_race_transition(self):
        """Transizione Qualifying→Race con griglia."""
        orchestrator = WeekendOrchestrator()
        orchestrator.start(circuit_id="MONZA", session_type=WeekendSessionType.QUALIFYING)
        
        # Simula qualifica completata
        orchestrator.expire_current_session(timestamp=2000.0)
        
        # Tutte le auto rientrano
        for i in range(1, 21):
            orchestrator.allow_final_lap(f"CAR_{i:02d}")
            orchestrator.mark_car_in_pit(f"CAR_{i:02d}")
        
        # Aggiorna
        orchestrator.update_transition(timestamp=2010.0)
        assert orchestrator.transition_machine.state == WeekendTransitionState.FINALIZING
        
        # Persisti risultati qualifica
        orchestrator.persist_session_results({
            "session_type": "QUALIFYING",
            "pole_position": "CAR_01",
            "grid": [{"position": i, "car_id": f"CAR_{i:02d}"} for i in range(1, 21)],
        })
        
        # Completa transizione
        orchestrator.update_transition(timestamp=2020.0)
        
        # Ora dovrebbe essere in Race
        assert orchestrator.current_session_type == "RACE"
        assert orchestrator.transition_machine.state == WeekendTransitionState.RUNNING
    
    def test_race_to_end_of_weekend(self):
        """Transizione Race→Fine Weekend."""
        orchestrator = WeekendOrchestrator()
        
        # Avvia weekend da Race (per test più veloce)
        orchestrator.start(circuit_id="MONZA", session_type=WeekendSessionType.RACE)
        
        # Simula gara completata
        orchestrator.expire_current_session(timestamp=5000.0)
        
        # Tutte le auto completano la gara
        for i in range(1, 21):
            orchestrator.allow_final_lap(f"CAR_{i:02d}")
            orchestrator.mark_car_in_pit(f"CAR_{i:02d}")
        
        # Aggiorna
        orchestrator.update_transition(timestamp=5010.0)
        assert orchestrator.transition_machine.state == WeekendTransitionState.FINALIZING
        
        # Persisti risultati gara
        orchestrator.persist_session_results({
            "session_type": "RACE",
            "winner": "CAR_01",
            "classification": [{"position": i, "car_id": f"CAR_{i:02d}"} for i in range(1, 21)],
        })
        
        # Completa transizione
        orchestrator.update_transition(timestamp=5020.0)
        
        # Weekend completato
        assert orchestrator.is_complete is True
        # La sessione corrente è Race (completata), non c'è sessione successiva
        assert orchestrator.current_session_type == "RACE"
        assert orchestrator.next_session_type is None


class TestTransitionMetrics:
    """Test per le metriche di transizione."""
    
    def test_metrics_tracked_during_transition(self):
        """Le metriche devono essere tracciate correttamente."""
        orchestrator = WeekendOrchestrator()
        orchestrator.start(circuit_id="MONZA", session_type=WeekendSessionType.FP1)
        
        # Scadenza timer
        orchestrator.expire_current_session(timestamp=1000.0)
        
        # 5 auto in pista
        for i in range(1, 6):
            orchestrator.allow_final_lap(f"CAR_{i:02d}")
        
        # Aggiorna metriche
        orchestrator.update_transition(timestamp=1010.0)
        
        metrics = orchestrator.get_transition_metrics()
        assert metrics["cars_on_track"] == 5
        assert metrics["cars_in_pit"] == 0
        assert metrics["grace_period_elapsed_s"] == 10.0
        
        # 3 auto rientrano
        for i in range(1, 4):
            orchestrator.mark_car_in_pit(f"CAR_{i:02d}")
        
        orchestrator.update_transition(timestamp=1020.0)
        
        metrics = orchestrator.get_transition_metrics()
        assert metrics["cars_on_track"] == 2
        assert metrics["cars_in_pit"] == 3
        assert metrics["grace_period_elapsed_s"] == 20.0
    
    def test_can_advance_flag(self):
        """Il flag can_advance deve essere accurato."""
        orchestrator = WeekendOrchestrator()
        orchestrator.start(circuit_id="MONZA", session_type=WeekendSessionType.FP1)
        
        # Inizialmente non può avanzare
        assert orchestrator.can_advance_to_next_session() is False
        
        # Scadenza timer
        orchestrator.expire_current_session(timestamp=1000.0)
        assert orchestrator.can_advance_to_next_session() is False
        
        # Auto in pista
        orchestrator.allow_final_lap("CAR_01")
        assert orchestrator.can_advance_to_next_session() is False
        
        # Finalizzazione
        orchestrator.update_transition(timestamp=1180.0)  # Timeout grace
        assert orchestrator.can_advance_to_next_session() is False
        
        # Persisti risultati
        orchestrator.persist_session_results({"test": "data"})
        
        # Ora può avanzare
        assert orchestrator.can_advance_to_next_session() is True


class TestSerialization:
    """Test per serializzazione con transition machine."""
    
    def test_orchestrator_roundtrip_with_transition(self):
        """Roundtrip to_dict -> from_dict con transition machine."""
        orchestrator = WeekendOrchestrator()
        orchestrator.start(circuit_id="MONZA", session_type=WeekendSessionType.FP1)
        
        # Simula transizione parziale
        orchestrator.expire_current_session(timestamp=1000.0)
        orchestrator.allow_final_lap("CAR_01")
        orchestrator.allow_final_lap("CAR_02")
        orchestrator.mark_car_completed_final_lap("CAR_01")
        
        # Serializza
        data = orchestrator.to_dict()
        
        # Verifica che la transition machine sia serializzata
        assert "transition_machine" in data
        assert data["transition_machine"]["state"] == "expired_grace"
        assert "CAR_01" in data["transition_machine"]["cars_completed_final_lap"]
        
        # Deserializza
        restored = WeekendOrchestrator.from_dict(data)
        
        # Verifica stato ripristinato
        assert restored.current_session_type == "FP1"
        assert restored.transition_machine.state == WeekendTransitionState.EXPIRED_GRACE
        assert "CAR_01" in restored.transition_machine.cars_completed_final_lap
        assert "CAR_02" in restored.transition_machine.cars_allowed_final_lap
    
    def test_save_load_mid_transition(self):
        """Salvataggio e caricamento a metà transizione."""
        orchestrator = WeekendOrchestrator()
        orchestrator.start(circuit_id="MONZA", session_type=WeekendSessionType.FP1)
        
        # Transizione in corso
        orchestrator.expire_current_session(timestamp=1000.0)
        for i in range(1, 11):
            orchestrator.allow_final_lap(f"CAR_{i:02d}")
        
        # 5 auto rientrano
        for i in range(1, 6):
            orchestrator.mark_car_in_pit(f"CAR_{i:02d}")
        
        # Aggiorna le metriche prima di salvare
        orchestrator.update_transition(timestamp=1010.0)
        
        # Salva
        data = orchestrator.to_dict()
        
        # Carica
        restored = WeekendOrchestrator.from_dict(data)
        
        # Verifica
        assert restored.transition_machine.state == WeekendTransitionState.EXPIRED_GRACE
        assert restored.transition_machine.metrics.cars_on_track == 5
        assert restored.transition_machine.metrics.cars_in_pit == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
