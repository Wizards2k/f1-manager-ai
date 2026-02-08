---
title: Power Unit – ICE/ERS modelling
last_updated: 2026-02-08
status: draft
scope: ICE/ERS maps, termica, derating, wear, coupling con setup/mappa circuito
---

## 1. Obiettivo
Descrivere il modello PowerUnit (ICE + ERS) usato da LapSimulator: mappe, termica, derating, usura/failure e segnali per orchestratori/UI.

## 2. Componenti
- **ICE**: torque_curve, heat_load, cooling_demand, wear_coeff, temp thresholds (warning/critical), over_rev/shock factors.
- **ERS**: output_kw per mappa, recovery_rate, heat_coeff, efficienza, SOC limits, degradation.
- **Mappe**: `ECONOMY/STANDARD/RICH/QUALY` (vedi `config/pu/pu_maps_global_default.json`).
- **Reliability**: soglie temp (warning/critical), wear_coeff, over_rev/shock (vedi `config/pu/pu_reliability_global_default.json`).

## 3. Flusso (LapSimulator passo PU)
1) Input da DriverIntent: `pace_factor`, `ers_mode`, `engine_map`, `cooling_margin` (dall’AeroPackage), `airflow_penalty`.
2) Calcolo potenza: `P_total = P_ice(engine_map, rpm, wear) + P_ers(ers_mode, soc)`; applica derating se `cooling_margin < 0` o temp > warning.
3) Termica: `temp_next = temp_current + heat_load(map) * dt - cooling_capacity * (1 - airflow_penalty)`; confronta con soglie.
4) Wear: `wear += wear_coeff(map) * pace_factor * dt`; extra usura se over_rev/shock (kerb, torque ramp alto).
5) Output: `power_output`, `temp_ice/ers`, `wear_ice/ers`, `derating_flag/factor`, eventuale `failure_event`.

## 4. Mappe e config
- `config/pu/pu_maps_global_default.json`: per mappa ICE/ERS → `heat_load_kw`, `torque_ramp`, `deployment_style`, `cooling_share`, `ers_output_kw`.
- `config/pu/pu_reliability_global_default.json`: `wear_coeff`, soglie `temp_warning/critical`, fattori `over_rev/shock` (ICE/ERS).
- Derived per circuito: `config/circuits/derived/<cid>/pu_maps.json` + `pu_reliability.json` (via `scripts/build_circuit_profiles.py`).

## 5. Coupling con AeroPackage e setup
- `cooling_margin` viene da `AeroPackage.compute_forces` (sidepods/engine cover + wake penalty).
- Circuito: `cooling_guidance.avg_track_temp_delta_c` nel setup_mapping regola `cooling_share` (derivati). `brake_energy_recovery_kj` guida recupero ERS.
- Setup: duct opening e ride height influenzano indirettamente airflow/cooling; mappe rimangono discrete.

## 6. Segnali verso orchestratori/UI
- Derating flag/factor, warning/critical temp ICE/ERS, wear %, failure events.
- Orchestratori: possono forzare mappa Economy/ERS hold se overtemp; decisioni di pit/strategia.
- HUD/telemetria: mostra potenza disponibile, stato temp ICE/ERS, SOC, derating warnings.

## 7. Riferimenti
- `docs/lap-physics-spec-v0.5.md` (§3.3–3.4) per formule e pseudocodice.
- Seed/config: `config/pu/pu_maps_global_default.json`, `config/pu/pu_reliability_global_default.json`, derived per circuito `config/circuits/derived/<cid>/`.
- Script di build: `scripts/build_circuit_profiles.py`.
