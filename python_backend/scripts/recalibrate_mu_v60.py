#!/usr/bin/env python3
"""V6.0.1 mu_mechanical Recalibration

Per ogni circuito, usa i wings ottimali (optimal_wings_v60.json) e fa binary
search su mu_mechanical per hit ref_time entro ±1.5%.

Patcha i file `data/circuits/aero_calibration/{circuit_id}_aero_cal.json`
preservando tutti i campi tranne grip_data.mu_mechanical.

Dopo ogni patch svuota la cache LRU di get_aero_calibration.
"""
import sys
import json
import time
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration
from scripts.calibrate_v57 import ALL_CIRCUITS, SUSP_SETUPS, DRIVER

AERO_CAL_DIR = ROOT / "data" / "circuits" / "aero_calibration"
OPTIMAL_WINGS_FILE = ROOT / "optimal_wings_v60.json"

TARGET_PCT = 1.5  # tolerance ±1.5%
MAX_ITER = 20
MU_MIN = 0.3
MU_MAX = 2.5


def sim_lap(circuit_id, fw, rw, bwing, compound, susp_key):
    setup = PhysicsV4Setup(driver_data=DRIVER, circuit=circuit_id, session="qualifying")
    setup.set_aero(front_wing=fw, rear_wing=rw, bwing=bwing)
    setup.set_suspension(**SUSP_SETUPS[susp_key])
    setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
    setup.set_tyres(compound=compound)
    setup.set_ers_mode("quali_deploy")
    return setup.simulate_lap(verbose=False)["lap_time_s"]


def aero_cal_path(circuit_id):
    return AERO_CAL_DIR / f"{circuit_id}_aero_cal.json"


def patch_mu(circuit_id, new_mu):
    """Patcha grip_data.mu_mechanical preservando tutto il resto."""
    path = aero_cal_path(circuit_id)
    with open(path) as f:
        data = json.load(f)
    data["grip_data"]["mu_mechanical"] = round(float(new_mu), 4)
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)
    get_aero_calibration.cache_clear()


def read_current_mu(circuit_id):
    path = aero_cal_path(circuit_id)
    with open(path) as f:
        data = json.load(f)
    return float(data["grip_data"]["mu_mechanical"])


def calibrate_circuit(name, cfg, optimal, verbose=True):
    circuit_id = cfg["circuit_id"]
    bwing = cfg["bwing"]
    compound = cfg["compound"]
    susp_key = cfg["susp_source"]
    ref_time = cfg["ref_time"]

    fw = optimal["optimal_fw"]
    rw = optimal["optimal_rw"]

    original_mu = read_current_mu(circuit_id)
    if verbose:
        print(f"\n  {name}: FW={fw}/RW={rw}, ref={ref_time:.3f}s, mu_orig={original_mu:.4f}")

    # Binary search
    lo, hi = MU_MIN, MU_MAX
    best_mu, best_t, best_err = original_mu, 9999.0, 999.0
    n_sims = 0

    for i in range(MAX_ITER):
        mu = (lo + hi) / 2.0
        patch_mu(circuit_id, mu)
        t = sim_lap(circuit_id, fw, rw, bwing, compound, susp_key)
        n_sims += 1
        err_pct = 100 * (t - ref_time) / ref_time

        if abs(err_pct) < abs(best_err):
            best_mu, best_t, best_err = mu, t, err_pct

        if verbose:
            print(f"    iter {i+1:2d}: mu={mu:.4f} → t={t:.3f}s  err={err_pct:+.3f}%")

        if abs(err_pct) < TARGET_PCT:
            break

        # t troppo lento (err > 0) → grip insufficiente → alza mu
        # t troppo veloce (err < 0) → troppo grip → abbassa mu
        if err_pct > 0:
            lo = mu
        else:
            hi = mu

    # Scrivi il mu migliore finale
    patch_mu(circuit_id, best_mu)
    if verbose:
        flag = "✅" if abs(best_err) < TARGET_PCT else "⚠️"
        print(f"    {flag} best: mu={best_mu:.4f} → t={best_t:.3f}s err={best_err:+.3f}% ({n_sims} sims)")

    return {
        "name": name,
        "original_mu": original_mu,
        "final_mu": best_mu,
        "final_time": best_t,
        "ref_time": ref_time,
        "error_pct": best_err,
        "n_sims": n_sims,
        "converged": abs(best_err) < TARGET_PCT,
        "fw": fw, "rw": rw,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--circuit", type=str, help="Calibrate specific circuit")
    parser.add_argument("--quick", action="store_true", help="Only 3 circuits")
    parser.add_argument("--dry-run", action="store_true", help="Don't write JSON changes (restore mu at end)")
    args = parser.parse_args()

    with open(OPTIMAL_WINGS_FILE) as f:
        optimal_wings = json.load(f)

    if args.circuit:
        circuits = {args.circuit: ALL_CIRCUITS[args.circuit]}
    elif args.quick:
        circuits = {k: v for k, v in ALL_CIRCUITS.items() if k in ["monza", "barcelona", "monaco"]}
    else:
        circuits = ALL_CIRCUITS

    # Save original mu values (for dry-run restore)
    original_mus = {}
    for name, cfg in circuits.items():
        original_mus[cfg["circuit_id"]] = read_current_mu(cfg["circuit_id"])

    print("=" * 90)
    print(f"  V6.0.1 mu_mechanical RECALIBRATION — {len(circuits)} circuits")
    print(f"  Target: |err| < {TARGET_PCT}%")
    print("=" * 90)

    results = []
    t_start = time.time()

    for name, cfg in sorted(circuits.items()):
        if name not in optimal_wings:
            print(f"\n  {name}: ⚠️ skipped (no optimal wings data)")
            continue
        r = calibrate_circuit(name, cfg, optimal_wings[name])
        results.append(r)

    t_total = time.time() - t_start

    # Summary
    print()
    print("=" * 90)
    print(f"  RECALIBRATION COMPLETE ({t_total:.0f}s)")
    print("=" * 90)
    print(f"  {'Circuit':<14} {'FW/RW':<8} {'mu_orig':<10} {'mu_new':<10} {'Δmu':<10} "
          f"{'t_sim':<10} {'ref':<10} {'err %':<8}")
    print("  " + "-"*90)

    converged = 0
    for r in results:
        flag = "✅" if r["converged"] else "⚠️"
        d_mu = r["final_mu"] - r["original_mu"]
        print(f"  {r['name']:<14} {r['fw']:>3d}/{r['rw']:<3d}  {r['original_mu']:<10.4f} "
              f"{r['final_mu']:<10.4f} {d_mu:<+10.4f} "
              f"{r['final_time']:<10.3f} {r['ref_time']:<10.3f} {r['error_pct']:<+8.3f} {flag}")
        if r["converged"]:
            converged += 1

    print("  " + "-"*90)
    print(f"\n  Converged: {converged}/{len(results)}  (target ±{TARGET_PCT}%)")

    if args.dry_run:
        print("\n  DRY RUN: restoring original mu values...")
        for cid, mu in original_mus.items():
            patch_mu(cid, mu)
        print("  Original mu values restored.")

    # Save report
    report_path = ROOT / "mu_recalibration_report_v60.json"
    with open(report_path, 'w') as f:
        json.dump({"results": results, "target_pct": TARGET_PCT}, f, indent=2)
    print(f"\n  Report saved to: {report_path}")


if __name__ == "__main__":
    main()
