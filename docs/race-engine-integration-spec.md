---
title: Race Engine Integration – Fase C
version: 0.2
last_updated: 2026-02-10
branch: feature/race-engine
scope: "Collegare il LapSimulator (Fase B) al gioco esistente, sostituendo il vecchio motore semplificato"
---

## 1. Obiettivo

Integrare il nuovo motore fisico (`python_backend/lap_simulator/`) nel backend di gioco esistente (`python_backend/`), in modo che:
- Le sessioni di Practice (FP1/FP2/FP3) usino il LapSimulator reale al posto del modello semplificato `speed * dt`.
- Il frontend non richieda modifiche: le stesse API e socket continuano a funzionare.
- Il vecchio motore resti disponibile come fallback tramite un flag di configurazione.

---

## 2. TICK LOOP — Architettura fondamentale

> **REGOLA CHIAVE**: il LapSimulator NON calcola un giro intero in un colpo.
> Il game loop chiama `update_section()` **una sezione alla volta** per ogni auto,
> ad ogni tick. Le auto si muovono progressivamente sulla mappa.

### 2.1 Schema del tick loop

```
f1_manager_ai.py — race_simulation() — ogni 100ms reali
│
├─ dt_real = 0.1s
├─ sim_dt = dt_real × game_speed          (es. 0.5s a 5×)
│
├─ if paused: skip
│
└─ SessionBridge.tick(sim_dt)
   │
   │  ┌─────────────────────────────────────────────────────────┐
   │  │  FASE 1: ADVANCE TIME                                  │
   │  │  - PSO clock += sim_dt                                 │
   │  │  - AI scheduling check (ogni 30s sim)                  │
   │  │  - Pitlane release (PIT_QUEUE → ON_TRACK)              │
   │  └─────────────────────────────────────────────────────────┘
   │
   │  ┌─────────────────────────────────────────────────────────┐
   │  │  FASE 2: MOVE CARS (per ogni auto ON_TRACK)            │
   │  │                                                         │
   │  │  L'auto è nella sezione corrente (es. sec_05).          │
   │  │  La sezione ha dt_ref_s = tempo reale per percorrerla.  │
   │  │                                                         │
   │  │  car.section_time_acc += sim_dt                         │
   │  │                                                         │
   │  │  ► Interpolazione posizione (OGNI tick):                │
   │  │    fraction = section_time_acc / section_dt_ref          │
   │  │    distance = section_start_m + fraction × section_len   │
   │  │    speed = section.v_entry + fraction×(v_exit - v_entry) │
   │  │    → aggiorna RaceCar.distance_traveled e .speed        │
   │  │                                                         │
   │  │  ► Se section_time_acc >= section_dt_ref:               │
   │  │    SEZIONE COMPLETATA                                   │
   │  │    → chiama update_section() (8 passi fisici)           │
   │  │    → produce SectionResult (dt_s, v_exit, grip, etc.)   │
   │  │    → aggiorna CarState (gomme, freni, PU, fuel)         │
   │  │    → avanza a sezione successiva                        │
   │  │    → section_time_acc = 0 (o overflow)                  │
   │  │    → se ultima sezione del giro → LAP COMPLETE          │
   │  └─────────────────────────────────────────────────────────┘
   │
   │  ┌─────────────────────────────────────────────────────────┐
   │  │  FASE 3: BATTLE RESOLVER                                │
   │  │                                                         │
   │  │  Dopo che tutte le auto hanno aggiornato la posizione:  │
   │  │  - Detecta coppie vicine per distance_traveled          │
   │  │  - Calcola dirty air per auto dietro                    │
   │  │  - Se gap < soglia → risolvi duello                     │
   │  │  - Risultato: overtake/blocked/side-by-side/collision   │
   │  │  - Aggiorna posizioni (swap se overtake)                │
   │  └─────────────────────────────────────────────────────────┘
   │
   │  ┌─────────────────────────────────────────────────────────┐
   │  │  FASE 4: STATE COMMIT                                   │
   │  │                                                         │
   │  │  - Sync fasi PSO → RaceCar.state                       │
   │  │  - Aggiorna session_bests (lap, sectors)                │
   │  │  - Emit eventi (radio, battle, pit)                     │
   │  │  - Se giro completato:                                  │
   │  │    → append lap_time, sector_times                      │
   │  │    → aggiorna tire_wear, fuel_percent                   │
   │  │    → check se stint finito → IN_LAP → BOX              │
   │  └─────────────────────────────────────────────────────────┘
   │
   └─ Frontend riceve race_update via socket con posizioni aggiornate
```

