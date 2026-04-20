"""
Physics Engine V4 - Initial Calibration Benchmark

Esegue il benchmark iniziale usato come punto di partenza della calibrazione:
- auto McLaren
- driver Lando Norris
- assetto qualifica
- singolo giro di riferimento
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_engine.core.team_driver_data import DriverSkill, TeamData, TeamDriverLoader
from lap_simulator.physics_engine.setup.default_setups import DefaultSetups


DEFAULT_CALIBRATION_CIRCUIT_ID = "it-1922_monza"
DEFAULT_CALIBRATION_TEAM_NAME = "McLaren"
DEFAULT_CALIBRATION_DRIVER_NAME = "Lando Norris"
DEFAULT_CALIBRATION_SESSION = "qualifying"
DEFAULT_CALIBRATION_WEATHER = "dry"
DEFAULT_CALIBRATION_TYRE_COMPOUND = "C5"
DEFAULT_CALIBRATION_PUSH_LEVEL = 10.0
DEFAULT_CALIBRATION_ENGINE_MAP = "QUALIFY"
DEFAULT_CALIBRATION_ERS_MODE = "OVERTAKE"
DEFAULT_CALIBRATION_ICE_MODE = "aggressive"
DEFAULT_CALIBRATION_PHYSICS_ERS_MODE = "quali_deploy"
DEFAULT_CALIBRATION_OBJECTIVE = "Simulate a telemetry-aligned Monza qualifying lap."
DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT = 0.02


def _get_soft_compound_from_telemetry(circuit_id: str) -> str:
    """Legge la mescola SOFT dal file telemetry del circuito."""
    base = Path(__file__).parent.parent.parent.parent / "data" / "circuits" / "2025"
    path = base / f"{circuit_id}_Telemetry.json"
    if not path.exists():
        return "C3"  # fallback generico
    with open(path) as f:
        data = json.load(f)
    return data.get("tyre_allocation", {}).get("dry_compounds", {}).get("soft", "C3")


@dataclass(frozen=True)
class InitialCalibrationSpec:
    """Specifica del benchmark iniziale di calibrazione."""

    circuit_id: str = DEFAULT_CALIBRATION_CIRCUIT_ID
    team_name: str = DEFAULT_CALIBRATION_TEAM_NAME
    driver_name: str = DEFAULT_CALIBRATION_DRIVER_NAME
    session: str = DEFAULT_CALIBRATION_SESSION
    weather: str = DEFAULT_CALIBRATION_WEATHER
    tyre_compound: str = DEFAULT_CALIBRATION_TYRE_COMPOUND


@dataclass(frozen=True)
class InitialCalibrationSetup:
    """Setup costruito per il benchmark iniziale di calibrazione."""

    spec: InitialCalibrationSpec
    physics_setup: PhysicsV4Setup
    reference_setup: Dict[str, float]
    team: TeamData
    driver: DriverSkill
    benchmark_context: Dict[str, Any] = field(default_factory=dict)


def _build_benchmark_context(physics_setup: PhysicsV4Setup) -> Dict[str, Any]:
    power_unit = physics_setup.car.power_unit
    return {
        "objective": DEFAULT_CALIBRATION_OBJECTIVE,
        "run_plan": {
            "push_level": DEFAULT_CALIBRATION_PUSH_LEVEL,
            "engine_map": DEFAULT_CALIBRATION_ENGINE_MAP,
            "ers_mode": DEFAULT_CALIBRATION_ERS_MODE,
        },
        "acceptance_criteria": {
            "microsector_margin_pct_max": DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT,
            "microsector_margin_basis": "abs((sim_dt - ref_dt) / ref_dt)",
        },
        "physics_modes": {
            "ice_mode": power_unit.ice_mode,
            "ers_deploy_mode": power_unit.ers_deploy_mode,
            "target_ice_mode": DEFAULT_CALIBRATION_ICE_MODE,
            "target_ers_mode": DEFAULT_CALIBRATION_PHYSICS_ERS_MODE,
        },
    }


def _normalize_team_identifier(team_name: str) -> str:
    team_key = team_name.strip().lower().replace("-", "_").replace(" ", "_")
    alias_map = {
        "mclaren_f1_team": "mclaren",
        "scuderia_ferrari": "ferrari",
        "oracle_red_bull_racing": "red_bull",
        "mercedes_amg_petronas": "mercedes",
        "bwt_alpine_f1_team": "alpine",
        "williams_racing": "williams",
        "visa_cash_app_rb": "rb",
        "stake_f1_team_kick_sauber": "sauber",
        "moneygram_haas_f1_team": "haas",
        "aston_martin_aramco": "aston_martin",
    }
    return alias_map.get(team_key, team_key)


def _resolve_team(loader: TeamDriverLoader, spec: InitialCalibrationSpec) -> TeamData:
    candidate_ids = []
    normalized = _normalize_team_identifier(spec.team_name)
    if normalized:
        candidate_ids.append(normalized)

    if normalized.endswith("_f1_team"):
        candidate_ids.append(normalized.removesuffix("_f1_team"))

    for token, resolved in (
        ("ferrari", "ferrari"),
        ("mercedes", "mercedes"),
        ("mclaren", "mclaren"),
        ("red_bull", "red_bull"),
        ("aston_martin", "aston_martin"),
        ("alpine", "alpine"),
        ("williams", "williams"),
        ("sauber", "sauber"),
        ("haas", "haas"),
        ("rb", "rb"),
    ):
        if token in normalized:
            candidate_ids.append(resolved)

    candidate_ids = list(dict.fromkeys(candidate_ids))
    for candidate_id in candidate_ids:
        team = loader.get_team(candidate_id)
        if team is not None:
            return team

    team = loader.get_team_by_driver(spec.driver_name)
    if team is not None:
        return team

    raise ValueError(
        f"Unable to resolve a team for benchmark calibration: {spec.team_name!r} / driver {spec.driver_name!r}"
    )


def build_initial_calibration_setup(
    spec: Optional[InitialCalibrationSpec] = None,
) -> InitialCalibrationSetup:
    """Costruisce il setup di riferimento McLaren/Norris per la calibrazione iniziale."""
    benchmark = spec or InitialCalibrationSpec()
    loader = TeamDriverLoader()

    team = _resolve_team(loader, benchmark)
    driver = loader.get_driver(benchmark.driver_name)
    if driver is None:
        raise ValueError(f"Unable to resolve driver for benchmark calibration: {benchmark.driver_name!r}")

    physics_setup = PhysicsV4Setup(
        team_data=team,
        driver_data=driver,
        circuit=benchmark.circuit_id,
        session=benchmark.session,
    )

    reference_defaults = DefaultSetups().get_default_setup(
        benchmark.circuit_id,
        weather=benchmark.weather,
        tire_compound=benchmark.tyre_compound,
    )

    physics_setup.set_aero(
        front_wing=reference_defaults["front_wing"],
        rear_wing=reference_defaults["rear_wing"],
    )
    physics_setup.set_suspension(
        spring_front=reference_defaults["front_suspension"],
        spring_rear=reference_defaults["rear_suspension"],
        ARB_front=reference_defaults["front_arb"],
        ARB_rear=reference_defaults["rear_arb"],
        ride_height_front=reference_defaults["ride_height"],
        ride_height_rear=reference_defaults["ride_height"],
    )
    physics_setup.set_brakes(bias_front=reference_defaults["brake_bias"])
    
    # Use soft compound from telemetry (correct per circuito)
    soft_compound = _get_soft_compound_from_telemetry(benchmark.circuit_id)
    physics_setup.set_tyres(compound=soft_compound)
    physics_setup.set_ers_mode("quali_deploy")

    return InitialCalibrationSetup(
        spec=benchmark,
        physics_setup=physics_setup,
        reference_setup=reference_defaults,
        team=team,
        driver=driver,
        benchmark_context=_build_benchmark_context(physics_setup),
    )


def run_initial_calibration_benchmark(
    spec: Optional[InitialCalibrationSpec] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Esegue il benchmark iniziale McLaren/Norris e ritorna la telemetria del giro."""
    setup = build_initial_calibration_setup(spec)
    result = setup.physics_setup.simulate_lap(verbose=verbose)
    
    # Build result with actual tyre compound used (from telemetry, not spec default)
    spec_dict = dict(asdict(setup.spec))
    spec_dict["tyre_compound"] = setup.physics_setup.car.tyres.compound  # Override with actual
    
    result["initial_calibration"] = {
        **spec_dict,
        "resolved_team_id": setup.team.team_id,
        "resolved_team_name": setup.team.name,
        "resolved_driver_name": setup.driver.name,
        "driver_skill": asdict(setup.driver),
        "team_data": asdict(setup.team),
        "reference_setup": dict(setup.reference_setup),
        "benchmark_context": dict(setup.benchmark_context),
        "car_configuration": asdict(setup.physics_setup.car),
        "setup_base": dict(result.get("setup_base", {})),
        "setup_applied": dict(result.get("setup", {})),
    }
    return result


__all__ = [
    "DEFAULT_CALIBRATION_CIRCUIT_ID",
    "DEFAULT_CALIBRATION_TEAM_NAME",
    "DEFAULT_CALIBRATION_DRIVER_NAME",
    "DEFAULT_CALIBRATION_SESSION",
    "DEFAULT_CALIBRATION_WEATHER",
    "DEFAULT_CALIBRATION_TYRE_COMPOUND",
    "DEFAULT_CALIBRATION_MICROSECTOR_MARGIN_PCT",
    "InitialCalibrationSpec",
    "InitialCalibrationSetup",
    "build_initial_calibration_setup",
    "run_initial_calibration_benchmark",
]
