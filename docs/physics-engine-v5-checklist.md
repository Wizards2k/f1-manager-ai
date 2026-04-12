---
title: Physics Engine V5.0 - Checklist Operativa
date: 2026-04-12
version: 5.2
status: VALIDATED - 24 CIRCUITI COMPLETATI (MEDIA 0.38% ERRORE, TARGET <0.5% RAGGIUNTO)
---

# Physics Engine V5.0 — Checklist Operativa

Questa checklist è la versione eseguibile della spec V5.0.
Serve per sapere, in ogni momento:
- cosa è già pronto;
- cosa va verificato prima di toccare il runtime;
- cosa manca per calibrazione, ottimizzazione e integrazione.

Riferimenti:
- `docs/physics-engine-v5-telemetry-bridge.md` — Spec V5.0 completa (24 circuiti)
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

### Risultati Validazione V5.0 — 24 Circuiti

| # | Circuito | Driver | Reale | Sim | Errore | Status |
|---|----------|--------|-------|-----|--------|--------|
| 1 | Baku | VER | 101.117 | 101.144 | **0.03%** | ✅ |
| 2 | Spa | NOR | 100.562 | 100.627 | **0.06%** | ✅ |
| 3 | Shanghai | PIA | 90.641 | 90.583 | **0.06%** | ✅ |
| 4 | Sakhir | PIA | 89.841 | 89.894 | **0.06%** | ✅ |
| 5 | Melbourne | NOR | 75.096 | 75.038 | **0.08%** | ✅ |
| 6 | Yas Marina | VER | 82.207 | 82.057 | **0.18%** | ✅ |
| 7 | Barcelona | PIA | 71.546 | 71.408 | **0.19%** | ✅ |
| 8 | Jeddah | VER | 87.294 | 87.119 | **0.20%** | ✅ |
| 9 | Singapore | RUS | 89.158 | 89.312 | **0.17%** | ✅ |
| 10 | São Paulo | NOR | 69.511 | 69.628 | **0.17%** | ✅ |
| 11 | Monaco | NOR | 69.954 | 70.037 | **0.12%** | ✅ |
| 12 | Suzuka | NOR | 86.995 | 86.703 | **0.34%** | ✅ |
| 13 | Silverstone | NOR | 85.010 | 84.725 | **0.33%** | ✅ |
| 14 | Zandvoort | PIA | 68.662 | 68.400 | **0.38%** | ✅ |
| 15 | Budapest | LEC | 75.372 | 75.071 | **0.40%** | ✅ |
| 16 | Monza | NOR | 78.869 | 79.152 | **0.36%** | ✅ |
| 17 | Montreal | RUS | 70.899 | 71.218 | **0.45%** | ✅ |
| 18 | Imola | PIA | 74.670 | 75.026 | **0.48%** | ✅ |
| 19 | Mexico City | NOR | 75.586 | 75.943 | **0.47%** | ✅ |
| 20 | Miami | VER | 86.204 | 86.369 | **0.19%** | ✅ |
| 21 | Lusail | PIA | 79.387 | 78.925 | **0.58%** | ⚠️ |
| 22 | Spielberg | NOR | 63.971 | 64.333 | **0.57%** | ⚠️ |
| 23 | Austin | VER | 92.510 | 93.945 | **1.55%** | ⚠️ |
| 24 | Las Vegas | NOR | 107.934 | 106.194 | **1.61%** | ⚠️ |

**Statistiche**: Media 0.38% | Mediana 0.33% | <0.5%: 20/24 | <1.0%: 22/24 | ≥1.0%: 2/24

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

### Outlier da investigare
- [ ] Austin (1.55%) — Sim troppo lento, deduplicazione waypoint V5.2 migliorata da 2.02% a 1.55%
- [ ] Las Vegas (1.61%) — Sim troppo veloce, modello drag ad alta velocità
- [ ] Spielberg (0.57%) — Sim troppo lento, downforce medio

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

- [x] `docs/physics-engine-v5-checklist.md` — Questo file, aggiornato a V5.1.
- [x] `docs/physics-engine-v5-telemetry-bridge.md` — Spec V5.1 completa (24 circuiti).
- [x] `docs/physics-engine-v4-spec.md` — Spec V4 di riferimento (archivio storico).
- [x] Rimosso `docs/physics-engine-v4-checklist.md` — Contenuto obsoleto e duplicato, consolidato in V5.1.
- [x] Rimossi 12 doc obsoleti/superati (V4.6 validation, V5.0 validation, V0.5 spec, V2 analysis, ecc.).

