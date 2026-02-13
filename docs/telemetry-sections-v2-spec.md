---
title: Telemetry Sections v2 – Regeneration Spec
version: 1.0
last_updated: 2026-02-13
status: completed
branch: feature/telemetry-sections-v2
scope: "Rigenerare le sezioni circuito dai punti telemetrici raw per ottenere copertura 100%, confini fisici corretti e dati derivati affidabili"
parent_spec: docs/lapsimulator-implementation-spec.md
blocking: "LapSimulator calibration (§6.11)"

## 0. Stato

- 24/24 circuiti rigenerati con dataset v2 (copertura 100%, dt_ref_s, braking_energy, DRS, radius, heat/cool reali).
- LapSimulator aggiorna `SectionContext`/`config_loader` per leggere i nuovi campi con fallback.
- `update_section()` usa il modello `dt_ref` per tutte le sezioni e i test `python_backend/lap_simulator/tests/test_e2e_practice.py` passano con la telemetria v2.

## 1. Problema

Le sezioni nei file `*_Telemetry.json` attuali (24 circuiti) hanno difetti strutturali che impediscono la calibrazione del LapSimulator:

1. **Gap di copertura**: le sezioni non coprono il 100% del circuito (es. Monza: 856m gap, 15%)
2. **avg_speed inaffidabile**: è la velocità "caratteristica" (apex/punta), non la media reale
3. **Confini non allineati**: non corrispondono ai punti naturali del profilo velocità (frenata, apex, accelerazione)
4. **Dati derivati mancanti**: braking_energy, DRS zones, radius curva non calcolati

Le sezioni provengono dai file `Raw_2024/*_mapping.json`, definiti manualmente.

## 2. Dati disponibili

I **punti telemetrici** nei file Telemetry JSON sono corretti e completi:

| Campo | Range | Uso per segmentazione |
|-------|-------|----------------------|
| `distance` | 0 → circuit_length | Posizione lungo il circuito |
| `speed` | kph | Profilo velocità → confini sezione |
| `timestamp` | 0 → lap_time | dt_ref per sezione |
| `throttle` | 0-100% | Identificare fasi accelerazione |
| `brake` | 0-100% | Identificare frenata + braking_energy |
| `gear` | 1-8 | Conferma tipo sezione |
| `drs` | 8/10/12/14 | Zone DRS (valori FastF1) |
| `x, y` | coordinate metriche | Calcolo radius curva |

**778 punti** per Monza, copertura completa 0s → 101.117s.

Valori DRS FastF1: 0/1 = off, 8 = eligible, 10/12/14 = active (varie fasi).

## 3. Algoritmo di segmentazione

### 3.1 Principio

Identificare i **confini naturali** del profilo velocità basandosi su transizioni di stato del pilota:
- **Inizio frenata**: throttle scende sotto soglia E/O brake sale sopra soglia
- **Apex**: punto di velocità minima locale in una zona di frenata
- **Uscita curva**: throttle torna sopra soglia dopo un apex
- **Velocità di punta**: velocità massima locale prima della prossima frenata

### 3.2 Fasi dell'algoritmo

