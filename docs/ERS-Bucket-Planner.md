---
title: ERS Bucket Planner Specification
status: in_progress
last_updated: 2026-03-21
authors: Gameplay/Physics
references:
  - docs/ERS-Deployment-Strategy.md
  - docs/Engine-MGU-H.md
  - docs/lap-physics-spec-v0.5.md
---

## 1. Obiettivo
Stabilire una strategia deterministica per distribuire l'energia ERS per giro seguendo i tre bucket (Primary/Secondary/Exit) configurati dall'utente. Il planner deve garantire che:
- la batteria venga scaricata finché esiste budget residuo sul bucket corrente;
- l'energia MGU-H direct rimanga separata dal budget batteria (4 MJ FIA);
- la UI/telemetria possano mostrare budget residui e warning coerenti.

## 2. Stato attuale (implementazione 2026-03-21)
- Il driver model usa `section_bucket_map` e i contatori per bucket per calcolare un cap dinamico per sezione basato sull'energia residua e sulle sezioni rimanenti (`dynamic_cap = bucket_remaining / sections_left`, con spread upper/lower configurabile).
- Ogni richiesta di deploy viene divisa tra quota batteria (`bucket_battery_request_mj`) e quota MGU-H direct. Solo la quota batteria riduce `bucket_remaining_mj`/`battery_budget_remaining_mj`, mentre l'energia MGU-H consuma gli specifici budget `mguh_*_remaining_mj`.
- `_ensure_bucket_budget()` inizializza per giro sia i bucket batteria sia gli equivalenti MGU-H rispettando `deploy_mj_per_lap`, `defense_reserve_mj` e le percentuali mappa (`bucket_primary_pct`, ecc.).
- `pu_telemetry.log`, `SessionBridge` e la UI mostrano i nuovi campi (`bucket_section_cap`, `bucket_sections_left`, `bucket_remaining`, `mguh_direct_remaining`).
- **Sweep globale ERS completato (2026-03-21)**: Tutti i circuiti sono stati riallineati con il runtime reale (`session_bridge`/`update_section`) e i target di `docs/Ers-Deploy-Sim.md` mantenendo `mguh_direct_ratio = 0.45`. Suzuka e Monaco sono stati validati manualmente e confermati in-game.

## 3. Planner implementato
### 3.1 State per giro
All'inizio di ogni lap per ciascun `CarEntry` (`power_unit._ensure_bucket_budget`):
- `battery_budget_total_mj` = `deploy_mj_per_lap` (clampato ≤ 4 MJ) e `battery_budget_remaining_mj` azzerato.
- Per ogni bucket `b ∈ {primary, secondary, exit}`:
  - `bucket_*_total_mj[b] = (deploy_mj_per_lap - defense_reserve_mj) * bucket_pct[b] / Σpct`.
  - `bucket_*_remaining_mj[b]` e `bucket_*_used_mj[b]` resettati.
- Quota MGU-H direct:
  - `mguh_*_total_mj[b]` derivata da `mguh_direct_ratio` × profilo circuito, ripartita con le stesse percentuali dei bucket batteria.
  - `mguh_*_remaining_mj[b]` usata per validare la disponibilità di energia direct drive.

### 3.2 Mappatura sezione → bucket
`SessionBridge._compute_section_buckets()` costruisce `section_bucket_map` applicando il mix di hint circuito (`bucket_hint`, `corner_exit`) e regole di fallback:
1. Flag `corner_exit` o sezione marcata `EXIT` → bucket `exit`.
2. Sezioni `STRAIGHT` / `MEDIUM_STRAIGHT` / DRS → bucket `primary`.
3. Altre curve veloci/medie → bucket `secondary`.
4. Se non esiste mappa, `_resolve_section_bucket` usa `SectionContext.bucket_hint` oppure `secondary` come default.
Durante `SessionBridge` vengono anche calcolati i conteggi `bucket_section_counts` necessari per il cap dinamico.

