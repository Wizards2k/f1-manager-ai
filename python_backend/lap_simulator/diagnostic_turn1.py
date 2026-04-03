"""
Diagnostic: Turn 1 (VerySlowCorner) exit speed analysis

The main straight after Turn 1 shows:
- Simulated avg: 190.5 km/h (should be 321-347 range)
- Real avg: 340.3 km/h

This suggests the simulation exits Turn 1 at much lower speed than reality.
Real telemetry: v_exit_kph = 108.0, v_entry_kph = 347.0
Turn 1: radius_m = 668.5, v_min_kph = 73.0
"""

import sys
sys.path.insert(0, '/Users/wizards/Sviluppo/F1 Manager AI')

from python_backend.lap_simulator.physics_v3.corner_solver import solve_corner_apex_speed
from python_backend.lap_simulator.physics_v3.balance_model import compute_balance
from python_backend.lap_simulator.physics_v3.aero_mapper import map_aero_setup
from python_backend.lap_simulator.data_types import AeroSetup, DriverSkills, EnvContext

# Setup
aero_setup = AeroSetup()
driver = DriverSkills(raw_pace=70)
env = EnvContext(air_temp_c=20.0, track_temp_c=40.0, air_density_kg_m3=1.225)

# Map aero
aero = map_aero_setup(aero_setup, env, v_estimate_kph=100.0, drs_active=False)

print("="*70)
print("DIAGNOSTIC: Turn 1 (VerySlowCorner) Analysis")
print("="*70)

# Turn 1 parameters
v_entry_kph = 347.0
v_exit_real_kph = 108.0
v_min_real_kph = 73.0
radius_m = 668.5

print(f"\n[1] REAL TELEMETRY (Turn 1)")
print(f"    Entry: {v_entry_kph:.1f} km/h")
print(f"    Exit: {v_exit_real_kph:.1f} km/h")
print(f"    Min: {v_min_real_kph:.1f} km/h")
print(f"    Radius: {radius_m:.1f} m")

# Compute balance and v_apex
from python_backend.lap_simulator.physics_v3 import constants

mu_base = 1.70  # C3 compound from restored constants

v_entry_ms = v_entry_kph / 3.6
v_exit_real_ms = v_exit_real_kph / 3.6
v_min_real_ms = v_min_real_kph / 3.6

# Compute balance at entry
balance_entry = compute_balance(
    mu_base=mu_base,
    aero=aero,
    aero_setup=aero_setup,
    v_ms=v_entry_ms,
    radius_m=radius_m,
    mass_kg=798.0,
    env=env,
    a_long_g=0.0,  # Not braking yet
)

# Compute balance at apex (low speed, high lateral G)
balance_apex = compute_balance(
    mu_base=mu_base,
    aero=aero,
    aero_setup=aero_setup,
    v_ms=v_min_real_ms,
    radius_m=radius_m,
    mass_kg=798.0,
    env=env,
    a_long_g=0.0,
)

print(f"\n[2] BALANCE AT ENTRY ({v_entry_kph:.0f} km/h)")
print(f"    mu_rear_eff: {balance_entry.mu_rear_eff:.3f}")
print(f"    Fz_rear: {balance_entry.Fz_rear:.0f} N")

print(f"\n[3] BALANCE AT APEX ({v_min_real_kph:.0f} km/h)")
print(f"    mu_rear_eff: {balance_apex.mu_rear_eff:.3f}")
print(f"    Fz_rear: {balance_apex.Fz_rear:.0f} N")

# Solve v_apex using corner solver
v_apex_sim = solve_corner_apex_speed(
    radius_m=radius_m,
    aero=aero,
    balance=balance_apex,
    mass_kg=798.0,
    mu_base=mu_base,
    env_rho=env.air_density_kg_m3,
    banking_deg=0.0,
)

print(f"\n[4] CORNER SOLVER v_apex")
print(f"    Calculated: {v_apex_sim:.1f} m/s = {v_apex_sim*3.6:.1f} km/h")
print(f"    Real v_min: {v_min_real_kph:.1f} km/h")
print(f"    Match: {'✓' if abs(v_apex_sim*3.6 - v_min_real_kph) < 10 else '✗'}")

# Calculate what grip coefficient would be needed
# At v_apex, centripetal acceleration should equal available lateral grip
# a_lateral = v²/R
# Available: a_lat_max = mu * g (simplified)

a_lat_required_real = (v_min_real_ms ** 2) / radius_m  # m/s²
a_lat_available_theoretical = mu_base * constants.G

print(f"\n[5] LATERAL ACCELERATION ANALYSIS")
print(f"    At v_apex ({v_min_real_kph:.1f} km/h):")
print(f"      Centripetal needed: {a_lat_required_real:.2f} m/s² = {a_lat_required_real/constants.G:.2f}g")
print(f"      Available (μ*g): {a_lat_available_theoretical:.2f} m/s² = {a_lat_available_theoretical/constants.G:.2f}g")

# What mu would be needed for real v_min?
mu_needed_for_real = (v_min_real_ms ** 2) / (radius_m * constants.G)
print(f"    μ needed for real v_apex: {mu_needed_for_real:.3f}")
print(f"    μ_base C3: {mu_base:.3f}")
print(f"    Difference: {mu_needed_for_real - mu_base:.3f}")

# Check if v_apex calculation is clamping
print(f"\n[6] V_APEX CLAMPING CHECK")
v_max_from_lateral = (constants.MAX_LATERAL_G * radius_m * constants.G) ** 0.5
print(f"    Max v from MAX_LATERAL_G ({constants.MAX_LATERAL_G}g) and R={radius_m}m:")
print(f"      v_max = {v_max_from_lateral:.1f} m/s = {v_max_from_lateral*3.6:.1f} km/h")
print(f"    Is v_apex clamped to this limit? {v_apex_sim*3.6 > v_max_from_lateral*3.6 - 1}")

print("\n" + "="*70)
print("INTERPRETATION")
print("="*70)

if abs(v_apex_sim*3.6 - v_min_real_kph) < 5:
    print("✓ Corner solver is correctly calculating v_apex")
    print("  The issue is elsewhere (maybe exit speed calculation)")
else:
    print("✗ Corner solver v_apex doesn't match reality")
    if v_apex_sim*3.6 > v_min_real_kph:
        print("  Simulation calculates HIGHER apex speed than reality")
        print("  → Grip might be overestimated, or corner shape is different")
    else:
        print("  Simulation calculates LOWER apex speed than reality")
        print("  → Grip might be underestimated, or equation is wrong")
