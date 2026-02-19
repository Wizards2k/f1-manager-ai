--

# 🏎️ Analisi Funzionale: Sistema di Simulazione F1 R&D e Power Unit

## 1. Architettura della Power Unit (PU)

Il sistema deve simulare l'interazione tra il motore termico (ICE) e il sistema di recupero energia (ERS).

### 1.1 Specifiche Tecniche

* **ICE:** V6 Turbo 1.6L, ~850 CV. Limite flusso carburante: 100 kg/h.
* **MGU-K:** 120 kW (161 CV). Max 4 MJ/giro di scarica dalla batteria, Max 2 MJ/giro di recupero.
* **MGU-H:** Potenza illimitata. Gestisce il turbo-lag e alimenta il **Direct Drive**.
* **Direct Drive (Bypass):** L'energia fluisce da MGU-H a MGU-K senza passare per la batteria, superando il limite dei 4 MJ/giro.

### 1.2 Logica di Gestione Batteria (Energy Store)

* **Capacità Nominale:** ~5.5 MJ (superiore ai 4 MJ utilizzabili per garantire stabilità di voltaggio e gestione termica).
* **Voltage Sag:** Se il SOC (Stato di Carica) scende sotto il 15%, la potenza erogata diminuisce.

---

## 2. Ciclo di Sviluppo Componenti (R&D Cycle)

Ogni evoluzione tecnica di un pezzo (Ala, Fondo, PU) segue un processo a tre stadi per gestire l'incertezza e la correlazione dati.

### Fase 1: CFD (Il Desiderata)

* **Input:** L'utente manovra degli slider parametrici.
* **Output:** Risultato teorico ottimistico (Performance target).
* **Costo:** Ore di calcolo digitale (Teraflops).

### Fase 2: Galleria del Vento (Il Reale)

* **Input:** Allocazione delle ore di test (ATR Limits).
* **Output:** Risultato validato fisicamente. Riduce il margine di errore del CFD.
* **Rischio:** Possibile scoperta di instabilità aerodinamiche (stallo) non rilevate dal software.

### Fase 3: La Pista (Il Verdetto)

* **Input:** Installazione del pezzo durante le sessioni di Prove Libere (FP1/FP2).
* **Output:** Valore di performance definitivo e feedback del pilota.
* **Verifica Correlazione:** Se i dati differiscono dalla Galleria, il team soffre di "problemi di correlazione", richiedendo investimenti nelle infrastrutture della fabbrica.

---

## 3. Matrice delle Aree di Sviluppo (Slider & Trade-off)

### AREA 1: Aerodinamica Esterna

| Slider | Funzione | Vantaggio (+) | Svantaggio (-) |
| --- | --- | --- | --- |
| **Angle of Attack** | Inclinazione profili | Downforce totale | Drag (Resistenza) |
| **Outwash** | Gestione flussi laterali | Pulizia aero posteriore | Difficoltà in scia (Dirty Air) |
| **Ride Height Sens.** | Altezza da terra | Picco di carico | Instabilità sui cordoli |

### AREA 2: Power Unit & Ibrido

| Slider | Funzione | Vantaggio (+) | Svantaggio (-) |
| --- | --- | --- | --- |
| **Intake Velocity** | Velocità aspirazione | Incremento CV Termici | Rischio Affidabilità (ICE) |
| **Turbo Backpressure** | Contropressione scarico | Max recupero MGU-H | Aumento Turbo-lag |
| **Exhaust Scavenging** | Lavaggio cilindri | Efficienza combustione | Surriscaldamento interno |

### AREA 3: Thermal Management (Packaging)

| Slider | Funzione | Vantaggio (+) | Svantaggio (-) |
| --- | --- | --- | --- |
| **Inlet Size** | Dimensione bocche pance | Raffreddamento sicuro | Enorme perdita Aerodinamica |
| **Core Density** | Massa radiatori | Scambio termico rapido | Peso e ingombro interno |
| **Brake Duct Flow** | Flusso condotti freni | Frenata costante | Turbolenza ruote anteriori |

---

## 4. Dinamica Avanzata di Frenata

### 4.1 Finestra Termica

* **Ottimale:** 500°C - 950°C.
* **Overheating:** > 1100°C (Ossidazione del carbonio, perdita di potenza).

### 4.2 Brake Migration (BMIG)

Variazione dinamica del bilanciamento frenante (BBAL) basata sulla pressione del pedale:

* **Alta Pressione:** Spostamento Bias all'Anteriore (Stabilità).
* **Bassa Pressione (Trail Braking):** Spostamento Bias al Posteriore (Rotazione in curva).

---

## 5. Dataset di Esempio (JSON per il Motore Fisico)

