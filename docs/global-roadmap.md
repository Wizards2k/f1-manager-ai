---
title: Roadmap Globale – Physics 2.0 Release
version: 0.1
last_updated: 2026-02-19
scope: "Coordinare tutte le iniziative necessarie per rilasciare F1 Manager AI con fisica 2.0, multi-car e setup engine rinnovato"
---

## 1. Visione
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
- Profili derivati per circuito generati (`config/circuits/derived/<cid>/`) via `scripts/build_circuit_profiles.py` (tyres/brakes/PU/damage).
- Catalogo JSON e uso moduli: `docs/config-spec.md`.
- AeroPackage: formule e componenti in `docs/AeroPackage.md` (sintesi), dettagli in `docs/lap-physics-spec-v0.5.md` (§3.1–3.3) e mapping slider in `docs/setup-engine-spec-v0.1.md` (§3.2).
- PowerUnit ICE/ERS: modello e mappe in `docs/PowerUnit.md` (sintesi), dati energetici/mode strategy in `docs/EngineData2025.md`, dettagli in `docs/lap-physics-spec-v0.5.md` (§3.3–3.4), seed/config in `config/pu/*_global_default.json`.

## 1. Analisi da completare prima del codice

### 1.1 AI Driver & Team Behavior (`docs/ai-driver-engine-spec.md`)
- Spec esistente: `docs/ai-driver-engine-spec.md` (run plan AI, fuel/ERS, parc fermé/setup seed, push/pace, log/eventi).

### 1.2 Practice Session Orchestrator (`docs/practice-session-orchestrator.md`)
- Spec esistente: `docs/practice-session-orchestrator.md` (stato sessione, queue pitlane, scheduling 18 AI + 2 player, persistenza lap/feedback, fast-forward/pause).

### 1.3 BattleResolver 2.0 (`docs/BattleResolver.md`)
- Spec aggiornata in `docs/BattleResolver.md`: tagging scenario (Start/Restart, Rettifilo, Curva, Uscita, Blue flag/team order), logica side-by-side senza cooldown persistente (penalty istantanei), metriche HUD/telemetria e output per QA harness.

### 1.4 Analisi aggiuntive (da pianificare — `docs/lap-physics-spec-v0.5.md`, `docs/physics-roadmap.md`)
- LapSimulator orchestration pseudocodice end-to-end (InputMixer → update_section → BattleResolver → StateCommit)
- Calibration/validation workflow (fitting componenti, badge CI, manifest)

## ✅ 2. Implementazione – Fase A (Setup & Validazione — `docs/setup-engine-spec-v0.1.md`, `docs/config-spec.md`, `docs/setup-ui-plan.md`)
> **Stato:** ✅ Completata il 2026-02-10 (merge in `feature/mvp-phase-1`)
1. ✅ **SetupEngineService runtime**: modulo/servizio REST + socket che applica mapping slider→fisica e restituisce scoring live.
2. ✅ **Evaluate Setup refresh**: rifattorizzare `evaluate_setup` e categorie per usare `aero_balance`, `drag_index`, `traction_index`, `brake_cooling`.
3. ✅ **Pipeline CI `setup-calibration`**: requisito assolto tramite i controlli già presenti (slider UI clampati sui range circuito + `SetupEngineService.sanitize_input()` lato backend). Non è previsto un job CI separato finché il progetto rimane single-developer.
4. ✅ **UI Garage 2.0 (base)** (`docs/setup-ui-plan.md`, `docs/setup-search-plan.md`): implementata con design Jarvis Variant B — 11 slider in 4 gruppi, valori fisici (°/mm/%), range circuito, feedback row + 5 category chips. Feedback ingegnere basato su quota informazioni (chip SETUP/Data rosso→giallo→verde) e senza feedback live; serve raccolta dati e rientro ai box per pubblicare nuovi suggerimenti. Modifica slider azzera il progresso.

## 3. Implementazione – Fase B (Race Engine Core — `docs/lap-physics-spec-v0.5.md`, `docs/BattleResolver.md`, `docs/practice-session-orchestrator.md`)

> **Spec tecnica di riferimento**: `docs/lapsimulator-implementation-spec.md`

