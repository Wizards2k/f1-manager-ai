"""
TEST DIAGNOSTICO: compute_drive_force in rettilineo

Verifica che l'accelerazione sia POSITIVA in rettilineo a v=321.6 kph con power=1110 kW
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lap_simulator.data_types import (
    PUState, EnvContext, AeroSetup, EngineMapName, ERSModeName
)
from lap_simulator.physics_v3.aero_mapper import map_aero_setup
from lap_simulator.physics_v3.balance_model import compute_balance, BalanceState
from lap_simulator.physics_v3.acceleration_profile import compute_drive_force
from lap_simulator.config_loader import load_circuit_config

print("="*100)
print("TEST: compute_drive_force in Straight 1 (rettilineo)")
print("="*100)
print()

# Setup
config = load_circuit_config("it-1922_monza")
env = EnvContext(air_temp_c=28.0, track_temp_c=42.0, air_density_kg_m3=1.225, wind_speed_kph=2.0)
aero_setup = AeroSetup()
aero_setup.ride_height_front_mm = 25.0
aero_setup.ride_height_rear_mm = 40.0

# Aero physics
physics_aero = map_aero_setup(
    aero_setup=aero_setup, env=env,
    v_estimate_kph=334.0, drs_active=False, config=config,
)

print(f"[AERO]")
print(f"  CLA: {physics_aero.CLA:.3f} m²")
print(f"  CDA: {physics_aero.CDA:.3f} m²")
print()

# Balance
mu_base = 1.90  # C5 SOFT
v_current_ms = 321.6 / 3.6  # 89.3 m/s
mass_kg = 803.0
radius_m = 0.0  # RETTILINEO!

balance = compute_balance(
    mu_base=mu_base, aero=physics_aero, aero_setup=aero_setup,
    v_ms=v_current_ms, radius_m=radius_m, mass_kg=mass_kg, env=env, a_long_g=0.0,
)

print(f"[BALANCE - STRAIGHT (R=0m)]")
print(f"  v: {v_current_ms:.1f} m/s ({v_current_ms*3.6:.1f} kph)")
print(f"  radius: {radius_m} m (RETTILINEO)")
print(f"  mu_base: {mu_base:.2f} (C5 SOFT)")
print(f"  mu_front_eff: {balance.mu_front_eff:.2f}")
print(f"  mu_rear_eff: {balance.mu_rear_eff:.2f}")
print(f"  Fz_front: {balance.Fz_front:.0f} N")
print(f"  Fz_rear: {balance.Fz_rear:.0f} N")
print()

# Power unit
pu_state = PUState(
    active_map=EngineMapName.QUALIFY,
    ers_mode=ERSModeName.QUALIFY,
    ice_temp_c=80.0,
    ice_power_kw=950.0,
    ers_energy_mj=2.0,
    ers_output_kw=160.0,
    fuel_kg=5.0,
)

print(f"[POWER]")
print(f"  ICE: {pu_state.ice_power_kw:.0f} kW")
print(f"  ERS: {pu_state.ers_output_kw:.0f} kW")
print(f"  Total: {pu_state.ice_power_kw + pu_state.ers_output_kw:.0f} kW")
print()

# compute_drive_force
print(f"[COMPUTE_DRIVE_FORCE]")
F_drive, a_net, wheelspin = compute_drive_force(
    v_ms=v_current_ms,
    aero=physics_aero,
    balance=balance,
    mass_kg=mass_kg,
    pu_state=pu_state,
    radius_m=radius_m,
    is_cornering=False,
    env_rho=env.air_density_kg_m3,
)

print(f"  F_drive: {F_drive:.0f} N")
print(f"  a_net: {a_net:.2f} m/s² = {a_net/9.81:.2f}g")
print(f"  wheelspin: {wheelspin}")
print()

# Interpretazione
if a_net > 0:
    print("✓ ACCELERAZIONE POSITIVA (corretto per rettilineo)")
    print(f"  Velocità aumenterà: v_new = {v_current_ms:.1f} + {a_net:.2f} * dt")
elif a_net == 0:
    print("⚠ ACCELERAZIONE NULLA (strano, dovrebbe accelerare)")
else:
    print(f"❌ ACCELERAZIONE NEGATIVA ({a_net:.2f} m/s²)")
    print(f"  Questo spiega perché la velocità scende a 11.4 kph!")
    print(f"  La decelerazione è: {abs(a_net)/9.81:.2f}g")

print()
print("="*100)
