---
title: Physics Engine V6.3 - Degradation & Systems Specification
date: 2026-04-19
status: Draft
author: AI Agent
---

# Physics Engine V6.3 — Specifica Degrado (Tire Thermal + Wear + Brake Fade)

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

### Modulo C: Thermodynamic Tyres (Strada A) — Per-Wheel Implementation

**Analisi Componente:** Le gomme attuali usano penalità statiche in cascata (`oversteer_multiplier`). In V6.1 calcoleremo empiricamente `Surface Temp` e `Core Temp` **per ogni singolo pneumatico (FL/FR/RL/RR)**. Dobbiamo integrare le logiche in `waypoint_integrator.py`.

**Implementazione (Come fare):**

#### 1. **Tyre State per Wheel** 
Includere nel `PhysicsState` un `TiresState` container con 4 istanze indipendenti (FL, FR, RL, RR), inizializzate a ~85°C (warm tires):
```python
tires_state = TiresState(
    fl=TireState(surface_temp_c=85.0, core_temp_c=75.0, wear_pct=0.0),
    fr=TireState(surface_temp_c=85.0, core_temp_c=75.0, wear_pct=0.0),
    rl=TireState(surface_temp_c=85.0, core_temp_c=75.0, wear_pct=0.0),
    rr=TireState(surface_temp_c=85.0, core_temp_c=75.0, wear_pct=0.0),
)
```

#### 2. **Load Distribution & Slip Per Wheel**
Ad ogni waypoint, calcolare il carico verticale **per ruota** basandosi su:
- Weight distribution (es. 45% front, 55% rear)
- Downforce distribution (simmetrico in rettilineo, asimmetrico in curva)
- Lateral load transfer in curva (es. curva destra → carico sinistro aumenta)
- Brake load transfer in frenata (es. frenata → carico anteriore aumenta)

```python
# Lateral load transfer (es. curva veloce destra, g_lateral = 2.0)
load_transfer_lateral = (m_kg * G * g_lateral) / 2  # metà del carico laterale
# Vertical load per wheel in curva destra:
f_z_fl = (m_kg * G / 2) + df_downforce_front/2 + load_transfer_lateral  # esterno caricato
f_z_fr = (m_kg * G / 2) + df_downforce_front/2 - load_transfer_lateral  # interno scaricato
f_z_rl = (m_kg * G / 2) + df_downforce_rear/2 + load_transfer_lateral   # esterno caricato
f_z_rr = (m_kg * G / 2) + df_downforce_rear/2 - load_transfer_lateral   # interno scaricato

# Brake load transfer (es. frenata pesante, decel = -10 m/s²)
load_transfer_brake = (m_kg * decel_required) / 2
f_z_fl = f_z_fl + load_transfer_brake  # front aumenta
f_z_fr = f_z_fr + load_transfer_brake
f_z_rl = f_z_rl - load_transfer_brake  # rear diminuisce
f_z_rr = f_z_rr - load_transfer_brake
```

Quindi calcolare slip **per ruota**:
```python
# Per ogni ruota (FL, FR, RL, RR)
slip_fl = 1.0 - (f_grip_available_fl / f_grip_required_fl)
slip_fr = 1.0 - (f_grip_available_fr / f_grip_required_fr)
slip_rl = 1.0 - (f_grip_available_rl / f_grip_required_rl)
slip_rr = 1.0 - (f_grip_available_rr / f_grip_required_rr)
```

#### 3. **Surface Heating (Attrito & Frenata) — Per Wheel**
```python
# Per ogni ruota (FL, FR, RL, RR)
friction_heat_fl = k_surface_fric * f_z_fl * slip_fl * velocity_ms * dt
friction_heat_fr = k_surface_fric * f_z_fr * slip_fr * velocity_ms * dt
friction_heat_rl = k_surface_fric * f_z_rl * slip_rl * velocity_ms * dt
friction_heat_rr = k_surface_fric * f_z_rr * slip_rr * velocity_ms * dt

# Brake heat (solo anteriori da brake_bias, posteriori ridotti)
brake_heat_fl = k_braking_transfer * braking_energy_mj * brake_bias / 2 * dt  # Ripartito FL/FR
brake_heat_fr = k_braking_transfer * braking_energy_mj * brake_bias / 2 * dt
brake_heat_rl = k_braking_transfer * braking_energy_mj * (1-brake_bias) / 2 * dt  # Ripartito RL/RR
brake_heat_rr = k_braking_transfer * braking_energy_mj * (1-brake_bias) / 2 * dt

# Update surface temps per wheel
tires_state.fl.surface_temp_c += (friction_heat_fl + brake_heat_fl) * k_surface_fric
tires_state.fr.surface_temp_c += (friction_heat_fr + brake_heat_fr) * k_surface_fric
tires_state.rl.surface_temp_c += (friction_heat_rl + brake_heat_rl) * k_surface_fric
tires_state.rr.surface_temp_c += (friction_heat_rr + brake_heat_rr) * k_surface_fric
```

#### 4. **Core Heating (Isteresi) — Per Wheel**
```python
# Core heat da deformazione (proporzionale al carico verticale)
core_heat_fl = k_hysteresis_core * f_z_fl * velocity_ms * dt
core_heat_fr = k_hysteresis_core * f_z_fr * velocity_ms * dt
core_heat_rl = k_hysteresis_core * f_z_rl * velocity_ms * dt
core_heat_rr = k_hysteresis_core * f_z_rr * velocity_ms * dt

tires_state.fl.core_temp_c += core_heat_fl
tires_state.fr.core_temp_c += core_heat_fr
tires_state.rl.core_temp_c += core_heat_rl
tires_state.rr.core_temp_c += core_heat_rr
```

#### 5. **Thermal Multiplier & Grip — Per Wheel**
```python
# Per ogni ruota, calcolare multiplier e aggiornare grip
for wheel in [fl, fr, rl, rr]:
    thermal_mult = gaussian(wheel.surface_temp_c, optim_surf) * gaussian(wheel.core_temp_c, optim_core)
    wear_factor = (100.0 - wheel.wear_pct) / 100.0
    mu_tyre[wheel] = mu_base_val * thermal_mult * wear_factor
    
    # Aggiornare f_grip_available per questa ruota
    f_grip_available[wheel] = f_z[wheel] * mu_tyre[wheel]
```

#### 6. **Wear Accumulation — Per Wheel**
```python
# Wear accumulates independently per wheel
for wheel in [fl, fr, rl, rr]:
    temp_dev = abs(wheel.surface_temp_c - optim_temp_surface)
    severity = 1.0 if temp_dev < sigma else 1.0 + ((temp_dev - sigma) / sigma) ** 1.5
    wear_per_km = k_wear_compound * severity * slip[wheel]
    wheel.wear_pct += wear_per_km * distance_km_lap

### Modulo D: Brake Fade Overhaul

**Analisi Componente:** Nel simulatore corrente il *Brake Penalty* è un semplice riepilogo a fine settore. Nel V6.1, la temperatura dei freni andrà a ridurre la capacità decelerativa massima disponibile, generando una **penalty fisica inescapabile** durante l'integrazione.

**Strategia Implementativa: OPTION B (Static Brake Fade)**

Il brake fade **non modifica dinamicamente il planning phase** (v_max_corner rimane calcolato). Invece, **agisce come una forza ambientale** durante l'integrazione che riduce la decelerazione disponibile. Se i freni sono caldi, l'auto semplicemente non può frenare quanto progettato, costringendola a entrare in curva più veloce e subire una penalità naturale di tempo sul giro.

**Rationale:** Coerente con V6.2 dual-pass: brake fade è una forza nativa come usura gomme o carburante, non una dinamica di feedback. L'AI può adattarsi **tra giri** (leggendo telemetria brake_temp e cambiano modo ERS o brake_duct), ma non **durante il giro**.

**Implementazione (Come fare):**

#### 1. **Brake Heating State Tracking**

Aggiungere a `PhysicsState`:
```python
@dataclass
class BrakeState:
    """Stato termico freni (front/rear separati)."""
    temp_front_c: float = 20.0  # °C, iniziale
    temp_rear_c: float = 20.0
    heat_accumulated_kj: float = 0.0  # Accumulatore per sub-step termico