### 3.3 Flusso runtime
1. **DriverModel.compute_inputs()** (`lap_simulator/driver_model.py`)
   - Risolve `bucket_key` e recupera `bucket_remaining`, `bucket_sections_left` e `bucket_counts` dalla configurazione.
   - Calcola `section_cap` iniziale (rapporto percentuale della sezione) e applica il cap dinamico:
     
     `dynamic_cap = bucket_remaining_total / bucket_sections_left`
     
     `section_cap = clamp(dynamic_cap × spread_lower, dynamic_cap × spread_upper)`
     
     con `bucket_section_spread_lower/upper` definiti nella mappa ERS.
   - `bucket_battery_cap = min(bucket_remaining, section_cap)` e `battery_window = min(battery_headroom, battery_budget_remaining, bucket_battery_cap)`, dove `battery_headroom` ora usa il **floor dinamico SOC**.
   - `mguh_window = mguh_direct_remaining` (per il bucket) ⇒ `bucket_target_mj = battery_window + mguh_window`.
   - Il DriverIntent trasporta due valori: `bucket_deploy_target_mj` (totale richiesto) e `bucket_battery_request_mj` (solo quota batteria).

2. **power_unit.generate_output()** (`lap_simulator/power_unit.py`)
   - Usa `bucket_battery_request_mj` per `_apply_bucket_allocation`: solo la quota batteria riduce `bucket_remaining_mj`/`battery_budget_remaining_mj`.
   - `mguh_energy_target_mj = bucket_deploy_target_mj - bucket_battery_request_mj` alimenta `_allocate_mguh_direct`, che scala i budget `mguh_*_remaining_mj` per bucket.
   - Warning dedicati: `bucket_exhausted:<bucket>`, `mguh_bucket_exhausted:<bucket>`, `battery_budget_exhausted`, `deploy_limit_hit`.

3. **Fine sezione**
   - `PUState.energy_trace` registra separatamente `deploy_mj` (batteria) e `mguh_direct_mj`.
   - `log_pu_snapshot` esporta `bucket_remaining`, `bucket_sections_left`, `bucket_dynamic_cap`, `bucket_section_cap` per debug/UI.

4. **Fine lap**
   - `SessionBridge` resetta i contatori e pubblica i totali usati per bucket e MGU-H per la UI garage.

### 3.4 Telemetria & UI
`pu_stats`/`pu_telemetry.log` espongono ora:
- `bucket_*_remaining_mj`, `bucket_sections_left`, `bucket_section_cap`, `bucket_dynamic_cap`.
- `battery_budget_remaining_mj`, `defense_reserve_available_mj`, `mguh_direct_remaining_mj`.
- Per-sezione: `section_deploy` (solo batteria), `section_harvest`, `mguh_direct_mj`.
- Warning dedicati per bucket e MGU-H.

## 4. Impatti implementativi
1. **SessionBridge** – `_compute_section_buckets`, `_build_pu_stats` ora serializzano bucket map, conteggi e residui per lap.
2. **lap_simulator.data_types.PUState / DriverIntent** – aggiunti campi `bucket_*_remaining`, `bucket_battery_request_mj`, metriche per telemetria (cap dinamico, sezioni rimanenti).
3. **driver_model.py** – calcolo cap dinamico, split batteria/MGU-H, headroom basato su SOC floor, spread configurabili.
4. **power_unit.py** – `_ensure_bucket_budget`, `_apply_bucket_allocation`, `_allocate_mguh_direct` garantiscono che solo la quota batteria consumi il budget; logging dei warning aggiornati.
5. **UI/Logs** – `player_garage_v3.js`, `log_pu_snapshot` e `pu_telemetry.log` mostrano i nuovi campi, permettendo di diagnosticare bucket esauriti per tempo.

## 5. Test
- Replay run standard con `DEBUG_PU_TELEMETRY=1` verificando che i bucket calino secondo le percentuali impostate.
- Caso limite: mappa Recharge → bucket planner non richiede deploy (solo MGU-H direct).
- Caso Overtake: bucket Primary deve arrivare a zero entro metà giro se il budget lo prevede.

## 6. Outstanding questions
- Parametro `section_cap`: fisso (target/n) o proporzionale alla lunghezza? Da calibrare in follow-up.
- Differenziare curve molto lente/uscite lunghe: possiamo aggiungere un flag extra nei dati circuito.