1. **LapSimulator runtime**: implementare il loop InputMixer → update_section parallelo → BattleResolver 2.0 → StateCommit.
   > **Stato:** 🔧 v0.1 implementata il 2026-02-10 (branch `feature/lapsimulator-runtime`, 85/85 test).
   > Modulo standalone in `python_backend/lap_simulator/` — 8 passi update_section, config loader, test integrazione Monza.
   > ✅ **Telemetry Sections v2** completato e merged: 24/24 circuiti rigenerati con copertura 100%, dt_ref, braking_energy, DRS, radius, classificazione 5-tier. Spec: `docs/telemetry-sections-v2-spec.md`.
   > ✅ **Modello dt_ref** integrato: `dt = dt_ref × (1 + baseline + Σ penalties)`. Monza Lap 1 = 108.1s (+6.9% vs VER 2024 Q). Baseline +5% = top team inizio 2025.
   > ✅ **Gap §6.7-§6.10** completati: fuel weight, mechanical grip (setup_bonus), driver skills nei freni, overtake window (OW max ~0.78 nelle zone DRS).
   > ✅ **Tuning multi-circuito** completato: baseline 0.07, k_grip 0.02, k_brake 0.015, k_fuel 0.015, k_driver 0.03, thermal floor 0.82. L1 avg=+5.7%, 22/24 nel target [4.5–7.5%]. Degrado L5 rimandato a TyreModel v2.
   > ✅ **PU over_rev/shock** fix: usura ICE/ERS ora tiene conto di `overrev_factor` (mappe aggressive) e `shock_factor` (kerb/bump).
   > **Copertura `degradation-and-consumption.md`**: §5.1 Tyres ✅, §5.2 Brakes ✅, §5.3 Fuel ✅, §5.4 PU ✅, §5.5 Damage 🟡 (struttura presente, dettagli da completare).
   > ✅ **AI Driver Engine** implementato: setup seed, session planning (FP1/2/3), run config, post-run analysis con refinement loop, 20 test. Spec: `docs/ai-driver-engine-spec.md`.
   > ✅ **TyreModel v2** completato: compound C1-C6+Inter+Wet con degradation_rate_multiplier, slip_sensitivity, heat-cycle penalty, graining/blistering temporali. 9 nuovi test (123/123 totali).
   > ✅ **BattleResolver 2.0** completato: proximity detection, dirty air, 7 scenari, attack/blocked/side-by-side/collision, radio messages, LapSimulator multi-car. 29 test (152/152 totali).
   > ✅ **Practice Session Orchestrator** completato: SessionClock, PitlaneQueue, TyreInventory, run management, red flag abort, leaderboard. 37 test (189/189 totali).
   > **Tutti i moduli core completati.** Prossimo: Fase C (Race Engine Integration).
2. ✅ **BattleResolver 2.0**: proximity detection, dirty air, scenario tagging (7 scenari), attack chance, resolve pair (overtake/blocked/side-by-side/collision), radio messages, integrazione LapSimulator multi-car (`_run_lap_multi`). 29 test, 152/152 totali.
3. ✅ **Practice Session Orchestrator**: SessionClock (60min, pause, fast-forward), PitlaneQueue (priority, cooldown, max slots), TyreInventory (check-out/check-in, heat cycles, EOL), PracticeSessionOrchestrator (tick loop, run management, red flag abort, leaderboard). 37 test, 189/189 totali.
4. ✅ **TyreModel v2**: compound C1-C6+Inter+Wet, degradation_rate_multiplier, slip_sensitivity, heat-cycle penalty, graining/blistering temporali. 123/123 test.

## ✅ 4. Implementazione – Fase C (Race Engine Integration — `docs/race-engine-integration-spec.md`)
> **Branch**: `feature/race-engine`
> **Spec tecnica di riferimento**: `docs/race-engine-integration-spec.md`

