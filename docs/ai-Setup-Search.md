# AI Setup Search – Vision & Specification

## 1. Scopo
Definire come le auto AI cercano il setup ideale durante FP1–FP3 usando gli stessi concetti chiave del giocatore (setup score da 0 a 10), ma con pipeline autonoma. Il documento traccia:
- da dove arriva il setup iniziale (simulatore team + stato auto)
- come i piloti contribuiscono a migliorarlo
- quando e perché l’AI decide che l’assetto è “abbastanza buono”
- quali dati servono prima di implementare codice

## 2. Concetti principali
### 2.1 Simulator Baseline Score (Team)
- Ogni team possiede un "simulator quality" (1–100) che determina quanto il setup iniziale è vicino all'ottimale.
- Il baseline viene generato con `generate_baseline_setup()`: per ogni slider, la deviazione dall'ottimale è proporzionale a `noise_factor = (1 - sim_q/100) * 2.4`.
- Lo **setup score** è calcolato con `evaluate_setup()` (penalty-based: 0.0 = perfetto, negativo = peggiore), mappato su scala 0–10: `score_10 = 10 + raw * 3.5`.

| Team tier       | Simulator quality | Baseline score (FP1 start) | Avg runs to complete | Note |
|-----------------|-------------------|----------------------------|----------------------|------|
| Top             | 84–90             | ~7.4 – 9.4 (avg 8.2)      | ~2.5                 | Simulatori quasi perfetti, pochi aggiustamenti |
| Midfield        | 68–76             | ~5.8 – 8.8 (avg 7.3)      | ~3.7                 | Necessarie 3-4 run di tuning |
| Backmarker      | 56–64             | ~5.0 – 8.4 (avg 6.5)      | ~4.0                 | Simulatori poveri, dipendenza forte dai piloti |

### 2.2 Pilot Skill – “Ricerca Assetto”
- Tabella skill piloti da rivedere e ampliare (0–100) in base alla forza reale.
- Il valore rappresenta: velocità con cui il pilota trasforma dati run → miglioramento score.
- Esempio mapping: 95 (Verstappen/Hamilton), 80 (mid field solid), 60 (rookie), 45 (backmarker debole).
- Skill agisce come moltiplicatore nella funzione `delta_score = base_gain * skill_mult` per ogni run di raccolta dati.

### 2.3 Setup Score Loop (FP1–FP3)
1. **Initialization**: ogni AI entra in FP1 con il baseline score calcolato al §2.1 e un “ideal target” legato all’auto/circuito (es. 8.5).
2. **Run execution**: durante le run contrassegnate “Setup Validation”, “Tyre Deg” ecc., i piloti accumulano info. Ogni run produce uno shift del setup score (non giri singoli, ma output di run).
3. **Score update**: nuovo score = score precedente + contributo pilota, limitato dal massimo teorico dell’auto (es. 9.0 per top, 8.2 per back) per mantenere carattere vettura.
4. **Threshold check**: se il nuovo score supera la soglia personalizzata, la squadra dichiara setup pronto e passa a programmi successivi.

### 2.4 Convergence Threshold per auto
- Invece di target multipli per tier, usiamo una **soglia legata allo score UI** (scala 0–10).
- Valore di riferimento: **8.5** (base threshold).
- Ogni auto AI ha un offset dovuto al tratto pilota "Perfezionismo" (1–100):
  - Soglia effettiva = `8.5 + (perfezionismo - 60) / 280`.
  - Perfezionismo 60 → 8.50, 75 → 8.55, 85 → 8.59, 95 → 8.63.
  - Piloti perfezionisti aspettano score più alto prima di fermarsi; altri accettano un assetto leggermente inferiore pur di risparmiare tempo.
- Questo preserva un'unica metrica (setup score) ma rende la decisione individuale.

### 2.5 Output & Telemetria
- Ogni run produce log con: sessione, programma, run_index, score_in, score_out, threshold, “setup_complete?” flag.
- Report HTML/CSV (vedi `scripts/sim_setup_analysis.py`) mostrerà: baseline, progress run-by-run, session in cui si è raggiunto il target.
- Dati verranno usati anche per UI spettatore (micro pannello “Setup status” per team AI?).

### 2.6 Algoritmo di regolazione slider (ali, sospensioni, rollbar)
Quando il pilota AI migliora il setup non si limita ad aumentare lo score astratto: modifica realmente le tarature che esistono anche per il giocatore.

1. **State snapshot**: ogni auto mantiene un vettore `setup_config` (front/rear wing, ride height F/R, suspension F/R, anti-roll bar F/R, brake bias, camber, toe, ecc.). Questo vettore parte dal baseline generato dal simulatore.
2. **Analisi del feedback run**:
   - Il motore di punteggio restituisce per ogni run tre indicatori “macro” (es. `cornering_balance`, `straight_line_efficiency`, `traction_stability`) con segno e intensità.
   - Ogni indicatore è mappato a un set di slider che possono correggerlo (es. cornering ↔ ali + sospensioni anteriori/posteriori; straight-line ↔ ali + rake; traction ↔ sospensioni + rollbar).
