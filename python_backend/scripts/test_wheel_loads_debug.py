"""Debug: stampa i carichi per ruota durante un giro"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.integrator.waypoint_integrator import calculate_per_wheel_loads

# Test diversi scenari
scenarios = [
    ("Rettilineo max", 80.0, 9999, 20000, 80.0, 0.02),
    ("Frenata violenta", 70.0, 9999, 15000, 30.0, 0.02),
    ("Curva veloce", 50.0, 150, 10000, 50.0, 0.02),
    ("Curva lenta", 25.0, 50, 3000, 25.0, 0.02),
]

print("="*90)
print("DEBUG WHEEL LOADS (mass=750kg, balanced setup 18/11)")
print("="*90)

for name, v, r, df, v_tgt, dt in scenarios:
    loads = calculate_per_wheel_loads(
        velocity_ms=v, radius_m=r, mass_kg=750.0,
        f_downforce=df, v_target_ms=v_tgt, dt_step=dt,
        front_wing=18.0, rear_wing=11.0, circuit_id="test"
    )
    total = sum(loads.values())
    print(f"\n{name}: v={v} m/s, r={r}m, DF={df}N")
    print(f"  FL: {loads['FL']:6.2f} kN | FR: {loads['FR']:6.2f} kN")
    print(f"  RL: {loads['RL']:6.2f} kN | RR: {loads['RR']:6.2f} kN")
    print(f"  Front total: {loads['FL']+loads['FR']:6.2f} kN | Rear total: {loads['RL']+loads['RR']:6.2f} kN")
    print(f"  Total: {total:6.2f} kN (expected ~{(750*9.81+df)/1000:.1f} kN)")

print("\n" + "="*90)
print("OVERSTEER setup 12/11")
print("="*90)
for name, v, r, df, v_tgt, dt in scenarios:
    loads = calculate_per_wheel_loads(
        velocity_ms=v, radius_m=r, mass_kg=750.0,
        f_downforce=df, v_target_ms=v_tgt, dt_step=dt,
        front_wing=12.0, rear_wing=11.0, circuit_id="test"
    )
    total = sum(loads.values())
    print(f"\n{name}: v={v} m/s, r={r}m, DF={df}N")
    print(f"  FL: {loads['FL']:6.2f} kN | FR: {loads['FR']:6.2f} kN")
    print(f"  RL: {loads['RL']:6.2f} kN | RR: {loads['RR']:6.2f} kN")
    print(f"  Front total: {loads['FL']+loads['FR']:6.2f} kN | Rear total: {loads['RL']+loads['RR']:6.2f} kN")
