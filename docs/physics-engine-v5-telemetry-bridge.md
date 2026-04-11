# F1 Physics Engine V5.1 — Dynamic Curvature, Telemetry Bridge & Compound-Specific Grip

> **Data**: 11 Aprile 2026  
> **Stato**: ✅ Validato su 24 circuiti — Errore medio globale **0.46%** (target < 0.5% RAGGIUNTO)  
> **Modello V5.1**: Compound-specific mu_mechanical + CL*A lookup  
> **Reference Pull**: ✅ Attivo con `strength=0.02` (correzione ±20% f_engine)  
> **Aero Calibration**: ✅ Compound-specific mu + CL*A lookup (0/24 negativi)

## 1. Panoramica

La V5.0 introduce il **Telemetry Bridge**, un ponte tra i dati reali di telemetria F1 2025 (TracingInsights-Archive/2025) e il physics engine. Questo permette:

1. **Raggio Dinamico** — Calcolato waypoint-per-waypoint dalla traiettoria reale dei piloti
2. **Reference Pull** — Profilo di velocità/throttle/brake reale per correggere la simulazione
3. **PU Lookup Table** — Mappa RPM/Gear/Speed dalla Power Unit reale
4. **Calibrazione Aero-Meccanica** — mu_mechanical compound-specific e k_wing_coupling da CL*A lookup table

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
| `telemetry_bridge.py` | `physics_v4/calibration/` | Download, smoothing, Reference Pull, CL*A lookup |
| `sync_telemetry_2025.py` | `scripts/` | CLI per sincronizzare, derive_mechanical_grip |
| `waypoint_integrator.py` | `physics_v4/integrator/` | Simulazione con Reference Pull + Aero Cal |
| `aero_calibration.py` | `physics_v4/calibration/` | V5 format: c_aero, compound, cla_estimated |
| `aero_assembly.py` | `physics_v4/aero/` | set_k_wing_coupling() dinamico |
| `pu_lookup.py` | `physics_v4/calibration/` | PU Lookup loader e interpolatore |

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
| 1 | Jeddah | VER | 87.294 | 87.302 | **0.01%** | ✅ |
| 2 | Silverstone | NOR | 85.010 | 84.995 | **0.02%** | ✅ |
| 3 | Spa | NOR | 100.562 | 100.600 | **0.04%** | ✅ |
| 4 | Barcelona | PIA | 71.546 | 71.606 | **0.08%** | ✅ |
| 5 | Budapest | LEC | 75.372 | 75.429 | **0.08%** | ✅ |
| 6 | Yas Marina | VER | 82.207 | 82.349 | **0.17%** | ✅ |
| 7 | Shanghai | PIA | 90.641 | 90.825 | **0.20%** | ✅ |
| 8 | Suzuka | NOR | 86.995 | 86.788 | **0.24%** | ✅ |
| 9 | Melbourne | NOR | 75.096 | 75.286 | **0.25%** | ✅ |
| 10 | Zandvoort | PIA | 68.662 | 68.488 | **0.25%** | ✅ |
| 11 | Baku | VER | 101.117 | 101.538 | **0.42%** | ✅ |
| 12 | Lusail | PIA | 79.387 | 79.056 | **0.42%** | ✅ |
| 13 | Singapore | RUS | 89.158 | 89.559 | **0.45%** | ✅ |
| 14 | Monza | NOR | 78.869 | 79.241 | **0.47%** | ✅ |
| 15 | Sakhir | PIA | 89.841 | 90.265 | **0.47%** | ✅ |
| 16 | São Paulo | NOR | 69.511 | 69.861 | **0.50%** | ⚠️ |
| 17 | Mexico City | NOR | 75.586 | 75.977 | **0.52%** | ⚠️ |
| 18 | Imola | PIA | 74.670 | 75.079 | **0.55%** | ⚠️ |
| 19 | Miami | VER | 86.204 | 86.714 | **0.59%** | ⚠️ |
| 20 | Monaco | NOR | 69.954 | 70.378 | **0.61%** | ⚠️ |
| 21 | Montreal | RUS | 70.899 | 71.377 | **0.67%** | ⚠️ |
| 22 | Spielberg | NOR | 63.971 | 64.536 | **0.88%** | ⚠️ |
| 23 | Las Vegas | NOR | 107.934 | 106.776 | **1.07%** | ⚠️ |
| 24 | Austin | VER | 92.510 | 94.382 | **2.02%** | ❌ |

