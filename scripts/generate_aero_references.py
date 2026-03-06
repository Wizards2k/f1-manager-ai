#!/usr/bin/env python3
"""
Generate circuit-specific aero reference values for all circuits.

Based on circuit characteristics:
- High DF circuits (Monaco, Budapest, Singapore): Higher df_ref, lower drag_ref
- Low drag circuits (Monza, Jeddah, Baku): Lower df_ref, higher drag_ref
- Balanced circuits: Moderate values
"""

import json
from pathlib import Path
from typing import Dict, Any

def get_aero_reference_for_circuit(circuit_id: str) -> Dict[str, float]:
    """
    Get circuit-specific aero reference values based on real circuit data.
    
    Logic based on power_bias from circuit telemetry:
    - Low power bias (< 0.63) = technical circuits = accept more drag for DF
    - High power bias (> 0.65) = power circuits = want less drag
    - Medium power bias = balanced
    """
    project_root = Path(__file__).resolve().parent.parent
    circuit_file = project_root / "config" / "circuits" / "derived" / circuit_id / f"{circuit_id}.json"
    
    # Default values
    default_values = {"df_ref": 72.0, "drag_ref": 31.0}
    
    if not circuit_file.exists():
        print(f"⚠️  Circuit file not found: {circuit_file}, using defaults")
        return default_values
    
    # Load circuit data
    with open(circuit_file, 'r', encoding='utf-8') as f:
        circuit_data = json.load(f)
    
    # Extract power_bias from stats
    power_bias = circuit_data.get("_meta", {}).get("stats", {}).get("power_bias", 0.64)
    drs_ratio = circuit_data.get("_meta", {}).get("stats", {}).get("drs_ratio", 0.35)
    
    # Logic based on power_bias (real data)
    if power_bias < 0.63:
        # Low power bias = technical circuits = accept more drag for DF
        df_ref = 78.0 + (0.63 - power_bias) * 50  # 78-85 DF
        drag_ref = 32.0 + (0.63 - power_bias) * 30  # 32-35 drag
    elif power_bias > 0.65:
        # High power bias = power circuits = want less drag
        df_ref = 70.0 - (power_bias - 0.65) * 50  # 65-70 DF
        drag_ref = 28.0 - (power_bias - 0.65) * 30  # 25-28 drag
    else:
        # Medium power bias = balanced
        df_ref = 74.0
        drag_ref = 30.0
    
    # Clamp values to reasonable ranges
    df_ref = max(65.0, min(85.0, df_ref))
    drag_ref = max(25.0, min(35.0, drag_ref))
    
    return {"df_ref": round(df_ref, 1), "drag_ref": round(drag_ref, 1)}

def update_penalty_profile(circuit_id: str) -> bool:
    """
    Update penalty profile with circuit-specific aero reference values.
    """
    project_root = Path(__file__).resolve().parent.parent
    profile_path = project_root / "config" / "circuits" / "derived" / circuit_id / "penalty_profile.json"
    
    if not profile_path.exists():
        print(f"⚠️  Penalty profile not found: {profile_path}")
        return False
    
    # Load existing profile
    with open(profile_path, 'r', encoding='utf-8') as f:
        profile = json.load(f)
    
    # Get circuit-specific aero reference
    aero_ref = get_aero_reference_for_circuit(circuit_id)
    
    # Add or update aero_reference section
    profile["aero_reference"] = aero_ref
    
    # Save updated profile
    with open(profile_path, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2)
    
    print(f"✅ Updated {circuit_id}: DF={aero_ref['df_ref']}, Drag={aero_ref['drag_ref']}")
    return True

def main():
    """Update all penalty profiles with circuit-specific aero reference values."""
    print("🔧 Generating circuit-specific aero reference values...")
    
    project_root = Path(__file__).resolve().parent.parent
    derived_dir = project_root / "config" / "circuits" / "derived"
    
    if not derived_dir.exists():
        print(f"❌ Derived directory not found: {derived_dir}")
        return
    
    # Get all circuit directories
    circuit_dirs = [d for d in derived_dir.iterdir() if d.is_dir()]
    
    updated_count = 0
    for circuit_dir in sorted(circuit_dirs):
        circuit_id = circuit_dir.name
        if update_penalty_profile(circuit_id):
            updated_count += 1
    
    print(f"\n📊 Summary: Updated {updated_count}/{len(circuit_dirs)} penalty profiles")
    print("\n🎯 Logic based on real power_bias data:")
    print("  Low power bias (< 0.63) = Technical circuits = High DF (78-85), High drag (32-35)")
    print("  High power bias (> 0.65) = Power circuits = Low DF (65-70), Low drag (25-28)")
    print("  Medium power bias = Balanced circuits = DF 74, Drag 30")
    print("\n📈 Examples:")
    print("  Budapest (power_bias=0.620) → High DF, High drag (accept drag for DF)")
    print("  Monza (power_bias=0.660) → Low DF, Low drag (prioritize speed over DF)")
    print("  Values calculated dynamically from real telemetry data!")

if __name__ == "__main__":
    main()
