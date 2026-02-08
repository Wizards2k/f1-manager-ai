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
- `temp_window` (min/opt/max), `base_grip`, `wear_rate_base`, `thermal_mass_surface/core`, `conduction_coeff`, `cooling_coeff`, `gaussian_sigma`, soglie warning/puncture.
- Track modifiers (da `pirelli_track_profile_2025.json`): bumpiness/kerb severity influenzano i moltiplicatori sopra; corner distribution può settare `section.heat_factor`/`bumpiness_factor`.
- Setup influence: aperture `brake_duct` e altezze da `setup_mapping_v2.json` modificano cooling e bump penalty (ride height troppo bassa → più `bump_penalty`/kerb impatti).
