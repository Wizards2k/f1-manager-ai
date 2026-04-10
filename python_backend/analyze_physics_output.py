#!/usr/bin/env python3
"""
Diagnostica Fisica - Analizza cosa il motore physico sta facendo

Esamina:
- CL/CD per setup ottimale vs terribile
- Grip disponibile
- Effetti sospensioni
- Delta settori dettagliato
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_v4.core.team_driver_data import get_team_data, get_driver_data
from lap_simulator.physics_v4.aero.front_wing import FrontWing
from lap_simulator.physics_v4.aero.rear_wing import RearWing


def analyze_aero_setup(circuit_id: str, setup_dict: dict, setup_name: str):
    """Analizza effetti aerodinamici di un setup."""
    print(f"\n{'='*80}")
    print(f"  {setup_name} - Analisi Aerodinamica")
    print(f"{'='*80}")

    # Front wing
    fw_angle = setup_dict["aero"]["front_wing"]
    fw_config = {"aoa": fw_angle}
    fw = FrontWing(fw_config)

    # Test velocità (100 m/s = 360 kph)
    rho = 1.225
    v = 100  # m/s

    fw_forces = fw.calculate_forces(rho, v)
    print(f"\n📐 Front Wing (Angolo: {fw_angle}°)")
    print(f"   CL: {fw_forces['CL']:.4f} │ CD: {fw_forces['CD']:.4f} │ L/D: {fw_forces['L/D']:.2f}")
    print(f"   Lift: {fw_forces['lift']:.1f} N │ Drag: {fw_forces['drag']:.1f} N")

    # Rear wing
    rw_angle = setup_dict["aero"]["rear_wing"]
    rw_config = {"aoa": rw_angle}
    rw = RearWing(rw_config)

    rw_forces = rw.calculate_forces(rho, v)
    print(f"\n📐 Rear Wing (Angolo: {rw_angle}°)")
    print(f"   CL: {rw_forces['CL']:.4f} │ CD: {rw_forces['CD']:.4f} │ L/D: {rw_forces['L/D']:.2f}")
    print(f"   Lift: {rw_forces['lift']:.1f} N │ Drag: {rw_forces['drag']:.1f} N")

    # Total aero
    total_cl = fw_forces["CL"] + rw_forces["CL"]
    total_cd = fw_forces["CD"] + rw_forces["CD"]

    print(f"\n🎯 TOTALE AERODINAMICO")
    print(f"   CL totale: {total_cl:.4f}")
    print(f"   CD totale: {total_cd:.4f}")
    print(f"   CLA: {setup_dict['aero']['cla_total']:.4f} (configurato)")
    print(f"   CDA: {setup_dict['aero']['cda_total']:.4f} (configurato)")


def analyze_suspension_setup(setup_dict: dict, setup_name: str):
    """Analizza effetti sospensioni."""
    print(f"\n{'='*80}")
    print(f"  {setup_name} - Analisi Sospensioni")
    print(f"{'='*80}")

    susp = setup_dict["suspension"]

    # Deviazioni dalle ottimali
    spring_f = susp["spring_front"]
    spring_r = susp["spring_rear"]
    arb_f = susp["arb_front"]
    arb_r = susp["arb_rear"]

    opt_sf = 15.0
    opt_sr = 18.0
    opt_af = 4.0
    opt_ar = 6.0

    dev_sf = abs(spring_f - opt_sf) / opt_sf * 100
    dev_sr = abs(spring_r - opt_sr) / opt_sr * 100
    dev_af = abs(arb_f - opt_af) / opt_af * 100
    dev_ar = abs(arb_r - opt_ar) / opt_ar * 100

    print(f"\n🔧 Spring Rate (Molla)")
    print(f"   Front:  {spring_f:.1f} (opt: {opt_sf:.1f}, dev: {dev_sf:+.1f}%)")
    print(f"   Rear:   {spring_r:.1f} (opt: {opt_sr:.1f}, dev: {dev_sr:+.1f}%)")

    print(f"\n⚙️  Anti-Roll Bar (ARB)")
    print(f"   Front:  {arb_f:.1f} (opt: {opt_af:.1f}, dev: {dev_af:+.1f}%)")
    print(f"   Rear:   {arb_r:.1f} (opt: {opt_ar:.1f}, dev: {dev_ar:+.1f}%)")

    # Stima effetti
    spring_dev_avg = (dev_sf + dev_sr) / 2
    arb_dev_avg = (dev_af + dev_ar) / 2

    mech_grip = 1.0 - 0.07 * (spring_dev_avg / 100.0) ** 1.5
    corner_penalty = 0.08 * (arb_dev_avg / 100.0) ** 1.3

    print(f"\n📊 EFFETTI FISICI STMATI")
    print(f"   Mechanical Grip Factor: {mech_grip:.4f} (delta: {(mech_grip-1)*100:+.2f}%)")
    print(f"   Corner Grip Penalty: {corner_penalty:.4f} (delta: {corner_penalty*100:+.2f}%)")


def main():
    # Definisci setup
    setup_opt = {
        "aero": {"front_wing": 20.0, "rear_wing": 22.0, "cla_total": 3.2, "cda_total": 1.1},
        "suspension": {
            "spring_front": 15.0,
            "spring_rear": 18.0,
            "arb_front": 4.0,
            "arb_rear": 6.0,
        },
    }

    setup_ter = {
        "aero": {"front_wing": 5.0, "rear_wing": 8.0, "cla_total": 1.5, "cda_total": 0.8},
        "suspension": {
            "spring_front": 5.0,
            "spring_rear": 8.0,
            "arb_front": 1.0,
            "arb_rear": 2.0,
        },
    }

    print("\n" + "="*80)
    print("DIAGNOSTICA FISICA - ANALISI DETTAGLIATA SETUP")
    print("="*80)

    # Analizza aero
    circuit = "it-1922_monza"

    analyze_aero_setup(circuit, setup_opt, "OTTIMALE")
    analyze_aero_setup(circuit, setup_ter, "TERRIBILE")

    # Analizza sospensioni
    analyze_suspension_setup(setup_opt, "OTTIMALE")
    analyze_suspension_setup(setup_ter, "TERRIBILE")

    # Comparazione
    print(f"\n{'='*80}")
    print("  COMPARAZIONE SETUP")
    print(f"{'='*80}")

    print(f"\nAERODINAMICA:")
    print(
        f"  Front Wing: {setup_opt['aero']['front_wing']}° (opt) vs {setup_ter['aero']['front_wing']}° (ter) = {setup_opt['aero']['front_wing']-setup_ter['aero']['front_wing']}° diff"
    )
    print(
        f"  Rear Wing:  {setup_opt['aero']['rear_wing']}° (opt) vs {setup_ter['aero']['rear_wing']}° (ter) = {setup_opt['aero']['rear_wing']-setup_ter['aero']['rear_wing']}° diff"
    )

    print(f"\nSSOPENSIONI:")
    print(f"  Spring Front: {setup_opt['suspension']['spring_front']} (opt) vs {setup_ter['suspension']['spring_front']} (ter)")
    print(
        f"  Spring Rear:  {setup_opt['suspension']['spring_rear']} (opt) vs {setup_ter['suspension']['spring_rear']} (ter)"
    )
    print(
        f"  ARB Front:    {setup_opt['suspension']['arb_front']} (opt) vs {setup_ter['suspension']['arb_front']} (ter)"
    )
    print(f"  ARB Rear:     {setup_opt['suspension']['arb_rear']} (opt) vs {setup_ter['suspension']['arb_rear']} (ter)")


if __name__ == "__main__":
    main()
