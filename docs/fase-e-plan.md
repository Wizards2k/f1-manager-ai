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
- [ ] **D0 – Branch & backup V1**: creare `feature/fase-e`, duplicare i file del simulatore attuale come `*_v1` o `legacy/` per permettere il confronto.
- [ ] **D1 – Dataset & data provider**:
  - **Core script**: continuare a usare `scripts/regenerate_telemetry_sections.py` per produrre i file `python_backend/data/circuits/*_Telemetry.json` (segmenti, heat/bump, DRS, pit delta). Nessuna riscrittura: lo script resta il cuore della pipeline.
  - **Wrapper FastF1 multi-anno**: nuovo comando (es. `scripts/fastf1_build_assets.py`) che scarica la sessione desiderata (`--year`, `--event`, `--session`) via FastF1, popola la cache locale (`python_backend/.fastf1_cache`), esporta i dati nel formato consumato dallo script core e lo invoca per generare i JSON.
    - ✅ Implementato `scripts/fastf1_build_assets.py` con supporto cache locale, selezione lap, invocazione automatico di `regenerate_telemetry_sections.py` e rigenerazione opzionale dei profili derived.
  - **Manifest**: salvare per ogni circuito il metadato di origine (anno, sessione, driver/lap usato, commit) in `python_backend/data/circuits/manifest.json` per tracciare versioni e rigenerare in futuro.
    - ✅ Manifest per anno scritto automaticamente (es. `python_backend/data/circuits/2024/manifest.json`).
  - **Derived refresh**: opzionale hook che, dopo la generazione del circuito, rilancia `scripts/build_circuit_profiles.py` per aggiornare `config/circuits/derived/<circuit_id>/` usando gli stessi dati.
  - **Documentazione**: guida operativa (sezione dedicata in questo file + README) con prerequisiti FastF1, setup cache e invocazione batch per produrre anni diversi.
- [ ] **D2 – Circuit profile loader**: loader runtime che espone segmenti, fattori termici, fuel burn, bumpiness e DRS al simulatore.
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
