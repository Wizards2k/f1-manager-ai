Ecco il contenuto dell'ultima risposta formattato in **Markdown (MD)**, pronto per essere salvato come documentazione tecnica per il tuo simulatore.

---

# Specifiche Tecniche ERS: MGU-H, MGU-K e Direct Drive (F1 2025)

Questo documento dettaglia i flussi energetici e le logiche di recupero dell'energia per le Power Unit di Formula 1, focalizzandosi sul bypass della batteria tramite il Direct Drive.

## 1. Architettura dei Flussi (Stime 2025)

Il limite regolamentare di scarica dalla batteria (ES) all'MGU-K è di **4 MJ per giro**. Tuttavia, le piste ad alta velocità richiedono spesso tra i **6 e gli 8 MJ** totali di assistenza elettrica. La differenza viene colmata dall'energia recuperata dall'MGU-H e inviata direttamente all'MGU-K.

### Tabella: Stima Recupero e Destinazione Energia per Tipologia di Pista

| Tipo Pista | Recupero Totale MGU-H | Direct Drive (H → K) | Ricarica (H → ES) | Note Tecniche |
| --- | --- | --- | --- | --- |
| **Monza (Power)** | ~7.0 - 8.0 MJ | **4.0 - 5.0 MJ** | 2.0 - 3.0 MJ | Priorità assoluta alla spinta in rettilineo. |
| **Silverstone (Mix)** | ~5.0 - 6.0 MJ | **2.5 - 3.5 MJ** | 2.5 MJ | Bilanciamento tra deploy e mantenimento SOC. |
| **Monaco (Twist)** | ~2.0 - 2.5 MJ | **0.5 MJ** | 1.5 - 2.0 MJ | Recupero limitato, focus sulla ricarica batteria. |

---

## 2. Logica Operativa dell'ECU

Per la simulazione, la priorità di alimentazione dell'MGU-K (limitato a **120 kW**) deve seguire questo schema gerarchico:

1. **Generazione MGU-H:** Calcolo dell'energia istantanea prodotta dal turbo.
2. **Direct Drive:** Invio dell'energia prodotta dall'H direttamente al K (Bypass del limite 4 MJ).
3. **Battery Drain:** Se la richiesta del pilota è > dell'energia fornita dall'H, preleva il rimanente dalla batteria (fino a completare i 120 kW).
4. **Accounting:** Solo la quota prelevata dalla batteria (punto 3) viene sottratta dal budget regolamentare di 4 MJ/giro.

---

## 3. Dataset per il Simulatore (JSON)

### Efficienza di Recupero MGU-H (Lookup Table)

Questo JSON definisce quanta potenza (kW) l'MGU-H è in grado di generare in base al carico motore. Valori negativi indicano consumo (Anti-lag).

```json
{
  "mguh_harvesting_efficiency": {
    "unit": "kW",
    "description": "Potenza netta generata dall'MGU-H in base a RPM e Throttle",
    "points": [
      { "rpm": 4000, "throttle": 0.0, "net_harvest_kw": -10, "mode": "anti_lag_consumption" },
      { "rpm": 4000, "throttle": 1.0, "net_harvest_kw": 0, "mode": "neutral" },
      { "rpm": 8000, "throttle": 1.0, "net_harvest_kw": 35, "mode": "moderate_harvest" },
      { "rpm": 10000, "throttle": 1.0, "net_harvest_kw": 60, "mode": "high_harvest" },
      { "rpm": 12000, "throttle": 1.0, "net_harvest_kw": 85, "mode": "peak_harvest" }
    ]
  }
}

```

### Profili Strategici per Circuito

Configurazioni predefinite per bilanciare l'uso dell'MGU-H tra ricarica e spinta diretta.

```json
{
  "energy_strategy_profiles": {
    "high_speed_spec": {
      "track_example": "Monza / Spa",
      "mguh_to_mguk_bias": 0.85, 
      "mguh_to_es_bias": 0.15,
      "estimated_direct_drive_mj_per_lap": 4.8
    },
    "balanced_spec": {
      "track_example": "Barcelona / Silverstone",
      "mguh_to_mguk_bias": 0.60,
      "mguh_to_es_bias": 0.40,
      "estimated_direct_drive_mj_per_lap": 3.1
    },
    "low_speed_spec": {
      "track_example": "Monaco / Hungaroring",
      "mguh_to_mguk_bias": 0.20,
      "mguh_to_es_bias": 0.80,
      "estimated_direct_drive_mj_per_lap": 0.6
    }
  }
}

```

