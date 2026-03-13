#!/usr/bin/env python3
"""Run LapSimulator from a custom scenario snapshot without touching main scripts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
python_backend = REPO_ROOT / "python_backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
if str(python_backend) not in sys.path:
    sys.path.append(str(python_backend))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from lap_simulator.config_loader import load_circuit_config  # type: ignore  # noqa: E402
from lap_simulator.data_types import TyreCompound  # type: ignore  # noqa: E402
from lap_simulator.lap_simulator import LapSimulator  # type: ignore  # noqa: E402
from python_backend.utils.tyre_debug_logger import is_tyre_debug_enabled, reset_tyre_debug_log  # type: ignore  # noqa: E402

from entry_loader import load_scenario  # type: ignore  # noqa: E402


GAME_SEND_OUT_TYRE_TEMPS_C = {
    "SOFT": 98.5,
    "MEDIUM": 94.5,
    "HARD": 90.5,
}


def _compound_to_game_family(compound: TyreCompound) -> str:
    if compound in {TyreCompound.C5, TyreCompound.C6}:
        return "SOFT"
    if compound in {TyreCompound.C3, TyreCompound.C4}:
        return "MEDIUM"
    if compound in {TyreCompound.C1, TyreCompound.C2}:
        return "HARD"
    return "MEDIUM"


def _game_send_out_tyre_temp_c(compound: TyreCompound) -> float:
    return GAME_SEND_OUT_TYRE_TEMPS_C[_compound_to_game_family(compound)]


def _format_events(events: Dict[str, Any]) -> str:
    if not events:
        return "-"
    return ", ".join(f"{k}:{v}" for k, v in events.items())


def run() -> None:
    parser = argparse.ArgumentParser(description="Run custom LapSimulator scenario")
    parser.add_argument("--snapshot", required=True, help="Path to scenario JSON (sim_scenario_XX)")
    parser.add_argument("--circuit", required=True, help="Circuit ID (e.g. jp-1962_suzuka)")
    parser.add_argument("--laps", type=int, default=1, help="Number of consecutive laps to run")
    parser.add_argument("--push", type=float, help="Override push level from snapshot")
    parser.add_argument("--fuel", type=float, help="Override starting fuel load from snapshot")
    parser.add_argument("--compound", help="Override tyre compound for all four wheels (e.g. C1, C3, C5)")
    parser.add_argument("--config-year", type=int, default=2025, help="Telemetry/config season to load")
    parser.add_argument(
        "--output-json",
        help="Optional path to dump LapResult summary as JSON (for later analysis)",
    )
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    env, car_entry, meta = load_scenario(snapshot_path)
    if args.push is not None:
        car_entry.push_level = args.push
    if args.fuel is not None:
        car_entry.state.pu.fuel_kg = args.fuel
    if args.compound is not None:
        compound = TyreCompound[str(args.compound).upper()]
        tyre_temp_c = _game_send_out_tyre_temp_c(compound)
        for tyre in car_entry.state.tyres.values():
            tyre.compound = compound
            tyre.surface_temp_c = tyre_temp_c
            tyre.core_temp_c = tyre_temp_c

    if is_tyre_debug_enabled():
        reset_tyre_debug_log()

    config = load_circuit_config(args.circuit, args.config_year)
    sim = LapSimulator(config, env)
    sim.register_car(car_entry)

    results = sim.run_laps(max(1, args.laps))
    laps = results[car_entry.car_id]

    print("=" * 80)
    print(f"Scenario: {meta.get('name', snapshot_path.name)} | Car: {car_entry.car_id}")
    print(f"Circuit: {config.circuit_name} ({args.circuit}) | Laps: {len(laps)} | Push: {car_entry.push_level}")
    print("=" * 80)
    for idx, lap in enumerate(laps, start=1):
        sectors = ", ".join(f"{s:.3f}" for s in lap.sector_times_s)
        print(f"Lap {idx:02d}: {lap.lap_time_s:.3f}s | Sectors [{sectors}]")
        print(
            f"  Fuel {lap.fuel_kg:.2f} kg | ERS {lap.ers_energy_mj:.2f} MJ | Avg tyre T {lap.avg_tyre_temp_surface_c:.1f} °C | Avg wear {lap.avg_tyre_wear_pct:.1f}%"
        )
        if lap.events:
            unique_events = {}
            for evt in lap.events:
                unique_events.setdefault(evt.event_type, 0)
                unique_events[evt.event_type] += 1
            print(f"  Events: {_format_events(unique_events)}")
        if lap.section_results:
            hot = [res for res in lap.section_results if any(evt.event_type == "tyre_overheat" for evt in res.events)]
            if hot:
                ids = ", ".join(config.sections[i].section_id for i, res in enumerate(lap.section_results) if res in hot)
                print(f"  Tyre overheat sections: {ids}")
        print("-" * 80)

    if args.output_json:
        payload = {
            "scenario": meta,
            "car_id": car_entry.car_id,
            "circuit": args.circuit,
            "push_level": car_entry.push_level,
            "laps": [
                {
                    "lap_number": lap.lap_number,
                    "lap_time_s": lap.lap_time_s,
                    "sector_times_s": lap.sector_times_s,
                    "avg_tyre_temp_surface_c": lap.avg_tyre_temp_surface_c,
                    "avg_tyre_wear_pct": lap.avg_tyre_wear_pct,
                    "fuel_kg": lap.fuel_kg,
                    "ers_energy_mj": lap.ers_energy_mj,
                    "events": [evt.event_type for evt in lap.events],
                }
                for lap in laps
            ],
        }
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Lap summary written to {out_path}")


if __name__ == "__main__":
    run()
