---
title: Roadmap Globale – Physics 2.0 Release
version: 0.1
last_updated: 2026-02-07
scope: "Coordinare tutte le iniziative necessarie per rilasciare F1 Manager AI con fisica 2.0, multi-car e setup engine rinnovato"
---

## 1. Visione – Obiettivi preposti
Portare il gioco a una release pubblica in cui:
- Il motore fisico (LapSimulator + BattleResolver) gestisce tutte le auto in pista con sorpassi coerenti.
- Il Setup Engine 2.0 traduce gli input utente in parametri fisici e guida il giocatore con feedback realistici.
- La PowerUnit, il TyreModel e il grip meccanico sono calibrati su dati FastF1 e integrati con pipeline CI di validazione.
- UI/UX, backend e tools lavorano insieme (telemetria, heatmap setup, log ingegnere) per una esperienza completa.

### Premessa – Deliverable già completati
- Spec LapSimulator/Lap Physics (`docs/lap-physics-spec-v0.5.md`) con definizione Car/Tyre/Driver e pipeline `update_section()`.
- Setup Engine 2.0 (`docs/setup-engine-spec-v0.1.md`) con mapping slider, scoring, harness/tabella mapping.
- Roadmap dati (`docs/physics-roadmap.md`) e bozza BattleResolver (`docs/BattleResolver.md`).
- Tooling setup mapping: `config/setup_mapping_v2.json`, report HTML e script di generazione completati.

## 1. Analisi da completare prima del codice

### 1.1 AI Driver & Team Behavior
- Documento `docs/ai-driver-engine-spec.md` per run plan AI (stint length, fuel/ERS usage), gestione parc fermé/setup seed, decisioni di push/pace per sezione, log/eventi necessari.

### 1.2 Practice Session Orchestrator
- Documento `docs/practice-session-orchestrator.md` che descrive stato sessione (tempo residuo, code pitlane), scheduling run multipli (18 AI + 2 player), persistenza lap/feedback, logiche fast-forward/pause.

### 1.3 BattleResolver 2.0
- Aggiornamento `docs/battleresolver-2.0.md`: stati attempt/lock/cooldown, logica side-by-side, metriche HUD/telemetria, output per QA harness.

## 2. Implementazione – Fase A (Setup & Validazione)
1. **SetupEngineService runtime**: modulo/servizio REST + socket che applica mapping slider→fisica e restituisce scoring live.
2. **Evaluate Setup refresh**: rifattorizzare `evaluate_setup` e categorie per usare `aero_balance`, `drag_index`, `traction_index`, `brake_cooling`.
3. **Pipeline CI `setup-calibration`**: job che rigenera mapping/heatmap, confronterà JSON e bloccherà regressioni.
4. **UI Garage 2.0 (base)**: slider con etichette fisiche e range circuito, feedback ingegnere collegato al nuovo servizio.

## 3. Implementazione – Fase B (Race Engine Core)
1. **LapSimulator runtime**: implementare il loop InputMixer → update_section parallelo → BattleResolver 2.0 → StateCommit.
2. **BattleResolver 2.0**: codice allineato alla nuova spec (cooldown, side-by-side, metriche HUD/telemetria).
3. **Practice Session Orchestrator**: scheduling tempo sessione, queue pitlane, gestione run e persistenza run data/log.
4. **Power Unit config**: creare `config/pu/pu_maps.json` (heat_load, torque_ramp, deployment) e `config/pu/pu_reliability.json` (wear_coeff, soglie temp) per integrazione LapSimulator/BattleResolver.

## 4. Implementazione – Fase C (AI & Experience)
1. **AI Driver Engine**: loop decisionale per run plan, fuel/ERS, strategie box e ricerca setup.
2. **Telemetria & HUD eventi**: logging sorpassi, blocchi, dirty air, feedback ingegnere per player e QA.
3. **UI Garage 2.0 completa**: engineer assistant, feedback testuale, gestione parc fermé e callouts realtime.

## 5. Implementazione – Fase D (Data & Calibrazione)
1. **FastF1 toolchain**: ingestion, caching, manifest dataset.
2. **Script fitting componenti**: `aero_fit`, `tyre_fit`, `powerunit_fit`, `brake_calibration` con output in `config/calibration/`.
3. **CI `calibration.yml`**: pipeline badge componenti → lap regression → race smoke test.
4. **Manifest & dashboard**: repository asset calibrati + dashboard Plotly per confronto sim vs telemetria reale.

## 6. Gameplay, Backend & QA Harness
1. **RaceSimulator backend integration**: scheduler sezioni, orchestrazione multi-car, storage `section_progress`, sincronizzazione multiplayer fantasma.
2. **Strategia/Engineer AI**: usare output LapSimulator per suggerire setup/strategie e gestire traffico.
3. **QA harness scenari**: test automatici (20 auto, DRS train, wet stint) con seed deterministico e utilizzo dei nuovi log.

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

## 4. Dipendenze chiave
- Setup Engine 2.0 deve essere completato prima di M3 (LapSimulator dipende dai parametri fisici corretti).
- TyreModel v0.4 e grip meccanico sono prerequisiti per LapSimulator Beta (altrimenti la fisica non riflette i setup).
- FastF1 pipeline deve essere operativa prima del gating CI (M4), altrimenti i badge componenti restano rossi.
- UI Garage/HUD necessarie per player feedback (setup e sorpassi) prima della release.
- AI Driver Engine dipende dal DriverModel (skill/stato mentale) già definito e deve essere operativo prima dei test con 20 auto (M5).

## 5. Documenti correlati
- `docs/lap-physics-spec-v0.5.md`
- `docs/setup-engine-spec-v0.1.md`
- `docs/physics-roadmap.md`
- `docs/setup-search-plan.md`, `docs/setup-ui-plan.md`
- `docs/BattleResolver.md` (da aggiornare)
- `docs/TyreModel.md`

## 6. Prossimi passi immediati
1. Validare questa roadmap con product/gameplay.
2. Aggiornare `docs/BattleResolver.md` con la nuova logica.
3. Pianificare implementazione Setup Engine 2.0 (ticket/branch dedicato).
4. Avviare design TyreModel v0.4 e Grip meccanico (spec + tasks).