---

## 4. Note sul Realismo Fisico


* **Derating (Clipping):** Se il budget di 4 MJ della batteria termina prima della fine del rettilineo, l'auto subirà un calo di potenza improvviso. La velocità massima sarà sostenuta solo dai ~40-60 kW residui del Direct Drive (se disponibili), portando a una perdita di circa 20-30 km/h rispetto alla velocità di punta massima.
* **Efficienza Termica:** L'MGU-H è sensibile al calore. In simulazione, un uso prolungato del Direct Drive in aria sporca (dietro un'altra vettura) dovrebbe ridurre l'efficienza di recupero del 5-10%.

## 5. Logica della Capacità Batteria (Energy Store - ES)

Nel regolamento F1 2025 la batteria ha una capacità fisica (~5.5 MJ) maggiore del limite regolamentare di deploy (4 MJ). Questo buffer garantisce:

### 5.1 Perché una batteria più grande?

1. **Finestra di efficienza ("sweet spot"):**
   - 0-10% SOC → voltaggio instabile, difficile mantenere i 120 kW.
   - 90-100% SOC → resistenza interna alta, ricarica lenta.
   - Operare tra 15% e 85% mantiene la batteria nel range ottimale.
2. **Stabilità del voltaggio (`P = V · I`):** mantenendo `V` alto, non serve aumentare `I` → meno calore Joule.
3. **Inerzia termica:** più massa chimica = distribuzione migliore dei 120 kW scaricati, quindi meno derating preventivo.

### 5.2 Parametri per il simulatore (JSON)

```json
{
  "battery_physical_model": {
    "nominal_capacity_mj": 5.8,
    "usable_regulatory_limit_mj": 4.0,
    "voltage_sag_threshold": 0.15,
    "thermal_derating_start_c": 115.0
  },
  "efficiency_curve": {
    "notes": "Moltiplicatore di potenza disponibile in base al SOC (State of Charge) reale",
    "points": [
      { "soc": 1.00, "efficiency": 0.98, "comment": "Internal resistance high" },
      { "soc": 0.50, "efficiency": 1.00, "comment": "Optimal window" },
      { "soc": 0.15, "efficiency": 0.95, "comment": "Voltage sag begins" },
      { "soc": 0.05, "efficiency": 0.75, "comment": "Heavy clipping to protect cells" }
    ]
  }
}
```

### 5.3 Sintesi per il gameplay

- **Consistenza:** MGU-K eroga 120 kW costanti lungo il rettilineo, senza crolli improvvisi.
- **Affidabilità:** SOC controllato → meno ingressi in "Thermal Protection Mode" → MGU-H può ricaricare in modo stabile.
- **UI/Feedback:** i valori della curva vengono esposti nel pannello ingegnere per motivare eventuali istruzioni di "Recharge" o "Save".

## 6. Rigenerazione profili e fitting automatico

- Lo script `scripts/powerunit_fit.py` legge le telemetrie (`python_backend/data/circuits/*_Telemetry.json`) e assegna ogni circuito a un profilo MGU-H (high/balanced/low) basato su `power_bias` e `drs_ratio`.
- Per ogni mappa (`ECONOMY`…`RECHARGE`) calcola `mguh_direct_ratio`, `mguh_power_kw` e annota `_meta.mguh_profile` + `lap_time_s` nei derived `config/circuits/derived/<cid>/pu_maps.json`.
- I report in `reports/calibration/pu/<cid>.md` descrivono i valori generati per audit e tuning manuale.

## 7. Telemetria e strumenti UI

- Il `SessionBridge` serializza ora `lap_mguh_direct_mj`, `lap_mguh_harvest_mj` e il trace per sezione (`mguh_direct_mj`, `mguh_es_mj`).
- La PU modal (garage v3) mostra i contatori MGU-H (tiles, chip giro, tabella), permettendo a QA e giocatore di verificare quando il direct-drive copre il deploy.
- Gli orchestratori (PSO, strumenti QA) consumano gli stessi campi per rilevare `mguh_clip`, monitorare la quota di energia diretta e pianificare cicli Recharge.