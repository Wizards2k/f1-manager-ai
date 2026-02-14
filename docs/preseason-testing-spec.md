# Specifica Fase Prestagionale & Scoperta Nuova Vettura (WIP)
Questa bozza descrive il flusso completo che collega gli ultimi sviluppi della stagione corrente alla generazione dei valori iniziali con cui parte la simulazione della stagione successiva, includendo focus dedicati su R&D e feedback ingegneri/piloti.

## 1. Executive Summary & Obiettivi
- **Problema**: oggi il salto tra stagione N e stagione N+1 avviene senza simulare la scoperta della nuova vettura; manca una fase che trasformi i dati teorici in prestazioni reali.
- **Obiettivo**: introdurre una sequenza di attività (progettazione, validazione virtuale, test in pista) che produca metriche iniziali coerenti (performance, affidabilità, confidenza setup, mappature PU) per l'avvio del campionato.
- **Vincoli**: durata limitata (3 sessioni ufficiali), risorse R&D finite, calendario logistico serrato, necessità di mantenere segretezza/sandbagging.
- **Output**: valori iniziali stagionali + narrativa che evidenzi rischi residui, apprendimenti e decisioni strategiche (es. quanto abbiamo nascosto il potenziale reale).

## 2. Contesto e Input di Sistema
- **Dipendenze**: LapSimulator runtime (per loop di pista), setup engine (per range iniziali), power-unit model, telemetria circuiti di Barcellona/Bahrain.
- **Riferimenti**: `global-roadmap.md`, `lap-physics-spec-v0.5.md`, `setup-engine-spec-v0.1.md`, `practice-session-orchestrator.md`.
- **Dati richiesti**:
  - Config test-specifiche (meteo medio, evoluzione grip, limitazioni regolamentari su gomme e fuel load).
  - Stato R&D finale stagione N (progetti completati, rischi aperti, budget residuo).
  - Allocazione personale (aerodinamica, PU, meccanica, operations) e loro efficienza.
- **Assunzioni**: tutti i componenti principali dell'auto nuova sono stati progettati ma non ancora validati su pista; alcune parti possono arrivare con ritardo (es. upgrade Bahrain).

## 3. Ciclo Progettuale Stagione N → N+1
- **Doppio board**: mantenere upgrade in-season mentre si costruisce la concept car N+1; il gioco deve obbligare a bilanciare budget e tempo.
- **Output teorici**: coefficienti di carico/drag, finestre di raffreddamento, efficienza ERS, mappe ICE, sensibilità setup (KPI con intervallo di confidenza).
- **Rischi**: mismatch aerodinamico, problemi di affidabilità PU, peso oltre limiti, supply chain.
- **Decisioni giocatore**: quanto investire in validazioni virtuali vs costruzione pezzi, scegliere trade-off tra performance e certezza dei dati.

## 4. Freeze e Validazione Virtuale
- **Freeze**: data limite entro cui i sottosistemi vengono "congelati" per produrre i target utilizzati nei test.
- **Validazione virtuale**:
  - Aggregazione dei contributi (ala, fondo, cofano, raffreddamento, PU) in un set di target metrici con confidenza %.
  - Calcolo di coefficienti di mismatch (es. ±X% carico, ±Y°C temperature freni) che rappresentano l'incertezza da verificare in pista.
- **Strumenti**: CFD/galleria, test dinamometro PU, banco sospensioni, simulatori piloti.
- **Deliverable**: schede digital twin per ogni sottosistema, usate come baseline durante i test.

## 5. Calendario Test Prestagionali
1. **Barcellona – Shake-down & Correlazione**
   - Obiettivi: verifica sistemi, raccolta dati sensori, allineamento con target teorici.
   - Limitazioni: run brevi, power unit limitata, focus su reliability.
2. **Bahrain Test #1 – Performance Window**
   - Obiettivi: prime simulazioni gara/qualifica, confronto in diverse condizioni meteo/pista.
   - Introduzione di primi pacchetti aggiornamento e gestione sandbagging medio.
