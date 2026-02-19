import json
import sys
from pathlib import Path
from types import SimpleNamespace

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
from lap_simulator.data_types import (
    CircuitConfig,
    DriverIntent,
    EngineMapName,
    EngineMapParams,
    EnvContext,
    PUState,
    PUReliabilityParams,
    SectionContext,
    SectionKind,
)
from lap_simulator.power_unit import generate_output, ERS_MAX_ENERGY_MJ
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


def test_power_unit_clamps_when_deploy_budget_exhausted():
    config = CircuitConfig(
        pu_maps={
            EngineMapName.QUALY: EngineMapParams(
                name=EngineMapName.QUALY,
                torque_ramp=1.0,
                cooling_share=0.5,
                ers_output_kw=120.0,
            )
        },
        pu_reliability=PUReliabilityParams(),
        ers_budget={
            "deploy_limit_mj": 0.2,
            "harvest_limit_mj": 0.05,
            "maps": {
                "QUALY": {
                    "deploy_mj_per_lap": 0.05,
                    "harvest_mj_per_lap": 0.02,
                }
            },
        },
        regen_profile={
            "base_factor": 0.4,
            "regen_limit_per_section": 0.03,
            "potential_mj_per_lap": 0.03,
        },
        brake_profile={
            "regen_migration_bias": 0.2,
            "hydraulic_vs_regen_ratio": 1.2,
        },
    )
    section = SectionContext(
        section_id="sec_test",
        name="Test",
        kind=SectionKind.SLOW_CORNER,
        length_m=150.0,
        v_base_kph=120.0,
        braking_energy_mj=0.1,
    )
    env = EnvContext()
    driver = DriverIntent(ers_deploy_request=True)
    aero = SimpleNamespace(cooling_capacity=1.0, kerb_severity=0.0, bump_penalty=0.0)
    pu_state = PUState(active_map=EngineMapName.QUALY, ers_energy_mj=0.2)

    # First section consumes the requested energy (bounded by per-bucket share)
    generate_output(pu_state, driver, aero, section, env, config, dt_estimate_s=1.0)
    assert 0.0 < pu_state.lap_deploy_mj < 0.05
    assert "deploy_limit_hit" not in pu_state.runtime_warnings

    # Keep deploying until bucket exhaustion warning appears
    for _ in range(20):
        generate_output(pu_state, driver, aero, section, env, config, dt_estimate_s=1.0)
        if any(w.startswith("bucket_exhausted") for w in pu_state.runtime_warnings):
            break
    else:
        pytest.fail("bucket_exhausted warning not raised after exhausting budget")

    assert pu_state.lap_deploy_mj <= 0.0501
    assert pu_state.energy_trace[-1]["deploy_mj"] == pytest.approx(0.0, abs=1e-4)
    assert pu_state.ers_output_kw == pytest.approx(0.0, abs=1e-3)


def test_brake_migration_respects_hydraulic_ratio():
    config = CircuitConfig(
        pu_maps={
            EngineMapName.STANDARD: EngineMapParams(
                name=EngineMapName.STANDARD,
                torque_ramp=1.0,
                cooling_share=0.5,
                ers_output_kw=60.0,
            )
        },
        pu_reliability=PUReliabilityParams(),
        regen_profile={
            "base_factor": 0.6,
            "regen_limit_per_section": 1.0,
            "potential_mj_per_lap": 5.0,
        },
        brake_profile={
            "hydraulic_vs_regen_ratio": 1.0,  # 50/50 split
        },
    )
    section = SectionContext(
        section_id="sec_brake",
        name="Brake Test",
        kind=SectionKind.SLOW_CORNER,
        length_m=120.0,
        v_base_kph=120.0,
        braking_energy_mj=0.2,
    )
    env = EnvContext()
    driver = DriverIntent(ers_deploy_request=False)
    aero = SimpleNamespace(cooling_capacity=1.0, kerb_severity=0.0, bump_penalty=0.0)
    pu_state = PUState(active_map=EngineMapName.STANDARD, ers_energy_mj=2.0)

    generate_output(pu_state, driver, aero, section, env, config, dt_estimate_s=1.0)

    trace = pu_state.energy_trace[-1]
    regen = trace["harvest_mj"]
    hydraulic = trace["hydraulic_mj"]
    assert regen > 0.0
    assert hydraulic > 0.0
    assert hydraulic == pytest.approx(regen, abs=1e-4)


