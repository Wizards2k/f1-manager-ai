#!/usr/bin/env python3

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
PYTHON_BACKEND_ROOT = PROJECT_ROOT / "python_backend"

for path in (PROJECT_ROOT, PYTHON_BACKEND_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from lap_simulator.data_types import SectionResult
from models import CarState
import utils.game_logic as game_logic_module
from utils import session_bridge as session_bridge_module
from utils.session_bridge import LapPhase, SessionBridge
from lap_simulator.practice_session import CarPhase


def _build_section(section_id: str):
    return SimpleNamespace(
        section_id=section_id,
        length_m=100.0,
        dt_ref_s=1.0,
        v_entry_kph=120.0,
        v_exit_kph=120.0,
        kind=SimpleNamespace(name="TEST"),
    )


def _build_track_state():
    pu_state = SimpleNamespace(
        fuel_kg=100.0,
        ers_energy_mj=0.0,
        active_map=SimpleNamespace(value="STANDARD"),
    )
    entry = SimpleNamespace(
        car_id="1",
        state=SimpleNamespace(
            tyres={},
            pu=pu_state,
            ers_mode="STANDARD",
        ),
        aero_setup=SimpleNamespace(),
        driver_skills=SimpleNamespace(),
        push_level=0,
        delta_aero=0.0,
        delta_grip=0.0,
        apply_baseline_delta=True,
        setup_sliders={},
        ideal_setup_sliders={},
    )
    track_state = SimpleNamespace(
        car_entry=entry,
        current_section_idx=0,
        section_time_acc=0.0,
        distance_in_lap=0.0,
        pit_exit_delay_s=0.0,
        pit_exit_waited_s=0.0,
        lap_phase=LapPhase.HOT_LAP,
        current_sector=0,
        sector_dt_acc=0.0,
        lap_number=1,
        laps_done_in_run=0,
        laps_planned=5,
        is_player=False,
        setup_data_complete=False,
        lap_section_results=[],
    )
    return track_state, entry


def test_move_cars_advances_multiple_sections_in_one_tick(monkeypatch):
    bridge = SessionBridge()
    bridge.sections = [_build_section("s1"), _build_section("s2"), _build_section("s3")]
    bridge.circuit_config = SimpleNamespace(circuit_length_m=300.0)
    bridge._section_end_m = [100.0, 200.0, 300.0]
    bridge._sector_end_m = [100.0, 200.0, 300.0]

    track_state, entry = _build_track_state()
    race_car = SimpleNamespace(
        state=CarState.BOX,
        speed=0.0,
        distance_traveled=0.0,
        best_sectors={},
        current_lap_sectors={},
    )

    bridge._track_states = {"1": track_state}
    bridge.race_cars_map = {"1": race_car}
    bridge.pso = SimpleNamespace(cars={"1": SimpleNamespace(phase=CarPhase.ON_TRACK)})

    calls = []

    def fake_update_section(**kwargs):
        calls.append(kwargs["section"].section_id)
        section = kwargs["section"]
        return SectionResult(
            dt_s=section.dt_ref_s,
            v_entry_kph=section.v_entry_kph,
            v_exit_kph=section.v_exit_kph,
            v_effective_kph=section.v_exit_kph,
            v_max_kph=section.v_exit_kph,
            telemetry_points=[],
            events=[],
        )

    monkeypatch.setattr(session_bridge_module, "update_section", fake_update_section)
    monkeypatch.setattr(session_bridge_module, "log_microsector", lambda *args, **kwargs: None)
    monkeypatch.setattr(game_logic_module, "update_session_bests", lambda *args, **kwargs: None)
    monkeypatch.setattr(session_bridge_module, "emit_thermal_feedback", lambda *args, **kwargs: None)

    bridge._sync_ers_mode_state = lambda ts: None
    bridge._apply_section_to_racecar = lambda *args, **kwargs: None
    bridge._log_pu_section_usage = lambda *args, **kwargs: None
    bridge._update_brake_warning = lambda *args, **kwargs: None
    bridge._format_pu_telemetry = lambda *args, **kwargs: {}

    bridge._move_cars(2.2)

    assert calls == ["s1", "s2"]
    assert track_state.current_section_idx == 2
    assert track_state.section_time_acc == pytest.approx(0.2)
    assert track_state.distance_in_lap == pytest.approx(220.0)
    assert race_car.distance_traveled == pytest.approx(220.0)
    assert len(track_state.lap_section_results) == 2
    assert track_state.current_sector == 2


def test_move_cars_accumulates_section_progress_across_ticks(monkeypatch):
    bridge = SessionBridge()
    bridge.sections = [_build_section("s1"), _build_section("s2"), _build_section("s3")]
    bridge.circuit_config = SimpleNamespace(circuit_length_m=300.0)
    bridge._section_end_m = [100.0, 200.0, 300.0]
    bridge._sector_end_m = [100.0, 200.0, 300.0]

    track_state, entry = _build_track_state()
    race_car = SimpleNamespace(
        state=CarState.BOX,
        speed=0.0,
        distance_traveled=0.0,
        best_sectors={},
        current_lap_sectors={},
    )

    bridge._track_states = {"1": track_state}
    bridge.race_cars_map = {"1": race_car}
    bridge.pso = SimpleNamespace(cars={"1": SimpleNamespace(phase=CarPhase.ON_TRACK)})

    calls = []

    def fake_update_section(**kwargs):
        calls.append(kwargs["section"].section_id)
        section = kwargs["section"]
        return SectionResult(
            dt_s=section.dt_ref_s,
            v_entry_kph=section.v_entry_kph,
            v_exit_kph=section.v_exit_kph,
            v_effective_kph=section.v_exit_kph,
            v_max_kph=section.v_exit_kph,
            telemetry_points=[],
            events=[],
        )

    monkeypatch.setattr(session_bridge_module, "update_section", fake_update_section)
    monkeypatch.setattr(session_bridge_module, "log_microsector", lambda *args, **kwargs: None)
    monkeypatch.setattr(game_logic_module, "update_session_bests", lambda *args, **kwargs: None)
    monkeypatch.setattr(session_bridge_module, "emit_thermal_feedback", lambda *args, **kwargs: None)

    bridge._sync_ers_mode_state = lambda ts: None
    bridge._apply_section_to_racecar = lambda *args, **kwargs: None
    bridge._log_pu_section_usage = lambda *args, **kwargs: None
    bridge._update_brake_warning = lambda *args, **kwargs: None
    bridge._format_pu_telemetry = lambda *args, **kwargs: {}

    bridge._move_cars(0.6)

    assert calls == []
    assert track_state.current_section_idx == 0
    assert track_state.section_time_acc == pytest.approx(0.6)
    assert track_state.distance_in_lap == pytest.approx(60.0)
    assert race_car.distance_traveled == pytest.approx(60.0)

    bridge._move_cars(0.6)

    assert calls == ["s1"]
    assert track_state.current_section_idx == 1
    assert track_state.section_time_acc == pytest.approx(0.2)
    assert track_state.distance_in_lap == pytest.approx(120.0)
    assert race_car.distance_traveled == pytest.approx(120.0)
    assert len(track_state.lap_section_results) == 1
