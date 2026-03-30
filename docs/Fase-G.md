---
title: Fase G — Weekend di gara completo
version: 0.2
last_updated: 2026-03-30
status: "Punto 3 COMPLETATO — Race subsystem in progress"
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

Obiettivo: introdurre un layer superiore al `SessionBridge` per governare l’intero weekend.

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

Obiettivo: implementare Q1, Q2 e Q3 come flusso dedicato con regole proprie.

**Stato**: ✅ Completato il 2026-03-29

Deliverable:

- timer e fasi qualifying-oriented tramite `QualifyingSessionState`;
- taglio progressivo dei classificati e gestione degli esclusi;
- regole tyre-specifiche e out-lap / flying lap / cool-down;
- classifica finale di qualifica e griglia provvisoria;
- eventi e telemetry per UI e QA.

### 5) Race subsystem — **IN PROGRESS**

Obiettivo: trasformare il runtime in una vera sessione gara con partenza, stint e arrivo.

**Input dalla qualifica**: griglia finale (`final_grid`) esportata da `QualifyingSessionState`.

Deliverable:

- procedura di start e formazione griglia;
- gestione stint gara, pit strategy e fine gara;
- classificazione con ordine d’arrivo, gap e stati finali;
- integrazione con battle resolver e telemetria;
- transizione pulita da qualifica a gara.

### 6) Backend/API/UI integration

Obiettivo: esporre il weekend completo alla UI senza rompere il flusso attuale.

Deliverable:

- endpoint per stato weekend, sessione corrente, risultati quali, grid e summary sessioni;
- azioni per avanzare sessione, avviare la race e gestire reset / replay;
- estensione del payload `race_update` con dati weekend;
- navigazione UI per weekend hub, session selector e viste dedicate.

### 7) Pagina transizione e consultazione risultati sessioni

Obiettivo: offrire una vista di transizione che mostra i risultati già registrati e porta alla sessione successiva del weekend.

Deliverable:

- overview del weekend con stato di FP1, FP2, FP3, Qualifying e Race;
- dettaglio sessione con classifiche, best lap, stint, incidenti e note;
- azione esplicita per avanzare alla sessione successiva quando la sessione è in stato `READY_TO_ADVANCE`;
- accesso dal weekend hub e dal selettore sessioni;
- consultazione basata su snapshot persistiti e risultati serializzati dal backend.

### 8) Persistenza, telemetry e QA

Obiettivo: rendere il weekend verificabile, salvabile e testabile end-to-end.

Deliverable:

- save/load del weekend intero, non solo della sessione attiva;
- log e telemetry per transizioni tra sessioni, qualifiche e gara;
- QA harness con scenari deterministici per weekend completo;
- test automatici su cut-off qualifiche, griglia, race start e fine weekend.

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
