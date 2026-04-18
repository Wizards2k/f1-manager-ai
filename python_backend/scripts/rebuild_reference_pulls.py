#!/usr/bin/env python3
"""
Rebuild Reference Pull v2 from TracingInsights telemetry data.

This script downloads raw telemetry from TracingInsights-Archive/2025,
resamples it to 5m intervals, and calculates real deceleration (in g)
from the speed profile. The result is a cleaner, more accurate Reference Pull
that replaces the original brake_pct (which had artifacts like negative values
and values > 1.0) with:
  - brake: binary 0/1 (from TracingInsights)
  - decel_g: real deceleration in g (calculated from speed profile)
  - speed_kph: real speed (from TracingInsights)
  - throttle_pct: real throttle (from TracingInsights)

Usage:
    python scripts/rebuild_reference_pulls.py [--all] [--circuit CIRCUIT_ID]

Circuit mapping (TracingInsights name -> circuit_id):
    Monaco Grand Prix -> mc-1929_monaco
    Italian Grand Prix -> it-1922_monza
    Belgian Grand Prix -> be-1925_spa_francorchamps
    Japanese Grand Prix -> jp-1962_suzuka
    British Grand Prix -> gb-1948_silverstone
"""

import json
import math
import os
import sys
import urllib.request
from pathlib import Path

# Circuit mapping: TracingInsights GP name -> circuit_id
CIRCUIT_MAP = {
    "Monaco Grand Prix": {
        "circuit_id": "mc-1929_monaco",
        "driver": "NOR",
        "lap": 26,
        "ref_time": 71.312,
    },
    "Italian Grand Prix": {
        "circuit_id": "it-1922_monza",
        "driver": "NOR",
        "lap": None,  # Will find fastest lap
        "ref_time": 78.869,
    },
    "Belgian Grand Prix": {
        "circuit_id": "be-1925_spa_francorchamps",
        "driver": "NOR",
        "lap": None,
        "ref_time": 100.562,
    },
    "Japanese Grand Prix": {
        "circuit_id": "jp-1962_suzuka",
        "driver": "NOR",
        "lap": None,
        "ref_time": None,
    },
    "British Grand Prix": {
        "circuit_id": "gb-1948_silverstone",
        "driver": "NOR",
        "lap": None,
        "ref_time": None,
    },
}

BASE_URL = "https://raw.githubusercontent.com/TracingInsights-Archive/2025/main"


def download_telemetry(gp_name: str, driver: str = "NOR", lap: int = None) -> dict:
    """Download telemetry from TracingInsights."""
    # Try qualifying first (fastest laps)
    for session in ["Qualifying", "Race"]:
        url = f"{BASE_URL}/{gp_name}/{session}/{driver}/"
        # Try to find the lap file
        # TracingInsights format: {lap_number}_tel.json
        if lap is not None:
            tel_url = f"{BASE_URL}/{gp_name}/{session}/{driver}/{lap}_tel.json"
        else:
            # Try common qualifying lap numbers
            tel_url = None
            for l in range(20, 30):  # Q3 laps typically 20-30
                test_url = f"{BASE_URL}/{gp_name}/{session}/{driver}/{l}_tel.json"
                try:
                    resp = urllib.request.urlopen(test_url, timeout=10)
                    data = json.loads(resp.read().decode())
                    if data.get('tel', {}).get('speed', []):
                        tel_url = test_url
                        break
                except:
                    continue
        
        if tel_url is None:
            continue
        
        try:
            print(f"  Downloading: {tel_url}")
            resp = urllib.request.urlopen(tel_url, timeout=30)
            data = json.loads(resp.read().decode())
            return data
        except Exception as e:
            print(f"  Error downloading: {e}")
            continue
    
    return None


def resample_telemetry(tel_data: dict, circuit_length: float = None) -> dict:
    """Resample telemetry to 5m intervals and calculate deceleration."""
    tel = tel_data.get('tel', tel_data)
    
    dist = tel['distance']
    speed = tel['speed']
    brake = tel['brake']
    throttle = tel['throttle']
    time_s = tel.get('time', [])
    
    if not dist or not speed:
        return None
    
    # Determine circuit length
    if circuit_length is None:
        circuit_length = max(dist)
    
    # Resample to 5m intervals
    num_points = int(circuit_length / 5.0) + 1
    
    resampled = {
        'dist_m': [],
        'speed_kph': [],
        'brake': [],        # binary 0/1
        'throttle_pct': [],
        'decel_g': [],      # real deceleration in g
    }
    
    for i in range(num_points):
        target_dist = i * 5.0
        
        # Find bracketing points
        idx = 0
        for j in range(len(dist) - 1):
            if dist[j + 1] >= target_dist:
                idx = j
                break
        else:
            idx = len(dist) - 2
        
        d0 = dist[idx]
        d1 = dist[idx + 1]
        if d1 > d0:
            t = (target_dist - d0) / (d1 - d0)
            t = max(0.0, min(1.0, t))
        else:
            t = 0.0
        
        # Interpolate
        s = speed[idx] * (1 - t) + speed[idx + 1] * t
        b = 1 if (brake[idx] + brake[idx + 1]) / 2.0 > 0.5 else 0
        th = throttle[idx] * (1 - t) + throttle[idx + 1] * t
        
        resampled['dist_m'].append(round(target_dist, 1))
        resampled['speed_kph'].append(round(s, 1))
        resampled['brake'].append(b)
        resampled['throttle_pct'].append(round(th, 1))
        resampled['decel_g'].append(0.0)  # placeholder
    
    # Second pass: calculate deceleration from speed profile
    # decel = (v[i-1] - v[i]) / dt / g
    # dt = dist_step / v_avg
    for i in range(1, len(resampled['dist_m'])):
        v_prev = resampled['speed_kph'][i - 1] / 3.6  # m/s
        v_curr = resampled['speed_kph'][i] / 3.6  # m/s
        v_avg = (v_prev + v_curr) / 2.0
        if v_avg > 1.0:
            dt = 5.0 / v_avg  # 5m step
            dv = v_prev - v_curr  # positive = decelerating
            decel_ms2 = dv / dt
            decel_g = decel_ms2 / 9.81
            resampled['decel_g'][i] = round(max(0.0, decel_g), 3)  # Only positive (braking)
        else:
            resampled['decel_g'][i] = 0.0
    
    return resampled


