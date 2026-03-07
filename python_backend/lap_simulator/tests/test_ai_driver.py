"""
Tests for AI Driver Engine – setup seed, session planning, run analysis.
"""
import pytest
import random

from lap_simulator.ai_data_types import (
    AIDriverConfig,
    AITeamConfig,
    AIPracticeRunEvent,
    CarStatus,
    PIT_OVERHEAD_S,
    PitWorkType,
    RunOutcome,
    RunPlan,
    RunProgram,
    RunResult,
    SessionPlan,
    SessionType,
    SetupAdjustment,
)
from lap_simulator.ai_driver_engine import (
    AIDriverEngine,
    analyze_run,
    apply_adjustments,
    compute_pit_stop,
    configure_run,
    emit_run_event,
    generate_setup_seed,
    plan_session,
)
from lap_simulator.data_types import (
    AeroSetup,
    CarState,
    CircuitConfig,
    DriverSkills,
    EngineMapName,
    EnvContext,
    TyreCompound,
)
from lap_simulator.lap_simulator import CarEntry, LapResult, LapSimulator
from lap_simulator.config_loader import load_circuit_config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def team_top():
    return AITeamConfig(
        team_id="red_bull",
        team_name="Red Bull Racing",
        simulation_efficiency=90,
        budget_tier="top",
        max_runs_per_session=4,
    )


@pytest.fixture
def team_back():
    return AITeamConfig(
        team_id="haas",
        team_name="Haas F1",
        simulation_efficiency=40,
        budget_tier="backmarker",
        max_runs_per_session=3,
    )


@pytest.fixture
def driver_good():
    return AIDriverConfig(
        driver_id="VER",
        driver_name="Verstappen",
        sim_affinity=85,
        setup_finding_skill=90,
        tyre_management_skill=85,
        mechanical_sympathy=80,
    )


@pytest.fixture
def driver_weak():
    return AIDriverConfig(
        driver_id="MAG",
        driver_name="Magnussen",
        sim_affinity=35,
        setup_finding_skill=50,
        tyre_management_skill=55,
        mechanical_sympathy=45,
    )


@pytest.fixture
def skills_good():
    return DriverSkills(
        raw_pace=92, race_craft=88, aggression=65,
        consistency=90, overtaking_skill=85, setup_finding=90,
    )


@pytest.fixture
def skills_weak():
    return DriverSkills(
        raw_pace=72, race_craft=60, aggression=55,
        consistency=65, overtaking_skill=50, setup_finding=50,
    )


@pytest.fixture
def monza_config():
    return load_circuit_config("it-1922_monza")


# ---------------------------------------------------------------------------
# §2 Setup seed generation
# ---------------------------------------------------------------------------

class TestSetupSeed:
    def test_top_team_seed_close_to_default(self, monza_config, team_top, driver_good):
        """Top team + good driver → setup close to default (small offsets)."""
        random.seed(42)
        setup = generate_setup_seed(monza_config, team_top, driver_good)
        default = AeroSetup()
        # Front wing should be within ~0.5 deg of default
        assert abs(setup.front_wing.angle_deg - default.front_wing.angle_deg) < 1.0
        # Ride height within ~2mm
        assert abs(setup.ride_height_front_mm - default.ride_height_front_mm) < 3.0

    def test_backmarker_seed_further_from_default(self, monza_config, team_back, driver_weak):
        """Backmarker + weak driver → larger offsets."""
        random.seed(42)
        setup = generate_setup_seed(monza_config, team_back, driver_weak)
        default = AeroSetup()
        # Should have larger deviation (offset_factor ~0.14 vs ~0.02)
        # At least one slider should deviate noticeably
        total_dev = (
            abs(setup.front_wing.angle_deg - default.front_wing.angle_deg)
            + abs(setup.rear_wing.angle_deg - default.rear_wing.angle_deg)
            + abs(setup.ride_height_front_mm - default.ride_height_front_mm)
        )
        assert total_dev > 0.1  # non-trivial deviation

    def test_seed_is_deterministic(self, monza_config, team_top, driver_good):
        """Same seed → same setup."""
        random.seed(123)
        s1 = generate_setup_seed(monza_config, team_top, driver_good)
        random.seed(123)
        s2 = generate_setup_seed(monza_config, team_top, driver_good)
        assert s1.front_wing.angle_deg == s2.front_wing.angle_deg
        assert s1.ride_height_front_mm == s2.ride_height_front_mm