```

#### 2. **Heat Generation (During Braking)**

Ad ogni waypoint durante la frenata, calcolare l'energia dissipata:
```python
# Energia cinetica dissipata in frenata
if is_braking and velocity_ms > V_MIN:
    # Decelerazione richiesta per raggiungere v_target
    decel_required = (velocity_ms - v_target_ms) / dt
    
    # Joule generato (metà anteriore, metà posteriore per semplificazione)
    joules_dissipated = 0.5 * mass_kg * velocity_ms * decel_required * dt
    
    # Ripartizione con brake bias (es. 55% front, 45% rear)
    heat_front_kj = (joules_dissipated / 1000.0) * brake_bias
    heat_rear_kj = (joules_dissipated / 1000.0) * (1.0 - brake_bias)
    
    brake_state.heat_accumulated_kj += heat_front_kj + heat_rear_kj
```

#### 3. **Thermal Integration (Sub-Stepping)**

Per ogni integrate_waypoint, usare sub-stepping **0.01s** per stabilità termica:
```python
# Termica freni (sub-step 0.01s per accuratezza Joule)
SUB_DT = 0.01
N_SUBSTEPS = int(dt / SUB_DT)

for _ in range(N_SUBSTEPS):
    # Heat transfer from friction (joules → temperature rise)
    # C_th_brake = capacità termica freni (kJ/K), es. 2.5 kJ/K
    temp_rise = brake_state.heat_accumulated_kj / C_TH_BRAKE
    
    # Cooling: convezione forzata (dipende da velocity + duct opening)
    # q_cool = h_conv * A * (T_brake - T_ambient)
    # h_conv = base_h * velocity_ms * (1.0 + duct_opening_factor)
    h_conv = H_CONV_BASE * velocity_ms * (0.5 + brake_duct_opening)
    q_cool_kj = h_conv * (brake_state.temp_front_c - T_AMBIENT) * SUB_DT / 1000.0
    
    # Update temperature
    brake_state.temp_front_c += temp_rise - q_cool_kj / C_TH_BRAKE
    brake_state.heat_accumulated_kj = max(0, brake_state.heat_accumulated_kj - q_cool_kj)
    
    # Clamp temperature (non può congelare)
    brake_state.temp_front_c = max(T_AMBIENT, brake_state.temp_front_c)
```

#### 4. **Fade Factor Calculation**

Una volta calcolata la temperatura, applicare il fade:
```python
# Parametri fade (determinano quando inizia e come si sviluppa)
FADE_THRESHOLD_FRONT_C = 850.0  # °C, temperatura soglia
FADE_SENSITIVITY = 40.0  # °C range per full fade (850°C → 890°C = full fade)

fade_factor = clamp(0.0, 1.0, 
    (brake_state.temp_front_c - FADE_THRESHOLD_FRONT_C) / FADE_SENSITIVITY
)

# Decelerazione disponibile viene ridotta dal fade
max_brake_decel_phys = (f_grip_total_longitudinal * (1.0 - fade_factor)) / mass_kg
```

#### 5. **Impact on Deceleration Target**

Durante integrate_waypoint, usare `max_brake_decel_phys` per limitare la decelerazione richiesta:
```python
# L'auto mira a v_target, ma non può frenare più di max_brake_decel_phys
decel_available = max_brake_decel_phys
decel_required = (velocity_ms - v_target_ms) / dt

if decel_required > decel_available:
    # Freni non riescono a frenare abbastanza
    # Auto entra in curva troppo veloce → overshoot v_max_corner
    velocity_actual = velocity_ms - decel_available * dt
else:
    # Freni OK, segui il piano
    velocity_actual = v_target_ms
```

#### 6. **Cooling (Asymmetric) and Aero Drag from Duct**

Il `brake_duct_opening` (slider 0-100) influenza **ONLY FRONT TIRES** (FL/FR):
- **Cooling front only:** Brake duct cools FL/FR brakes and tires preferentially (rear gets only ram-air)
- **Drag:** aggiunge c_da supplementare all'aero assembly (globale)

```python
# Brake duct aggiunge drag aerodinamico (globale, non per wheel)
duct_opening_pct = brake_duct_opening / 100.0  # 0.0-1.0
c_da_brake_duct = 0.005 * duct_opening_pct  # Esempio: max 0.005 di drag

# Cooling asimmetrico: solo FRONT tires beneficiano dal brake duct
h_conv_front = H_CONV_BASE * velocity_ms * (0.5 + brake_duct_opening)  # Duct helps
h_conv_rear = H_CONV_BASE * velocity_ms * 0.5  # No duct benefit

