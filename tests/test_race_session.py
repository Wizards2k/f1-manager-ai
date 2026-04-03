#!/usr/bin/env python3

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_backend"))

from utils.race_session import RaceDriverState, RaceLapRecord, RaceSessionState
from utils.weekend_orchestrator import WeekendOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_participants(total: int = 20):
    return [
        {
            "car_id": str(idx),
            "driver_name": f"Driver {idx:02d}",
            "team_name": f"Team {((idx - 1) // 2) + 1:02d}",
            "is_player": idx == 1,
        }
        for idx in range(1, total + 1)
    ]


def _build_grid(total: int = 20):
    return [
        {"car_id": str(idx), "position": idx}
        for idx in range(1, total + 1)
    ]


def _record_laps(state: RaceSessionState, lap_number: int, base_time: float) -> None:
    """Registra un giro per tutti i partecipanti con tempi progressivi."""
    for position, (car_id, participant) in enumerate(
        sorted(state.participants.items(), key=lambda x: x[1].current_position or 999),
        start=1,
    ):
        state.record_lap(
            car_id=car_id,
            lap_time_s=base_time + position * 0.1,
            lap_number=lap_number,
            timestamp_s=float(lap_number * base_time),
            sector_times={
                "sector1": base_time / 3.0,
                "sector2": base_time / 3.0,
                "sector3": base_time / 3.0,
            },
            is_competitive=True,
            tyre_compound="medium",
            tyre_condition_pct=max(10.0, 95.0 - lap_number * 2.0),
            position=position,
        )


# ---------------------------------------------------------------------------
# RaceSessionState — unit tests
# ---------------------------------------------------------------------------

class TestRaceSessionStateStart:
    def test_start_sets_status_active(self):
        state = RaceSessionState()
        state.start(_build_participants(), circuit_id="monza", started_at_s=0.0)
        assert state.status == "active"
        assert not state.is_complete

    def test_start_populates_participants(self):
        state = RaceSessionState()
        state.start(_build_participants(20))
        assert len(state.participants) == 20

    def test_start_applies_starting_grid(self):
        state = RaceSessionState()
        grid = _build_grid(20)
        state.start(_build_participants(20), starting_grid=grid)
        assert state.participants["1"].starting_position == 1
        assert state.participants["20"].starting_position == 20
        assert len(state.starting_grid) == 20

    def test_start_sets_initial_running_order(self):
        state = RaceSessionState()
        state.start(_build_participants(5), starting_grid=_build_grid(5))
        assert len(state.running_order) == 5
        assert state.leader_car_id == "1"

    def test_start_clears_previous_data(self):
        state = RaceSessionState()
        state.start(_build_participants(5))
        # Registra un giro poi ri-avvia
        state.record_lap(car_id="1", lap_time_s=90.0, lap_number=1)
        state.start(_build_participants(5))
        assert state.lap_records == []
        assert state.pit_stops == []
        assert state.classification == []


