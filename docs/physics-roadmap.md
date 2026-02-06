# FastF1 integration plan
Questo piano definisce come usare FastF1 come fonte dati reale per calibrare un simulatore F1 “gioco” (parametri circuito + modello tempo-giro/settori + gomme/meteo), senza l’obiettivo di riprodurre gare storiche.

## 1) Cosa ci dà FastF1 che è utile qui
- **Session object come entry point**: con `fastf1.get_session(...)` + `Session.load(...)` ottieni in modo coerente:
  - `session.laps` (timing/laps)
  - `session.car_data` e `session.pos_data` (telemetria/posizioni per driver number)
  - `session.weather_data`
  - `session.track_status`, `session.session_status`, `session.race_control_messages`
  - `session.results`
- **Telemetry utilities**: oggetto Telemetry con helper per:
  - `slice_by_lap`, `slice_by_time`
  - `merge_channels`, `resample_channels`, `fill_missing`
  - `add_distance`, `add_relative_distance`, `add_track_status`, `add_driver_ahead`
  - Nota importante dalle docs: `add_distance`/integrazione accumula errore → meglio per singolo giro o pochi giri.
- **Caching e rate limits**: FastF1 ha caching “stage 1/2” e offline mode (restituisce solo cache). Questo è cruciale per non martellare le API e per ripetibilità.
- **LiveTiming client**: `fastf1.livetiming` permette di registrare durante una sessione (anche in debug) e poi estrarre/riusare i messaggi. Potenzialmente utile per generare dataset JSONL simili al tuo `python_backend/telemetry/lap_debug.jsonl`.

## 1c) Dati che abbiamo già (repo Wizards2k/F1-Manager-Simulator)
- Esistono file JSON per ogni GP e sessione:
  - `*_2024_Q.json` (pole/qualifying fastest)
  - `*_2024_R.json` (fastest/representative lap in gara, con fuel stimato)
- Struttura osservata (esempio `italy_2024_Q.json`):
  - metadati: `CircuitName`, `SessionType`, `Year`, `Driver`, `LapTime`, `EstimatedFuelLevel`, `TireCompound`, `TireLife`, `Sector*Time`, `OfficialSectorMapping`
  - array `TelemetryPoints[]` con campi già pronti per il modello segment-based:
    - `Speed`, `RPM`, `Gear`, `Throttle`, `Brake`, `DRS`
    - `TimestampSeconds`
    - `DistanceFromStart` (metri lungo il giro)
    - coordinate `X`, `Y`
- Inoltre esiste una cartella `Circuit_data/*_mapping.json` (es. `italy_mapping.json`) che contiene:
  - `circuit_length` e una lista `sections[]` con segmenti già classificati (`Straight`, `SlowCorner`, `FastCorner`) e range `start/end` in metri
  - `telemetry_stats` e vari “legacy_parameters” (utili come baseline di tuning)

## 1b) Come lo useremo (focus “gioco realistico”)
- **Calibrazione del profilo circuito**: estrarre (o derivare) zone di curva/rettilineo, distanze e marker per costruire un profilo utilizzabile dal tuo calcolo settori/tempo-giro.
- **Calibrazione del modello tempo-giro**: usare telemetria reale per stimare parametri di accelerazione/frenata, velocità di percorrenza in curva (curvatura vs velocità), penalità gomme (compound/age), effetti meteo.
- **Validazione**: confrontare l’output della simulazione con statistiche aggregate (distribuzione lap time, delta per compound, coerenza settori), non “copiare” una singola gara.

## 1d) Ruolo FastF1 vs file Telemetry esistenti
- **Datasource primario (subito utilizzabile)**: i file `*_Q.json`/`*_R.json` + `Circuit_data/*_mapping.json` perché contengono già:
  - `DistanceFromStart`
  - `Throttle/Brake`
  - settori ufficiali e mapping index→timestamp
  - segmentazione base del circuito
- **FastF1 come “generatore/aggiornatore”**:
  - se vogliamo aggiungere anni/circuiti mancanti o rigenerare la segmentazione
  - per verificare correttezza/consistenza (o arricchire con meteo/track status)

