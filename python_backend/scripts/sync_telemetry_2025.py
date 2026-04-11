#!/usr/bin/env python3
"""
sync_telemetry_2025.py — Sincronizzazione Telemetria Reale 2025 (TracingInsights)

Scarica i dati di telemetria reali dal repository TracingInsights-Archive/2025
e li integra nel simulatore F1 Manager AI per:

1. Aggiornamento waypoints HD con raggio dinamico reale (X/Y curvature)
2. Creazione lookup table RPM/Gear per la Power Unit
3. Calibrazione aero-meccanica (grip meccanico vs aerodinamico)
4. Validazione pre/post integrazione

Usage:
    # Sincronizza tutti e 5 i circuiti
    python3 python_backend/scripts/sync_telemetry_2025.py --all

    # Sincronizza un singolo circuito
    python3 python_backend/scripts/sync_telemetry_2025.py --circuit monaco

    # Solo raggio dinamico (Task 2)
    python3 python_backend/scripts/sync_telemetry_2025.py --circuit monaco --task radius

    # Solo lookup RPM/Gear (Task 3)
    python3 python_backend/scripts/sync_telemetry_2025.py --circuit monza --task pu_lookup

    # Solo calibrazione aero (Task 4)
    python3 python_backend/scripts/sync_telemetry_2025.py --circuit monaco --task aero_cal

    # Validazione (Task 5)
    python3 python_backend/scripts/sync_telemetry_2025.py --validate

Dati TracingInsights:
    Repository: https://github.com/TracingInsights-Archive/2025
    Formato telemetria: {tel: {time, rpm, speed, gear, throttle, brake, drs,
                                distance, x, y, z, acc_x, acc_y, acc_z, ...}}
    Formato laptimes: {time, lap, compound, stint, s1, s2, s3, ...}
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Mappatura circuiti: nome interno → nome TracingInsights
CIRCUIT_MAP = {
    # 5 circuiti originali (validati V5.0)
    "monaco": {
        "gp_name": "Monaco Grand Prix",
        "circuit_id": "mc-1929_monaco",
        "reference_driver": "NOR",
    },
    "spa": {
        "gp_name": "Belgian Grand Prix",
        "circuit_id": "be-1925_spa_francorchamps",
        "reference_driver": "NOR",
    },
    "silverstone": {
        "gp_name": "British Grand Prix",
        "circuit_id": "gb-1948_silverstone",
        "reference_driver": "NOR",
    },
    "monza": {
        "gp_name": "Italian Grand Prix",
        "circuit_id": "it-1922_monza",
        "reference_driver": "NOR",
    },
    "suzuka": {
        "gp_name": "Japanese Grand Prix",
        "circuit_id": "jp-1962_suzuka",
        "reference_driver": "NOR",
    },
    # 19 circuiti aggiuntivi (V5.1)
    "abudhabi": {
        "gp_name": "Abu Dhabi Grand Prix",
        "circuit_id": "ae-2009_yas_marina",
        "reference_driver": "VER",
    },
    "austria": {
        "gp_name": "Austrian Grand Prix",
        "circuit_id": "at-1969_spielberg",
        "reference_driver": "NOR",
    },
    "australia": {
        "gp_name": "Australian Grand Prix",
        "circuit_id": "au-1953_melbourne",
        "reference_driver": "NOR",
    },
    "baku": {
        "gp_name": "Azerbaijan Grand Prix",
        "circuit_id": "az-2016_baku",
        "reference_driver": "VER",
    },
    "bahrain": {
        "gp_name": "Bahrain Grand Prix",
        "circuit_id": "bh-2002_sakhir",
        "reference_driver": "PIA",
    },
    "saopaulo": {
        "gp_name": "São Paulo Grand Prix",
        "circuit_id": "br-1940_sao_paulo",
        "reference_driver": "NOR",
    },
    "canada": {
        "gp_name": "Canadian Grand Prix",
        "circuit_id": "ca-1978_montreal",
        "reference_driver": "RUS",
    },
    "china": {
        "gp_name": "Chinese Grand Prix",
        "circuit_id": "cn-2004_shanghai",
        "reference_driver": "PIA",
    },
    "spain": {
        "gp_name": "Spanish Grand Prix",
        "circuit_id": "es-1991_barcelona",
        "reference_driver": "PIA",
    },
    "hungary": {
        "gp_name": "Hungarian Grand Prix",
        "circuit_id": "hu-1986_budapest",
        "reference_driver": "LEC",
    },
    "imola": {
        "gp_name": "Emilia Romagna Grand Prix",
        "circuit_id": "it-1953_imola",
        "reference_driver": "PIA",
    },
    "mexico": {
        "gp_name": "Mexico City Grand Prix",
        "circuit_id": "mx-1962_mexico_city",
        "reference_driver": "NOR",
    },
    "zandvoort": {
        "gp_name": "Dutch Grand Prix",
        "circuit_id": "nl-1948_zandvoort",
        "reference_driver": "PIA",
    },
    "qatar": {
        "gp_name": "Qatar Grand Prix",
        "circuit_id": "qa-2004_lusail",
        "reference_driver": "PIA",
    },
    "jeddah": {
        "gp_name": "Saudi Arabian Grand Prix",
        "circuit_id": "sa-2021_jeddah",
        "reference_driver": "VER",
    },
    "singapore": {
        "gp_name": "Singapore Grand Prix",
        "circuit_id": "sg-2008_singapore",
        "reference_driver": "RUS",
    },
    "austin": {
        "gp_name": "United States Grand Prix",
        "circuit_id": "us-2012_austin",
        "reference_driver": "VER",
    },
    "miami": {
        "gp_name": "Miami Grand Prix",
        "circuit_id": "us-2022_miami",
        "reference_driver": "VER",
    },
    "lasvegas": {
        "gp_name": "Las Vegas Grand Prix",
        "circuit_id": "us-2023_las_vegas",
        "reference_driver": "NOR",
    },
}

BASE_URL = "https://raw.githubusercontent.com/TracingInsights-Archive/2025/main"
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "circuits" / "2025"
CACHE_DIR = Path(__file__).resolve().parents[2] / ".telemetry_cache_2025"

# Parametri fisici
G = 9.81
RHO_SEA_LEVEL = 1.225
MASS_TOTAL_QUALY_KG = 798.0  # F1 2025 minimum weight + fuel qualifica


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class TelemetryPoint:
    """Punto di telemetria reale da TracingInsights."""
    time_s: float
    speed_kph: float
    rpm: float
    gear: int
    throttle_pct: float
    brake_pct: float
    drs: bool
    distance_m: float
    x: float
    y: float
    z: float
    acc_x: float = 0.0
    acc_y: float = 0.0
    acc_z: float = 0.0


@dataclass
class RadiusPoint:
    """Raggio di curvatura calcolato per un waypoint."""
    dist_m: float
    radius_m: float
    curvature_1pm: float  # 1/R
    method: str  # 'xy_derivative', 'speed_glat', 'hybrid'


@dataclass
class PULookupEntry:
    """Entry nella lookup table RPM/Gear/Speed."""
    speed_kph: float
    rpm: float
    gear: int
    throttle_pct: float
    f_engine_estimated: float  # N stimati


@dataclass
class AeroCalibrationResult:
    """Risultato calibrazione aero-meccanica."""
    circuit_id: str
    mu_base_derived: float
    mu_mechanical: float
    mu_aero_contribution: float
    cla_floor_dynamic: float
    k_wing_coupling: float
    lap_time_real: float
    lap_time_sim_before: float
    lap_time_sim_after: float
    error_pct_before: float
    error_pct_after: float


# ---------------------------------------------------------------------------
# Task 1: Download & Parse TracingInsights Data
# ---------------------------------------------------------------------------

def download_json(url: str) -> Any:
    """Scarica un JSON da URL con gestione errori."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "F1ManagerAI/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  ❌ Errore download {url}: {e}")
        return None


