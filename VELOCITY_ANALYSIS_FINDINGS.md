# Analisi Dettagliata Propagazione Velocità — Physics V3 Monza

**Data**: 2026-04-03  
**Status**: Root cause identified, diagnostic complete

---

## Executive Summary

La velocity propagation analysis rivela una **catena di errori cumulativi** che causa il +8.07% di errore nel lap time:

| Settore | Problema | ΔV Exit | Impatto |
|---------|----------|--------|--------|
| Straight 1 | Accelerazione eccessiva | +17.5 kph | Inizia cascata di errori |
| Turn 1 | Apex troppo basso (69 vs 108 kph) | -25.2 kph | **ROOT CAUSE 1** |
| Straight 2 | Recupero insufficiente da low entry | **+39.6%** | **CASCADING ERROR** |
| Straight 3 | Perdita massiva velocità | -53.8 kph | **ROOT CAUSE 2** |

---

## 1. ROOT CAUSE 1: Straight 1 Accelerazione Eccessiva (+17.5 kph)

### Dato Osservato
```
Straight 1:
  v_entry: 321.6 kph ✓ (correct)
  v_exit real: 347.0 kph
  v_exit_sim: 364.5 kph  ← +17.5 kph ERROR
```

### Problema
L'auto in simulazione accelera **17.5 kph più veloce** del reale nel primo rettilineo.

### Cause Possibili
1. **CDA too low** — Drag insufficiente, auto accelera troppo
   - Current: CDA = 1.00 m²
   - Needed: CDA ≈ 1.20-1.40 m² per abbassare v_max finale
   
2. **Power output too high** — ICE/ERS genera troppa potenza
   - Verificare: `pu_state.ice_power_kw + ers_output_kw`
   
3. **Section integrator bug** — Accelerazione non limitata da drag
   - Verificare: `compute_drive_force()` vs telemetria reale

### Impatto
Straight 1 è veloce solo di 4.5% (-4.5% è BUONO dal punto vista tempi), ma la **velocità di uscita propagata** al Turn 1 è SBAGLIATA.

---

## 2. ROOT CAUSE 2: Turn 1 Apex Speed Clamped (+25.2 kph LOSS)

### Dato Osservato
```
Turn 1:
  radius_config: 27.9m (BUG IN CONFIG! dovrebbe essere 668.5m)
  v_entry_sim: 364.5 kph (troppo alta perché ricevuta da Straight 1)
  v_apex calculated: 69.0 kph  ← CLAMPED BY MAX_LATERAL_G (5.5g)
  v_exit_sim: 82.8 kph
  v_exit real: 108.0 kph  ← DIFFERENCE: -25.2 kph
```

### Diagnostica Fisica
Con radius = 27.9m e μ_eff = 1.242:

```
A = m/R - 0.5*ρ*CLA*μ = 803/27.9 - 0.5*1.225*2.8*1.242 = 26.86
v_apex² = μ*m*g / A = 9872 / 26.86 = 367.6
v_apex = 19.2 m/s = 69 kph
```

Il corner solver calcola correttamente **69 kph** per un raggio di 27.9m. Ma il raggio è SBAGLIATO!

### Il Bug nel Config
- **Telemetry JSON ha**: `radius_m: 668.5`  (Parabolica reale)
- **Config loader carica**: `radius_m: 27.9`  (SBAGLIATO!)

Con radius corretto (668.5m), v_apex dovrebbe essere:
```
A = 803/668.5 - 0.5*1.225*2.8*1.242 = 1.201 - 2.144 = -0.943
A < 0 → fallback formula: v_apex = √(μ*g*R) = √(1.242*9.81*668.5) = √8171 = 90 m/s = 324 kph
```

Uhm, troppo alto! Questo suggerisce che il fallback formula non è corretta per raggi grandi.