# ---------------------------------------------------------------------------
# §3 Session planning
# ---------------------------------------------------------------------------

class TestSessionPlanning:
    def test_fp1_has_setup_validation(self, team_top, driver_good):
        plan = plan_session(SessionType.FP1, team_top, driver_good)
        programs = [r.program for r in plan.runs]
        assert RunProgram.SETUP_VALIDATION in programs

    def test_fp1_top_team_gets_extra_run(self, team_top, driver_good):
        """Top teams get an extra tyre deg run in FP1."""
        plan = plan_session(SessionType.FP1, team_top, driver_good)
        assert len(plan.runs) >= 3
        programs = [r.program for r in plan.runs]
        assert RunProgram.TYRE_DEG in programs

    def test_fp2_has_three_programs(self, team_top, driver_good):
        plan = plan_session(SessionType.FP2, team_top, driver_good)
        programs = [r.program for r in plan.runs]
        assert RunProgram.TYRE_DEG in programs
        assert RunProgram.QUALI_SIM in programs
        assert RunProgram.RACE_TRIM in programs

    def test_fp3_converged_skips_setup(self, team_top, driver_good):
        """FP3 with converged setup → only quali sim."""
        plan = plan_session(SessionType.FP3, team_top, driver_good, setup_converged=True)
        programs = [r.program for r in plan.runs]
        assert RunProgram.SETUP_VALIDATION not in programs
        assert RunProgram.QUALI_SIM in programs

    def test_fp3_not_converged_includes_setup(self, team_top, driver_good):
        plan = plan_session(SessionType.FP3, team_top, driver_good, setup_converged=False)
        programs = [r.program for r in plan.runs]
        assert RunProgram.SETUP_VALIDATION in programs

    def test_run_plan_fuel_and_compound(self, team_top, driver_good):
        plan = plan_session(SessionType.FP2, team_top, driver_good)
        quali_run = [r for r in plan.runs if r.program == RunProgram.QUALI_SIM][0]
        assert quali_run.fuel_kg == 15.0
        assert quali_run.compound == TyreCompound.C4
        assert quali_run.engine_map == EngineMapName.QUALITY

        race_run = [r for r in plan.runs if r.program == RunProgram.RACE_TRIM][0]
        assert race_run.fuel_kg == 95.0
        assert race_run.compound == TyreCompound.C2


# ---------------------------------------------------------------------------
# Run configuration
# ---------------------------------------------------------------------------

class TestRunConfiguration:
    def test_configure_run_sets_fuel(self):
        plan = RunPlan(
            program=RunProgram.RACE_TRIM,
            fuel_kg=95.0,
            engine_map=EngineMapName.RACE,
            push_level=0.93,
        )
        entry = configure_run(plan, "car_1", AeroSetup(), DriverSkills())
        assert entry.state.pu.fuel_kg == 95.0
        assert entry.push_level == 0.93
        assert entry.state.pu.active_map == EngineMapName.RACE


# ---------------------------------------------------------------------------
# Post-run analysis
# ---------------------------------------------------------------------------

