> Riferimento energetico: vedi `docs/EngineData2025.md` per spec ufficiali 2025 (capacità batteria, tabella torque combinata, preset mappe Qualy/Race/Recharge).

---
title: Power Unit – ICE/ERS modelling
last_updated: 2026-02-08
status: draft
scope: ICE/ERS maps, termica, derating, wear, coupling con setup/mappa circuito
---

## 1. Obiettivo
Descrivere il modello PowerUnit (ICE + ERS) usato da LapSimulator: mappe, termica, derating, usura/failure e segnali per orchestratori/UI.

## 2. Componenti
- **ICE**: torque_curve (lookup ICE-only), heat_load, cooling_demand, wear_coeff, temp thresholds (warning/critical), over_rev/shock factors.
- **MGU-K**: eroga max 120 kW / ~200 Nm; parametri per `deploy_mj_per_lap`, `harvest_mj_per_lap` (≤2 MJ da frenata) e logiche di clipping.
- **MGU-H**: supporta direct-drive illimitato verso MGU-K e harvest illimitato verso ES; fornisce boost anti-lag e alimenta la batteria quando la SOC scende.
- **Energy Store (Batteria)**: capacità nominale 5–6 MJ, con limite regolamentare 4 MJ per il deploy da MGU-K per giro; traccia SOC, temperatura batteria e vincoli di safety.
- **Mappe**: `ECONOMY`, `STANDARD`, `RICH`, `QUALY`, `WET`, `RECHARGE` (vedi `config/pu/pu_maps_global_default.json`). Ogni mappa definisce split consumo/recupero, target SOC e torque bias.
- **Reliability**: soglie temp (warning/critical), wear_coeff, over_rev/shock (vedi `config/pu/pu_reliability_global_default.json`).

## 3. Flusso (LapSimulator passo PU)
1) **Input** da DriverIntent e AeroPackage: `pace_factor`, `ers_mode`, `engine_map`, `cooling_margin`, `airflow_penalty`, richieste di overtake/recharge.
2) **Calcolo potenza**: `P_total = P_ice(engine_map, rpm, wear, torque_curve) + P_ers(ers_mode, soc)` applicando i vincoli FIA:
   - `deploy_mj_per_lap` ≤ 4 MJ (MGU-K → ruote).
   - `harvest_mj_per_lap` ≤ 2 MJ (frenata → batteria) + quota illimitata da MGU-H.
   - Direct-drive: `mguh_direct_ratio` e `mguh_power_kw` determinano quanta energia MGU-H alimenta direttamente l’MGU-K (bypass batteria) e quanta viene instradata all’ES. Gli offset per mappa arrivano dai derived (`config/circuits/derived/<cid>/pu_maps.json`).
3) **Gestione SOC/batteria**: aggiorna `soc_current = clamp(soc - deploy + harvest, 0, capacity_mj)` e segnala clipping se SOC < target; memorizza `target_soc_end_lap` per la mappa attiva.
4) **Termica**: `temp_next = temp_current + heat_load(map) * dt - cooling_capacity * (1 - airflow_penalty)` sia per ICE che per ERS/ES; derating quando temp > soglia.
5) **Brake migration / rigenerazione frenante**:
   - Quando `soc_current >= soc_max` o `harvest_mj_per_lap` raggiunge 2 MJ, l’MGU-K non può più generare coppia negativa → `brake_migration_active = True`.
   - In tal caso il modello freni deve aumentare automaticamente la quota frenante idraulica posteriore (`brake_bias_override`) per evitare instabilità.
   - Necessario registrare `regen_brake_torque`, `hydraulic_brake_torque` e un `brake_energy_dumped` per i report.
6) **Wear**: `wear += wear_coeff(map) * pace_factor * dt`; extra usura se over_rev/shock (kerb, torque ramp alto, mguh direct > soglia) e durante brake migration prolungata.
7) **Output**: `power_output`, `soc`, `temp_ice/ers/es`, `wear_ice/ers`, `derating_flag/factor`, `brake_migration_flag`, eventuali `failure_event`, `strategy_suggestion` (es. passare a RECHARGE).