## 2) Dove si aggancia nel tuo repo (stato attuale)
- **Backend Flask**: entry `python_backend/f1_manager_ai.py` + routes in `python_backend/routes/api.py`.
- **Telemetria debug**: `python_backend/utils/lap_telemetry.py` scrive `python_backend/telemetry/lap_debug.jsonl` (feature flag `LAP_DEBUG_ENABLED`).
- **Simulazione**: `python_backend/utils/simulation.py` calcola settori/giro e aggiorna `RaceCar`; `RaceCar._persist_lap_debug` aggrega dati (compound, grip, settore, circuito, ecc.).

## 3) Obiettivo (allineato alla tua richiesta)
- **A. Calibrazione del simulatore (primary)**
  - Usare FastF1 per creare dataset di riferimento e “fit” di parametri del modello.
  - Il gioco resta autonomo: generiamo gare nuove, ma con dinamiche credibili.

## 4) Proposta architetturale (read-only, nessun codice ancora)
- **Modulo dedicato “data provider”** (nuovo) con interfacce tipo:
  - `get_session_meta(year, gp, kind)`
  - `get_laps(year, gp, kind, drivers=...)`
  - `get_telemetry_for_lap(year, gp, kind, driver, lap_no, channels=...)`
  - `export_dataset_jsonl(..., out_path)`
- **Caching**
  - Abilitare cache FastF1 in una cartella configurabile (es: `python_backend/.fastf1_cache/` o path da env).
  - Usare offline mode per riproducibilità (dataset “freezato”).
- **Persistenza**
  - Per dataset: esportare JSON/JSONL, non DataFrame pickled (più portabile, versionabile).
  - Per runtime: mettere un micro-cache applicativo (in-memory LRU o su disco) per query frequenti (es. stessa session/lap).

## 5) Mapping dati FastF1 → tuoi concetti (regola: tutto offline)

> **Project rule:** la simulazione deve funzionare al 100% offline. Tutti i dati FastF1 vengono acquisiti e trasformati in asset statici (JSON/JSONL) prima dell’esecuzione del gioco; nessuna dipendenza da feed live.
- **Driver**: FastF1 usa driver number come string (coerente col tuo `driver_number`).
- **Lap types**: nel tuo modello hai `OUT_LAP/HOT_LAP/IN_LAP/BOX`; FastF1 ha flags in laps (da verificare nel dettaglio nei campi di `Session.laps`) → mappatura da definire.
- **Settori**: FastF1 può fornire `Sector1Time/Sector2Time/Sector3Time` nei laps (da confermare nella Data Reference) e/o derivabili.
- **Tyres/compound**: FastF1 espone compound/stint info nei laps; nel tuo modello hai `TireCompound` + `Gomma` con usura. Possiamo:
  - usare compound reale come input;
  - stimare una curva di degrado per compound da fitting su lap time delta.
- **Track status / safety car**: FastF1 offre `track_status` e race control messages; utile per “neutralizzare” giri non comparabili.

## 5b) Uso diretto nel calcolo del giro (idee operative)
- **Curva/rettilineo e target speed**
  - Da telemetria reale (Speed vs Distance) puoi stimare:
    - velocità massima in rettilineo (drag/power limit)
    - punti di frenata e pendenze di decelerazione (brake performance)
    - velocità minima in curva (lateral grip “effettivo”)
  - Questi diventano parametri per un modello “segment-based”: per ogni segmento del circuito definisci `v_target(distance)` e penalità gomme.
- **Settori più credibili**
  - Invece di calcolare settore solo da distanza e “random”, puoi calcolare il tempo come somma di micro-step lungo il circuito usando `v(distance)`.
  - I tuoi settori possono essere agganciati a marker del circuito (o ai tuoi `circuit_sectors`).
- **Gomme/degrado**
  - Dalle laps reali (compound + tyre age + lap time) puoi stimare curve di degrado per compound e applicarle al tuo `Gomma.aggiorna_degrado()`.
- **Meteo**
  - `weather_data` può guidare coefficienti (grip, degrado, probabilità errori) per condizioni caldo/freddo/pioggia.

## 5c) Modello “segment-based” con aero (DF/drag) + power unit (mappature)
- **Obiettivo**
  - Calcolare il tempo-giro come somma dei tempi sui segmenti del circuito, dove ogni segmento impone limiti diversi: trazione, frenata, grip laterale.
  - Rendere modificabili parametri “giocabili”: incidenze ali, livello di carico (fondo/ali), drag, potenza PU, mappature ERS.