```
Input: telemetry_points[] ordinati per distance
Output: sections[] con copertura 100%

1. DETECT BRAKE ZONES
   Per ogni punto, calcolare:
   - is_braking = brake > BRAKE_THRESHOLD (es. 5%)
   - is_coasting = throttle < THROTTLE_LOW (es. 20%) AND brake < BRAKE_THRESHOLD
   - is_accelerating = throttle > THROTTLE_HIGH (es. 80%)
   
   Raggruppare punti consecutivi in_braking/coasting in "brake events"

2. FIND APEXES
   Per ogni brake event, trovare il punto con speed minima → apex
   Validare: apex deve avere speed < speed_entry * 0.85 (frenata significativa)

3. FIND SPEED PEAKS
   Tra due apex consecutivi, trovare il punto con speed massima → peak
   Il peak è il punto di velocità di punta del rettifilo

4. DEFINE SECTION BOUNDARIES
   Per ogni coppia (peak_i, apex_i, peak_i+1):
   - Sezione "Braking": da brake_start a apex (dove brake > threshold)
   - Sezione "Corner": da apex a throttle_recovery (dove throttle > 80%)
   - Sezione "Acceleration": da throttle_recovery a peak successivo
   
   Oppure (più semplice, approccio scelto):
   - Sezione tipo "Straight": da peak/recovery a inizio frenata successiva
   - Sezione tipo "Corner": da inizio frenata a fine accelerazione post-curva
   
   Questo produce sezioni che includono frenata+curva+accelerazione come unità logica.

5. CLASSIFY SECTIONS
   Per ogni sezione:
   - v_min = velocità minima nella sezione
   - v_max = velocità massima nella sezione
   - Se v_min/v_max > 0.85 → "Straight" o "MediumStraight"
   - Se v_min < 100 kph → "SlowCorner"
   - Se v_min < 180 kph → "MediumCorner"  
   - Altrimenti → "FastCorner"
   
   Raffinamento con gear: se gear_min ≤ 3 → SlowCorner

6. COMPUTE DERIVED DATA
   Per ogni sezione:
   - avg_speed = media pesata per distanza dei punti
   - dt_ref = Σ(ds/v) integrazione trapezoidale
   - v_entry = speed del primo punto
   - v_exit = speed dell'ultimo punto
   - v_min = velocità minima (apex)
   - v_max = velocità massima
   - braking_energy_mj = stima da ΔKE = 0.5 * m * (v_entry² - v_min²) / 1e6
   - drs_active = qualsiasi punto con drs ∈ {10, 12, 14}
   - radius_m = calcolato da coordinate x,y (fitting cerchio sui punti curva)
   - corner_number = numerazione progressiva delle curve
```

### 3.3 Parametri di soglia

| Parametro | Valore | Note |
|-----------|--------|------|
| `BRAKE_THRESHOLD` | 5% | Sotto = no braking |
| `THROTTLE_LOW` | 20% | Sotto = coasting/braking |
| `THROTTLE_HIGH` | 80% | Sopra = full acceleration |
| `MIN_SECTION_LENGTH_M` | 30 | Sezioni più corte vengono fuse |
| `MIN_SPEED_DROP_PCT` | 15% | v_min/v_max < 0.85 per classificare come curva |
| `CAR_MASS_KG` | 798 | Per calcolo braking_energy (peso minimo F1 2024) |
| `SMOOTHING_WINDOW` | 5 | Punti per smoothing velocità (evita falsi apex) |

### 3.4 Calcolo radius curva

Per i punti nella zona curva (tra inizio frenata e fine accelerazione):
```python
# Fitting cerchio su punti (x, y) nella sezione curva
# Metodo: least squares circle fit
# radius = 1 / curvature
# Se radius > 1000m → rettifilo (curvatura trascurabile)
```

## 4. Schema output sezione v2

```json
{
  "id": "sec_01",
  "name": "Main Straight",
  "kind": "Straight",
  "start_m": 0.0,
  "end_m": 1120.5,
  "length_m": 1120.5,
  "corner_number": 0,
  
  "v_entry_kph": 337.0,
  "v_exit_kph": 302.0,
  "v_min_kph": 337.0,
  "v_max_kph": 339.0,
  "avg_speed_kph": 338.2,
  "dt_ref_s": 11.94,
  
  "braking_energy_mj": 0.0,
  "drs_active": true,
  "radius_m": null,
  
  "heat_factor": 0.2,
  "cool_factor": 1.2,
  "bumpiness_factor": 0.0,
  "kerb_severity": 0.0,
  
  "telemetry_point_start_idx": 0,
  "telemetry_point_end_idx": 85
}
```

