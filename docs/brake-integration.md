---
Title: Brake Integration – Runtime & UI decisions
Date: 2026-02-18
---

## 1. Dock chip (pilot cooling hints)
- **Scope**: Pilot dock nel Garage V3 → area chip (fuel, tyres, ERS) con nuovo blocco "Brake cooling".
- **Dati**: payload socket `driver_dock.brake_cooling.{front|rear}` con apertura attuale, target range e stato.
- **Rendering**: pillole duali (Front/Rear) con colore verde/giallo/rosso (verde dentro target, giallo ±2%, rosso fuori range). Tooltip mostra "Target 32–42%".
- **Warning hook**: se arriva evento `brake_hot_section` o `brake_duct_low/high` riferito all'asse corrispondente, la pill sfarfalla per 2-3 s.

## 2. HUD warning (live feedback)
- **Trigger**: eventi runtime `brake_hot_section`, `brake_duct_low/high`, `regen_limit`.
- **Canale UI**: Practice HUD banner (già usato per blue/yellow flag) + toast stack lato destro.
- **Messaggi**: English-only, sintetici (es. "Front brakes near critical temp – Turn 1", "Ducts too closed for Sector 2").
- **Priorità**: `brake_hot_section` > `regen_limit` > `duct_low/high`. Garantire debounce (≥8 s tra due messaggi uguali per stesso pilota).
- **Telemetria**: loggare su timeline sessione per replay (append a `brake_alerts` array inviato al frontend ogni 5s).

## 3. Garage Telemetry panel (post-run analysis)
- **Posizionamento**: Tab Telemetry → nuova card "Brake insights" sotto chart della temperatura gomme.
- **Contenuti**:
  - Mini sparkline temp front/rear con overlay soglie fade (linee orizzontali).
  - Lista critical sections (top 5 per energia) con badge "OK / Warm / HOT" basato sull'evento più recente.
  - Tabella torque split: per ogni macro settore, % regen vs idraulico media (calcolata dai nuovi segnali runtime).
- **Interazione**: click su sezione apre highlight nella mappa sezione (riutilizziamo highlight usato per ERS priority).
- **Backend**: nuovo endpoint `/api/brake-insights/<session_id>/<car_id>` che restituisce:
  ```json
  {
    "temps": {"front": [...], "rear": [...]},
    "critical_sections": [
      {"id": "T1", "status": "hot", "last_msg": "Front brakes near critical temp"}
    ],
    "torque_split": {
      "sector1": {"regen_pct": 0.42, "hydraulic_pct": 0.58}
    }
  }
  ```
- **Refresh**: live durante run (socket) e disponibile on-demand quando la vettura rientra in garage.
