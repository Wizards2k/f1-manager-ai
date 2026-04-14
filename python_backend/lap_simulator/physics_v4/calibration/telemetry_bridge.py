"""
Telemetry Bridge V5.0 — Ponte tra dati reali TracingInsights e Physics Engine.

Questo modulo:
1. Scarica e cache i dati di telemetria reali (TracingInsights-Archive/2025)
2. Applica smoothing ai dati GPS (filtri da utils.py / telQ.py)
3. Calcola il raggio dinamico waypoint-per-waypoint (formula 3 punti cerchio)
4. Genera Lookup Table RPM/Gear/Speed per la Power Unit
5. Deriva parametri aero-meccanici (mu_base, k_wing_coupling)
6. Fornisce Reference Pull per il waypoint_integrator

Usage:
    from lap_simulator.physics_v4.calibration.telemetry_bridge import TelemetryBridge

    bridge = TelemetryBridge()
    ref_data = bridge.get_reference_pull("mc-1929_monaco")
    # ref_data = {dist_m: [0, 5, 10, ...], speed_kph: [...], throttle_pct: [...], ...}
"""

from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CIRCUIT_MAP = {
    # 5 circuiti originali (validati V5.0)
    "monaco": {"gp_name": "Monaco Grand Prix", "circuit_id": "mc-1929_monaco", "reference_driver": "NOR"},
    "spa": {"gp_name": "Belgian Grand Prix", "circuit_id": "be-1925_spa_francorchamps", "reference_driver": "NOR"},
    "silverstone": {"gp_name": "British Grand Prix", "circuit_id": "gb-1948_silverstone", "reference_driver": "NOR"},
    "monza": {"gp_name": "Italian Grand Prix", "circuit_id": "it-1922_monza", "reference_driver": "NOR"},
    "suzuka": {"gp_name": "Japanese Grand Prix", "circuit_id": "jp-1962_suzuka", "reference_driver": "NOR"},
    # 19 circuiti aggiuntivi (V5.1)
    "abudhabi": {"gp_name": "Abu Dhabi Grand Prix", "circuit_id": "ae-2009_yas_marina", "reference_driver": "VER"},
    "austria": {"gp_name": "Austrian Grand Prix", "circuit_id": "at-1969_spielberg", "reference_driver": "NOR"},
    "australia": {"gp_name": "Australian Grand Prix", "circuit_id": "au-1953_melbourne", "reference_driver": "NOR"},
    "baku": {"gp_name": "Azerbaijan Grand Prix", "circuit_id": "az-2016_baku", "reference_driver": "VER"},
    "bahrain": {"gp_name": "Bahrain Grand Prix", "circuit_id": "bh-2002_sakhir", "reference_driver": "PIA"},
    "saopaulo": {"gp_name": "São Paulo Grand Prix", "circuit_id": "br-1940_sao_paulo", "reference_driver": "NOR"},
    "canada": {"gp_name": "Canadian Grand Prix", "circuit_id": "ca-1978_montreal", "reference_driver": "RUS"},
    "china": {"gp_name": "Chinese Grand Prix", "circuit_id": "cn-2004_shanghai", "reference_driver": "PIA"},
    "spain": {"gp_name": "Spanish Grand Prix", "circuit_id": "es-1991_barcelona", "reference_driver": "PIA"},
    "hungary": {"gp_name": "Hungarian Grand Prix", "circuit_id": "hu-1986_budapest", "reference_driver": "LEC"},
    "imola": {"gp_name": "Emilia Romagna Grand Prix", "circuit_id": "it-1953_imola", "reference_driver": "PIA"},
    "mexico": {"gp_name": "Mexico City Grand Prix", "circuit_id": "mx-1962_mexico_city", "reference_driver": "NOR"},
    "zandvoort": {"gp_name": "Dutch Grand Prix", "circuit_id": "nl-1948_zandvoort", "reference_driver": "PIA"},
    "qatar": {"gp_name": "Qatar Grand Prix", "circuit_id": "qa-2004_lusail", "reference_driver": "PIA"},
    "jeddah": {"gp_name": "Saudi Arabian Grand Prix", "circuit_id": "sa-2021_jeddah", "reference_driver": "VER"},
    "singapore": {"gp_name": "Singapore Grand Prix", "circuit_id": "sg-2008_singapore", "reference_driver": "RUS"},
    "austin": {"gp_name": "United States Grand Prix", "circuit_id": "us-2012_austin", "reference_driver": "VER"},
    "miami": {"gp_name": "Miami Grand Prix", "circuit_id": "us-2022_miami", "reference_driver": "VER"},
    "lasvegas": {"gp_name": "Las Vegas Grand Prix", "circuit_id": "us-2023_las_vegas", "reference_driver": "NOR"},
}

