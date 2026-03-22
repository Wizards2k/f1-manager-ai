---
title: ERS Map Manager & Engine Hub Technical Reference
status: draft
last_updated: 2026-03-22
authors: Gameplay/UI, Physics
scope: Navigazione Motore, gestione mappe ERS, modello dati, runtime alignment, persistenza circuiti
references:
  - docs/ERS-Roadmap.md
  - docs/ERS-Deployment-Strategy.md
  - docs/ERS-Bucket-Planner.md
  - docs/Ers-Deploy-Sim.md
  - docs/PU-Engine-MGU-H.md
  - docs/pu-energy-model.md
  - docs/PowerUnit.md
  - docs/ers_bonus_testing_reference.md
  - python_backend/static/js/modules/player_garage_v3.js
  - python_backend/utils/session_bridge.py
  - python_backend/lap_simulator/update_section.py
  - python_backend/lap_simulator/power_unit.py
  - python_backend/lap_simulator/config_loader.py
  - config/circuits/derived/jp-1962_suzuka/pu_maps.json
---

# 1. Obiettivo

Questo documento definisce il riferimento tecnico per la nuova catena:

- **Main Menu** → tile **Engine**
- **Engine Hub** intermedio con 4 tile
  - **Engine Development**
  - **ICE Maps**
  - **ERS Maps**
  - **Engine Technicians**
- **ERS Map Manager** dedicato alla creazione, modifica, salvataggio e cancellazione delle mappe ERS

Il punto chiave è mantenere la nuova UI **separata** dal componente esistente `player_garage_v3.js`, che resta una base di ispirazione per layout, interazioni e filosofia di aggiornamento, ma **non** deve essere modificato in-place per questa milestone.

> Nota UI: tutte le etichette in-game devono restare in **English**. Questo documento può restare in italiano, ma i nomi dei pulsanti, tile e campi UI devono essere coerenti con il gioco.

---

# 2. Principi architetturali

## 2.1 Separazione dei livelli

Il sistema ERS va tenuto diviso in tre livelli concettuali:

1. **Map definition**
   - configurazione persistita nel bundle circuito
   - definisce budget, split e target energetici

2. **Runtime state**
   - stato vivo dell’auto nel giro corrente
   - SOC, budget residui, warning, trace per sezione

3. **UI / Editor**
   - mostra e modifica i dati
   - non deve diventare fonte di verità della fisica

## 2.2 Source of truth

Nel gioco, la source of truth live resta:

- `python_backend/utils/session_bridge.py`
- `python_backend/lap_simulator/update_section.py`
- `python_backend/lap_simulator/power_unit.py`

`player_garage_v3.js` visualizza i dati ma non li determina.

## 2.3 Reuse strategy

Dal garage v3 conviene riusare solo la filosofia di UI:

- cards
- meter / bar
- bucket cards
- chip state
- auto-balance unlocked buckets
- render fingerprint per evitare rebuild inutili

Il nuovo editor deve essere un **componente nuovo**, con stato e lifecycle propri.

---

# 3. Flusso di navigazione

## 3.1 Flow proposto

```text
Main Menu
└── Engine
    └── Engine Hub
        ├── Engine Development
        ├── ICE Maps
        ├── ERS Maps
        └── Engine Technicians

ERS Maps
└── ERS Map Manager
```

## 3.2 Route proposal

Le route esatte possono essere finalizzate in implementazione, ma il flow tecnico di riferimento è questo:

- `/engine` → Engine Hub
- `/engine/development` → Engine Development
- `/engine/ice` → ICE Maps
- `/engine/ers` → ERS Map Manager
- `/engine/technicians` → Engine Technicians

La tile **Engine Technicians** è parte dell’hub intermedio e non deve bloccare il rilascio del manager ERS: può restare una schermata indipendente o un placeholder funzionale.

---

# 4. Stato attuale del backend

## 4.1 Caricamento configurazione circuito

`python_backend/lap_simulator/config_loader.py` carica la configurazione circuito seguendo questa precedence:

1. `config/circuits/derived/<circuit_id>/...`
2. fallback globale in `config/*_global_default.json`

Per il PU / ERS, il loader fa in pratica:

- prova `config/circuits/derived/<cid>/pu_maps.json`
- se non esiste, fallback a `config/pu/pu_maps_global_default.json`
- legge anche `regen_profile` e `soc_warnings` dal bundle circuito

## 4.2 Struttura runtime

I tipi dati rilevanti sono:

- `EngineMapParams`
- `PUState`
- `DriverIntent`
- `CircuitConfig`

Questi oggetti sono il ponte tra JSON, fisica e UI.

## 4.3 Runtime live

Il path live è:

1. `SessionBridge` prepara il contesto e costruisce `pu_stats`
2. `update_section()` orchestra il passaggio di sezione
3. `power_unit.generate_output()` consuma budget, calcola SOC e genera trace
4. `SessionBridge` serializza tutto nel payload `race_update`

Il simulatore standalone è utile per test e calibrazione, ma **non** è la source of truth del gameplay live.

---

# 5. Modello dati ERS

## 5.1 Bundle circuito `pu_maps.json`

Il file derivato circuito deve essere trattato come bundle di riferimento per le mappe ERS/PU.

### Struttura logica

```json
{
  "_meta": {
    "circuit_id": "jp-1962_suzuka",
    "circuit_name": "Japanese Grand Prix",
    "mguh_profile": {
      "name": "balanced_spec",
      "total_mj": 2.2,
      "direct_mj": 0.99,
      "es_mj": 1.21
    }
  },
  "maps": {
    "RACE": { "...": "..." },
    "QUALIFY": { "...": "..." },
    "PRACTICE": { "...": "..." },
    "SAFETY_CAR": { "...": "..." }
  },
  "regen_profile": {
    "base_factor": 0.828,
    "potential_mj_per_lap": 1.3,
    "regen_limit_per_section": 2.0
  },
  "ers_budget": {
    "battery_capacity_mj": 5.5,
    "deploy_limit_mj": 4.0,
    "harvest_limit_mj": 2.0,
    "maps": {
      "RACE": { "...": "..." },
      "QUALIFY": { "...": "..." }
    },
    "warnings": []
  },
  "soc_warnings": []
}
```

## 5.2 Due livelli di configurazione

Il file attuale usa due livelli distinti:

### A. `maps`
Contiene i parametri della mappa in senso lato:

- `heat_load_kw`
- `torque_ramp`
- `deployment_style`
- `cooling_share`
- `ers_output_kw`
- `deploy_mj_per_lap`
- `harvest_mj_per_lap`
- `target_soc_end_lap`
- `torque_bias`
- `mguh_power_kw`
- `mguh_direct_ratio`
- bucket percentages, quando presenti o quando ricostruite dai default

### B. `ers_budget.maps`
Contiene l’overlay budget/strategy per mappa:

- `deploy_mj_per_lap`
- `harvest_mj_per_lap`
- `target_soc_end_lap`
- `mguh_direct_ratio`
- `deploy_ratio`
- `harvest_ratio`
- bucket/defense metadata dove necessario

## 5.3 Mapping runtime

`config_loader._parse_pu_maps()` costruisce `EngineMapParams` a partire da `maps` e usa `ers_budget.maps` come sorgente preferenziale per `mguh_direct_ratio`.

### Runtime fields principali

`EngineMapParams` include:

- `power_pct_min`
- `power_pct_max`
- `power_pct_base`
- `heat_load_kw`
- `torque_ramp`
- `deployment_style`
- `cooling_share`
- `ers_output_kw`
- `mguh_direct_ratio`
- `mguh_power_kw`
- `bucket_primary_pct`
- `bucket_secondary_pct`
- `bucket_exit_pct`
- `defense_reserve_mj`

`PUState` mantiene invece lo stato vivo:

- SOC
- energy trace
- warnings
- bucket totals / used
- section counters
- last bucket allocation
- SOC floor / target runtime

---

# 6. Runtime flow ERS

## 6.1 Sequenza per sezione

```text
load_circuit_config()
  → SessionBridge prepara pu_stats
  → update_section()
      → compute_inputs()
      → generate_output()
      → _initialize_bucket_budget()
      → _apply_bucket_allocation()
      → _consume_bucket()
      → _decrement_section_count()
  → SessionBridge serializza race_update
```

## 6.2 Significato dei flussi energia

Il runtime distingue chiaramente:

- **Battery deploy**
  - energia usata dal deploy MGU-K
  - `lap_deploy_mj`

- **Brake harvest**
  - recupero frenata MGU-K → ES
  - `lap_harvest_mj`

- **MGU-H direct**
  - energia MGU-H diretta alle ruote
  - `lap_mguh_direct_mj`

- **MGU-H to ES**
  - energia MGU-H indirizzata alla batteria
  - `lap_mguh_harvest_mj`

### Regola importante

`lap_harvest_mj` **non** è il totale ERS del giro.
È solo il recupero frenata.

`mguh_total` nelle telemetrie deriva da:

- `lap_mguh_direct_mj`
- `lap_mguh_harvest_mj`

e **non** include il brake harvest.

## 6.3 Bucket planner

Il planner usa tre bucket:

- `primary`
- `secondary`
- `exit`

La logica attuale:

