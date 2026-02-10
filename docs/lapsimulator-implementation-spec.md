---
title: LapSimulator Runtime – Implementation Spec v0.2
version: 0.2
last_updated: 2026-02-10
status: in_progress
branch: feature/lapsimulator-runtime
scope: "Implementazione standalone del motore fisico LapSimulator (8-step update_section loop) con test indipendenti"
parent_spec: docs/lap-physics-spec-v0.5.md
---

## 1. Obiettivo

Implementare il LapSimulator come modulo Python standalone (`python_backend/lap_simulator/`), completamente indipendente dal RaceEngine esistente. Il modulo implementa il loop a 8 passi descritto in `lap-physics-spec-v0.5.md` §3.3 e il runtime loop §3.3.1.

Una volta testato e calibrato, il modulo verrà integrato nel gioco sostituendo il motore fisico attuale.

## 2. Architettura

```
python_backend/lap_simulator/
├── __init__.py              # Package entry point
├── data_types.py            # Type system (30+ dataclass, enum, helpers)
├── config_loader.py         # Carica JSON circuito + profili derivati
├── aero_package.py          # Passo 3 – Forze aerodinamiche
├── power_unit.py            # Passo 4 – ICE + ERS + fuel
├── tyre_model.py            # Passo 5a – Termica 2 strati + grip + usura
├── brake_system.py          # Passo 5b – Termica freni + fade
├── driver_model.py          # Passo 2 – Decisione pilota (tattico, per-sezione)
├── update_section.py        # Passi 1-8 orchestrati
├── lap_simulator.py         # Runtime loop (InputMixer → update × N → Commit)
├── ai_data_types.py         # AI Driver Engine types (RunProgram, RunPlan, SessionPlan)
├── ai_driver_engine.py      # AI Driver Engine (strategico, per-run)
└── tests/                   # 105 test unitari + integrazione
```

### 2.1 Flusso dati (un giro)

```
CircuitConfig (JSON)  ──►  LapSimulator
                              │
EnvContext (meteo)    ──►     │
                              │
CarEntry (state+setup+driver) │
                              ▼
                    ┌─── Per ogni sezione ───┐
                    │                        │
                    │  1. Input & stato       │
                    │  2. DriverModel         │  → DriverIntent
                    │  3. AeroPackage         │  → AeroForces
                    │  4. PowerUnit           │  → PU output + thermal
                    │  5a. TyreModel          │  → grip + thermal + wear
                    │  5b. BrakeSystem        │  → braking_efficiency
                    │  6. Velocità + dt       │  → v_effective, dt_s
                    │  7. State update        │  → fuel, mental, cooldowns
                    │  8. Return              │  → SectionResult
                    │                        │
                    └────────────────────────┘
                              │
                              ▼
                         LapResult
                    (lap_time, sectors, events,
                     fuel, wear, temperatures)
```

## 3. Moduli implementati

### 3.1 data_types.py – Type System

| Dataclass | Ruolo | Campi chiave |
|-----------|-------|-------------|
| `SectionContext` | Descrizione statica sezione circuito | kind, length_m, v_base_kph, heat/cool_factor, bumpiness, kerb_severity, braking_energy_mj |
| `EnvContext` | Condizioni ambientali | air_temp, track_temp, air_density, rain, rubber_level |
| `TyreCompoundParams` | Parametri immutabili per compound | temp_window (surface/core), sigma, base_grip, wear_rate, thermal_mass, conduction/cooling |
| `TyreState` | Stato mutabile per ruota | surface_temp, core_temp, wear_pct, graining, blistering, effective_grip |
| `BrakeSystemParams` / `BrakeState` | Parametri e stato freni | heat_capacity, fade_threshold, temp, fade_level, duct_opening, bias |
| `EngineMapParams` / `PUState` | Mappe motore e stato PU | heat_load, torque_ramp, ers_output; ice/ers_temp, wear, fuel_kg, ers_energy_mj |
| `AeroComponent` / `AeroSetup` / `AeroForces` | Componenti aero, setup e output | base_df/drag, angle, suspension, ride_height; df_eff, drag_eff, handling_penalty |
| `DriverSkills` / `DriverMentalState` / `DriverIntent` | Pilota statico, mentale, decisioni | raw_pace, aggression, consistency; confidence, fatigue; pace_factor, target_line |
| `DamageCoeffs` / `DamageState` | Danni meccanici | shock_threshold per componente, grip_drop, drag_increase |
| `CarState` | Stato completo auto | tyres (4), brakes, pu, damage, mental, lap tracking, battle signals |
| `SectionResult` | Output di update_section() | dt_s, v_effective, events, overtake_window, grip, power |
| `CircuitConfig` | Config completa circuito | sections, tyre/brake/pu/damage params, coefficienti globali |

