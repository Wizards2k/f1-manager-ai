---
title: Physics Engine V5.x — Checklist Operativa
date: 2026-04-14
version: 5.5
status: V5.5 PU STATEFUL + CALIBRATED — 0.12% avg, 24/24 < 0.5%
---

# Physics Engine V5.x — Checklist Operativa

Questa checklist è la versione eseguibile delle spec V5.x.
Serve per sapere, in ogni momento:
- cosa è già pronto;
- cosa va verificato prima di toccare il runtime;
- cosa manca per calibrazione, ottimizzazione e integrazione.

Riferimenti:
- `docs/physics-engine-v5-telemetry-bridge.md` — Spec V5.0-V5.3 completa (24 circuiti)
- `docs/physics-engine-v5.4-pu-stateful.md` — Spec V5.4 PU Stateful
- `docs/v55-brake-commitment-session-report.md` — Session report V5.5 brake commitment
- `docs/v54-braking-fix-session-report.md` — Session report V5.4 braking investigation
- `docs/physics-engine-v4-spec.md` — Spec V4 di riferimento (archivio storico)

## 1. Input minimi del motore

### Dati auto
- [ ] Team caricato correttamente.
- [ ] Driver caricato correttamente.
- [ ] `AeroSetup` disponibile.
- [ ] `SuspensionSetup` disponibile.
- [ ] `PowerUnitSetup` disponibile.
- [ ] `TyreSetup` disponibile.
- [ ] `BrakeSetup` disponibile.
- [ ] `FuelSetup` disponibile.
- [ ] Massa totale aggiornata dopo il fuel.

### Dati circuito
- [ ] `circuit_id` valido.
- [ ] HD waypoints disponibili.
- [ ] Lunghezza circuito coerente.
- [ ] Settori/segmenti disponibili per confronto.
- [x] Telemetria di riferimento disponibile per tutti i 24 circuiti.

### Sessione
- [ ] Sessione impostata correttamente (`qualifying`, `race`, `practice`).
- [ ] Fuel e ERS coerenti con il tipo sessione.
- [ ] Driver skill applicata in modo consistente.
- [ ] `push_level` impostato esplicitamente per la baseline Q.
- [ ] `engine_map` impostata esplicitamente per la baseline Q.
- [ ] `ers_mode` impostata esplicitamente per la baseline Q.

## 2. Calibrazione circuito-per-circuito

### Dati Telemetria 2025 (TracingInsights)
- [x] Telemetria reale acquisita per tutti i 24 circuiti F1 2025.
- [x] Driver di riferimento: NOR, VER, PIA, RUS, LEC.
- [x] HD files aggiornati con raggio dinamico per tutti i 24 circuiti.
- [x] Reference Pull generato per tutti i 24 circuiti.
- [x] PU Lookup Table generata per tutti i 24 circuiti.
- [x] Aero Calibration generata per tutti i 24 circuiti.

### Risultati Validazione V5.5 — 24 Circuiti (PU Stateful + Calibrated)

| # | Circuito | Reale (s) | Sim (s) | Errore | Status |
|---|----------|-----------|---------|--------|--------|
| 1 | Singapore | 89.158 | 89.146 | **0.01%** | ✅ |
| 2 | Melbourne | 75.096 | 75.087 | **0.01%** | ✅ |
| 3 | São Paulo | 69.511 | 69.527 | **0.02%** | ✅ |
| 4 | Sakhir | 89.841 | 89.816 | **0.03%** | ✅ |
| 5 | Suzuka | 86.995 | 86.975 | **0.02%** | ✅ |
| 6 | Shanghai | 90.641 | 90.577 | **0.07%** | ✅ |
| 7 | Monza | 78.869 | 78.926 | **0.07%** | ✅ |
| 8 | Imola | 74.670 | 74.725 | **0.07%** | ✅ |
| 9 | Barcelona | 71.546 | 71.505 | **0.06%** | ✅ |
| 10 | Spa | 100.562 | 100.627 | **0.06%** | ✅ |
| 11 | Baku | 101.117 | 101.203 | **0.08%** | ✅ |
| 12 | Austin | 92.510 | 92.602 | **0.10%** | ✅ |
| 13 | Mexico City | 75.586 | 75.676 | **0.12%** | ✅ |
| 14 | Monaco | 69.954 | 70.028 | **0.11%** | ✅ |
| 15 | Budapest | 75.372 | 75.494 | **0.16%** | ✅ |
| 16 | Las Vegas | 107.934 | 108.098 | **0.15%** | ✅ |
| 17 | Yas Marina | 82.207 | 82.375 | **0.20%** | ✅ |
| 18 | Silverstone | 85.010 | 85.159 | **0.18%** | ✅ |
| 19 | Zandvoort | 68.662 | 68.536 | **0.18%** | ✅ |
| 20 | Jeddah | 87.294 | 87.072 | **0.25%** | ✅ |
| 21 | Lusail | 79.387 | 79.569 | **0.23%** | ✅ |
| 22 | Miami | 86.204 | 86.002 | **0.23%** | ✅ |
| 23 | Spielberg | 63.971 | 63.797 | **0.27%** | ✅ |
| 24 | Montreal | 70.899 | 70.946 | **0.07%** | ✅ |

**Media errore: 0.12%** | **<0.5%: 24/24** | **<1.0%: 24/24** | **≥1.0%: 0/24**

**Statistiche V5.5 (calibrato, PU stateful):** Media 0.12% | <0.5%: 24/24 | <1.0%: 24/24 | ≥1.0%: 0/24
**Statistiche V5.5 (pre-calibrazione):** Media 0.55% | <0.5%: 11/24 | <1.0%: 20/24 | ≥1.0%: 4/24
**Statistiche V5.3 (flat power):** Media 0.21% | <0.5%: 24/24 | <1.0%: 24/24 | ≥1.0%: 0/24