- `power_unit._initialize_bucket_budget()` ripartisce il budget totale per lap
- `power_unit._apply_bucket_allocation()` consuma la quota del bucket corrente
- `power_unit._consume_bucket()` applica il consumo effettivo
- `power_unit._decrement_section_count()` aggiorna il numero di sezioni rimaste

La riserva difensiva è una quota separata e non deve essere confusa con il deploy normale.

### Note operative

- Il bucket budget è un **cap**, non un target da spendere completamente.
- `Bucket_Section_CAP` è un limite per sezione.
- `Bucket_budget_remaining` è un valore post-allocation.
- `Bucket_Section_DIR` viene loggato separatamente e non consuma bucket battery budget.

---

# 7. Telemetria esposta alla UI

`SessionBridge._build_pu_stats()` costruisce il payload che la UI vede.

## 7.1 Campi fondamentali

- `map`
- `soc_mj`
- `soc_pct`
- `capacity_mj`
- `deploy_limit_mj`
- `harvest_limit_mj`
- `deploy_mj_per_lap`
- `harvest_mj_per_lap`
- `target_soc_end_lap`
- `mguh_direct_ratio`
- `mguh_es_ratio`
- `bucket_primary_pct`
- `bucket_secondary_pct`
- `bucket_exit_pct`
- `bucket_primary_total_mj`
- `bucket_secondary_total_mj`
- `bucket_exit_total_mj`
- `bucket_primary_used_mj`
- `bucket_secondary_used_mj`
- `bucket_exit_used_mj`
- `defense_reserve_available_mj`
- `soc_floor_dynamic_pct`
- `soc_target_pct`
- `primary_sections_count`
- `secondary_sections_count`
- `exit_sections_count`
- `primary_sections_remaining`
- `secondary_sections_remaining`
- `exit_sections_remaining`
- `last_priority_score`
- `last_bucket_key`
- `last_bucket_allocated_mj`
- `last_defense_used_mj`
- `last_push_mode`
- `last_defense_mode`
- `last_recharge_mode`
- `energy_trace`
- `warnings`
- `warnings_runtime`

## 7.2 Warning types rilevanti

Tra i warning runtime più utili per il manager:

- `bucket_cap_hit:<bucket>`
- `bucket_exhausted:<bucket>`
- `battery_budget_exhausted`
- `deploy_limit_hit`
- `harvest_limit_hit`
- `brake_migration_disabled_soc`
- `mguh_bucket_exhausted:<bucket>`

La UI dovrebbe trasformare questi segnali in badge leggibili e non in puro debug text.

---

# 8. ERS Map Manager – funzionalità

## 8.1 Schermata principale

L’editor deve offrire:

- selezione mappa esistente
- creazione nuova mappa da zero
- modifica mappa esistente
- salvataggio
- cancellazione
- import/export JSON

## 8.2 Campi da esporre

### A. Energia totale della mappa

- campo UI: **Total Energy**
- persistenza: `deploy_mj_per_lap`
- rappresentazione utile: % sul totale batteria

### B. Direct / ES split

- campo UI: **Direct / ES Split**
- persistenza: `mguh_direct_ratio`
- valore complementare: `mguh_es_ratio = 1 - mguh_direct_ratio`

### C. Floor / SOC target

- campo UI: **SOC Floor** o **Target SOC End Lap**
- persistenza: `target_soc_end_lap`
- runtime live correlato: `soc_floor_dynamic_pct`, `soc_target_pct`

### D. Defense Energy

- campo UI: **Defense Reserve**
- persistenza: `defense_reserve_mj`

### E. Bucket split

- **Primary Bucket**
- **Secondary Bucket**
- **Exit Bucket**

La somma deve essere 100%.

## 8.3 Azioni UI

L’editor deve permettere:

- **Save**
- **Delete**
- **Duplicate**
- **Reset to preset**
- **Create new map**
- **Import JSON**
- **Export JSON**

## 8.4 Preview grafica

Il pannello preview dovrebbe mostrare:

- curva deploy vs sezione
- split Direct / ES
- SOC target e floor
- bar del bucket planner
- warning per clipping / budget insufficiente

## 8.5 Pattern da riusare dal garage v3

Da `player_garage_v3.js` conviene riprendere solo il pattern, non il file:

- bucket cards
- chips colorate
- auto-balance delle percentuali libere
- aggiornamento in-place dei badge
- fingerprint di rendering per evitare rebuild completi

---

# 9. Regole di validazione

Il manager non deve salvare una mappa se non rispetta almeno queste regole:

1. **Bucket sum = 100%**
   - tolleranza consigliata: `±0.05`
   - i bucket non bloccati possono essere auto-bilanciati

2. **Deploy budget**
   - `deploy_mj_per_lap <= 4.0`