Collegare il LapSimulator (Fase B) al gioco esistente, sostituendo il vecchio motore semplificato.
1. ✅ **Adapter RaceCar ↔ CarEntry**: traduzione bidirezionale via `session_bridge.py` (`_build_car_entry`, `_commit_lap`).
2. ✅ **Session Bridge**: wrappa PSO + LapSimulator + AIDriverEngine in un loop compatibile. Batch scheduling randomizzato (blocchi da 8), cooldown 45s nativo, inter-run gap 75-150s.
3. ✅ **Backend integration**: `f1_manager_ai.py` usa SessionBridge v2 con fallback V1. Flag system (green/yellow/red banner + blue flag per-car).
4. ✅ **Socket/frontend compatibility**: tutti i campi frontend mappati 1:1 con payload `race_update`. `player_car_ids` set per team multi-player. Banner flag + blue-flag-bar in timing UI.
5. ✅ **Test end-to-end**: FP1 Suzuka, 20 auto (2 player + 18 AI), 54/54 AI runs completati, 0.5s wall time.
6. ✅ **BattleResolver 2.0 integration**: BR2 nel tick loop SessionBridge (FASE 3). Proximity detection per sezione, resolve pairs (overtake/blocked/side-by-side/collision). Collision → yellow flag con auto-recovery (60-120s). Blue flag detection per auto doppiate. Battle events emessi via socket. E2E: 166 overtakes, 40 blocked, 6 collisions, 6 yellow periods, 54/54 runs completati.

## ✅ 5. Implementazione – Fase D (AI & Experience — `docs/ai-driver-engine-spec.md`, `docs/setup-ui-plan.md`)
1. ✅ **AI Driver Engine**: implementato in `python_backend/lap_simulator/ai_driver_engine.py`. Setup seed, session planning, run config, refinement loop. 105/105 test.
2. ✅ **Telemetria & HUD eventi**: logging sorpassi, blocchi, dirty air, feedback ingegnere per player e QA.
   - 🔧 Backend 2026-02-15: SessionBridge e PSO propagano `ers_budget`/`regen_profile`/`brake_profile` nei nuovi blocchi `pu_stats` e `brake_diagnostics`, emessi via `race_update`.
   - ✅ Regression test `test_calibration_and_telemetry.py` (10 giri per circuito) confronta i payload con i JSON derivati, garantendo coerenza per tutte le 24 piste.
   - ⏭ UI da aggiornare per consumare i dati (panel HUD/Garage, preset push/recharge) — rimane aperto come follow-up FE.
3. ✅ **UI Garage 2.0 completa**: engineer assistant, feedback testuale, gestione parc fermé e callouts realtime.