BASE_URL = "https://raw.githubusercontent.com/TracingInsights-Archive/2025/main"
DATA_DIR = Path("/Users/wizards/Sviluppo/F1 Manager AI/python_backend/data/circuits/2025")
CACHE_DIR = Path(__file__).resolve().parents[3] / ".telemetry_cache_2025"

G = 9.81

# Smoothing kernel sizes (from telQ.py / utils.py)
_KERNEL_3 = np.ones(3, dtype=np.float64) / 3.0
_KERNEL_9 = np.ones(9, dtype=np.float64) / 9.0
_KERNEL_15 = np.ones(15, dtype=np.float64) / 15.0


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class ReferencePull:
    """Dati di riferimento per il Reference Pull nel waypoint_integrator.

    Contiene la velocità reale per ogni distanza del circuito,
    usata per correggere la forza motrice se la simulazione diverge.
    """
    circuit_id: str
    driver: str
    lap_time_s: float
    dist_m: np.ndarray       # Distanza [m]
    speed_kph: np.ndarray    # Velocità reale [km/h]
    throttle_pct: np.ndarray # Throttle reale [%]
    brake_pct: np.ndarray    # Brake reale [%]
    gear: np.ndarray         # Marcia reale
    rpm: np.ndarray          # RPM reali
    radius_m: np.ndarray     # Raggio dinamico calcolato [m]
    mu_mechanical: float = 0.0
    k_wing_coupling: float = 0.0
    c_aero: float = 0.0


# ---------------------------------------------------------------------------
# Smoothing Functions (from telQ.py / utils.py)
# ---------------------------------------------------------------------------

def smooth_outliers(arr: np.ndarray, threshold: float, use_abs: bool = True) -> np.ndarray:
    """Rimuove outlier sostituendoli con il valore precedente (da telQ.py)."""
    arr = arr.copy()
    if use_abs:
        mask = np.abs(arr) > threshold
    else:
        mask = arr > threshold
    if mask.any():
        indices = np.where(mask)[0]
        indices = indices[(indices >= 1) & (indices < len(arr) - 1)]
        if len(indices) > 0:
            arr[indices] = arr[indices - 1]
    return arr


def savgol_smooth(arr: np.ndarray, window: int = 11, polyorder: int = 3) -> np.ndarray:
    """Savitzky-Golay smoothing (da extract_circuit_hd.py)."""
    try:
        from scipy.signal import savgol_filter
        if len(arr) >= window:
            return savgol_filter(arr, window, polyorder)
    except ImportError:
        pass
    # Fallback: media mobile
    kernel = np.ones(window) / window
    return np.convolve(arr, kernel, mode="same")


