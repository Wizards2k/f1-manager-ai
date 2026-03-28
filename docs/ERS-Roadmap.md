# ERS Setup & Telemetry Roadmap

_Last updated: 2026-03-24_

## 1. Scope
- Uniformare sorgenti dati ERS tra frontend, backend e configurazioni circuito.
- Rendere il motore ERS coerente con i requisiti descritti in:
  - `docs/ERS-Deployment-Strategy.md`
  - `docs/Ers-Deploy-Sim.md`
  - `docs/ERS-Bucket-Planner.md`
  - `docs/ers_bonus_testing_reference.md`
- Fornire strumenti UI per gestire e verificare le mappe ERS.

**Nota importante (2026-03-21)**: Il recupero MGU-K è ora controllato dal sistema ERS Bucket (`bucket_primary_pct`, `bucket_secondary_pct`, `bucket_exit_pct`) nei `pu_maps.json`. Il parametro `regen_migration_bias` nei `brake_params.json` non influisce materialmente su `lap_harvest_mj` perché il recupero è limitato dai bucket/SOC.

## 2. Current Gaps
1. **Preset UI vs backend**
   - L'editor in `player_garage_v3` mostra ancora preset locali (es. 3.41 MJ) invece dei valori runtime (`deploy_budget_total_mj`).
   - I bucket percentuali/riserva non vengono aggiornati dinamicamente dalle `pu_stats`.
2. **Dock e pannelli runtime**
   - Il dock motore usa `deploy_mj_per_lap`/`deploy_limit_mj` anziché i budget reali per lap.
   - Mancano indicatori coerenti con i bucket (Primary/Secondary/Exit) e la defense reserve riportata dal backend.
3. **Motore ERS**
   - Le formule di allocazione non riflettono ancora tutte le fasi del documento strategico (es. bonus situazionali, assist MGU-H, profilazione bucket).
   - Il simulatore usa fallback generici (global default) quando la configurazione circuito è incompleta.
4. **Coverage config**
   - Non tutti i circuiti hanno `pu_maps.json` derivati aggiornati; diversi file restano sui valori legacy.
   - Non esiste un workflow automatizzato per convalidare e rigenerare i profili.
5. **Interfaccia mappe ERS**
   - L’attuale pannello "Preset / Custom / Import" è statico e non permette editing/salvataggio reale.

## 3. Milestones

### M1 · UI ↔ Backend Alignment ✅
- [x] Aggiornare `player_garage_v3` per usare sempre `deploy_budget_total_mj`, `defense_reserve_available_mj` e bucket runtime.
- [x] Garantire che `SocketBridge` esegua un refresh completo delle `pu_stats` al primo `race_update` (non solo bootstrap `/api/cars`).
- [x] Introdurre un test smoke (es. Cypress/Playwright light) che verifica la corrispondenza tra log `pu_telemetry` e valori mostrati in UI.

### M2 · Dock Runtime Sync ✅
- [x] Rimuovere i fallback a `deploy_mj_per_lap` anche nel dock motore (`buildTabMotore`, `buildPUInlineBar`).
- [x] Esporre in dock i bucket runtime (Primary/Secondary/Exit + reserve) con gli stessi numeri del pannello.
- [x] Aggiornare `applyLocalCarState` così da mantenere solo `pu_stats` provenienti dal backend (no merge con preset).

### M3 · ERS Engine Realism ✅
- [x] Implementare tutte le sezioni operative definite in `docs/ERS-Deployment-Strategy.md` (cap per settore, SOC floor dinamici, bonus/penalty scenario-based).
- [x] Integrare la simulazione descritta in `docs/Ers-Deploy-Sim.md` per validare `bucket_section_cap`, `mguh_dir/es`, `defense reserve`.
- [x] Applicare il planner definito in `docs/ERS-Bucket-Planner.md` per la distribuzione delle mappe (inclusi preset Custom).
- [x] Validare contro i benchmark in `docs/ers_bonus_testing_reference.md` (test automatici).
- **Runtime alignment completed (2026-03-21)**: Tutti i circuiti riallineati con runtime reale e target doc.

### M4 · Circuit Config Sync ✅
- [x] Automatizzare `scripts/ers_budget_backfill.py` + pipeline di verifica (lint) per tutti i circuiti.
- [x] Confrontare i derived con i log reali (FastF1 / telemetrie interne) e aggiornare `config/calibration/pu/<cid>.json`.
- [x] Aggiungere un comando CI che rifiuti valori mancanti (assenza di `deploy_mj_per_lap`, `bucket_*_pct`).
- **Global sweep completed (2026-03-21)**: 22 circuiti riallineati con runtime e target doc; Suzuka/Monaco validati in-game.

### M5 · ERS Map Editor ✅
- [x] Progettare un pannello "ERS Map Manager" separato dal garage, con:
  - editor dei bucket (percentuali, reserve, target SOC) e salvataggio preset circuito.
  - import/export JSON compatibile con `config/circuits/derived/*/pu_maps.json`.
  - preview grafica (curva deploy vs sezione, timeline MGU-H).
- [x] Collegare il nuovo editor alla pipeline di generazione (possibilità di applicare preset + esportare su file).
- **Implementation completed (2026-03-24)**: Sistema completo di gestione mappe ERS con editor bucket, preview grafica, import/export e sincronizzazione backend.

## 4. Dependencies & Notes
- Richiede disponibilità dei log `pu_telemetry.log` e `session_bridge` per confronto.
- Necessaria sincronizzazione con il team UI/UX per il nuovo pannello.
- Eventuali modifiche al motore ERS devono mantenere compatibilità con `PracticeSessionOrchestrator` e i test in `tests/` (green validation, scenario harness).

## 5. Next Steps
1. **All Milestones Completed**: M1-M5 completate con successo (2026-03-24)
2. **Production Deployment**: Sistema ERS completo e operativo in produzione
3. **Maintenance**: Monitoraggio e ottimizzazione basata sui log `pu_telemetry` e `penalties.log`
4. **Future Enhancements**: Valutazione di nuove funzionalità basate sui requisiti utente
