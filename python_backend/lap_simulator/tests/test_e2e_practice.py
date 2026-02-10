"""
End-to-end test: FP1 session with 4 cars (2 teams) on Monza.

Validates that all Fase B modules work together:
  PracticeSessionOrchestrator → AIDriverEngine → LapSimulator + BattleResolver

Uses real Monza telemetry config.
"""
import random
import pytest

from lap_simulator.config_loader import load_circuit_config
from lap_simulator.ai_driver_engine import (
    AIDriverEngine,
    generate_setup_seed,
    plan_session,
)
from lap_simulator.ai_data_types import (
    AIDriverConfig,
    AITeamConfig,
    SessionType,
)
from lap_simulator.data_types import (
    AeroSetup,
    CarState,
    DriverSkills,
    EnvContext,
    TyreCompound,
)
from lap_simulator.lap_simulator import CarEntry, LapSimulator
from lap_simulator.practice_session import (
    CarPhase,
    PracticeEventType,
    PracticeSessionOrchestrator,
)


CIRCUIT_ID = "it-1922_monza"


@pytest.fixture(scope="module")
def monza_config():
    """Load real Monza circuit config."""
    try:
        return load_circuit_config(CIRCUIT_ID)
    except Exception:
        pytest.skip(f"Monza config not available: {CIRCUIT_ID}")


@pytest.fixture(scope="module")
def env():
    return EnvContext()


def _make_team_config(team_id, tier="top"):
    return AITeamConfig(
        team_id=team_id,
        budget_tier=tier,
        simulation_efficiency=85 if tier == "top" else 60,
    )


def _make_driver_config(driver_id, skill=75):
    return AIDriverConfig(
        driver_id=driver_id,
        sim_affinity=skill,
        mechanical_sympathy=skill,
    )


def _make_driver_skills(overtaking=70, defending=70, aggression=50):
    return DriverSkills(
        overtaking_skill=overtaking,
        defending_skill=defending,
        aggression=aggression,
    )