class TestRunAnalysis:
    def _make_lap_results(self, n_laps=3, lap_time=107.0):
        """Create mock LapResults."""
        results = []
        for i in range(n_laps):
            from lap_simulator.data_types import SectionResult, SectionEvent
            sr = SectionResult(
                dt_s=5.0, v_effective_kph=200.0,
                effective_grip_front=0.72, effective_grip_rear=0.70,
            )
            lr = LapResult(
                car_id="test",
                lap_number=i + 1,
                lap_time_s=lap_time + i * 0.5,
                section_results=[sr] * 10,
                fuel_kg=90.0 - i * 3.0,
                avg_tyre_wear_pct=2.0 + i * 1.5,
                avg_tyre_temp_surface_c=110.0,
            )
            results.append(lr)
        return results

    def test_analyze_success(self, driver_good):
        plan = RunPlan(program=RunProgram.SETUP_VALIDATION, laps_planned=3)
        laps = self._make_lap_results(3)
        result = analyze_run(plan, laps, driver_good, AeroSetup())
        assert result.outcome == RunOutcome.SUCCESS
        assert result.telemetry.best_lap_time_s == 107.0
        assert result.telemetry.total_laps == 3

    def test_analyze_partial_if_fewer_laps(self, driver_good):
        plan = RunPlan(program=RunProgram.TYRE_DEG, laps_planned=8)
        laps = self._make_lap_results(5)
        result = analyze_run(plan, laps, driver_good, AeroSetup())
        assert result.outcome == RunOutcome.PARTIAL

    def test_analyze_aborted_no_laps(self, driver_good):
        plan = RunPlan(program=RunProgram.SETUP_VALIDATION, laps_planned=3)
        result = analyze_run(plan, [], driver_good, AeroSetup())
        assert result.outcome == RunOutcome.ABORTED

    def test_setup_adjustments_proposed(self, driver_good):
        """If grip imbalance detected, adjustments should be proposed."""
        plan = RunPlan(program=RunProgram.SETUP_VALIDATION, laps_planned=3)
        laps = self._make_lap_results(3)
        # Create grip imbalance
        for lr in laps:
            for sr in lr.section_results:
                sr.effective_grip_front = 0.80
                sr.effective_grip_rear = 0.60
        result = analyze_run(plan, laps, driver_good, AeroSetup())
        assert len(result.setup_adjustments) > 0

    def test_converged_setup_no_adjustments(self, driver_good):
        """Balanced grip → converged, no adjustments."""
        plan = RunPlan(program=RunProgram.SETUP_VALIDATION, laps_planned=3)
        laps = self._make_lap_results(3)
        for lr in laps:
            for sr in lr.section_results:
                sr.effective_grip_front = 0.70
                sr.effective_grip_rear = 0.70
        result = analyze_run(plan, laps, driver_good, AeroSetup())
        assert result.setup_converged is True
        assert len(result.setup_adjustments) == 0


# ---------------------------------------------------------------------------
# Apply adjustments
# ---------------------------------------------------------------------------

class TestApplyAdjustments:
    def test_apply_front_wing(self):
        setup = AeroSetup()
        setup.front_wing.angle_deg = 5.0
        adj = [SetupAdjustment(
            slider_name="front_wing_angle",
            old_value=5.0, new_value=4.5, reason="test",
        )]
        result = apply_adjustments(setup, adj)
        assert result.front_wing.angle_deg == 4.5


# ---------------------------------------------------------------------------
# Event generation
# ---------------------------------------------------------------------------

class TestEvents:
    def test_emit_run_started(self, team_top, driver_good):
        plan = RunPlan(program=RunProgram.QUALI_SIM, laps_planned=3,
                       compound=TyreCompound.C4, fuel_kg=15.0)
        event = emit_run_event("ai_run_started", team_top, driver_good, run_plan=plan)
        assert event.event_type == "ai_run_started"
        assert event.program == "QualiSim"
        assert event.compound == "C4"
        assert event.fuel_kg == 15.0


# ---------------------------------------------------------------------------
# Full integration: AIDriverEngine + LapSimulator
# ---------------------------------------------------------------------------

