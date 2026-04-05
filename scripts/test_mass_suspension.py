#!/usr/bin/env python3
"""Test rapido moduli mass e suspension V4."""

import sys
sys.path.insert(0, '/Users/wizards/Sviluppo/F1 Manager AI/python_backend')

import numpy as np
from lap_simulator.physics_v4.mass import MassDistribution, CenterOfGravity, MomentOfInertia
from lap_simulator.physics_v4.suspension import SpringDamper, AntiRollBar, RideHeight

print("=" * 80)
print("TEST MODULI MASS & SUSPENSION - PHYSICS V4")
print("=" * 80)
print()

# Test Mass Distribution
print("🏋️  MASS DISTRIBUTION")
print("-" * 40)
mass_dist = MassDistribution()
state = mass_dist.get_mass_state()
print(f"  Massa totale: {state.mass_total:.1f} kg")
print(f"  Massa dry: {state.mass_dry:.1f} kg")
print(f"  Massa fuel: {state.mass_fuel:.1f} kg")
print(f"  Massa driver: {state.mass_driver:.1f} kg")
print(f"  Distribuzione front: {state.front_percentage * 100:.1f}%")
print(f"  Distribuzione rear: {state.rear_percentage * 100:.1f}%")
print(f"  Massa front: {mass_dist.get_mass_front():.1f} kg")
print(f"  Massa rear: {mass_dist.get_mass_rear():.1f} kg")
print()

# Test Center of Gravity
print("🎯 CENTER OF GRAVITY")
print("-" * 40)
cg = CenterOfGravity()
cg_pos = cg.get_cg_position(fuel_mass=100.0)
print(f"  CG X: {cg_pos.x:.3f} m ({cg_pos.x / cg.wheelbase * 100:.1f}% wheelbase)")
print(f"  CG Y: {cg_pos.y:.3f} m")
print(f"  CG Z: {cg_pos.z:.3f} m ({cg_pos.z * 1000:.0f} mm)")
print(f"  Distanza front axle: {cg.get_cg_from_front_axle():.3f} m")
print(f"  Distanza rear axle: {cg.get_cg_from_rear_axle():.3f} m")
print()

# Test Moment of Inertia
print("🔄 MOMENT OF INERTIA")
print("-" * 40)
inertia = MomentOfInertia()
inertia_tensor = inertia.get_inertia(fuel_mass=100.0)
print(f"  Ixx (roll): {inertia_tensor.ixx:.0f} kg·m²")
print(f"  Iyy (pitch): {inertia_tensor.iyy:.0f} kg·m²")
print(f"  Izz (yaw): {inertia_tensor.izz:.0f} kg·m²")
print()

# Test Spring Damper
print("🔧 SPRING & DAMPER")
print("-" * 40)
spring = SpringDamper()
force = spring.calculate_force(displacement=0.020, velocity=0.5)
print(f"  Spring rate: {spring.config['spring_rate'] / 1000:.0f} N/mm")
print(f"  Damping compression: {spring.config['damping_compression']:.0f} N·s/m")
print(f"  Damping rebound: {spring.config['damping_rebound']:.0f} N·s/m")
print(f"  Forza a 20mm/0.5m/s: {force.force:.0f} N")
print()

# Test Anti-Roll Bar
print("🔩 ANTI-ROLL BAR")
print("-" * 40)
arb = AntiRollBar()
print(f"  Stiffness: {arb.get_stiffness_nm_deg():.0f} Nm/deg")
roll_angle = np.radians(2.0)  # 2 gradi
force_arb = arb.calculate_force(roll_angle, track_width=1.60)
print(f"  Forza con 2° roll: {force_arb.force:.0f} N")
print(f"  Load transfer: {arb.get_load_transfer(roll_angle, track_width=1.60):.0f} N")
print()

# Test Ride Height
print("📏 RIDE HEIGHT")
print("-" * 40)
rh = RideHeight()
rh_state = rh.get_ride_height_state()
print(f"  Front: {rh_state.front * 1000:.1f} mm")
print(f"  Rear: {rh_state.rear * 1000:.1f} mm")
print(f"  Rake: {rh_state.rake * 180 / np.pi:.2f}°")
print(f"  Plank gap: {rh_state.plank_gap * 1000:.2f} mm")
print(f"  Plank contact: {rh.check_plank_contact()}")
print(f"  GE factor: {rh.get_ground_effect_factor():.2f}")
print()

print("=" * 80)
print("✅ TUTTI I MODULI MASS & SUSPENSION TESTATI CON SUCCESSO!")
print("=" * 80)
