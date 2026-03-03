# Specifica refactor: Team, Auto, PowerUnit, Pilota (e classi correlate)

## Obiettivo
Separare le responsabilità tra entità di dominio (Team, Auto, PowerUnit, Pilota, Pit Crew) eliminando campi ibridi e introducendo classi dedicate per motore e telaio. Il Team diventa un contenitore di risorse (piloti, auto, PU) senza parametri tecnici duplicati.

## Stato attuale (mar 2026)
- `Team` (@python_backend/models.py) è stato rifattorizzato: ora richiede `auto: Auto`, `power_unit: PowerUnit`, `pilota1/2` nominati e opzionalmente `pilota_riserva`; i campi legacy (`forza_auto`, `affidabilita`, `meccanica`, `pitstop_skill`) sono stati rimossi.
- Il dataset `TEAMS` (@python_backend/data/teams/__init__.py) usa i registri ufficiali `data.power_units` e `data.cars` per costruire ogni scuderia e continua ad assegnare `team_id` incrementale.
- Gli adapter verso LapSimulator (SessionBridge, AI driver, API) costruiscono ormai `CarEntry` direttamente da `team.auto`/`team.power_unit`: `_build_sim_state` crea `PUState` via `PowerUnit.create_state()` e mappa `ice_mode`/`ers_mode` sui nuovi EngineMap.
- Gli script di validazione (`scripts/run_sim_teams.py`, `scripts/physics_validator.py`, `scripts/congruence_check.py`) utilizzano le stesse istanze ufficiali per generare baseline e report, eliminando l’uso di `make_pu_state()` legacy.
- La logica motore di `lap_simulator/power_unit.py` e i runtime state (`PUState`, `EngineMapParams`) restano invariati in attesa del successivo step di calibrazione.

## Target modello dati

### Team (ridisegnato)
- Campi mantenuti: `nome_scuderia`, `sigla_scuderia`, `nazionalita`, `colore_team`, `sponsor_principale`, `simulator_quality`, `team_id` (assegnato dal loader).
- Campi rimossi: `forza_auto`, `affidabilita`, `meccanica`, `pitstop_skill`.
- Campi spostati: `aerodinamica` → sarà proprietà di `Auto`.
- Campi convertiti/nuovi:
  - `power_unit: PowerUnit` (istanza classe dedicata, non stringa).
  - `auto: Auto` (istanza chassis/aero/meccanica, escluso motore).
  - `pilota1: Pilota`
  - `pilota2: Pilota`
  - `pilota_riserva: Pilota | None` (aka simulatore/reserve).

### PowerUnit (nuova entità roster)
- Identità (obbligatorio ID in testa): `pu_id`, `nome`, `fornitore`, `anno`, `spec_version`.
- Componenti separati:
  - `ice`: include `ice_id`, `nome`, `potenza_pct` (0–120%), parametri termici/affidabilità (derivabili da `PUReliabilityParams`).
  - `mgu_k`: `mgu_k_id`, `nome`, `max_kw`, efficienza, termica.
  - `mgu_h`: `mgu_h_id`, `nome`, `base_kw`, `direct_ratio_default`, efficienza, termica.
  - `battery`: `battery_id`, `nome`, `capacity_mj`, `max_charge_kw`, `max_discharge_kw`, termica.
- Mappe separate ICE/ERS (nuove classi dati):
  - **Mappa ICE**: `ice_map_id`, `nome`, `power_pct` (0–120%).
  - **Mappa ERS** (interfaccia modale ERS): `ers_map_id`, `nome`, `deploy_budget_mj`, `bucket_primary_pct`, `bucket_secondary_pct`, `bucket_exit_pct` (range suggerito 1–120%).
- Dati statici comuni: budget ERS, affidabilità (`PUReliabilityParams`), fuel tank capacità, limiti recupero/consumo, `regen_profile`.
- Factory: metodo per creare `PUState` runtime (stato vettura) valorizzando mappa ICE/ERS di default.

### Auto (nuova entità roster)
- Dati statici: pacchetto aero (front/rear/beam wing, floor/diffuser, cooling area), componenti meccaniche (sospensioni, antiroll, ride height base), brake ducts, peso base, grip meccanico baseline.
- Output: factory per `AeroSetup`/`CarState` iniziale e profili di cooling/drag/downforce.
- Identità: `auto_id`, `nome`, `anno`, `team_ref` opzionale.

