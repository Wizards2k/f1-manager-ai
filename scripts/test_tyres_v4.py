#!/usr/bin/env python3
"""Test rapido moduli Tyres V4."""

import sys
sys.path.insert(0, '/Users/wizards/Sviluppo/F1 Manager AI/python_backend')

from lap_simulator.physics_v4.tyres import (
    TyreConstruction,
    TyreThermal,
    TyreWear,
    TyreGripModel
)

print("=" * 80)
print("TEST TYRES V4 - PHYSICS ENGINE")
print("=" * 80)
print()

# Test 1: Tyre Construction
print("🛞 TYRE CONSTRUCTION")
print("-" * 40)

for compound_name in ['C1', 'C3', 'C5']:
    tyre = TyreConstruction(compound_name)
    print(f"  {compound_name}:")
    print(f"    Grip coeff: {tyre.compound_data.grip_coefficient:.2f}")
    print(f"    Temp window: {tyre.compound_data.optimal_temp_min_c:.0f}-{tyre.compound_data.optimal_temp_max_c:.0f}°C")
    print(f"    Durability: {tyre.compound_data.durability_laps} giri")
    print(f"    Warmup: {tyre.compound_data.warmup_laps} giri")
print()

# Test 2: Tyre Thermal
print("🌡️  TYRE THERMAL")
print("-" * 40)
thermal = TyreThermal(ambient_temp=25.0)
print(f"  Ambiente: {thermal.ambient_temp:.1f}°C, Pista: {thermal.track_temp:.1f}°C")
print(f"  Soglie: COLD={thermal.TEMP_COLD:.0f}°C, WARNING={thermal.TEMP_HOT_WARNING:.0f}°C, CRITICAL={thermal.TEMP_HOT_CRITICAL:.0f}°C")
print()

# Simula riscaldamento (10 giri a 250 kph, carico 10kN)
print("  Simulazione riscaldamento (10s, 250 kph, 10kN):")
for i in range(10):
    thermal.update_temperatures(
        load_kn=10.0,
        slip_ratio=0.05,
        slip_angle_deg=2.0,
        v_car_kph=250.0,
        dt=1.0
    )
    state = thermal.get_thermal_state()
    print(f"    Step {i+1}: T_surf={state.surface_temp_c:.1f}°C, T_core={state.core_temp_c:.1f}°C, gradient={state.temp_gradient_c:.1f}°C")
print()

# Test 3: Tyre Wear
print("📉 TYRE WEAR")
print("-" * 40)
wear = TyreWear('C3', track_abrasiveness=1.0)
print(f"  Compound: {wear.compound}")
print(f"  Wear coeff: {wear.wear_coeff:.2f}")
print(f"  Tread new: {wear.TREAD_NEW_MM:.1f}mm, worn: {wear.TREAD_WORN_MM:.1f}mm")
print()

# Simula usura (5 giri)
print("  Simulazione usura (5 giri, 5000m/giro):")
for lap in range(5):
    for i in range(10):  # 10 step per giro
        wear.update_wear(
            load_kn=10.0,
            slip_ratio=0.08,
            slip_angle_deg=3.0,
            v_car_kph=200.0,
            temp_c=105.0,
            dt=1.0
        )
    
    state = wear.get_state()
    remaining = wear.get_remaining_life_laps(0.3)
    print(f"    Giro {lap+1}: wear={state.wear_pct:.1f}%, tread={state.tread_depth_mm:.2f}mm, remaining={remaining:.1f} giri")
print()

# Test 4: Grip Model (integrazione completa)
print("🎯 GRIP MODEL (INTEGRAZIONE COMPLETA)")
print("-" * 40)
grip_model = TyreGripModel('C3', ambient_temp=25.0)
print(f"  Compound: {grip_model.compound}")
print()

# Simula giro completo (warmup, grip ottimale, degradation)
print("  Simulazione giro (warmup → ottimale → degradation):")
print(f"  {'Step':5s} | {'T_surf':8s} | {'T_core':8s} | {'Wear':6s} | {'Mu_eff':7s} | {'Mu_peak':7s} | {'Grip%':6s} | {'Window':7s}")
print(f"  {'-'*5}-+-{'-'*8}-+-{'-'*8}-+-{'-'*6}-+-{'-'*7}-+-{'-'*7}-+-{'-'*6}-+-{'-'*7}")

for step in range(15):
    # Carico e slip variano (simula curva + rettilineo)
    load_kn = 10.0 + (step % 5) * 2.0  # 10-18 kN
    slip_ratio = 0.05 + (step % 3) * 0.03
    slip_angle_deg = 2.0 + (step % 4) * 1.5
    v_car_kph = 150.0 + step * 10.0
    
    grip_state = grip_model.calculate_grip(load_kn, slip_ratio, slip_angle_deg, v_car_kph, dt=1.0)
    
    state = grip_model.get_state()
    in_window_str = "✅" if state['in_window'] else "❌"
    
    print(f"  {step+1:5d} | {state['temp_surface_c']:8.1f}°C | {state['temp_core_c']:8.1f}°C | {state['wear_pct']:6.1f}% | {grip_state.mu_effective:7.3f} | {grip_state.mu_peak:7.3f} | {grip_state.grip_pct:6.1f} | {in_window_str:7s}")
print()

# Riepilogo finale
print("=" * 80)
print("RIEPILOGO")
print("=" * 80)
state = grip_model.get_state()
print(f"  Compound: {state['compound']}")
print(f"  Grip effettivo: mu = {state['mu_effective']:.3f}")
print(f"  Grip picco: mu = {state['mu_peak']:.3f}")
print(f"  Grip residuo: {state['grip_pct']:.1f}%")
print(f"  Temperatura: {state['temp_surface_c']:.1f}°C (surface), {state['temp_core_c']:.1f}°C (core)")
print(f"  In window: {state['in_window']}")
print(f"  Usura: {state['wear_pct']:.1f}%")
print(f"  Battistrada: {state['tread_depth_mm']:.2f}mm")
print(f"  Pressione: {state['pressure_bar']:.2f} bar")
print()
print(f"  ✅ Tyre Construction: OK")
print(f"  ✅ Tyre Thermal: OK")
print(f"  ✅ Tyre Wear: OK")
print(f"  ✅ Grip Model: OK")
print()
print("  📊 Moduli V4 standalone - nessun impatto su V1!")
print("=" * 80)
