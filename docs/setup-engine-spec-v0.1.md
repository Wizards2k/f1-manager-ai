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
| `brake_duct`        | 0-100    | `duct_opening` (0-1)                | `opening = slider / 100`            | Usato da BrakeSystem
| `engine_map`        | discrete | `PowerUnit.set_maps(engine_map, ...)` | scegli `EngineMapConfig`            | Sempre deciso dal giocatore
| `ers_mode`          | discrete | `active_ers_mode`                   |                                     | -

> Tutti i driver sono definiti nei file `config/setup_mapping.json` per circuito/stato upgrade (permette override).

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

## 6. Integrazione con LapSimulator
1. SetupUI salva i valori nello stato sessione.
2. `SetupEngineService.map_slider_to_physics()` chiama `Car.apply_setup_change()` che aggiorna gli oggetti `FrontWing`, `RearWing`, `Sidepods`, ecc.
3. `LapSimulator.InputMixer` legge i componenti già aggiornati (nessuna conversione runtime) e prosegue con la fisica.
4. Driver feedback (`setup_finding` skill) aggiunge messaggi contestuali che rimandano a slider specifici.

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