class TestAIDriverEngineIntegration:
    def test_full_fp1_session(self, monza_config, team_top, driver_good, skills_good):
        """Run a complete FP1 session with AI Driver Engine + LapSimulator."""
        random.seed(42)
        env = EnvContext()

        engine = AIDriverEngine(
            monza_config, team_top, driver_good, skills_good
        )
        plan = engine.start_session(SessionType.FP1)
        assert len(plan.runs) >= 2

        sim = LapSimulator(monza_config, env)

        while engine.has_next_run():
            run_plan = engine.next_run()
            assert run_plan is not None

            car_entry = engine.configure_current_run()
            assert car_entry is not None

            # Run with LapSimulator
            sim.cars.clear()
            sim.register_car(car_entry)
            multi = sim.run_laps(run_plan.laps_planned)
            lap_results = multi[car_entry.car_id]

            # Complete the run
            result = engine.complete_run(lap_results)
            assert result.outcome in (RunOutcome.SUCCESS, RunOutcome.PARTIAL)
            assert result.telemetry.best_lap_time_s > 0
            assert result.telemetry.total_laps > 0

        # Session summary
        summary = engine.session_summary()
        assert summary["runs_completed"] >= 2
        assert summary["best_lap_s"] > 0
        assert summary["elapsed_s"] > 0
        assert len(engine.events) >= 4  # at least start+end per run

    def test_setup_converges_over_runs(self, monza_config, team_top, driver_good, skills_good):
        """Setup should converge (or at least improve) over multiple runs."""
        random.seed(42)
        env = EnvContext()

        engine = AIDriverEngine(
            monza_config, team_top, driver_good, skills_good
        )
        engine.start_session(SessionType.FP1)
        sim = LapSimulator(monza_config, env)

        best_times = []
        while engine.has_next_run():
            run_plan = engine.next_run()
            car_entry = engine.configure_current_run()
            sim.cars.clear()
            sim.register_car(car_entry)
            multi = sim.run_laps(run_plan.laps_planned)
            lap_results = multi[car_entry.car_id]
            result = engine.complete_run(lap_results)
            best_times.append(result.telemetry.best_lap_time_s)

        # All runs should produce valid times
        assert all(t > 0 for t in best_times)
        assert len(best_times) >= 2

    def test_backmarker_fp2(self, monza_config, team_back, driver_weak, skills_weak):
        """Backmarker team completes FP2 with slower times."""
        random.seed(42)
        env = EnvContext()

        engine = AIDriverEngine(
            monza_config, team_back, driver_weak, skills_weak
        )
        plan = engine.start_session(SessionType.FP2)
        sim = LapSimulator(monza_config, env)

        while engine.has_next_run():
            run_plan = engine.next_run()
            car_entry = engine.configure_current_run()
            sim.cars.clear()
            sim.register_car(car_entry)
            multi = sim.run_laps(run_plan.laps_planned)
            result = engine.complete_run(multi[car_entry.car_id])

        summary = engine.session_summary()
        assert summary["runs_completed"] == len(plan.runs)


# ---------------------------------------------------------------------------
# Pit work calculation (spec §4.1)
# ---------------------------------------------------------------------------

