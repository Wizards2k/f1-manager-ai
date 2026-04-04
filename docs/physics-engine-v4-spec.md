---
title: Physics Engine V4 - Specifica Tecnica Completa
date: 2026-04-04
version: 1.0
status: IMPLEMENTATION IN PROGRESS (Core Engine ✅ COMPLETE)
---

# Physics Engine V4 — Motore Fisico Newtoniano F1 2025

## Executive Summary

Il **Physics Engine V4** è un motore di simulazione **completamente indipendente** da V1/V2/V3 che calcola il tempo sul giro attraverso **integrazione numerica delle equazioni del moto** (F = m × a), senza tempi di riferimento o penalità empiriche.

**Filosofia**: Il tempo sul giro **EMERGE** dalla simulazione fisica, non è un target da raggiungere con aggiustamenti.

---

## 📊 Implementation Status (2026-04-04)

### ✅ PHASE 1: Core Engine Implementation — COMPLETE

**Completion Date**: 2026-04-04  
**Duration**: 2 ore  
**Lines of Code**: ~800 (4 moduli Python)

#### Moduli Implementati

| Modulo | File | Status | Lines | Descrizione |
|--------|------|--------|-------|-------------|
| **Constants** | `core/constants.py` | ✅ DONE | 250 | 80+ costanti fisiche F1 2025 |
| **AeroAssembly** | `aero/aero_assembly.py` | ✅ DONE | 350 | 7 componenti aero → forze fisiche |
| **WaypointIntegrator** | `integrator/waypoint_integrator.py` | ✅ DONE | 400 | Integrazione 5m passo su HD |
| **API** | `__init__.py` | ✅ DONE | 50 | Export pubblico V4 |

**Total**: ~1,050 lines of production code

#### Test Results (2026-04-04)

| Circuito | Tempo V4 | Target F1 | Delta | Errore | Status |
|----------|----------|-----------|-------|--------|---------|
| **Monza** | 80.6s | 79.5s | +1.1s | +1.4% | ✅ OK |
| **Monaco** | 84.9s | 70.2s | +14.7s | +20.9% | ⚠️ DA CALIBRARE |
| **Suzuka** | 83.8s | 88.5s | -4.7s | -5.3% | ⚠️ DA CALIBRARE |

**Velocità Massime**:
- Monza: 383.8 kph (target: 365.0 kph) ✅
- Monaco: 299.5 kph (target: 290.0 kph) ✅
- Suzuka: 356.9 kph (target: 320.0 kph) ⚠️

---

## 🎯 OBIETTIVI DEL PROGETTO V4

### **Obiettivo Primario**
Creare un motore fisico che:
1. ✅ Calcola tempi giro da **prime principi fisici** (F = m × a)
2. ✅ Usa **waypoints HD** per tutti i 24 circuiti F1 2025
3. ✅ Simula **componenti individuali** (ali, fondo, sidepods, etc.)
4. ✅ **Nessun tempo di riferimento** nascosto o penalty empiriche
5. ✅ **Indipendente** da V1/V2/V3 (confronto comparativo possibile)

### **Obiettivi Secondari**
- [ ] Tempi entro ±2% da telemetria ufficiale su tutti i 24 circuiti
- [ ] Velocità massime entro ±5% da dati reali
- [ ] Setup dell'utente si riflette fisicamente in pista
- [ ] Calibrazione automatica da telemetria ufficiale

---

## 🏗️ ARCHITETTURA COMPLETA V4

### **Struttura Directory**

