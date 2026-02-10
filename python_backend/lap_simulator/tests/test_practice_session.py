"""
Tests for Practice Session Orchestrator.
"""
import pytest

from lap_simulator.practice_session import (
    CarPhase,
    PitlanePriority,
    PitlaneQueue,
    PracticeEventType,
    PracticeRunRecord,
    PracticeSessionOrchestrator,
    SessionClock,
    SessionFlag,
    TyreInventory,
    TyreSet,
    TyreSetStatus,
)
from lap_simulator.ai_data_types import RunOutcome, RunProgram, SessionType
from lap_simulator.data_types import TyreCompound


# ---------------------------------------------------------------------------
# TyreInventory
# ---------------------------------------------------------------------------

class TestTyreInventory:
    def test_default_allocation(self):
        inv = TyreInventory("team_a")
        # Should have sets for multiple compounds
        assert len(inv.sets) > 0
        all_compounds = {s.compound for s in inv.sets.values()}
        assert TyreCompound.C3 in all_compounds

    def test_custom_allocation(self):
        alloc = {TyreCompound.C4: 3, TyreCompound.C5: 5}
        inv = TyreInventory("team_a", allocation=alloc)
        assert len(inv.sets) == 8
        c4_sets = inv.available_sets(TyreCompound.C4)
        c5_sets = inv.available_sets(TyreCompound.C5)
        assert len(c4_sets) == 3
        assert len(c5_sets) == 5

    def test_checkout_returns_set(self):
        alloc = {TyreCompound.C3: 2}
        inv = TyreInventory("team_a", allocation=alloc)
        ts = inv.checkout("car_1", TyreCompound.C3)
        assert ts is not None
        assert ts.compound == TyreCompound.C3
        assert ts.current_car_id == "car_1"

    def test_checkout_prefers_new(self):
        alloc = {TyreCompound.C3: 2}
        inv = TyreInventory("team_a", allocation=alloc)
        # Use one set
        ts1 = inv.checkout("car_1", TyreCompound.C3)
        inv.checkin(ts1.set_id)
        # Next checkout should prefer the new one
        ts2 = inv.checkout("car_2", TyreCompound.C3, prefer_new=True)
        assert ts2.set_id != ts1.set_id
        assert ts2.status == TyreSetStatus.NEW

    def test_checkout_none_when_exhausted(self):
        alloc = {TyreCompound.C3: 1}
        inv = TyreInventory("team_a", allocation=alloc)
        ts = inv.checkout("car_1", TyreCompound.C3)
        assert ts is not None
        # Second checkout should fail (set is in use)
        ts2 = inv.checkout("car_2", TyreCompound.C3)
        assert ts2 is None

    def test_checkin_increments_heat_cycles(self):
        alloc = {TyreCompound.C3: 1}
        inv = TyreInventory("team_a", allocation=alloc)
        ts = inv.checkout("car_1", TyreCompound.C3)
        assert ts.heat_cycles == 0
        inv.checkin(ts.set_id, km_driven=5.0)
        assert ts.heat_cycles == 1
        assert ts.status == TyreSetStatus.USED
        assert ts.km_driven == 5.0
        assert ts.current_car_id is None

    def test_eol_after_threshold(self):
        alloc = {TyreCompound.C3: 1}
        inv = TyreInventory("team_a", allocation=alloc, eol_threshold=3)
        ts = inv.checkout("car_1", TyreCompound.C3)
        for i in range(3):
            inv.checkin(ts.set_id)
            if i < 2:
                ts.current_car_id = None  # simulate re-checkout
                ts = inv.checkout("car_1", TyreCompound.C3)
        assert ts.status == TyreSetStatus.END_OF_LIFE
        assert not ts.is_available

    def test_summary(self):
        alloc = {TyreCompound.C3: 3}
        inv = TyreInventory("team_a", allocation=alloc)
        inv.checkout("car_1", TyreCompound.C3)
        summary = inv.summary()
        assert "C3" in summary
        assert summary["C3"]["new"] == 2
        assert summary["C3"]["in_use"] == 1

    def test_new_and_used_sets(self):
        alloc = {TyreCompound.C3: 3}
        inv = TyreInventory("team_a", allocation=alloc)
        ts = inv.checkout("car_1", TyreCompound.C3)
        inv.checkin(ts.set_id)
        assert len(inv.new_sets(TyreCompound.C3)) == 2
        assert len(inv.used_sets(TyreCompound.C3)) == 1


