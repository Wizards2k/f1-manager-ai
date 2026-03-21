---
title: ERS Deployment Strategy
status: active
last_updated: 2026-03-21
authors: Gameplay/Physics
scope: Gestione energia MGU-K / MGU-H (deploy, harvest, telemetria)
references:
  - docs/EngineData2025.md
  - docs/PowerUnit.md
  - docs/Engine-MGU-H.md
  - docs/pu-energy-model.md
  - docs/lap-physics-spec-v0.5.md
---

## 1. Obiettivo
Definire una specifica unificata per la gestione dell'energia elettrica (ERS) nel LapSimulator, combinando i vincoli FIA 2025, i dati derivati per circuito e le esigenze di gameplay/UI. Il documento funge da base di discussione per l'iterazione **PU Hybrid V2.1** (consumo MGU-H direct + strategia deploy intelligente).

## 2. Vincoli regolamentari (recap)
- **MGU-K → Ruote (deploy)**: max **4 MJ/lap**.
- **MGU-K ← Frenata (harvest)**: max **2 MJ/lap**.
- **MGU-H → ES**: illimitato (limitato solo da efficienza e profilo circuito).
- **MGU-H → MGU-K (direct drive)**: illimitato, bypassa la batteria e non consuma il budget 4 MJ, ma è limitato dalla potenza disponibile `mguh_power_kw` e dai fattori sezione (derating termico / dirty air).

Questi limiti sono documentati in `docs/EngineData2025.md` e sono già presenti nei blocchi `ers_budget` generati da `scripts/powerunit_fit.py`.

## 3. Dati disponibili
### 3.1 Config globale (`config/pu/pu_maps_global_default.json`)
- `deploy_mj_per_lap`, `harvest_mj_per_lap`, `target_soc_end_lap`, `torque_ramp`, `mguh_direct_ratio` per ogni mappa.

### 3.2 Derived per circuito (`config/circuits/derived/<cid>/pu_maps.json`)
- `mguh_power_kw` (potenza media MGU-H), `_meta.mguh_profile` (high/balanced/low speed).
- `ers_budget`: limiti MJ e warning runtime (clipping, SOC target violati).
- `regen_profile`: look-up per brake migration (torque split previsto).

### 3.3 Runtime/Telemetria
- `power_unit.py` calcola `lap_mguh_direct_mj`, `lap_mguh_harvest_mj`, `lap_deploy_mj`, `lap_harvest_mj`.
- `SessionBridge` espone i campi e la trace sezione (`mguh_direct_mj`, `mguh_es_mj`).
- `player_garage_v3.js` visualizza i dati ma non influenza la logica.

### 3.4 Driver Intent (`docs/lap-physics-spec-v0.5.md`)
- `driver_intent.ers_mode` (deploy / hold / recover) e "ERS management style" (aggressive/balanced/conservative). Attualmente mappa i rettilinei senza pesi.

## 4. Stato attuale
1. **MGU-H direct**: calcoliamo la potenza disponibile per sezione (`_estimate_mguh_power_kw`) ma **non** sottraiamo l'energia usata; manca un budget per evitare overflow e per trasferire l'energia residua al giro successivo.
2. **Deploy batteria**: il DriverModel applica `ers_mode == deploy` su tutti i rettilinei, ignorando la priorità delle sezioni e il target SOC → la batteria si svuota prima della fine del giro anche in mappe neutrali.
3. **Brake migration**: profili presenti ma torque split non ancora applicato.
4. **Overtake/defense**: i pulsanti (K1/K2) forzano 120 kW ma non verificano la disponibilità MGU-H direct.
5. **Runtime alignment (2026-03-21)**: Tutti i circuiti sono stati riallineati con il runtime reale (`session_bridge`/`update_section`) e i target di `docs/Ers-Deploy-Sim.md`. Il tuning globale ha mantenuto `mguh_direct_ratio = 0.45` e ha converto per tutti i circuiti. Suzuka e Monaco sono stati validati in-game.
6. **Nota importante**: Il recupero MGU-K è ora controllato dal sistema ERS Bucket (`bucket_primary_pct`, `bucket_secondary_pct`, `bucket_exit_pct`) nei `pu_maps.json`. Il parametro `regen_migration_bias` nei `brake_params.json` non influisce materialmente su `lap_harvest_mj` perché il recupero è limitato dai bucket/SOC.

