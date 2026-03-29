---
title: Fase G — Weekend di gara completo
version: 0.1
last_updated: 2026-03-29
status: "Punto 3 completato — in progress su Race subsystem"
scope: "Weekend di gara completo con cleanup architetturale aggressivo, Qualifying e Race"
---

# Fase G — Weekend di gara completo

Fase G porta il motore da una singola sessione practice a un weekend completo, consolidando anche la nomenclatura dei file e rimuovendo gli ultimi legacy path non più necessari.

## Roadmap in 7 punti

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

### 3) ✅ Qualifying subsystem — **COMPLETATO**

Obiettivo: implementare Q1, Q2 e Q3 come flusso dedicato con regole proprie.

**Stato**: ✅ Completato il 2026-03-29

Deliverable:

- timer e fasi qualifying-oriented tramite `QualifyingSessionState`;
- taglio progressivo dei classificati e gestione degli esclusi;
- regole tyre-specifiche e out-lap / flying lap / cool-down;
- classifica finale di qualifica e griglia provvisoria;
- eventi e telemetry per UI e QA.

### 4) Race subsystem — **IN PROGRESS**

Obiettivo: trasformare il runtime in una vera sessione gara con partenza, stint e arrivo.

**Input dalla qualifica**: griglia finale (`final_grid`) esportata da `QualifyingSessionState`.

Deliverable:

- procedura di start e formazione griglia;
- gestione stint gara, pit strategy e fine gara;
- classificazione con ordine d’arrivo, gap e stati finali;
- integrazione con battle resolver e telemetria;
- transizione pulita da qualifica a gara.

### 5) Backend/API/UI integration

Obiettivo: esporre il weekend completo alla UI senza rompere il flusso attuale.

Deliverable:

- endpoint per stato weekend, sessione corrente, risultati quali, grid e summary sessioni;
- azioni per avanzare sessione, avviare la race e gestire reset / replay;
- estensione del payload `race_update` con dati weekend;
- navigazione UI per weekend hub, session selector e viste dedicate.

### 6) Pagina consultazione risultati sessioni

Obiettivo: offrire una vista read-only per consultare i risultati già registrati durante il weekend.

Deliverable:

- overview del weekend con stato di FP1, FP2, FP3, Qualifying e Race;
- dettaglio sessione con classifiche, best lap, stint, incidenti e note;
- accesso dal weekend hub e dal selettore sessioni;
- consultazione basata su snapshot persistiti e risultati serializzati dal backend.

### 7) Persistenza, telemetry e QA

Obiettivo: rendere il weekend verificabile, salvabile e testabile end-to-end.

Deliverable:

- save/load del weekend intero, non solo della sessione attiva;
- log e telemetry per transizioni tra sessioni, qualifiche e gara;
- QA harness con scenari deterministici per weekend completo;
- test automatici su cut-off qualifiche, griglia, race start e fine weekend.

## Ordine consigliato di esecuzione

1. Cleanup architetturale e nomenclatura.
2. Weekend Orchestrator e state model.
3. Qualifying subsystem.
4. Race subsystem.
5. Backend/API/UI integration.
6. Pagina consultazione risultati sessioni.
7. Persistenza, telemetry e QA.

## Documenti correlati

- `docs/global-roadmap.md`
- `docs/practice-session-orchestrator.md`
- `docs/race-engine-integration-spec.md`
- `docs/race-module-architecture.md`