# Applica cooling per ruota (durante thermal integration sub-stepping)
q_cool_fl = h_conv_front * (brake_state.temp_front_c - T_AMBIENT) * SUB_DT / 1000.0
q_cool_fr = h_conv_front * (brake_state.temp_front_c - T_AMBIENT) * SUB_DT / 1000.0
q_cool_rl = h_conv_rear * (brake_state.temp_rear_c - T_AMBIENT) * SUB_DT / 1000.0
q_cool_rr = h_conv_rear * (brake_state.temp_rear_c - T_AMBIENT) * SUB_DT / 1000.0
```

**Consequence:** 
- Con duct 100% aperto: FL/FR ricevono -40% brake temp, RL/RR no change
- Brake fade asimmetrico: freni anteriori may stay <850°C while posteriori climb
- Setup strategico: se freni anteriori sono il bottleneck, brake duct full aperto

#### 7. **Reset Logic at Pit Stop**

Quando l'auto rientra ai box (pit stop completo):
```python
# Reset brake temperature (freni nuovi dopo sosta)
brake_state.temp_front_c = 30.0  # Raffreddati durante sosta
brake_state.temp_rear_c = 30.0
brake_state.heat_accumulated_kj = 0.0
```

---

#### **Validazione Criteri**

- **Green-Run Baseline (No Long Run):** Qualifying lap senza heat accumulo → tempo identico a V6.2
- **Race Pace Validation:** Long run 20 giri con RACE map + Medium tyres
  - Giro 1-3: brake_temp ~500°C, fade_factor ≈ 0 → time baseline
  - Giro 10-15: brake_temp ~850-900°C, fade_factor ≈ 0.3-0.5 → time +0.08-0.15s per fade
  - Giro 18-20: se duct aperto, brake_temp scende → time stabilizza
- **Duct Effect:** Brake duct aperto (100%) → cooling 40% migliore, fade ridotto
- **Telemetria:** Log `brake_temp_front`, `brake_temp_rear`, `fade_factor`, `c_da_duct` ad ogni waypoint

---

## 6.1 Parameter Definitions & Quantification

Tutti i coefficienti e i parametri utilizzati nei Moduli C (Tyres) e D (Brakes) sono quantificati di seguito per l'implementazione.

### Tire Thermal Heat Generation Coefficients

**k_surface_fric = 0.95** (Friction heating on contact patch)
- **Applicazione:** Heat generation from slip and lateral friction during cornering
- **Formula:** `heat_friction = k_surface_fric * f_z_vertical * slip_factor * velocity_ms`
- **Rationale:** Calibrated from Silverstone telemetry (Turn 1 lateral 2.1g, 80kN load, produces 20°C surface rise across 3-second corner). At 80 kph + 80 kN load → ~2-3°C rise per integration iteration
- **Unità:** Dimensionless coefficient, absorbs conversion from °C-per-Joule

**k_hysteresis_core = 0.35** (Deformation heating in tire bulk)
- **Applicazione:** Heat generation from tire deformation and hysteresis during high-speed rolling
- **Formula:** `heat_hysteresis = k_hysteresis_core * f_z_vertical * velocity_ms`
- **Rationale:** Hysteresis heating scales with velocity and vertical load. At 80 kph + 80 kN → ~1-2°C per iteration; at 320 kph same load → ~3-4°C per iteration (matching Silverstone telemetry heat_factor ratios: straights 0.2x, slow corners 1.4x)
- **Unità:** Dimensionless coefficient

**k_braking_transfer = 0.25** (Brake energy transferred to front tires during braking)
- **Applicazione:** Heat transfer from brake system to tire surface during heavy braking
- **Formula:** `brake_heat_to_tire = k_braking_transfer * braking_energy_mj / braking_duration_s`
- **Rationale:** ~25% of braking energy (1.84 MJ Silverstone Turn 1) transfers to tires via friction and weight transfer. Calibrated to produce 15-25°C surface temp rise during heavy braking events
- **Unità:** Energy transfer ratio (0-1)

### Thermal Window Gaussian Parameters

Tire grip (μ) has an optimal temperature. Away from optimum, grip falls via gaussian curve. Parameters:

**C5 (Soft compound):**
- Optimal surface temp: 100°C
- Optimal core temp: 85°C
- σ_surface: 7.5°C (narrow window → sharp penalty outside)
- σ_core: 6.5°C
- **Grip behavior:** At 85°C (within window) = 1.0× grip; at 70°C (cold) = 0.27× grip; at 130°C (hot) = 0.27× grip

**C4 (Medium compound):**
- Optimal surface temp: 105°C
- Optimal core temp: 90°C
- σ_surface: 8.0°C (slightly wider, more forgiving)
- σ_core: 7.0°C
- **Grip behavior:** More gradual degradation outside window vs C5, but lower peak grip

**C3 (Hard compound):**
- Optimal surface temp: 110°C
- Optimal core temp: 95°C
- σ_surface: 8.5°C (broad window → slower warm-up, more forgiving)
- σ_core: 7.5°C
- **Grip behavior:** Slower to warm up, more robust outside window, but lower ultimate grip

**Gaussian Implementation:**
```python
thermal_multiplier = exp(-(temp - temp_opt)^2 / (2 * sigma^2))
mu_tyre = mu_base_val * thermal_multiplier * wear_factor
```

At temp = temp_opt ± sigma: multiplier ≈ 0.61 (61% grip)
At temp = temp_opt ± 2*sigma: multiplier ≈ 0.14 (14% grip)

### Tire Wear Degradation Formula

**Base wear rate (per mescola, from TyreModel.md):**
- C5: 0.19%/km
- C4: 0.18%/km
- C3: 0.17%/km

**Temperature acceleration term:**
When temperature deviates from optimal window, rubber degrades faster (accelerated wear):

```python
temp_deviation = abs(surface_temp - temp_opt_surface)

if temp_deviation < sigma:
    temp_severity = 1.0  # No acceleration (within window)
else:
    # Accelerated degradation outside window
    temp_severity = 1.0 + ((temp_deviation - sigma) / sigma) ** 1.5
```

**Full wear formula:**
```
wear_pct_per_lap = k_wear_compound * lap_distance_km * temp_severity * slip_factor
```

**Example progression (Silverstone C4, 5-lap race):**
| Lap | Surf Temp | Severity | Base Wear | Total Wear | Grip Loss |
|-----|-----------|----------|-----------|------------|-----------|
| 1   | 102°C     | 1.0      | 1.06%     | 1.06%      | 1.3% |
| 2   | 107°C     | 1.1      | 1.17%     | 2.23%      | 2.7% |
| 3   | 112°C     | 1.5      | 1.59%     | 3.82%      | 4.4% |
| 4   | 119°C     | 2.8      | 2.97%     | 6.79%      | 6.8% |
| 5   | 124°C     | 4.2      | 4.45%     | 11.24%     | 10.2% |

At 11.24% wear: grip down ~10%, tire performance degraded, difficulty controlling temperature.

### Brake Fade Parameters

**FADE_THRESHOLD_FRONT_C = 850.0°C** — Temperature threshold above which fade begins

**FADE_SENSITIVITY = 40.0°C** — Temperature range for full fade progression (850°C → 890°C = 100% fade)

**H_CONV_BASE = 15.0** — Base convective heat transfer coefficient (W/m²·K equivalent, tuned for F1 brake physics)

**C_TH_BRAKE = 2.5 kJ/K** — Brake thermal capacity (energy storage per degree)

**T_AMBIENT = 20.0°C** — Ambient temperature

**Fade factor calculation:**
```python
fade_factor = clamp(0.0, 1.0, 
    (brake_state.temp_front_c - FADE_THRESHOLD_FRONT_C) / FADE_SENSITIVITY
)
# At 850°C: fade = 0 (no fade)
# At 870°C: fade = 0.5 (50% reduction in brake decel)
# At 890°C+: fade = 1.0 (full fade, minimum brake capability)
```

**Brake cooling with duct opening:**
```python
h_conv = H_CONV_BASE * velocity_ms * (0.5 + brake_duct_opening)
# brake_duct_opening: 0.0-1.0 (0%-100% open)
# At zero duct: h_conv scales only with velocity
# At full duct: h_conv increases by 50% additional (more air flow)
```

**Brake duct aerodynamic drag:**
```python
c_da_brake_duct = 0.005 * duct_opening_pct
# Max 0.005 additional drag coefficient (small penalty for cooling benefit)
```

---

## 6.2 Multi-Lap State Management

### Tire State Persistence — Per-Wheel Independence (CRITICAL)

**⚠️ EACH OF THE 4 WHEELS (FL, FR, RL, RR) HAS INDEPENDENT THERMAL & WEAR STATE**

Tire thermal and wear state must persist across laps **per individual wheel**:

```python
@dataclass
class TireState:
    """Tire state for SINGLE WHEEL (FL, FR, RL, RR each have separate instance)."""
    surface_temp_c: float = 85.0  # Reactive to friction/cooling
    core_temp_c: float = 75.0     # Inertial, slower change
    wear_pct: float = 0.0         # Cumulative wear [0-100]
    is_graining: bool = False     # Blistering flag
    is_blistering: bool = False   # Surface damage flag

@dataclass
class TiresState:
    """Container for all 4 wheels."""
    fl: TireState = field(default_factory=TireState)  # Front Left
    fr: TireState = field(default_factory=TireState)  # Front Right
    rl: TireState = field(default_factory=TireState)  # Rear Left
    rr: TireState = field(default_factory=TireState)  # Rear Right