### 2.2 Timing — come le sezioni mappano sui tick

Esempio: Monza, sezione sec_05 (MediumStraight), `dt_ref_s = 9.99s`, `length_m = 700.5m`

| game_speed | sim_dt per tick | tick per completare sec_05 | tick per 1 giro (~101s) |
|---|---|---|---|
| 1× | 0.1s | ~100 tick (10s reali) | ~1010 tick |
| 5× | 0.5s | ~20 tick (2s reali) | ~202 tick |
| 10× | 1.0s | ~10 tick (1s reale) | ~101 tick |
| 30× | 3.0s | ~3 tick (0.3s reali) | ~34 tick |

A 1× speed, le auto si muovono fluidamente (100 aggiornamenti posizione per sezione).
A 30× speed, le sezioni si completano in pochi tick ma il movimento resta visibile.

### 2.3 Stato per-auto nel tick loop

Ogni auto ON_TRACK mantiene:

```python
class CarTrackState:
    car_id: str
    current_section_idx: int      # indice sezione corrente (0..N-1)
    section_time_acc: float       # tempo accumulato nella sezione corrente
    lap_section_results: list     # SectionResult per sezioni completate nel giro
    lap_number: int               # giro corrente
    distance_in_lap: float        # distanza percorsa nel giro corrente (0..circuit_length)
    laps_done_in_run: int         # giri completati in questo run
    laps_planned: int             # giri pianificati per questo run
```

### 2.4 Completamento sezione — quando chiamare update_section()

```
section_time_acc += sim_dt

if section_time_acc >= section.dt_ref_s:
    # L'auto ha "percorso" tutta la sezione nel tempo simulato
    
    overflow = section_time_acc - section.dt_ref_s
    
    result = update_section(
        car_state, aero_setup, driver_skills,
        section, env, config,
        push_level, airflow_penalty, traffic_v_max
    )
    
    # result.dt_s è il tempo FISICO calcolato (può differire da dt_ref)
    # dt_ref è il riferimento telemetria; dt_s è il risultato della simulazione
    
    lap_section_results.append(result)
    current_section_idx += 1
    section_time_acc = overflow  # porta avanti il tempo residuo
    
    if current_section_idx >= len(sections):
        # GIRO COMPLETATO
        lap_time = sum(r.dt_s for r in lap_section_results)
        → commit lap, aggiorna RaceCar, reset per giro successivo
```

> **NOTA**: `dt_ref_s` determina QUANDO l'auto completa la sezione (timing di gioco).
> `update_section()` calcola il tempo FISICO `dt_s` che determina il lap time reale.
> Se l'auto è più veloce del riferimento, `dt_s < dt_ref_s` → lap time migliore.

### 2.5 Interpolazione posizione (movimento fluido)

Ad ogni tick, PRIMA di controllare il completamento sezione:

```python
section = sections[current_section_idx]
fraction = min(section_time_acc / section.dt_ref_s, 1.0)

# Posizione lungo il circuito
distance_in_section = fraction * section.length_m
distance_in_lap = section.start_m + distance_in_section

# Velocità interpolata (per animazione mappa)
speed_kph = section.v_entry_kph + fraction * (section.v_exit_kph - section.v_entry_kph)

# Aggiorna RaceCar
race_car.distance_traveled = distance_in_lap
race_car.speed = speed_kph / 3.6  # m/s
```

Questo garantisce che le auto:
- Si muovono fluidamente ad ogni tick (non a scatti)
- Rallentano nelle curve (v_entry > v_exit per curve)
- Accelerano nei rettilinei (v_entry < v_exit per rettilinei)

---

## 3. Architettura attuale (V1 — backup in `*_v1.py`)