## 5. Architettura proposta (PU Hybrid V2.1)
### 5.1 Energy Budget Manager (per entry)
- **State per lap**:
  - `battery_available_mj` (≤ 4 MJ, inizializzato a `deploy_mj_per_lap` map-specific).
  - `mguh_direct_available_mj` (da profilo circuito × bias mappa, limitato per sezione da `mguh_power_kw` e `SECTION_MGUH_FACTORS`).
  - `mguh_to_es_buffer_mj` (harvest destinato alla batteria quando SOC < target).
- **Aggiornamento per sezione**:
  - Calcola richiesta driver (`ers_request_kw`).
  - Consuma prima MGU-H direct (fino al massimo disponibile nel dt sezione), il residuo scala alla batteria.
  - Se la batteria non può soddisfare la richiesta → derating + warning (`deploy_clip`).

### 5.2 Section Priority Map
- Input: `section.kind`, `length_m`, `drs_available`, `power_bias`, `overtake_windows`, `traffic_state`.
- Output: `priority_score ∈ [0,1]` usato per pesare quanto deploy destinare alla sezione.
- Derived idea: normalizzare `power_bias` per circuito e creare 3 bucket (Primary straight, Secondary straight, Micro straight/corner exit).

### 5.3 Strategy Profiles
- **Balanced (default)**: ripartisce `battery_available_mj` in base al priority score + conserva 0.5 MJ per gli ultimi 2 settori del giro.
- **Aggressive (push/overtake)**: moltiplica i pesi per un fattore >1 e consente SOC < target, ma segnala `runtime_warning` se la batteria scende sotto 20% prima dell'ultimo settore.
- **Recharge**: blocca deploy (solo MGU-H direct) e forza `harvest_preference = high`.

### 5.4 Event Hooks
- **Overtake button**: richiede `priority_score = 1` per la sezione corrente, consuma in ordine: MGU-H direct (max), batteria (fino a 120 kW). Se l'energia residua < soglia, l'evento si interrompe automaticamente.
- **Defensive deploy**: simile a overtake ma applicato quando `battle_resolver` segnala attacco.
- **Yellow/VSC**: forza modalità Recharge.

## 6. Telemetria & UI
- Nuovi campi suggeriti:
  - `mguh_direct_available_mj` (per lap e per sezione → debug pane QA).
  - `deploy_budget_remaining_pct`, `priority_score_current`.
  - `deploy_strategy_state` (balanced/aggressive/recharge).
- Garage v3: aggiungere badge "Budget restante" + warning se la batteria scende prima del previsto.

## 7. QA & Test
- Estendere `test_power_unit.py` con casi: (1) direct drive saturato, (2) deploy prioritizzato (batteria non si svuota a metà giro), (3) transizione push → recharge.
- Integrare nei report derived un riepilogo `mguh_profile` + energy split previsto e verificare nel runtime (tolleranza ±5%).

## 8. Open Questions (per discussione)
1. **Budget spillover**: l'energia MGU-H non usata in un settore deve essere trasferita al successivo o considerata persa? (Proposta: trasferire entro lo stesso giro, limitata da `mguh_power_kw`).
2. **SOC target dinamico**: vogliamo adattare `target_soc_end_lap` in base alla durata dello stint o ai comandi del giocatore?
3. **Priority tuning**: usare un file JSON per circuito (`ers_priority.json`) o derivare tutto dai parametri esistenti (section length + drs ratio)?
4. **Brake migration UI**: come surfaciamo la quota regen/idraulico e gli eventuali warning quando il deploy viene bloccato dalla batteria piena?
5. **AI Driver Engine**: i programmi practice (push, quali sim) devono poter richiedere una strategia ERS specifica.