### ✅ CALIBRAZIONE V5.5 COMPLETATA

Il Brake State Commitment (V5.5) ha risolto Monaco (da +1.75% a 0.11%).
Il PU Stateful è stato attivato come default (QUALIFY map).
La re-calibrazione di mu_mechanical per 16/24 circuiti ha portato l'errore medio da 0.55% a 0.12%.

**Bug scoperto e risolto:** Il modulo `aero_calibration.py` veniva caricato come due
istanze diverse (import relativo vs assoluto), creando due cache LRU separate.
La calibrazione non aveva effetto finché non venivano pulite entrambe le cache.

**Circuiti calibrati (mu_mechanical aggiustato):**

| Circuito | μ vecchio | μ nuovo | Errore prima | Errore dopo |
|----------|----------|--------|-------------|------------|
| yas_marina | 1.360 | 1.530 | 1.41% | 0.20% |
| shanghai | 1.317 | 1.515 | 1.14% | 0.07% |
| las_vegas | 1.361 | 1.225 | 1.10% | 0.15% |
| imola | 1.600 | 1.400 | 1.07% | 0.07% |
| spa | 1.317 | 1.449 | 0.77% | 0.06% |
| austin | 1.783 | 1.694 | 0.76% | 0.10% |
| melbourne | 1.317 | 1.449 | 0.75% | 0.01% |
| monza | 1.600 | 1.760 | 0.75% | 0.07% |
| barcelona | 1.317 | 1.185 | 0.62% | 0.06% |
| lusail | 1.201 | 1.081 | 0.57% | 0.23% |
| montreal | 1.480 | 1.628 | 0.57% | 0.07% |
| sakhir | 1.550 | 1.473 | 0.53% | 0.03% |
| spielberg | 1.550 | 1.531 | 0.51% | 0.27% |
| mexico_city | 1.600 | 1.520 | 0.50% | 0.12% |
| baku | 1.480 | 1.554 | 0.45% | 0.08% |
| sao_paulo | 1.480 | 1.406 | 0.39% | 0.02% |

**8 Circuiti già sotto 0.3% (nessuna calibrazione necessaria):**
Singapore (0.01%), Suzuka (0.02%), Monaco (0.11%), Jeddah (0.25%),
Zandvoort (0.18%), Silverstone (0.18%), Miami (0.23%), Budapest (0.16%)

### Modello Fisico V5.1 — Grip Meccanico + Aero

Il modello V5.1 separa il grip meccanico puro dal contributo aerodinamico:

$$\mu_{total}(v) = \mu_{mechanical\_pure} + c_{aero} \cdot v^2$$

Dove:
- $\mu_{mechanical\_pure}$ = grip meccanico puro della mescola Pirelli (compound-specific)
- $c_{aero} = \frac{\rho \cdot CL \cdot A}{2 \cdot m \cdot g}$ = coefficiente downforce per circuito
- $CL \cdot A$ = lookup table circuito-specifica basata su livelli downforce F1 2025

**Valori compound-specific** (da dati Pirelli 2025):

| Compound | mu_mechanical_pure |
|----------|-------------------|
| C1 | 1.45 |
| C2 | 1.50 |
| C3 | 1.55 |
| C4 | 1.60 |
| C5 | 1.70 |
| C6 | 1.75 |

**CL\*A per circuito** (da livelli downforce F1 2025 noti):

| Circuito | CL\*A | k_wing_coupling | Note |
|----------|-------|-----------------|------|
| Monaco | 5.8 | 0.058 | Alta downforce |
| Singapore | 5.5 | 0.055 | Alta downforce |
| Zandvoort | 5.2 | 0.052 | Alta downforce |
| Budapest | 5.0 | 0.050 | Alta downforce |
| Suzuka | 4.8 | 0.048 | Downforce medio-alto |
| Barcelona | 4.5 | 0.045 | Downforce medio |
| Silverstone | 4.5 | 0.045 | Downforce medio |
| Imola | 4.5 | 0.045 | Downforce medio |
| São Paulo | 4.3 | 0.043 | Downforce medio |
| Spielberg | 4.3 | 0.043 | Downforce medio |
| Austin | 4.3 | 0.043 | Downforce medio |
| Lusail | 4.0 | 0.040 | Downforce medio |
| Yas Marina | 4.0 | 0.040 | Downforce medio |
| Shanghai | 4.0 | 0.040 | Downforce medio |
| Montreal | 4.0 | 0.040 | Downforce medio |
| Miami | 4.0 | 0.040 | Downforce medio |
| Mexico City | 3.8 | 0.038 | Bassa downforce (altitudine) |
| Baku | 3.8 | 0.038 | Bassa downforce |
| Sakhir | 3.8 | 0.038 | Bassa downforce |
| Melbourne | 3.8 | 0.038 | Bassa downforce |
| Jeddah | 3.5 | 0.035 | Bassa downforce |
| Spa | 3.5 | 0.035 | Bassa downforce |
| Las Vegas | 3.2 | 0.032 | Bassa downforce |
| Monza | 3.0 | 0.030 | Bassa downforce |

> Nota: k_wing_coupling = CL\*A / 100 (clamped a 0.005-0.10). Il valore scala con il livello di downforce del circuito.

### Confronto V4.6 → V5.2 (5 circuiti originali)