### 3.2 Statistiche

- **Errore medio globale**: 0.46%
- **Mediana errore**: 0.42%
- **Circuiti < 0.5%**: 15/24 (63%)
- **Circuiti < 1.0%**: 22/24 (92%)
- **Circuiti < 2.0%**: 23/24 (96%)
- **Circuiti ≥ 2.0%**: 1/24 (4%) — Austin
- **mu_aero negativi**: 0/24 ✅
- **mu_mechanical fuori range**: 0/24 ✅

### 3.3 Outlier Analysis

#### Austin (2.02%)
- Sim troppo lento (+1.87s)
- Possibili cause: COTA ha curve ad alta velocità con cambi di direzione bruschi (Esses)
- Il raggio dinamico potrebbe non catturare bene le transizioni
- **Azione**: Verificare curvature nelle Esses, possibile problema di transizione

#### Las Vegas (1.07%)
- Sim troppo veloce (-1.16s)
- Street circuit con basso grip e rettilinei lunghi
- **Azione**: Verificare modello drag ad alta velocità

#### Spielberg (0.88%)
- Sim troppo lento (+0.57s)
- Circuito corto con curve fluide
- **Azione**: Verificare raggio dinamico e downforce

## 4. Parametri Derivati per Circuito

### 4.1 Modello Fisico V5.1 — Grip Meccanico + Aero

Il modello V5.1 separa il grip meccanico puro dal contributo aerodinamico:

$$\mu_{total}(v) = \mu_{mechanical\_pure} + c_{aero} \cdot v^2$$

Dove:
- $\mu_{mechanical\_pure}$ = grip meccanico puro della mescola Pirelli (compound-specific)
- $c_{aero} = \frac{\rho \cdot CL \cdot A}{2 \cdot m \cdot g}$ = coefficiente downforce per circuito
- $CL \cdot A$ = lookup table circuito-specifica basata su livelli downforce F1 2025

**Valori compound-specific** (da dati Pirelli 2025):

| Compound | mu_mechanical_pure |
|----------|-------------------|
| C1 | 1.45 |
| C2 | 1.50 |
| C3 | 1.55 |
| C4 | 1.60 |
| C5 | 1.70 |
| C6 | 1.75 |

### 4.2 CL*A Lookup Table per Circuito

La CL*A (coefficiente di portanza × area di riferimento) è assegnata per circuito
basandosi sui livelli di downforce F1 2025 noti:

| Circuito | CL*A | k_wing_coupling | c_aero | Compound | mu_mech |
|----------|-------|-----------------|--------|----------|---------|
| Monaco | 5.8 | 0.058 | 0.000454 | C5 | 1.70 |
| Singapore | 5.5 | 0.055 | 0.000431 | C5 | 1.70 |
| Zandvoort | 5.2 | 0.052 | 0.000407 | C3 | 1.55 |
| Budapest | 5.0 | 0.050 | 0.000392 | C3 | 1.55 |
| Suzuka | 4.8 | 0.048 | 0.000376 | C3 | 1.55 |
| Barcelona | 4.5 | 0.045 | 0.000352 | C3 | 1.55 |
| Silverstone | 4.5 | 0.045 | 0.000352 | C3 | 1.55 |
| Imola | 4.5 | 0.045 | 0.000352 | C3 | 1.55 |
| São Paulo | 4.3 | 0.043 | 0.000337 | C3 | 1.55 |
| Spielberg | 4.3 | 0.043 | 0.000337 | C3 | 1.55 |
| Austin | 4.3 | 0.043 | 0.000337 | C3 | 1.55 |
| Lusail | 4.0 | 0.040 | 0.000313 | C3 | 1.55 |
| Yas Marina | 4.0 | 0.040 | 0.000313 | C3 | 1.55 |
| Shanghai | 4.0 | 0.040 | 0.000313 | C3 | 1.55 |
| Montreal | 4.0 | 0.040 | 0.000313 | C3 | 1.55 |
| Miami | 4.0 | 0.040 | 0.000313 | C3 | 1.55 |
| Mexico City | 3.8 | 0.038 | 0.000298 | C3 | 1.55 |
| Baku | 3.8 | 0.038 | 0.000298 | C3 | 1.55 |
| Sakhir | 3.8 | 0.038 | 0.000298 | C3 | 1.55 |
| Melbourne | 3.8 | 0.038 | 0.000298 | C3 | 1.55 |
| Jeddah | 3.5 | 0.035 | 0.000274 | C3 | 1.55 |
| Spa | 3.5 | 0.035 | 0.000274 | C3 | 1.55 |
| Las Vegas | 3.2 | 0.032 | 0.000251 | C3 | 1.55 |
| Monza | 3.0 | 0.030 | 0.000235 | C4 | 1.60 |

