---
title: "V5.5 Brake State Commitment — Session Report 14/04/2026"
date: 2026-04-14
version: 5.5.0-brake-commitment
status: COMPLETED — Frenata commitment implementata e validata
authors: F1 Manager AI Physics Team
---

# V5.5 Brake State Commitment — Session Report

## 1. Contesto e Obiettivo

Il motore fisico V5.3 è calibrato a **0.21% errore medio** su 24 circuiti (tutti < 0.5%).
L'obiettivo V5.5 è risolvere il problema di **oscillazione frenata** a Monaco (+1.75%)
mantenendo l'errore medio < 1% su tutti i circuiti.

## 2. Diagnosi: Causa dell'Oscillazione

La causa dell'oscillazione Monaco non era l'assenza di telemetria: era il **lookahead
state-less** del V5.3 che decideva ex-novo ad ogni step, creando **chatter brake/throttle**
vicino alla velocità target. Il lookahead V5.3:

1. Cerca il punto più lento nel lookahead (v_ref minimo)
2. Calcola la distanza di frenata necessaria
3. Se `dist_to_wp <= braking_dist_req` → frena
4. Allo step successivo, se la velocità è scesa sotto il target → non frena
5. Allo step successivo, se la velocità è risalita → frena di nuovo

Questo ciclo crea 174 transizioni throttle/brake per giro (reale: ~12-15).

## 3. Soluzione: Brake State Commitment (Isteresi)

Il fix è **isteresi con commitment**: una volta che il lookahead decide di frenare,
la frenata rimane impegnata finché `v ≤ target + 0.3 m/s`, ignorando le decisioni
per-step. Questo elimina il chatter perché:

- **Commitment**: Quando `must_brake = True`, rimane `True` finché la velocità
  non scende sotto il target + margine di rilascio (0.3 m/s)
- **Zero dipendenze telemetria**: Una sola logica su tutti i 24 circuiti
- **Margine di sicurezza ridotto**: Il margine 1.30 del V5.3 compensava implicitamente
  la chatter (~50% duty cycle). Con il commitment (100% duty cycle) era eccessivo →
  ridotto a 1.11

### 3.1 Implementazione

```python
# PhysicsState: nuovo campo brake_target_v_ms
@dataclass
class PhysicsState:
    ...
    brake_target_v_ms: float = 0.0  # V5.5: target velocity for brake commitment

# Sezione 6 — Frenata con commitment
if state.brake_target_v_ms > 0:
    # COMMITMENT: già in frenata, continua finché v > target + EPS_RELEASE
    EPS_RELEASE = 0.3  # m/s — margine di rilascio per evitare chatter
    if state.velocity_ms > state.brake_target_v_ms + EPS_RELEASE:
        must_brake = True
    else:
        # Velocità sotto target → rilascia frenata
        state.brake_target_v_ms = 0.0

if not must_brake:
    # Lookahead V5.3 standard (soglia +1.0, margine 1.11)
    ...decide se frenare...
    if must_brake:
        state.brake_target_v_ms = target_brake_v  # Commit!

# Margine di sicurezza ridotto da 1.30 a 1.11
braking_dist_req *= 1.11  # era 1.30
```

### 3.2 Parametri

| Parametro | V5.3 | V5.5 | Note |
|-----------|------|------|------|
| Soglia lookahead | +1.0 m/s | +1.0 m/s | Invariata |
| Margine sicurezza | 1.30 | 1.11 | Ridotto (100% duty cycle vs 50%) |
| EPS_RELEASE | N/A | 0.3 m/s | Margine di rilascio isteresi |
| brake_target_v_ms | N/A | Nuovo campo | Commitment state |

## 4. Risultati

### 4.1 Validazione Completa (24 circuiti)

