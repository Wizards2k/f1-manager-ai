#!/usr/bin/env python3
"""Analisi dettagliata Monaco HD per verificare Hairpin."""

import json
from pathlib import Path

hd_file = Path("/Users/wizards/Sviluppo/F1 Manager AI/python_backend/data/circuits/2025/mc-1929_monaco_HD.json")

with open(hd_file, 'r') as f:
    data = json.load(f)

waypoints = data.get("waypoints", [])
print(f"Waypoints totali: {len(waypoints)}")
print("")

# Trova i 10 raggi minimi
radii_with_wp = [(wp.get("radius_m"), wp) for wp in waypoints if wp.get("radius_m") and wp.get("radius_m") > 0]
radii_with_wp.sort(key=lambda x: x[0])

print("🔍 10 CURVE PIÙ STRETTE:")
print("-" * 80)
for i, (radius, wp) in enumerate(radii_with_wp[:10], 1):
    print(f"{i:2d}. Raggio: {radius:7.1f}m | Dist: {wp['dist_m']:6.1f}m | Speed: {wp['v_ref_kph']:6.1f} kph | Section: {wp['section_kind']}")

print("")
print("🔍 10 CURVE PIÙ VELOCI:")
print("-" * 80)
for i, (radius, wp) in enumerate(radii_with_wp[-10:], 1):
    print(f"{i:2d}. Raggio: {radius:7.1f}m | Dist: {wp['dist_m']:6.1f}m | Speed: {wp['v_ref_kph']:6.1f} kph | Section: {wp['section_kind']}")

print("")
print("=" * 80)
print("✅ Analisi completata!")
