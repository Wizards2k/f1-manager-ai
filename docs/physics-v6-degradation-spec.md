---
title: Physics Engine V6.1 - Degradation & Systems Specification (Fase 2)
date: 2026-04-19
status: Draft
author: AI Agent
---

# Physics Engine V6.1 — Specifica Gestione Degrado (Fase 2)

## 1. Obiettivo Generale
Il nuovo Physics Engine V6.0.1 ha rivoluzionato il calcolo balistico della performance con architettura *dual-pass*, unificando la *load sensitivity* (K=0.010) e ribilanciando il peso aerodinamico. Ora che il comportamento baseline della vettura in Qualifica ("Giro secco") è fisicamente stabile e congruente (100% preference pass, 91.7% typology), è necessario sbloccare la **Fase 2**: trasformare le appendici e "penalità additive" del V5 (Usura, Termica Gomme, PU/ERS, Freni, Carburante) in forze e limiti nativi del nuovo motore.

Questo documento di sintesi delinea come i concetti espressi nei vari modelli isolati saranno cablati logicamente al polso del V6 (nello specifico, nel ciclo di integrazione di `waypoint_integrator.py`).

---

## 2. Tyre Thermal & Wear Model (Gomme)

Nel V5, il degrado era pesantemente legato in feedback negativi artificiali ("rear runaway" via moltiplicatori in cascata `axis_multiplier * traction_multiplier * oversteer_multiplier`).

### Integrazione nel V6.1 (Seguendo la "Strada A")
L'integrazione avverrà rimuovendo la logica dei bucket di "penalità" astratte a favore di un rateo basato sulle forze calcolate lungo il giro del V6.

*   **Two-Layer Model per ruota**:
    *   **Surface Temp (Reattiva)**: Salirà in base al `Friction_Heat`. Nel V6, deriviamo la severità della curva non solo da un array astratto, ma usando `F_grip_total_lateral` calcolata al waypoint e `v_max_corner`.
    *   **Core/Bulk Temp (Inerziale)**: Salirà a causa dell'Isteresi ($\uparrow$ Peso $m = m_{base} + m_{fuel}$) e della deformazione nelle curve ad alta velocità ($\uparrow$ Downforce e Velocity).
*   **Decoupling Handling & Heat**: 
    Il bilanciamento Sottosterzo/Sovrasterzo nel V6 è reale (le ali bilanciano i carichi asse anteriore/posteriore). Il delta di grip frontale rispetto a quello posteriore si tradurrà nativamente in `slip` maggiore per l'asse meno aderente. Non servono più moltiplicatori artificiali `oversteer_multiplier`, ma il calore sarà guidato da *quanto il setup devia dal grip richiesto* (Forza effettiva generata vs limite).
*   **Cooling Dipendente e Sensato**: 
    Nei rettilinei la dissipazione termica sarà dettata da $\Delta T \cdot v$, ma influenzata attivamente dai **Brake Ducts** (vedi Sezione Freni).
*   **Finestre Termiche (Pirelli Matrix)**:
    Il base grip derivato dalla calibrazione aero (es. `mu_mechanical`) calcolato su mescola Soft (C4/C5), verrà scalato istante-per-istante tramite curva gaussiana basata sulle temperature Surface e Core del modello, abbassando progressivamente `mu_mechanical` se fuori finestra.

---

## 3. Power Unit Stateful, ERS & Thermal Clipping

Il modello PU V5.4 (già in parte cablato ma forzato su mappa `QUALIFY` nel V6.0.1) dovrà essere sganciato per permettere dinamiche mutabili nel tempo.

### Integrazione nel V6.1
*   **Deployment Dinamico (Bucket Planner)**:
    Nel V6, le zone DRS, i `MediumStraight` e le ripartenze dalle curve vengono gestiti a livello di waypoint. Le mappe motore non distribuiranno solo un $P_{elec}$ predeterminato, ma seguiranno la gerarchia: 
    *   Energia limitata tramite Bucket ERS (Primary/Secondary/Exit).
    *   Energia ERS che si **somma** proporzionalmente alla `Torque_ICE` per definire l'effettiva $F_{engine}$ trasmessa a terra.
