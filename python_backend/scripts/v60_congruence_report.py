#!/usr/bin/env python3
"""Detailed congruence analysis and recommendations for V6.0 calibration."""

import json
from pathlib import Path

SETUP_CAL_DIR = Path(__file__).resolve().parent.parent / "data" / "circuits" / "setup_calibration"

def generate_report():
    """Generate congruence report with recommendations."""

    results_files = sorted(SETUP_CAL_DIR.glob("*_setup_v60.json"))

    if not results_files:
        print("No calibration results found yet.")
        return

    print("\n" + "="*120)
    print("V6.0 CONGRUENCE DETAILED REPORT")
    print("="*120)

    results = []
    for f in results_files:
        with open(f) as fp:
            data = json.load(fp)
            results.append(data)

    results.sort(key=lambda x: x["circuit_name"])

    # Categorize by congruence type
    congruent = []
    low_wins = []
    high_wins = []
    close_low = []  # LOW within 0.1s of CAL

    for r in results:
        c = r["congruence_test"]
        if c["congruent"]:
            congruent.append(r)
        elif c["d_low_vs_cal"] < 0:
            low_wins.append(r)
        elif c["d_high_vs_cal"] < 0:
            high_wins.append(r)
        elif c["d_low_vs_cal"] < 0.1:
            close_low.append(r)

    # Print categorized results
    print(f"\nTOTAL: {len(results)} circuits")
    print(f"  ✅ Congruent: {len(congruent)}")
    print(f"  ❌ LOW wins: {len(low_wins)}")
    print(f"  ❌ HIGH wins: {len(high_wins)}")
    print(f"  ⚠️  Close (LOW <0.1s behind CAL): {len(close_low)}")

    print("\n" + "="*120)
    print("✅ CONGRUENT (CAL beats LOW and HIGH):")
    print("="*120)
    for r in congruent:
        opt = r["optimal_setup"]
        print(f"{r['circuit_name']:>15s}: FW={opt['front_wing']:>5.1f}  RW={opt['rear_wing']:>5.1f}  "
              f"mu={opt['mu_mechanical']:.4f}  error={r['calibration_results']['error_pct']:+.2f}%")

    print("\n" + "="*120)
    print("⚠️  CLOSE CALLS (LOW within 0.1s, should fail ±6° test):")
    print("="*120)
    for r in sorted(close_low, key=lambda x: x["congruence_test"]["d_low_vs_cal"], reverse=True):
        c = r["congruence_test"]
        opt = r["optimal_setup"]
        print(f"{r['circuit_name']:>15s}: CAL={c['t_cal']:.3f}s  LOW={c['t_low']:.3f}s  "
              f"Δ={c['d_low_vs_cal']:+.3f}s  FW={opt['front_wing']>5.1f}  RW={opt['rear_wing']>5.1f}")

    print("\n" + "="*120)
    print("❌ LOW WINS (faster than CAL):")
    print("="*120)
    for r in sorted(low_wins, key=lambda x: x["congruence_test"]["d_low_vs_cal"]):
        c = r["congruence_test"]
        opt = r["optimal_setup"]
        print(f"{r['circuit_name']:>15s}: CAL={c['t_cal']:.3f}s  LOW={c['t_low']:.3f}s  "
              f"Δ={c['d_low_vs_cal']:+.3f}s (CAL slower by {abs(c['d_low_vs_cal']):.3f}s)  FW={opt['front_wing']:.1f}  RW={opt['rear_wing']:.1f}")

    if high_wins:
        print("\n" + "="*120)
        print("❌ HIGH WINS (faster than CAL):")
        print("="*120)
        for r in sorted(high_wins, key=lambda x: x["congruence_test"]["d_high_vs_cal"]):
            c = r["congruence_test"]
            opt = r["optimal_setup"]
            print(f"{r['circuit_name']:>15s}: CAL={c['t_cal']:.3f}s  HIGH={c['t_high']:.3f}s  "
                  f"Δ={c['d_high_vs_cal']:+.3f}s  FW={opt['front_wing']:.1f}  RW={opt['rear_wing']:.1f}")

    # Recommendations
    print("\n" + "="*120)
    print("RECOMMENDATIONS:")
    print("="*120)

    total_congruent = len(congruent)
    total_close = len(close_low)
    total_failed = len(results) - total_congruent

    if total_congruent >= 18:
        print("✅ SUCCESS: ≥18/24 circuits congruent. V6.0 ready for use.")
    elif total_congruent + total_close >= 18:
        print(f"⚠️  BORDERLINE: {total_congruent}/24 congruent, {total_close} more are close.")
        print("   Option A: Widen preference test from ±6° to ±8° and retest")
        print("   Option B: Accept {total_congruent}/24 and document as limitation")
    else:
        print(f"❌ INSUFFICIENT: Only {total_congruent}/24 congruent.")
        print(f"   {len(low_wins)} circuits have LOW winning → physics model prefers low downforce")
        print(f"   {len(high_wins)} circuits have HIGH winning → physics model prefers high downforce")
        print("\n   Root cause: Physics model (drag vs corner benefit trade-off) doesn't match design goal.")
        print("   Options:")
        print("   1. Widen preference test (±8° or ±10°)")
        print("   2. Adjust physics drag coefficients (unrealistic)")
        print("   3. Accept this as design limitation of V6.0")
        print("   4. Switch to different setup definition (not circuit-optimal)")

    print("\n" + "="*120)

if __name__ == "__main__":
    generate_report()