**Helpers**: `clamp()`, `gaussian()`, `SECTION_HEAT_COOL`, `CURVE_FACTOR`

### 3.2 config_loader.py – Caricamento configurazione

- Carica telemetria circuito da `python_backend/data/circuits/<id>_Telemetry.json`
- Carica profili derivati da `config/circuits/derived/<id>/` (tyre, brake, PU, damage)
- Fallback a global defaults (`config/tyres|brakes|pu|damage/*_global_default.json`)
- Parsing automatico sezioni con heat/cool factor da `SECTION_HEAT_COOL`

### 3.3 aero_package.py – Passo 3

**Input**: AeroSetup, SectionContext, EnvContext, CarState, v_kph, airflow_penalty, drs_active
**Output**: AeroForces (df_front/rear_eff, drag_eff, aero_balance, handling_penalty, under/oversteer, bump/kerb, cooling)

**Decisione implementativa**: DF e drag sono trattati come "punti aero" (scala 0-50 per componente), NON come forze fisiche. Un `speed_factor` (0.8-1.15) modula leggermente il DF con la velocità. Questo mantiene i valori nella scala di `df_ref=70`.

Formula chiave:
```
df_component = base_downforce * angle_term * speed_factor * damage_factor
aero_balance = df_front_eff / df_total
handling_penalty = |balance_error| * k_handling
```

### 3.4 power_unit.py – Passo 4

**Input**: PUState, DriverIntent, AeroForces, SectionContext, config
**Output**: PUState aggiornato, eventi

- ICE: `power = BASE_550kW * torque_ramp * wear_factor * derating_factor * fuel_mix`
- ERS: output da mappa, limitato da batteria e derating termico
- Fuel burn: `rate = BASE_0.035 * torque_ramp * fuel_mix`
- Termica: heat_in da mappa, cooling da aero capacity
- Derating: progressivo tra temp_warning e temp_critical
- Wear: `ice_wear += coeff * power * dt * overrev_factor * shock_factor` (over_rev se torque_ramp > 0.85; shock da kerb_severity + bump_penalty)

### 3.5 tyre_model.py – Passo 5a

**Input**: CarState (4 gomme), SectionContext, EnvContext, AeroForces, DriverIntent
**Output**: effective_grip_front/rear, eventi

Modello termico a 2 strati per ogni ruota:
- **Surface**: reattiva — heat da section.heat_factor × pace × axis_modifier, cool da convection
- **Core**: inerte — scambio con surface via conduction_coeff
- **Grip**: `base_grip × gaussian_thermal × wear_factor × setup_bonus`
- **Usura**: `wear_rate_base × pace × (1 + bump + kerb + handling) × section_km`
- **Failure modes**: overheat, puncture risk (>80% wear), graining (understeer+cold), blistering (core hot), flatspot (kerb+brake)

### 3.6 brake_system.py – Passo 5b

**Input**: CarState.brakes, SectionContext, AeroForces, DriverIntent
**Output**: braking_efficiency (0.9-1.15), eventi

