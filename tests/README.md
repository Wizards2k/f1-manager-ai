# Tests Directory

This is the canonical location for all automated tests in the F1 Manager AI project.

## Test Map

| Area | Files | Purpose |
| --- | --- | --- |
| Support files | `conftest.py`, `physics_v4_config.py` | Shared pytest fixtures, import path setup, and Physics V4 configuration |
| Physics V4 subsystem suite | `physics_v4/` | Dedicated coverage for aero, mass, suspension, power unit, tyres, brakes, vehicle, driver, setup, and integration |
| Calibration & telemetry | `test_calibration_and_telemetry.py` | Calibration validation and telemetry correlation |
| Session bridge | `test_session_bridge_team_plan.py`, `test_session_bridge_high_speed.py` | Session bridge planning and runtime checks |
| Game flow | `test_game_components_simple.py`, `test_game_practice_session.py`, `test_ai_simulation_full.py`, `test_qualifying_session.py`, `test_save_load.py` | Core gameplay, qualifying, and persistence flows |
| Penalty system | `test_penalty_toggles.py`, `test_penalty_cache.py`, `test_brake_penalty_integration.py`, `test_brake_penalty_real_sections.py`, `test_realistic_brake_penalty.py`, `test_engine_penalty_integration.py`, `test_mclaren_engine_penalty.py`, `test_rbr_engine_penalty.py` | Master toggle, cache behavior, and brake/engine penalty scenarios |
| Setup & parameters | `test_parameters_impact.py`, `test_setup_penalties.py` | Setup impact and penalty validation |
| Driver behavior | `test_driver_push_penalty.py` | Driver push-level penalties |
| Tyres | `test_suzuka_tyre_validation.py`, `test_suzuka_tyre_validation_simple.py`, `test_tyre_low_push_cooling.py` | Tyre validation and cooling behavior |
| Weekend flow | `test_weekend_transition.py`, `test_weekend_transition_e2e.py` | Weekend state machine and end-to-end session progression |

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run the Physics V4 suite only
python -m pytest tests/physics_v4/

# Run penalty-related tests
python -m pytest tests/test_*penalty*.py

# Run with coverage
python -m pytest tests/ --cov=python_backend
```

## Organization Rules

- Use the `test_*.py` naming convention for every new test file.
- Keep shared pytest fixtures in `conftest.py`.
- Keep Physics V4 subsystem tests inside `tests/physics_v4/`.
- Add cross-module scenarios at the project level in `tests/`.
- Prefer small, deterministic tests with explicit fixtures.
