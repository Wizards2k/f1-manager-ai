#!/usr/bin/env python3
"""FastF1-powered asset builder.

Scarica una sessione FastF1 (anno/evento/sessione), seleziona il lap di riferimento,
produce il file `python_backend/data/circuits/<circuit_id>_Telemetry.json`
riutilizzando `regenerate_telemetry_sections.py` per calcolare i segmenti.

⚠️ Questo script è pensato per uso offline/manuale (non in-game):
- richiede il pacchetto `fastf1` e una connessione per il primo download;
- salva una cache locale (default `python_backend/.fastf1_cache`).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import fastf1
    from fastf1.core import Laps
except ImportError as exc:  # pragma: no cover
    fastf1 = None  # type: ignore

from regenerate_telemetry_sections import (  # type: ignore
    apply_to_telemetry,
    regenerate_sections,
)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True, help="Anno della stagione (es. 2025)")
    parser.add_argument("--event", required=True, help="Nome evento (es. 'Abu Dhabi' o round number)")
    parser.add_argument("--session", default="Q", help="Tipo sessione FastF1 (FP1/FP2/FP3/Q/R)")
    parser.add_argument("--circuit-id", required=True, help="Circuit ID target (es. ae-2009_yas_marina)")
    parser.add_argument("--driver", help="Driver code/number (es. VER). Default: fastest lap overall")
    parser.add_argument("--lap-number", type=int, help="Lap specifico se noto")
    parser.add_argument(
        "--output-dir",
        default="python_backend/data/circuits",
        help="Directory radice dei Telemetry JSON. Lo script crea una sottocartella per anno (es. data/circuits/2024).",
    )
    parser.add_argument(
        "--cache-dir",
        default="python_backend/.fastf1_cache",
        help="Cartella cache FastF1 (verrà creata se non esiste)",
    )
    parser.add_argument(
        "--manifest",
        help="Percorso manifest (per default viene creato nella cartella dell'anno)",
    )
    parser.add_argument(
        "--skip-derived",
        action="store_true",
        help="Non lanciare eventuali hook per rigenerare i profili derived",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scarica e mostra i dettagli ma non scrive file",
    )
    return parser


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ManifestEntry:
    circuit_id: str
    year: int
    event: str
    session: str
    driver: str
    lap_number: int
    lap_time_s: float
    source: str = "fastf1"
    generated_at: str = datetime.utcnow().isoformat() + "Z"


# ---------------------------------------------------------------------------
# FastF1 helpers
# ---------------------------------------------------------------------------


def ensure_fastf1(cache_dir: Path) -> None:
    if fastf1 is None:
        print("❌ Il pacchetto fastf1 non è installato. Esegui `pip install fastf1`.", file=sys.stderr)
        sys.exit(1)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)


def load_session(year: int, event: str, session_name: str):
    session = fastf1.get_session(year, event, session_name)
    session.load()
    return session


def pick_lap(session, driver: Optional[str], lap_number: Optional[int]):
    laps: Laps = session.laps
    if driver:
        laps = laps.pick_driver(driver)
    if lap_number is not None:
        lap = laps.loc[laps["LapNumber"] == lap_number]
        if lap.empty:
            raise ValueError(f"Lap {lap_number} non trovato per driver={driver or 'ALL'}")
        return lap.iloc[0]
    # Default: fastest lap (per driver se filtrato, altrimenti assoluto)
    fastest = laps.pick_fastest()
    if fastest is None:
        raise ValueError("Nessun lap valido nella sessione selezionata")
    return fastest


def telemetry_points_from_lap(lap) -> Dict[str, Any]:
    telemetry = lap.get_telemetry()
    telemetry = telemetry.add_distance()
    telemetry = telemetry.reset_index(drop=True)

    points = []
    for idx, row in telemetry.iterrows():
        dist = float(row.get("Distance", 0.0))
        speed = float(row.get("Speed", 0.0))
        timestamp = row.get("Time")
        timestamp_s = float(timestamp.total_seconds()) if timestamp is not None else float(idx)
        points.append(
            {
                "idx": idx,
                "distance": max(0.0, dist),
                "speed": speed,
                "timestamp": timestamp_s,
                "throttle": float(row.get("Throttle", 0.0) or 0.0),
                "brake": float(row.get("Brake", 0.0) or 0.0),
                "gear": int(row.get("nGear", 0) or 0),
                "drs": int(row.get("DRS", 0) or 0),
                "x": float(row.get("X", 0.0) or 0.0),
                "y": float(row.get("Y", 0.0) or 0.0),
            }
        )
    lap_time = lap["LapTime"]
    lap_time_s = float(lap_time.total_seconds()) if lap_time is not None else sum(p["distance"] for p in points) / 300.0
    return {
        "driver": lap.get("Driver", "UNKNOWN"),
        "lap_number": int(lap.get("LapNumber", 0) or 0),
        "team": lap.get("Team", ""),
        "compound": lap.get("Compound", ""),
        "lap_time": lap_time_s,
        "telemetry_points": points,
    }


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def build_telemetry_payload(
    session,
    circuit_id: str,
    reference_lap: Dict[str, Any],
    season_year: int,
) -> Dict[str, Any]:
    circuit_info = session.get_circuit_info()
    circuit_name = getattr(circuit_info, "name", None) or session.event.get("EventName", circuit_id)
    pit_lane_time = getattr(circuit_info, "pit_lane_time", None)
    drs_zones = getattr(circuit_info, "drs_zones", None) or []
    circuit_length = getattr(circuit_info, "length", None)

    payload: Dict[str, Any] = {
        "metadata": {
            "circuit_id": circuit_id,
            "circuit_name": circuit_name,
            "year": session.event.get("Year", season_year),
            "session_type": session.name,
            "description": "auto_generated",
            "pit_lane_time": pit_lane_time,
            "drs_zones": drs_zones,
        },
        "geometry": {
            "circuit_length": float(circuit_length)
            if circuit_length
            else float(reference_lap["telemetry_points"][-1]["distance"]),
            "sections": [],
        },
        "reference_lap": reference_lap,
    }
    return payload


def write_manifest(manifest_path: Path, entry: ManifestEntry) -> None:
    manifest_data: Dict[str, Any]
    if manifest_path.exists():
        manifest_data = json.loads(manifest_path.read_text())
    else:
        manifest_data = {}
    manifest_data.setdefault(entry.circuit_id, []).append(asdict(entry))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def main():
    parser = build_parser()
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    output_root = Path(args.output_dir)
    year_dir = output_root / str(args.year)
    year_dir.mkdir(parents=True, exist_ok=True)

    if args.manifest:
        manifest_path = Path(args.manifest)
    else:
        manifest_path = year_dir / "manifest.json"

    ensure_fastf1(cache_dir)

    print(f"⚙️  Scarico sessione FastF1 {args.year} {args.event} {args.session}…")
    session = load_session(args.year, args.event, args.session)

    lap = pick_lap(session, args.driver, args.lap_number)
    reference_lap = telemetry_points_from_lap(lap)

    payload = build_telemetry_payload(session, args.circuit_id, reference_lap, args.year)

    sections, errors = regenerate_sections(payload)
    if errors:
        print("❌ Validazione sezioni fallita:")
        for err in errors:
            print(f"   - {err}")
        sys.exit(2)

    payload = apply_to_telemetry(payload, sections)

    output_path = year_dir / f"{args.circuit_id}_Telemetry.json"
    if args.dry_run:
        print("Dry-run attivo: non scrivo il file Telemetry né aggiorno il manifest.")
    else:
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"💾 File aggiornato: {output_path}")
        entry = ManifestEntry(
            circuit_id=args.circuit_id,
            year=args.year,
            event=str(args.event),
            session=args.session,
            driver=str(reference_lap.get("driver", "UNKNOWN")),
            lap_number=int(reference_lap.get("lap_number", 0)),
            lap_time_s=float(reference_lap.get("lap_time", 0.0)),
        )
        write_manifest(manifest_path, entry)
        print(f"📝 Manifest aggiornato: {manifest_path}")

    if not args.skip_derived and not args.dry_run:
        hook_script = Path(__file__).with_name("build_circuit_profiles.py")
        if hook_script.exists():
            print(f"🔁 Hook: rigenero derived tramite {hook_script.name} (single circuit)…")
            exit_code = run_hook(hook_script, args.circuit_id)
            if exit_code != 0:
                print("⚠️ Hook build_circuit_profiles.py ha restituito un errore. Verifica manualmente.")
        else:
            print("ℹ️ Hook skipped: build_circuit_profiles.py non trovato nello stesso folder.")


def run_hook(script_path: Path, circuit_id: str) -> int:
    import subprocess

    result = subprocess.run(
        [sys.executable, str(script_path), circuit_id],
        cwd=script_path.parent,
    )
    return result.returncode


if __name__ == "__main__":
    main()