```

**Why Independent State Matters:**

1. **Asymmetric Brake Loading:** Heavy braking heats front tires far more than rear (55% front / 45% rear bias). Front tires fade first.
   - Example: Silverstone Turn 1 braking → FL/FR heat +20°C, RL/RR heat +5°C
   
2. **Asymmetric Cornering Load:** In a high-speed right-hand corner, outside (left) tires experience higher vertical load → more slip → more heat
   - Example: Fast left corner → RL/RR overheat vs FR normal (especially RR exterior)
   
3. **Asymmetric Setup Effect:** Oversteer setup overloads rear tires, understeer overloads front tires
   - Oversteer setup: RL/RR degrade 20-30% faster than FL/FR
   - Understeer setup: FL/FR degrade faster
   
4. **Asymmetric Cooling:** Brake ducts cool front brakes/tires selectively
   - Only FL/FR benefit from brake duct cooling
   - RL/RR cooling depends only on ram-air speed

5. **Blister/Grain Risk Asymmetric:** If surface temp exceeds window by +30°C on one wheel, blistering occurs on THAT wheel only, not all 4

**Implementation Consequence:**
- During `integrate_waypoint()`, calculate `slip_factor` per wheel based on vertical load distribution
- Calculate `surface_heat` and `core_heat` per wheel
- Apply thermal_multiplier **per wheel** when computing grip for force calculations
- Track wear_pct **per wheel**
- Pit stop resets ALL wheels simultaneously (all tires changed together)

**Lap-to-lap logic:**
1. **Start of new lap:** Preserve `wear_pct` from previous lap
2. **Cool-down period:** Between lap end and start, if car is in pit lane, cool temps at fixed rate (e.g., -50°C/lap if in garage)
3. **Pit stop reset:** Full tire change → all temps reset to 85°C (warm tires), wear_pct reset to 0%
4. **Compound change:** If switching compounds mid-race, reset surface/core temps, but preserve wear tracking from previous compound (carry over wear impact)

### Multi-Lap Accumulation

Wear accumulates across laps following the formula in 6.1. Temperature state carries forward but can be reset by pit stops.

**Example: 5-lap race on Silverstone C4**
- Lap 1: Start 85°C, end 102°C, wear +1.06%
- Lap 2: Start 102°C (carry), end 107°C, wear +1.17% (cumulative 2.23%)
- Lap 3: Start 107°C (carry), end 112°C, wear +1.59% (cumulative 3.82%)
- Pit stop: Reset temps to 85°C, reset wear to 0% (new tires)
- Lap 4: Start 85°C, end 100°C, wear +1.05% (fresh tires)

---

## 7. Criteri di Validazione Finale
*   **Green-Run Baseline**: La differenza fra il lap time *QUALIFY ERS* V6.0.1 (già ottimizzato) e il nuovo V6.1 con mappa *QUALIFY* deve essere nulla. 
*   **Race Pace Simulation**: Passaggio tra una Mappa RACE pesante e gomma Media, per un long run, deve rispecchiare cali organici di ritmo (Tire Wear curve $\sim$ -0.05..0.150s a giro; Fuel drop $\sim$ +0.06s in favore a giro).
*   **Debug Logs Puliti**: Tutte le entità penalizzanti devono lasciare traccia nel telemetry array (`ers_thermal_eta`, `tyre_surface_temp`, `ice_fuel_flow`), non in misurazioni di scarto come `brake_delta_s`.

---

## 8. Roadmap di Sviluppo e Rilasci (Release Plan)

Per garantire la stabilità del Physics Engine, il passaggio dalla V6.0.1 alla V6.1 "Degradation" deve essere affrontato in modo incrementale (Agile/Sprint). 

### Fase 1: Core Physics Base & Fuel (Sprint 1) - [✅ COMPLETATO]
**Focus:** Rimuovere l'architettura obsoleta delle penalità V5 e implementare le fisiche passive.
1. Branch: `feature/v6.1-fuel-passive-core`.
2. Sostituzione delle formule su `waypoint_integrator.py` legate a $mass\_kg$ (Fuel).
3. Eliminazione di `update_section.py` dei delta additivi.
4. **Test & Milestone:** Implementato con successo e validato su tutti i 24 circuiti (Fuel margin sempre rispettato usando i calcoli nativi su massa e farfalla V6).

### Fase 2: L'Avvento dell'Ibrido Dinamico (Sprint 2) - [✅ COMPLETATO]
**Focus:** Integrazione del Modulo B (Mappe ERS/ICE, Harvesting e Thermal Clipping) all'interno dell'engine V6.
1. Branch: `feature/v6.1-dynamic-hybrid`
2. **Esito**: Modello termico ed elettronico (V5.4 Payload) importato via module hook nel V6.
3. La logica di deploy (Bucket Planner) lavora ora di pari passo al `throttle_pct` calcolato da V6.
4. Cablato l'harvesting MGU-K nella pipeline dinamica e il clipping (Temperature \> 102°C).
5. **Test & Milestone:** Le vetture tagliano potenza correttamente a fine rettilineo su circuiti come Monza, influenzate dallo scorrimento temporale ERS e decurtando il budget di mappa (es: RACE vs QUALIFY).

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

---

## 9. Validation Test Suite

### Test 1: Tire Thermal Multiplier Effect (Single Lap Baseline)

**Objective:** Verify that thermal_multiplier reduces grip outside optimal window, causing realistic lap time degradation.

**Test Case: Silverstone, QUALIFY session, C4 medium**
```
Setup: Optimal wings (14/8)
Fuel: Standard (50kg)
Baseline: Warm tires (105°C surface, 90°C core) → grip 1.0x
Test: Cold tires (70°C surface, 60°C core) → grip reduced
```

**Expected Results:**
- Cold tires: 70°C surface → multiplier ≈ 0.27 → μ_tyre ≈ 0.27× baseline → lap time ~0.5-1.0s slower (increased braking distance, reduced cornering speed)
- Warm tires (100-110°C): multiplier ≈ 0.95-1.0 → lap time baseline
- Hot tires (120°C): multiplier ≈ 0.75 → lap time ~0.3-0.5s slower (grip limit reduced)

**Metric:** Lap time variance with temperature = 1.0-1.5s per 50°C deviation from optimal

---

### Test 2: Tire Wear Accumulation (5-Lap Race)

**Objective:** Verify wear accumulates realistically and accelerates outside thermal window.

**Test Case: Silverstone, RACE session, C4 medium, 5 laps**
```
Setup: Medium wings (18/11)
Fuel: Start 70kg, consume ~14kg/lap
Brake duct: 50% open
```

**Expected Results:**
```
Lap 1: wear +1.06%, surface temp 102°C (within window)
       → multiplier 1.0, grip baseline
Lap 2: wear +1.17%, surface temp 107°C (within window)
       → multiplier 1.0, grip baseline, cumulative wear 2.23%
Lap 3: wear +1.59%, surface temp 112°C (slightly hot)
       → multiplier 0.9, ~0.5s slower, cumulative wear 3.82%
Lap 4: wear +2.97%, surface temp 119°C (hot)
       → multiplier 0.7, ~1.0s slower, cumulative wear 6.79%
Lap 5: wear +4.45%, surface temp 124°C (very hot)
       → multiplier 0.55, ~1.5s slower, cumulative wear 11.24%
```

**Metric:** 
- Wear rate increases ~3-4x when temp exceeds ±2σ
- Lap time degradation ~0.2-0.3s per lap due to wear + thermal multiplier combined
- Total race time loss: +3-5s over 5 laps vs fresh tires

---

### ⚠️ CRITICAL: Per-Wheel Asymmetry Validation (All Tests)

**Every test MUST verify that 4 wheels develop independent thermal/wear states:**

For each lap in test output, log:
```
Lap N:
  FL: temp_surf=XXX°C, wear=YY%, slip=Z.Z%
  FR: temp_surf=XXX°C, wear=YY%, slip=Z.Z%
  RL: temp_surf=XXX°C, wear=YY%, slip=Z.Z%
  RR: temp_surf=XXX°C, wear=YY%, slip=Z.Z%
