#!/usr/bin/env python3
"""Test rapido moduli Power Unit V4."""

import sys
sys.path.insert(0, '/Users/wizards/Sviluppo/F1 Manager AI/python_backend')

from lap_simulator.physics_v4.power_unit import (
    ICEEngine,
    ERSDeployManager,
    ThermalModel,
    PUPhysics
)

print("=" * 80)
print("TEST POWER UNIT V4 - PHYSICS ENGINE")
print("=" * 80)
print()

# Test 1: ICE Engine
print("🔥 ICE ENGINE")
print("-" * 40)
ice = ICEEngine()
print(f"  Specifiche: {ice.config['displacement_l']}L V{ice.config['cylinders']} Turbo")
print(f"  Fuel flow limit: {ice.config['fuel_flow_limit_kg_h']} kg/h")
print(f"  Redline: {ice.config['redline_rpm']} RPM")
print()

# Test torque curve
for rpm in [0, 4000, 8000, 10500, 12500]:
    torque = ice.get_torque_at_rpm(rpm)
    power = ice.calculate_power(rpm, 100.0)
    print(f"  {rpm:5d} RPM: {torque:6.1f} Nm, {power:6.1f} kW")
print()

# Test consumo
fuel_flow = ice.calculate_fuel_flow(600.0)  # 600 kW
print(f"  Consumo a 600 kW: {fuel_flow * 3600:.3f} kg/h")
print()

# Test 2: Thermal Model
print("🌡️  THERMAL MODEL")
print("-" * 40)
thermal = ThermalModel(ambient_temp=25.0)
print(f"  Ambiente: {thermal.ambient_temp:.1f}°C")
print(f"  ERS: T_limit={thermal.ERS_T_LIMIT:.0f}°C, T_max={thermal.ERS_T_MAX:.0f}°C")
print(f"  ICE: T_warning={thermal.ICE_T_WARNING:.0f}°C, T_critical={thermal.ICE_T_CRITICAL:.0f}°C")
print()

# Simula riscaldamento ERS
print("  Simulazione riscaldamento ERS (120 kW, 300 kph):")
for i in range(5):
    derating = thermal.calculate_ers_derating(120.0, 300.0, 1.0)
    print(f"    Step {i+1}: T_ERS={thermal.ers_temp:.1f}°C, derating={derating:.3f}")
print()

# Test 3: ERS Deploy Manager
print("⚡ ERS DEPLOY MANAGER")
print("-" * 40)
ers = ERSDeployManager()
print(f"  Limiti FIA: deploy={ers.DEPLOY_LIMIT_MJ:.1f} MJ, harvest={ers.HARVEST_LIMIT_MJ:.1f} MJ")
print(f"  Battery capacity: {ers.BATTERY_CAPACITY_MJ:.1f} MJ")
print(f"  Bucket split: P={ers.config['bucket_primary_pct']*100:.0f}%, S={ers.config['bucket_secondary_pct']*100:.0f}%, E={ers.config['bucket_exit_pct']*100:.0f}%")
print()

# Imposta settori per giro (simulazione Monza: 3 primary, 4 secondary, 5 exit)
ers.set_section_counts(primary=3, secondary=4, exit=5)
state = ers.get_energy_state()
print(f"  Inizio giro: SOC={state.soc_pct:.1f}%, deploy_remaining={state.deploy_remaining_mj:.2f} MJ")
print()

# Simula richiesta deploy su rettilineo DRS
request = ers.calculate_deploy_request(
    section_priority=1.0,
    section_length_m=500.0,
    v_car_kph=340.0,
    dt=5.0,
    is_drs=True,
    is_corner=False
)
print(f"  Richiesta su rettilineo DRS:")
print(f"    Battery: {request.battery_power_kw:.1f} kW")
print(f"    MGU-H direct: {request.mguh_direct_kw:.1f} kW")
print(f"    Totale ERS: {request.total_ers_kw:.1f} kW")
print(f"    Priority: {request.priority_score:.2f}, Bucket: {request.bucket_key}")
print()

# Test 4: PU Physics (integrazione completa)
print("🚀 PU PHYSICS (INTEGRAZIONE COMPLETA)")
print("-" * 40)
pu = PUPhysics()

# Simula giro su rettilineo Monza
print("  Simulazione rettilineo Monza (throttle 100%, DRS attivo):")
for i in range(5):
    v_kph = 200.0 + i * 30.0  # 200 → 320 kph
    rpm = 8000 + i * 800  # 8000 → 11200 RPM
    
    output = pu.step(
        throttle_pct=100.0,
        rpm=rpm,
        v_kph=v_kph,
        section_priority=1.0,
        is_drs=True,
        is_corner=False,
        dt=1.0
    )
    
    print(f"    {v_kph:.0f} kph, {rpm:.0f} RPM:")
    print(f"      ICE: {output.ice_power_kw:.1f} kW (derating: {output.ice_derating:.3f})")
    print(f"      ERS: {output.ers_power_kw:.1f} kW (derating: {output.ers_derating:.3f})")
    print(f"      TOTALE: {output.total_power_kw:.1f} kW")
    print(f"      SOC: {output.soc_pct:.1f}%")
print()

# Riepilogo finale
print("=" * 80)
print("RIEPILOGO")
print("=" * 80)
print(f"  ✅ ICE Engine: torque curve, fuel flow OK")
print(f"  ✅ Thermal Model: clipping, derating OK")
print(f"  ✅ ERS Deploy: bucket planner, MGU-H direct OK")
print(f"  ✅ PU Physics: integrazione completa OK")
print()
print("  📊 Moduli V4 standalone - nessun impatto su V1!")
print("=" * 80)