class TestRaceSessionStateRecordLap:
    def setup_method(self):
        self.state = RaceSessionState()
        self.state.start(_build_participants(5), starting_grid=_build_grid(5), started_at_s=0.0)

    def test_record_lap_increments_laps_completed(self):
        self.state.record_lap(car_id="1", lap_time_s=90.0, lap_number=1)
        assert self.state.participants["1"].laps_completed == 1

    def test_record_lap_accumulates_total_time(self):
        self.state.record_lap(car_id="1", lap_time_s=90.0, lap_number=1)
        self.state.record_lap(car_id="1", lap_time_s=91.5, lap_number=2)
        assert abs(self.state.participants["1"].total_time_s - 181.5) < 0.001

    def test_record_lap_updates_best_lap(self):
        self.state.record_lap(car_id="1", lap_time_s=92.0, lap_number=1)
        self.state.record_lap(car_id="1", lap_time_s=90.5, lap_number=2)
        self.state.record_lap(car_id="1", lap_time_s=91.0, lap_number=3)
        assert abs(self.state.participants["1"].best_lap_s - 90.5) < 0.001

    def test_record_lap_creates_record(self):
        self.state.record_lap(car_id="1", lap_time_s=90.0, lap_number=1, tyre_compound="soft")
        assert len(self.state.lap_records) == 1
        record = self.state.lap_records[0]
        assert record.car_id == "1"
        assert record.tyre_compound == "soft"

    def test_record_lap_updates_position(self):
        self.state.record_lap(car_id="3", lap_time_s=89.0, lap_number=1, position=1)
        assert self.state.participants["3"].current_position == 1

    def test_record_lap_updates_running_order(self):
        self.state.record_lap(car_id="1", lap_time_s=90.0, lap_number=1, position=1)
        self.state.record_lap(car_id="2", lap_time_s=90.2, lap_number=1, position=2)
        assert self.state.running_order[0]["car_id"] == "1"
        assert self.state.running_order[1]["car_id"] == "2"

    def test_record_lap_updates_tyre_info(self):
        self.state.record_lap(
            car_id="1", lap_time_s=90.0, lap_number=1,
            tyre_set_id="set-01", tyre_compound="hard", tyre_condition_pct=85.0,
        )
        p = self.state.participants["1"]
        assert p.tyre_set_id == "set-01"
        assert p.tyre_compound == "hard"
        assert abs(p.tyre_condition_pct - 85.0) < 0.001


class TestRaceSessionStateRecordPitStop:
    def setup_method(self):
        self.state = RaceSessionState()
        self.state.start(_build_participants(5), starting_grid=_build_grid(5))

    def test_pit_stop_increments_counter(self):
        self.state.record_pit_stop(car_id="1")
        assert self.state.participants["1"].pit_stops == 1

    def test_pit_stop_increments_stint_number(self):
        self.state.record_pit_stop(car_id="1")
        assert self.state.participants["1"].current_stint_number == 2

    def test_pit_stop_sets_status_pit(self):
        self.state.record_pit_stop(car_id="1")
        assert self.state.participants["1"].status == "pit"

    def test_pit_stop_updates_tyre(self):
        self.state.record_pit_stop(
            car_id="1", tyre_compound="soft", tyre_condition_pct=100.0
        )
        assert self.state.participants["1"].tyre_compound == "soft"
        assert abs(self.state.participants["1"].tyre_condition_pct - 100.0) < 0.001

    def test_pit_stop_appended_to_list(self):
        self.state.record_pit_stop(car_id="2", reason="strategy")
        assert len(self.state.pit_stops) == 1
        assert self.state.pit_stops[0]["reason"] == "strategy"

    def test_multiple_pit_stops(self):
        self.state.record_pit_stop(car_id="1")
        self.state.record_pit_stop(car_id="1")
        assert self.state.participants["1"].pit_stops == 2
        assert self.state.participants["1"].current_stint_number == 3


class TestRaceSessionStateMarkRetired:
    def setup_method(self):
        self.state = RaceSessionState()
        self.state.start(_build_participants(5))

    def test_mark_retired_sets_status(self):
        self.state.mark_retired(car_id="3", reason="engine")
        assert self.state.participants["3"].status == "retired"
        assert self.state.participants["3"].retirement_reason == "engine"

    def test_mark_retired_records_timestamp(self):
        self.state.mark_retired(car_id="3", reason="crash", timestamp_s=450.0)
        assert abs(self.state.participants["3"].finished_at_s - 450.0) < 0.001