- **Rappresentazione circuito**
  - Segmenti sequenziali con attributi minimi:
    - `length_m`
    - `kind` ∈ {`straight`, `brake`, `corner`, `accel`}
    - opzionale: `radius_m` o `curvature` per le curve (se disponibile); altrimenti una classe di curva (`slow/medium/fast`).
  - Nota: i marker “corners” di FastF1 sono utili come guida/annotazione ma non super-accurati; per la segmentazione conviene derivare le zone da `Speed(distance)` (frenate e minimi di velocità).
- **Parametri vettura (gameplay)**
  - Aero (derivati da componenti: ala ant/post, fondo, carrozzeria):
    - `ClA_base` (downforce “effettivo” come coefficiente*area)
    - `CdA_base` (drag “effettivo”)
    - `front_wing_angle`, `rear_wing_angle` → delta su `ClA` e `CdA`
    - distribuzione bilanciamento (es. `aero_balance`) per influenzare stabilità/velocità minima in curva (opzionale)
  - Power unit:
    - `P_ice` (potenza termico)
    - `P_ers_map` (qualifica/sorpasso/gara) → fattore o additivo su potenza totale
    - `v_max_gearing` (limite “meccanico”/rapporti: opzionale)
  - Massa/aderenza:
    - `mass_kg`
    - `mu_base` (grip meccanico base)
    - gomme: `mu_tyre(compound, age, temp)` e degrado.
- **Equazioni base (semplificate ma coerenti)**
  - Downforce: `F_down(v) = 0.5 * rho * ClA * v^2`
  - Drag: `F_drag(v) = 0.5 * rho * CdA * v^2`
  - Limite laterale in curva (approssimazione):
    - `F_lat_max(v) = mu_eff * (mass*g + F_down(v))`
    - `v_corner_max ≈ sqrt( (F_lat_max / mass) * radius )`
    - dove `mu_eff` dipende da gomma + temperatura + stato pista.
  - Accelerazione in rettilineo (approssimazione “power-limited”):
    - `P_total = P_ice + P_ers(map)`
    - `F_drive(v) ≈ P_total / max(v, v_eps)` (limitata da trazione a bassa velocità)
    - `a(v) = (F_drive(v) - F_drag(v) - F_roll) / mass`
  - Frenata:
    - `a_brake_max ≈ mu_brake * (g + F_down(v)/mass)` (limitata dall’aderenza)
  - In pratica, per ogni segmento si integra numericamente per ottenere tempo e velocità di uscita.
- **Come entra il setup ali**
  - `front_wing_angle`/`rear_wing_angle` aggiornano `ClA` e `CdA`:
    - più ala → più `ClA` → curva più forte (v_min più alta)
    - ma aumenta `CdA` → top speed più bassa e accel peggiore ad alta v
  - Questo crea il tradeoff corretto “setup da Monaco vs Monza”.

## 5d) Come FastF1 aiuta a calibrare aero e PU
- **Calibrare `CdA`/potenza dalla top speed**
  - Dai tratti di pieno gas (rettilinei lunghi) osservi plateau di velocità.
  - In steady-state: `F_drive(v) ≈ F_drag(v)` → colleghi `P_total` e `CdA`.
  - Non serve stimare assoluti perfetti: basta una scala coerente per far funzionare le differenze tra setup e mappe ERS.
- **Calibrare `ClA`/grip dalla velocità minima in curva**
  - Identifica per ogni curva il minimo di `Speed` e la velocità in percorrenza.
  - La relazione con `F_down(v)` ti dà una stima di quanto la downforce aiuta nelle curve veloci rispetto alle lente.
- **Calibrare frenata/accelerazione**
  - Da `Brake`/`Throttle` + derivata di `Speed` (o slope Speed vs Time) ricavi profili medi di decel/accel in funzione di velocità.
- **Output della calibrazione**
  - Per circuito: mappa segmenti + target `v_corner` per classi di curva e rettilinei principali.
  - Per “classe auto” (era): range plausibili di `ClA`/`CdA` e `P_total`.
  - Per setup: delta `ClA`/`CdA` per click di ala.

