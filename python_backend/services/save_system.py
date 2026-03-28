import json
import os
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from lap_simulator.practice_session import PracticeSessionOrchestrator
from utils.game_logic import (
    race_cars, get_session_bridge, get_session_telemetry_store,
    accumulated_game_time, is_paused, game_speed_multiplier,
    session_start_time, player_team_id, player_driver_numbers,
    session_best_lap, session_best_sectors
)
from services.tyre_inventory_service import TyreInventoryService

logger = logging.getLogger(__name__)

class SaveGameService:
    def __init__(self, data_root: Optional[Path] = None):
        self.base_path = data_root or Path(__file__).resolve().parents[1]
        self.save_dir = self.base_path / "saves"
        os.makedirs(self.save_dir, exist_ok=True)
        self.tyre_service = TyreInventoryService()

    def get_save_files(self) -> List[Dict[str, Any]]:
        saves = []
        for p in self.save_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    meta = data.get("metadata", {})
                    saves.append({
                        "id": p.stem,
                        "name": meta.get("name", p.stem),
                        "timestamp": meta.get("timestamp"),
                        "circuit_id": meta.get("circuit_id"),
                        "session_type": meta.get("session_type"),
                    })
            except Exception:
                continue
        return sorted(saves, key=lambda x: x.get("timestamp", ""), reverse=True)

    def save_game(self, name: str) -> str:
        bridge = get_session_bridge()
        if not bridge or not bridge.active:
            raise ValueError("No active session to save")

        timestamp = datetime.now().isoformat()
        save_id = f"save_{int(time.time())}"
        
        # 1. Metadata
        metadata = {
            "name": name,
            "timestamp": timestamp,
            "circuit_id": bridge.circuit_id,
            "session_type": bridge.pso.session_type.value if bridge.pso else "FP1",
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
        if bridge.circuit_id:
            for car in race_cars:
                driver_id = str(car.driver_number)
                inv = self.tyre_service.get_inventory(driver_id, bridge.circuit_id)
                inventories[driver_id] = inv.to_dict()

        payload = {
            "metadata": metadata,
            "engine_state": engine_state,
            "pso_state": pso_state,
            "bridge_state": bridge_state,
            "cars_state": cars_state,
            "inventories": inventories,
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
        circuit_id = metadata.get("circuit_id")

        if not circuit_id:
            logger.error("Save file %s missing circuit_id", save_id)
            return False

        # 1. Initialize Circuit and Session Bridge
        import config
        config.set_current_circuit(circuit_id)
        
        import utils.game_logic as gl
        gl.start_session_for_circuit()
        gl.simulation_ready = True

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
        for driver_id, inv_data in inventories_state.items():
            from models.tyre_inventory import DriverTyreInventory
            inv = DriverTyreInventory.from_dict(inv_data)
            key = self.tyre_service._inventory_key(driver_id, circuit_id)
            self.tyre_service._inventory_cache[key] = inv
            # Update store cache too
            store = self.tyre_service._load_store()
            store[key] = inv_data

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
