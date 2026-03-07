# Tests Directory

This is the canonical location for all test files in the F1 Manager AI project.

## Test Categories

### Integration Tests
- `test_calibration_and_telemetry.py` - Calibration validation and telemetry correlation
- `test_session_bridge_team_plan.py` - Session bridge team planning tests

### Game Component Tests  
- `test_game_components_simple.py` - Basic game component functionality
- `test_game_practice_session.py` - Practice session game logic
- `test_ai_simulation_full.py` - Complete AI simulation workflows

### Performance Tests
- `test_brake_penalty_integration.py` - Brake system penalty integration
- `test_brake_penalty_real_sections.py` - Real-world brake section validation
- `test_engine_penalty_integration.py` - Engine penalty system tests
- `test_mclaren_engine_penalty.py` - McLaren-specific engine penalties
- `test_rbr_engine_penalty.py` - Red Bull Racing engine penalties
- `test_realistic_brake_penalty.py` - Realistic brake penalty scenarios

### Parameter Tests
- `test_parameters_impact.py` - Setup parameter impact analysis
- `test_setup_penalties.py` - Setup penalty validation

### Driver Tests
- `test_driver_push_penalty.py` - Driver push level penalties

### Tyre Tests
- `test_suzuka_tyre_validation.py` - Suzuka tyre model validation
- `test_suzuka_tyre_validation_simple.py` - Simplified Suzuka tyre tests

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test category
python -m pytest tests/test_brake_*.py

# Run with coverage
python -m pytest tests/ --cov=python_backend
```

## Test Organization

- All test files should use the `test_*.py` naming convention
- Integration tests should test multiple components working together
- Unit tests should be located within the respective module directories
- Performance tests should include realistic circuit data
