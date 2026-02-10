---
title: Race Engine Integration – Fase C
version: 0.1
last_updated: 2026-02-10
branch: feature/race-engine
scope: "Collegare il LapSimulator (Fase B) al gioco esistente, sostituendo il vecchio motore semplificato"
---

## 1. Obiettivo

Integrare il nuovo motore fisico (`python_backend/lap_simulator/`) nel backend di gioco esistente (`python_backend/`), in modo che:
- Le sessioni di Practice (FP1/FP2/FP3) usino il LapSimulator reale al posto del modello semplificato `speed * dt`.
- Il frontend non richieda modifiche: le stesse API e socket continuano a funzionare.
- Il vecchio motore resti disponibile come fallback tramite un flag di configurazione.

## 2. Architettura attuale (da sostituire)

### 2.1 Modello auto: `RaceCar` (`models/models.py`)
- ~30 campi letti dal frontend: `state`, `distance_traveled`, `speed`, `lap_times`, `sector_times`, `tire_temps`, `tire_wear`, `fuel_percent`, `setup_feedback`, etc.
- Logica di sessione embedded: `exit_box()`, `enter_box()`, `complete_lap()`, `update_tire_wear()`.
- Tempi generati con formula semplice + random: `realistic_lap_time = 79.5 + random.uniform(-2.5, 2.5)`.

### 2.2 Loop simulazione: `update_car_position()` (`utils/simulation.py`)
- Tick-based: `distance += speed * dt`.
- Check sector crossing per distanza.
- Stato macchina: BOX → OUT_LAP → HOT_LAP → IN_LAP → BOX.

### 2.3 Stato sessione: `game_logic.py`
- Variabili globali: timer, pausa, speed multiplier, lista 20 `RaceCar`.
- `start_session_for_circuit()` resetta tutto.
- `set_game_speed()`, `toggle_pause()` gestiscono il tempo.

### 2.4 API: `routes/api.py`
- `/api/cars` → posizioni, tempi, gomme, setup.
- `/api/circuit/<id>` → carica circuito e avvia sessione.
- `/api/toggle_pause`, `/api/game_speed` → controlli sessione.
- Socket bridge per aggiornamenti real-time.

## 3. Architettura target

### 3.1 Nuovo motore (già implementato, Fase B)
- `LapSimulator` → fisica per sezione (8 passi).
- `AIDriverEngine` → programmi AI (setup validation, tyre deg, quali sim, race trim).
- `BattleResolver` → interazioni multi-car (dirty air, sorpassi, collisioni).
- `PracticeSessionOrchestrator` → clock, pitlane queue, tyre inventory, run management.

### 3.2 Layer di integrazione (da implementare)

```
┌─────────────────────────────────────────────┐
│  Frontend (invariato)                       │
│  socket_bridge.js / API calls               │
├─────────────────────────────────────────────┤
│  api.py (modifiche minime)                  │
│  game_logic.py (delega a SessionBridge)     │
├─────────────────────────────────────────────┤
│  SessionBridge (NUOVO)                      │
│  ├── adapter.py: RaceCar ↔ CarEntry        │
│  ├── PracticeSessionOrchestrator            │
│  ├── AIDriverEngine (×18 AI)               │
│  ├── LapSimulator + BattleResolver         │
│  └── TyreInventory (×10 team)              │
├─────────────────────────────────────────────┤
│  lap_simulator/ (invariato, Fase B)         │
└─────────────────────────────────────────────┘
```

## 4. Componenti da implementare

### 4.1 Adapter (`adapter.py`)
- `racecar_to_car_entry(car: RaceCar, config: CircuitConfig) → CarEntry`
  - Mappa compound (SOFT/MEDIUM/HARD → C3/C4/C5 per evento).
  - Mappa setup slider → `AeroSetup` (usa `SetupEngineService`).
  - Mappa pilot skills → `DriverSkills`.
  - Mappa fuel_percent → fuel_kg.
  - Crea `CarState` con stato gomme/freni/PU iniziale.