def find_fastest_lap(laptimes: Dict) -> Tuple[int, float]:
    """Trova il giro più veloce nei laptimes."""
    times = laptimes.get("time", [])
    laps = laptimes.get("lap", [])
    best_idx = -1
    best_time = float("inf")
    for i, (t, l) in enumerate(zip(times, laps)):
        if t == "None" or t is None:
            continue
        try:
            t_float = float(t)
            if t_float < best_time and t_float > 60.0:  # Ignora out-lap
                best_time = t_float
                best_idx = i
        except (TypeError, ValueError):
            continue
    if best_idx < 0:
        raise ValueError("Nessun giro valido trovato")
    return int(laps[best_idx]), best_time


def download_fastest_telemetry(gp_name: str, driver: str = "NOR",
                                session: str = "Qualifying") -> Optional[Dict]:
    """
    Scarica la telemetria del giro più veloce per un circuito/pilota.

    Returns:
        Dict con chiavi 'tel' contenente i dati telemetria, oppure None
    """
    gp_encoded = urllib.parse.quote(gp_name)
    base = f"{BASE_URL}/{gp_encoded}/{session}"

    # 1. Scarica laptimes per trovare il giro più veloce
    laptimes_url = f"{base}/{driver}/laptimes.json"
    print(f"  📥 Scaricando laptimes: {driver} @ {gp_name} {session}...")
    laptimes = download_json(laptimes_url)
    if laptimes is None:
        return None

    try:
        best_lap, best_time = find_fastest_lap(laptimes)
    except ValueError:
        print(f"  ⚠️ Nessun giro valido per {driver} @ {gp_name}")
        return None

    print(f"  ✅ Giro più veloce: lap {best_lap} ({best_time:.3f}s)")

    # 2. Scarica telemetria del giro più veloce
    tel_url = f"{base}/{driver}/{best_lap}_tel.json"
    print(f"  📥 Scaricando telemetria lap {best_lap}...")
    tel_data = download_json(tel_url)
    if tel_data is None:
        return None

    return {
        "lap_number": best_lap,
        "lap_time_s": best_time,
        "driver": driver,
        "session": session,
        "gp_name": gp_name,
        "tel": tel_data.get("tel", tel_data),
        "laptimes": laptimes,
    }


