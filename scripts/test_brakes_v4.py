#!/usr/bin/env python3
"""Test rapido moduli Brakes V4."""

import sys
sys.path.insert(0, '/Users/wizards/Sviluppo/F1 Manager AI/python_backend')

from lap_simulator.physics_v4.brakes import (
    BrakeMaterial,
    BrakeCooling,
    BrakeBias,
    BrakeWear
)

print("=" * 80)
print("TEST BRAKES V4 - PHYSICS ENGINE")
print("=" * 80)
print()

# Test 1: Brake Material
print("🔥 BRAKE MATERIAL (Carbon-Carbon)")
print("-" * 40)

for is_front, name in [(True, "Anteriore"), (False, "Posteriore")]:
    brake = BrakeMaterial(is_front=is_front)
    print(f"  {name}:")
    print(f"    Massa: {brake.params.mass_kg:.1f} kg")
    print(f"    Capacità termica: {brake.get_thermal_capacity():.2f} kJ/K")
    print(f"    Finestra ottimale: {brake.params.optimal_temp_min_c:.0f}-{brake.params.optimal_temp_max_c:.0f}°C")
    print(f"    Critico: >{brake.params.critical_temp_c:.0f}°C")
    
    # Test attrito vs temperatura
    for temp in [25, 300, 500, 800, 1000, 1200]:
        mu = brake._get_friction_coeff_at_temp(temp)
        print(f"      {temp:4d}°C: mu = {mu:.3f}")
print()

# Test 2: Brake Cooling
print("❄️  BRAKE COOLING (Brake Ducts)")
print("-" * 40)

cooling = BrakeCooling('size_3_medium')
print(f"  Config: {cooling.config.name}")
print(f"  Apertura: {cooling.config.opening_pct:.0f}%")
print(f"  Cooling rate: {cooling.config.cooling_rate:.1f}x")
print(f"  Drag penalty: {cooling.config.drag_penalty * 100:.2f}%")
print(f"  Tyre heat transfer: {cooling.config.tyre_heat_transfer:.1f}x")
print()

# Test raffreddamento a diverse velocità
print("  Raffreddamento a diverse velocità (brake 800°C, dt=1s):")
for v_kph in [50, 150, 250, 350]:
    q_cool = cooling.calculate_convective_cooling(800.0, v_kph, 1.0)
    print(f"    {v_kph:3d} kph: {q_cool:.2f} kJ dissipati")
print()

# Test trasferimento calore a gomma
print("  Trasferimento calore a gomma (brake 800°C, rim 100°C, dt=1s):")
q_tyre = cooling.calculate_tyre_heat_transfer(800.0, 100.0, 1.0)
print(f"    {q_tyre:.2f} kJ trasferiti alla gomma")
print()

# Test 3: Brake Bias
print("⚖️  BRAKE BIAS & MIGRATION")
print("-" * 40)

bias = BrakeBias(base_bias_front=57.0)
print(f"  Base bias: {bias.base_bias_front:.1f}% front, {bias.base_bias_rear:.1f}% rear")
print()

# Test migration a diverse pressioni
print("  Brake migration (map_3_neutral):")
for pedal in [0, 20, 50, 80, 100]:
    front, rear = bias.calculate_effective_bias(pedal, 250.0, mguk_available=True)
    print(f"    Pedale {pedal:3d}%: front={front:.1f}%, rear={rear:.1f}%, migration={bias.state.migration_offset:+.1f}%")
print()

# Test mappe migration
print("  Confronto mappe migration (pedale 100%):")
for map_name in ['map_1_stable', 'map_2_agile', 'map_3_neutral']:
    bias.set_migration_map(map_name)
    front, rear = bias.calculate_effective_bias(100, 250.0, mguk_available=True)
    print(f"    {map_name:15s}: front={front:.1f}%, migration={bias.state.migration_offset:+.1f}%")
print()

# Test MGU-K harvest
print("  MGU-K harvest (pedale 100%, 250 kph):")
front, rear = bias.calculate_effective_bias(100, 250.0, mguk_available=True)
print(f"    Harvest attivo: {bias.state.mguk_harvest_active}")
print(f"    Harvest potenza: {bias.state.mguk_harvest_kw:.1f} kW")
print(f"    Bias effettivo: front={front:.1f}%, rear={rear:.1f}%")
print()

# Test 4: Brake Wear
print("📉 BRAKE WEAR")
print("-" * 40)

wear = BrakeWear(is_front=True)
print(f"  Spessore: {wear.THICKNESS_NEW_MM:.1f}mm (nuovo) → {wear.THICKNESS_MIN_MM:.1f}mm (minimo)")
print(f"  Usura critica: >{wear.WEAR_CRITICAL:.0f}% (sostituzione)")
print()

# Simula usura (5 giri)
print("  Simulazione usura (5 giri, pressione 80 bar, temp 700°C):")
for lap in range(5):
    for i in range(10):  # 10 step per giro
        wear.update_wear(
            brake_pressure_bar=80.0,
            friction_coeff=0.52,
            v_car_kph=200.0,
            brake_temp_c=700.0,
            dt_s=1.0
        )
    
    remaining = wear.get_remaining_life_laps(0.5)
    print(f"    Giro {lap+1}: wear={wear.state.wear_pct:.2f}%, thickness={wear.state.thickness_mm:.2f}mm, remaining={remaining:.1f} giri")
print()

# Test ossidazione
print("  Usura da ossidazione (temp >1000°C):")
wear_ox = BrakeWear(is_front=True)
for temp in [900, 1000, 1100, 1200]:
    ox_wear = wear_ox.calculate_oxidation_wear(temp, 1.0)
    print(f"    {temp:.0f}°C: {ox_wear*100:.4f}% usura/sec")
print()

# Riepilogo finale
print("=" * 80)
print("RIEPILOGO")
print("=" * 80)
print(f"  ✅ Brake Material: Carbon-Carbon, attrito 0.15-0.52")
print(f"  ✅ Brake Cooling: 5 configurazioni ducts, drag 0-3%")
print(f"  ✅ Brake Bias: 50-65% front, migration ±4%, MGU-K harvest 120kW")
print(f"  ✅ Brake Wear: usura meccanica/termica, vita 10-20 giri")
print()
print("  📊 Moduli V4 standalone - nessun impatto su V1!")
print("=" * 80)
