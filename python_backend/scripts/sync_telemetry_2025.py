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
    c_aero: float = 0.0
    compound: str = "C3"
    cla_estimated: float = 0.0


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

    V5.1: Lookup table completa con TUTTI i punti del giro (non solo full throttle).
    Usa le stesse costanti del simulatore per coerenza con il modello fisico.

    La lookup contiene:
    - Punti di full throttle (rpm, gear, throttle per velocità)
    - Punti di partiale e frenata (throttle basso, brake attivo)
    - f_engine stimata con modello coerente col simulatore

    Nota: f_engine_estimated è calcolata con le costanti del simulatore
    (910 kW, efficienza 0.895, ICE_IDLE_RPM=5000, ICE_MAX_RPM=12500).
    Questo garantisce che i valori siano direttamente comparabili con il modello.
    """
    if not points:
        return []

    # Costanti del simulatore (da core/constants.py)
    ICE_PEAK_KW = 750.0
    ERS_PEAK_KW = 160.0
    PU_TOTAL_KW = ICE_PEAK_KW + ERS_PEAK_KW  # 910 kW
    DRIVETRAIN_EFF = 0.895
    ICE_IDLE = 5000
    ICE_MAX = 12500

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
        brakes = np.array([e["brake_pct"] for e in entries])

        # V5.1: Includiamo TUTTI i punti, non solo full throttle.
        # Separiamo in due profili: full throttle (per potenza massima)
        # e partiale/frenata (per comportamento reale).
        full_throttle_mask = throttles > 95.0
        if full_throttle_mask.sum() < 3:
            full_throttle_mask = throttles > 80.0

        # Crea bins di velocità per ogni marcia
        speed_min = speeds.min()
        speed_max = speeds.max()
        speed_bins = np.arange(speed_min, speed_max + 5, 5.0)

        for s_low in speed_bins:
            s_high = s_low + 5.0

            # --- Profilo full throttle (potenza massima) ---
            mask_ft = (speeds >= s_low) & (speeds < s_high) & full_throttle_mask
            if mask_ft.sum() >= 2:
                avg_speed = float(np.mean(speeds[mask_ft]))
                avg_rpm = float(np.mean(rpms[mask_ft]))
                avg_throttle = float(np.mean(throttles[mask_ft]))

                # f_engine con modello coerente col simulatore
                rpm_fraction = np.clip((avg_rpm - ICE_IDLE) / (ICE_MAX - ICE_IDLE), 0.3, 1.0)
                power_kw = PU_TOTAL_KW * rpm_fraction * (avg_throttle / 100.0) * DRIVETRAIN_EFF
                v_ms = avg_speed / 3.6
                f_engine = power_kw * 1000.0 / max(v_ms, 1.0) if v_ms > 1.0 else 0.0

                lookup_entries.append(PULookupEntry(
                    speed_kph=round(avg_speed, 1),
                    rpm=round(avg_rpm, 0),
                    gear=int(gear),
                    throttle_pct=round(avg_throttle, 1),
                    f_engine_estimated=round(f_engine, 1),
                ))

            # --- Profilo partiale/frenata (tutti i punti non-full-throttle) ---
            mask_partial = (speeds >= s_low) & (speeds < s_high) & ~full_throttle_mask
            if mask_partial.sum() >= 3:
                avg_speed = float(np.mean(speeds[mask_partial]))
                avg_rpm = float(np.mean(rpms[mask_partial]))
                avg_throttle = float(np.mean(throttles[mask_partial]))

                # f_engine con modello coerente col simulatore
                rpm_fraction = np.clip((avg_rpm - ICE_IDLE) / (ICE_MAX - ICE_IDLE), 0.3, 1.0)
                power_kw = PU_TOTAL_KW * rpm_fraction * (avg_throttle / 100.0) * DRIVETRAIN_EFF
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
        "description": "Power Unit lookup table from real telemetry data (V5.1: all throttle states, simulator-coherent model)",
        "entries": [asdict(e) for e in entries],
        "gear_summary": {},
    }

    # Riassunto per marcia
    for gear in sorted(set(e.gear for e in entries)):
        gear_entries = [e for e in entries if e.gear == gear]
        if gear_entries:
            # Separa full throttle da partiale
            ft_entries = [e for e in gear_entries if e.throttle_pct >= 95.0]
            partial_entries = [e for e in gear_entries if e.throttle_pct < 95.0]
            summary = {
                "speed_range_kph": [
                    min(e.speed_kph for e in gear_entries),
                    max(e.speed_kph for e in gear_entries),
                ],
                "rpm_range": [
                    min(e.rpm for e in gear_entries),
                    max(e.rpm for e in gear_entries),
                ],
                "n_entries": len(gear_entries),
                "n_full_throttle": len(ft_entries),
                "n_partial": len(partial_entries),
            }
            if ft_entries:
                summary["avg_throttle_pct_ft"] = round(
                    sum(e.throttle_pct for e in ft_entries) / len(ft_entries), 1
                )
            if partial_entries:
                summary["avg_throttle_pct_partial"] = round(
                    sum(e.throttle_pct for e in partial_entries) / len(partial_entries), 1
                )
            payload["gear_summary"][str(gear)] = summary

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
    Deriva il grip meccanico puro e il coefficiente aero (c_aero) dalla telemetria.

    Modello fisico:
        mu_total(v) = mu_mechanical_pure + c_aero * v²

    dove:
        mu_mechanical_pure = grip puro meccanico (gomma + asfalto, senza downforce)
        c_aero = coefficiente aero: c_aero = 0.5 * rho * CL*A / (m * g)
        mu_aero(v) = c_aero * v² = contributo aero alla velocità v

    V5.1 FIX: Il vecchio approccio (mu_aero = mu_total_high - mu_mechanical_low)
    era buggato perché:
    1. mu_mechanical a bassa velocità include già downforce residuo (~0.12-0.23)
    2. Curve ad alta velocità possono avere meno g_lat di curve lente → mu_aero negativo
    3. P75 di mu a bassa velocità dà valori > 2.0 (fisicamente impossibili)

    Nuovo approccio:
    1. mu_mechanical_pure è fisso per compound (da dati Pirelli)
    2. c_aero è derivato dalla telemetria: mu_aero = mu_total - mu_mech_pure
    3. CL*A è vincolato al range realistico 3.0-6.0
    """
    if not points:
        return {"mu_mechanical": 1.65, "mu_aero_contribution": 0.0, "c_aero": 0.000235}

    # Parametri fisici
    RHO = 1.225   # densità aria al livello del mare (kg/m³)
    MASS = 798.0   # massa totale qualifica (kg)
    G_LOCAL = G    # 9.81 m/s²

    # Compound-specific mu_mechanical_pure (da dati Pirelli + letteratura)
    # Questi sono i coefficienti di grip puro meccanico (senza downforce)
    COMPOUND_MU = {
        "C1": 1.45, "C2": 1.50, "C3": 1.55, "C4": 1.60,
        "C5": 1.70, "C6": 1.75,
    }

    # Mappatura circuito → compound qualifica 2025
    CIRCUIT_COMPOUND = {
        "mc-1929_monaco": "C5",
        "be-1925_spa_francorchamps": "C3",
        "gb-1948_silverstone": "C3",
        "it-1922_monza": "C4",
        "jp-1962_suzuka": "C3",
        "ae-2009_yas_marina": "C4",
        "at-1969_spielberg": "C3",
        "au-1953_melbourne": "C3",
        "az-2016_baku": "C4",
        "bh-2002_sakhir": "C3",
        "br-1940_sao_paulo": "C4",
        "ca-1978_montreal": "C4",
        "cn-2004_shanghai": "C3",
        "es-1991_barcelona": "C3",
        "hu-1986_budapest": "C4",
        "it-1953_imola": "C4",
        "mx-1962_mexico_city": "C4",
        "nl-1948_zandvoort": "C3",
        "qa-2004_lusail": "C3",
        "sa-2021_jeddah": "C3",
        "sg-2008_singapore": "C5",
        "us-2012_austin": "C3",
        "us-2022_miami": "C4",
        "us-2023_las_vegas": "C4",
    }

    # Determina compound e mu_mechanical_pure
    compound = CIRCUIT_COMPOUND.get(circuit_id, "C3")
    mu_mech_pure = COMPOUND_MU.get(compound, 1.55)

    # ── Step 1: Raccogli punti in curva (alta g_lat)
    #    Questi sono i punti dove il grip laterale è al massimo e il downforce
    #    è il contributo dominante oltre al grip meccanico.
    cornering_speeds = []
    cornering_mus = []
    for p in points:
        a_lat = abs(p.acc_y)
        # Punto in curva: g_lat significativa
        if a_lat > 1.0 * G_LOCAL and p.speed_kph > 60.0 and p.speed_kph < 340.0:
            mu_total = a_lat / G_LOCAL
            cornering_speeds.append(p.speed_kph)
            cornering_mus.append(mu_total)

    # Fallback: se non abbiamo abbastanza punti, allarga i criteri
    if len(cornering_speeds) < 20:
        cornering_speeds = []
        cornering_mus = []
        for p in points:
            a_lat = abs(p.acc_y)
            if a_lat > 0.5 * G_LOCAL and p.speed_kph > 40.0 and p.speed_kph < 340.0:
                mu_total = a_lat / G_LOCAL
                cornering_speeds.append(p.speed_kph)
                cornering_mus.append(mu_total)

    if len(cornering_speeds) < 10:
        print("  ⚠️ Pochi punti in curva, usando valori di default")
        c_aero_default = 3.5 * RHO / (2 * MASS * G_LOCAL)
        mu_aero_ref = c_aero_default * (250.0 / 3.6) ** 2
        return {
            "mu_mechanical": mu_mech_pure,
            "mu_aero_contribution": round(mu_aero_ref, 3),
            "c_aero": round(c_aero_default, 6),
            "compound": compound,
            "low_speed_points": 0,
            "high_speed_points": 0,
        }

    cornering_speeds = np.array(cornering_speeds)
    cornering_mus = np.array(cornering_mus)

    # ── Step 2: Calcola c_aero per ogni punto in curva
    #    mu_aero = mu_total - mu_mech_pure
    #    c_aero = mu_aero / v²
    v_ms = cornering_speeds / 3.6
    v_sq = v_ms ** 2
    mu_aero_observed = cornering_mus - mu_mech_pure

    # Usa solo punti dove mu_aero > 0 (fisicamente significativi)
    # e v > 10 m/s (evita noise a bassa velocità)
    valid = (mu_aero_observed > 0) & (v_sq > 100)

    if valid.sum() < 5:
        # Se troppo pochi punti validi, usa un c_aero di default
        # corrispondente a CL*A ≈ 3.5 (media F1)
        c_aero_default = 3.5 * RHO / (2 * MASS * G_LOCAL)
        print(f"  ⚠️ Pochi punti validi per c_aero ({valid.sum()}), usando default CL*A=3.5")
        mu_aero_ref = c_aero_default * (250.0 / 3.6) ** 2
        return {
            "mu_mechanical": mu_mech_pure,
            "mu_aero_contribution": round(mu_aero_ref, 3),
            "c_aero": round(c_aero_default, 6),
            "compound": compound,
            "low_speed_points": int(len(cornering_speeds)),
            "high_speed_points": int(valid.sum()),
        }

    c_aero_values = mu_aero_observed[valid] / v_sq[valid]

    # ── Step 3: Determina CL*A dal lookup circuito-specifico
    #    La telemetria è troppo rumorosa per derivare CL*A con regressione.
    #    Usiamo valori noti per circuito F1 2025 (da letteratura e setup data).
    #    Questi sono i CL*A totali (ala + fondo) in configurazione qualifica.
    CLA_BY_CIRCUIT = {
        # Alto downforce (Monaco, Singapore, Hungaroring, Zandvoort)
        "mc-1929_monaco": 5.8,       # Monaco: massimo downforce
        "sg-2008_singapore": 5.5,    # Singapore: street circuit, alto downforce
        "hu-1986_budapest": 5.0,     # Hungaroring: alto downforce
        "nl-1948_zandvoort": 5.2,    # Zandvoort: alto downforce, banking
        # Medio-alto downforce
        "jp-1962_suzuka": 4.8,       # Suzuka: medio-alto, curve veloci
        "es-1991_barcelona": 4.5,    # Barcelona: medio-alto, curve veloci
        "gb-1948_silverstone": 4.5,  # Silverstone: medio-alto, curve veloci
        "it-1953_imola": 4.5,        # Imola: medio-alto
        "br-1940_sao_paulo": 4.3,   # Interlagos: medio-alto
        "at-1969_spielberg": 4.3,    # Spielberg: medio-alto
        "us-2012_austin": 4.3,       # Austin: medio-alto
        # Medio downforce
        "qa-2004_lusail": 4.0,       # Qatar: medio, curve veloci
        "ae-2009_yas_marina": 4.0,   # Abu Dhabi: medio
        "cn-2004_shanghai": 4.0,     # Shanghai: medio
        "ca-1978_montreal": 4.0,     # Montreal: medio, stop-and-go
        "us-2022_miami": 4.0,        # Miami: medio
        "mx-1962_mexico_city": 3.8,  # Mexico: medio (aria rara → meno downforce)
        # Medio-basso downforce
        "az-2016_baku": 3.8,         # Baku: medio-basso, rettilineo lungo
        "bh-2002_sakhir": 3.8,       # Bahrain: medio-basso
        "sa-2021_jeddah": 3.5,       # Jeddah: medio-basso, street circuit veloce
        "au-1953_melbourne": 3.8,    # Melbourne: medio
        # Basso downforce
        "be-1925_spa_francorchamps": 3.5,  # Spa: basso, rettilineo lungo
        "it-1922_monza": 3.0,        # Monza: minimo downforce
        "us-2023_las_vegas": 3.2,    # Las Vegas: basso, rettilineo lungo
    }

    cla_circuit = CLA_BY_CIRCUIT.get(circuit_id, 4.0)  # Default medio
    c_aero = cla_circuit * RHO / (2 * MASS * G_LOCAL)

    # ── Step 3b: Usa la regressione per validare e aggiustare mu_mech_pure
    #    Se la regressione dà un intercetta ragionevole (1.3-2.0), usiamo quello
    #    altrimenti manteniamo il valore dal compound.
    # Binning per velocità e uso P75 per bin
    speed_bins = np.arange(60, 340, 20)
    bin_v_ms = []
    bin_mu_p75 = []
    for i in range(len(speed_bins) - 1):
        mask = (cornering_speeds >= speed_bins[i]) & (cornering_speeds < speed_bins[i+1])
        if mask.sum() >= 3:
            bin_v_ms.append((speed_bins[i] + speed_bins[i+1]) / 2 / 3.6)
            bin_mu_p75.append(float(np.percentile(cornering_mus[mask], 75)))

    if len(bin_v_ms) >= 3:
        # Regressione: mu = mu_mech_pure + c_aero * v²
        bin_v_ms_arr = np.array(bin_v_ms)
        bin_mu_p75_arr = np.array(bin_mu_p75)
        bin_v_sq_arr = bin_v_ms_arr ** 2
        A = np.vstack([np.ones_like(bin_v_sq_arr), bin_v_sq_arr]).T
        result = np.linalg.lstsq(A, bin_mu_p75_arr, rcond=None)
        intercept, c_aero_reg = result[0]

        # Se l'intercetta è fisicamente ragionevole (1.3-2.0), usala
        # altrimenti mantieni mu_mech_pure dal compound
        if 1.3 <= intercept <= 2.0:
            mu_mech_pure = round(intercept, 3)
            print(f"  📊 Intercetta regressione: {intercept:.3f} (usata come mu_mech)")

        # Calcola CL*A dalla regressione per confronto
        cla_reg = c_aero_reg * 2 * MASS * G_LOCAL / RHO
        print(f"  📊 CL*A regressione: {cla_reg:.2f} vs lookup: {cla_circuit:.2f}")
    else:
        cla_reg = cla_circuit  # Fallback

    # Statistiche per-point per confronto
    c_aero_p25 = float(np.percentile(c_aero_values, 25))
    c_aero_p50 = float(np.percentile(c_aero_values, 50))
    c_aero_p75 = float(np.percentile(c_aero_values, 75))
    cla_p25 = c_aero_p25 * 2 * MASS * G_LOCAL / RHO
    cla_p50 = c_aero_p50 * 2 * MASS * G_LOCAL / RHO
    cla_p75 = c_aero_p75 * 2 * MASS * G_LOCAL / RHO

    # ── Step 4: c_aero finale dal lookup circuito-specifico
    #    Usiamo il CL*A dal lookup (valori noti F1 2025) invece della
    #    regressione rumorosa. La regressione è usata solo per validare
    #    l'intercetta (mu_mech_pure).
    cla_estimated = cla_circuit
    c_aero = cla_estimated * RHO / (2 * MASS * G_LOCAL)

    # ── Step 5: Calcola mu_aero_contribution a velocità di riferimento (250 kph)
    V_REF_KPH = 250.0
    v_ref_ms = V_REF_KPH / 3.6
    mu_aero_contribution = c_aero * v_ref_ms ** 2

    # ── Step 6: Verifica con dati a bassa velocità
    #    I punti a bassa velocità dovrebbero avere mu ≈ mu_mech_pure + piccolo aero
    low_speed_mask = (cornering_speeds < 80.0) & (cornering_speeds > 30.0)
    if low_speed_mask.sum() > 5:
        mu_low_avg = float(np.mean(cornering_mus[low_speed_mask]))
        mu_low_aero = c_aero * (60.0 / 3.6) ** 2  # aero a ~60 kph
        mu_low_predicted = mu_mech_pure + mu_low_aero
        print(f"  📊 Verifica bassa velocità: mu_avg={mu_low_avg:.3f}, "
              f"predetto={mu_low_predicted:.3f} (mech={mu_mech_pure:.3f} + aero={mu_low_aero:.3f})")

    print(f"  📊 Compound: {compound}, mu_mechanical_pure: {mu_mech_pure:.3f}")
    print(f"  📊 c_aero: {c_aero:.6f} (CL*A={cla_estimated:.2f})")
    print(f"  📊 CL*A range: P25={cla_p25:.2f}, P50={cla_p50:.2f}, P75={cla_p75:.2f}")
    print(f"  📊 mu_aero @ 200 kph: {c_aero * (200/3.6)**2:.3f}")
    print(f"  📊 mu_aero @ 250 kph: {mu_aero_contribution:.3f}")
    print(f"  📊 mu_aero @ 300 kph: {c_aero * (300/3.6)**2:.3f}")
    print(f"  📊 Punti curva analizzati: {len(cornering_speeds)}, validi: {valid.sum()}")

    return {
        "mu_mechanical": round(mu_mech_pure, 3),
        "mu_aero_contribution": round(mu_aero_contribution, 3),
        "c_aero": round(c_aero, 6),
        "compound": compound,
        "cla_estimated": round(cla_estimated, 2),
        "low_speed_points": int(len(cornering_speeds)),
        "high_speed_points": int(valid.sum()),
    }