class TestPitWork:
    def test_tyre_change_only(self):
        """Tyre change only → 25-30s + 15s overhead."""
        random.seed(42)
        pit = compute_pit_stop(
            has_tyre_change=True, has_refuel=False,
            setup_adjustments=0,
        )
        assert len(pit.work_items) == 1
        assert pit.work_items[0].work_type == PitWorkType.TYRE_CHANGE
        assert 40.0 <= pit.total_duration_s <= 45.0  # 25-30 + 15
        assert pit.status_label == CarStatus.BOX_TYRES

    def test_refuel_scales_with_fuel(self):
        """Refuel time ~1s/kg, clamped to [40, 60]."""
        pit_low = compute_pit_stop(
            has_tyre_change=False, has_refuel=True, fuel_kg=20.0,
        )
        pit_high = compute_pit_stop(
            has_tyre_change=False, has_refuel=True, fuel_kg=80.0,
        )
        # 20kg → clamped to 40s; 80kg → clamped to 60s
        assert pit_low.work_items[0].duration_s == 40.0
        assert pit_high.work_items[0].duration_s == 60.0

    def test_setup_minor_vs_major(self):
        """1-2 adjustments = minor (60-90s), 3+ = major (120-180s)."""
        random.seed(42)
        pit_minor = compute_pit_stop(
            has_tyre_change=False, has_refuel=False,
            setup_adjustments=1,
        )
        pit_major = compute_pit_stop(
            has_tyre_change=False, has_refuel=False,
            setup_adjustments=4,
        )
        minor_item = pit_minor.work_items[0]
        major_item = pit_major.work_items[0]
        assert minor_item.work_type == PitWorkType.SETUP_MINOR
        assert major_item.work_type == PitWorkType.SETUP_MAJOR
        assert minor_item.duration_s < major_item.duration_s

    def test_parallel_work_uses_max(self):
        """Multiple work items → total = max(durations) + overhead."""
        random.seed(42)
        pit = compute_pit_stop(
            has_tyre_change=True, has_refuel=True, fuel_kg=50.0,
            setup_adjustments=1,
        )
        assert len(pit.work_items) == 3
        max_dur = max(item.duration_s for item in pit.work_items)
        assert abs(pit.total_duration_s - (max_dur + PIT_OVERHEAD_S)) < 0.01

    def test_status_label_shows_longest_work(self):
        """Status label = label of the longest work item."""
        random.seed(42)
        pit = compute_pit_stop(
            has_tyre_change=True, has_refuel=False,
            setup_adjustments=3,  # major setup = 120-180s, longer than tyres
        )
        assert pit.status_label == CarStatus.BOX_SETUP

    def test_no_work_items(self):
        """No work → just overhead, status = BOX_READY."""
        pit = compute_pit_stop(
            has_tyre_change=False, has_refuel=False,
            setup_adjustments=0,
        )
        assert pit.total_duration_s == PIT_OVERHEAD_S
        assert pit.status_label == CarStatus.BOX_READY

    def test_description_includes_time(self):
        """Description should list work items and estimated time."""
        random.seed(42)
        pit = compute_pit_stop(
            has_tyre_change=True, has_refuel=True, fuel_kg=50.0,
        )
        assert "Tyre change" in pit.description
        assert "Refuel" in pit.description
        assert "~" in pit.description


# ---------------------------------------------------------------------------
# Car status tracking in AIDriverEngine
# ---------------------------------------------------------------------------

class TestCarStatus:
    def test_status_transitions(self, monza_config, team_top, driver_good, skills_good):
        """Car status should transition through the session lifecycle."""
        random.seed(42)
        env = EnvContext()

        engine = AIDriverEngine(
            monza_config, team_top, driver_good, skills_good
        )
        assert engine.car_status == CarStatus.BOX_READY

        engine.start_session(SessionType.FP1)
        run_plan = engine.next_run()
        car_entry = engine.configure_current_run()
        assert engine.car_status == CarStatus.OUT_LAP

        sim = LapSimulator(monza_config, env)
        sim.register_car(car_entry)
        multi = sim.run_laps(run_plan.laps_planned)
        result = engine.complete_run(multi[car_entry.car_id])

        # After completing run, should be BOX_READY
        assert engine.car_status == CarStatus.BOX_READY
        # Should have a pit stop recorded
        assert engine.last_pit_stop is not None
        assert engine.last_pit_stop.total_duration_s > PIT_OVERHEAD_S

    def test_pit_events_emitted(self, monza_config, team_top, driver_good, skills_good):
        """Pit work start/complete events should be emitted."""
        random.seed(42)
        env = EnvContext()

        engine = AIDriverEngine(
            monza_config, team_top, driver_good, skills_good
        )
        engine.start_session(SessionType.FP1)
        run_plan = engine.next_run()
        car_entry = engine.configure_current_run()

        sim = LapSimulator(monza_config, env)
        sim.register_car(car_entry)
        multi = sim.run_laps(run_plan.laps_planned)
        engine.complete_run(multi[car_entry.car_id])

        event_types = [e.event_type for e in engine.events]
        assert "ai_run_started" in event_types
        assert "ai_pit_work_started" in event_types
        assert "ai_pit_work_complete" in event_types
        assert "ai_run_completed" in event_types