*   **Harvesting MGU-K & MGU-H**:
    *   Nella logica V6.0, il *Lookahead Physics-Driven* usa ora direttamente $F_{brake} = m_{kg} \cdot a_{max\_brake}$ per impostare un target $V_{corner}$. Questa decelerazione fisica si tradurrà in ricarica per l'MGU-K. 
    *   L'*Harvest_Mj* accumulato modificherà attivamente l'inerzia del SOC.
*   **Thermal Clipping**: 
    Basandosi sul calcolo termico $T_{ers}^{(t+dt)} = T_{ers}^{(t)} + \frac{\dot{Q}_{gen} - \dot{Q}_{cool}}{C_{th}} dt $, nei tratti ultra-veloci dove $t$ trascorso è notevole a $WOT$ (Wide Open Throttle), la $T_{ers}$ supererà la soglia $102^\circ$C fino a de-ratare il moltiplicatore $\eta_{th}$. Questo farà sì che $v_{max}$ su piste come Monza cali *fisicamente* verso la fine dei rettilinei per assenza di grip longitudinale propulsivo ($P_{elec}$ in clipping).

---

## 4. Freni: Termica, Fade e Sforzo

Il sistema dei freni introdotto dalla "Penalty Overhaul" è basato sui *Brake Ducts* e *Fade Thresholds* ma agisce in back-end aggiungendo "secondi di penalità" a fine sezione. Questo non è compatibile con il purismo del V6.

### Trasformazione da Penalità Astratta a Forza nel V6.1
*   **Brake Fade (Riduzione Decelerazione)**: 
    Invece di aggiungere $+0.1s$ quando i freni superano gli $850^\circ$C, il `Brake Fade` andrà a **limitare l'energia decelerativa massimale** disponibile ($F_{brake\_max} = \mu \cdot m \cdot g \cdot (1 - Fade\_Factor)$). Ciò causerà ingressi in curva più veloci del dovuto rispetto al calcolo V6 dei $V_{max\_corner\_array}$, forzando overshoot di velocità che rovineranno l'effettiva traiettoria o la tempistica, risultando organicamente nel tempo sul giro più sfavorevole.
*   **Termica a cascata**:
    La temperatura dei freni subirà il calcolo istantaneo di $Joules = \frac{1}{2}m\Delta v^2$. E, al contempo, questo calore si riverserà (transfer rate) alle gomme anteriori. I brake duct (apertura \%) agiranno da moderatori aerodinamici sia di raffreddamento dischi che di drag intrinseco ($c_d$ supplementare integrato nella fase *AeroAssembly* e nella pipeline di `integrate_waypoint`).

---

## 5. Massa Carburante (Derivazione Diretta)

Nel V5, il peso del carburante aggiungeva decimi o centesimi pre-calcolati.

### Gestione Nativa (Mass_KG)
In V6.1, `mass_kg = MASS_BASE_KG + FUEL_KG`.
Effetti automatici sul V6.0.1 dual-pass:
1.  **Grip Laterale vs. Inerzia**: Il downforce alza proporzionalmente $F_z$, ma la *Load Sensitivity* (k=0.010) applicata al peso maggiore rende le gomme meno "efficienti" per kg di spinta. Il limite $V_{max\_corner}$ si ridurrà naturalmente in vetture molto pesanti ($\uparrow$ $m$).
2.  **Grip Longitudinale (Accelerazione)**: In uscita, $F=ma \rightarrow a = F/m$. Più carburante $\rightarrow$ $a$ nativamente ridotta. Non servirà alcun *fuel_delta_s* fittizio.
3.  **Consumo**: Verrà tracciato ad ogni waypoint basandosi su $Throttle\_\%$ (estratto con proxy mapping RPM o blend) e mappa ICE in uso (es. RICH consuma fisicamente +kg/s di STANDARD).

