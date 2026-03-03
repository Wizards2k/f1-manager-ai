#!/usr/bin/env python3
"""
Physics watchdog CLI: runs a regression lap on selected circuits and fails if the
simulated lap time drifts beyond thresholds vs reference telemetry.

Usage:
    python tools/watchdog.py \
        --manifest config/calibration/manifest.json \
        --max-delta-pct 1.0 \
        --max-delta-s 0.5

Exit code: 0 if all circuits within thresholds, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# Add python_backend to path
ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "python_backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from lap_simulator.config_loader import load_circuit_config  # type: ignore
from lap_simulator.lap_simulator import LapSimulator  # type: ignore
from lap_simulator.data_types import EnvContext  # type: ignore
from scripts.physics_validator import get_baseline_entry  # type: ignore


@dataclass
class Entry:
    circuit_id: str
    year: int = 2025
    max_delta_pct: Optional[float] = None
    max_delta_s: Optional[float] = None


def parse_manifest(path: Path) -> List[Entry]:
    data = json.loads(path.read_text())
    circuits = data.get("circuits") if isinstance(data, dict) else data
    if not isinstance(circuits, list):
        raise ValueError("Manifest must be a list or contain a 'circuits' list")
    entries: List[Entry] = []
    for item in circuits:
        if not isinstance(item, dict):
            continue
        cid = item.get("id") or item.get("circuit_id")
        year = item.get("year", 2025)
        entries.append(
            Entry(
                circuit_id=cid,
                year=year,
                max_delta_pct=item.get("max_delta_pct"),
                max_delta_s=item.get("max_delta_s"),
            )
        )
    if not entries:
        raise ValueError("Manifest empty or invalid")
    return entries


def run_entry(entry: Entry, default_max_pct: float, default_max_s: float):
    config = load_circuit_config(entry.circuit_id, entry.year)
    env = EnvContext()
    sim = LapSimulator(config, env)
    car_entry = get_baseline_entry(entry.circuit_id)
    sim.register_car(car_entry)
    res = sim.run_lap()["BASE"]

    ref_time = sum(s.dt_ref_s for s in config.sections)
    sim_time = res.lap_time_s
    delta = sim_time - ref_time
    pct = (delta / ref_time * 100.0) if ref_time > 0 else 0.0

    max_pct = entry.max_delta_pct if entry.max_delta_pct is not None else default_max_pct
    max_s = entry.max_delta_s if entry.max_delta_s is not None else default_max_s
    ok = abs(pct) <= max_pct and abs(delta) <= max_s

    return {
        "circuit": entry.circuit_id,
        "year": entry.year,
        "sim_time_s": sim_time,
        "ref_time_s": ref_time,
        "delta_s": delta,
        "delta_pct": pct,
        "max_delta_s": max_s,
        "max_delta_pct": max_pct,
        "ok": ok,
    }


def main():
    parser = argparse.ArgumentParser(description="Physics watchdog (sim vs telemetry)")
    parser.add_argument("--manifest", type=Path, required=True, help="Path to calibration manifest JSON")
    parser.add_argument("--max-delta-pct", type=float, default=1.0, help="Max allowed delta percent")
    parser.add_argument("--max-delta-s", type=float, default=0.5, help="Max allowed delta seconds")
    parser.add_argument("--output", type=Path, help="Optional JSON report output path")
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"Manifest not found: {args.manifest}", file=sys.stderr)
        return 1

    try:
        entries = parse_manifest(args.manifest)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Invalid manifest: {exc}", file=sys.stderr)
        return 1

    results = []
    failed = False
    for entry in entries:
        try:
            res = run_entry(entry, args.max_delta_pct, args.max_delta_s)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"ERROR {entry.circuit_id}: {exc}", file=sys.stderr)
            failed = True
            continue
        results.append(res)
        status = "OK" if res["ok"] else "FAIL"
        print(
            f"{status:<4} {res['circuit']:<22} sim={res['sim_time_s']:.3f}s ref={res['ref_time_s']:.3f}s "
            f"Δ={res['delta_s']:+.3f}s ({res['delta_pct']:+.2f}%) limits [{res['max_delta_s']:.3f}s, {res['max_delta_pct']:.2f}%]"
        )
        if not res["ok"]:
            failed = True

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"results": results}, indent=2))

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
