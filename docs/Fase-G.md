---
title: Fase G — Weekend di gara completo
version: 0.3
last_updated: 2026-04-01
status: "COMPLETATO — tutti gli 8 punti implementati"
scope: "Weekend di gara completo con cleanup architetturale aggressivo, transizioni weekend, Qualifying e Race"
---

# Fase G — Weekend di gara completo

Fase G porta il motore da una singola sessione practice a un weekend completo, consolidando anche la nomenclatura dei file e rimuovendo gli ultimi legacy path non più necessari.

La transizione tra sessioni non va trattata come un semplice incremento lineare: richiede una state machine dedicata con criteri di avanzamento, persistenza e side effect su UI e backend.

## Roadmap in 8 punti

### 1) ✅ Cleanup architetturale e nomenclatura — **COMPLETATO**

**Stato**: ✅ Completato il 2026-03-29

**Azioni eseguite**:
- Rimossi 10 file legacy orfani (6 backend + 4 frontend)
- Migrato route `/race` al frontend V3 canonico
- Allineata documentazione di migrazione
- Test di import backend: passato
- Test di riferimenti residui: nessuno trovato

**File rimossi**:
- Backend: `api_legacy.py.old`, `models_v1.py`, `game_logic_v1.py`, `simulation_v1.py`, `performance_v1.py`, `dashboard.legacy.js`
- Frontend: `index.html`, `base.html`, `dashboard-v1.css`, `dashboard-v1.js`

### 2) ✅ Weekend Orchestrator e state model — **COMPLETATO**

**Stato**: ✅ Completato

Obiettivo: introdurre un layer superiore al `SessionBridge` per governare l'intero weekend.

Deliverable:

- modello di stato weekend con sessione corrente, risultati intermedi e stato globale;
- macchina a stati per avanzare tra FP1, FP2, FP3, Qualifying e Race;
- serializzazione e deserializzazione del weekend completo;
- propagazione del tipo sessione al runtime e al backend.

> Nota: la policy di avanzamento del weekend è trattata come item separato al punto 3.

### 3) ✅ Weekend transition state machine — **COMPLETATO**

**Stato**: ✅ Completato il 2026-03-30

**Approvato**:
- ✅ State machine a 3 stati + transizione automatica
- ✅ Grace period 180s per ultimi giri (regolamento F1)
- ✅ Timeout finalizzazione 60s per auto bloccate
- ✅ Avanzamento automatico (nessuna conferma utente)
- ⚠️ Red flag/abort rimandato a implementazione futura

**Implementato**:
- `utils/weekend_transition_machine.py` (429 righe)
- `tests/test_weekend_transition.py` (32 test)
- `tests/test_weekend_transition_e2e.py` (8 test e2e)
- Integrazione con `WeekendOrchestrator` e `SessionBridge`
- Esposizione UI tramite payload `race_update`

Obiettivo: definire come il weekend passa da una sessione alla successiva senza assumere un semplice `next_session()`.

Deliverable:

- ✅ criteri di avanzamento per FP1→FP2, FP2→FP3, FP3→Qualifying e Qualifying→Race;
- ✅ handshake con garage, persistenza e UI prima del cambio sessione;
- ✅ salvataggio del contesto di sessione, risultati intermedi e lock di fine sessione;
- ⚠️ eventi di transizione e gestione fallback in caso di pause, abort o restart (red flag rimandato);
- ✅ test deterministici sulla state machine del weekend;

#### Criteri operativi di transizione

La sessione passa alla successiva automaticamente quando entra nello stato `FINALIZING`.

**Transizioni:**
- `RUNNING` → `EXPIRED_GRACE`: timer sessione = 0
- `EXPIRED_GRACE` → `FINALIZING`: tutte le auto ai box O timeout 180s
- `FINALIZING` → `NEXT_SESSION`: risultati persistiti, timeout 60s O tutte auto finalizzate

**Regole:**
- il timer della sessione corrente è a zero, oppure la sessione è stata chiusa da un evento equivalente;
- tutte le auto risultano ai box oppure sono state finalizzate dopo l'ultimo attraversamento valido del traguardo;
- un'auto ancora in pista quando scatta il timer può completare **solo un ultimo passaggio** e poi viene forzata ai box;
- nessuna auto può iniziare un nuovo giro valido dopo lo scadere del timer;
- risultati, best lap, classifiche, note e telemetry della sessione corrente sono consolidati e persistiti;
- il runtime è entrato in una fase di finalizzazione che blocca nuove run e nuovi giri;
- se un'auto resta bloccata in uno stato intermedio, è ammesso un timeout di sicurezza per chiudere la finalizzazione;
- **NOTA**: pause, abort e red flag saranno gestiti in un futuro aggiornamento (stato `RED_FLAG_PAUSE` da aggiungere).

**Timeout:**
- Grace period: 180 secondi (3 minuti) per completare ultimi giri
- Finalizzazione timeout: 60 secondi per auto bloccate

Flusso della state machine:

- `RUNNING` → sessione in corso, timer attivo
- `EXPIRED_GRACE` → timer scaduto, auto in pista completano ultimo giro (max 180s)
- `FINALIZING` → tutte le auto ai box, consolidamento risultati (max 60s)
- `NEXT_SESSION` → transizione in corso, avvio nuova sessione

### 4) ✅ Qualifying subsystem — **COMPLETATO**

**Stato**: ✅ Completato il 2026-03-29

Obiettivo: implementare Q1, Q2 e Q3 come flusso dedicato con regole proprie.