# ---------------------------------------------------------------------------
# SessionClock
# ---------------------------------------------------------------------------

class TestSessionClock:
    def test_tick_advances_time(self):
        clock = SessionClock(duration_s=60)
        dt = clock.tick(1.0)
        assert dt == 1.0
        assert clock.elapsed_s == 1.0

    def test_fast_forward(self):
        clock = SessionClock(duration_s=60)
        clock.set_speed(4.0)
        dt = clock.tick(1.0)
        assert dt == 4.0
        assert clock.elapsed_s == 4.0

    def test_pause_stops_time(self):
        clock = SessionClock(duration_s=60)
        clock.pause()
        dt = clock.tick(1.0)
        assert dt == 0.0
        assert clock.elapsed_s == 0.0

    def test_resume_after_pause(self):
        clock = SessionClock(duration_s=60)
        clock.pause()
        clock.tick(1.0)
        clock.resume()
        dt = clock.tick(1.0)
        assert dt == 1.0

    def test_does_not_exceed_duration(self):
        clock = SessionClock(duration_s=10)
        clock.tick(15.0)
        assert clock.elapsed_s == 10.0
        assert clock.is_finished

    def test_remaining(self):
        clock = SessionClock(duration_s=60)
        clock.tick(25.0)
        assert clock.remaining_s == 35.0

    def test_speed_clamped(self):
        clock = SessionClock()
        clock.set_speed(10.0)
        assert clock.speed_multiplier == 6.0
        clock.set_speed(0.5)
        assert clock.speed_multiplier == 1.0

    def test_flag_changes(self):
        clock = SessionClock()
        assert clock.flag == SessionFlag.GREEN
        clock.set_flag(SessionFlag.RED)
        assert clock.flag == SessionFlag.RED


# ---------------------------------------------------------------------------
# PitlaneQueue
# ---------------------------------------------------------------------------

class TestPitlaneQueue:
    def test_request_and_release(self):
        pq = PitlaneQueue()
        req = pq.request_exit("car_1", "team_a", current_time_s=10.0)
        assert req.car_id == "car_1"
        released = pq.process_tick(10.0)
        assert len(released) == 1
        assert released[0].car_id == "car_1"

    def test_priority_ordering(self):
        pq = PitlaneQueue()
        pq.request_exit("ai_car", "team_a", current_time_s=10.0, priority=PitlanePriority.AI_STANDARD)
        pq.request_exit("player_car", "team_a", current_time_s=10.0, priority=PitlanePriority.PLAYER, is_player=True)
        released = pq.process_tick(10.0)
        # Player should be released first
        assert released[0].car_id == "player_car"

    def test_cooldown_enforced(self):
        pq = PitlaneQueue()
        pq.car_returned("car_1", current_time_s=10.0)
        req = pq.request_exit("car_1", "team_a", current_time_s=15.0)
        # Should be delayed until 10 + 120 = 130
        assert req.release_at_s >= 130.0

    def test_queue_delay(self):
        pq = PitlaneQueue()
        # Simulate one car already exiting
        pq.request_exit("car_1", "team_a", current_time_s=0.0)
        pq.process_tick(0.0)  # car_1 exits → active
        # Next car gets queue delay
        req = pq.request_exit("car_2", "team_b", current_time_s=0.0)
        assert req.release_at_s > 0.0  # delayed

    def test_is_car_queued(self):
        pq = PitlaneQueue()
        pq.request_exit("car_1", "team_a", current_time_s=100.0)
        assert pq.is_car_queued("car_1")
        assert not pq.is_car_queued("car_2")

    def test_max_slots(self):
        pq = PitlaneQueue()
        for i in range(6):
            pq.request_exit(f"car_{i}", "team_a", current_time_s=0.0)
        released = pq.process_tick(0.0)
        assert len(released) <= 4  # MAX_PITLANE_SLOTS


