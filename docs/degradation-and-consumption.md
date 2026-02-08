---
title: Degradation & Consumption spec v0.1
last_updated: 2026-02-08
scope: tyres, brakes, fuel burn, power unit, mechanical damage
status: draft
---

## 1. Obiettivo
Fonte unica per regole di degrado/consumi usate da LapSimulator e dagli orchestratori (Practice/Race). Definisce parametri, segnali in ingresso/uscita e criteri di failure.

## 2. Perimetro
Copre:
- Pneumatici: termica, usura, failure modes (graining, flatspot, puncture risk).
- Freni: termica, fade, usura, feedback.
- Fuel: calcolo consumo per sezione/run e impatto peso.
- Power Unit (ICE/ERS): termica, derating, usura/failure.
- Danni meccanici da bump/kerb/contatti (sospensioni, fondo, cambio, sterzo).

Non copre:
- Logiche AI di run-plan e orchestrazione (rimando a ai-driver-engine-spec, practice-session-orchestrator).
- Allocazione set gomme (rimando a tyre-allocation.md).
- UI/HUD (solo effetti funzionali esposti ai moduli).

## 3. Output attesi
- Parametri/coeff base per ogni macro-area (tyre, brake, fuel, PU, damage).
- Segnali prodotti/consumati: stimoli LapSimulator ↔ orchestratori; flag di warning/failure.
- TODO di calibrazione: coefficienti numerici da validare (tyre temp windows, wear rates, fuel → tempo/giro, shock→danno).

## 4. Integrazione
- LapSimulator: legge parametri, genera stimoli (under/oversteer, bump/kerb, airflow_penalty) e consuma stati aggiornati.
- Practice/Race Orchestrator: usa grip/derating/failure per decisioni di rientro, pianificazione run e feedback engineer.
- BattleResolver: legge grip effettivo/derating per chance sorpasso/errore.

## 5. Struttura dettagliata (da compilare)
1) Tyres (termica, usura, failure, heat-cycle penalty)
2) Brakes (termica, fade, wear, feedback)
3) Fuel burn (per sezione/run, effetti peso)
4) Power Unit (ICE/ERS) termica/derating/usura/failure
5) Mechanical damage (sospensioni, fondo, cambio, sterzo)
6) Parametrizzazione & calibrazione

### 5.1 Tyres
**Input chiave**: `pace_factor`, `understeer_level`/`oversteer_level`, `handling_penalty`, `torque_ramp`, `airflow_penalty`, `bump_penalty`, `kerb_impact`/`kerb_severity`, brake bias/fade, skill (`aggression`, `smoothness`, `tyre_management`). Track modifiers da `config/pirelli_track_profile_2025.json` (bumpiness, kerbs, corner load) e setup bounds per circuito da `config/setup_mapping_v2.json` (influiscono su `ride_height`, `brake_duct`, quindi cooling e bump penalty).

**Termica** (coerente con lap-physics §5.2):
- `heat_gen = section.heat_factor * pace_factor * load_multiplier`
- Aggiunte: asse frontale moltiplica per `1 + understeer_level` + calore freni; asse posteriore moltiplica per `1 + oversteer_level` e `1 + torque_ramp*0.3`.
- Raffreddamento: `convective_cool = cooling_coeff * air_speed * (1 - airflow_penalty)`; scambio core/surface con `conduction_coeff`.

**Usura**:
- `wear_rate = tyre.wear_rate_base * pace_factor * bumpiness_factor`
- Moltiplicatori: `1 + bump_penalty + kerb_severity`, `1 + handling_penalty + fade_level*0.1`, `1 + (aggression-50)/150`, `1 - (smoothness-50)/200`, `1 - tyre_management/150`; posteriori `* (1 + torque_ramp*0.25)`.
- `wear_pct += wear_rate * load_duration` con `load_duration = section.length / max(v_entry,1)`.

**Grip effettivo**:
- `thermal_factor = gaussian(temp_surface + airflow_penalty*5, temp_window)`
- `wear_factor = max(0.5, 1 - wear_pct/100)`
- `effective_grip = base_grip * thermal_factor * wear_factor * setup_bonus` (setup_bonus da sospensioni/antiroll/ride height per asse).

**Failure & warning**:
- Overheat: `temp_surface > temp_window.max + Δ` → flag + feedback (gated da `tyre_management`).
- Puncture risk: `wear_pct > 80%` → `puncture_risk += pace_factor * 0.01`.
- Graining/flatspot: da `understeer_level`, `kerb_impact`, `brake_bias_factor` (ruota/asse selettiva).
- Heat-cycle penalty: applicare malus grip/warmup se set usato (rimando a `docs/tyre-allocation.md`).