### 3.1 Modello auto: `RaceCar` (`models/models.py`)
- ~30 campi letti dal frontend: `state`, `distance_traveled`, `speed`, `lap_times`, `sector_times`, `tire_temps`, `tire_wear`, `fuel_percent`, `setup_feedback`, etc.
- Tempi generati con formula semplice + random.

### 3.2 Loop simulazione V1: `update_car_position()` (`utils/simulation_v1.py`)
- Tick-based: `distance += speed * dt`.
- Check sector crossing per distanza.
- Stato macchina: BOX → OUT_LAP → HOT_LAP → IN_LAP → BOX.

### 3.3 Stato sessione: `game_logic.py`
- Variabili globali: timer, pausa, speed multiplier, lista 20 `RaceCar`.
- `start_session_for_circuit()` resetta tutto.

### 3.4 API: `routes/api.py`
- `/api/cars` → posizioni, tempi, gomme, setup.
- `/api/circuit/<id>` → carica circuito e avvia sessione.
- Socket bridge per aggiornamenti real-time.

---

## 4. Architettura target (V2)

### 4.1 Motore fisico (Fase B — già implementato)
- `update_section()` → 8 passi fisici per una sezione (driver, aero, PU, tyres, brakes, time, state, return).
- `AIDriverEngine` → programmi AI (setup validation, tyre deg, quali sim, race trim).
- `BattleResolver` → interazioni multi-car (dirty air, sorpassi, collisioni).
- `PracticeSessionOrchestrator` → clock, pitlane queue, tyre inventory, run management.

### 4.2 Layer di integrazione

```
┌─────────────────────────────────────────────────┐
│  Frontend (invariato)                           │
│  socket_bridge.js / API calls                   │
├─────────────────────────────────────────────────┤
│  f1_manager_ai.py (tick loop 100ms)             │
│  api.py (send_out/box delegano a bridge)        │
│  game_logic.py (USE_NEW_ENGINE flag)            │
├─────────────────────────────────────────────────┤
│  SessionBridge (NUOVO)                          │
│  ├── tick(sim_dt):                              │
│  │   ├── FASE 1: advance time + AI scheduling   │
│  │   ├── FASE 2: move cars (per-section)        │
│  │   ├── FASE 3: BattleResolver                │
│  │   └── FASE 4: state commit                  │
│  ├── adapter.py: RaceCar ↔ CarEntry            │
│  ├── CarTrackState per auto (section tracking)  │
│  ├── PracticeSessionOrchestrator                │
│  ├── AIDriverEngine (×18 AI)                   │
│  └── TyreInventory (×10 team)                  │
├─────────────────────────────────────────────────┤
│  lap_simulator/                                 │
│  ├── update_section.py (chiamato 1× per sezione)│
│  ├── battle_resolver.py                         │
│  ├── tyre_model.py, brake_system.py, etc.       │
│  └── data_types.py (CarState, SectionResult)    │
└─────────────────────────────────────────────────┘
```

---

## 5. Componenti da implementare

### 5.1 Adapter (`adapter.py`) — ✅ Implementato
- `pilot_to_driver_skills(pilot) → DriverSkills`
- `racecar_to_car_entry(car) → CarEntry`
- `apply_section_result_to_racecar(car, result, section)` — aggiorna posizione/speed per tick
- `apply_lap_complete_to_racecar(car, lap_results)` — aggiorna tempi/gomme/fuel a fine giro
- `set_racecar_phase(car, phase)` — PSO phase → game CarState
- Compound mapping: SOFT/MEDIUM/HARD ↔ C4/C3/C2

### 5.2 Session Bridge (`session_bridge.py`) — da riscrivere con tick per-sezione
- `init_session(circuit_id, race_cars, session_type)` → crea PSO, AI engines, carica config
- `tick(sim_dt)` → il loop a 4 fasi descritto in §2.1
- `player_send_out(car, compound, fuel, laps)` → manda player in pista
- `player_box_now(car)` → richiama player ai box
- `get_leaderboard()`, `get_session_summary()` → query per API

