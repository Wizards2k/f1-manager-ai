# V5.8 Setup Congruence — Root Cause

Il problema: V5.7 matcha 24/24 tempi di riferimento <0.5% error ma su 11/24 circuiti il motore fisico preferisce un setup a basso DF rispetto a quello calibrato. I tentativi di fix parametrico nella sessione del 2026-04-15 hanno fallito — il blocco è strutturale.

## Ipotesi iniziali (CONFUTATE)

1. ~~**Load sensitivity clamp troppo alto (0.75)**~~ — TESTATO: clamp 0.55 peggiora la congruenza da 18/24 a 8/24. Il clamp basso penalizza il setup CALIBRATO (più carico → più decay → mu ricalibrato +12%) mentre il low-DF subisce meno decay e vince ancora più nettamente. Solo Monza (già low-DF) resta congruente. **Il clamp NON è il root cause.**

2. **Dual import path bug** — Confermato: gli aero components vengono importati via due path diversi. `lap_simulator.physics_v4.aero.front_wing` (dai test/scripts) e `aero.front_wing` (waypoint_integrator.py via `sys.path.insert`). Python tratta questi come moduli distinti, creando due class object separati. Monkeypatch su uno NON ha effetto sull'altro. File edit funziona. **Lesson: usare sempre file edit, mai monkeypatch.**

3. ~~**Floor L/D troppo basso (3.15 vs reale F1 5-8)**~~ — Confermato numericamente ma il fix naive (K_floor → 0.06/0.05) rende high-DF ancora più attraente via wing-coupling. Il floor L/D basso è un sintomo, non la causa.

## Root Cause identificato: Cornering Utilization (CU)

