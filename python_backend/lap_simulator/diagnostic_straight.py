"""
Diagnostic: Analyze the first DRS straight (Straight 1)

Why is simulation 87 km/h slower than reality on the main DRS straight?
- Real: 340 km/h
- Sim: 253 km/h
- Delta: -87 km/h (-25.6%)

This script investigates:
1. Entry speed to straight
2. Power available
3. Drag force at speed
4. Theoretical v_max calculation
"""

import math
import sys
sys.path.insert(0, '/Users/wizards/Sviluppo/F1 Manager AI')

from python_backend.lap_simulator.physics_v3 import constants
from python_backend.lap_simulator.physics_v3.aero_mapper import map_aero_setup
from python_backend.lap_simulator.data_types import (
    AeroSetup, DriverSkills, EnvContext, SectionContext, CurveProfile, SectionKind
)

# Setup: baseline Monza
aero_setup = AeroSetup()
driver = DriverSkills(raw_pace=70)
env = EnvContext(air_temp_c=20.0, track_temp_c=40.0, air_density_kg_m3=1.225)

# Section: Straight 1 (main DRS straight)
section = SectionContext(
    section_id="sec_01",
    name="Straight 1",
    kind=SectionKind.STRAIGHT,
    length_m=784.5,
    v_base_kph=340.3,
    v_entry_kph=321.6,
    v_exit_kph=347.0,
    v_min_kph=321.6,
    v_max_kph=348.0,
    drs_available=True,
    curve_profile=CurveProfile(),
)

# Map aero to physics params - WITH DRS ACTIVE
aero_no_drs = map_aero_setup(aero_setup, env, v_estimate_kph=340.0, drs_active=False)
aero_with_drs = map_aero_setup(aero_setup, env, v_estimate_kph=340.0, drs_active=True)

print("="*70)
print("DIAGNOSTIC: DRS Straight Analysis")
print("="*70)

print(f"\n[1] REAL TELEMETRY")
print(f"    Entry speed: {section.v_entry_kph:.1f} km/h")
print(f"    Exit speed:  {section.v_exit_kph:.1f} km/h")
print(f"    Avg speed:   {section.v_base_kph:.1f} km/h")
print(f"    Section len: {section.length_m:.0f} m")
print(f"    DRS active:  {section.drs_available}")

print(f"\n[2] AERO PARAMETERS")
print(f"    WITHOUT DRS:")
print(f"      CLA = {aero_no_drs.CLA:.4f} m²")
print(f"      CDA = {aero_no_drs.CDA:.4f} m²")
print(f"    WITH DRS:")
print(f"      CLA = {aero_with_drs.CLA:.4f} m²")
print(f"      CDA = {aero_with_drs.CDA:.4f} m²")
print(f"      CDA_drs_open = {aero_with_drs.CDA_drs_open:.4f} m²")
print(f"    DRS drag reduction: {(1 - aero_with_drs.CDA_drs_open/aero_with_drs.CDA)*100:.1f}%")

# Calculate theoretical v_max
v_entry_ms = section.v_entry_kph / 3.6
v_max_real_ms = section.v_exit_kph / 3.6  # Use exit as proxy for peak

# Power available
ice_power_kw = constants.ICE_PEAK_POWER_KW
ers_power_kw = constants.ERS_PEAK_POWER_KW
total_power_kw = (ice_power_kw + ers_power_kw) * constants.DRIVETRAIN_EFFICIENCY
total_power_w = total_power_kw * 1000.0

print(f"\n[3] POWER AVAILABLE")
print(f"    ICE: {ice_power_kw:.0f} kW")
print(f"    ERS: {ers_power_kw:.0f} kW")
print(f"    Total (with drivetrain): {total_power_kw:.0f} kW ({total_power_w/1000:.0f} kW)")

# Calculate drag force at real v_max
rho = env.air_density_kg_m3
v_max_real = section.v_exit_kph / 3.6  # m/s

# Drag with DRS
F_drag_aero_drs = 0.5 * rho * (v_max_real ** 2) * aero_with_drs.CDA_drs_open
F_rolling = constants.ROLLING_RESISTANCE_COEFF * constants.MASS_DRY_KG * constants.G
F_drag_total_drs = F_drag_aero_drs + F_rolling

# Power at v_max should equal drag force * v
F_power_drs = total_power_w / v_max_real