```json
{
  "project_id": "RW26_SPOON_EVO",
  "area": "Aerodynamics",
  "validation_status": "Wind_Tunnel_Confirmed",
  "physics_modifiers": {
    "cl_gain": 0.045,
    "cd_penalty": 0.012,
    "cooling_efficiency_impact": -0.05
  },
  "correlation_data": {
    "cfd_prediction": 1.0,
    "tunnel_result": 0.94,
    "track_actual": 0.92
  }
}

```

---

Certamente. Per rendere l’analisi funzionale completa, dobbiamo mappare con precisione quali **oggetti fisici** della vettura vengono modificati quando l'utente agisce sugli slider di ogni area. Questo permette di gestire anche i costi di produzione e i tempi di assemblaggio nel tuo simulatore.

Ecco l'integrazione specifica delle componenti per ogni area.

---

# 🛠️ Appendice Componenti per Area R&D

## 1. AREA: Aerodinamica Esterna (Performance)

In quest'area, lo sviluppo agisce sulle superfici "bagnate" dall'aria. Ogni modifica richiede la produzione di nuovi stampi in carbonio.

* **Ala Anteriore (Front Wing):** Composta da *Mainplane* e *Flaps* regolabili. Influenza l'intero flusso che investe l'auto.
* **Ala Posteriore (Rear Wing):** Include il *Mainplane*, il *Top Flap* (mobile per il DRS) e le paratie laterali (*Endplates*).
* **Fondo Piatto (Underfloor):** La componente più critica. Include i *Canali Venturi* (sotto l'auto) e i *Bordi del Fondo* (Floor Edges).
* **Diffusore:** La sezione di uscita del fondo posteriore che "estrae" l'aria da sotto la vettura.
* **Pance (Sidepods):** La carrozzeria laterale che modella il flusso verso il retrotreno.
* **Beam Wing:** La piccola ala situata sopra il diffusore e sotto l'ala posteriore.

---

## 2. AREA: Power Unit & Ibrido (Efficienza)

Qui lo sviluppo è meccanico e fluidodinamico interno. Le modifiche coinvolgono leghe metalliche e componenti elettroniche.

* **Collettori di Aspirazione (Intake Manifold):** Regolano la velocità dell'aria in ingresso nei cilindri.
* **Turbocompressore (Turbocharger):** La chiocciola che comprime l'aria. Lo sviluppo agisce sulle palette della turbina.
* **MGU-H:** Il motore elettrico collegato all'albero del turbo. Lo sviluppo ne migliora la capacità di recupero termico.
* **Camera di Combustione (ICE):** Geometria del cielo del pistone e posizionamento degli iniettori.
* **MGU-K:** Il motore elettrico sull'albero motore. Lo sviluppo ne migliora l'efficienza di scarica e le dimensioni.
* **Scarichi (Exhaust System):** La geometria dei tubi di scarto che alimentano la turbina.

---

## 3. AREA: Thermal Management (Packaging)

In quest'area lo sviluppo riguarda gli scambiatori di calore e la canalizzazione interna dell'aria.

* **Radiatori (Cooling Cores):** Pacchi radianti per acqua e olio, solitamente alloggiati nelle pance.
* **Intercooler:** Lo scambiatore di calore che raffredda l'aria compressa dal turbo prima che entri nel motore.
* **Prese d'aria (Air Intakes):** Le "bocche" delle pance e l'Airbox sopra la testa del pilota.
* **Condotti Freni (Brake Ducts):** Strutture in carbonio che pescano aria dai cerchioni per raffreddare dischi e pinze.
* **Involucro Batteria (ES Casing):** Il contenitore del pacco batterie, progettato con canali di raffreddamento integrati.
* **Sfiati Posteriori (Coke Bottle Exit):** La zona posteriore della carrozzeria dove l'aria calda viene espulsa.

---

## 4. Matrice di Interdipendenza (Esempio Funzionale)

Per il tuo codice di gioco, ecco come un componente può essere influenzato da più aree:

| Componente | Area Primaria | Area Secondaria | Effetto Incrociato |
| --- | --- | --- | --- |
| **Sidepods** | Aerodinamica | Thermal | Se le stringi (Aero), riduci lo spazio per i radiatori (Thermal). |
| **Brake Ducts** | Thermal | Aerodinamica | Se li ingrandisci per i freni, sporchi il flusso verso il diffusore. |
| **Turbo** | Power Unit | Thermal | Un turbo più efficiente genera più calore da smaltire nel cofano. |

---

### Prossimo Step suggerito:

Siamo arrivati alla definizione completa. Vuoi che prepari una **"Scheda Tecnica di Progetto"** (un template MD) che l'utente compila prima di lanciare il CFD, dove sceglie appunto quali di questi componenti coinvolgere nel nuovo step evolutivo?