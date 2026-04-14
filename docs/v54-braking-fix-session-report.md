---
title: "V5.4 Braking Fix — Session Report 14/04/2026"
date: 2026-04-14
version: 5.4.x-braking-investigation
status: WORK IN PROGRESS — Riepilogo sessione di debug frenata
authors: F1 Manager AI Physics Team
---

# V5.4 Braking Fix — Session Report

## 1. Contesto e Obiettivo

Il motore fisico V5.3 è calibrato a **0.21% errore medio** su 24 circuiti (tutti < 0.5%).
L'obiettivo V5.4 è sostituire il modello flat-power (910 kW costanti) con un modello
PU stateful (torque-based con SOC, bucket, thermal) mantenendo l'errore < 0.5%.

Durante l'implementazione V5.4, è emerso un problema di **frenata** che causa:
- Monaco troppo lento (+1.75% nel baseline V5.3 con Fix 1)
- Oscillazione frenata/accelerazione (frena→accelera→frena ogni 5m)

## 2. Stato del Codice

### 2.1 Codice Committato (V5.3 baseline — `ff1ad69`)

Il codice committato funziona correttamente (0.21% medio). La frenata usa:
```python
if v_current > wp_v_ref + 1.0:  # Frena per qualsiasi differenza > 1 m/s
```

### 2.2 Codice Corrente (non committato — working tree)

Tre fix sono stati aggiunti al `waypoint_integrator.py`:

| Fix | Descrizione | Cambiamento |
|-----|-------------|-------------|
| **V5.4.2** | Soglia frenata da `+1.0` a `*1.04` | Ignora differenze < 4% |
| **V5.4.3** | Limit speed drop 30 kph ai boundary | Previene collasso velocità |
| **V5.4.4** | Graduated throttle (brake_intensity 0.3→1.0) | Transizione graduale |

Inoltre, il modello PU stateful V5.4 è stato aggiunto (ma non attivo di default).

### 2.3 Risultati Attuali (codice non committato)

| Circuito | V5.3 Baseline | Codice Corrente | Delta |
|----------|--------------|-----------------|-------|
| Monza | -0.22% | -2.17% | -1.95% |
| Spa | +0.32% | -1.90% | -2.22% |
| Monaco | +1.75% | -3.45% | -5.20% |
| Austin | -0.15% | -1.58% | -1.43% |

**Tutti i circuiti sono ora troppo veloci** (errore negativo = sim troppo veloce).
Il Fix V5.4.2 (`*1.04`) riduce troppo la frenata, il Fix V5.4.4 (graduated throttle con
brake_intensity che parte da 0.3) riduce ulteriormente la decelerazione.

### 2.4 File Modificati (non committati)

- `python_backend/lap_simulator/physics_v4/integrator/waypoint_integrator.py` — Fix V5.4.2/3/4 + PU V5.4
- `python_backend/lap_simulator/physics_v4/integrator/pu_stateful.py` — NUOVO (V5.4 Phase 1)
- `python_backend/lap_simulator/physics_v4/integrator/pu_stateful_v2.py` — NUOVO (V5.4 con deployment zones)
- `docs/physics-engine-v5.4-pu-stateful.md` — NUOVO (spec V5.4)
- `docs/physics-engine-v5-checklist.md` — Aggiornato
- `docs/physics-engine-v5-telemetry-bridge.md` — Aggiornato

## 3. Problema Principale: Frenata

### 3.1 Il Problema Originale (Monaco +1.75%)

A Monaco, il simulatore V5.3 era +1.75% troppo lento. Analisi micro-settore ha mostrato:
- **Frenata anticipata**: Il sim inizia a frenare ~30-40m prima del pilota reale
- **Frenata a scatti**: Il sim passa da 280 kph a 114 kph in un singolo step
- **Oscillazione**: 174 transizioni throttle/brake per giro (reale: ~12-15)

La causa: la soglia `v_current > wp_v_ref + 1.0` fa frenare il sim per qualsiasi
differenza di velocità, anche minima. Questo causa:
1. Frenata anticipata (il lookahead trova un punto lento anche lontano)
2. Oscillazione (frena troppo → accelera → frena di nuovo)