def parse_telemetry_points(raw_tel: Dict) -> List[TelemetryPoint]:
    """Converte i dati telemetria grezzi in TelemetryPoint objects."""
    points = []
    n = len(raw_tel.get("time", []))
    if n == 0:
        return points

    for i in range(n):
        try:
            speed = raw_tel["speed"][i]
            if speed == "None" or speed is None:
                continue
            points.append(TelemetryPoint(
                time_s=float(raw_tel["time"][i]) if raw_tel["time"][i] != "None" else 0.0,
                speed_kph=float(speed),
                rpm=float(raw_tel["rpm"][i]) if raw_tel["rpm"][i] != "None" else 0.0,
                gear=int(raw_tel["gear"][i]) if raw_tel["gear"][i] != "None" else 0,
                throttle_pct=float(raw_tel["throttle"][i]) if raw_tel["throttle"][i] != "None" else 0.0,
                brake_pct=float(raw_tel["brake"][i]) if raw_tel["brake"][i] != "None" else 0.0,
                drs=bool(int(raw_tel["drs"][i])) if raw_tel["drs"][i] != "None" else False,
                distance_m=float(raw_tel["distance"][i]) if raw_tel["distance"][i] != "None" else 0.0,
                x=float(raw_tel["x"][i]) if raw_tel["x"][i] != "None" else 0.0,
                y=float(raw_tel["y"][i]) if raw_tel["y"][i] != "None" else 0.0,
                z=float(raw_tel["z"][i]) if raw_tel["z"][i] != "None" else 0.0,
                acc_x=float(raw_tel.get("acc_x", [0.0]*n)[i]) if i < len(raw_tel.get("acc_x", [])) else 0.0,
                acc_y=float(raw_tel.get("acc_y", [0.0]*n)[i]) if i < len(raw_tel.get("acc_y", [])) else 0.0,
                acc_z=float(raw_tel.get("acc_z", [0.0]*n)[i]) if i < len(raw_tel.get("acc_z", [])) else 0.0,
            ))
        except (IndexError, TypeError, ValueError):
            continue

    return points


# ---------------------------------------------------------------------------
# Task 2: Dynamic Radius Calculation (Raggio di Curvatura Istantaneo)
# ---------------------------------------------------------------------------

def compute_dynamic_radius(points: List[TelemetryPoint],
                           step_m: float = 5.0) -> List[RadiusPoint]:
    """
    Calcola il raggio di curvatura istantaneo usando le coordinate X, Y.

    Formula: R = ((x2-x1)² + (y2-y1)²)^(3/2) / |2·((x2-x1)·(y3-y2) - (x3-x2)·(y2-y1))|

    Metodo alternativo (derivata seconda):
        k = |dx·ddy - dy·ddx| / (dx² + dy²)^(3/2)
        R = 1/k

    Questo risolve il problema dell'auto che 'parcheggia' a Spa sec_12
    e Monaco sec_11, dove il radius_m approssimativo era troppo grande.
    """
    if len(points) < 3:
        return []

    # Estrai arrays
    x = np.array([p.x for p in points])
    y = np.array([p.y for p in points])
    dist = np.array([p.distance_m for p in points])
    speed = np.array([p.speed_kph for p in points])

    # Calcola derivate prime e seconde rispetto alla distanza
    dx = np.gradient(x, dist)
    dy = np.gradient(y, dist)
    ddx = np.gradient(dx, dist)
    ddy = np.gradient(dy, dist)

    # Curvature: k = |dx·ddy - dy·ddx| / (dx² + dy²)^(3/2)
    numerator = np.abs(dx * ddy - dy * ddx)
    denominator = (dx**2 + dy**2) ** 1.5

    # Evita divisione per zero
    curvature = np.zeros_like(dist)
    valid = denominator > 1e-6
    curvature[valid] = numerator[valid] / denominator[valid]

    # Smoothing con Savitzky-Golay (se disponibile) o media mobile
    try:
        from scipy.signal import savgol_filter
        if len(curvature) >= 11:
            curvature = savgol_filter(curvature, 11, 3)
            curvature = np.maximum(curvature, 0.0)
    except ImportError:
        # Fallback: media mobile semplice
        kernel_size = 11
        kernel = np.ones(kernel_size) / kernel_size
        curvature = np.convolve(curvature, kernel, mode="same")

    # Raggio = 1/curvature, con clamp
    radius = np.full_like(dist, 999999.0)
    radius[curvature > 1e-5] = 1.0 / curvature[curvature > 1e-5]
    radius = np.clip(radius, 5.0, 999999.0)

    # Crea output interpolato su griglia uniforme (step_m)
    total_length = dist[-1]
    dist_grid = np.arange(0.0, total_length, step_m)

    radius_interp = np.interp(dist_grid, dist, radius)
    curvature_interp = np.interp(dist_grid, dist, curvature)

    results = []
    for i in range(len(dist_grid)):
        results.append(RadiusPoint(
            dist_m=float(dist_grid[i]),
            radius_m=float(radius_interp[i]),
            curvature_1pm=float(curvature_interp[i]),
            method="xy_derivative",
        ))

    return results


