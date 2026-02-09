---
title: Setup Engine 2.0 – v0.1 (Auto/LapSimulator integration)
version: 0.1
last_updated: 2026-02-07
scope: "Ridefinire il motore di setup (UI + simulazione) per allinearlo alla nuova fisica LapSimulator e ai componenti Car"
---

## 1. Obiettivi
1. Esporre un modello di setup coerente con i componenti fisici descritti nel documento `lap-physics-spec-v0.5.md`.
2. Separare **input utente** (slider/UI) da **parametri fisici** usati nel LapSimulator (angle, ride height mm, duct opening, mappe PU/ERS).
3. Fornire un motore di scoring/calibrazione capace di suggerire range ottimali e di alimentare l’AI del setup engineer.
4. Integrare il motore con le nuove pipeline di validazione (component e system checks).

## 2. Architettura generale
```
SetupUI (Garage / Engineer Screen)
    │  slider events (front_wing, brake_duct, engine_map, ers_mode, ride_height, antiroll)
    ▼
SetupEngineService
    ├─ validate_input(circuit_constraints)
    ├─ map_slider_to_physics()
    ├─ evaluate_setup()  # punteggio + suggerimenti
    └─ persist_state(session_id)
        │
        ├─► Car.apply_setup_change()        # aggiorna componenti fisici
        └─► LapSimulator.InputMixer         # utilizza parametri convertiti
```

### 2.1 Componenti principali
- **SetupUI**: slider 1‑100 ma con etichette fisiche (°/mm) e range per circuito.
- **SetupEngineService**: microservizio (o modulo Python) che esegue validazioni, conversione 1‑100 → parametri fisici e calcola punteggio.
- **SetupPersistence**: salva per pilota/car session (`garage_state.json`).
- **SetupHarness**: script offline per generare heatmap/consigli.

## 3. Data model

| Campo UI            | Range UI | Parametro fisico                    | Conversione                         | Note |
|---------------------|----------|-------------------------------------|------------------------------------|------|
| `front_wing`        | 0-100    | `angle_deg` (0°-25°)                | `angle = angle_min + slider * step` | Aggiorna `front_wing.angle` (AeroComponent)
| `rear_wing`         | 0-100    | `angle_deg` (0°-35°)                | idem                                | Influenza drag + DRS range
| `beam_wing`         | 0-100    | `angle_deg` (0°-20°)                |                                     | Coupling con rear floor
| `ride_height_front` | 0-100    | `mm` (25-60)                        | `height = lin_interp(slider)`       | Limiti circuito in `circuit_profile`
| `ride_height_rear`  | 0-100    | `mm` (35-70)                        |                                     | Sinergia con sospensioni
| `suspension_front`  | 0-100    | `rigidity` + `efficiency`           | mappa logaritmica                   | Alimenta `suspension_front` component
| `suspension_rear`   | 0-100    | idem                                |                                     | -
| `antiroll_front`    | 0-100    | `rigidity`                          |                                     | Influenza handling penalty
| `antiroll_rear`     | 0-100    | `rigidity`                          |                                     | -
| `brake_balance`     | 0-100    | `bias_front_pct` (es. 52-58%)       | `bias = bias_min + slider * step`   | Range definito dal circuito
| `brake_duct`        | 0-100    | `duct_opening` (0-1)                | `opening = slider / 100`            | Usato da BrakeSystem
| `engine_map`        | discrete | `PowerUnit.set_maps(engine_map, ...)` | scegli `EngineMapConfig`            | Sempre deciso dal giocatore
| `ers_mode`          | discrete | `active_ers_mode`                   |                                     | -

> Tutti i driver sono definiti nei file `config/setup_mapping.json` per circuito/stato upgrade (permette override).