### 5.3 CarTrackState (NUOVO — stato per-auto nel tick loop)
Traccia la posizione di ogni auto nella griglia di sezioni:
- `current_section_idx` — sezione corrente
- `section_time_acc` — tempo accumulato nella sezione
- `lap_section_results` — risultati sezioni completate nel giro corrente
- `distance_in_lap` — posizione lungo il circuito (per mappa)

### 5.4 Modifiche backend — ✅ Implementato
- `game_logic.py`: `USE_NEW_ENGINE` flag, `session_bridge` global, init on circuit load
- `f1_manager_ai.py`: V2 tick path con pause check, fallback a V1
- `api.py`: send_out/box delegano a SessionBridge quando attivo

### 5.5 Mapping campi RaceCar ↔ LapSimulator

| Campo RaceCar | Fonte V2 | Quando aggiornato |
|---|---|---|
| `distance_traveled` | interpolazione sezione (§2.5) | **ogni tick** |
| `speed` | interpolazione v_entry→v_exit (§2.5) | **ogni tick** |
| `state` | PSO CarPhase → CarState | ogni tick (sync) |
| `lap_times` | `sum(r.dt_s for r in lap_results)` | a fine giro |
| `sector_times` | somma dt_s per sezioni nel settore | a fine giro |
| `best_sectors` | min per settore | a fine giro |
| `tire_wear` | `CarState.tyre.wear_pct` | a fine sezione |
| `tire_temps` | `CarState.tyre.surface_temp_c` | a fine sezione |
| `tire_age` | incrementato a fine giro | a fine giro |
| `fuel_percent` | `PUState.fuel_kg / fuel_max × 100` | a fine sezione |
| `current_tire` | compound mapping | a cambio gomme |
| `setup_feedback` | AIDriverEngine adjustments | a fine run |
| `last_driver_feedback` | BattleEvent.message | a fine duello |

---

## 6. Fasi di implementazione

### 6.1 ✅ Step 1 — Backup V1 + E2E test standalone
- Backup file V1 (`*_v1.py`)
- Test E2E con 4 auto su Monza (PSO + AI + LapSim + Battle)
- 192/192 test passing

### 6.2 ✅ Step 2 — Adapter + Session Bridge v1 (giro intero)
- `adapter.py` e `session_bridge.py` implementati
- Backend integration (game_logic, f1_manager_ai, api)
- 20 auto funzionanti su Suzuka (~91.5s)

### 6.3 🔄 Step 3 — Session Bridge v2 (tick per-sezione)
- Riscrivere `session_bridge.py` con il tick loop a 4 fasi (§2.1)
- Implementare `CarTrackState` per tracking sezione
- Interpolazione posizione fluida (§2.5)
- BattleResolver per-tick basato su distance_traveled
- Le auto si muovono sulla mappa in tempo reale

### 6.4 Step 4 — Polish e fallback
- Verifica tutti i campi frontend
- Gestione errori e fallback al vecchio motore
- Performance profiling (20 auto × tick)
- Sector crossing detection per timing panel

---

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Performance (20 auto × tick × interpolazione) | update_section() chiamato solo a fine sezione, non ogni tick |
| Sincronizzazione BattleResolver con posizioni | Battle check dopo che tutte le auto hanno aggiornato la posizione |
| dt_ref vs dt_s divergenza | dt_ref controlla il timing di gioco; dt_s il lap time fisico |
| Sector crossing detection | Usa sector_markers_m dal circuito, check distance_in_lap |
| Compound mapping (S/M/H → C1-C6) | Configurabile per evento, default C3/C4/C5 |

## 8. Dipendenze

- ✅ LapSimulator v0.2 con `update_section()` (Fase B)
- ✅ AIDriverEngine (Fase B)
- ✅ BattleResolver 2.0 (Fase B)
- ✅ PracticeSessionOrchestrator (Fase B)
- ✅ TyreModel v2 (Fase B)
- ✅ SetupEngineService (Fase A)
- ✅ Telemetry Sections v2 — 24 circuiti con `dt_ref_s`, `v_entry/exit/min/max`, copertura 100%
- ✅ Backup V1 engine (`*_v1.py`)