# ---------------------------------------------------------------------------
# PracticeSessionOrchestrator
# ---------------------------------------------------------------------------

class TestOrchestratorLifecycle:
    def test_register_team(self):
        orch = PracticeSessionOrchestrator(SessionType.FP1)
        orch.register_team("team_a", ["car_1", "car_2"], ["Driver A", "Driver B"])
        assert "car_1" in orch.cars
        assert "car_2" in orch.cars
        assert orch.cars["car_1"].driver_name == "Driver A"
        assert "team_a" in orch.inventories

    def test_start_session(self):
        orch = PracticeSessionOrchestrator(SessionType.FP1)
        orch.register_team("team_a", ["car_1"])
        orch.start_session()
        assert any(e.event_type == PracticeEventType.SESSION_START for e in orch.events)

    def test_session_finishes(self):
        orch = PracticeSessionOrchestrator(SessionType.FP1, duration_s=10)
        orch.register_team("team_a", ["car_1"])
        orch.start_session()
        for _ in range(15):
            orch.tick(1.0)
        assert orch.is_finished
        assert any(e.event_type == PracticeEventType.SESSION_END for e in orch.events)

    def test_tick_returns_events(self):
        orch = PracticeSessionOrchestrator(SessionType.FP1, duration_s=10)
        orch.register_team("team_a", ["car_1"])
        orch.start_session()
        events = orch.tick(1.0)
        assert isinstance(events, list)


class TestOrchestratorRuns:
    def _setup_orch(self, duration_s=3600):
        orch = PracticeSessionOrchestrator(SessionType.FP1, duration_s=duration_s)
        alloc = {TyreCompound.C3: 5, TyreCompound.C4: 3}
        orch.register_team("team_a", ["car_1", "car_2"],
                           ["Driver A", "Driver B"],
                           player_car_id="car_1",
                           allocation=alloc)
        orch.start_session()
        return orch

    def test_request_run(self):
        orch = self._setup_orch()
        record = orch.request_run("car_1", RunProgram.SETUP_VALIDATION,
                                  TyreCompound.C3, fuel_kg=50.0, laps_planned=3)
        assert record is not None
        assert orch.cars["car_1"].phase == CarPhase.PIT_QUEUE

    def test_run_exits_pit_on_tick(self):
        orch = self._setup_orch()
        orch.request_run("car_1", RunProgram.SETUP_VALIDATION,
                         TyreCompound.C3, fuel_kg=50.0, laps_planned=3)
        orch.tick(1.0)
        assert orch.cars["car_1"].phase == CarPhase.ON_TRACK

    def test_complete_run(self):
        orch = self._setup_orch()
        orch.request_run("car_1", RunProgram.SETUP_VALIDATION,
                         TyreCompound.C3, fuel_kg=50.0, laps_planned=3)
        orch.tick(1.0)  # exit pit
        record = orch.complete_run("car_1", laps_completed=3,
                                   best_lap_s=90.5, km_driven=15.0)
        assert record is not None
        assert record.outcome == RunOutcome.SUCCESS
        assert orch.cars["car_1"].best_lap_s == 90.5
        assert orch.cars["car_1"].runs_completed == 1

    def test_partial_run(self):
        orch = self._setup_orch()
        orch.request_run("car_1", RunProgram.TYRE_DEG,
                         TyreCompound.C3, fuel_kg=50.0, laps_planned=5)
        orch.tick(1.0)
        record = orch.complete_run("car_1", laps_completed=3, best_lap_s=91.0)
        assert record.outcome == RunOutcome.PARTIAL

    def test_no_tyres_blocks_run(self):
        orch = PracticeSessionOrchestrator(SessionType.FP1)
        alloc = {TyreCompound.C5: 1}
        orch.register_team("team_a", ["car_1"], allocation=alloc)
        orch.start_session()
        # First run takes the only set
        r1 = orch.request_run("car_1", RunProgram.QUALI_SIM,
                              TyreCompound.C5, fuel_kg=20.0, laps_planned=2)
        assert r1 is not None
        # Second run should fail (set in use)
        r2 = orch.request_run("car_1", RunProgram.QUALI_SIM,
                              TyreCompound.C5, fuel_kg=20.0, laps_planned=2)
        assert r2 is None

    def test_pit_work_delays_next_run(self):
        orch = self._setup_orch()
        orch.request_run("car_1", RunProgram.SETUP_VALIDATION,
                         TyreCompound.C3, fuel_kg=50.0, laps_planned=3)
        orch.tick(1.0)
        orch.complete_run("car_1", laps_completed=3, best_lap_s=90.0,
                          pit_work_duration_s=60.0)
        assert orch.cars["car_1"].phase == CarPhase.PIT_WORK
        # Can't start new run while in pit work
        assert not orch.car_can_run("car_1")
        # After pit work completes
        for _ in range(65):
            orch.tick(1.0)
        assert orch.cars["car_1"].phase == CarPhase.IN_GARAGE

    def test_red_flag_aborts_runs(self):
        orch = self._setup_orch()
        orch.request_run("car_1", RunProgram.SETUP_VALIDATION,
                         TyreCompound.C3, fuel_kg=50.0, laps_planned=3)
        orch.tick(1.0)
        assert orch.cars["car_1"].phase == CarPhase.ON_TRACK
        orch.clock.set_flag(SessionFlag.RED)
        orch.tick(1.0)
        assert orch.cars["car_1"].phase == CarPhase.IN_GARAGE
        assert any(e.event_type == PracticeEventType.RUN_ABORT for e in orch.events)


