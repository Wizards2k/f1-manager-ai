# Gameplay MVP (Team Management)
Questo piano definisce l’MVP di gameplay per permettere al giocatore di gestire una scuderia (2 auto) e impartire comandi base durante una sessione.

## 1) Obiettivo MVP
- Dare un primo loop giocabile: scegli team → controlli 2 auto → vedi risultati (tempo sul giro, stato stint, gomme, rientri).
- Non richiede ancora fisica segment-based completa: i comandi devono comunque avere effetti visibili e coerenti.

Scope decisioni:
- Sessione unica: **Practice**
- In questa fase si muovono **solo le 2 auto del giocatore**; le altre auto restano ferme ai box.

Scelte architetturali (MVP):
- Comandi giocatore via **REST (POST)**.
- Aggiornamenti stato sessione/auto via **SocketIO** (`race_update`).
- Auto non-player ferme: introdurre `car.is_player_controlled` e saltare l’update quando `False`.

## 2) Comandi base (quelli che hai elencato)
Per ciascuna delle 2 auto del giocatore:
1. Mandare in pista (uscita box)
2. Selezionare gomme
3. Impostare passo/spinta
4. Decidere carico carburante
5. Richiamare ai box

Nota: la durata della stint viene impostata come "giri target" prima di premere il bottone di uscita dai box.

Regola stint (Practice MVP):
- Dopo `Send out`, l’auto completa automaticamente `stint_target_laps` hot laps e poi rientra (IN_LAP → BOX),
  a meno che il giocatore non prema **Box** per un richiamo anticipato.

Regola **Box** (Practice MVP):
- Quando il giocatore preme **Box**, lo stato passa immediatamente a `IN_LAP`.
- L’auto rientra ai box non appena raggiunge l’entry/box (senza necessariamente completare il giro corrente).

## 3) Comandi “minimi” aggiuntivi confermati
- Mappature **ICE** e **ERS**: controllo stile "qualifica/sorpasso/gara" (o simile), con effetto su prestazione/consumo.
- Durata stint come **giri target**: il giocatore imposta `stint_target_laps` prima della release.
- Bottone **Send out**: rilascia l’auto dai box e la manda in pista usando le scelte correnti (gomme, fuel, mappe, passo, stint).

## 3d) Setup feedback (Practice MVP)
- Il feedback è:
  - **sempre** generato al rientro ai box (fine run)
  - **opzionale live** durante il run (dipende dalla skill del pilota `Pilota.ricerca_assetto`)
- Formato feedback:
  - testo in-game in inglese
  - indicatori a colori (no numeri): `Red`, `Orange`, `Yellow`, `Green`, `Fuchsia`
- Categorie feedback MVP:
  - `Cornering balance` (Understeer/Oversteer)
  - `Straight-line speed` (Drag)
  - `Traction` (slow corners / exits)
  - `Stability` (braking)

## 3b) Controllo "Spinta" (pace) – definizione MVP
- **UI**
  - Slider `pace_level` in `1..10`.
  - Interpretazione: `1` conservativo, `5` medio, `10` massimo (massimo rischio).
- **Effetti (prima iterazione, facili da tarare)**
  - `pace_factor = 1 + k_pace_time * (pace_level - 5)`
    - `pace_level > 5` → giri più veloci
    - `pace_level < 5` → giri più lenti
  - Usura gomme (deve pesare più del fuel):
    - `tire_wear_rate = base_tire_wear * (1 + k_pace_tire * (pace_level - 5))`
  - Consumo fuel (meno sensibile di gomme):
    - `fuel_burn_rate = base_fuel_burn * (1 + k_pace_fuel * (pace_level - 5))`
  - Rischio (errori/lockup/uscita):
    - `risk = base_risk + k_pace_risk * max(0, pace_level - 7)`
  - Nota: i coefficienti `k_*` sono da tuning; l’obiettivo è severità “media” (decimi/qualche secondo su stint lungo), non punizione estrema.

## 3c) Mappe ICE/ERS – priorità su fuel, secondaria su performance
- **Scelta di design**
  - Come richiesto: le mappe ICE/ERS impattano **di più il fuel** che le gomme.
  - Convenzione: UI e terminologia di gioco **in inglese**.
- **Modello semplificato**
  - `fuel_burn_rate *= ice_fuel_multiplier[ice_mode] * ers_fuel_multiplier[ers_mode]`
  - `pace_factor *= ice_time_multiplier[ice_mode] * ers_time_multiplier[ers_mode]` (effetto più piccolo rispetto al fuel)
- **Interazione con Spinta**
  - `Spinta` modula soprattutto `tire_wear_rate`.
  - `ICE/ERS` modula soprattutto `fuel_burn_rate`.
  - Entrambi possono influenzare il tempo-giro (ma con pesi diversi).

Stati confermati:
- `ice_mode` (3 stati): `Save`, `Standard`, `Push`
- `ers_mode` (4 stati): `Harvest`, `Neutral`, `Deploy`, `Overtake`

## 4) Selezione team e associazione auto-giocatore
- UI iniziale: selezione team.
- Backend: memorizzare `player_team_id` e individuare le 2 `RaceCar` del team.