### Pilota (esistente, da referenziare)
- Nessun cambio nel modello; Team usa campi nominativi `pilota1/2/riserva` al posto della lista.

### Pit Crew / Operations (futuro)
- Nuova classe dedicata per skill pitstop, efficienza operativa e tempi box. Rimossa da `Team` per ora.

## Migrazioni dati
- Aggiornare `python_backend/data/teams/__init__.py`:
  - Usare `pilota1`, `pilota2`, `pilota_riserva` da `PILOTS`.
  - Passare `power_unit` come istanza dal registry `data/power_units.py`.
  - Passare `auto` come istanza dal registry `data/cars.py` (o sezione dedicata).
- Rimuovere l’uso di `forza_auto`, `affidabilita`, `meccanica`, `pitstop_skill` nei consumatori (UI/garage, builder roster, simulator adapters).

## Impatti attesi
- **Simulazione**: costruzione `RaceCar` richiederà composizione `Auto` + `PowerUnit` + Pilota → genera `CarState` e `PUState` coerenti con la fisica.
- **UI/garage**: indicatori di performance dovranno leggere attributi di `Auto` (DF/drag/cooling) e `PowerUnit` (mappe, reliability) invece dei campi legacy.
- **Script dataset**: generatori dovranno creare istanze `PowerUnit` e `Auto` per ogni team.

## Dataset sandbox (solo analisi)
- **Posizione**: `python_backend/tmp_data/` ospita i moduli `power_units_2025.py`, `cars_2025.py` e `teams_2025.py` che generano roster 2025 temporanei sfruttando le misure di gap estratte dai primi tre GP.
- **Origine dati**: i gap percentuali derivano da manifest/telemetria FastF1 (Bahrain, Jeddah, Australia) e sono stati convertiti in scaling factor separati per aero, grip e power unit per ogni team, mantenendo la baseline McLaren.
- **Skill piloti**: gli attributi sono stati assegnati secondo le fasce Top/Mid/Rookie (range 90–96, 75–85, 50–74) già validati nella pipeline Piloti, con associazione pilota/team coerente con il 2025.
- **Isolamento**: i file sandbox non sono importati da nessun modulo di gioco esistente; `data/teams/__init__.py` continua a usare i registri ufficiali e non fa riferimento a questa cartella. Lavorare in questa area permette iterazioni veloci senza influenzare la build principale.

### Classifica gap (primi 3 GP)
I gap riportati nella sandbox sono stati ordinati rispetto a McLaren (baseline 0%) e servono come riferimento per calibrare i parametri delle nuove istanze `Auto` e `PowerUnit`. La classifica è la seguente:

| Team | Gap medio vs McLaren |
| --- | --- |
| McLaren | +0.0% |
| Red Bull Racing | +0.8% |
| Ferrari | +1.2% |
| Mercedes | +1.8% |
| Aston Martin | +2.5% |
| Alpine | +3.2% |
| Haas | +4.1% |
| Williams | +4.8% |
| Sauber | +5.5% |
| RB | +6.8% |

Questi gap sono applicati a componenti aero/grip/PU (distribuiti rispettivamente 40/35/25%) per generare i valori delle 10 auto tecniche nel modulo `cars_2025.py` (tutte le configurazioni sono già definite ma rimangono scollegate dal gioco principale). In particolare la sandbox contiene un `AeroPackage`, sospensioni, ride height e valori di grip per ciascuna delle 10 squadre, che generano output coerenti con i gap sopra riportati.

## Stato lavori (2 mar 2026)

### Fatto
- **Dataset sandbox**: creati `python_backend/tmp_data/power_units_2025.py`, `cars_2025.py`, `teams_2025.py` con istanze `PowerUnit`, `Auto`, `Team` basate sui gap dei primi 3 GP 2025 (baseline McLaren). I moduli sono isolati e non importati dal gioco.
- **Classifica gap**: tabella con gap attesi per ogni squadra (MCL 0.0% → RBRB +6.8%) e spiegazione della distribuzione 40% aero / 35% grip / 25% PU.
- **Documentazione**: aggiornata sezione “Dataset sandbox” e “Classifica gap” in questo documento.

