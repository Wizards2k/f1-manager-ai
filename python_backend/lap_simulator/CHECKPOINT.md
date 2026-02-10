# LapSimulator Runtime — Checkpoint 2026-02-10

## Branch: `feature/lapsimulator-runtime`

## Stato: 🔧 IN CORSO — modello dt_ref integrato, tuning coefficienti da fare

---

## Cosa è stato fatto

### LapSimulator v0.1 — Modulo standalone completo
- **85/85 test passano** (unit + integrazione Monza)
- 8 moduli Python in `python_backend/lap_simulator/`:
  - `data_types.py` — 30+ dataclass, enum, helpers
  - `config_loader.py` — carica JSON circuito + profili derivati
  - `aero_package.py` — Passo 3: DF/drag/balance/handling/cooling
  - `power_unit.py` — Passo 4: ICE+ERS, termica, fuel, derating
  - `tyre_model.py` — Passo 5a: termica 2 strati, grip, usura
  - `brake_system.py` — Passo 5b: termica freni, fade, efficienza
  - `driver_model.py` — Passo 2: decisione pilota
  - `update_section.py` — orchestrazione Passi 1-8
  - `lap_simulator.py` — runtime loop completo

### 3 Bug trovati e risolti
1. **Velocità curve esplode** — DF calcolato come forza fisica (×dyn_pressure) invece di punti aero → fix: rimosso dyn_pressure, usato speed_factor
2. **Brake fade non rilevato** — soglia evento troppo alta (0.1 vs fade reale 0.03) → fix: soglia a 0.01
3. **late_brake_success ovunque** — braking_efficiency sempre 1.15 anche su rettilinei → fix: calcolo solo con braking_energy ≥ 0.05

### Documentazione
- `docs/lapsimulator-implementation-spec.md` — spec tecnica completa con 11 gap identificati
- `docs/global-roadmap.md` — Fase B aggiornata con stato LapSimulator

---

## Problema bloccante: Sezioni telemetria difettose (§6.11)

### Scoperta
Durante il tentativo di calibrazione (lap time 81s vs VER Q 101s), l'analisi ha rivelato che le sezioni nei file `*_Telemetry.json` hanno problemi strutturali:

### Problema 1: Gap di copertura
- Monza: sezioni coprono 4869m su 5725m → **856m non coperti (15%)**
- Il gap principale (132m → 988m) contiene la zona di frenata più pesante

### Problema 2: avg_speed inaffidabile
- `avg_speed` NON è la velocità media reale della sezione
- È la velocità "caratteristica" (apex per curve, punta per rettilinei)
- Esempio: Turn 1-2 ha avg_speed=81 ma i punti telemetrici nella sezione mostrano 284-294 kph

### Problema 3: Confini non allineati
- La frenata per Turn 1 avviene FUORI dalla sezione Turn 1-2
- "Medium Straight 3-4" contiene una frenata pesante (v: 142→134)
- Le sezioni curve sono troppo corte (58m, 57m)

### Conseguenza
- `dt = length / avg_speed` produce 72s vs 101s reali
- Impossibile calibrare il LapSimulator senza dt_ref affidabili
- Tutti i dati derivati (braking_energy, DRS, radius) dipendono dalla segmentazione

### Dato positivo
I **778 punti telemetrici** (distance, speed, timestamp, throttle, brake, gear, rpm, drs) sono corretti e coprono l'intero giro (0s → 101.117s). Il problema è solo nella definizione delle sezioni sopra quei punti.

---

## ✅ Completato: Telemetry Sections v2

Branch `feature/telemetry-sections-v2` merged in `feature/lapsimulator-runtime`.
24/24 circuiti rigenerati con `scripts/regenerate_telemetry_sections.py`.
Spec: `docs/telemetry-sections-v2-spec.md`

## ✅ Completato: Modello dt_ref penalty

Formula: `dt = dt_ref × (1 + baseline + Σ penalties)`

- `baseline_delta = +0.05` (top team inizio 2025, +5% vs VER 2024 Q)
- Penalties: aero (±0.03), grip (±0.05), brake (±0.03), fuel (±0.03), driver (±0.05)
- Clamp: -0.05 → +0.30

Risultati Monza (top team, baseline=+5%):
- Lap 1: 108.1s (+6.9% vs VER Q 101.1s) ✅
- Lap 5: 112.0s (degrado ~2s/giro preservato) ✅

Posizionamento griglia (basato su F1 2025 reale, prime 4 gare):
- Top team: +5% | Midfield: +7% | Backmarker: +9% | Spread: ~4%
- Floor post-sviluppo: +2% (raggiungibile a fine stagione)

---

## ✅ Completato: Gap §6.7-6.10

- **§6.7 Fuel weight**: `delta_fuel` con `corner_fuel_mult` (curve +30%)
- **§6.8 Mechanical grip**: `setup_bonus` da suspension.efficiency, ride_height, antiroll (0.92–1.05)
- **§6.9 Driver skills brakes**: `driver_brake_skill = (race_craft + aggression) / 200`
- **§6.10 Overtake window**: `ow = base + drs + driver + grip + brake + aggression` (0–1)

Risultati 3 circuiti (top team, baseline=+5%):
- Monza L1: 108.3s (+7.1%), OW_max=0.78
- Monaco L1: 76.5s (+6.5%), OW_max=0.78
- Silverstone L1: 107.2s (+6.2%), OW_max=0.78

---

## ✅ Completato: Tuning coefficienti multi-circuito