La formula CU in [waypoint_integrator.py:1125](../python_backend/lap_simulator/physics_v4/integrator/waypoint_integrator.py#L1125):

```python
CU = min(0.95, 0.35 + radius_m / 150.0)
```

Questa formula assegna un utilizzo del grip laterale molto basso alle curve strette:
- r=10m (Monaco hairpin): CU=0.417 → solo il 42% del grip usato
- r=30m: CU=0.550 → solo il 55%
- r=50m: CU=0.683 → solo il 68%
- r=100m+: CU=0.950 → 95%

**Conseguenza:** l'extra downforce dell'high-DF viene sprecato nelle curve strette perché il pilota (modello) non lo usa. Il vantaggio in velocità di curva è minimo:

| Raggio | CU | Low DF v_max | High DF v_max | Diff |
|--------|-----|-------------|--------------|------|
| 10m | 0.417 | 31.3 kph | 32.7 kph | +1.4 kph |
| 30m | 0.550 | 62.3 kph | 65.1 kph | +2.9 kph |
| 100m | 0.950 | 149.5 kph | 156.3 kph | +6.9 kph |

A Monaco (curve r=10-50m), l'high-DF guadagna solo 1-4 kph in curva, ma perde 7 kph sul rettilineo (287 vs 280). Il bilancio è negativo.

**Perché il clamp 0.55 peggiora le cose:** con clamp 0.55, il grip decade di più ad alto carico. Il setup CALIBRATO (più DF) perde più grip → mu ricalibrato +12% per compensare → il low-DF (meno carico, meno decay) diventa ancora più competitivo.

## Altre ipotesi da investigare

1. **Drag totale sottostimato per low-DF** — Il low-DF non perde abbastanza tempo in curva sui circuiti tortuosi. Possibili cause:
   - CU troppo bassa (ipotesi principale)
   - Mancanza di penalità handling per setup sbilanciati
   - Wing-floor coupling che amplifica il low-DF invece che il calibrato

2. **v_ref ceiling — CONFERMATO come root cause su fast-sweep circuits (2026-04-16)** — L'ipotesi iniziale era sbagliata: v_ref è letto direttamente come `v_target_ms` a [waypoint_integrator.py:1154](../python_backend/lap_simulator/physics_v4/integrator/waypoint_integrator.py#L1154) e il grip fisico entra solo come CEILING a [line 1289](../python_backend/lap_simulator/physics_v4/integrator/waypoint_integrator.py#L1289) (`v_target = min(v_target, v_max_corner)`). Quando il grip è sufficiente a raggiungere v_ref (fast corners), la curva segue la telemetria e il downforce extra è pura perdita (drag senza upside).

   **Prova decisiva — Silverstone mu sensitivity sweep (2026-04-16):**
   | mu | LOW (16/20) | CAL (22/26) | HIGH (28/32) | winner |
   |---|---|---|---|---|
   | 1.0 | 87.53 | 87.80 | 88.89 | LOW (-0.27s) |
   | 1.56 | 84.32 | 85.03 | 86.26 | LOW (-0.71s) |
   | 2.5 | 83.42 | 83.91 | 85.61 | LOW (-0.49s) |
   | 4.0 | 83.01 | 83.51 | 84.92 | LOW (-0.50s) |
   | 8.0 | 82.60 | 83.16 | 85.09 | LOW (-0.56s) |

   LOW vince a **ogni** mu, il gap **non si chiude** aumentando il grip. A mu=8 la differenza LOW→HIGH è +2.48s: **pura drag penalty, zero beneficio curva**. Questo prova che sui fast-sweep circuits il grip non è il vincolo attivo — v_ref lo è.

3. **Aero balance penalty assente** — Non c'è penalità per aero_balance non ottimale. Un setup FW=28/RW=32 ha balance simile a FW=38/RW=42, quindi non paga penalità handling.

## Test V5.8 K_FACTOR=0.30/0.35 (2026-04-16) — PARZIALE

Riduzione K wings per aumentare L/D marginale (da AI analysis):
- **3-circuiti preference test**: 2/3 ✅ — Monaco passa da ❌ a ✅ (K fix funziona sui slow-corner circuits)
- **24-circuiti preference test (uncalibrated)**: 10/24 — peggio di V5.7 baseline (13/24)
- **Silverstone**: gap LOW-CAL invariato (-0.706s, identico al baseline) — K non tocca il problema

**Conclusione bipartizione dei circuiti:**
- **Slow-corner circuits** (Monaco, forse Singapore, Budapest): grip è attivo nei tornanti stretti, K_FACTOR reduction aiuta. Fix parametrico sufficiente.
- **Fast-sweep circuits** (Silverstone, Suzuka, Spa, Zandvoort, Austin, Melbourne, Montreal, Sao Paulo, Mexico, Imola): v_ref ceiling blocca il beneficio downforce nelle curve veloci. **Fix parametrico IMPOSSIBILE** — serve cambio architetturale al corner model.

Il test 24-circuiti peggiora perché il K più basso rende il floor relativamente troppo efficiente e alcuni low-DF circuits (monza, baku, las_vegas, sakhir) iniziano a preferire high-DF. Il K sbagliato non è 0.30/0.35 — è che **non esiste un K che risolva entrambi i tipi di circuito**.

## V5.8 Quartic Aero Model (stato attuale)

Il modello quartico (CD = CD_MIN + K₂·CL² + K₃·CL³ + K₄·CL⁴) è implementato e calibrato:
- Front Wing: K₂=0.4335, K₃=-0.1591, K₄=0.0417 → L/D: 5.0→3.1→2.2
- Rear Wing: K₂=0.5007, K₃=-0.2384, K₄=0.0823 → L/D: 3.9→2.8→1.9
- Congruence: 18/24 (vs 13/24 V5.7) — miglioramento significativo ma non risolutivo
- Calibrazione: 24/24 < 0.30% error

I 6 circuiti non congruenti rimanenti (Baku, Las Vegas, Sakhir, Monaco, Singapore, Zandvoort) sono bloccati dalla CU formula, non dal modello aero.

## Prossimi passi (aggiornati 2026-04-16)

Il root cause architetturale è ora chiaro: **il corner model è telemetry-driven, non physics-driven**. La linea [1154](../python_backend/lap_simulator/physics_v4/integrator/waypoint_integrator.py#L1154) legge `v_target_ms = v_ref_kph / 3.6` e la linea [1289](../python_backend/lap_simulator/physics_v4/integrator/waypoint_integrator.py#L1289) applica il grip solo come `min(v_target, v_max_corner)`. Questo garantisce che lap time matchi la telemetria ma disaccoppia setup → corner speed su tutti i fast corners.

### Opzioni di fix (in ordine di invasività crescente)

1. **Accettare V5.7 come baseline** — 13/24 congruenti, 0.17% lap time error. Il fix K=0.30/0.35 NON è un miglioramento su scala 24 (10/24 uncalibrated). **Non applicare il K fix senza un fix architetturale parallelo.**

2. **Rimuovere v_ref ceiling nei soli fast corners** — aggiungere al [waypoint_integrator.py:1289](../python_backend/lap_simulator/physics_v4/integrator/waypoint_integrator.py#L1289) una logica del tipo:
   ```python
   # Se grip permette più di v_ref, allow up to v_max_corner (capped a v_ref * 1.10)
   if v_max_corner_ms > v_ref_ms and radius_m > 150:  # solo fast corners
       v_target_ms = min(v_max_corner_ms, v_ref_ms * 1.10)
   else:
       v_target_ms = min(v_target_ms, v_max_corner_ms)
   ```
   **Rischio:** rompe la calibrazione lap time di tutti i 24 circuiti. Serve ricalibrazione completa mu + reference_pull_strength.

3. **Modello corner fully physics-driven** — rimuovere v_ref come target e usare solo `v_max_corner_ms`. Questo richiede:
   - Calibrazione nuova di mu_mechanical, max_lateral_g, CU per ogni circuito
   - Sistema di reference_pull per tenere ancorato il lap time al riferimento
   - Validation completa su 24 circuiti
   - **Effort: 2-3 sessioni dedicate.**

### Raccomandazione

**Mantenere V5.7 come baseline funzionante.** Il fix congruenza è un cambio architetturale non-banale che richiede una sessione dedicata con un budget di test esteso. Il K_FACTOR tweak dell'AI è un sub-problema parziale (Monaco-type circuits) e non va applicato isolatamente perché regredisce i low-DF circuits.

Il documento corrente deve restare come riferimento per la prossima sessione dedicata al fix architetturale.