## 6. Implementazione – Fase E (Data & Calibrazione — `docs/physics-roadmap.md`, `docs/config-spec.md`, `docs/degradation-and-consumption.md`)
1. ✅ **FastF1 toolchain**: ingestion, caching, manifest dataset (wrapper `scripts/fastf1_build_assets.py`, manifest per anno, cache locale).
2. ✅ **Script fitting componenti**: `aero_fit`, `tyre_fit`, `powerunit_fit`, `brake_calibration` implementati con output in `config/circuits/derived/` e `reports/calibration/`.
   - ✅ Documentazione PU/ERS aggiornata: `docs/PowerUnit.md` + `docs/EngineData2025.md` (limiti FIA, torque curve, strategie push/recharge).
   - ✅ **PU energy model & UI mockup** (`docs/pu-energy-model.md`, `docs/Engine-MGU-H.md`).
   - **Piano di integrazione MGU-H (completato 2026-02-15)**
     1. ✅ *Config & fitting* – tutti i 24 circuiti rigenerati con profili MGU-H (high/balanced/low speed), `mguh_direct_ratio` e `mguh_power_kw` per ogni mappa.
     2. ✅ *Runtime* – logica MGU-H completa in `power_unit.py` (direct drive + harvest ES illimitati, calcolo dinamico potenza, split energetico gerarchico).
     3. ✅ *Telemetria* – `lap_mguh_direct_mj`, `lap_mguh_harvest_mj` esposti via SessionBridge, trace per sezione con `mguh_direct_mj` e `mguh_es_mj`.
     4. ✅ *UI/UX* – PU modal aggiornata con stat cards MGU-H, colonne trace, chip giro. Layout ottimizzato (grid 3 col, tabella scrollabile). Fix lap label (0-based).
     5. ✅ *Documentazione & QA* – `Engine-MGU-H.md` creato, `EngineData2025.md` e `PowerUnit.md` aggiornati. 242/242 test passing.

   - **Punti aperti post-MGU-H (2026-02-15, aggiornati 2026-02-16)**
     1. ✅ **MGU-H direct drive consumption** – budget per bucket implementato nel LapSimulator (`power_unit.py`).
     2. ✅ **ERS deployment strategy** – refactor completo con priorità sezione, SOC target e telemetria/UI aggiornata.
     3. ✅ **Brake migration torque split** – split regen/idraulico implementato nel runtime (power_unit.py) con telemetria e warning SOC.
     4. ✅ **Component integration** – verificata interazione aero/tyres/brakes/driver con la nuova logica PU (SessionBridge 3-lap QA run).

   - **Roadmap operativa (rollout incrementale)**
     1. ✅ **PU Hybrid V2.1** – implementare consumo MGU-H direct, refactor deployment strategy (section priority, MGU-H awareness), brake migration torque split.
        - ✅ Consumo MGU-H direct + budget bucketizzato (LapSimulator `power_unit.py`, 2026-02-16).
        - ✅ Strategia ERS basata su priorità sezioni + SOC target con nuova UI/telemetria ERS Map (Garage V3, 2026-02-16).
        - ✅ Brake migration torque split (regen vs idraulico) con telemetria e warning SOC (2026-02-16).
     2. **Brake Calibration & Migration** – usare i profili frenata per calcolare coppie regen/idrauliche, loggare warning e visualizzarli (bias/duct/cooling) nella UI.
       - ✅ Script `brake_calibration.py`: integra `braking_energy_mj` per sezione e produce `config/calibration/brakes/<circuit>.json` con heat_capacity, fade_threshold, cooling_coeff, ratio regen/idraulico.
       - ✅ Aggiornare la pipeline `build_circuit_profiles.py`/loader per fondere i parametri calibrati nei derived `config/circuits/derived/<circuit>/brake_params.json`.
       - ✅ Estendere il LapSimulator (BrakeSystem + Degradation loop) per leggere i nuovi coeff, calcolare torque split regen/idraulico per sezione e generare warning termici.
       - ✅ Surface FE/HUD: Garage V3 mostra ora guidance freni (bias/duct) accanto al feedback pilota, toast dinamici + HUD banner gestiscono `brake_hot_section` / `brake_duct_low|high` con auto-resize per messaggi lunghi (`player_garage_v3.js`, `socket_bridge.js`, `dashboard-v3.css`).
       - ✅ QA & test: esteso `test_calibration_and_telemetry.py` con validazione completa di `brake_cooling`, `brake_thermal`, status checks e threshold verification. Creato script `brake_validation_report.py` per report HTML/JSON di validazione componenti per tutti i circuiti con test multi-configurazione duct e SessionBridge integration.
     3. ✅ **Tyre Model V2** – integrare i parametri derivati (temp window, gaussian, graining/blistering) nel simulatore e mostrare trend degrado/termico.
     4. ✅ **Aero Package dettagliato** – applicare DF/drag/handling penalty avanzati nel runtime e surface UI con indicatori aero balance/cooling.
     5. **Automazione & QA** – pipeline `calibration.yml`, watchdog FastF1 vs sim, manifest + dashboard Plotly e checklist QA dedicate.
3. ✅ **CI `calibration.yml`**: pipeline watchdog implementata con badge componenti → lap regression → race smoke test (`.github/workflows/calibration.yml`).
4. ✅ **Data coherence watchdog**: CLI `tools/watchdog.py` completa che confronta sim vs FastF1/telemetry con report drift; esecuzione in CI.
5. ✅ **Manifest & dashboard**: `config/calibration/manifest.json` completo con 24 circuiti; dashboard Plotly (sim vs telemetria) e report HTML implementati.

6. Penalty System Overhaul – `docs/penalty-overhaul-spec.md`
1. ✅ **Fuel penalty**: implementato con telemetry integration, test Yas Marina 100kg = +3.5s/lap
2. ⏳ **Struttura PerformancePenalties**: fuel, tyres, push, driver_skill, ice_map, ers_map, brakes, setup, circuit_extra
3. ⏳ **Team performance gaps**: mapping driver→team, calcolo delta_aero/delta_grip per AI e giocatore
4. ⏳ **Runtime integration**: delta values passati da CarEntry a update_section() con applicazione fisica
5. ⏳ **Validazione**: AI con tempi realistici e logging dettagliato