3. **Harvest budget**
   - `harvest_mj_per_lap <= 2.0`

4. **Direct ratio**
   - `0.0 <= mguh_direct_ratio <= 1.0`

5. **Defense reserve**
   - non deve superare il deploy disponibile
   - il runtime può azzerarla automaticamente in QUALIFY

6. **SOC target / floor**
   - deve restare in un range realistico `0.0 – 1.0`

7. **Unique map IDs**
   - ogni mappa deve avere un identificatore stabile e unico

8. **Canonical names**
   - i nomi in UI devono restare in inglese
   - esempi: `Engine Development`, `ERS Maps`, `Primary Bucket`

---

# 10. Persistenza e salvataggio

## 10.1 File canonicale

Per la modifica circuito-specifica, il punto di salvataggio deve essere:

- `config/circuits/derived/<circuit_id>/pu_maps.json`

## 10.2 Cosa va aggiornato

Quando si salva una mappa, il writer deve mantenere allineati almeno:

- `maps[<map_id>]`
- `ers_budget.maps[<map_id>]`
- `_meta` se necessario per versioning
- `soc_warnings` se cambiano i warning di calibrazione

## 10.3 Flusso di salvataggio consigliato

```text
User edit
  → validation
  → normalize values
  → write derived pu_maps.json
  → reload circuit / refresh session
  → UI updates runtime chips and preview
```

## 10.4 Nuova mappa da zero

Per supportare la creazione di una nuova mappa, il sistema deve avere un identificatore stabile.

### Strategia consigliata

- mappe built-in: `PRACTICE`, `RACE`, `QUALIFY`, `SAFETY_CAR`
- mappe custom: registry separato con `map_id` stringa stabile

> Decisione aperta: se la runtime enum verrà estesa oppure se le custom map verranno risolte tramite registry/alias.

---

# 11. Integrazione file e moduli

## 11.1 Frontend proposto

- `python_backend/templates/engine-hub.html`
- `python_backend/static/js/modules/engine_hub_v1.js`
- `python_backend/static/js/modules/ers_map_manager_v1.js`
- `python_backend/static/js/modules/ice_map_manager_v1.js`
- `python_backend/static/js/modules/engine_technicians_v1.js`
- `python_backend/static/css/engine-hub-v1.css`
- `python_backend/static/css/ers-map-manager-v1.css`

## 11.2 Backend proposto

- route per `Engine Hub`
- route per `ERS Map Manager`
- endpoint import/export/validate per le mappe
- eventuale endpoint reload dopo save

## 11.3 File da non toccare in-place

- `python_backend/static/js/modules/player_garage_v3.js`

Questo file può essere consultato e riusato come riferimento, ma non va usato come base di patch diretta per l’editor nuovo.

---

# 12. Esempio tecnico: Suzuka

Il bundle derivato di Suzuka è un buon riferimento perché mostra il flusso reale tra mappa, budget e runtime.

Valori attualmente rilevanti nel derived:

- `RACE`
  - `deploy_mj_per_lap`: `3.631`
  - `harvest_mj_per_lap`: `1.029`
  - `target_soc_end_lap`: `0.05`
  - `mguh_direct_ratio`: `0.45`

- `QUALIFY`
  - `deploy_mj_per_lap`: `4.0`
  - `harvest_mj_per_lap`: `0.475`
  - `target_soc_end_lap`: `0.05`
  - `mguh_direct_ratio`: `0.45`

Questo è utile per verificare che il manager non presenti una mappa “bella” solo in UI ma incoerente con il runtime.

---

# 13. Checklist operativa per la milestone

Prima del rilascio dell’Engine Hub + ERS Map Manager, il sistema dovrebbe garantire che:

- la tile **Engine** apra una schermata intermedia dedicata
- la schermata intermedia mostri 4 tile, inclusa **Engine Technicians**
- la tile **ERS Maps** apra il nuovo editor
- l’editor legga e scriva i dati del bundle circuito
- i bucket restino sincronizzati con il runtime
- la UI mostri warning chiari per budget, SOC e split incoerenti
- `player_garage_v3.js` resti invariato
- i nomi UI restino in inglese

---

# 14. Conclusione

L’ERS Map Manager deve essere pensato come un editor di **configurazione circuito + strategia ERS**, non come una semplice maschera grafica.

La catena corretta è:

- **Engine Hub** per la navigazione
- **ERS Map Manager** per la modifica dei preset
- **SessionBridge / update_section / power_unit** per il runtime live
- **`pu_maps.json` derivato** come persistenza canonica

Questa struttura permette di:

- mantenere il runtime coerente
- separare UI e fisica
- abilitare il CRUD delle mappe
- preparare il terreno per l’implementazione senza toccare il garage v3 esistente