## 5e) Handling: sottosterzo/sovrasterzo da bilanciamento aero + impatto su corner speed e usura
- **Idea base**
  - Separare la downforce in due contributi: `ClA_front` e `ClA_rear`.
  - Definire un indicatore di bilanciamento aero:
    - `aero_balance = ClA_front / (ClA_front + ClA_rear)`
    - range tipico target: ~`0.45`–`0.55` (dipende dall’auto/era; va tarato)
  - Scostarsi dal target genera:
    - **sottosterzo** se `aero_balance` troppo basso (front debole)
    - **sovrasterzo** se `aero_balance` troppo alto (rear debole)
- **Penalità su velocità in curva (prima iterazione)**
  - Calcoli `v_corner_max` “ideale” dal grip (mu + downforce totale).
  - Applichi una riduzione in base a quanto sei sbilanciato:
    - `balance_error = aero_balance - aero_balance_target`
    - `handling_penalty = k_handling[class] * abs(balance_error)`
    - `v_corner = v_corner_max * (1 - handling_penalty)`
  - `k_handling` diverso per classe curva:
    - curve lente: più sensibili a trazione/rotazione (k più alto)
    - curve veloci: più sensibili a stabilità aero (k alto o medio, da tarare)
    - curve medie: k medio
- **Effetto secondario (opzionale ma utile): errore/instabilità**
  - Se `abs(balance_error)` supera una soglia, aumenti probabilità di:
    - micro-lift (perdita throttle)
    - bloccaggio (frenata meno efficace)
    - correzioni (piccoli dt extra)
- **Usura gomme (prima iterazione: per asse)**
  - Mantieni `tire_wear_front` e `tire_wear_rear` (o incrementi su `tire_wear` con contributi separati).
  - Regola semplice:
    - sottosterzo (`balance_error < 0`) → stress anteriore ↑ → wear front ↑
    - sovrasterzo (`balance_error > 0`) → stress posteriore ↑ → wear rear ↑
  - Esempio (concettuale):
    - `wear_front += base_wear * (1 + k_wear * max(0, -balance_error))`
    - `wear_rear  += base_wear * (1 + k_wear * max(0,  balance_error))`
  - `base_wear` dipende da:
    - lunghezza/tempo del segmento di curva
    - compound e temperatura (in futuro)
- **Gancio per futura usura per singola gomma**
  - Estendere da `{front,rear}` a `{FL,FR,RL,RR}` usando:
    - direzione curva (sinistra/destra) se disponibile dal profilo circuito
    - distribuzione carico laterale (approssimata) per scaricare usura sulla gomma esterna

## 5f) Assetto (setup): ali, altezza, sospensioni
- **Obiettivo**
  - Dare al giocatore leve che cambiano realmente la performance in modo coerente e “circuit-dependent”, senza introdurre un modello troppo complesso.
  - L’assetto deve influenzare direttamente i parametri del modello: `ClA_front`, `ClA_rear`, `CdA`, `mu_eff` e `aero_balance`.
  - L’assetto ottimale è **specifico per circuito**; in evoluzione potrà dipendere anche da meteo e condizioni pista.

### 5f.0 Scala controlli (1–100) e normalizzazione
- **Scelta UI**
  - Tutti i controlli setup sono espressi come interi `1..100`.
- **Normalizzazione**
  - Convertire in uno scalare `u ∈ [0,1]`:
    - `u = (value - 1) / 99`
  - Usare curve non lineari dove serve (per evitare che 1 click cambi troppo):
    - `u_smooth = u^gamma` (es. `gamma=1.3` per rendere più “fine” la parte bassa)
    - oppure `u_smooth = smoothstep(u)`.
- **Severità “media” (target)**
  - Setup pessimo deve costare circa:
    - ~`0.5s`–`2.0s` sul giro (dipende dal circuito)
  - Setup buono vs ottimo deve dare margini in decimi, non secondi.

### 5f.1 Ali (Front wing / Rear wing)
- **Variabili giocatore**
  - `front_wing` in `1..100`
  - `rear_wing` in `1..100`
