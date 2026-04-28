"""Quick test for V5.5 telemetry-guided braking on Monaco."""
import sys
sys.path.insert(0, '.')
from lap_simulator.physics_v4.integrator.waypoint_integrator import integrate_lap_hd

# Monaco test with telemetry-guided braking
result = integrate_lap_hd(
    circuit_id='mc-1929_monaco',
    aero_setup={'front_wing': 22.0, 'rear_wing': 26.0},
    mass_kg=798+20,
    tyre_compound='C5',
    driver_skill=1.0,
    suspension_setup={
        'spring_front': 10.0, 'spring_rear': 18.0,
        'arb_front': 25.0, 'arb_rear': 30.0,
        'ride_height_front': 16.0, 'ride_height_rear': 23.0,
    },
    verbose=True,
)

ref_time = 71.312
lap_time = result['lap_time_s']
error_pct = (lap_time - ref_time) / ref_time * 100

print(f'\n=== Monaco V5.5 (telemetry braking) ===')
print(f'Lap time: {lap_time:.3f}s (ref: {ref_time:.3f}s)')
print(f'Error: {error_pct:+.2f}%')
print(f'V_max: {result["v_max_kph"]:.1f} kph')
print(f'V_min: {result["v_min_kph"]:.1f} kph')