3. **Delta calcolato con skill pilota**:
   - `delta_component = base_step * feedback_intensity * pilot_skill_mult`
   - `base_step` è diverso per tipologia componente (ali: 2 punti, sospensioni: 1 punto, rollbar: 1 punto, ride height: 1.5 punti) per riflettere la sensibilità reale.
   - `pilot_skill_mult = 0.6 + skill/100 * 0.8` (stesso concetto della raccolta dati): piloti bravi applicano correzioni più precise.
   - **Qualità regolazione**: aggiungiamo una classificazione derivata dalla stessa skill (es. Elite ≥85, Solido 70-84, Incostante 55-69, Sperimentale <55). Ogni categoria influenza:
     - *Precisione*: moltiplicatore 1.05 / 1.0 / 0.9 / 0.8 sul delta calcolato.
     - *Varianza*: errore casuale gaussian (σ = 0.1 / 0.2 / 0.4 / 0.6) per simulare piccoli overshoot/undershoot.

| Categoria pilota | Range skill ricerca | Precisione (mult) | Varianza σ | Prob. errore casuale | Comportamento |
|------------------|---------------------|-------------------|------------|----------------------|---------------|
| Elite            | ≥ 85                | 1.05              | 0.10       | 5%                   | Regolazioni quasi perfette, piccoli fine-tuning |
| Solido           | 70 – 84             | 1.00              | 0.20       | 10%                  | Affidabile, qualche correzione extra |
| Incostante       | 55 – 69             | 0.90              | 0.40       | 18%                  | Alterna buone intuizioni a errori evidenti |
| Sperimentale     | < 55                | 0.80              | 0.60       | 25%                  | Tende a sbagliare slider o esagerare le modifiche |
4. **Aggiornamento configurazione**:
   - Per ogni slider legato all’indicatore, si applica `new_value = clamp(old_value + delta_component * direction, min, max)` rispettando i bound usati dal giocatore.
   - Si registra la modifica per telemetria (“run 2 → front wing +1.2, rear wing +0.8”).
   - **Errori casuali controllati**: con probabilità dipendente dalla categoria (es. 5% Elite, 10% Solido, 18% Incostante, 25% Sperimentale) viene applicata una correzione nel verso opposto oppure su uno slider non ideale, per riprodurre iterazioni “sbagliate” prima di convergere.
5. **Ricalcolo score reale**:
   - Una volta aggiornati gli slider, il motore `evaluate_setup()` (lo stesso che sarà usato dal giocatore) ricalcola il setup score effettivo.
   - Il valore ottenuto alimenta il loop di §2.3 (score update + threshold).

In questo modo l’AI segue lo stesso ciclo che seguirebbe un umano: prova un assetto, riceve feedback, modifica ali/sospensioni/rollbar, ricalcola lo score. La differenza è che il suo “istinto” deriva da skill pilota + qualità simulatore.

## 3. Dati da preparare prima dell’implementazione
1. **Mappa simulator quality per team** (tabella definitiva top/mid/back + eventuali eccezioni).
2. **Nuova tabella skill piloti** con valori chiari per `ricerca_assetto` + nuovo attributo `perfectionism`.
3. **Bound auto**: valore massimo raggiungibile da ogni vettura (es. top 9.0, mid 8.4, back 8.0) per evitare che un team scarso superi i top.
4. **Funzione di mapping score → performance** (serve in futuro per collegare al ritmo gara).

## 4. Flusso riassuntivo
1. Caricamento sessione ⇒ calcola baseline score usando simulator quality.
2. FP1 run #1 ⇒ applica contributo pilota, aggiorna score; se score ≥ soglia personale ⇒ flag “setup pronto”.
3. Se non pronto, pianifica run successive (FP1 run #2/#3, FP2). Midfield/back, partendo più lontani, spenderanno fisiologicamente più run.
4. Al raggiungimento soglia ⇒ passa automaticamente a programmi quali/race trim.

## 5. Implementazione (completata)

### File creati/modificati
- **`utils/ai_setup_search.py`** — Nuovo modulo: baseline generation, score computation, slider adjustment algorithm, convergence check, `AISetupState` dataclass.
- **`utils/session_bridge.py`** — Wired: `AISetupState` creato in `init_session()`, `process_run()` chiamato in `_complete_car_run()`, player-only `_accumulate_setup_info` in `_commit_lap()`.
- **`models/models.py`** — Aggiunto `perfezionismo` a `Pilota`, `simulator_quality` e `pitstop_skill` a `Team`.
- **`data/pilots.py`** — Tutte le skill piloti aggiornate con valori reali.
- **`data/teams/__init__.py`** — `simulator_quality` e `pitstop_skill` per ogni team.
- **`scripts/sim_setup_analysis_v2.py`** — Script di simulazione headless + report HTML.

### Risultati simulazione (seed 42)
- **Top**: avg 2.5 runs (range 1–4), initial avg 8.20, final avg 9.14
- **Mid**: avg 3.7 runs (range 1–6), initial avg 7.27, final avg 8.91
- **Back**: avg 4.0 runs (range 3–5), initial avg 6.54, final avg 8.49
