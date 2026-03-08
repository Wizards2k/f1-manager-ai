---
title: AI Driver & Team Behavior – Practice Sessions
version: 0.2
last_updated: 2026-02-10
scope: "Definire logica e requisiti per le 18 auto AI durante le sessioni practice (setup search, run plan, strategia box)"
---

## 1. Obiettivo
Garantire che le vetture non controllate dal giocatore gestiscano autonomamente l’intera sessione di Practice: dalla pianificazione dei run (fuel load, compound, ERS map) alla raccolta dati setup, passando per traffico, box timing e feedback ingegnere. L’AI deve comportarsi in modo credibile, reagire alle condizioni pista/meteo e produrre log/eventi utili per UI e QA.

## 2. Seed iniziale del setup

- **Team.SimulationEfficiency (0‑100)**: esprime la qualità del reparto simulatore. Influenza il delta iniziale rispetto al setup ideale. Valori alti = assetto di base già vicino ai target.
- **Driver.SimAffinity (0‑100)**: quanto il pilota riesce a trasferire il lavoro del sim e affinare l’assetto in pista. Piloti “sim lover” convergono più rapidamente, quelli che lo detestano forniscono feedback meno precisi.
- **Formula di combinazione** (applicata sia a player che AI):
  - `setup_seed_score = 0.7 * team_sim_eff + 0.3 * driver_sim_affinity`
  - Ogni categoria slider parte da `target ± offset`, dove `offset = f(100 - setup_seed_score)` con peso diverso per Aero / Ride Height / Brake Balance.
- **Parc fermé / vincoli**: la distanza massima consentita dal mapping circuito viene rispettata fin da subito; se il seed cade fuori range, viene clampato.

## 3. Programmi di run (Practice)

| Sessione | Finestra tempo | Programmi principali | Config motore / ERS | Note |
|----------|----------------|----------------------|---------------------|------|
| FP1      | 60'            | Setup Validation, Aero/R&D placeholder | ICE map "Base", ERS Balanced | Focus su trovare il setup e correlare aero. |
| FP2      | 60' (split 30+30) | 0‑30' Tyre/Quali sims, 30‑60' Race run | Prime 30' fuel leggero, ERS Attack; seconde 30' fuel medio-alto, ERS Harvest | Usa run per giri rapidi e long run. |
| FP3      | 60'            | Qualifying rehearsal | Fuel minimo, ERS Attack | Solo rifinitura setup se necessario. |

Programmi di base:
1. **Setup Validation Run** – 3‑6 giri, fuel medio-basso, ERS Balanced. Obiettivo: confrontare il seed con i dati reali e produrre feedback per aggiustare slider.
2. **Tyre Deg Run** – 6‑10 giri, fuel medio-alto, ERS Harvest, pace costante. Obiettivo: calcolare consumo gomme, brake temps, cooling margin.
3. **Quali Simulation** – out + push + cool. Fuel minimo, ERS Attack, ICE map "Quali". Serve per calibrare tempi di riferimento.
4. **Race Trim Run** – 5‑8 giri, fuel gara simulato, ERS Balanced. Convalida comportamento full-tank (FP2 seconda metà).
5. **Aero/R&D Correlation** *(placeholder)* – run dedicati agli upgrade. Attiveremo quando il modulo R&D fornirà componenti da validare.

Ogni team compone un **programma sessione** scegliendo 2‑3 run coerenti con la tabella sopra. Squadre di alto livello possono inserire un run extra se rimane tempo inutilizzato.

## 4. Scheduling run e vincoli temporali

- **Durata run**: `laps_planned` ∈ [3, 10] a seconda del programma. L'AI può anticipare il rientro se raggiunge l'obiettivo (es. dati sufficienti) o se scatta un warning (traffico, bandiera gialla).
- **Tyre allocation**: ogni team consuma set reali del weekend. Il Practice Planner controlla la disponibilità e sceglie composti coerenti (es. FP1 usa soprattutto Hard/Medium, FP3 Soft nuovi). TBD il dettaglio numerico nel modulo gomme.
- **Traffico**: se il LapSimulator segnala congestione, l'AI può ritardare l'uscita fino a 60s (slot di respiro) per simulare queue pitlane.

