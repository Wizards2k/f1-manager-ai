---
title: AeroPackage – component model & formulas
last_updated: 2026-02-08
status: draft
scope: component-level aero (DF/drag/cooling), setup coupling, integration in LapSimulator
---

## 1. Obiettivo
Documentare l’AeroPackage usato da LapSimulator e Setup Engine: componenti, formule DF/drag/cooling, coupling con sospensioni/ride height e segnali prodotti per TyreModel e BattleResolver.

## 2. Componenti e input
- **Front Wing / Rear Wing / Beam Wing**: base_downforce, base_drag, angle_sensitivity, drag_sensitivity, profile_curve, damage_factor.
- **Front/Rear Floor, Sidepods, Engine Cover, B-Wing**: contributi DF/drag, cooling (sidepods/engine cover), profili opzionali (standard/high_load/low_drag/rain).
- **Ride Height F/R**: range circuito; influenza DF effettiva e rischio bottoming.
- **Suspension Front/Rear**: rigidity, efficiency, df_bonus, skill; modula DF effettiva e bump penalty.
- **Antiroll Front/Rear**: rigidità; influisce su handling penalty.
- **Setup bounds**: da `config/setup/setup_mapping_v2.json` (range angoli ali, ride height, rake, sospensioni, antiroll).
- **Damage flags**: riducono df_contribution e aumentano drag se presente.

## 3. Formule chiave (sintesi)
### 3.1 Contributo ali (esempio Front Wing)
```
dyn_pressure = 0.5 * air_density * v^2
angle_term = 1 + angle_sensitivity * (angle - angle_ref)
profile_term = profile_curve.get(active_profile, 1.0)
df_front_wing = base_downforce * dyn_pressure * angle_term * profile_term * damage_factor
drag_front_wing = base_drag * angle_term * profile_term * damage_factor
cooling_penalty = max(0, angle - cutoff_angle) * cooling_penalty_coeff
```
Analoghe formule per Rear Wing/Beam Wing con parametri specifici e opzionale DRS (`drag *= (1 - drs_gain)`).

### 3.2 Aggregati AeroPackage (`compute_forces`)
1) **DF per asse**: somma ali + floor + sidepods + engine cover (+ beam wing) separando fronte/retro.
2) **Sospensioni**: moltiplicatori da efficiency/skill (`clamp 0.8-1.2`) e `df_bonus`.
3) **Ride height / rake**: penalità proporzionale a distanza dall’ottimale sezione (`max(0.7, 1 - rh_pen)`).
4) **Bump/kerb**: `bump_penalty` da `section.bumpiness_factor` e rigidità sospensioni; `kerb_impact` se aggressione alta.
5) **Drag effettivo**: `drag_total` corretto per densità aria, slipstream, airflow_penalty (wake). Cooling capacity ridotta da wake.
6) **Cooling margin**: `cooling_capacity = sidepods.cooling + engine_cover.cooling`; confronto con `power_unit.cooling_demand` → derating se negativo.
7) **Aero balance & handling penalty**: `aero_balance = df_front_eff / (df_front_eff + df_rear_eff)`; `handling_penalty = abs(balance_error) * k_handling` mitigato da skill pilota.
8) **Under/oversteer signals**: se |balance_error| > soglia → `understeer_level`/`oversteer_level` per TyreModel (temperatura/usura asse).

## 4. Output verso altri moduli
- `df_front_eff`, `df_rear_eff`, `drag_eff`, `cooling_margin`, `handling_penalty`, `understeer_level/oversteer_level`, `bump_penalty`, `kerb_impact/kerb_severity`.
- Inviati a TyreModel (termica/usura), PowerUnit (derating), BattleResolver (grip effettivo).

## 5. Setup Engine coupling
- Conversioni slider → fisico in `docs/setup-engine-spec-v0.1.md` (§3.2) e bounds per circuito in `config/setup/setup_mapping_v2.json`.
- UI mostra `aero_balance`, drag index, cooling guidance; valida rake e delta sospensioni per circuito.

## 6. Riferimenti
- `docs/lap-physics-spec-v0.5.md` (§3.1–3.4) per formule dettagliate e pseudocodice `compute_forces`.
- `docs/setup-engine-spec-v0.1.md` (§3.2 AeroPackage – formule e range) per mapping slider.
- Config seed/danni: `config/damage/damage_coeffs_global_default.json` per effetti damage; `config/tyres/pirelli_track_profile_2025.json` e `config/setup/setup_mapping_v2.json` per contesto circuito.
