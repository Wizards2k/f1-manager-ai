#!/usr/bin/env python3
"""Analyze V6.0 calibration results across all circuits."""

import json
from pathlib import Path
from statistics import mean, stdev

SETUP_CAL_DIR = Path(__file__).resolve().parent.parent / "data" / "circuits" / "setup_calibration"

def analyze_results():
    """Load and analyze all V6.0 calibration results."""

    results_files = sorted(SETUP_CAL_DIR.glob("*_setup_v60.json"))

    if not results_files:
        print("No calibration results found yet.")
        return

    print("\n" + "="*100)
    print("V6.0 CALIBRATION ANALYSIS")
    print("="*100)

    results = []
    for f in results_files:
        with open(f) as fp:
            data = json.load(fp)
            results.append(data)

    # Statistics
    congruent = [r for r in results if r["congruence_test"]["congruent"]]
    not_congruent = [r for r in results if not r["congruence_test"]["congruent"]]

    errors = [r["calibration_results"]["error_pct"] for r in results]
    gaps_low = [r["congruence_test"]["d_low_vs_cal"] for r in results]
    gaps_high = [r["congruence_test"]["d_high_vs_cal"] for r in results]

    print(f"\nTotal circuits calibrated: {len(results)}/24")
    print(f"Congruent: {len(congruent)}/24 ({100*len(congruent)/len(results):.1f}%)")
    print(f"Not congruent: {len(not_congruent)}/24")

    print(f"\nLap Time Error:")
    print(f"  Mean: {mean(errors):+.2f}%")
    print(f"  Min: {min(errors):+.2f}% ({results[errors.index(min(errors))]['circuit_name']})")
    print(f"  Max: {max(errors):+.2f}% ({results[errors.index(max(errors))]['circuit_name']})")
    if len(errors) > 1:
        print(f"  StdDev: {stdev(errors):.2f}%")

    print(f"\nCongruence Gap (LOW vs CAL):")
    print(f"  Mean: {mean(gaps_low):+.3f}s")
    print(f"  Min: {min(gaps_low):+.3f}s (should be >0)")
    print(f"  Circuits with LOW faster: {sum(1 for g in gaps_low if g < 0)}/24")

    print(f"\nCongruence Gap (HIGH vs CAL):")
    print(f"  Mean: {mean(gaps_high):+.3f}s")
    print(f"  Min: {min(gaps_high):+.3f}s (should be >0)")

    print("\n" + "-"*100)
    print("✅ CONGRUENT CIRCUITS:")
    print("-"*100)
    for r in sorted(congruent, key=lambda x: x["circuit_name"]):
        print(f"  {r['circuit_name']:>15s}: CAL={r['congruence_test']['t_cal']:.3f}s, "
              f"LOW={r['congruence_test']['t_low']:.3f}s (Δ={r['congruence_test']['d_low_vs_cal']:+.3f}s), "
              f"error={r['calibration_results']['error_pct']:+.2f}%")

    print("\n" + "-"*100)
    print("❌ NOT CONGRUENT (LOW or HIGH winning):")
    print("-"*100)

    low_winning = [r for r in not_congruent if r["congruence_test"]["d_low_vs_cal"] < 0]
    high_winning = [r for r in not_congruent if r["congruence_test"]["d_high_vs_cal"] < 0]

    if low_winning:
        print(f"\nLOW wins ({len(low_winning)}):")
        for r in sorted(low_winning, key=lambda x: x["congruence_test"]["d_low_vs_cal"]):
            print(f"  {r['circuit_name']:>15s}: CAL={r['congruence_test']['t_cal']:.3f}s, "
                  f"LOW={r['congruence_test']['t_low']:.3f}s (Δ={r['congruence_test']['d_low_vs_cal']:+.3f}s)")

    if high_winning:
        print(f"\nHIGH wins ({len(high_winning)}):")
        for r in sorted(high_winning, key=lambda x: x["congruence_test"]["d_high_vs_cal"]):
            print(f"  {r['circuit_name']:>15s}: CAL={r['congruence_test']['t_cal']:.3f}s, "
                  f"HIGH={r['congruence_test']['t_high']:.3f}s (Δ={r['congruence_test']['d_high_vs_cal']:+.3f}s)")

    print("\n" + "="*100)

if __name__ == "__main__":
    analyze_results()
