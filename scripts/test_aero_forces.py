#!/usr/bin/env python3
"""Test debug forze aerodinamiche V4."""

import sys
sys.path.insert(0, '/Users/wizards/Sviluppo/F1 Manager AI/python_backend')

from lap_simulator.physics_v4.aero.aero_assembly import AeroAssembly

# Crea assembly
assembly = AeroAssembly()

# Test a 100 m/s (~360 kph)
speed = 100.0
density = 1.225

print("=" * 80)
print("TEST FORZE AERODINAMICHE V4")
print("=" * 80)
print(f"Velocità: {speed} m/s ({speed * 3.6:.1f} kph)")
print(f"Densità aria: {density} kg/m³")
print()

# Calcola forze
forces = assembly.compute_forces(
    speed_ms=speed,
    air_density=density,
    ride_height_front=0.040,
    ride_height_rear=0.050,
    drs_active=False
)

print("📊 RISULTATI:")
print(f"  CLA_total: {forces.cla_total:.3f} m²")
print(f"  CDA_total: {forces.cda_total:.3f} m²")
print(f"  L/D ratio: {forces.cla_total / max(forces.cda_total, 0.01):.2f}")
print()
print(f"  CLA_front: {forces.cla_front:.3f} m²")
print(f"  CLA_rear: {forces.cla_rear:.3f} m²")
print(f"  Aero Balance: {forces.aero_balance:.3f} ({forces.aero_balance * 100:.1f}% front)")
print()
print(f"  F_downforce: {forces.f_downforce:.0f} N")
print(f"  F_drag: {forces.f_drag:.0f} N")
print(f"  F_down_front: {forces.f_downforce_front:.0f} N")
print(f"  F_down_rear: {forces.f_downforce_rear:.0f} N")
print()

# Confronto con valori F1 reali
print("🎯 CONFRONTO CON F1 REALE:")
print(f"  CLA target: ~3.2 m² (reale F1 2025)")
print(f"  CDA target: ~1.1 m² (reale F1 2025)")
print(f"  L/D target: ~3.5-4.2 (reale F1 2025)")
print()

delta_cla = (forces.cla_total - 3.2) / 3.2 * 100
delta_cda = (forces.cda_total - 1.1) / 1.1 * 100
ld_ratio = forces.cla_total / max(forces.cda_total, 0.01)
delta_ld = (ld_ratio - 3.8) / 3.8 * 100

print(f"  Δ CLA: {delta_cla:+.1f}%")
print(f"  Δ CDA: {delta_cda:+.1f}%")
print(f"  Δ L/D: {delta_ld:+.1f}%")
print()

# Dettaglio per componente
print("🔍 DETTAGLIO PER COMPONENTE:")
for name, comp_forces in forces.component_forces.items():
    cl = comp_forces['CL']
    cd = comp_forces['CD']
    lift = comp_forces['lift']
    drag = comp_forces['drag']
    print(f"  {name:15s}: CL={cl:.3f}, CD={cd:.3f}, F_lift={lift:.0f}N, F_drag={drag:.0f}N")

print()
print("=" * 80)

# Verifica se valori sono accettabili
if 2.8 <= forces.cla_total <= 3.6 and 0.9 <= forces.cda_total <= 1.3 and 3.0 <= ld_ratio <= 4.5:
    print("✅ VALORI AERO ACCETTABILI!")
else:
    print("⚠️  VALORI AERO DA CORREGGERE")
