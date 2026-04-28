"""Analyze braking zones in Monaco reference pull."""
import json

with open('../python_backend/lap_simulator/data/circuits/reference_pull/mc-1929_monaco_reference_pull.json') as f:
    data = json.load(f)

bp = data['data']['brake_pct']
dist = data['data']['dist_m']
spd = data['data']['speed_kph']

# Find braking zones (consecutive points with brake_pct > 0.1)
zones = []
in_zone = False
start = 0
for i in range(len(bp)):
    if bp[i] > 0.1 and not in_zone:
        start = i
        in_zone = True
    elif bp[i] <= 0.1 and in_zone:
        max_brake = max(bp[start:i])
        avg_brake = sum(bp[start:i]) / (i - start)
        zones.append((dist[start], dist[i-1], max_brake, avg_brake, i - start))
        in_zone = False
if in_zone:
    max_brake = max(bp[start:])
    avg_brake = sum(bp[start:]) / len(bp[start:])
    zones.append((dist[start], dist[-1], max_brake, avg_brake, len(bp) - start))

print(f'Braking zones: {len(zones)}')
for z in zones:
    print(f'  {z[0]:.0f}-{z[1]:.0f}m: max_brake={z[2]:.2f}, avg_brake={z[3]:.2f}, {z[4]}pts')