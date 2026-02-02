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

## Rischi e mitigazioni
1. **Coefficiente poco realistico** → iniziare con valori conservative, prevedere file configurabili.
2. **UI sovraccarica** → introdurre slider solo dopo payload stabile, usare tooltips per messaggi estesi.
3. **Prestazioni harness** → limitare la griglia (es. step 5) e supportare campionamento random.