- Energia ripartita front/rear da bias
- Termica: heat_in da energy/capacity, cooling da duct × airspeed
- Fade: se temp > threshold → fade_level proporzionale all'eccesso
- Braking efficiency calcolata SOLO su sezioni con braking_energy ≥ 0.05

### 3.7 driver_model.py – Passo 2

**Input**: DriverSkills, DriverMentalState, SectionContext, CarState
**Output**: DriverIntent

- `pace_factor` = skill_pace + confidence - fatigue - pressure, × push_level
- Aggression bonus in curva proporzionale a skill × confidence
- Target line: optimal/defensive/aggressive basato su stato battaglia
- ERS deploy: su rettilinei con batteria > 0.5 MJ o in attacco
- Tyre/fuel save: attivati da usura alta, push basso, fuel critico

### 3.8 update_section.py – Orchestrazione Passi 1-8

Chiama in sequenza: DriverModel → AeroPackage → PowerUnit → TyreModel → BrakeSystem → calcolo velocità → state update → return SectionResult.

Formula velocità:
- **Curva**: `v = v_base × (1 + curvature × k_df × Δdf/df_ref) × (1 - handling) × braking_eff × grip_axis`
- **Rettifilo**: `v = v_base + k_power × Δpower - k_drag × Δdrag`, clampato a v_cap
- **dt = section_length / v_effective**

### 3.9 lap_simulator.py – Runtime Loop

Classe `LapSimulator` con:
- `register_car(CarEntry)` — registra auto con stato, setup, driver
- `run_lap()` → Dict[car_id, LapResult] — un giro per tutte le auto
- `run_laps(n)` → Dict[car_id, List[LapResult]] — N giri
- Tracking settori via `sector_markers_m`
- Placeholder per `_compute_airflow_penalty()` e `_compute_traffic_constraint()` (multi-car futuro)

### 3.10 ai_driver_engine.py – AI Driver Engine (strategico)

Livello **strategico** (per-run) che si affianca al livello **tattico** (per-sezione) di `driver_model.py`.

**Moduli**: `ai_data_types.py` (tipi) + `ai_driver_engine.py` (logica)

**Tipi principali**:
- `RunProgram`: enum (SETUP_VALIDATION, TYRE_DEG, QUALI_SIM, RACE_TRIM, AERO_RND)
- `RunPlan`: programma + laps + fuel + compound + engine_map + ers_mode + push_level
- `SessionPlan`: lista RunPlan per FP1/FP2/FP3
- `AITeamConfig`: simulation_efficiency, budget_tier
- `AIDriverConfig`: sim_affinity, setup_finding_skill, mechanical_sympathy
- `RunResult`: outcome + telemetry summary + setup adjustments + converged flag

**Classe `AIDriverEngine`** — lifecycle per sessione:
1. `start_session(session_type)` → genera `SessionPlan` con 2-3 run
2. `has_next_run()` / `next_run()` → iterazione sui run pianificati
3. `configure_current_run()` → `CarEntry` pronto per LapSimulator
4. `complete_run(lap_results)` → analisi telemetria, proposta setup adjustments, avanzamento
5. `session_summary()` → riepilogo sessione

**Setup seed** (spec §2): `score = 0.7 × sim_eff + 0.3 × sim_affinity` → offset_factor inversamente proporzionale. Top team: offset ~2%, backmarker: ~14%.

**Refinement loop** (spec §5): dopo ogni run, analizza grip balance (front vs rear), brake cooling, traction. Se delta > threshold → propone adjustment su front_wing, antiroll, brake_duct. Accuracy dipende da `sim_affinity + mechanical_sympathy`.

**Session programs** (spec §3):
- FP1: 2× Setup Validation (+ Tyre Deg per top team)
- FP2: Tyre Deg + Quali Sim + Race Trim
- FP3: Quali Sim (+ Setup Validation se non converged)

## 4. Coefficienti globali di tuning

### 4.1 Coefficienti velocità (v_effective model, fallback)

