---
title: Practice Session Orchestrator
version: 0.2
last_updated: 2026-02-10
scope: "Coordinare FP1/FP2/FP3 con 18 AI + 2 player, integrando Setup Engine e LapSimulator"
---

## 1. Obiettivo
Coordinare un’intera sessione di Practice (FP1/FP2/FP3) gestendo simultaneamente 18 vetture AI e fino a 2 player. L’orchestratore deve:
- mantenere il cronometro ufficiale e lo stato sessione (bandiere, meteo, disponibilità pitlane);
- schedulare i run programmati (fuel, tyre set, mappe ICE/ERS) rispettando cooldown e queue box;
- sincronizzarsi con SetupEngineService e LapSimulator per applicare setup e far girare le auto;
- persistere dati/telemetria per UI, feedback ingegnere e QA harness;
- **generare un piano lavoro per squadra a inizio sessione** con ordine di uscita randomizzato.

## 2. Stato sessione & timeline
### 2.1 Cronometro ufficiale
- Timer base 60 minuti (FP1/FP2/FP3) con tick a 1 s.
- Supporta `resume`, `pause`, `fast_forward(×2/×4/×6)` per QA/manual testing.
- Tiene traccia del tempo trascorso/rimanente e invalida run se il timebox termina.
### 2.2 Slot pitlane e bandiere
- Pitlane con slot limitati: massimo 2 auto per team (1 per player). Queue gestita secondo priorità (player > AI run critico > AI standard).
- Eventi bandiera (gialla/rossa) limitano l’uscita o forzano rientro. In caso di rossa il timer continua ma run vengono marcati `aborted_by_flag`.
- Meteo dinamico (quando attivo) aggiorna grip e limita i programmi (es. Quali Sim sospesa se piove troppo).
### 2.3 Pause / fast-forward
- Pausa manuale da UI ingegnere blocca solo l’auto player; AI continua (come broadcast reale). Modalità debug permette freeze totale.
- Fast-forward disabilitato durante eventi critici (bandiere, incidenti) per non perdere log/telemetria.

## 3. Scheduling run
### 3.1 Input programma (AI/Player)
- Player: definisce manualmente run (compound, fuel, mappe) via UI; l’orchestratore valida disponibilità set/fuel e registra il run, **consultando le regole di allocazione gomme del weekend** (doc dedicato).
- AI: utilizza il programma definito nella spec AI Driver (Setup Validation, Tyre Deg, Quali Sim, Race Trim, R&D). Ogni entry è un `PracticeRunPlan` con `start_window`, `laps_planned`, `objective`, `priority` e rispetta i vincoli del documento gomme.
### 3.2 Cooldown e queue pitlane
- Cooldown minimo 120 s tra run con modifiche setup/fuel/tyre. L’orchestratore mantiene `next_slot_time` per ogni auto per evitare violazioni.
- Queue pitlane: se più auto vogliono uscire nello stesso tick, vengono ordinate per priorità e ritardate di 5‑10 s per simulare traffico reale.
### 3.3 Gestione gomme/fuel
- Tyre allocation per sessione: numero di set per compound definito dal regolamento. Ogni run consuma un set (flag `reused` se riutilizzato con penalty grip).
- Fuel load espresso in kg e convertito in litri. Rifornimenti conteggiati nel pit turnaround.
- L’orchestratore aggiorna l’inventario set/fuel per ogni team e blocca run impossibili.

### 3.4 Piano lavoro squadra (Team Session Plan)

> **PRINCIPIO**: ogni sessione deve essere diversa dalla precedente.
> Il giocatore non deve poter prevedere chi esce per primo o quando.

All'inizio di ogni sessione, il `SessionBridge` genera un **Team Session Plan** per ogni squadra AI. Il piano definisce:

1. **Programmi run**: lista ordinata dei run da completare (da `SESSION_PROGRAMS` in `ai_data_types.py`)
   - FP1: 2× SetupValidation
   - FP2: TyreDeg + QualiSim + RaceTrim
   - FP3: QualiSim + SetupValidation