```

**Expected Asymmetries by Scenario:**

1. **Heavy Braking Turn (e.g., Turn 1):**
   - FL/FR temps +15-25°C higher than RL/RR (brake load transfer)
   - Slip: FL/FR higher than RL/RR if brake bias front-heavy

2. **High-Speed Sweeper (e.g., Monza Parabolica, fast right):**
   - Exterior wheels (FL/RL in right turn) +3-8°C hotter than interior (FR/RR)
   - Exterior wheel slip higher due to load transfer

3. **Oversteer Setup (low front wing):**
   - RL/RR hotter than FL/FR across long run
   - RL/RR wear 20-30% faster than FL/FR by lap 10

4. **Understeer Setup (high front wing):**
   - FL/FR hotter than RL/RR
   - FL/FR wear faster

5. **Brake Duct 100% Open:**
   - FL/FR brake temps 40% lower than RL/RR
   - Brake fade (if any) appears on RL/RR first, not FL/FR

**If all 4 wheels show identical temperatures/wear → IMPLEMENTATION BUG**

---

### Test 3: Brake Fade Progression (Long Run 20 Laps)

**Objective:** Verify brake fade develops gradually with temperature, limiting deceleration physically.

**Test Case: Silverstone, RACE session, 20-lap endurance, C4 medium**
```
Setup: Medium wings (18/11)
Fuel: Start 110kg, pit stop lap 10
Brake duct: 50% open
Brake bias: 55% front / 45% rear
```

**Expected Progression:**
```
Laps 1-3:   brake_temp ~500°C, fade_factor ≈ 0.0 → braking distance baseline
Laps 4-8:   brake_temp ~700°C, fade_factor ≈ 0.1 → braking distance +2-5%
Laps 9-12:  brake_temp ~850-900°C, fade_factor ≈ 0.3-0.5 → braking distance +10-15%
            (Pit stop lap 10: temps reset to 30°C)
Laps 11-15: brake_temp ~500°C (fresh), fade_factor ≈ 0.0 → braking distance baseline
Laps 16-20: brake_temp ~700-800°C (accumulating again), fade_factor ≈ 0.1-0.25 → +5-10%
```

**Metrics:**
- Brake deceleration available: `max_decel = (f_grip * (1 - fade_factor)) / mass_kg`
- Turn-in speed overshoot: car enters corner ~2-5 kph faster due to reduced deceleration
- Lap time impact: ~0.08-0.15s per lap when fade_factor > 0.3
- Duct effect: 100% open reduces fade progression ~40% (better cooling)

---

### Test 4: Brake Duct Cooling Effect

**Objective:** Verify brake duct opening reduces temperatures and prevents fade escalation.

**Test Case: Monaco, RACE session, 10 laps, brake-heavy circuit**
```
Scenario A: Duct 0% (closed) - baseline
Scenario B: Duct 100% (open) - maximum cooling
```

**Expected Results:**
```
Scenario A (0% duct):
Lap 5:  brake_temp_front ≈ 900°C, fade_factor ≈ 0.5
Lap 10: brake_temp_front ≈ 920°C, fade_factor ≈ 0.7 (escalating)

Scenario B (100% duct):
Lap 5:  brake_temp_front ≈ 720°C, fade_factor ≈ 0.0
Lap 10: brake_temp_front ≈ 780°C, fade_factor ≈ 0.1 (controlled)
```

**Metrics:**
- Temperature reduction: ~40-50% lower peak temps with duct 100% open
- Drag penalty: +0.005 c_da from duct → ~0.2-0.3s per lap on fast circuits
- Trade-off: Duct worth it only on brake-heavy circuits where fade would accumulate

---

### Test 5: Fuel Weight Impact on Grip (Qualifying Session)

**Objective:** Verify fuel weight naturally reduces corner speed via load sensitivity.

**Test Case: Monza, QUALIFY session, C5 soft**
```
Setup A: Fuel 5kg (light) → mass 705kg
Setup B: Fuel 50kg (standard) → mass 750kg
Setup C: Fuel 110kg (heavy) → mass 815kg
```

**Expected Results (optimal wings 9/4):**
```
Setup A (light 705kg):  v_max_corner ≈ 89.2 m/s, lap time ≈ 78.5s
Setup B (standard 750kg): v_max_corner ≈ 87.8 m/s, lap time ≈ 79.1s (baseline)
Setup C (heavy 815kg):  v_max_corner ≈ 86.1 m/s, lap time ≈ 80.2s
```

**Metrics:**
- Grip reduction from load: K=0.010 × ΔF_z = 0.010 × (45kg × 9.81) ≈ 4.4% loss at +45kg
- Lap time delta: ~0.6s per 45kg fuel increase (natural from load sensitivity, no artificial penalty)
- Acceleration impact: a = F/m → heavier car slower on exit (another 0.2-0.3s cumulative)

---

### Test 6: Validation Against V6.2 Baseline (Regression Test)

**Objective:** Ensure V6.1 degradation model doesn't break V6.2 baseline (green-run QUALIFY).

**Test Case: All 24 circuits, QUALIFY session, optimal setup**
```
Tire: C5 soft, 85°C initial (warm-up lap already done)
Fuel: Standard 50kg
Brake duct: 50% (neutral)
ERS: QUALIFY map
```

**Expected Results:**
- Lap times within **±0.1s** of V6.2 recorded optimal times
- Setup congruence: **24/24** (unchanged)
- Typology congruence: **91.7%+** (unchanged)
- All thermal multipliers = 1.0 (since start temps in optimal window)
- All brake temps < 500°C (no fade)

**Metric:** If regression test fails, degradation model introduces unintended coupling. Debug source: thermal/wear accumulation artifact from initialization.

---

### Test 7: Integration Test - 15-Lap Race Simulation

**Objective:** Full end-to-end validation with pit stop, compound change, fuel consumption, multi-lap degradation.

**Test Case: Hungary, RACE simulation, 15 laps with pit stop lap 8**
```
Stint 1 (Laps 1-7): C4 medium, 110kg fuel, 50% duct
Pit stop lap 8:    Fresh C4 medium (wear reset), 85kg fuel
Stint 2 (Laps 9-15): C4 medium, 50% duct (remaining fuel)
```

**Expected Outcomes:**
```
Stint 1:
  Lap 1-3:   ~70.5s (fuel impact minimal, tires warming)
  Lap 4-6:   ~70.0s (steady state, optimal thermal window)
  Lap 7:     ~70.6s (fuel lighter, but heat building)

Pit Stop Lap 8: Reset tires, refuel to 85kg, +45s pit loss

Stint 2:
  Lap 9:     ~69.8s (fresh tires, lower fuel = faster)
  Lap 10-13: ~70.0-70.2s (tires re-warming, steady state)
  Lap 14-15: ~70.5-70.8s (tires aging again, fuel running out helps balance)