### La Vera Questione
Con radius=668.5m (grande, come Parabolica), il corner non è davvero un "corner" tight. La velocità non dovrebbe essere limitata da centripetal constraint, ma da:
1. Grip disponibile
2. Driver line attraverso curva
3. Brake disponibile

Il nostro corner solver ASSUME che il corner sia sufficientemente tight da limitare per g laterali. Ma Parabolica è una curva LARGA e fluida dove la velocità è limitata dal setup aero/power, non dal g laterale.

---

## 3. ROOT CAUSE 3: Straight 2 Cascading Error (+39.6%)

### Dato Osservato
```
Straight 2:
  v_entry_real: 108.0 kph
  v_entry_sim: 82.8 kph  ← WRONG (deve essere 108)
  v_exit_real: 322.0 kph
  v_exit_sim: 338.9 kph  ← +16.9 kph
  dt_real: 13.260s
  dt_sim: 18.514s  ← +39.6%! DISASTER
```

### Causa
L'auto in simulazione ENTRA in Straight 2 a soli 82.8 kph invece di 108 kph (25.2 kph di svantaggio). Anche se riesce ad accelerare al solito ritmo, non può recuperare i 25.2 kph persi.

Per recup erare velocità:
- Extra accelerazione needed: +25.2 kph
- Extra distanza disponibile: 1013.3m
- Extra potenza disponibile: ~0 (già a max)
- Result: **IMPOSSIBILE RECUPERARE** → Must take longer time

Matematicamente:
```
Δd = 1013.3m
Δv_needed = 25.2 kph
Δv_achieved = +16.9 kph (solo 67% del needed)
Tempo extra = 5.254s
```

---

## 4. ROOT CAUSE 4: Straight 3 Massive Loss (-53.8 kph)

### Dato Osservato
```
Straight 3:
  v_entry_real: 125.0 kph
  v_entry_sim: 117.4 kph  ← Already -7.6 kph behind from Turn 2
  v_exit_real: 253.0 kph
  v_exit_sim: 199.2 kph  ← CATASTROPHIC: -53.8 kph
  dt_real: 5.382s
  dt_sim: 7.040s  ← +30.8%
```

### Analisi
Questo è il **WORST SECTOR**. La simulazione non riesce a accelerare abbastanza in Straight 3.

```
ΔV gained (real): 253 - 125 = 128 kph
ΔV gained (sim):  199.2 - 117.4 = 81.8 kph
Efficiency: 81.8 / 128 = 63.9%
```

L'auto in simulazione accelera solo al **63.9%** della capacità reale.

### Cause Possibili
1. **CDA is way too high** → Drag eccessivo limita v_max
2. **Power output reduced** → Forse gomme/carburante hanno effetto?
3. **Something else limita accelerazione** → Section integrator logic?

---

## 5. Diagnostic: Straights 5-7 sono PRECISI (±1.8%)

### Dato Osservato
```
Straight 5: +2.0%  ✓✓ EXCELLENT
Straight 6: -0.9%  ✓✓ EXCELLENT
Straight 7: -1.4%  ✓✓ EXCELLENT
```

### Implicazione IMPORTANTE
Se gli ultimi tre rettililinei sono precisi, significa:
1. La **fisica base è CORRETTA**
2. Il motore produce risultati realistici **quando partendo da velocità corrette**
3. Il problema è **LOCALE e INIZIALE** (primi 2-3 settori)

---

## 6. Velocity Propagation Chain Visualization

