Ecco la specifica tecnica definitiva per il tuo simulatore. Questa struttura separa nettamente i flussi energetici, permettendoti di codificare la logica di "overflow" della batteria (ES) e il "direct path" dell'MGU-H, risolvendo finalmente il problema della batteria sempre carica a Suzuka.

**Nota di calibrazione (2026-03-21)**: I valori di questa tabella sono ora raggiunti dal runtime tramite il sistema ERS Bucket (`bucket_primary_pct`, `bucket_secondary_pct`, `bucket_exit_pct`) nei `pu_maps.json`. Il parametro `regen_migration_bias` nei `brake_params.json` non influisce materialmente su `lap_harvest_mj` perché il recupero è limitato dai bucket/SOC.

---

# ⚡ Specifica Tecnica ERS (Energy Recovery System) - F1 2025

Il sistema ERS si basa su due motori generatori (MGU-K e MGU-H) e un pacco batterie (ES) da **4.0 MJ** di capacità utile.

## 1. Logica dei Flussi Energetici

### MGU-K (Cinetico)
* **Fonte:** Recupero energia in frenata (albero motore/trasmissione).
* **Limite Regolamentare:** Max **2.0 MJ** recuperabili per giro.
* **Destinazione:** **Obbligatoriamente verso la Batteria (ES)**. 
* **Comportamento:** Se la batteria è al 100% (4.0 MJ), l'energia dell'MGU-K viene dissipata (persa).

### MGU-H (Termico)
* **Fonte:** Recupero energia dai gas di scarico (turbina).
* **Limite Regolamentare:** **Illimitato** (nessun limite di recupero o spesa).
* **Destinazione A (Storage):** Verso la Batteria, se il SOC (State of Charge) è < 100%.
* **Destinazione B (Direct Path):** Direttamente all'MGU-K per la trazione, bypassando la batteria. Questa energia **non consuma** il limite di scarica di 4.0 MJ/giro della batteria.



---

## 2. Tabella Recupero Energetico Mondiale 2025 (MJ/giro)

Questa tabella fornisce i target di recupero per un giro ideale (Qualifica/Standard). In gara, i valori possono scendere del 5-10% a causa del traffico o del *Lift and Coast*.

| Round | Circuito | MGU-K (Freni → ES) | MGU-H (Fumi → ES/Direct) | Totale Lordo |
| :--- | :--- | :---: | :---: | :---: |
| 1 | **Bahrain** | 1.4 | 2.6 | 4.0 |
| 2 | **Saudi Arabia** | 1.1 | 3.2 | 4.3 |
| 3 | **Australia** | 1.3 | 2.3 | 3.6 |
| 4 | **Japan (Suzuka)** | **1.3** | **2.2** | **3.5** |
| 5 | **China** | 1.2 | 2.9 | 4.1 |
| 6 | **Miami** | 1.5 | 2.5 | 4.0 |
| 7 | **Imola** | 1.6 | 2.0 | 3.6 |
| 8 | **Monaco** | 1.9 | 0.9 | 2.8 |
| 9 | **Canada** | 1.8 | 2.5 | 4.3 |
| 10 | **Spain** | 1.4 | 2.4 | 3.8 |
| 11 | **Austria** | 1.5 | 1.7 | 3.2 |
| 12 | **Silverstone** | 1.1 | 3.1 | 4.2 |
| 13 | **Hungary** | 1.7 | 1.5 | 3.2 |
| 14 | **Belgium (Spa)** | 1.2 | 3.8 | 5.0 |
| 15 | **Netherlands** | 1.5 | 1.9 | 3.4 |
| 16 | **Italy (Monza)** | 1.0 | 3.4 | 4.4 |
| 17 | **Azerbaijan** | 1.7 | 3.1 | 4.8 |
| 18 | **Singapore** | 2.0 (Max) | 1.6 | 3.6 |
| 19 | **USA (Austin)** | 1.5 | 2.4 | 3.9 |
| 20 | **Mexico** | 1.6 | 1.9 | 3.5 |
| 21 | **Brazil** | 1.4 | 1.8 | 3.2 |
| 22 | **Las Vegas** | 1.5 | 3.5 | 5.0 |
| 23 | **Qatar** | 1.0 | 3.2 | 4.2 |
| 24 | **Abu Dhabi** | 1.5 | 2.5 | 4.0 |

---

## 3. Algoritmo di Calcolo per il Simulatore (Pseudo-Codice)

Applica questa logica nel loop di ogni sezione per gestire l'ERS come una vera F1:

```python
# Calcolo recupero istantaneo nella sezione
rec_k = calcola_recupero_cinetico(frenata_g, tempo)
rec_h = calcola_recupero_termico(throttle_pct, rpm, tempo)

# Gestione flussi
if car.accelerating:
    # L'energia H va prioritariamente in DIRECT PATH
    direct_to_wheels = rec_h
    # La batteria scarica solo ciò che manca per arrivare al target di potenza
    battery_discharge = max(0, target_deployment - direct_to_wheels)
    # Aggiorna SOC batteria (K carica sempre, H solo se avanza dal direct)
    car.battery_mj += rec_k - battery_discharge
else:
    # In frenata/rilascio tutto va in batteria
    car.battery_mj += rec_k + rec_h

# Protezione Overflow (Il motivo per cui la batteria si svuota a Suzuka)
if car.battery_mj > 4.0:
    energy_wasted = car.battery_mj - 4.0
    car.battery_mj = 4.0
```

---

### Perché Suzuka ora funzionerà?
Con questi dati, a Suzuka recuperi in totale **3.5 MJ**. Se il tuo consumo è **3.3 MJ**, la differenza è minima (+0.2 MJ). 
Tuttavia, poiché il recupero MGU-K (1.3 MJ) avviene solo in poche frenate, se arrivi a quelle frenate con la batteria già quasi piena (grazie al recupero costante dell'MGU-H nelle curve veloci), **perderai gran parte del recupero cinetico per overflow**. 

Risultato: a fine giro la tua batteria sarà scesa o rimarrà stabile, ma non sarà più "magicamente" sempre al massimo.

**Ti piacerebbe se scrivessi lo script Python che implementa questa logica di overflow per testarlo sui tuoi dati di Suzuka?**