---
description: race module architecture overview
---

# Race Module Architecture (FE + BE)

## 1. Overview
The race module simula in tempo reale una sessione di pista e sincronizza i dati tra backend Flask/Socket.IO e la UI V3. Gli obiettivi principali sono:
- calcolare continuamente lo stato di ogni vettura (posizione, stint, feedback setup);
- distribuire aggiornamenti in push ai client tramite eventi `race_update`;
- permettere al giocatore di comandare i propri piloti (setup, send out, energy modes) con feedback immediato sull'interfaccia V3.

Componenti macro:
1. **Backend Simulation Layer** – loop di simulazione, modello `RaceCar`, gestione setup/telemetria, API REST e logging.
2. **Transport Layer** – Socket.IO per race updates + REST per comandi e setup.
3. **Frontend V3 Layer** – `dashboard-v3.js` e moduli (Map, Timing, Garage, SessionControls, SocketBridge) che consumano lo stato condiviso `AppState`.

## 2. Backend Architecture

### 2.1 Entry Point e Thread simulazione
- File: `python_backend/f1_manager_ai.py`.
- Inizializza Flask + SocketIO, registra le route (`routes/api.py`) e avvia il thread `race_simulation()`.
- Il loop gira ogni 100ms, aggiorna ciascuna `RaceCar` (via `utils.update_car_position`) e invia l’evento `race_update` con:
  - elenco completo delle auto (`cars_data`), uno snapshot con informazioni di stato + player config;
  - tempo sessione residuo formattato;
  - `game_speed`, `is_paused`, `session_bests` per colori timing.

### 2.2 Modello `RaceCar`
- File: `python_backend/models/models.py`.
- Contiene lo stato persistente di ogni vettura: driver/team, fuel, tire, state, flag `has_completed_hot_lap`, `player_config`, `setup_feedback`.
- Metodi chiave:
  - `update_position` (in `utils/simulation.py`) aggiorna distanza, lap type, transizioni OUT/HOT/IN.
  - `enter_box()` imposta `state=BOX` e, se auto player e `has_completed_hot_lap`, richiama `_generate_setup_feedback(trigger='box_entry')` che
    - valuta il setup tramite `utils.setup_engine.evaluate_setup` e aggiorna `setup_feedback`;
    - registra log strutturati (`setup_feedback_generated`).
  - `complete_lap()` aggiorna telemetria e setta `has_completed_hot_lap=True` quando un HOT LAP termina.
- Ogni vettura ha il proprio flag, quindi i due piloti del giocatore restano indipendenti.

### 2.3 API REST rilevanti
Tutte definite in `routes/api.py`.
1. `POST /api/player/car/<driver>/setup/save`
   - Valida payload slider, richiede auto in BOX, aggiorna `player_config.setup`, ritorna l’intero car payload aggiornato.
   - Log `setup_saved` nel file `/tmp/f1_setup_debug.log`.
2. `POST /api/player/car/<driver>/setup`
   - Storico endpoint usato per generare feedback. Ora chiamato solo dalla telemetria (tramite `_generate_setup_feedback`) ma resta disponibile per debug/manual trigger.
3. Comandi gara (es. send out, box, energy modes)
   - Aggiornano `player_config` e l’oggetto `RaceCar`; su conferma restituiscono lo stato aggiornato che il frontend applica localmente.

### 2.4 Logging & Monitoring
- File `python_backend/debug_log.py` fornisce `log_debug_event` che scrive JSON lines in `/tmp/f1_setup_debug.log`.
- Eventi chiave: `car_reset`, `lap_transition`, `setup_saved`, `setup_feedback_generated`, `setup_feedback_error`.
- Utilizzati per correlare azioni UI e stato simulazione durante il debug di feedback setup o send-out.

## 3. Frontend Architecture (V3)

