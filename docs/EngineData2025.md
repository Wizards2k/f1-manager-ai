Ecco una panoramica tecnica dettagliata sulle **Power Unit (PU)** secondo i regolamenti tecnici FIA **2025** (l'ultimo anno dell'era attuale prima del cambio regolamentare del 2026 che rimuoverà l'MGU-H).

Questi dati sono fondamentali per la fisica di un simulatore, poiché la gestione dell'energia (ERS) è complessa e strategica.

### 1. Specifiche Tecniche Hardware (Regolamento 2025)

Il motore è ibrido: **ICE** (Termico) + **ERS** (Sistema di recupero energia).

| Componente | Specifica | Dettagli per il Simulatore |
| --- | --- | --- |
| **ICE** | 1.6L V6 Turbo (90°) | Potenza: ~850 CV (630 kW). Limite giri: 15.000 rpm (in realtà cambiano marcia a 11.5k-12k per via del flusso carburante). |
| **MGU-K** (Cinetico) | Motore elettrico sull'albero motore | **Potenza Max:** 120 kW (~161 CV). Funziona sia in trazione (deploy) che in frenata (harvest). |
| **MGU-H** (Calore) | Motore elettrico sul turbo | **Potenza:** Illimitata (teoricamente). Recupera energia dai gas di scarico e tiene il turbo in rotazione (Anti-lag). |
| **ES** (Energy Store) | Batteria (Pacco celle) | Peso min: 20kg. Voltaggio: ~800V-1000V. Capacità reale: ~5-6 MJ (utilizzabile per regolamento: 4 MJ/giro). |
| **Fuel Flow** | Flusso Carburante | Max 100 kg/ora. Questo appiattisce la curva di potenza sopra i 10.500 giri. |

---

### 2. Flussi di Energia (La "Logica" dell'Ibrido)

Qui sta il cuore della simulazione. Non è una semplice batteria "carica/scarica". Ci sono regole ferree sui flussi (misurati in **MegaJoule, MJ**).

* **Conversione utile:** .

#### I Limiti Regolamentari (Hard Limits)

1. **ES  MGU-K (Deploy da Batteria):** Max **4 MJ** per giro. (Una volta consumati questi, il motore elettrico "taglia" (clipping), a meno che non intervenga l'MGU-H).
2. **MGU-K  ES (Harvest in Frenata):** Max **2 MJ** per giro.
3. **MGU-H  ES (Harvest da Scarico):** **Illimitato**.
4. **MGU-H  MGU-K (Direct Drive):** **Illimitato**. *Questo è cruciale.*

> **Il "Trucco" del Direct Drive:** Quando vedi un'auto che continua a spingere a 330 km/h senza tagliare potenza, sta usando l'energia generata dall'MGU-H e la manda *direttamente* all'MGU-K, bypassando la batteria. Questo non conta nel limite dei 4 MJ.

---

### 3. Mappature Motore (Engine Modes / STRAT)

I team usano selettori rotativi sul volante (spesso etichettati come STRAT, SOC, o MIX). Ecco come configurarli nel simulatore:

#### A. Qualifica ("Hotlap" / "Strat 1")

* **ICE:** Mix carburante massimo (ricco).
* **ERS Deploy:** 100% su tutto il giro.
* **ERS Harvest:** Minimo (solo frenate violente).
* **Obiettivo:** Arrivare al traguardo con la batteria (SOC) quasi allo 0%.
* **Effetto:** Massima prestazione, insostenibile per più di 1-2 giri consecutivi (surriscaldamento e batteria vuota).

#### B. Gara - Bilanciato ("Race" / "Strat 5-7")

* **Logic (SOC Neutral):** L'energia spesa deve essere uguale a quella recuperata nel giro.
* **Deploy:** Taglia la potenza elettrica alla fine dei rettilinei (Derating) prima della staccata per risparmiare energia.
* **MGU-H:** Lavora al massimo per tenere la batteria stabile.

#### C. Sorpasso ("Overtake Button" / K1 / K2)

* Un bottone fisico (hold) o un toggle.
* Scavalca la logica di gestione (Derating) e forza il **120 kW** di deploy immediato.
* Consuma il budget dei 4 MJ molto velocemente.

#### D. Ricarica ("Recharge" / "Slow" / "Cool")

* Usato in VSC, Safety Car o In-Lap.
* **Harvesting:** Molto aggressivo sull'asse posteriore (freno motore elettrico forte).
* **Deploy:** Quasi nullo.
* **ICE:** Taglio cilindri o miscela magra per raffreddare.

---

### 4. Dati Fisici per il JSON del Simulatore

Ecco un esempio di struttura dati per un motore generico 2025 (es. Ferrari/Honda style) da inserire nel tuo codice.

```json
{
  "engine_specs": {
    "ice_max_power_hp": 855,
    "ice_max_torque_nm": 480,
    "ice_redline_rpm": 12500,
    "idle_rpm": 4500,
    "fuel_tank_capacity_kg": 110,
    "fuel_flow_limit_kg_h": 100
  },
  "ers_specs": {
    "mguk_max_power_kw": 120,
    "mguk_max_torque_nm": 200, 
    "battery_capacity_mj": 5.0,
    "regulatory_caps": {
      "deploy_per_lap_mj": 4.0,
      "harvest_mguk_per_lap_mj": 2.0,
      "harvest_mguh_per_lap_mj": "unlimited"
    }
  },
  "maps": {
    "qualifying": {
      "deploy_aggressiveness": 1.0,
      "harvest_aggressiveness": 0.2,
      "fuel_mix": 1.0,
      "target_soc_end_lap": 0.1
    },
    "race_balanced": {
      "deploy_aggressiveness": 0.85,
      "harvest_aggressiveness": 0.8,
      "fuel_mix": 0.95,
      "target_soc_end_lap": "neutral"
    },
    "save_recharge": {
      "deploy_aggressiveness": 0.3,
      "harvest_aggressiveness": 1.0,
      "fuel_mix": 0.8,
      "target_soc_end_lap": 0.9
    }
  },
  "deployment_logic": {
    "clipping_speed_kmh": 310, 
    "overtake_mode_duration_sec": 15
  }
}

```

### 5. Dettagli "Pro" per il Realismo

1. **Brake Migration (Brake-by-wire):** Quando la batteria è piena, l'MGU-K non può più frenare l'auto (non ha dove mettere l'energia). Il simulatore deve compensare spostando automaticamente la frenata sui dischi posteriori idraulici, altrimenti il pilota va lungo (brake balance shift).
2. **Turbo Lag & Anti-Lag:** L'MGU-H tiene il turbo sempre in pressione. Se l'MGU-H si rompe (o finisce energia), il motore termico ha un turbo lag enorme (inguidabile).
3. **Consumo Carburante:** Circa 1.35 kg - 1.5 kg per giro (dipende dalla pista). Se metti meno di 110kg in partenza sei più veloce (ogni 10kg sono circa 0.3s al giro), ma devi fare "Lift and Coast" (alzare il piede prima della frenata) a fine gara.

Vuoi che ti generi una curva di coppia approssimativa (Torque Curve) combinata ICE + Elettrico per capire come erogano la potenza?


Ecco i dati per simulare la curva di erogazione (Torque Curve).

In F1 l'obiettivo non è avere una curva "appuntita", ma una linea di potenza il più piatta possibile verso l'alto. Qui entra in gioco il concetto di **"Torque Fill"**: il motore elettrico (MGU-K) riempie i buchi di coppia del motore termico (ICE) ai bassi giri o mentre il turbo va in pressione.

### Analisi della Curva di Erogazione Combinata (2025 Spec)

1. **0 - 4.000 RPM (Launch / Partenza):**
* L'ICE è debole e il turbo non spinge ancora.
* L'MGU-K fornisce la coppia istantanea massima (200 Nm) per lanciare l'auto.


2. **4.000 - 9.500 RPM (Accelerazione Media):**
* Il turbo è a regime. La coppia dell'ICE è al massimo (~500-600 Nm).
* L'MGU-K inizia a calare la coppia per mantenere i 120kW di potenza costante.


3. **10.500 - 12.500 RPM (Top End / Limit):**
* **Il Muro del Flusso:** A 10.500 giri si raggiunge il limite di flusso benzina (100kg/h). Da qui in poi la potenza dell'ICE **non può salire**.
* La coppia *scende* matematicamente (perché , se la potenza è fissa e i giri salgono, la coppia deve scendere).
* Qui si cambia marcia (shift point) per restare nel picco di potenza (circa 11.800 - 12.200 giri).



---

### Tabella Dati (Lookup Table)

*Valori approssimativi per un Top Team (es. Ferrari/Red Bull).*

| RPM | ICE Torque (Nm) | MGU-K Torque (Nm) | Totale (Nm) | Note |
| --- | --- | --- | --- | --- |
| **0** | 0 | 200 | 200 | Solo elettrico (Start) |
| **2000** | 250 | 200 | 450 | Turbo lag |
| **4000** | 480 | 200 | 680 | Uscita curve lente |
| **6000** | 580 | 190 | 770 | Picco spinta |
| **8000** | 600 | 143 | 743 | Max Torque ICE |
| **10500** | 570 | 109 | 679 | Fuel Flow Limit |
| **12000** | 500 | 95 | 595 | Shift Point |
| **13000** | 460 | 88 | 548 | Over-rev (Inutile) |

---

### JSON per il Simulatore

Questo JSON rappresenta una `lut` (Look Up Table) che il tuo motore fisico può interpolare linearmente.

```json
{
  "torque_curve_data": {
    "unit": "Nm",
    "notes": "ICE values based on 100kg/h fuel flow limit. MGU-K values based on 120kW max power cap.",
    "points": [
      {
        "rpm": 0,
        "ice_torque": 0,
        "mguk_torque": 200,
        "total_torque": 200,
        "behavior": "electric_launch"
      },
      {
        "rpm": 1500,
        "ice_torque": 180,
        "mguk_torque": 200,
        "total_torque": 380,
        "behavior": "turbo_spooling"
      },
      {
        "rpm": 4000,
        "ice_torque": 480,
        "mguk_torque": 200,
        "total_torque": 680,
        "behavior": "traction_zone"
      },
      {
        "rpm": 6500,
        "ice_torque": 590,
        "mguk_torque": 176,
        "total_torque": 766,
        "behavior": "peak_acceleration"
      },
      {
        "rpm": 8500,
        "ice_torque": 610,
        "mguk_torque": 134,
        "total_torque": 744,
        "behavior": "mid_range_sustain"
      },
      {
        "rpm": 10500,
        "ice_torque": 575,
        "mguk_torque": 109,
        "total_torque": 684,
        "behavior": "fuel_flow_limit_hit"
      },
      {
        "rpm": 11500,
        "ice_torque": 525,
        "mguk_torque": 99,
        "total_torque": 624,
        "behavior": "optimal_shift_window"
      },
      {
        "rpm": 12500,
        "ice_torque": 480,
        "mguk_torque": 91,
        "total_torque": 571,
        "behavior": "power_dropoff"
      },
      {
        "rpm": 13500,
        "ice_torque": 400,
        "mguk_torque": 85,
        "total_torque": 485,
        "behavior": "mechanical_stress_high"
      }
    ]
  },
  "gear_ratios_example": {
    "description": "Standard 8-speed gearbox ratios (approximate) for Monza/Spa setup",
    "final_drive": 4.1,
    "gears": [
      2.53, 
      1.96, 
      1.63, 
      1.40, 
      1.22, 
      1.10, 
      1.01, 
      0.92
    ]
  }
}

```

### Consigli per l'implementazione fisica:

1. **Interpolazione:** Non usare i valori "a scalini". Usa un'interpolazione lineare o (meglio) una spline cubica tra i punti RPM per avere un'erogazione fluida.
2. **MGU-K Mapping:** Nel codice, moltiplica il valore `mguk_torque` per il valore di pedale dell'acceleratore MA anche per la mappa ERS selezionata (es. in modalità "Ricarica" il valore `mguk_torque` diventa 0 o negativo in rilascio).
3. **Freno Motore:** Ricorda che quando l'acceleratore è a 0, l'MGU-K genera coppia *negativa* (es. -120 Nm) per ricaricare la batteria. Questo deve sommarsi al freno motore meccanico dell'ICE.