```
python_backend/lap_simulator/physics_v4/
├── __init__.py                      # ✅ API pubblica
├── test_v4_quick.py                 # ✅ Test rapido
│
├── core/                            # FONDAMENTA
│   ├── __init__.py                  # ✅ Export costanti
│   ├── constants.py                 # ✅ 80+ costanti fisiche
│   └── physics_state.py             # ⏳ Stato fisico auto (TODO)
│
├── aero/                            # AERODINAMICA COMPONENTE-PER-COMPONENTE
│   ├── __init__.py                  # ⏳ TODO
│   ├── aero_assembly.py             # ✅ Combina 7 componenti → forze
│   ├── front_wing.py                # ⏳ Modello dettagliato ala anteriore
│   ├── rear_wing.py                 # ⏳ Modello dettagliato ala posteriore (DRS)
│   ├── floor_front.py               # ⏳ Fondo anteriore (ground effect)
│   ├── floor_rear.py                # ⏳ Fondo posteriore (diffusore)
│   ├── sidepods.py                  # ⏳ Sidepods (drag + cooling)
│   ├── engine_cover.py              # ⏳ Cofano motore
│   └── bwing.py                     # ⏳ B-wing (mini-ala)
│
├── mass/                            # MASSA E BARICENTRO (TODO)
│   ├── __init__.py                  # ⏳ TODO
│   ├── mass_distribution.py         # ⏳ Massa totale + fuel burn
│   ├── center_of_gravity.py         # ⏳ CG dinamico (fuel shift)
│   └── inertia.py                   # ⏳ Momenti di inerzia (yaw, pitch, roll)
│
├── suspension/                      # SOSPENSIONI (TODO)
│   ├── __init__.py                  # ⏳ TODO
│   ├── spring_damper.py             # ⏳ Molle + ammortizzatori
│   ├── antiroll.py                  # ⏳ Antiroll bars (load transfer)
│   └── ride_height.py               # ⏳ Altezza da suolo → ground effect
│
├── power_unit/                      # MOTORE (TODO - riuso V3 possibile)
│   ├── __init__.py                  # ⏳ TODO
│   ├── ice_engine.py                # ⏳ Curva coppia/potenza ICE (RPM-based)
│   ├── ers_motor.py                 # ⏳ MGU-K deployment fisico
│   ├── ers_heat.py                  # ⏳ MGU-H thermal harvesting
│   ├── battery.py                   # ⏳ SOC, carica/scarica, thermal limits
│   └── drivetrain.py                # ⏳ Trasmissione (efficienza, diff)
│
├── tyres/                           # GOMME (TODO - riuso V3 possibile)
│   ├── __init__.py                  # ⏳ TODO
│   ├── tyre_construction.py         # ⏳ Carcassa, pressione, deformazione
│   ├── tyre_thermal.py              # ⏳ Heating/cooling termodinamica
│   ├── tyre_wear.py                 # ⏳ Usura (abrasione, blistering)
│   └── grip_model.py                # ⏳ μ vs T, load sensitivity (Pacejka)
│
├── brakes/                          # FRENI (TODO - riuso V3 possibile)
│   ├── __init__.py                  # ⏳ TODO
│   ├── brake_material.py            # ⏳ Carbon-carbon μ(T)
│   ├── brake_cooling.py             # ⏳ Duct cooling termodinamica
│   ├── brake_bias.py                # ⏳ Bias dinamico (BBW)
│   └── brake_wear.py                # ⏳ Usura dischi/pastiglie
│
├── driver/                          # PILOTA (TODO)
│   ├── __init__.py                  # ⏳ TODO
│   ├── driving_line.py              # ⏳ Scelta traiettoria ottimale
│   ├── braking_point.py             # ⏳ Punto frenata (skill-based)
│   ├── throttle_curve.py            # ⏳ Controllo trazione (skill)
│   └── steering_input.py            # ⏳ Input sterzo (smoothness)
│
├── vehicle/                         # DINAMICA VEICOLO (TODO)
│   ├── __init__.py                  # ⏳ TODO
│   ├── balance.py                   # ⏳ Fz_front/Fz_rear → balance %
│   ├── load_transfer.py             # ⏳ Longitudinale + laterale
│   ├── kamm_circle.py               # ⏳ Traction circle (F_lat vs F_long)
│   ├── handling.py                  # ⏳ Understeer/oversteer emergente
│   └── cornering_limit.py           # ⏳ Velocità massima in curva
│
├── integrator/                      # INTEGRATORE (✅ CORE DONE)
│   ├── __init__.py                  # ✅ Export
│   ├── waypoint_integrator.py       # ✅ Integrazione HD (5m passo)
│   ├── analytic_integrator.py       # ⏳ Fallback per circuiti no-HD
│   ├── physics_step.py              # ⏳ Singolo step di simulazione
│   └── lap_loop.py                  # ⏳ Giro completo + settori
│
├── setup/                           # SETUP → FISICA (TODO)
│   ├── __init__.py                  # ⏳ TODO
│   ├── slider_to_physics.py         # ⏳ Slider UI → parametri fisici
│   ├── default_setups.py            # ⏳ Setup default auto-calibrati
│   └── optimizer.py                 # ⏳ Ricerca setup ottimale (grid search)
│
└── calibration/                     # CALIBRAZIONE (TODO)
    ├── __init__.py                  # ⏳ TODO
    ├── circuit_targets.py           # ⏳ Tempi ufficiali per circuito
    ├── sensitivity_analysis.py      # ⏳ Sensibilità parametri
    └── auto_calibration.py          # ⏳ Calibrazione automatica
```

