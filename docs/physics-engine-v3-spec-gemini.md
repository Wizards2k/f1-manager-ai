Questo è il passaggio fondamentale per trasformare il tuo simulatore da un "calcolatore di tempi" a una **simulazione fisica scientifica**. Il segreto del Motore V3 non è aggiungere "penalità", ma simulare la **lotta tra forze**.

Ecco il documento di specifiche tecniche dettagliate per lo sviluppo del **Newtonian Physics Engine V3**.

---

# 🏎️ Specifica Tecnica: Motore Fisico Newtoniano (V3)

## 1. Filosofia del Motore
Il Motore V3 abbandona la logica additiva (`tempo + penalità`) per una logica di **Equilibrio delle Forze**. Il tempo sul giro è la *conseguenza* delle accelerazioni limitate dalla fisica.

### Il Modello dei Tre Assi
Ogni waypoint del file `it-1922_monza_HD.json` deve essere elaborato considerando:
1.  **Asse Longitudoinale ($a_x$):** Trazione e Frenata vs Drag.
2.  **Asse Laterale ($a_y$):** Forza Centrifuga vs Grip Aeromeccanico.
3.  **Asse Verticale ($F_z$):** Massa + Downforce (che determina il limite di $a_x$ e $a_y$).

---

## 2. Architettura Aerodinamica: Il Trade-off
Per far "capire" al sistema il delta tra 4° (Monza) e 30° (Monaco), usiamo le equazioni dei fluidi.

### 2.1 Coefficienti Aero ($C_l$ e $C_d$)
Non usare i gradi direttamente, ma mappa l'inclinazione su due coefficienti:
* **$C_l$ (Lift Coefficient):** Determina il Downforce.
* **$C_d$ (Drag Coefficient):** Determina la resistenza all'avanzamento.

**Esempio di Mapping 2025:**
* **Assetto Monza (4°):** $C_l = 2.8, C_d = 0.7$ (Efficienza $\approx 4.0$)
* **Assetto Monaco (30°):** $C_l = 5.2, C_d = 1.4$ (Efficienza $\approx 3.7$)



### 2.2 Calcolo delle Forze Aero
In ogni punto della simulazione, calcola:
$$F_{drag} = \frac{1}{2} \cdot \rho \cdot v^2 \cdot A \cdot C_d$$
$$F_{downforce} = \frac{1}{2} \cdot \rho \cdot v^2 \cdot A \cdot C_l$$

---

## 3. Dinamica del Veicolo: Trazione e Curva

### 3.1 Limite di Grip (Il Cerchio di Kamm)
Il grip totale della gomma è limitato dal carico verticale. Più vai veloce, più il Downforce "schiaccia" l'auto, più puoi curvare forte.
$$Grip_{max} = \mu \cdot ( (Massa \cdot g) + F_{downforce} )$$

### 3.2 Velocità Limite in Curva ($v_{limit}$)
In una curva con raggio $R$ (preso dal tuo JSON HD):
$$v_{limit} = \sqrt{\frac{Grip_{max} \cdot R}{Massa}}$$
* **Se l'ala è a 30°:** $F_{downforce}$ è alto $\to v_{limit}$ è altissima.
* **Se l'ala è a 4°:** $F_{downforce}$ è basso $\to v_{limit}$ è bassa (l'auto scivola).



---

## 4. Bilanciamento e Sospensioni (Handling)

Per simulare **Sottosterzo** e **Sovrasterzo**, dividiamo il carico aerodinamico tra asse anteriore e posteriore.

### 4.1 Centro di Pressione (CoP)
L'utente definisce l'inclinazione dell'ala anteriore ($W_{front}$) e posteriore ($W_{rear}$).
* **Balance %:** $\frac{F_{down\_front}}{F_{down\_total}}$
* **Sovrasterzo:** Se $Balance > 45\%$, il posteriore è leggero. In uscita curva, il simulatore deve limitare la $a_x$ (trazione) perché le ruote dietro pattinano.
* **Sottosterzo:** Se $Balance < 38\%$, l'anteriore non ha carico. In ingresso curva, il raggio $R$ effettivo aumenta (l'auto "allarga").

---

## 5. Struttura del Codice (Consigli)

Ti consiglio di strutturare il nuovo motore in moduli Python separati per facilitare il debug:

1.  **`aero_model.py`**: Converte i gradi ala in $C_l$ e $C_d$ usando una tabella di lookup o una funzione quadratica.
2.  **`engine_model.py`**: Gestisce la curva di coppia dell'ICE + l'apporto ERS (con il clipping termico che abbiamo definito).
3.  **`tyre_model.py`**: Calcola il $\mu$ (coefficiente di attrito) in base alla mescola (C1-C5) e alla temperatura.
4.  **`integrator.py`**: Il cuore del V3. Scorre i waypoint e calcola il tempo per percorrere i 5 metri tra uno e l'altro risolvendo l'equazione del moto.

### Esempio di Loop Logico nel V3:
```python
for wp in waypoints:
    # 1. Carico verticale attuale
    f_down = aero.calc_downforce(state.v, setup.wings)
    f_load_total = (car.mass + fuel.mass) * 9.81 + f_down
    
    # 2. Resistenza aria vs Spinta motore
    f_drag = aero.calc_drag(state.v, setup.wings)
    f_engine = engine.get_force(state.v, state.ers_boost)
    state.a_long = (f_engine - f_drag) / total_mass
    
    # 3. Controllo limite curva
    v_max_wp = math.sqrt((f_load_total * tyre.mu * wp.radius) / total_mass)
    
    # 4. Scelta velocità
    state.v = min(state.v + state.a_long * dt, v_max_wp)
    
    # 5. Calcolo tempo sezione
    dt_step = distance_step / state.v
```

---

## 6. Range e Valori di Riferimento 2025

| Componente | Range / Valore | Effetto nel V3 |
| :--- | :--- | :--- |
| **Inclinazione Ali** | 4° - 35° | Determina il rapporto $C_l / C_d$ |
| **Efficienza Aero** | 3.5 - 4.2 | $C_l$ diviso $C_d$ (più è alto, più l'auto è efficiente) |
| **Massa Carburante** | 5kg - 110kg | Aumenta l'inerzia in frenata e riduce l'accelerazione |
| **Apertura Radiatori** | 1 - 10 | Aumenta il raffreddamento (meno clipping) ma aumenta il $C_d$ |

### Consigli per il Testing:
* **Test 1 (Monza):** Ali a 4°. L'auto deve toccare i 350 km/h ma fare la *Parabolica* con una $v_{min}$ bassa.
* **Test 2 (Monaco):** Ali a 30°. L'auto non deve superare i 290 km/h ma deve "volare" nel *Tabac*.
* **Confronto V1 vs V3:** Se il V3 produce tempi entro il 2% della telemetria reale (`it-1922_monza_Telemetry.json`), il modello fisico è validato.

**Vuoi che prepari il file JSON di configurazione "Base Physics" con i coefficienti $C_l$ e $C_d$ pre-calcolati per le auto 2025?**