---
title: AI Driver & Team Behavior – Practice Sessions
version: 0.1
last_updated: 2026-02-08
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

- **Durata run**: `laps_planned` ∈ [3, 10] a seconda del programma. L’AI può anticipare il rientro se raggiunge l’obiettivo (es. dati sufficienti) o se scatta un warning (traffico, bandiera gialla).
- **Pit turnaround minimo**: quando si modificano slider, fuel load o pneumatici, il team impiega almeno **120s** prima di rimandare l’auto in pista (simula cambio gomme, regolazioni meccaniche, refuel).
- **Tyre allocation**: ogni team consuma set reali del weekend. Il Practice Planner controlla la disponibilità e sceglie composti coerenti (es. FP1 usa soprattutto Hard/Medium, FP3 Soft nuovi). TBD il dettaglio numerico nel modulo gomme.
- **Fuel handling**: ogni refuel richiede quota del pit turnaround. Il planner evita run consecutivi con fuel alto senza pausa per coerenza.
- **Traffico**: se il LapSimulator segnala congestione, l’AI può ritardare l’uscita fino a 60s (slot di respiro) per simulare queue pitlane.

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

## 7. Logging & eventi

- Ogni run genera un record `AIPracticeRun` con: programma, time window, laps, compound usato, fuel load, mappe ICE/ERS, outcome (success/partial/abort), delta setup.
- Eventi principali emessi verso HUD/telemetria:
  - `ai_run_started`, `ai_run_completed`, `ai_run_aborted` (motivo: traffico, incidente, meteo).
  - `ai_setup_adjustment` con dettaglio slider cambiati.
  - `ai_rnd_correlation` (placeholder) per when R&D runs saranno attivi.
- I log vengono usati anche dal QA harness per validare comportamenti multi-car.

## 8. Dipendenze future

- **R&D Module**: quando introdurremo upgrade dinamici, i run di correlazione verranno alimentati dai dati di sviluppo per generare delta prestazionale reale.
- **Tyre allocation detail**: servirà un documento dedicato per indicare quanti set sono disponibili per FP1/FP2/FP3 e come l’AI li prenota.
- **Practice Session Orchestrator**: gestirà timeline, cooldown globali e sincronia con i run dei player.