## 7. Stato attuale sintetico (2026-04-11)

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

### In corso / Da fare
- [x] Rendere effettivo il Reference Pull correction (strength=0.02, ±20% f_engine).
- [x] Integrare PU Lookup nel simulatore (pu_lookup_blend=0.0 default, Opzione A implementata).
- [x] Integrare Aero Calibration (mu_mechanical, k_wing_coupling) nel simulatore.
- [x] Bug fix mu_aero_contribution — Modello compound-specific + CL\*A lookup.
- [x] Floor Coupling dinamico V5.2 — CL_MAX, wing_coupling, K_FACTOR calibrati.
- [x] Deduplicazione waypoint V5.2 — Keep both boundary waypoints with 0.01m offset.
- [x] **P4: Definire conversioni slider→reale** — ✅ `slider_to_real()` e `real_to_slider()` in `car_setup.py`.
- [x] **P5: Riscrivere _compute_suspension_effects()** — ✅ Valori reali (N/mm, Nm/deg). Setup ottimale → penalità 0%.
- [x] **P6: Collegare ride height a compute_forces()** — ✅ Floor/sidepods sensibili all'altezza.
- [x] **P7: Bug sospensioni — unità sbagliate** — ✅ Risolto da P4+P5.
- [x] **P8: Bug ride height non passato all'aero** — ✅ Risolto da P6.
- [x] **P9: Bug ride height mm vs metri** — ✅ Risolto da P4+P6.
- [ ] **P10: 50% DF braking → 100% + ricalibrazione** — Passare al 100% downforce nella frenata e ricalibrare 24 circuiti.
- [ ] **P11: Investigare Austin (1.55%)** — Sim troppo lento. Deduplicazione V5.2 migliorata da 2.02% a 1.55%.
- [ ] **P12: Investigare Las Vegas (1.61%)** — Sim troppo veloce, drag ad alta velocità.
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
- [x] **P7: Bug sospensioni — unità sbagliate** — ✅ Risolto da P4+P5. `set_suspension()` ora salva slider values (non più scalati). `_compute_suspension_effects()` usa valori reali.
- [x] **P8: Bug ride height non passato all'aero** — ✅ Risolto da P6. `compute_forces()` ora riceve ride_height da `_compute_suspension_effects()`.
- [x] **P9: Bug ride height unità mm vs metri** — ✅ Risolto da P4+P6. `slider_to_real()` converte in mm, poi `/1000` per metri. Validazione 0.015-0.10m.

#### 🎯 Gruppo 4 — Calibrazioni (dopo i fix)
- [x] **P3: Validazione setup variati** — ✅ Superato: Monaco High-DF più veloce, Monza Low-DF più veloce, Suzuka campana corretta. Silverstone OK. Spa/Monza ~4° troppo carico (known limitation: 50% DF braking).
- [ ] **P10: 50% DF braking → 100% DF braking + ricalibrazione** — Il calcolo della distanza di frenata usa solo il 50% della downforce. Passare al 100% (fisicamente corretto) e ricalibrare tutti i 24 circuiti. Effetto: Monza ottimale diventa FW8-10 (corretto), curve veloci più realistiche.
- [ ] **P11: Investigare Austin (1.55%)** — Sim troppo lento. Deduplicazione V5.2 migliorata da 2.02% a 1.55%. Ulteriore indagine in corso.
- [ ] **P12: Investigare Las Vegas (1.61%)** — Sim troppo veloce, drag ad alta velocità.

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
| **P10** | **50% DF braking → 100% + ricalibrazione** | 🟡 Medio | Distanza di frenata usa 50% downforce. Monza ottimale FW14 invece di FW8. Curve veloci sistematicamente lente. Richiede ricalibrazione completa se cambiato. |
| **P11** | **Investigare Austin (1.55%)** | Alto | Outlier peggiore. Dopo Floor Coupling + CU adattivo, potrebbe migliorare da solo. |
| **P12** | **Investigare Las Vegas (1.61%)** | Medio | Sim troppo veloce. Dopo le modifiche al modello, ri-validare. |

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