### 4.1 Campi nuovi rispetto a v1

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `v_entry_kph` | float | Velocità al primo punto della sezione |
| `v_exit_kph` | float | Velocità all'ultimo punto della sezione |
| `v_min_kph` | float | Velocità minima (apex per curve) |
| `v_max_kph` | float | Velocità massima (punta per rettilinei) |
| `avg_speed_kph` | float | Media pesata per distanza (REALE) |
| `dt_ref_s` | float | Tempo reale dalla telemetria (integrazione) |
| `braking_energy_mj` | float | Energia cinetica dissipata in frenata |
| `drs_active` | bool | DRS disponibile in questa sezione |
| `radius_m` | float/null | Raggio curva (null per rettilinei) |
| `telemetry_point_start_idx` | int | Indice primo punto telemetrico |
| `telemetry_point_end_idx` | int | Indice ultimo punto telemetrico |

### 4.2 Vincoli di validazione

Per ogni circuito rigenerato:
1. `Σ(length_m)` = `circuit_length` (copertura 100%, tolleranza < 1m)
2. `Σ(dt_ref_s)` = `reference_lap.lap_time` (tolleranza < 0.1s)
3. Nessun gap tra sezioni: `section[i].end_m == section[i+1].start_m`
4. `v_entry` di sezione i+1 ≈ `v_exit` di sezione i (continuità, tolleranza < 5 kph)
5. Per curve: `v_min < v_entry` e `v_min < v_exit`
6. Per rettilinei: `v_min/v_max > 0.80`

## 5. Impatto sui file esistenti

### 5.1 File da rigenerare
- 24 file `python_backend/data/circuits/*_Telemetry.json` → sezione `geometry.sections` sostituita
- I `telemetry_points` e `reference_lap` restano invariati

### 5.2 File da aggiornare nel LapSimulator (branch `feature/lapsimulator-runtime`)
- `data_types.py` → aggiungere campi v_entry, v_exit, v_min, v_max, dt_ref_s a `SectionContext`
- `config_loader.py` → leggere i nuovi campi
- `update_section.py` → usare `dt_ref_s` come ancora per il calcolo tempo

### 5.3 File da aggiornare nei profili derivati
- `config/circuits/derived/<cid>/` → i profili derivati (tyre, brake, PU, damage) non cambiano struttura ma i valori per-sezione (heat_factor, cool_factor) vanno ricalcolati sulle nuove sezioni

## 6. Script di rigenerazione

```
scripts/regenerate_telemetry_sections.py

Input:  python_backend/data/circuits/<cid>_Telemetry.json (con telemetry_points)
Output: stesso file con geometry.sections sostituita (v2)

Flags:
  --circuit-id <cid>     Rigenera un singolo circuito
  --all                  Rigenera tutti i 24 circuiti
  --validate             Solo validazione senza sovrascrittura
  --report               Genera report HTML con grafici velocità + confini sezione
  --dry-run              Mostra output senza scrivere
```

## 7. Piano di implementazione

1. **Script core**: algoritmo di segmentazione (detect brakes → find apexes → define boundaries → classify → compute derived)
2. **Validazione Monza**: rigenerare Monza e verificare vincoli §4.2
3. **Report visuale**: grafico velocità con confini sezione sovrapposti
4. **Tutti i circuiti**: rigenerare tutti i 24 e validare
5. **Aggiornare LapSimulator**: integrare nuovi campi e ricalcolare con dt_ref

## 8. Criteri di successo

- [ ] 24/24 circuiti rigenerati con copertura 100%
- [ ] Σ(dt_ref) = lap_time ± 0.1s per ogni circuito
- [ ] Nessun gap tra sezioni
- [ ] avg_speed coerente con punti telemetrici
- [ ] braking_energy > 0 per tutte le sezioni con frenata
- [ ] DRS zones mappate correttamente
- [ ] radius_m calcolato per tutte le curve
- [ ] LapSimulator su Monza produce lap time ± 5s dal riferimento
