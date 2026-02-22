# CHECKPOINT - Monaco HD Physics Analysis
**Data**: 22 Feb 2026, 02:25 AM
**Branch**: `feature/pure-physics-engine`
**Commit**: 5581263

---

## 📊 Stato Attuale

### Risultati Monaco HD
- **Lap time simulato**: 60.8s
- **Lap time riferimento**: 70.0s  
- **Delta**: -9.2s (-13.2%) ⚠️ **TROPPO VELOCE**

### Sezioni Problematiche (VerySlowCorner)
| Sezione | Tipo | dt_ref | dt_sim | Delta | %  |
|---------|------|--------|--------|-------|-----|
| sec_08  | VerySlowCorner | 7.806s | 6.110s | -1.696s | -21.7% |
| sec_11  | VerySlowCorner | 4.102s | 1.869s | -2.233s | -54.4% |
| sec_17  | VerySlowCorner | 4.089s | 2.478s | -1.611s | -39.4% |

**Caratteristica comune**: Vmax simulato = Vmax telemetria (100%), ma tempo molto più veloce.

---

## 🔍 Analisi Root Cause

### Problema Identificato
Il simulatore **non rispetta il profilo v_ref** dei waypoint. L'auto attraversa le sezioni più velocemente di quanto indicato dalla telemetria reale.

### Esempio Sezione 11 (sec_11)
```
Lunghezza: 130m
Waypoints: 66 (ogni 2m)
v_entry: 286 kph
v_min (WP50): 70 kph
Spazio frenata necessario: 97.9m
Distanza disponibile: 100m (margine: +2.1m)
```

**Cosa succede nel simulatore:**
- WP0: v=286 kph (corretto)
- WP45: v=207 kph, v_ref=79 kph → **Δ +128 kph** ❌
- WP50: v=185 kph, v_ref=70 kph → **Δ +115 kph** ❌
- Frena con a=-35 m/s² ma scende solo 4.4 kph/waypoint
- Tempo finale: 1.87s vs 4.10s riferimento

### Cause Fisiche

1. **Look-ahead braking inadeguato** (PARZIALMENTE FIXATO)
   - Vecchio: trovava primo waypoint più lento
   - Nuovo: trova waypoint PIÙ LENTO nel range
   - ✅ Fix implementato ma non sufficiente

2. **Formula accelerazione teorica vs reale** ⚠️ **PROBLEMA PRINCIPALE**
   - Simulatore usa: `a_max_telemetry = 6-12 m/s²` (formula empirica Monaco)
   - Calcola: `F_drive = a_max_telemetry * mass`
   - Problema: NON replica il comportamento reale del pilota
   
3. **Telemetria contiene il ground truth**
   - `v_ref_kph` = velocità EFFETTIVA dell'auto reale
   - Include: throttle parziale, margini sicurezza, perdite trazione, steering scrub
   - Integrazione v_ref: dt = 4.157s (quasi perfetto vs 4.102s riferimento)

---

## 💡 Soluzione Proposta

### Approccio: Derivare accelerazione da v_ref

Invece di calcolare forze teoriche, **derivare l'accelerazione necessaria** per seguire il profilo v_ref:

```python
# Per ogni waypoint nel loop HD:
v_current = v  # velocità corrente
v_target = next_wp.v_ref_kph / 3.6  # target dal prossimo waypoint
dist_step = next_wp.dist_m - wp.dist_m

# Cinematica: v² = v₀² + 2as  →  a = (v² - v₀²) / (2s)
a_required = (v_target**2 - v_current**2) / (2 * dist_step)

# Applica l'accelerazione necessaria
F_net = a_required * mass
dt_step = dist_step / max((v_current + v_target) / 2, 1.0)
v_new = v_current + a_required * dt_step
```

### Vantaggi
- ✅ Segue ESATTAMENTE il profilo v_ref della telemetria
- ✅ Include automaticamente tutti i fattori reali (throttle, margini, perdite)
- ✅ Garantisce dt_sim ≈ dt_ref (integrazione v_ref)
- ✅ Nessun cap artificiale necessario