---

## 6. Execution Roadmap & Cablaggio V6.1 (Dettaglio Tecnico)

Al fine di introdurre questo layer di degradazione si raccomanda una pipeline in moduli sequenziali, poiché le dipendenze si annidano e possono sfalsare il bilancio calcolato dei $V_{max\_corner}$ del V6.0. Ogni modulo modifica direttamente i file core del simulatore o rimuove codice obsoleto.

### Modulo A: Peso e Carburante (Foundation)

**Analisi Componente:** Il carburante non deve più essere una somma di "decimi di penalità" a fine giro. L'inizio di ogni lap (o mini-run) deve instanziare `mass_kg = MASS_BASE_KG + current_fuel_kg`. 
**Implementazione (Come fare):**
1. **Modifica Interfaccia:** In `waypoint_integrator.py:integrate_lap_hd`, sostituire l'argomento `mass_kg=MASS_TOTAL_QUALY_KG` con un approccio dinamico `current_car_mass_kg`.
2. **Propagazione Massa:** Questo valore viene già propagato in `compute_v_max_corners` e `f_vertical_kn`:
   ```python
   f_vertical = state.mass_kg * G + f_downforce
   ```
   Un peso maggiore ridurrà nativamente l'accelerazione ($a = F_{net} / m$) in fase di trazione.
3. **Consumo Carburante:** Implementare una nuova funzione `compute_fuel_consumption(throttle_pct, engine_map, dt)` che sottragga grammi di carburante ad ogni waypoint basandosi sul flusso del carburante stabilito dalla mappa ICE.
4. **Cleanup:** Rimuovere qualsiasi variabile `fuel_penalty_s` dal costrutto legacy `update_section.py` e `lap_simulator.py`.

### Modulo B: ERS e Engine Maps Switching

**Analisi Componente:** Attualmente il V6.0.1 forza `init_pu_context(circuit_id, "QUALIFY")`. Dobbiamo poter eseguire giri in mappa RACE o ECONOMY, attivando il reale prelievo dalla batteria e l'harvest dal MGU-K.
**Implementazione (Come fare):**
1. **Context Dinamico PU:** Adattare `car_setup.py` affinché accetti un payload come `{"engine_map": "RACE", "ers_bucket_strategy": "BALANCED"}`.
2. **Bucket Planner e SOC:** Ad ogni `integrate_waypoint`, agganciare `pu_state.soc_mj`. 
   * In frenata ($brake > 5\%$): calcolare energià recuperata `harvested = min(120kW * dt, budget_rimasto)` e aggiungere al `soc_mj`.
   * In trazione: verificare `soc_mj > 0.1` e disponibilità nel *Bucket ERS* (Primary/Secondary/Exit).
   * Generare $T_{MGU-K\_eff}$ in base al rateo ERS e all'efficienza corrente.
3. **Thermal Clipping Code:** Aggiungere un contatore `ers_temp_c` nell'integratore termico usando un sub-stepping fine (es. `0.01s`) per stabilità numerica:
   ```python
   # Termica ERS (sub-step 0.01s per stabilità Joule)
   q_gen = K_JOULE * (p_elec_kw ** 2)
   q_cool = H_V * state.velocity_ms * (pu_ctx.ers_temp_c - T_AMB)
   pu_ctx.ers_temp_c += (q_gen - q_cool) / C_TH * dt
   ```
   Se `ers_temp_c > 102.0`, abbattere la potenza elettrica richiesta per un fattore $\eta_{th}$ linearmente decrescente verso 0 (122.0 °C).

### Modulo C: Thermodynamic Tyres (Strada A)