2. **Finestra di uscita** (`first_exit_window_s`): tempo simulato in cui la squadra inizia il primo run
   - Range: **30s – 300s** (da 30 secondi a 5 minuti dall'inizio sessione)
   - Generato con `random.uniform()` per ogni squadra, diverso ad ogni sessione
   - Squadre top tendono ad uscire prima (range 30–180s), backmarker più tardi (60–300s)
3. **Gap tra run** (`inter_run_gap_s`): pausa tra la fine di un run e l'inizio del successivo
   - Range: **120s – 360s** (2–6 minuti)
   - Include pit work + analisi dati + modifiche setup
4. **Ordine piloti nel team**: chi esce per primo tra i due piloti
   - Randomizzato: 50/50 per ogni run
   - Gap tra i due piloti dello stesso team: **5s – 20s**

```python
@dataclass
class TeamSessionPlan:
    team_id: str
    first_exit_window_s: float    # quando inizia il primo run (30-300s)
    inter_run_gap_s: float        # pausa tra run (120-360s)
    pilot_order: List[str]        # ordine piloti per il primo run (randomizzato)
    run_schedule: List[dict]      # [{car_id, program, planned_start_s}, ...]
```

Esempio per una sessione FP1 con 10 team:

| Team | first_exit | Pilota 1 esce a | Pilota 2 esce a |
|---|---|---|---|
| Ferrari | 45s | 45s | 57s |
| Red Bull | 152s | 152s | 163s |
| McLaren | 78s | 78s | 91s |
| Mercedes | 210s | 210s | 225s |
| ... | ... | ... | ... |

Ogni sessione i valori sono diversi → il giocatore vede un ordine di uscita sempre nuovo.

### 3.5 Uscita scaglionata (Staggered Pit Exit)

Quando più auto devono uscire nello stesso intervallo di tempo:

1. **Stagger per squadra**: ogni squadra ha il suo `first_exit_window_s` randomico
2. **Stagger intra-team**: i due piloti della stessa squadra escono con 5–20s di gap
3. **Stagger anti-collisione**: se due auto di squadre diverse hanno finestre sovrapposte (< 5s), la seconda viene ritardata di 5–8s
4. **Pit exit delay**: dopo che il PSO rilascia l'auto (PIT_QUEUE → ON_TRACK), c'è un delay fisico di uscita dalla pitlane (simulato dal `pit_exit_delay_s` nel `CarTrackState`)

Questo garantisce che:
- Le auto **non escono mai tutte insieme**
- L'ordine di uscita è **diverso ad ogni sessione**
- Le squadre top non escono sempre per prime
- Non ci sono "treni" di 5+ auto sovrapposte in pista

## 4. Persistenza e telemetria
### 4.1 Run log & setup history
- Ogni run produce `PracticeRunRecord` con team, pilota, programma, start/stop time, tyre/fuel, delta setup, outcome (success/abort/partial) e note (traffico, bandiere, meteo).
- Mantiene `setup_history` per auto, con snapshot slider (valori fisici) ad ogni rientro per audit/parc fermé.
### 4.2 Export per UI/QA
- API per UI engineer con paginazione dei run (per mostrare cronologia, feedback, tempi).
- QA harness può scaricare JSON/CSV con timeline, lap times e eventi (per test deterministici).

## 5. Integrazione con LapSimulator & servizi
### 5.1 API / eventi
- `SetupEngineService.apply_setup(car_id, setup_payload)` chiamato prima di ogni run (player/AI) per applicare slider → fisica.
- `update_section()` chiamato sezione per sezione nel tick loop (vedi `race-engine-integration-spec.md §2`).
- Eventi su EventBus (futuro): `practice_run_started`, `practice_run_finished`, `practice_run_aborted`, `flag_changed`, `weather_changed`.
### 5.2 Diagramma di sequenza (aggiornato)
```
SessionBridge.init_session()
  → genera TeamSessionPlan per ogni squadra (randomizzato)
  → registra team nel PSO
  → crea AIDriverEngine per ogni pilota AI

SessionBridge.tick(sim_dt)
  → FASE 1: check TeamSessionPlan → schedule run quando è il momento
  → PSO.tick() → rilascia auto da PIT_QUEUE → ON_TRACK
  → FASE 2: move cars (per-section, update_section)
  → FASE 3: separation / battle
  → FASE 4: state commit → RaceCar → socket → frontend
```

## 6. Eventi & notifiche
- Verso UI engineer/player:
  - `RUN_START` (programma, compound, fuel, obiettivo)
  - `RUN_END` (miglior tempo, deg, feedback setup)
  - `RUN_ABORT` (motivo: flag, incidente, traffico, meteo)
  - `SETUP_CHANGE` (slider modificati, ragione feedback)
  - `TYRE_INVENTORY_UPDATE`
- Verso QA/telemetria: `time_pause`, `fast_forward`, `bandiera`, `weather_update`.

## 7. Dipendenze e futuri estensibili
- Dipendenze: AI Driver Engine spec, SetupEngineService, LapSimulator, Tyre allocation doc.
- Futuro: orchestratore weekend (FP→Quali→Race), meteo dinamico avanzato, run R&D dettagliati, interfaccia con Race Strategist AI e parc fermé cross-sessione.

---

## 8. Stato implementazione (aggiornato 2026-02-10)

| Feature | Stato | Note |
|---|---|---|
| Cronometro ufficiale (§2.1) | ✅ | `PSO.clock`, tick con sim_dt |
| Pitlane queue (§2.2) | 🟡 | Queue funziona, bandiere non attive |
| Pause/fast-forward (§2.3) | 🟡 | Pausa globale (non selettiva), speed 1×/5×/15×/30× |
| Input programma AI (§3.1) | ✅ | `AIDriverEngine.start_session()` genera `SessionPlan` |
| Cooldown tra run (§3.2) | ⬜ | Solo `pit_work_duration_s` base |
| Tyre inventory (§3.3) | ✅ | Allocazione per team, consumo set |
| **Team Session Plan (§3.4)** | ⬜ | **Da implementare** — scheduling fisso ogni 30s |
| **Staggered exit (§3.5)** | 🟡 | Stagger per indice (3+5×i), non randomico per squadra |
| Run log (§4.1) | ✅ | `PracticeRunRecord` nel PSO |
| Export API (§4.2) | ⬜ | |
| SetupEngine integration (§5.1) | ⬜ | |
| EventBus (§5.1) | ⬜ | |
| Eventi UI (§6) | ⬜ | |