| Coefficiente | Valore | Ruolo |
|-------------|--------|-------|
| `df_ref` | 70.0 | DF normalizzazione (punti aero) |
| `drag_ref` | 30.0 | Drag normalizzazione |
| `power_ref_kw` | 450.0 | Potenza di riferimento (ICE+ERS STANDARD) |
| `k_df` | 0.15 | Peso DF su velocità curva |
| `k_drag` | 0.10 | Peso drag su velocità rettifilo |
| `k_drag_curve` | 0.05 | Peso drag in curva/staccata |
| `k_power` | 0.12 | Peso potenza su velocità rettifilo |
| `k_handling` | 0.8 | Peso balance error su handling penalty |
| `v_min_kph` | 50.0 | Velocità minima assoluta |
| `v_cap_kph` | 370.0 | Velocità massima assoluta |

### 4.2 Coefficienti dt_ref penalty model (v0.2 — tuned su 24 circuiti)

| Coefficiente | v0.1 | v0.2 (tuned) | Ruolo |
|-------------|------|-------------|-------|
| `baseline_delta` | 0.05 | **0.07** | Baseline % sopra VER 2024 Q (netto ~+5.5% dopo grip bonus) |
| `k_aero_penalty` | 0.03 | 0.03 | Contributo aero al penalty |
| `k_grip_penalty` | 0.05 | **0.02** | Contributo grip (formula normalizzata su `grip_ref=0.70`) |
| `k_brake_penalty` | 0.03 | **0.015** | Contributo brake fade |
| `k_fuel_penalty` | 0.03 | **0.015** | Contributo peso carburante |
| `k_driver_penalty` | 0.05 | **0.03** | Contributo skill pilota |
| `fuel_max_kg` | 110.0 | 110.0 | Fuel di riferimento per normalizzazione |

**Modifiche formula v0.2**:
- `delta_grip = k_grip × (grip_ref - grip_avg) / grip_ref` — neutro a grip=0.70, bonus se sopra, penalty se sotto
- `thermal_factor` floor alzato da 0.70 → 0.82 (gomme fredde meno penalizzanti al L1)
- Clamp totale invariato: [-0.05, +0.30]

## 5. Bug trovati e risolti durante implementazione

### Bug 1 – Velocità curve esplode (CRITICO)
- **Causa**: `dyn_pressure` (forza fisica) moltiplicata per `base_downforce` (punti aero) produceva DF ~271K vs df_ref=70
- **Fix**: Rimosso dyn_pressure, usato speed_factor (0.8-1.15). Aggiunto v_cap clamp anche per curve.
- **Gap spec**: §3.3 Passo 3 mescola coefficienti fisici (Cl × q) con punti aero (df_ref=70). Serve chiarire la scala.

### Bug 2 – Brake fade non rilevato
- **Causa**: Soglia evento brake_fade a 0.1, ma fade_level reale era 0.033 (corretto ma sotto soglia)
- **Fix**: Soglia abbassata a 0.01
- **Gap spec**: Manca tabella severity → azione per tutti gli eventi

### Bug 3 – late_brake_success su ogni sezione
- **Causa**: Formula braking_efficiency produceva sempre 1.15 (termine positivo troppo forte), anche su rettilinei senza frenata
- **Fix**: braking_efficiency = 1.0 se braking_energy < 0.05; ridotto peso termine positivo; evento richiede braking_energy ≥ 0.5
- **Gap spec**: Formula non specifica che va applicata solo con frenata significativa

## 6. Gap identificati nelle specifiche funzionali

### 6.1 Ambiguità DF: punti aero vs forze fisiche
La spec usa `dyn_pressure = 0.5 * ρ * v²` nel calcolo DF componente (§3.3 Passo 3), ma poi normalizza con `df_ref = 70` (§5). Se df_ref fosse in Newton, dovrebbe essere ~10,000-50,000 N. Se è in "punti aero", dyn_pressure non va applicato. **Decisione presa**: punti aero. **Azione**: aggiornare la spec per chiarire.

