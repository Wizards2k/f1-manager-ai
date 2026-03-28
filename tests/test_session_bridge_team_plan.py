"""Integration test validating SessionBridge TeamSessionPlan scheduling."""

import os
import random
import sys
from pathlib import Path

import pytest


TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
PYTHON_BACKEND_ROOT = PROJECT_ROOT / "python_backend"
REPO_ROOT = PROJECT_ROOT

for path in (PROJECT_ROOT, PYTHON_BACKEND_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from data.teams import TEAMS
from models import RaceCar
from utils.session_bridge import SessionBridge


CIRCUIT_ID = "jp-1962_suzuka"


def _team_pilots(team):
    pilots = []
    if getattr(team, "pilota1", None):
        pilots.append(team.pilota1)
    if getattr(team, "pilota2", None):
        pilots.append(team.pilota2)
    if not pilots and hasattr(team, "piloti_titolari"):
        pilots.extend(team.piloti_titolari)
    return pilots


def _build_race_cars(max_teams: int = 4) -> list:
    cars = []
    for team in TEAMS[:max_teams]:
        for pilot in _team_pilots(team):
            cars.append(RaceCar(pilot=pilot, team=team))
    return cars


@pytest.mark.slow
def test_session_bridge_fp2_team_plan(tmp_path: Path):
    """Simulate an FP2 session and ensure every AI car attempts runs."""
    random.seed(1234)

    cars = _build_race_cars(max_teams=4)  # 4 teams → 8 cars for manageable runtime
    bridge = SessionBridge()

    assert bridge.init_session(CIRCUIT_ID, cars, session_type="FP2"), "Failed to init SessionBridge"

    # Shorten session duration for the test (30 minutes)
    bridge.pso.clock.duration_s = 1800

    max_ticks = 2200  # 2200s simulated time cap
    for _ in range(max_ticks):
        if bridge.is_finished:
            break
        bridge.tick(1.0)
    else:
        pytest.fail("Practice session did not finish in allotted time")

    report_lines = [
        "# Practice Session Report",
        "| Team | Driver | Planned | Completed | Best Lap (s) | Converged | Programs |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]

    for car_id, engine in bridge.ai_engines.items():
        summary = engine.session_summary()
        planned = summary["runs_planned"]
        completed = summary["runs_completed"]
        assert completed >= 1, f"{car_id} did not attempt any runs"

        programs = ", ".join(run.program.value for run in engine.session_plan.runs) if engine.session_plan else ""
        report_lines.append(
            "| {team} | {driver} | {planned} | {completed} | {best:.1f} | {conv} | {programs} |".format(
                team=engine.team_config.team_id,
                driver=engine.driver_config.driver_id,
                planned=planned,
                completed=completed,
                best=summary["best_lap_s"],
                conv="yes" if summary["setup_converged"] else "no",
                programs=programs,
            )
        )

    # Write to pytest tmp path (for artifacts) and repo tmp/ for manual inspection
    tmp_report = tmp_path / "practice_session_report.md"
    tmp_report.write_text("\n".join(report_lines), encoding="utf-8")
    assert tmp_report.exists()

    repo_tmp_dir = REPO_ROOT / "tmp"
    repo_tmp_dir.mkdir(parents=True, exist_ok=True)
    repo_report = repo_tmp_dir / "practice_session_report.md"
    repo_report.write_text("\n".join(report_lines), encoding="utf-8")
    assert repo_report.exists()
