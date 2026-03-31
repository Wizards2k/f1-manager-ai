import json
import os
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from lap_simulator.practice_session import PracticeSessionOrchestrator
from models.tyre_inventory import DriverTyreInventory
from utils.game_logic import (
    race_cars, get_session_bridge, get_session_telemetry_store,
    accumulated_game_time, is_paused, game_speed_multiplier,
    session_start_time, player_team_id, player_driver_numbers,
    session_best_lap, session_best_sectors, get_weekend_orchestrator,
    set_weekend_orchestrator,
)
from services.tyre_inventory_service import TyreInventoryService
from utils.weekend_orchestrator import (
    WeekendOrchestrator,
    WeekendSessionType,
    normalize_weekend_session_type,
)

logger = logging.getLogger(__name__)


def _bridge_session_type_from_weekend(session_type: Optional[str]) -> str:
    try:
        normalized = normalize_weekend_session_type(session_type)
    except ValueError:
        return WeekendSessionType.FP1.value

    # Backward compatibility: old saves may have QUALIFYING
    if normalized in {WeekendSessionType.Q1, WeekendSessionType.Q2, WeekendSessionType.Q3}:
        return 'QUALIFYING'

    if normalized == WeekendSessionType.RACE:
        return normalized.value

    if normalized in {
        WeekendSessionType.FP1,
        WeekendSessionType.FP2,
        WeekendSessionType.FP3,
    }:
        return normalized.value

    return WeekendSessionType.FP1.value