Total race time: ~1058s (14.4s pit stop penalty counted)
Comparison: V6.2 baseline (no degradation) would be ~1008s (50s difference = reality of fuel/wear/fade)
```

**Metrics:**
- Pit stop timing correct
- Tire warm-up smooth (no step functions)
- Fuel consumption realistic (~14-15kg/lap RACE)
- Brake temps controlled with duct at 50%
- Lap time variance consistent with thermal model

---

## 9.1 Known Challenges & Considerations from Past Implementations

### Warm-Up vs Outlap Dynamics

**Challenge:** Tire initial temperature depends on context:
- **Quali outlap (cold start):** Tires start ~20-30°C (off-compound window), require 1-2 warm-up laps before reaching optimal 85-110°C
- **Quali hot lap (launched):** Tires already 85°C+ from warm-up lap, grip available immediately
- **Race stint start:** If pit stop lap N, tires reset to 85°C (warm tires from Pirelli), not 20°C (cold)

**Implementation Impact:**
- Don't assume all laps start at optimal temperature
- Outlap simulation must show 0.5-1.5s penalty vs hot lap (realistic warm-up loss)
- Pit stop should instantiate tires at 85°C, not cold
- Test script must differentiate `simulate_outlap()` vs `simulate_qualifying_lap()`

### Pirelli Window Enforcement Difficulties

**Historical issue:** In V5, thermal windows (C5: 85-115°C) were theoretically defined but empirically unreliable because:
- Underlying physics wasn't reactive enough to temperature changes
- Multipliers were applied artificially, not as natural grip consequences
- Rear tires overheated in runaway feedback loops (cascading multipliers)

**V6.2 Physics Advantage:**
V6.2 dual-pass is more physically grounded (force-based, load-sensitive), so thermal multiplier should behave more realistically. However, **expect calibration challenges:**
- Sigma values (7.5°C for C5, etc.) may need fine-tuning based on real simulation data
- Tire warm-up rate may not match Pirelli curves exactly (different heat sources than real F1)
- Monitor if rear tires still exhibit runaway heating in long corners

**Mitigation:**
- Run validation tests and compare against historical lap times to detect unintended thermal coupling
- Be prepared to adjust sigma ±1-2°C if thermal window is too narrow or too wide
- Log all thermal multiplier values to detect anomalies

---

## 10. Extended Test Matrix (Comprehensive Coverage)

Beyond the 7 base validation tests, comprehensive testing must cover **all combinations** of:

### a) Stint Length & Degradation Curves

**Test stint durations:**
- Short stint (3 laps): Fresh tires only, minimal degradation
- Medium stint (7-10 laps): Degradation visible, thermal window stress
- Long stint (15-20 laps): Severe wear (10-15%), tire management critical

**Per circuit & compound, measure:**
- Wear progression curve (wear_pct vs lap_n)
- Temperature progression (surface_temp vs lap_n)
- Lap time delta vs lap_n (expected: monotonic ~+0.1s/lap)

### b) Setup Variation (Assetti Diversi)

**Test per circuit: optimal setup vs suboptimal**
- **Optimal setup:** Minimal understeer/oversteer balance → minimal slip → minimal heat
- **Understeer setup:** High front wing (e.g., 25/9 instead of optimal 14/8 on Monza) → front tires work harder → +2-4°C heat → accelerated wear
- **Oversteer setup:** Low front wing (e.g., 8/12) → rear tires work harder → rear overheating → +3-6°C heat → asymmetric degradation (rear faster)

**Metrics:**
- Setup quality directly affects `slip_factor` → directly affects heat generation
- Oversteer setup should show rear tires degrading 20-30% faster than front
- Lap time impact: suboptimal setup +0.3-0.8s from setup alone, +additional from thermal degradation

### c) Driver Push Level (Spinta Pilota Diversa)

**Simulate different push strategies:**
- **Conservative (push_level=30%):** Lower target_g_lat (less aggressive cornering) → lower slip → lower heat → better tire longevity
- **Balanced (push_level=70%):** Normal qualifying pace → moderate heat generation
- **Aggressive (push_level=100%):** Maximum target_g_lat every corner → maximum slip → maximum heat → rapid degradation

**Expected behavior:**
- Conservative: Lap time slower but tires last 50%+ longer in long stints
- Aggressive: Faster per-lap but unsustainable (tires fail by lap 12-15)
- Trade-off curves critical for AI tire management strategy

### d) Engine Map Variation (Mappature Motore)

**Test all 4 maps (already in pu_maps.json):**
- **QUALIFY:** 100% ICE power, 4.0 MJ ERS/lap, high thermal load on PU
- **RACE:** 84% ICE power, 3.84 MJ ERS/lap, moderate thermal
- **PRACTICE:** 35% ICE power, 1.96 MJ ERS/lap, low thermal
- **SAFETY_CAR:** 43% ICE power, 0.5 MJ ERS/lap, minimal thermal

**Metrics per engine map:**
- Straight speed variation (QUALIFY +5-8 kph vs PRACTICE on Monza)
- Exit acceleration variation (affects tire heating out of slow corners)
- ERS thermal clipping effect (on ultra-fast circuits like Spa, does QUALIFY hit thermal limit?)
- Lap time delta: should be 1.5-3.5s between QUALIFY and PRACTICE

### e) Circuit Variety (Circuiti Diversi)

**Mandatory test circuits covering different thermal profiles:**

| Circuit | Heat Profile | Notes |
|---------|--------------|-------|
| **Monza** | Low heat (straights, low downforce) | Long straights = tire cooling; test drag_index effect |
| **Barcelona** | High heat (long medium corners) | 1-2s corners generate sustained lateral load; test surface temp peaks |
| **Monaco** | Very high heat (low speed, aggressive steering) | High slip at low speed; rear overheating risk |
| **Suzuka** | High heat + high speed | Spoon Curve (high speed + lateral); test core temp coupling |
| **Canada** | Brake-heavy | T1 heavy braking, walls tight; test brake-to-tire coupling |
| **Baku** | Mixed (long straights + tight corners) | Runway effect; test cooling in DRS straights |
| **Las Vegas** | Straight-dominant (87% straights) | Terminal velocity circuit; test drag model interaction with tire temps |

**Per circuit, verify:**
- Tire temps realistic vs historical telemetry (if available)
- Brake temps realistic for corner/strait mix
- Thermal window respected (peak temps within Pirelli range)

### f) Fuel Load Variation (Carichi Benzina Diversi)

**Test 4 fuel scenarios per circuit:**
- Light (20kg): Fast but risky range management
- Standard (50kg): Baseline for single stint
- Heavy (85kg): Heavy but strategic for multi-stint
- Full (110kg): Race start fuel

**Metrics:**
- Mass impact on v_max_corner (heavier = slower corners, load sensitivity K=0.010)
- Acceleration impact a=F/m (heavier = slower exits)
- Tire wear correlation with fuel (heavier = more friction = +heat)
- Lap time delta per 10kg fuel: expect ~0.05-0.08s

### g) Tire Compound & Degradation Curve (Mescole)

**Test all compounds (C5, C4, C3) on mandatory circuits:**

| Compound | Warm-Up Laps | Peak Window | Degradation Rate | Best Stint |
|----------|-------------|-------------|------------------|------------|
| **C5 soft** | 1-2 laps | Early (lap 1-5) | Fast (0.19%/km) | 5-8 laps |
| **C4 medium** | 2-3 laps | Stable (lap 2-10) | Moderate (0.18%/km) | 10-15 laps |
| **C3 hard** | 3-4 laps | Late (lap 5-15) | Slow (0.17%/km) | 15-20 laps |

**Per compound, measure:**
- Warm-up curve (lap time vs lap_n, first 5 laps)
- Degradation curve (lap time vs wear_pct, after warm-up)
- Thermal stress (peak surface/core temps in long stint)
- Blister/grain risk (if pushing aggressively on soft compound)

### h) Pilot Skill / Tire Management (Abilità Gestione Gomme)

**Simulate different driver styles:**
- **Aggressive manager:** Push_level high early, rely on pit stop recovery
- **Conservative manager:** Push_level low, manage temps, extend stint
- **Balanced manager:** Adapt push_level based on tire temp telemetry

**Metrics:**
- Total race time (sum all laps + pit penalty)
- Lap time evolution (detect tire failure or runaway heat)
- Tire age at pit stop (pit stop timing impact)

---

## 11. Technical Implementation Specifications

Complete guide for developers implementing V6.1 degradation model with per-wheel thermal/wear tracking.

### 11.1 File Modifications Required

#### A. `python_backend/lap_simulator/physics_v4/integrator/waypoint_integrator.py`

**File Location:** [waypoint_integrator.py](python_backend/lap_simulator/physics_v4/integrator/waypoint_integrator.py)

**Modification 1: Add TiresState to PhysicsState (Line 73-108)**

Current:
```python
@dataclass
class PhysicsState:
    """Stato fisico dell'auto durante l'integrazione."""
    distance_m: float = 0.0
    velocity_ms: float = 0.0
    # ... other fields ...
    telemetry_points: List[Dict] = None