**Analisi Componente:** Le gomme attuali usano penalità statiche in cascata (`oversteer_multiplier`). In V6.1 calcoleremo empiricamente `Surface Temp` e `Core Temp`. Dobbiamo integrare le logiche in `waypoint_integrator.py`.
**Implementazione (Come fare):**
1. **Tyre State:** Includere nel `PhysicsState` o ad ogni step, un Tracking State delle temperature per i due layer, inizializzate termocoperte ($~90^\circ$C).
2. **Surface Heating (Attrito & Frenata):** Calcolare durante la curva e in `is_braking`:
   ```python
   # Calore generato da slip laterale in appoggio
   lateral_force = f_grip_total_lateral * cornering_utilization
   friction_heat = lateral_force * slip_factor * dt
   surface_temp += (friction_heat + braking_heat) * k_surface_generate
   ```
3. **Core Heating (Isteresi e Deformazione):** Generato prettamente dal peso e velocità di rotazione:
   ```python
   # Il carico verticale ad alta velocità deforma la gomma innescando isteresi
   core_heat_hysteresis = (f_vertical * state.velocity_ms) * k_hysteresis * dt
   core_temp += core_heat_hysteresis
   ```
4. **Retroazione Termica su Grip Fisico:** Creare una curva Gaussiana $f(Temp)$ incentrata sulle *windows ottimali* (Pirelli matrix). Prima della fase di integrazione passiamo in rassegna le finestre attuali:
   ```python
   thermal_multiplier = gaussian(surface_temp, optim_surf) * gaussian(core_temp, optim_core)
   mu_tyre = mu_base_val * thermal_multiplier * wear_factor
   ```
   Questo valore rimpiazzerà il `mu_base_val` usato nell'integratore, impedendo a gomme troppo calde o usurate di fornire un $V_{max\_corner}$ alto e limitando nativamente l'accelerazione a causa dell'inferiore `f_grip_total_longitudinal`.

### Modulo D: Brake Fade Overhaul

**Analisi Componente:** Nel simulatore corrente il *Brake Penalty* è un semplice riepilogo a fine settore. Ora la temperatura dei freni andrà a deviare le distanze di frenata del lookahead.
**Implementazione (Come fare):**
1. **Brake Heating:** In fase di decelerazione (`is_braking`), la perdita di energia cinetica ($E_k = \frac{1}{2}m\Delta v^2$) viene instradata direttamente allo state termico del freno anteriore e posteriore con un *Brake Bias*.
2. **Duct Cooling vs Aero Drag:** L'utente imposta `brake_duct_opening`. Questo valore:
   * Aumenterà inversamente lo scambio termico per dissipazione (`q_cool = f(v, duct_opening)`).
   * Aggiungerà coefficiente di resistenza $c_{da}$ addizionale ad `AeroAssembly` in logica proportionale.
3. **Impatto del Fading sulla Decelerazione:**
   Aggiungere nel file `waypoint_integrator.py` (~linea 1415), una contrazione fisica della capacità decelerante se `brake_temp_c` sfora i parametri:
   ```python
   # Calcolo Fading (es. fade_threshold_front_c = 850°C)
   fade_factor = clamp(0.0, 1.0, (brake_temp_c - fade_threshold) / sensitivity)
   
   # La decelerazione massima viene mozzata proporzionalmente al fade
   max_brake_decel_phys = (f_grip_total_longitudinal * (1.0 - fade_factor)) / mass_kg
   ```
   Nel V6.0, il modulo di frenata inizia a "frenare" al punto logico fissato. Limitare `max_brake_decel` empiricamente costringerà il veicolo a superare il $V_{target\_ms}$ alla corda, sprecando decimi di secondo naturali e riducendo il raggio utile in percorrenza.

---