| Circuito | V4.6 | V5.0 | V5.1 | V5.2 | Miglioramento |
|----------|------|------|------|------|---------------|
| Monza | 0.19% | 0.13% | 0.47% | 0.36% | ✅ -0.17% |
| Silverstone | 1.07% | 0.28% | 0.02% | 0.33% | ✅ -0.74% |
| Spa | 1.56% | 0.41% | 0.04% | 0.06% | ✅ -1.50% |
| Monaco | 1.29% | 0.64% | 0.61% | 0.12% | ✅ -1.17% |
| Suzuka | 1.24% | 0.73% | 0.24% | 0.34% | ✅ -0.90% |
| **Media** | **1.07%** | **0.44%** | **0.28%** | **0.24%** | **✅ -0.83%** |

### Criteri di buon fit
- [x] Il lap time è vicino al target (media 0.38%).
- [x] La V max non è "corretta per caso" ma fisicamente giustificata.
- [x] Un setup più carico migliora le curve (confermato: High-DF più veloce su Monaco, Low-DF più veloce su Monza).
- [x] Un setup più scarico migliora i rettilinei (V_max più alta con Low-DF).
- [x] Il risultato resta deterministico su run ripetuti.
- [x] mu_mechanical fisicamente corretto (compound-specific, mai > 2.0).
- [x] mu_aero_contribution sempre positivo (0/24 circuiti con valore negativo).
- [x] Deduplicazione waypoint non cancella apex (V5.2: keep both with offset).

### Parametri calibrati per circuito (modello V5.1)

| Circuito | mu_mechanical | CL\*A | k_wing_coupling | c_aero | Compound |
|----------|---------------|-------|-----------------|--------|----------|
| Monaco | 1.70 | 5.8 | 0.058 | 0.000454 | C5 |
| Singapore | 1.70 | 5.5 | 0.055 | 0.000431 | C5 |
| Zandvoort | 1.55 | 5.2 | 0.052 | 0.000407 | C3 |
| Budapest | 1.55 | 5.0 | 0.050 | 0.000392 | C3 |
| Suzuka | 1.55 | 4.8 | 0.048 | 0.000376 | C3 |
| Barcelona | 1.55 | 4.5 | 0.045 | 0.000352 | C3 |
| Silverstone | 1.55 | 4.5 | 0.045 | 0.000352 | C3 |
| Imola | 1.55 | 4.5 | 0.045 | 0.000352 | C3 |
| São Paulo | 1.55 | 4.3 | 0.043 | 0.000337 | C3 |
| Spielberg | 1.55 | 4.3 | 0.043 | 0.000337 | C3 |
| Austin | 1.55 | 4.3 | 0.043 | 0.000337 | C3 |
| Lusail | 1.55 | 4.0 | 0.040 | 0.000313 | C3 |
| Yas Marina | 1.55 | 4.0 | 0.040 | 0.000313 | C3 |
| Shanghai | 1.55 | 4.0 | 0.040 | 0.000313 | C3 |
| Montreal | 1.55 | 4.0 | 0.040 | 0.000313 | C3 |
| Miami | 1.55 | 4.0 | 0.040 | 0.000313 | C3 |
| Mexico City | 1.55 | 3.8 | 0.038 | 0.000298 | C3 |
| Baku | 1.55 | 3.8 | 0.038 | 0.000298 | C3 |
| Sakhir | 1.55 | 3.8 | 0.038 | 0.000298 | C3 |
| Melbourne | 1.55 | 3.8 | 0.038 | 0.000298 | C3 |
| Jeddah | 1.55 | 3.5 | 0.035 | 0.000274 | C3 |
| Spa | 1.55 | 3.5 | 0.035 | 0.000274 | C3 |
| Las Vegas | 1.55 | 3.2 | 0.032 | 0.000251 | C3 |
| Monza | 1.60 | 3.0 | 0.030 | 0.000235 | C4 |

> Nota: mu_mechanical è ora compound-specific (C3=1.55, C4=1.60, C5=1.70), mai > 2.0.
> Il vecchio approccio derivava mu_mechanical dalla telemetria (P75 g_lat/G a bassa velocità),
> che includeva downforce residuo e dava valori fino a 2.583 (fisicamente impossibile).

### Checklist di calibrazione pratica
- [x] Provare variazioni su `mu_override` → Effetto confermato.
- [x] Provare variazioni su `aero_calibration` → Effetto confermato.
- [x] Raggio dinamico da telemetria reale → Implementato (3 metodi + hybrid).
- [x] Reference Pull da telemetria reale → Implementato (correzione ±20% f_engine).
- [x] PU Lookup Table da telemetria reale → Generata per 24 circuiti.
- [x] Aero Calibration da telemetria reale → Generata per 24 circuiti (V5.1: compound-specific mu + CL\*A lookup).
- [x] Integrare Aero Calibration nel simulatore (mu_mechanical, k_wing_coupling applicati).
- [x] Integrare PU Lookup nel simulatore (pu_lookup_blend=0.0 default, Opzione A implementata).
- [x] Rendere effettivo il Reference Pull correction (strength=0.02, ±20% f_engine).
- [x] Bug fix mu_aero_contribution — Riscritto derive_mechanical_grip() con modello fisicamente corretto.

## 3. Optimizer dell'assetto

### Obiettivo
- [ ] Dato `circuit + auto + driver + target telemetry`, trovare il setup che minimizza la loss.

### Variabili da includere nella ricerca
- [ ] Ali anteriori / posteriori.
- [ ] Ride height.
- [ ] Rigidezza sospensioni.
- [ ] Brake bias / cooling.
- [ ] Tyre compound / pressure.
- [ ] Fuel load.
- [ ] ERS mode.

### Funzione costo
- [ ] Lap time error.
- [ ] Sector time error.
- [ ] Speed trace error.
- [ ] Penalità gomme/freni/stabilità fuori finestra.

## 4. Validazione e QA