### 3.1 Campi UI esposti (garage)
- **Front Wing / Rear Wing / Beam Wing** – slider 0‑100 mappati su angoli reali (rispettivamente 0°‑25°, 0°‑35°, 0°‑20°). Aggiornano i componenti `FrontWing`, `RearWing`, `BeamWing` e influenzano direttamente DF/drag e l’aero balance calcolato dal LapSimulator.
- **Ride Height Front / Rear** – slider 0‑100 con range circuito (front 25‑60 mm, rear 35‑70 mm). Alimentano rake, rischio bottoming/porpoising e il coupling con il diffusore.
- **Suspension Front / Rear** – slider logaritmici che modificano `rigidity`+`efficiency`, utilizzati dal blocco Mechanical Grip (gestione bump/kerb e grip meccanico).
- **Antiroll Front / Rear** – slider rigidità barre antirolla (soft→hard). Regolano la stabilità in curva e l’handling penalty nello `update_section()`.
- **Brake Balance** – slider 0‑100 che mappa la percentuale di frenata sull’anteriore (es. 52‑58%), limitata dalla `bias_range` del circuito. Entra nella `BrakeSystem` per calcolare ripartizione di energia e termica freni.
- **Brake Duct Opening** – slider 0‑100 → apertura 0.0‑1.0, passato alla `BrakeSystem` per calcolare temperature, fade e cooling_penalty.

> **Esclusioni**: comandi `engine_map`, `ers_mode`, fuel load e pace level rimangono nel pannello gara (non fanno parte del Setup Engine). Il cooling bias front/rear non viene esposto nella maschera iniziale.

### 3.2 AeroPackage – formule e range fisici

| Componente       | Conversione slider → fisico                                                                                                     | Range base (override circuito)             | Note / effetto fisico |
|------------------|-------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------|-----------------------|
| Front Wing       | `angle = front_wing.min_deg + slider/100 * (max_deg - min_deg)`                                                                | Default 12°–28° (`step_deg = 0.25`), fino a 30° su piste ad alto carico | Contribuisce a `df_front = front_wing.downforce * sin(angle)` e influenza subito l’aero balance. |
| Rear Wing        | Idem con `rear_wing.min_deg/max_deg`                                                                                           | Default 10°–32° (fino a 35° per piste lenti) | Termina in `df_rear = rear_wing.downforce * sin(angle)` e regola il drag sensibile al DRS.| 
| Beam Wing        | Slider 0‑100 → `beam_angle = min + slider% * span`                                                                            | Default 4°–18°                              | Somma deportanza al retrotreno e stabilizza il diffusore, ma aumenta `drag_total`. |
| Ride Height F/R  | Interpolazione lineare su range circuito (`height = min_mm + slider% * span_mm`)                                              | Front 25‑60 mm / Rear 35‑70 mm (rake max 25 mm) | Fissa `rh_pen_front/rear = |height - rh_optimal| * 0.02` che riduce la deportanza disponibile. |
| Rake (derivato)  | `rake_mm = ride_height_rear - ride_height_front`; `rake_deg = atan(rake_mm / wheelbase_mm)` (wheelbase ≈ 3600 mm)              | +5 mm…+25 mm equiv. ≈0.08°–0.40°            | Valori estremi aumentano deportanza ma penalizzano drag e stabilità frenata. |
| Constraints      | `rake_mm` e `suspension_delta_limit` dal mapping circuito assicurano che la combinazione rimanga fisicamente valida             | Es. Monza `rake_mm` 5‑18 mm, Singapore 10‑22 mm | Usati da `validate_input()` per bloccare slider fuori specifica. |

**Relazione con l’AeroPackage LapSimulator**

- Il Setup Engine replica le formule del passo 3 (`AeroPackage.compute_forces`): `df_front`/`df_rear` sommano contributi ali + pavimento; poi vengono corretti da efficienza sospensioni e qualità assetto.¹
- Ride height/rake influiscono tramite i termini `rh_pen_front/rear`, riducendo la deportanza fino al 30 % se si esce dalle finestre ottimali sezione per sezione.¹
- Il drag finale è `drag_total = Σ component.drag` corretto per densità aria e slipstream; i cambi di angolo (specialmente rear/beam wing) aumentano il coefficiente di drag e riducono il cooling margin disponibile.¹
- Il bilanciamento aerodinamico utilizzato nei messaggi UI è `aero_balance = df_front_eff / (df_front_eff + df_rear_eff)`; spostarlo oltre ±0.05 rispetto al 50/50 alimenta handling penalty e segnali di under/oversteer inviati al TyreModel.¹

¹ Fonte: `docs/lap-physics-spec-v0.5.md`, §3.3 passo 3.

### 3.3 Power Unit – mapping ICE/ERS

