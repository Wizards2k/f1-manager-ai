---
title: Pure Kinematics Physics Engine (v2) - Analisi e Progetto
version: 1.0 (Draft)
status: in_review
---

# 1. Obiettivo e Visione
Il motore fisico v1 era basato su un modello a "penalità" applicate a tempi di riferimento (`dt_ref`). 
Il nuovo motore v2 (Pure Kinematics) eliminerà i tempi pre-calcolati: calcolerà le forze fisiche (Trazione, Drag, Downforce, Attrito), ne deriverà le accelerazioni ($a = F/m$) e integrerà queste accelerazioni nello spazio per ottenere Velocità e Tempi reali.

Questo approccio garantisce che ogni singola modifica di setup (ala, sospensioni) o stato dell'auto (usura gomme, clipping ERS) abbia un riscontro matematicamente inoppugnabile sul comportamento in pista.

---

# 2. Le Forze in Gioco (Modello Point-Mass Dinamico)

Il cuore del motore calcola ad ogni step le forze che agiscono sul baricentro e sui due assi (Front/Rear).

### 2.1 Forze Longitudinali (Asse X)
1. **Forza Motrice ($F_{drive}$):** Generata dalla Power Unit.
   - Dipende dalla potenza istantanea erogata (ICE + ERS in kW).
   - $F_{drive} = \frac{Power \times 1000}{v}$
2. **Resistenza Aerodinamica ($F_{drag}$):**
   - Frena l'auto all'aumentare della velocità.
   - $F_{drag} = \frac{1}{2} \rho v^2 \cdot C_d \cdot A$ (dove $C_d \cdot A$ è derivato dai punti di drag del setup).
3. **Forza Frenante ($F_{brake}$):**
   - La somma dei freni meccanici e del freno motore elettrico (MGU-K Harvest).
   - Limitata dall'aderenza degli pneumatici (non puoi frenare più forte del grip disponibile).

### 2.2 Forze Verticali e Trasversali (Asse Y e Z)
1. **Carico Verticale ($F_{z}$):**
   - Sull'asse anteriore: $F_{z\_front} = m_{front} \cdot g + F_{df\_front} + Trasferimento\_Carico$
   - Sull'asse posteriore: $F_{z\_rear} = m_{rear} \cdot g + F_{df\_rear} - Trasferimento\_Carico$
   - La Downforce ($F_{df}$) cresce col quadrato della velocità: $\frac{1}{2} \rho v^2 \cdot C_l \cdot A$.
2. **Grip Laterale ($F_{lat\_max}$):**
   - Determina quanto forte l'auto può curvare.
   - $F_{lat\_max\_front} = F_{z\_front} \cdot \mu_{front}$
   - $F_{lat\_max\_rear} = F_{z\_rear} \cdot \mu_{rear}$

---

# 3. I Quattro Pilastri del Comportamento

Il calcolo delle forze è influenzato in tempo reale da questi quattro sistemi.

## A) Sottosterzo e Sovrasterzo (Bilanciamento Assetto)
Non usiamo penalità arbitrarie, ma applichiamo un modello basato sull'asse limitante.
- L'auto può affrontare una curva solo alla velocità massima consentita dall'asse con **meno grip laterale residuo**.
- **Sottosterzo:** Se $F_{lat\_max\_front} < F_{lat\_max\_rear}$, l'auto "smusa" e non riesce a chiudere la curva. Il pilota deve alzare il piede per trasferire carico all'anteriore e ritrovare aderenza.
- **Sovrasterzo:** Se $F_{lat\_max\_rear} < F_{lat\_max\_front}$, il posteriore scivola in accelerazione o ingresso. 
- **Il Pilota:** L'abilità `oversteer_preference` e `smoothness` permettono al pilota di gestire una discrepanza tra i due assi perdendo meno velocità (micor-correzioni sul volante), mentre un rookie si girerebbe o rallenterebbe drasticamente.