**Parametrizzazione** (per compound S/M/H/Int/W):
- `temp_window` (min/opt/max), `base_grip`, `wear_rate_base`, `thermal_mass_surface/core`, `conduction_coeff`, `cooling_coeff`, `gaussian_sigma`, soglie warning/puncture. Le finestre termiche dettagliate restano in `TyreModel`.
- Track modifiers (da `pirelli_track_profile_2025.json`): bumpiness/kerb severity influenzano i moltiplicatori sopra; corner distribution può settare `section.heat_factor`/`bumpiness_factor`.
- Setup influence: aperture `brake_duct` e altezze da `setup_mapping_v2.json` modificano cooling e bump penalty (ride height troppo bassa → più `bump_penalty`/kerb impatti).

⚠️ Parametri critici da tabellare (mancanti): `gaussian_sigma` per compound, `heat_capacity` e `cooling_coeff` per freni/gomme, `fade_threshold`/`fade_sensitivity`, `wear_coeff` PU, `damage_thresholds` per componenti. Fino a calibrazione, usare fallback di sicurezza (es. sigma 7°C surface/6°C core, cooling_coeff 1.0 base) e loggare warning se un coeff mancante/illeggibile.

Nota: le finestre termiche ufficiali per compound (surface/core min-opt-max) sono definite in `docs/TyreModel.md` e devono essere usate dal calcolo grip in `lap-physics-spec-v0.5` (§5.2).

### 5.2 Brakes
**Input chiave**: energia frenata per sezione (`braking_energy`), brake bias (driver intent), apertura `brake_duct`, qualità impianto (`system_quality`), airflow_penalty, cooling_coeff; stimoli da pista (heavy_brake_events nel cluster) e setup per circuito (`setup_mapping_v2.json` per duct range).

**Termica** (lap-physics §5.1): calore generato da energia frenata ripartita (front/rear), ridotto da `heat_quality` (miglior impianto disperde meno calore) e dissipato da `duct_cooling = duct_opening * cooling_coeff * (1 - airflow_penalty)`. Temperature per asse aggiornate a ogni sezione.

**Usura / fade**: usura proporzionale a energia per asse e `wear_quality`; se `temp_front` supera soglia → `fade_level` cresce e riduce efficacia frenante + aumenta handling_penalty (sottosterzo ingresso). Influenza indiretta sulle gomme (fade entra nei moltiplicatori di usura).

**Feedback & warning**: se skill `setup_finding`/`tyre_management` è alta, genera messaggi (“Front brakes hot”, “Brake wear high”). Derating/cooling guidance per circuito può provenire da Pirelli track profile (weather_impact) e dal cluster (`heavy_brake_events`).

**Parametrizzazione**: soglie fade (`fade_threshold_front/rear`), sensitività (`fade_sensitivity`), `heat_capacity`, `thermal_mass`, curve qualità impianto (`system_quality`). Range duct per circuito da `config/setup/setup_mapping_v2.json`; requisiti climatici da `config/tyres/pirelli_track_profile_2025.json` (campo `weather_impact`).

### 5.3 Fuel
**Input chiave**: fuel_mix (Lean/Standard/Rich), `pace_factor`, massa carburante iniziale, intensità consumo circuito (`fuel_burn_intensity` da cluster/Pirelli), temperatura aria/pista.

**Consumo**: stima per sezione/run: `fuel_burn ≈ base_fuel_per_section * pace_factor * fuel_mix_coeff`, raffinata con `dt` e massa residua. Effetto peso: più fuel → peggio accelerazione/frenata e più calore su freni/gomme (coeff lineare da calibrare in LapSimulator).

**Feedback/strategie**: derating termico PU → forzare fuel_mix Lean; orchestratore usa consumo previsto per pianificare stint e rientri.

**Parametrizzazione**: tabella `fuel_mix_profiles.json` (coeff Lean/Std/Rich), curve peso→tempo/giro, `base_fuel_per_section` per circuito (derivabile da Telemetry), scalers da `pirelli_track_profile_2025.json` se presenti note su fuel burn.

### 5.4 Power Unit (ICE/ERS)
**Input chiave**: mappa motore/ERS (torque_ramp, heat_load, deployment style), cooling_capacity, airflow_penalty, driver intent (pace_factor, deploy mode), shock da kerb/bump.

**Termica**: calcolo da LapPhysics §4 (ICE/ERS heat in/out). Se `temp_ice_next > warning` → derating; sopra `critical` → forzare Economy o rischio failure.

**Usura/failure**: usura ICE proporzionale a power_ice_eff e coeff affidabilità; ERS con cicli carica/scarica e temp. Failure modes: overtemp, over-rev, shock da kerb/contatti.

