Ecco un documento tecnico in formato Markdown progettato per essere integrato direttamente nella documentazione del tuo simulatore. Questo file definisce la fisica, le soglie e le equazioni necessarie per modellare il **Thermal Clipping** (o *Derating Termico*) dell'MGU-H e dell'Inverter.

---

# 📑 Specifica Tecnica: Modello di Thermal Clipping ERS

## 1. Definizione del Fenomeno
Il **Thermal Clipping** è la riduzione automatica della potenza elettrica erogata dall'MGU-K causata dal raggiungimento dei limiti termici dei componenti critici (Inverter, Magneti MGU-H, Celle Batteria). A differenza del clipping regolamentare (limite di 4.0 MJ), il clipping termico dipende dall'efficienza del raffreddamento e dallo stress energetico accumulato.

## 2. Architettura del Modello Termico

Il sistema è modellato come un **corpo a massa termica singola** soggetto a generazione di calore per effetto Joule e dissipazione convettiva.

### A. Equazione del Bilancio Termico
Ad ogni step temporale $dt$, la variazione di temperatura $\Delta T$ è calcolata come:

$$T_{ers}^{(t+dt)} = T_{ers}^{(t)} + \left( \frac{\dot{Q}_{gen} - \dot{Q}_{cool}}{C_{th}} \right) \cdot dt$$

Dove:
* **$\dot{Q}_{gen}$ (W):** Calore generato. $\dot{Q}_{gen} = R_{int} \cdot I^2 \approx k_{joule} \cdot P_{elec}^2$.
* **$\dot{Q}_{cool}$ (W):** Calore dissipato. $\dot{Q}_{cool} = h_{v} \cdot v_{car} \cdot (T_{ers} - T_{amb})$.
* **$C_{th}$ (J/K):** Capacità termica del sistema (Inerzia termica).



---

## 3. Parametri di Configurazione (Mondiale 2025)

| Parametro | Simbolo | Valore Suggerito | Unità |
| :--- | :---: | :---: | :---: |
| Soglia Inizio Clipping | $T_{limit}$ | 102.0 | °C |
| Soglia Taglio Totale | $T_{max}$ | 122.0 | °C |
| Coefficiente Joule | $k_{joule}$ | 0.000045 | - |
| Coeff. Raffreddamento | $h_{v}$ | 0.0025 | - |
| Capacità Termica | $C_{th}$ | 18.0 | kJ/K |

---

## 4. Logica di Derating (Fattore $\eta_{th}$)

La potenza finale erogata $P_{final}$ è il prodotto della potenza richiesta e del coefficiente di efficienza termica:

$$P_{final} = P_{req} \cdot \eta_{th}$$

L'algoritmo di calcolo per $\eta_{th}$ segue una funzione lineare tra le due soglie critiche:

1.  **Zona Safe:** Se $T_{ers} < T_{limit} \implies \eta_{th} = 1.0$
2.  **Zona Clipping:** Se $T_{limit} \leq T_{ers} < T_{max}$:
    $$\eta_{th} = 1.0 - \left( \frac{T_{ers} - T_{limit}}{T_{max} - T_{limit}} \right)$$
3.  **Zona Shutdown:** Se $T_{ers} \geq T_{max} \implies \eta_{th} = 0.0$



---

## 5. Impatto sui Circuiti (Use Cases)

### Monza & Spa-Francorchamps
* **Comportamento:** Alto accumulo termico dovuto a tratti WOT (Wide Open Throttle) > 15 secondi.
* **Risultato:** Il clipping termico si innesca solitamente negli ultimi 200-300 metri dei rettilinei principali, causando un calo della velocità massima di circa **3-5 km/h**.

### Monaco & Singapore
* **Comportamento:** Basso raffreddamento convettivo ($\dot{Q}_{cool}$) dovuto alle basse velocità medie.
* **Risultato:** Rischio di surriscaldamento accumulato nel terzo settore, limitando la trazione elettrica nelle ripartenze lente.

---

## 6. Implementazione (Python Pseudocode)

```python
def apply_thermal_clipping(p_req, v_car, current_temp, dt):
    # Costanti
    t_limit, t_max = 102.0, 122.0
    k_j, h_v, c_th = 0.000045, 0.0025, 18.0
    
    # Bilancio energetico
    q_gen = k_j * (p_req ** 2)
    q_cool = h_v * v_car * (current_temp - 30.0) # 30.0 è T_amb
    
    # Update temperatura
    new_temp = current_temp + ((q_gen - q_cool) / c_th) * dt
    
    # Calcolo efficienza
    if new_temp < t_limit:
        eta = 1.0
    else:
        eta = max(0.0, 1.0 - (new_temp - t_limit) / (t_max - t_limit))
        
    return p_req * eta, new_temp
```

---

## 7. Implementation Completed ✅

### Files Modified
- `python_backend/lap_simulator/power_unit.py` - Modello termico doc-spec (Joule + convettivo)
- `python_backend/lap_simulator/data_types.py` - Nuovi campi `ers_thermal_eta`, `lap_ers_bonus_s`, `last_section_ers_bonus_s`
- `python_backend/lap_simulator/engine_penalty.py` - Funzione `compute_ers_bonus()` con coefficiente 0.125 s/MJ
- `python_backend/lap_simulator/update_section.py` - Integrazione bonus ERS nel calcolo dt_s
- `python_backend/utils/game_logic.py` - Flag `ENABLE_ERS_BONUS = True`
- `python_backend/utils/pu_telemetry_logger.py` - Logging temperatura, eta_th, clipping, bonus
- `python_backend/utils/session_bridge.py` - Payload telemetria esteso con dati ERS
- `python_backend/lap_simulator/lap_simulator.py` - Fix `DEBUG_PENALTIES` NameError

### ERS Bonus Model
Il bonus temporale ERS è calcolato come:

```python
ers_bonus_s = -1 * (deploy_mj + mguh_direct_mj) * 0.125  # secondi guadagnati
```

- **Coefficiente calibrato**: 0.125 s/MJ (guadagno di ~0.125s per MJ deployato)
- **Clamping**: Bonus limitato per sezione per evitare valori eccessivi
- **Solo rettilinei**: Applicato solo su `STRAIGHT_KINDS` (come le penalità motore)

### Thermal Model Constants (Implementati)
| Parametro | Valore | Unità |
|-----------|--------|-------|
| T_limit | 102.0 | °C |
| T_max | 122.0 | °C |
| k_joule | 0.000045 | - |
| h_v | 0.0025 | - |
| C_th | 18.0 | kJ/K |

### Telemetry Fields Added
- `ers_temp_c` - Temperatura ERS corrente
- `ers_thermal_eta` - Coefficiente di efficienza termica (0.0-1.0)
- `ers_clipping_active` - Flag clipping attivo
- `section_ers_bonus_s` - Bonus ERS sezione corrente
- `lap_ers_bonus_s` - Bonus ERS cumulativo per giro

### Validation
- ✅ Temperatura ERS parte da T_amb (~25°C) e sale con deployment
- ✅ Su circuiti veloci (Suzuka/Monza): raffreddamento efficace, nessun clipping
- ✅ Su circuiti lenti (Monaco): rischio surriscaldamento settore 3
- ✅ Bonus ERS negativo (guadagno tempo) solo su rettilinei
- ✅ Accumulo lap_ers_bonus_s corretto per telemetria

---

**Vuoi che aggiungiamo una variabile per la "Mappa di Raffreddamento" (Radiator Opening)?** Questo ti permetterebbe di simulare la perdita di velocità in rettilineo dovuta al Drag quando decidi di raffreddare di più per evitare il clipping.