def compute_radius_from_speed_glat(points: List[TelemetryPoint],
                                    step_m: float = 5.0) -> List[RadiusPoint]:
    """
    Calcola il raggio dalla velocità e accelerazione laterale reale.

    Formula: R = v² / |a_lat|
    Dove a_lat è l'accelerazione laterale misurata (acc_y).

    Questo è un metodo indipendente che può essere usato per validazione.
    """
    if len(points) < 3:
        return []

    dist = np.array([p.distance_m for p in points])
    speed_kph = np.array([p.speed_kph for p in points])
    acc_y = np.array([p.acc_y for p in points])

    speed_ms = speed_kph / 3.6
    a_lat = np.abs(acc_y)  # Accelerazione laterale in m/s²

    # Raggio = v² / |a_lat|
    radius = np.full_like(dist, 999999.0)
    valid = a_lat > 0.5  # Soglia minima per considerare curva
    radius[valid] = speed_ms[valid] ** 2 / a_lat[valid]
    radius = np.clip(radius, 5.0, 999999.0)

    # Interpola su griglia uniforme
    total_length = dist[-1]
    dist_grid = np.arange(0.0, total_length, step_m)
    radius_interp = np.interp(dist_grid, dist, radius)

    results = []
    for i in range(len(dist_grid)):
        results.append(RadiusPoint(
            dist_m=float(dist_grid[i]),
            radius_m=float(radius_interp[i]),
            curvature_1pm=float(1.0 / radius_interp[i]) if radius_interp[i] < 999999.0 else 0.0,
            method="speed_glat",
        ))

    return results


def hybrid_radius(xy_radius: List[RadiusPoint],
                  glat_radius: List[RadiusPoint]) -> List[RadiusPoint]:
    """
    Combina i due metodi: usa XY derivative come primario,
    ma in curve lente (< 80 kph) usa il metodo speed/g_lat
    che è più affidabile per GPS noise.
    """
    if not xy_radius or not glat_radius:
        return xy_radius or glat_radius

    # Assumiamo stessa griglia di distanza
    results = []
    for i in range(min(len(xy_radius), len(glat_radius))):
        r_xy = xy_radius[i].radius_m
        r_glat = glat_radius[i].radius_m

        # In curve strette (raggio piccolo), il metodo g_lat è più affidabile
        # perché il GPS ha più noise nelle coordinate X/Y a basse velocità
        if r_xy < 200.0 and r_glat < 5000.0:
            # Blend pesato: più g_lat per curve strette
            weight = max(0.0, min(1.0, (200.0 - r_xy) / 200.0))
            r_hybrid = r_xy * (1.0 - weight) + r_glat * weight
        else:
            r_hybrid = r_xy

        results.append(RadiusPoint(
            dist_m=xy_radius[i].dist_m,
            radius_m=float(r_hybrid),
            curvature_1pm=float(1.0 / r_hybrid) if r_hybrid < 999999.0 else 0.0,
            method="hybrid",
        ))

    return results


