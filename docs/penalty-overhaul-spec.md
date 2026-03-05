# Penalty System Overhaul – Specifiche Operative

## 1. Obiettivo
Portare il LapSimulator a modellare penalties realistiche per ogni vettura (AI + giocatore) partendo da una baseline "McLaren ideale" (fuel 10 kg, compound soft fresco, push 10, pilota top, mappe ICE/ERS attacco, freni in finestra, setup raccomandato) e introducendo scostamenti controllati per tutti i fattori fisici principali.

## 2. Scope
1. **Baseline circuito/vettura**: ingestione dei dati `python_backend/data/circuits/2025/*_Telemetry.json` + `config/` per definire i valori zero-penalty per ciascun tracciato.
2. **Fattori considerati**: fuel, gomme, push level, skill pilota, mappe ICE/ERS, freni, assetto, circuit extras (vento, grip evolution, bumpiness).
3. **Output**: nuova struttura `PerformancePenalties`, breakdown telemetrico/UI, suite di test per convalida.

## 3. Baseline Circuito
- **CircuitPenaltyProfile** (nuova sorgente dati) per ogni circuito:
  - `fuel_reference_kg`, `fuel_penalty_coeff`
  - `tyre_reference` (compound, temperatura, usura)
  - `setup_window` (ali, rake, sospensioni)
  - `brake_duct_range`, `fade_thresholds`
  - `sensitivity` (drag, cornering, fuel)
- I valori sono derivati da:
  - Telemetria: `v_ref`, `braking_energy_mj`, `grip_evolution_curve`, `wind`
  - Config: `k_aero_penalty`, `k_grip_penalty`, `duct_recommendation`, `brake_params`

## 4. Struttura Penalty
```python
dataclass PerformancePenalty:
    value: float
    baseline: float
    coeff: float
    limit_ms: float
    penalty_ms: float

dataclass PerformancePenalties:
    fuel: PerformancePenalty
    tyres: PerformancePenalty
    push: PerformancePenalty
    driver_skill: PerformancePenalty
    ice_map: PerformancePenalty
    ers_map: PerformancePenalty
    brakes: PerformancePenalty
    setup: PerformancePenalty
    circuit_extra: PerformancePenalty
    total_penalty_ms: float
```
- Memorizzata in `CarState`, aggiornata ogni sezione.
- Helper `apply_penalty(value, baseline, coeff, limit)` garantisce saturazione sotto il limite definito.

## 5. Fattori & Limiti
| Fattore | Baseline | Formula | Limite realistico |
| --- | --- | --- | --- |
| Fuel | 10 kg | `(fuel - 10) * coeff_circuit` con coeff medio 0,0035 s/kg | +2,5 s |
| Gomme | Compound più morbido, T ottimale, usura <2% | somma di penalty per compound più duro, usura, temperatura (curve da TyreModel) | +1,8 s |
| Push | Push 10 | curva logaritmica per 1..9, zero a 10 | +1,3 s |
| Skill Pilota | Driver top (vel 100, agr 85, consistenza 90) | sommatoria pesata degli scostamenti, con coupling su altri fattori (es. fuel) | +0,8 s |
| Mappe ICE | ICE Attack | riduzione potenza % * coeff, più cooldown penalty | +0,8 s |
| Mappe ERS | ERS Attack | saturazione deploy vs target, penalty su regen heavy | +0,7 s |
| Freni | Duct range, fade < threshold-50°C | penalty per duct errato, fade lieve/grave | +0,9 s |
| Assetto | Setup finestra circuito | penalità per ali/rake/sospensioni fuori range, separate drag/corner | +1,3 s |
| Circuit Extras | Setup adattato a grip/vento/bumpiness | mismatch vs param circuito | +0,3 s |
- Somma penalty saturata a +6 s per evitare distorsioni estreme.