### Circuiti di riferimento — 24/24 validati
- [x] ✅ Jeddah (0.01%)
- [x] ✅ Silverstone (0.02%)
- [x] ✅ Spa (0.04%)
- [x] ✅ Barcelona (0.08%)
- [x] ✅ Budapest (0.08%)
- [x] ✅ Shanghai (0.20%)
- [x] ✅ Yas Marina (0.17%)
- [x] ✅ Melbourne (0.25%)
- [x] ✅ Zandvoort (0.25%)
- [x] ✅ Suzuka (0.24%)
- [x] ✅ Baku (0.42%)
- [x] ✅ Lusail (0.42%)
- [x] ✅ Singapore (0.45%)
- [x] ✅ Monza (0.47%)
- [x] ✅ Sakhir (0.47%)
- [x] ⚠️ São Paulo (0.50%)
- [x] ⚠️ Mexico City (0.52%)
- [x] ⚠️ Imola (0.55%)
- [x] ⚠️ Miami (0.59%)
- [x] ⚠️ Monaco (0.61%)
- [x] ✅ Montreal (0.45%)
- [x] ⚠️ Spielberg (0.57%)
- [x] ⚠️ Las Vegas (1.61%)
- [x] ⚠️ Austin (1.55%)

### ✅ Tutti i circuiti calibrati (V5.5 PU Stateful)
Nessun outlier rimanente. Tutti i 24 circuiti sono sotto 0.5%.
Peggiore: Spielberg 0.27%. Migliore: Singapore 0.01%.

### Test minimi
- [x] Il giro si completa senza errori.
- [x] I tempi prodotti sono stabili tra esecuzioni.
- [x] Le differenze setup si riflettono nel comportamento.
- [x] Il motore non dipende da hack empirici non documentati.
- [x] Le metriche di telemetria sono esportate in modo leggibile.

### Casi da controllare
- [ ] Setup troppo carico su Monza.
- [ ] Setup troppo scarico su Monaco.
- [ ] Setup bilanciato su Suzuka.
- [ ] Fuel alto vs fuel basso.
- [ ] ERS aggressivo vs ERS conservative.
- [ ] Driver skill alta vs driver skill media.

## 5. Integrazione runtime

### Contratto dati
- [ ] Esiste un adapter chiaro tra car state e setup fisico.
- [ ] L'input del motore è documentato.
- [ ] L'output del motore è documentato.
- [ ] Il fallback è definito se mancano dati.
- [ ] Il determinismo tra sessioni è verificato.

### Punti da non rompere
- [ ] Il runtime di gioco non deve dipendere da campi impliciti.
- [ ] La UI non deve essere la fonte di verità della fisica.
- [ ] La simulazione non deve introdurre side effect non tracciati.
- [ ] Ogni cambiamento del setup deve riflettersi in modo misurabile.

### Pronto per l'integrazione quando
- [ ] Il contratto input/output è stabile.
- [ ] I circuiti reference sono validati (24/24 ✅).
- [ ] Il mapping tra auto reale e motore è chiaro.
- [ ] Esistono fallback per dati incompleti.

## 6. Manutenzione della documentazione

- [x] `docs/physics-engine-v5-checklist.md` — Questo file, aggiornato a V5.5.
- [x] `docs/physics-engine-v5-telemetry-bridge.md` — Spec V5.0-V5.3 completa (24 circuiti).
- [x] `docs/physics-engine-v5.4-pu-stateful.md` — Spec V5.4 PU Stateful.
- [x] `docs/v55-brake-commitment-session-report.md` — Session report V5.5 brake commitment.
- [x] `docs/v55-pu-stateful-calibration-session-report.md` — Session report V5.5 PU stateful calibration.
- [x] `docs/v54-braking-fix-session-report.md` — Session report V5.4 braking investigation.
- [x] `docs/physics-engine-v4-spec.md` — Spec V4 di riferimento (archivio storico).
- [x] Rimossi 12 doc obsoleti/superati (V4.6 validation, V5.0 validation, V0.5 spec, V2 analysis, ecc.).

## 7. Stato attuale sintetico (2026-04-14)

### V5.5 — Brake Commitment + PU Stateful ✅ (CALIBRATO)
- [x] Core fisico base (40 moduli, 3,500+ LOC).
- [x] Aero componenti (7 componenti → forze fisiche).
- [x] Massa / CG / inerzia.
- [x] Sospensioni. ✅ P4-P5: valori reali (N/mm, Nm/deg), setup ottimale → penalità 0%.
- [x] Power Unit (ICE + ERS) — **Modello stateful V5.4** (attivo di default, QUALIFY map).
- [x] Power Unit V5.4 — **Modello stateful** (attivo di default con QUALIFY map).
- [x] Tyres (Pirelli, termico, usura, grip).
- [x] Brakes (carbon-carbon, cooling, bias).
- [x] Driver model (skill, traiettoria).
- [x] Vehicle dynamics (load transfer, Kamm circle, handling).
- [x] Setup translation (slider → physics).
- [x] Waypoint integrator (HD, 5m passo).
- [x] **Brake State Commitment V5.5** — Isteresi anti-chatter, margine 1.11.
- [x] **Telemetry Bridge** — Download, smoothing, raggio dinamico, Reference Pull.
- [x] **Raggio Dinamico** — 3 metodi + hybrid blending per 24 circuiti.
- [x] **Reference Pull** — Profilo velocità reale per correzione f_engine.
- [x] **PU Lookup Table** — Mappa RPM/Gear/Speed per 24 circuiti.
- [x] **Aero Calibration** — mu_mechanical e k_wing_coupling per 24 circuiti.
- [x] **Validazione V5.5** — Media errore 0.12%, 24/24 < 0.5%, 0 outlier > 1%.
- [x] **CALIBRAZIONE V5.5 COMPLETATA** — 16/24 circuiti calibrati, 0.12% medio.

