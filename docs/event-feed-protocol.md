---
title: Protocollo Socket.IO – Eventi Telemetria & HUD
version: 0.1
last_updated: 2026-02-14
scope: "Definire schema JSON per eventi in-game (AI runs, battaglie, notifiche) via Socket.IO. Supporta barra notifiche + HUD overlay."
---

# 1. Overview
Il protocollo definisce eventi emessi dal backend (SessionBridge/BattleResolver) al frontend via Socket.IO. Gli eventi sono divisi in categorie: AI Practice Runs (da AI Driver Engine), Battle Events (da BattleResolver), Notifications (generali).

**Canali Socket**:
- `race_update`: payload principale per aggiornamenti sessione (auto, timing, banner).
- `event_feed`: canale dedicato per eventi telemetria/HUD (nuovo).

**UI Targets**:
- **Barra notifiche**: messaggi temporanei (3-5s) per player car (es. "Run completato – best: 1:47.2").
- **HUD overlay**: banner in alto-destra per eventi critici/globali (es. "Collision: VER vs HAM in sec_05").
- **Timeline race view**: accumulo eventi per riepilogo post-sessione.

# 2. Schema generale evento
Ogni messaggio su `event_feed` ha struttura:

```json
{
  "event_type": "string",  // Es. "ai_run_completed", "battle_overtake"
  "timestamp": "ISO8601",  // UTC timestamp emissione
  "session_id": "string",  // FP1, FP2, etc.
  "car_id": "string",      // ID auto coinvolta (es. "1" per VER)
  "team_name": "string",   // Nome team (es. "Oracle Red Bull Racing")
  "driver_name": "string", // Nome pilota (es. "Max Verstappen")
  "payload": {             // Dati specifici evento (vedi sotto)
    // ...
  },
  "ui_targets": ["string"] // ["notification_bar", "hud_overlay", "timeline"]
}
```

# 3. Eventi AI Practice Runs (da AI Driver Engine)
Estendono quelli in `docs/ai-driver-engine-spec.md §7`.

## 3.1 ai_run_started
Emetto quando un AI inizia un run programmato.

**Payload**:
```json
{
  "program": "SetupValidation",  // Codice programma (vedi ai-driver-engine-spec)
  "laps_planned": 5,
  "fuel_load": 25,  // kg
  "compound": "SOFT",
  "engine_map": "Balanced",
  "ers_mode": "Attack"
}
```

**UI**: Barra notifiche (solo se car_id == player_car), timeline.

**Esempio messaggio UI**: "Starting Setup Validation (5 laps)"

## 3.2 ai_run_completed
Emetto al termine run AI (success/partial/abort).

**Payload**:
```json
{
  "outcome": "success",  // "success", "partial", "aborted"
  "reason": null,        // Se aborted: "traffic", "red_flag", "collision"
  "laps_done": 5,
  "best_lap_s": 107.234,
  "delta_setup": {       // Slider cambiati (se refinement)
    "front_wing": 1.5,
    "rear_wing": -2.0
  }
}
```

**UI**: Barra notifiche (player car), timeline.

**Esempio messaggio UI**: "Run complete – best: 1:47.2"

## 3.3 ai_setup_adjustment
Emetto dopo pit work setup (solo se cambi effettuati).

**Payload**:
```json
{
  "changes": {
    "front_wing": 1.5,
    "suspension_front": -1.0
  },
  "reason": "Refinement after run 3"
}
```

**UI**: Barra notifiche (player car), HUD overlay (se vicino al player).

**Esempio messaggio UI**: "Setup adjusted: Front Wing +1.5, Susp Front -1.0"

## 3.4 ai_setup_converged
Emetto quando AI raggiunge soglia setup OK.

**Payload**:
```json
{
  "threshold_reached": true,
  "final_score": 8.45
}
```

**UI**: Barra notifiche (high priority), HUD overlay.

**Esempio messaggio UI**: "Setup OK – all targets in range"

# 4. Eventi Battle (da BattleResolver)
Nuovi, per sorpassi/collisioni. Emetto solo se coinvolgono auto vicine al player (distanza <50m) o il player stesso.

## 4.1 battle_overtake
Sorpasso riuscito.

**Payload**:
```json
{
  "overtaken_car_id": "44",     // Auto sorpassata
  "overtaken_driver": "Lewis Hamilton",
  "section": "sec_07",          // Sezione pista
  "overtake_type": "straight"   // "straight", "corner", "corner_exit"
}
```

**UI**: HUD overlay, timeline.

**Esempio messaggio UI**: "HAM overtaken by VER in sec_07"

## 4.2 battle_blocked
Tentativo sorpasso bloccato.

**Payload**:
```json
{
  "blocked_by_car_id": "44",
  "blocked_driver": "Lewis Hamilton",
  "section": "sec_05",
  "reason": "defensive_driving"
}
```

**UI**: HUD overlay (giallo), barra notifiche (se player coinvolto).

**Esempio messaggio UI**: "Overtake attempt blocked by HAM in sec_05"

## 4.3 battle_collision
Collisione (da BattleResolver.resolve_pair).

**Payload**:
```json
{
  "collided_with_car_id": "44",
  "collided_driver": "Lewis Hamilton",
  "section": "sec_04",
  "damage_level": "minor",  // "minor", "major", "severe"
  "yellow_flag_triggered": true
}
```

**UI**: HUD overlay (rosso, lampeggiante), barra notifiche (high priority).

**Esempio messaggio UI**: "Collision: VER vs HAM in sec_04 – Yellow flag"

## 4.4 battle_side_by_side
Battaglia side-by-side (da BattleResolver).

**Payload**:
```json
{
  "opponent_car_id": "44",
  "opponent_driver": "Lewis Hamilton",
  "section": "sec_12",
  "duration_s": 5.2  // Durata battaglia
}
```

**UI**: HUD overlay, timeline.

**Esempio messaggio UI**: "Side-by-side battle with HAM in sec_12"

# 5. Implementazione backend
- **SessionBridge**: emette eventi AI su `event_feed` durante `_complete_car_run`.
- **BattleResolver**: emette eventi battle su `event_feed` in `resolve_section` (solo se rilevanti per player).
- **Filtro player**: eventi battle solo se `car_id` o `opponent_car_id` è player, o distanza <50m.

# 6. Implementazione frontend
- Ascolta `event_feed` in `socket_bridge.js`.
- **Barra notifiche**: mostra messaggi temporanei con priorità (normal/low/high).
- **HUD overlay**: div in alto-destra, animato in/out, colore basato evento (rosso collision, giallo blocked).
- **Timeline**: accumula eventi in array, mostra in pannello race view post-sessione.

# 7. Test & QA
- **Unit test**: emettere eventi mock su channel `event_feed`.
- **Integration test**: simula sessione con battaglie, verifica payload ricevuti.
- **UI test**: conferma visualizzazione barra/HUD/timeline senza crash.

# 8. Dipendenze
- Completato: BattleResolver 2.0, AI Driver Engine.
- Prossimo: implementare serializzazione in SessionBridge, widget FE in `player_garage_v3.js`.
