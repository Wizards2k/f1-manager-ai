#!/usr/bin/env python3
"""CLI per eseguire sweep multi-circuito sul bonus ERS."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ers_validation_utils import (
    DEFAULT_CIRCUITS,
    DEFAULT_PUSH_LEVELS,
    format_validation_report,
    run_validation,
    write_json_report,
)


def parse_float_list(raw: str) -> List[float]:
    return [float(token.strip()) for token in raw.split(",") if token.strip()]


def parse_str_list(raw: str) -> List[str]:
    return [token.strip() for token in raw.split(",") if token.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep ERS bonus su più circuiti")
    parser.add_argument(
        "--circuits",
        default=",".join(DEFAULT_CIRCUITS),
        help="Lista di circuiti separati da virgola",
    )
    parser.add_argument(
        "--maps",
        default="STANDARD",
        help="Lista di mappe engine separata da virgola (default: STANDARD)",
    )
    parser.add_argument(
        "--push-levels",
        default=",".join(f"{lvl:.2f}" for lvl in DEFAULT_PUSH_LEVELS),
        help="Lista di push level separata da virgola (es. '0.90,1.00,1.10')",
    )
    parser.add_argument("--laps", type=int, default=1, help="Numero di giri per combinazione")
    parser.add_argument("--compare-off", action="store_true", help="Confronta sempre con ERS off")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Percorso custom del project root",
    )
    parser.add_argument("--json-out", type=Path, default=None, help="Percorso JSON per risultati completi")
    parser.add_argument("--csv-out", type=Path, default=None, help="Percorso CSV per tabella sintetica")
    parser.add_argument(
        "--fail-on-check",
        action="store_true",
        help="Exit code 1 se un check fallisce",
    )
    return parser.parse_args()


def summarize_row(result: Dict[str, any]) -> Dict[str, any]:
    summary = result["lap_summary"]
    row = {
        "circuit_id": result["circuit_id"],
        "circuit_name": result["circuit_name"],
        "map": result["map"],
        "push_level": result["push_level"],
        "lap_time_s": summary["lap_time_s"],
        "total_ers_bonus_s": summary["total_ers_bonus_s"],
        "deploy_mj": summary["deploy_mj"],
        "mguh_direct_mj": summary["mguh_direct_mj"],
        "straight_sections": summary["straight_sections"],
        "clamp_hits": summary["clamp_hits"],
        "clamp_ratio": summary["clamp_hits"] / summary["straight_sections"] if summary["straight_sections"] else 0.0,
        "checks_failed": sum(1 for c in result["checks"] if not c["ok"]),
    }
    if result.get("ers_off"):
        cmp_block = result["ers_off"]
        row.update(
            {
                "ers_off_lap_time_s": cmp_block["lap_time_s"],
                "delta_on_minus_off_s": cmp_block["lap_delta_s"],
                "delta_pct": cmp_block["lap_delta_pct"],
            }
        )
    return row


def write_csv(rows: List[Dict[str, any]], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    circuits = parse_str_list(args.circuits)
    maps = parse_str_list(args.maps)
    push_levels = parse_float_list(args.push_levels)

    results: List[Dict[str, any]] = []
    rows: List[Dict[str, any]] = []
    failed_checks = 0

    for circuit in circuits:
        for map_name in maps:
            for push_level in push_levels:
                result = run_validation(
                    circuit_id=circuit,
                    map_name=map_name,
                    push_level=push_level,
                    laps=args.laps,
                    compare_ers_off=args.compare_off,
                    project_root=args.project_root,
                )
                print(format_validation_report(result))
                print("=" * 60)
                results.append(result)
                rows.append(summarize_row(result))
                failed_checks += sum(1 for c in result["checks"] if not c["ok"])

    if args.json_out:
        write_json_report({"results": results}, args.json_out.expanduser().resolve())
    if args.csv_out:
        write_csv(rows, args.csv_out.expanduser().resolve())

    if args.fail_on_check and failed_checks:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