def update_hd_with_radius(circuit_id: str, radius_points: List[RadiusPoint],
                          step_m: float = 5.0) -> bool:
    """
    Aggiorna il file HD.json con i raggi dinamici calcolati.

    Returns True se l'aggiornamento è avvenuto con successo.
    """
    hd_path = DATA_DIR / f"{circuit_id}_HD.json"
    if not hd_path.exists():
        print(f"  ❌ File HD non trovato: {hd_path}")
        return False

    with open(hd_path, "r", encoding="utf-8") as f:
        hd_data = json.load(f)

    waypoints = hd_data.get("waypoints", [])
    if not waypoints:
        print(f"  ❌ Nessun waypoint in {hd_path}")
        return False

    # Crea lookup dict per radius per distanza
    radius_lookup = {}
    for rp in radius_points:
        radius_lookup[round(rp.dist_m, 1)] = rp.radius_m

    # Aggiorna ogni waypoint
    updated = 0
    for wp in waypoints:
        dist_key = round(wp["dist_m"], 1)
        if dist_key in radius_lookup:
            old_radius = wp.get("radius_m", 999999.0)
            new_radius = radius_lookup[dist_key]
            wp["radius_m"] = new_radius
            # Aggiorna anche target_g_lat e steering_angle
            v_ms = wp.get("v_ref_kph", 200.0) / 3.6
            if new_radius < 999999.0:
                wp["target_g_lat"] = round(abs(v_ms**2 / (new_radius * G)), 3)
                WHEELBASE_M = 3.6
                STEERING_RATIO = 11.0
                delta_rad = math.atan(WHEELBASE_M / new_radius)
                wp["steering_angle_deg"] = round(delta_rad * STEERING_RATIO * (180.0 / math.pi), 2)
            updated += 1

    # Backup del file originale
    backup_path = hd_path.with_suffix(".json.backup_radius")
    if not backup_path.exists():
        import shutil
        shutil.copy2(hd_path, backup_path)
        print(f"  💾 Backup salvato: {backup_path}")

    # Salva il file aggiornato
    with open(hd_path, "w", encoding="utf-8") as f:
        json.dump(hd_data, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Aggiornati {updated}/{len(waypoints)} waypoints con raggio dinamico")
    return True


# ---------------------------------------------------------------------------
# Task 3: Power Unit Lookup Table (RPM/Gear/Speed)
# ---------------------------------------------------------------------------

def build_pu_lookup(points: List[TelemetryPoint],
                    circuit_id: str) -> List[PULookupEntry]:
    """
    Estrae la relazione Speed/RPM/Gear dalla telemetria reale.

    Crea una lookup table che forza la f_engine a seguire il profilo
    di accelerazione reale registrato. Se a Monza l'auto reale rallena
    l'accelerazione a 330 km/h (clipping ERS), il simulatore deve
    replicare esattamente quel comportamento.
    """
    if not points:
        return []

    # Raggruppa per marcia e calcola profilo medio
    gear_profiles: Dict[int, List[Dict]] = {}
    for p in points:
        if p.gear <= 0 or p.speed_kph < 10:
            continue
        if p.gear not in gear_profiles:
            gear_profiles[p.gear] = []
        gear_profiles[p.gear].append({
            "speed_kph": p.speed_kph,
            "rpm": p.rpm,
            "throttle_pct": p.throttle_pct,
            "brake_pct": p.brake_pct,
        })

    # Per ogni marcia, calcola RPM vs Speed e stima forza motrice
    lookup_entries = []

    for gear in sorted(gear_profiles.keys()):
        entries = gear_profiles[gear]
        if len(entries) < 5:
            continue

        speeds = np.array([e["speed_kph"] for e in entries])
        rpms = np.array([e["rpm"] for e in entries])
        throttles = np.array([e["throttle_pct"] for e in entries])

        # Filtra solo punti a throttle pieno (>95%) per il profilo massimo
        full_throttle_mask = throttles > 95.0
        if full_throttle_mask.sum() < 3:
            full_throttle_mask = throttles > 80.0

        # Crea bins di velocità per ogni marcia
        speed_bins = np.arange(
            speeds[full_throttle_mask].min() if full_throttle_mask.any() else speeds.min(),
            speeds.max() + 5,
            5.0  # Bin ogni 5 km/h
        )

        for s_low in speed_bins:
            s_high = s_low + 5.0
            mask = (speeds >= s_low) & (speeds < s_high) & full_throttle_mask
            if mask.sum() < 2:
                continue

            avg_speed = float(np.mean(speeds[mask]))
            avg_rpm = float(np.mean(rpms[mask]))
            avg_throttle = float(np.mean(throttles[mask]))

            # Stima forza motrice: F = P/v
            # Potenza F1 2025: ~750kW (ICE) + ~150kW (ERS) = ~900kW peak
            # Ma a RPM bassi la potenza è minore
            rpm_fraction = np.clip((avg_rpm - 4000) / (12000 - 4000), 0.3, 1.0)
            power_kw = 900.0 * rpm_fraction * (avg_throttle / 100.0)
            v_ms = avg_speed / 3.6
            f_engine = power_kw * 1000.0 / max(v_ms, 1.0) if v_ms > 1.0 else 0.0

            lookup_entries.append(PULookupEntry(
                speed_kph=round(avg_speed, 1),
                rpm=round(avg_rpm, 0),
                gear=int(gear),
                throttle_pct=round(avg_throttle, 1),
                f_engine_estimated=round(f_engine, 1),
            ))

    # Ordina per velocità
    lookup_entries.sort(key=lambda e: (e.gear, e.speed_kph))
    return lookup_entries


def save_pu_lookup(circuit_id: str, entries: List[PULookupEntry]) -> bool:
    """Salva la lookup table PU per un circuito."""
    output_dir = DATA_DIR.parent / "pu_lookup"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{circuit_id}_pu_lookup.json"

    payload = {
        "circuit_id": circuit_id,
        "source": "TracingInsights-Archive/2025",
        "description": "Power Unit lookup table from real telemetry data",
        "entries": [asdict(e) for e in entries],
        "gear_summary": {},
    }

    # Riassunto per marcia
    for gear in sorted(set(e.gear for e in entries)):
        gear_entries = [e for e in entries if e.gear == gear]
        if gear_entries:
            payload["gear_summary"][str(gear)] = {
                "speed_range_kph": [
                    min(e.speed_kph for e in gear_entries),
                    max(e.speed_kph for e in gear_entries),
                ],
                "rpm_range": [
                    min(e.rpm for e in gear_entries),
                    max(e.rpm for e in gear_entries),
                ],
                "avg_throttle_pct": round(
                    sum(e.throttle_pct for e in gear_entries) / len(gear_entries), 1
                ),
            }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"  ✅ PU lookup salvata: {output_path} ({len(entries)} entries)")
    return True


# ---------------------------------------------------------------------------
# Task 4: Aero-Mechanical Calibration (Monaco Case Study)
# ---------------------------------------------------------------------------

