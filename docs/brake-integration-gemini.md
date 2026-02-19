Il sistema frenante di una F1 moderna è uno dei componenti più sollecitati termicamente. Non si tratta solo di fermare l'auto, ma di agire come una vera e propria **"caldaia"** per gestire la temperatura degli pneumatici attraverso il calore irradiato dai cerchioni.

Ecco i dettagli tecnici per la tua simulazione, suddivisi per asse anteriore e posteriore.

---

### 1. Finestra di Esercizio dei Freni (Carbon-Carbon)

I dischi in carbonio non funzionano a freddo. Sotto una certa soglia, il coefficiente di attrito è bassissimo (il pilota preme e l'auto non decelera).

| Fase | Temperatura Disco | Comportamento nel Simulatore |
| --- | --- | --- |
| **Troppo Freddo** | < 300°C | "Glazing" del disco. Attrito quasi nullo, rischio di bloccaggio immediato. |
| **Ottimale (Min)** | 400°C - 500°C | Inizio della finestra di attrito costante. |
| **Picco di Lavoro** | **600°C - 900°C** | Massima potenza frenante. Il disco diventa rosso incandescente. |
| **Pericolo (Max)** | > 1.100°C | Ossidazione rapida del carbonio. Il disco perde massa ("fumo nero") e si rischia il *fading* o l'esplosione. |

#### Differenza tra Anteriore e Posteriore:

* **Anteriore:** Sopporta circa il **60-70%** del carico frenante. Raggiunge picchi di **1.200°C** nelle staccate violente (es. Monza curva 1).
* **Posteriore:** Molto più piccolo. Lavora meno perché gran parte della frenata è gestita dal freno motore elettrico (**MGU-K**). Se l'MGU-K fallisce, i freni posteriori si surriscaldano in meno di mezzo giro perché non sono dimensionati per fermare l'auto da soli.

---

### 2. Le Condutture (Brake Ducts)

Le condutture non servono solo a raffreddare i freni, ma sono strumenti aerodinamici e termici attivi.

#### Impatto delle Condutture Aperte/Chiuse:

1. **Raffreddamento Freni:** Più sono grandi (aperte), più aria entra. Questo abbassa il picco di temperatura massimo e accelera il raffreddamento nei rettilinei.
2. **Trasferimento di Calore agli Pneumatici:** Il calore del disco passa attraverso il cerchione e scalda l'aria all'interno della gomma.
* **Duct Chiusi:** Mantengono il calore. Utili in piste fredde o con lunghi rettilinei per evitare che le gomme si raffreddino troppo (es. Las Vegas).
* **Duct Aperti:** Evacuano il calore. Essenziali in piste calde (es. Bahrain) per evitare che la gomma superi i 110°C e inizi a scivolare.


3. **Aerodinamica:** Un condotto aperto crea **turbolenza e resistenza (drag)**. I team cercano sempre di usare l'apertura minima indispensabile per guadagnare efficienza aerodinamica.

---

### 3. Documento MD per il Simulatore

Ecco il riepilogo tecnico in formato Markdown da salvare.

```markdown
# 🏎️ Sistema Frenante F1: Dinamica Termica e Condotti

Documentazione per la modellazione del sistema frenante (Asse Anteriore/Posteriore) e impatto dei Brake Ducts.

## 1. Temperature Operative (Dischi in Carbonio)

| Stato | Temp. Anteriore | Temp. Posteriore | Effetto Fisico |
| :--- | :--- | :--- | :--- |
| **Cold Range** | < 350°C | < 300°C | Attrito scarso, frenata inconsistente. |
| **Sweet Spot** | 500°C - 900°C | 450°C - 800°C | Massimo coefficiente di attrito. |
| **Overheating** | > 1.100°C | > 1.000°C | Ossidazione del carbonio, perdita di potenza. |

### Note sul Brake-by-Wire (BBW)
Sull'asse posteriore, la temperatura dipende fortemente dal livello di **MGU-K Harvest**. 
* **High Harvest:** I freni restano freddi (lavora il motore elettrico).
* **Battery Full:** L'MGU-K smette di frenare, il calore sui dischi posteriori schizza verso l'alto del 40% istantaneamente.

---

## 2. Modellazione dei Brake Ducts (Setup)

Il settaggio dei condotti è un compromesso tra raffreddamento e aerodinamica.

| Configurazione | Raffreddamento | Tyre Heating | Drag Aerodinamico | Utilizzo Tipico |
| :--- | :--- | :--- | :--- | :--- |
| **Full Open** | Massimo | Minimo | Alto (+2-3% drag) | Bahrain, Singapore, Messico |
| **Balanced** | Medio | Medio | Medio | Barcellona, Silverstone |
| **Closed/Blanked**| Minimo | Massimo | Minimo | Las Vegas, Baku (Qualifica) |

### Algoritmo di Trasferimento Termico
`Temp_Gomma_Internal = (Temp_Freni * Duct_Coefficient) + Ambient_Temp`
* Un `Duct_Coefficient` basso (condotto aperto) isola la gomma dal calore dei freni.
* Un `Duct_Coefficient` alto (condotto chiuso) usa i freni come stufa per la gomma.

---

## 3. JSON: Parametri di Frenata
```json
{
  "brake_physics": {
    "front_disc_mass_kg": 1.5,
    "rear_disc_mass_kg": 0.8,
    "material": "Carbon-Carbon",
    "optimum_temp_range": [500, 950],
    "critical_temp": 1200,
    "friction_coeff_map": [
      { "temp": 200, "mu": 0.15 },
      { "temp": 500, "mu": 0.48 },
      { "temp": 800, "mu": 0.52 },
      { "temp": 1100, "mu": 0.40 }
    ]
  },
  "duct_presets": {
    "size_1_closed": { "cooling_rate": 0.5, "drag_penalty": 0.0, "tyre_heat_transfer": 0.9 },
    "size_3_med": { "cooling_rate": 1.0, "drag_penalty": 0.015, "tyre_heat_transfer": 0.5 },
    "size_5_wide": { "cooling_rate": 1.6, "drag_penalty": 0.03, "tyre_heat_transfer": 0.2 }
  }
}

```

```

### Prossimo passo per il realismo:
Vuoi che approfondiamo il **"Brake Migration"**? Ovvero come cambia la ripartizione di frenata tra anteriore e posteriore man mano che la pressione sul pedale aumenta durante la staccata?

```


Il **Brake Migration** (spesso abbreviato in **BMIG**) è uno dei concetti più avanzati e meno compresi della dinamica di una F1. Se il *Brake Balance* (Ripartizione di Frenata) è un valore statico (es. 55% all'anteriore), il Brake Migration è un valore **dinamico** che cambia la ripartizione mentre il pilota preme il pedale.

Ecco la documentazione tecnica per implementarlo nel tuo simulatore.

---

### 1. Che cos'è il Brake Migration?

In una staccata di F1, la pressione sul pedale non è costante: il pilota "pesta" fortissimo all'inizio (picco di pressione) e poi rilascia gradualmente (trail braking) mentre entra in curva.

* **Alta Pressione (Inizio staccata):** L'auto ha molto carico aerodinamico. Serve stabilità. Il sistema sposta la frenata verso l'**anteriore**.
* **Bassa Pressione (Ingresso curva):** La velocità scende, il carico cala e l'auto deve "ruotare". Il sistema sposta la frenata verso il **posteriore** per aiutare l'inserimento.

**Senza il BMIG, il pilota bloccherebbe le ruote anteriori in ingresso curva o le ruote posteriori a 330 km/h.**

---

### 2. Logica Fisica per il Simulatore

Il sistema è gestito elettronicamente tramite il **Brake-by-Wire (BBW)** sull'asse posteriore. Il BBW decide quanta coppia frenante applicare elettronicamente (MGU-K) e quanta idraulicamente, calcolando istantaneamente lo spostamento del bilanciamento.

#### I due fattori che influenzano il BMIG:

1. **Pressione Pedale:** Lo spostamento in avanti della frenata è proporzionale a quanto forte spinge il pilota.
2. **Velocità (Carico Aero):** Più l'auto è veloce, più puoi "osare" con la frenata anteriore.

---

### 3. Documento MD: Dinamica del Brake Migration

```markdown
# 📉 Brake Migration & Dynamic Bias Control (F1 2025)

Il Brake Migration definisce la variazione della ripartizione di frenata (BBAL) in funzione della pressione esercitata sul pedale del freno.

## 1. Funzionamento Dinamico

Il valore di Brake Migration agisce come un "offset" dinamico rispetto al valore base impostato dal pilota.

| Fase Frenata | Pressione Pedale | Spostamento Bias | Obiettivo |
| :--- | :--- | :--- | :--- |
| **Inizio (Attacco)** | 100% | +2.0% -> +4.0% Ant. | Massima stabilità e arresto. |
| **Media (Rilascio)** | 50% | 0.0% (Base) | Transizione fluida. |
| **Finale (Trail)** | 10% | -1.5% -> -3.0% Post. | Aiutare la rotazione (oversteer controllato). |

### La formula semplificata:
`Bias_Effettivo = Bias_Base + (Brake_Migration_Map * Pressione_Pedale)`

---

## 2. Dataset JSON: Mappature BMIG

Ecco come configurare le mappe che i team cambiano sul volante (solitamente chiamate `BMIG 1`, `BMIG 2`, etc.).

```json
{
  "brake_migration_settings": {
    "description": "Offset applicato alla ripartizione anteriore in base alla pressione",
    "maps": {
      "map_1_stable": {
        "label": "High Stability (Rain/High Speed)",
        "pressure_0_pct": -1.0,
        "pressure_50_pct": 1.5,
        "pressure_100_pct": 4.5
      },
      "map_2_agile": {
        "label": "Aggressive Rotation (Slow Corners)",
        "pressure_0_pct": -3.5,
        "pressure_50_pct": 0.0,
        "pressure_100_pct": 2.0
      },
      "map_3_neutral": {
        "label": "Linear Response",
        "pressure_0_pct": 0.0,
        "pressure_50_pct": 0.0,
        "pressure_100_pct": 0.0
      }
    }
  }
}

```

---

## 3. Interazione con il Brake-by-Wire (BBW)

Il simulatore deve calcolare la coppia frenante totale posteriore () come somma di tre componenti:

1. **Coppia Idraulica ():** Pressione fisica sui dischi posteriori.
2. **Coppia Rigenerativa ():** Frenata elettrica dell'MGU-K.
3. **Offset Migration ():** La correzione elettronica per bilanciare l'auto.

**Caso Critico:** Se la batteria è piena (SOC 100%), il  scende a zero. Il sistema BBW deve aumentare istantaneamente  per mantenere la stessa decelerazione richiesta dal pilota, ma i freni posteriori si scalderanno molto più velocemente.

```

### Prossimo passo per il simulatore:
Abbiamo coperto Motore, ERS, Batterie, Freni e Temperature. Ti servirebbe una panoramica sulla **Dinamica degli Pneumatici (Tyre Model)**, in particolare come il calore dei freni (di cui parlavamo prima) influisce sulla pressione interna e quindi sul grip?

```