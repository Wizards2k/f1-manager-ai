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
    Get circuit-specific aero reference values based on circuit characteristics.
    """
    # High DF circuits - need more downforce, less drag concern
    high_df_circuits = {
        "mc-1929_monaco": {"df_ref": 85.0, "drag_ref": 28.0},
        "hu-1986_budapest": {"df_ref": 82.0, "drag_ref": 29.0},
        "sg-2008_singapore": {"df_ref": 83.0, "drag_ref": 28.5},
    }
    
    # Low drag circuits - need less downforce, more drag concern
    low_drag_circuits = {
        "it-1922_monza": {"df_ref": 65.0, "drag_ref": 35.0},
        "sa-2021_jeddah": {"df_ref": 68.0, "drag_ref": 34.0},
        "az-2016_baku": {"df_ref": 70.0, "drag_ref": 33.0},
    }
    
    # Medium speed circuits - balanced
    medium_circuits = {
        "gb-1948_silverstone": {"df_ref": 75.0, "drag_ref": 31.0},
        "be-1925_spa_francorchamps": {"df_ref": 78.0, "drag_ref": 30.5},
        "ca-1978_montreal": {"df_ref": 74.0, "drag_ref": 31.5},
        "jp-1962_suzuka": {"df_ref": 75.0, "drag_ref": 32.0},
    }
    
    # Default values for other circuits
    default_values = {"df_ref": 72.0, "drag_ref": 31.0}
    
    # Check circuit-specific values
    if circuit_id in high_df_circuits:
        return high_df_circuits[circuit_id]
    elif circuit_id in low_drag_circuits:
        return low_drag_circuits[circuit_id]
    elif circuit_id in medium_circuits:
        return medium_circuits[circuit_id]
    else:
        return default_values

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
    print("\n🎯 Circuit Categories:")
    print("  High DF: Monaco (85/28), Budapest (82/29), Singapore (83/28.5)")
    print("  Low Drag: Monza (65/35), Jeddah (68/34), Baku (70/33)")
    print("  Balanced: Silverstone (75/31), Spa (78/30.5), Montreal (74/31.5), Suzuka (75/32)")
    print("  Default: All others (72/31)")

if __name__ == "__main__":
    main()