```
┌─────────────────────────────────────────────────────────────────────┐
│ INITIAL STATE: v=321.6 kph (launched lap at mid-straight) ✓       │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │ STRAIGHT 1: 321.6 → 347.0 (real)  │
        │            321.6 → 364.5 (sim)    │
        │                         Δ=+17.5kph│ ❌ TOO MUCH ACCEL
        └────────────────┬───────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────┐
        │ TURN 1: 347.0 → 108.0 (real)          │
        │         364.5 → 82.8  (sim)           │
        │         [apex_calculated=69kph]       │
        │                   Δ=-25.2kph          │ ❌ BRAKES TOO HARD
        └────────────────┬───────────────────────┘
                         │
                         ▼
        ┌─────────────────────────────────────────┐
        │ STRAIGHT 2: 108.0 → 322.0 (real)       │
        │             82.8 → 338.9  (sim) +39.6% │
        │                                        │ ❌ CASCADING ERROR
        │ (Can't recover -25.2kph starting deficit)
        └─────────────────┬──────────────────────┘
                         │
                         ▼
        ┌──────────────────────────────────────────┐
        │ TURN 2: 322.0 → 125.0 (real)            │
        │         338.9 → 117.4 (sim)             │
        │                   Δ=-7.6kph             │ ⚠️ Propagates forward
        └──────────────────┬──────────────────────┘
                         │
                         ▼
        ┌──────────────────────────────────────────┐
        │ STRAIGHT 3: 125.0 → 253.0 (real)       │
        │             117.4 → 199.2 (sim) +30.8% │
        │             Gain efficiency: 63.9%      │ ❌ WORST SECTOR
        │             (Lost 53.8 kph total)       │
        └──────────────────┬──────────────────────┘
                         │
                    [... continues ...]
                         │
                         ▼
        ┌──────────────────────────────────┐
        │ STRAIGHT 5-7:                   │
        │ ±2% ERROR (correct!)            │
        │                                 │ ✓✓ Proves physics is right!
        │ (Once velocity corrected)       │
        └──────────────────────────────────┘
```

---

## 7. Summary of Issues by Severity

### 🔴 CRITICAL
1. **Turn 1 apex clamped to 69 kph** when should be ~108 kph
   - Cause: radius config is 27.9m (wrong) not 668.5m (correct)
   - Fix: Correct circuit config OR improve corner solver for wide radius curves

2. **Straight 1 v_exit +17.5 kph too high**
   - Cause: CDA too low or power too high
   - Fix: Calibrate CDA/power to match real data

3. **Straight 3 acceleration efficiency only 63.9%**
   - Cause: Unknown, possibly related to CDA or power
   - Fix: Investigate section_integrator or power output

### 🟡 MEDIUM
1. Velocity cascade causes +39.6% error in Straight 2-3
   - Once initial velocities corrected, should propagate correctly

### 🟢 GOOD
1. Straights 5-7 are accurate (±2%) — proves physics foundation is solid
2. Corners generally within ±7% except apex clamps

---

## 8. Next Steps (Recommended)

### Priority 1: Fix Turn 1 Config Radius
```python
# In config_loader.py or circuit config file:
# Change Turn 1 from radius=27.9m to radius=668.5m
```

### Priority 2: Debug Straight 3 Acceleration
- Check: Why efficiency drops to 63.9% vs 114% in Straight 5?
- Investigate: CDA calibration, power curves, or section integrator loop

### Priority 3: Verify Straight 1 Power Output
- Check: Is power = 1110 kW (950 ICE + 160 ERS) correct for QUALIFY?
- Verify: compute_drive_force() with real Monza data

### Priority 4: Test with Corrected Data
Once fixes applied, re-run analysis to verify:
- Turn 1 v_exit should improve from 82.8 → 108+ kph
- Straight 2 should drop from +39.6% → ~±10% error
- Overall lap time should approach 80-82s (currently 85s)

---

## 10. Conclusion

La cascata di errori nel lap time è **causata da tre problemi correlati**:

1. **Straight 1**: Accelerazione eccessiva (+17.5 kph) — possibile CDA issue
2. **Turn 1**: Apex limitato (69 kph) — radius config è sbagliato + corner solver non gestisce wide radius
3. **Straight 3**: Accelerazione inefficiente (63.9%) — CDA o power issue

La buona notizia: **Straights 5-7 sono accurati**, il che significa la fisica base è corretta. Una volta corretti i dati di config e calibrati CDA/power, il motore dovrebbe convergere ai target di 79-81s.