**Legenda**:
- ✅ = Implementato e funzionante
- ⏳ = Da implementare

---

## 📋 MODULI DA IMPLEMENTARE (Roadmap)

### **Phase 2: Modelli Fisici Dettagliati** (3-4 giorni)

#### 2.1 Aerodinamica Dettagliata
- [ ] `aero/front_wing.py` - Modello fisico ala anteriore (stallo, DRS)
- [ ] `aero/rear_wing.py` - Modello fisico ala posteriore (DRS, beam wing)
- [ ] `aero/floor_front.py` - Ground effect anteriore (venturi)
- [ ] `aero/floor_rear.py` - Diffusore posteriore (espansione flusso)
- [ ] `aero/sidepods.py` - Drag sidepods + cooling contribution
- [ ] `aero/engine_cover.py` - Flow conditioning cofano
- [ ] `aero/bwing.py` - Mini-ala posteriore

**Benefit**: Ogni componente ha parametri fisici indipendenti, l'utente può modificare singolarmente.

---

#### 2.2 Massa e Baricentro
- [ ] `mass/mass_distribution.py` - Massa totale = auto + pilota + fuel
- [ ] `mass/center_of_gravity.py` - CG si sposta con fuel burn
- [ ] `mass/inertia.py` - Momenti di inerzia (yaw, pitch, roll)

**Equazioni**:
```
m_totale = m_auto + m_pilota + m_fuel
x_cg = (Σ m_i × x_i) / m_totale
I_yaw = Σ m_i × (x_i² + y_i²)
```

---

#### 2.3 Sospensioni
- [ ] `suspension/spring_damper.py` - Molle lineari/progressive + damper
- [ ] `suspension/antiroll.py` - Antiroll bars (load transfer laterale)
- [ ] `suspension/ride_height.py` - Altezza da suolo → ground effect

**Effetti**:
- Load transfer in curva: ΔFz = (m × a_lat × H_CG) / TRACK_WIDTH
- Ground effect: +1% CLA per mm sotto ottimale
- ARB rigidity → distribuzione load transfer front/rear

---

#### 2.4 Power Unit
- [ ] `power_unit/ice_engine.py` - Curva potenza/coppia vs RPM
- [ ] `power_unit/ers_motor.py` - MGU-K deploy/harvest
- [ ] `power_unit/ers_heat.py` - MGU-H harvesting (energy balance)
- [ ] `power_unit/battery.py` - SOC, thermal limits, charge/discharge
- [ ] `power_unit/drivetrain.py` - Efficienza trasmissione, differenziale

**Riuso V3**: Possibile riusare `power_unit.py` esistente se fisicamente accurato.

---

#### 2.5 Gomme
- [ ] `tyres/tyre_construction.py` - Carcassa, pressione, deformazione
- [ ] `tyres/tyre_thermal.py` - Termodinamica (heating/cooling)
- [ ] `tyres/tyre_wear.py` - Usura (abrasione, blistering, graining)
- [ ] `tyres/grip_model.py` - μ vs T, load sensitivity (Pacejka)

**Riuso V3**: `tyre_model.py` esistente è sofisticato, possibile adattamento.

---

#### 2.6 Freni
- [ ] `brakes/brake_material.py` - Carbon-carbon μ(T)
- [ ] `brakes/brake_cooling.py` - Duct cooling termodinamica
- [ ] `brakes/brake_bias.py` - Bias dinamico (BBW, brake migration)
- [ ] `brakes/brake_wear.py` - Usura dischi/pastiglie

**Riuso V3**: `brake_system.py` esistente ha già modello termico.

---