### 3.2 Il Fix V5.4.2 (Soglia `*1.04`)

Cambiando la soglia da `+1.0` a `*1.04`, il sim ignora differenze < 4%:
- A 300 kph: ignora rallentamenti < 12 kph
- A 100 kph: ignora rallentamenti < 4 kph

**Effetto**: Monaco migliora (meno oscillazione), MA tutti gli altri circuiti
diventano troppo veloci perché il sim non frena abbastanza.

### 3.3 Il Fix V5.4.4 (Graduated Throttle)

Quando `must_brake` si attiva, il sim ora usa `brake_intensity` che parte da 0.3
e rampa a 1.0. Questo riduce la decelerazione iniziale, peggiorando il problema.

### 3.4 Il Fix V5.4.3 (Boundary Speed Collapse)

Ai confini di sezione, il waypoint duplicato porta il raggio APEX della sezione
entrante (es. 45m per la hairpin di Monaco) invece del raggio reale a quel punto
(es. 3842m all'ingresso curva). Questo causa un collasso catastrofico di v_max_corner.

Il fix limita il drop a 30 kph per step ai boundary. Questo aiuta Monaco ma
ha un impatto limitato sugli altri circuiti.

## 4. Soluzione Proposta: Frenata Guidata dalla Telemetria

### 4.1 L'idea

Il Reference Pull contiene **brake_pct reale** per ogni punto del giro:
- Monaco: 12 zone di frenata (da 90m a 2940m)
- Spa: 7 zone di frenata (da 255m a 6750m)
- Range: 0-1 (1.0 = 100% frenata)

**Usare il brake_pct del Reference Pull per decidere QUANDO e QUANTO frenare**,
invece di euristiche basate su v_ref.

### 4.2 Architettura

```
Per ogni waypoint:
  1. Estrai brake_pct dal Reference Pull alla distanza corrente
  2. Se brake_pct > 0.1 (10%):
     → Frena con intensità proporzionale a brake_pct
     → brake_intensity = brake_pct (0.1-1.0 → 10%-100% decel)
  3. Se brake_pct ≤ 0.1:
     → Lookahead fisico come fallback (con soglia +1.0 originale)
```

### 4.3 Vantaggi

- **Elimina l'oscillazione**: Il pilota reale non oscilla, il brake_pct è smooth
- **Frenata al momento giusto**: Il Reference Pull dice esattamente quando frenare
- **Intensità corretta**: brake_pct reale dice quanto frenare
- **Nessuna euristica**: Non serve la soglia `1.04` né il graduated throttle
- **Backward compatible**: Se Reference Pull non disponibile, fallback al lookahead

### 4.4 Implementazione (DA FARE)

1. **Estrarre brake_pct dal Reference Pull** nella sezione 6 (frenata) di
   `integrate_waypoint()`, indipendentemente da `pu_lookup_blend`
2. **Sostituire l'euristica del lookahead** con la frenata guidata da brake_pct
3. **Mantenere il lookahead come fallback** quando il Reference Pull non è disponibile
4. **Rimuovere i Fix V5.4.2 e V5.4.4** (soglia `1.04` e graduated throttle)
5. **Mantenere il Fix V5.4.3** (boundary speed collapse) — è un fix strutturale

### 4.5 Fonte Dati Telemetria

Il Reference Pull è generato da dati reali F1 (TracingInsights):
- `python_backend/lap_simulator/data/circuits/reference_pull/{circuit_id}_reference_pull.json`
- Disponibili: Monza, Spa, Monaco, Suzuka, Silverstone (5 circuiti)
- Formato: `{"data": {"dist_m": [...], "speed_kph": [...], "throttle_pct": [...], "brake_pct": [...], "gear": [...], "rpm": [...], "radius_m": [...]}}`
- brake_pct range: 0-1 (1.0 = 100% frenata, valori negativi = artefatti)

Fonte esterna: https://github.com/TracingInsights-Archive/2025/blob/main/Monaco%20Grand%20Prix/Qualifying/NOR/26_tel.json

## 5. Problema Secondario: Boundary Speed Collapse (V5.4.3)

### 5.1 Il Problema

Ai confini di sezione nei waypoint HD, il primo punto della sezione entrante
porta il raggio APEX minimo di quella sezione, non il raggio reale a quella
posizione. Esempio Monaco T1:
- Waypoint uscente: radius = 4660m (rettilineo)
- Waypoint entrante (stessa posizione): radius = 77m (apex T1)
- v_max_corner crolla da ~280 kph a ~30 kph in un singolo step

### 5.2 Il Fix Attuale

```python
is_boundary_transition = False
if dist_step < 1.0 and waypoints is not None and waypoint_idx > 0:
    prev_wp = waypoints[waypoint_idx - 1]
    prev_radius = prev_wp.get('radius_m', 9999.0)
    if radius_m < prev_radius * 0.2 and prev_radius > 100:
        is_boundary_transition = True
if dist_step < 0.02:  # Also apply at boundary duplicates
    is_boundary_transition = True
if is_boundary_transition:
    max_drop_ms = 30.0 / 3.6  # 30 kph in m/s
    v_new_ms = max(v_new_ms, state.velocity_ms - max_drop_ms)
```

### 5.3 Stato

Il fix funziona per Monaco (da +1.75% a +0.09% con solo V5.4.3), ma il limite
di 30 kph potrebbe essere troppo restrittivo per altri circuiti. Da rivalutare
dopo aver risolto la frenata.

## 6. Documentazione di Riferimento

| Documento | Path | Contenuto |
|-----------|------|-----------|
| Spec V5.4 PU Stateful | `docs/physics-engine-v5.4-pu-stateful.md` | Architettura PU, torque curve, bucket, thermal |
| Spec V5.x Telemetry Bridge | `docs/physics-engine-v5-telemetry-bridge.md` | Dynamic curvature, Reference Pull, compound grip |
| Checklist V5.x | `docs/physics-engine-v5-checklist.md` | Stato implementazione, fasi V5.4 |
| Engine Data 2025 | `docs/EngineData2025.md` | Dati reali ICE torque curve, gear ratios |
| ERS Bucket Planner | `docs/ERS-Bucket-Planner.md` | Strategia deploy ERS per zona |
| ERS Deployment Strategy | `docs/ERS-Deployment-Strategy.md` | Mappe motore, SOC floor, priority scoring |
| ERS Thermal Clipping | `docs/ERS-ThermalClipping.md` | Modello termico, parametri clipping |
| Brake Penalty System | `docs/brake-penalty-system.md` | Penalità usura freni |
| Brake Integration | `docs/brake-integration.md` | Integrazione freni nel physics engine |
| Lap Physics Spec V0.5 | `docs/lap-physics-spec-v0.5.md` | Spec originale integratore waypoint |
| Telemetria Reale (GitHub) | `TracingInsights-Archive/2025` | Dati telemetria F1 2025 per tutti i GP |

## 7. Script di Verifica

### 7.1 Script Principale

| Script | Path | Uso |
|--------|------|-----|
| **validate_v53.py** | `python_backend/scripts/validate_v53.py` | Validazione ufficiale 24 circuiti. Parametri: `--quick` (3 circuiti), `--driver 1.05` |
| validate_v5.py | `python_backend/scripts/validate_v5.py` | Versione precedente (V5.0) |
| validate_ers_bonus.py | `python_backend/scripts/validate_ers_bonus.py` | Test bonus ERS |

### 7.2 Come Eseguire

```bash
cd python_backend
python3 scripts/validate_v53.py              # Full validation (24 circuiti)
python3 scripts/validate_v53.py --quick       # Quick (Monza, Monaco, Silverstone)
```

### 7.3 Test Rapido Inline (usato in questa sessione)

```python
import sys
sys.path.insert(0, 'python_backend')
# Poi da python_backend/:
from lap_simulator.physics_v4.integrator.waypoint_integrator import integrate_lap_hd

result = integrate_lap_hd(
    circuit_id='mc-1929_monaco',
    aero_setup={'front_wing': 22.0, 'rear_wing': 26.0},
    mass_kg=798+20,
    tyre_compound='C5',
    driver_skill=1.0,
    suspension_setup={...},
    verbose=True,
)
```

### 7.4 Parametri V5.3 di Riferimento (da validate_v53.py)

```python
SUSP_SETUPS = {
    "monza": {"spring_front": 25.0, "spring_rear": 33.0, "arb_front": 8.0, "arb_rear": 13.0, "ride_height_front": 10.0, "ride_height_rear": 17.0},
    "monaco": {"spring_front": 10.0, "spring_rear": 18.0, "arb_front": 25.0, "arb_rear": 30.0, "ride_height_front": 16.0, "ride_height_rear": 23.0},
    "silverstone": {"spring_front": 25.0, "spring_rear": 33.0, "arb_front": 25.0, "arb_rear": 30.0, "ride_height_front": 2.0, "ride_height_rear": 9.0},
}

# Esempio parametri circuito:
# Monaco: circuit_id='mc-1929_monaco', compound='C5', fw=22, rw=26, ref=71.312s, susp=monaco
# Monza: circuit_id='it-1922_monza', compound='C4', fw=8, rw=10, ref=78.869s, susp=monza
# Spa: circuit_id='be-1925_spa_francorchamps', compound='C4', fw=10, rw=12, ref=100.562s, susp=monza
# Austin: circuit_id='us-2012_austin', compound='C4', fw=22, rw=26, ref=92.510s, susp=silverstone
```

## 8. Problemi Aperti

### 8.1 CRITICO: Frenata troppo debole (V5.4.2 + V5.4.4)

**Sintomo**: Tutti i circuiti sono troppo veloci (-1.5% to -3.5%)
**Causa**: La soglia `*1.04` e il graduated throttle (brake_intensity 0.3) riducono
troppo la frenata
**Soluzione proposta**: Frenata guidata dalla telemetria (brake_pct dal Reference Pull)
**Stato**: DA IMPLEMENTARE

### 8.2 MEDIO: Boundary Speed Collapse (V5.4.3)

**Sintomo**: Monaco +1.75% (baseline), collasso velocità ai confini sezione
**Causa**: Waypoint duplicati portano raggio APEX invece di raggio reale
**Soluzione**: Limite 30 kph drop per step ai boundary (attuale)
**Stato**: FUNZIONA PER MONACO, da rivalutare per altri circuiti dopo fix frenata

### 8.3 BASSO: Reference Pull solo 5 circuiti

**Sintomo**: brake_pct disponibile solo per Monza, Spa, Monaco, Suzuka, Silverstone
**Causa**: Telemetria reale non scaricata per gli altri 19 circuiti
**Soluzione**: Scaricare da TracingInsights o usare fallback lookahead
**Stato**: NOTA — il fallback al lookahead fisico è già previsto nell'architettura

### 8.4 BASSO: PU V5.4 non validato

**Sintomo**: Modello PU stateful implementato ma non calibrato
**Causa**: Priorità alla fix della frenata
**Soluzione**: Dopo fix frenata, calibrare PU V5.4 su 5 circuiti
**Stato**: IN PAUSA — file `pu_stateful.py` e `pu_stateful_v2.py` esistono ma non attivi

## 9. Piano di Azione (Prossima Sessione)

### Step 1: Ripristinare baseline V5.3
- Rimuovere Fix V5.4.2 (soglia `*1.04` → tornare a `+1.0`)
- Rimuovere Fix V5.4.4 (graduated throttle → tornare a frenata piena)
- Mantenere Fix V5.4.3 (boundary speed collapse)
- Verificare che i risultati tornino al baseline V5.3

### Step 2: Implementare frenata guidata dalla telemetria
- Aggiungere estrazione `brake_pct` dal Reference Pull nella sezione 6
- Quando `brake_pct > 0.1`: frenare con intensità proporzionale
- Quando `brake_pct ≤ 0.1`: usare lookahead fisico (soglia `+1.0`)
- Test su Monaco, Spa, Monza

### Step 3: Validare
- Eseguire `validate_v53.py` completo
- Verificare errore < 0.5% su tutti i circuiti
- Per i 5 circuiti con Reference Pull: usare brake_pct reale
- Per gli altri 19: usare lookahead fisico (dovrebbe essere identico a V5.3)

### Step 4: Calibrare V5.4.3 (boundary fix)
- Con frenata corretta, rivalutare il limite 30 kph
- Potrebbe servire un valore diverso per circuiti diversi

## 10. Note per Altra IA

### 10.1 Contesto Essenziale

Questo è un simulatore di giri F1 che integra waypoint ad alta definizione (5m passo)
con un modello fisico completo (aero, tyres, PU, brakes, suspension). Il modello V5.3
è calibrato a 0.21% errore medio su 24 circuiti.

Il problema attuale è che i fix per Monaco (V5.4.2 e V5.4.4) hanno rotto la frenata
su tutti gli altri circuiti. La soluzione è usare la telemetria reale (brake_pct dal
Reference Pull) per guidare la frenata invece di euristiche.

### 10.2 File Chiave

- **Motore fisico**: `python_backend/lap_simulator/physics_v4/integrator/waypoint_integrator.py` (1653 righe)
  - Sezione 1 (righe ~558-770): Potenza motore (V5.3 flat / V5.4 stateful)
  - Sezione 6 (righe ~1085-1200): Frenata (lookahead + V5.4.2/4 fix)
  - Sezione 9 (righe ~1240-1260): Boundary fix (V5.4.3)
- **PU Stateful V2**: `python_backend/lap_simulator/physics_v4/integrator/pu_stateful_v2.py` (878 righe)
- **Calibrazione aero**: `python_backend/lap_simulator/physics_v4/calibration/aero_calibration.py`
- **Calibrazione circuito**: `python_backend/lap_simulator/physics_v4/calibration/circuit_calibration.py`
- **Telemetria**: `python_backend/lap_simulator/physics_v4/calibration/telemetry_bridge.py`
- **Waypoints HD**: `python_backend/data/circuits/2025/{circuit_id}_HD.json`
- **Reference Pull**: `python_backend/lap_simulator/data/circuits/reference_pull/{circuit_id}_reference_pull.json`

### 10.3 Costanti Fisiche Importanti

```python
MASS_TOTAL_QUALY_KG = 798  # kg (auto + pilota, senza benzina)
G = 9.81  # m/s²
MU_BASE = {"C3": 1.65, "C4": 1.55, "C5": 1.75}  # Grip meccanico per compound
MAX_BRAKE_DECEL_G = 5.0  # g — decelerazione massima frenata
MAX_LATERAL_G = 5.5  # g — accelerazione laterale massima
TYRE_LOAD_SENSITIVITY_K = 0.010  # Rendimento decrescente carico
ICE_PEAK_POWER_KW = 750.0  # kW
ERS_PEAK_POWER_KW = 160.0  # kW
DRIVETRAIN_EFFICIENCY = 0.96
```

### 10.4 Risultati V5.3 Baseline (codice committato `ff1ad69`)

| Circuito | Sim (s) | Ref (s) | Errore |
|----------|---------|---------|--------|
| Monza | 78.69 | 78.869 | -0.22% |
| Spa | 100.88 | 100.562 | +0.32% |
| Monaco | 72.56 | 71.312 | +1.75% |
| Austin | 92.37 | 92.510 | -0.15% |
| **Media 24 circuiti** | | | **0.21%** |

### 10.5 Avvertenze

1. **NON modificare la soglia di frenata** senza testare su tutti i 24 circuiti
2. **Il Reference Pull ha solo 5 circuiti** — il fallback al lookahead è essenziale
3. **Il boundary fix (V5.4.3) è separato** dalla frenata — non rimuoverlo
4. **Il modello PU V5.4 non è attivo** di default (pu_config=None → V5.3)
5. **I test_brake.py e test_brake2.py** nella root sono file temporanei, non ufficiali
6. **La calibrazione V5.3 è nel codice committato** — le modifiche non committate
   potrebbero aver alterato i risultati. Per tornare al baseline: `git checkout HEAD -- python_backend/lap_simulator/physics_v4/integrator/waypoint_integrator.py`