## 7. Implementazione – Fase F (Gameplay, Backend & QA Harness — `docs/physics-roadmap.md`, `docs/BattleResolver.md`, `docs/setup-ui-plan.md`)
1. **RaceSimulator backend integration**: scheduler sezioni, orchestrazione multi-car, storage `section_progress`, sincronizzazione multiplayer fantasma.
2. **Strategia/Engineer AI**: usare output LapSimulator per suggerire setup/strategie e gestire traffico.
3. **QA harness scenari**: test automatici (20 auto, DRS train, wet stint) con seed deterministico e utilizzo dei nuovi log.

### 7.1 UI/UX & Player Experience (`docs/setup-ui-plan.md`, `docs/setup-engine-spec-v0.1.md`)
1. HUD aggiornato (eventi Side-by-side, Attempt blocked, cooldown timer, engineer radio).
2. Engineer assistant: roadmap `setup-ui-plan.md` + nuove API Setup Engine.
3. Replay/lap overview "pallino" con timeline eventi e indicatori (attempts, successi, penalità).
4. Manuale/tooltip per Setup Engine 2.0 e metrica fisica (aero_balance, drag index, brake cooling).

### 7.2 Frontend Race Engine (`docs/physics-roadmap.md`, `docs/setup-ui-plan.md`)
1. Refactoring FE race renderer (pallino su rotaia) per supportare 20 auto simultanee con eventi dinamici.
2. Animazioni overlay per sorpassi: side-by-side, cooldown indicator, penalty flash.
3. Timeline pratica/qualifica con markers (tentativi, best lap, traffico) e link a replay.
4. Integrazione con Setup Engine feedback (engineer callouts, recommended adjustments).
5. Performance budget: target 60 FPS su Electron/web (profiling + virtualization dati telemetria).

### 7.3 Release Engineering (`docs/physics-roadmap.md`, `docs/global-physics-roadmap.md`)
1. Branch strategy: `physics-engine` → `release/physics2` → main.
2. Build "Engineer Mode" per manual QA (logging esteso, overlay debug).
3. Backend load tests per 20 auto (practice session) con profili AI diversi.
4. Release checklist (da §3.5: 3 circuiti calibrati, report `docs/calibration_runs/<date>.md`, manifest aggiornato).
5. Telemetry anonymizer per dati FastF1 se condivisi.

## 8. Dipendenze chiave (`docs/physics-roadmap.md`, `docs/lap-physics-spec-v0.5.md`, `docs/setup-engine-spec-v0.1.md`)
- Setup Engine 2.0 deve essere completato prima di M3 (LapSimulator dipende dai parametri fisici corretti).
- TyreModel v0.4 e grip meccanico sono prerequisiti per LapSimulator Beta (altrimenti la fisica non riflette i setup).
- FastF1 pipeline deve essere operativa prima del gating CI (M4), altrimenti i badge componenti restano rossi.
- UI Garage/HUD necessarie per player feedback (setup e sorpassi) prima della release.
- AI Driver Engine dipende dal DriverModel (skill/stato mentale) già definito e deve essere operativo prima dei test con 20 auto (M5).

## 9. Documenti correlati
- `docs/lap-physics-spec-v0.5.md`
- `docs/lapsimulator-implementation-spec.md` (Fase B, spec tecnica implementazione)
- `docs/race-engine-integration-spec.md` ← **NEW** (Fase C, integrazione nel gioco)
- `docs/setup-engine-spec-v0.1.md`
- `docs/physics-roadmap.md`
- `docs/setup-search-plan.md`, `docs/setup-ui-plan.md`
- `docs/BattleResolver.md` (da aggiornare)
- `docs/TyreModel.md`
- `docs/AeroPackage.md`, `docs/config-spec.md`, `docs/degradation-and-consumption.md`

## 10. Prossimi passi immediati
1. **PU Hybrid V2.1** – implementare consumo MGU-H direct drive e refactor deployment strategy (priorità sezioni, MGU-H awareness).
2. **Brake migration** – completare split torque regen/idraulico nel runtime usando i profili derivati.
3. **Component integration** – verificare e ottimizzare interazione tra tutti i moduli LapSimulator con nuova logica PU.
4. Validare roadmap con product/gameplay.
5. Pianificare implementazione Setup Engine 2.0 (ticket/branch dedicato).
6. Avviare design TyreModel v0.4 e Grip meccanico (spec + tasks).