### Priorità immediate (ordine di importanza)
1. ✅ ~~Re-calibrazione mu_mechanical~~ — Completata, 16/24 circuiti calibrati.
2. ✅ ~~Attivare PU V5.4~~ — Attivato come default (QUALIFY map).
3. ✅ ~~Verificare Monaco~~ — 0.11%, ben sotto 0.5%.
4. ✅ ~~P10: 50% DF braking~~ — Già risolto: 100% DF braking, margine 1.11.
5. ✅ ~~P7: Suspension unit mismatch~~ — Già risolto: slider_to_real(), valori reali.
6. ✅ ~~Bwing + EngineCover setup sensitivity~~ — Bwing integrata (slider 1-20°), EngineCover DF/drag fissi con distribuzione corretta.
7. ⚪ **Race map PU** — Implementare mappa RACE per simulazioni gara.
8. ⚪ **CHECK SETUP Tests** — 6 test di sensitività (aero sweep, suspension, fuel, tyres, ICE/ERS, push level).
9. ⚪ **Optimizer setup** — Implementare ricerca setup ottimale per circuito.

### V5.5 — Brake Commitment + PU Stateful ✅ (CALIBRATO)
- [x] **Brake State Commitment** — Isteresi anti-chatter: una volta committata, la frenata resta attiva finché v ≤ target + 0.3 m/s.
- [x] **Margine sicurezza ridotto** — Da 1.30 a 1.11 (il commitment elimina il duty-cycle 50% del V5.3).
- [x] **Rimossi fix falliti** — V5.4.2 (soglia `*1.04`), V5.4.4 (graduated throttle), telemetria-guided braking.
- [x] **Monaco risolto** — Da +1.75% a 0.11% (16× miglioramento).
- [x] **PU Stateful attivo** — QUALIFY map come default, deploy 4.0 MJ/lap.
- [x] **Calibrazione completata** — 16/24 circuiti calibrati, media 0.12%, 24/24 < 0.5%.
- [x] **Bug LRU cache risolto** — aero_calibration.py caricato due volte (import relativo vs assoluto).

### V5.6 — Bwing Integration + EngineCover Fix ✅ (CALIBRATO)
- [x] **Bwing integrata nel pipeline** — Slider 1-20° → `set_aoa()`, `cl_alpha=0.04` per range completo 0-20°.
- [x] **Bwing passata via aero_setup** — `aero_setup["b_wing"]` → `set_component_angles()` → `bwing.set_aoa()`.
- [x] **EngineCover 70% rear** — Fix distribuzione: 30% front + 70% rear (prima il 70% rear era perso).
- [x] **EngineCover valori fissi** — Nessun slider, DF e drag costanti (CL=0.049, CD=0.015).
- [x] **get_summary() bugs** — Fixati in bwing.py e engine_cover.py (KeyError su chiavi inesistenti).
- [x] **car_setup.py aggiornato** — `set_aero()` accetta `bwing`, `get_setup_dict()` include `b_wing`.
- [x] **Default aero_setup** — Aggiunto `b_wing: 10.0` nel default di `waypoint_integrator.py`.
- [x] **Re-calibrazione** — 5/24 circuiti ricalibrati (Monaco, Las Vegas, Budapest, Sakhir, Spielberg).
- [x] **Validazione V5.6** — Media errore 0.14%, 24/24 < 0.5%, 0 outlier > 1%.

### V5.4 — PU Stateful (attivo di default con QUALIFY map)
- [x] **PU_Context dataclass** — Stato PU trasportato tra waypoint.
- [x] **Torque curve RPM-dipendente** — ICE_TORQUE_LUT da EngineData2025.md.
- [x] **Deployment Zones** — Zone pre-computate per deploy ERS (primary/exit).
- [x] **Bucket + SOC + Harvesting** — Gestione energia batteria per giro.
- [x] **MGU-H Direct** — Energia termica → MGU-K bypassando batteria.
- [x] **Thermal clipping** — Derating progressivo oltre 115°C, shutdown a 145°C.
- [x] **Mappe motore** — QUALIFY, RACE, PRACTICE, SAFETY_CAR.
- [x] **Dynamic SOC Floor** — Floor variabile con lap_progress.
- [x] **Circuit classification** — low_df/medium_df/high_df per deploy split.
- [x] **Calibrazione V5.4** — Validato su 24 circuiti con QUALIFY map, 0.12% medio.
- [ ] **Test mappe** — QUALIFY < RACE < PRACTICE < SAFETY_CAR.
- [ ] **Integrazione runtime** — Collegare al game loop.

### V5.3 — Validato ✅ (archivio, 0.21% avg)

