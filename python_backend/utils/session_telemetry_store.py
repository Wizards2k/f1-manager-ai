from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional


@dataclass
class SessionTelemetryStore:
    circuit_id: Optional[str] = None
    session_id: str = "current"
    max_laps_per_car: int = 8
    _laps_by_car: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def reset(self, circuit_id: Optional[str] = None, session_id: str = "current") -> None:
        self.circuit_id = circuit_id
        self.session_id = session_id
        self._laps_by_car.clear()

    def append_lap(
        self,
        car_id: str,
        lap_number: int,
        lap_time_s: float,
        lap_phase: str,
        is_competitive: bool,
        points: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        lap_payload = {
            "car_id": str(car_id),
            "lap_number": lap_number,
            "lap_time_s": round(float(lap_time_s), 3),
            "lap_phase": lap_phase,
            "is_competitive": bool(is_competitive),
            "points": list(points or []),
        }
        history = self._laps_by_car.setdefault(str(car_id), [])
        history.append(lap_payload)
        
        # DEBUG: Log telemetry storage to dedicated file
        if is_competitive:
            import os
            import json
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'telemetry_debug.log')
            sample = points[:3] if points else []
            with open(log_file, 'a') as f:
                f.write(f"LAP_COMPLETE car={car_id} lap={lap_number} time={lap_time_s:.3f} competitive={is_competitive} points_count={len(points)} sample={json.dumps(sample)}\n")
        if len(history) > self.max_laps_per_car:
            competitive_with_points = [
                item for item in history
                if item.get("is_competitive") and (item.get("points") or []) and item.get("lap_time_s") is not None
            ]
            protected_best = None
            if competitive_with_points:
                protected_best = min(competitive_with_points, key=lambda item: item.get("lap_time_s", float("inf")))

            trimmed = history[-self.max_laps_per_car:]
            if protected_best and all(item is not protected_best for item in trimmed):
                trimmed = trimmed[1:] + [protected_best]
                trimmed.sort(key=lambda item: item.get("lap_number", 0))
            history[:] = trimmed
        return lap_payload

    def get_history(self, car_id: str) -> List[Dict[str, Any]]:
        return list(self._laps_by_car.get(str(car_id), []))

    def get_lap(self, car_id: str, lap: str = "latest") -> Dict[str, Any]:
        history = self._laps_by_car.get(str(car_id), [])
        if not history:
            return {}

        if lap == "latest":
            return history[-1]
        if lap == "best":
            competitive = [item for item in history if item.get("is_competitive")]
            if not competitive:
                return {}
            return min(competitive, key=lambda item: item.get("lap_time_s", float("inf")))
        try:
            lap_number = int(lap)
        except (TypeError, ValueError):
            return history[-1]
        return next((item for item in history if item.get("lap_number") == lap_number), history[-1])

    def _get_best_competitive_lap_time(self) -> Optional[float]:
        best_time: Optional[float] = None
        for history in self._laps_by_car.values():
            for lap in history:
                if not lap.get("is_competitive"):
                    continue
                lap_time = lap.get("lap_time_s")
                if lap_time is None:
                    continue
                if best_time is None or lap_time < best_time:
                    best_time = float(lap_time)
        return best_time

    def _project_points_for_ui(self, points: List[Dict[str, Any]], lap_time_s: Optional[float], best_lap_time_s: Optional[float] = None) -> List[Dict[str, Any]]:
        if not points:
            return []
        raw_total_dt = sum(max(0.0, float(point.get("dt_s", 0.0) or 0.0)) for point in points)
        if raw_total_dt <= 0 or not lap_time_s or lap_time_s <= 0:
            return [dict(point) for point in points]

        base_ratio = max(0.75, min(1.08, raw_total_dt / float(lap_time_s)))
        relative_best_ratio = 1.0
        if best_lap_time_s and best_lap_time_s > 0:
            relative_best_ratio = max(1.0, float(lap_time_s) / float(best_lap_time_s))

        projected: List[Dict[str, Any]] = []
        for point in points:
            projected_point = dict(point)
            speed_kph = float(point.get("speed_kph", 0.0) or 0.0)
            throttle = max(0.0, min(100.0, float(point.get("throttle_pct", 0.0) or 0.0))) / 100.0
            brake = max(0.0, min(100.0, float(point.get("brake_pct", 0.0) or 0.0))) / 100.0
            corner_weight = max(brake, 1.0 - throttle)
            technical_weight = max(corner_weight, min(1.0, abs(float(point.get("target_g_lat", 0.0) or 0.0)) / 4.5))
            lap_delta_ratio = min(0.12, max(0.0, relative_best_ratio - 1.0))
            straight_weight = 1.0 - technical_weight

            if base_ratio < 1.0:
                local_ratio = base_ratio - ((1.0 - base_ratio) * (0.55 + 1.10 * technical_weight))
            else:
                local_ratio = base_ratio + ((base_ratio - 1.0) * (0.18 * throttle + 0.06 * straight_weight))

            if lap_delta_ratio > 0:
                local_ratio -= lap_delta_ratio * (0.22 + 1.18 * technical_weight)
                if throttle > 0.92 and brake < 0.01:
                    local_ratio -= lap_delta_ratio * 0.04

            local_ratio = max(0.54, min(1.10, local_ratio))
            projected_point["speed_kph"] = round(speed_kph * local_ratio, 3)

            point_dt = float(point.get("dt_s", 0.0) or 0.0)
            if point_dt > 0:
                dt_ratio = max(0.82, min(1.65, 1.0 / max(local_ratio, 0.01)))
                projected_point["dt_s"] = round(point_dt * dt_ratio, 4)

            steering = abs(float(point.get("steering_angle_deg", 0.0) or 0.0))
            if steering > 0 and local_ratio < 1.0:
                projected_point["steering_angle_deg"] = round(math.copysign(steering * (1.0 + (1.0 - local_ratio) * 0.18), float(point.get("steering_angle_deg", 0.0) or 0.0)), 3)

            projected.append(projected_point)
        return projected

    def build_trace_payload(self, car_id: str, lap: str = "latest") -> Dict[str, Any]:
        selected = self.get_lap(car_id, lap=lap)
        if not selected:
            return {}
        best_lap_time_s = self._get_best_competitive_lap_time()
        return {
            "car_id": str(car_id),
            "lap_number": selected.get("lap_number"),
            "lap_time_s": selected.get("lap_time_s"),
            "lap_phase": selected.get("lap_phase"),
            "is_competitive": selected.get("is_competitive", False),
            "points": self._project_points_for_ui(selected.get("points", []), selected.get("lap_time_s"), best_lap_time_s),
        }

    def build_session_best_trace(self) -> Dict[str, Any]:
        best_entry: Optional[Dict[str, Any]] = None
        best_car: Optional[str] = None
        best_time = float("inf")
        for car_id, history in self._laps_by_car.items():
            for lap in history:
                lap_time = lap.get("lap_time_s")
                if lap_time is None or not lap.get("is_competitive"):
                    continue
                if lap_time < best_time and (lap.get("points") or []):
                    best_time = lap_time
                    best_entry = lap
                    best_car = str(car_id)

        if not best_entry or best_car is None:
            return {}

        best_lap_time_s = self._get_best_competitive_lap_time()
        return {
            "car_id": best_car,
            "lap_number": best_entry.get("lap_number"),
            "lap_time_s": best_entry.get("lap_time_s"),
            "lap_phase": best_entry.get("lap_phase"),
            "is_competitive": best_entry.get("is_competitive", False),
            "points": self._project_points_for_ui(best_entry.get("points", []), best_entry.get("lap_time_s"), best_lap_time_s),
        }
