#!/usr/bin/env python3
"""V6.0 Optimal Wings Calibration

Per ogni circuito, trova gli angoli di ala ottimali (FW, RW) che minimizzano
il tempo sul giro. Questo è il nuovo "CAL" per il preference test.

Strategia a 2 fasi:
  1. Coarse grid search (step 4°): 5×5 = 25 simulazioni per circuito
  2. Fine grid search (step 2°): 3×3 = 9 simulazioni intorno al best

Totale: 34 simulazioni × 24 circuiti = 816 simulazioni

Output: file JSON con le wing angles ottimali per ogni circuito.
"""
import sys
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup, DriverSkill
from scripts.calibrate_v57 import ALL_CIRCUITS, SUSP_SETUPS, DRIVER


def sim_lap(circuit_id, fw, rw, bwing, compound, susp_key):
    """Simulate a lap and return lap time."""
    setup = PhysicsV4Setup(driver_data=DRIVER, circuit=circuit_id, session="qualifying")
    setup.set_aero(front_wing=fw, rear_wing=rw, bwing=bwing)
    setup.set_suspension(**SUSP_SETUPS[susp_key])
    setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
    setup.set_tyres(compound=compound)
    setup.set_ers_mode("quali_deploy")
    return setup.simulate_lap(verbose=False)["lap_time_s"]


def find_optimal_wings(name, cfg, verbose=True):
    """Find optimal wing angles for a circuit via 2-phase grid search.

    Returns: (best_fw, best_rw, best_time, n_sims)
    """
    circuit_id = cfg["circuit_id"]
    bwing = cfg["bwing"]
    compound = cfg["compound"]
    susp_key = cfg["susp_source"]

    # Starting point: current config
    initial_fw = cfg["front_wing"]
    initial_rw = cfg["rear_wing"]

    best_fw = initial_fw
    best_rw = initial_rw
    best_time = sim_lap(circuit_id, best_fw, best_rw, bwing, compound, susp_key)
    n_sims = 1

    if verbose:
        print(f"\n  {name}: start FW={initial_fw}/RW={initial_rw} → {best_time:.3f}s")

    # PHASE 1: Coarse grid search (step 4°)
    # FW range: [4, 42], RW range: [4, 45]
    coarse_fw_values = list(range(4, 43, 4))  # 4, 8, 12, ..., 40
    coarse_rw_values = list(range(4, 46, 4))  # 4, 8, 12, ..., 44

    if verbose:
        print(f"  Phase 1 (coarse): searching {len(coarse_fw_values)}×{len(coarse_rw_values)} grid...")

    for fw in coarse_fw_values:
        for rw in coarse_rw_values:
            # Skip if same as already tested
            if fw == initial_fw and rw == initial_rw:
                continue
            t = sim_lap(circuit_id, fw, rw, bwing, compound, susp_key)
            n_sims += 1
            if t < best_time:
                best_time = t
                best_fw = fw
                best_rw = rw
                if verbose:
                    print(f"    → New best: FW={fw}/RW={rw} → {t:.3f}s")

    # PHASE 2: Fine grid search around coarse best (step 2°, ±4°)
    fine_fw_values = [best_fw + d for d in [-2, 0, 2] if 4 <= best_fw + d <= 42]
    fine_rw_values = [best_rw + d for d in [-2, 0, 2] if 4 <= best_rw + d <= 45]

    if verbose:
        print(f"  Phase 2 (fine): searching {len(fine_fw_values)}×{len(fine_rw_values)} grid around FW={best_fw}/RW={best_rw}...")

    for fw in fine_fw_values:
        for rw in fine_rw_values:
            if fw == best_fw and rw == best_rw:
                continue
            t = sim_lap(circuit_id, fw, rw, bwing, compound, susp_key)
            n_sims += 1
            if t < best_time:
                best_time = t
                best_fw = fw
                best_rw = rw
                if verbose:
                    print(f"    → New best: FW={fw}/RW={rw} → {t:.3f}s")

    # PHASE 3: Very fine search around best (step 1°, ±2°)
    vf_fw_values = [best_fw + d for d in [-1, 0, 1] if 4 <= best_fw + d <= 42]
    vf_rw_values = [best_rw + d for d in [-1, 0, 1] if 4 <= best_rw + d <= 45]

    if verbose:
        print(f"  Phase 3 (very fine): searching step 1°...")

    for fw in vf_fw_values:
        for rw in vf_rw_values:
            if fw == best_fw and rw == best_rw:
                continue
            t = sim_lap(circuit_id, fw, rw, bwing, compound, susp_key)
            n_sims += 1
            if t < best_time:
                best_time = t
                best_fw = fw
                best_rw = rw
                if verbose:
                    print(f"    → New best: FW={fw}/RW={rw} → {t:.3f}s")

    return best_fw, best_rw, best_time, n_sims


