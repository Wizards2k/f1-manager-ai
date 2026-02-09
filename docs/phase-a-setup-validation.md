---
title: Phase A – Setup & Validation – Technical Spec
version: 0.1
last_updated: 2026-02-08
scope: "SetupEngineService runtime, mapping slider→fisica, endpoint REST minimi, validazione e feedback iniziale"
---

## 1. Obiettivo fase
- Introdurre **SetupEngineService v0** con mapping slider→fisica, validazione vincoli e primo feedback setup.
- Esporre endpoint REST minimi per UI Garage 2.0 (ranges, validate, apply).
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
- `POST /api/setup/validate` → ok/errors/sanitized/physics/constraints
- `POST /api/setup/apply` → aggiorna setup auto + evaluation

## 5. Stato corrente
✅ Modulo `SetupEngineService` creato e connesso alle API.
✅ Estesi i campi di setup per includere: beam_wing, antiroll, brake balance, brake duct.
✅ Endpoint testati localmente (ranges/validate/apply) con circuito specifico.
✅ `evaluate_setup` aggiornato con indici fisici (`aero_balance`, `drag_index`, `traction_index`) + `recommended_ranges`.
✅ `evaluate_setup_categories` allineato ai nuovi indici (cornering/speed/traction/stability).
✅ Generati i file `config/setup/setup_ranges/*.json` tramite `scripts/generate_setup_ranges.py` (es. `config/setup/setup_ranges/at-1969_spielberg.json`).
✅ Implementata la gerarchia ideal setup (baseline circuito + offset team/pilota) con `config/setup/team_offsets.json` e endpoint `/api/setup/ideal`.

## 6. Gap / prossimo step
- Integrare `setup_ranges/<circuit>.json` quando disponibile (oggi fallback ai range base).
- Esporre feedback UI più coerente con Setup Engine 2.0 (tone/messages).
- (Opzionale) persistenza `garage_state.json` per sessione.

## 7. Test minimi
- `GET /api/setup/ranges/<circuit_id>` restituisce mapping circuito corretto.
- `POST /api/setup/validate` con setup valido → ok=true, physics popolato.
- `POST /api/setup/apply` con driver in BOX → setup aggiornato + evaluation.
- Verifica presenza output in `config/setup/setup_ranges/`.
- Verifica campione: `config/setup/setup_ranges/at-1969_spielberg.json` coerente con range/target/tolerance/weight base.

## 8. Note
- In caso di `circuit_id` non risolto, fallback su `default`.
- Tutti i messaggi UI devono restare in **English** (come da requisito di prodotto).
