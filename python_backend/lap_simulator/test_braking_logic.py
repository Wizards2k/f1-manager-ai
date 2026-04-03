"""
TEST: Logica braking/acceleration nel section_integrator

Verifica perché nel Straight 1 il motore sta FRENANDO invece di ACCELERANDO
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lap_simulator.data_types import (
    SectionContext, SectionKind, CurveProfile, PUState, BrakeState, EnvContext, AeroSetup, EngineMapName, ERSModeName
)
from lap_simulator.physics_v3.braking_profile import compute_braking_distance
from lap_simulator.physics_v3.aero_mapper import map_aero_setup
from lap_simulator.config_loader import load_circuit_config

print("="*100)
print("TEST: Brake Logic in Straight 1")
print("="*100)
print()

# Setup reale Straight 1
config = load_circuit_config("it-1922_monza")
section = SectionContext(
    section_id="S1", name="Straight 1", kind=SectionKind.STRAIGHT,
    length_m=784.5, v_base_kph=334.0, v_entry_kph=321.6, v_exit_kph=347.0,
    v_min_kph=321.6, v_max_kph=347.0, dt_ref_s=8.305,
    curve_profile=CurveProfile(radius_m=0.0),
)

env = EnvContext(air_temp_c=28.0, track_temp_c=42.0, air_density_kg_m3=1.225, wind_speed_kph=2.0)
aero_setup = AeroSetup()
aero_setup.ride_height_front_mm = 25.0
aero_setup.ride_height_rear_mm = 40.0

physics_aero = map_aero_setup(
    aero_setup=aero_setup, env=env,
    v_estimate_kph=334.0, drs_active=False, config=config,
)

pu_state = PUState(
    active_map=EngineMapName.QUALIFY, ers_mode=ERSModeName.QUALIFY,
    ice_power_kw=950.0, ers_output_kw=160.0, fuel_kg=5.0,
)

brake_state = BrakeState(temp_front_c=200.0, temp_rear_c=200.0)

# Parametri inizio rettilineo
v_current_ms = 321.6 / 3.6  # 89.3 m/s
v_apex_ms = 347.0 / 3.6  # 96.4 m/s (velocità target)
distance = 0.0
section_length = 784.5
mass_kg = 803.0

print(f"[INITIAL STATE]")
print(f"  v_current: {v_current_ms*3.6:.1f} kph ({v_current_ms:.1f} m/s)")
print(f"  v_apex: {v_apex_ms*3.6:.1f} kph ({v_apex_ms:.1f} m/s)")
print(f"  section_length: {section_length} m")
print()

# Prima iterazione: calcola distance_remaining e s_brake_needed
distance_remaining = section_length - distance
print(f"[ITERATION 1 - LOOK-AHEAD]")
print(f"  distance_remaining: {distance_remaining} m")
print()

# Calcola braking distance per frenare da v_current a v_apex
s_brake_needed = compute_braking_distance(
    v_entry_ms=v_current_ms,
    v_target_ms=v_apex_ms,
    aero=physics_aero,
    brake_state=brake_state,
    mass_kg=mass_kg,
    env=env,
)

print(f"  s_brake_needed: {s_brake_needed:.1f} m")
print(f"  s_brake_needed * 1.05: {s_brake_needed * 1.05:.1f} m")
print()

# DECISIONE CRITICA
if distance_remaining <= s_brake_needed * 1.05:
    print(f"❌ DECISIONE: FRENA (perché {distance_remaining:.1f} ≤ {s_brake_needed*1.05:.1f})")
else:
    print(f"✓ DECISIONE: ACCELERA (perché {distance_remaining:.1f} > {s_brake_needed*1.05:.1f})")

print()
print(f"ANALISI:")
print(f"  v_current ({v_current_ms*3.6:.1f} kph) < v_apex ({v_apex_ms*3.6:.1f} kph)")
print(f"  → Auto dovrebbe ACCELERARE, non frenare!")
print(f"  → Se il motore sta frenando, significa che s_brake_needed è TROPPO GRANDE")
print()

# Calcola velocità di frenata per capire quanto "spazio serve"
# Se freno con a_decel = 3 m/s², quanto spazio serve per andare da 89.3 a 96.4 m/s?
# Aspetta, 96.4 > 89.3, quindi NON SERVE SPAZIO PER FRENARE!
print(f"NOTA CRITICA:")
print(f"  v_current ({v_current_ms:.1f} m/s) < v_apex ({v_apex_ms:.1f} m/s)")
print(f"  Differenza di velocità: {(v_apex_ms - v_current_ms)*3.6:.1f} kph")
print(f"  → L'auto deve ACCELERARE di {(v_apex_ms - v_current_ms)*3.6:.1f} kph")
print(f"  → s_brake_needed per DECELERARE non dovrebbe nemmeno essere calcolato!")
print()

if v_apex_ms >= v_current_ms:
    print("⚠ BUG LOGICO IDENTIFICATO:")
    print("  compute_braking_distance(v_entry=89.3, v_target=96.4)")
    print("  → Dovrebbe calcolare che NON SERVE FRENARE (v_target > v_entry)")
    print("  → Se ritorna un valore > 0, significa che la funzione sta sbagliando")
    print(f"  → Ritorno: {s_brake_needed:.1f} m")
    if s_brake_needed > 0:
        print("  → QUESTO è il bug! La funzione calcola erroneamente lo spazio di frenata")

print()
print("="*100)