- **Adattatore per simulazione**: `scripts/run_sim_teams.py` ora costruisce `CarEntry` a partire dai pacchetti aero/grip/PU 2025 ridotti; `delta_aero`/`delta_grip` sono solo di contorno e la simulazione riflette direttamente i nuovi setup. Il wrapper gira per ogni circuito, registra i tempi simulati ed esporta JSON/HTML in `reports/`.
- **Report HTML**: i report comparativi sono stati rigenerati per Silverstone, Monza, Monaco, Baku, Suzuka, Spa e Barcellona con i valori aggiornati e l’ultima simulazione su Silverstone (con `--zero-baseline-delta`) certifica che i gap attesi sono ancora rispettati.
- **Registri ufficiali**: creati `python_backend/data/power_units.py` e `python_backend/data/cars.py` e collegati a `python_backend/data/teams/__init__.py`, che ora istanzia ogni `Team` con `auto` e `power_unit` ufficiali oltre a `pilota1/pilota2`. La migrazione dal sandbox è avvenuta mantenendo l’isolamento e assegnando `team_id` automaticamente.
- **Refactor Team**: `python_backend/models.py` espone ora `power_unit`, `auto`, `pilota1/2/riserva` come attributi nativi, applica clamp solo a `simulator_quality` e rende `bonus_prestazione` dipendente dagli attributi tecnici dell’`Auto`. Il loader ufficiale usa esclusivamente questo costruttore.
- **Adapter LapSimulator/SessionBridge**: `python_backend/utils/adapter.py` risolve `ice_mode` → `EngineMapName`, costruisce `PUState` da `team.power_unit.create_state()` e viene usato da SessionBridge, RaceCar builder e API per popolare lo stato sim.
- **Script e validator**: `scripts/run_sim_teams.py`, `scripts/physics_validator.py` e `scripts/congruence_check.py` non impostano più manualmente `PUState`; ogni baseline usa i registri ufficiali (MCL come reference) e le mappe Qualy per fuel da 2.5 kg.

### Prossimi passi
1. Aggiornare/estendere i test di regressione (LapSimulator e script) per coprire la pipeline `Team → RaceCar → CarEntry` con i nuovi factory e garantire coerenza fuel/mappe per tutti i consumer.
2. Documentare nella UI e nei manuali tecnici la nuova fonte dati (Auto/PU) e sincronizzare i report multi-circuito con i registri ufficiali via workflow `calibration.yml`.
3. Integrare un watchdog che rigeneri i report (Silverstone/Monza/Monaco/Baku/Suzuka/Spa/Barcellona) e segnali gap > 1% sfruttando direttamente `team.auto`/`team.power_unit`.

## LapSimulator e dati scalati
- Il wrapper `scripts/run_sim_teams.py` deve alimentare LapSimulator con le istanze `Auto` e `PowerUnit` scalate per il 2025, non applicare dei delta manuali sulla vettura di riferimento. McLaren resta la reference perché i suoi valori (aero, sospensioni, PU) sono quelli hardcodati nella simulazione, ma gli altri team devono ricevere direttamente i valori ridotti dalla sandbox (`cars_2025.py`, `power_units_2025.py`, `teams_2025.py`).
- LapSimulator gestisce realmente le prestazioni solo tramite i coefficienti `delta_aero`, `delta_grip` e `delta_power`, quindi è fondamentale che essi rappresentino la differenza tra la reference e i setup scalati (anche negativi se un team deve migliorare la reference). Tuttavia, il modo più pulito è lasciare i `delta_*` a zero e costruire il `CarEntry` con i dati definitivi della vettura: la fisica calcola automaticamente drag, downforce, grip e potenza sulla base di quegli input.
- Quando questi dati saranno promossi nei registri ufficiali (`python_backend/data/teams`, `data/cars.py`), il loader dovrà comportarsi allo stesso modo: ogni `Team` ha una `Auto` e una `PowerUnit` che riflettono la performance attesa, invece di tre campi di penalità sparsi.

### Penalità dinamiche del simulatore
- Oltre alle tre `delta_*`, il cuore di `update_section` applica penalità dinamiche legate ad usura gomma (`update_tyres`), handling (penalità da `aero_forces.handling_penalty`, camber/kerb/bumpiness) e derivazione termica della PU (`generate_output` derating, bucket ERS). Questo significa che, dopo aver passato setup 2025 completi, possiamo ancora bilanciare fine tuning tramite compound, sospensioni e mappe PU senza inventare nuovi `delta`. 
- Lo stesso motore integra aerodinamica reale direttamente da `AeroSetup` e `AeroForces`, quindi drag e downforce influenzano già la velocità di uscita dei settori.
- Conserviamo la configurazione reference originale del simulatore per confronti e benchmarking, ma i test di equilibrio usano i dati scalati + questi valori dinamici anziché manipolare manualmente i delta.

