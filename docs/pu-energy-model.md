---
title: PU Energy Model & UI Strategy
last_updated: 2026-02-15
status: draft
scope: Definire requisiti funzionali/UI per la gestione di ICE + MGU-K/H + Batteria (SOC) in gioco
links:
  - docs/PowerUnit.md
  - docs/EngineData2025.md
  - docs/global-roadmap.md
---

## 1. Obiettivo
Integrare nel gioco la gestione completa della Power Unit 2025 (limiti 4 MJ deploy / 2 MJ harvest MGU-K, batteria 5–6 MJ, direct-drive MGU-H) con strumenti UI chiari sia per il giocatore sia per i tool R&D.

## 2. Requisiti tecnici
- **Energia per giro**: ogni mappa definisce `deploy_mj_per_lap`, `harvest_mj_per_lap`, `mguh_direct_ratio`, `target_soc_end_lap`.
- **SOC tracking**: SOC normalizzato 0–1 + valore assoluto in MJ; warning sotto 0.2, clipping sotto 0.1.
- **Torque curve**: lookup ICE+MGU-K da `docs/EngineData2025.md`; usato per calcolare la resa delle mappe e per il grafico UI.
- **R&D overrides**: possibilità di impostare manualmente percentuali di energia immessa/recuperata per ogni mappa (file `config/calibration/pu/<cid>.json`).
- **Telemetria**: segment log deve includere `mj_deploy`, `mj_harvest_k`, `mj_harvest_h`, `soc_after_section`.

## 3. UI/UX – Mockup testuale
### 3.1 Garage – pannello mappe PU
```
+----------------------------------------------------+
|  MAPPA PU                                          |
|  [ ECONOMY ] [ STANDARD ] [ RICH ] [ QUALY ]       |
|  [ WET ] [ RECHARGE ]                              |
|                                                    |
|  SOC CURRENT   ████████░░  3.2 MJ (79%)            |
|  TARGET LAP    0.6 (push)                          |
|  MJ DEPLOY     3.8 / 4.0   |■■■■■■■■■■■■■■■■■□□|   |
|  MJ HARVEST    1.5 / 2.0   |■■■■■■■■■■■□□□□□□□|   |
|                                                    |
|  STRATEGY PRESET                                   |
|  ( ) Push 2 laps  (•) Push 1 + Recharge 1          |
|  ( ) Full Recharge                                 |
|                                                    |
|  NOTES                                             |
|  Qualy: SOC->0.1 | Recharge: SOC->0.9              |
+----------------------------------------------------+
```
- Indicatori a barre per MJ usati/recuperati sul giro corrente.
- Pulsanti preset che impostano sequenze (es. push → recharge).
- Tooltip per ogni mappa con descrizione di aggressività (estratto da JSON).

### 3.2 HUD in pista
```
 ┌──────────────────────────────────────────────┐
 │ SOC 72%  |  Deploy 2.6/4 MJ  |  Harvest 0.8 │
 │ Map: RICH (Hold A to Recharge)              │
 │ Clipping in 300m  ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄  (warn) │
 └──────────────────────────────────────────────┘
```
- Notifiche contestuali: "SOC Low – switch Recharge" oppure "Battery Full – Brake Migration Active".
- Pulsante rapido per mappa Wet/Regen.

## 4. API & dati
| Endpoint / Payload | Campo nuovo | Note |
| --- | --- | --- |
| `race_update` | `pu_stats` | `{map, soc, deploy_mj, harvest_mj, mguh_direct_active}` |
| `player_action` | `set_engine_map`, `set_strategy_preset` | Comandi dalla UI verso SessionBridge |
| Telemetria JSON | `pu_energy_trace` | Array per sezione con MJ e SOC |

## 5. Documentazione correlata
- `docs/PowerUnit.md` – modello fisico e parametri.
- `docs/EngineData2025.md` – limiti FIA, curve e preset.
- `docs/global-roadmap.md` – Fase E punto 2 aggiornato con riferimento a questo documento.

## 6. Prossimi step
1. Produrre mockup grafici (Figma o PNG) basati sul wireframe testuale (owner UI/UX).
2. Aggiornare `docs/setup-ui-plan.md` con la sezione "PU Control".
3. Allineare backend (`session_bridge`, `race_update`) per trasportare i nuovi campi `pu_stats`.
4. Aggiornare `scripts/powerunit_fit.py` per generare `deploy/harvest/mguh_ratio/torque_bias` e allegare preview nel report Markdown.