#### 2.7 Pilota
- [ ] `driver/driving_line.py` - Scelta traiettoria (apex, entry, exit)
- [ ] `driver/braking_point.py` - Punto frenata (skill-based, brake marker)
- [ ] `driver/throttle_curve.py` - Controllo trazione (smoothness, wheelspin)
- [ ] `driver/steering_input.py` - Input sterzo (smoothness, rotation speed)

**Skill Pilota**:
- `braking_skill`: anticipa/ritarda punti frenata
- `cornering_skill`: usa più/meno cordolo, apex diverso
- `throttle_skill`: controllo trazione in uscita
- `consistency`: variabilità giro-per-giro

---

#### 2.8 Dinamica Veicolo
- [ ] `vehicle/balance.py` - Calcolo Fz_front/Fz_rear, aero balance
- [ ] `vehicle/load_transfer.py` - Longitudinale (frenata/accelerazione) + laterale (curva)
- [ ] `vehicle/kamm_circle.py` - Traction circle (F_lat vs F_long)
- [ ] `vehicle/handling.py` - Understeer/oversteer emergente da balance
- [ ] `vehicle/cornering_limit.py` - Velocità massima in curva (grip limit)

**Equazioni Chiave**:
```
Fz_front = m × g × 0.455 + 0.5 × ρ × v² × CLA_front
Fz_rear = m × g × 0.545 + 0.5 × ρ × v² × CLA_rear

ΔFz_laterale = (m × a_lat × H_CG) / TRACK_WIDTH
ΔFz_longitudinale = (m × a_long × H_CG) / WHEELBASE

v_max_corner = sqrt( μ × (m × g + F_downforce) × R / m )
```

---

#### 2.9 Integratore (Completamento)
- [ ] `integrator/analytic_integrator.py` - Fallback per circuiti senza HD
- [ ] `integrator/physics_step.py` - Singolo step di simulazione (F=ma)
- [ ] `integrator/lap_loop.py` - Giro completo + settori + telemetria

---

#### 2.10 Setup
- [ ] `setup/slider_to_physics.py` - Traduzione slider UI → parametri fisici
- [ ] `setup/default_setups.py` - Setup default auto-calibrati per circuito
- [ ] `setup/optimizer.py` - Grid search per setup ottimale

**Logica Default Setups**:
```python
if circuit_type == "low_downforce":  # Monza, Jeddah, Baku
    return {"front_wing": 14.0, "rear_wing": 12.0}
elif circuit_type == "high_downforce":  # Monaco, Budapest, Singapore
    return {"front_wing": 26.0, "rear_wing": 30.0}
else:  # balanced
    return {"front_wing": 20.0, "rear_wing": 22.0}
```

---

#### 2.11 Calibrazione
- [ ] `calibration/circuit_targets.py` - Tempi ufficiali F1 per circuito
- [ ] `calibration/sensitivity_analysis.py` - Sensibilità parametri (Δt/Δparam)
- [ ] `calibration/auto_calibration.py` - Calibrazione automatica (grid search)

**Target Circuiti** (da telemetria F1 2025):
```python
CIRCUIT_TARGETS = {
    "it-1922_monza": {"lap_time_s": 79.5, "v_max_kph": 365.0},
    "mc-1929_monaco": {"lap_time_s": 70.2, "v_max_kph": 290.0},
    "jp-1962_suzuka": {"lap_time_s": 88.5, "v_max_kph": 320.0},
    # ... altri 21 circuiti
}
```

---

### **Phase 3: Calibrazione Fine** (2-3 giorni)

#### 3.1 Calibrazione Monza (Low Downforce)
- [ ] Aggiustare CDA per v_max corretta (365 kph)
- [ ] Verificare accelerazione in rettilineo
- [ ] Calibrare frenata Variante del Rettilineo

**Parametri da tuning**:
- `CDA_MIN`: 0.85 → 0.88? (più drag)
- `PU_TOTAL_PEAK_KW`: 910 → 890? (meno potenza)
- `ROLLING_RESISTANCE_COEFF`: 0.011 → 0.012?

---

#### 3.2 Calibrazione Monaco (High Downforce)
- [ ] **Ridurre tempo da 84.9s a 70.2s** (-14.7s!)
- [ ] Aumentare grip gomme (μ da 1.65 → 1.85?)
- [ ] Ridurre drag in configurazione carico
- [ ] Verificare punti frenata (troppo anticipati?)