## 6. Telemetria & UI
- Nuovo payload `penalty_breakdown` pubblicato via socket + registrato in `RaceCar.telemetry`.
- Garage V3: card "Penalty Stack" con contributi e suggerimenti (es. "Fuel 95 kg → +1,5 s vs baseline 10 kg").
- Log QA: CSV/JSON per ogni stint con penalty per giro + delta vs baseline.

## 7. Testing
1. **Unit test** per `compute_*_penalty` verificando baseline 0, scaling e limiti.
2. **Integration test** `test_penalty_stack` che esegue lap sweep (fuel ladder, compound switch, push slider) verificando monotonicità.
3. **Scenario test circuito**: caricare profili (es. Melbourne vs Baku) e confrontare penalty attese.

## 8. Stato Implementazione (Mar 2026)
### ✅ **Wave 1 - COMPLETATA**
- **Fuel**: Implementato e testato
  - `fuel_reference_kg = 10.0`, `fuel_penalty_coeff` da telemetria
  - Calcolo per sezione: `coeff * extra_fuel * (section_length / circuit_length)`
  - Test Yas Marina: 100kg = +3.5s/lap (realistico)
  - Telemetry in SessionBridge: `fuel_penalty_s` per sezione
  - Interfaccia % ↔ kg funzionante
- **Gomme**: Implementato (TyreModel integration)
  - `tyre_reference_compound` da penalty profile o fallback a telemetria nomination
  - `tyre_compound_deltas` e `tyre_wear_coeffs` per tutti i compound
  - Calcolo penalty solo su curve (n_curve_sections)
  - `pirelli_nomination` in penalty profile con hard/medium/soft per ogni GP
  - Test Silverstone: C3 vs C5 delta -1.1s, allineamento con baseline zero
- **Push**: Implementato (driver push penalty con skill modulation) ✅
  - Scala 1-10 con 10 = riferimento zero penalty
  - Range casuali con min 0.150s distanza tra livelli
  - Massimo 1.600s per push = 1, distribuito per settore
  - **Skill pilota integrate**: Modulazione skill pilota (qualifica/gara) con pesi diversi per Quali vs Race
  - Forbice basata su regolarità pilota (costanza)
  - **REGOLA SPECIALE**: Push 1 = penalty massima senza riduzione skill (1.600s)
  - Test Suzuka: push 10 = 87.153s, push 1 = 88.753s (+1.600s)
  - Esempi: Norris push=5 = 87.686s (Quali), push=1 = 88.753s (massima penalty)
- **Engine Penalty System**: Implementato e testato ✅
  - **CV-based penalties**: Mercedes reference (1008 CV), higher CV = penalty (not bonus)
  - **Circuit-specific coefficients**: Base 0.01 (20 CV = 0.2s), scaled by power_bias
    - High-speed (Monza): 0.012 (20 CV = 0.24s)
    - Medium-speed (Baku): 0.01 (20 CV = 0.2s)  
    - Low-speed (Monaco): 0.008 (20 CV = 0.16s)
  - **Engine map penalties**: QUALY=0.0s, RICH=0.12s, STANDARD=0.25s, ECONOMY=0.40s, WET=0.18s, RECHARGE=0.50s
  - **Straight-only application**: Applied only on STRAIGHT, MEDIUM_STRAIGHT, ULTRA_FAST_CORNER
  - **Integration**: Full integration with update_section() physics loop
  - **Test results**: 
    - McLaren Mercedes (1008 CV) + QUALY = 0.000s penalty (reference)
    - RBR Honda (1015 CV) + QUALY = +0.770s on Baku (11 straights)
    - RBR Honda (1015 CV) + STANDARD = +3.520s on Baku
  - **Files**: `engine_penalty.py`, updated `data_types.py`, `config_loader.py`, `update_section.py`
  - **Tests**: 7 unit tests + integration test, all passing

### 🔄 **Wave 1 - COMPLETATA**
- **Mappe ICE/ERS**: Implementato come parte dell'Engine Penalty System