class TestRaceSessionStateFinalizeSession:
    def setup_method(self):
        self.state = RaceSessionState()
        self.state.start(_build_participants(5), starting_grid=_build_grid(5), started_at_s=0.0)

    def _run_full_race(self, total_laps: int = 10) -> None:
        for lap in range(1, total_laps + 1):
            _record_laps(self.state, lap_number=lap, base_time=90.0)

    def test_finalize_sets_complete(self):
        self._run_full_race(3)
        self.state.finalize_session(finished_at_s=300.0)
        assert self.state.is_complete
        assert self.state.status == "completed"

    def test_finalize_returns_classification(self):
        self._run_full_race(3)
        classification = self.state.finalize_session(finished_at_s=300.0)
        assert len(classification) == 5

    def test_finalize_classification_ordered_by_position(self):
        self._run_full_race(5)
        classification = self.state.finalize_session(finished_at_s=500.0)
        positions = [row["position"] for row in classification]
        assert positions == sorted(positions)

    def test_finalize_leader_has_zero_gap(self):
        self._run_full_race(5)
        classification = self.state.finalize_session(finished_at_s=500.0)
        assert classification[0]["gap_to_leader_s"] == 0.0

    def test_finalize_sets_finish_positions(self):
        self._run_full_race(3)
        self.state.finalize_session()
        for row in self.state.classification:
            assert row["finish_position"] is not None

    def test_finalize_retired_car_last(self):
        self._run_full_race(3)
        self.state.mark_retired(car_id="5", reason="engine")
        classification = self.state.finalize_session()
        # L'auto ritirata deve avere status "retired" in classifica
        car5 = next(row for row in classification if row["car_id"] == "5")
        assert car5["status"] == "retired"

    def test_finalize_gap_to_leader_positive(self):
        self._run_full_race(5)
        classification = self.state.finalize_session(finished_at_s=500.0)
        for row in classification[1:]:
            if row["gap_to_leader_s"] is not None:
                assert row["gap_to_leader_s"] >= 0.0

    def test_finalize_interval_to_ahead(self):
        self._run_full_race(5)
        classification = self.state.finalize_session()
        # Primo ha interval 0; gli altri hanno interval >= 0
        assert classification[0]["interval_to_ahead_s"] == 0.0
        for row in classification[1:]:
            if row["interval_to_ahead_s"] is not None:
                assert row["interval_to_ahead_s"] >= 0.0


class TestRaceSessionStateSerialization:
    def test_roundtrip_empty(self):
        state = RaceSessionState()
        restored = RaceSessionState.from_dict(state.to_dict())
        assert restored.status == state.status
        assert restored.is_complete == state.is_complete

    def test_roundtrip_after_start(self):
        state = RaceSessionState()
        state.start(_build_participants(5), starting_grid=_build_grid(5), started_at_s=0.0)
        restored = RaceSessionState.from_dict(state.to_dict())
        assert len(restored.participants) == 5
        assert restored.participants["1"].starting_position == 1

    def test_roundtrip_after_laps(self):
        state = RaceSessionState()
        state.start(_build_participants(5))
        _record_laps(state, lap_number=1, base_time=90.0)
        restored = RaceSessionState.from_dict(state.to_dict())
        assert len(restored.lap_records) == 5
        assert abs(restored.participants["1"].total_time_s - state.participants["1"].total_time_s) < 0.001

    def test_roundtrip_after_finalize(self):
        state = RaceSessionState()
        state.start(_build_participants(5))
        _record_laps(state, lap_number=1, base_time=90.0)
        state.finalize_session(finished_at_s=100.0)
        restored = RaceSessionState.from_dict(state.to_dict())
        assert restored.is_complete
        assert len(restored.classification) == 5


# ---------------------------------------------------------------------------
# WeekendOrchestrator — race delegation tests
# ---------------------------------------------------------------------------