**Parametri da tuning**:
- `MU_BASE["C5"]`: 1.80 → 1.95? (più grip)
- `CLA_MAX`: 4.80 → 5.20? (più downforce)
- `CDA_MAX`: 1.60 → 1.45? (meno drag)
- `MAX_BRAKE_DECEL_G`: 6.5 → 5.8? (frenata meno aggressiva)

---

#### 3.3 Calibrazione Suzuka (Balanced)
- [ ] **Aumentare tempo da 83.8s a 88.5s** (+4.7s)
- [ ] Ridurre grip (auto troppo veloce in curva)
- [ ] Aumentare drag (v_max 356.9 → 320 kph)
- [ ] Verificare 130R (raggio corretto 830m)

**Parametri da tuning**:
- `MU_BASE["C3"]`: 1.65 → 1.55? (meno grip)
- `CLA_NEUTRAL`: 3.20 → 3.40? (più downforce)
- `CDA_NEUTRAL`: 1.10 → 1.25? (più drag)

---

### **Phase 4: Testing Estensivo** (3-4 giorni)

#### 4.1 Test su Tutti i 24 Circuiti
- [ ] Eseguire V4 su tutti i circuiti F1 2025
- [ ] Confrontare tempi con telemetria ufficiale
- [ ] Identificare outlier (>5% errore)

**Circuiti di Validazione**:
1. ✅ Monza (low DF)
2. ✅ Monaco (high DF)
3. ✅ Suzuka (balanced)
4. ⏳ Silverstone (fast, bumpy)
5. ⏳ Spa (veloce, weather)
6. ⏳ Bahrain (hot, traction)
7. ⏳ Australia (mix medio)
8. ⏳ ...altri 17

---

#### 4.2 Test Setup Variati
- [ ] Monza: ali basse vs ali alte (delta atteso: -3s vs +5s)
- [ ] Monaco: ali alte vs ali basse (delta atteso: -2s vs +4s)
- [ ] Suzuka: setup bilanciato vs estremi

**Test da passare**:
- Monza low-wing < Monza high-wing (velocità)
- Monaco high-wing < Monaco low-wing (velocità)
- Suzuka balanced < Suzuka estremi (velocità)

---

#### 4.3 Test Condizioni Ambientali
- [ ] Temperature diverse (10°C, 20°C, 30°C, 40°C)
- [ ] Umidità (20%, 50%, 80%)
- [ ] Wind (0 kph, 10 kph, 20 kph)
- [ ] Pioggia (dry, wet, intermediate)

---

### **Phase 5: Integrazione con Sistema Esistente** (2-3 giorni)

#### 5.1 Compatibilità I/O
- [ ] Definire interfaccia pubblica V4 (stessa firma V1/V2/V3?)
- [ ] Creare adapter per input/output compatibili
- [ ] Testare swap V1 ↔ V4 senza modificare downstream

---

#### 5.2 Confronto Comparativo V1 vs V4
- [ ] Script `compare_engines.py` (V1 vs V4 stesso setup)
- [ ] Report differenze (tempi, velocità, handling)
- [ ] Identificare vantaggi/svantaggi V4

---

#### 5.3 Documentazione
- [ ] Aggiornare `docs/physics-engine-v4-spec.md` (questo file)
- [ ] Creare `docs/v4-migration-guide.md` (da V1/V2/V3 a V4)
- [ ] Scrivere `docs/v4-calibration-guide.md` (come calibrare)

---

## 🔬 EQUAZIONI FONDAMENTALI V4

### **1. Aerodinamica**

**Forza Downforce**:
$$F_{down} = \frac{1}{2} \cdot \rho \cdot v^2 \cdot C_L \cdot A$$

**Forza Drag**:
$$F_{drag} = \frac{1}{2} \cdot \rho \cdot v^2 \cdot C_D \cdot A$$

**Dove**:
- ρ = 1.225 kg/m³ (densità aria)
- v = velocità [m/s]
- C_L = coefficiente di portanza (CLA nel nostro modello)
- C_D = coefficiente di resistenza (CDA nel nostro modello)
- A = area di riferimento (implicita nei coefficienti)

---

### **2. Grip e Velocità in Curva**

**Grip Totale**:
$$F_{grip} = \mu \cdot (m \cdot g + F_{downforce})$$