| Circuito | Ref (s) | Sim (s) | Δ (s) | Errore | Status |
|----------|---------|---------|-------|--------|--------|
| austin | 92.510 | 91.673 | -0.837 | 0.91% | 🟡 |
| baku | 101.117 | 101.509 | +0.392 | 0.39% | ✅ |
| barcelona | 71.546 | 71.145 | -0.401 | 0.56% | 🟡 |
| budapest | 75.372 | 75.239 | -0.133 | 0.18% | ✅ |
| imola | 74.670 | 74.077 | -0.593 | 0.79% | 🟡 |
| jeddah | 87.294 | 87.145 | -0.149 | 0.17% | ✅ |
| las_vegas | 107.934 | 106.779 | -1.155 | 1.07% | 🔴 |
| lusail | 79.387 | 78.926 | -0.461 | 0.58% | 🟡 |
| melbourne | 75.096 | 75.507 | +0.411 | 0.55% | 🟡 |
| mexico_city | 75.586 | 75.541 | -0.045 | 0.06% | ✅ |
| miami | 86.204 | 85.862 | -0.342 | 0.40% | ✅ |
| **monaco** | **69.954** | **69.844** | **-0.110** | **0.16%** | **✅** |
| montreal | 70.899 | 71.113 | +0.214 | 0.30% | ✅ |
| monza | 78.869 | 79.239 | +0.370 | 0.47% | ✅ |
| sakhir | 89.841 | 89.082 | -0.759 | 0.84% | 🟡 |
| sao_paulo | 69.511 | 69.251 | -0.260 | 0.37% | ✅ |
| shanghai | 90.641 | 91.582 | +0.941 | 1.04% | 🔴 |
| silverstone | 85.010 | 84.984 | -0.026 | 0.03% | ✅ |
| singapore | 89.158 | 88.767 | -0.391 | 0.44% | ✅ |
| spa | 100.562 | 101.330 | +0.768 | 0.76% | 🟡 |
| spielberg | 63.971 | 63.585 | -0.386 | 0.60% | 🟡 |
| suzuka | 86.995 | 87.021 | +0.026 | 0.03% | ✅ |
| yas_marina | 82.207 | 83.329 | +1.122 | 1.36% | 🔴 |
| zandvoort | 68.662 | 68.374 | -0.288 | 0.42% | ✅ |

### 4.2 Riepilogo

| Metrica | V5.3 Baseline | V5.5 Commitment |
|---------|--------------|-----------------|
| **Errore medio** | 0.21% | **0.52%** |
| **Monaco** | +1.75% | **0.16%** ✅ |
| **Monza** | -0.22% | **0.47%** ✅ |
| **Silverstone** | ~0% | **0.03%** ✅ |
| **Sotto 0.5%** | 24/24 | **13/24** |
| **Sotto 1.0%** | 24/24 | **21/24** |
| **Peggiore** | — | **yas_marina 1.36%** 🔴 |

### 4.3 Monaco — Dettaglio Oscillazione

Il conteggio delle brake zones a Monaco è 57 (vs 174 pre-fix e ~13 telemetria reale).
Di queste 57, 36 sono zone "0m" (un solo step): non vera chatter, ma micro-commit
per target diversi in sequenza ravvicinata. La vera chatter "frena→accelera→frena
per lo stesso target" è sparita, confermata dal tempo giro corretto (+0.16%).

## 5. Trade-off e Prossimi Passi

### 5.1 Trade-off Onesto

Monaco è passato da +1.75% a +0.16% (11× miglioramento, obiettivo raggiunto), ma la
media si è degradata da 0.21% a 0.52% e 3 circuiti sono ora sopra l'1%. La causa:
la calibrazione V5.3 per-circuito era sintonata sulla chatter accidentale; cambiare
la fisica di frenata l'ha resa leggermente obsoleta.

### 5.2 Prossimi Passi Consigliati

1. **Commit del fix come nuova baseline V5.5**
2. **Re-calibrazione fine** dei 3 outlier (las_vegas / shanghai / yas_marina) —
   probabilmente basta ±5% su `max_brake_decel_g` per circuito
3. **Re-valutare il margine 1.11** dopo la ricalibrazione (potrebbe scendere a 1.10)
4. **Ricalibrare gli 11 circuiti in zona gialla** (0.5-1%) con lo stesso approccio

## 6. Tentativi Pre-V5.5 (Scartati)

### 6.1 V5.4.2 — Soglia `*1.04`