Deliverable:

- ✅ timer e fasi qualifying-oriented tramite `QualifyingSessionState`;
- ✅ taglio progressivo dei classificati e gestione degli esclusi;
- ✅ regole tyre-specifiche e out-lap / flying lap / cool-down;
- ✅ classifica finale di qualifica e griglia provvisoria;
- ✅ eventi e telemetry per UI e QA.

### 5) ✅ Race subsystem — **COMPLETATO**

**Stato**: ✅ Completato il 2026-04-01

Obiettivo: trasformare il runtime in una vera sessione gara con partenza, stint e arrivo.

**Input dalla qualifica**: griglia finale (`final_grid`) esportata da `QualifyingSessionState`.

**Implementato**:
- `utils/race_session.py` — `RaceSessionState`, `RaceDriverState`, `RaceLapRecord` con serializzazione completa
- `tests/test_race_session.py` — 45 test (start, record_lap, pit_stop, finalize, serialization, delegazione orchestrator)
- Bug fix: deduplicazione griglia in `RaceSessionState.start()` quando si passano sia `starting_grid` che `participants`
- Metodi delegazione in `WeekendOrchestrator`: `start_race`, `record_race_lap`, `finalize_race`

Deliverable:

- ✅ procedura di start e formazione griglia (da `final_grid` della qualifica);
- ✅ registrazione giri di gara con posizione, gap, stint e tyre info;
- ✅ pit stop con cambio gomme e aggiornamento stint;
- ✅ classificazione con ordine d'arrivo, gap al leader, distacco, pit stop e stati finali;
- ✅ ritiro auto con motivo;
- ✅ integrazione con `WeekendOrchestrator` e `SessionBridge`;
- ✅ transizione pulita da qualifica a gara (`finalize_qualifying` → `start_race`);
- ✅ pit strategy AI (logica autonoma per decidere quando fare pit in gara - compound, giro target, undercut/overcut);
- ✅ Red flag / Safety Car (stato `RED_FLAG_PAUSE` nella transition machine implementato).

### 6) ✅ Backend/API/UI integration — **COMPLETATO**

**Stato**: ✅ Completato il 2026-04-01

Obiettivo: esporre il weekend completo alla UI senza rompere il flusso attuale.

**Implementato**:

- ✅ `GET /api/weekend/status` — stato weekend, sessioni, indice corrente
- ✅ `GET /api/weekend/session/results` — risultati sessione corrente o specifica
- ✅ `GET /api/weekend/qualifying/grid` — griglia finale di qualifica
- ✅ `GET /api/weekend/race/status` — running order e classifica gara in tempo reale
- ✅ `GET /api/weekend/transition/state` — stato transition machine
- ✅ `POST /api/weekend/advance` — avanza alla sessione successiva
- ✅ `POST /api/weekend/force_end` — forza fine sessione (test/debug)
- ✅ `POST /api/weekend/reset` — reset weekend completo
- ✅ payload `race_update` esteso con `weekend_session_type` e `race_running_order`
- ✅ fix `can_advance_transition()` in `WeekendOrchestrator`

### 7) ✅ Pagina transizione e consultazione risultati sessioni — **COMPLETATO**

**Stato**: ✅ Completato

Obiettivo: offrire una vista di transizione che mostra i risultati già registrati e porta alla sessione successiva del weekend.

**Implementato**:
- `templates/session-transition.html` — pagina completa con:
  - ✅ overview del weekend con timeline FP1→FP2→FP3→Q1→Q2→Q3→Race
  - ✅ dettaglio sessione con classifica dinamica
  - ✅ colonne adattive per tipo sessione: FP/Q (best lap, giri) vs RACE (gap, distacco, pit stop, stato)
  - ✅ sezione eliminazione per Q1 (top 15) e Q2 (top 10)
  - ✅ pulsante avanzamento sessione
  - ✅ route `/session-transition` nel backend

### 8) ✅ Persistenza, telemetry e QA — **COMPLETATO**

**Stato**: ✅ Completato il 2026-04-01

Obiettivo: rendere il weekend verificabile, salvabile e testabile end-to-end.

**Implementato**:
- ✅ save/load del weekend intero inclusi `qualifying_state` e `race_state` (`services/save_system.py`)
- ✅ `current_session_type` aggiunto al `to_dict()` dell'orchestrator
- ✅ metodi aggiunti a `WeekendOrchestrator`: `record_session_snapshot`, `start_qualifying`, `record_race_pit_stop`
- ✅ `tests/test_save_load.py` — 4 scenari roundtrip: weekend state, qualifying state, race state, qualifying→race transition
- ✅ fix test obsoleti (`WeekendSessionType.QUALIFYING` → `Q1`)
- ✅ log e telemetry strutturati per transizioni tra sessioni — copertura completa tramite `debug_log.py` e log dedicati per race

## Gap residui (rimandati a Fase H)

Nessun gap residuo - tutti gli elementi precedentemente rimandati alla Fase H sono stati integrati nella Fase G.

## Ordine consigliato di esecuzione

1. Cleanup architetturale e nomenclatura.
2. Weekend Orchestrator e state model.
3. Weekend transition state machine.
4. Qualifying subsystem.
5. Race subsystem.
6. Backend/API/UI integration.
7. Pagina consultazione risultati sessioni.
8. Persistenza, telemetry e QA.

## Documenti correlati

- `docs/global-roadmap.md`
- `docs/practice-session-orchestrator.md`
- `docs/race-engine-integration-spec.md`
- `docs/race-module-architecture.md`
