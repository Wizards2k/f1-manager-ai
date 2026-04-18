#!/usr/bin/env python3
"""Verifica congruenza tipologica: wing angles vs tipo di circuito F1 reale."""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Mappatura reale F1 → atteso wing range (FW)
EXPECTED = {
    # fast
    "monza":        ("FAST",   "lowest",  (4,  12)),
    "jeddah":       ("FAST",   "lowest",  (4,  12)),
    "spa":          ("FAST",   "low",     (6,  15)),
    "baku":         ("FAST",   "low",     (8,  16)),
    "las_vegas":    ("FAST",   "low",     (8,  16)),
    # medium
    "silverstone":  ("MEDIUM", "mid-low", (10, 22)),
    "spielberg":    ("MEDIUM", "mid",     (10, 22)),
    "melbourne":    ("MEDIUM", "mid",     (10, 22)),
    "lusail":       ("MEDIUM", "mid",     (12, 22)),
    "miami":        ("MEDIUM", "mid",     (12, 22)),
    "montreal":     ("MEDIUM", "mid",     (12, 22)),
    "austin":       ("MEDIUM", "mid",     (14, 24)),
    "sakhir":       ("MEDIUM", "mid",     (14, 24)),
    "shanghai":     ("MEDIUM", "mid",     (14, 24)),
    "mexico_city":  ("MEDIUM", "mid",     (14, 24)),
    "imola":        ("MEDIUM", "mid-high",(16, 26)),
    "suzuka":       ("MEDIUM", "mid-high",(14, 24)),
    "sao_paulo":    ("MEDIUM", "mid-high",(14, 24)),
    "yas_marina":   ("MEDIUM", "mid",     (12, 22)),
    # slow
    "zandvoort":    ("SLOW",   "high",    (18, 30)),
    "barcelona":    ("SLOW",   "high",    (18, 30)),
    "budapest":     ("SLOW",   "high",    (18, 32)),
    "singapore":    ("SLOW",   "high",    (18, 34)),
    "monaco":       ("SLOW",   "highest", (25, 42)),
}


def main():
    opt_file = ROOT / "optimal_wings_v60.json"
    with open(opt_file) as f:
        optimal = json.load(f)

    print("\n" + "="*95)
    print("  TYPOLOGICAL CONGRUENCE CHECK")
    print("="*95)
    print(f"  {'Circuit':<14} {'Cat':<8} {'Expected':<10} {'Range':<12} {'Actual FW':<10} {'Verdict':<10}")
    print(f"  {'-'*95}")

    congruent = 0
    borderline = 0
    incongruent = 0
    total = 0

    by_cat = {"FAST": [], "MEDIUM": [], "SLOW": []}

    for name, (cat, label, (lo, hi)) in EXPECTED.items():
        if name not in optimal:
            continue
        total += 1
        opt_fw = int(optimal[name]["optimal_fw"])
        opt_rw = int(optimal[name]["optimal_rw"])

        # Tolerance: ±2° from the range
        if lo <= opt_fw <= hi:
            verdict = "✅"
            congruent += 1
        elif lo - 3 <= opt_fw <= hi + 3:
            verdict = "⚠️  borderline"
            borderline += 1
        else:
            verdict = "❌ INCONGRUENT"
            incongruent += 1

        by_cat[cat].append((name, opt_fw, verdict))
        print(f"  {name:<14} {cat:<8} {label:<10} [{lo},{hi}]        {opt_fw:>3d}/{opt_rw:<3d}  {verdict}")

    print(f"  {'-'*95}")
    print(f"\n  TOTALI: {congruent}/{total} congruenti, {borderline} borderline, {incongruent} incongruent")
    print(f"  Strict  : {congruent}/{total} = {100*congruent/total:.1f}%")
    print(f"  Lenient : {(congruent+borderline)}/{total} = {100*(congruent+borderline)/total:.1f}%")

    # Per categoria
    print(f"\n  Per categoria (FW angles):")
    for cat in ["FAST", "MEDIUM", "SLOW"]:
        vals = [fw for _, fw, _ in by_cat[cat]]
        if vals:
            print(f"    {cat:<8}: min={min(vals)}, max={max(vals)}, mean={sum(vals)/len(vals):.1f}  "
                  f"({len(vals)} circuits)")


if __name__ == "__main__":
    main()
