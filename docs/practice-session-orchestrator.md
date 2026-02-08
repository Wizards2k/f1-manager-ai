---
title: Practice Session Orchestrator
version: 0.1
last_updated: 2026-02-09
scope: "Coordinare FP1/FP2/FP3 con 18 AI + 2 player, integrando Setup Engine e LapSimulator"
---

## 1. Obiettivo
Coordinare un’intera sessione di Practice (FP1/FP2/FP3) gestendo simultaneamente 18 vetture AI e fino a 2 player. L’orchestratore deve:
- mantenere il cronometro ufficiale e lo stato sessione (bandiere, meteo, disponibilità pitlane);
- schedulare i run programmati (fuel, tyre set, mappe ICE/ERS) rispettando cooldown e queue box;
- sincronizzarsi con SetupEngineService e LapSimulator per applicare setup e far girare le auto;
- persistere dati/telemetria per UI, feedback ingegnere e QA harness.

## 2. Stato sessione & timeline
### 2.1 Cronometro ufficiale
- Timer base 60 minuti (FP1/FP2/FP3) con tick a 1 s.
- Supporta `resume`, `pause`, `fast_forward(×2/×4/×6)` per QA/manual testing.
- Tiene traccia del tempo trascorso/rimanente e invalida run se il timebox termina.
### 2.2 Slot pitlane e bandiere
- Pitlane con slot limitati: massimo 2 auto per team (1 per player). Queue gestita secondo priorità (player > AI run critico > AI standard).
- Eventi bandiera (gialla/rossa) limitano l’uscita o forzano rientro. In caso di rossa il timer continua ma run vengono marcati `aborted_by_flag`.
- Meteo dinamico (quando attivo) aggiorna grip e limita i programmi (es. Quali Sim sospesa se piove troppo).
### 2.3 Pause / fast-forward
- Pausa manuale da UI ingegnere blocca solo l’auto player; AI continua (come broadcast reale). Modalità debug permette freeze totale.
- Fast-forward disabilitato durante eventi critici (bandiere, incidenti) per non perdere log/telemetria.

## 3. Scheduling run
### 3.1 Input programma (AI/Player)
- Player: definisce manualmente run (compound, fuel, mappe) via UI; l’orchestratore valida disponibilità set/fuel e registra il run, **consultando le regole di allocazione gomme del weekend** (doc dedicato).
- AI: utilizza il programma definito nella spec AI Driver (Setup Validation, Tyre Deg, Quali Sim, Race Trim, R&D). Ogni entry è un `PracticeRunPlan` con `start_window`, `laps_planned`, `objective`, `priority` e rispetta i vincoli del documento gomme.
### 3.2 Cooldown e queue pitlane
- Cooldown minimo 120 s tra run con modifiche setup/fuel/tyre. L’orchestratore mantiene `next_slot_time` per ogni auto per evitare violazioni.
- Queue pitlane: se più auto vogliono uscire nello stesso tick, vengono ordinate per priorità e ritardate di 5‑10 s per simulare traffico reale.
### 3.3 Gestione gomme/fuel
- Tyre allocation per sessione: numero di set per compound definito dal regolamento. Ogni run consuma un set (flag `reused` se riutilizzato con penalty grip).
- Fuel load espresso in kg e convertito in litri. Rifornimenti conteggiati nel pit turnaround.
- L’orchestratore aggiorna l’inventario set/fuel per ogni team e blocca run impossibili.

## 4. Persistenza e telemetria
### 4.1 Run log & setup history
- Ogni run produce `PracticeRunRecord` con team, pilota, programma, start/stop time, tyre/fuel, delta setup, outcome (success/abort/partial) e note (traffico, bandiere, meteo).
- Mantiene `setup_history` per auto, con snapshot slider (valori fisici) ad ogni rientro per audit/parc fermé.
### 4.2 Export per UI/QA
- API per UI engineer con paginazione dei run (per mostrare cronologia, feedback, tempi).
- QA harness può scaricare JSON/CSV con timeline, lap times e eventi (per test deterministici).

## 5. Integrazione con LapSimulator & servizi
### 5.1 API / eventi
- `SetupEngineService.apply_setup(car_id, setup_payload)` chiamato prima di ogni run (player/AI) per applicare slider → fisica.
- `LapSimulator.run(practice_context)` riceve circuito, car state, driver intent, env ctx; restituisce telemetria e summary run.
- Eventi su EventBus: `practice_run_started`, `practice_run_finished`, `practice_run_aborted`, `flag_changed`, `weather_changed`.
### 5.2 Diagramma di sequenza (bozza)
```
PracticeOrchestrator -> SetupEngine: map_slider_to_physics
PracticeOrchestrator -> LapSimulator: run(practice_context)
LapSimulator -> PracticeOrchestrator: run_result + telemetry
PracticeOrchestrator -> TelemetryStore: persist(run_result)
PracticeOrchestrator -> UI Bus: emit events
```

## 6. Eventi & notifiche
- Verso UI engineer/player:
  - `RUN_START` (programma, compound, fuel, obiettivo)
  - `RUN_END` (miglior tempo, deg, feedback setup)
  - `RUN_ABORT` (motivo: flag, incidente, traffico, meteo)
  - `SETUP_CHANGE` (slider modificati, ragione feedback)
  - `TYRE_INVENTORY_UPDATE`
- Verso QA/telemetria: `time_pause`, `fast_forward`, `bandiera`, `weather_update`.

## 7. Dipendenze e futuri estensibili
- Dipendenze: AI Driver Engine spec, SetupEngineService, LapSimulator, Tyre allocation doc.
- Futuro: orchestratore weekend (FP→Quali→Race), meteo dinamico avanzato, run R&D dettagliati, interfaccia con Race Strategist AI e parc fermé cross-sessione.

