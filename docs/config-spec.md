---
title: JSON Configuration – Technical Reference
last_updated: 2026-02-08
status: draft
scope: runtime configs, seeds, derived profiles
---

## 1. Obiettivo
Catalogo dei file JSON di configurazione e del loro utilizzo nei moduli (LapSimulator, Setup Engine, Orchestratori, BattleResolver, Telemetria/Calibrazione). Evidenzia cosa è seed, cosa è derivato, e dove vengono caricati a runtime.

## 2. Convenzioni
- **Seeds globali**: valori di base non calibrati, per compound/sistemi/componenti. Prefisso `_global_default`.
- **Derived per circuito**: profili pre-fusi per circuito in `config/circuits/derived/<circuit_id>/` (generati offline).
- **Raw**: telemetria e profili Pirelli originali in `python_backend/data/circuits/`.
- **Setup bounds**: mapping slider → range fisico per circuito in `config/setup/setup_mapping_v2.json`.
- I nomi dei circuiti usano `circuit_id` (es. `it-1922_monza`).

## 3. Seeds globali (non calibrati)
- `config/tyres/tyre_params_global_default.json`
  - Compounds S/M/H/C1-C6/Int/Wet: finestre termiche, sigma gaussiane, base_grip, wear_rate_base, thermal_mass, conduction/cooling.
  - Usato da: TyreModel (LapSimulator) per grip termico/usura.
- `config/brakes/brake_params_global_default.json`
  - Sistemi base/performance/endurance: heat_capacity, thermal_mass, fade_threshold, fade_sensitivity, cooling_coeff, heat_quality. Range duct/bias default.
  - Usato da: brake termica/fade in LapSimulator; UI bounds (duct/bias) se non c’è profilo circuito.
- `config/pu/pu_maps_global_default.json`
  - Mappe ICE/ERS (Economy/Standard/Rich/Qualy): heat_load, torque_ramp, deployment_style, cooling_share, ers_output.
  - Usato da: PU termica/derating in LapSimulator.
- `config/pu/pu_reliability_global_default.json`
  - wear_coeff, soglie temp warning/critical, fattori over-rev/shock per ICE/ERS.
  - Usato da: PU wear/derating/failure.
- `config/damage/damage_coeffs_global_default.json`
  - Componenti (sospensioni, floor/beam, gearbox, steering): soglie shock, malus (grip drop, drag, shift delay, steering precision), failure_risk. Shock scalers e recovery rate.
  - Usato da: Damage model (LapSimulator / DegradationManager futuro).

## 4. Setup & track bounds
- `config/setup/setup_mapping_v2.json`
  - Per-circuito: range fisici slider (ali, ride height, sospensioni, antiroll, brake_duct, brake_balance), constraints (rake, delta sospensioni), tyre_nomination, energy_profile (fuel/ERS), cooling_guidance, cluster_context (metrics), pirelli_context (track_features, wear_rate_base, corner distribution), metadata circuito.
  - Default: fallback per circuiti senza entry dedicata.
  - Usato da: Setup Engine per bounds/interpolazione; script derived per modulare tyres/brakes/PU/damage.

## 5. Profili derivati per circuito (runtime)
- Path: `config/circuits/derived/<circuit_id>/`
  - `tyre_params.json`
  - `brake_params.json`
  - `pu_maps.json`
  - `pu_reliability.json`
  - `damage_coeffs.json`
- Generati da: `scripts/build_circuit_profiles.py` (input: seeds globali + setup_mapping_v2 + metadata telemetria per _meta). Nessun calcolo a runtime.
- Usati da: LapSimulator / orchestratori come fonte diretta per il circuito.

## 6. Raw circuit data
- Path: `python_backend/data/circuits/`
  - `*_Telemetry.json`: telemetria per circuito (geometry, reference_lap, points). Oggi usata solo come metadata; potrà affinare i modulatori in futuro.
  - `Raw_2024/`: backup/mapping FastF1.
- Usati da: pipeline di fitting/calibrazione; potenziale refinement dei modulatori.

## 7. Altre config
- `config/tyres/pirelli_track_profile_2025.json`
  - Calendario Pirelli (nomination, track_features, wear_rate_base, prescrizioni). Oggi il contesto è già incluso in `setup_mapping_v2` (campo `pirelli_context`).
- `config/config.py` / `python_backend/config.py`
  - Variabili di percorso e default di servizio (non fisica). Usati da script/server.

## 8. Utilizzo nei moduli
- **LapSimulator**: carica profili derivati (tyres/brakes/PU/damage) per calcolo termica, usura, derating, damage; legge setup bounds per interpretare slider/duct/balance.
- **BattleResolver**: consuma grip effettivo / derating per chance di sorpasso/errore.
- **Practice/Race Orchestrator**: usa stati degradazione (grip, fade, derating, warning/failure) per strategy/rientri; legge energy_profile/fuel guidance da setup_mapping.
- **Setup Engine & UI**: usa `setup_mapping_v2` per bounds slider; usa derived per mostrare suggerimenti cooling/duct.
- **Degradation & Consumption spec**: fonte di verità sui parametri; i seeds/derived sono istanze della spec.

## 9. Rigenerazione
- Derived: `python3 scripts/build_circuit_profiles.py <circuit_id> [...] --verbose`
- Rigenera quando cambiano: seeds globali, setup_mapping_v2, (in futuro) modulatori da telemetria.

## 10. Note su versioning
- I seeds sono marcati `_global_default` e vanno sostituiti dopo fitting con valori calibrati.
- I derived includono `_meta` con `circuit_id`, `setup_profile_key`, `built_at`, e (se presente) `telemetry_source`.
