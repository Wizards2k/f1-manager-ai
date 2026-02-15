#!/usr/bin/env python3
"""Calibrazione aerodinamica basata sui file Telemetry JSON.

Esempio d'uso:

    python scripts/aero_fit.py --circuit-id ae-2009_yas_marina --year 2024

Genera `config/calibration/aero/<circuit>.json` con CdA/ClA calibrati e
un report opzionale.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# Costanti di riferimento (tunable)
REFERENCE_TOP_SPEED_KPH = 330.0
REFERENCE_CORNER_SCORE = 6.0  # empirico: v_min / sqrt(radius)
BASE_CDA = 1.45
BASE_CLA = 4.85


@dataclass
class AeroCalibration:
    CdA: float
    ClA: float
    drag_index: float
    downforce_index: float
    aero_balance_target: float
    notes: Dict[str, Any]


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def load_telemetry(circuit_id: str, year: Optional[int], data_dir: Path) -> Dict[str, Any]:
    candidates: List[Path] = []
    if year:
        candidates.append(data_dir / str(year) / f"{circuit_id}_Telemetry.json")
    candidates.append(data_dir / f"{circuit_id}_Telemetry.json")

    for path in candidates:
        if path.exists():
            return json.loads(path.read_text())

    raise FileNotFoundError(
        f"Telemetry JSON non trovato. Cercati: {', '.join(str(p) for p in candidates)}"
    )


def compute_drag_index(straights: List[Dict[str, Any]]) -> float:
    vmax_values = [s.get("v_max_kph") for s in straights if s.get("v_max_kph")]
    if not vmax_values:
        return 1.0
    avg_vmax = statistics.mean(vmax_values)
    if avg_vmax <= 0:
        return 1.0
    return clamp(REFERENCE_TOP_SPEED_KPH / avg_vmax, 0.5, 1.8)


def compute_downforce_index(corners: List[Dict[str, Any]]) -> float:
    scores = []
    for c in corners:
        radius = c.get("radius_m")
        v_min = c.get("v_min_kph")
        if not radius or not v_min or radius <= 0:
            continue
        score = v_min / math.sqrt(radius)
        scores.append(score)
    if not scores:
        return 1.0
    avg_score = statistics.mean(scores)
    return clamp(avg_score / REFERENCE_CORNER_SCORE, 0.6, 1.8)


def compute_balance_target(corners: List[Dict[str, Any]]) -> float:
    slow = [c["v_min_kph"] for c in corners if c.get("v_min_kph", 0) < 130]
    fast = [c["v_min_kph"] for c in corners if c.get("v_min_kph", 0) >= 180]

    if not slow or not fast:
        return 0.0

    slow_avg = statistics.mean(slow)
    fast_avg = statistics.mean(fast)

    # Bilanciamento: positivo → carico anteriore (più confidenza curve veloci), negativo → posteriore
    delta = (fast_avg - slow_avg) / max(fast_avg, 1.0)
    return clamp(delta, -0.15, 0.15)


def calibrate_aero(telemetry: Dict[str, Any], circuit_id: str, year: Optional[int]) -> AeroCalibration:
    sections = telemetry["geometry"]["sections"]
    straights = [s for s in sections if "Straight" in s.get("kind", "")]
    corners = [s for s in sections if "Corner" in s.get("kind", "")]

    drag_index = compute_drag_index(straights)
    downforce_index = compute_downforce_index(corners)
    aero_balance_target = compute_balance_target(corners)

    cda = round(BASE_CDA * drag_index, 4)
    cla = round(BASE_CLA * downforce_index, 4)

    metadata = telemetry.get("metadata", {})
    notes = {
        "source_year": metadata.get("year", year),
        "session_type": metadata.get("session_type"),
        "description": metadata.get("description"),
        "generated_from": metadata.get("circuit_id", circuit_id),
    }

    return AeroCalibration(
        CdA=cda,
        ClA=cla,
        drag_index=round(drag_index, 4),
        downforce_index=round(downforce_index, 4),
        aero_balance_target=round(aero_balance_target, 4),
        notes=notes,
    )


def write_output(calibration: AeroCalibration, circuit_id: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{circuit_id}.json"
    payload = {"aero": asdict(calibration)}
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out_path


def write_report(calibration: AeroCalibration, circuit_id: str, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = report_dir / f"{circuit_id}.md"
    lines = [
        f"# Aero calibration – {circuit_id}",
        "",
        "| Parametro | Valore |",
        "|-----------|--------|",
        f"| CdA | {calibration.CdA:.4f} |",
        f"| ClA | {calibration.ClA:.4f} |",
        f"| drag_index | {calibration.drag_index:.4f} |",
        f"| downforce_index | {calibration.downforce_index:.4f} |",
        f"| aero_balance_target | {calibration.aero_balance_target:.4f} |",
        "",
        "## Notes",
    ]
    for key, value in calibration.notes.items():
        lines.append(f"- **{key}**: {value}")
    out_path.write_text("\n".join(lines))
    return out_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--circuit-id", required=True, help="ID circuito (es. ae-2009_yas_marina)")
    parser.add_argument("--year", type=int, help="Anno da usare (cartella data/circuits/<year>)")
    parser.add_argument(
        "--data-dir",
        default="python_backend/data/circuits",
        help="Directory base dei Telemetry JSON",
    )
    parser.add_argument(
        "--output-dir",
        default="config/calibration/aero",
        help="Directory dove salvare il file di calibrazione",
    )
    parser.add_argument(
        "--report-dir",
        help="Directory opzionale per un report Markdown",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra i valori calcolati senza salvare file",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    telemetry = load_telemetry(args.circuit_id, args.year, Path(args.data_dir))
    calibration = calibrate_aero(telemetry, args.circuit_id, args.year)

    print("=== Aero calibration ===")
    print(json.dumps({"aero": asdict(calibration)}, indent=2, ensure_ascii=False))

    if not args.dry_run:
        out_path = write_output(calibration, args.circuit_id, Path(args.output_dir))
        print(f"📝 Salvato: {out_path}")
        if args.report_dir:
            report_path = write_report(calibration, args.circuit_id, Path(args.report_dir))
            print(f"📄 Report: {report_path}")
    else:
        print("Dry-run attivo: nessun file scritto.")


if __name__ == "__main__":
    main()