## 4. Mappe e config
- `config/pu/pu_maps_global_default.json`: per mappa → `heat_load_kw`, `torque_ramp`, `deployment_style`, `cooling_share`, `ers_output_kw`, **nuovi campi** `deploy_mj_per_lap`, `harvest_mj_per_lap`, `mguh_direct_ratio`, `target_soc_end_lap`, `torque_bias`, `notes`.
- `config/pu/pu_reliability_global_default.json`: `wear_coeff`, soglie `temp_warning/critical`, fattori `over_rev/shock` (ICE/ERS) + parametri batteria (`temp_warning_c`, `temp_critical_c`).
- Derived per circuito: `config/circuits/derived/<cid>/pu_maps.json` + `pu_reliability.json` + eventuali `torque_curve.json` generati da `scripts/powerunit_fit.py` + parametri freno/regen (es. `regen_brake_limit_nm`). Dal 2026-02-15 il fitting calcola anche `mguh_power_kw` e annota il profilo (`_meta.mguh_profile`) scelto tra high/balanced/low speed, utilizzato runtime per i bias Dynamici.
- Documentazione tecnica: `docs/EngineData2025.md` (spec), nuovo allegato "PU energy model" (in preparazione) per detailing UI + mappature.

## 5. Coupling con AeroPackage e setup
- `cooling_margin` viene da `AeroPackage.compute_forces` (sidepods/engine cover + wake penalty).
- Circuito: `cooling_guidance.avg_track_temp_delta_c` nel setup_mapping regola `cooling_share` (derivati). `brake_energy_recovery_kj` guida recupero ERS.
- Setup: duct opening e ride height influenzano indirettamente airflow/cooling; mappe rimangono discrete.

## 6. Segnali verso orchestratori/UI
- Derating flag/factor, warning/critical temp ICE/ERS/ES, wear %, failure events, `soc_target_gap`.
- Orchestratori: possono forzare mappa Economy/ERS hold se overtemp o SOC troppo basso, pianificare cicli `Push x` / `Recharge y`.
- HUD/telemetria: mostra potenza disponibile, stato temp ICE/ERS/ES, SOC, indicatori MJ consumati/recuperati sul giro corrente e suggerimenti mappa. Con l’aggiornamento MGU-H vengono serializzati anche `lap_mguh_direct_mj`, `lap_mguh_harvest_mj`, oltre al trace per sezione (`mguh_direct_mj`, `mguh_es_mj`) consumati da garage v3 e strumenti QA.

### 6.1 Feed per Telemetria, debug e PSO
- Gli script di fitting (`config/calibration/pu/<cid>.json`) espongono blocchi `ers_budget` e `regen_profile` che contengono target SOC per mappa, limiti MJ per giro, rapporto MGUH direct-drive e coefficiente di rigenerazione consigliato: queste strutture devono essere serializzate nei payload `race_update.pu_stats` e nella telemetria sezione-per-sezione (`pu_energy_trace`).
- Gli stessi blocchi alimentano gli strumenti di debug (overlay ingegnere, report QA) evitando di parsare i Markdown: il SessionBridge inoltra il JSON direttamente ai pannelli interni.
- Il Practice Session Orchestrator legge `ers_budget` per programmare automaticamente sequenze push/recharge e usa `regen_profile` per decidere quando proporre brake migration o aprire i duct; i report Markdown sono la rappresentazione leggibile di questi stessi dati e vanno generati assieme al JSON per audit.

## 7. Riferimenti
- `docs/lap-physics-spec-v0.5.md` (§3.3–3.4) per formule e pseudocodice.
- `docs/EngineData2025.md` per limiti FIA 2025, torque curve, preset mappa.
- Seed/config: `config/pu/pu_maps_global_default.json`, `config/pu/pu_reliability_global_default.json`, derived per circuito `config/circuits/derived/<cid>/`.
- Script di build: `scripts/build_circuit_profiles.py`, `scripts/powerunit_fit.py`.