### 4.1 Heuristica compound (aggiornamento 2026-03-08)
- Il planner applica una scelta compound contestuale:
  - **FP1** → bias Hard/Medium (`C2/C3`) sia per Setup Validation sia per Tyre Deg.
  - **FP2** → prima metà più aggressiva (Tyre Deg/Quali Sim su `C3/C4`), seconda metà (Race Trim) su `C2/C3`.
  - **FP3** → Quali rehearsal su `C4`; eventuali Setup Validation residui su `C3` per non consumare gli ultimi Soft.
- Programmi speciali:
  - `Tyre Test` usa `C4` tranne in FP1 dove scala a `C3`.
  - `Race Sim` resta su `C2` (full-fuel validation).
  - `Race Trim` alterna `C2/C3` in base alla disponibilità.
- L’AI pesca sempre da `TyreInventoryService`, quindi le scelte rispettano i set rimasti e le riserve Q3.

### 4.2 Policy riuso set (Practice)
- L’AI prova a riutilizzare lo stesso set del run precedente quando:
  - il programma richiede lo stesso compound,
  - il set è ancora marcato disponibile,
  - la `condition` è ≥ **40%**.
- Se il set scende sotto il 40% viene automaticamente scartato per i run successivi ed entra nello stato `unavailable`.
- Il riuso è tracciato nei log QA tramite flag `reused` (vedi §7) ma non viene mostrato nella UI del giocatore.

### 4.1 Pit work – lavori ai box e tempi

Ogni sosta ai box è composta da uno o più lavori. I tempi si sommano con overlap parziale (il team lavora in parallelo su aree diverse): `total = max(work_times) + 15s` (overhead base ingresso/uscita box).

| Lavoro | Codice | Tempo (s) | Note |
|--------|--------|-----------|------|
| Tyre change | `TYRE_CHANGE` | 25–30 | 4 gomme, practice (non gara) |
| Fuel refill | `REFUEL` | 40–60 | ~1 s/kg, dipende da quantità |
| Setup change (minor) | `SETUP_MINOR` | 60–90 | 1–2 slider (ala, brake bias) |
| Setup change (major) | `SETUP_MAJOR` | 120–180 | Ride height, sospensioni, antiroll |
| Brake duct change | `BRAKE_DUCT` | 45–60 | Cambio configurazione cooling |
| Front wing replacement | `WING_REPLACE` | 90–120 | Danno o cambio spec |
| Inspection / check | `INSPECTION` | 30–45 | Controllo visivo post-run |

Formula tempo totale:
```
pit_duration_s = max(work_durations) + PIT_OVERHEAD_S
```
dove `PIT_OVERHEAD_S = 15` (ingresso pitlane + posizionamento + uscita).

### 4.2 Car status labels

Ogni auto ha una label di stato visibile nell'interfaccia:

| Label | Significato |
|-------|-------------|
| `Out Lap` | Uscita dai box, riscaldamento gomme |
| `Hot Lap` | Giro lanciato |
| `In Lap` | Rientro ai box |
| `Box - Tyres` | Cambio gomme in corso |
| `Box - Fuel` | Rifornimento |
| `Box - Setup` | Modifica setup |
| `Box - Check` | Ispezione / controllo |
| `Box - Ready` | Lavori completati, in attesa uscita |

Se più lavori sono in corso contemporaneamente, la label mostra il lavoro principale (quello con durata maggiore). Esempio: cambio gomme + setup minor → `Box - Setup`.

### 4.3 Visibilità programmi

- **Auto del player**: programma di lavoro visibile (il player è il team principal).
- **Auto AI avversarie**: solo la label di stato è visibile (Box/Out/Hot/In). Il programma specifico (Setup Validation, Quali Sim, ecc.) resta nascosto, come nel mondo reale.

## 5. Refinement loop

