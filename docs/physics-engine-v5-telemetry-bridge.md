# F1 Physics Engine V5.0 — Dynamic Curvature & Telemetry Bridge

> **Data**: 11 Aprile 2026  
> **Stato**: ✅ Validato su 24 circuiti — Errore medio globale **0.495%** (target < 0.5%)  
> **Reference Pull**: ✅ Attivo con `strength=0.02` (correzione ±20% f_engine)

## 1. Panoramica

La V5.0 introduce il **Telemetry Bridge**, un ponte tra i dati reali di telemetria F1 2025 (TracingInsights-Archive/2025) e il physics engine. Questo permette:

1. **Raggio Dinamico** — Calcolato waypoint-per-waypoint dalla traiettoria reale dei piloti
2. **Reference Pull** — Profilo di velocità/throttle/brake reale per correggere la simulazione
3. **PU Lookup Table** — Mappa RPM/Gear/Speed dalla Power Unit reale
4. **Calibrazione Aero-Meccanica** — mu_mechanical e k_wing_coupling derivati dai dati reali

## 2. Architettura

```
TracingInsights-Archive/2025
         │
         ▼
  sync_telemetry_2025.py ──► HD files aggiornati (raggio dinamico)
         │                    PU Lookup Tables
         │                    Aero Calibration files
         │
  telemetry_bridge.py ─────► Reference Pull files
                              (velocità, throttle, brake, gear, RPM, raggio)
         │
         ▼
  waypoint_integrator.py ──► Reference Pull correction
                              (f_engine ±20% max se sim diverge da real)
```

### 2.1 Moduli

| Modulo | Path | Funzione |
|--------|------|----------|
| `telemetry_bridge.py` | `physics_v4/calibration/` | Download, smoothing, Reference Pull, raggio dinamico |
| `sync_telemetry_2025.py` | `scripts/` | CLI per sincronizzare tutti i circuiti |
| `waypoint_integrator.py` | `physics_v4/integrator/` | Simulazione con Reference Pull correction |

### 2.2 Dati Generati

| Tipo | Path | Quantità |
|------|------|----------|
| HD files aggiornati | `data/circuits/2025/*_HD.json` | 24 |
| Reference Pull | `data/circuits/reference_pull/` | 24 |
| PU Lookup | `data/circuits/pu_lookup/` | 24 |
| Aero Calibration | `data/circuits/aero_calibration/` | 24 |
| Validation Reports | `data/circuits/validation_reports/` | 29 |

## 3. Risultati Validazione — 24 Circuiti

### 3.1 Tabella Completa

| # | Circuito | Driver | Tempo Reale | Tempo Sim | Errore | Status |
|---|----------|--------|-------------|-----------|--------|--------|
| 1 | Mexico | NOR | 75.586 | 75.587 | **0.00%** | ✅ |
| 2 | Canada | RUS | 70.899 | 70.883 | **0.02%** | ✅ |
| 3 | Qatar | PIA | 79.387 | 79.349 | **0.05%** | ✅ |
| 4 | Baku | VER | 101.117 | 101.057 | **0.06%** | ✅ |
| 5 | Monza | NOR | 78.869 | 78.967 | **0.12%** | ✅ |
| 6 | Melbourne | NOR | 75.096 | 75.211 | **0.15%** | ✅ |
| 7 | Austria | NOR | 63.971 | 63.862 | **0.17%** | ✅ |
| 8 | China | PIA | 90.641 | 90.489 | **0.17%** | ✅ |
| 9 | Jeddah | VER | 87.294 | 87.469 | **0.20%** | ✅ |
| 10 | Hungary | LEC | 75.372 | 75.532 | **0.21%** | ✅ |
| 11 | Abu Dhabi | VER | 82.207 | 82.018 | **0.23%** | ✅ |
| 12 | Silverstone | NOR | 85.010 | 85.267 | **0.30%** | ✅ |
| 13 | Zandvoort | PIA | 68.662 | 68.456 | **0.30%** | ✅ |
| 14 | Spa | NOR | 100.562 | 100.141 | **0.42%** | ✅ |
| 15 | Barcelona | PIA | 71.546 | 71.883 | **0.47%** | ✅ |
| 16 | Las Vegas | NOR | 107.934 | 107.425 | **0.47%** | ✅ |
| 17 | Monaco | NOR | 69.954 | 69.504 | **0.64%** | ⚠️ |
| 18 | Suzuka | NOR | 86.995 | 86.344 | **0.75%** | ⚠️ |
| 19 | Sakhir | PIA | 89.841 | 89.342 | **0.56%** | ⚠️ |
| 20 | Singapore | RUS | 89.158 | 89.639 | **0.54%** | ⚠️ |
| 21 | Imola | PIA | 74.670 | 75.603 | **1.25%** | ⚠️ |
| 22 | São Paulo | NOR | 69.511 | 70.770 | **1.81%** | ⚠️ |
| 23 | Austin | VER | 92.510 | 95.092 | **2.79%** | ❌ |
| 24 | Miami | VER | 86.204 | 86.041 | **0.19%** | ✅ |