class SaveGameService:
    def __init__(self, data_root: Optional[Path] = None):
        self.base_path = data_root or Path(__file__).resolve().parents[1]
        self.save_dir = self.base_path / "saves"
        os.makedirs(self.save_dir, exist_ok=True)
        self.tyre_service = TyreInventoryService()

    def _restore_tyre_inventories(
        self,
        service: Optional[TyreInventoryService],
        inventories_state: Dict[str, Dict[str, Any]],
        circuit_id: str,
    ) -> None:
        if service is None or not circuit_id:
            return

        store = service._load_store()
        for driver_id, inv_data in inventories_state.items():
            try:
                inventory = DriverTyreInventory.from_dict(inv_data)
            except Exception as exc:
                logger.warning(
                    "Failed to restore tyre inventory for driver %s on circuit %s: %s",
                    driver_id,
                    circuit_id,
                    exc,
                )
                continue

            key = service._inventory_key(driver_id, circuit_id)
            service._inventory_cache[key] = inventory
            store[key] = inv_data

    def _merge_car_state_into_inventory_payloads(
        self,
        inventories_state: Dict[str, Dict[str, Any]],
        cars_state: List[Dict[str, Any]],
    ) -> None:
        active_track_states = {"OUT LAP", "HOT LAP", "IN LAP"}

        for car_data in cars_state:
            if not isinstance(car_data, dict):
                continue

            driver_number = car_data.get("driver_number")
            if driver_number is None:
                continue

            driver_id = str(driver_number)
            inv_data = inventories_state.get(driver_id)
            if not isinstance(inv_data, dict):
                continue

            tyre_set_id = ""
            player_config = car_data.get("player_config") or {}
            if isinstance(player_config, dict):
                tyre_set_id = str(player_config.get("tyre_set_id") or "").strip()
            if not tyre_set_id:
                tyre_set_id = str(car_data.get("current_tyre_set_id") or "").strip()
            if not tyre_set_id:
                continue

            sets = inv_data.get("sets")
            if not isinstance(sets, list):
                continue

            matching_set = next(
                (
                    tyre_set for tyre_set in sets
                    if isinstance(tyre_set, dict) and tyre_set.get("set_id") == tyre_set_id
                ),
                None,
            )
            if matching_set is None:
                continue

            condition = car_data.get("current_tyre_condition_pct")
            if condition is not None:
                matching_set["condition"] = max(0.0, min(100.0, float(condition)))

            heat_cycles = car_data.get("current_tyre_heat_cycles")
            if heat_cycles is not None:
                matching_set["heat_cycles"] = int(heat_cycles)

            laps_completed = car_data.get("current_tyre_laps_completed")
            if laps_completed is not None:
                matching_set["laps_completed"] = int(laps_completed)

            state_value = str(car_data.get("state") or "").strip().upper()
            if state_value in active_track_states:
                matching_set["is_available"] = False
            elif state_value == "BOX":
                matching_set["is_available"] = True

    def get_save_files(self) -> List[Dict[str, Any]]:
        saves = []
        for p in self.save_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    meta = data.get("metadata", {})
                    weekend_state = data.get("weekend_state", {}) or {}
                    saves.append({
                        "id": p.stem,
                        "name": meta.get("name", p.stem),
                        "timestamp": meta.get("timestamp"),
                        "circuit_id": meta.get("circuit_id"),
                        "session_type": meta.get("session_type"),
                        "weekend_session_type": meta.get("weekend_session_type", weekend_state.get("current_session_type")),
                        "weekend_status": meta.get("weekend_status", weekend_state.get("status")),
                    })
            except Exception:
                continue
        return sorted(saves, key=lambda x: x.get("timestamp", ""), reverse=True)

    def save_game(self, name: str) -> str:
        bridge = get_session_bridge()
        if not bridge or not bridge.active:
            raise ValueError("No active session to save")

        weekend_orchestrator = get_weekend_orchestrator()
        weekend_state = weekend_orchestrator.to_dict() if weekend_orchestrator else None

        timestamp = datetime.now().isoformat()
        save_id = f"save_{int(time.time())}"
        
        # 1. Metadata
        current_session_type = (
            weekend_orchestrator.current_session_type
            if weekend_orchestrator and weekend_orchestrator.current_session_type
            else (bridge.pso.session_type.value if bridge.pso else "FP1")
        )
        metadata = {
            "name": name,
            "timestamp": timestamp,
            "circuit_id": bridge.circuit_id,
            "session_type": current_session_type,
            "weekend_session_type": current_session_type,
            "weekend_status": weekend_orchestrator.status if weekend_orchestrator else None,
        }

        # 2. Global Game Logic State
        engine_state = {
            "accumulated_game_time": accumulated_game_time,
            "game_speed_multiplier": game_speed_multiplier,
            "is_paused": is_paused,
            "player_team_id": player_team_id,
            "player_driver_numbers": list(player_driver_numbers),
            "session_best_lap": session_best_lap,
            "session_best_sectors": session_best_sectors,
        }

        # 3. PSO (Practice Session Orchestrator) State
        pso_state = bridge.pso.to_dict() if bridge.pso else None

        # 4. Bridge Internal State
        bridge_state = bridge.to_dict()

        # 5. RaceCars State
        cars_state = [car.to_dict() for car in race_cars]

        # 6. Tyre Inventory State
        inventories = {}
        tyre_service = getattr(bridge, "tyre_inventory_service", None) or self.tyre_service
        if bridge.circuit_id and tyre_service is not None:
            for car in race_cars:
                driver_id = str(car.driver_number)
                inv = tyre_service.get_inventory(driver_id, bridge.circuit_id)
                inventories[driver_id] = inv.to_dict()

        payload = {
            "metadata": metadata,
            "engine_state": engine_state,
            "pso_state": pso_state,
            "bridge_state": bridge_state,
            "cars_state": cars_state,
            "inventories": inventories,
            "weekend_state": weekend_state,
        }

        file_path = self.save_dir / f"{save_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.error("JSON serialization failed for save %s: %s", save_id, str(e))
            # Optional: identify which part failed if payload is large
            raise e

        logger.info("Game saved to %s", file_path)
        return save_id

    def load_game(self, save_id: str) -> bool:
        file_path = self.save_dir / f"{save_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Save file {save_id} not found")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        metadata = data.get("metadata", {})
        engine_state = data.get("engine_state", {})
        pso_state = data.get("pso_state")
        cars_state = data.get("cars_state", [])
        inventories_state = data.get("inventories", {})
        weekend_state = data.get("weekend_state")
        circuit_id = metadata.get("circuit_id")

        if not circuit_id:
            logger.error("Save file %s missing circuit_id", save_id)
            return False

        restored_weekend_orchestrator = None
        if weekend_state:
            try:
                restored_weekend_orchestrator = WeekendOrchestrator.from_dict(weekend_state)
            except Exception as exc:
                logger.warning("Failed to restore weekend state for save %s: %s", save_id, exc)
                restored_weekend_orchestrator = None

        bridge_session_type = _bridge_session_type_from_weekend(
            restored_weekend_orchestrator.current_session_type if restored_weekend_orchestrator else metadata.get("session_type")
        )

        # 1. Initialize Circuit and Session Bridge
        import config
        config.set_current_circuit(circuit_id)
        
        import utils.game_logic as gl
        gl.start_session_for_circuit(session_type=bridge_session_type)
        gl.simulation_ready = True

        if restored_weekend_orchestrator is not None:
            set_weekend_orchestrator(restored_weekend_orchestrator)

        # Reconcile inventory payloads with the saved car state so older saves
        # keep the currently installed tyre set condition.
        self._merge_car_state_into_inventory_payloads(inventories_state, cars_state)

        # 2. Restore Global Game Logic State
        with gl.state_lock:
            gl.accumulated_game_time = engine_state.get("accumulated_game_time", 0.0)
            gl.game_speed_multiplier = engine_state.get("game_speed_multiplier", 1.0)
            gl.is_paused = engine_state.get("is_paused", False)
            gl.player_team_id = engine_state.get("player_team_id")
            gl.player_driver_numbers = set(engine_state.get("player_driver_numbers", []))
            gl.session_best_lap = engine_state.get("session_best_lap")
            gl.session_best_sectors = engine_state.get("session_best_sectors", gl.session_best_sectors)
            gl.last_speed_change_time = time.time()
            if gl.is_paused:
                gl.pause_start_time = time.time()
            else:
                gl.pause_start_time = None

        # 3. Restore Tyre Inventories Caches
        self._restore_tyre_inventories(self.tyre_service, inventories_state, circuit_id)

        # 4. Restore RaceCars data into existing objects
        for car_data in cars_state:
            d_num = car_data.get("driver_number")
            car = gl.get_car_by_driver_number(d_num)
            if car:
                car.load_state(car_data)

        # 5. Restore SessionBridge dynamic state
        bridge = gl.get_session_bridge()
        if bridge:
            # We must restore the PSO if we have it
            if pso_state:
                from lap_simulator.practice_session import PracticeSessionOrchestrator
                bridge.pso = PracticeSessionOrchestrator.from_dict(pso_state)

            self._restore_tyre_inventories(getattr(bridge, "tyre_inventory_service", None), inventories_state, circuit_id)
            
            # Load the sub-state (track states, accumulated time, AI engines, etc.)
            bridge_state = data.get("bridge_state")
            if bridge_state:
                bridge.load_session_state(bridge_state)
            
            # Sync bridge state back to cars if needed
            bridge.active = True
            logger.info("SessionBridge restored: active=%s, time=%.1f, engines=%d", 
                        bridge.active, bridge._accumulated_time_s, len(bridge.ai_engines))
        
        logger.info("Game '%s' (ID: %s) loaded successfully for circuit %s", 
                    metadata.get("name", "Unknown"), save_id, circuit_id)
        return {
            "success": True,
            "circuit_id": circuit_id
        }