- **Effetti fisici (prima iterazione)**
  - Convertire `front_wing`/`rear_wing` in `u_front/u_rear` con la normalizzazione sopra.
  - `ClA_front = ClA_front_base + dClA_front * u_front`
  - `ClA_rear  = ClA_rear_base  + dClA_rear  * u_rear`
  - `CdA = CdA_base + dCdA_front * u_front + dCdA_rear * u_rear`
  - `aero_balance` cambia e quindi influenza sottosterzo/sovrasterzo (sezione 5e)
- **Tradeoff gameplay**
  - più ala → curva più forte (soprattutto fast corner) ma top speed e accel peggiorano
  - più rear wing → più stabilità in ingresso/centro curva, ma più drag
  - più front wing → più “turn-in” ma rischio sovrasterzo e usura posteriore se il bilanciamento diventa estremo

### 5f.2 Altezza da terra (Ride height)
- **Variabili giocatore**
  - `ride_height_front` in `1..100`
  - `ride_height_rear` in `1..100`
- **Effetti fisici (semplificati ma utili)**
  - Convertire in `u_rh_front/u_rh_rear`.
  - Interpretazione: 1 = molto basso, 100 = molto alto.
  - Altezza più bassa → floor più efficiente:
    - `ClA_total` aumenta (soprattutto in curva veloce)
    - `CdA` può aumentare leggermente o restare quasi invariato (dipende dal modello scelto)
  - Altezza troppo bassa su circuito sconnesso → penalità:
    - rischio “bottoming”/instabilità → riduzione `mu_eff` o aumento `handling_penalty`
    - aumento usura (vibrazioni) e probabilità errori
- **Dipendenza dal circuito**
  - usare `circuit_bumpiness`/`circuit_smoothness` (se disponibili nei mapping) per modulare:
    - soglia minima di ride height
    - severità della penalità quando troppo basso

### 5f.3 Sospensioni (rigidezza / compliance)
- **Variabili giocatore**
  - `suspension_front` in `1..100`
  - `suspension_rear` in `1..100`
  - opzionale: `antiroll_front`, `antiroll_rear` (in una fase successiva)
- **Effetti fisici (prima iterazione)**
  - Convertire in `u_susp_front/u_susp_rear`.
  - Sospensioni più rigide:
    - migliorano piattaforma aero (mantengono assetto stabile) → boost su `ClA_effective`
    - ma peggiorano grip meccanico su sconnesso/cordoli → riducono `mu_base` effettivo
  - Sospensioni più morbide:
    - migliorano `mu_base` su sconnesso → più trazione e stabilità lenta
    - ma riducono stabilità aero in curve veloci → più `handling_penalty` o `ClA_effective` più basso
- **Dipendenza dal tipo di curva**
  - curve lente: conta di più `mu_base` (trazione)
  - curve veloci: conta di più piattaforma aero (`ClA_effective`)

### 5f.4 Integrazione nel modello segment-based
- **Corner segments**
  - `v_corner_max` deriva da `mu_eff` e downforce totale;
  - `mu_eff` viene da: `mu_base` (sospensioni + bumpiness) * gomma * meteo * penalità handling.
- **Straight/accel segments**
  - `CdA` influenza `F_drag(v)`;
  - `P_total` (PU+ERS) determina `F_drive(v)`;
  - `DRS` (se modellato) può ridurre `CdA` in rettilineo.

### 5f.5 Impatto su usura gomme (semplificato)
- Ali e bilanciamento:
  - spostare `aero_balance` lontano dal target aumenta wear sull’asse “debole” (sezione 5e).
- Ride height troppo basso:
  - aumenta wear globale (vibrazioni/bottoming) e degrado termico simulato.
- Sospensioni troppo rigide su pista sconnessa:
  - aumenta wear e riduce consistenza (più varianza sul tempo-giro).

### 5f.6 Come si “ottimizza” l’assetto per un circuito (regole intuitive)
- circuiti con lunghi rettilinei (Monza): ridurre ali (CdA↓), accettando minor velocità in curva.
- circuiti con curve veloci (Silverstone/Suzuka): aumentare efficienza aero (ClA↑) e stabilità.
- circuiti sconnessi/cordoli (Baku/Monaco): ride height ↑ e sospensioni più morbide per `mu_base`.