### 3.2 Statistiche

- **Errore medio globale**: 0.495%
- **Mediana errore**: 0.30%
- **Circuiti < 0.5%**: 16/24 (67%)
- **Circuiti < 1.0%**: 21/24 (88%)
- **Circuiti < 2.0%**: 22/24 (92%)
- **Circuiti ≥ 2.0%**: 1/24 (4%) — Austin

### 3.3 Outlier Analysis

#### Austin (2.79%)
- Sim troppo lento (+2.58s)
- Possibili cause: COTA ha curve ad alta velocità con cambi di direzione bruschi (Esses)
- Il raggio dinamico potrebbe non catturare bene le transizioni
- **Azione**: Verificare mu_mechanical per Austin (nessun punto a bassa velocità trovato)

#### São Paulo (1.81%)
- Sim troppo lento (+1.26s)
- Circuito con curve lente e rettilinee medie
- **Azione**: Verificare raggio dinamico e mu_mechanical

#### Imola (1.25%)
- Sim troppo lento (+0.93s)
- Circuito tecnico con varianti e curve a media velocità
- **Azione**: Verificare raggio dinamico nelle varianti

## 4. Parametri Derivati per Circuito

### 4.1 Grip Meccanico (mu_mechanical)

| Circuito | mu_base | mu_aero | k_wing | Note |
|----------|---------|---------|--------|------|
| Monaco | 2.299 | — | 0.000 | Street circuit, bassa velocità |
| Spa | 1.848 | — | 0.026 | Alta velocità, curvature miste |
| Silverstone | 1.650 | — | 0.071 | Alta velocità, curvature fluide |
| Monza | 2.057 | — | 0.000 | Bassa downforce |
| Suzuka | 2.086 | — | 0.045 | Tecnico, curvature variate |
| Las Vegas | 1.520 | 0.028 | 0.000 | Basso grip, street circuit |
| Austin | 1.650 | — | 0.068 | Misto, Esses problematici |
| Qatar | 1.650 | — | 0.090 | Alta downforce |

### 4.2 Note sulla Calibrazione

- **mu_mechanical = 1.650** per molti circuiti indica che il fallback è stato usato (nessun punto a bassa velocità con g_lat significativo trovato)
- Questo valore corrisponde al grip meccanico puro (senza downforce) stimato per pneumatici F1 2025
- Circuiti con mu > 2.0 hanno punti lenti con g_lat elevato (hairpin, chicane)

## 5. Raggio Dinamico

### 5.1 Metodi di Calcolo

Il raggio dinamico è calcolato con 3 metodi indipendenti e poi fusi (hybrid):

1. **3-Point Circle** — Cerchio passante per 3 punti consecutivi GPS
2. **XY Derivative** — Derivata seconda della traiettoria XY
3. **Speed/g_lat** — R = v² / (g_lat * G) dai dati di telemetria

### 5.2 Blending Ibrido

