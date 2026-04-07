---
title: Physics Engine V4 - Checklist Operativa
date: 2026-04-07
version: 1.2
status: WORKING CHECKLIST - MONZA Q PROSSIMO AL TARGET (LOOKAHEAD DINAMICO)
---

# Physics Engine V4 — Checklist Operativa

Questa checklist è la versione eseguibile della spec V4.
Serve per sapere, in ogni momento:
- cosa è già pronto;
- cosa va verificato prima di toccare il runtime;
- cosa manca per calibrazione, ottimizzazione e integrazione.

Riferimento principale:
- `docs/physics-engine-v4-spec.md`

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
- [ ] Telemetria di riferimento disponibile per il circuito target.

### Sessione
- [ ] Sessione impostata correttamente (`qualifying`, `race`, `practice`).
- [ ] Fuel e ERS coerenti con il tipo sessione.
- [ ] Driver skill applicata in modo consistente.
- [ ] `push_level` impostato esplicitamente per la baseline Q.
- [ ] `engine_map` impostata esplicitamente per la baseline Q.
- [ ] `ers_mode` impostata esplicitamente per la baseline Q.

## 2. Calibrazione circuito-per-circuito

### Baseline dati
- [ ] Telemetria reale acquisita per Monza.
- [ ] Telemetria reale acquisita per Monaco.
- [ ] Telemetria reale acquisita per Suzuka.
- [ ] Parametri di partenza versionati.
- [ ] Fonte dati annotata nel file di calibrazione.

### Metriche da verificare
- [ ] Lap time totale.
- [ ] V max.
- [ ] V min.
- [ ] Sector times.
- [ ] Profilo velocità per tratto.
- [ ] Coerenza frenata / accelerazione.
- [ ] Coerenza grip / cornering.

### Criteri di buon fit
- [ ] Il lap time è vicino al target.
- [ ] La V max non è “corretta per caso” ma fisicamente giustificata.
- [ ] La V min nelle curve chiave è credibile.
- [ ] Un setup più carico migliora le curve.
- [ ] Un setup più scarico migliora i rettilinei.
- [ ] Il risultato resta deterministico su run ripetuti.

### Checklist di calibrazione pratica
- [x] Provare variazioni su `mu_override` → **Effetto confermato sui corner (sec_02, sec_10, sec_12)**.
- [x] Provare variazioni su `aero_calibration` (drag_index, downforce_index) → **Effetto confermato su tutti i settori**.
- [ ] Provare variazioni su `max_brake_decel_g_override` → Da verificare con nuovo reference_pull.
- [ ] Provare variazioni su `max_lateral_g_override` → Da verificare con nuovo reference_pull.
- [x] Salvare la combinazione migliore per circuito → **Candidate: drag=1.94, downforce=1.28, mu=2.10** (4 settori ancora sopra soglia).
- [x] Documentare il perché del best fit → **Il compromesso aero globale è più stabile delle scale per-sezione**.
- [x] Separare override temporanei da baseline valide → `circuit_calibration.py` pronto per i profili versionati.

### Benchmark guida: Monza Q e validazione fisica
- [x] Il target finale è simulare un giro di Monza in assetto da qualifica con parametri fisici coerenti.
- [x] La baseline è fissata su McLaren + Lando Norris + `qualifying` + `C5`.
- [x] `push_level`, mappa ICE ed ERS mode sono inclusi in modo esplicito nel benchmark.
- [x] La telemetria di riferimento viene confrontata sui 13 microsettori oltre che sul lap time totale.
- [x] Tutti i microsettori devono restare entro un margine relativo massimo del 2% rispetto alla telemetria.
- [x] Il benchmark serve sia a misurare la distanza dalla telemetria sia a validare la risposta fisica del motore.
- [ ] **Current status**: Lap time Monza a -0.58s con errore max 9.94% nel sec_02. Frenata gestita 100% fisicamente con look-ahead dinamico basato esclusivamente su `v^2/2a`.
- [ ] **Manca**: Aggiungere un margin/buffer al pilota sulla staccata perfetta della macchina per dissipare quell'ultimo mezzo secondo di anticipo surreale.

### Parametri congelati nel baseline
- [ ] `circuit_id = it-1922_monza`.
- [ ] Team e driver risolti in modo deterministico.
- [ ] `fuel`, massa, aero setup, sospensioni, brake bias e compound definiti.
- [ ] `push_level = 10`.
- [ ] `engine_map = QUALIFY`.
- [ ] `ers_mode = OVERTAKE`.

### Sweep di sensibilità minima
- [ ] Ali: front / rear wing con perturbazioni piccole e controllate.
- [ ] Sospensioni: più rigide vs più morbide.
- [ ] Ride height: più basso vs più alto.
- [ ] Massa / fuel: step controllati sopra e sotto il baseline.
- [ ] Power unit: mappe più conservative vs più aggressive.
- [ ] Driver push: 8, 9 e 10.
- [ ] Gomme: C3, C4 e C5.