1. **Post-run telemetry**: raccoglie delta vs. target (aero balance, drag index, traction index, brake cooling, tyre deg). Gli stessi segnali sono disponibili per player e AI.
2. **Feedback accuracy** dipende da Driver.SimAffinity + skill Mechanical Sympathy. Piloti più precisi producono suggerimenti migliori.
3. **Adjustment heuristic**: il team applica fino a `max_slots_per_run` cambi, limitati da `circuit.constraints`. Il peso di Team.SimulationEfficiency determina quanto aggressivo è l’aggiustamento.
4. **Convergenza**: una volta raggiunta la soglia "setup ok" (es. tutti gli indici in range giallo/verde), il team passa automaticamente ai programmi Tyre / Quali / Race previsti per la sessione.
5. **Failure cases**: se il tempo sessione finisce o il team termina i run senza trovare il target, i dati finali resteranno “partial” e l’auto scatterà in Qualifica con un setup meno ottimale.

## 6. Configurazioni motore/ERS

- Ogni programma mappa automaticamente ICE/ERS:
  - Setup Validation: `engine_map = Base`, `ers_mode = Balanced`.
  - Tyre Deg / Race Trim: `engine_map = Race`, `ers_mode = Harvest/Balanced`.
  - Quali Simulation: `engine_map = Quali`, `ers_mode = Attack`.
- I livelli di push restano inferiori a quelli di Qualifica reale per preservare i componenti, eccetto nei run esplicitamente "Quali".
- Il planner può ridurre la potenza se il cooling margin scende sotto soglia.

## 7. Logging, eventi & notifiche

- Ogni run genera un record `AIPracticeRun` con: programma, time window, laps, compound usato, fuel load, mappe ICE/ERS, outcome (success/partial/abort), delta setup.
- Eventi principali emessi verso HUD/telemetria:
  - `ai_run_started`, `ai_run_completed`, `ai_run_aborted` (motivo: traffico, incidente, meteo).
  - `ai_setup_adjustment` con dettaglio slider cambiati.
  - `ai_rnd_correlation` (placeholder) per when R&D runs saranno attivi.
- I log vengono usati anche dal QA harness per validare comportamenti multi-car.

### 7.1 Tracciamento gomme AI (2026-03-08)
- Gli eventi `ai_tyre_reserved`, `ai_tyre_stint_completed`, `ai_tyre_reserve_failed`, `ai_tyre_released` vengono emessi da `SessionBridge` e duplicati su `python_backend/logs/ai_tyre_debug.log`.
- Ogni evento include:
  - `compound_requested`, `tyre_set_id`, `condition`, `heat_cycles`, `laps_completed`.
  - Flag `reused` per distinguere set nuovi vs riutilizzati.
  - Delta usura (`condition_before/after`) e chilometraggio per le chiusure stint.
- I log restano backend-only (nessuna esposizione di dati AI all'interfaccia giocatore) e vengono usati dal QA harness per auditare allocation e riuso set.

### 7.1 Notifiche barra (player car)

Per l'auto del player, il sistema invia notifiche alla barra notifiche:

| Evento | Messaggio esempio | Priorità |
|--------|-------------------|----------|
| Pit work start | `"Pit: Tyre change + Setup adj. (~90s)"` | normal |
| Pit work complete | `"Work complete – ready to go"` | normal |
| Run started | `"Starting Quali Simulation (3 laps)"` | low |
| Run completed | `"Run complete – best: 1:47.2"` | normal |
| Setup converged | `"Setup OK – all targets in range"` | high |
| Run aborted | `"Run aborted: red flag"` | high |

Per le auto AI avversarie, le notifiche non vengono inviate (solo label di stato visibile).

## 8. Dipendenze future

- **R&D Module**: quando introdurremo upgrade dinamici, i run di correlazione verranno alimentati dai dati di sviluppo per generare delta prestazionale reale.
- **Tyre allocation detail**: servirà un documento dedicato per indicare quanti set sono disponibili per FP1/FP2/FP3 e come l’AI li prenota.
- **Practice Session Orchestrator**: gestirà timeline, cooldown globali e sincronia con i run dei player.

