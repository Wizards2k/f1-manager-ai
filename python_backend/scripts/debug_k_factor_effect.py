#!/usr/bin/env python3
"""Debug: verifica che K_FACTOR cambi veramente drag/downforce."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.aero.aero_assembly import AeroAssembly
from lap_simulator.physics_v4.aero.front_wing import FrontWing
from lap_simulator.physics_v4.aero.rear_wing import RearWing


def test_with_k(k_fw, k_rw, fw_aoa, rw_aoa):
    """Crea aero assembly con K specifici."""
    aero = AeroAssembly()
    aero.front_wing.K_FACTOR = k_fw
    aero.rear_wing.K_FACTOR = k_rw
    aero.set_component_angles({'front_wing': fw_aoa, 'rear_wing': rw_aoa, 'b_wing': 10.0})

    forces = aero.compute_forces(speed_ms=80.0)
    fw_forces = aero.front_wing.calculate_forces(1.225, 80.0)
    rw_forces = aero.rear_wing.calculate_forces(1.225, 80.0)

    return {
        'total_df_kn': forces.f_downforce / 1000,
        'total_drag_kn': forces.f_drag / 1000,
        'ld_total': forces.f_downforce / max(forces.f_drag, 0.1),
        'fw_ld': fw_forces['L/D'],
        'rw_ld': rw_forces['L/D'],
        'fw_drag_kn': fw_forces['drag'] / 1000,
        'rw_drag_kn': rw_forces['drag'] / 1000,
    }


def main():
    print("\n" + "="*100)
    print("  K_FACTOR EFFECT ON AERO (@ 80 m/s, ride_height default)")
    print("="*100)

    configs = [
        ("LOW wings (8/10)", 8, 10),
        ("MED wings (20/24)", 20, 24),
        ("HIGH wings (35/40)", 35, 40),
    ]

    k_sets = [
        ("BASE", 0.35, 0.40),
        ("MED",  0.30, 0.35),
        ("LOW",  0.25, 0.30),
    ]

    for cfg_name, fw, rw in configs:
        print(f"\n  {cfg_name}:")
        print(f"    {'K_set':<8} {'DF (kN)':<10} {'Drag (kN)':<12} {'L/D total':<11} {'FW drag':<10} {'RW drag':<10}")
        for k_name, k_fw, k_rw in k_sets:
            r = test_with_k(k_fw, k_rw, fw, rw)
            print(f"    {k_name:<8} {r['total_df_kn']:<10.3f} {r['total_drag_kn']:<12.3f} "
                  f"{r['ld_total']:<11.3f} {r['fw_drag_kn']:<10.3f} {r['rw_drag_kn']:<10.3f}")


if __name__ == "__main__":
    main()
