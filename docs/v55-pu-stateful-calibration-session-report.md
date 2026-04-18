---
title: "V5.5 PU Stateful Activation & Calibration — Session Report 14/04/2026"
date: 2026-04-14
version: 5.5.1-pu-stateful-calibrated
status: COMPLETED — PU stateful attivato, 24/24 circuiti calibrati a 0.12% medio
authors: F1 Manager AI Physics Team
---

# V5.5 PU Stateful Activation & Calibration — Session Report

## 1. Contesto e Obiettivo

Il motore fisico V5.5 (Brake Commitment) era calibrato con il modello flat-power V5.3
per l'ERS. L'obiettivo era:
1. Attivare il modello PU stateful V5.4 come default (QUALIFY map)
2. Re-calibrare tutti i 24 circuiti per compensare le differenze di deploy ERS

Il modello PU stateful distribuisce l'energia ERS in modo più realistico:
- Deploy ERS solo nelle zone designate (primary/exit)
- SOC battery gestito per giro intero
- MGU-H direct power bypassando la batteria
- Thermal clipping per protezione componenti

## 2. Risultati Pre-Calibrazione (PU Stateful attivo, calibrazione V5.3)

| Metrica | Valore |
|---------|--------|
| Errore medio | 0.55% |
| Sotto 0.5% | 11/24 |
| Sotto 1.0% | 20/24 |
| Peggiore | Yas Marina 1.41% |

Il PU stateful ha un impatto differenziato per circuito:
- **Circuiti lenti/tortuosi** (Yas Marina, Shanghai): più lenti perché l'ERS non può deployare efficacemente nelle curve lente
- **Circuiti veloci/misti** (Las Vegas, Imola): più veloci perché l'ERS deploya efficacemente sui rettilineati

## 3. Bug Scoperto: Dual LRU Cache

Durante la calibrazione, abbiamo scoperto che `aero_calibration.py` viene caricato
come **due moduli Python diversi**:

- `calibration.aero_calibration` (via import relativo in waypoint_integrator.py)
- `lap_simulator.physics_v4.calibration.aero_calibration` (via import assoluto negli script)

Ogni modulo ha la propria `lru_cache`, quindi pulire una cache non ha effetto
sull'altra. Questo faceva sembrare che le modifiche a `mu_mechanical` non avessero
effetto sulla simulazione.

**Soluzione**: Pulire entrambe le cache quando si modifica un file di calibrazione:
```python
from calibration.aero_calibration import get_aero_calibration as cal1
from lap_simulator.physics_v4.calibration.aero_calibration import get_aero_calibration as cal2
cal1.cache_clear()
cal2.cache_clear()
```

**Fix permanente raccomandato**: Convertire gli import relativi in waypoint_integrator.py
a import assoluti, o usare una strategia di import singola.

## 4. Calibrazione mu_mechanical

La calibrazione usa binary search su `mu_mechanical` per ogni circuito, con target <0.3%.
Il parametro `mu_mechanical` controlla il grip meccanico a bassa velocità:
- Aumentare μ → più grip → tempi più veloci (per circuiti troppo lenti)
- Diminuire μ → meno grip → tempi più lenti (per circuiti troppo veloci)

### 4.1 Circuiti Calibrati (16/24)

| Circuito | μ vecchio | μ nuovo | Errore prima | Errore dopo |
|----------|----------|--------|-------------|------------|
| yas_marina | 1.360 | 1.530 | 1.41% | 0.20% |
| shanghai | 1.317 | 1.515 | 1.14% | 0.07% |
| las_vegas | 1.361 | 1.225 | 1.10% | 0.15% |
| imola | 1.600 | 1.400 | 1.07% | 0.07% |
| spa | 1.317 | 1.449 | 0.77% | 0.06% |
| austin | 1.783 | 1.694 | 0.76% | 0.10% |
| melbourne | 1.317 | 1.449 | 0.75% | 0.01% |
| monza | 1.600 | 1.760 | 0.75% | 0.07% |
| barcelona | 1.317 | 1.185 | 0.62% | 0.06% |
| lusail | 1.201 | 1.081 | 0.57% | 0.23% |
| montreal | 1.480 | 1.628 | 0.57% | 0.07% |
| sakhir | 1.550 | 1.473 | 0.53% | 0.03% |
| spielberg | 1.550 | 1.531 | 0.51% | 0.27% |
| mexico_city | 1.600 | 1.520 | 0.50% | 0.12% |
| baku | 1.480 | 1.554 | 0.45% | 0.08% |
| sao_paulo | 1.480 | 1.406 | 0.39% | 0.02% |

