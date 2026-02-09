---
title: Phase A – Setup & Validation – Technical Spec
version: 0.3
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

### 4.4 Flusso feedback setup (sistema adattivo info_points)
Il feedback ingegnere è basato sulla quantità di **informazioni raccolte** in pista, non su un singolo hot lap.

#### Accumulo informazioni
Ogni giro completato genera `info_points` in base a:
- **Tipo giro**: HOT LAP = 35 punti base, OUT LAP = 8, IN LAP = 5.
- **Skill pilota**: `ricerca_assetto` (1–100) → moltiplicatore 0.6x–1.4x.
- Formula: `info_gain = base_gain × (0.6 + ricerca_assetto / 100 × 0.8)`

#### Soglia dinamica
`info_target = 100 + delta_penalty(setup_delta)` dove `delta_penalty` segue una curva U-shaped:
- Delta < 5 (quasi perfetto): +40 (difficile da leggere)
- Delta 5–15: +10
- Delta 15–25 (sweet spot): +0
- Delta 25–40: +20
- Delta > 40 (terribile): +50 (difficile da giudicare)

#### Chip DATA sulla car card
Sempre visibile accanto alla pill di stato (HOT/OUT/IN):
- **Rosso**: 0–33% del target.
- **Giallo**: 34–66%.
- **Verde**: ≥67%; **lampeggia** quando raggiunge il 100%.

#### Setup panel
- Barra di progresso colorata (rosso/giallo/verde) con messaggi contestuali:
  - `"Send the car out to collect setup data."` (0%)
  - `"Gathering data… N%"` (1–99%)
  - `"Data ready — box the car for engineer feedback."` (≥100%)
- Feedback completo (score, categorie, delta) visibile solo quando `setup_feedback_ready AND setup_feedback`.

#### Reset
- **Apply/save setup** → `car.reset_setup_info()`: azzera `info_points`, ricalcola `info_target`, cancella `setup_feedback`.
- **Rientro BOX**: `enter_box()` genera feedback solo se `setup_feedback_ready` è True.

#### Flag e serializzazione
- `car.setup_info_points` (float), `car.setup_info_target` (float)
- `car.setup_feedback_ready` (property: `info_points >= info_target`)
- `car.setup_info_percent` (property: `info_points / info_target × 100`, cap 100)
- API + websocket: `has_setup_feedback`, `setup_info_percent`

## 5. Stato corrente
✅ Modulo `SetupEngineService` creato e connesso alle API.
✅ Estesi i campi di setup per includere: beam_wing, antiroll, brake balance, brake duct.
✅ Endpoint testati localmente (ranges/validate/apply) con circuito specifico.
✅ `evaluate_setup` aggiornato con indici fisici (`aero_balance`, `drag_index`, `traction_index`) + `recommended_ranges`.
✅ `evaluate_setup_categories` allineato ai nuovi indici (cornering/speed/traction/stability).
✅ Generati i file `config/setup/setup_ranges/*.json` tramite `scripts/generate_setup_ranges.py` (es. `config/setup/setup_ranges/at-1969_spielberg.json`).
✅ Implementata la gerarchia ideal setup (baseline circuito + offset team/pilota) con `config/setup/team_offsets.json` e endpoint `/api/setup/ideal`.
✅ UI Garage 2.0 implementata (Jarvis Variant B): 11 slider, design compatto, feedback row, category chips.
✅ Sistema adattivo info_points: accumulo per giro (skill × tipo giro), soglia U-shaped, chip DATA (rosso/giallo/verde/blink), progress bar nel pannello setup.
✅ 5 categorie feedback: cornering, speed, traction, stability, braking.
✅ Score globale colorato (28px, classi green/yellow/orange/red/fuchsia).
✅ Barra notifiche ancorata al dock (non più flottante).

## 6. Gap / prossimo step
- ✅ **CI setup-calibration**: coperto dai clamp FE/BE.
- ✅ **UI Garage 2.0**: implementata con Jarvis Variant B.
- ✅ **Feedback flow**: sistema adattivo info_points con chip DATA e progress bar.
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
