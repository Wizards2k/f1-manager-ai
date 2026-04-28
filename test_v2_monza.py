#!/usr/bin/env python3
"""Test LapSimulatorV2 su Monza per diagnosticare problemi velocità rettilineo."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd() / 'python_backend'))

from lap_simulator.config_loader import load_circuit_config
from lap_simulator.lap_simulator_v2 import LapSimulatorV2, CarEntryV2
from lap_simulator.data_types import AeroSetup, TyreCompound, EnvContext, AeroComponent
from lap_simulator.ai_data_types import AIDriverConfig, AITeamConfig

# Load circuit
config = load_circuit_config('it-1922_monza')

def create_aero_setup(low_drag=True, balanced=True):
    """Create aero setup with different configurations."""
    aero = AeroSetup()
    
    if low_drag:
        # Monza setup - low drag, low downforce
        aero.front_wing = AeroComponent(
            name="front_wing", base_downforce=8.0, base_drag=3.2,
            angle_deg=12.0, angle_ref_deg=40.0, angle_sensitivity=0.04, drag_sensitivity=0.02
        )
        aero.rear_wing = AeroComponent(
            name="rear_wing", base_downforce=10.0, base_drag=6.0,
            angle_deg=16.0, angle_ref_deg=42.0, angle_sensitivity=0.04, drag_sensitivity=0.02,
            drs_drag_reduction=0.28
        )
        aero.sidepods = AeroComponent(name="sidepods", base_downforce=3.5, base_drag=2.5)
    else:
        # High downforce setup - more drag
        aero.front_wing = AeroComponent(
            name="front_wing", base_downforce=14.0, base_drag=5.6,
            angle_deg=20.0, angle_ref_deg=40.0, angle_sensitivity=0.04, drag_sensitivity=0.02
        )
        aero.rear_wing = AeroComponent(
            name="rear_wing", base_downforce=16.0, base_drag=9.6,
            angle_deg=24.0, angle_ref_deg=42.0, angle_sensitivity=0.04, drag_sensitivity=0.02,
            drs_drag_reduction=0.28
        )
        aero.sidepods = AeroComponent(name="sidepods", base_downforce=6.0, base_drag=4.0)
    
    if balanced:
        # Balanced aero (target 0.50)
        aero.ride_height_front_mm = 45.0
        aero.ride_height_rear_mm = 55.0
    else:
        # Unbalanced (sotto/sovrasterzo)
        aero.ride_height_front_mm = 40.0
        aero.ride_height_rear_mm = 60.0
    
    return aero

def run_test(aero_setup, name):
    """Run a single test with given aero setup."""
    sim = LapSimulatorV2(
        config, 
        EnvContext(
            air_temp_c=20, track_temp_c=30, 
            wind_speed_kph=5, wind_direction_deg=0, 
            air_density_kg_m3=1.225, track_rubber_level=1.0
        )
    )
    
    car_entry = CarEntryV2(
        driver_config=AIDriverConfig(driver_id='p1'),
        team_config=AITeamConfig(team_id='t1'),
        aero_setup=aero_setup,
        tyre_compound=TyreCompound('C3'),
        fuel_load_kg=100.0,
        starting_position=1
    )
    
    res = sim.run_lap(car_entry)
    
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(f"Lap time: {res.lap_time_ms/1000:.3f}s")
    print(f"Sections: {len(res.sectors)}")
    
    # Check straight sections
    straights = [s for s in res.sectors if s.v_entry_kph > 250 or s.v_exit_kph > 250]
    if straights:
        print(f"Straight sections ({len(straights)}):")
        for s in straights[:3]:
            print(f"  dt={s.dt_s:.3f}s, v_entry={s.v_entry_kph:.1f}kph, v_exit={s.v_exit_kph:.1f}kph, drag={s.drag_eff:.2f}")
    
    # Check corner sections
    corners = [s for s in res.sectors if s.v_entry_kph < 200 and s.v_exit_kph < 200]
    if corners:
        print(f"Corner sections ({len(corners)}):")
        for s in corners[:3]:
            print(f"  dt={s.dt_s:.3f}s, v_entry={s.v_entry_kph:.1f}kph, v_exit={s.v_exit_kph:.1f}kph, hpen={s.handling_penalty:.3f}")
    
    return res

# Run all test configurations
print("Running comprehensive aero tests on Monza...")

# Test 1: Low drag, balanced
res1 = run_test(create_aero_setup(low_drag=True, balanced=True), "Low Drag + Balanced")

# Test 2: Low drag, unbalanced
res2 = run_test(create_aero_setup(low_drag=True, balanced=False), "Low Drag + Unbalanced")

# Test 3: High downforce, balanced
res3 = run_test(create_aero_setup(low_drag=False, balanced=True), "High DF + Balanced")

# Test 4: High downforce, unbalanced
res4 = run_test(create_aero_setup(low_drag=False, balanced=False), "High DF + Unbalanced")

# Summary
print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"Low Drag + Balanced:     {res1.lap_time_ms/1000:.3f}s")
print(f"Low Drag + Unbalanced:   {res2.lap_time_ms/1000:.3f}s")
print(f"High DF + Balanced:      {res3.lap_time_ms/1000:.3f}s")
print(f"High DF + Unbalanced:    {res4.lap_time_ms/1000:.3f}s")
print(f"\nExpected Monza lap: ~86-87s (Q3 telemetry)")