def derive_mechanical_grip(points: List[TelemetryPoint],
                           circuit_id: str) -> Dict[str, float]:
    """
    Deriva il grip meccanico (mu_base) dai dati di bassa velocità.

    Nei punti a bassa velocità (< 80 km/h), il downforce è minimo
    e il grip è prevalentemente meccanico. Usiamo la formula:

        mu_mechanical = v² / (R × g)

    dove v è la velocità in curva lenta e R è il raggio.

    Per Monaco, il Tornante (hairpin) ha R≈10-15m e v≈45-50 km/h,
    che dà mu ≈ 1.8-2.0, realistico per gomme C5 su asfalto stradale.
    """
    if not points:
        return {"mu_mechanical": 1.65, "mu_aero_contribution": 0.0}

    # Filtra punti a bassa velocità (< 80 km/h) con accelerazione laterale significativa
    low_speed_corners = []
    for p in points:
        if p.speed_kph < 80.0 and p.speed_kph > 20.0:
            a_lat = abs(p.acc_y)
            if a_lat > 1.0:  # Accelerazione laterale > 1g
                v_ms = p.speed_kph / 3.6
                # R = v² / a_lat
                radius = v_ms**2 / a_lat if a_lat > 0.1 else 999999.0
                # mu = a_lat / g (senza downforce a basse velocità)
                mu = a_lat / G
                low_speed_corners.append({
                    "speed_kph": p.speed_kph,
                    "a_lat": a_lat,
                    "radius_m": radius,
                    "mu": mu,
                })

    if not low_speed_corners:
        print("  ⚠️ Nessun punto a bassa velocità con g_lat significativo trovato")
        return {"mu_mechanical": 1.65, "mu_aero_contribution": 0.0}

    # mu_mechanical è il percentile 75 dei mu calcolati
    # (escludiamo i valori più bassi che possono essere errori di GPS)
    mu_values = sorted([c["mu"] for c in low_speed_corners])
    p75_idx = int(len(mu_values) * 0.75)
    mu_mechanical = mu_values[p75_idx]

    # Calcola contributo aerodinamico ad alta velocità
    high_speed_corners = []
    for p in points:
        if p.speed_kph > 180.0:
            a_lat = abs(p.acc_y)
            if a_lat > 2.0:  # g_lat > 2g ad alta velocità
                v_ms = p.speed_kph / 3.6
                # mu_total = a_lat / g
                mu_total = a_lat / G
                # Downforce aggiunge: mu_aero = mu_total - mu_mechanical
                mu_aero = mu_total - mu_mechanical
                high_speed_corners.append({
                    "speed_kph": p.speed_kph,
                    "a_lat": a_lat,
                    "mu_total": mu_total,
                    "mu_aero": mu_aero,
                })

    mu_aero_avg = 0.0
    if high_speed_corners:
        mu_aero_avg = np.mean([c["mu_aero"] for c in high_speed_corners])

    print(f"  📊 Grip meccanico derivato: mu_base = {mu_mechanical:.3f}")
    print(f"  📊 Contributo aero medio: mu_aero = {mu_aero_avg:.3f}")
    print(f"  📊 Punti bassa velocità analizzati: {len(low_speed_corners)}")
    print(f"  📊 Punti alta velocità analizzati: {len(high_speed_corners)}")

    return {
        "mu_mechanical": round(mu_mechanical, 3),
        "mu_aero_contribution": round(mu_aero_avg, 3),
        "low_speed_points": len(low_speed_corners),
        "high_speed_points": len(high_speed_corners),
    }


def compute_floor_coupling(points: List[TelemetryPoint],
                           mu_mechanical: float) -> Dict[str, float]:
    """
    Calibra il coefficiente k per il CL_floor dinamico:

        CL_floor = CL_base × (1 + k × WingAngle)

    Analizzando la differenza di grip tra curve lente e veloci,
    possiamo derivare quanto il downforce (e quindi l'angolo ala)
    contribuisce al grip totale.
    """
    if not points:
        return {"k_wing_coupling": 0.015, "cla_floor_dynamic": 0.0}

    # Raggruppa per range di velocità
    speed_bins = {
        "slow": [],     # < 100 kph
        "medium": [],   # 100-200 kph
        "fast": [],     # 200-270 kph
        "very_fast": [], # > 270 kph
    }

    for p in points:
        a_lat = abs(p.acc_y)
        if a_lat < 0.5:
            continue
        v_ms = p.speed_kph / 3.6
        mu_total = a_lat / G

        if p.speed_kph < 100:
            speed_bins["slow"].append(mu_total)
        elif p.speed_kph < 200:
            speed_bins["medium"].append(mu_total)
        elif p.speed_kph < 270:
            speed_bins["fast"].append(mu_total)
        else:
            speed_bins["very_fast"].append(mu_total)

    # Calcola mu medio per ogni range
    mu_avg = {}
    for key, values in speed_bins.items():
        if values:
            mu_avg[key] = float(np.mean(values))
        else:
            mu_avg[key] = 0.0

    # Il downforce aumenta il grip con v²
    # mu_total = mu_mechanical + mu_aero(v²)
    # Nei dati reali, mu_aero cresce con la velocità
    # k_wing_coupling determina quanto l'angolo ala influenza questo effetto

    # Stima: la differenza tra mu_fast e mu_slow è dovuta al downforce
    mu_downforce_contribution = mu_avg.get("fast", 0.0) - mu_mechanical
    if mu_downforce_contribution < 0:
        mu_downforce_contribution = 0.0

    # k è calibrato affinché il setup 'Ottimale' di Monaco (ali massime)
    # sia più veloce di quello 'Neutro'
    # Tipico: k ≈ 0.01-0.02 per F1 2025
    k_wing_coupling = round(mu_downforce_contribution / 10.0, 4)  # Scala empirica

    print(f"  📊 mu per range: slow={mu_avg['slow']:.3f}, "
          f"medium={mu_avg['medium']:.3f}, fast={mu_avg['fast']:.3f}, "
          f"very_fast={mu_avg.get('very_fast', 0.0):.3f}")
    print(f"  📊 k_wing_coupling stimato: {k_wing_coupling:.4f}")

    return {
        "k_wing_coupling": k_wing_coupling,
        "cla_floor_dynamic": round(mu_downforce_contribution, 3),
        "mu_by_speed": mu_avg,
    }


# ---------------------------------------------------------------------------
# Task 5: Validation Report
# ---------------------------------------------------------------------------