### Metriche e criteri di validazione
- [ ] Lap time totale.
- [ ] Errore per microsettore con vincolo `<= 2%` su ogni microsettore.
- [ ] Profilo velocità per tratto.
- [ ] Coerenza fisica delle differenze.
- [ ] Monotonicità delle risposte sotto perturbazione.
- [ ] Nessuna inversione del comportamento atteso tra setup migliore e setup errato.

## 3. Optimizer dell’assetto

### Obiettivo
- [ ] Dato `circuit + auto + driver + target telemetry`, trovare il setup che minimizza la loss.

### Variabili da includere nella ricerca
- [ ] Ali anteriori.
- [ ] Ali posteriori.
- [ ] Ride height.
- [ ] Rigidezza sospensioni.
- [ ] Brake bias.
- [ ] Duct cooling.
- [ ] Tyre compound.
- [ ] Pressure anteriori / posteriori.
- [ ] Fuel load.
- [ ] ERS mode.

### Funzione costo
- [ ] Lap time error.
- [ ] Sector time error.
- [ ] Speed trace error.
- [ ] Penalità gomme fuori finestra.
- [ ] Penalità freni fuori finestra.
- [ ] Penalità instabilità / bottoming.
- [ ] Penalità uso ERS inefficiente.

### Output atteso
- [ ] Ranking delle configurazioni.
- [ ] Best fit esportato.
- [ ] Parametri del best fit salvati.
- [ ] Risultato ripetibile con seed uguale.

## 4. Validazione e QA

### Circuiti di riferimento
- [ ] Monza.
- [ ] Monaco.
- [ ] Suzuka.

### Test minimi
- [ ] Il giro si completa senza errori.
- [ ] I tempi prodotti sono stabili tra esecuzioni.
- [ ] Le differenze setup si riflettono nel comportamento.
- [ ] Il motore non dipende da hack empirici non documentati.
- [ ] Le metriche di telemetria sono esportate in modo leggibile.

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
- [ ] L’input del motore è documentato.
- [ ] L’output del motore è documentato.
- [ ] Il fallback è definito se mancano dati.
- [ ] Il determinismo tra sessioni è verificato.

### Punti da non rompere
- [ ] Il runtime di gioco non deve dipendere da campi impliciti.
- [ ] La UI non deve essere la fonte di verità della fisica.
- [ ] La simulazione non deve introdurre side effect non tracciati.
- [ ] Ogni cambiamento del setup deve riflettersi in modo misurabile.

### Pronto per l’integrazione quando
- [ ] Il contratto input/output è stabile.
- [ ] I circuiti reference sono validati.
- [ ] Il mapping tra auto reale e motore è chiaro.
- [ ] Esistono fallback per dati incompleti.

## 6. Manutenzione della documentazione

- [ ] Aggiornare questa checklist quando cambia il contratto dati.
- [ ] Aggiornare questa checklist quando cambia la loss function.
- [ ] Aggiornare questa checklist quando cambia la calibrazione per circuito.
- [ ] Aggiornare questa checklist quando cambia l’output dell’integratore.
- [ ] Allineare questa checklist alla spec V4 dopo ogni revisione importante.

## 7. Stato attuale sintetico (2026-04-07)

### Già pronto
- [x] Core fisico base.
- [x] Aero componenti.
- [x] Massa / CG / inerzia.
- [x] Sospensioni.
- [x] Power Unit.
- [x] Tyres.
- [x] Brakes.
- [x] Driver model.
- [x] Vehicle dynamics.
- [x] Setup translation.
- [x] Waypoint integrator.
- [x] **Benchmark Monza Q baseline stabilito** (McLaren + Norris, C5, push=10, QUALIFY mode).
- [x] **Analisi microsettori completata** - identificati i 4 microsettori critici (sec_05, sec_08, sec_10, sec_12).

### In corso
- [ ] **Calibrazione finale Monza Q** - Ottimizzazione completata per il modello di guida puro. Rimosso reference_pull come proxy empirico, introdotto frenata 100% fisica calcolata sulle capacità della monoposto.
  - Lap time attuale: -0.58s di delta con margini per i microsettori inferiori al 10% senza usare shortcut o teletrasporto matematico.
  - Da aggiungere: `driver_safety_margin` per mitigare la perfetta decelerazione macchina.
- [ ] Baseline versionate.
- [ ] Optimizer setup.
- [ ] Harness QA definitivo.
- [ ] Integrazione runtime completa.

### Da tenere sotto controllo
- [ ] Rischio overfitting su un circuito singolo.
- [ ] Distanza tra lap time corretto e telemetria fisicamente corretta.
- [ ] Coerenza tra assetto e comportamento in pista.
- [ ] Stabilità dei risultati nel tempo.
- [ ] **Trade-off aero/downforce/mu** - Aumentare mu migliora i corner ma li rende troppo veloci; serve trovare il punto di equilibrio esatto.
- [ ] **section_speed_scales rimosse** - Il meccanismo non aveva effetto sui tempi dei microsettori; calibrazione ora puramente globale.