def rebuild_reference_pull(gp_name: str, circuit_info: dict) -> bool:
    """Download and rebuild a Reference Pull from TracingInsights."""
    circuit_id = circuit_info['circuit_id']
    driver = circuit_info.get('driver', 'NOR')
    lap = circuit_info.get('lap')
    
    print(f"\n{'='*60}")
    print(f"Processing: {gp_name} -> {circuit_id}")
    print(f"{'='*60}")
    
    # Download telemetry
    tel_data = download_telemetry(gp_name, driver, lap)
    if tel_data is None:
        print(f"  ❌ Failed to download telemetry for {gp_name}")
        return False
    
    tel = tel_data.get('tel', tel_data)
    print(f"  ✅ Downloaded: {len(tel.get('speed', []))} points")
    print(f"  Lap time: {tel.get('time', [0])[-1]:.3f}s")
    
    # Load circuit length from HD waypoints
    circuits_dir = Path(__file__).resolve().parents[1] / "data" / "circuits" / "2025"
    hd_file = circuits_dir / f"{circuit_id}_HD.json"
    circuit_length = None
    if hd_file.exists():
        with open(hd_file) as f:
            hd_data = json.load(f)
        waypoints = hd_data.get('waypoints', [])
        if waypoints:
            circuit_length = waypoints[-1].get('dist_m', None)
            print(f"  Circuit length from HD: {circuit_length:.1f}m")
    
    # Resample
    resampled = resample_telemetry(tel_data, circuit_length)
    if resampled is None:
        print(f"  ❌ Failed to resample telemetry")
        return False
    
    # Build output (format compatible with TelemetryBridge.load_reference_pull)
    output = {
        'driver': driver,
        'lap_time_s': round(tel.get('time', [0])[-1], 3),
        'source': 'TracingInsights-2025',
        'format': 'v2',
        'description': f'Rebuilt from TracingInsights telemetry with real deceleration',
        'data': resampled,
    }
    
    # Save
    out_dir = Path(__file__).resolve().parents[1] / "lap_simulator" / "data" / "circuits" / "reference_pull"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{circuit_id}_reference_pull_v2.json"
    
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"  ✅ Saved: {out_path}")
    print(f"  Points: {len(resampled['dist_m'])}")
    
    # Show brake zones
    brake_zones = []
    in_brake = False
    for i in range(len(resampled['brake'])):
        if resampled['brake'][i] and not in_brake:
            in_brake = True
            start_idx = i
        elif not resampled['brake'][i] and in_brake:
            in_brake = False
            brake_zones.append((start_idx, i - 1))
    if in_brake:
        brake_zones.append((start_idx, len(resampled['brake']) - 1))
    
    print(f"  Brake zones: {len(brake_zones)}")
    for j, (si, ei) in enumerate(brake_zones):
        v_in = resampled['speed_kph'][si]
        v_out = resampled['speed_kph'][ei]
        d_start = resampled['dist_m'][si]
        d_end = resampled['dist_m'][ei]
        max_decel = max(resampled['decel_g'][si:ei + 1])
        avg_decel = sum(resampled['decel_g'][si:ei + 1]) / (ei - si + 1)
        print(f"    Zone {j + 1:2d}: {d_start:6.0f}m - {d_end:6.0f}m ({d_end - d_start:4.0f}m) | "
              f"v: {v_in:3.0f} -> {v_out:3.0f} | max: {max_decel:.2f}g avg: {avg_decel:.2f}g")
    
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Rebuild Reference Pull v2 from TracingInsights')
    parser.add_argument('--all', action='store_true', help='Rebuild all circuits')
    parser.add_argument('--circuit', type=str, help='Rebuild specific circuit (e.g., mc-1929_monaco)')
    args = parser.parse_args()
    
    if args.all:
        for gp_name, info in CIRCUIT_MAP.items():
            rebuild_reference_pull(gp_name, info)
    elif args.circuit:
        # Find circuit by ID
        for gp_name, info in CIRCUIT_MAP.items():
            if info['circuit_id'] == args.circuit:
                rebuild_reference_pull(gp_name, info)
                break
        else:
            print(f"Circuit {args.circuit} not found in CIRCUIT_MAP")
    else:
        # Default: rebuild Monaco only
        rebuild_reference_pull("Monaco Grand Prix", CIRCUIT_MAP["Monaco Grand Prix"])