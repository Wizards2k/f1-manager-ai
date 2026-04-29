"""
StateAdapter — Traduzione stato tra CarState (V1 Bridge) e PhysicsState (V6 engine).

Usato da update_section_v6.py per:
  - init: CarState → PhysicsState (prima sezione del stint)
  - sync: PhysicsState → CarState (dopo ogni sezione completata)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from lap_simulator.data_types import CarState
    from lap_simulator.physics_engine.integrator.state import PhysicsState

# Mapping WheelPosition (V1: LF/RF/LR/RR) → TiresState attr (V6: fl/fr/rl/rr)
_WHEEL_TO_TIRE = {
    "LF": "fl",
    "RF": "fr",
    "LR": "rl",
    "RR": "rr",
}


class StateAdapter:
    """Traduce stato tra CarState (Bridge V1) e PhysicsState (V6 engine)."""

    @staticmethod
    def car_state_to_physics_state(car_state: "CarState", physics_state: "PhysicsState") -> None:
        """Sync V1 → V6. Chiamato SOLO alla prima sezione del stint (init).

        Non chiamare a ogni sezione: PhysicsState porta avanti i propri valori.
        """
        physics_state.velocity_ms = max(1.0, getattr(car_state, "v_current_ms", 0.0))

        tyres = getattr(car_state, "tyres", {}) or {}
        for wp_value, tire_attr in _WHEEL_TO_TIRE.items():
            tyre = None
            # WheelPosition is a str Enum — try by value
            for key, val in tyres.items():
                key_val = key.value if hasattr(key, "value") else str(key)
                if key_val == wp_value:
                    tyre = val
                    break
            if tyre is None:
                continue
            tire_state = getattr(physics_state.tires_state, tire_attr, None)
            if tire_state is None:
                continue
            tire_state.surface_temp_c = getattr(tyre, "surface_temp_c", 85.0)
            tire_state.core_temp_c = getattr(tyre, "core_temp_c", 75.0)
            tire_state.wear_pct = getattr(tyre, "wear_pct", 0.0)

        brakes = getattr(car_state, "brakes", None)
        if brakes is not None and physics_state.brake_state is not None:
            physics_state.brake_state.temp_front_c = getattr(brakes, "temp_front_c", 20.0)
            physics_state.brake_state.temp_rear_c = getattr(brakes, "temp_rear_c", 20.0)

    @staticmethod
    def physics_state_to_car_state(physics_state: "PhysicsState", car_state: "CarState") -> None:
        """Sync V6 → V1. Chiamato dopo ogni sezione completata."""
        car_state.v_current_ms = physics_state.velocity_ms

        tyres = getattr(car_state, "tyres", {}) or {}
        tires_state = getattr(physics_state, "tires_state", None)
        if tires_state is not None:
            for wp_value, tire_attr in _WHEEL_TO_TIRE.items():
                tyre = None
                for key, val in tyres.items():
                    key_val = key.value if hasattr(key, "value") else str(key)
                    if key_val == wp_value:
                        tyre = val
                        break
                if tyre is None:
                    continue
                tire_state = getattr(tires_state, tire_attr, None)
                if tire_state is None:
                    continue
                tyre.surface_temp_c = tire_state.surface_temp_c
                tyre.core_temp_c = tire_state.core_temp_c
                tyre.wear_pct = tire_state.wear_pct

        brake_state = getattr(physics_state, "brake_state", None)
        brakes = getattr(car_state, "brakes", None)
        if brake_state is not None and brakes is not None:
            brakes.temp_front_c = brake_state.temp_front_c
            brakes.temp_rear_c = brake_state.temp_rear_c
            brakes.fade_level = getattr(physics_state, "brake_fade_factor", 0.0)

    @staticmethod
    def apply_pit_stop_reset(physics_state: "PhysicsState", new_compound: str) -> None:
        """Reset parziale dopo pit stop: nuove gomme fresche."""
        tires_state = getattr(physics_state, "tires_state", None)
        if tires_state is None:
            return
        for attr in ("fl", "fr", "rl", "rr"):
            tire = getattr(tires_state, attr, None)
            if tire is not None:
                tire.surface_temp_c = 85.0
                tire.core_temp_c = 75.0
                tire.wear_pct = 0.0
        brake_state = getattr(physics_state, "brake_state", None)
        if brake_state is not None:
            brake_state.temp_front_c = 20.0
            brake_state.temp_rear_c = 20.0
