#!/usr/bin/env python3
"""
Test automatico del ciclo Practice Sessions: FP1 → FP2 → FP3

Simula un weekend completo di prove libere accelerando il tempo
e verificando che le transizioni avvengano correttamente.

Usage:
    cd "/Users/wizards/Sviluppo/F1 Manager AI"
    .venv/bin/python scripts/test_practice_cycle.py
"""
import sys
import os
import time
from pathlib import Path

# Aggiungi python_backend al path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

from utils.weekend_orchestrator import WeekendOrchestrator, WeekendSessionType, WeekendSessionState
from utils.session_bridge import SessionBridge
from utils.weekend_transition_machine import WeekendTransitionState
from lap_simulator.config_loader import load_circuit_config
from models import RaceCar
from utils import race_cars
import config


class PracticeCycleTester:
    """Test automatico del ciclo FP1 → FP2 → FP3."""

    def __init__(self, circuit_id: str = "jp-1962_suzuka"):
        self.circuit_id = circuit_id
        self.circuit_config = load_circuit_config(circuit_id)
        self.orchestrator = None
        self.bridge = None
        self.test_log = []
        self.errors = []

    def log(self, message: str, level: str = "INFO"):
        """Registra un messaggio nel log di test."""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.test_log.append(log_entry)
        print(log_entry)

    def log_error(self, message: str):
        """Registra un errore."""
        self.log(message, level="ERROR")
        self.errors.append(message)

    def setup_weekend(self):
        """Inizializza il weekend con FP1."""
        self.log("=" * 80)
        self.log("SETUP: Inizializzazione weekend")
        self.log("=" * 80)

        try:
            # Configura circuito
            config.current_circuit = self.circuit_id
            self.log(f"Circuito caricato: {self.circuit_id}")

            # Crea orchestrator (usa default FP1→FP2→FP3→QUALIFY→RACE)
            self.orchestrator = WeekendOrchestrator()
            self.orchestrator.circuit_id = self.circuit_id
            
            # Override sessions: FP1→FP2→FP3→Q1→Q2→Q3→RACE per questo test
            self.orchestrator.sessions = [
                WeekendSessionState(session_type=WeekendSessionType.FP1),
                WeekendSessionState(session_type=WeekendSessionType.FP2),
                WeekendSessionState(session_type=WeekendSessionType.FP3),
                WeekendSessionState(session_type=WeekendSessionType.Q1),
                WeekendSessionState(session_type=WeekendSessionType.Q2),
                WeekendSessionState(session_type=WeekendSessionType.Q3),
                WeekendSessionState(session_type=WeekendSessionType.RACE),
            ]
            self.orchestrator.current_index = 0
            self.orchestrator.sessions[0].activate()
            
            self.log("Weekend Orchestrator creato")
            self.log(f"Sessioni: {[s.session_type.value for s in self.orchestrator.sessions]}")

            # Skip auto creation - il test è sulla transition machine, non sulle auto
            # race_cars.clear()
            # for i in range(1, 21):
            #     car = RaceCar(driver_number=i)
            #     race_cars.append(car)
            # self.log(f"Create {len(race_cars)} auto")
            self.log("⚠️ Skip creazione auto (test focalizzato su transition machine)")

            # Inizializza SessionBridge per FP1
            self.bridge = SessionBridge()
            self.bridge.active = True
            self.bridge.session_kind = "FP1"
            self.log("SessionBridge FP1 creata")

            self.log("✅ SETUP completato con successo")
            return True

        except Exception as e:
            self.log_error(f"❌ SETUP fallito: {e}")
            import traceback
            traceback.print_exc()
            return False

    def simulate_session(self, session_name: str, duration_s: int = 90 * 60):
        """
        Simula una sessione pratica accelerando il tempo.

        Args:
            session_name: Nome sessione (FP1, FP2, FP3)
            duration_s: Durata sessione in secondi (default: 90 minuti)
        """
        self.log("=" * 80)
        self.log(f"SIMULAZIONE: {session_name}")
        self.log("=" * 80)

        if not self.bridge or not self.bridge.active:
            self.log_error(f"{session_name}: SessionBridge non attiva")
            return False

        # Verifica stato iniziale
        state = self.orchestrator.get_transition_state()
        self.log(f"Stato iniziale: {state.value}")

        if state != WeekendTransitionState.RUNNING:
            self.log_error(f"{session_name}: Stato iniziale non è RUNNING")
            return False

        # Simula tempo accelerato
        # Acceleriamo di 1000x: 90 minuti = 5400s → 5.4s reali
        simulation_speed = 1000.0
        real_dt = 0.1  # 100ms per tick
        sim_dt = real_dt * simulation_speed

        total_real_ticks = int(duration_s / sim_dt)
        check_interval = max(1, total_real_ticks // 20)  # Check ogni 5%

        self.log(f"Accelerazione: {simulation_speed}x")
        self.log(f"Durata simulata: {duration_s}s ({duration_s/60:.1f} minuti)")
        self.log(f"Tick totali: {total_real_ticks}")
        self.log("Avvio simulazione...")

        start_time = time.time()

        # Simula il loop principale che aggiorna la transition machine
        # Dopo il primo tick, forza l'expire della sessione per testare la transizione
        for tick in range(total_real_ticks):
            # Aggiorna transition machine
            self.orchestrator.update_transition()

            # Check stato transizione
            state = self.orchestrator.get_transition_state()

            # Log progressi
            if tick % check_interval == 0:
                progress = (tick / total_real_ticks) * 100
                elapsed_real = time.time() - start_time
                self.log(f"Progresso: {progress:.0f}% - Stato: {state.value} - Tempo reale: {elapsed_real:.2f}s")

            # Simula scadenza timer: dopo il primo tick, marca la sessione come scaduta
            # Questo è ciò che farebbe il loop principale quando session_time_remaining <= 0
            if tick == 1 and state == WeekendTransitionState.RUNNING:
                self.log("⏰ Simulo scadenza timer sessione")
                self.orchestrator.expire_current_session()
                continue
            
            # Simula auto che completano ultimo giro: marca come finalizzate
            # In un test reale, questo accadrebbe quando le auto rientrano ai box
            if state == WeekendTransitionState.EXPIRED_GRACE:
                self.log("🏎️ Simulo auto completano ultimo giro e rientrano ai box")
                # Simula 20 auto che completano il giro
                for car_num in range(1, 21):
                    self.orchestrator.mark_car_completed_final_lap(str(car_num))
                    self.orchestrator.mark_car_in_pit(str(car_num))
                # Dopo che tutte le auto sono rientrate, aggiorna la transition machine
                self.orchestrator.update_transition()
                state = self.orchestrator.get_transition_state()
                self.log(f"Stato dopo rientro auto: {state.value}")

            # Se la sessione è finalizzata, persisti risultati e avanza
            if state == WeekendTransitionState.FINALIZING:
                self.log("📊 Persisto risultati sessione")
                
                # Crea dati di classifica fittizi per Q1/Q2 (necessari per testare eliminazione)
                results_data = {"test": True}
                if session_name in ["Q1", "Q2"]:
                    # Genera classifica con 20 auto (Q1) o 15 auto (Q2)
                    num_cars = 20 if session_name == "Q1" else 15
                    classification = []
                    for i in range(1, num_cars + 1):
                        classification.append({
                            "car_number": i,
                            "position": i,
                            "best_lap_time": 90.0 + (i * 0.5)  # Tempi crescenti
                        })
                    results_data["classification"] = classification
                    self.log(f"📋 Generata classifica {session_name} con {num_cars} auto")
                
                self.orchestrator.persist_session_results(results_data)
                
                # Avanza direttamente alla sessione successiva
                self.log("⏭️ Avanzo alla sessione successiva")
                current_idx_before = self.orchestrator.current_index
                
                # Applica eliminazione e logga PRIMA di avanzare
                if session_name == "Q1":
                    self.orchestrator._apply_q1_elimination(results_data)
                    q1_elim = results_data.get("q1_elimination", {})
                    if q1_elim:
                        self.log(f"   🎯 Q1: {q1_elim.get('admitted_count')} ammesse, {q1_elim.get('eliminated_count')} eliminate")
                elif session_name == "Q2":
                    self.orchestrator._apply_q2_elimination(results_data)
                    q2_elim = results_data.get("q2_elimination", {})
                    if q2_elim:
                        self.log(f"   🎯 Q2: {q2_elim.get('admitted_count')} ammesse, {q2_elim.get('eliminated_count')} eliminate")
                
                self.orchestrator.advance_to_next_session(results_data)
                
                # Resetta la transition machine per la nuova sessione
                self.orchestrator.transition_machine.reset()
                
                # Verifica se l'avanzamento è avvenuto
                current_idx_after = self.orchestrator.current_index
                current_session = self.orchestrator.current_session
                if current_idx_after > current_idx_before:
                    session_type = current_session.session_type.value if current_session else 'None'
                    self.log(f"✅ Avanzamento completato: indice {current_idx_before} → {current_idx_after}, sessione: {session_type}")
                    return True  # Sessione completata con successo
                elif current_idx_after == current_idx_before and session_name == "RACE":
                    # RACE è l'ultima sessione del weekend
                    self.log(f"✅ {session_name} completata - Ultima sessione (nessun avanzamento possibile)")
                    return True
                else:
                    self.log_error(f"❌ Avanzamento fallito: indice {current_idx_before} → {current_idx_after}")
                    return False
            
            if state in (WeekendTransitionState.FINALIZING, WeekendTransitionState.NEXT_SESSION):
                self.log(f"Sessione {session_name} completata allo stato {state.value}")
                break

            # Simula tick del bridge (semplificato)
            if self.bridge.active:
                # Qui dovremmo chiamare bridge.tick(sim_dt) ma per il test
                # ci concentriamo sulla transition machine
                pass

        elapsed_real = time.time() - start_time
        self.log(f"Simulazione completata in {elapsed_real:.2f}s reali")

        # Verifica stato finale
        state = self.orchestrator.get_transition_state()
        self.log(f"Stato finale: {state.value}")

        if state == WeekendTransitionState.NEXT_SESSION:
            self.log(f"✅ {session_name} completata - Pronto per sessione successiva")
            return True
        elif state == WeekendTransitionState.FINALIZING:
            self.log(f"⚠️ {session_name} in finalizzazione (timeout 60s)")
            time.sleep(0.5)  # Simula attesa
            self.orchestrator.update_transition()
            state = self.orchestrator.get_transition_state()
            if state == WeekendTransitionState.NEXT_SESSION:
                self.log(f"✅ {session_name} finalizzata - Pronto per sessione successiva")
                return True
            else:
                self.log_error(f"❌ {session_name} non ha raggiunto NEXT_SESSION")
                return False
        else:
            self.log_error(f"❌ {session_name} non completata - Stato: {state.value}")
            return False

    def advance_to_next_session(self):
        """Avanza alla sessione successiva."""
        self.log("=" * 80)
        self.log("AVANZAMENTO: Sessione successiva")
        self.log("=" * 80)

        try:
            # Verifica se può avanzare
            if not self.orchestrator.can_advance_to_next_session():
                self.log_error("Impossibile avanzare: can_advance_to_next_session = False")
                return False

            # Avanza
            result = self.orchestrator.advance_to_next_session()
            if result is None:
                self.log("Nessuna sessione successiva (weekend completato)")
                return False

            # Resetta transition machine
            self.orchestrator.transition_machine.reset()

            # Aggiorna bridge
            next_session = self.orchestrator.current_session
            if next_session:
                self.bridge.session_kind = next_session.value
                self.log(f"SessionBridge aggiornata a: {next_session.value}")

            self.log(f"✅ Avanzato a: {next_session.value}")
            return True

        except Exception as e:
            self.log_error(f"❌ Avanzamento fallito: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_full_test(self):
        """Esegue il test completo del ciclo FP1 → FP2 → FP3."""
        self.log("🏁 START TEST CICLO PRACTICE")
        self.log("=" * 80)

        # Setup
        if not self.setup_weekend():
            return False

        # Ciclo completo: FP1→FP2→FP3→Q1→Q2→Q3→RACE
        sessions = ["FP1", "FP2", "FP3", "Q1", "Q2", "Q3", "RACE"]
        results = {}

        for i, session_name in enumerate(sessions):
            self.log("\n" + "=" * 80)
            self.log(f"SESSIONE {i+1}/7: {session_name}")
            self.log("=" * 80)

            # Simula sessione
            session_ok = self.simulate_session(session_name)
            results[session_name] = session_ok

            if not session_ok:
                self.log_error(f"Sessione {session_name} fallita")
            
            # Per le sessioni non-ultime, verifica che l'avanzamento sia avvenuto
            if i < len(sessions) - 1 and session_ok:
                self.log(f"✅ Avanzamento da {session_name} verificato")
                results[f"{session_name}_advance"] = True
            elif i < len(sessions) - 1:
                self.log_error(f"Avanzamento da {session_name} non avvenuto")
                results[f"{session_name}_advance"] = False
            else:
                # Ultima sessione (RACE): non serve avanzare
                self.log(f"✅ {session_name} completata - Ultima sessione del weekend")

        # Report finale
        self.print_report(results)

        return len(self.errors) == 0

    def print_report(self, results: dict):
        """Stampa il report finale del test."""
        self.log("\n" + "=" * 80)
        self.log("📊 REPORT FINALE")
        self.log("=" * 80)

        # Risultati sessioni
        self.log("\nRISULTATI SESSIONI:")
        for session in ["FP1", "FP2", "FP3", "Q1", "Q2", "Q3", "RACE"]:
            status = "✅ PASS" if results.get(session) else "❌ FAIL"
            self.log(f"  {session}: {status}")

            advance_key = f"{session}_advance"
            if advance_key in results:
                advance_status = "✅ PASS" if results[advance_key] else "❌ FAIL"
                self.log(f"    → Avanzamento: {advance_status}")

        # Transizioni
        self.log("\nTRANSIZIONI:")
        transitions = [
            ("FP1 → FP2", results.get("FP1") and results.get("FP1_advance")),
            ("FP2 → FP3", results.get("FP2") and results.get("FP2_advance")),
            ("FP3 → Q1", results.get("FP3") and results.get("FP3_advance")),
            ("Q1 → Q2", results.get("Q1") and results.get("Q1_advance")),
            ("Q2 → Q3", results.get("Q2") and results.get("Q2_advance")),
            ("Q3 → RACE", results.get("Q3") and results.get("Q3_advance")),
        ]
        for transition, ok in transitions:
            status = "✅ OK" if ok else "❌ FAIL"
            self.log(f"  {transition}: {status}")

        # Errori
        if self.errors:
            self.log(f"\n❌ ERRORI TROVATI: {len(self.errors)}")
            for i, error in enumerate(self.errors, 1):
                self.log(f"  {i}. {error}")
        else:
            self.log("\n✅ NESSUN ERRORE - TEST COMPLETATO CON SUCCESSO")

        # Log completo
        self.log("\n" + "=" * 80)
        self.log("LOG COMPLETO:")
        self.log("=" * 80)
        for entry in self.test_log:
            print(entry)

        # Salva log su file
        log_file = Path(__file__).parent.parent / "python_backend" / "logs" / "practice_cycle_test.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("\n".join(self.test_log))
        self.log(f"\n📄 Log salvato in: {log_file}")


def main():
    """Funzione main."""
    print("=" * 80)
    print("TEST AUTOMATICO CICLO PRACTICE: FP1 → FP2 → FP3")
    print("=" * 80)
    print()

    tester = PracticeCycleTester(circuit_id="jp-1962_suzuka")
    success = tester.run_full_test()

    print()
    print("=" * 80)
    if success:
        print("✅ TEST COMPLETATO CON SUCCESSO")
        sys.exit(0)
    else:
        print("❌ TEST FALLITO - Controlla gli errori nel log")
        sys.exit(1)


if __name__ == "__main__":
    main()