### 3.1 Ingresso e stato condiviso
- File: `python_backend/static/js/dashboard-v3.js`.
- Istanzia `AppState` (store globale), `SocketBridge`, `MapModuleV3`, `TimingPanelV3`, `PlayerGarageV3`, `SessionControls`.
- `AppState` (file `static/js/modules/app_state.js`) mantiene
  - mappa `playerCars` (key = driver number);
  - `sessionBests`, `sessionStatus`, opzioni UI.
- Ogni modulo si iscrive ai cambiamenti dello store tramite metodi `state.set...` seguiti da `render()`.

### 3.2 SocketBridge
- File: `static/js/modules/socket_bridge.js`.
- Si connette al backend via Socket.IO e ascolta `race_update`.
- Aggiorna `AppState` con:
  - `state.setSessionBests`, `state.setCars(cars)`;
  - invoca `garage.applyLocalCarState` per ogni player car (sincronizza setup, feedback, stato). 
- Emette eventi console utili al debug (es. log se manca `setup_recommendation`).

### 3.3 Moduli UI principali
1. **MapModuleV3** – disegna pista e posizioni auto, usa `cars.position` e `team_color` per icone.
2. **TimingPanelV3** – mostra la tabella tempi, utilizza `session_bests` per colorare settori, e `state.is_player_controlled` per highlight.
3. **PlayerGarageV3** – UI dei comandi pilota:
   - Card status (fuel, tires, stint laps).
   - Pulsanti `Send Out`, `Box`, `Setup`.
   - **Setup overlay**: costruisce slider leggendo `player_config.setup` e feedback. Dopo Apply chiama `/setup/save`; all’arrivo del payload aggiorna `AppState` e ricalcola colori.
   - Gestisce due piloti separati (driverNumber 16/55) usando la chiave `data-driver` e `AppState.getPlayerCar`.
4. **SessionControls** – comandi globali (play/pause, game speed) che invocano le relative route.

### 3.4 Flusso Setup end-to-end
1. Giocatore apre Setup (auto in BOX). Overlay carica:
   - valori correnti da `car.player_config.setup`;
   - feedback/categorie da `car.setup_recommendation` se presenti.
2. Modifica slider → `BuildSetupPayloadFromDraft`.
3. `Apply` → `fetch('/setup/save')`. Risposta include `car` aggiornato.
4. `PlayerGarageV3.applyLocalCarState` aggiorna `AppState` → UI mostra valori salvati.
5. Auto esce, completa hot lap, rientra box: `_generate_setup_feedback` elabora nuove raccomandazioni, inviate nel successivo `race_update`. UI ricolora slider mantenendo i valori salvati.

### 3.5 Altri flussi
- `Send Out` chiama l’endpoint corrispondente; la risposta aggiorna `state`, ma anche il successivo `race_update` conferma `state='OUT_LAP'`.
- `SocketBridge` gestisce anche `session_time_remaining` per il timer countdown (60 minuti) e passa i dati a `TimingPanelV3`.

## 4. Data Flow sintetico
```
Player action (Apply) ──REST──> /setup/save ──┐
                                             │
Backend `RaceCar` state <──Socket── race_update◄── Simulation loop
                                             │
Telemetry (hot lap + box) ──> `_generate_setup_feedback()` ──┘
```
- Eventi che richiedono conferma immediata (setup save, send out) usano REST.
- Tutte le UI autosincronizzate ascoltano `race_update` che funge da verità unica per stato auto/sessione.

## 5. Testing & Troubleshooting
1. **Functional**
   - Flow completo: setup → send out → hot lap → box → verifica feedback colori.
   - Ripetere con entrambi i piloti per validare isolamento stato.
2. **Logging**
   - Monitorare `/tmp/f1_setup_debug.log` per correlare `setup_saved`, `lap_transition`, `setup_feedback_generated`.
3. **Socket**
   - Verificare che i client ricevano `race_update` ogni 100ms (più lento in produzione se necessario) e che il timer scenda correttamente.
4. **UI**
   - Testare overlay in BOX vs in pista; slider devono sempre mostrare il valore reale salvato; badge “Recommended” opzionale aiuta a capire delta.

---

Document last updated: Feb 5, 2026.