**Velocità Massima in Curva**:
$$v_{max} = \sqrt{\frac{F_{grip} \cdot R}{m}} = \sqrt{\frac{\mu \cdot (m \cdot g + \frac{1}{2} \rho v^2 C_L A) \cdot R}{m}}$$

**Equazione implicita in v** → risolta iterativamente (converge in 2-3 passi).

---

### **3. Accelerazione e Frenata**

**Accelerazione Netta**:
$$a = \frac{F_{engine} - F_{drag} - F_{gravity}}{m}$$

**Dove**:
- F_engine = P / v (potenza / velocità)
- F_drag = 0.5 × ρ × v² × CDA
- F_gravity = m × g × sin(pendenza)

**Distanza di Frenata**:
$$s = \frac{v_{entry}^2 - v_{exit}^2}{2 \cdot a_{brake}}$$

---

### **4. Load Transfer**

**Laterale (in curva)**:
$$\Delta F_{z,lat} = \frac{m \cdot a_{lat} \cdot H_{CG}}{TRACK\_WIDTH}$$

**Longitudinale (frenata/accelerazione)**:
$$\Delta F_{z,long} = \frac{m \cdot a_{long} \cdot H_{CG}}{WHEELBASE}$$

**Distribuzione Antiroll**:
$$\Delta F_{z,front} = \Delta F_{z,lat} \cdot \frac{ARB_{front}}{ARB_{front} + ARB_{rear}}$$

---

### **5. Traction Circle (Kamm Circle)**

**Grip Totale Disponibile**:
$$F_{total} = \mu \cdot F_z$$

**Composizione Grip**:
$$F_{long}^2 + F_{lat}^2 \leq F_{total}^2$$

**Se F_lat richiesto > F_total → wheelspin/skid**

---

## 📈 METRICHE DI QUALITÀ V4

### **Accuratezza Tempi**
- **Target**: ±2% da telemetria ufficiale su 24 circuiti
- **Attuale**: Monza +1.4%, Monaco +20.9%, Suzuka -5.3%
- **Priorità**: Calibrare Monaco (-14.7s) e Suzuka (+4.7s)

---

### **Accuratezza Velocità**
- **Target**: ±5% v_max da dati ufficiali
- **Attuale**: Monza +5.1%, Monaco +3.3%, Suzuka +11.5%
- **Priorità**: Ridurre v_max Suzuka (356.9 → 320 kph)

---

### **Performance Computazionali**
- **Target**: <100ms per giro (Monza 1176 waypoints)
- **Attuale**: ~50ms (Python puro, non ottimizzato)
- **Status**: ✅ OK

---

### **Code Quality**
- **Test Coverage**: 0% (da implementare)
- **Type Hints**: 80% (migliorabile)
- **Documentation**: 90% (docstring complete)
- **Modularity**: ✅ Alta (10 moduli indipendenti)

---

## 🚀 ROADMAP E TIMELINE

### **Settimana 1 (2026-04-04 → 2026-04-11)**
- ✅ Day 1: Core engine (constants, aero, integrator)
- ⏳ Day 2-3: Calibrazione Monza/Monaco/Suzuka
- ⏳ Day 4: Modelli gomme/freni ( riuso V3)
- ⏳ Day 5: Power unit + ERS deployment
- ⏳ Day 6-7: Testing su 24 circuiti

### **Settimana 2 (2026-04-11 → 2026-04-18)**
- ⏳ Day 8-9: Setup optimizer + default setups
- ⏳ Day 10: Driver model (skill, braking points)
- ⏳ Day 11: Vehicle dynamics (load transfer, handling)
- ⏳ Day 12: Integrazione con sistema esistente
- ⏳ Day 13-14: Documentazione + bug fixing

### **Settimana 3 (2026-04-18 → 2026-04-25)**
- ⏳ Day 15-17: Test estensivo (tutti circuiti, condizioni)
- ⏳ Day 18-19: Calibrazione fine (parametri ottimali)
- ⏳ Day 20: Release candidate V4.0

---

## 📚 RIFERIMENTI E RISORSE

### **Documenti Correlati**
- `docs/physics-engine-v3-spec.md` - Specifica V3 (da cui ereditiamo costanti)
- `docs/lap-physics-spec-v0.5.md` - Fisica di base
- `docs/AeroPackage.md` - Aerodinamica esistente