### 6.2 braking_energy_mj mancante nelle sezioni
I file Telemetry JSON non contengono `braking_energy_mj` per sezione. Attualmente è 0 per tutte le sezioni, il che rende il BrakeSystem inerte. **Azione**: calcolare braking_energy dalla telemetria (punti brake > 0) o stimarla da v_entry - v_exit.

### 6.3 bumpiness_factor e kerb_severity mancanti
I file Telemetry hanno `bumpiness: null` per tutte le sezioni. I valori sono nel `pirelli_track_profile_2025.json` a livello circuito (bumps: 2, kerbs: 4 per Monza) ma non per sezione. **Azione**: distribuire i valori circuito alle sezioni o arricchire la telemetria.

### 6.4 Soglie eventi non definite
La spec non definisce quando un evento deve essere generato (es. a quale fade_level scatta "Brake fade", a quale temperatura "Tyres overheating"). **Azione**: creare tabella severity/threshold per tutti gli event_type.

### 6.5 DRS zones non mappate alle sezioni
I file Telemetry hanno `drs_zones` con `detection_m/start_m/end_m` tutti null. Le sezioni non hanno `drs_available` popolato. **Azione**: mappare le zone DRS reali alle sezioni.

### 6.6 Assenza di radius_m nelle sezioni
Le sezioni curve hanno `radius_m: null`. Il `curvature_factor` viene calcolato dal tipo sezione (SlowCorner=0.4, FastCorner=1.0) invece che dalla geometria reale. **Azione**: estrarre radius dalla telemetria (coordinate x,y) o definire valori manuali.

### 6.7 ✅ RISOLTO — Fuel weight effect
Implementato in `update_section.py` Step 6: `delta_fuel = k_fuel_penalty × (fuel_kg / fuel_max_kg) × corner_mult`. Le curve sono penalizzate 30% in più (massa → meno grip in curva). Il fuel si scarica progressivamente via PU step.

### 6.8 ✅ RISOLTO — Mechanical grip / setup_bonus
Implementato in `tyre_model.py`: `setup_bonus` ora derivato da `suspension.efficiency` (+3% max), `ride_height` deviation (-0.1%/mm), `antiroll` deviation (-2% max). Passato `AeroSetup` a `update_tyres()` → `_update_single_tyre()`. Range: 0.92–1.05.

### 6.9 ✅ RISOLTO — DriverSkills in BrakeSystem
`brake_system.py`: aggiunto parametro `driver_skills` a `update_brakes()`. `driver_brake_skill = (race_craft + aggression) / 200` (0.0–1.0). Passato da `update_section.py`.

### 6.10 ✅ RISOLTO — Overtake window
Implementato in `update_section.py` Step 7: `overtake_window = ow_base + ow_drs + ow_driver + ow_grip + ow_brake + ow_aggression` (0–1).
- `ow_base`: per section kind (Straight=0.6, SlowCorner=0.10, FastCorner=0.02)
- `ow_drs`: +0.15 se DRS attivo
- `ow_driver`: overtaking_skill/100 × 0.15
- `ow_grip`: (grip_avg - 0.85) × 0.5, clamped ±0.1
- `ow_brake`: 0.1 × braking_efficiency (solo con braking_energy ≥ 0.5)
- Risultati: max ~0.78 (rettilineo+DRS), avg ~0.36. Pronto per BattleResolver.

### 6.11 ✅ RISOLTO — Sezioni telemetria con gap e avg_speed inaffidabile

**Scoperto durante calibrazione il 2026-02-10. Risolto il 2026-02-10** con `scripts/regenerate_telemetry_sections.py`.

#### Problema 1: Gap di copertura
Le sezioni nel Telemetry JSON (es. Monza) non coprono il 100% del circuito:
- Circuito: 5725m, coperto da sezioni: 4869m → **856m non coperti (15%)**
- Gap principale: 856m tra "Main Straight Start-1" (end=132m) e "Turn 1-2" (start=988m)
- Quel gap contiene la **zona di frenata più pesante** del circuito (da 339 a 81 kph)

