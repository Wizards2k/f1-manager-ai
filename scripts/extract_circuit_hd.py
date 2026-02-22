#!/usr/bin/env python3
"""FastF1 → High-Density waypoint extractor.

Genera un JSON HD con waypoint spaziali (2-10 metri) arricchiti con i
campi necessari al nuovo LapSimulator.

Usage (esempio Monaco Q 2025):
    python3 scripts/extract_circuit_hd.py \
        --year 2025 --event Monaco --session Q \
        --circuit-id mc-1929_monaco --driver LEC \
        --step-m 2
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

try:
    import fastf1
    from fastf1.core import Laps
except ImportError as exc:  # pragma: no cover
    fastf1 = None  # type: ignore

# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--event", required=True, help="Nome evento FastF1 (es. Monaco)")
    parser.add_argument("--session", default="Q", help="FP1/FP2/FP3/Q/R")
    parser.add_argument("--driver", default=None, help="Codice pilota (es. LEC). Default: giro più veloce")
    parser.add_argument("--lap-number", type=int, help="Lap specifico se noto")
    parser.add_argument("--circuit-id", required=True, help="Circuit ID interno (es. mc-1929_monaco)")
    parser.add_argument("--step-m", type=float, default=5.0, help="Distanza in metri tra waypoint uniformi")
    parser.add_argument(
        "--base-telemetry",
        help="Telemetry JSON macro esistente da cui ricavare macro settori"
             " (default: python_backend/data/circuits/<year>/<circuit_id>_Telemetry.json)",
    )
    parser.add_argument(
        "--output",
        help="Percorso file HD JSON di output"
             " (default: python_backend/data/circuits/<year>/<circuit_id>_HD.json)",
    )
    parser.add_argument(
        "--cache-dir",
        default="python_backend/.fastf1_cache",
        help="Cache FastF1 (creata se non esiste)",
    )
    return parser


# ---------------------------------------------------------------------------
# FastF1 utilities
# ---------------------------------------------------------------------------


def ensure_fastf1(cache_dir: Path) -> None:
    if fastf1 is None:
        print("❌ fastf1 non è installato. Esegui `pip install fastf1 pandas numpy scipy`.", file=sys.stderr)
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
    fastest = laps.pick_fastest()
    if fastest is None:
        raise ValueError("Nessun lap valido nella sessione selezionata")
    return fastest


# ---------------------------------------------------------------------------
# HD extraction logic
# ---------------------------------------------------------------------------


def extract_hd_telemetry(session, lap, step_m: float) -> pd.DataFrame:
    tel = lap.get_telemetry().add_distance()
    max_dist = float(tel["Distance"].max())
    dist_grid = np.arange(0.0, max_dist, step_m)

    def safe_column(name: str, default: float = 0.0) -> pd.Series:
        if name in tel:
            return tel[name].fillna(default)
        return pd.Series([default] * len(tel))

    v = np.interp(dist_grid, tel["Distance"], tel["Speed"].fillna(0.0))
    z = np.interp(dist_grid, tel["Distance"], safe_column("Z"))
    throttle = np.interp(dist_grid, tel["Distance"], safe_column("Throttle"))
    brake = np.interp(dist_grid, tel["Distance"], safe_column("Brake"))
    drs_raw = np.interp(dist_grid, tel["Distance"], safe_column("DRS", default=0.0).astype(float))
    
    # Extract X, Y for radius calculation
    x = np.interp(dist_grid, tel["Distance"], safe_column("X"))
    y = np.interp(dist_grid, tel["Distance"], safe_column("Y"))

    # Slope (smoothed)
    dz = np.gradient(z, step_m)
    slope_deg = np.degrees(np.arctan2(dz, step_m))
    if len(slope_deg) >= 7:
        slope_deg = savgol_filter(slope_deg, 7, 3)

    # Calculate Radius using derivatives of X and Y
    dx = np.gradient(x, step_m)
    dy = np.gradient(y, step_m)
    ddx = np.gradient(dx, step_m)
    ddy = np.gradient(dy, step_m)
    
    # curvature k = |dx*ddy - dy*ddx| / (dx^2 + dy^2)^(3/2)
    # R = 1 / k
    num = np.abs(dx * ddy - dy * ddx)
    den = (dx**2 + dy**2)**1.5
    
    radius = np.full_like(dist_grid, 999999.0)
    valid = den > 1e-6
    k = np.zeros_like(dist_grid)
    k[valid] = num[valid] / den[valid]
    
    # Apply smoothing to curvature
    if len(k) >= 11:
        k = savgol_filter(k, 11, 3)
        k = np.maximum(k, 0.0) # ensure positive
    
    radius[k > 1e-4] = 1.0 / k[k > 1e-4]
    radius = np.clip(radius, 5.0, 999999.0)

    v_ms = v / 3.6
    g_lat = (v_ms ** 2) / (radius * 9.81)
    
    # Calcolo steering angle (Ackermann base)
    WHEELBASE_M = 3.6
    STEERING_RATIO = 11.0
    delta_rad = np.arctan(WHEELBASE_M / radius)
    steering_angle_deg = delta_rad * STEERING_RATIO * (180.0 / np.pi)

    camber = np.zeros_like(dist_grid) # We don't have true GLat to estimate camber


    df = pd.DataFrame(
        {
            "dist_m": np.round(dist_grid, 3),
            "v_ref_kph": np.round(v, 3),
            "elevation_m": np.round(z, 3),
            "slope_deg": np.round(slope_deg, 3),
            "radius_m": np.round(radius, 3),
            "camber_deg": np.round(camber, 3),
            "target_g_lat": np.round(np.abs(g_lat), 3),
            "steering_angle_deg": np.round(steering_angle_deg, 2),
            "throttle_pct": throttle.astype(int),
            "brake_pct": brake.astype(int),
            "drs_active": drs_raw > 0.5,
            "surface_type": "asphalt",
        }
    )
    return df


def _ensure_macro_waypoint_bounds(df: pd.DataFrame, sections: List[Dict[str, Any]]) -> pd.DataFrame:
    df = df.copy()

    for sec in sections:
        sec_id = sec.get("id")
        if sec_id is None:
            continue
        mask = df["macro_sector_id"] == sec_id
        if not mask.any():
            continue

        sec_waypoints = df.loc[mask]
        start = sec.get("start_m", sec_waypoints.iloc[0]["dist_m"])
        end = sec.get("end_m", sec_waypoints.iloc[-1]["dist_m"])

        if abs(sec_waypoints.iloc[0]["dist_m"] - start) > 1e-3:
            new_wp = sec_waypoints.iloc[0].copy()
            new_wp["dist_m"] = start
            df = pd.concat([df, pd.DataFrame([new_wp])], ignore_index=True)
        if abs(sec_waypoints.iloc[-1]["dist_m"] - end) > 1e-3:
            new_wp = sec_waypoints.iloc[-1].copy()
            new_wp["dist_m"] = end
            df = pd.concat([df, pd.DataFrame([new_wp])], ignore_index=True)

    if not df.empty:
        df = df.sort_values("dist_m").reset_index(drop=True)

    return df


def load_macro_sections(base_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not base_path.exists():
        raise FileNotFoundError(f"Telemetry base non trovata: {base_path}")
    data = json.loads(base_path.read_text())
    sections = data.get("geometry", {}).get("sections", [])
    return sections, data


def assign_macro_sectors(df: pd.DataFrame, sections: List[Dict[str, Any]]) -> pd.DataFrame:
    df = df.copy()
    df["macro_sector_id"] = "unknown"
    df["section_kind"] = "UNKNOWN"

    for raw in sections:
        start = raw.get("start_m", 0.0)
        end = raw.get("end_m", start)
        mask = (df["dist_m"] >= start) & (df["dist_m"] < end)
        df.loc[mask, "macro_sector_id"] = raw.get("id", "unknown")
        df.loc[mask, "section_kind"] = raw.get("kind", "UNKNOWN")

    # Ultimo punto (exact end) → assegna all'ultimo settore definito
    tail_idx = df.index[-1]
    if df.loc[tail_idx, "macro_sector_id"] == "unknown" and sections:
        df.loc[tail_idx, "macro_sector_id"] = sections[-1].get("id", "unknown")
        df.loc[tail_idx, "section_kind"] = sections[-1].get("kind", "UNKNOWN")
    return df


def apply_empirical_radius_correction(df: pd.DataFrame, sections: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    CORREZIONE EMPIRICA: per curve con raggio FastF1 troppo smoothato.
    Se il raggio medio calcolato è >150m (irrealistico per F1), lo correggiamo
    usando la formula: R = (v_min_m/s)^2 / (mu_eff * g)
    """
    df = df.copy()
    
    for sec in sections:
        if "Corner" not in sec.get("kind", ""):
            continue
            
        sec_id = sec.get("id")
        mask = df["macro_sector_id"] == sec_id
        if not mask.any():
            continue
            
        # Calcola raggio medio attuale nei waypoints
        avg_radius = df.loc[mask, "radius_m"].mean()
        
        # Se il raggio è irrealisticamente grande (>150m), applichiamo correzione
        if avg_radius > 150.0:
            v_min_kph = sec.get("v_min_kph", sec.get("v_min", 0))
            if v_min_kph > 0:
                # Formula empirica: R = v^2 / (mu * g)
                v_min_ms = v_min_kph / 3.6
                mu_eff = 1.5
                g = 9.81
                r_corrected = (v_min_ms ** 2) / (mu_eff * g)
                r_corrected = max(5.0, min(150.0, r_corrected))  # Clamp
                
                # Aggiorna tutti i waypoints del macro-settore
                df.loc[mask, "radius_m"] = r_corrected
                
                # Aggiorna anche g_lat e steering_angle
                v_ms = df.loc[mask, "v_ref_kph"] / 3.6
                df.loc[mask, "target_g_lat"] = np.abs((v_ms ** 2) / (r_corrected * 9.81))
                
                WHEELBASE_M = 3.6
                STEERING_RATIO = 11.0
                delta_rad = np.arctan(WHEELBASE_M / r_corrected)
                df.loc[mask, "steering_angle_deg"] = delta_rad * STEERING_RATIO * (180.0 / np.pi)
    
    return df


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def build_payload(
    circuit_id: str,
    df: pd.DataFrame,
    session,
    lap,
    macro_sections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    circuit_info = session.get_circuit_info()
    circuit_name = getattr(circuit_info, "name", circuit_id)
    drs_zones = getattr(circuit_info, "drs_zones", []) or []

    df = _ensure_macro_waypoint_bounds(df, macro_sections)
    waypoints = df.to_dict("records")
    for wp in waypoints:
        # Convert numpy types to native
        for key, val in list(wp.items()):
            if isinstance(val, (np.integer, np.int64)):
                wp[key] = int(val)
            elif isinstance(val, (np.floating, np.float64)):
                wp[key] = float(val)
            elif isinstance(val, (np.bool_,)):
                wp[key] = bool(val)

    macro_payload = []
    for raw in macro_sections:
        sec_id = raw.get("id")
        # Calcola raggio medio dai waypoints corretti di questo macro-settore
        mask = df["macro_sector_id"] == sec_id
        avg_radius = None
        if mask.any():
            avg_radius = float(df.loc[mask, "radius_m"].mean())
        # Calcola grip telemetrico medio (g_lat)
        telemetry_mu = float(df.loc[mask, "target_g_lat"].mean()) if mask.any() else 0.0
        
        # CORREZIONE: v_entry/v_exit dai waypoints HD (ground truth), non dal JSON Telemetry
        v_entry_hd = float(df.loc[mask, "v_ref_kph"].iloc[0]) if mask.any() else raw.get("v_entry_kph", raw.get("v_entry", 0.0))
        v_exit_hd = float(df.loc[mask, "v_ref_kph"].iloc[-1]) if mask.any() else raw.get("v_exit_kph", raw.get("v_exit", 0.0))
        v_min_hd = float(df.loc[mask, "v_ref_kph"].min()) if mask.any() else raw.get("v_min_kph", raw.get("v_min", 0.0))
        v_max_hd = float(df.loc[mask, "v_ref_kph"].max()) if mask.any() else raw.get("v_max_kph", raw.get("v_max", 0.0))
        waypoint_start = float(df.loc[mask, "dist_m"].iloc[0]) if mask.any() else raw.get("start_m", 0.0)
        waypoint_end = float(df.loc[mask, "dist_m"].iloc[-1]) if mask.any() else raw.get("end_m", waypoint_start)
        length_m = float(max(0.0, waypoint_end - waypoint_start))

        macro_payload.append(
            {
                "id": raw.get("id"),
                "name": raw.get("name"),
                "kind": raw.get("kind"),
                "start_m": waypoint_start,
                "end_m": waypoint_end,
                "length_m": length_m,
                "v_entry_kph": v_entry_hd,
                "v_exit_kph": v_exit_hd,
                "v_min_kph": v_min_hd,
                "v_max_kph": v_max_hd,
                "dt_ref_s": raw.get("dt_ref_s", 0.0),
                "radius_m": avg_radius,
                "telemetry_mu": telemetry_mu,
            }
        )

    payload = {
        "circuit_id": circuit_id,
        "circuit_name": circuit_name,
        "sample_step_m": float(df["dist_m"].iloc[1] - df["dist_m"].iloc[0]) if len(df) > 1 else 0.0,
        "total_length_m": float(df["dist_m"].max()),
        "reference_lap": {
            "driver": lap.get("Driver", "UNKNOWN"),
            "lap_number": int(lap.get("LapNumber", 0) or 0),
            "lap_time_s": float(lap.get("LapTime" ).total_seconds()) if lap.get("LapTime") else float(lap.get("LapTime", 0.0)),
        },
        "waypoints": waypoints,
        "macro_sectors": macro_payload,
        "drs_zones": drs_zones,
    }
    return payload


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    ensure_fastf1(cache_dir)

    session = load_session(args.year, args.event, args.session)
    lap = pick_lap(session, args.driver, args.lap_number)

    df = extract_hd_telemetry(session, lap, max(args.step_m, 0.5))

    base_path = (
        Path(args.base_telemetry)
        if args.base_telemetry
        else Path(f"python_backend/data/circuits/{args.year}/{args.circuit_id}_Telemetry.json")
    )
    sections, _ = load_macro_sections(base_path)
    df = assign_macro_sectors(df, sections)
    
    # CORREZIONE EMPIRICA per curve corte con raggio FastF1 troppo smoothato
    df = apply_empirical_radius_correction(df, sections)

    payload = build_payload(args.circuit_id, df, session, lap, sections)

    output_path = (
        Path(args.output)
        if args.output
        else base_path.with_name(base_path.name.replace("_Telemetry.json", "_HD.json"))
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"💾 HD telemetry salvata in {output_path}")
    print(f"   Waypoints: {len(payload['waypoints'])} | step={payload['sample_step_m']}m")


if __name__ == "__main__":
    main()
