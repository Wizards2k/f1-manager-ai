---
title: Tyre Thermal Engine Refactor Roadmap (Strada A)
last_updated: 2026-03-10
status: draft
scope: lap simulator, tyre thermal model, staged refactor
---

## 1. Obiettivo

Questo documento definisce la roadmap tecnica per il refactor **Strada A** del motore termico gomme.

Scopo del refactor:
- correggere i limiti strutturali dell'attuale `tyre_model.py` senza riscrivere subito tutto il blocco termico;
- mantenere la compatibilità con l'API attuale di `_update_single_tyre()`;
- intervenire prima su **heat generation** e **cooling**, lasciando inizialmente invariata la parte di grip, wear ed eventi;
- validare il nuovo comportamento con gli scenari già usati su **Suzuka** e **Hungaroring**.

Questa roadmap prende come riferimento:
- `docs/TyreModel.md`
- `docs/degradation-and-consumption.md`
- `docs/brake-integration.md`
- `docs/brake-integration-gemini.md`
- `config/tyres/tyre_params_global_default.json`
- `config/circuits/derived/<circuit>/tyre_params.json`
- `config/circuits/derived/<circuit>/brake_params.json`
- `python_backend/data/circuits/2025/*_Telemetry.json`

## 2. Problemi del modello attuale

L'analisi runtime/log ha evidenziato questi problemi principali:

### 2.1 Rear heat runaway

Il rear usa una cascata di moltiplicatori:
- `axis_multiplier`
- `traction_multiplier`
- `rear_instability_multiplier`

Questo produce un'escalation troppo aggressiva soprattutto negli scenari oversteer e su piste con poco recupero termico.

### 2.2 Rapporto heat/cooling sbilanciato in curva

Nelle sezioni di cornering il cooling è spesso troppo basso rispetto al calore generato.
Il risultato è un accumulo netto quasi costante, poi compensato artificialmente nei rettilinei.

### 2.3 Straight cooling troppo compensativo

L'attuale `straight_cooling_multiplier` svolge un ruolo troppo grande nel mantenere le temperature sotto controllo, soprattutto su Suzuka.
Questo rende il modello fragile e poco trasferibile ad altri circuiti.

### 2.4 Brake-to-tyre coupling troppo semplice

Il front tyre heating da frenata è trattato quasi interamente come:
- `braking_energy_mj * coeff`

Manca una distinzione tra:
- energia frenante diretta sulla gomma in ingresso curva;
- trasferimento termico da disco/cerchio verso la gomma;
- effetto reale dell'apertura `brake_duct`.

### 2.5 Uso incompleto dei dati disponibili per sezione

Il runtime usa già `heat_factor`, `cool_factor`, `braking_energy_mj`, `dt_s`, `v_kph`, ma il budget termico resta troppo semplificato.
Non c'è ancora una vera costruzione energetica per sezione basata sulla severità reale del tratto.

## 3. Obiettivi della Strada A

La Strada A non riscrive subito l'intero thermal block.
Interviene in modo progressivo e controllato.

### 3.1 Cosa cambia
- rifattorizzazione del blocco **heat generation**;
- rifattorizzazione del blocco **cooling**;
- riduzione dell'accoppiamento improprio tra handling e heat generation;
- miglior uso dei segnali per sezione e dei dati brake-related.

### 3.2 Cosa non cambia nel primo step
- firma di `_update_single_tyre()`;
- struttura pubblica di `update_tyres()`;
- calcolo di `wear_rate`;
- calcolo di `effective_grip`;
- warning ed eventi (`tyre_overheat`, `tyre_blistering`, ecc.);
- parametri compound già caricati dal circuito.

### 3.3 Obiettivo di validazione
Ottenere un modello che:
- mantenga il ranking qualitativo tra `green`, `understeer`, `oversteer`;
- riduca il rear runaway;
- non dipenda eccessivamente dal bonus di cooling nei rettilinei;
- sia più credibile su piste diverse, in particolare Suzuka e Hungaroring.

## 4. Principi fisici del refactor

## 4.1 Heat generation come somma di contributi

Il nuovo `heat_gen_total` deve essere costruito come somma di contributi distinti:
- `cornering_heat`
- `braking_heat`
- `traction_heat`
- `instability_heat`

Obiettivo:
- eliminare lo stacking eccessivo di moltiplicatori in cascata;
- rendere leggibile e calibrabile ogni sorgente;
- facilitare debug e tuning.