#### Problema 2: avg_speed non è la velocità media reale
Il campo `avg_speed` nelle sezioni non corrisponde alla media dei punti telemetrici nella sezione:
| Sezione | avg_speed | v reale @start | v reale @end | Media punti |
|---------|-----------|---------------|-------------|-------------|
| Turn 1-2 (SlowCorner) | 81 | 284 | 294 | 291 |
| Medium Straight 3-4 | 280 | 142 | 134 | 149 |
| Turn 6-7 (FastCorner) | 223 | 153 | 114 | 136 |

`avg_speed` sembra essere la velocità **caratteristica** (apex per curve, punta per rettilinei), non la media reale.

#### Problema 3: Confini sezione non allineati alla fisica
I confini delle sezioni non corrispondono ai punti naturali del profilo velocità:
- La frenata per Turn 1 avviene **fuori** dalla sezione Turn 1-2 (nel gap 132-988m)
- "Medium Straight 3-4" contiene una frenata pesante (v scende da 142 a 134)
- Le sezioni curve sono troppo corte (58m, 57m) e non catturano il profilo completo

#### Conseguenza
- `dt = length / v_base` produce tempi irrealistici (somma 72s vs 101s reali)
- Il LapSimulator non può calibrare correttamente senza `dt_ref` affidabili per sezione
- I dati mancanti (braking_energy, DRS, radius) dipendono dalla corretta segmentazione

#### Risoluzione
Rigenerati tutti i 24 circuiti con `scripts/regenerate_telemetry_sections.py`:
1. ✅ Copertura 100% del circuito (nessun gap)
2. ✅ Confini ai punti naturali (inizio frenata, apex, uscita curva)
3. ✅ `avg_speed` = vera media pesata per distanza
4. ✅ `dt_ref_s` = integrazione `Σ(ds/v)` (delta < 0.1s vs lap_time reale)
5. ✅ `braking_energy_mj` calcolata da ΔKE
6. ✅ DRS zones mappate da codici FastF1
7. ✅ `radius_m` calcolato via circle fit
8. ✅ Classificazione 5-tier allineata a `derive_setup_clusters.py`:
   - VerySlowCorner (< 80 kph): 24 sezioni
   - SlowCorner (80-130 kph): 76 sezioni
   - MediumCorner (130-200 kph): 59 sezioni
   - FastCorner (200-270 kph): 17 sezioni

Nuovi campi per sezione: `v_entry_kph`, `v_exit_kph`, `v_min_kph`, `v_max_kph`, `dt_ref_s`, `braking_energy_mj`, `drs_active`, `radius_m`.

Spec: `docs/telemetry-sections-v2-spec.md`. Branch `feature/telemetry-sections-v2` merged in `feature/lapsimulator-runtime`.

## 7. Stato test

| Suite | Test | Stato |
|-------|------|-------|
| test_data_types | 19 | ✅ PASS |
| test_config_loader | 17 | ✅ PASS |
| test_aero_package | 11 | ✅ PASS |
| test_power_unit | 10 | ✅ PASS |
| test_tyre_model | 18 | ✅ PASS |
| test_brake_system | 7 | ✅ PASS |
| test_integration_lap | 12 | ✅ PASS |
| test_ai_driver | 29 | ✅ PASS |
| test_battle_resolver | 29 | ✅ PASS |
| **Totale** | **152** | **✅ ALL PASS** |

## 8. Risultati simulazione Monza

### 8.1 v0.1 (pre-calibrazione, sezioni v1 difettose)

| Giro | Tempo | Fuel | Usura | Temp gomme | Note |
|------|-------|------|-------|------------|------|
| 1 | 81.6s | 98.5 kg | 1.09% | 72.7°C | Ref VER Q: 101.1s |
| 5 | 84.3s | 92.4 kg | 5.36% | 57.9°C | Gap: -20s |

