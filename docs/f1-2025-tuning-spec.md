# F1 2025 Performance Tuning – Guida Operativa Completa (Fasi 1-5)

Questo documento rappresenta la guida completa e dettagliata per calibrare le prestazioni iniziali 2025, validare i tempi simulati, definire il delta assetto/mappe motore e automatizzare il controllo qualità (QA) del motore fisico.

## Fase 1 – Raccolta Dati & Calibrazione Iniziale Team
**Obiettivo:** Impostare i parametri base (Telaio/Aero/Power Unit) dei team allineati all’inizio stagione 2025.

**Passi Operativi per la Realizzazione:**
- [x] 1. **Estrazione dati reali:** Creare uno script (`tools/fetch_fastf1_baselines.py`) che scarica da FastF1 i dati sia di Qualifica che di Gara per i circuiti target (Melbourne, Bahrain, Jeddah).
- [x] 2. **Calcolo metriche aggregate (Gap Combinato):** Calcolare per ogni team il gap percentuale. Ponderare il risultato usando un mix Qualifica/Gara (es. 40% Qualifica + 60% passo Gara, quest'ultimo calcolato sulla mediana dei giri puliti e normalizzato per il carico di carburante). Estrarre anche Vmax in trap, Vmin e consumo carburante medio.
- [x] 3. **Mappatura parametri fisici:** 
   - Suddividere i team in tier (Top, Mid, Back).
   - Assegnare `baseline_delta` (offset grip/aero) scalando i valori entro un range di tolleranza rigido (±5%).
   - Assegnare modificatori Power Unit (`k_power`, `mguh_direct_ratio`) per differenziare i motoristi.
- [x] 4. **Scrittura file configurazione:** Salvare i risultati nei file JSON dei team in `python_backend/data/teams/` assicurandosi che il LapSimulator li legga all'avvio.

## Fase 2 – Validazione Tempi Sim vs Reale
**Obiettivo:** Assicurare che i tempi simulati coincidano con la realtà (focus sui Top Team), regolando la fisica senza offset artificiali sul cronometro.

**Passi Operativi per la Realizzazione:**
1. **Setup Batch Runner:** Scrivere uno script (`tools/run_validation_batch.py`) che esegue un HOT LAP e uno stint di gara sui 4 circuiti di regressione (Barcellona, Monza, Montecarlo, Silverstone).
2. **Generazione delta:** Lo script calcolerà la differenza tra il tempo simulato e il record reale FastF1 per la corrispondente sessione.
3. **Micro-tuning iterativo (Soft Tuning):** 
   - Se il tempo è troppo lento su piste veloci (es. Monza), ridurre `k_drag` globale o aumentare `k_power` (max ±5%).
   - Se il tempo è troppo veloce nel misto (es. Barcellona S3), ritoccare il drop di aderenza in curva.
4. **Congelamento Baseline:** Raggiunto un errore target di `~0.5-1.0s`, bloccare i file globali del simulatore e considerare la baseline fisica validata.

## Fase 3 – Delta Assetto & Mappe Motore
**Obiettivo:** Garantire un impatto prestazionale tangibile (trade-off) tra scelte giuste e sbagliate del giocatore, salvaguardando il realismo fisico.

**Passi Operativi per la Realizzazione:**
1. **Definizione dello Sweep Test:** Creare uno script (`tools/run_tradeoff_sweep.py`) che simula una griglia di scenari: 
   - Ala da 0 a 100 in step di 10.
   - Mappe ERS da "Harvest" a "Overtake".
2. **Validazione Monotonicità:** Eseguire lo script e asserire matematicamente che l'aumento dell'ala riduca *sempre* la Vmax e aumenti *sempre* il grip, producendo variazioni di lap time coerenti.
3. **Tuning del Delta (Penalty):** Aggiustare i moltiplicatori di setup penalty (`handling_penalty`, `k_aero_penalty`) fino a ottenere esattamente un differenziale di `≥ 1.5s` tra un setup al 100% e uno allo 0%.
4. **Bilanciamento Energetico:** Verificare che l'uso prolungato della mappa "Overtake" porti il SOC (State of Charge) della batteria a 0 entro 1.5 giri, costringendo al recharge.

## Fase 4 – Tuning e Validazione Visiva (Dashboard Telemetria)
**Obiettivo:** Creare uno strumento visivo per sovrapporre e analizzare la telemetria del simulatore contro i dati reali (FastF1) curva per curva.

**Passi Operativi per la Realizzazione:**
1. **Sviluppo Ingestion Data:** Creare un modulo (`utils/telemetry_parser.py`) capace di allineare spazialmente (stessa distanza percorsa) i dati del `LapSimulator` e i DataFrame di FastF1.
2. **Creazione App Plotly/Dash:** Creare lo script web `tools/telemetry_dashboard.py` usando Plotly/Dash.
3. **Pannelli Grafici (Traces):** 
   - Grafico 1: Velocità (km/h) vs Distanza (m) (Simulata vs Reale).
   - Grafico 2: Input Pilota (Throttle % / Brake).
   - Grafico 3: ERS (SOC %, Deploy MJ).
4. **Workflow d'uso:** Usare questa UI ogni volta che la Fase 2 rileva un'anomalia cronometrica, per capire visivamente il problema (es. staccata anticipata o trazione debole).

## Fase 5 – Automazione, Watchdog & Continuous Integration (QA)
**Obiettivo:** "Blindare" il motore fisico in modo perpetuo. Nessun update futuro del codice deve rompere i tempi sul giro o l'equilibrio energetico.

**Passi Operativi per la Realizzazione:**
1. **Costruzione Watchdog CLI:** Implementare `tools/watchdog.py`, eseguibile da terminale, che lancia una suite di 10 giri. Fallisce con Exit Code 1 se il `lap_time` differisce di >1.0% o il consumo fuel è sballato.
2. **Setup GitHub Actions:** Creare `.github/workflows/calibration.yml` configurato per fare checkout del codice, installare Python/dependencies e avviare `tools/watchdog.py` ad ogni Push o Pull Request sul branch principale.
3. **Creazione File Manifest:** Aggiungere `config/calibration/manifest.json`. Al completamento di calibrazioni manuali su una pista, aggiornare il manifest col checksum o data di approvazione.
4. **Implementazione Checklists PR:** Creare in `.github/pull_request_template.md` una checklist obbligatoria che richiede ai developer di dichiarare l'assenza di regressioni fisiche (es. "✅ Test monotonicità aero passati").

## Processo di Validazione Finale
Nessuna release del motore di simulazione passa in `main` senza che le Fasi 4 e 5 diano semaforo verde sui 4 circuiti di regressione. Tutte le eccezioni devono essere giustificate da una Issue formale.