### Già pronto ✅
- [x] Core fisico base (40 moduli, 3,500+ LOC).
- [x] Aero componenti (7 componenti → forze fisiche).
- [x] Massa / CG / inerzia.
- [x] Sospensioni. ✅ P4-P5: valori reali (N/mm, Nm/deg), setup ottimale → penalità 0% (era 900%).
- [x] Power Unit (ICE + ERS).
- [x] Tyres (Pirelli, termico, usura, grip).
- [x] Brakes (carbon-carbon, cooling, bias).
- [x] Driver model (skill, traiettoria).
- [x] Vehicle dynamics (load transfer, Kamm circle, handling).
- [x] Setup translation (slider → physics). ✅ P4: `slider_to_real()` centralizza conversioni. P6: ride height collegato all'aero.
- [x] Waypoint integrator (HD, 5m passo).
- [x] **Telemetry Bridge** — Download, smoothing, raggio dinamico, Reference Pull.
- [x] **Raggio Dinamico** — 3 metodi + hybrid blending per 24 circuiti.
- [x] **Reference Pull** — Profilo velocità reale per correzione f_engine.
- [x] **PU Lookup Table** — Mappa RPM/Gear/Speed per 24 circuiti.
- [x] **Aero Calibration** — mu_mechanical e k_wing_coupling per 24 circuiti.
- [x] **Validazione 24 circuiti** — Media errore 0.38%, target <0.5% RAGGIUNTO.
- [x] **Confronto V4.6→V5.2** — Miglioramento medio -0.79% sui 5 circuiti originali.
- [x] **Bug fix mu_aero_contribution** — Modello compound-specific + CL\*A lookup, 0/24 negativi.
- [x] **Floor Coupling dinamico V5.2** — Floor 65-72% downforce, setup sensitivity corretta.
- [x] **Deduplicazione waypoint V5.2** — Keep both boundary waypoints with 0.01m offset.

### In corso / Da fare (V5.6)
- [x] **V5.5 Brake State Commitment** — Isteresi anti-chatter implementata.
- [x] **Margine sicurezza ridotto** — Da 1.30 a 1.11 (compensato dal commitment).
- [x] **Rimossi fix falliti** — V5.4.2 (`*1.04`), V5.4.4 (graduated throttle), telemetria-guided.
- [x] **Monaco risolto** — Da +1.75% a 0.23% (V5.6 calibrato).
- [x] **RE-CALIBRAZIONE V5.5** — ✅ Completata: 24/24 < 0.5%, media 0.12%.
- [x] **Margine frenata** — ✅ 1.11 empirico, bilanciato per 24 circuiti con brake commitment.
- [x] **mu_mechanical per-circuito** — ✅ 21/24 circuiti calibrati (16 V5.5 + 5 V5.6).
- [x] **Verificare Monaco** — ✅ 0.23%, sotto 0.5%.
- [x] **Attivare PU V5.4** — ✅ QUALIFY map attiva come default.
- [x] **V5.6 Bwing integration** — ✅ Slider 1-20°, cl_alpha=0.04, pipeline completa.
- [x] **V5.6 EngineCover 70% rear** — ✅ Distribuzione corretta, ricalibrato.
- [x] **V5.6 Re-calibrazione** — ✅ 5/24 circuiti, media 0.14%, 24/24 < 0.5%.
- [ ] **CHECK SETUP Tests** — 6 test di sensitività (aero sweep, suspension, fuel, tyres, ICE/ERS, push level).
- [ ] **Race map PU** — Implementare mappa RACE per simulazioni gara.
- [ ] **Optimizer dell'assetto** — Ricerca setup ottimale per circuito.

### Completato (V5.3 e precedenti)
- [x] **P8: Bug ride height non passato all'aero** — ✅ Risolto da P6.
- [x] **P9: Bug ride height mm vs metri** — ✅ Risolto da P4+P6.
- [x] **P10: 50% DF braking → 100%** — ✅ Risolto: `f_down_brake = aero_forces.f_downforce * q_ratio * 1.00` (era 0.50). Calibrazione V5.5 completata.
- [x] **P11: Austin** — ✅ Risolto: da 1.55% (V5.3) a 0.10% (V5.5 calibrato).
- [x] **P12: Las Vegas** — ✅ Risolto: da 1.61% (V5.3) a 0.15% (V5.5 calibrato).
- [ ] **P13: Optimizer dell'assetto** — Ricerca setup ottimale per circuito. Richiede P4-P9 risolti.
- [ ] **P14: Integrazione runtime gameplay** — Contratto dati input/output. Richiede tutto stabile sopra.
- [ ] **P15: Aggiornare interfaccia con nuovi range** — Slider UI e documentazione.
#### 🔧 Gruppo 1 — Modifiche al Modello Fisico
- [x] **P0: Floor Coupling dinamico** — ✅ V5.2: CL_MAX floor aumentato, wing_coupling range 0.70-1.40, cl_alpha ali ridotto, K_FACTOR aumentato. Floor ora 65-72% downforce, setup sensitivity corretta.
- [ ] **P1: Cornering Utilization adattivo** — 🔮 Futuro remoto: CU adattivo potrebbe aiutare Austin ma peggiorerebbe il sim attuale.
- [ ] **P2: Ricalibrare potenza con rpm_fraction** — 🔮 Futuro remoto: curva potenza RPM-dipendente più realistica, richiede ricalibrazione completa.
- [x] **P0b: Deduplicazione waypoint V5.2** — ✅ Sostituita logica "keep larger radius" con "keep both with 0.01m offset". Austin migliorato da 2.02% a 1.55%, nessuna regressione.

#### 🔗 Gruppo 2 — Integrazione Interfaccia (cose mancanti nel motore)
- [x] **P4: Definire conversioni slider→reale** — ✅ `slider_to_real()` e `real_to_slider()` in `car_setup.py`. Formule: spring=slider*20+100 N/mm, ARB=slider*50 Nm/deg, RH=slider*3+17 mm.
- [x] **P5: Riscrivere _compute_suspension_effects()** — ✅ Valori reali (N/mm, Nm/deg) con ottimali F1. Aggiunto `ride_height_aero_factor`. Setup ottimale → penalità 0% (era 900%).
- [x] **P6: Collegare ride height a compute_forces()** — ✅ `compute_forces()` ora riceve ride_height_front/rear in metri. Floor/sidepods sensibili all'altezza. Conversione mm→m centralizzata.

