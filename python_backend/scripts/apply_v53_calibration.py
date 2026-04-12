#!/usr/bin/env python3
from __future__ import annotations
"""
Apply V5.3 calibration results to aero calibration files.

This script reads the Phase 3 calibration results and updates the
mu_mechanical values in the aero calibration JSON files.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # python_backend
CAL_DIR = ROOT / "data" / "circuits" / "aero_calibration"

# Mapping from circuit name to circuit_id
CIRCUIT_ID_MAP = {
    "baku": "az-2016_baku",
    "spa": "be-1925_spa_francorchamps",
    "shanghai": "cn-2004_shanghai",
    "sakhir": "bh-2002_sakhir",
    "melbourne": "au-1953_melbourne",
    "yas_marina": "ae-2009_yas_marina",
    "barcelona": "es-1991_barcelona",
    "jeddah": "sa-2021_jeddah",
    "singapore": "sg-2008_singapore",
    "sao_paulo": "br-1940_sao_paulo",
    "monaco": "mc-1929_monaco",
    "suzuka": "jp-1962_suzuka",
    "silverstone": "gb-1948_silverstone",
    "zandvoort": "nl-1948_zandvoort",
    "budapest": "hu-1986_budapest",
    "monza": "it-1922_monza",
    "montreal": "ca-1978_montreal",
    "imola": "it-1953_imola",
    "mexico_city": "mx-1962_mexico_city",
    "miami": "us-2022_miami",
    "lusail": "qa-2004_lusail",
    "spielberg": "at-1969_spielberg",
    "austin": "us-2012_austin",
    "las_vegas": "us-2023_las_vegas",
}

# Phase 3 calibration results (from the first run with 0.17% avg error)
# Format: circuit_name -> mu_mechanical value (None = use default)
MU_CALIBRATION = {
    "austin": 1.783,       # +15.00% from 1.550
    "barcelona": 1.317,    # -15.00% from 1.550
    "budapest": 1.360,     # -15.00% from 1.600
    "jeddah": 1.317,       # -15.00% from 1.550
    "las_vegas": 1.361,    # -18.75% from 1.675
    "lusail": 1.201,       # -22.50% from 1.550
    "monaco": 1.509,       # -11.25% from 1.700
    "suzuka": 1.201,       # -22.50% from 1.550
    "yas_marina": 1.360,   # -15.00% from 1.600
    # Fine-tuned circuits (previously above 0.5%):
    "baku": 1.480,         # -7.50% from 1.600
    "melbourne": 1.317,    # -15.00% from 1.550
    "montreal": 1.480,     # -7.50% from 1.600
    "sao_paulo": 1.480,    # -7.50% from 1.600
    "shanghai": 1.317,     # -15.00% from 1.550
    "silverstone": 1.317,  # -15.00% from 1.550
    "spa": 1.317,          # -15.00% from 1.550
    "zandvoort": 1.317,    # -15.00% from 1.550
    # No adjustment needed (already < 0.5% error):
    "imola": None,
    "mexico_city": None,
    "miami": None,
    "monza": None,
    "sakhir": None,
    "singapore": None,
    "spielberg": None,
}


def main():
    print("Applying V5.3 mu_mechanical calibration to aero files...")
    print("=" * 60)

    updated = 0
    skipped = 0

    for name, mu_value in MU_CALIBRATION.items():
        circuit_id = CIRCUIT_ID_MAP[name]
        filepath = CAL_DIR / f"{circuit_id}_aero_cal.json"

        if not filepath.exists():
            print(f"  ⚠️  {name}: File not found: {filepath}")
            continue

        with open(filepath) as f:
            data = json.load(f)

        if mu_value is None:
            # No adjustment needed, but ensure grip_data section exists
            if "grip_data" not in data:
                print(f"  ⏭️  {name}: No adjustment needed, no grip_data section")
                skipped += 1
            else:
                print(f"  ⏭️  {name}: No adjustment needed, grip_data exists")
                skipped += 1
            continue

        # Add/update grip_data section with mu_mechanical
        if "grip_data" not in data:
            data["grip_data"] = {}

        old_mu = data["grip_data"].get("mu_mechanical", "N/A")
        data["grip_data"]["mu_mechanical"] = mu_value

        # Add note about calibration
        if "notes" not in data["grip_data"]:
            data["grip_data"]["notes"] = {}
        data["grip_data"]["notes"]["v53_calibration"] = f"V5.3: mu_mechanical calibrated to {mu_value:.3f} for <0.5% lap time error"

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        print(f"  ✅ {name}: mu_mechanical {old_mu} → {mu_value:.3f}")
        updated += 1

    print(f"\n{'='*60}")
    print(f"Updated: {updated}, Skipped: {skipped}")
    print("Done!")


if __name__ == "__main__":
    main()