## 9. Catalogo mappe default (baseline gioco)
All'avvio vogliamo fornire un set di mappature curate, già tarate per tipologia di circuito. L'idea è mantenere 5 preset base (override dal giocatore facoltativo):

| Nome | Use case | Parametri chiave |
| --- | --- | --- |
| **Standard** | Giro gara neutro | `deploy_budget_pct=60`, `mguh_direct_pct=55`, priority: Primary 50% / Secondary 35% / Corner exit 15%, `target_soc_end_lap=55%` |
| **Push** | Attacco / uscita Safety Car | `deploy_budget_pct=95`, `mguh_direct_pct=70`, priority: Primary 65% / Secondary 25% / Corner exit 10%, `defense_reserve_pct=0` |
| **Overtake** | Bottone K1 | come Push ma con `overtake_boost_window=12s`, `defense_reserve_pct=10` |
| **Recharge** | In/out lap, VSC | `deploy_budget_pct=10`, `mguh_direct_pct=30`, priority: Corner exit 60%, `harvest_bias_pct=90`, `target_soc_end_lap=95%` |
| **Wet/Cool** | Condizioni grip basso | `deploy_budget_pct=45`, `mguh_direct_pct=40`, priority bilanciata (Primary 35% / Secondary 30% / Corner exit 35%), `harvest_bias_pct=60` |

Per ogni circuito il fitting script sceglie il profilo (high/balanced/low) e applica offset a questi preset (es. Monza aumenta `deploy_budget_pct` del Push, Monaco riduce `mguh_direct_pct`). Dedicheremo un capitolo ad hoc nel documento (appendice futura) con la tabella iniziale completa.

## 10. Editor mappature custom (proposta UX)
1. **Input utente**: slider 0–100% per i parametri descritti in §5 (budget, split MGU-H, bucket priority, trigger speciali). Valori suggeriti e tooltip con limiti regolamentari.
2. **Validazione live**: se la somma dei bucket supera 100% o il budget supera 4 MJ, mostriamo un warning e correggiamo automaticamente; clampiamo `mguh_direct_pct` 0–100.
3. **Anteprima**: grafico a barre per settore che mostra quanta energia verrà allocata, + gauge SOC target. Possiamo simulare un giro usando il profilo circuito per dare feedback "Batteria ok / clipping".
4. **Persistenza**: salviamo il preset in `profiles/ers_maps/<player>.json` e lo agganciamo alle mappe standard (ECONOMY, STANDARD, ecc.) quando il giocatore seleziona il preset dal garage o dal volante.
5. **Edge cases**: se il preset richiede più energia di quella fisica disponibile (MGU-H + batteria), il runtime scala i valori e invia un warning nella PU modal.

## 11. Gestione mappe per AI
- **Seed default**: ogni team AI parte dai preset standard (Standard, Push, Recharge). Il profilo circuito definisce quale mappa usare in quali run (es. Monza FP1 → Standard, Push per run 3).
- **Driver persona**: l'AI Driver Engine (vedi `docs/ai-driver-engine-spec.md`) sceglie `deploy_budget_pct` dinamicamente in base a aggressività e obiettivi run: un pilota aggressivo alza `deploy_budget_pct` e anticipa l'uso del bottone overtake.
- **Strategy planner**: durante la gara, il Race Engineer AI può switchare mappa se il SOC scende sotto il target o se serve difendere/attaccare. La logica usa gli stessi parametri (priority score, defense reserve).
- **Calibrazione**: i report derivati includeranno anche i preset AI per circuito (`ai_ers_map_plan`) così da garantire comportamento coerente nelle simulazioni QA.

---
Questa bozza è un collage delle informazioni disseminate nei documenti esistenti, integrato con i gap osservati in runtime. Possiamo usarla come base per la discussione sulle idee che vuoi proporre (es. nuove mappe prioritarie, controlli giocatore, script di calibrazione aggiuntivi).