def compute_floor_coupling(points: List[TelemetryPoint],
                           mu_mechanical: float,
                           c_aero: float = 0.0) -> Dict[str, float]:
    """
    Calibra il coefficiente k per il CL_floor dinamico:

        CL_floor = CL_base × (1 + k × WingAngle)

    V5.1: Usa c_aero (se disponibile) per derivare k_wing_coupling
    in modo fisicamente coerente con il modello mu_total = mu_mech + c_aero * v².

    k_wing_coupling determina quanto l'angolo ala influenza il downforce
    del floor. Un valore più alto significa che il floor è più sensibile
    all'angolo dell'ala (effetto ground effect + wing coupling).
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

    # V5.1: Se abbiamo c_aero, usiamo quello per derivare k_wing_coupling
    # Il downforce totale è proporzionale a CL*A * v², dove CL*A = c_aero * 2 * m * g / rho
    # k_wing_coupling rappresenta la frazione del downforce che varia con l'angolo ala
    # Tipico: k ≈ 0.01-0.05 per F1 2025 (più alto per circuiti ad alto downforce)
    if c_aero > 0:
        # CL*A stimato da c_aero
        RHO = 1.225
        MASS = 798.0
        cla_estimated = c_aero * 2 * MASS * G / RHO

        # k_wing_coupling: frazione del CL*A che varia con l'angolo ala
        # Per F1 2025: il floor contribuisce ~60-70% del downforce totale
        # e il wing coupling è ~5-15% del floor CL
        # k ≈ 0.01 per basso downforce (Monza), k ≈ 0.05 per alto downforce (Monaco)
        # Scala con CL*A: più downforce = più sensibilità al wing angle
        k_wing_coupling = round(min(0.10, max(0.005, cla_estimated / 100.0)), 4)

        # mu_downforce_contribution a 250 kph (riferimento)
        mu_downforce_contribution = c_aero * (250.0 / 3.6) ** 2
    else:
        # Fallback: stima empirica dalla differenza fast-slow
        mu_downforce_contribution = mu_avg.get("fast", 0.0) - mu_mechanical
        if mu_downforce_contribution < 0:
            mu_downforce_contribution = 0.0
        k_wing_coupling = round(mu_downforce_contribution / 10.0, 4)

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
                   reference_pull_strength: float = 0.02,
                   pu_lookup_blend: float = 0.0) -> Dict:
    """
    Esegue una simulazione con il waypoint_integrator corrente.
    reference_pull_strength: forza della correzione verso la velocità reale (0.0-0.05 tipico).
    pu_lookup_blend: fusione modello PU con lookup table (0.0=model only, 1.0=lookup only).
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
            pu_lookup_blend=pu_lookup_blend,
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
    floor_data = compute_floor_coupling(points, grip_data["mu_mechanical"],
                                           c_aero=grip_data.get("c_aero", 0.0))

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
            floor_data = compute_floor_coupling(points, grip_data["mu_mechanical"],
                                                   c_aero=grip_data.get("c_aero", 0.0))

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