**Output**: `derating_flag/factor`, `temp_ice/ers`, `wear_ice/ers`, eventuale `failure_event`. Orchestratori decidono se rientrare o cambiare mappa; BattleResolver legge derating per valutare sorpasso.

**Parametrizzazione**: `pu_maps.json` (heat_load, torque_ramp, deployment), `pu_reliability.json` (wear_coeff, temp thresholds), `cooling_capacity` per configurazioni radiatori/ducts; link ai profili Pirelli per guidance climatica.

### 5.5 Mechanical damage
**Input chiave**: stimoli da LapSimulator (bump_penalty, kerb_impact/kerb_severity, airflow_penalty), contatti (collision events), torque_ramp elevato (shock cambio), setup estremo (ride height basso su piste bump/kerb).

**Componenti target**:
- Sospensioni: accumulo danno → malus grip meccanico/risposta sterzo.
- Fondo/beam wing: danno → aumento drag e perdita downforce.
- Cambio: shock da coppia e kerb → rischio failure, shift imprecisi.
- Sterzo: danno → perdita precisione, aumento handling_penalty.

**Effetti**: malus progressivi (grip_mech_drop, drag_increase, shift_delay, steering_precision_loss), più rischio failure oltre soglie.

**Parametrizzazione**: coeff urti/kerb→shock, soglie danno per componente, curve di accumulo e recupero (se previsto), mapping piste bump/kerb da `config/tyres/pirelli_track_profile_2025.json`. Setup influence: ride height e sospensioni da `config/setup/setup_mapping_v2.json` modulano esposizione a bump/kerb.

### 6. Performance & fallback
- L’aggiornamento avviene per sezione per ogni auto; per 20 auto usare batching/vectorization dove possibile e limitare valutazioni di eventi rari (collisione, failure) a step più larghi se non necessari al frame-rate.
- Se un coefficiente o JSON è mancante/illeggibile, applicare default conservativi e loggare warning (no crash):
  - Tyres: sigma 7°C surface / 6°C core, cooling_coeff 1.0, wear_rate_base fallback 0.15.
  - Brakes: fade_threshold_front/rear 850/750°C, fade_sensitivity 15°C, heat_capacity 1.0 base.
  - PU: derating a warning 130°C ICE/90°C ERS, critical +10°C, wear_coeff minimo.
  - Damage: shock_threshold medio e malus ridotti.
Annotare i default in config quando saranno definiti; rimuovere i fallback appena i parametri sono tabellati.

### 7. Flusso "derived per circuito" (offline)
- Input: `*_global_default.json` (tyres/brakes/PU/damage), profilo circuito raw (telemetria) in `python_backend/data/circuits/`, setup bounds per circuito (`config/setup/setup_mapping_v2.json`).
- Nota: il contesto Pirelli è già consolidato dentro `config/setup/setup_mapping_v2.json` (campo `pirelli_context`), quindi lo script non legge direttamente `config/tyres/pirelli_track_profile_2025.json`.
- Processo offline (script `scripts/build_circuit_profiles.py`): combina global default + raw circuito + setup bounds → produce i profili derivati per circuito.
- Output: `config/circuits/derived/<circuit_id>/` con i 4 JSON combinati usati a runtime. Runtime carica solo i derivati (niente calcolo on-the-fly); rigenerare se cambiano global_default o profilo raw.

### 7. Config JSON da produrre (fase analisi)
- `config/tyres/tyre_params_global_default.json` — per compound S/M/H/Int/W: `temp_window`, `gaussian_sigma_surface/core`, `base_grip`, `wear_rate_base`, `thermal_mass_surface/core`, `conduction_coeff`, `cooling_coeff`.
- `config/brakes/brake_params.json` — per classe impianto: `heat_capacity`, `thermal_mass`, `fade_threshold_front/rear`, `fade_sensitivity`, `heat_quality` curve.
- `config/pu/pu_maps.json` — mappe ICE/ERS: `heat_load`, `torque_ramp`, `deployment_style`, `cooling_share`.
- `config/pu/pu_reliability.json` — `wear_coeff` per ICE/ERS, soglie `temp_warning/critical`, fattori over-rev/shock.
- `config/damage/damage_coeffs.json` — `shock_thresholds`, malus per componente (sospensioni, fondo/beam, cambio, sterzo), fattori pista bump/kerb.
- `config/circuits/derived/<circuit_id>/` — profili combinati per circuito (tyres/brakes/PU/damage) generati dallo script offline.

Nota: i valori seed possono provenire da `docs/TyreModel.md`, profili Pirelli (`config/tyres/pirelli_track_profile_2025.json`), telemetria FastF1 (per heat/cool), e fitting dei componenti (fase D, scripts `*_fit`).