3. **Bahrain Test #2 – Race Prep & Sandbagging**
   - Obiettivi: finalizzare assetti gara, stress test affidabilità lunga durata, definire setup baseline per Sakhir GP.
   - Sandbagging spinto: il giocatore sceglie quanto nascondere (affect reputation/media).
- **Regole comuni**: gestione allocation gomme dedicata (diversa da FP), track evolution custom, eventuali sessioni extra per filming day (opzionale).

## 6. Meccaniche in Pista & Telemetria
- **Loop di ogni stint**:
  1. Configurazione run (fuel, mappature, assetto provvisorio, livello di sandbagging).
  2. LapSimulator + ambienti (meteo + track evolution) → produzione telemetria.
  3. Confronto automatico misurato vs target → aggiornamento punteggio di correlazione per ciascun sottosistema.
- **Eventi dinamici**: scoperte positive (target superati), failure strutturali, ritardi componenti, quick fix tra sessioni.
- **Metriche**: correlation score %, affidabilità per subsystem, knowledge gain (simile a setup info_points), confidence PU.
- **Interazione AI**: squadre AI possono seguire loop completo o versioni scriptate (TODO definire modello definitivo).

## 7. R&D Focus
- **Struttura**:
  - Aerodinamica: milestone (concept, validazione CFD, correlazione pista), metriche (CL/CD, bilanciamento, cooling).
  - Power Unit: ICE/ERS/turbo, mappe disponibili, limiti termici, affidabilità km accumulati.
  - Meccanica & sistemi: sospensioni, freni, integrazione packaging.
- **Risorse**: staff assegnabile, efficienza, costi giornalieri, possibilità di task paralleli.
- **Gate**: pass/fail che autorizzano l'uso di componenti nei test (es. se non validato → rischio failure elevato).
- **TODO (approfondire)**: definire numeri target per ciascun subsystem, interfaccia R&D con economia gioco, tempistiche reali vs accelerate.

## 8. Feedback Ingegneri/Piloti
- **Canali**: report ingegneri pista, note capo ingegnere R&D, commenti piloti post-run.
- **Granularità**: messaggi qualitativi ("sovrasterzo high-speed") + indicatori numerici (confidence %, temperatura media, delta vs target).
- **Impatto gameplay**:
  - Sblocco nuovi range setup/mappature quando la correlazione supera soglie.
  - Warning affidabilità/temperature se mismatch supera limiti.
  - Possibilità di scelte narrative (es. continuare a nascondere vs mostrare passo reale).
- **TODO (design)**: definire UI/UX dedicata o riuso dashboard garage, timeline notifiche, priorità messaggi.

## 9. Output e Collegamento alla Stagione
- **Valori generati**:
  - Performance base (per settore, per condizione) → seed iniziale per prime gare.
  - Affidabilità componenti + rischio failure extra se problemi non risolti.
  - Setup baseline per ciascun pilota, con livello di confidenza.
  - Configurazioni PU disponibili (mappe sbloccate o limitate).
- **Regole**:
  - Se correlazione alta → riduzione incertezza e maggiore performance iniziale.
  - Se sandbagging eccessivo → reputazione media bassa ma vantaggio sorpresa in gara 1.
  - Eventuali mismatch non risolti generano malus adattivi (es. degrado gomme maggiore nelle prime gare).
- **Integrazione**: output salvati come stato iniziale nel savegame e consumati dal modulo principale (Practice/Qualifica/Gara).

## 10. Questioni Aperte & TODO
1. **Granularità Power Unit** – decidere se simulare separatamente ICE, ERS, turbo oppure usare un layer astratto. _Owner: Tech Design_.
2. **Loop AI** – definire se le AI team seguono l'intero processo o una versione semplificata. _Owner: AI Systems_.
3. **UI dedicata** – valutare se creare dashboard prestagionale o estendere garage esistente. _Owner: UX_.
4. **Telemetria storica** – integrare esempi reali 2026 per narrativa/benchmark. _Owner: Narrative_.
5. **Bilancio economico** – connettere costi R&D e logistica al modello finanziario. _Owner: Economy_.

---
**Stato**: WIP – aggiornare questo documento man mano che le sezioni R&D e Feedback vengono dettagliate e quando le dipendenze con roadmap esistenti saranno confermate.