- `lap_result_to_racecar(result: LapResult, car: RaceCar)`
  - Aggiorna `lap_times`, `sector_times`, `best_sectors`.
  - Aggiorna `tire_wear`, `tire_temps`, `tire_age`.
  - Aggiorna `fuel_percent`.
  - Aggiorna `state` (HOT_LAP, IN_LAP, BOX).
  - Aggiorna `distance_traveled` per posizione su mappa.
  - Popola `battle_events` per HUD.

### 4.2 Session Bridge (`session_bridge.py`)
- Classe `SessionBridge` che wrappa tutto il nuovo motore.
- `init(circuit_id, race_cars, session_type)` → crea PSO, registra team, crea AIDriverEngine per ogni AI car.
- `tick(dt)` → avanza PSO, schedula run AI, esegue laps via LapSimulator, aggiorna RaceCar.
- `request_player_run(car, compound, fuel, laps)` → interfaccia per comandi player.
- `get_leaderboard()`, `get_session_summary()` → query per API.

### 4.3 Modifiche backend
- `game_logic.py`: `start_session_for_circuit()` crea `SessionBridge` se flag attivo.
- `simulation.py`: `update_car_position()` delega a `SessionBridge.tick()` se attivo.
- `api.py`: nuova route `/api/session/engine` per query/switch motore.
- `config.py`: flag `USE_NEW_ENGINE = True`.

### 4.4 Mapping campi RaceCar ↔ LapSimulator

| Campo RaceCar | Fonte LapSimulator | Note |
|---|---|---|
| `state` (BOX/OUT_LAP/HOT_LAP/IN_LAP) | `CarSessionState.phase` | Mapping diretto |
| `distance_traveled` | `section_progress × circuit_length` | Per posizione su mappa |
| `speed` | `SectionResult.v_effective_kph / 3.6` | m/s per animazione |
| `lap_times` | `LapResult.lap_time_s` | Append |
| `sector_times` | `LapResult.sector_times_s` | 3 settori |
| `best_sectors` | Min per settore | Calcolato |
| `tire_wear` | `avg_tyre_wear_pct / 100` | 0-1 |
| `tire_temps` | `TyreState.surface_temp_c` per wheel | FL/FR/RL/RR |
| `tire_age` | `TyreState.lap_age` | Laps |
| `fuel_percent` | `PUState.fuel_kg / fuel_max_kg × 100` | % |
| `current_tire` | `TyreState.compound` → TireCompound | Mapping enum |
| `setup_feedback` | `AIDriverEngine.complete_run()` adjustments | Solo AI |
| `last_driver_feedback` | `BattleEvent.message` | Radio messages |

## 5. Fasi di implementazione

### 5.1 Step 1 — Test end-to-end standalone
- Script che simula FP1 con 4 auto su Monza usando tutti i moduli.
- Valida che PSO → AIDriverEngine → LapSimulator → BattleResolver funzionano insieme.
- Nessuna modifica al gioco.

### 5.2 Step 2 — Adapter + Session Bridge
- Implementa `adapter.py` e `session_bridge.py`.
- Test unitari per mapping bidirezionale.

### 5.3 Step 3 — Backend integration
- Modifica `game_logic.py` e `simulation.py`.
- Flag `USE_NEW_ENGINE`.
- Test con il gioco nel browser.

### 5.4 Step 4 — Polish e fallback
- Verifica tutti i campi frontend.
- Gestione errori e fallback al vecchio motore.
- Performance profiling (20 auto × tick).

## 6. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Campi RaceCar mancanti nel mapping | Tabella §4.4 come checklist, test per ogni campo |
| Performance (20 auto × sezioni × tick) | LapSimulator già ottimizzato; profiling dopo Step 3 |
| Compound mapping (S/M/H → C1-C6) | Configurabile per evento, default C3/C4/C5 |
| Setup slider → AeroSetup | Usa SetupEngineService già implementato |
| Tempi non realistici | Già calibrato su 24 circuiti (Fase B) |

## 7. Dipendenze

- ✅ LapSimulator v0.2 (Fase B)
- ✅ AIDriverEngine (Fase B)
- ✅ BattleResolver 2.0 (Fase B)
- ✅ PracticeSessionOrchestrator (Fase B)
- ✅ TyreModel v2 (Fase B)
- ✅ SetupEngineService (Fase A)
- Config circuito telemetry JSON (24 circuiti disponibili)
