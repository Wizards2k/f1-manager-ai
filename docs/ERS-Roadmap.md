# ERS Setup & Telemetry Roadmap

_Last updated: 2026-03-21_

## 1. Scope
- Uniformare sorgenti dati ERS tra frontend, backend e configurazioni circuito.
- Rendere il motore ERS coerente con i requisiti descritti in:
  - `docs/ERS-Deployment-Strategy.md`
  - `docs/Ers-Deploy-Sim.md`
  - `docs/ERS-Bucket-Planner.md`
  - `docs/ers_bonus_testing_reference.md`
- Fornire strumenti UI per gestire e verificare le mappe ERS.

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

### M5 · ERS Map Editor
- [ ] Progettare un pannello "ERS Map Manager" separato dal garage, con:
  - editor dei bucket (percentuali, reserve, target SOC) e salvataggio preset circuito.
  - import/export JSON compatibile con `config/circuits/derived/*/pu_maps.json`.
  - preview grafica (curva deploy vs sezione, timeline MGU-H).
- [ ] Collegare il nuovo editor alla pipeline di generazione (possibilità di applicare preset + esportare su file).

## 4. Dependencies & Notes
- Richiede disponibilità dei log `pu_telemetry.log` e `session_bridge` per confronto.
- Necessaria sincronizzazione con il team UI/UX per il nuovo pannello.
- Eventuali modifiche al motore ERS devono mantenere compatibilità con `PracticeSessionOrchestrator` e i test in `tests/` (green validation, scenario harness).

## 5. Next Steps
1. Completare M1 (UI/backend alignment) → blocco per ogni milestone successiva.
2. Preparare checklist circuiti e lanciare `ers_budget_backfill.py` su tutto l’elenco.
3. Pianificare design del nuovo ERS Map Manager con UX (wireframe + API contract).
