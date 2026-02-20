#!/usr/bin/env python3
"""Batch builder: scarica e rigenera la telemetria Q3 2025 per tutti i 24 circuiti.

Uso:
    python3 scripts/batch_build_all_circuits.py
    python3 scripts/batch_build_all_circuits.py --year 2025 --dry-run
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Mapping: circuit_id → FastF1 event name (2025 calendar)
# ---------------------------------------------------------------------------
CIRCUITS = [
    ("bh-2002_sakhir",           "Bahrain"),
    ("sa-2021_jeddah",           "Saudi Arabia"),
    ("au-1953_melbourne",        "Australia"),
    ("jp-1962_suzuka",           "Japan"),
    ("cn-2004_shanghai",         "China"),
    ("us-2022_miami",            "Miami"),
    ("it-1953_imola",            "Emilia Romagna"),
    ("mc-1929_monaco",           "Monaco"),
    ("es-1991_barcelona",        "Spain"),
    ("ca-1978_montreal",         "Canada"),
    ("at-1969_spielberg",        "Austria"),
    ("gb-1948_silverstone",      "Great Britain"),
    ("be-1925_spa_francorchamps","Belgium"),
    ("hu-1986_budapest",         "Hungary"),
    ("nl-1948_zandvoort",        "Netherlands"),
    ("it-1922_monza",            "Italy"),
    ("az-2016_baku",             "Azerbaijan"),
    ("sg-2008_singapore",        "Singapore"),
    ("us-2012_austin",           "United States"),
    ("mx-1962_mexico_city",      "Mexico"),
    ("br-1940_sao_paulo",        "Brazil"),
    ("us-2023_las_vegas",        "Las Vegas"),
    ("qa-2004_lusail",           "Qatar"),
    ("ae-2009_yas_marina",       "Abu Dhabi"),
]

SCRIPTS_DIR = Path(__file__).resolve().parent


def run_circuit(year: int, circuit_id: str, event: str, dry_run: bool) -> bool:
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "fastf1_build_assets.py"),
        "--year", str(year),
        "--event", event,
        "--session", "Q",
        "--circuit-id", circuit_id,
    ]
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}▶  {circuit_id}  ({event} {year})")
    if dry_run:
        print("   CMD:", " ".join(cmd))
        return True

    result = subprocess.run(cmd, cwd=SCRIPTS_DIR.parent, capture_output=False)
    if result.returncode != 0:
        print(f"   ❌ FAILED (exit {result.returncode})")
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--dry-run", action="store_true", help="Mostra i comandi senza eseguirli")
    parser.add_argument("--only", help="Esegui solo questo circuit_id (debug)")
    args = parser.parse_args()

    circuits = CIRCUITS
    if args.only:
        circuits = [(cid, ev) for cid, ev in CIRCUITS if cid == args.only]
        if not circuits:
            print(f"Circuit ID '{args.only}' non trovato nella lista.")
            sys.exit(1)

    ok = 0
    failed = []
    total = len(circuits)

    for i, (circuit_id, event) in enumerate(circuits, 1):
        print(f"\n[{i}/{total}]", end="")
        success = run_circuit(args.year, circuit_id, event, args.dry_run)
        if success:
            ok += 1
        else:
            failed.append(circuit_id)

    print(f"\n{'='*60}")
    print(f"Completati: {ok}/{total}")
    if failed:
        print(f"Falliti ({len(failed)}): {', '.join(failed)}")
    else:
        print("Tutti i circuiti generati con successo!")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
