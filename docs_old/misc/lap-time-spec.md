# Specifica Calcolo Tempo sul Giro

## 1. Obiettivo
Definire il modello deterministico/procedurale utilizzato per simulare il tempo sul giro in F1 Manager AI a partire da quattro fattori principali:

1. **Auto (Team/Car Strength)**
2. **Pilota (Driver Skill)**
3. **Gomme (Tire Compound + Degrado)**
4. **Condizioni Pista (placeholder futuro: meteo, grip, ecc.)

La versione attuale implementa i primi tre fattori con pesi combinati secondo la regola 60/30/10.

## 2. Modello dati

### 2.1 Pilota (`models.Pilota`)
- Attributi anagrafici completi (nome, cognome, nazionalità, numero di gara, ecc.)
- Skill clampate 1–100 tramite `MathUtils.clamp`:
  - Velocità, Consumo gomme, Qualifica (vincolata a ±10 rispetto a Velocità), Sorpasso, Aggressività, Ricerca assetto, Stile sottosterzo/sovrasterzo, Costanza, Gara, Gestione carburante.
- `abbreviazione` derivata da lookup FIA o fallback iniziali.

#### Skill bonus pilota
```
skill_score = 0.4 * Velocità + 0.3 * Gara + 0.2 * Qualifica + 0.1 * GestioneCarburante
pilot_bonus_seconds = skill_score * PILOT_COEFF   # es. 0.05 s/pt
pilot_contribution = pilot_bonus_seconds * 0.10   # peso 10%
```

### 2.2 Gomma (`models.Gomma`)
- Mescole supportate: Soft, Medium, Hard.
- `percentuale_vita` (0–1) aggiornata da `aggiorna_degrado()` con valori base (Soft 0.08, Medium 0.05, Hard 0.03).
- Bonus/Malus lap time tramite `impatto_su_laptime()`:
  - Grip ≥ 0.9 → bonus pieno: `-BONUS_LAP_TIME[mescola]` (Soft −1.5s, Medium −0.7s, Hard −0.2s).
  - 0.9 > grip ≥ 0.5 → bonus lineare: `(grip - 0.5) / 0.4`.
  - Grip < 0.5 → malus: `(0.5 - grip) * MALUS_COEFF[mescola]` (Soft 2.2, Medium 1.8, Hard 1.4).
- Uso nel modello: `tire_contribution = gomma.impatto_su_laptime() * 0.30` (peso 30%).

### 2.3 Circuiti (`config.circuit_info.json`)
- Ogni circuito dispone di un profilo JSON (generato via `scripts/build_circuit_info.py`) con:
  - `base_lap_seconds`: tempo di riferimento reale (es. Suzuka 88.197s, Monza 79.662s).
  - `sector_times`: tempi medi dei tre settori per ricostruire la geometria.
  - Parametri di superficie (grip, bumpiness) usati per futuri moltiplicatori.
- Il backend carica il profilo del circuito corrente tramite `config.set_current_circuit` e lo espone con `config.get_current_circuit_profile()`.
- La funzione `_current_base_lap_time()` in `utils.performance` legge sempre `base_lap_seconds`; il fallback 80.0s è usato solo se manca il profilo.

### 2.4 Team (`models.Team`)
- Campi principali: nome, sigla, nazionalità, colore, power unit, `forza_auto` (0–100) e lista di piloti.
- `bonus_prestazione = forza_auto * 0.1`.
- Contributo nel lap time: `car_contribution = bonus_prestazione * 0.60`.
- Dataset 2025 in `python_backend/data/teams/__init__.py`:
  - McLaren 95, Red Bull 91, Ferrari 87, Mercedes 85, Aston Martin 82, Alpine 79, RB 77, Williams 76, Sauber 73, Haas 71.

### 2.5 Associazione RaceCar
Ogni `RaceCar` deve riferirsi a:
- `team` (per colore, forza e power unit)
- `pilota` (per skill bonus e dati UI)
- `gomma_corrente` (`Gomma` con percentuale di vita dinamica)

## 3. Formula Lap Time
Per ogni giro (o settore) il tempo simulato deriva da:

```
LapTime = base_lap_seconds(circuito)
          - car_contribution      # 60%
          - pilot_contribution    # 10%
          + tire_contribution     # 30% (può essere negativo o positivo)
          + altri fattori (futuro: meteo, traffico, errori)
```

- **Tempo base**: letto da `config.get_current_circuit_profile()['base_lap_seconds']` (es. Suzuka 88.197 s). Solo in assenza del profilo si usa il fallback 80.0 s.
- **Car contribution**: `0.6 * team.bonus_prestazione` (es. forza 95 ⇒ 0.6 * 9.5 = 5.7 s sottratti).
- **Pilot contribution**: `0.1 * (skill_score * coeff)`.
- **Tire contribution**: `0.3 * gomma.impatto_su_laptime()`.
- Quando la gomma scende sotto il 50% il termine diventa malus positivo.

## 4. Aggiornamento in tempo reale
- Il motore (`simulation.update_car_position`) deve calcolare velocità/tempi ogni tick tenendo conto dei coefficienti correnti.
- Variazioni runtime (cambio passo pilota, engine mode, gomma nuova, degrado, penalità) aggiornano direttamente `team`, `pilota` o `gomma` e influenzano solo il tratto restante del giro.
- Lap time parziale = somma dei settori: ogni settore usa i coefficienti “instantanei”.

## 5. Integrazione prevista
1. **Setup RaceCar**: associare all’inizializzazione i dati da `TEAMS` e `PILOTS` (colore, forza, skill, gomma iniziale).
2. **Loop simulazione**: applicare la formula ad ogni settore/giro, aggiornando `gomma.percentuale_vita` e registrando bonus/malus.
3. **Telemetria**: esporre a frontend pilota, forza, gomma (percentuale), stato per UI.
4. **Test**: validare scenari (gomma 100% vs 40%, auto forte vs debole) per verificare i delta desiderati (es. Medium nuova vs 40% ⇒ +0.6s).

## 6. Estensioni future
- Condizioni pista (meteo, evoluzione grip) ⇒ fattore aggiuntivo.
- ERS/DRS & engine modes ⇒ ulteriori pesi dinamici.
- Traffico e incidenti (dirty air, errori random).
- Temperature gomme, finestre operative, crossover intermedie/wet.

Questo documento funge da riferimento ufficiale per l’implementazione del nuovo motore di calcolo tempi sul giro nel branch `feature/lap-time-model`.

## 7. Telemetria di debug (opzionale)
- Il logging JSONL dei giri (`python_backend/telemetry/lap_debug.jsonl`) è controllato dalla variabile d’ambiente `LAP_DEBUG_ENABLED`.
- Per abilitare la telemetria: `LAP_DEBUG_ENABLED=1 python python_backend/f1_manager_ai.py` (o configurazione equivalente in Electron).
- Con il flag disattivo (default) il file non viene creato né scritto, evitando overhead.
