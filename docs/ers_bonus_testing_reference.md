# ERS Bonus – Reference Test Playbook

Questa nota riassume come validare rapidamente l'ERS bonus e integrare i nuovi test nella suite.

**Nota di calibrazione (2026-03-21)**: I test di riferimento ora usano i target ufficiali di `docs/Ers-Deploy-Sim.md`. Tutti i circuiti sono stati riallineati con il runtime reale (`session_bridge`/`update_section`) mantenendo `mguh_direct_ratio = 0.45`. Usa `scripts/ers_budget_backfill.py` per ritestare dopo modifiche al motore ERS.

**Importante**: Il recupero MGU-K è ora controllato dal sistema ERS Bucket (`bucket_primary_pct`, `bucket_secondary_pct`, `bucket_exit_pct`) nei `pu_maps.json`. Il parametro `regen_migration_bias` non influisce materialmente su `lap_harvest_mj`.

## 1. Pytest di integrazione
- File: `python_backend/lap_simulator/tests/test_integration_lap.py`
- Copertura:
  - Lap singolo e multi-lap su Monza (pipeline completa).
  - Suite parametrica sui circuiti `it-1922_monza`, `az-2016_baku`, `jp-1962_suzuka`, `mc-1929_monaco`.
  - Assert principali: tempo plausibile, numero sezioni, `ers_bonus_s` solo sui rettilinei, clamp per sezione, somma section times == lap time.
- Esecuzione consigliata:
  ```bash
  PYTHONPATH=python_backend .venv/bin/python -m pytest \
      python_backend/lap_simulator/tests/test_integration_lap.py -k ers
  ```

## 2. CLI `validate_ers_bonus.py`
- Percorso: `python_backend/scripts/validate_ers_bonus.py`
- Uso: simula N giri su un circuito e opzionalmente confronta ERS ON vs OFF.
- Argomenti chiave:
  - `--circuit it-1922_monza`
  - `--map STANDARD`
  - `--push-level 1.0`
  - `--laps 1`
  - `--compare-off`
  - `--json-out reports/ers_monza.json`
  - `--fail-on-check`
- Output: report testuale (lap time, bonus totale, clamp ratio, deploy) + JSON opzionale.
- Comando esempio:
  ```bash
  PYTHONPATH=python_backend .venv/bin/python \
      python_backend/scripts/validate_ers_bonus.py \
      --circuit it-1922_monza --compare-off --json-out /tmp/monza.json
  ```

## 3. CLI `run_ers_sweep.py`
- Percorso: `python_backend/scripts/run_ers_sweep.py`
- Esegue lo stesso validatore su combinazioni circuito × mappa × push level.
- Argomenti principali:
  - `--circuits it-1922_monza,az-2016_baku,jp-1962_suzuka,mc-1929_monaco`
  - `--maps STANDARD`
  - `--push-levels 0.90,1.00,1.10`
  - `--compare-off`
  - `--laps 1`
  - `--csv-out reports/ers_sweep.csv`
  - `--json-out reports/ers_sweep.json`
  - `--fail-on-check`
- Ogni combinazione stampa il report e viene registrata in CSV/JSON con colonne: lap time, bonus totale, deploy, clamp ratio, delta ERS ON-OFF, numero di check falliti.
- Comando esempio:
  ```bash
  PYTHONPATH=python_backend .venv/bin/python \
      python_backend/scripts/run_ers_sweep.py \
      --circuits it-1922_monza,az-2016_baku,jp-1962_suzuka,mc-1929_monaco \
      --push-levels 0.90,1.00,1.10 --compare-off \
      --csv-out reports/ers_sweep.csv --json-out reports/ers_sweep.json
  ```

## 4. Come integrare futuri test
1. **Nuovi circuiti**: aggiungerli alla lista `--circuits` dello sweep e, se necessario, alle parametrizzazioni pytest.
2. **Metriche aggiuntive**: `run_validation()` (in `ers_validation_utils.py`) espone già `section_stats` e `lap_summary`; basta aggiungere nuovi check per altri penalty (es. fuel, setup) e salvarli in JSON/CSV.
3. **CI/Regression**: eseguire `run_ers_sweep.py --fail-on-check` per far fallire la pipeline in caso di regressione del bonus.
4. **Documentazione**: aggiornare questo file con ogni nuova variante per mantenere la traccia storica dei test disponibili.

Con questi strumenti, per ogni modifica al sistema penalty basta: (1) far girare i pytest, (2) lanciare lo sweep CLI sui circuiti target, e (3) allegare ai report i CSV/JSON generati.
