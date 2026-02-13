---
title: Blue Flag Handling
version: 0.1
last_updated: 2026-02-13
scope: "Definisce chi gestisce le bandiere blu e le regole di esposizione per FP/Q e gara"
---

## 1. Panoramica
Le bandiere blu vengono calcolate nel `SessionBridge` e applicate per ogni vettura tramite il `PracticeSessionOrchestrator` (PSO) durante le sessioni di prova/qualifica. In gara lo stesso flusso viene riutilizzato, ma con criteri di attivazione diversi. Questo documento chiarisce *chi* aggiorna lo stato e *quando* una vettura deve vedere la bandiera.

Componenti principali:
- **SessionBridge**: rileva le situazioni di sovrapposizione (lap diff + gap) nel ciclo `_resolve_battles` e decide se un car_id deve ricevere la bandiera.
- **PracticeSessionOrchestrator**: espone `set_blue_flag(car_id, active)` che memorizza lo stato in `CarSessionState.blue_flag` ed emette `PracticeEventType.FLAG_CHANGE` → socket.
- **Socket bridge + Frontend**: inoltrano il flag nel payload `race_update` e lo mostrano su timing/mappe.

## 2. Regole per FP1/FP2/FP3/Qualifiche
Durante le sessioni non di gara l’obiettivo è proteggere gli hot lap da vetture lente appena uscite o in cool-down.

1. **Auto candidate alla bandiera**: tutte le vetture che risultano in uno dei seguenti stati lato PSO:
   - `OUT_LAP`
   - `IN_LAP` / `PIT_ENTRY`
   - `COOL_DOWN` (dito di rallentamento immediatamente dopo un hot lap)
2. **Auto che richiede la bandiera**: una vettura su `HOT_LAP` (hot lap dichiarato dal run plan o dallo stato corrente) che sta sopraggiungendo dietro la candidata.
3. **Condizione sul gap**: se la vettura veloce è dietro ma entro la soglia di prossimità (250 m di default) scatta la bandiera blu sulla vettura lenta finché:
   - viene superata oppure
   - non ci sono più vetture in `HOT_LAP` che la seguono a distanza critica.
4. Il SessionBridge resetta automaticamente il flag quando la vettura rientra ai box o torna su un nuovo hot lap con pista libera.

## 3. Regole per la gara
In modalità gara la bandiera blu è più conservativa:

1. **Candidata**: qualsiasi vettura che ha `lap_diff >= 1` rispetto a un’altra (sta per essere doppiata o è già doppiata).
2. **Trigger**: se il leader (non importa lo stato) sta per sorpassarla e la distanza effettiva scende entro la soglia di prossimità, viene esposta la bandiera.
3. **Stati ignorati**: non analizziamo OUT/IN lap o cool-down; conta solo il fatto di essere doppiati.
4. **Clear**: dopo il sorpasso, se non ci sono altre vetture con `lap_diff >= 1` pronte a superare, il flag viene rimosso.

## 4. Modifiche future
- La severità delle soglie (250 m e priorità di stato) verrà riesaminata quando introdurremo il nuovo BattleResolver 2.1.
- Possibile estensione: distinguere fra `Quali Hot Lap` e `Install Lap` per ridurre falsi positivi.

## 5. Riferimenti
- `python_backend/utils/session_bridge.py` → `_resolve_battles()`
- `python_backend/lap_simulator/practice_session.py` → `set_blue_flag`
- `docs/practice-session-orchestrator.md §2.2` (slot pitlane & bandiere)