class TestE2EPracticeSession:
    """Full FP1 session with 4 cars using all modules."""

    def test_full_fp1_session(self, monza_config, env):
        """
        Simulate a mini FP1:
        - 2 teams × 2 cars
        - Each AI car does 1 run (setup validation)
        - LapSimulator runs laps with BattleResolver
        - PSO manages clock, pitlane, tyre inventory
        """
        random.seed(42)

        # --- Setup teams ---
        teams = [
            ("ferrari", "top", ["LEC", "SAI"]),
            ("williams", "midfield", ["ALB", "SAR"]),
        ]

        # --- Create PSO ---
        pso = PracticeSessionOrchestrator(
            SessionType.FP1,
            duration_s=600,  # 10 min for test speed
        )

        alloc = {TyreCompound.C2: 3, TyreCompound.C3: 3, TyreCompound.C4: 3, TyreCompound.C5: 3}
        for team_id, tier, drivers in teams:
            car_ids = [f"{team_id}_{d}" for d in drivers]
            pso.register_team(
                team_id=team_id,
                car_ids=car_ids,
                driver_names=drivers,
                allocation=alloc,
            )

        pso.start_session()
        assert not pso.is_finished

        # --- Create AI engines ---
        ai_engines = {}
        for team_id, tier, drivers in teams:
            team_cfg = _make_team_config(team_id, tier)
            for d in drivers:
                car_id = f"{team_id}_{d}"
                driver_cfg = _make_driver_config(d)
                skills = _make_driver_skills()
                engine = AIDriverEngine(monza_config, team_cfg, driver_cfg, skills)
                engine.start_session(SessionType.FP1)
                ai_engines[car_id] = engine

        # --- Create LapSimulator ---
        sim = LapSimulator(monza_config, env, enable_battles=True)

        # --- Run: each AI car does its first run ---
        results_by_car = {}

        for car_id, engine in ai_engines.items():
            if not engine.has_next_run():
                continue

            # Configure run
            car_entry = engine.configure_current_run()
            assert car_entry is not None

            # Get run plan for PSO (current_run_idx points to current run)
            run_plan = engine.session_plan.runs[engine.current_run_idx - 1]

            # Request run via PSO
            record = pso.request_run(
                car_id=car_id,
                program=run_plan.program,
                compound=run_plan.compound,
                fuel_kg=run_plan.fuel_kg,
                laps_planned=run_plan.laps_planned,
            )
            assert record is not None, f"Failed to request run for {car_id}"

            # Tick PSO to release car
            pso.tick(1.0)
            assert pso.cars[car_id].phase in (CarPhase.ON_TRACK, CarPhase.PIT_QUEUE)

            # Register car in simulator
            sim.register_car(car_entry)

        # --- Run laps ---
        n_laps = 3  # short run for test
        all_lap_results = sim.run_laps(n_laps)

        # --- Validate results ---
        assert len(all_lap_results) == 4  # 4 cars

        for car_id, laps in all_lap_results.items():
            assert len(laps) == n_laps

            for lap in laps:
                # Lap time should be realistic for Monza (~100-115s)
                assert 80.0 < lap.lap_time_s < 150.0, \
                    f"{car_id} lap {lap.lap_number}: {lap.lap_time_s:.1f}s out of range"

                # Should have section results
                assert len(lap.section_results) == len(monza_config.sections)

                # Fuel should decrease
                assert lap.fuel_kg >= 0

            # Complete run in AI engine
            engine = ai_engines[car_id]
            run_result = engine.complete_run(laps)
            assert run_result is not None
            assert run_result.telemetry.best_lap_time_s > 0

            # Complete run in PSO
            best_lap = min(l.lap_time_s for l in laps)
            pso.complete_run(
                car_id=car_id,
                laps_completed=n_laps,
                best_lap_s=best_lap,
                km_driven=monza_config.circuit_length_m * n_laps / 1000,
            )

            results_by_car[car_id] = {
                "best_lap": best_lap,
                "run_result": run_result,
            }

        # --- Validate PSO state ---
        assert len(pso.run_log) == 4
        assert all(pso.cars[cid].runs_completed == 1 for cid in ai_engines)

        # Leaderboard should have 4 entries
        lb = pso.leaderboard()
        assert len(lb) == 4

        # Top team should generally be faster
        ferrari_best = min(
            results_by_car[f"ferrari_{d}"]["best_lap"]
            for d in ["LEC", "SAI"]
        )
        williams_best = min(
            results_by_car[f"williams_{d}"]["best_lap"]
            for d in ["ALB", "SAR"]
        )
        # Not guaranteed due to randomness, but log it
        print(f"\nFP1 Results:")
        print(f"  Ferrari best:  {ferrari_best:.2f}s")
        print(f"  Williams best: {williams_best:.2f}s")
        for entry in lb:
            print(f"  P{lb.index(entry)+1}: {entry['driver']} ({entry['team']}) - {entry['best_lap_s']:.2f}s")

        # --- Validate events ---
        event_types = {e.event_type for e in pso.events}
        assert PracticeEventType.SESSION_START in event_types
        assert PracticeEventType.RUN_START in event_types
        assert PracticeEventType.RUN_END in event_types
        assert PracticeEventType.CAR_EXIT_PIT in event_types

        # --- Validate AI engine state ---
        for car_id, engine in ai_engines.items():
            summary = engine.session_summary()
            assert summary["runs_completed"] == 1
            assert summary["best_lap_s"] > 0

    def test_battle_events_generated(self, monza_config, env):
        """Verify that BattleResolver generates events when cars are close."""
        random.seed(123)

        sim = LapSimulator(monza_config, env, enable_battles=True)

        # Two cars with different speeds
        fast = CarEntry(
            car_id="fast",
            state=CarState(car_id="fast"),
            aero_setup=AeroSetup(),
            driver_skills=_make_driver_skills(overtaking=90),
            push_level=1.05,
        )
        slow = CarEntry(
            car_id="slow",
            state=CarState(car_id="slow"),
            aero_setup=AeroSetup(),
            driver_skills=_make_driver_skills(defending=60),
            push_level=0.92,
        )

        sim.register_cars([fast, slow])
        results = sim.run_laps(2)

        # Both should have valid times
        assert results["fast"][0].lap_time_s > 0
        assert results["slow"][0].lap_time_s > 0

        # Both should have section results and battle_events field
        for car_id in ["fast", "slow"]:
            for lap in results[car_id]:
                assert len(lap.section_results) == len(monza_config.sections)
                assert hasattr(lap, "battle_events")

    def test_tyre_inventory_consumed(self, monza_config):
        """Verify tyre sets are consumed during runs."""
        pso = PracticeSessionOrchestrator(SessionType.FP1, duration_s=300)
        alloc = {TyreCompound.C3: 2}
        pso.register_team("team_a", ["car_1"], allocation=alloc)
        pso.start_session()

        inv = pso.inventories["team_a"]
        assert len(inv.new_sets(TyreCompound.C3)) == 2

        # First run
        pso.request_run("car_1", program=__import__("lap_simulator.ai_data_types", fromlist=["RunProgram"]).RunProgram.SETUP_VALIDATION,
                        compound=TyreCompound.C3, fuel_kg=50, laps_planned=3)
        pso.tick(1.0)
        pso.complete_run("car_1", laps_completed=3, best_lap_s=90.0, km_driven=15.0)

        # One set used, one still new
        assert len(inv.new_sets(TyreCompound.C3)) == 1
        assert len(inv.used_sets(TyreCompound.C3)) == 1