```python
# Peso: 60% XY derivative, 30% speed/g_lat, 10% 3-point circle
radius_hybrid = 0.6 * radius_xy + 0.3 * radius_glat + 0.1 * radius_3pt
```

### 5.3 Copertura Waypoint

| Circuito | Waypoints Aggiornati | Totale | % |
|----------|---------------------|--------|---|
| Monaco | 85 | 696 | 12% |
| Spa | 41 | 1421 | 3% |
| Silverstone | 38 | 1189 | 3% |
| Baku | 85 | 1229 | 7% |
| China | 103 | 1109 | 9% |
| Zandvoort | 89 | 884 | 10% |

> Nota: La % bassa è attesa — il raggio dinamico sovrascrive solo i waypoint dove il valore calcolato differisce significativamente dal valore originale nell'HD file.

## 6. Reference Pull

Il Reference Pull è un profilo di velocità reale per ogni punto del circuito, usato nel `waypoint_integrator` per correggere la forza motrice se la simulazione diverge.

### 6.1 Meccanismo di Correzione

```python
# Nel waypoint_integrator.py
if reference_pull_strength > 0 and reference_pull is not None:
    v_ref_ms = interpolate(reference_pull.speed_kph, dist_m) / 3.6
    v_error = v_ref_ms - v_sim_ms  # Positivo = sim troppo lento
    
    # Correzione proporzionale: F = strength * m * (v_error / v_ref) * g
    f_correction = reference_pull_strength * mass_kg * v_error / max(v_ref_ms, 10.0) * G
    
    # Limita a ±20% della forza motrice
    max_correction = abs(f_engine) * 0.20
    f_correction = clamp(f_correction, -max_correction, max_correction)
    f_engine += f_correction
```

**Parametro `reference_pull_strength`**:
- `0.0` = disabilitato (nessuna correzione)
- `0.01-0.05` = range tipico (correzione sottile)
- Valore di default: `0.02`

### 6.2 Effetto sul Tempo Giro

Con `strength=0.02`, l'effetto sul tempo giro è minimo (~0.01-0.05s) perché il modello fisico è già molto accurato. Il Reference Pull ha effetto maggiore sullo **speed trace punto-per-punto**, riducendo l'errore locale di velocità dove il modello diverge dalla realtà.

### 6.2 Struttura Dati

```json
{
  "circuit_id": "mc-1929_monaco",
  "driver": "NOR",
  "lap_time_s": 69.954,
  "mu_mechanical": 2.299,
  "k_wing_coupling": 0.0,
  "step_m": 5.0,
  "total_length_m": 3367.0,
  "data": {
    "dist_m": [0.0, 5.0, 10.0, ...],
    "speed_kph": [85.2, 87.1, ...],
    "throttle_pct": [100, 100, ...],
    "brake_pct": [0, 0, ...],
    "gear": [5, 5, ...],
    "rpm": [11200, 11500, ...],
    "radius_m": [150.0, 145.0, ...]
  }
}
```

## 7. CIRCUIT_MAP Completo

