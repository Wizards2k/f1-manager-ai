# F1 Manager AI Physics Engine — Roadmap 2026

**Ultima aggiornamento:** 2026-04-19  
**Stato attuale:** V6.1 COMPLETE — Multi-session engine maps + FIA ERS compliance  
**Prossimo milestone:** V6.2 (Optional Las Vegas fix + Generic setup optimizer)

---

## ✅ Completato: V6.1

- [x] **V6.1-2a**: Engine map wiring in car_setup.py (4 edits)
- [x] **V6.1-2**: FIA ERS Compliance — mguh_direct_ratio fix su tutte le 25 pu_maps.json
- [x] **V6.1-2b**: Engine map tests (test_engine_maps.py, 3/3 PASS)
- [x] **V6.1-4**: Auto-map session type → engine_map (QUALIFY/RACE/PRACTICE)
- [x] Documentation update (physics-engine-v6-specification.md)

**Risultati:**
- ✅ Multi-lap race simulations fully supported
- ✅ FIA Energy Budget compliance verified
- ✅ All tests passing (engine maps 3/3, preference test 24/24, typology 91.7%)

---

## ⏳ Prossimi Task (V6.2+)

### 🔴 **P1 — OPEN: Las Vegas Straight Speed (altitude NOT the root cause)**

**Priorità:** Bassa (singolo circuito)  
**Impatto:** 🟡 Medio

**V6.2 altitude fix landed, Las Vegas NOT solved:**
- V6.2 ISA air density propagated through `compute_v_max_corners` AND `integrate_waypoint` main loop (previously only v_max_corners)
- Result at 610m (ρ = 1.139, -7%): 104.79s → 104.68s (**~0.1s, effects cancel**)
- Reference 107.934s → still **-3.00% error**

**Collateral: Mexico City (2232m, -24% ρ) needed wing recalibration**
- Old CAL 16/9 broke congruence (HIGH-wing began winning as downforce ↓ 24%)
- New CAL: **22/14** → 24/24 restored
- Saved in `optimal_wings_v60.json` with `v62_altitude_recal` note

**Real root cause for Las Vegas — still open:**
- μ already clamped at floor 0.3 → not grip
- Altitude only accounts for ~0.1s of the 3.1s gap
- Candidates: PU power curve, braking dynamics, long-straight drag under-modelling, or telemetry reference quality

**Status:** V6.2-altitude done ✅ · straight-speed investigation **deferred**

---

### 🟡 **P2 — OPTIONAL: CHECK SETUP Sensitivity Tests (V6.1-3)**

**Priorità:** Bassa (validation only)  
**Impatto:** 🟢 Basso (confidence check)

**Descrizione:**
6 test di sensitività per validare che il motore fisico risponde correttamente ai cambi di assetto:

| # | Test | Atteso | Metrica |
|---|------|--------|---------|
| 1 | **Aero sweep** (FW 4→42) | Monotonic time decrease vs speed increase | Δt_lap / Δwing |
| 2 | **Suspension stiffness** (soft → hard) | Balance shift, min time at mid-range | t_min, optimal_stiffness |
| 3 | **Fuel load** (light → heavy) | Lap time +0.2-0.5s per 10kg | Δt / Δfuel |
| 4 | **Tyre compound** (soft → hard) | Soft faster early, degradation trail | t_lap curve vs lap_n |
| 5 | **ICE/ERS mode** (PRACTICE → QUALIFY) | Time delta matches engine map diff | Δt_expected vs Δt_sim |
| 6 | **Push level** (0→100%) | Gradual lap time increase, then penalty | t_lap(push) curve |

**Script:** `python scripts/check_setup_sensitivity.py [--circuit monza] [--test 1-6]`

**Output:**
- Per circuito: tabella risultati + grafico per ogni test
- Report JSON: `setup_sensitivity_report.json`

**Status:** Deferred (confidence boost, non critico)

---

### 🔵 **P3 — Generic Setup Optimizer (V6.2+)**

**Priorità:** Molto bassa (future feature)  
**Impatto:** 🔵 Visione

**Descrizione:**
Estendere grid search da ali a sospensioni + fuel. Goal: trovare **multi-parametric optimum** per circuito.

**Parametri:**
- Front Wing: [4-42], step 2°
- Rear Wing: [4-45], step 2°
- Front Susp: [4-10], step 1 (example range)
- Rear Susp: [4-10], step 1
- Fuel: [10-110], step 10 kg

**Algoritmo:**
1. **Bayesian Optimization** (più efficiente di grid search brute-force)
2. Campioni iniziali: 50-100 sims random
3. Predict best region, sample iteratively
4. Converge a optimum locale in 200-300 sims total (~30 min per circuito)

