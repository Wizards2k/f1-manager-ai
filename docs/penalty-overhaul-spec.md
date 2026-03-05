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

### 🔄 **Wave 1 - In Progress**
- **Push**: Da implementare (push level scaling)
- **Mappe ICE/ERS**: Da implementare (engine map penalties)

### 📋 **Wave 2-4 - Pending**
- **Wave 2**: freni + assetto
- **Wave 3**: skill pilota + circuit extras + telemetria UI
- **Wave 4**: refinements (bonus eventuali, toggle legacy)

### 📁 **File Modificati**
- `python_backend/lap_simulator/data_types.py` - Aggiunti campi fuel penalty
- `python_backend/lap_simulator/config_loader.py` - Caricamento penalty profile e fallback nomination
- `python_backend/lap_simulator/update_section.py` - Calcolo penalità fuel e gomme
- `python_backend/utils/session_bridge.py` - Telemetry fuel penalty
- `scripts/build_circuit_profiles.py` - Generazione penalty profile con pirelli_nomination
- `config/circuits/derived/*/penalty_profile.json` - Profili penalità per circuito
- `scripts/run_sim_teams.py`, `scripts/physics_validator.py` - Test con compound C3/C5

## 9. Roadmap Incrementale Originale
1. **Wave 1**: fuel + gomme + push + mappe ICE/ERS (dati già strutturati).
2. **Wave 2**: freni + assetto (richiede affinamento doc setup/brake).
3. **Wave 3**: skill pilota + circuit extras + telemetria UI.
4. **Wave 4**: refinements (bonus eventuali, toggle legacy).

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
