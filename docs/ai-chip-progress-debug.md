# AI DATA Chip Progress Debug

## Problema osservato
- Durante le FP le chip DATA delle AI restano quasi sempre rosse e, in rari casi, saltano direttamente allo stato "READY" senza passare per giallo/verde.
- Il backend calcola `setup_info_percent` per ogni AI basandosi su `setup_info_points`, ma la logica delle penalità riportava immediatamente i punti a 0 ad ogni run in cui venivano cambiati gli slider.
- La UI (timing panel + garage) applica soglie 40%/80%: con i punti sempre a 0 le chip non possono mai diventare gialle o verdi.

## Diagnosi
1. **Strumentazione**
   - Aggiunto logging mirato in `RaceCar.apply_ai_progress_result` e in `SessionBridge._complete_car_run` (`ai_chip_progress`, `ai_chip_run`).
   - Il log viene scritto in `f1_setup_debug.log` (override con `F1_DEBUG_LOG`).
2. **Evidenze dal log (12 feb 23:43-23:46)**
   - Ogni run IA registrava `outcome = "penalty"`, `points_before = points_after = 0`, colore invariato su rosso.
   - Solo il driver 12, che ha ricevuto `setup_complete = true`, è passato da rosso a ready in un singolo step.
   - Le penalità scattavano perché il motore setup modificava quasi tutti gli 11 slider ogni run, raggiungendo subito il cap di 40 punti e annullando qualsiasi progresso.

## Contromisura adottata (Opzione 3)
- `RaceCar.apply_ai_progress_result` ora accetta `score_before`, `score_after`, `score_threshold` e calcola la percentuale partendo direttamente da `(score_after / threshold) * 100`.
- Quando il motore dichiara `setup_complete`, forziamo 100% (chip "READY").
- Solo se il motore non fornisce punteggi (fallback legacy) torniamo alla logica gain/penalty.
- I log includono ora le metriche di score per ogni run, così possiamo tracciare la progressione.

## Prossimi passi
1. Avviare una sessione FP post-patch e raccogliere di nuovo `f1_setup_debug.log` per verificare che `percent_after` salga progressivamente verso 40/80.
2. Controllare nella UI (garage + timing panel) che le chip passino rosso → giallo → verde → ready/blink in linea con le soglie.
3. Se necessario, ritoccare le soglie UI o introdurre smoothing (es. media mobile sui punteggi) per evitare oscillazioni.
