#!/usr/bin/env python3

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_backend"))

import config
from f1_manager_ai import app as flask_app
import utils.game_logic as gl
import services.save_system as save_system_module
from routes import api as api_module
from models.models import CarState, Nazionalita, Pilota, RaceCar, Team, TireCompound
from models.tyre_inventory import DriverTyreInventory, TyreSet
from services.save_system import SaveGameService
from utils.adapter import racecar_to_car_entry
from utils.session_bridge import CarTrackState, SessionBridge


def _build_team_and_driver(driver_number: int = 7) -> tuple[Team, Pilota]:
    team = Team(
        nome_scuderia="McLaren",
        sigla_scuderia="MCL",
        nazionalita=Nazionalita.REGNO_UNITO,
        colore_team="#FF6600",
        simulator_quality=75,
    )
    driver = Pilota(
        nome="Lando",
        cognome="Norris",
        nazionalita=Nazionalita.REGNO_UNITO,
        eta=25,
        numero_di_gara=driver_number,
        velocita=95,
        qualifica=95,
        gara=94,
        aggressivita=90,
        costanza=91,
        consumo_gomme=93,
        ricerca_assetto=92,
        perfezionismo=88,
    )
    return team, driver


def _build_race_car(driver_number: int = 7) -> RaceCar:
    team, driver = _build_team_and_driver(driver_number)
    car = RaceCar(pilot=driver, team=team, initial_compound=TireCompound.MEDIUM)
    car.set_tire_compound(TireCompound.MEDIUM, percentuale_vita=0.94, laps_completed=12)
    car.current_tyre_heat_cycles = 2
    car.current_tyre_laps_at_install = 12
    car.player_config["tyre_set_id"] = "M1"
    car.state = CarState.OUT_LAP
    return car


def _build_inventory(
    *,
    driver_id: str = "7",
    circuit_id: str = "test-circuit",
    condition: float = 94.0,
    heat_cycles: int = 2,
    laps_completed: int = 12,
    is_available: bool = False,
) -> DriverTyreInventory:
    return DriverTyreInventory(
        driver_id=driver_id,
        circuit_id=circuit_id,
        allocation={},
        sets=[
            TyreSet(
                set_id="M1",
                compound="medium",
                condition=condition,
                heat_cycles=heat_cycles,
                laps_completed=laps_completed,
                is_available=is_available,
            )
        ],
    )


def test_save_load_preserves_tyre_condition_after_reentry(tmp_path, monkeypatch):
    bridge = SessionBridge()
    bridge.active = True
    bridge.circuit_id = "test-circuit"
    bridge._track_states = {}

    race_car = _build_race_car()
    inventory_key = bridge.tyre_inventory_service._inventory_key("7", "test-circuit")
    bridge.tyre_inventory_service._inventory_cache[inventory_key] = _build_inventory()

    monkeypatch.setattr(save_system_module, "get_session_bridge", lambda: bridge)
    monkeypatch.setattr(save_system_module, "race_cars", [race_car], raising=False)
    monkeypatch.setattr(gl, "start_session_for_circuit", lambda: None)
    monkeypatch.setattr(gl, "get_session_bridge", lambda: bridge)
    monkeypatch.setattr(gl, "get_car_by_driver_number", lambda driver_number: race_car if int(driver_number) == 7 else None)
    monkeypatch.setattr(config, "set_current_circuit", lambda circuit_id: None)

    service = SaveGameService(data_root=tmp_path)
    save_id = service.save_game("tyre regression")
    save_path = service.save_dir / f"{save_id}.json"

    with save_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["inventories"]["7"]["sets"][0]["condition"] == pytest.approx(94.0)

    payload["inventories"]["7"]["sets"][0]["condition"] = 100.0
    payload["inventories"]["7"]["sets"][0]["heat_cycles"] = 0
    payload["inventories"]["7"]["sets"][0]["laps_completed"] = 0
    payload["inventories"]["7"]["sets"][0]["is_available"] = True

    with save_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    live_set = bridge.tyre_inventory_service.get_inventory("7", "test-circuit").find_set("M1")
    assert live_set is not None
    live_set.condition = 100.0
    live_set.heat_cycles = 0
    live_set.laps_completed = 0
    live_set.is_available = True

    result = service.load_game(save_id)
    assert result["success"] is True

    restored_set = bridge.tyre_inventory_service.get_inventory("7", "test-circuit").find_set("M1")
    assert restored_set is not None
    assert restored_set.condition == pytest.approx(94.0)
    assert restored_set.heat_cycles == 2
    assert restored_set.laps_completed == 12
    assert restored_set.is_available is False
    assert race_car.current_tyre_condition_pct == pytest.approx(94.0)


def test_session_bridge_relinks_loaded_tyre_set_from_bridge_inventory():
    bridge = SessionBridge()
    bridge.circuit_id = "test-circuit"
    bridge.circuit_config = None
    bridge._track_states = {}

    race_car = _build_race_car()
    car_entry = racecar_to_car_entry(race_car)
    inventory_key = bridge.tyre_inventory_service._inventory_key("7", "test-circuit")
    bridge.tyre_inventory_service._inventory_cache[inventory_key] = _build_inventory(is_available=True)

    track_state = CarTrackState(car_id="7", car_entry=car_entry, tyre_set_id="M1")
    bridge.load_session_state(
        {
            "circuit_id": "test-circuit",
            "session_kind": "FP1",
            "_accumulated_time_s": 0.0,
            "_track_states": {"7": track_state.to_dict()},
            "_ai_teams_cars": {},
            "_player_runtime_state": {},
            "_ai_engines": {},
            "_ai_setup_states": {},
        }
    )

    restored_ts = bridge._track_states["7"]
    assert restored_ts.tyre_set is not None
    assert restored_ts.tyre_set.set_id == "M1"
    assert restored_ts.tyre_set.condition == pytest.approx(94.0)


def test_tyre_inventory_endpoint_prefers_active_bridge_inventory(monkeypatch):
    bridge = SessionBridge()
    bridge.active = True
    bridge.circuit_id = "test-circuit"
    bridge._track_states = {}

    bridge_key = bridge.tyre_inventory_service._inventory_key("7", "test-circuit")
    fallback_key = api_module.tyre_inventory_service._inventory_key("7", "test-circuit")

    monkeypatch.setitem(
        bridge.tyre_inventory_service._inventory_cache,
        bridge_key,
        _build_inventory(condition=94.0),
    )
    monkeypatch.setitem(
        api_module.tyre_inventory_service._inventory_cache,
        fallback_key,
        _build_inventory(condition=100.0),
    )
    monkeypatch.setattr(gl, "get_session_bridge", lambda: bridge)

    with flask_app.test_client() as client:
        response = client.get("/api/driver/7/tyre-inventory/test-circuit")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload["sets"][0]["condition"] == pytest.approx(94.0)
    assert payload["sets"][0]["is_available"] is False