class TestOrchestratorQueries:
    def test_session_summary(self):
        orch = PracticeSessionOrchestrator(SessionType.FP2, duration_s=100)
        orch.register_team("team_a", ["car_1"])
        orch.start_session()
        orch.tick(10.0)
        summary = orch.session_summary()
        assert summary["session_type"] == "FP2"
        assert summary["elapsed_s"] == 10.0
        assert summary["remaining_s"] == 90.0

    def test_leaderboard(self):
        orch = PracticeSessionOrchestrator(SessionType.FP1)
        alloc = {TyreCompound.C3: 5}
        orch.register_team("team_a", ["car_1", "car_2"],
                           ["Fast", "Slow"], allocation=alloc)
        orch.start_session()

        # Car 1 does a run
        orch.request_run("car_1", RunProgram.QUALI_SIM,
                         TyreCompound.C3, fuel_kg=20.0, laps_planned=2)
        orch.tick(1.0)
        orch.complete_run("car_1", laps_completed=2, best_lap_s=88.0)

        # Car 2 does a run
        orch.request_run("car_2", RunProgram.QUALI_SIM,
                         TyreCompound.C3, fuel_kg=20.0, laps_planned=2)
        orch.tick(1.0)
        orch.complete_run("car_2", laps_completed=2, best_lap_s=90.0)

        lb = orch.leaderboard()
        assert len(lb) == 2
        assert lb[0]["car_id"] == "car_1"  # faster
        assert lb[1]["car_id"] == "car_2"

    def test_car_can_run(self):
        orch = PracticeSessionOrchestrator(SessionType.FP1)
        orch.register_team("team_a", ["car_1"], allocation={TyreCompound.C3: 3})
        orch.start_session()
        assert orch.car_can_run("car_1")
        orch.request_run("car_1", RunProgram.SETUP_VALIDATION,
                         TyreCompound.C3, fuel_kg=50.0, laps_planned=3)
        assert not orch.car_can_run("car_1")  # in queue
