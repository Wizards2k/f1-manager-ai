import json
from lap_simulator.physics_v4.integrator.waypoint_integrator import integrate_lap_hd

result = integrate_lap_hd('it-1922_monza', verbose=False)
tel = result['telemetry']
print("Dist\tVel(kph)\tBrake\tAccel\tTgtV(kph)")
for t in tel[:220]:
    print(f"{t['distance_m']:.1f}\t{t['velocity_kph']:.1f}\t{t['is_braking']}\t{t['acceleration_ms2']/9.81:.2f}")