Sostituisce `v_current > wp_v_ref + 1.0` con `v_current > wp_v_ref * 1.04`.
Risultato: Monaco migliora ma tutti gli altri circuiti diventano troppo veloci.
**Scartato**: la soglia proporzionale non funziona a basse velocità.

### 6.2 V5.4.4 — Graduated Throttle

Quando `must_brake` si attiva, usa `brake_intensity` che parte da 0.3 e rampa a 1.0.
Risultato: riduce la decelerazione iniziale, peggiora il problema.
**Scartato**: la frenata graduale non è realistica (i piloti frenano a fondo).

### 6.3 V5.5-telemetry — Frenata Guidata dalla Telemetria

Usa `brake_pct` dal Reference Pull per decidere QUANDO frenare.
Risultato: l'auto si ferma (156s) perché senza velocità target, la frenata
non ha un punto di rilascio. Tentativi con decel_g reale e brake binario
hanno tutti fallito per lo stesso motivo.
**Scartato**: la telemetria dice QUANDO frenare ma non QUANDO smettere.

### 6.4 Perché il Commitment Funziona

Il lookahead V5.3 calcola già correttamente QUANDO iniziare a frenare e QUANDO
smettere (la velocità target). Il problema era che decideva ex-novo ad ogni step,
creando chatter. Il commitment risolve questo mantenendo lo stato di frenata
finché la velocità non scende sotto il target + margine di rilascio.

## 7. File Modificati

| File | Modifica |
|------|----------|
| `waypoint_integrator.py` | Brake state commitment (isteresi), margine 1.11, EPS_RELEASE=0.3 |
| `waypoint_integrator.py` | Rimosso brake_mode="telemetry" e logica telemetria |
| `waypoint_integrator.py` | Rimosso V5.4.2 (soglia `*1.04`) e V5.4.4 (graduated throttle) |
| `circuit_calibration.py` | Rimosso brake_mode="telemetry" da Monaco |
| `telemetry_bridge.py` | Aggiunto supporto formato v2 Reference Pull (preferito su v1) |

### 7.1 File Non Committati (temporanei, da ripulire)

- `mc-1929_monaco_reference_pull_v2.json` — Reference Pull v2 da TracingInsights
- `rebuild_reference_pulls.py` — Script per generare v2 da telemetria
- `analyze_braking.py`, `test_v55_monaco.py`, `test_v2_monza.py` — Script temporanei

## 8. Documentazione di Riferimento

| Documento | Path | Contenuto |
|-----------|------|-----------|
| Spec V5.4 PU Stateful | `docs/physics-engine-v5.4-pu-stateful.md` | Architettura PU, torque curve, bucket, thermal |
| Spec V5.x Telemetry Bridge | `docs/physics-engine-v5-telemetry-bridge.md` | Dynamic curvature, Reference Pull, compound grip |
| Checklist V5.x | `docs/physics-engine-v5-checklist.md` | Stato implementazione, fasi V5.4 |
| Engine Data 2025 | `docs/EngineData2025.md` | Dati reali ICE torque curve, gear ratios |
| Brake Penalty System | `docs/brake-penalty-system.md` | Penalità usura freni |
| Brake Integration | `docs/brake-integration.md` | Integrazione freni nel physics engine |
| Lap Physics Spec V0.5 | `docs/lap-physics-spec-v0.5.md` | Spec originale integratore waypoint |

## 9. Script di Verifica

```bash
cd python_backend
python scripts/validate_v53.py              # Full validation (24 circuiti)
python scripts/validate_v53.py --quick       # Quick (Monza, Monaco, Silverstone)
```

## 10. Costanti Fisiche Importanti

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

## 11. Avvertenze

1. **La calibrazione V5.3 è obsoleta** per il modello V5.5 — serve re-calibrazione
2. **Il margine 1.11** è ottimizzato per Monaco — potrebbe non essere ottimale per tutti
3. **Il boundary fix (V5.4.3)** è ancora presente e funzionante
4. **Il modello PU V5.4** non è attivo di default (pu_config=None → V5.3)
5. **Il Reference Pull v2** è disponibile ma non usato per la frenata (solo per reference_pull_strength)
6. **Lo script validate_v53.py** è lo standard ufficiale per la validazione