def main():
    import argparse
    parser = argparse.ArgumentParser(description="V6.0 Optimal Wings Calibration")
    parser.add_argument("--quick", action="store_true", help="Only calibrate 3 circuits")
    parser.add_argument("--circuit", type=str, help="Calibrate specific circuit")
    parser.add_argument("--output", type=str, default="optimal_wings_v60.json",
                        help="Output JSON file")
    args = parser.parse_args()

    if args.circuit:
        circuits = {args.circuit: ALL_CIRCUITS[args.circuit]}
    elif args.quick:
        circuits = {k: v for k, v in ALL_CIRCUITS.items() if k in ["monza", "monaco", "austin"]}
    else:
        circuits = ALL_CIRCUITS

    print("=" * 90)
    print(f"  V6.0 OPTIMAL WINGS CALIBRATION — {len(circuits)} circuits")
    print("=" * 90)

    results = {}
    total_sims = 0
    t_start = time.time()

    for name, cfg in sorted(circuits.items()):
        initial_fw = int(cfg["front_wing"])
        initial_rw = int(cfg["rear_wing"])

        best_fw, best_rw, best_time, n_sims = find_optimal_wings(name, cfg)
        total_sims += n_sims

        delta_fw = int(best_fw) - initial_fw
        delta_rw = int(best_rw) - initial_rw

        results[name] = {
            "circuit_id": cfg["circuit_id"],
            "initial_fw": initial_fw,
            "initial_rw": initial_rw,
            "optimal_fw": best_fw,
            "optimal_rw": best_rw,
            "delta_fw": delta_fw,
            "delta_rw": delta_rw,
            "optimal_time": best_time,
            "ref_time": cfg["ref_time"],
            "n_sims": n_sims,
        }

        # Print summary for this circuit
        elapsed = time.time() - t_start
        print(f"  ✓ {name}: FW={initial_fw}→{int(best_fw)} ({delta_fw:+d}°), RW={initial_rw}→{int(best_rw)} ({delta_rw:+d}°), "
              f"time={best_time:.3f}s, {n_sims} sims [{elapsed:.0f}s total]")

    t_total = time.time() - t_start

    # Save results
    output_path = ROOT / args.output
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print()
    print("=" * 90)
    print(f"  CALIBRATION COMPLETE")
    print(f"  Total simulations: {total_sims}")
    print(f"  Total time: {t_total:.0f}s ({t_total/60:.1f} min)")
    print(f"  Results saved to: {output_path}")
    print("=" * 90)

    # Print summary table
    print()
    print("  SUMMARY — Circuit-optimal wing angles:")
    print(f"  {'Circuit':<15} {'Initial':<10} {'Optimal':<10} {'Δ FW/RW':<12} {'Time (s)':<10}")
    print(f"  {'-'*70}")
    for name in sorted(results.keys()):
        r = results[name]
        print(f"  {name:<15} {int(r['initial_fw']):>3d}/{int(r['initial_rw']):<3d}   "
              f"{int(r['optimal_fw']):>3d}/{int(r['optimal_rw']):<3d}   "
              f"{r['delta_fw']:+d}/{r['delta_rw']:+d}       {r['optimal_time']:.3f}")


if __name__ == "__main__":
    main()
