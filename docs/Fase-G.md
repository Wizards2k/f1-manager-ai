---
title: Fase G — Weekend di gara completo
version: 0.1
last_updated: 2026-03-29
scope: "Weekend di gara completo con cleanup architetturale aggressivo, Qualifying e Race"
---

# Fase G — Weekend di gara completo

Fase G porta il motore da una singola sessione practice a un weekend completo, consolidando anche la nomenclatura dei file e rimuovendo gli ultimi legacy path non più necessari.

## Roadmap in 6 punti

### 1) Cleanup architetturale e nomenclatura

Obiettivo: ridurre la ridondanza e rendere canonico un solo percorso runtime, backend e frontend.

Deliverable:

- inventario dei file legacy (`*_v1`, `.legacy`, `.old`) e classificazione tra mantenere, rinominare o eliminare;
- sostituzione dei nomi ambigui con nomi canonici;
- rimozione del codice abbandonato dopo la migrazione;
- allineamento di docs, test e import ai nuovi nomi.

### 2) Weekend Orchestrator e state model

Obiettivo: introdurre un layer superiore al `SessionBridge` per governare l’intero weekend.

Deliverable:

- modello di stato weekend con sessione corrente, risultati intermedi e stato globale;
- macchina a stati per avanzare tra FP1, FP2, FP3, Qualifying e Race;
- serializzazione e deserializzazione del weekend completo;
- propagazione del tipo sessione al runtime e al backend.

### 3) Qualifying subsystem

Obiettivo: implementare Q1, Q2 e Q3 come flusso dedicato con regole proprie.

Deliverable:

- timer e fasi qualifying-oriented;
- taglio progressivo dei classificati e gestione degli esclusi;
- regole tyre-specifiche e out-lap / flying lap / cool-down;
- classifica finale di qualifica e griglia provvisoria;
- eventi e telemetry per UI e QA.

### 4) Race subsystem

Obiettivo: trasformare il runtime in una vera sessione gara con partenza, stint e arrivo.

Deliverable:

- procedura di start e formazione griglia;
- gestione stint gara, pit strategy e fine gara;
- classificazione con ordine d’arrivo, gap e stati finali;
- integrazione con battle resolver e telemetria;
- transizione pulita da qualifica a gara.

### 5) Backend/API/UI integration

Obiettivo: esporre il weekend completo alla UI senza rompere il flusso attuale.

Deliverable:

- endpoint per stato weekend, sessione corrente, risultati quali e grid;
- azioni per avanzare sessione, avviare la race e gestire reset / replay;
- estensione del payload `race_update` con dati weekend;
- navigazione UI per weekend hub, session selector e viste dedicate.

### 6) Persistenza, telemetry e QA

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
6. Persistenza, telemetry e QA.

## Documenti correlati

- `docs/global-roadmap.md`
- `docs/practice-session-orchestrator.md`
- `docs/race-engine-integration-spec.md`
- `docs/race-module-architecture.md`
