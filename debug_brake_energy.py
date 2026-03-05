#!/usr/bin/env python3
"""
Debug script to check braking energy data loading.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "python_backend"))

from python_backend.lap_simulator.config_loader import load_circuit_config

def debug_brake_energy():
    """Debug braking energy data loading."""
    
    config = load_circuit_config("az-2016_baku")
    
    print("="*80)
    print("BRAKE ENERGY DEBUG - BAKU")
    print("="*80)
    
    print(f"\nTotal sections: {len(config.sections)}")
    
    # Show sections with braking energy
    brake_sections = [s for s in config.sections if s.braking_energy_mj > 0]
    print(f"Sections with any braking energy: {len(brake_sections)}")
    
    # Show high energy sections
    high_energy = [s for s in config.sections if s.braking_energy_mj >= 0.05]
    print(f"Sections with braking_energy_mj >= 0.05: {len(high_energy)}")
    
    print(f"\nFirst 10 sections with braking energy:")
    for i, section in enumerate(brake_sections[:10]):
        print(f"  {i+1:2d}. {section.name:15}: {section.braking_energy_mj:6.3f} MJ | {section.kind.value}")
    
    # Show critical sections
    critical = config.brake_critical_sections or []
    print(f"\nCritical sections from config: {len(critical)}")
    for cs in critical[:5]:
        print(f"  - {cs.get('name', 'Unknown')}: {cs.get('braking_energy_mj', 0):.3f} MJ")
    
    print(f"\n🎉 Debug completed!")

if __name__ == "__main__":
    debug_brake_energy()