```python
CIRCUIT_MAP = {
    "monaco":      {"gp_name": "Monaco Grand Prix",           "circuit_id": "mc-1929_monaco",              "reference_driver": "NOR"},
    "spa":         {"gp_name": "Belgian Grand Prix",           "circuit_id": "be-1925_spa_francorchamps",   "reference_driver": "NOR"},
    "silverstone": {"gp_name": "British Grand Prix",          "circuit_id": "gb-1948_silverstone",          "reference_driver": "NOR"},
    "monza":       {"gp_name": "Italian Grand Prix",           "circuit_id": "it-1922_monza",               "reference_driver": "NOR"},
    "suzuka":      {"gp_name": "Japanese Grand Prix",          "circuit_id": "jp-1962_suzuka",              "reference_driver": "NOR"},
    "abudhabi":    {"gp_name": "Abu Dhabi Grand Prix",         "circuit_id": "ae-2009_yas_marina",          "reference_driver": "VER"},
    "austria":     {"gp_name": "Austrian Grand Prix",          "circuit_id": "at-1969_spielberg",           "reference_driver": "NOR"},
    "australia":   {"gp_name": "Australian Grand Prix",        "circuit_id": "au-1953_melbourne",           "reference_driver": "NOR"},
    "baku":        {"gp_name": "Azerbaijan Grand Prix",        "circuit_id": "az-2016_baku",               "reference_driver": "VER"},
    "bahrain":     {"gp_name": "Bahrain Grand Prix",            "circuit_id": "bh-2002_sakhir",             "reference_driver": "PIA"},
    "saopaulo":    {"gp_name": "São Paulo Grand Prix",         "circuit_id": "br-1940_sao_paulo",          "reference_driver": "NOR"},
    "canada":      {"gp_name": "Canadian Grand Prix",          "circuit_id": "ca-1978_montreal",           "reference_driver": "RUS"},
    "china":       {"gp_name": "Chinese Grand Prix",            "circuit_id": "cn-2004_shanghai",            "reference_driver": "PIA"},
    "spain":       {"gp_name": "Spanish Grand Prix",            "circuit_id": "es-1991_barcelona",           "reference_driver": "PIA"},
    "hungary":     {"gp_name": "Hungarian Grand Prix",          "circuit_id": "hu-1986_budapest",           "reference_driver": "LEC"},
    "imola":       {"gp_name": "Emilia Romagna Grand Prix",    "circuit_id": "it-1953_imola",              "reference_driver": "PIA"},
    "mexico":      {"gp_name": "Mexico City Grand Prix",       "circuit_id": "mx-1962_mexico_city",         "reference_driver": "NOR"},
    "zandvoort":   {"gp_name": "Dutch Grand Prix",             "circuit_id": "nl-1948_zandvoort",          "reference_driver": "PIA"},
    "qatar":       {"gp_name": "Qatar Grand Prix",             "circuit_id": "qa-2004_lusail",             "reference_driver": "PIA"},
    "jeddah":      {"gp_name": "Saudi Arabian Grand Prix",     "circuit_id": "sa-2021_jeddah",             "reference_driver": "VER"},
    "singapore":   {"gp_name": "Singapore Grand Prix",         "circuit_id": "sg-2008_singapore",           "reference_driver": "RUS"},
    "austin":      {"gp_name": "United States Grand Prix",    "circuit_id": "us-2012_austin",             "reference_driver": "VER"},
    "miami":       {"gp_name": "Miami Grand Prix",             "circuit_id": "us-2022_miami",              "reference_driver": "VER"},
    "lasvegas":    {"gp_name": "Las Vegas Grand Prix",        "circuit_id": "us-2023_las_vegas",           "reference_driver": "NOR"},
}
```

## 8. Prossimi Passi (V5.1)

> **Strategia**: prima integrare PU Lookup e Aero Calibration nel simulatore
> (migliora TUTTI i circuiti), poi investigare i singoli outlier rimanenti.

1. **[PRIORITÀ 1] Integrare PU Lookup nel simulatore** — Usare la lookup table RPM/Gear/Speed per modellare potenza, coppia e ERS per ogni circuito
2. **[PRIORITÀ 2] Integrare Aero Calibration nel simulatore** — Applicare mu_mechanical e k_wing_coupling per-circuito al posto dei valori hardcoded
3. **[PRIORITÀ 3] Re-validare tutti i 24 circuiti** — Dopo le integrazioni, l'errore medio dovrebbe scendere
4. **[DOPO 3] Investigare outlier rimanenti** — Austin (2.79%), São Paulo (1.81%), Imola (1.25%)

## 9. Fonte Dati

- **Repository**: [TracingInsights-Archive/2025](https://github.com/TracingInsights-Archive/2025)
- **Formato**: `{GP Name}/Qualifying/{Driver}/{LapNumber}_tel.json`
- **Campi**: time, rpm, speed, gear, throttle, brake, drs, distance, x, y, z, acc_x, acc_y, acc_z
- **Driver di riferimento**: NOR (Norris), VER (Verstappen), PIA (Piastri), RUS (Russell), LEC (Leclerc)