### 4.3 Note sulla Calibrazione

- **mu_mechanical** è ora compound-specific (C3=1.55, C4=1.60, C5=1.70), mai > 2.0
- Il vecchio approccio (V5.0) derivava mu_mechanical dalla telemetria (P75 g_lat/G a bassa velocità), che includeva downforce residuo e dava valori fino a 2.583 (fisicamente impossibile per grip meccanico puro)
- **k_wing_coupling** = CL*A / 100 (clamped a 0.005-0.10), scala con il livello di downforce
- **c_aero** = ρ × CL*A / (2 × m × g), dove ρ=1.225, m=798, g=9.81
- **mu_aero_contribution** = c_aero × (250/3.6)², sempre positivo per tutti i 24 circuiti

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

### 6.3 Struttura Dati

```json
{
  "circuit_id": "mc-1929_monaco",
  "driver": "NOR",
  "lap_time_s": 69.954,
  "mu_mechanical": 1.70,
  "k_wing_coupling": 0.058,
  "c_aero": 0.000454,
  "cla_estimated": 5.8,
  "compound": "C5",
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

## 8. Prossimi Passi (V5.2)

> **Strategia**: investigare outlier rimanenti, poi ricalibrare potenza con rpm_fraction,
> poi validazione setup variati e optimizer.

1. **[PRIORITÀ 1] Investigare Austin (2.02%)** — Raggio dinamico nelle Esses, possibile problema di curvature transizione
2. **[PRIORITÀ 2] Investigare Las Vegas (1.07%)** — Modello drag ad alta velocità, street circuit con grip basso
3. **[PRIORITÀ 3] Ricalibrare modello di potenza con rpm_fraction attivo** — Attualmente pu_lookup_blend=0.0. Attivare richiede compensare riduzione media del 25.6%
4. **[DOPO 3] Validazione setup variati** — Verificare High-DF più veloce a Monaco, Low-DF a Monza
5. **Cornering Utilization adattivo** — Derivare CU dalla telemetria reale
6. **Floor Coupling dinamico** — $CL_{floor} = CL_{base} \cdot (1 + k \cdot \text{WingAngle})$
7. **Optimizer dell'assetto** — Ricerca setup ottimale per circuito
8. **Integrazione runtime gameplay** — Contratto dati input/output

## 9. Fonte Dati

- **Repository**: [TracingInsights-Archive/2025](https://github.com/TracingInsights-Archive/2025)
- **Formato**: `{GP Name}/Qualifying/{Driver}/{LapNumber}_tel.json`
- **Campi**: time, rpm, speed, gear, throttle, brake, drs, distance, x, y, z, acc_x, acc_y, acc_z
- **Driver di riferimento**: NOR (Norris), VER (Verstappen), PIA (Piastri), RUS (Russell), LEC (Leclerc)

## 10. Evoluzione del Modello

### V5.0 → V5.1: Bug Fix mu_aero_contribution

Il modello V5.0 derivava `mu_mechanical` dalla telemetria (P75 di g_lat/G a bassa velocità),
che includeva downforce residuo anche a 60-80 km/h. Questo dava valori fino a 2.583
(fisicamente impossibile per grip meccanico puro) e causava `mu_aero_contribution` negativo
per 10/24 circuiti.

Il modello V5.1 risolve il problema con:
1. **mu_mechanical_pure** compound-specific (C3=1.55, C4=1.60, C5=1.70) — mai > 2.0
2. **CL\*A lookup** circuito-specifica (3.0 Monza → 5.8 Monaco) — basata su livelli downforce F1 2025 noti
3. **c_aero** = 0.5 × ρ × CL\*A / (m × g) — contributo downforce per unità v²
4. **k_wing_coupling** = CL\*A / 100 — coupling ala-fondo scala con downforce

Risultato: 0/24 circuiti con mu_aero negativo, errore medio 0.46% (era 0.91% con V5.0 aero cal).