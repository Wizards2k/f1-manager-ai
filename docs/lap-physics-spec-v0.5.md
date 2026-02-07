title: Motore fisico lap time – v0.5 (Auto/Aero/PowerUnit/Tyre/Driver/Battle)
version: 0.5
last_updated: 2026-02-07
scope: "Definizione del modello fisico per il contributo Auto (aerodinamica, Power Unit, TyreModel e DriverModel) al tempo sul giro"
---

## 1. Obiettivo
Stabilire le regole del motore fisico per calcolare il tempo sul giro utilizzando componenti realistici dell’auto (solo sezione aerodinamica al momento). Il documento descrive come mappare i valori 1–100 delle parti dell’auto in downforce (DF) e drag, e come questi incidono sui segmenti del tracciato senza impostazioni manuali per curva.

## 2. Dati disponibili
- **Telemetria 2025** (`*_2025_Q.json`): velocità e distanza lungo il giro, usate per calcolare velocità di riferimento per ogni sezione.
- **Mapping circuito** (`*_mapping.json`): lista `sections[]` con tipo (`Straight`, `SlowCorner`, `FastCorner`, ecc.), start/end metri e attributi legacy.
- **RaceCar attuale**: possiede hook per gomme, pilota, setup; verrà estesa con il nuovo profilo aerodinamico.

## 3. Componenti Auto (valori 1–100)
| Componente        | Parametri                          | Note |
|-------------------|------------------------------------|------|
| Ala anteriore     | `downforce`, `drag`, `angle`       | L’angolo modifica direttamente DF/drag.
| Ala posteriore    | `downforce`, `drag`, `angle`       | Drag naturalmente più alto.
| Sidepods          | `downforce`, `drag`, `cooling`     | Contribuisce a entrambi gli assi (50/50) e fornisce raffreddamento.
| Fondo anteriore   | `downforce`, `drag`                | DF concentrato sull’anteriore.
| Fondo posteriore  | `downforce`, `drag`                | DF per il posteriore.
| Cofano motore     | `downforce`, `drag`, `cooling`     | Influenza aerodinamica del retrotreno e il raffreddamento.
| B-Wing            | `downforce`, `drag`                | Mini ala posteriore aggiuntiva.
| Sospensione ant.  | `efficiency`, `df_bonus`, `rigidity` | Efficienza gestisce bump/kerb, `df_bonus` aggiunge grip meccanico, rigidità controlla trasferimento carico.
| Sospensione post. | `efficiency`, `df_bonus`, `rigidity` | Stessa logica per l’asse posteriore.
| Ride height ant.  | `height_value` (1-100)              | Valore alto = assetto più alto (protezione bump), basso = più carico ma rischio bottoming.
| Ride height post. | `height_value` (1-100)              | Come sopra per retrotreno.
| Antiroll bar ant. | `skill`, `rigidity` (1-100)         | `skill` rappresenta qualità dell’elemento, `rigidity` regola morbidezza 1 (soft) → 100 (hard).
| Antiroll bar post.| `skill`, `rigidity` (1-100)         | Stessa logica per l’asse posteriore (stabilità uscita curva / sovrasterzo).
| Power Unit        | vedi §7.1 (ICE + ERS)               | Componente fisico con sottoblocchi ICEUnit/ERSUnit e mappe dedicate.

> **Nota:** il blocco `Mechanical grip` viene trattato come sottosistema dedicato (vedi roadmap §7.2) che aggrega sospensioni, ride height e antiroll per modulare il grip alle basse velocità.

> **TyreModel (rimando)**: le regole termiche e di usura per ogni ruota sono definite nel documento `docs/TyreModel.md`. Ogni `TyreState` mantiene `surface_temp`, `core_temp`, `wear_pct`, flag `graining/blistering` e produce un output semplificato per l'UI (surface/core temp, wear%, stato finestra). La classe `TyreModel` aggiorna le quattro ruote in base al tipo di sezione (heat/cool factors) e ai dati Pirelli 2025 (nomination, `lap_time_delta_hint`, `wear_rate_base`).

### Diagramma `TyreModel` / `TyreState` (per ruota)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TYREMODEL (per vettura)                                │
├─────────────────────────────────────────────────────────────────────────┤
│  TYRESET (collezione 4 ruote)                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  TyreState  │  │  TyreState  │  │  TyreState  │  │  TyreState  │     │
│  │     LF      │  │     RF      │  │     LR      │  │     RR      │     │
│  │ (LeftFront) │  │ (RightFront)│  │ (LeftRear)  │  │ (RightRear) │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │                │            │
│         └────────────────┴────────────────┴────────────────┘            │
│                              ↓ update_section()                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         TYRESTATE (singola ruota)                  │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ IDENTITÀ                                                        │   │
│  │ • compound (C1-C6/INT/WET) • pirelli_label (Soft/Medium/Hard)    │   │
│  │ • wheel_position (LF/RF/LR/RR) • stint_id                        │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ TERMICA                                                        │   │
│  │ ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │   │
│  │ │surface_temp │  │  core_temp  │  │    temp_window          │ │   │
│  │ │  (reactive) │  │  (inertial) │  │  (surface/core min/max) │ │   │
│  │ └─────────────┘  └─────────────┘  └─────────────────────────┘ │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ USURA & HEALTH                                                  │   │
│  │ • wear_pct (0-100%) • wear_rate_base/dynamic                   │   │
│  │ ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │   │
│  │ │  graining   │  │  blistering │  │    overheat/cold        │ │   │
│  │ │   (bool)    │  │   (bool)    │  │     warnings            │ │   │
│  │ └─────────────┘  └─────────────┘  └─────────────────────────┘ │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ OUTPUT UTENTE (semplificato)                                    │   │
│  │ → surface_temp + status (COLD/IN/HOT)                          │   │
│  │ → core_temp + status (COLD/IN/HOT)                             │   │
│  │ → wear_pct (0-100%) • graining SI/NO • blistering SI/NO          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

## 3.1 Classe `Car` (struttura e responsabilità)

### Identità e dati generali
- `car_id`, `team_ref`, `season`, `project_code`.
- Dati geometrici: `base_mass`, `fuel_mass_current`, `wheelbase`, `track_width_front/rear`, `cg_position`, `cp_position`.

### Componenti fisici
Ogni componente dell’elenco precedente è rappresentato da un oggetto dedicato (`FrontWing`, `RearWing`, `Sidepods`, `FrontFloor`, `RearFloor`, `EngineCover`, `BWing`, `SuspensionFront`, `SuspensionRear`, `RideHeightFront`, `RideHeightRear`, `AntirollFront`, `AntirollRear`, `PowerUnit`, `BrakeSystem`). I valori 1‑100 vengono convertiti in attributi fisici (`downforce`, `drag`, `cooling`, `efficiency`, `rigidity`, ecc.).

Nel codice la `Car` mantiene un registro `aero_components: Dict[str, AeroComponent]` che contiene tutte le istanze attive (es. `front_wing`, `rear_wing`, `front_floor`, `rear_floor`, `sidepods`, `engine_cover`, `beam_wing`). Ogni elemento deriva dall’archetipo seguente e viene aggiornato da `recalculate_aero()` prima di calcolare il Passo 3.

> **Setup Engine 2.0**: la gestione completa dei valori di setup lato UI, scoring e mapping slider→parametri fisici è documentata in `docs/setup-engine-spec-v0.1.md`. Questo documento si concentra sugli effetti fisici; ogni riferimento a slider/setup assume che le conversioni siano gestite dal Setup Engine.

#### 3.1.1 Archetipo `AeroComponent`
Per standardizzare il Punto 2 definiamo un archetipo comune usato da tutti i componenti aerodinamici.

- `component_name` (es. "FW-24 Alpha")
- `version_id` (incrementale, es. FW24-V3)
- `introduced_at` (data/pacchetto aero in cui il pezzo è stato omologato)
- `base_downforce` (N @ 200 km/h)
- `base_drag`
- `angle` (°) – input setup 0‑25
- `angle_sensitivity` (ΔDF/Δ°)
- `drag_sensitivity` (Δdrag/Δ°)
- `profile_curve` – moltiplicatori per profili (high-load, low-drag, rain)
- `damage_factor` (0‑1) – riduzione se l’elemento è danneggiato
- `coupling`: percentuali che influenzano cooling o bilanciamento (es. `cooling_penalty_coeff`)

```python
class AeroComponent:
    def compute_downforce(self, airspeed):
        dyn_pressure = 0.5 * air_density * (airspeed**2)
        angle_term = 1 + angle_sensitivity * (self.angle - angle_ref)
        profile_term = profile_curve.get(active_profile, 1.0)
        return base_downforce * dyn_pressure * angle_term * profile_term * damage_factor

    def compute_drag(self, airspeed):
        angle_term = 1 + drag_sensitivity * (self.angle - angle_ref)
        return base_drag * angle_term * profile_term * damage_factor

    def cooling_penalty(self):
        if self.angle > cutoff_angle:
            return cooling_penalty_coeff * (self.angle - cutoff_angle)
        return 0
```

Gli output `df_contribution`, `drag_contribution`, `cooling_penalty` alimentano l’AeroPackage (Passo 3).

##### Front Wing (istanza)
- `component_name = "FW-24 Alpha"`
- `version_id = "FW24-V1"`
- `introduced_at = GP Monza 2025`
- `base_downforce = 1200 N`
- `base_drag = 95 N`
- `angle_sensitivity = 0.018/°`
- `drag_sensitivity = 0.012/°`
- `profile_curve`: {`standard`:1.0, `high_load`:1.08, `low_drag`:0.92}
- `cooling_penalty_coeff = 0.015` (ostruzione brake ducts)
- `cutoff_angle = 20°`
- `damage_factor` derivato da `damage_flags['front_wing']`

