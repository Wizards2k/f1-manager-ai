import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PYTHON_BACKEND_ROOT = TESTS_DIR.parent
REPO_ROOT = PYTHON_BACKEND_ROOT.parent

for path in (PYTHON_BACKEND_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from data.teams import TEAMS
from lap_simulator.config_loader import load_circuit_config
from models import RaceCar
from utils.session_bridge import SessionBridge

DERIVED_DIR = REPO_ROOT / "config" / "circuits" / "derived"


def _list_circuits():
    return sorted(p.name for p in DERIVED_DIR.iterdir() if p.is_dir())


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _build_player_cars(count: int = 2):
    cars = []
    for team in TEAMS:
        for pilot in team.piloti_titolari:
            car = RaceCar(pilot=pilot, team=team)
            car.is_player_controlled = True
            car.player_config["fuel_percent"] = 70
            car.player_config["tyre_compound"] = car.current_tire.value
            car.fuel_percent = 70
            car.stint_target_laps = 4
            cars.append(car)
            if len(cars) >= count:
                return cars
    raise RuntimeError("Not enough pilots in TEAMS to build player cars")


@pytest.mark.parametrize("circuit_id", _list_circuits())
def test_circuit_config_matches_calibration_sources(circuit_id):
    derived_dir = DERIVED_DIR / circuit_id
    pu_path = derived_dir / "pu_maps.json"
    brake_path = derived_dir / "brake_params.json"

    assert pu_path.exists(), f"Missing PU maps for {circuit_id}"
    assert brake_path.exists(), f"Missing brake params for {circuit_id}"

    pu_data = _load_json(pu_path)
    brake_data = _load_json(brake_path)

    config = load_circuit_config(circuit_id)

    expected_ers = pu_data.get("ers_budget", {})
    expected_regen = pu_data.get("regen_profile", {})
    expected_soc_warnings = pu_data.get("soc_warnings", [])

    assert config.ers_budget == expected_ers
    assert config.regen_profile == expected_regen
    assert config.soc_warnings == expected_soc_warnings

    calibration = brake_data.get("_calibration", {})
    expected_profile = calibration.get("brake_profile", {})
    expected_sections = calibration.get("critical_sections", [])

    assert config.brake_profile == expected_profile
    assert config.brake_critical_sections == expected_sections


@pytest.mark.slow
@pytest.mark.parametrize("circuit_id", _list_circuits())
def test_session_bridge_three_laps_per_circuit(circuit_id):
    cars = _build_player_cars()
    bridge = SessionBridge()
    assert bridge.init_session(circuit_id, cars, session_type="FP1"), f"Failed to init SessionBridge for {circuit_id}"

    laps_required = 10

    for car in cars:
        fuel = max(90, car.player_config.get("fuel_percent", car.fuel_percent))
        stint = max(laps_required + 2, car.stint_target_laps)
        ok = bridge.player_send_out(
            car,
            compound=str(car.current_tire.value),
            fuel_percent=fuel,
            stint_laps=stint,
        )
        assert ok, f"player_send_out failed for car {car.driver_number} on {circuit_id}"

    max_ticks = laps_required * 2000  # generous cap to allow cooldowns
    for _ in range(max_ticks):
        bridge.tick(1.0)
        if all(car.total_laps >= laps_required for car in cars):
            break
    else:
        pytest.fail(f"Cars did not complete {laps_required} laps on {circuit_id}")

    config = bridge.circuit_config
    assert config is not None

    for car in cars:
        stats = getattr(car, "pu_stats", None)
        diagnostics = getattr(car, "brake_diagnostics", None)
        assert stats, f"Missing pu_stats for car {car.driver_number} on {circuit_id}"
        assert diagnostics, f"Missing brake diagnostics for car {car.driver_number} on {circuit_id}"

        capacity = config.ers_budget.get("battery_capacity_mj")
        if capacity is not None:
            assert stats.get("capacity_mj") == pytest.approx(capacity)
        deploy_limit = config.ers_budget.get("deploy_limit_mj")
        if deploy_limit is not None:
            assert stats.get("deploy_limit_mj") == pytest.approx(deploy_limit)
        harvest_limit = config.ers_budget.get("harvest_limit_mj")
        if harvest_limit is not None:
            assert stats.get("harvest_limit_mj") == pytest.approx(harvest_limit)

        assert stats.get("warnings", []) == config.ers_budget.get("warnings", [])

        map_name = stats.get("map")
        maps_budget = config.ers_budget.get("maps", {})
        if map_name in maps_budget:
            map_budget = maps_budget[map_name]
            deploy = map_budget.get("deploy_mj_per_lap")
            harvest = map_budget.get("harvest_mj_per_lap")
            target_soc = map_budget.get("target_soc_end_lap")
            if deploy is not None:
                assert stats.get("deploy_mj_per_lap") == pytest.approx(deploy)
            if harvest is not None:
                assert stats.get("harvest_mj_per_lap") == pytest.approx(harvest)
            if target_soc is not None:
                assert stats.get("target_soc_end_lap") == pytest.approx(target_soc)

        soc_pct = stats.get("soc_pct")
        if soc_pct is not None:
            assert 0.0 <= soc_pct <= 105.0
        soc_mj = stats.get("soc_mj")
        if soc_mj is not None and capacity is not None:
            assert soc_mj <= capacity + 0.01

        profile = config.brake_profile or {}
        regen_base = profile.get("regen_brake_base")
        if regen_base is not None:
            assert diagnostics.get("regen_brake_base") == pytest.approx(regen_base)
        regen_bias = profile.get("regen_migration_bias")
        if regen_bias is not None:
            assert diagnostics.get("regen_migration_bias") == pytest.approx(regen_bias)
        ratio = profile.get("hydraulic_vs_regen_ratio")
        if ratio is not None:
            assert diagnostics.get("hydraulic_vs_regen_ratio") == pytest.approx(ratio)

        assert diagnostics.get("critical_sections") == config.brake_critical_sections
        assert diagnostics.get("current_section_id") is not None
        assert diagnostics.get("current_braking_energy_mj") is not None