### 5f.9 Estensione futura: meteo e condizioni pista
- **Meteo**
  - temperatura aria/pista: influenza `mu_eff` e `tire_wear` (finestre operative)
  - pioggia: abbassa `mu_eff`, aumenta penalità handling e modifica degrado (intermedie/wet)
- **Condizioni pista**
  - “green track” vs gommato: modifica `mu_eff`
  - vento: può alterare stabilità in curve veloci (prima iterazione: piccola varianza su `v_corner`)

### 5f.10 Estensione futura: temperatura gomme, finestra di utilizzo e guasti
- **Temperature gomme + finestra**
  - Aggiungere stato gomma: `tire_temp` (o `tire_temp_front/rear`) e definire per compound una `optimal_window`.
  - Effetto sul modello:
    - se sotto-finestra: `mu_eff` ↓ (mancanza grip), wear può aumentare per scivolamento
    - se sopra-finestra: `mu_eff` ↓ (surriscaldamento), `tire_wear` ↑
  - Input che influenzano temp: pace/traffic, temperatura pista, pressione gomme, scivolamento da under/oversteer.
- **Temperatura motore e guasti**
  - Aggiungere stato PU: `engine_temp`, `ers_temp`, `cooling_level`.
  - Effetto sul modello:
    - temperatura alta → `P_total` limitato (derating) e probabilità guasto ↑
    - guasto → perdita potenza o DNF (in base a severità)
  - Input che influenzano temp: mappa PU/ERS, scia/aria sporca (futuro), condizioni ambientali.

### 5f.7 Calibrazione iniziale con dataset Telemetry
- Usare `*_Q.json` come riferimento per “massima performance” e `*_R.json` come riferimento di gara.
- Obiettivo tuning: riprodurre:
  - `max_speed_kmh` (sensibile a `CdA` e `P_total`)
  - `min_speed` e `avg_speed` in `sections` (sensibili a `ClA_effective` e `mu_eff`)
  - differenze tra Q e R (fuel/compound/ERS).

### 5f.8 Regole “parc fermé” (lock setup)
- **Vincolo di regolamento (come da tua richiesta)**
  - Il setup completo (ali, altezza, sospensioni) è modificabile fino all’ultima sessione pre-qualifica.
  - Dopo il lock:
    - modificabile solo `front_wing` (ala anteriore)
    - modificabile `tyre_pressure` (pressione gomme; modellazione iniziale semplificata)
    - modificabili le mappature `ERS/PU` (gioco)
- **Implicazione tecnica**
  - Salvare uno stato `setup_locked: bool` per vettura/sessione.
  - Validare lato backend: rifiutare modifiche ai campi bloccati quando `setup_locked=True`.
  - Le modifiche consentite post-lock devono riflettersi in tempo reale su `ClA_front` (front wing) e su parametri gomma (pressione) e `P_total` (ERS map).

## 6) Rischi / note pratiche
- **Peso dati**: car telemetry per sessioni intere è grande; meglio lavorare per driver+lap e resampling.
- **Rate limits**: senza cache si rischiano errori/ban temporanei; la cache è obbligatoria.
- **Compatibilità**: i formati/campi variano per anno/evento; va gestita la mancanza di dati (`f1_api_support`).

## 7) Deliverable proposti (in ordine)
1. **Spec parametri da stimare**: accel/freno, v-curva, drag/top speed, degrado per compound, effetti meteo.
2. **Spec dataset**: campi minimi per fitting (telemetry per lap, laps/settori, compound/tyre age, meteo, track status).
3. **Proof-of-concept**: estrarre 1 circuito/sessione di riferimento e generare JSONL “training” + script di fitting.
4. **Integrazione nel modello**: usare i parametri stimati dentro `project_sector_time`/`compute_projected_lap_time`.

## 8) Domande per te (per finalizzare)
- Vuoi che la simulazione sia tarata su un “era” specifica (es. 2020s ground effect) o più generica?
- Ti interessa stimare parametri per:
  - un’unica “classe auto” (semplificato),
  - o per team/driver (più realistico ma più complesso)?
- Per il fitting iniziale preferisci:
  - usare solo **qualifying laps** (più pulite),
  - o anche **race stints** (introduce fuel/traffic)?