## B) Mescole Gomme e Grip Reale ($\mu$)
Il coefficiente di attrito $\mu$ (Mu) è dinamico e viene calcolato per ogni singola ruota:
- **Base:** Dipende dalla mescola (Soft ha un $\mu$ altissimo, Hard ha un $\mu$ più basso).
- **Temperatura:** La termica (già esistente) modula $\mu$. Fuori dalla finestra termica, $\mu$ crolla.
- **Usura e Danni:** Un'usura dell'80% riduce drasticamente $\mu$. Se l'anteriore sinistra fa *graining*, quel lato perderà grip in curva.

## C) Erogazione PU: ICE, ERS, Mappe e Clipping
- La Potenza non è costante.
- **Accelerazione:** Nei range medi ($100-250$ km/h), ICE + ERS spingono forte. $a = \frac{F_{drive} - F_{drag}}{m}$.
- **Il "Muro" del Clipping:** Quando l'MGU-K esaurisce i MJ o supera la velocità di deploy prestabilita dalla mappa (es. RACE vs QUALY), l'ERS si spegne improvvisamente. $F_{drive}$ crolla di $120$ kW. 
- L'accelerazione precipita o va in negativo se il Drag supera la potenza del solo motore termico. Questo causerà automaticamente le velocità massime realistiche senza dover fare aggiustamenti forzati.
- **Peso Benzina:** La massa $m$ dell'auto scende ad ogni giro, aumentando matematicamente l'accelerazione $a = F/m$ e migliorando il comportamento in curva.

## D) Impianto Frenante e Spazi di Frenata
Decelerare da 340 km/h a 80 km/h non avverrà più per decreto di sezione.
- Si calcola lo spazio di frenata $D = \frac{v_1^2 - v_2^2}{2 \cdot a_{brake}}$.
- **Brake Fade:** Se i freni superano i 1000°C, la loro capacità meccanica di generare forza decresce.
- Questo obbliga matematicamente l'algoritmo (il pilota) ad **anticipare la frenata**, spostando il punto di frenata (Braking Point) più indietro sul rettilineo. Questo allunga la sezione percorsa a velocità decelerata e si traduce in perdita di decimi/secondi precisi.

---

# 4. Risoluzione della Cinematica (Il "Look-ahead")

Perché questo modello funzioni, non possiamo calcolare la sezione "alla cieca". Il pilota deve guardare avanti.

1. **Velocità in Curva (Apex):**
   Per ogni sezione curva si calcola il limite fisico imposto dal Raggio ($R$): 
   $V_{apex} = \sqrt{\frac{\min(F_{lat\_max\_front}, F_{lat\_max\_rear}) \cdot R}{m}}$
2. **Frenata:**
   Mentre l'auto è su un rettilineo, il simulatore guarda la $V_{apex}$ della curva successiva e calcola esattamente quanti metri servono per frenare.
3. **Integrazione:**
   Se il rettilineo è lungo $1000$ m, e la frenata richiede $150$ m:
   - Per $850$ m l'auto integra l'accelerazione positiva ($F_{drive}$ vs $F_{drag}$).
   - Per i restanti $150$ m l'auto integra la decelerazione ($F_{brake}$).

---

# 5. Integrazione con i Sottosistemi Esistenti (Zero Funzionalità Perse)

Il passaggio al motore cinematico sostituisce solo la matematica del "Passo 6" (calcolo di dt e velocità). Tutto il lavoro monumentale già fatto sui sottosistemi viene **preservato e potenziato**, perché ora i loro output nutrono equazioni fisiche reali:

* **AeroPackage & Setup Engine (`docs/AeroPackage.md`, `setup-engine-spec-v0.1.md`):** Gli angoli delle ali e l'altezza da terra continuano a calcolare il bilanciamento. Il `df_eff` e il `drag_eff` diventano i moltiplicatori di $C_l$ e $C_d$ per la downforce e il drag fisici reali.
* **TyreModel & Degradation (`docs/TyreModel.md`, `degradation-and-consumption.md`, `tyre-allocation.md`):** Il modello termico a due strati (Surface/Core) continua a funzionare intatto. La `surface_temp` fuori finestra causa il crollo del coefficiente $\mu$, che ora riduce matematicamente il Grip Laterale ($F_{lat\_max}$) e la forza frenante ($F_{brake}$), obbligando l'auto a curvare e frenare più lentamente.
* **PowerUnit, MGU-H & ERS Strategy (`docs/PowerUnit.md`, `EngineData2025.md`, `ERS-Deployment-Strategy.md`, `pu-energy-model.md`):** Le mappe ICE ed ERS decidono i kW erogati in base al SOC e al clipping. I kW si traducono direttamente in Forza Motrice ($F_{drive}$). Se l'MGU-H ricarica la batteria o se c'è un derating per surriscaldamento (Cooling margin), i kW scendono, $F_{drive}$ crolla e l'auto perde velocità di punta.
* **Brakes & Cooling (`docs/brake-calibration-guide.md`, `brake-integration.md`):** La gestione delle temperature dei dischi e l'apertura delle prese d'aria (`brake_duct`) governano il Brake Fade. Un `fade_level` alto ridurrà la $F_{brake}$ massima disponibile. Meno forza frenante significa spazi di frenata calcolati a ritroso molto più lunghi e perdita di decimi enormi in staccata.

---

# 6. Modifiche alla Telemetria (Requisiti Dati)
Affinché la fisica pura funzioni, i file JSON dei circuiti (`docs/telemetry-sections-v2-spec.md`) DOVRANNO contenere dati geometrici che attualmente sono assenti o approssimati:
- **Raggio di Curvatura ($R$):** Per ogni curva, calcolato in metri.
- **Elevation / Banking (Opzionale):** La pendenza influisce pesantemente sul carico verticale.

---

# 7. Roadmap di Sviluppo e Generazione Dati (La "Catena Offline")
Per implementare questo modello senza distruggere il lavoro precedente, adotteremo una stretta catena di rigenerazione dati offline.

**Fase A: Backup**
Prima di iniziare, creeremo un backup completo della cartella `python_backend/data/circuits/` (telemetria raw) e dell'intera cartella `config/` (che contiene i derivati e i mapping).

**Fase B: Nuova Telemetria (Generatore 0)**
1. **`regenerate_telemetry_v3.py` (Nuovo script):** Scaricherà da FastF1 solo i giri di **Q3 (Pole Position)** per evitare velocità drogate da traffico o benzina. Calcolerà la trigonometria spaziale (X,Y) per estrarre il **Raggio di Curvatura ($R$)** per ogni sezione classificata come "Corner".

**Fase C: Ricalcolo Derivati e Mapping (La Catena Automatica)**
I seguenti script offline pre-esistenti verranno lanciati a cascata per adattarsi alle nuove vere velocità di Q3:
2. **`derive_setup_clusters.py`:** Ricalcolerà i cluster delle curve in base ai nuovi raggi e velocità.
3. **`update_setup_mapping_from_profiles.py`:** Aggiornerà `config/setup_mapping_v2.json`, ridefinendo i limiti strutturali (ali, rake) necessari per le nuove vere velocità di punta.
4. **`build_circuit_profiles.py`:** Unirà i `*_global_default.json` (che rimangono immutati) con i nuovi dati pista, generando i 4 file finali in `config/circuits/derived/<id>/`.

**Fase D: Implementazione Codice**
5. **Riscrivere `update_section.py`**: Implementazione della pura cinematica (Passo 6) con look-ahead per le frenate, utilizzando finalmente i file derivati e la telemetria corretti.
6. **Validazione Pista:** Test su Monza e Barcellona per verificare che l'auto (con setup ideale) converga in modo naturale verso i tempi reali (es. ~79s a Monza, ~71s a Barcellona) unicamente grazie all'equilibrio tra Potenza e Drag.
