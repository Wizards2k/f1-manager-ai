---
title: Fase E – Physics & Degradation Roadmap
last_updated: 2026-02-14
status: draft
scope: engine simulator v2, segment-based physics, degradation pipelines
---

## 1. Obiettivi principali
1. Introdurre l'Engine Simulator V2 basato su profili circuito segmentati e parametri aerodinamici/fisici coerenti (ClA/CdA, PU maps).
2. Implementare il modello di degradazione e consumi (gomme, freni, fuel, PU, danni) secondo `docs/degradation-and-consumption.md`.
3. Garantire coesistenza e confronti con l'attuale Engine V1 (freeze, comparatore, report).
4. Provisioning dati & tooling: pipeline FastF1/telemetry offline, derived JSON per circuito.

## 2. Deliverable (work in progress)
- **Aggiornamento 2026-02-16**
  - ✅ ERS Map Panel rivisto e integrato nel Garage V3 con tutte le telemetrie MGU-H/SOC richieste (propedeutico a D4-D5 per monitoring degradazione).
  - ✅ Script QA `python_backend/scripts/ers_speed_compare.py` per confronti on/off ERS e raccolta delta velocità (supporta le attività di tuning globale in D2/D4).
  - ✅ Suite `python_backend/tests/test_calibration_and_telemetry.py` aggiornata alla nuova logica bucket-based (49 test verdi) → base per le validazioni automatiche richieste in D6.
- [ ] **D0 – Branch & backup V1**: creare `feature/fase-e`, duplicare i file del simulatore attuale come `*_v1` o `legacy/` per permettere il confronto.
- [ ] **D1 – Dataset & data provider**:
  - **Core script**: continuare a usare `scripts/regenerate_telemetry_sections.py` per produrre i file `python_backend/data/circuits/*_Telemetry.json` (segmenti, heat/bump, DRS, pit delta). Nessuna riscrittura: lo script resta il cuore della pipeline.
  - **Wrapper FastF1 multi-anno**: nuovo comando (es. `scripts/fastf1_build_assets.py`) che scarica la sessione desiderata (`--year`, `--event`, `--session`) via FastF1, popola la cache locale (`python_backend/.fastf1_cache`), esporta i dati nel formato consumato dallo script core e lo invoca per generare i JSON.
    - ✅ Implementato `scripts/fastf1_build_assets.py` con supporto cache locale, selezione lap, invocazione automatico di `regenerate_telemetry_sections.py` e rigenerazione opzionale dei profili derived.
  - **Manifest**: salvare per ogni circuito il metadato di origine (anno, sessione, driver/lap usato, commit) in `python_backend/data/circuits/manifest.json` per tracciare versioni e rigenerare in futuro.
    - ✅ Manifest per anno scritto automaticamente (es. `python_backend/data/circuits/2024/manifest.json`).
  - **Derived refresh**: opzionale hook che, dopo la generazione del circuito, rilancia `scripts/build_circuit_profiles.py` per aggiornare `config/circuits/derived/<circuit_id>/` usando gli stessi dati.
  - **Documentazione**: guida operativa (sezione dedicata in questo file + README) con prerequisiti FastF1, setup cache e invocazione batch per produrre anni diversi.