def test_brake_migration_warns_when_soc_full():
    config = CircuitConfig(
        pu_maps={
            EngineMapName.STANDARD: EngineMapParams(
                name=EngineMapName.STANDARD,
                torque_ramp=1.0,
                cooling_share=0.5,
                ers_output_kw=60.0,
            )
        },
        pu_reliability=PUReliabilityParams(),
        regen_profile={
            "base_factor": 0.5,
            "regen_limit_per_section": 1.0,
            "potential_mj_per_lap": 5.0,
        },
        brake_profile={
            "regen_brake_base": 0.7,
        },
    )
    section = SectionContext(
        section_id="sec_soc",
        name="SOC Full",
        kind=SectionKind.SLOW_CORNER,
        length_m=110.0,
        v_base_kph=110.0,
        braking_energy_mj=0.2,
    )
    env = EnvContext()
    driver = DriverIntent(ers_deploy_request=False)
    aero = SimpleNamespace(cooling_capacity=1.0, kerb_severity=0.0, bump_penalty=0.0)
    pu_state = PUState(active_map=EngineMapName.STANDARD, ers_energy_mj=ERS_MAX_ENERGY_MJ)

    generate_output(pu_state, driver, aero, section, env, config, dt_estimate_s=1.0)

    trace = pu_state.energy_trace[-1]
    assert trace["harvest_mj"] <= 0.003
    assert trace["hydraulic_mj"] == pytest.approx(section.braking_energy_mj, abs=3e-3)
    assert "brake_migration_disabled_soc" in pu_state.runtime_warnings


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
        maps_budget = config.ers_budget.get("maps", {})
        map_name = stats.get("map")
        map_budget = maps_budget.get(map_name, {}) if map_name else {}

        runtime_warnings = stats.get("warnings_runtime", [])
        assert isinstance(runtime_warnings, list)
        deploy_budget = map_budget.get("deploy_mj_per_lap", 0)
        assert "deploy_limit_hit" not in runtime_warnings or stats.get("lap_deploy_mj", 0) >= deploy_budget

        if map_budget:
            deploy = map_budget.get("deploy_mj_per_lap")
            harvest = map_budget.get("harvest_mj_per_lap")
            target_soc = map_budget.get("target_soc_end_lap")
            if deploy is not None:
                assert stats.get("deploy_mj_per_lap") == pytest.approx(deploy)
            if harvest is not None:
                assert stats.get("harvest_mj_per_lap") == pytest.approx(harvest)
            if target_soc is not None:
                assert stats.get("target_soc_end_lap") == pytest.approx(target_soc)
            lap_deploy = stats.get("lap_deploy_mj")
            lap_harvest = stats.get("lap_harvest_mj")
            if lap_deploy is not None:
                assert lap_deploy <= deploy + 0.05
            if lap_harvest is not None and harvest is not None:
                assert lap_harvest <= harvest + 0.05

        soc_pct = stats.get("soc_pct")
        if soc_pct is not None:
            assert 0.0 <= soc_pct <= 105.0
        soc_mj = stats.get("soc_mj")
        if soc_mj is not None and capacity is not None:
            assert soc_mj <= capacity + 0.01

        trace = stats.get("energy_trace", [])
        assert isinstance(trace, list)
        if trace:
            sample = trace[-1]
            assert "section_id" in sample
            assert "deploy_mj" in sample
            assert "harvest_mj" in sample

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

        # Validate brake cooling data structure
        cooling = getattr(car, "brake_cooling", {})
        assert isinstance(cooling, dict), f"brake_cooling should be dict for car {car.driver_number}"
        assert "front" in cooling, f"Missing front brake cooling for car {car.driver_number}"
        assert "rear" in cooling, f"Missing rear brake cooling for car {car.driver_number}"
        
        # Validate brake cooling structure
        for axis in ["front", "rear"]:
            axis_data = cooling[axis]
            assert isinstance(axis_data, dict), f"brake_cooling[{axis}] should be dict"
            assert "current_open" in axis_data, f"Missing current_open for {axis} brake cooling"
            assert "status" in axis_data, f"Missing status for {axis} brake cooling"
            assert axis_data["status"] in ["ok", "warn", "bad", "na"], f"Invalid status {axis_data['status']} for {axis}"
        
        # Validate brake thermal data structure
        thermal = getattr(car, "brake_thermal", {})
        assert isinstance(thermal, dict), f"brake_thermal should be dict for car {car.driver_number}"
        assert "front" in thermal, f"Missing front brake thermal for car {car.driver_number}"
        assert "rear" in thermal, f"Missing rear brake thermal for car {car.driver_number}"
        
        # Validate brake thermal values
        for axis in ["front", "rear"]:
            temp = thermal[axis]
            assert isinstance(temp, (int, float)), f"brake_thermal[{axis}] should be numeric"
            assert 0 <= temp <= 1200, f"Unrealistic {axis} brake temperature: {temp}°C"
        
        # Validate brake thermal thresholds
        thresholds = thermal.get("thresholds", {})
        if thresholds:
            assert "front_c" in thresholds, "Missing front fade threshold"
            assert "rear_c" in thresholds, "Missing rear fade threshold"
            assert isinstance(thresholds["front_c"], (int, float)), "Front threshold should be numeric"
            assert isinstance(thresholds["rear_c"], (int, float)), "Rear threshold should be numeric"
