---
title: Tyre Allocation & Usage Rules (Weekend)
version: 0.1
last_updated: 2026-02-09
scope: "Definire quanti set per compound sono disponibili per FP1/FP2/FP3/Quali/Gara e come vengono consumati da player/AI"
---

## 1. Obiettivo
Stabilire le regole di allocazione e consumo dei set gomme durante un weekend (dry e wet), così che Practice Orchestrator, AI Driver Engine e future logiche Quali/Race possano validare run e inventario.

## 2. Allocazione di base (dry)
- Set disponibili per weekend (esempio F1 style, personalizzabile per circuito/evento):
  - **Soft (S)**: 8 set
  - **Medium (M)**: 3 set
  - **Hard (H)**: 2 set
- Ogni set ha un identificativo univoco (`set_id`, `compound`, `heat_cycles`).
- Regola generale: un run Practice consuma un set. Se lo stesso set viene riutilizzato (`reused = true`), applicare penalty grip/tempo di warmup (da TyreModel).

## 3. Uso per sessione
- **FP1**: libero uso, preferenza H/M. Set usati restano disponibili come `used` (penalty).
- **FP2**: primo blocco (0-30') per Tyre/Quali sim, secondo blocco (30-60') per Race trim. Usare set Soft nuovi per quali sim, Medium/Hard per race trim.
- **FP3**: tipicamente Soft nuovi per simulare Qualifica. Se setup non è ottimale, è permesso usare M/H usati.
- **Qualifica/Gara**: (placeholder) seguiremo le regole del weekend orchestrator quando definite.

## 4. Wet allocation
- **Intermediate (I)**: 4 set
- **Wet (W)**: 3 set
- In caso di pista dichiarata wet, l’uso dei set dry è sospeso; l’inventario wet è separato e non limita i dry rimasti.

## 5. Penalità riuso / warmup (hook TyreModel)
- Ad ogni heat cycle incrementare `heat_cycles` e applicare:
  - `grip_penalty = base_penalty * heat_cycles` (parametro del TyreModel).
  - `warmup_time += warmup_penalty_per_cycle` per i primi giri del run.
- Se `heat_cycles` supera soglia (es. 5), marcato `end_of_life` → run bloccato.

## 6. Interfacce per gli orchestratori
- **Check-out set**: `reserve_set(team_id, compound, new_or_used)` restituisce `set_id` o errore se esauriti.
- **Check-in set**: al termine run, aggiornare `heat_cycles`, stato `used`, chilometraggio.
- **Inventory API**: elenco set disponibili/usati per team con stato (new/used/eol).

## 7. Integrazioni
- **Practice Session Orchestrator**: valida ogni run consultando questa allocazione e impedisce run se i set richiesti non esistono.
- **AI Driver Engine**: sceglie i set in base al programma (FP1: H/M; FP2 quali sim Soft, race trim M/H; FP3 Soft nuovi).
- **Weekend Orchestrator (futuro)**: gestirà carry-over dei set tra sessioni e regole Quali/Gara.
- **TyreModel**: applica penalty grip/warmup basato su `heat_cycles` e stato `used`.

## 8. Parametrizzazione
- I numeri di set per compound sono configurabili per evento/circuito (es. sprint weekend). Definire un JSON di config (`config/tyre_allocation/<event>.json`).
- Possibile override manuale per scenari QA/test.

## 9. Note aperte
- Definire esattamente i coefficienti di penalty in TyreModel v0.4.
- Stabilire regole Quali/Gara (parc fermé pneumatici) nel futuro documento Weekend Orchestrator.