## 7. Criteri di Validazione Finale
*   **Green-Run Baseline**: La differenza fra il lap time *QUALIFY ERS* V6.0.1 (già ottimizzato) e il nuovo V6.1 con mappa *QUALIFY* deve essere nulla. 
*   **Race Pace Simulation**: Passaggio tra una Mappa RACE pesante e gomma Media, per un long run, deve rispecchiare cali organici di ritmo (Tire Wear curve $\sim$ -0.05..0.150s a giro; Fuel drop $\sim$ +0.06s in favore a giro).
*   **Debug Logs Puliti**: Tutte le entità penalizzanti devono lasciare traccia nel telemetry array (`ers_thermal_eta`, `tyre_surface_temp`, `ice_fuel_flow`), non in misurazioni di scarto come `brake_delta_s`.

---

## 8. Roadmap di Sviluppo e Rilasci (Release Plan)

Per garantire la stabilità del Physics Engine, il passaggio dalla V6.0.1 alla V6.1 "Degradation" deve essere affrontato in modo incrementale (Agile/Sprint). 

### Fase 1: Core Physics Base & Fuel (Sprint 1)
**Focus:** Rimuovere l'architettura obsoleta delle penalità V5 e implementare le fisiche passive.
1. Branch: `feature/v6.1-fuel-passive-core`.
2. Sostituzione delle formule su `waypoint_integrator.py` legate a $mass\_kg$ (Fuel).
3. Eliminazione di `update_section.py` dei delta additivi.
4. **Test & Milestone:** Il giro di qualifica è identico a prima. Un giro con 110KG di fuel risulta sensibilmente più lento (causa minore grip specifico sull'accelerazione radiale: diminuisce $V_{max\_corner}$).

### Fase 2: L'Avvento dell'Ibrido Dinamico (Sprint 2)
**Focus:** Implementare Modulo B (Mappe ERS/ICE, Harvesting e Thermal Clipping).
1. Branch: `feature/v6.1-dynamic-hybrid`.
2. Aggancio del `PU_Context` con la lettura dinamica della Mappa (non più solo QUALIFY).
3. Integrazione logica dei sub-step termici per l'Inverter dell'MGU-K.
4. Cablaggio del `soc_mj` in modo che l'Energia recuperata in decelerazione riempia la capienza della batteria.
5. **Test & Milestone:** Validare Monza in mappa RACE: il soc oscilla coerentemente, sul traguardo c'è clipping termico che abbassa i km/h massimi di circa 3-5 km/h.

### Fase 3: Il Contatto con l'Asfalto (Sprint 3)
**Focus:** Implementare Modulo C & D (Tyres e Brakes).
1. Branch: `feature/v6.1-thermodynamics-contact`.
2. Introduzione logica Surface/Core Heating in base al $F_{grip}$ sviluppato in curva.
3. Creazione campane Gaussiane per mappare il $\rightarrow \mu_{tyre}$ reattivo che varia le curve di grip nei pass down-stream.
4. Limitazione fisica decelerativa per Fading Termico post-riscaldamento ($brake\_temp\_c$).
5. **Test & Milestone:** Con gomma C5 usata ed elevati carichi, la Surface ed il Core sorpassano la finestra Pirelli; $\mu_{tyre}$ scende ad es. dell'8%, dirottando pesantemente in basso la $V_{max}$ che la macchina può sostenere.

### Fase 4: Integrazione AI e Telemetria (Sprint Finale)
**Focus:** Rendere visibile il nuovo Engine a UI e CPU.
1. Branch: `feature/v6.1-ai-telemetry-ui`.
2. Il Driver Model (AI e UI Input) sceglie i "Push Level" e "Tyre Save Mode" modulando il target di throttle/accelerazione laterale.
3. Propagazione array telemetrie: aggiungere `tyre_core_temp`, `brake_temp`, `ers_eta`.
4. **Test & Milestone:** Full Race Simulation (Long run di 15+ giri), dove il pitstop compensa l'usura gomme, l'IA reagisce ricaricando ERS in caso di clipping e l'effetto Drop Fuel fa scendere i tempi cronometrati progressivamente. Rilascio **V6.1 Stable**.
