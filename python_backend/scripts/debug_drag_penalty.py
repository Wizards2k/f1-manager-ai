#!/usr/bin/env python3
"""Debug: Check if drag is causing the lap time inversion."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.aero.aero_assembly import AeroAssembly

def test_drag_penalty():
    """Test if drag increases significantly with wing angles."""

    test_speed = 100.0  # m/s (~360 kph, typical F1 straight speed)

    configs = [
        ("LOW", {"front_wing": 16.0, "rear_wing": 20.0, "b_wing": 10.0}),
        ("CAL", {"front_wing": 22.0, "rear_wing": 26.0, "b_wing": 10.0}),
        ("HIGH", {"front_wing": 28.0, "rear_wing": 32.0, "b_wing": 10.0}),
    ]

    print("\n" + "="*80)
    print("DEBUG: DOWNFORCE vs DRAG TRADE-OFF")
    print("="*80)
    print(f"Test speed: {test_speed:.1f} m/s ({test_speed*3.6:.1f} kph)")
    print("-"*80)
    print(f"{'Setup':<10} {'FW':<8} {'RW':<8} {'Downforce (N)':<20} {'Drag (N)':<20} {'L/D Ratio':<15}")
    print("-"*80)

    results = {}
    for name, setup in configs:
        aero = AeroAssembly()
        aero.set_component_angles(setup)
        forces = aero.compute_forces(speed_ms=test_speed)

        df = forces.f_downforce
        drag = forces.f_drag
        ld_ratio = df / max(drag, 0.01)

        results[name] = (setup, df, drag, ld_ratio)

        fw = setup["front_wing"]
        rw = setup["rear_wing"]
        print(f"{name:<10} {fw:<8.1f} {rw:<8.1f} {df:<20.1f} {drag:<20.1f} {ld_ratio:<15.2f}")

    print("-"*80)

    low_df, low_drag = results["LOW"][1], results["LOW"][2]
    cal_df, cal_drag = results["CAL"][1], results["CAL"][2]
    high_df, high_drag = results["HIGH"][1], results["HIGH"][2]

    print("\nCHANGE FROM CAL:")
    print(f"  LOW:  DF={low_df-cal_df:+.1f}N ({100*(low_df-cal_df)/cal_df:+.1f}%), Drag={low_drag-cal_drag:+.1f}N ({100*(low_drag-cal_drag)/cal_drag:+.1f}%)")
    print(f"  HIGH: DF={high_df-cal_df:+.1f}N ({100*(high_df-cal_df)/cal_df:+.1f}%), Drag={high_drag-cal_drag:+.1f}N ({100*(high_drag-cal_drag)/cal_drag:+.1f}%)")

    print("\nANALYSIS:")
    print(f"  More wing → More DF (+{100*(high_df-low_df)/low_df:.1f}% HIGH vs LOW)")
    print(f"  More wing → More Drag (+{100*(high_drag-low_drag)/low_drag:.1f}% HIGH vs LOW)")
    print(f"  L/D ratio HIGH/LOW: {results['HIGH'][3]/results['LOW'][3]:.3f}x")

    print("\nEffect on straights (at 360 kph):")
    print(f"  LOW:  {low_drag:.0f}N drag = {low_drag/9.81:.1f}kg downward force")
    print(f"  CAL:  {cal_drag:.0f}N drag = {cal_drag/9.81:.1f}kg downward force")
    print(f"  HIGH: {high_drag:.0f}N drag = {high_drag/9.81:.1f}kg downward force")

    print("="*80 + "\n")

if __name__ == "__main__":
    test_drag_penalty()