| Input UI / parametro | Range / preset                                          | Conversione → fisica                                                                                                    | Impatto simulazione |
|----------------------|---------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|---------------------|
| `engine_map`         | Tabelle discrete (es. "Race", "Quali", "Safety")     | Seleziona `EngineMapConfig`: `power_percent`, `consumption_rate`, `heat_load`, `min/max_temp`.                           | Aggiorna `power_unit.ice.active_map`, da cui `torque_ice = torque_curve[rpm] * power_percent * (1 - wear*0.002)`.¹ |
| `ers_mode`           | `deploy`, `balanced`, `harvest`, `attack`, ecc.         | Mappa a `ErsMapConfig`: `output_kw`, `recovery_rate`, `heat_coeff`, `efficiency`.                                        | Determina `power_ers` e il delta SOC per sezione (`ers.consume(output_kw)` / `ers.harvest(recovery_rate)`).¹ |
| Brake Energy Target  | derivato da `brake_balance` + `brake_duct`              | Usa `brake_energy_recovery_kj` dal profilo circuito per dimensionare il recupero massimo in `DriverIntent`.              | Modula `mguk_state` e la temperatura freni; limita deploy se fade > soglia. |
| Cooling Guidance     | `Requirement` (low/medium/high) + `ΔTrack Temp`         | Somma al `cooling_margin`: `cooling_capacity = sidepods.cooling + engine_cover.cooling`, confrontato con `heat_load`.¹    | Se `cooling_margin < 0` viene applicato derating potenza e warning UI. |
| Fuel Burn slider²    | (futuro) 0‑3 step (Lean, Standard, Push)                 | Moltiplica `fuel_burn_rate = map.consumption_rate * fuel_bias`.                                                          | Influenza peso carburante e temperatura ICE. |

¹ Fonte: `docs/lap-physics-spec-v0.5.md`, §3.3 passo 4.

² Fuori scope UI attuale ma già previsto nel modello fisico (`DriverIntent.pace_factor`).

## 4. Motore di punteggio `evaluate_setup`

### 4.1 Input
```
SetupContext {
    circuit_profile: CircuitProfile
    car_state: CarDevelopmentState
    weather_profile: WeatherSnapshot
    driver_feedback: DriverFeedback (opzionale)
}
SetupConfig {
    front_wing, rear_wing, ride_height_front, ...
}
```

### 4.2 Output
```
SetupEvaluation {
    lap_time_delta: float  # s rispetto baseline
    tire_wear_delta: float
    fuel_delta: float
    stability_score: float
    aero_balance: float
    drag_index: float
    traction_index: float
    recommended_ranges: Dict[field, Range]
    messages: List[{severity, code, text}]
}
```

### 4.3 Algoritmo
1. Converte slider → parametri fisici con `map_slider_to_physics()`.
2. Calcola indicatori:
   - `aero_balance = df_front / (df_front + df_rear)` usando gli stessi calcoli del LapSimulator (riusa componenti `AeroComponent`).
   - `drag_index = drag_total / drag_ref`.
   - `traction_index = f(ride_height_rear, suspension_rear.rigidity, mechanical_grip)`.
3. Applica un modello lineare (versione semplificata del LapSimulator) per stimare `lap_time_delta`, `tire_wear_delta`, `fuel_delta` usando coefficienti per circuito (derivati dal doc principale).
4. Normalizza gli score in 5 categorie (Cornering, Straight-line speed, Traction, Stability, Brake cooling) per UI.
5. Propaga `recommended_ranges` basati su heatmap/harness.

## 5. Harness & Calibrazione setup
- Script `scripts/setup_heatmap.py` genera una griglia (es. step 5) e salva `heatmap_<circuit>.json`.
- Notebook `notebooks/setup/setup_analysis.ipynb` visualizza curve e aiuta a scegliere i range consigliati.
- File `config/setup_ranges/<circuit>.json` contiene per ogni slider: `min`, `max`, `target`, `tolerance`, `weight` (riutilizzati dall’attuale `evaluate_setup` UI).
- Suite test: `pytest tests/setup/test_evaluate_setup.py` (component) + `tests/setup/test_api_endpoints.py` (integrazione UI/server).