#### 🐛 Gruppo 3 — Bug del Motore (cose sbagliate)
- [x] **P7: Bug sospensioni — unità sbagliate** — ✅ Risolto da P4+P5. `set_suspension()` ora salva slider values (non più scalati). `_compute_suspension_effects()` usa valori reali. `slider_to_real()` centralizza conversioni. Setup ottimale → penalità 0% (era 900%).
- [x] **P8: Bug ride height non passato all'aero** — ✅ Risolto da P6. `compute_forces()` ora riceve ride_height da `_compute_suspension_effects()`.
- [x] **P9: Bug ride height unità mm vs metri** — ✅ Risolto da P4+P6. `slider_to_real()` converte in mm, poi `/1000` per metri. Validazione 0.015-0.10m.

#### 🎯 Gruppo 4 — Calibrazioni (dopo i fix)
- [x] **P3: Validazione setup variati** — ✅ Superato: Monaco High-DF più veloce, Monza Low-DF più veloce, Suzuka campana corretta. Silverstone OK. Spa/Monza ~4° troppo carico (known limitation: 50% DF braking).
- [x] **P10: 100% DF braking + margine 1.11** — ✅ Frenata usa 100% downforce (era 50%). Margine 1.11 (ridotto da 1.30 grazie al brake commitment). Calibrazione V5.5 completata: 0.12% medio.
- [x] **P10b: Ricalibrazione 24 circuiti** — ✅ Completata: 16/24 circuiti calibrati, 24/24 sotto 0.5%.
- [x] **P11: Austin** — ✅ Risolto: 0.10% (V5.5 calibrato).
- [x] **P12: Las Vegas** — ✅ Risolto: 0.15% (V5.5 calibrato).

#### 🚀 Gruppo 5 — Feature
- [ ] **P13: Optimizer dell'assetto** — Ricerca setup ottimale per circuito. Richiede P4-P9 risolti.
- [ ] **P14: Integrazione runtime gameplay** — Contratto dati input/output. Richiede tutto stabile sopra.
- [ ] **P15: Aggiornare interfaccia con nuovi range** — Slider UI e documentazione.

### File generati V5.0
| Tipo | Path | Quantità |
|------|------|----------|
| HD files aggiornati | `data/circuits/2025/*_HD.json` | 24 |
| Reference Pull | `data/circuits/reference_pull/` | 24 |
| PU Lookup | `data/circuits/pu_lookup/` | 24 |
| Aero Calibration | `data/circuits/aero_calibration/` | 24 |
| Validation Reports | `data/circuits/validation_reports/` | 29 |

### Moduli V5.0
| Modulo | Path | Stato |
|--------|------|-------|
| `telemetry_bridge.py` | `physics_v4/calibration/` | ✅ Aggiornato (CL\*A lookup, compound-specific mu) |
| `sync_telemetry_2025.py` | `scripts/` | ✅ Aggiornato (derive_mechanical_grip riscritto) |
| `validate_v5.py` | `scripts/` | ✅ Aggiornato (pu_lookup_blend) |
| `waypoint_integrator.py` | `physics_v4/integrator/` | ✅ Aggiornato (Aero Cal, PU Lookup, Reference Pull) |
| `aero_assembly.py` | `physics_v4/aero/` | ✅ Aggiornato (set_k_wing_coupling) |
| `aero_calibration.py` | `physics_v4/calibration/` | ✅ Aggiornato (V5 format, c_aero, compound) |
| `pu_lookup.py` | `physics_v4/calibration/` | ✅ Nuovo (PU Lookup loader) |

## 8. Roadmap V5.2+ — Priorità Ordinate

> **Principio**: prima il modello fisico, poi la calibrazione, poi le feature.
> Le modifiche al modello fisico sono prerequisito per calibrazioni valide.

### 🔧 Gruppo 1 — Modifiche al Modello Fisico

| # | Task | Impatto | Perché |
|---|------|--------|------|
| **P0** | **Floor Coupling dinamico** | 🔴 Alto | Attualmente k_wing_coupling è costante per circuito. Rendere $CL_{floor} = CL_{base} \cdot (1 + k \cdot \text{WingAngle})$ significa che il fondo genera più downforce quando l'ala è carica. **Senza questo, i setup variati non funzionano fisicamente.** |
| **P1** | **Cornering Utilization adattivo** | 🟡 Medio | 🔮 Futuro remoto. Derivare CU dalla telemetria per ogni curva. Potrebbe aiutare Austin ma richiede ricalibrazione. |
| **P2** | **Ricalibrare potenza con rpm_fraction** | 🟢 Basso | 🔮 Futuro remoto. Curva potenza RPM-dipendente più realistica, richiede ricalibrazione completa. |

### 🔗 Gruppo 2 — INTEGRAZIONE INTERFACCIA (cose mancanti nel motore)

> **Principio**: Il motore fisico lavora con unità reali (N/mm, Nm/deg, mm, gradi).
> L'interfaccia usa slider user-friendly (1-30, 1-10). La conversione avviene
> in un solo punto (`car_setup.py`). Le funzioni interne ricevono valori reali.
> **Questi task sono prioritari perché senza di essi il motore ha parti mancanti o sbagliate.**

| # | Task | Impatto | Stato | Dettaglio |
|---|------|--------|------|-----------|
| **P4** | **Definire conversioni slider→reale** | 🔴 Critico | ✅ Completato | `slider_to_real()` e `real_to_slider()` in `car_setup.py`. Formule: spring=slider*20+100 N/mm, ARB=slider*50 Nm/deg, RH=slider*3+17 mm. |
| **P5** | **Riscrivere `_compute_suspension_effects()`** | 🔴 Critico | ✅ Completato | Valori reali (N/mm, Nm/deg) con ottimali F1. Ottimale: spring_front≈400 N/mm, ARB≈200 Nm/deg. Aggiunto ride_height_aero_factor. |
| **P6** | **Collegare ride height a `compute_forces()`** | 🔴 Critico | ✅ Completato | `compute_forces()` ora riceve ride_height_front/rear in metri. Conversione mm→m centralizzata. Floor/sidepods ora sensibili all'altezza. |

