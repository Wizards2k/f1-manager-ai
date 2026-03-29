#!/usr/bin/env python3

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_backend"))

from utils.qualifying_session import QualifyingPhase, QualifyingSessionState


def _build_participants(total: int = 20):
    participants = []
    for idx in range(1, total + 1):
        participants.append(
            {
                "car_id": str(idx),
                "driver_name": f"Driver {idx:02d}",
                "team_name": f"Team {((idx - 1) // 2) + 1:02d}",
                "is_player": idx == 1,
            }
        )
    return participants


def _run_phase(
    state: QualifyingSessionState,
    phase: QualifyingPhase,
    lap_number: int,
    base_time: float,
    tyre_compound: str = "soft",
    tyre_condition_pct: float = 98.0,
    tyre_is_q3_reserve: bool = False,
) -> None:
    phase_state = state.get_phase(phase)
    assert phase_state is not None
    for position, car_id in enumerate(list(phase_state.participants), start=1):
        state.record_lap(
            car_id=car_id,
            lap_time_s=base_time + (position * 0.1),
            lap_number=lap_number,
            phase=phase,
            timestamp_s=base_time + position,
            sector_times={"sector1": base_time / 3.0, "sector2": base_time / 3.0, "sector3": base_time / 3.0},
            is_competitive=True,
            tyre_set_id=f"{phase.value}-{position:02d}",
            tyre_compound=tyre_compound,
            tyre_condition_pct=tyre_condition_pct,
            tyre_is_q3_reserve=tyre_is_q3_reserve,
        )


def test_qualifying_progression_cutoffs_and_roundtrip():
    state = QualifyingSessionState().start(
        _build_participants(),
        circuit_id="test-circuit",
        metadata={"round": "Monza"},
        started_at_s=0.0,
    )

    _run_phase(state, QualifyingPhase.Q1, lap_number=1, base_time=90.0, tyre_compound="soft", tyre_condition_pct=96.0)
    q1 = state.complete_current_phase(finished_at_s=1080.0)
    assert q1 is not None
    assert q1.phase == QualifyingPhase.Q1
    assert q1.eliminated_car_ids == ["16", "17", "18", "19", "20"]
    assert state.current_phase == QualifyingPhase.Q2.value
    assert state.participants["16"].status == "eliminated"
    assert state.participants["1"].status == "qualified"

    _run_phase(state, QualifyingPhase.Q2, lap_number=2, base_time=80.0, tyre_compound="soft", tyre_condition_pct=92.0)
    q2 = state.complete_current_phase(finished_at_s=1980.0)
    assert q2 is not None
    assert q2.phase == QualifyingPhase.Q2
    assert q2.eliminated_car_ids == ["11", "12", "13", "14", "15"]
    assert state.current_phase == QualifyingPhase.Q3.value
    assert state.participants["11"].status == "eliminated"
    assert state.participants["10"].status == "qualified"

    _run_phase(
        state,
        QualifyingPhase.Q3,
        lap_number=3,
        base_time=70.0,
        tyre_compound="soft",
        tyre_condition_pct=88.0,
        tyre_is_q3_reserve=True,
    )
    q3 = state.complete_current_phase(finished_at_s=2700.0)
    assert q3 is not None
    assert q3.phase == QualifyingPhase.Q3
    assert state.is_complete is True
    assert len(state.final_grid) == 20
    assert [row["car_id"] for row in state.final_grid[:10]] == [str(i) for i in range(1, 11)]
    assert [row["car_id"] for row in state.final_grid[10:15]] == [str(i) for i in range(11, 16)]
    assert [row["car_id"] for row in state.final_grid[15:20]] == [str(i) for i in range(16, 21)]
    assert state.final_grid[0]["status"] == "pole"
    assert state.final_grid[0]["best_phase"] == "Q3"
    assert state.final_grid[0]["best_lap_tyre_set_id"] == "Q3-01"
    assert state.final_grid[0]["best_lap_tyre_compound"] == "soft"
    assert state.final_grid[0]["best_lap_tyre_condition_pct"] == pytest.approx(88.0)
    assert state.final_grid[0]["best_lap_tyre_is_q3_reserve"] is True

    roundtrip = QualifyingSessionState.from_dict(state.to_dict())
    assert roundtrip.is_complete is True
    assert roundtrip.final_grid == state.final_grid
    assert roundtrip.participants["1"].best_lap_phase == "Q3"
    assert roundtrip.participants["1"].best_lap_tyre_set_id == "Q3-01"
    assert roundtrip.participants["1"].best_lap_tyre_compound == "soft"
    assert roundtrip.participants["1"].best_lap_tyre_condition_pct == pytest.approx(88.0)
    assert roundtrip.participants["1"].best_lap_tyre_is_q3_reserve is True
    assert roundtrip.participants["16"].eliminated_in_phase == "Q1"
    assert roundtrip.participants["11"].eliminated_in_phase == "Q2"
    assert roundtrip.metadata["round"] == "Monza"