def compute_accelerations(speed_kph: np.ndarray, time_s: np.ndarray,
                          x: np.ndarray, y: np.ndarray, z: np.ndarray,
                          dist: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calcola accelerazioni X, Y, Z (da telQ.py _compute_accelerations)."""
    vx = speed_kph / 3.6
    if vx.dtype != np.float64:
        vx = vx.astype(np.float64)
    time_f = time_s.astype(np.float64) if time_s.dtype != np.float64 else time_s
    x_f = x.astype(np.float64) if x.dtype != np.float64 else x
    y_f = y.astype(np.float64) if y.dtype != np.float64 else y
    z_f = z.astype(np.float64) if z.dtype != np.float64 else z
    dist_f = dist.astype(np.float64) if dist.dtype != np.float64 else dist

    # X acceleration
    dtime = np.gradient(time_f)
    ax = np.gradient(vx) / dtime
    ax = smooth_outliers(ax, 25.0, use_abs=False)
    ax = np.convolve(ax, _KERNEL_3, mode="same")

    # Y (lateral) acceleration
    dx = np.gradient(x_f)
    dy = np.gradient(y_f)
    ds = np.gradient(dist_f)
    theta = np.arctan2(dy, dx + 1e-10)
    theta[0] = theta[1]
    dtheta = np.gradient(np.unwrap(theta))
    dtheta = smooth_outliers(dtheta, 0.5, use_abs=True)
    C = dtheta / (ds + 0.0001)
    ay = np.square(vx) * C
    ay[np.abs(ay) > 150] = 0
    ay = np.convolve(ay, _KERNEL_9, mode="same")

    # Z acceleration
    dz = np.gradient(z_f)
    z_theta = np.arctan2(dz, dx + 1e-10)
    z_theta[0] = z_theta[1]
    z_dtheta = np.gradient(np.unwrap(z_theta))
    z_dtheta = smooth_outliers(z_dtheta, 0.5, use_abs=True)
    z_C = z_dtheta / (ds + 0.0001)
    az = np.square(vx) * z_C
    az[np.abs(az) > 150] = 0
    az = np.convolve(az, _KERNEL_9, mode="same")

    return ax, ay, az


# ---------------------------------------------------------------------------
# Radius Calculation (3-Point Circle + XY Derivative)
# ---------------------------------------------------------------------------

def compute_radius_three_point(x: np.ndarray, y: np.ndarray,
                                dist: np.ndarray) -> np.ndarray:
    """
    Calcola il raggio di curvatura usando la formula del cerchio
    passante per 3 punti (metodo geometrico puro).

    Per ogni tripletta di punti (P1, P2, P3):
        R = |AB| * |BC| * |CA| / (4 * Area)

    Dove Area è l'area del triangolo formato dai 3 punti.
    """
    n = len(x)
    radius = np.full(n, 999999.0)

    for i in range(1, n - 1):
        x1, y1 = x[i - 1], y[i - 1]
        x2, y2 = x[i], y[i]
        x3, y3 = x[i + 1], y[i + 1]

        # Area del triangolo con formula di Shoelace
        area = abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2.0

        if area < 1e-6:
            continue  # Punti allineati → raggio infinito

        # Lunghezze lati
        ab = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        bc = math.sqrt((x3 - x2) ** 2 + (y3 - y2) ** 2)
        ca = math.sqrt((x1 - x3) ** 2 + (y1 - y3) ** 2)

        # Raggio del cerchio circoscritto
        r = (ab * bc * ca) / (4.0 * area)
        radius[i] = min(r, 999999.0)

    # Primo e ultimo punto ereditano dal vicino
    radius[0] = radius[1]
    radius[-1] = radius[-2]

    return radius


def compute_radius_xy_derivative(x: np.ndarray, y: np.ndarray,
                                  dist: np.ndarray) -> np.ndarray:
    """
    Calcola il raggio usando le derivate prime e seconde (da extract_circuit_hd.py).

    k = |dx·ddy - dy·ddx| / (dx² + dy²)^(3/2)
    R = 1/k
    """
    dx = np.gradient(x, dist)
    dy = np.gradient(y, dist)
    ddx = np.gradient(dx, dist)
    ddy = np.gradient(dy, dist)

    numerator = np.abs(dx * ddy - dy * ddx)
    denominator = (dx ** 2 + dy ** 2) ** 1.5

    curvature = np.zeros_like(dist)
    valid = denominator > 1e-6
    curvature[valid] = numerator[valid] / denominator[valid]

    # Smoothing
    curvature = savgol_smooth(curvature, window=11, polyorder=3)
    curvature = np.maximum(curvature, 0.0)

    radius = np.full_like(dist, 999999.0)
    radius[curvature > 1e-5] = 1.0 / curvature[curvature > 1e-5]
    radius = np.clip(radius, 5.0, 999999.0)

    return radius


def compute_radius_speed_glat(speed_kph: np.ndarray, acc_y: np.ndarray) -> np.ndarray:
    """
    Calcola il raggio dalla velocità e accelerazione laterale.

    R = v² / |a_lat|
    """
    v_ms = speed_kph / 3.6
    a_lat = np.abs(acc_y)

    radius = np.full_like(v_ms, 999999.0)
    valid = a_lat > 0.5  # Soglia minima
    radius[valid] = v_ms[valid] ** 2 / a_lat[valid]
    radius = np.clip(radius, 5.0, 999999.0)

    return radius


def hybrid_radius(radius_3pt: np.ndarray, radius_xy: np.ndarray,
                   radius_glat: np.ndarray, speed_kph: np.ndarray) -> np.ndarray:
    """
    Combina i tre metodi:
    - 3-punti: affidabile per curve strette (GPS noise filtrato)
    - XY derivative: affidabile per curve aperte
    - speed/g_lat: affidabile per validazione incrociata

    Blend pesato in base alla velocità e raggio.
    """
    result = radius_xy.copy()  # Default: XY derivative

    for i in range(len(result)):
        r_3pt = radius_3pt[i]
        r_xy = radius_xy[i]
        r_glat = radius_glat[i]
        v = speed_kph[i]

        # In curve strette (raggio piccolo, velocità bassa), il 3-punti è più robusto
        if r_3pt < 200.0 and v < 120.0:
            weight_3pt = max(0.0, min(1.0, (200.0 - r_3pt) / 200.0))
            result[i] = r_3pt * weight_3pt + r_xy * (1.0 - weight_3pt)

        # Validazione incrociata con g_lat
        if r_glat < 5000.0 and r_3pt < 200.0:
            # Se i metodi discordano >50%, usa la media
            if abs(r_3pt - r_glat) / max(r_3pt, r_glat) > 0.5:
                result[i] = (r_3pt + r_glat) / 2.0

    return result


# ---------------------------------------------------------------------------
# Telemetry Bridge Class
# ---------------------------------------------------------------------------

class TelemetryBridge:
    """
    Ponte tra dati reali TracingInsights e Physics Engine V5.

    Scarica, cache, processa e fornisce dati di riferimento per:
    - Raggio dinamico (aggiornamento HD waypoints)
    - Reference Pull (correzione velocità nel integrator)
    - Lookup Table RPM/Gear
    - Calibrazione aero-meccanica
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Any] = {}

    def _download_json(self, url: str) -> Optional[Any]:
        """Scarica JSON con cache locale."""
        # Hash URL per nome file cache
        cache_key = url.replace("/", "_").replace(":", "")[-80:]
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "F1ManagerAI/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            with open(cache_file, "w") as f:
                json.dump(data, f)
            return data
        except Exception as e:
            print(f"  ❌ Errore download {url}: {e}")
            return None

    def _find_fastest_lap(self, laptimes: Dict) -> Tuple[int, float]:
        """Trova il giro più veloce nei laptimes."""
        times = laptimes.get("time", [])
        laps = laptimes.get("lap", [])
        best_idx, best_time = -1, float("inf")
        for i, (t, l) in enumerate(zip(times, laps)):
            if t == "None" or t is None:
                continue
            try:
                t_float = float(t)
                if 60.0 < t_float < best_time:
                    best_time = t_float
                    best_idx = i
            except (TypeError, ValueError):
                continue
        if best_idx < 0:
            raise ValueError("Nessun giro valido")
        return int(laps[best_idx]), best_time

    def get_reference_pull(self, circuit_id: str,
                           driver: str = "NOR",
                           session: str = "Qualifying") -> Optional[ReferencePull]:
        """
        Scarica e processa i dati di riferimento per un circuito.

        Returns:
            ReferencePull con velocità, throttle, brake, gear, RPM per ogni distanza
        """
        # Trova il circuito nella mappa
        circuit_key = None
        for key, info in CIRCUIT_MAP.items():
            if info["circuit_id"] == circuit_id:
                circuit_key = key
                break

        if circuit_key is None:
            # Fallback: prova con il circuit_id direttamente
            print(f"  ⚠️ Circuito {circuit_id} non nella mappa, uso diretto")
            gp_name = circuit_id
        else:
            gp_name = CIRCUIT_MAP[circuit_key]["gp_name"]

        gp_encoded = urllib.parse.quote(gp_name)
        base = f"{BASE_URL}/{gp_encoded}/{session}"

        # 1. Trova il giro più veloce
        laptimes_url = f"{base}/{driver}/laptimes.json"
        laptimes = self._download_json(laptimes_url)
        if laptimes is None:
            return None

        try:
            best_lap, best_time = self._find_fastest_lap(laptimes)
        except ValueError:
            return None

        # 2. Scarica telemetria
        tel_url = f"{base}/{driver}/{best_lap}_tel.json"
        raw = self._download_json(tel_url)
        if raw is None:
            return None

        tel = raw.get("tel", raw)
        if not tel:
            return None

        # 3. Estrai e pulisci i dati
        n = len(tel.get("time", []))
        if n < 10:
            return None

        # Estrai arrays con gestione None
        def safe_array(key: str, default: float = 0.0) -> np.ndarray:
            vals = tel.get(key, [])
            result = np.array([float(v) if v != "None" and v is not None else default for v in vals], dtype=np.float64)
            return result if len(result) == n else np.full(n, default)

        time_s = safe_array("time")
        speed_kph = safe_array("speed")
        rpm = safe_array("rpm")
        throttle_pct = safe_array("throttle")
        brake_pct = safe_array("brake")
        dist_m = safe_array("distance")
        x = safe_array("x")
        y = safe_array("y")
        z = safe_array("z")

        gear_raw = tel.get("gear", [])
        gear = np.array([int(v) if v != "None" and v is not None else 0 for v in gear_raw], dtype=np.int32)
        if len(gear) != n:
            gear = np.ones(n, dtype=np.int32)

        drs_raw = tel.get("drs", [])
        drs = np.array([int(v) if v != "None" and v is not None else 0 for v in drs_raw], dtype=np.int32)
        if len(drs) != n:
            drs = np.zeros(n, dtype=np.int32)

        # 4. Applica smoothing (da telQ.py)
        speed_kph = savgol_smooth(speed_kph, window=9, polyorder=3)
        throttle_pct = savgol_smooth(throttle_pct, window=5, polyorder=2)
        brake_pct = savgol_smooth(brake_pct, window=5, polyorder=2)

        # 5. Calcola accelerazioni
        acc_x, acc_y, acc_z = compute_accelerations(speed_kph, time_s, x, y, z, dist_m)

        # 6. Calcola raggio dinamico (3 metodi + hybrid)
        radius_3pt = compute_radius_three_point(x, y, dist_m)
        radius_xy = compute_radius_xy_derivative(x, y, dist_m)
        radius_glat = compute_radius_speed_glat(speed_kph, acc_y)
        radius_hybrid = hybrid_radius(radius_3pt, radius_xy, radius_glat, speed_kph)

        # 7. Interpola su griglia uniforme (5m)
        total_length = dist_m[-1]
        step_m = 5.0
        dist_grid = np.arange(0.0, total_length, step_m)

        speed_interp = np.interp(dist_grid, dist_m, speed_kph)
        throttle_interp = np.interp(dist_grid, dist_m, throttle_pct)
        brake_interp = np.interp(dist_grid, dist_m, brake_pct)
        gear_interp = np.interp(dist_grid, dist_m, gear.astype(float))
        rpm_interp = np.interp(dist_grid, dist_m, rpm)
        radius_interp = np.interp(dist_grid, dist_m, radius_hybrid)

        # 8. Deriva parametri aero-meccanici
        mu_mechanical, k_wing_coupling, c_aero = self._derive_aero_params(
            speed_kph, acc_y, acc_x, circuit_id=circuit_id
        )

        return ReferencePull(
            circuit_id=circuit_id,
            driver=driver,
            lap_time_s=best_time,
            dist_m=dist_grid,
            speed_kph=speed_interp,
            throttle_pct=throttle_interp,
            brake_pct=brake_interp,
            gear=gear_interp.astype(int),
            rpm=rpm_interp,
            radius_m=radius_interp,
            mu_mechanical=mu_mechanical,
            k_wing_coupling=k_wing_coupling,
            c_aero=c_aero,
        )

    def _derive_aero_params(self, speed_kph: np.ndarray,
                             acc_y: np.ndarray, acc_x: np.ndarray,
                             circuit_id: str = "") -> Tuple[float, float, float]:
        """
        Deriva mu_base meccanico, k_wing_coupling e c_aero dai dati reali.

        V5.1 FIX: Usa modello fisicamente vincolato con CL*A lookup
        per circuito (valori noti F1 2025) invece di derivare dalla telemetria.

        mu_mechanical: grip puro meccanico (compound-specific, senza downforce)
        k_wing_coupling: sensibilità del floor all'angolo ala
        c_aero: coefficiente aero per mu_aero = c_aero * v²
        """
        # Parametri fisici
        RHO = 1.225   # densità aria (kg/m³)
        MASS = 798.0   # massa totale qualifica (kg)

        # Compound-specific mu_mechanical_pure
        COMPOUND_MU = {
            "C1": 1.45, "C2": 1.50, "C3": 1.55, "C4": 1.60,
            "C5": 1.70, "C6": 1.75,
        }
        mu_mechanical = 1.55  # Default C3

        # CL*A lookup per circuito (valori noti F1 2025 qualifica)
        CLA_BY_CIRCUIT = {
            "mc-1929_monaco": 5.8, "sg-2008_singapore": 5.5,
            "hu-1986_budapest": 5.0, "nl-1948_zandvoort": 5.2,
            "jp-1962_suzuka": 4.8, "es-1991_barcelona": 4.5,
            "gb-1948_silverstone": 4.5, "it-1953_imola": 4.5,
            "br-1940_sao_paulo": 4.3, "at-1969_spielberg": 4.3,
            "us-2012_austin": 4.3, "qa-2004_lusail": 4.0,
            "ae-2009_yas_marina": 4.0, "cn-2004_shanghai": 4.0,
            "ca-1978_montreal": 4.0, "us-2022_miami": 4.0,
            "mx-1962_mexico_city": 3.8, "az-2016_baku": 3.8,
            "bh-2002_sakhir": 3.8, "sa-2021_jeddah": 3.5,
            "au-1953_melbourne": 3.8, "be-1925_spa_francorchamps": 3.5,
            "it-1922_monza": 3.0, "us-2023_las_vegas": 3.2,
        }

        cla_circuit = CLA_BY_CIRCUIT.get(circuit_id, 4.0)
        c_aero = cla_circuit * RHO / (2 * MASS * G)

        # k_wing_coupling: scala con CL*A
        k_wing_coupling = round(min(0.10, max(0.005, cla_circuit / 100.0)), 4)

        return round(mu_mechanical, 3), round(k_wing_coupling, 4), round(c_aero, 6)

    def update_hd_file(self, circuit_id: str, ref_pull: ReferencePull) -> bool:
        """Aggiorna il file HD.json con i raggi dinamici calcolati."""
        hd_path = DATA_DIR / f"{circuit_id}_HD.json"
        if not hd_path.exists():
            print(f"  ❌ File HD non trovato: {hd_path}")
            return False

        with open(hd_path, "r", encoding="utf-8") as f:
            hd_data = json.load(f)

        waypoints = hd_data.get("waypoints", [])
        if not waypoints:
            return False

        # Crea lookup dict
        radius_lookup = {}
        for i in range(len(ref_pull.dist_m)):
            radius_lookup[round(float(ref_pull.dist_m[i]), 1)] = float(ref_pull.radius_m[i])

        # Backup
        backup_path = hd_path.with_suffix(".json.backup_v5")
        if not backup_path.exists():
            import shutil
            shutil.copy2(hd_path, backup_path)

        # Aggiorna waypoints
        updated = 0
        for wp in waypoints:
            dist_key = round(wp["dist_m"], 1)
            if dist_key in radius_lookup:
                new_radius = radius_lookup[dist_key]
                old_radius = wp.get("radius_m", 999999.0)
                # Solo aggiorna se il nuovo raggio è significativamente diverso
                if abs(new_radius - old_radius) > 1.0 or new_radius < 500.0:
                    wp["radius_m"] = new_radius
                    v_ms = wp.get("v_ref_kph", 200.0) / 3.6
                    if new_radius < 999999.0:
                        wp["target_g_lat"] = round(abs(v_ms ** 2 / (new_radius * G)), 3)
                    updated += 1

        # Salva
        with open(hd_path, "w", encoding="utf-8") as f:
            json.dump(hd_data, f, indent=2, ensure_ascii=False)

        print(f"  ✅ Aggiornati {updated}/{len(waypoints)} waypoints con raggio dinamico V5")
        return True

    def save_reference_pull(self, circuit_id: str, ref_pull: ReferencePull) -> bool:
        """Salva il Reference Pull per uso nel waypoint_integrator."""
        output_dir = Path("/Users/wizards/Sviluppo/F1 Manager AI/python_backend/data/circuits/reference_pull")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{circuit_id}_reference_pull.json"

        payload = {
            "circuit_id": ref_pull.circuit_id,
            "driver": ref_pull.driver,
            "lap_time_s": ref_pull.lap_time_s,
            "mu_mechanical": ref_pull.mu_mechanical,
            "k_wing_coupling": ref_pull.k_wing_coupling,
            "step_m": 5.0,
            "total_length_m": float(ref_pull.dist_m[-1]),
            "data": {
                "dist_m": [round(float(v), 1) for v in ref_pull.dist_m],
                "speed_kph": [round(float(v), 1) for v in ref_pull.speed_kph],
                "throttle_pct": [round(float(v), 1) for v in ref_pull.throttle_pct],
                "brake_pct": [round(float(v), 1) for v in ref_pull.brake_pct],
                "gear": [int(v) for v in ref_pull.gear],
                "rpm": [round(float(v), 0) for v in ref_pull.rpm],
                "radius_m": [round(float(v), 1) for v in ref_pull.radius_m],
            },
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        print(f"  ✅ Reference Pull salvato: {output_path}")
        return True

    @staticmethod
    def load_reference_pull(circuit_id: str) -> Optional[Dict]:
        """Carica un Reference Pull precedentemente salvato.
        
        V5.5: Supporta sia il formato v1 (brake_pct continuo) che il formato v2
        (brake binario + decel_g reale). Il formato v2 è preferito perché
        il brake_pct del formato v1 ha artefatti (valori negativi, >1.0).
        
        Formato v1: {data: {dist_m, speed_kph, brake_pct, throttle_pct, gear, rpm, radius_m}}
        Formato v2: {data: {dist_m, speed_kph, brake (0/1), throttle_pct, decel_g}}
        """
        # Cerca in entrambe le posizioni possibili
        search_dirs = [
            DATA_DIR.parent / "reference_pull",
            Path(__file__).resolve().parents[2] / "data" / "circuits" / "reference_pull",
            Path("/Users/wizards/Sviluppo/F1 Manager AI/python_backend/data/circuits/reference_pull"),
        ]
        # V5.5: Preferisci formato v2 (più pulito)
        for suffix in ["_reference_pull_v2", "_reference_pull"]:
            for ref_dir in search_dirs:
                ref_path = ref_dir / f"{circuit_id}{suffix}.json"
                if ref_path.exists():
                    with open(ref_path, "r", encoding="utf-8") as f:
                        return json.load(f)
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Telemetry Bridge V5.0")
    parser.add_argument("--circuit", "-c", choices=list(CIRCUIT_MAP.keys()) + ["all"],
                        default="all", help="Circuito da processare")
    parser.add_argument("--driver", "-d", default="NOR", help="Codice pilota")
    parser.add_argument("--session", "-s", default="Qualifying", help="Sessione")
    parser.add_argument("--dry-run", action="store_true", help="Non modificare file")
    args = parser.parse_args()

    circuits = list(CIRCUIT_MAP.keys()) if args.circuit == "all" else [args.circuit]

    bridge = TelemetryBridge()

    for circuit_key in circuits:
        circuit_id = CIRCUIT_MAP[circuit_key]["circuit_id"]
        gp_name = CIRCUIT_MAP[circuit_key]["gp_name"]
        driver = CIRCUIT_MAP[circuit_key].get("reference_driver", args.driver)
        # Override con CLI se specificato esplicitamente
        if args.driver != "NOR":
            driver = args.driver

        print(f"\n{'─'*70}")
        print(f"  🏎️ {circuit_key.upper()} — {gp_name} (Driver: {driver})")
        print(f"{'─'*70}")

        ref_pull = bridge.get_reference_pull(circuit_id, driver=driver, session=args.session)
        if ref_pull is None:
            print(f"  ❌ Impossibile scaricare dati per {gp_name}")
            continue

        print(f"  ✅ {len(ref_pull.dist_m)} punti di riferimento")
        print(f"  ⏱️ Tempo giro reale: {ref_pull.lap_time_s:.3f}s")
        print(f"  📊 mu_mechanical: {ref_pull.mu_mechanical:.3f}")
        print(f"  📊 k_wing_coupling: {ref_pull.k_wing_coupling:.4f}")

        if not args.dry_run:
            bridge.update_hd_file(circuit_id, ref_pull)
            bridge.save_reference_pull(circuit_id, ref_pull)

    print(f"\n{'='*70}")
    print("  ✅ Telemetry Bridge V5.0 completato!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()