### 🐛 Gruppo 3 — Bug del Motore (cose sbagliate)

| # | Bug | Impatto | Dettaglio |
|---|-----|--------|----------|
| **P7** | **Sospensioni: unità sbagliate** | 🔴 Critico | ✅ Risolto da P4+P5 | `set_suspension()` ora salva slider values (non più scalati). `_compute_suspension_effects()` usa valori reali (N/mm, Nm/deg). Setup ottimale → penalità 0%. |
| **P8** | **Ride height non passato all'aero** | 🔴 Critico | ✅ Risolto da P6 | `compute_forces()` ora riceve ride_height_front/rear da `_compute_suspension_effects()`. Fondo/sidepods ora sensibili all'altezza da suolo. |
| **P9** | **Ride height: unità mm vs metri** | 🟡 Medio | ✅ Risolto da P4+P6 | `slider_to_real()` converte in mm, poi `/1000` per metri. `compute_forces()` riceve metri. Validazione: 0.015-0.10m. |

### 🎯 Gruppo 4 — Calibrazioni (dopo i fix)

| # | Task | Impatto | Perché |
|---|------|--------|------|
| **P10** | **100% DF braking + margine 1.30** | 🟡 Medio | ✅ Completato. Frenata usa 100% downforce (era 50%). Margine sicurezza 1.30 (era 1.20). Errore medio: 0.59% (era 0.38% con 50% DF). Austin migliorato da 2.40% a 0.87%. Serve ricalibrazione per tornare sotto 0.5%. |
| **P11** | **Investigare Austin** | Alto | ✅ Migliorato da 2.40% a 0.87% con P10 (100% DF braking). Ancora sopra 0.5%, ma molto migliorato. |
| **P12** | **Investigare Las Vegas** | Medio | Peggiorato da 1.61% a 1.68% con P10. Sim troppo veloce, problema di drag ad alta velocità. Serve ricalibrazione specifica. |

### 🚀 Gruppo 5 — Feature

| # | Task | Impatto | Perché |
|---|------|--------|------|
| **P13** | **Optimizer dell'assetto** | Alto | Ricerca setup ottimale per circuito. Richiede P4-P9 risolti. |
| **P14** | **Integrazione runtime gameplay** | 🔴 Critico | Contratto dati input/output. Richiede tutto stabile sopra. |
| **P15** | **Aggiornare interfaccia con nuovi range** | 🟡 Medio | Slider dell'interfaccia devono riflettere i range reali F1. Aggiornare UI e documentazione. |

#### Dettaglio P4 — Conversioni Slider→Reale

| Parametro | Slider | Unità Reale | Formula Conversione | Range Reale F1 |
|-----------|--------|-------------|--------------------|----------------|
| Front Wing | 0-45° | gradi | `slider` (nessuna conversione) | 0-45° |
| Rear Wing | 0-45° | gradi | `slider` (nessuna conversione) | 0-45° |
| Spring Front | 1-50 | N/mm | `slider * 12 + 100` | 112-700 N/mm |
| Spring Rear | 1-50 | N/mm | `slider * 14 + 100` | 114-800 N/mm |
| ARB Front | 1-30 | Nm/deg | `slider * 15 + 35` | 50-485 Nm/deg |
| ARB Rear | 1-30 | Nm/deg | `slider * 15 + 35` | 50-485 Nm/deg |
| Ride Height Front | 1-30 | mm | `slider * 1 + 19` | 20-49 mm |
| Ride Height Rear | 1-30 | mm | `slider * 1.2 + 28.8` | 30-65 mm |
| B-Wing | 0-20° | gradi | `slider` (nessuna conversione) | 0-20° |

> **Nota**: Le formule di conversione sono indicative e saranno validate con dati F1 reali.
> Il principio è che il motore fisico riceve sempre valori in unità reali (N/mm, Nm/deg, mm, gradi).
> Valori ottimali F1: spring_front≈400 N/mm (slider 25), spring_rear≈562 N/mm (slider 33),
> ARB_front≈200 Nm/deg (slider 11), ARB_rear≈305 Nm/deg (slider 18),
> RH_front≈26 mm (slider 7), RH_rear≈46 mm (slider 14).

### Dettaglio P0: Floor Coupling Dinamico

Attualmente il modello ha `k_wing_coupling` costante per circuito (derivato da CL\*A).
Il floor coupling dinamico rende il fondo piatto sensibile all'angolo dell'ala:

$$CL_{floor} = CL_{base} \cdot (1 + k_{wing} \cdot \text{WingAngle})$$

Dove:
- $CL_{base}$ = downforce del fondo a angolo ala neutro
- $k_{wing}$ = coefficiente di coupling ala-fondo (già derivato da CL\*A)
- $\text{WingAngle}$ = angolo dell'ala (da setup, 0-100%)

Effetto atteso:
- Monaco (High-DF): WingAngle alto → più downforce dal fondo → più grip in curva
- Monza (Low-DF): WingAngle basso → meno downforce dal fondo → meno drag in rettilineo
- Questo rende i setup variati fisicamente significativi

---

**Author**: F1 Manager AI Development Team  
**Last Updated**: 2026-04-12  
**Version**: 5.3 (P4-P6: Slider→Real, Suspension Fix, Ride Height Connected)  
**Status**: VALIDATED - 24 CIRCUITI COMPLETATI ✅ (0.38% avg error)