print(f"\n[4] FORCES AT REAL V_MAX ({section.v_exit_kph:.1f} km/h)")
print(f"    Drag (aero) with DRS: {F_drag_aero_drs:.0f} N")
print(f"    Rolling resistance: {F_rolling:.0f} N")
print(f"    Total drag: {F_drag_total_drs:.0f} N")
print(f"    Force from power (P/v): {F_power_drs:.0f} N")
print(f"    Power equilibrium: {F_power_drs:.0f} N ~= {F_drag_total_drs:.0f} N ✓" if abs(F_power_drs - F_drag_total_drs) < 100 else f"    MISMATCH: {F_power_drs:.0f} vs {F_drag_total_drs:.0f}")

# Solve for theoretical v_max with current drag
# At v_max: P = F_drag * v
# P = 0.5*rho*v³*CDA + F_rolling*v
# Rearrange: 0.5*rho*CDA*v³ + F_rolling*v - P = 0

def calc_vmax_equilibrium(power_w, cda, f_rolling, rho):
    """Find v where power = drag at that speed."""
    # Binary search: P = 0.5*rho*v²*CDA*v + F_rolling*v
    v_low = 0.1
    v_high = 200.0

    for _ in range(50):
        v_mid = (v_low + v_high) / 2
        if v_mid < 0.1:
            break
        f_drag_calc = 0.5 * rho * (v_mid ** 2) * cda + f_rolling
        power_calc = f_drag_calc * v_mid

        if power_calc < power_w:
            v_low = v_mid
        else:
            v_high = v_mid

    return v_mid

v_max_calc_drs_ms = calc_vmax_equilibrium(total_power_w, aero_with_drs.CDA_drs_open, F_rolling, rho)
v_max_calc_drs_kph = v_max_calc_drs_ms * 3.6

print(f"\n[5] THEORETICAL V_MAX (power equilibrium)")
print(f"    With current CDA_DRS={aero_with_drs.CDA_drs_open:.4f}:")
print(f"    V_max = {v_max_calc_drs_kph:.1f} km/h")
print(f"    vs Real: {section.v_exit_kph:.1f} km/h")
print(f"    Delta: {v_max_calc_drs_kph - section.v_exit_kph:.1f} km/h")

# What CDA would be needed to reach real v_max?
# P = 0.5*rho*v_max²*CDA + F_rolling*v_max
# CDA = (P/v_max - F_rolling) / (0.5*rho*v_max²)

v_real_ms = section.v_exit_kph / 3.6
cda_needed = (total_power_w / v_real_ms - F_rolling) / (0.5 * rho * (v_real_ms ** 2))

print(f"\n[6] REQUIRED CDA TO REACH REAL V_MAX")
print(f"    To reach {section.v_exit_kph:.1f} km/h with {total_power_kw:.0f} kW:")
print(f"    CDA_needed = {cda_needed:.4f} m²")
print(f"    Current CDA_drs_open = {aero_with_drs.CDA_drs_open:.4f} m²")
print(f"    Difference: {aero_with_drs.CDA_drs_open - cda_needed:.4f} m²")

if cda_needed < aero_with_drs.CDA_drs_open:
    print(f"    ⚠️  CDA is TOO HIGH - drag is limiting top speed")
else:
    print(f"    ✓ CDA is low enough - power should allow reaching v_max")

# Check without DRS for comparison
print(f"\n[7] WHAT IF NO DRS REDUCTION?")
cda_no_reduction = aero_with_drs.CDA
v_max_no_drs_ms = calc_vmax_equilibrium(total_power_w, cda_no_reduction, F_rolling, rho)
v_max_no_drs_kph = v_max_no_drs_ms * 3.6
print(f"    If CDA = {cda_no_reduction:.4f} (no DRS reduction):")
print(f"    V_max would be: {v_max_no_drs_kph:.1f} km/h")
print(f"    DRS gain: {v_max_calc_drs_kph - v_max_no_drs_kph:.1f} km/h")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)

if abs(v_max_calc_drs_kph - section.v_exit_kph) < 10:
    print("✓ Drag coefficient is realistic - power/drag are well balanced")
else:
    print(f"✗ Drag mismatch: simulation would reach {v_max_calc_drs_kph:.0f} km/h, reality is {section.v_exit_kph:.0f} km/h")
    if v_max_calc_drs_kph > section.v_exit_kph:
        print("  Simulation is FASTER - check if corner exit speed is too low")
    else:
        print("  Simulation is SLOWER - check if CDA is too high or power too low")