```

Add after line 103 (before `__post_init__`):
```python
    # V6.1: Tire thermal state (per-wheel independent)
    tires_state: Optional['TiresState'] = None  # TiresState with FL/FR/RL/RR
```

**Modification 2: Import TiresState/TireState dataclass (Line 30-70)**

After line 70 (after other imports), add:
```python
from tyres.tyre_thermal import TireState, TiresState  # V6.1: Per-wheel thermal state
```

**Modification 3: Initialize TiresState in PhysicsState.__post_init__ (Line 105-108)**

After line 108, add:
```python
        if self.tires_state is None:
            self.tires_state = TiresState()  # Initialize with default FL/FR/RL/RR
```

**Modification 4: integrate_waypoint() signature (Line 735)**

Add new parameter after line 766:
```python
    tires_state: Optional['TiresState'] = None,  # V6.1: Tire thermal/wear state (per-wheel)
    slip_per_wheel: Optional[Dict[str, float]] = None,  # V6.1: Slip angle per wheel (FL/FR/RL/RR)
```

**Modification 5: Load Distribution Calculation in integrate_waypoint (Line 800-900)**

Around line 850 (after vertical force calculation), add:

```python
    # V6.1: Calculate per-wheel load distribution
    # Lateral load transfer (curva)
    g_lateral = state.velocity_ms ** 2 / (radius_m * 9.81) if radius_m < 999999 else 0.0
    load_transfer_lateral_kn = (mass_kg * 9.81 / 1000) * g_lateral / 2  # kN
    
    # Brake load transfer (frenata)
    decel_required = max(0.0, (state.velocity_ms - v_target_ms) / dt_step) if dt_step > 0 else 0.0
    load_transfer_brake_kn = (mass_kg * decel_required / 9.81) / 2  # kN
    
    # Static load per axle
    static_load_front_kn = (mass_kg * 9.81 * 0.45) / 1000.0  # 45% front
    static_load_rear_kn = (mass_kg * 9.81 * 0.55) / 1000.0   # 55% rear
    
    # Downforce distribution (symmetric)
    df_front_kn = (f_downforce * 0.45) / 1000.0  # 45% front
    df_rear_kn = (f_downforce * 0.55) / 1000.0   # 55% rear
    
    # Per-wheel load (determines slip and heat)
    load_fl_kn = (static_load_front_kn / 2 + df_front_kn / 2 
                  + load_transfer_lateral_kn + load_transfer_brake_kn)
    load_fr_kn = (static_load_front_kn / 2 + df_front_kn / 2 
                  - load_transfer_lateral_kn + load_transfer_brake_kn)
    load_rl_kn = (static_load_rear_kn / 2 + df_rear_kn / 2 
                  + load_transfer_lateral_kn - load_transfer_brake_kn)
    load_rr_kn = (static_load_rear_kn / 2 + df_rear_kn / 2 
                  - load_transfer_lateral_kn - load_transfer_brake_kn)
    
    wheels_load = {
        'FL': max(0.1, load_fl_kn),  # kN (clamp to avoid negative)
        'FR': max(0.1, load_fr_kn),
        'RL': max(0.1, load_rl_kn),
        'RR': max(0.1, load_rr_kn),
    }
```

**Modification 6: Slip Calculation per Wheel (Line 900-950)**

Add after load calculation:

```python
    # V6.1: Calculate slip per wheel
    if tires_state is None:
        tires_state = TiresState()  # Initialize if not passed
    
    # Grip available per wheel (depends on load, temp, wear)
    wheels_slip = {}
    for wheel_name in ['FL', 'FR', 'RL', 'RR']:
        wheel = wheel_name.lower() if len(wheel_name) == 2 else wheel_name
        tire_state = getattr(tires_state, wheel)  # Get TireState for this wheel
        
        # Thermal multiplier for this wheel
        thermal_mult = _gaussian_thermal_multiplier(
            tire_state.surface_temp_c, 
            tire_state.core_temp_c,
            tyre_compound  # C3, C4, C5, etc.
        )
        
        # Grip reduction from wear
        wear_factor = (100.0 - tire_state.wear_pct) / 100.0
        
        # μ tyre for this wheel
        mu_tyre_wheel = mu_base.get(tyre_compound, 1.3) * thermal_mult * wear_factor
        
        # Grip available
        f_grip_available = wheels_load[wheel_name] * mu_tyre_wheel  # kN
        
        # Grip required (target lateral acceleration)
        target_g_lat = source_waypoint.get('target_g_lat', 1.0)  # g
        f_grip_required = (mass_kg * 9.81 / 1000) * target_g_lat  # kN
        
        # Slip (0.0 = no slip, 1.0 = full slip)
        slip = max(0.0, 1.0 - (f_grip_available / max(0.1, f_grip_required)))
        wheels_slip[wheel_name] = slip
```

**Modification 7: Tire Heating Calculation (Line 950-1050)**

Add after slip calculation:

```python
    # V6.1: Update tire thermal state (per-wheel)
    # Constants
    K_SURFACE_FRIC = 0.95
    K_HYSTERESIS_CORE = 0.35
    K_BRAKING_TRANSFER = 0.25
    
    # Brake heat distribution (front vs rear)
    brake_bias = 0.55  # 55% front, 45% rear (configurable from setup)
    
    dt_step = dist_step / max(state.velocity_ms, 1.0)  # seconds for this waypoint
    
    for wheel_name in ['FL', 'FR', 'RL', 'RR']:
        tire_state = getattr(tires_state, wheel_name.lower())
        load_kn = wheels_load[wheel_name]
        slip = wheels_slip[wheel_name]
        
        # 1. Surface heating (friction + braking)
        friction_heat = K_SURFACE_FRIC * load_kn * slip * state.velocity_ms * dt_step
        
        # Braking heat (only if is_braking)
        brake_heat = 0.0
        if is_braking and brake_pct > 5:
            # Estimate braking energy (rough: 0.5 * m * v^2 / num_wheels)
            braking_energy_mj = 0.5 * mass_kg * state.velocity_ms ** 2 / 1e6
            
            # Distribute to wheels (front gets more from brake bias)
            if wheel_name in ['FL', 'FR']:
                brake_heat = K_BRAKING_TRANSFER * braking_energy_mj * brake_bias / 2 * dt_step
            else:  # RL, RR
                brake_heat = K_BRAKING_TRANSFER * braking_energy_mj * (1-brake_bias) / 2 * dt_step
        
        # Update surface temp (with cooling)
        tire_state.surface_temp_c += (friction_heat + brake_heat)
        
        # 2. Core heating (hysteresis)
        core_heat = K_HYSTERESIS_CORE * load_kn * state.velocity_ms * dt_step
        tire_state.core_temp_c += core_heat
        
        # 3. Cooling (convective, asymmetric for brake duct)
        h_conv_base = 15.0
        brake_duct_opening = setup.get('brake_duct', 0.5)  # 0.0-1.0
        
        if wheel_name in ['FL', 'FR']:
            # Front tires benefit from brake duct
            h_conv = h_conv_base * state.velocity_ms * (0.5 + brake_duct_opening)
        else:
            # Rear tires only get ram-air
            h_conv = h_conv_base * state.velocity_ms * 0.5
        
        q_cool = h_conv * (tire_state.surface_temp_c - 25.0) * dt_step / 1000.0
        tire_state.surface_temp_c -= q_cool
        
        # 4. Wear accumulation
        temp_dev = abs(tire_state.surface_temp_c - _get_optimal_temp(tyre_compound))
        sigma = _get_sigma(tyre_compound)  # Window width
        
        if temp_dev < sigma:
            severity = 1.0
        else:
            severity = 1.0 + ((temp_dev - sigma) / sigma) ** 1.5
        
        k_wear = {'C5': 0.19, 'C4': 0.18, 'C3': 0.17}.get(tyre_compound, 0.18)
        wear_per_km = k_wear * severity * slip
        wear_delta = wear_per_km * (dist_step / 1000.0)
        tire_state.wear_pct += wear_delta
        
        # Clamp temps and wear
        tire_state.surface_temp_c = max(20.0, min(150.0, tire_state.surface_temp_c))
        tire_state.core_temp_c = max(20.0, min(130.0, tire_state.core_temp_c))
        tire_state.wear_pct = min(100.0, tire_state.wear_pct)