Formule specifiche:
```python
df_front_wing = base_downforce * dyn_pressure * (1 + 0.018 * (angle-15)) * profile_term * damage_factor
drag_front_wing = base_drag * (1 + 0.012 * (angle-15)) * profile_term * damage_factor
cooling_penalty = max(0, angle-20) * 0.015
```
Questo contributo va in `df_front` / `drag_total` e il `cooling_penalty` riduce la capacità dei sidepods.

##### Rear Wing (istanza)
- `component_name = "RW-24 Delta"`
- `version_id = "RW24-V2"`
- `introduced_at = GP Silverstone 2025`
- `base_downforce = 2100 N`
- `base_drag = 160 N`
- `angle_sensitivity = 0.022/°`
- `drag_sensitivity = 0.018/°`
- `profile_curve`: {`standard`:1.0, `high_load`:1.12, `low_drag`:0.88, `rain`:1.05}
- `damage_factor = damage_flags['rear_wing']`
- `coupling`: `drs_gain = 0.25`, `aero_balance_weight = 0.6`

```
df_rear_wing = base_downforce * dyn_pressure * (1 + 0.022 * (angle-12)) * profile_term * damage_factor
drag_rear_wing = base_drag * (1 + 0.018 * (angle-12)) * profile_term * damage_factor
if DRS_active:
    drag_rear_wing *= (1 - drs_gain)
```
Il suo contributo guida `df_rear`, il drag totale e le chance di DRS in Passo 6.

##### Beam Wing (istanza)
- `component_name = "BW-24 Echo"`
- `version_id = "BW24-V1"`
- `introduced_at = GP Singapore 2025`
- `base_downforce = 600 N`
- `base_drag = 40 N`
- `angle_sensitivity = 0.015/°`
- `drag_sensitivity = 0.010/°`
- `profile_curve`: {`standard`:1.0, `high_rake`:1.10}
- `coupling`: `diffuser_boost = 0.05` (moltiplica il rear floor), `engine_cover_flow = 0.03`

```
df_beam_wing = base_downforce * dyn_pressure * (1 + 0.015 * (angle-8)) * profile_term * damage_factor
rear_floor.df_bonus += df_beam_wing * diffuser_boost
```

##### Front Floor (istanza)
- `component_name = "FF-24 Delta"`
- `version_id = "FF24-V2"`
- `introduced_at = GP Suzuka 2025`
- `base_downforce = 1800 N`
- `base_drag = 35 N`
- `angle_sensitivity = 0.0` (driver = ride height)
- `rake_sensitivity = 0.02 / mm`
- `porpoising_threshold = 42 mm`
- `porpoising_coeff = 0.015`
- `damage_factor = damage_flags['front_floor']`

```
rh_eff = ride_height_front - susp_compliance_front * df_front
rh_term = clamp(1 + rake_sensitivity * (ride_height_opt_front - rh_eff), 0.6, 1.2)
porpoising = max(0, porpoising_threshold - rh_eff) * porpoising_coeff
df_front_floor = base_downforce * dyn_pressure * rh_term * (1 - porpoising) * damage_factor
drag_front_floor = base_drag * (1 + 0.002 * (rh_eff - ride_height_opt_front))
```

##### Rear Floor / Diffuser (istanza)
- `component_name = "RF-24 Sigma"`
- `version_id = "RF24-V3"`
- `introduced_at = GP Austin 2025`
- `base_downforce = 2400 N`
- `base_drag = 50 N`
- `rake_sensitivity = 0.028 / mm` (usa ride_height_rear)
- `stall_threshold = 55 mm`
- `stall_drop = 0.25` (riduzione DF se stall)
- `diffuser_coupling = beam_wing.df_contribution * 0.05`
- `damage_factor = damage_flags['rear_floor']`

```
rh_eff_rear = ride_height_rear - susp_compliance_rear * df_rear
rh_term = clamp(1 + rake_sensitivity * (ride_height_opt_rear - rh_eff_rear), 0.5, 1.3)
stall = 1 - (rh_eff_rear > stall_threshold) * stall_drop
df_rear_floor = base_downforce * dyn_pressure * rh_term * stall * (1 + diffuser_coupling) * damage_factor
```

##### Sidepods (istanza)
- `component_name = "SP-24 Gamma"`
- `version_id = "SP24-V1"`
- `introduced_at = GP Miami 2025`
- `base_downforce = 400 N`
- `base_drag = 60 N`
- `cooling_capacity_base = 1.0`
- `cooling_slider` (setup 0-1) → `cooling_gain = 0.03`, `df_penalty = 0.01`, `drag_penalty = 0.015`
- `damage_factor = damage_flags['sidepods']`

```
cooling_mult = 1 + cooling_slider * cooling_gain
df_sidepods = base_downforce * dyn_pressure * (1 - cooling_slider * df_penalty) * damage_factor
drag_sidepods = base_drag * (1 + cooling_slider * drag_penalty)
cooling_capacity_contrib = cooling_capacity_base * cooling_mult
```

##### Engine Cover (istanza)
- `component_name = "EC-24 Beta"`
- `version_id = "EC24-V1"`
- `introduced_at = GP Baku 2025`
- `base_downforce = 250 N`
- `base_drag = 45 N`
- `cooling_slider` (0-1) → `cooling_gain = 0.02`, `drag_penalty = 0.01`
- `diffuser_flow_coeff = 0.04` (moltiplica il rear floor se slider basso)
- `damage_factor = damage_flags['engine_cover']`

```
cooling_mult = 1 + cooling_slider * 0.02
df_engine_cover = base_downforce * dyn_pressure * (1 - cooling_slider * 0.005) * damage_factor
drag_engine_cover = base_drag * (1 + cooling_slider * 0.01)
cooling_capacity_contrib = cooling_base * cooling_mult
rear_floor.df_bonus += clamp(0.04 - cooling_slider * diffuser_flow_coeff, 0, 0.04)
```

Queste istanze completano il Punto 2: ogni componente aero deriva dallo stesso archetipo e fornisce contributi coerenti a `Car.update_section()`.

#### BrakeSystem
- `disc_material_front/rear` (1‑100): capacità termica e risposta.
- `duct_opening` (0‑1): apertura condotti, influenza `cooling_capacity` (più aperti = più raffreddamento ma più drag).
- `bias_range` (es. 0.53–0.60): limiti hardware del bilanciamento frenata disponibili nel pannello setup per circuito.
- `wear_rate_base_front/rear`: consumo pad/dischi per kg di energia dissipata.
- `fade_threshold_front/rear`: temperatura oltre la quale `fade_level` cresce e l’efficacia frenante cala.
- `cooling_share_front/rear`: quanto del flusso d’aria (duct_opening) è dedicato ai freni.
- `system_quality` (1‑100): bontà complessiva dell’impianto (risposta lineare, modulabilità).

> **Setup note**: il pannello setup mostrerà `brake bias` entro `bias_range` consigliata dal circuito; `duct_opening` verrà esposto come slider “Brake cooling” collegato a un indicatore “Cooling vs Drag”.

### Sottosistemi collegati
- `TyreSet` (quattro TyreState, vedi TyreModel v0.2).
- `AeroPackage`: calcola aggregati (`df_front/rear`, `drag_total`, `aero_balance`, `cooling_capacity`, moltiplicatori sospensioni/antiroll, penalità ride height).
- `MechanicalGrip`: blocco telaio per grip meccanico/curve lente (roadmap §7.2).
- `DriverModel`: gestisce skill, stile guida, stato mentale e interazione con setup (§3.2).

### Metodi principali
1. `recalculate_aero()` → invoca `AeroPackage` per aggiornare forze DF/drag e derivati.
2. `update_section(section_ctx, env_ctx)` → orchestrazione per ogni sezione:
   1. `driver_inputs = driver_model.compute_inputs(...)`
   2. `aero_forces = aero_package.compute_forces(section_ctx, driver_inputs)`
   3. `power_output = power_unit.generate_output(section_ctx, driver_inputs, cooling_margin)`
   4. `tyre_set.update(section_ctx, aero_forces, power_output, driver_inputs, env_ctx)`
   5. Integrate velocità/tempo/fuel/ERS e registrare telemetria.
3. `apply_setup_change(component, value)` → aggiorna il componente e richiama `recalculate_aero()`.
4. `reset_for_session(session_type, fuel_load)`.
5. `car_state_snapshot()` → DTO per UI/telemetria.

