---
title: Phase A – Setup & Validation – Technical Spec
version: 0.2
last_updated: 2026-02-09
scope: "SetupEngineService runtime, mapping slider→fisica, endpoint REST minimi, validazione e feedback iniziale"
---

## 1. Obiettivo fase
- Introdurre **SetupEngineService v0** con mapping slider→fisica, validazione vincoli e primo feedback setup.
- Esporre endpoint REST minimi per UI Garage 2.0 (ranges, validate, apply).
- Implementare UI Garage 2.0 con pannello setup Jarvis Variant B (11 slider, feedback ingegnere, category chips).
- Assicurare coerenza con `docs/setup-engine-spec-v0.1.md`, `docs/config-spec.md`, `docs/setup-ui-plan.md`.

## 2. Documenti di riferimento
- `docs/setup-engine-spec-v0.1.md`
- `docs/config-spec.md`
- `docs/setup-ui-plan.md`

## 3. Moduli coinvolti
- Backend: `python_backend/services/setup_engine_service.py` (nuovo)
- API: `python_backend/routes/api.py`
- Modelli: `python_backend/models/models.py` (`DEFAULT_SETUP_CONFIG`)
- Eval: `python_backend/utils/setup_engine.py`
- Config: `config/setup/setup_mapping_v2.json`

## 4. Funzionalità implementate (v0)
### 4.1 SetupEngineService
- Load mapping per circuito (`setup_mapping_v2.json`)
- Merge default + circuito
- Sanitizzazione input slider (0–100)
- Conversione slider → fisica (deg/mm/rigidity/duct/bias)
- Validazione vincoli (rake, suspension_delta_limit)
- Evaluate setup (wrapper su `evaluate_setup` + categories)

### 4.2 Endpoint REST minimi
- `GET /api/setup/ranges/<circuit_id>` → mapping + constraints + metadata
- `POST /api/setup/validate` → ok/errors/sanitized/physics/constraints + evaluation
- `POST /api/setup/apply` → aggiorna setup auto, resetta feedback flag

### 4.3 UI Garage 2.0 (Jarvis Variant B)
- 11 slider in 4 gruppi: Aerodynamics (front/rear/beam wing), Ride Height (front/rear), Suspension & Anti-roll (susp F/R, antiroll F/R), Brakes (balance, duct).
- Design compatto (720px max-width, no scroll) con grid 2 colonne.
- Feedback row con score giallo + messaggio ingegnere + left border accent.
- 5 category chips (Cornering, Speed, Traction, Stability, Braking) ordinati per score.
- Valori fisici (°, mm, %) e range circuito mostrati per ogni slider.
- Hover effects su slider cards e bottoni.

### 4.4 Flusso feedback setup (HOT LAP gate)
Il feedback ingegnere NON è mostrato in tempo reale durante la modifica degli slider. Il flusso è:
1. **BOX → Setup**: slider visibili, nessun feedback ("Complete a hot lap to see engineer feedback").
2. **Apply**: salva setup come nuovo default; resetta `has_completed_hot_lap` e `setup_feedback`.
3. **Send Out → HOT LAP**: al completamento del giro, `has_completed_hot_lap = True`.
4. **Rientro BOX**: `enter_box()` genera feedback via `_generate_setup_feedback()` solo se `has_completed_hot_lap`.
5. **Setup panel**: feedback visibile (score, categorie, delta per campo).
6. **Modifica slider**: feedback nascosto ("Apply and complete a hot lap to see updated feedback").
7. **Apply → nuovo hot lap necessario** per aggiornare il feedback.

Flag chiave: `car.has_completed_hot_lap` (bool), `car.setup_feedback` (dict|None).
Serializzazione: `has_setup_feedback = has_completed_hot_lap AND setup_feedback` (esposto in API + websocket).

## 5. Stato corrente
✅ Modulo `SetupEngineService` creato e connesso alle API.
✅ Estesi i campi di setup per includere: beam_wing, antiroll, brake balance, brake duct.
✅ Endpoint testati localmente (ranges/validate/apply) con circuito specifico.
✅ `evaluate_setup` aggiornato con indici fisici (`aero_balance`, `drag_index`, `traction_index`) + `recommended_ranges`.
✅ `evaluate_setup_categories` allineato ai nuovi indici (cornering/speed/traction/stability).
✅ Generati i file `config/setup/setup_ranges/*.json` tramite `scripts/generate_setup_ranges.py` (es. `config/setup/setup_ranges/at-1969_spielberg.json`).
✅ Implementata la gerarchia ideal setup (baseline circuito + offset team/pilota) con `config/setup/team_offsets.json` e endpoint `/api/setup/ideal`.
✅ UI Garage 2.0 implementata (Jarvis Variant B): 11 slider, design compatto, feedback row, category chips.
✅ Flusso feedback post-HOT LAP: nessun feedback live, solo dopo rientro ai box con almeno 1 hot lap completato.

## 6. Gap / prossimo step
- ✅ **CI setup-calibration**: coperto dai clamp FE/BE.
- ✅ **UI Garage 2.0**: implementata con Jarvis Variant B.
- ✅ **Feedback flow**: gated da HOT LAP, nessun feedback live.
- Integrare `setup_ranges/<circuit>.json` quando disponibile (oggi fallback ai range base).
- (Opzionale) persistenza `garage_state.json` per sessione.
- (Opzionale) tooltips/manuale ingegnere per spiegare gli indicatori fisici.

## 7. Test minimi
- `GET /api/setup/ranges/<circuit_id>` restituisce mapping circuito corretto.
- `POST /api/setup/validate` con setup valido → ok=true, physics popolato.
- `POST /api/setup/apply` con driver in BOX → setup aggiornato + evaluation.
- Verifica presenza output in `config/setup/setup_ranges/`.
- Verifica campione: `config/setup/setup_ranges/at-1969_spielberg.json` coerente con range/target/tolerance/weight base.

## 8. Note
- In caso di `circuit_id` non risolto, fallback su `default`.
- Tutti i messaggi UI devono restare in **English** (come da requisito di prodotto).