## 4.2 Handling come modulatore, non motore principale del calore

`understeer_level` e `oversteer_level` devono restare nel modello, ma come contributi moderati.

Principio:
- l'handling altera il carico termico;
- non deve diventare il principale responsabile del livello assoluto di temperatura.

## 4.3 Cooling sempre attivo, rettilinei solo come recovery boost moderato

Il cooling deve esistere in tutte le sezioni.
I rettilinei devono migliorare il recupero termico, ma senza svolgere il ruolo di “salvataggio” del modello.

## 4.4 Brake heat più vicino ai dati reali disponibili

Il calore front deve dipendere meglio da:
- `braking_energy_mj`
- brake temperature / brake state
- effetto `brake_duct`
- criticità della sezione

## 4.5 Surface e core non devono dipendere da un solo canale termico

La validazione contro `docs/TyreModel_Thermal_Gemini` ha confermato che il modello deve distinguere meglio:
- calore superficiale da attrito/slip;
- calore di carcassa (`bulk/core`) da deformazione e isteresi;
- raffreddamento più rapido della surface rispetto al core nei rettilinei.

Indicazioni progettuali:
- il `core` non deve scaldarsi solo per conduzione dalla `surface`;
- serve un contributo diretto, piccolo ma esplicito, di **bulk hysteresis heat**;
- il contributo deve crescere soprattutto con velocità e massa carburante (inerzia) e restare moderato nelle sezioni a bassa severità;
- il logging deve mostrare il nuovo termine per calibrazione (flag `TYRE_DEBUG`).

Stato: fase introduttiva implementata nel refactor fuel-aware (Mar 2026) con termine conservativo sul core. Ulteriori raffinamenti (camber/toe, distribuzione inner/outer) restano fuori scope di questa fase.

## 5. Nuova struttura concettuale del blocco termico

## 5.1 Section load

Per ogni sezione introdurre un concetto di severità energetica che combini:
- `section.heat_factor`
- `dt_s`
- `v_kph` o `avg_speed`
- contesto curva/rettilineo

Questo non richiede nuove API pubbliche, ma serve a costruire contributi più coerenti internamente.

## 5.2 Front heat budget

Per l'asse anteriore:
- `cornering_heat_front`
- `braking_heat_front`
- `understeer_heat_front` (moderato)

Indicazione progettuale:
- `braking_heat_front` resta importante;
- `understeer_heat_front` deve cambiare il ranking, non dominare tutto il budget.

## 5.3 Rear heat budget

Per l'asse posteriore:
- `cornering_heat_rear`
- `traction_heat_rear`
- `oversteer_heat_rear` (moderato)
- `mech_instability_heat_rear` (piccolo, se necessario)

Indicazione progettuale:
- niente prodotto di tre moltiplicatori successivi;
- preferire contributi additivi o un solo moltiplicatore globale leggero.

## 5.4 Cooling budget

Rifattorizzare il cooling in componenti leggibili:
- `base_convective_cool`
- `straight_recovery_bonus`
- `duct_cooling_factor`
- eventuale `low_push_cooling_bonus`

Obiettivo:
- tenere la forma fisica coerente con la spec;
- ridurre l'attuale dipendenza dal bonus rettilineo.

## 6. Fasi di implementazione

## Fase 1 — Refactor heat generation

### Intervento
Sostituire l'attuale schema con una costruzione esplicita di:
- `cornering_heat`
- `braking_heat`
- `traction_heat`
- `instability_heat`

### Linee guida
- front e rear devono avere budget separati ma simmetricamente leggibili;
- `rear_instability_multiplier` non deve più moltiplicare in cascata l'intero heat budget;
- `traction_heat` deve essere attivo soprattutto nei corner lenti e medi;
- `instability_heat` deve restare contenuto.

### Obiettivo
- ridurre il rear runaway senza rompere il ranking qualitativo.

## Fase 2 — Refactor cooling

### Intervento
Rivedere:
- `convective_cool_raw`
- `straight_cooling_multiplier`

### Linee guida
- il cooling in curva deve restare fisicamente significativo;
- il bonus sui rettilinei deve essere presente ma meno “salvifico”;
- se possibile introdurre un piccolo coupling con `brake_duct`.

### Obiettivo
- evitare che il modello sopravviva solo grazie alle sezioni straight.