### Diagramma classe `Car`

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CAR (Classe Principale)                        │
├─────────────────────────────────────────────────────────────────────────┤
│  IDENTITÀ                                                               │
│  • car_id, team_ref, season, project_code                               │
│  • base_mass, fuel_mass_current, wheelbase                              │
│  • track_width_front/rear, cg_position, cp_position                     │
├─────────────────────────────────────────────────────────────────────────┤
│  COMPONENTI FISICI (valori 1-100)                                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │ FrontWing   │ │ RearWing    │ │ Sidepods    │ │ FrontFloor  │       │
│  │ downforce   │ │ downforce   │ │ downforce   │ │ downforce   │       │
│  │ drag        │ │ drag        │ │ drag        │ │ drag        │       │
│  │ angle       │ │ angle       │ │ cooling     │ │             │       │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │ RearFloor   │ │ EngineCover │ │ BWing       │ │ Suspension  │       │
│  │ downforce   │ │ downforce   │ │ downforce   │ │ Front/Rear  │       │
│  │ drag        │ │ drag        │ │ drag        │ │ efficiency  │       │
│  │             │ │ cooling     │ │             │ │ df_bonus    │       │
│  └─────────────┘ └─────────────┘ └─────────────┘ │ rigidity    │       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ └─────────────┘       │
│  │ RideHeight  │ │ Antiroll    │ │ PowerUnit   │ ┌─────────────┐       │
│  │ Front/Rear  │ │ Front/Rear  │ │ ICE + ERS   │ │ Mechanical  │       │
│  │ height_value│ │ skill       │ │             │ │ Grip        │       │
│  │             │ │ rigidity    │ │             │ │             │       │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │
├─────────────────────────────────────────────────────────────────────────┤
│  SOTTOSISTEMI COLLEGATI                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐           │
│  │ TyreSet         │  │ AeroPackage     │  │ DriverModel     │           │
│  │ 4 TyreState     │  │ (aggregati DF)  │  │ (skill/stile)   │           │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘           │
├─────────────────────────────────────────────────────────────────────────┤
│  STATO DINAMICO                                                         │
│  • current_speed, current_gear, fuel_level, ers_state                   │
│  • damage_state, active_engine_map, active_ers_mode                     │
│  • cooling_margin, handling_penalty                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  METODI CHIAVE                                                          │
│  recalculate_aero()     apply_setup_change()    reset_for_session()   │
│  update_section()        car_state_snapshot()                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3.2 Classe `DriverModel` / Pilota

### Dati anagrafici (UI/Persistenza)
- `driver_id`, `name`, `surname`, `nationality`, `age`, `race_number` (1-99).
- `team_ref`, `experience_level` (rookie → veteran).
- Campi calcolati: `full_name`, `initials`, `abbreviation` (3 chars).

### Statistiche carriera (valutazione long-term)
- `career_gp_entered`, `career_gp_wins`, `career_points_season`, `career_points_total`.
- `championships_won`, `pole_positions`, `fastest_laps`, `current_season_points`.

### Skill base (valori 1-100, clampati)
- `raw_pace`: velocità pura.
- `qualifying_skill`: velocità in Q, **vincolata ±10 punti da raw_pace**.
- `race_craft`: gestione gara.
- `consistency`: costanza tempi settore.
- `tyre_management`: preservazione gomme.
- `wet_weather_skill`: performance in pioggia.
- `overtaking_skill`: manovre di sorpasso specifiche.
- `setup_finding`: capacità di trovare assetto ottimale, fondamentale per feedback all'ingegnere.
- `fuel_management`: skill fuel saving per strategie.

### Stile di guida (parametri comportamentali)
- `aggression` (1-100): intensità frenate, rischi in sorpassi.
- `smoothness` (1-100): modulazione throttle curva per curva.
- `oversteer_preference` (1-100): tolleranza setup posteriore mobile.
- `understeer_preference` (1-100): tolleranza setup anteriore pungente.
- `ers_management_style`: conservative / aggressive / balanced.

### Stato mentale dinamico (evolve durante gara)
- `confidence`: varia con performance recenti.
- `fatigue`: accumulo fisico con stint lunghi.
- `pressure_level`: situazioni critiche (bandiere, traffico, ultimi giri).
- `mistakes_probability`: derivata da pressure + fatigue + condizioni.

### Metodi principali
1. `compute_inputs(section_ctx, car_state, tyre_set, env_ctx)` → Restituisce intenti: `target_speed`, `brake_points`, `throttle_style`, `ers_deploy_decision`, `tyre_protection_mode`.
2. `apply_driver_bonus(aero_balance_error, handling_penalty)` → Riduce penalty se pilota bravo compensa setup.
3. `calculate_lap_variance()` → Varianza tempi settore da `consistency` + `pressure_level`.
4. `adapt_to_conditions(weather, track_evolution, traffic)` → Aggiusta aggressione e target in base a condizioni.
5. `update_mental_state(lap_outcome, race_context)` → Modifica confidence/fatigue/pressure in real-time.
6. `provide_setup_feedback(current_setup, car_balance)` → Usa `setup_finding` per suggerimenti assetto.