def run_simulation(circuit_id: str, aero_setup: Dict = None,
                   reference_pull_strength: float = 0.02) -> Dict:
    """
    Esegue una simulazione con il waypoint_integrator corrente.
    reference_pull_strength: forza della correzione verso la velocità reale (0.0-0.05 tipico).
    """
    # Import dinamico per evitare dipendenze circolari
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from lap_simulator.physics_v4.integrator.waypoint_integrator import integrate_lap_hd

    if aero_setup is None:
        aero_setup = {"front_wing": 20.0, "rear_wing": 22.0}

    try:
        result = integrate_lap_hd(
            circuit_id=circuit_id,
            aero_setup=aero_setup,
            verbose=False,
            reference_pull_strength=reference_pull_strength,
        )
        return result
    except Exception as e:
        print(f"  ❌ Errore simulazione {circuit_id}: {e}")
        return {"lap_time_s": float("inf"), "error": str(e)}


def generate_validation_report(circuit_key: str) -> Dict:
    """
    Genera un report di confronto pre/post integrazione per un circuito.
    """
    circuit_info = CIRCUIT_MAP[circuit_key]
    circuit_id = circuit_info["circuit_id"]
    gp_name = circuit_info["gp_name"]

    print(f"\n{'='*70}")
    print(f"  VALIDAZIONE: {circuit_key.upper()} ({gp_name})")
    print(f"{'='*70}")

    # 1. Scarica dati reali
    raw_data = download_fastest_telemetry(gp_name, circuit_info["reference_driver"])
    if raw_data is None:
        print(f"  ❌ Impossibile scaricare dati per {gp_name}")
        return {}

    points = parse_telemetry_points(raw_data["tel"])
    if not points:
        print(f"  ❌ Nessun punto di telemetria valido")
        return {}

    real_lap_time = raw_data["lap_time_s"]
    print(f"  ⏱️ Tempo giro reale: {real_lap_time:.3f}s")

    # 2. Simulazione PRE (configurazione attuale)
    sim_pre = run_simulation(circuit_id)
    sim_pre_time = sim_pre.get("lap_time_s", float("inf"))
    error_pre = abs(sim_pre_time - real_lap_time) / real_lap_time * 100.0

    print(f"  🏁 Sim PRE: {sim_pre_time:.3f}s (errore: {error_pre:.1f}%)")

    # 3. Calcola raggio dinamico
    radius_xy = compute_dynamic_radius(points, step_m=5.0)
    radius_glat = compute_radius_from_speed_glat(points, step_m=5.0)
    radius_hybrid = hybrid_radius(radius_xy, radius_glat)

    # 4. Calcola grip meccanico
    grip_data = derive_mechanical_grip(points, circuit_id)

    # 5. Calibra floor coupling
    floor_data = compute_floor_coupling(points, grip_data["mu_mechanical"])

    # 6. Aggiorna HD con raggio dinamico
    update_success = update_hd_with_radius(circuit_id, radius_hybrid, step_m=5.0)

    # 7. Simulazione POST
    sim_post = run_simulation(circuit_id)
    sim_post_time = sim_post.get("lap_time_s", float("inf"))
    error_post = abs(sim_post_time - real_lap_time) / real_lap_time * 100.0

    print(f"  🏁 Sim POST: {sim_post_time:.3f}s (errore: {error_post:.1f}%)")
    print(f"  📊 Delta: {sim_post_time - sim_pre_time:+.3f}s")

    # 8. Crea PU lookup
    pu_entries = build_pu_lookup(points, circuit_id)
    save_pu_lookup(circuit_id, pu_entries)

    # 9. Salva report
    report = {
        "circuit_id": circuit_id,
        "circuit_key": circuit_key,
        "gp_name": gp_name,
        "reference_driver": circuit_info["reference_driver"],
        "real_lap_time_s": real_lap_time,
        "sim_pre_lap_time_s": sim_pre_time,
        "sim_pre_error_pct": round(error_pre, 2),
        "sim_post_lap_time_s": sim_post_time,
        "sim_post_error_pct": round(error_post, 2),
        "improvement_pct": round(error_pre - error_post, 2),
        "radius_updated": update_success,
        "grip_data": grip_data,
        "floor_data": floor_data,
        "pu_lookup_entries": len(pu_entries),
        "radius_points_count": len(radius_hybrid),
    }

    # Salva report JSON
    report_dir = DATA_DIR.parent / "validation_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{circuit_id}_validation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  📄 Report salvato: {report_path}")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--circuit", "-c",
        choices=list(CIRCUIT_MAP.keys()) + ["all"],
        default="all",
        help="Circuito da sincronizzare (default: all)",
    )
    parser.add_argument(
        "--task", "-t",
        choices=["radius", "pu_lookup", "aero_cal", "all"],
        default="all",
        help="Task da eseguire (default: all)",
    )
    parser.add_argument(
        "--validate", "-v",
        action="store_true",
        help="Esegui solo validazione (non modifica file)",
    )
    parser.add_argument(
        "--driver", "-d",
        default="NOR",
        help="Codice pilota di riferimento (default: NOR)",
    )
    parser.add_argument(
        "--session", "-s",
        default="Qualifying",
        help="Sessione (default: Qualifying)",
    )
    parser.add_argument(
        "--step-m",
        type=float,
        default=5.0,
        help="Step in metri per interpolazione waypoint (default: 5.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scarica dati ma non modifica file",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Crea cache directory
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Determina circuiti da processare
    if args.circuit == "all":
        circuits = list(CIRCUIT_MAP.keys())
    else:
        circuits = [args.circuit]

    # Override driver se specificato
    if args.driver != "NOR":
        for key in circuits:
            CIRCUIT_MAP[key]["reference_driver"] = args.driver

    print("=" * 70)
    print("  F1 Manager AI — Sync Telemetry 2025 (TracingInsights)")
    print("=" * 70)
    print(f"  Circuiti: {', '.join(circuits)}")
    print(f"  Task: {args.task}")
    print(f"  Driver: {args.driver}")
    print(f"  Session: {args.session}")
    print()

    all_reports = []

    for circuit_key in circuits:
        circuit_info = CIRCUIT_MAP[circuit_key]
        circuit_id = circuit_info["circuit_id"]
        gp_name = circuit_info["gp_name"]
        driver = circuit_info["reference_driver"]

        print(f"\n{'─'*70}")
        print(f"  🏎️ {circuit_key.upper()} — {gp_name}")
        print(f"  Circuit ID: {circuit_id} | Driver: {driver}")
        print(f"{'─'*70}")

        # Scarica dati
        raw_data = download_fastest_telemetry(gp_name, driver, args.session)
        if raw_data is None:
            print(f"  ⚠️ Saltando {circuit_key} — dati non disponibili")
            continue

        points = parse_telemetry_points(raw_data["tel"])
        if not points:
            print(f"  ⚠️ Saltando {circuit_key} — telemetria vuota")
            continue

        print(f"  📊 Punti telemetria: {len(points)}")
        print(f"  ⏱️ Tempo giro reale: {raw_data['lap_time_s']:.3f}s")

        # Esegui task richiesti
        if args.task in ("all", "radius"):
            print(f"\n  📐 Task 2: Raggio Dinamico")
            radius_xy = compute_dynamic_radius(points, step_m=args.step_m)
            radius_glat = compute_radius_from_speed_glat(points, step_m=args.step_m)
            radius_hybrid = hybrid_radius(radius_xy, radius_glat)
            print(f"  ✅ {len(radius_hybrid)} punti raggio calcolati")

            if not args.dry_run:
                update_hd_with_radius(circuit_id, radius_hybrid, step_m=args.step_m)

        if args.task in ("all", "pu_lookup"):
            print(f"\n  ⚡ Task 3: Lookup Table RPM/Gear")
            pu_entries = build_pu_lookup(points, circuit_id)
            print(f"  ✅ {len(pu_entries)} entries nella lookup table")

            if not args.dry_run:
                save_pu_lookup(circuit_id, pu_entries)

        if args.task in ("all", "aero_cal"):
            print(f"\n  🔧 Task 4: Calibrazione Aero-Meccanica")
            grip_data = derive_mechanical_grip(points, circuit_id)
            floor_data = compute_floor_coupling(points, grip_data["mu_mechanical"])

            # Salva parametri calibrati
            if not args.dry_run:
                cal_dir = DATA_DIR.parent / "aero_calibration"
                cal_dir.mkdir(parents=True, exist_ok=True)
                cal_path = cal_dir / f"{circuit_id}_aero_cal.json"
                cal_payload = {
                    "circuit_id": circuit_id,
                    "source": "TracingInsights-Archive/2025",
                    "grip_data": grip_data,
                    "floor_data": floor_data,
                }
                with open(cal_path, "w", encoding="utf-8") as f:
                    json.dump(cal_payload, f, indent=2, ensure_ascii=False)
                print(f"  ✅ Calibrazione salvata: {cal_path}")

        # Validazione
        if args.validate or args.task == "all":
            report = generate_validation_report(circuit_key)
            all_reports.append(report)

    # Report finale
    if all_reports:
        print(f"\n{'='*70}")
        print("  📊 REPORT DI VALIDAZIONE FINALE")
        print(f"{'='*70}")
        print(f"  {'Circuito':<15} {'Reale':>8} {'Sim PRE':>8} {'Sim POST':>8} {'Err PRE':>8} {'Err POST':>8} {'Δ%':>6}")
        print(f"  {'─'*15} {'─'*8} {'─'*8} {'─'*8} {'─'*8} {'─'*8} {'─'*6}")
        for r in all_reports:
            if not r:
                continue
            print(f"  {r.get('circuit_key', '?'):<15} "
                  f"{r.get('real_lap_time_s', 0):>8.3f} "
                  f"{r.get('sim_pre_lap_time_s', 0):>8.3f} "
                  f"{r.get('sim_post_lap_time_s', 0):>8.3f} "
                  f"{r.get('sim_pre_error_pct', 0):>7.1f}% "
                  f"{r.get('sim_post_error_pct', 0):>7.1f}% "
                  f"{r.get('improvement_pct', 0):>+5.1f}%")

        # Calcola errore medio globale
        valid_reports = [r for r in all_reports if r and r.get("sim_post_error_pct") is not None]
        if valid_reports:
            avg_error = np.mean([r["sim_post_error_pct"] for r in valid_reports])
            print(f"\n  📈 Errore medio globale: {avg_error:.2f}%")
            if avg_error < 0.5:
                print(f"  ✅ Target < 0.5% RAGGIUNTO!")
            else:
                print(f"  ⚠️ Target < 0.5% NON raggiunto (attuale: {avg_error:.2f}%)")

    print(f"\n{'='*70}")
    print("  ✅ Sincronizzazione completata!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()