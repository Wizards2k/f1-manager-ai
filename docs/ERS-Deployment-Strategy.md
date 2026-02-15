---
title: ERS Deployment Strategy
status: draft
last_updated: 2026-02-15
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

---
Questa bozza è un collage delle informazioni disseminate nei documenti esistenti, integrato con i gap osservati in runtime. Possiamo usarla come base per la discussione sulle idee che vuoi proporre (es. nuove mappe prioritarie, controlli giocatore, script di calibrazione aggiuntivi).