### 📋 **Wave 2-4 - Pending**
- **Wave 2**: ✅ **COMPLETATA** - freni
- **Wave 3**: assetto setup + circuit extras + telemetria UI (skill pilota già integrate nel push system)
- **Wave 4**: refinements (bonus eventuali, toggle legacy)

### 📁 **File Modificati**
- `python_backend/lap_simulator/data_types.py` - Aggiunti campi fuel penalty, push_penalty params, push_level, engine_penalty_s, team_code e brake_penalty_s
- `python_backend/lap_simulator/config_loader.py` - Caricamento penalty profile, fallback nomination, engine penalty config e calcolo braking energy da HD telemetry
- `python_backend/lap_simulator/update_section.py` - Calcolo penalità fuel, gomme, push, engine e brake (con skill modulation)
- `python_backend/lap_simulator/push_penalty.py` - Nuovo modulo per calcolo penalità push
- `python_backend/lap_simulator/engine_penalty.py` - Nuovo modulo per calcolo penalità motore CV/mappe
- `python_backend/lap_simulator/brake_penalty.py` - Nuovo modulo per calcolo penalità freni duct/fade
- `python_backend/utils/session_bridge.py` - Telemetry fuel penalty
- `scripts/build_circuit_profiles.py` - Generazione penalty profile, pirelli_nomination e engine penalty parameters
- `config/circuits/derived/*/penalty_profile.json` - Profili penalità per circuito con engine penalty config
- `scripts/run_sim_teams.py`, `scripts/physics_validator.py` - Test con compound C3/C5, push level 10, engine e brake penalties
- `tests/test_driver_push_penalty.py` - Suite test per sistema push penalty
- `tests/test_engine_penalty.py` - Suite test per sistema engine penalty (7 test)
- `tests/test_brake_penalty.py` - Suite test per sistema brake penalty (12 test)
- `test_push_validation.py` - Script validazione per scenari realistici
- `test_engine_penalty_integration.py` - Script test integrazione engine penalty
- `test_mclaren_engine_penalty.py` - Script test McLaren reference
- `test_rbr_engine_penalty.py` - Script test RBR engine penalties
- `test_brake_penalty_integration.py` - Script test integrazione brake penalty
- `test_realistic_brake_penalty.py` - Script test scenari realistici brake penalty (CV + mappe ICE/ERS)

## 9. Roadmap Incrementale Aggiornata
1. **Wave 1**: ✅ **COMPLETATA** - fuel + gomme + push (con skill pilota integrate) + engine penalties (CV + mappe ICE/ERS)
2. **Wave 2**: ✅ **COMPLETATA** - brake penalties (duct + fade)
3. **Wave 3**: assetto setup + circuit extras + telemetria UI (skill pilota già integrate nel push system)
4. **Wave 4**: refinements (bonus eventuali, toggle legacy).

**Status Wave 1-2**: 100% completato con Engine e Brake Penalty Systems integrati e testati

## 10. Deliverable
- Specifica approvata (questo documento).
- Implementazione graduale con flag e test.
- Aggiornamento doc correlati (`degradation-and-consumption`, `TyreModel`, `EngineData2025`, `brake-integration`, `setup-ui-plan`).

## 11. Documenti di riferimento
- `docs/degradation-and-consumption.md`
- `docs/TyreModel.md`
- `docs/tyre-allocation.md`
- `docs/PIlotiSkill.json`
- `docs/team-refactor-spec.md`
- `docs/Engine-MGU-H.md`
- `docs/EngineData2025.md`
- `docs/ERS-Deployment-Strategy.md`
- `docs/setup-engine-spec-v0.1.md`
- `docs/brake-integration.md`
- `docs/brake-integration-gemini.md`
- `docs/brake-calibration-guide.md`
- `docs/ai-Setup-Search.md`
- `docs/ai-chip-progress-debug.md`
- `docs/ai-driver-engine-spec.md`
- `docs/setup-search-plan.md`
- `docs/setup-ui-plan.md`
- `python_backend/data/circuits/2025/*_Telemetry.json`
- `config/` (brake params, duct recommendation, circuit profiles)