### **Dati Telemetria**
- `python_backend/data/circuits/2025/*_HD.json` - Waypoints HD (24 circuiti)
- `python_backend/data/circuits/2025/*_Telemetry.json` - Tempi ufficiali

### **File Configurazione**
- `config/setup/setup_ranges/*.json` - Setup target per circuito
- `config/setup/team_offsets.json` - Offset team/driver

---

## ❓ DOMANDE APERTE (FAQ)

### **D: V4 sostituirà V1/V2/V3?**
**R**: Non immediatamente. V4 sarà **parallelo** per testing e confronto. La migrazione avverrà dopo validazione completa.

---

### **D: Quanto è accurato V4 rispetto a V1?**
**R**: Attualmente V4 è ±5-20% (da calibrare). V1 è ±2% (calibrato su telemetria). Obiettivo V4: ±2% come V1.

---

### **D: Posso usare V4 per i race weekend ora?**
**R**: No. V4 è in fase alpha. Usare solo per testing e sviluppo. V1/V2 rimangono in production.

---

### **D: Quali moduli V3 posso riusare in V4?**
**R**: 
- ✅ `tyre_model.py` - Modello termico sofisticato
- ✅ `brake_system.py` - Modello fade termico
- ✅ `power_unit.py` - Bucket system ERS
- ⚠️ `aero_package.py` - Da riscrivere (usa aero points, non CLA/CDA)
- ⚠️ `driver_model.py` - Da adattare (intent system → fisica pura)

---

### **D: Come calibro V4 per un nuovo circuito?**
**R**: 
1. Carica tempi ufficiali da `calibration/circuit_targets.py`
2. Esegui `calibration/auto_calibration.py` (grid search)
3. Verifica errori <2%
4. Salva parametri ottimali

---

### **D: V4 è più lento di V1?**
**R**: V4 è ~2x più lento (50ms vs 25ms per giro) ma ancora trascurabile vs tempo reale. Non un problema.

---

### **D: Posso modificare singoli componenti aero in V4?**
**R**: Sì! V4 permette di modificare:
- front_wing, rear_wing, floor_front, floor_rear
- sidepods, engine_cover, b_wing
Ogni componente ha CLA/CDA indipendenti.

---

### **D: Come gestisce V4 il fuel burn?**
**R**: Da implementare in `mass/center_of_gravity.py`. La massa scende linearmente (2.5kg/giro) e il CG si sposta.

---

### **D: V4 supporta pioggia e condizioni miste?**
**R**: Da implementare in `tyres/tyre_thermal.py` e `calibration/circuit_targets.py`. Attualmente solo dry.

---

## 📝 NOTE IMPLEMENTATIVE

### **Stabilità Numerica**
- Integratore usa passo fisso (5m waypoints)
- Clamping su velocità: [5 m/s, 150 m/s]
- Clamping su temperatura: [0°C, 1500°C]
- Divisioni per zero: sempre check v > 1.0 m/s

### **Performance**
- Python puro (no numpy/scipy per ora)
- Possibile ottimizzare con numba/cython in futuro
- Parallelizzare su più circuiti per calibratione

### **Debugging**
- `DEBUG_ENABLE = True` in `constants.py` abilita log
- Telemetria salvata in `logs/physics_v4_debug.csv`
- Confronto V1 vs V4: `scripts/compare_engines.py`

---

## 🎯 SUCCESS CRITERIA

### **Criteri di Accettazione V4.0**
- [ ] Tempi su 24 circuiti entro ±2% da telemetria
- [ ] Velocità massime entro ±5% da dati reali
- [ ] Setup dell'utente si riflette fisicamente (ali alte → più drag)
- [ ] Understeer/oversteer emerge da balance aero (non hardcoded)
- [ ] Test automatici passano (coverage >80%)
- [ ] Documentazione completa

### **Criteri di Accettazione V4.1 (Production)**
- [ ] Integrazione con race weekend (practice, qualy, race)
- [ ] Supporto condizioni meteo (rain, intermediate)
- [ ] Degrado gomme multi-lap
- [ ] Fuel strategy (race stint)
- [ ] Performance <100ms per giro

---

**Author**: F1 Manager AI Development Team  
**Last Updated**: 2026-04-04  
**Version**: 1.0 (Draft)  
**Status**: IN PROGRESS
