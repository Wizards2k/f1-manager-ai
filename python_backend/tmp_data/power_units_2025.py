"""
Power Unit data registry for 2025 season
Generated from race performance gaps (first 3 GPs)
NOT CONNECTED TO GAME - sandbox data only
"""

from dataclasses import dataclass
from typing import Dict, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.power_unit import PowerUnit, ICE, MGUK, MGUH, Battery, IceMap, ErsMap, PUReliabilityParams


def create_power_unit_2025(team_name: str, scaling_factor: float) -> PowerUnit:
    """
    Create a PowerUnit instance scaled based on team performance
    scaling_factor: 1.0 = baseline (McLaren), >1.0 = slower
    """
    
    # Baseline McLaren power unit specs
    base_ice_power = 560000  # Watts
    base_mguk_power = 120000  # Watts  
    base_mguh_power = 90000   # Watts
    base_battery_capacity = 4.0  # MJ
    
    # Apply scaling (higher factor = less power)
    ice_power = base_ice_power / scaling_factor
    mguk_power = base_mguk_power / scaling_factor
    mguh_power = base_mguh_power / scaling_factor
    battery_capacity = base_battery_capacity / scaling_factor
    
    # Create components
    ice = ICE(
        ice_id=1,
        nome="ICE-2025",
        potenza_pct=1.0 / scaling_factor,  # Scale power percentage
        temp_warning_c=130.0,
        temp_critical_c=140.0,
        wear_coeff=0.0008 * scaling_factor,  # More wear for slower teams
        overrev_factor=1.15,
        shock_factor=1.10
    )
    
    mgu_k = MGUK(
        mgu_k_id=1,
        nome="MGUK-2025",
        max_kw=120.0 / scaling_factor,  # Scale MGUK power
        efficienza=1.0 / scaling_factor,
        temp_warning_c=95.0,
        temp_critical_c=110.0,
        wear_coeff=0.0012
    )
    
    mgu_h = MGUH(
        mgu_h_id=1,
        nome="MGUH-2025", 
        base_kw=90.0 / scaling_factor,  # Scale MGUH power
        direct_ratio_default=0.0,
        efficienza=1.0 / scaling_factor,
        temp_warning_c=95.0,
        temp_critical_c=110.0,
        wear_coeff=0.0010
    )
    
    battery = Battery(
        battery_id=1,
        nome="Battery-2025",
        capacity_mj=4.0 / scaling_factor,  # Scale battery capacity
        max_charge_kw=120.0,
        max_discharge_kw=160.0,
        temp_warning_c=60.0,
        temp_critical_c=80.0,
        wear_coeff=0.0010
    )
    
    # Create maps
    ice_maps = {
        1: IceMap(
            ice_map_id=1,
            nome="Standard",
            power_pct=1.0 / scaling_factor,
            heat_load_kw=260.0 * scaling_factor,
            cooling_share=0.5,
            deployment_style="balanced"
        )
    }
    
    ers_maps = {
        1: ErsMap(
            ers_map_id=1,
            nome="Standard",
            deploy_budget_mj=4.0 / scaling_factor,
            bucket_primary_pct=0.4,
            bucket_secondary_pct=0.3,
            bucket_exit_pct=0.2,
            defense_reserve_mj=0.4,
            ers_output_kw=120.0 / scaling_factor,
            mguh_direct_ratio=0.45,
            mguh_power_kw=90.0 / scaling_factor,
            heat_load_kw=260.0 * scaling_factor,
            cooling_share=0.5,
            deployment_style="balanced"
        )
    }
    
    return PowerUnit(
        pu_id=1,
        nome=f"PU-{team_name}-2025",
        fornitore=team_name,
        anno=2025,
        spec_version="v1.0",
        ice=ice,
        mgu_k=mgu_k,
        mgu_h=mgu_h,
        battery=battery,
        ice_maps=ice_maps,
        ers_maps=ers_maps,
        reliability=PUReliabilityParams(
            ice_wear_coeff=0.0008 * scaling_factor,
            ice_temp_warning_c=130.0,
            ice_temp_critical_c=140.0,
            ice_overrev_factor=1.15,
            ice_shock_factor=1.10,
            ers_wear_coeff=0.0012 * scaling_factor,
            ers_temp_warning_c=90.0,
            ers_temp_critical_c=100.0,
            ers_overrev_factor=1.10,
            ers_shock_factor=1.05
        ),
        fuel_tank_capacity_kg=110.0,
        deploy_limit_mj_per_lap=4.0 / scaling_factor,
        recovery_limit_mj_per_lap=2.0 / scaling_factor,
        default_ice_map_id=1,
        default_ers_map_id=1
    )


# Power unit registry based on 2025 performance gaps
POWER_UNITS_2025: Dict[str, PowerUnit] = {
    'MCL': create_power_unit_2025('McLaren', 1.0000),  # Baseline
    'RBR': create_power_unit_2025('Red Bull', 1.0020),  # +0.2% slower
    'FER': create_power_unit_2025('Ferrari', 1.0030),   # +0.3% slower
    'MER': create_power_unit_2025('Mercedes', 1.0045),  # +0.45% slower
    'AST': create_power_unit_2025('Aston Martin', 1.0063),  # +0.63% slower
    'ALP': create_power_unit_2025('Alpine', 1.0080),    # +0.8% slower
    'HAAS': create_power_unit_2025('Haas', 1.0103),     # +1.03% slower
    'WIL': create_power_unit_2025('Williams', 1.0120), # +1.2% slower
    'SAU': create_power_unit_2025('Sauber', 1.0137),   # +1.37% slower
    'RBRB': create_power_unit_2025('RB', 1.0170),      # +1.7% slower
}


def get_power_unit(team_code: str) -> Optional[PowerUnit]:
    """Get power unit for team code"""
    return POWER_UNITS_2025.get(team_code)


def list_all_power_units() -> Dict[str, PowerUnit]:
    """Get all power units"""
    return POWER_UNITS_2025.copy()


if __name__ == "__main__":
    # Test output
    print("=== POWER UNITS 2025 REGISTRY ===")
    for team_code, pu in POWER_UNITS_2025.items():
        print(f"{team_code}: {pu.nome} - ICE Power: {pu.ice.potenza_pct:.3f}")
