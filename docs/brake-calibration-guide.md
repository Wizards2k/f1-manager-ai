---
title: Brake Calibration & Migration – Manual Workflow
last_updated: 2026-02-18
status: draft
scope: "Istruzioni operative per aggiornare i file JSON dei freni e consumarli in runtime/UI"
---

## 1. Obiettivo
Documentare come mantenere manualmente i file `config/calibration/brakes/<circuit_id>.json` finché non verrà introdotto uno script automatico. Il contenuto guida:
- quali dati leggere dalle telemetrie 2025.
- come aggiornare i JSON di calibrazione esistenti.
- dove vengono consumati (LapSimulator, UI/HUD, QA tests).

## 2. Struttura del file di calibrazione
Ogni JSON segue lo schema già usato da `jp-1962_suzuka.json` / `ae-2009_yas_marina.json`:

```json
{
  "_meta": {
    "version": "0.1",
    "circuit_id": "xx-YYYY_name",
    "stats": {
      "total_brake_mj": 0.0,
      "brake_density": 0.0,
      "avg_brake_section": 0.0,
      "p75_brake_section": 0.0,
      "p90_brake_section": 0.0,
      "peak_brake_section": 0.0,
      "avg_heat_factor": 0.0,
      "avg_bump_factor": 0.0,
      "length_km": 0.0
    },
    "notes": "Derived from telemetry braking energy and thermal factors"
  },
  "brake_profile": {
    "regen_brake_base": 0.65,
    "regen_migration_bias": -0.40,
    "hydraulic_vs_regen_ratio": 1.30,
    "cooling_targets": {
      "front_delta": -0.12,
      "rear_delta": -0.08
    },
    "fade_threshold": {
      "front_c": 880,
      "rear_c": 780
    },
    "fade_sensitivity": {
      "front": 16,
      "rear": 13
    },
    "heat_capacity": {
      "front": 1.25,
      "rear": 1.10
    },
    "thermal_mass": {
      "front": 1.08,
      "rear": 0.95
    }
  },
  "sections": [
    {
      "id": "sec_01",
      "name": "Turn 1",
      "braking_energy_mj": 2.15,
      "heat_factor": 1.35,
      "bumpiness_factor": 0.10,
      "length_m": 220.0
    }
  ]
}
```

### Campi principali
- **`_meta.stats`**: riassunto della telemetria (somma energia frenata, densità MJ/km, percentili).
- **`brake_profile`**: coefficienti globali usati da LapSimulator.
  - `regen_brake_base` e `hydraulic_vs_regen_ratio` → guidano la ripartizione MGU-K vs idraulico.
  - `cooling_targets.front_delta/rear_delta` → target aperture duct rispetto allo standard.
  - `fade_threshold`/`fade_sensitivity`/`heat_capacity`/`thermal_mass` → parametri termici/fade.
- **`sections[]`**: elenco delle frenate più rilevanti con energia, heat factor e lunghezza (serve al Degradation loop per warning localizzati).

## 3. Procedura manuale di aggiornamento
1. **Recupero telemetria**
   - Aprire `python_backend/data/circuits/<season>/<circuit_id>_Telemetry.json`.
   - Filtrare le sezioni con campo `braking_energy_mj` > 0.
   - Calcolare statistiche (sum/percentili) con un foglio di calcolo o script ad hoc.
2. **Stimare coefficienti**
   - `total_brake_mj` = somma di tutte le frenate; `brake_density = total / (track_length_km)`.
   - `avg_brake_section`, `p75`, `p90`, `peak` = statistiche sulle frenate individuali.
   - `regen_brake_base`: default 0.65, aumentare per circuiti con molte frenate medio-lunghe.
   - `hydraulic_vs_regen_ratio`: >1 rende il contributo idraulico dominante; <1 enfatizza l’MGU-K.
   - `cooling_targets`: usare `setup_mapping_v2.json` → campo `cooling_guidance.brake_front/back` come riferimento. Impostare delta (es. `-0.12` = aprire i duct del 12% in più).
   - `fade_threshold`: front tipicamente 850–900°C, rear 750–800°C. Spostare in alto se `p90_brake_section` è bassa.
   - `heat_capacity`/`thermal_mass`: partire da 1.0 e modulare ±0.2 in base a densità MJ/km.
3. **Sezioni**
   - Ordinare le frenate decrescenti per `braking_energy_mj` e riportare almeno le prime 10 (o tutte >1.0 MJ).
   - Copiare `heat_factor`/`bumpiness_factor` dai dati telemetrici per ogni sezione.
4. **Salvataggio**
   - Scrivere/aggiornare il file `config/calibration/brakes/<circuit_id>.json` mantenendo ordinamento e formattazione.
   - Aggiornare `notes` con data/telemetria di riferimento.

## 4. Consumo dei dati
- **LapSimulator (`python_backend/lap_simulator/power_unit.py`, `brake_system.py`)**
  - Durante `update_section` legge i parametri per calcolare temperatura, fade e torque split. I campi `sections[]` servono per accentuare warning nelle frenate critiche.
- **Derived profiles**
  - `scripts/build_circuit_profiles.py` fonde i nuovi JSON con i seed globali per generare `config/circuits/derived/<circuit_id>/brake_params.json` (usati a runtime).
- **UI / PU Modal (`player_garage_v3.js`)**
  - Le guidance su `brake bias`, `duct opening`, warning “Brake fade/hot” sono basate su `cooling_targets`, `regen_migration_bias` e `fade_threshold`.
- **Test/QA (`python_backend/tests/test_calibration_and_telemetry.py`)**
  - I test leggono i parametri per verificare che la telemetria runtime combaci con i profili calibrati.

## 5. Checklist aggiornata
- [ ] Verificare che ogni circuito 2025 abbia il JSON nella cartella `config/calibration/brakes/`.
- [ ] Annotare nel `notes` la telemetria usata (anno/sessione).
- [ ] Rigenerare `config/circuits/derived/<circuit_id>/brake_params.json` tramite `scripts/build_circuit_profiles.py <circuit>`.
- [ ] Lanciare `pytest python_backend/tests/test_calibration_and_telemetry.py -k brakes` per validare.
- [ ] Comunicare il change al team UI per aggiornare i pannelli Garage/PU.

## 6. Follow-up
Finché il gioco rimane ancorato alle telemetrie 2025, questo workflow è sufficiente. Quando servirà evolvere i dati su più stagioni sarà possibile convertire la guida in uno script automatico riutilizzando le stesse colonne/statistiche.
