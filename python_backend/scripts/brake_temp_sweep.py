#!/usr/bin/env python3
"""Brake temperature sweep utility.

Simulates a single-car lap across one or more circuits while forcing
specific brake-duct openings, so we can compare front/rear peak
temperatures against each circuit's calibrated target/fade windows.

Usage examples
--------------
Run default sample (first few derived circuits) with min/med/max ducts::

    python brake_temp_sweep.py

Focus on a circuit list and 5 laps per configuration::

    python brake_temp_sweep.py --circuits it-1922_monza sg-2008_singapore --laps 5

Probe custom duct openings::

    python brake_temp_sweep.py --ducts 0.25 0.4 0.55 0.7

Use all derived circuits::

    python brake_temp_sweep.py --all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

# --- repo path bootstrap ----------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
PY_BACKEND = ROOT / "python_backend"
if str(PY_BACKEND) not in sys.path:
    sys.path.insert(0, str(PY_BACKEND))

from lap_simulator.config_loader import load_circuit_config  # type: ignore  # noqa: E402
from lap_simulator.data_types import (  # type: ignore  # noqa: E402
    AeroSetup,
    CarState,
    DriverSkills,
    EnvContext,
)
from lap_simulator.lap_simulator import CarEntry, LapSimulator  # type: ignore  # noqa: E402


StatusRange = Tuple[float, float]


def discover_circuits(limit: Optional[int] = 10) -> List[str]:
    """Return a sorted list of available circuit IDs (derived profiles first)."""
    derived = ROOT / "config" / "circuits" / "derived"
    telem = ROOT / "python_backend" / "data" / "circuits"

    names: List[str] = []
    if derived.exists():
        names.extend(sorted(p.name for p in derived.iterdir() if p.is_dir()))
    if not names and telem.exists():
        names.extend(
            sorted(
                p.name.rsplit("_Telemetry", 1)[0]
                for p in telem.glob("*_Telemetry.json")
            )
        )
    if limit is not None:
        return names[:limit]
    return names


def compute_target_range(config, axis: str) -> Optional[StatusRange]:
    """Replicate the frontend heuristic for optimal brake temps."""
    profile = config.brake_profile or {}
    fade_cfg = profile.get("fade_threshold", {})
    cooling_targets = profile.get("cooling_targets", {})

    if axis == "front":
        fade_default = config.brake_params.fade_threshold_front_c
        fade_limit = fade_cfg.get("front_c", fade_default)
        delta = cooling_targets.get("front_delta")
        fallback_center = fade_limit - 80.0
    else:
        fade_default = config.brake_params.fade_threshold_rear_c
        fade_limit = fade_cfg.get("rear_c", fade_default)
        delta = cooling_targets.get("rear_delta")
        fallback_center = fade_limit - 80.0

    if fade_limit is None:
        return None

    center = fallback_center
    if isinstance(delta, (int, float)):
        center += delta * 100.0
    return (center - 40.0, center + 40.0)


def fade_threshold(config, axis: str) -> float:
    profile = config.brake_profile or {}
    fade_cfg = profile.get("fade_threshold", {})
    if axis == "front":
        return fade_cfg.get("front_c", config.brake_params.fade_threshold_front_c)
    return fade_cfg.get("rear_c", config.brake_params.fade_threshold_rear_c)


def classify_temp(value: float, target: Optional[StatusRange], fade_limit: float) -> str:
    if target:
        low, high = target
        if value < low - 40.0:
            return "cold"
        if value < low:
            return "cool"
        if low <= value <= high:
            return "ok"
        if value <= high + 10.0:
            return "warm"
    if value >= fade_limit:
        return "critical"
    return "hot"


def format_range(target: Optional[StatusRange]) -> str:
    if not target:
        return "n/a"
    return f"{target[0]:.0f} – {target[1]:.0f}°C"


def run_sweep(
    circuit_id: str,
    duct_values: Sequence[float],
    laps: int,
    env: EnvContext,
) -> Tuple[List[dict], Optional[StatusRange], Optional[StatusRange], float, float]:
    config = load_circuit_config(circuit_id, project_root=ROOT)
    front_target = compute_target_range(config, "front")
    rear_target = compute_target_range(config, "rear")
    front_fade = fade_threshold(config, "front")
    rear_fade = fade_threshold(config, "rear")

    circuit_results: List[dict] = []
    for duct in duct_values:
        car_state = CarState(car_id=f"{circuit_id}_{duct:.2f}")
        car_state.brakes.duct_opening = duct
        entry = CarEntry(
            car_id=car_state.car_id,
            state=car_state,
            aero_setup=AeroSetup(),
            driver_skills=DriverSkills(),
            push_level=1.0,
        )
        sim = LapSimulator(config, env)
        sim.register_car(entry)
        for _ in range(max(1, laps)):
            sim.run_lap()
        front_temp = car_state.brakes.temp_front_c
        rear_temp = car_state.brakes.temp_rear_c
        circuit_results.append(
            {
                "duct": duct,
                "front_temp": front_temp,
                "rear_temp": rear_temp,
                "front_status": classify_temp(front_temp, front_target, front_fade),
                "rear_status": classify_temp(rear_temp, rear_target, rear_fade),
                "fade_level": car_state.brakes.fade_level,
            }
        )
    return circuit_results, front_target, rear_target, front_fade, rear_fade


def print_report(
    circuit_id: str,
    results: List[dict],
    front_target: Optional[StatusRange],
    rear_target: Optional[StatusRange],
    front_fade: float,
    rear_fade: float,
) -> None:
    print("=" * 88)
    print(f"Circuit: {circuit_id}")
    print(
        f"  Front target: {format_range(front_target)} | Fade: {front_fade:.0f}°C\n"
        f"  Rear target : {format_range(rear_target)} | Fade: {rear_fade:.0f}°C"
    )
    print("  duct  | front °C (status) | rear °C (status) | fade level")
    print("  ----- | ----------------- | ---------------- | ----------")
    for row in results:
        print(
            f"  {row['duct']:.2f}  | "
            f"{row['front_temp']:.1f} ({row['front_status']:<8}) | "
            f"{row['rear_temp']:.1f} ({row['rear_status']:<7}) | "
            f"{row['fade_level']:.3f}"
        )
    print()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Brake temperature sweep tool")
    parser.add_argument(
        "--circuits",
        nargs="*",
        default=None,
        help="Circuit IDs to simulate (defaults to first derived profiles)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run over every derived circuit (overrides --limit)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=8,
        help="Max circuits to auto-select when --circuits is omitted",
    )
    parser.add_argument(
        "--ducts",
        nargs="+",
        type=float,
        default=[0.25, 0.50, 0.75],
        help="Brake-duct openings (0-1) to sweep",
    )
    parser.add_argument(
        "--laps",
        type=int,
        default=3,
        help="Number of consecutive laps per duct setting",
    )
    parser.add_argument(
        "--air-temp",
        type=float,
        default=25.0,
        help="Ambient air temperature in °C",
    )
    parser.add_argument(
        "--track-temp",
        type=float,
        default=35.0,
        help="Track temperature in °C",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)

    if any(d < 0.0 or d > 1.0 for d in args.ducts):
        raise ValueError("All duct openings must be within [0, 1]")

    if args.circuits:
        circuits = args.circuits
    else:
        circuits = discover_circuits(limit=None if args.all else args.limit)
    if not circuits:
        raise RuntimeError("No circuits found. Pass --circuits explicitly.")

    env = EnvContext(air_temp_c=args.air_temp, track_temp_c=args.track_temp)

    for circuit_id in circuits:
        try:
            results, front_target, rear_target, front_fade, rear_fade = run_sweep(
                circuit_id=circuit_id,
                duct_values=args.ducts,
                laps=args.laps,
                env=env,
            )
        except FileNotFoundError as exc:
            print(f"[WARN] Skipping {circuit_id}: {exc}")
            continue
        print_report(
            circuit_id,
            results,
            front_target,
            rear_target,
            front_fade,
            rear_fade,
        )


if __name__ == "__main__":
    main()
