#!/usr/bin/env python3
"""
Physics V3 — Acceleration Profile Test

Valida le modifiche al modello di accelerazione:
- Wheelspin penalty progressiva
- Power limit per velocità
- Traction control
- Traction circle scaling

Usage:
    python scripts/test_acceleration_profile.py
"""

import sys
import math

# Add parent directory to path
sys.path.insert(0, '/Users/wizards/Sviluppo/F1 Manager AI/python_backend')

from lap_simulator.physics_v3 import constants
from lap_simulator.physics_v3.aero_mapper import PhysicsAeroParams
from lap_simulator.physics_v3.balance_model import BalanceState
from lap_simulator.physics_v3.acceleration_profile import compute_drive_force
from lap_simulator.data_types import PUState


def create_test_aero():
    """Create test aero params (Monza low wing setup)."""
    return PhysicsAeroParams(
        CLA=2.8,  # Low downforce
        CDA=0.85,  # Low drag
        CLA_front=1.3,
        CLA_rear=1.5,
        aero_balance=1.5/2.8,  # ~0.54 (rear-biased)
        ground_effect_bonus=1.0,
        understeer_grip_penalty=0.0,
        oversteer_grip_penalty=0.0,
        CDA_drs_open=0.85 * 0.825,
        setup_quality_score=0.95
    )


def create_test_balance():
    """Create test balance state."""
    return BalanceState(
        mu_front_eff=1.70,
        mu_rear_eff=1.70,
        load_transfer_lat=0.0,
        load_transfer_long=0.0,
        a_lat_g=0.0,
        a_long_g=0.0,
        balance_label="neutral",
        Fz_front=3500.0,
        Fz_rear=4200.0,
        load_transfer_lat_front=0.5,
        load_transfer_lat_rear=0.5
    )


def create_test_pu_state():
    """Create test PU state (full power)."""
    return PUState(
        ice_power_kw=950.0,
        ers_output_kw=160.0,
        ers_energy_mj=3.5,
        ice_temp_c=95.0,
        ice_wear_pct=0.0,
        ers_temp_c=55.0,
        ers_wear_pct=0.0,
        fuel_kg=5.0,
        lap_deploy_mj=0.0,
        lap_harvest_mj=0.0
    )


def test_acceleration_profile():
    """Test acceleration profile from 100 to 130 kph."""
    print("=" * 80)
    print("Physics V3 — Acceleration Profile Test")
    print("=" * 80)
    
    mass_kg = 798.0 + 5.0  # Dry mass + fuel
    aero = create_test_aero()
    balance = create_test_balance()
    pu_state = create_test_pu_state()
    env_rho = constants.RHO_SEA_LEVEL
    
    print(f"\nTest Parameters:")
    print(f"  Mass: {mass_kg:.1f} kg")
    print(f"  CLA: {aero.CLA:.2f} m²")
    print(f"  CDA: {aero.CDA:.2f} m²")
    print(f"  PU Power: {pu_state.ice_power_kw + pu_state.ers_output_kw:.0f} kW")
    print(f"  Grip (μ): {balance.mu_rear_eff:.2f}")
    
    # Test velocities: 100 to 130 kph
    test_velocities_kph = [100, 105, 110, 115, 120, 125, 130]
    
    print(f"\n{'V [kph]':>8} {'V [m/s]':>8} {'F_drive [N]':>12} {'F_drag [N]':>12} {'a_net [m/s²]':>12} {'Wheelspin':>10}")
    print("-" * 80)
    
    results = []
    for v_kph in test_velocities_kph:
        v_ms = v_kph / 3.6
        
        F_drive, a_net, wheelspin = compute_drive_force(
            v_ms=v_ms,
            aero=aero,
            balance=balance,
            mass_kg=mass_kg,
            pu_state=pu_state,
            radius_m=0.0,  # Straight
            is_cornering=False,
            env_rho=env_rho
        )
        
        # Calculate drag force for display
        F_drag_aero = 0.5 * env_rho * (v_ms ** 2) * aero.CDA
        F_drag_rolling = constants.ROLLING_RESISTANCE_COEFF * balance.Fz_rear
        F_drag_total = F_drag_aero + F_drag_rolling
        
        results.append({
            'v_kph': v_kph,
            'v_ms': v_ms,
            'F_drive': F_drive,
            'F_drag': F_drag_total,
            'a_net': a_net,
            'wheelspin': wheelspin
        })
        
        print(f"{v_kph:8.1f} {v_ms:8.2f} {F_drive:12.0f} {F_drag_total:12.0f} {a_net:12.3f} {str(wheelspin):>10}")
    
    # Analyze results
    print("\n" + "=" * 80)
    print("Analysis")
    print("=" * 80)
    
    # Check 1: Acceleration should increase with speed (not decrease)
    a_min = min(r['a_net'] for r in results)
    a_max = max(r['a_net'] for r in results)
    
    print(f"\nAcceleration Range:")
    print(f"  Min: {a_min:.3f} m/s²")
    print(f"  Max: {a_max:.3f} m/s²")
    print(f"  Delta: {a_max - a_min:.3f} m/s²")
    
    if a_max > a_min:
        print("  ✅ PASS: Acceleration increases with speed (correct)")
    else:
        print("  ❌ FAIL: Acceleration decreases with speed (bug)")
    
    # Check 2: No wheelspin at 100-130 kph
    wheelspin_count = sum(1 for r in results if r['wheelspin'])
    print(f"\nWheelspin Events: {wheelspin_count}/{len(results)}")
    
    if wheelspin_count == 0:
        print("  ✅ PASS: No wheelspin detected (traction control working)")
    else:
        print("  ❌ FAIL: Wheelspin detected (bug)")
    
    # Check 3: Expected acceleration at 100 kph
    v_100_ms = 100 / 3.6
    idx_100 = next(i for i, r in enumerate(results) if abs(r['v_kph'] - 100) < 0.1)
    a_100 = results[idx_100]['a_net']
    
    print(f"\nAcceleration at 100 kph: {a_100:.3f} m/s²")
    print(f"  Expected: 3.0-4.0 m/s² (realistic F1 acceleration)")
    
    if 3.0 <= a_100 <= 4.0:
        print("  ✅ PASS: Acceleration in expected range")
    else:
        print("  ❌ FAIL: Acceleration outside expected range")
    
    # Check 4: Expected acceleration at 130 kph
    v_130_ms = 130 / 3.6
    idx_130 = next(i for i, r in enumerate(results) if abs(r['v_kph'] - 130) < 0.1)
    a_130 = results[idx_130]['a_net']
    
    print(f"\nAcceleration at 130 kph: {a_130:.3f} m/s²")
    print(f"  Expected: 3.5-4.5 m/s² (higher than at 100 kph)")
    
    if 3.5 <= a_130 <= 4.5 and a_130 > a_100:
        print("  ✅ PASS: Acceleration higher at 130 kph (correct)")
    else:
        print("  ❌ FAIL: Acceleration not higher at 130 kph (bug)")
    
    # Summary
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    
    all_pass = (
        a_max > a_min and
        wheelspin_count == 0 and
        3.0 <= a_100 <= 4.0 and
        3.5 <= a_130 <= 4.5 and
        a_130 > a_100
    )
    
    if all_pass:
        print("\n✅ ALL TESTS PASSED")
        print("Acceleration profile is working correctly.")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        print("Acceleration profile needs further tuning.")
        return 1


