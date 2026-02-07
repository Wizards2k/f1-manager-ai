---
title: Roadmap Globale – Physics 2.0 Release
version: 0.1
last_updated: 2026-02-07
scope: "Coordinare tutte le iniziative necessarie per rilasciare F1 Manager AI con fisica 2.0, multi-car e setup engine rinnovato"
---

## 1. Visione
Portare il gioco a una release pubblica in cui:
- Il motore fisico (LapSimulator + BattleResolver) gestisce tutte le auto in pista con sorpassi coerenti.
- Il Setup Engine 2.0 traduce gli input utente in parametri fisici e guida il giocatore con feedback realistici.
- La PowerUnit, il TyreModel e il grip meccanico sono calibrati su dati FastF1 e integrati con pipeline CI di validazione.
- UI/UX, backend e tools lavorano insieme (telemetria, heatmap setup, log ingegnere) per una esperienza completa.

## 2. Stato attuale (Feb 2026)
- `docs/lap-physics-spec-v0.5.md`: definizione Car/Tyre/Driver, passi `update_section()`, LapSimulator loop, pipeline calibrazione.
- `docs/setup-engine-spec-v0.1.md`: spec Setup Engine 2.0 (slider mapping, scoring, harness).
- `docs/BattleResolver.md`: bozza high-level da allineare alla nuova logica.
- `docs/TyreModel.md`: modello termico base (da estendere a v0.4 completo).
- `docs/physics-roadmap.md`: piano FastF1 e calibrazione dati.

## 3. Workstreams principali (physics + backend + AI)

### 3.1 Physics Core
1. **Implementare LapSimulator runtime** (loop InputMixer → parallel update → BattleResolver → StateCommit).
2. **BattleResolver 2.0**: cooldown/lock, side-by-side events, metriche output (HUD, telemetria). Aggiornare `docs/BattleResolver.md`.
3. **Grip meccanico / Telaio**: completare spec v0.3 e implementazione (ride height dinamico, sospensioni avanzate, antiroll, handling penalty).
4. **TyreModel v0.4**: integrare termica completa, finestra ottimale, degrado per asse/ruota, effetti meteo.
5. **PowerUnit detail**: spec dedicata ICE/ERS maps, derating, SOC, interfaccia Setup Engine.

### 3.2 Setup Engine & UI
1. Implementare `SetupEngineService` (REST + socket) con mapping slider→fisica e scoring aggiornato.
2. Aggiornare `evaluate_setup`/`evaluate_setup_categories` per usare indici fisici (aero_balance, drag_index).
3. UI Garage 2.0: slider con etichette fisiche, range per circuito, feedback ingegnere, status parc fermé.
4. Setup Harness (`scripts/setup_heatmap.py`) + notebook analisi.
5. Pipeline `setup-calibration` (CI) per generare range consigliati e verificare regressioni.

### 3.3 Data & Calibrazione
1. FastF1 ingestion toolchain (dataset generator, caching, manifest).
2. Script fitting componenti (`aero_fit`, `tyre_fit`, `powerunit_fit`, `brake_calibration`).
3. CI `calibration.yml` (component badge → lap regression → race smoke test).
4. Repository asset calibrati (`config/calibration/*.json`, manifest con checksum).
5. Dashboard validation (notebook + Plotly) per confrontare simulazioni vs telemetria reale.

### 3.4 Gameplay, Backend & AI Fleet
1. **RaceSimulator integration** nel backend (scheduler sezioni, orchestrazione multi-car, storage `section_progress`, sincronizzazione multiplayer fantasma).
2. **AI Driver Engine** per vetture gestite dal gioco:
   - profili piloti (aggressione, tyre/fuel management) + stato mentale dinamico
   - decisioni di push level, ERS map e linee attacco/difesa per ogni sezione (interfaccia con DriverModel).
   - gestione eventi (cooldown, difesa, pit strategy base per Practice/Qualy).
3. Telemetria & replay: log degli eventi (sorpassi, tentativi, contatti) per UI e analisi.
4. Strategia/Engineer AI: usare output LapSimulator per suggerire setup/strategie al giocatore.
5. QA harness: scenari automatici (20 auto in pista, DRS train, wet stint) con seed deterministico.