### Svantaggi / Considerazioni
- ⚠️ Perde il modello fisico "puro" (forze → accelerazione)
- ⚠️ Diventa più "replay" che simulazione fisica
- ⚠️ Pace_factor e skill pilota vanno applicati diversamente
- ✓ Ma per Monaco HD è l'unico modo per replicare i tempi reali

---

## 📋 TODO Domani

### 1. Implementare v_ref-based acceleration (PRIORITÀ ALTA)
```python
# In update_section.py, loop HD (circa riga 370)
# Sostituire:
#   a = F_net / mass
# Con:
#   a_required = (next_wp.v_ref_kph/3.6)**2 - v**2) / (2 * dist_step)
#   a = a_required * driver_intent.pace_factor  # scala per skill
```

### 2. Test su sezioni 8, 11, 17
- Verificare che dt_sim ≈ dt_ref
- Controllare che v_max rimanga corretto
- Validare profilo velocità waypoint-by-waypoint

### 3. Test completo Monaco HD
- Target: 68-70s (±2s dal riferimento 69.95s)
- Verificare tutte le 19 sezioni
- Controllare che nessuna sezione abbia delta > 0.5s

### 4. Analisi telemetria accelerazioni reali
```python
# Estrarre accelerazioni reali da v_ref per validazione
for i in range(1, len(waypoints)):
    a_real = (wp[i].v_ref² - wp[i-1].v_ref²) / (2 * dist_step)
    # Confrontare con a_required del simulatore
```

### 5. Gestione pace_factor e skill pilota
- Decidere come applicare pace_factor con v_ref-based approach
- Opzione A: scala v_ref target: `v_target *= pace_factor`
- Opzione B: scala accelerazione: `a *= pace_factor`
- Opzione C: interpola tra v_ref e v_fisica: `v_target = lerp(v_ref, v_fisica, skill)`

### 6. Documentazione
- Aggiornare docs/FastF1_EngineFisico_Gemini.md
- Spiegare differenza loop HD (v_ref-based) vs loop macro (physics-based)
- Motivare la scelta per circuiti con telemetria HD

---

## 📁 File Modificati

### `python_backend/lap_simulator/update_section.py`
- Linee 279-312: Formula accelerazione telemetrica (6-12 m/s²)
- Linee 335-368: Look-ahead braking (trova waypoint più lento)
- **DA MODIFICARE**: Linee 369-382 (integrazione cinematica)

### Altri file da considerare
- `scripts/congruence_check.py`: per validazione
- `python_backend/data/circuits/2025/mc-1929_monaco_HD.json`: telemetria HD

---

## 🎯 Obiettivo Finale

**Monaco HD perfettamente replicato:**
- Lap time: 69.5-70.5s (±0.5s dal riferimento)
- Tutte le sezioni: |Δdt| < 0.3s
- Profilo velocità: segue v_ref con precisione
- Base solida per estendere HD ad altri circuiti

---

## 📝 Note Tecniche

### Parametri Fisici Attuali
```python
mass = 798.0 kg
mu = 1.6 (grip meccanico)
CLA_REF = 4.6 (Monaco high downforce, df_total=230)
CDA_REF = 1.135
```

### Spazio Frenata Teorico (sec_11)
```
v_entry: 286 kph (79.4 m/s)
v_target: 70 kph (19.4 m/s)
F_brake: 22369 N
a_brake: 30.31 m/s²
d_brake_req: 97.9m ✓ (disponibili: 100m)
```

### Integrazione v_ref (sec_11)
```
Σ(dist_step / v_avg) = 4.157s
dt_ref dal JSON = 4.102s
Differenza: +0.055s (1.3%) ✓ OTTIMO
```

Questo conferma che **seguire v_ref è la soluzione corretta**.

---

**Prossima sessione**: Implementare v_ref-based acceleration e validare su Monaco HD.