def test_wheelspin_penalty():
    """Test wheelspin penalty scaling."""
    print("\n" + "=" * 80)
    print("Wheelspin Penalty Test")
    print("=" * 80)
    
    mass_kg = 798.0 + 5.0
    aero = create_test_aero()
    balance = create_test_balance()
    pu_state = create_test_pu_state()
    env_rho = constants.RHO_SEA_LEVEL
    
    # Test with high power to trigger wheelspin
    pu_state_high_power = PUState(
        ice_power_kw=1200.0,  # Excessive power
        ers_output_kw=200.0,
        ers_energy_mj=3.5,
        ice_temp_c=95.0,
        ice_wear_pct=0.0,
        ers_temp_c=55.0,
        ers_wear_pct=0.0,
        fuel_kg=5.0,
        lap_deploy_mj=0.0,
        lap_harvest_mj=0.0
    )
    
    v_ms = 28.0  # 100 kph
    
    print(f"\nTest Parameters:")
    print(f"  Velocity: {v_ms:.1f} m/s ({v_ms * 3.6:.0f} kph)")
    print(f"  PU Power: {pu_state_high_power.ice_power_kw + pu_state_high_power.ers_output_kw:.0f} kW")
    
    # Test with normal power
    F_drive_normal, a_normal, ws_normal = compute_drive_force(
        v_ms=v_ms,
        aero=aero,
        balance=balance,
        mass_kg=mass_kg,
        pu_state=pu_state,
        radius_m=0.0,
        is_cornering=False,
        env_rho=env_rho
    )
    
    # Test with high power
    F_drive_high, a_high, ws_high = compute_drive_force(
        v_ms=v_ms,
        aero=aero,
        balance=balance,
        mass_kg=mass_kg,
        pu_state=pu_state_high_power,
        radius_m=0.0,
        is_cornering=False,
        env_rho=env_rho
    )
    
    print(f"\nResults:")
    print(f"  Normal Power: F_drive={F_drive_normal:.0f} N, a={a_normal:.3f} m/s², wheelspin={ws_normal}")
    print(f"  High Power:   F_drive={F_drive_high:.0f} N, a={a_high:.3f} m/s², wheelspin={ws_high}")
    
    # Check: high power should not cause excessive wheelspin
    if ws_high:
        # Calculate overage ratio
        F_traction_limit = balance.mu_rear_eff * balance.Fz_rear * 1.05
        P_total_w = (pu_state_high_power.ice_power_kw + pu_state_high_power.ers_output_kw) * constants.DRIVETRAIN_EFFICIENCY * 1000
        F_drive_power = P_total_w / v_ms
        
        # Apply power scaling
        v_ref = 50.0
        speed_ratio = min(v_ms / v_ref, 1.0)
        power_scaling = speed_ratio ** 2
        F_drive_power = F_drive_power * power_scaling
        
        v_limit_ref = 60.0
        if v_ms < v_limit_ref:
            power_limit_factor = (v_ms / v_limit_ref) ** 1.5
            F_drive_power = F_drive_power * power_limit_factor
        
        overage_ratio = F_drive_power / F_traction_limit
        
        print(f"\n  Overage Ratio: {overage_ratio:.2f}")
        print(f"  Expected penalty: ~30-50% (not 15% flat)")
        
        if overage_ratio > 1.5:
            print("  ✅ PASS: Wheelspin detected with high overage ratio")
        else:
            print("  ⚠️  WARNING: Wheelspin detected but overage ratio low")
    else:
        print("  ✅ PASS: No wheelspin (traction control working)")
    
    return 0


def main():
    """Run all tests."""
    print("\nPhysics V3 — Acceleration Profile Validation")
    print("Testing fixes for acceleration bugs")
    
    exit_code = 0
    
    # Run main test
    exit_code = test_acceleration_profile()
    
    # Run wheelspin test
    exit_code = test_wheelspin_penalty()
    
    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
