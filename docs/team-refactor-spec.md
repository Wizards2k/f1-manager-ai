# Specifica refactor: Team, Auto, PowerUnit, Pilota (e classi correlate)

## Obiettivo
Separare le responsabilità tra entità di dominio (Team, Auto, PowerUnit, Pilota, Pit Crew) eliminando campi ibridi e introducendo classi dedicate per motore e telaio. Il Team diventa un contenitore di risorse (piloti, auto, PU) senza parametri tecnici duplicati.

## Stato attuale (feb 2026)
- `Team` (@python_backend/models/models.py) include campi ibridi (forza_auto, affidabilita, aerodinamica, meccanica, pitstop_skill) e `power_unit` come stringa.
- Dataset `TEAMS` (@python_backend/data/teams/__init__.py) istanzia 10 scuderie 2025 e assegna `team_id` incrementale.
- Logica motore già presente in `lap_simulator/power_unit.py` + `PUState`/`EngineMapParams` in `data_types.py`, ma non esiste una classe dati “PowerUnit” a livello roster.

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

## Stato lavori (26 feb 2026)

### Fatto
- **Dataset sandbox**: creati `python_backend/tmp_data/power_units_2025.py`, `cars_2025.py`, `teams_2025.py` con istanze `PowerUnit`, `Auto`, `Team` basate sui gap dei primi 3 GP 2025 (baseline McLaren). I moduli sono isolati e non importati dal gioco.
- **Classifica gap**: tabella con gap attesi per ogni squadra (MCL 0.0% → RBRB +6.8%) e spiegazione della distribuzione 40% aero / 35% grip / 25% PU.
- **Documentazione**: aggiornata sezione “Dataset sandbox” e “Classifica gap” in questo documento.

### In corso
- **Adattatore per simulazione**: `scripts/run_sim_teams.py` ora costruisce `CarEntry` applicando penalità `delta_aero`/`delta_grip` calcolate dal gap target e dai coefficienti `k_*` del circuito (con `--zero-baseline-delta` si mantiene McLaren al tempo telemetrico). Il wrapper gira per ogni circuito, registra i tempi simulati ed esporta JSON/HTML in `reports/`.
- **Report HTML**: i report comparativi sono stati rigenerati per Silverstone, Monza, Monaco, Baku, Suzuka, Spa e Barcellona, ciascuno con gap atteso vs simulato analizzato.

### Prossimi passi
1. Consolidare i report multi-circuito (e.g., Silverstone/Monza/Monaco/Baku/Suzuka/Spa/Barcelona) in un documento di confronto o dashboard per evidenziare eventuali deviazioni.
2. Integrare la pipeline con il watchdog CLI e il workflow `calibration.yml` affinché ogni push rigeneri i report e segnali gap > 1%.
3. Valutare come promuovere i dataset sandbox verso i registri ufficiali mantenendo il mapping `auto`/`power_unit` per i team reali.
4. Ogni nuova pista deve continuare a usare `run_sim_teams.py --zero-baseline-delta` per garantire che McLaren resti sul riferimento e che gli altri team riflettano i gap target.

## LapSimulator e dati scalati
- Il wrapper `scripts/run_sim_teams.py` deve alimentare LapSimulator con le istanze `Auto` e `PowerUnit` scalate per il 2025, non applicare dei delta manuali sulla vettura di riferimento. McLaren resta la reference perché i suoi valori (aero, sospensioni, PU) sono quelli hardcodati nella simulazione, ma gli altri team devono ricevere direttamente i valori ridotti dalla sandbox (`cars_2025.py`, `power_units_2025.py`, `teams_2025.py`).
- LapSimulator gestisce realmente le prestazioni solo tramite i coefficienti `delta_aero`, `delta_grip` e `delta_power`, quindi è fondamentale che essi rappresentino la differenza tra la reference e i setup scalati (anche negativi se un team deve migliorare la reference). Tuttavia, il modo più pulito è lasciare i `delta_*` a zero e costruire il `CarEntry` con i dati definitivi della vettura: la fisica calcola automaticamente drag, downforce, grip e potenza sulla base di quegli input.
- Quando questi dati saranno promossi nei registri ufficiali (`python_backend/data/teams`, `data/cars.py`), il loader dovrà comportarsi allo stesso modo: ogni `Team` ha una `Auto` e una `PowerUnit` che riflettono la performance attesa, invece di tre campi di penalità sparsi.

### Penalità dinamiche del simulatore
- Oltre alle tre `delta_*`, il cuore di `update_section` applica penalità dinamiche legate ad usura gomma (`update_tyres`), handling (penalità da `aero_forces.handling_penalty`, camber/kerb/bumpiness) e derivazione termica della PU (`generate_output` derating, bucket ERS). Questo significa che, dopo aver passato setup 2025 completi, possiamo ancora bilanciare fine tuning tramite compound, sospensioni e mappe PU senza inventare nuovi `delta`. 
- Lo stesso motore integra aerodinamica reale direttamente da `AeroSetup` e `AeroForces`, quindi drag e downforce influenzano già la velocità di uscita dei settori.
- Conserviamo la configurazione reference originale del simulatore per confronti e benchmarking, ma i test di equilibrio usano i dati scalati + questi valori dinamici anziché manipolare manualmente i delta.

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