class TestWeekendOrchestratorRaceDelegation:
    def setup_method(self):
        self.orchestrator = WeekendOrchestrator()
        self.orchestrator.start(circuit_id="monza", session_type="RACE")

    def test_start_race_creates_race_state(self):
        self.orchestrator.start_race(
            participants=_build_participants(5),
            starting_grid=_build_grid(5),
        )
        assert self.orchestrator.race_state is not None
        assert self.orchestrator.race_state.status == "active"

    def test_start_race_populates_participants(self):
        self.orchestrator.start_race(
            participants=_build_participants(20),
            starting_grid=_build_grid(20),
        )
        assert len(self.orchestrator.race_state.participants) == 20

    def test_record_race_lap_returns_none_without_race_state(self):
        self.orchestrator.race_state = None
        result = self.orchestrator.record_race_lap(
            car_id="1", lap_time_s=90.0, lap_number=1
        )
        assert result is None

    def test_record_race_lap_delegates_to_race_state(self):
        self.orchestrator.start_race(
            participants=_build_participants(5),
            starting_grid=_build_grid(5),
        )
        record = self.orchestrator.record_race_lap(
            car_id="1",
            lap_time_s=90.0,
            lap_number=1,
            timestamp_s=90.0,
            tyre_compound="medium",
            position=1,
        )
        assert record is not None
        assert record.car_id == "1"
        assert abs(record.lap_time_s - 90.0) < 0.001
        assert self.orchestrator.race_state.participants["1"].laps_completed == 1

    def test_finalize_race_returns_empty_without_race_state(self):
        self.orchestrator.race_state = None
        result = self.orchestrator.finalize_race(finished_at_s=5400.0)
        assert result == []

    def test_finalize_race_produces_classification(self):
        self.orchestrator.start_race(
            participants=_build_participants(5),
            starting_grid=_build_grid(5),
        )
        for car_id in ["1", "2", "3", "4", "5"]:
            for lap in range(1, 4):
                self.orchestrator.record_race_lap(
                    car_id=car_id,
                    lap_time_s=90.0 + int(car_id) * 0.1,
                    lap_number=lap,
                    timestamp_s=float(lap * 90),
                )
        classification = self.orchestrator.finalize_race(finished_at_s=300.0)
        assert len(classification) == 5
        assert self.orchestrator.race_state.is_complete

    def test_get_qualifying_summary_returns_none_without_state(self):
        assert self.orchestrator.get_qualifying_summary() is None

    def test_start_race_sets_circuit_id(self):
        self.orchestrator.start_race(participants=_build_participants(3))
        assert self.orchestrator.race_state.circuit_id == "monza"


class TestWeekendOrchestratorQualifyingDelegation:
    def setup_method(self):
        from utils.qualifying_session import QualifyingSessionState, QualifyingPhase
        self.orchestrator = WeekendOrchestrator()
        self.orchestrator.start(circuit_id="monza", session_type="Q1")
        self.orchestrator.qualifying_state = QualifyingSessionState().start(
            _build_participants(20),
            circuit_id="monza",
            started_at_s=0.0,
        )

    def test_get_qualifying_summary_returns_dict(self):
        summary = self.orchestrator.get_qualifying_summary()
        assert isinstance(summary, dict)
        assert "final_grid" in summary

    def test_record_qualifying_lap_returns_none_without_state(self):
        self.orchestrator.qualifying_state = None
        result = self.orchestrator.record_qualifying_lap(
            car_id="1", lap_time_s=90.0, lap_number=1
        )
        assert result is None

    def test_record_qualifying_lap_delegates(self):
        from utils.qualifying_session import QualifyingPhase
        record = self.orchestrator.record_qualifying_lap(
            car_id="1",
            lap_time_s=88.5,
            lap_number=1,
            phase=QualifyingPhase.Q1,
            timestamp_s=300.0,
            is_competitive=True,
            tyre_compound="soft",
        )
        assert record is not None
        assert abs(record.lap_time_s - 88.5) < 0.001

    def test_finalize_qualifying_returns_empty_without_state(self):
        self.orchestrator.qualifying_state = None
        result = self.orchestrator.finalize_qualifying(finished_at_s=1080.0)
        assert result == []

    def test_finalize_qualifying_produces_grid(self):
        from utils.qualifying_session import QualifyingPhase
        # Registra giri per Q1
        for idx in range(1, 21):
            self.orchestrator.record_qualifying_lap(
                car_id=str(idx),
                lap_time_s=90.0 + idx * 0.1,
                lap_number=1,
                phase=QualifyingPhase.Q1,
                is_competitive=True,
            )
        grid = self.orchestrator.finalize_qualifying(finished_at_s=1080.0)
        assert len(grid) > 0
        assert self.orchestrator.qualifying_state.status == "completed"