### 4.2 Circuiti Già Sotto 0.3% (8/24, nessuna calibrazione necessaria)

| Circuito | Errore |
|----------|--------|
| Singapore | 0.01% |
| Suzuka | 0.02% |
| Monaco | 0.11% |
| Jeddah | 0.25% |
| Zandvoort | 0.18% |
| Silverstone | 0.18% |
| Miami | 0.23% |
| Budapest | 0.16% |

## 5. Risultati Finali

| Metrica | V5.3 (flat) | V5.5 pre-cal | V5.5 calibrato |
|---------|-------------|-------------|----------------|
| Errore medio | 0.21% | 0.55% | **0.12%** |
| Sotto 0.5% | 24/24 | 11/24 | **24/24** |
| Sotto 1.0% | 24/24 | 20/24 | **24/24** |
| Peggiore | 0.47% | 1.41% | **0.27%** |
| Migliore | 0.03% | 0.01% | **0.01%** |

### Risultati per Circuito (V5.5 calibrato)

| # | Circuito | Reale (s) | Sim (s) | Errore |
|---|----------|-----------|---------|--------|
| 1 | Singapore | 89.158 | 89.146 | 0.01% |
| 2 | Melbourne | 75.096 | 75.087 | 0.01% |
| 3 | São Paulo | 69.511 | 69.527 | 0.02% |
| 4 | Sakhir | 89.841 | 89.816 | 0.03% |
| 5 | Suzuka | 86.995 | 86.975 | 0.02% |
| 6 | Shanghai | 90.641 | 90.577 | 0.07% |
| 7 | Monza | 78.869 | 78.926 | 0.07% |
| 8 | Imola | 74.670 | 74.725 | 0.07% |
| 9 | Barcelona | 71.546 | 71.505 | 0.06% |
| 10 | Spa | 100.562 | 100.627 | 0.06% |
| 11 | Baku | 101.117 | 101.203 | 0.08% |
| 12 | Austin | 92.510 | 92.602 | 0.10% |
| 13 | Mexico City | 75.586 | 75.676 | 0.12% |
| 14 | Monaco | 69.954 | 70.028 | 0.11% |
| 15 | Budapest | 75.372 | 75.494 | 0.16% |
| 16 | Las Vegas | 107.934 | 108.098 | 0.15% |
| 17 | Yas Marina | 82.207 | 82.375 | 0.20% |
| 18 | Silverstone | 85.010 | 85.159 | 0.18% |
| 19 | Zandvoort | 68.662 | 68.536 | 0.18% |
| 20 | Jeddah | 87.294 | 87.072 | 0.25% |
| 21 | Lusail | 79.387 | 79.569 | 0.23% |
| 22 | Miami | 86.204 | 86.002 | 0.23% |
| 23 | Spielberg | 63.971 | 63.797 | 0.27% |
| 24 | Montreal | 70.899 | 70.946 | 0.07% |

## 6. Modifiche al Codice

### waypoint_integrator.py
- **PU stateful attivo come default**: `pu_config=None` ora attiva QUALIFY map
- **Rimosso blocco verbose duplicato V5.4**: Il blocco `if verbose: print("⚡ V5.4 PU Stateful")` era duplicato

### File di calibrazione (16 circuiti)
- `python_backend/data/circuits/aero_calibration/*_aero_cal.json`
- `grip_data.mu_mechanical` aggiornato per 16 circuiti
- `grip_data.notes.v55_calibration` aggiunto con nota di calibrazione

### Script di calibrazione
- `python_backend/scripts/calibrate_v55_pu.py` — Script di calibrazione con binary search
- `python_backend/scripts/validate_v55_pu.py` — Script di validazione

## 7. Lezioni Apprese

1. **Dual LRU Cache Bug**: Gli import relativi vs assoluti in Python creano
   moduli diversi con cache separate. Sempre pulire tutte le cache quando si
   modificano file di configurazione.

2. **PU Stateful Impact**: Il modello PU stateful ha un impatto differenziato
   per circuito. I circuiti con lunghi rettilineati (Las Vegas, Imola) beneficiano
   del deploy ERS mirato, mentre i circuiti tortuosi (Yas Marina, Shanghai)
   perdono efficienza perché l'ERS non può deployare nelle curve lente.

3. **Calibrazione mu_mechanical**: Il parametro mu_mechanical è molto sensibile
   e permette correzioni precise dell'errore. Una variazione di ±0.1 in μ
   corrisponde a circa ±0.3-0.5% di errore nel tempo giro.

4. **Monaco Stability**: Monaco rimane stabile a 0.11% dopo la calibrazione,
   confermando che il Brake State Commitment risolve definitivamente il problema
   di oscillazione frenata.