### Diagramma classe `DriverModel`

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      DRIVERMODEL / PILOTA                               │
├─────────────────────────────────────────────────────────────────────────┤
│  DATI ANAGRAFICI                                                        │
│  • driver_id, name, surname, nationality, age                           │
│  • race_number (1-99), team_ref, experience_level                       │
│  • full_name, initials, abbreviation (3 chars)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  STATISTICHE CARRIERA                                                    │
│  • career_gp_entered, career_gp_wins, career_points_season/total        │
│  • championships_won, pole_positions, fastest_laps                    │
│  • current_season_points                                                │
├─────────────────────────────────────────────────────────────────────────┤
│  SKILL BASE (1-100, clamped)                                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ raw_pace        │  │ qualifying_skill│  │ race_craft      │         │
│  │ (velocità pura) │  │ (vincolata ±10) │  │ (gestione gara) │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ consistency     │  │ tyre_management │  │ wet_weather     │         │
│  │ (costanza)      │  │ (preserva gomme)│  │ (pioggia)       │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ overtaking_skill│  │ setup_finding   │  │ fuel_management │         │
│  │ (sorpassi)      │  │ (ricerca assetto│  │ (fuel saving)   │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
├─────────────────────────────────────────────────────────────────────────┤
│  STILE DI GUIDA                                                         │
│  • aggression (1-100)    • smoothness (1-100)                           │
│  • oversteer_preference • understeer_preference                       │
│  • ers_management_style (conservative/aggressive/balanced)            │
├─────────────────────────────────────────────────────────────────────────┤
│  STATO MENTALE DINAMICO                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌──────────┐│
│  │   confidence    │  │    fatigue      │  │ pressure_level  │  │mistakes_ ││
│  │  (performance)  │  │ (stint lunghi)  │  │  (situazioni    │  │probability│
│  │                 │  │                 │  │   critiche)     │  │          ││
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └──────────┘│
├─────────────────────────────────────────────────────────────────────────┤
│  METODI CHIAVE                                                          │
│  compute_inputs()      calculate_lap_variance()   update_mental_state()   │
│  apply_driver_bonus()  adapt_to_conditions()    provide_setup_feedback()│
└─────────────────────────────────────────────────────────────────────────┘
```

### Interazione con la simulazione
- Il `DriverModel` fornisce "intenti" (target_speed, stile guida) che la `Car` applica nel loop sezione-per-sezione.
- Skill influenzano: slip ammesso, carico gomme, scelta mappa ERS, decisioni strategia.
- Vincolo `qualifying_skill` ±10 da `raw_pace` garantisce coerenza fisica tra velocità pura e performance in qualifica.

## 3.3 Calcoli motore fisico – `Car.update_section()`

Il metodo `update_section(section_ctx, env_ctx)` è il cuore del motore fisico. Avanza l'auto di una sezione del circuito, calcola il tempo impiegato e aggiorna lo stato di auto, gomme e pilota. Opera in 8 passi sequenziali.

### Output del metodo
```python
@dataclass
class SectionResult:
    dt: float                    # Tempo impiegato (secondi)
    v_exit: float               # Velocità in uscita
    events: List[str]          # Eventi triggerati

@dataclass
class BrakeState:
    temp_front: float            # °C medi dischi anteriori
    temp_rear: float             # °C medi dischi posteriori
    wear_front: float            # % usura pad/disco anteriore
    wear_rear: float             # % usura pad/disco posteriore
    fade_level: float            # 0-1, 1 = fade completo

class CarStateSnapshot:
    fuel_remaining: float
    ers_battery: float
    tyre_states: List[TyreState]      # 4 ruote aggiornate
    driver_mental: DriverMentalState  # confidence/fatigue/pressure
    damage_flags: Dict[str, float]
    temp_ice: float                   # temperatura ICE (°C)
    temp_ers: float                   # temperatura ERS (°C)
    brake_state: BrakeState           # stato termico/consumo freni
    last_v_exit: float                # velocità uscita ultima sezione
    last_pace_factor: float           # livello spinta adottato
    driver_feedback_queue: List[str]  # messaggi raccolti dal pilota
```

### I 8 passi del calcolo

#### Passo 1 – Input e stato iniziale
Riceve:
- `section_ctx`: tipo, lunghezza, v_base, curvatura, downforce_importance
- `env_ctx`: track_temp, air_temp, weather, water_film, track_rubber, wind
- Stato corrente car: velocità entrata, fuel, ers, gomme, assetto

#### Passo 2 – Decisione pilota (`DriverModel.compute_inputs`)
Il pilota decide come affrontare la sezione basandosi su:

1. **Livello di spinta** impostato dal giocatore
2. **Skill del pilota** (raw_pace per velocità, race_craft/qualifying_skill per contesto)
3. **Stato mentale dinamico**: confidence modula limite velocità, fatigue riduce aggressione, pressure aggiunge varianza, mistakes_probability triggera errori
4. **Stile di guida**: aggression influenza punti frenata, smoothness modula throttle, oversteer/understeer_preference compensano setup
5. **Experience level**: rookie vs veteran influenza sfruttamento setup
6. **Tyre/Fuel management**: alta skill = sa spingere nonostante usura
7. **ERS management style**: conservative/aggressive/balanced per decisione deploy
8. **Condizioni circuito/meteo**: wet_weather_skill attiva se pioggia

Output `driver_intent`:
- `pace_factor` (0.8–1.2): quanto vicino al limite
- `ers_mode` (deploy/hold/recover)
- `brake_bias_target` (0.55–0.65)
- `throttle_style` (smooth/aggressive)
- `target_line` (race/attack/defend)

#### Passo 3 – Forze aerodinamiche (`AeroPackage.compute_forces`)
Calcola l’effettiva deportanza/drag del pacchetto aero e fornisce segnali per gomme e pilota.

1. **DF per asse**
   ```python
   df_front = front_wing.downforce * sin(front_wing.angle) + front_floor.downforce \
              + sidepods.downforce * 0.5
   df_rear  = rear_wing.downforce * sin(rear_wing.angle) + rear_floor.downforce \
              + engine_cover.downforce + b_wing.downforce + sidepods.downforce * 0.5
   ```

2. **Moltiplicatori sospensioni + skill**
   ```python
   susp_front_mult = 0.85 + 0.3 * (suspension_front.efficiency - 50)/50
   susp_rear_mult  = 0.85 + 0.3 * (suspension_rear.efficiency - 50)/50
   df_front_eff = (df_front + suspension_front.df_bonus) * clamp(susp_front_mult, 0.8, 1.2)
   df_rear_eff  = (df_rear  + suspension_rear.df_bonus) * clamp(susp_rear_mult, 0.8, 1.2)

   susp_quality = 0.95 + 0.001 * (suspension_front.skill + suspension_rear.skill)  # 0.95-1.15
   df_front_eff *= susp_quality
   df_rear_eff  *= susp_quality
   ```

3. **Ride height / antiroll / bump**
   ```python
   rh_pen_front = abs(ride_height_front.height_value - section.rh_optimal_front) * 0.02
   rh_pen_rear  = abs(ride_height_rear.height_value  - section.rh_optimal_rear)  * 0.02
   df_front_eff *= max(0.7, 1 - rh_pen_front)
   df_rear_eff  *= max(0.7, 1 - rh_pen_rear)

   section_bump = section.bumpiness_factor  # 0-1
   bump_penalty = section_bump * (1 - susp_quality/1.1)
   bump_penalty *= 1 + (suspension_front.rigidity + suspension_rear.rigidity)/200
   ```

4. **Drag effettivo + slipstream/aria disturbata**
   ```python
   airflow_penalty = constraints.airflow_penalty  # 0 se in aria pulita, crescente se segue un'auto
   drag_total = sum(component.drag for component in aero_parts)
   air_density_factor = 1.0 - 0.003 * (env_ctx.air_temp - 20)
   drag_eff = drag_total * air_density_factor * (1 - driver_intent.slipstream_bonus)
   cooling_capacity *= (1 - airflow_penalty)  # wake riduce aria fresca su radiatori
   ```

5. **Cooling margin**
   ```python
   cooling_capacity = sidepods.cooling + engine_cover.cooling
   cooling_margin = cooling_capacity - power_unit.cooling_demand
   ```

6. **Handling penalty + skill pilota**
   ```python
   aero_balance = df_front_eff / (df_front_eff + df_rear_eff)
   balance_error = aero_balance - 0.50
   handling_penalty_raw = abs(balance_error) * 0.30

   if balance_error > 0:
       driver_comp = driver.understeer_preference / 100
   elif balance_error < 0:
       driver_comp = driver.oversteer_preference / 100
   else:
       driver_comp = 0

   handling_penalty = handling_penalty_raw * (1 - 0.5 * driver_comp)
   ```

7. **Sottosterzo/Sovrasterzo per gomme**
   ```python
   if abs(balance_error) > 0.05:
       base_level = min(1.0, (abs(balance_error) - 0.05) * 5)
       adjust = (1 - 0.3 * driver_comp)
       understeer_level = base_level * adjust if balance_error > 0 else 0
       oversteer_level  = base_level * adjust if balance_error < 0 else 0
   else:
       understeer_level = oversteer_level = 0
   ```

8. **Kerb impact** (per degrado gomme/ sospensioni)
   ```python
   if section.has_kerb and driver_intent.aggression > 70:
       kerb_impact = True
       kerb_severity = (driver_intent.aggression - 70) / 30  # 0-1
   else:
       kerb_impact = False
       kerb_severity = 0
   ```

**Output Passo 3**
- `df_available`: `df_front_eff` o `df_rear_eff` a seconda della curvatura
- `drag_eff`: drag corretto per densità aria/slipstream
- `cooling_margin`: margine (positivo → ok, negativo → derating motore)
- `handling_penalty`: penalità da applicare alla velocità di curva
- `understeer_level` / `oversteer_level`: segnali per TyreSet (temperatura/usura asse)
- `bump_penalty`, `kerb_impact`, `kerb_severity`: incrementano vibrazioni/usura gomme e rischio damage sospensioni

#### Passo 4 – Potenza motore (`PowerUnit.generate_output`)
Prima di entrare nelle formule del passo definisci l’aggregato `PowerUnit` e i due sottosistemi `InternalCombustionEngine` ed `EnergyRecoverySystem`, ognuno con metadata tecnici (nome pezzo, versione, data di introduzione) e gestione dell’usura.

```python
@dataclass
class InternalCombustionEngine:
    component_name: str      # es. "PU106C EVO"
    version_id: str          # "ICE25-V2"
    introduced_at: str       # GP / data omologazione
    torque_curve: Dict[int, float]   # rpm → Nm
    fuel_flow_limit: float          # kg/h
    thermal_capacity: float         # MJ/°C
    wear_rate: float                # % per MJ dissipata
    maps: Dict[str, EngineMapConfig]
    temp: float
    wear: float                     # 0-100%
    rpm_target: int

@dataclass
class EnergyRecoverySystem:
    component_name: str      # es. "ERS-H/K Gen3"
    version_id: str
    introduced_at: str
    soc_capacity: float      # MJ
    deploy_limit_kw: float
    harvest_limit_kw: float
    thermal_capacity: float
    wear_rate: float         # % per MJ caricata/scaricata
    maps: Dict[str, ErsMapConfig]
    temp: float
    wear: float
    soc: float
    mguk_state: str
    mguh_state: str

@dataclass
class PowerUnit:
    ice: InternalCombustionEngine
    ers: EnergyRecoverySystem
    engine_maps: Dict[str, EngineMapConfig]
    ers_maps: Dict[str, ErsMapConfig]
    active_engine_map: str
    active_ers_mode: str

    def set_maps(self, engine_map: str, ers_mode: str): ...
    def generate_output(self, driver_intent, car_state, env_ctx): ...
```

- **EngineMapConfig**: contiene `power_percent`, `consumption_rate`, `torque_ramp`, `heat_load` e vincoli (`min_temp`, `max_temp`).
- **ErsMapConfig**: definisce `output_kw`, `consumption_rate` (MJ/s), `recovery_rate`, `heat_coeff`, `efficiency`.

L’utente può creare nuove mappe mappa ICE/ERS (UI “Engine Map”, “ERS Mode”): basta instanziare nuovi `EngineMapConfig` / `ErsMapConfig`. Il metodo `set_maps()` aggiorna `active_engine_map` e `active_ers_mode`, che vengono letti dai sottosistemi nel passo seguente.

Calcola ora la potenza disponibile per la sezione e gli impatti su fuel/ERS.

1. **Mappa ICE attiva + coppia**
   ```python
   map = power_unit.ice.active_map
   torque_ice = torque_curve[rpm] * map.power_percent * (1 - ice.wear * 0.002)
   power_ice = torque_ice * rpm / 9549   # kW
   fuel_burn_rate = min(fuel_flow_limit, map.consumption_rate) / clamp(ice.fuel_efficiency, 1, 100)
   torque_ramp = map.torque_ramp  # 0 (dolce) → 1 (brusca)
   ```

   Usura ICE aggiornata proporzionalmente all’energia generata:
   ```python
   ice.wear += ice.wear_rate * power_ice * dt
   ```

2. **Derating termico / affidabilità**
   ```python
   if cooling_margin < 0:
       derating_factor = clamp(1 + cooling_margin / cooling_ref, 0.7, 1.0)
   else:
       derating_factor = 1.0

   wear_factor = 1 - (ice.km_used / ice.max_km) * wear_coeff
   power_ice_eff = power_ice * derating_factor * wear_factor
   ```

3. **ERS (deploy + usura)**
   ```python
   mode = power_unit.ers.modes[power_unit.ers.active_mode]
   if driver_intent.ers_mode == 'deploy':
       ers_output = mode.output_kw
       ers_delta = -mode.consumption_rate
   elif driver_intent.ers_mode == 'recover':
       ers_output = mode.output_kw * 0.2
       ers_delta = mode.recovery_rate
   else:  # hold
       ers_output = mode.output_kw * 0.5
       ers_delta = 0
   ```

   Se `ers_battery` < soglia → forza modalità hold e riduce `ers_output`.

   Aggiorna usura ERS in base a energia scambiata:
   ```python
   energy_moved = abs(ers_output) * dt
   ers.wear += ers.wear_rate * energy_moved
   ```

4. **Potenza complessiva e limite FIA**
   ```python
   power_kw = min(power_ice_eff + ers_output, FIA_MAX_POWER)
   ```

5. **Fuel burn / ERS state per la sezione**
   ```python
   fuel_burn = fuel_burn_rate * section_ctx.length / max(v_entry, 1)
   ```
   (approssimazione: consumo proporzionale al tempo speso nella sezione; il valore preciso viene ricalcolato dopo con `dt`).

6. **Gestione termica**
   ```python
   heat_ice_in  = power_ice_eff * map.heat_load
   heat_ice_out = cooling_capacity * (1 - airflow_penalty) * cooling_coeff
   temp_ice_next = temp_ice + (heat_ice_in - heat_ice_out) * dt / thermal_mass_ice
   temp_ice_next *= (1 - natural_cooling * dt)

   heat_ers_in  = ers_output * ers_heat_coeff
   heat_ers_out = cooling_capacity * (1 - airflow_penalty) * ers_cooling_share
   temp_ers_next = temp_ers + (heat_ers_in - heat_ers_out) * dt / thermal_mass_ers
   temp_ers_next *= (1 - natural_cooling * dt)
   ```

   Se `temp_ice_next > temp_warning` → `derating_flag = True`. Se supera `temp_critical` forziamo mappa Economy o inneschiamo rischio failure.

**Output Passo 4**
- `power_kw`: potenza efficace (ICE+ERS) da usare nei rettilinei (Passo 6)
- `fuel_burn`: consumo indicativo (kg) per la sezione, raffinato con `dt`
- `ers_delta`: variazione batteria (MJ)
- `derating_flag`: true se `derating_factor < 1` o `temp_ice` in warning
- `temp_ice_next`, `temp_ers_next`: nuove temperature da salvare nello stato
- `torque_ramp`: coefficiente di aggressività erogazione (usato dalle gomme posteriori)

#### Passo 5 – Stato gomme e freni (`TyreSet.update` + `BrakeSystem.update`)
Integra la termica condivisa gomme/freni, gli effetti del brake bias e genera feedback pilota quando skill `setup_finding` o `tyre_management` ≥ 75.

##### 5.1 BrakeSystem.update
1. **Energia frenata e ripartizione**
   ```python
   braking_energy = section.braking_energy  # input circuito (kJ)
   front_share = clamp(driver_intent.brake_bias, bias_range.min, bias_range.max)
   rear_share = 1 - front_share
   energy_front = braking_energy * front_share
   energy_rear  = braking_energy * rear_share
   ```

2. **Temperatura / cooling**
   ```python
   heat_quality = 1 - (brake_system.system_quality - 50)/200  # impianto migliore → meno calore disperso
   heat_front = (energy_front / disc_material_front.heat_capacity) * heat_quality
   heat_rear  = (energy_rear  / disc_material_rear.heat_capacity) * heat_quality
   duct_cooling = duct_opening * cooling_coeff * (1 - airflow_penalty)

   temp_front += (heat_front - duct_cooling * cooling_share_front) / thermal_mass_front
   temp_rear  += (heat_rear  - duct_cooling * cooling_share_rear)  / thermal_mass_rear
   ```

3. **Usura / fade**
   ```python
   wear_quality = 1 - (brake_system.system_quality - 50)/250
   wear_front += wear_rate_base_front * energy_front * wear_quality
   wear_rear  += wear_rate_base_rear  * energy_rear  * wear_quality

   if temp_front > fade_threshold_front:
       fade_level += (temp_front - fade_threshold_front)/fade_sensitivity
   ```
   `fade_level` riduce efficacia frenante e alimenta `handling_penalty` (sottosterzo in ingresso).

4. **Feedback pilota**
   ```python
   if driver.setup_finding >= 75 and temp_front > fade_threshold_front + 30:
       driver_feedback_queue.append("Front brakes hot")
   if driver.tyre_management >= 80 and wear_front > 70%:
       driver_feedback_queue.append("Brake wear high")
   ```

##### 5.2 TyreSet.update (per ruota)
1. **Heat generation / perdita** (ora include calore indotto dai freni anteriori)
   ```python
   heat_gen = section.heat_factor * driver_intent.pace_factor * load_multiplier
   heat_gen *= 1 + understeer_level if tyre.axis == 'front' else 1 + oversteer_level
   heat_gen += brake_bias_factor per asse anteriore + temp_front * brake_heat_transfer * heat_quality
   heat_gen *= 1 + (driver.aggression - 50)/200 - (driver.smoothness - 50)/200
   if tyre.axis == 'rear':
       heat_gen *= 1 + torque_ramp * 0.3

   convective_cool = cooling_coeff * section.air_speed * (1 - airflow_penalty)
   core_exchange = (temp_surface - temp_core) * conduction_coeff

   temp_surface += (heat_gen - convective_cool - kerb_penalty) * dt / thermal_mass_surface
   temp_core    += core_exchange * dt / thermal_mass_core
   ```

2. **Usura** (ora dipende anche dal fade freni se eccessivo)
   ```python
   load_duration = section_ctx.length / max(v_entry, 1)
   wear_rate = tyre.wear_rate_base * driver_intent.pace_factor * section.bumpiness_factor
   wear_rate *= 1 + bump_penalty + kerb_severity
   wear_rate *= 1 + handling_penalty + fade_level * 0.1
   wear_rate *= 1 + (driver.aggression - 50)/150
   wear_rate *= 1 - (driver.smoothness - 50)/200
   wear_rate *= 1 - driver.tyre_management/150
   if tyre.axis == 'rear':
       wear_rate *= 1 + torque_ramp * 0.25
   wear_pct += wear_rate * load_duration
   ```

3. **Grip effettivo**
   ```python
   thermal_factor = gaussian(temp_surface + airflow_penalty * 5, tyre.temp_window)
   wear_factor = max(0.5, 1 - wear_pct/100)
   setup_bonus = 1 + mechanical_grip_bonus + suspension_axis_mult
   effective_grip = tyre.base_grip * thermal_factor * wear_factor * setup_bonus
   ```

4. **Flags salute + feedback**
   ```python
   if temp_surface > tyre.temp_window.max + 10:
       tyre.overheat_warning = True
       if driver.tyre_management >= 80:
           driver_feedback_queue.append("Tyres overheating")
   if wear_pct > 80%:
       tyre.puncture_risk += pace_factor * 0.01
   if understeer_level > 0.3 e tyre.axis == 'front':
       tyre.graining_level += 0.02
   if kerb_impact and tyre.wheel_position in kerb_side:
       tyre.flatspot_severity += kerb_severity * brake_bias_factor
   ```

**Output Passo 5**
- `effective_grip_front`, `effective_grip_rear`: media grip asse (usate nel Passo 6)
- `brake_state` aggiornato (temperature, wear, fade)
- Aggiornamento `TyreState` (temp_surface/core, wear, flags)
- `tyre_events` + `brake_events` e `driver_feedback_queue` aggiornati

#### Passo 6 – Velocità effettiva e dt
1. **Curva: velocità teorica da DF, pilota e freni**
   ```python
   curvature_factor = section.curve_profile.curvature_factor  # calcolato da radius effettivo (1/r) e banking
   v_curve = v_base * (1 + curvature_factor * k_df * (df_available - df_ref)/df_ref)
   v_curve *= (1 - handling_penalty)
   v_curve *= 1 + (driver_intent.pace_factor - 1) * driver_intent.aggression_curve_bonus

   temp_delta = abs(brake_state.temp_front - brake_opt_window.center) / brake_opt_window.center
   brake_quality = 0.9 + brake_system.system_quality / 200
   brake_health = 1 - clamp(brake_state.fade_level + brake_state.wear_front/100, 0, 0.8)
   driver_brake_skill = (driver.race_craft + driver.aggression)/200
   braking_efficiency = clamp(1 + brake_quality * driver_brake_skill * brake_health - temp_delta * 0.4, 0.9, 1.15)

   drag_curve_penalty = k_drag_curve * (drag_eff - drag_ref)
   v_curve = (v_curve * braking_efficiency) - drag_curve_penalty
   ```

2. **Limite grip**
   ```python
   grip_axis = effective_grip_front if section.curvature > 0 else effective_grip_rear
   v_grip_limited = v_curve * grip_axis
   ```

3. **Rettifilo: potenza vs drag**
   ```python
   delta_power = k_power * (power_kw - power_ref)
   delta_drag  = k_drag * (drag_eff - drag_ref)
   v_straight = min(v_base + delta_power - delta_drag, v_cap)
   ```

4. **Constraint traffico / difesa**
   ```python
   v_constraint = constraints.v_max_constraint or +inf
   v_curve = min(v_grip_limited, v_constraint)
   v_straight = min(v_straight, v_constraint)
   ```

5. **Velocità effettiva finale**
   ```python
   if section.type in ['SlowCorner', 'MediumCorner', 'FastCorner']:
       v_effettiva = max(v_min, v_curve)
   else:
       v_effettiva = max(v_min, v_straight)
   ```

> **Nota sul profilo curva**: ogni `section.curve_profile` contiene `radius_m`, `banking_deg`, `curvature_factor` e un flag `complex_corner`. Questo permette di distinguere Parabolica, Lesmo, Variante Ascari pur condividendo la stessa classe `FastCorner`. Il coefficiente `k_drag_curve` introduce l’effetto aerodinamico del drag anche nelle staccate/curve complesse.

6. **Penalità eventi**
   - Se `tyre_events` contiene `overheat`, moltiplica `v_effettiva` per `0.98`.
   - Se `engine_temp_event`, riduci `power_kw` alla prossima sezione.
   - Se `braking_efficiency < 0.95`, registra evento "Brake fade"; se `> 1.05`, evento "Late braking success" (usato da BattleResolver per sorpassi).

7. **Tempo sezione**
   ```python
   dt = section_ctx.length / max(v_effettiva, 1)
   ```

#### Passo 7 – Aggiornamento stati interni
- `fuel_remaining -= fuel_burn × dt`
- `ers_battery += ers_delta`
- `tyre_states`: temp e wear aggiornati
- `driver_mental`: confidence/fatigue/pressure modulati da performance sezione
- `damage_flags`: se eventi (es. flat spot da frenata violenta)

#### Passo 8 – Return
Restituisce `SectionResult(dt, v_exit, events)` e stato interno aggiornato.

---

### 3.3.1 LapSimulator runtime loop (single lap)

Il motore LAP in-game orchestra più auto mantenendo la fisica pura di `Car.update_section()` separata dalla logica d’interazione. Il loop di un giro è composto da quattro blocchi principali.

```
SessionController
    │
    ├─► InputMixer ──► Car.update_section()  × N (in parallelo)
    │                     │
    │                     └─► SectionResult + segnali (df, drag, power, section_progress)
    │
    ├─► BattleResolver (pacchetti auto vicine, cooldown/lock)
    │
    ├─► StateCommit (swap ordine, gap, penalty, eventi)
    │
    └─► OutputBus (HUD, DegradationManager, Strategia AI, Replay)
```

1. **InputMixer**
   - Aggrega informazioni statiche e dinamiche: `section_ctx`, `env_ctx`, comandi giocatore (push level, ERS map), stato auto precedente.
   - Prepara pacchetti dati batteria/cooling condivisi per uso in `Car.update_section()`.

2. **Fase fisica parallela**
   - Ogni auto invoca `update_section()` sulla sezione corrente. Output arricchito con segnali aggiuntivi esposti al resolver:
     - `section_progress` = `distance_in_section / section_length`.
     - `overtake_window` (0-1) = disponibilità attacco (derivato da pace_factor, delta_vel, driver intent `target_line`).
     - `attack_cooldown`, `defense_reset`: contatori decrementati internamente e restituiti per sincronizzazione.
     - `srs_flags`: abilità attive (DRS, Boost ERS, Frenata Perfetta), `braking_efficiency_event`, `late_brake_tag`.
     - `traffic_constraints`: velocità massima consentita dalla presenza di auto davanti (usata anche in Passo 6).

3. **BattleResolver**
   - Riceve la lista di auto raggruppata per sezione (`section_id`). Per ogni pacchetto ordina per `section_progress` e valuta coppie adiacenti.
   - Calcola `attack_score`/`defense_score` usando segnali fisici (delta `v_exit`, `power_kw`, `effective_grip`, `handling_penalty`), skill pilota, stato mentale, e bonus delle abilità speciali.
   - Stati gestiti:
     - `side_by_side`: true quando `attack_score` supera soglia di tentativo → penalità comune (aria sporca, consumo ERS ulteriore) e evento "Side-by-side".
     - `attack_cooldown`: attivato se tentativo fallisce; BattleResolver forza `overtake_window = 0` finché il timer (in sezioni) non scade.
     - `defense_reset`: per l'auto sorpassata; finché attivo riduce `attack_score` e impedisce controsorpasso immediato.
   - Esiti possibili:
     1. **Sorpasso riuscito** → scambia l'ordine, assegna offset sicuro (`section_progress += 0.02`), aggiorna confidence e registra evento "Overtake success".
     2. **Tentativo fallito** → mantiene ordine, applica cooldown all'attaccante, aumenta usura/temperatura a seconda di `side_by_side` e logga "Attempt blocked".
     3. **Contatto / errore** → genera penalità tempo o damage, invia evento a `OutputBus`, può inserire un ritardo (delta tempo) nella sezione successiva.

4. **StateCommit & OutputBus**
   - Aggiorna `section_progress` globale, `lap_time_accumulator`, classifiche e gap virtuali.
   - Scrive gli eventi nel `OutputBus` consumato da HUD/telemetria/radio e da `DegradationManager` (che userà i segnali `understeer_level`, `bump_penalty`, `attack_cooldown` ecc. per calcolare degradi a lungo termine).
   - Reimmette i cooldown aggiornati nello stato auto per la sezione successiva.

> **Nota implementativa**: la fase fisica gira in thread separati (uno per auto o batch) con barrier alla fine della sezione; BattleResolver gira nel thread principale per garantire determinismo. Questo consente di scalare a 20+ auto senza toccare il motore fisico di base.

Con questa struttura il motore LAP fornisce una sequenza coerente di eventi “pallino su rotaia”: il sorpasso emerge dal gioco di `section_progress`+BattleResolver, mentre la complessità percepita deriva dai cooldown, dalle penalità e dai feedback che alimentano l’esperienza utente.

## 3.4 Architettura multi-auto: RaceSimulator e BattleResolver

Il metodo `update_section()` definito sopra calcola la fisica di una singola auto isolata (time-trial). Per simulare una gara multi-auto con sorpassi e interazioni, introduciamo un'architettura a **due livelli**.

### Livello 1 – Car.update_section() (Fisica singola auto)
Calcola lo spostamento in una sezione dati:
- Input pilota (spinta, stile, ERS)
- Assetto auto (DF, drag, potenza)
- Meteo e condizioni pista

**Ignora completamente le altre auto.** Restituisce il tempo "ideale" che l'auto impiegherebbe nella sezione se fosse sola.

### Livello 2 – BattleResolver (Orchestratore interazioni)
Analizza le coppie di auto che occupano la stessa sezione nello stesso momento e decide gli esiti delle interazioni.

```
┌─────────────────────────────────────────────────────────────────┐
│                    RACESIMULATOR LOOP                           │
├─────────────────────────────────────────────────────────────────┤
│  1. FASE FISICA (parallela per tutte le auto)                   │
│     Per ogni auto:                                              │
│     dt_pure = car.update_section(section, env)                  │
│                                                                 │
│  2. FASE BATTLE (sequenziale, analizza conflitti)               │
│     Per ogni coppia auto nella stessa sezione:                  │
│     • Calcola gap spaziale e temporale                          │
│     • Determina se c'è tentativo di sorpasso                    │
│     • BattleResolver decide esito                               │
│                                                                 │
│  3. FASE APPLICAZIONE                                          │
│     • Sorpasso riuscito: scambia posizioni, applica dt         │
│     • Bloccata: auto dietro usa dt = dt_davanti + gap          │
│     • Contatto: applica damage, rallentamenti forzati          │
│                                                                 │
│  4. FASE AGGIORNAMENTO                                         │
│     Aggiorna posizioni globali, classifica, telemetria         │
└─────────────────────────────────────────────────────────────────┘
```

### Parametri BattleResolver per decisioni

Il resolver valuta ogni potenziale interazione basandosi su:

| Parametro | Auto attaccante (B) | Auto difendente (A) |
|-----------|---------------------|---------------------|
| **Skill** | `overtaking_skill`, `race_craft` | `raw_pace` (velocità pura) |
| **Stato mentale** | `confidence` (coraggio), `aggression` | `pressure` (suscettibile errore) |
| **Setup sezione** | `top_speed` (rettilineo) / `df_rear` (curva) | Assetto difensivo |
| **Gomme** | `grip_available` (serve aderenza) | `wear_pct` (alta = difesa debole) |
| **Posizione** | Esterno curva = rischio/alto reward | Interno = vantaggio posizionale |
| **ERS** | `deploy` disponibile per boost | - |
| **Gap** | < 0.5s = facile, > 1.0s = difficile | Distanza da difendere |

### Formula esito sorpasso (proposta)

```
p_success = sigmoid(advantage_total)

advantage_total = 0.30 * Δskill + 0.20 * Δsetup_match + 0.20 * Δgrip
                + 0.15 * Δmental + 0.10 * Δposition + 0.05 * random

se p_success > 0.7 → Sorpasso riuscito
se 0.3 < p_success < 0.7 → Lotta continua (prossima sezione)
se p_success < 0.3 → Tentativo fallito, rimane dietro
```

### Vantaggi dell'approccio a due livelli

1. **Separazione responsabilità**: fisica pura vs logica di gara
2. **Testabilità**: si può testare una singola auto senza RaceSimulator
3. **Scalabilità**: aggiungere auto non complica la fisica base
4. **Eleganza**: nessuna logica gap-based complicata nella fisica

## 3.5 Calibrazione & Validazione (Punto 5)

Per garantire che ogni blocco del motore fisico resti coerente con la realtà costruiamo una pipeline a due livelli: **verifica dei componenti** e **verifica integrata**. Ogni step dispone di dataset di riferimento, metriche e tool dedicati.

### 3.5.1 Component Verification Suite

| Modulo | Dataset reale | Script/tool | Metriche accettazione |
|--------|---------------|-------------|-----------------------|
| AeroPackage | CFD/galleria 2025 + telemetria FastF1 (DF/drag) | `notebooks/calibration/aero_fit.ipynb` | errore DF/drag < 3% | 
| TyreModel | Delta Pirelli, stint reali | `tyre_fit.py` + `pytest physics/tests/test_tyre_fit.py` | Δtemp < 5°C, wear trend <10% |
| PowerUnit (ICE/ERS) | dati FIA fuel/ERS, run telemetry | `powerunit_fit.py` | consumo ≤0.1 kg/giro, ΔERS ≤0.2 MJ |
| BrakeSystem | log frenate (energia vs temp) | `brake_calibration.ipynb` | temp error < 20°C, fade curve sovrapponibile |
| DriverModel | dataset simulazioni AI/umana | `driver_skill_validation.py` | varianza tempi coerente (+/−5%) |

Flusso:
1. Aggiorna i file `config/calibration/<module>.json` con i parametri fittati.
2. Esegui `pytest physics/tests/test_<module>_fit.py` per assicurarti che i modelli singoli generino output consistenti.
3. Solo dopo i “component badge” verdi è consentito promuovere le modifiche al LapSimulator.

### 3.5.2 Single-Car Lap Validation

- **Input**: setup reali, tempi settore referenziati (FastF1 / telemetria interna).
- **Tool**: `scripts/simulate_lap.py --circuit <ID> --setup <JSON>`.
- **Ottimizzazione**: fitting automatico dei coefficienti globali (`k_power`, `k_drag`, `curve_factor`, `thermal_coeff`) via least squares.
- **Metriche**:
  - RMSE tempi settore < 0.15 s.
  - Lap time totale entro ±0.30 s rispetto alla telemetria.
  - Trend degrado gomme coerente (errore < 5% sulla pendenza wear vs giro).
- **Test regression**: `pytest tests/lap_regression/test_<circuit>.py` esegue 3 circuiti (alto carico, medio, low drag) ad ogni PR; se l’errore supera soglia fallisce la pipeline.

### 3.5.3 RaceSimulator & BattleResolver Validation

- **Input**: log gara reali (gap, sorpassi, safety car) + dataset interno di scenari sintetici (2-car fight, DRS train, wet stint).
- **Tool**: `scripts/run_race_validation.py --scenario <name> --seed <n>` che avvia il RaceSimulator completo e BattleResolver con i componenti calibrati.
- **Metriche**:
  - # sorpassi per gara entro ±10% rispetto al riferimento.
  - Rapporto tentativi riusciti/falliti (0.45–0.55 range target).
  - Distribuzione tempo in aria sporca e consumo ERS combacia con dati reali (<8% di errore).
  - Penalità/eventi coerenti (nessun contatto non giustificato).
- **Outcome**: genera report JSON + grafici (gap vs giro, timeline eventi) usati da game design e QA.

### 3.5.4 Automation & Release Gate

1. **Pipeline CI** (`make calibrate` oppure workflow gha `calibration.yml`):
   - Step A: Component Verification Suite (pytest + notebook convertiti in script) → badge.
   - Step B: Single-Car Lap Validation su 2 circuiti.
   - Step C: RaceSimulator smoke test (scenario breve 5 giri) per garantire che BattleResolver + cooldown funzionino.
2. **Manual QA**: build “Engineer Mode” permette di loggare durante playtest; i log vengono confrontati con baseline tramite `notebooks/validation/report.ipynb`.
3. **Release checklist**:
   - Rifare la calibrazione completa su 3 circuiti (high DF, bilanciato, low drag).
   - Salvare i risultati in `docs/calibration_runs/<date>.md` con metriche.
   - Aggiornare `config/calibration/manifest.json` con checksum dei parametri promossi.

Con questa pipeline ogni componente simulato è verificato individualmente prima dell’integrazione, e il sistema completo viene ricontrollato tramite LapSimulator e RaceSimulator. Qualsiasi regressione sui test blocca il merge, garantendo che l’esperienza “pallino su rotaia” resti fisicamente plausibile e consistente.

## 4. Aggregati aerodinamici
Calcolati ogni tick o quando cambia il setup:
- `df_front = front_wing.df + front_floor.df + sidepods.df * 0.5`
- `df_rear = rear_wing.df + rear_floor.df + engine_cover.df + b_wing.df + sidepods.df * 0.5`
- `df_total = df_front + df_rear`
- `drag_total = somma drag componenti`
- `aero_balance = df_front / df_total` (target 0.50 ± epsilon)
- Le sospensioni forniscono moltiplicatori `susp_front_mult`, `susp_rear_mult` (es. 0.85–1.15) basati su `efficiency` e `rigidity`, oltre a un bonus additivo `df_bonus` (convertito in punti DF).
- Raffreddamento disponibile: `cooling_capacity = sidepods.cooling + engine_cover.cooling`; usato per valutare se le mappe motore richieste rientrano nella finestra termica.
- Ride height target per circuito: ogni pista definisce `ride_height_optimal_front/rear`; scostamenti riducono il `df_bonus` e aumentano `bump_penalty` se sotto la soglia o drag se troppo alti.
- Antiroll multipliers: `antiroll_front_mult`, `antiroll_rear_mult` (0.9–1.1) applicati rispettivamente a curve veloci (front) e curve lente/uscita (rear) per modulare `v_section` e usura gomme sull’asse esterno.
- Grip meccanico effettivo: `grip_mech_eff = grip_base * f(ride_height, antiroll, tyre_state)` utilizzato nei segmenti `SlowCorner`/`Traction`.
- Formula proposta per asse anteriore (simile per posteriore):
  - `susp_front_mult = 0.85 + 0.3 * (efficiency_front - 50)/50`
  - `df_front_effective = (df_front + df_bonus_front) * clamp(susp_front_mult, 0.8, 1.2)`
  - `rigidity_front` modula il trade-off: valori alti migliorano curve veloci ma aumentano `bump_penalty` su sezioni sconnesse; valori bassi proteggono i bump ma riducono precisione e quindi `df_bonus`.

## 5. Regola di calcolo velocità per sezione
Invece di definire manualmente la velocità per ogni curva:
1. **Velocità base** (`v_base(section)`) = media telemetria 2025 per quella sezione.
2. **Coefficiente curva** (`curve_factor`) derivato automaticamente dal tipo sezione:
   - Straight → 0.0
   - SlowCorner → 0.4
   - MediumCorner → 0.7
   - FastCorner → 1.0
3. **Downforce effettivo**:
   - Sezione con curvatura positiva (curva a destra) → usa `df_front` per l’avantreno dominante.
   - Curvatura negativa → usa `df_rear`.
   - DF effettivo = `df_axis * suspension_axis_mult` normalizzato rispetto a `df_ref` (valore medio 70).
4. **Velocità finale curva**:
   ```
   v_section = v_base * (1 + curve_factor * k_df * (df_eff - df_ref) / df_ref)
   v_section = v_section * (1 - handling_penalty)
   ```
   - `k_df` coefficiente globale (es. 0.15).
   - `handling_penalty` dipende da `|aero_balance - target|` (sottosterzo/sovrasterzo penalizza curve relative all’asse carente).
5. **Rettifili**: usano `drag_total` e la potenza motore (placeholder) per applicare `delta_drag`:
   ```
   v_section = min(v_base + delta_power - k_drag * (drag_total - drag_ref), v_cap)
   ```

Questo schema scala automaticamente per tutte le curve/rettifili, senza editing manuale. DF alto → curve più veloci; drag alto → top speed ridotta.

## 6. Collegamento al modello 60/30/10
- L’output delle formule di sezione sostituisce la parte “Auto 60%” della vecchia formula. Aggregando i tempi dei segmenti otteniamo il contributo reale dell’auto.
- Le gomme (30%) limitano il DF sfruttabile: se grip < soglia, `df_eff` viene ridotto.
- Il pilota (10%) può compensare piccoli squilibri (riduce `handling_penalty` o sfrutta meglio il DF disponibile).

## 7. Componenti auto future

### 7.1 Motore / Power Unit (v0.2)
Suddiviso in due macro blocchi:

#### 7.1.1 ICE (Internal Combustion Engine)
- Parametri:
  - `power_rating` (1-100) → cavalli disponibili.
  - `reliability` (1-100) → consumo per km e possibilità di usare mappature spinte.
  - `fuel_efficiency` (1-100) → quanto consuma per unità di potenza; valori alti riducono il burn rate.
  - `max_km` (km teorici) e `km_used` → tracking usura season-based.
  - `available_maps`: lista di mappature definite come `% potenza` rispetto al rating base.
    - Range consentito 50%–110%; mappa >100% richiede `reliability` elevata.
- Mappature ICE (esempio iniziale):
  | Nome      | % Potenza | Consumo km | Note |
  |-----------|-----------|------------|------|
  | Economy   | 70%       | basso      | Uso in fuel saving.
  | Race      | 95%       | medio      | Default gara.
  | Qualy     | 105%      | alto       | Disponibile se `reliability >= 70`.
- Effetto sul calcolo rettilinei:
  - `delta_power = k_power * (power_rating * map_multiplier - power_ref)`.
  - `fuel_burn_rate = base_consumption * map_multiplier / clamp(fuel_efficiency, 1, 100)`.
  - Penalità se `km_used / max_km` supera soglia (potenza limitata o rischio failure).

#### 7.1.2 ERS / Sistema elettrico (MGU-K/H)
- Parametri:
  - `power_rating_kw` (1-100) mappato sui limiti FIA (~120 kW max).
  - `reliability` (1-100) e contatore `max_km`/`km_used` analoghi all’ICE.
  - Mappature predefinite (statiche):
    1. **Gara** – output equilibrato, neutral.
    2. **Qualifica** – erogazione massima per un giro.
    3. **Sorpasso** – boost breve ad alto consumo.
    4. **Recupero** – priorità a ricarica (output ridotto).
    5. **Safety Car** – output minimo, efficienza alta.
- Per ciascuna mappa definiamo: `% output`, `% recupero`, `consumo_batteria`, `limiti durata`.
- L’utente seleziona la mappa, il sistema calcola l’energia disponibile/giro e aggiorna la batteria.
- Il contributo ERS entra nel delta rettilineo insieme all’ICE:
  - `delta_power = delta_power_ice + k_ers * (ers_output - ers_ref)`.
  - Se la mappa ERS supera il limite FIA (es. >120 kW), si clampa e segnala.
- Stato batteria (SoC) da tracciare per vincolare l’uso di mappe Sorpasso/Qualy: `ers_energy` in MJ con limiti per giro (es. 4 MJ deploy / 2 MJ recovery).
- Temperature ERS: se l’output alto persiste oltre soglia, attivare derating temporaneo o passaggio forzato a modalità Recupero.

#### 7.1.3 Interfaccia dati proposta
```
@dataclass
class EngineMap:
    name: str
    power_percent: float  # 0.5 - 1.1
    consumption_rate: float
    duration_laps: Optional[int]

@dataclass
class ICEUnit:
    power_rating: int  # 1-100
    reliability: int  # 1-100
    max_km: float
    km_used: float
    maps: Dict[str, EngineMap]
    active_map: str

@dataclass
class ERSMode:
    name: str
    output_kw: int   # limitato ~120 kW
    recovery_rate: float
    consumption_rate: float

@dataclass
class ERSUnit:
    power_rating_kw: int
    reliability: int
    max_km: float
    km_used: float
    modes: Dict[str, ERSMode]
    active_mode: str

@dataclass
class PowerUnit:
    ice: ICEUnit
    ers: ERSUnit
```

#### 7.1.4 Impatto nel modello
- Top speed rettilineo = funzione di `ICE power`, `ERS output`, `drag_total`, `rear_wing angle`.
- `delta_power` calcolato per sezione rettilinea e applicato in `v_section` (vedi §5 punto 5).
- `reliability` e `km_used` determinano rischio di failure o limitazione potenza (es. `power_cap = power_rating * (1 - wear_coeff)`).
- `fuel_tank`: tenere un contatore di kg carburante; il `fuel_burn_rate` delle mappe ICE scala il consumo e impone strategie di fuel saving (se il livello scende sotto soglie predefinite si forzano mappe Economy).
- Temperature ICE/raffreddamento: introdurre `cooling_efficiency = cooling_capacity / cooling_ref` che, se insufficiente rispetto alla mappa attiva, riduce progressivamente il `power_rating` o costringe a mappe meno spinte.

### 7.2 Grip meccanico / Telaio (v0.3)
- Valori da gestire: `ride_height_front/rear`, `antiroll_front/rear`, `mechanical_grip` base (che assorbe la parte “rigidity” delle sospensioni quando serve).
- Impatto: moltiplicatori su `df_eff` alle basse velocità e controllo sui bump/kerb (sinergia con sospensioni).
- Penalità previste se troppo basso/rigido: aumento usura gomme, probabilità errori.

### 7.3 Gomme (v0.4)
- Evoluzione della classe `Gomma`: aggiungere temperatura, finestra operativa, delta grip per compound.
- Il DF effettivo verrà limitato da `grip_available = f(temperatura, vita, compound)`.
- Output richiesto: `tire_grip_multiplier` e `wear_rate` da applicare ai segmenti.

#### 7.3.1 Dati e input necessarie
1. **Catalogo Pirelli**: per ogni compound slick C1–C5 (più INT/WET) memorizziamo grip baseline, finestra termica ottimale, coefficiente di warm-up e slope di degrado.
2. **Profilo GP**: ogni circuito deve dichiarare le tre nomination Pirelli (Soft/Medium/Hard reali), i delta tempo stimati tra le mescole e le note di degrado/stint length. I mapping esistenti (es. `Raw_2024/italy_mapping.json`) forniscono i `*_tire_multiplier` e parametri di smoothness/bumpiness.
3. **Assetto qualità**: uno scalare derivato da setup (ali, ride height, sospensioni, antiroll, balance) e skill pilota `consumo_gomme`; questo valore modula degrado e controllo termico.

#### 7.3.2 Stato per ogni gomma
Ogni istanza `Tyre` (per ruota oppure per asse) conserva almeno i seguenti attributi:
- **Identità**: `compound`, `pirelli_label` (Soft/Medium/Hard/INT/WET), `stint_id`, `wheel_position`.
- **Lifecycle**: `life_percent`, `lap_age`, `wear_rate_base`, `wear_rate_dynamic`, `heat_cycle_count`, `graining_level`, `blistering_level`.
- **Termica**: `temp_surface`, `temp_core`, `temp_window_min/max`, `thermal_mass`, accumulatori `heat_generation` e `heat_dissipation`.
- **Grip & performance**: `base_grip`, `thermal_grip_factor`, `wear_grip_factor`, `pressure_offset`, `effective_grip`, `lap_time_delta_hint`.
- **Setup/balance input**: `aero_balance_error`, `suspension_stiffness`, `ride_height_offset`, `antiroll_setting`, `mechanical_grip_score`, `pace_factor`, `track_bumpiness_factor`.
- **Environment hooks**: `air_temp`, `track_temp`, `track_rubber_level`, `weather_state`, `water_film_level` (per INT/WET), `drs_active`, `last_section_kind`.
- **Health flags**: `overheat_warning`, `cold_warning`, `puncture_risk`, `flatspot_severity`, `safety_crossover_ready`.

#### 7.3.3 Modello termico e grip
1. **Due strati**: `temp_surface` reagisce rapidamente a attrito/frenata, `temp_core` ha inerzia maggiore e accumula calore dalla superficie.
2. **Bilancio energetico**: `dT/dt = (Heat_Gen - Heat_Loss) / Thermal_Mass` con contributi di curve (slip & lateral G), frenata (anteriore), convezione (velocità/aria) e conduzione (temperatura pista).
3. **Thermal factor**: curva gaussiana centrata sulla finestra termica ottimale della mescola, clampata per evitare valori >1.1/<0.7.
4. **Grip effettivo**: `effective_grip = base_grip * thermal_factor * wear_factor * setup_bonus`, dove `setup_bonus` deriva da bilanciamento aero, sospensioni e antiroll.
5. **Degrado**: `wear_rate_dynamic = wear_rate_base * pace_factor * handling_penalty * track_bumpiness_factor`, aggiornato per singolo segmento e usato per scalare `life_percent`.

#### 7.3.4 Integrazione dei multiplier Pirelli
1. **Estrazione**: leggere da ciascun mapping circuito i campi `soft_tire_multiplier`, `medium_tire_multiplier`, `hard_tire_multiplier` e renderli disponibili via `circuit_profile['tyre_package']`.
2. **Base grip**: `base_grip_compound = reference_grip * multiplier` dove `reference_grip` proviene dagli stessi file legacy.
3. **Wear baseline**: `wear_rate_compound = wear_ref * (1 + k_wear * (multiplier - 1))`, con `wear_ref` definito dal circuito o da default globali.
4. **Delta tempo attesi**: `delta_time_SM = (mult_soft - mult_medium) * lap_time_ref`, idem per SH/MH; salvati nel profilo circuito per AI/strategie.
5. **Bootstrap TyreModel**: quando `RaceCar.set_tire_compound` crea una gomma, inizializza `base_grip`, `wear_rate_base`, `lap_time_delta_hint` usando il pacchetto circuito corrente.
6. **Override/validazione**: confrontare i delta teorici con la telemetria reale; se lo scostamento supera soglia, permettere override manuali nel file circuito (`tyre_overrides`).

#### 7.3.5 Hook di simulazione
1. `TyreModel.update(delta_time, section, car_state, environment)` osserva il tipo di sezione (`Straight`, `SlowCorner`, ecc.), la velocità e i comandi (throttle/brake) per aggiornare temperature e usura.
2. I rettilinei incrementano la convezione (raffreddamento, soprattutto con DRS attivo); le curve assegnano più calore alla ruota esterna basandosi su `wheel_position` e direzione curva.
3. Il metodo restituisce `effective_grip` per ogni asse/ruota e i delta usura da applicare al calcolo tempi settore.

### 7.4 Pilota (v0.4)
- Riuso skill esistenti (`velocita`, `qualifica`, `gara`, `costanza`, `stile_sottosterzo/sovrasterzo`).
- Effetti:
  - Riduzione `handling_penalty` (pilota bravo sfrutta meglio bilanciamento non ideale).
  - Varianza minore nei tempi settore → maggiore consistenza.
  - Bonus situazionale (qualifica vs gara) selezionando skill appropriate.

## 8. Roadmap versioni
- **v0.1** (questo documento): auto – aerodinamica + regola DF/drag.
- **v0.2**: aggiungere motore/power unit nel calcolo (rettilinei, ERS, drag dinamico).
- **v0.3**: introdurre grip meccanico (ride height, antiroll, sospensioni avanzate) e collegarlo a gomme/degrado.
- **v0.4**: integrare completamente gomme (modello termico/degrado) e pilota (skill dinamiche).
- Versioni successive: meteo, track evolution, errori pilota, DRS/ERS dinamico.

## 9. Prossimi passi immediati
1. Implementare le classi `AeroPart`, `Suspension`, `CarAeroProfile` e integrarle in `RaceCar`.
2. Generare i coefficienti `v_base` e `curve_factor` per ogni sezione dai dataset esistenti (script helper).
3. Aggiornare il motore di simulazione per usare `v_section` in luogo dei bonus statici Auto.
4. Stendere gli scheletri dati per motore, grip meccanico, gomme e pilota (anche se non ancora implementati) per mantenere coerenza.
5. Validare su un circuito pilota confrontando i delta tra auto “high DF” e “low DF”.