```

**Modification 8: Helper Functions to Add (End of file, before integrate_lap_hd)**

```python
def _gaussian_thermal_multiplier(surface_temp_c: float, core_temp_c: float, compound: str) -> float:
    """V6.1: Gaussian thermal multiplier for grip reduction outside window."""
    import math
    
    optim_data = {
        'C5': {'optim_surf': 100.0, 'sigma_surf': 7.5, 'optim_core': 85.0, 'sigma_core': 6.5},
        'C4': {'optim_surf': 105.0, 'sigma_surf': 8.0, 'optim_core': 90.0, 'sigma_core': 7.0},
        'C3': {'optim_surf': 110.0, 'sigma_surf': 8.5, 'optim_core': 95.0, 'sigma_core': 7.5},
    }
    
    data = optim_data.get(compound, optim_data['C4'])
    
    surf_mult = math.exp(-((surface_temp_c - data['optim_surf']) ** 2) / 
                         (2 * data['sigma_surf'] ** 2))
    core_mult = math.exp(-((core_temp_c - data['optim_core']) ** 2) / 
                         (2 * data['sigma_core'] ** 2))
    
    return surf_mult * core_mult

def _get_optimal_temp(compound: str) -> float:
    """V6.1: Get optimal surface temperature for compound."""
    optim_temps = {'C5': 100.0, 'C4': 105.0, 'C3': 110.0}
    return optim_temps.get(compound, 105.0)

def _get_sigma(compound: str) -> float:
    """V6.1: Get thermal window width (sigma) for compound."""
    sigmas = {'C5': 7.5, 'C4': 8.0, 'C3': 8.5}
    return sigmas.get(compound, 8.0)
```

#### B. `python_backend/lap_simulator/physics_v4/tyres/tyre_thermal.py`

**File Location:** [tyre_thermal.py](python_backend/lap_simulator/physics_v4/tyres/tyre_thermal.py)

**Modification 1: Add TiresState dataclass (After TyreThermalState, Line 26)**

```python
@dataclass
class TiresState:
    """Container for all 4 wheels tire state (V6.1)."""
    fl: TireState = field(default_factory=TireState)  # Front Left
    fr: TireState = field(default_factory=TireState)  # Front Right
    rl: TireState = field(default_factory=TireState)  # Rear Left
    rr: TireState = field(default_factory=TireState)  # Rear Right
    
    def reset_at_pit_stop(self):
        """Reset all tires at pit stop (new tires)."""
        self.fl = TireState(surface_temp_c=85.0, core_temp_c=75.0, wear_pct=0.0)
        self.fr = TireState(surface_temp_c=85.0, core_temp_c=75.0, wear_pct=0.0)
        self.rl = TireState(surface_temp_c=85.0, core_temp_c=75.0, wear_pct=0.0)
        self.rr = TireState(surface_temp_c=85.0, core_temp_c=75.0, wear_pct=0.0)
```

(Add import: `from dataclasses import dataclass, field`)

#### C. `python_backend/lap_simulator/physics_v4/core/car_setup.py`

**File Location:** [car_setup.py](python_backend/lap_simulator/physics_v4/core/car_setup.py)

**Modification: Add brake_duct to setup dictionary**

If not already present, ensure setup dict includes:
```python
"brake_duct": float,  # 0.0-1.0, cooling vs drag trade-off
```

### 11.2 Integration Flow

**High-Level Flow for V6.1 Degradation:**

```
integrate_lap_hd(circuit_id, ...)
  ├─ Load waypoints + aero calibration
  ├─ Initialize: state = PhysicsState()
  │  └─ state.tires_state = TiresState()  [V6.1]
  │
  └─ For each waypoint:
      └─ integrate_waypoint(state, waypoint, ..., tires_state, ...)
         ├─ Calculate per-wheel loads (load_fl/fr/rl/rr) [NEW V6.1]
         ├─ Calculate per-wheel slip (slip_fl/fr/rl/rr) [NEW V6.1]
         ├─ Update per-wheel temps (surface/core) [NEW V6.1]
         ├─ Calculate per-wheel wear (wear_pct) [NEW V6.1]
         ├─ Apply thermal multiplier (μ = mu_base × thermal_mult × wear_factor) [MODIFIED V6.1]
         └─ Return updated: state, tires_state
  
  └─ On pit stop:
      └─ tires_state.reset_at_pit_stop()  [NEW V6.1]
         └─ All 4 wheels: surface=85°C, core=75°C, wear=0%
```

### 11.3 Key Interfaces

**Signature Changes:**

1. **integrate_waypoint()**
   - Add: `tires_state: Optional[TiresState] = None`
   - Pass: `tires_state=state.tires_state` when calling

2. **PhysicsState dataclass**
   - Add: `tires_state: Optional[TiresState] = None`

3. **car_setup.py simulate_lap()**
   - Ensure `setup` dict has `"brake_duct": float` (0.0-1.0)

### 11.4 Telemetry Logging (Per Lap)

When logging results, add per-wheel telemetry:

```python
telemetry_point = {
    # ... existing fields ...
    'tires_fl_temp_surface_c': state.tires_state.fl.surface_temp_c,
    'tires_fl_temp_core_c': state.tires_state.fl.core_temp_c,
    'tires_fl_wear_pct': state.tires_state.fl.wear_pct,
    'tires_fr_temp_surface_c': state.tires_state.fr.surface_temp_c,
    'tires_fr_temp_core_c': state.tires_state.fr.core_temp_c,
    'tires_fr_wear_pct': state.tires_state.fr.wear_pct,
    # ... repeat for RL, RR ...
}
```

### 11.5 Implementation Order (Recommended)

1. **Phase 1:** Add TireState/TiresState dataclasses + PhysicsState.tires_state field
2. **Phase 2:** Add per-wheel load distribution calculations in integrate_waypoint()
3. **Phase 3:** Add per-wheel slip calculations + heat generation
4. **Phase 4:** Add per-wheel wear accumulation
5. **Phase 5:** Integrate thermal multiplier into grip calculation
6. **Phase 6:** Add telemetry logging
7. **Phase 7:** Run validation test suite

---

## 10. Implementation Checklist

Before releasing V6.1, verify:

- [ ] All thermal constants quantified in code (k_surface_fric, k_hysteresis_core, k_braking_transfer)
- [ ] Gaussian thermal multiplier integrated into grip calculation
- [ ] Tire state persistence across laps (wear_pct carries forward)
- [ ] Brake fade state tracking (temp_front_c, temp_rear_c, heat_accumulated_kj)
- [ ] Brake duct drag addition to aero assembly
- [ ] Fuel consumption loop (consume ~14-15kg/lap at RACE pace)
- [ ] Sub-stepping for thermal integration (0.01s substeps)
- [ ] Telemetry logging (tyre_surface_temp, tyre_core_temp, brake_temp_front, fade_factor, fuel_remaining)
- [ ] Regression test passes: V6.1 QUALIFY = V6.2 (within ±0.1s)
- [ ] Multi-lap test passes: 5-lap race shows realistic degradation
- [ ] Pit stop reset logic (all thermal state reset, wear reset, fuel refilled)
- [ ] Documentation updated with all parameters