3 round di calibrazione su 24/24 circuiti:
- `baseline_delta`: 0.05 → 0.07 (netto ~+5.5% dopo grip bonus)
- `k_grip_penalty`: 0.05 → 0.02, formula normalizzata su `grip_ref=0.70`
- `k_brake_penalty`: 0.03 → 0.015
- `k_fuel_penalty`: 0.03 → 0.015
- `k_driver_penalty`: 0.05 → 0.03
- `thermal_factor` floor: 0.70 → 0.82 (gomme fredde meno penalizzanti)

Risultati L1 (top team, 24 circuiti):
- Media: +5.7% vs ref | Range: 4.7%–8.8% | 22/24 nel target [4.5–7.5%]
- Outlier alti: Imola +8.8% (23 sez, 12 curve), Austin +7.6% (17 sez) — giustificato dalla natura tecnica
- Degrado L5 su circuiti tecnici: da riaffrontare con TyreModel v2

---

## ✅ Completato: AI Driver Engine

Moduli: `ai_data_types.py` + `ai_driver_engine.py` (20 test, 105/105 totali)

- **Setup seed**: `score = 0.7 × sim_eff + 0.3 × sim_affinity` → offset inversamente proporzionale
- **Session planning**: FP1 (2× Setup Validation + Tyre Deg per top), FP2 (Tyre Deg + Quali Sim + Race Trim), FP3 (Quali Sim + Setup se non converged)
- **Run config**: `configure_run()` → `CarEntry` pronto per LapSimulator (fuel, compound, engine_map, push_level)
- **Post-run analysis**: telemetry summary, grip balance delta, brake cooling delta → setup adjustments
- **Refinement loop**: accuracy da `sim_affinity + mechanical_sympathy`, convergenza quando tutti i delta < threshold
- **Classe `AIDriverEngine`**: lifecycle completo start_session → has_next_run → configure → complete_run → summary

Integrazione testata su Monza: top team FP1 (3 run), backmarker FP2 (3 run).

---

## ✅ Completato: TyreModel v2

4 feature aggiunte chirurgicamente al modello esistente (18 test, 123/123 totali):

- **degradation_rate_multiplier**: C1=0.6x, C3=1.0x, C5=1.6x, C6=1.8x — wear proporzionale al compound
- **slip_sensitivity**: C1=0.75, C3=1.0, C5=1.30, C6=1.45 — amplifica grip in curva per soft compound
- **heat_cycle_penalty**: grip_penalty = 0.005/cycle, floor 0.85. Gomme usate perdono grip progressivamente
- **Graining/blistering temporali**: accumulatori con soglia (8s/10s). Brief exposure non triggera, sustained sì. Decay quando condizioni rientrano.

Nuovi campi `TyreCompoundParams`: degradation_rate_multiplier, slip_sensitivity, heat_cycle_grip_penalty, heat_cycle_warmup_penalty_s, heat_cycle_eol_threshold, graining_time_threshold_s, blistering_time_threshold_s.
Nuovi campi `TyreState`: heat_cycles, graining_time_acc_s, blistering_time_acc_s.

JSON config aggiornato per tutti gli 8 compound (C1-C6 + Inter + Wet).

---

## ✅ Completato: BattleResolver 2.0

Modulo `battle_resolver.py` (29 test, 152/152 totali):

- **Tipi**: BattleOutcome (6 stati), ScenarioTag (7 scenari), BattlePair, BattleEvent, BattleResult
- **Proximity detection**: soglie per scenario (straight 60m, braking 25m, corner 10m, exit 20m)
- **Dirty air**: penalty lineare con distanza (max 0.15), peggiore in curva (×1.5), minima su rettilineo (×0.3)
- **Scenario tagging**: straight, heavy_braking, corner, corner_exit, start_restart, blue_flag, team_order
- **Attack chance**: delta-v + grip advantage + DRS + driver skill + overtake_window - dirty_air, modulato per scenario
- **Resolution**: overtake (chance ≥0.65), side-by-side (≥0.4), blocked (<0.4), collision (risk da aggression)
- **Radio messages**: per scenario × outcome (attacker + defender)
- **LapSimulator integration**: `enable_battles=True` → `_run_lap_multi()` con per-section battle resolution, dirty air cache, ordering changes

---

## ✅ Completato: Practice Session Orchestrator

Modulo `practice_session.py` (37 test, 189/189 totali):

- **TyreInventory**: check-out/check-in set, heat_cycles tracking, EOL threshold, prefer_new logic, summary per UI
- **SessionClock**: timer 60min, pause/resume, fast-forward (×1-×6), flag (green/yellow/red), remaining_s
- **PitlaneQueue**: priority (player > AI critical > AI standard), cooldown 120s, queue delay 7s/car, max 4 slot
- **PracticeRunRecord**: log completo per run (program, compound, tyre_set_id, laps, outcome, timing)
- **CarSessionState**: fase (in_garage, pit_queue, pit_exit, on_track, pit_entry, pit_work)
- **PracticeSessionOrchestrator**: register_team, start_session, tick loop, request_run, complete_run, red flag abort, leaderboard, session_summary
- **PracticeEvent**: 9 tipi evento (RUN_START/END/ABORT, FLAG_CHANGE, TYRE_INVENTORY_UPDATE, SESSION_START/END, CAR_EXIT/ENTER_PIT)

---

## Prossimi passi

Tutti i moduli core del LapSimulator sono completati:
1. ✅ LapSimulator v0.2 (dt_ref penalty model, 24 circuiti)
2. ✅ AI Driver Engine (setup seed, session planning, refinement)
3. ✅ TyreModel v2 (compound-specific, heat-cycle, graining/blistering)
4. ✅ BattleResolver 2.0 (multi-car, dirty air, 7 scenari)
5. ✅ Practice Session Orchestrator (clock, pitlane, tyre inventory)

**Prossima fase**: integrazione end-to-end, Telemetria & HUD, UI Garage 2.0, FastF1 toolchain