## Fase 3 — Brake-to-tyre coupling più pulito

### Intervento
Separare concettualmente:
- brake contact heat
- brake-to-rim / brake-to-tyre transfer

### Linee guida
- non serve ancora una simulazione completa della ruota interna;
- basta introdurre una distinzione pulita che renda il front heating più credibile;
- usare `braking_energy_mj`, brake state e `brake_duct` come segnali principali.

### Obiettivo
- rendere il front heating meno grezzo e più controllabile.

## Fase 4 — Validazione e calibrazione iniziale

Dopo il refactor dei blocchi di cui sopra, rieseguire:
- Suzuka `green`
- Suzuka `oversteer`
- Hungaroring `green`
- Hungaroring `understeer`
- Hungaroring `oversteer`

Solo dopo questa validazione si valuterà se toccare anche il blocco `surface ↔ core`.

## 7. Dati/config da usare durante il refactor

## 7.1 Dati runtime già disponibili
- `section.heat_factor`
- `section.cool_factor`
- `section.braking_energy_mj`
- `dt_s`
- `v_kph`
- `aero.understeer_level`
- `aero.oversteer_level`
- `aero.airflow_penalty`
- stato freni asse anteriore/posteriore
- `aero_setup`

## 7.2 Config di riferimento
- `config/tyres/tyre_params_global_default.json`
- `config/circuits/derived/<circuit>/tyre_params.json`
- `config/circuits/derived/<circuit>/brake_params.json`
- `config/setup/setup_mapping_v2.json`
- `config/setup/setup_ranges/<circuit>.json`
- `config/setup/team_offsets.json`

## 7.3 Telemetria raw/derived utile
Da `*_Telemetry.json` e profili `derived`:
- severità per sezione
- velocità media
- durata sezione
- energia frenante
- distribuzione heat/cool del circuito
- densità frenante

## 8. Criteri di validazione

## 8.1 Invarianti termici

### Green
- temperature stabili;
- niente runaway spontaneo;
- core in zona credibile rispetto alla compound window.

### Understeer
- il front deve scaldare più del green;
- l'incremento deve essere chiaro ma non esplosivo.

### Oversteer
- il rear deve scaldare più del green;
- niente salti irreali di 15-20°C solo per pochi giri su pista tecnica.

## 8.2 Invarianti per circuito

### Suzuka
- carico laterale continuo;
- buon recupero grazie ai rettilinei;
- front core green vicino al target consolidato.

### Hungaroring
- recupero termico limitato;
- maggiore severità cumulativa;
- green non deve essere fuori finestra “a prescindere”.

## 8.3 Invarianti di modello
- il ranking relativo deve essere preservato;
- il livello assoluto deve diventare più credibile;
- le sorgenti di calore devono essere interpretabili dal debug log.

## 9. Piano operativo consigliato

## Step 1
Refactor del solo blocco `heat generation` in `python_backend/lap_simulator/tyre_model.py`.

## Step 2
Riesecuzione degli scenari minimi Suzuka/Hungaroring e raccolta log debug.

## Step 3
Refactor del blocco `cooling` se i risultati mostrano ancora forte dipendenza dai rettilinei.

## Step 4
Pulizia del coupling freni → gomma anteriore.

## Step 5
Nuova validazione comparativa.

## Step 6
Solo se necessario, review del blocco `surface ↔ core`.

## 10. Rischi da evitare

- introdurre clamp artificiali per spegnere il rear runaway;
- correggere Hungaroring rompendo Suzuka;
- usare `understeer_level` / `oversteer_level` come scorciatoie termiche troppo forti;
- risolvere tutto con straight cooling più alto;
- cambiare contemporaneamente heat generation, cooling e core exchange senza una validazione intermedia.

## 11. Deliverable finali della Strada A

A completamento della Strada A ci si aspetta:
- nuovo blocco `heat generation` più leggibile e fisico;
- cooling ribilanciato;
- log debug con contributi termici più interpretabili;
- validazione su Suzuka e Hungaroring;
- decisione informata se procedere o meno con una futura **Strada B** sul blocco core/surface completo.

## 12. Stato del documento

Documento iniziale di roadmap tecnica.
Va aggiornato durante l'implementazione con:
- decisioni effettive sui coefficienti;
- risultati dei run di validazione;
- eventuali deviazioni dalla roadmap.
