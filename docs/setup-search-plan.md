# Piano sviluppo ricerca setup semplificata
Questo piano descrive come introdurre subito una ricerca setup funzionante usando un modello di punteggio semplificato, mantenendo l’architettura pronta per la futura fisica completa.

## Obiettivi e deliverable
1. Esporre leve di setup persistenti per ciascuna auto giocatore (front/rear wing, ride height F/R, suspension F/R).
2. Integrare un motore di punteggio semplificato che produca delte coerenti su ritmo, usura gomme e fuel.
3. Restituire al giocatore feedback e range consigliati basati su tale punteggio.
4. Fornire un harness offline per generare heatmap e best range per ogni circuito/stato sviluppo.

## Sequenza operativa
1. **Persistenza e API setup**
   - Strutturare i campi setup su `RaceCar` + storage stato sessione.
   - Aggiungere endpoint REST `/api/player/car/<driver>/setup` con validazioni (in box / parc fermé).
   - Estendere `race_update` con payload `setup` e `recommended_range` placeholder.
2. **Motore punteggio semplificato**
   - Funzione `evaluate_setup(config, circuit_state, car_dev_level)` calcola: `lap_time_delta`, `tire_wear_delta`, `fuel_delta`, `stability_score` usando coefficienti lineari (derivati dal doc tecnico).
   - Definire `score = w_time * lap_time_delta + w_wear * tire_wear_delta + w_stability * stability_score` con pesi iniziali.
   - Collegare il motore al loop simulazione Practice per aggiornare l’auto a ogni run.
3. **Feedback e UI**
   - Tradurre deviazioni (es. `aero_balance`, `drag_index`, `traction_index`) in categorie MVP (`Cornering balance`, `Straight-line speed`, ecc.).
   - Inviare `{color, message}` via SocketIO; aggiornare `PlayerGarage` per mostrare slider setup + indicatori #range best.
4. **Harness automatico**
   - Script `scripts/setup_heatmap.py` che itera su una griglia di valori, chiama `evaluate_setup`, salva CSV/JSON con score.
   - Generare e versionare i range consigliati per circuito/stato sviluppo (pre-upgrade, post-upgrade aero, ecc.).
   - Collegare l’harness a un comando npm/pip per esecuzioni batch.
5. **Coefficiente e tuning**
   - Creare file config (es. `data/setup_coefficients/<circuit>.json`) con target `aero_balance`, `drag_window`, `ride_height_bounds`, moltiplicatore sviluppo.
   - Introdurre tabella dei bonus upgrade (nuovo fondo, sospensioni, PU) che modifica i baseline caricati dal motore.

## Test e validazione
- Unit test Python per `evaluate_setup` (coerenza segni e boundary).
- Test end-to-end REST + SocketIO (simulare run, verificare feedback UI).
- Harness: confronto contro range attesi, generazione report PASS/FAIL.

## Fuel Learning Mechanic (Next Development)
### Obiettivi
1. Tracciare il consumo reale di carburante durante i giri hot
2. Stimare il numero massimo di giri stint basandosi sul carburante attuale
3. Fornire avvisi quando il pilota imposta stint target superiori alla stima
4. Integrare il sistema con il setup feedback e la UI del garage

### Implementazione tecnica
**Backend (`models/models.py`)**
- Estendere `RaceCar` con attributi fuel learning:
  - `fuel_learning_samples: List[float]` - consumi per giro
  - `fuel_learning_hot_laps: int` - contatore giri hot
  - `fuel_consumption_per_lap: Optional[float]` - media consumi
  - `fuel_estimate_laps_at_100: Optional[int]` - stima giri al 100%
- Modificare `consume_fuel()` per chiamare `_track_fuel_learning()` solo su HOT LAP
- Implementare `_track_fuel_learning()` per raccogliere campioni e calcolare media
- Aggiungere `reset_fuel_learning()` per reset su cambiamenti significativi setup
- Esporre campi in socket payload: `fuel_learning_hot_laps`, `fuel_estimate_ready`, `fuel_estimate_laps_at_100`

**Frontend (`player_garage_v3.js`)**
- Aggiungere logica UI per stato "Learning" vs "Ready"
- Mostrare contatore progress: `Fuel learning 3/5`
- Visualizzare stinta massima: `Est. max 12 laps with 85% fuel`
- Implementare warning per stint target eccessivo
- Aggiornare fingerprint rendering per includere fuel learning fields

**Stile (`dashboard-v3.css`)**
- Classi per `.fuel-pill-v3`, `.fuel-pill-ready`, `.fuel-pill-learning`
- Stili per `.stint-helper-v3`, `.stint-warning-v3`
- Evidenziazione input quando warning attivo

### Logica di funzionamento
1. **Fase learning (primi 5 giri hot)**:
   - Ogni giro hot registra consumo percentuale
   - UI mostra进度 "Fuel learning X/5"
   - Input stint limitato a 99 (nessun limite ancora)

2. **Fase ready (dopo 5 giri)**:
   - Calcola media consumi e stima giri massimi
   - UI mostra "Fuel est. ready – max 12 laps"
   - Input stint limitato al valore stimato
   - Warning se pilota supera limite

3. **Reset conditions**:
   - Cambiamento ≥3 slider setup con delta ≥5
   - Cambio mappatura ICE
   - Non resetta su ERS o fuel percent changes

### Debug e logging
- Backend: log `fuel_burn` events con `learn_hot_laps`, `learn_samples`, `learn_ready`
- Frontend: console log player team e fuel learning status
- Verifica `is_player_controlled` flag correttamente impostato

## Rischi e mitigazioni
1. **Coefficiente poco realistico** → iniziare con valori conservative, prevedere file configurabili.
2. **UI sovraccarica** → introdurre slider solo dopo payload stabile, usare tooltips per messaggi estesi.
3. **Prestazioni harness** → limitare la griglia (es. step 5) e supportare campionamento random.
4. **Fuel learning accuracy** → implementare finestra mobile (12 campioni) per evitare valori obsoleti.
