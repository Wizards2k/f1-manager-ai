#!/usr/bin/env python3
"""CLI per validare il bonus ERS su un singolo circuito."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ers_validation_utils import (
    format_validation_report,
    run_validation,
    write_json_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida il bonus ERS su un circuito")
    parser.add_argument("--circuit", default="it-1922_monza", help="ID telemetry del circuito")
    parser.add_argument("--map", default="STANDARD", help="Engine map da usare (default: STANDARD)")
    parser.add_argument("--push-level", type=float, default=1.0, help="Comando push (0.8 conserve → 1.15 attack)")
    parser.add_argument("--laps", type=int, default=1, help="Numero di giri da simulare (default: 1)")
    parser.add_argument("--compare-off", action="store_true", help="Esegue anche un run con ERS disabilitato")
    parser.add_argument("--tolerance", type=float, default=5e-5, help="Tolleranza numerica per gli assert (default: 5e-5)")
    parser.add_argument("--project-root", type=Path, default=None, help="Percorso custom del project root")
    parser.add_argument("--json-out", type=Path, default=None, help="Se impostato salva il report completo in JSON")
    parser.add_argument(
        "--fail-on-check",
        action="store_true",
        help="Restituisce exit code 1 se almeno un check fallisce",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_validation(
        circuit_id=args.circuit,
        map_name=args.map,
        push_level=args.push_level,
        laps=args.laps,
        compare_ers_off=args.compare_off,
        tolerance=args.tolerance,
        project_root=args.project_root,
    )
    print(format_validation_report(result))

    if args.json_out:
        write_json_report(result, args.json_out.expanduser().resolve())

    failed = [check for check in result["checks"] if not check["ok"]]
    if args.fail_on_check and failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
