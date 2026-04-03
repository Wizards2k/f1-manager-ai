"""
Test: Simulate just Turn 1 and the main straight to understand the speed mismatch.
"""

import sys
sys.path.insert(0, '/Users/wizards/Sviluppo/F1 Manager AI')

from python_backend.lap_simulator.lap_simulator_v3 import LapSimulatorV3, CarEntryV3
from python_backend.lap_simulator.data_types import AeroSetup, DriverSkills, EnvContext

# Setup a test car
aero_setup = AeroSetup()
driver = DriverSkills(raw_pace=70)

entry = CarEntryV3(
    car_id="TEST_CAR",
    aero_setup=aero_setup,
    driver_skills=driver,
    push_level=10,
)

# Run simulation
sim = LapSimulatorV3(debug=True)
env = EnvContext(air_temp_c=20.0, track_temp_c=40.0)

print("="*70)
print("TEST: First Two Sections (Turn 1 + Straight 1)")
print("="*70)

results = sim.run_lap([entry], "it-1922_monza", is_qualifying=True, env=env)

print("\n" + "="*70)
print("SECTION DETAILS (first 3 sections)")
print("="*70)

result = results[0]
section_names = ["Straight 1", "Turn 1", "Straight 2", "Turn 2"]

for i, section in enumerate(result.section_results[:4]):
    name = section_names[i] if i < len(section_names) else f"Section {i}"
    print(f"\n[Section {i}] {name}")
    print(f"  v_entry:  {section.v_entry_kph:.1f} km/h")
    print(f"  v_exit:   {section.v_exit_kph:.1f} km/h")
    print(f"  v_max:    {section.v_max_kph:.1f} km/h")
    print(f"  v_effective: {section.v_effective_kph:.1f} km/h")
    print(f"  dt:       {section.dt_s:.3f} s")

print("\n" + "="*70)
print("EXPECTED (from telemetry)")
print("="*70)

expected = [
    ("Straight 1", 321.6, 347.0, 321.6, 348.0),
    ("Turn 1", 347.0, 108.0, 73.0, 347.0),
    ("Straight 2", 108.0, 322.0, 108.0, 329.0),
]

for name, v_entry, v_exit, v_min, v_max in expected:
    print(f"\n[Section] {name}")
    print(f"  v_entry:  {v_entry:.1f} km/h")
    print(f"  v_exit:   {v_exit:.1f} km/h")
    print(f"  v_min:    {v_min:.1f} km/h")
    print(f"  v_max:    {v_max:.1f} km/h")

print("\n" + "="*70)
print("ANALYSIS")
print("="*70)

print(f"\nLap time: {result.lap_time_s:.2f} seconds")
print(f"v_max: {result.v_max_kph:.1f} km/h")
print(f"v_min: {result.v_min_kph:.1f} km/h")

if len(result.section_results) >= 2:
    straight1 = result.section_results[0]
    turn1 = result.section_results[1]

    print(f"\n[Straight 1] (should avg ~340 km/h)")
    print(f"  Entry: {straight1.v_entry_kph:.1f} km/h (expected 321.6)")
    print(f"  Exit: {straight1.v_exit_kph:.1f} km/h (expected 347.0)")
    print(f"  Effective: {straight1.v_effective_kph:.1f} km/h")

    print(f"\n[Turn 1] (should have min ~73 km/h)")
    print(f"  Entry: {turn1.v_entry_kph:.1f} km/h (expected 347.0 from straight exit)")
    print(f"  Max: {turn1.v_max_kph:.1f} km/h")
    print(f"  Exit: {turn1.v_exit_kph:.1f} km/h (expected 108.0)")

    if turn1.v_entry_kph < 100:
        print(f"\n⚠️  Turn 1 entry speed VERY LOW ({turn1.v_entry_kph:.0f} km/h vs expected 347)")
        print("   This is the root cause of low speeds on following straight!")
