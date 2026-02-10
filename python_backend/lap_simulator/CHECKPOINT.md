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

## Prossimi passi

1. Tuning coefficienti k_* su più circuiti
2. Implementare gap §6.7-6.9 (fuel weight, mechanical grip, driver skills)
3. Overtake window (§6.10)
4. BattleResolver 2.0