- [ ] **D2 – Script fitting componenti & circuit profile loader**:
  - **Input comuni**: `python_backend/data/circuits/<year>/*_Telemetry.json`, manifest (per sapere anno/sessione), seed globali in `config/tyres`, `config/brakes`, `config/pu`, `config/damage`.
  - **Output**: file in `config/calibration/` (`aero.json`, `tyres.json`, `pu.json`, `brakes.json`) + opzionale `reports/calibration/<date>/<circuit>.md` con grafici/resoconto.
  - **aero_fit.py**:
    1. Carica profilo circuito e telemetria (velocità entry/exit/min per sezione).
    2. Calcola target `v_corner_max` per classi di curva, stima `CdA`/`ClA` per ogni circuito confrontando velocità rettilinei vs referenza.
    3. Produce parametri `drag_index`, `downforce_index`, `aero_balance_target` per team e li salva in `config/calibration/aero/<circuit>.json`.
  - **tyre_fit.py**:
    1. Usa lap delta vs compound/tyre_age (da manifest → sessione/gomma) per stimare `wear_rate_base`, `thermal_mass`, `temp_window` corretti.
    2. Genera curve `wear_pct(lap)` e `thermal_factor(temp)` per ogni compound e circuito.
    3. Scrive `config/calibration/tyres/<circuit>.json` e aggiorna `tyre_params.json` derived via hook.
  - **powerunit_fit.py**:
    1. Analizza velocità e throttle lungo i rettilinei per stimare `torque_ramp`, `P_total`, `ERS_deploy_profile`.
    2. Calcola `heat_load`, `cooling_share`, soglie derating basate su telemetria temperature (se disponibile) o fallback da modelli.
    3. Output in `config/calibration/pu/<circuit>.json` (mappe ICE/ERS e reliability overrides) includendo blocchi `ers_budget` e `regen_profile` che saranno inoltrati al SessionBridge, agli strumenti debug e al Practice Session Orchestrator senza parsing dei report.
  - **brake_calibration.py**:
    1. Integra `braking_energy_mj` per sezione per dedurre `heat_capacity`, `fade_threshold`, `cooling_coeff`.
    2. Bilancia front/rear in base a `brake_bias` (se registrato) e bumpiness; produce suggerimenti su duct aperto minimo.
    3. Scrive `config/calibration/brakes/<circuit>.json` includendo `regen_brake_base`/`hydraulic_vs_regen_ratio` che alimentano Telemetria/HUD e tool QA.
  - **Circuit profile loader (runtime)**:
    - Funzione `load_circuit_profile(circuit_id, season)` che:
      1. Carica Telemetry JSON per l’anno richiesto (default quello più recente disponibile).
      2. Merge dei parametri calibrati (`config/calibration/*`) con i seed derived in `config/circuits/derived/<circuit_id>/`.
      3. Restituisce un oggetto `CircuitProfile` già completo di segmenti, heat/cool factors, fuel burn, DRS, mapping setup.
    - Prevede caching in memoria per evitare reload continuo e logging del provenance (quale anno/calibrazione sono stati usati).
- [ ] **D3 – Setup → parametri fisici**:
  - Mappatura slider (front/rear wing, ride height, sospensioni, anti-roll, brake ducts) → `ClA`, `CdA`, `aero_balance`, `mu_base`, `cooling_coeff`.
  - Aggiornare `config/setup_mapping_v2.json`/derived per includere i coefficienti necessari.
- [ ] **D4 – Engine Simulator V2**:
  - Integrazione segmento per segmento (rettilinei, frenate, curve). Uso di parametri fisici per calcolare velocità target, accelerazioni, frenate.
  - Collegamento con `project_sector_time` o nuovo modulo per ottenere tempi settore/giro.
- [ ] **D5 – Degradation & consumption core**:
  - Tyre thermal/wear, brake fade, fuel burn, PU derating, mechanical damage per sezione.
  - Output di warning/failure per orchestratori e HUD.
- [ ] **D6 – Validation tooling**:
  - Report comparativi V1 vs V2 (lap time delta, settori, degradazione). Possibile generazione di HTML/Markdown in `tmp/`.
  - Test automatici e dataset di riferimento (es. JSON di simulazioni note).
- [ ] **D7 – Documentation & roadmap**:
  - Aggiornare `docs/global-roadmap.md` quando i deliverable sono completati.
  - Integrare specifiche tecniche aggiuntive in questo documento.

## 3. Specifiche tecniche (da riempire durante lo sviluppo)
### 3.1 Profilo circuito
- Struttura JSON attesa (es. sezione `geometry.sections[]`).
- Parametri obbligatori: `kind`, `length_m`, `v_entry_kph`, `v_exit_kph`, `v_min_kph`, `braking_energy_mj`, `heat_factor`, `bumpiness_factor`, `drs_active`.
- Mapping su runtime: funzione `load_circuit_profile(circuit_id)` → `CircuitProfile` (obj/dataclass).

### 3.2 Setup mapping
- Tabella slider → parametri fisici (`ClA_front`, `ClA_rear`, `CdA`, `mu_base`...), curve di normalizzazione, limiti circuito (ride height minimo, duct range).
- TBD: come combinare team_offset/driver_offset con baseline circuito.

### 3.3 Engine V2
- Pipeline di calcolo: segment loop → integrate velocity (accel/freno) → aggiornare stato vettura.
- Necessità di fallback per segmenti mancanti; log di debug per validare la sequenza.
- Interfaccia per orchestratori (metodi `RaceCar` o `SessionBridge`).

### 3.4 Degradation model
- Tyres: formule termiche/usura, link a `TyreModel` e `setup_engine`.
- Brakes: heat/fade, feedback.
- Fuel: `fuel_burn_per_segment`, effetto peso.
- PU: temperature, derating, usura ICE/ERS.
- Damage: soglie bump/kerb, malus su grip e drag.

### 3.5 Tooling & report
- Specificare formato dei report comparativi V1 vs V2 (JSON/HTML) e path (es. `tmp/sim_v2_reports/`).
- Checklist per log di debug (inclusi i dati di segmenti, handling_penalty, tyre temps).

_(queste sezioni sono placeholder: da aggiornare man mano che sviluppiamo le feature)_