### 5.1 Workflow operativo
1. **Refresh dati** – eseguire `derive_setup_clusters.py` + `update_setup_mapping_from_profiles.py`; commitare `config/setup_mapping_v2.json` e report (`docs/setup_mapping_report.html`).
2. **Generazione heatmap** – per i circuiti target lanciare `scripts/setup_heatmap.py --circuit <slug>`; allegare l’output nella cartella `tmp/heatmap/`.
3. **Validazione** – importare i risultati nel notebook `notebooks/setup/setup_analysis.ipynb`, verificare che `recommended_ranges` ricadano entro i vincoli fisici e aggiornare `config/setup_ranges/`.
4. **CI setup-calibration** – job dedicato (da aggiungere alla pipeline) che esegue: lint → unit test SetupEngine → rigenera una heatmap rapida (step 10) → confronta i JSON con soglia `±0.5` sui target.
5. **Sign-off** – l’AI engineer valida i warning/notes generati dal job e aggiorna il changelog (sezione 8 di questo doc).

### 5.2 Ideal setup hierarchy (nuovo requisito)
- **Baseline circuito**: `config/setup/setup_ranges/<circuit>.json` definisce il target neutro per ciascun slider, coerente con i vincoli fisici del tracciato.
- **Offset team/auto**: ogni team/car development state applica correzioni (±2‑5 punti) per riflettere il DNA dell’auto (es. high‑DF vs low‑drag). Gli offset sono definiti in `config/setup/team_offsets.json` (da introdurre) e vengono sommati clamped 0‑100.
- **Offset pilota**: skill/stile pilota (`understeer_style`, `oversteer_style`, aggressività) aggiungono micro correzioni (±1‑3 punti) per personalizzare la preferenza di handling.
- **Combinazione**: `ideal_setup = clamp(baseline + team_offset + driver_offset, 0, 100)` e viene esposto sia nella UI (highlight target) sia nelle raccomandazioni ingegnere.
- **Persistenza**: gli offset applicati vanno salvati in `garage_state.json` per garantire coerenza fra sessioni.

## 6. Integrazione con LapSimulator
1. SetupUI salva i valori nello stato sessione.
2. `SetupEngineService.map_slider_to_physics()` chiama `Car.apply_setup_change()` che aggiorna gli oggetti `FrontWing`, `RearWing`, `Sidepods`, ecc.
3. `LapSimulator.InputMixer` legge i componenti già aggiornati (nessuna conversione runtime) e prosegue con la fisica.
4. Driver feedback (`setup_finding` skill) aggiunge messaggi contestuali che rimandano a slider specifici.

### 6.1 Orchestrazione (pseudocode)
```python
def run_lap_simulation(session_state: GarageSession, circuit: CircuitProfile, weather: WeatherSnapshot):
    setup_engine.validate_input(session_state.setup, circuit.constraints)
    physics_params = setup_engine.map_slider_to_physics(session_state.setup, circuit)
    car.apply_setup_change(physics_params)

    driver_intent = DriverModel.compute_inputs(session_state.driver, weather, session_state.strategy)
    lap_result = LapSimulator.run(
        circuit=circuit,
        car_state=car.export_state(),
        driver_intent=driver_intent,
        env_ctx=weather
    )

    evaluation = setup_engine.evaluate_setup(physics_params, lap_result.telemetry)
    return LapRunResult(lap_result, evaluation, session_state)
```

Key points:
- `map_slider_to_physics()` è chiamato **una sola volta** prima del LapSimulator per evitare branching runtime.
- `driver_intent` usa le stesse finestre di brake balance / ERS definite nel mapping circuito.
- `evaluate_setup()` riusa l’output sezione per calcolare `lap_time_delta`, `stability_score` e generare messaggi UI.

## 7. Collegamenti
- Documento fisico principale: `docs/lap-physics-spec-v0.5.md` (sezione 3.1, 3.3, 3.3.1) per capire l’impatto di ogni slider sulla fisica.
- Roadmap UI: `docs/setup-ui-plan.md` per l’evoluzione grafica.
- Pianificazione ricerca: `docs/setup-search-plan.md` (include la sequenza operativa già approvata).

## 8. Prossimi passi
1. Trasporre i vecchi slider nel nuovo mapping (definire file `config/setup_mapping_v2.json`).
2. Implementare `SetupEngineService` con API REST + socket feedback.
3. Aggiornare `evaluate_setup_categories` per usare gli indici fisici (`aero_balance`, `drag_index`, `traction_index`).
4. Integrare i test di calibrazione setup nella pipeline descritta al §3.5 del documento principale (nuovo job CI `setup-calibration`).
5. Documentare nella UI (tooltips + manuale ingegnere) come leggere gli indicatori.