## Sviluppo motore fisico

### Visione di gameplay
- Partire dai coefficienti di downforce/drag dell’auto per determinare direttamente velocità in curva e in rettilineo.
- Assetti sbilanciati devono penalizzare sensibilmente il tempo sul giro: una McLaren con setup errato deve perdere decimi in ogni curva anche se la base vettura è la migliore.
- Circuiti diversi devono richiedere scelte di carico diverse (Monza → ala quasi zero, Monaco → massimo carico), premiando chi adatta il setup e penalizzando chi usa un assetto “bilanciato ma sbagliato” per il tracciato.

### Stato attuale
- `compute_forces` (@python_backend/lap_simulator/aero_package.py) somma DF/drag e calcola un `handling_penalty`, ma l’effetto è limitato a piccole variazioni di grip meccanico.
- Non esistono finestre circuito-specifiche: tutti i tracciati usano gli stessi coefficienti (`baseline_delta`, `k_aero_penalty`, ecc.) caricati da `config_loader`.
- I delta (`delta_aero`, `delta_grip`) sono applicati a fine sezione e non derivano da un modello fisico di “più DF = più drag”.
- La pipeline assetto (slider → valori fisici) non impone vincoli sulle piste: un setup 60/70 funziona allo stesso modo su Monza e Monaco se i delta restano nei range.

### Gap da colmare
1. **Penalità assetto deboli**: l’handling penalty riduce poco il grip e non limita la velocità in curva/uscita.
2. **Nessuna finestra per circuito**: manca un target DF/drag per pista; non c’è boost/penalty extra per low‑drag vs high‑drag.
3. **Assenza di saturazione**: gli angoli di ala non saturano la generazione del carico né impongono compromessi concreti su drag/top speed.
4. **Validazione limitata**: non esistono test automatici “setup ottimale vs setup sbagliato” che garantiscano differenze di almeno 0.6‑0.8s al giro.

### Roadmap proposta
1. **Layer circuito-specifico**: definire per ogni pista una tabella `target_aero` (range DF, rapporto front/rear, drag minimo) e applicare penalty moltiplicativi quando il setup cade fuori finestra.
2. **Penalità dinamiche forti**: estendere `handling_penalty` per agire direttamente su `df_front`/`df_rear` e introdurre un `drag_penalty` che riduca `v_max_kph` nei rettilinei quando l’ala è troppo carica.
3. **Assetto → fisica**: aggiornare `setup_engine_service` per mappare i slider sulle finestre circuito e implementare curve di saturazione/efficienza (più angolo → plateau DF ma drag esplode).
4. **Test & watchdog**: creare scenari di benchmark (setup ottimale vs errato su Monza/Monaco) e integrare il check nel watchdog, così ogni regressione viene segnalata oltre una soglia.

Questa sezione guida l’evoluzione del LapSimulator verso il “motore fisico” desiderato, mantenendo la base attuale ma introducendo layer di bilanciamento più aggressivi e circuit‑aware.

---

## Piano di implementazione
1. **Definizioni modelli**: creare `PowerUnit` e `Auto` in `python_backend/models/` con factory per `PUState`/`CarState` e setup base.
2. **Refactor Team**: aggiornare `Team` in `models.py` con campi nuovi; rimuovere legacy.
3. **Registry dati**: creare `data/power_units.py` e `data/cars.py` (o moduli equivalenti) con roster 2025, importati da `data/teams/__init__.py`.
4. **Migrazione dataset**: aggiornare `TEAMS` per usare `pilota1/2/riserva`, `power_unit`, `auto`.
5. **Consumatori**: adattare builder di gara/garage per leggere i nuovi campi; rimuovere riferimenti a campi eliminati.
6. **Test**: aggiungere test di integrità roster (Team→Auto/PU/Piloti) e factory di costruzione `RaceCar`.

## Decisioni aperte
- Nome campo riserva: `pilota_riserva` (proposto) vs `pilota_simulatore`.
- Collocazione `Auto`: campo diretto su Team (proposto) vs mapping esterno.
- Struttura registry: moduli separati `power_units.py` e `cars.py` o integrazione in `teams/__init__.py`.

## Glossario
- **PU**: Power Unit (ICE + ERS + fuel tank).
- **Auto**: chassis + aero + meccanica escluso motore.
- **Pilota**: entità con skill e stile di guida.
