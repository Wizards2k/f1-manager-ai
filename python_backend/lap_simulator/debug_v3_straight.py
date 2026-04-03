"""
DEBUG V3 PHYSICS — Analisi dettagliata Straight 1

Straight 1 Monza: 784.5m
- Real: 8.305s (v_entry=321.6 kph, v_exit=347.0 kph)
- Sim: 22.372s (169% più lento!)

Analisi step-by-step del motore fisico per capire dove sta il problema.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lap_simulator.data_types import (
    CarState, AeroSetup, DriverSkills, SectionContext, EnvContext,
    CircuitConfig, WheelPosition, TyreCompound,
    EngineMapName, ERSModeName, SectionKind
)
from lap_simulator.config_loader import load_circuit_config
from lap_simulator.physics_v3.update_section_v3 import update_section_v3
from lap_simulator.physics_v3.aero_mapper import map_aero_setup
from lap_simulator.physics_v3.balance_model import compute_balance
from lap_simulator.physics_v3.corner_solver import solve_corner_apex_speed
import math

print("="*120)
print("DEBUG: Physics V3 — Straight 1 Monza (784.5m, 321.6→347.0 kph)")
print("="*120)
print()

# Setup reale McLaren/Norris/C5/push=10
driver_skills = DriverSkills(
    raw_pace=93, race_craft=93, aggression=86, consistency=94,
    tyre_management=88, overtaking_skill=80, defending_skill=80,
    wet_skill=75, smoothness=88, setup_finding=85,
)

aero_setup = AeroSetup()
aero_setup.ride_height_front_mm = 25.0
aero_setup.ride_height_rear_mm = 40.0

car_state = CarState(
    car_id="mclaren_norris",
    team_code="MCL",
    v_current_ms=321.6 / 3.6,  # Entry velocity
)

for pos in WheelPosition:
    from lap_simulator.data_types import TyreState
    car_state.tyres[pos] = TyreState(
        wheel_pos=pos, compound=TyreCompound.C5,
        surface_temp_c=25.0, core_temp_c=25.0, wear_pct=0.0,
    )

car_state.brakes.temp_front_c = 200.0
car_state.brakes.temp_rear_c = 200.0
car_state.pu.active_map = EngineMapName.QUALIFY
car_state.pu.ers_mode = ERSModeName.QUALIFY
car_state.pu.fuel_kg = 5.0

# Environment Monza
env = EnvContext(
    air_temp_c=28.0, track_temp_c=42.0,
    air_density_kg_m3=1.225, wind_speed_kph=2.0,
)

# Load circuit config
config = load_circuit_config("it-1922_monza")

# Create section context for Straight 1
from lap_simulator.data_types import CurveProfile
section = SectionContext(
    section_id="S1",
    name="Straight 1",
    kind=SectionKind.STRAIGHT,
    length_m=784.5,
    v_base_kph=334.0,  # Average
    v_entry_kph=321.6,
    v_exit_kph=347.0,
    v_min_kph=321.6,
    v_max_kph=347.0,
    dt_ref_s=8.305,
    curve_profile=CurveProfile(radius_m=0.0),
)

print("[INPUT STATE]")
print(f"  v_entry: {car_state.v_current_ms * 3.6:.1f} kph ({car_state.v_current_ms:.1f} m/s)")
print(f"  mass: {798.0 + car_state.pu.fuel_kg:.1f} kg")
print(f"  ICE map: {car_state.pu.active_map.value}")
print(f"  ERS mode: {car_state.pu.ers_mode.value}")
print(f"  Fuel: {car_state.pu.fuel_kg} kg")
print(f"  Tyre: {car_state.tyres[WheelPosition.LF].compound.name} (C5 SOFT)")
print()

# Step 1: Aero mapping
print("[STEP 1: AERO MAPPING]")
physics_aero = map_aero_setup(
    aero_setup=aero_setup, env=env,
    v_estimate_kph=section.v_base_kph,
    drs_active=False, config=config,
)
print(f"  CLA: {physics_aero.CLA:.3f} m²")
print(f"  CDA: {physics_aero.CDA:.3f} m²")
print(f"  DF total: {physics_aero.CLA * 0.5 * env.air_density_kg_m3 * (334/3.6)**2:.0f} N")
print()

# Step 2: Power calculation
print("[STEP 2: POWER OUTPUT]")
# For QUALIFY map: ~1047 kW total
P_ice = 950.0  # kW
P_ers = 160.0  # kW (full deployment in QUALIFY)
P_total = P_ice + P_ers
print(f"  ICE: {P_ice:.0f} kW")
print(f"  ERS: {P_ers:.0f} kW")
print(f"  Total: {P_total:.0f} kW")
print()

# Step 3: Grip calculation (C5 soft)
print("[STEP 3: GRIP (C5 SOFT)]")
# C5 grip_base = 1.90
# Thermal factor: optimal at ~115°C
mu_base = 1.90
print(f"  Base grip (C5): {mu_base:.2f}")
print(f"  Surface temp: 25°C (cold, not yet optimal)")
print(f"  Note: Temps will rise during acceleration phase")
print()

# Step 4: Balance model
print("[STEP 4: BALANCE MODEL]")
balance = compute_balance(
    mu_base=mu_base, aero=physics_aero, aero_setup=aero_setup,
    v_ms=car_state.v_current_ms, radius_m=0.0,
    mass_kg=798.0 + car_state.pu.fuel_kg, env=env, a_long_g=0.0,
)
print(f"  μ_front_eff: {balance.mu_front_eff:.2f}")
print(f"  μ_rear_eff: {balance.mu_rear_eff:.2f}")
print(f"  Fz_front: {balance.Fz_front:.0f} N")
print(f"  Fz_rear: {balance.Fz_rear:.0f} N")
print()

# Step 5: Max velocity equilibrium
print("[STEP 5: MAX VELOCITY CALCULATION]")
# At v_max: P = F_drag * v
# F_drag = 0.5 * ρ * v² * CDA + Crr * Fz
# For Monza: expect v_max around 347-350 kph

rho = env.air_density_kg_m3
cda = physics_aero.CDA
mass_kg = 798.0 + car_state.pu.fuel_kg
Crr = 0.011

# Binary search for v_max
def calc_drag_force(v_ms):
    """Calcola forza drag totale a velocità v_ms"""
    f_drag_aero = 0.5 * rho * (v_ms**2) * cda
    f_drag_rolling = Crr * balance.Fz_rear
    return f_drag_aero + f_drag_rolling

def calc_power_force(v_ms, p_w):
    """Calcola forza disponibile da potenza"""
    if v_ms < 0.1:
        return 0
    return p_w / v_ms

p_total_w = P_total * 1000.0
v_test_ms = 347.0 / 3.6  # Real exit velocity

f_drag_at_max = calc_drag_force(v_test_ms)
f_power_at_max = calc_power_force(v_test_ms, p_total_w)

print(f"  At v={v_test_ms*3.6:.1f} kph (real exit velocity):")
print(f"    F_drag: {f_drag_at_max:.0f} N")
print(f"    F_power: {f_power_at_max:.0f} N")
print(f"    Net: {f_power_at_max - f_drag_at_max:.0f} N")
print()

# Step 6: Run full update_section_v3
print("[STEP 6: FULL UPDATE_SECTION_V3]")
result = update_section_v3(
    car_state=car_state,
    aero_setup=aero_setup,
    driver_skills=driver_skills,
    section=section,
    env=env,
    config=config,
    push_level=10,
    is_qualifying=True,
    circuit_id="it-1922_monza",
    driver_id="NORRIS",
    lap_number=1,
)

print(f"  dt_s: {result.dt_s:.3f}s")
print(f"  v_exit: {result.v_exit_kph:.1f} kph")
print(f"  v_max: {result.v_max_kph:.1f} kph")
print(f"  Power: {result.power_kw:.0f} kW")
print()

# Analisi errore
print("[ANALISI ERRORE]")
dt_real = section.dt_ref_s
dt_sim = result.dt_s
error_s = dt_sim - dt_real
error_pct = (error_s / dt_real) * 100

print(f"  Real: {dt_real:.3f}s")
print(f"  Sim:  {dt_sim:.3f}s")
print(f"  Δ: {error_s:+.3f}s ({error_pct:+.1f}%)")
print()

# Velocità medie
v_avg_real = section.length_m / dt_real * 3.6
v_avg_sim = section.length_m / dt_sim * 3.6

print(f"  v_avg_real: {v_avg_real:.1f} kph")
print(f"  v_avg_sim:  {v_avg_sim:.1f} kph")
print(f"  Δ v_avg: {v_avg_sim - v_avg_real:+.1f} kph")
print()

print("="*120)
if error_pct < 10:
    print("✓ Accettabile (<10%)")
elif error_pct < 25:
    print("⚠ Da affinare (10-25%)")
else:
    print("❌ Significativo (>25%) — Problema nel motore di integrazione")
print("="*120)