### 3.5 UI/UX & Player Experience
1. HUD aggiornato (eventi Side-by-side, Attempt blocked, cooldown timer, engineer radio).
2. Engineer assistant: roadmap `setup-ui-plan.md` + nuove API Setup Engine.
3. Replay/lap overview "pallino" con timeline eventi e indicatori (attempts, successi, penalità).
4. Manuale/tooltip per Setup Engine 2.0 e metrica fisica (aero_balance, drag index, brake cooling).

### 3.6 Frontend Race Engine
1. Refactoring FE race renderer (pallino su rotaia) per supportare 20 auto simultanee con eventi dinamici.
2. Animazioni overlay per sorpassi: side-by-side, cooldown indicator, penalty flash.
3. Timeline pratica/qualifica con markers (tentativi, best lap, traffico) e link a replay.
4. Integrazione con Setup Engine feedback (engineer callouts, recommended adjustments).
5. Performance budget: target 60 FPS su Electron/web (profiling + virtualization dati telemetria).

### 3.7 Release Engineering
1. Branch strategy: `physics-engine` → `release/physics2` → main.
2. Build "Engineer Mode" per manual QA (logging esteso, overlay debug).
3. Backend load tests per 20 auto (practice session) con profili AI diversi.
4. Release checklist (da §3.5: 3 circuiti calibrati, report `docs/calibration_runs/<date>.md`, manifest aggiornato).
5. Telemetry anonymizer per dati FastF1 se condivisi.

## 4. Milestone timeline (indicativa)
1. **M1 – Foundations (Feb)**
   - Setup Engine spec (done), LapSimulator spec (done), global roadmap (this doc).
2. **M2 – Setup Engine 2.0 (Mar)**
   - Implementazione service + UI base, heatmap harness, CI `setup-calibration`.
3. **M3 – Physics Core Alpha (Apr)**
   - LapSimulator runtime + BattleResolver 2.0 stub, TyreModel v0.4 implementato, PowerUnit detailed spec.
4. **M4 – Data & Calibration (May)**
   - FastF1 ingestion, component fitting scripts, CI `calibration.yml`, manifest versioning.
5. **M5 – RaceSimulator Beta (Jun)**
   - Backend multi-car (20 auto) in esecuzione, AI driver loop completo, QA harness scenari, HUD eventi, engineering logs.
6. **M6 – Release Candidate (Jul)**
   - Full pipeline verde (component + lap + race), setup UI final, manual QA completato.
7. **M7 – Physics 2.0 Release (Aug)**
   - Merge in main, package release note, asset calibrati pubblici.

## 5. Dipendenze chiave
- Setup Engine 2.0 deve essere completato prima di M3 (LapSimulator dipende dai parametri fisici corretti).
- TyreModel v0.4 e grip meccanico sono prerequisiti per LapSimulator Beta (altrimenti la fisica non riflette i setup).
- FastF1 pipeline deve essere operativa prima del gating CI (M4), altrimenti i badge componenti restano rossi.
- UI Garage/HUD necessarie per player feedback (setup e sorpassi) prima della release.
- AI Driver Engine dipende dal DriverModel (skill/stato mentale) già definito e deve essere operativo prima dei test con 20 auto (M5).

## 6. Documenti correlati
- `docs/lap-physics-spec-v0.5.md`
- `docs/setup-engine-spec-v0.1.md`
- `docs/physics-roadmap.md`
- `docs/setup-search-plan.md`, `docs/setup-ui-plan.md`
- `docs/BattleResolver.md` (da aggiornare)
- `docs/TyreModel.md`

## 7. Prossimi passi immediati
1. Validare questa roadmap con product/gameplay.
2. Aggiornare `docs/BattleResolver.md` con la nuova logica.
3. Pianificare implementazione Setup Engine 2.0 (ticket/branch dedicato).
4. Avviare design TyreModel v0.4 e Grip meccanico (spec + tasks).