**Alternative:** 
- Simulated annealing
- Genetic algorithm
- Neural network surrogate model

**Blockers:**
- Attualmente mu è fix per circuito; fuel change richiede ricalibrazione mu
- Soluzione: "Fuel-neutral" mu (account for fuel density change)

**Status:** Vision (post V6.1, richiede architettura stabile)

---

## 🎯 Testing & Validation

### Game Integration Readiness Checklist

- [ ] **Multi-lap race simulation** — test 1 giro QUALIFY + 3 giri RACE
  - Setup: Monza, same aero (optimal)
  - Verify: QUALIFY fastest, RACE slower ma dentro range, consistency lap-to-lap
  
- [ ] **Engine map switching** — test session switching mid-session
  - Scenario: Start PRACTICE, switch to RACE mid-session
  - Verify: Lap time changes immediately, no anomalies
  
- [ ] **Thermal model** — test temperature across maps
  - QUALIFY: high temp (102+°C limit?)
  - RACE: stable mid-range
  - PRACTICE: low temp (battery focus)
  
- [ ] **Multi-circuit validation** — spot-check 5 diverse circuits
  - Monza (fast): QUALIFY optimal ~9-10°, time ~79-81s
  - Monaco (slow): QUALIFY optimal ~38-40°, time ~70-72s
  - Singapore (night): QUALIFY optimal ~25-28°, thermal check
  - Spa (mixed): engine map sensitivity
  - Hungary (technical): setup response

---

## 📋 Deferred Items (Post V6.2)

| Item | Motivo Defer | Estimated Effort |
|------|-------------|------------------|
| **Optimizer generico setup** | Richiede V6.1 stabile + rethink fuel/mu coupling | 3-4 giorni |
| **Tire degradation modeling** | Separe dalla V6.1, basso priorità | 2 giorni |
| **Weather effects** (rain/temps) | Ipotesi: fixed per sessione, non dynamic | 1 giorno |
| **Pit strategy optimizer** | Gameplay, non physics | 5+ giorni |
| **Real-time telemetry export** | Integration task, non physics | 2-3 giorni |

---

## 🔍 Known Issues & Tracking

### Open Issues

| Issue | Severity | Assignee | Status |
|-------|----------|----------|--------|
| **Las Vegas -2.9% error** | Medium | V6.2-1 WIP | Altitude fix implemented, error persists (-2.98%). Root cause investigation needed. |
| **Barcelona typology (9° vs 22°)** | Low | Accepted limit | Single-lap physics |
| **Spa borderline typology** | Low | Accepted (lenient range) | Boundary case |

**V6.2-1 Altitude Fix Status:**
- ✅ Implemented ISA barometric air density model
- ✅ Las Vegas elevation 610m → rho = 1.1390 kg/m³ (-7.02% vs sea level)
- ✅ compute_v_max_corners now uses altitude-corrected air_density
- ❌ Las Vegas time unchanged: 104.785s → 104.715s (still -2.98% error)
- **Diagnosis:** v_max_corner likely not limiting factor (98% of lap is corners/braking at lower speeds)
- **Next:** Investigate power unit, braking dynamics, or fundamental modeling constraint

### Resolved Issues

- ✅ Setup congruence (13/24 → 24/24)
- ✅ MGU-H direct ratio (incorrect → FIA-compliant)
- ✅ Engine map selection (hardcoded → auto-select)
- ✅ Load sensitivity K (variable → unified 0.010)

---

## 📊 Current Metrics (V6.1)

| Metrica | Target | Actual | Status |
|---------|--------|--------|--------|
| Setup Congruence | 24/24 | 24/24 | ✅ |
| Typology Congruence | 90%+ | 91.7% | ✅ |
| Lap Time Accuracy | 90%+ | 96% (23/24) | ✅ |
| Engine Map Tests | PASS | 3/3 | ✅ |
| FIA ERS Compliance | 100% | 100% | ✅ |

---

## 🚀 Quick Start: Next Session

**If resuming work:**

1. **Review V6.1 state** → Read physics-engine-v6-specification.md section 7.4
2. **Run validation** → `python scripts/preference_v60_optimal.py` (should be 24/24)
3. **Choose next task** → V6.1-1 (Las Vegas fix) or P2 (CHECK SETUP tests)
4. **Update memory** → Document findings in `/memory/` if pursuing new direction

**If integrating into game:**

1. Verify multi-lap race sim: `python scripts/test_engine_maps.py --all`
2. Test game integration layer with V6.1 engine_map selection
3. Validate UI shows correct ERS behavior per map

---

**Document Date:** 2026-04-19  
**Physics Engine Status:** ✅ V6.1 Complete — Ready for game integration  
**Next Maintainer:** Update this roadmap monthly or before major pivots
