---
title: FastF1-Derived Circuit Layout Pipeline
last_updated: 2026-02-06
---

## Objective
Create a reproducible pipeline that turns raw FastF1 telemetry feeds into a single authoritative circuit JSON used by both the physics backend and the race UI. The resulting file must encode geometry, sectors, DRS information, and circuit physics metadata so that no separate GeoJSON/mapping/config artifacts are required.

## Data Sources
1. **FastF1 Session Telemetry** (`fastf1` Python package)
   - `session.get_circuit_info().corners`: official distances/naming for corners & sectors.
   - `session.laps.pick_fastest().get_telemetry()`: ordered `(Distance, X, Y)` samples for a clean lap.
   - `session.car_data`, `session.pos_data`: raw channels (RPM, Speed, Gear, Throttle, Brake, DRS channel 45, positional X/Y/Z).
2. **Race Control Messages**
   - Provide DRS detection/activation enable/disable timestamps and descriptions.
3. **Legacy Parameters** (optional initial seed)
   - Reuse existing `legacy_parameters` (grip, drag, tyre multipliers, pit delta) until we replace them with computed equivalents.

## Target JSON Schema (proposal)
```jsonc
{
  "circuit_id": "sa-2021_jeddah",
  "name": "Jeddah Corniche Circuit",
  "year": 2025,
  "length_m": 6102,
  "layout": {
    "points": [
      { "distance": 0.0, "x": 123.4, "y": -56.7 },
      ... (monotonic by distance)
    ],
    "polyline_precision": "meters",
    "bbox": { "min_x": ..., "max_x": ..., "min_y": ..., "max_y": ... }
  },
  "corners": [
    { "number": 1, "name": "Turn 1", "distance": 580.3, "x": ..., "y": ... },
    ...
  ],
  "sectors": [
    { "id": 1, "start_m": 0, "end_m": 2000 },
    { "id": 2, "start_m": 2000, "end_m": 4100 },
    { "id": 3, "start_m": 4100, "end_m": 6102 }
  ],
  "drs_zones": [
    {
      "detection_m": 1505,
      "activation_m": 1712,
      "end_m": 2450,
      "detection_xy": { "x": ..., "y": ... },
      "activation_xy": { "x": ..., "y": ... },
      "end_xy": { "x": ..., "y": ... }
    }
  ],
  "physics": {
    "reference_grip": 1.21,
    "aerodynamic_drag": 88.4,
    "downforce_importance": 1.8,
    "pit_lane_time": 24.0,
    "tyre_multipliers": { "SOFT": 1.15, "MEDIUM": 1.05, "HARD": 0.94 }
  },
  "metadata": {
    "country": "Saudi Arabia",
    "city": "Jeddah",
    "lap_record": null,
    "source": "FastF1 v3.7.0",
    "generated_at": "2026-02-06T00:05:00Z"
  }
}
```

## Pipeline Steps
1. **Session Selection**
   - Inputs: year, event name/location, session type (prefer Qualifying or Race).
   - Use `fastf1.get_session(...).load()` once per circuit (cache enabled).

2. **Lap Extraction**
   - Pick a representative lap (`laps.pick_fastest()` as default).
   - Pull telemetry DataFrame with `Distance`, `X`, `Y`, `nGear`, `Throttle`, `Brake`, `DRS`.

3. **Layout Generation**
   - Sort by `Distance`.
   - Remove duplicated/NaN segments.
   - Resample to a fixed resolution (e.g., every 5 meters) via interpolation.
   - Compute bounding box and store raw coordinates.

4. **Corner & Sector Mapping**
   - Read `session.get_circuit_info().corners` for official distances and names.
   - For each entry, find the nearest point in the layout to capture coordinates.
   - Derive sector boundaries: use `Sector` column if provided, otherwise fallback to `length/3`.

5. **DRS Zone Detection**
   - Scan `RaceControlMessages` for `Category == "Drs"`.
   - Parse detection/activation strings (e.g., "DRS detection zone 1 at turn 4").
   - Optionally combine con `car_data[channel 45]`: identify stretches dove `DRS == 8/10` per driver e mediare le distanze.
   - Save detection/activation/end in metri + convertiti in XY tramite layout lookup.

6. **Physics Block**
   - Reuse legacy parameters per circuito (dal mapping JSON attuale) come seed.
   - In futuro calcolare grip/drag direttamente dai dati (vedi `circuit_mapping_generator_final.py`).

7. **Serialization**
   - Validare con schema JSON (pydantic/dataclasses) per garantire consistenza.
   - Scrivere in `python_backend/circuits/generated/<circuit_id>.json` o sostituire gli attuali file dopo QA.

8. **Integration Plan**
   - Backend: aggiornare `generate_circuit_config.py` per leggere il nuovo circuito JSON invece di tre file separati.
   - Frontend/race UI: aggiornare map renderer per tracciare `layout.points` e posizionare le vetture mappando `distance -> XY`.
   - Physics engine: leggere `physics` + `sectors` + `drs_zones` dal nuovo formato.

## Open Questions / Next Steps
1. Confermare formato definitivo (serve compatibilità retro? versioning?).
2. Definire strategia per ricavare DRS detection/activation in modo affidabile (messaggi vs elaborazione canale 45).
3. Scegliere algoritmo di smoothing (spline, moving average) per layout pulito ma fedele.
4. Pianificare migrazione graduale: generazione batch → confronto con GeoJSON legacy → switch nel backend → rimozione artefatti vecchi.

## Implementation Checklist
- [ ] Script `scripts/build_circuit_from_fastf1.py`:
  - CLI: `--year`, `--event`, `--session`, `--output`.
  - Usa FastF1 per tutte le estrazioni sopra.
  - Produce JSON conforme allo schema.
- [ ] Test pilota (es. Bahrain) e confronto visuale.
- [ ] Aggiornare documentazione backend/UI per il nuovo formato.
- [ ] Pianificare rigenerazione per tutti i circuiti (batch + validazione automatica).
