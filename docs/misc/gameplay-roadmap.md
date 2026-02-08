# Gameplay Roadmap (Tech-focused F1 Manager)
Questa roadmap consolida la visione di gioco (racing_engine + gestione team) mantenendo il focus su scelte tecniche e simulazione credibile, con economia semplificata.

## 0) Principi guida
- Focus: **tecnica e performance** (setup, sviluppo auto, strategia)
- Economia: **semplice**, non deve diventare il “gioco nel gioco”
- UI/terminologia in-game: **inglese**

Nota architetturale (per partire veloce):
- Comandi del giocatore via **REST (POST)**.
- Aggiornamenti realtime stato auto/sessione via **SocketIO**.
- Nel MVP Practice iniziale, le auto non-player restano ferme usando un flag `is_player_controlled` e skip della simulazione.

## 1) Racing Engine (schermata in cui girano le auto) – macro-feature
### 1.1 Setup search + driver feedback (Practice)
- Obiettivo: introdurre il loop “try setup → run → feedback pilota → adjust”.
- Comandi base già previsti: tyres, fuel %, pace (1–10), ICE map, ERS map, stint target laps, Send out, Box.
- Feedback al rientro:
  - messaggi in inglese del tipo:
    - “Front end is weak in high-speed corners”
    - “Rear is unstable under braking”
    - “Too much drag on straights”
  - indicatori **visivi a colori** (no numeri) per guidare il giocatore senza precisione “da spreadsheet”:
    - `Red` = wrong direction
    - `Orange` = bad
    - `Yellow` = acceptable
    - `Green` = good
    - `Fuchsia` = near perfect
- Categorie feedback (MVP):
  - `Cornering balance` (Understeer/Oversteer)
  - `Straight-line speed` (Drag)
  - `Traction` (slow corners / exits)
  - `Stability` (braking)
- Timing:
  - feedback **sempre** quando l’auto rientra ai box
  - feedback **live** durante il run è opzionale e dipende dalla skill del pilota `Pilota.ricerca_assetto`
- Collegamento col doc fisica: usa concetti di bilanciamento aero/drag e (in futuro) ride height/suspension.

### 1.2 AI cars on track (traffic + baseline competitors)
- Obiettivo: mettere in pista le altre auto, anche in Practice.
- Ogni AI team gestisce:
  - run plan (stint target laps)
  - scelta gomme
  - pace e mappe
  - (più avanti) ricerca setup

Prima iterazione:
- AI **semplice** (preset + un po’ di rumore), poi aumentiamo complessità.

### 1.3 Overtakes / traffic / blocking + time loss
- Obiettivo: simulare interazione tra auto:
  - sorpassi
  - blocchi (auto più lenta davanti)
  - perdita di tempo (delta sul settore/giro)
- Nota: feature fondamentale per rendere credibile qualifica/gara (aria sporca, traffico, ecc.).

Prima iterazione:
- modello **semplice** (probabilistico + delta time), poi aumentiamo complessità.

### 1.4 Weekend flow (FP → Quali → Race)
- Obiettivo: introdurre la progressione del weekend:
  - Practice: setup search
  - Quali: performance peak, traffico, gestione ERS
  - Race: strategia (stints, pit windows, tyre deg, fuel, traffic)
- Impostazione strategia: almeno “piano base” prima della gara (pit window e compound).

Sequenza di rilascio:
- Per ora si parte con **selezione singolo GP** → Practice.
- Weekend completo (FP/Quali/Race) è lo step successivo.
- Calendario, mondiale e classifiche arrivano dopo (non in questa fase).

## 2) Team Management (fuori dal weekend)
### 2.1 Car development (focus principale)
- Sviluppo componenti singole: wings, floor, bodywork, engine/PU.
- Doppio orizzonte:
  - anno corrente
  - anno successivo
- Output gameplay atteso:
  - cambiamento dei parametri auto (aero, PU, tyre deg) percepibile in pista.

### 2.2 Staff market
- Acquisto/vendita personale:
  - engineers
  - drivers
- Effetti: sviluppo più rapido/migliore, feedback setup più accurato, strategia migliore (in futuro).

### 2.3 Engine supply
- Per team customer: acquisto motori/PU.
- Effetti: potenza/affidabilità/costi (economia semplificata).

### 2.4 Facilities
- Strutture team: CFD, wind tunnel, factory, simulatore.
- Effetti: velocità sviluppo, qualità upgrade, affidabilità.

## 3) Sequenza milestone suggerita (dopo MVP Practice)
1. **MVP Practice (solo player cars)**
   - comandi + stint loop + fuel/tyre wear/fuel burn + pace/ICE/ERS
2. **AI cars in Practice (traffic baseline)**
   - far girare le altre auto con run plan semplice
3. **Traffic & overtakes/time loss**
   - modello semplice: “car ahead within X → speed cap/delta time”
4. **Driver feedback + setup search loop**
   - feedback testuale + “setup score” per circuito
5. **Qualifying mini-flow**
   - sessione corta, attenzione traffico, ERS peak
6. **Race mini-flow**
   - strategia pit + degrado + traffic
7. **Meta management layer (R&D + staff + facilities)**

## 4) Domande aperte per chiudere specifiche
- Feedback setup: lo vuoi come:
  - A) testo + suggerimento direzione (more front wing / less rear wing)
  - B) punteggi (understeer/oversteer/drag) + testo
- AI setup search: vuoi che l’AI “ottimizzi” davvero o che usi preset/rumore?
- Overtake model: preferisci:
  - A) sistema probabilistico (pass/fail) + delta time
  - B) micro-simulazione su segmenti (più realistica)
- Weekend: vuoi un calendario completo o iniziamo con 1 solo GP selezionabile?
- Economia semplificata: vuoi un budget fisso per stagione o progressione per risultati?