### 8.2 v0.2 (modello dt_ref, sezioni v2, baseline=+5%)

| Giro | Tempo | Fuel | Usura | Temp gomme | Note |
|------|-------|------|-------|------------|------|
| 1 | 108.1s | 98.1 kg | 1.43% | 107.0°C | +6.9% vs VER Q ✅ |
| 2 | 110.0s | 96.1 kg | 2.83% | 115.0°C | Degrado visibile |
| 3 | 111.6s | 94.2 kg | 4.22% | 117.3°C | Stabilizzazione |
| 4 | 111.9s | 92.2 kg | 5.60% | 117.5°C | |
| 5 | 112.0s | 90.3 kg | 6.97% | 117.1°C | Plateau |

**Modello dt_ref**: `dt = dt_ref × (1 + baseline + Σ penalties)`
- `baseline_delta = +0.07` (netto ~+5.5% dopo grip bonus)
- Penalties: aero (±0.03), grip (±0.02), brake (±0.015), fuel (±0.015), driver (±0.03)
- Clamp totale: -0.05 → +0.30

### 8.3 v0.2 (tuning multi-circuito, 24/24 circuiti)

Risultati L1 (top team, raw_pace=85):
- **Media**: +5.7% vs ref | **Range**: 4.7%–8.8% | **22/24** nel target [4.5–7.5%]
- Outlier alti: Imola +8.8% (23 sez, 12 curve), Austin +7.6% (17 sez) — giustificato dalla natura tecnica
- Degrado L5 su circuiti tecnici: rimandato a TyreModel v2 (compound C1-C6 cambieranno il comportamento)

**Posizionamento griglia** (basato su dati F1 2025 reali, prime 4 gare):
- Top team inizio stagione: +5.5% netto (~107s Monza)
- Midfield: +7.5% (~109s)
- Backmarker: +9.5% (~111s)
- Spread griglia: ~4% (~4s)
- Floor post-sviluppo: +2% (~103s, raggiungibile a fine stagione)

## 9. Prossimi passi

1. ✅ ~~Integrare sezioni v2 nel LapSimulator~~ — completato (modello dt_ref penalty)
2. ✅ ~~Implementare gap §6.7-6.10~~ — fuel weight, mechanical grip, driver skills brakes, overtake window
3. ✅ ~~Tuning coefficienti~~ — calibrato su 24/24 circuiti (3 round). L1 avg=+5.7%, 22/24 nel target.
4. ✅ ~~PU over_rev/shock~~ — usura ICE/ERS ora usa overrev_factor + shock_factor
5. ✅ ~~AI Driver Engine~~ — setup seed, session planning (FP1/2/3), run config, post-run analysis, refinement loop. 20 test.
6. ✅ ~~BattleResolver 2.0~~ — proximity detection, dirty air, scenario tagging, attack chance, resolve pair (overtake/blocked/side-by-side/collision), radio messages, integrazione LapSimulator multi-car. 29 test.
7. **Practice Session Orchestrator** — scheduling sessione, queue pitlane, run data
8. ✅ ~~TyreModel v2~~ — compound C1-C6 con degradation_rate_multiplier + slip_sensitivity, graining/blistering temporali, heat-cycle penalty. 9 nuovi test.

### 9.1 Copertura `degradation-and-consumption.md`

| Sezione | Stato | Note |
|---------|-------|------|
| §5.1 Tyres | ✅ Completo | Compound C1-C6+Inter+Wet, degradation multiplier, slip sensitivity, heat-cycle penalty, graining/blistering temporali |
| §5.2 Brakes | ✅ Completo | Termica, fade, wear, braking_efficiency |
| §5.3 Fuel | ✅ Completo | Fuel burn + fuel weight penalty (§6.7) |
| §5.4 PU | ✅ Completo | Termica, derating, wear con over_rev/shock |
| §5.5 Damage | 🟡 Parziale | Struttura DamageState presente, effetti progressivi da completare |