## 5) Stato auto necessario (estensione minima)
- Attributi per auto:
  - `is_player_controlled` (bool)
  - campi diretti per: `target_compound`, `target_fuel`, `pace_mode`, `ers_mode`, `ice_mode`, `pit_request`, `stint_target_laps`
  - `setup_locked` (parc fermé; per ora può restare sempre True/False in base alla sessione)

Nota fuel:
- `target_fuel` è una percentuale `1..100` dove `100` è pieno e `1` è quasi vuoto.

## 6) Mappatura comandi → logica attuale (punti di aggancio)
- `RaceCar.exit_box()` oggi sceglie gomme random: va trasformato in “usa gomme scelte dal giocatore se presenti”.
- `RaceCar.enter_box()` oggi imposta un timer random: per il giocatore va aggiunta la possibilità di:
  - restare in box finché non viene dato il comando “manda in pista”
- `stint_target_laps` oggi è random: legarlo al comando “obiettivo run” o al fuel.

Gestione auto non giocatore (AI) in questa fase:
- Approccio minimo: in `update_car_position` saltare l’update se `not car.is_player_controlled`.
- Alternativa equivalente: mantenere le AI in `BOX` con `box_time_until` molto alto.

Nota implementativa (preferita): usare l’approccio `is_player_controlled` (più chiaro e meno fragile).

## 6b) API comandi giocatore (REST POST) – MVP
Nota: i nomi API sono in stile tecnico; i testi UI in-game restano in inglese.

- `POST /api/player/team/select`
  - body: `{ "team_id": 3 }`
  - effetto: setta `player_team_id` e marca `is_player_controlled=True` sulle 2 auto del team.

- `POST /api/player/car/<driver_number>/configure`
  - body:
    - `tyre_compound`: `SOFT|MEDIUM|HARD`
    - `fuel_percent`: `1..100`
    - `pace_level`: `1..10`
    - `ice_mode`: `Save|Standard|Push`
    - `ers_mode`: `Harvest|Neutral|Deploy|Overtake`
    - `stint_target_laps`: `1..N`
  - effetto: salva le scelte come “pending config” per l’auto.

Regole di validazione (MVP):
- Se l’auto è **in pista** (`OUT_LAP|HOT_LAP|IN_LAP`):
  - endpoint **strict**: `/configure` accetta solo `pace_level`, `ice_mode`, `ers_mode`
  - tentativi di cambiare `tyre_compound`, `fuel_percent`, `stint_target_laps` (o setup/assetto in futuro) devono ritornare errore (4xx)
- Se l’auto è **in box** (`BOX`):
  - è possibile cambiare tutto (tyres/fuel/pace/maps/stint)

- `POST /api/player/car/<driver_number>/send_out`
  - effetto: applica la config corrente e chiama l’equivalente di `exit_box()` per iniziare la stint.

- `POST /api/player/car/<driver_number>/box`
  - effetto: set immediato di stato `IN_LAP` (richiamo anticipato).

## 6d) Vincolo fuel → massimo giri stint (MVP)
Per la prima iterazione, il fuel è una percentuale `1..100` e definisce un limite massimo di giri completabili.

Proposta semplice (tarabile):
- Definire un coefficiente circuito/sessione `fuel_laps_at_100` (es. 12 giri con fuel al 100%)
- `max_stint_laps = floor(fuel_percent / 100 * fuel_laps_at_100)`
- `stint_target_laps` deve rispettare `1 <= stint_target_laps <= max_stint_laps`

Nota: in run, il fuel scende e quindi il limite può solo peggiorare; per MVP blocchiamo la riduzione di `stint_target_laps` e permettiamo solo aumento finché è compatibile con il fuel corrente.

## 6c) SocketIO payload (race_update) – campi aggiuntivi per UI MVP
Obiettivo: la UI deve poter mostrare e controllare le 2 auto del player senza query extra.

Per ogni auto in `cars[]` aggiungere (oltre ai campi già presenti):
- `is_player_controlled` (bool)
- `fuel_percent` (1..100)
- `pace_level` (1..10)
- `ice_mode` (Save/Standard/Push)
- `ers_mode` (Harvest/Neutral/Deploy/Overtake)
- `setup_feedback` (opzionale):
  - `cornering_balance`: `{ color, message }`
  - `straight_line_speed`: `{ color, message }`
  - `traction`: `{ color, message }`
  - `stability`: `{ color, message }`

## 7) UI minima
- Pannello team con due card (Auto 1 / Auto 2) contenenti:
  - stato (BOX/OUT_LAP/HOT_LAP/IN_LAP)
  - gomme attuali + wear
  - fuel (percentuale 1–100)
  - passo (push/normal/save)
  - ICE mode
  - ERS mode
  - bottoni: “Send out”, “Box”, selettore gomme, slider fuel %, giri stint target

## 8) Criteri di successo MVP
- Il giocatore riesce a:
  - far uscire una singola auto con gomme e fuel scelti
  - vedere differenze di tempi/consumi/usura cambiando passo
  - richiamare l’auto ai box e farla rientrare
  - ripetere un run

## 9) Domande aperte (per finalizzare prima di implementare)
- Vuoi che il passo impatti:
  - solo il tempo sul giro
  - oppure anche consumo fuel e usura gomme (consigliato)
