# Racing Engine UI Mockup (MVP Practice)
Questo mockup propone una nuova interfaccia per la schermata "racing engine" focalizzata sulle 2 auto del giocatore (Practice), con controlli e feedback chiari.

Nota: testi e label in-game **in inglese**.

---

## Layout (desktop)

```
+-----------------------------------------------------------------------------------+
| Top Bar                                                                           |
| [GP: Monza]  [Session: Practice]  [Time Left: 42:18]  [Speed: 1x/2x/4x/6x] [Pause]|
+-----------------------------------------------------------------------------------+
| Track View + Timing Table (center/left)               | Right Sidebar (controls) |
|                                                       |                            |
|  (simple track map + dots)                            |  PLAYER TEAM              |
|                                                       |  Team: Ferrari (ID 3)     |
|                                                       |                            |
|  - cars (all) shown as small dots                     |  CAR #16  Charles Leclerc |
|    - player cars: highlighted                         |  State: BOX / OUT / HOT   |
|    - AI cars: greyed (MVP: stationary)                |  Tyre: SOFT/MED/HARD      |
|                                                       |  Fuel: [ 75% ] (locked*)  |
|                                                       |  Pace: [1..10 slider]     |
|                                                       |  ICE: Save/Standard/Push  |
|                                                       |  ERS: Harvest/Neutral/... |
|                                                       |  Stint: [ 6 ] laps        |
|                                                       |  [Send out]  [Box]        |
|                                                       |                            |
|                                                       |  Setup Feedback (colors)  |
|                                                       |  Balance:  [Green]  text  |
|                                                       |  Drag:     [Yellow] text  |
|                                                       |  Traction: [Orange] text  |
|                                                       |  Stability:[Green]  text  |
|                                                       |                            |
|                                                       |  Messages (Radio)         |
|                                                       |  - (live optional)        |
|                                                       |  - (always on box)        |
|                                                       |                            |
|                                                       |  CAR #55  Carlos Sainz    |
|                                                       |  (same block as above)    |
|-----------------------------------------------------------------------------------|
| Timing Table (leaderboard)                                                       |
|  Pos | Driver | Team | Lap | Last | Best | S1 | S2 | S3 | Tyre | Age | Fuel | Gap |
|  1   | LEC    | FER  |  6  |1:21.3|1:20.9|...|...|...| SOFT |  4  | 63%  |  -- |
|  2   | SAI    | FER  |  6  |1:21.7|1:21.2|...|...|...| SOFT |  4  | 61%  |+0.3 |
|  ... (AI rows optional/greyed in MVP)                                             |
|  [Filter: All / Player]  [Sort: Best / Last]  [Compact]                           |
+-----------------------------------------------------------------------------------+
| Bottom Panel (telemetry & timing)                                                  |
|  Last Lap: 1:21.345  Best Lap: 1:20.912  Sector: S1 26.8 | S2 31.2 | S3 22.9      |
|  Tyre Wear: 12%     Tyre Age: 4 laps    Fuel: 63%        Stint: 2/6 laps           |
+-----------------------------------------------------------------------------------+
```

### Note UI
- **Track View**: per MVP basta la mappa circuito + posizione auto; no bisogno di grafici complessi.
- **Timing Table**: tabella tempi stile "timing screen" sempre visibile sotto la track view.
  - In MVP, se le AI sono ferme, possiamo:
    - mostrare solo le 2 auto player (filtro default `Player`), oppure
    - mostrare tutte le auto ma con righe AI “greyed”.
- **Right Sidebar**: focus sulle 2 auto player; ogni auto ha un "control card".
- **Bottom Panel**: tempi giro/settori e stato stint (fuel/tyre) per immediatezza.

### Comportamento responsive/UX
- La **Timing Table** può essere:
  - collassabile (toggle "Timing")
  - modalità "Compact" per lasciare più spazio alla track view.
- Se lo schermo è piccolo, la tabella può spostarsi in un tab laterale (ma per desktop resta sotto track).

---

## Stati e lock UI (MVP)
- Quando `State != BOX` (OUT_LAP/HOT_LAP/IN_LAP):
  - `Tyre` disabled
  - `Fuel` disabled
  - `Stint laps` può solo aumentare (fino al max da fuel)
  - `Pace`, `ICE`, `ERS` enabled
  - `Box` enabled
- Quando `State == BOX`:
  - tutto configurabile

---

## Setup Feedback (no numbers)
Per ogni categoria:
- Color chip: `Red | Orange | Yellow | Green | Fuchsia`
- Short text (English), es:
  - Balance: "Understeer in slow corners"
  - Drag: "Too much drag on straights"
  - Traction: "Poor traction on exit"
  - Stability: "Unstable under braking"

### Live feedback
- appare come "Radio" message solo a volte, in base a `Pilota.ricerca_assetto`.

---

## REST controls mapping (summary)
- `Send out` → `POST /api/player/car/<driver_number>/send_out`
- `Box` → `POST /api/player/car/<driver_number>/box`
- ogni change su slider/select (quando consentito) → `POST /api/player/car/<driver_number>/configure`

---

## Minimal landing flow
1. Circuit selection screen (existing) → user selects GP/track.
2. Race screen opens (`/race`) and shows:
   - team selection dropdown/modal (numeric IDs)
   - once selected, shows the 2 car control cards.
