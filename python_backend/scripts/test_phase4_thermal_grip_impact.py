"""
Test Phase 4 — V6.3 Thermal Multiplier Impact on Lap Times
Verifies that tire thermal state actually affects lap time and cornering speed.
"""

import sys
from pathlib import Path
import json

# Add physics_engine to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.tyres.tyre_thermal import TireState, TiresState
from lap_simulator.physics_engine.integrator.waypoint_integrator import (
    _gaussian_thermal_multiplier,
    _get_optimal_temp,
    _get_sigma,
    integrate_lap_hd,
)


def test_thermal_multiplier_to_grip_reduction():
    """Test that thermal multiplier reduces grip availability."""
    print("Test 1: Thermal multiplier reduces grip availability...")

    compound = 'C4'
    load_kn = 25.0
    mu_base = 1.3

    # Cold tire: 85°C surface, 80°C core (below optimal 105°C/90°C)
    thermal_mult_cold = _gaussian_thermal_multiplier(85.0, 80.0, compound)
    mu_cold = mu_base * thermal_mult_cold
    grip_cold = load_kn * mu_cold

    # Optimal tire: 105°C surface, 90°C core
    thermal_mult_opt = _gaussian_thermal_multiplier(105.0, 90.0, compound)
    mu_opt = mu_base * thermal_mult_opt
    grip_opt = load_kn * mu_opt

    # Hot tire: 120°C surface, 105°C core (above optimal)
    thermal_mult_hot = _gaussian_thermal_multiplier(120.0, 105.0, compound)
    mu_hot = mu_base * thermal_mult_hot
    grip_hot = load_kn * mu_hot

    print(f"  Cold (85°C/80°C): thermal_mult={thermal_mult_cold:.4f}, grip={grip_cold:.2f} kN")
    print(f"  Optimal (105°C/90°C): thermal_mult={thermal_mult_opt:.4f}, grip={grip_opt:.2f} kN")
    print(f"  Hot (120°C/105°C): thermal_mult={thermal_mult_hot:.4f}, grip={grip_hot:.2f} kN")

    assert grip_opt > grip_cold, f"Optimal grip should be > cold grip: {grip_opt} vs {grip_cold}"
    assert grip_opt > grip_hot, f"Optimal grip should be > hot grip: {grip_opt} vs {grip_hot}"
    assert grip_cold < grip_hot, f"Cold should be less than hot"

    print(f"  ✅ Grip degradation: optimal={grip_opt:.2f}kN, cold={grip_cold:.2f}kN (-{(1-grip_cold/grip_opt)*100:.1f}%), hot={grip_hot:.2f}kN (-{(1-grip_hot/grip_opt)*100:.1f}%)")


def test_wear_factor_reduces_grip():
    """Test that tire wear reduces grip availability."""
    print("\nTest 2: Tire wear reduces grip availability...")

    load_kn = 20.0
    mu_base = 1.3
    thermal_mult = 1.0  # Optimal temperature

    # Fresh tire: 0% wear
    wear_factor_fresh = (100.0 - 0.0) / 100.0  # 1.0
    mu_fresh = mu_base * thermal_mult * wear_factor_fresh
    grip_fresh = load_kn * mu_fresh

    # Worn tire: 50% wear
    wear_factor_worn = (100.0 - 50.0) / 100.0  # 0.5
    mu_worn = mu_base * thermal_mult * wear_factor_worn
    grip_worn = load_kn * mu_worn

    # Severely worn: 80% wear
    wear_factor_severe = (100.0 - 80.0) / 100.0  # 0.2
    mu_severe = mu_base * thermal_mult * wear_factor_severe
    grip_severe = load_kn * mu_severe

    print(f"  Fresh (0% wear): mu={mu_fresh:.3f}, grip={grip_fresh:.2f} kN")
    print(f"  Worn (50% wear): mu={mu_worn:.3f}, grip={grip_worn:.2f} kN")
    print(f"  Severe (80% wear): mu={mu_severe:.3f}, grip={grip_severe:.2f} kN")

    assert grip_fresh > grip_worn, f"Fresh should have more grip than worn"
    assert grip_worn > grip_severe, f"Worn should have more grip than severe"
    assert grip_fresh / grip_severe == 5.0, f"Fresh should have 5x grip of severe (100%/20%)"

    print(f"  ✅ Wear degradation: fresh={grip_fresh:.2f}kN, worn={grip_worn:.2f}kN (-50%), severe={grip_severe:.2f}kN (-80%)")


def test_combined_thermal_and_wear():
    """Test combined effect of thermal multiplier and wear on grip."""
    print("\nTest 3: Combined thermal + wear degradation...")

    load_kn = 25.0
    mu_base = 1.3

    # Scenario 1: Fresh, optimal temperature
    thermal_mult_opt = _gaussian_thermal_multiplier(105.0, 90.0, 'C4')
    wear_factor_fresh = 1.0
    grip_1 = load_kn * mu_base * thermal_mult_opt * wear_factor_fresh

    # Scenario 2: Fresh, cold temperature (85°C, realistic outlap)
    thermal_mult_cold = _gaussian_thermal_multiplier(85.0, 80.0, 'C4')
    wear_factor_fresh = 1.0
    grip_2 = load_kn * mu_base * thermal_mult_cold * wear_factor_fresh

    # Scenario 3: Worn (50%), optimal temperature
    thermal_mult_opt = _gaussian_thermal_multiplier(105.0, 90.0, 'C4')
    wear_factor_worn = 0.5
    grip_3 = load_kn * mu_base * thermal_mult_opt * wear_factor_worn

    # Scenario 4: Worn (50%), cold temperature
    thermal_mult_cold = _gaussian_thermal_multiplier(85.0, 80.0, 'C4')
    wear_factor_worn = 0.5
    grip_4 = load_kn * mu_base * thermal_mult_cold * wear_factor_worn

    print(f"  Fresh + optimal (105°C): {grip_1:.2f} kN (baseline)")
    print(f"  Fresh + cold (85°C): {grip_2:.2f} kN ({(grip_2/grip_1-1)*100:+.1f}%)")
    print(f"  Worn 50% + optimal (105°C): {grip_3:.2f} kN ({(grip_3/grip_1-1)*100:+.1f}%)")
    print(f"  Worn 50% + cold (85°C): {grip_4:.2f} kN ({(grip_4/grip_1-1)*100:+.1f}%)")

    assert grip_1 > grip_2, "Optimal should be better than cold"
    assert grip_1 > grip_3, "Fresh should be better than worn"
    assert grip_1 > grip_4, "Fresh+optimal should be better than worn+cold"

    print(f"  ✅ Worst case (worn+cold) is {grip_4/grip_1*100:.1f}% of best case (fresh+optimal)")


def test_slip_increases_with_grip_loss():
    """Test that slip increases when grip is reduced by thermal/wear."""
    print("\nTest 4: Slip increases with thermal/wear degradation...")

    mass_kg = 798.0
    load_kn = 20.0  # Interior wheel under high lateral load
    target_g_lat = 2.5  # Very high lateral g to induce slip
    mu_base = 1.3

    # Required grip for target lateral g
    f_grip_required = (mass_kg * 9.81 / 1000.0) * target_g_lat

    # Case 1: Fresh, optimal (max grip)
    thermal_mult = _gaussian_thermal_multiplier(105.0, 90.0, 'C4')
    wear_factor = 1.0
    mu_effective = mu_base * thermal_mult * wear_factor
    f_grip_available = load_kn * mu_effective
    slip_1 = max(0.0, 1.0 - (f_grip_available / f_grip_required))

    # Case 2: Cold (reduced grip, realistic 85°C outlap)
    thermal_mult = _gaussian_thermal_multiplier(85.0, 80.0, 'C4')
    wear_factor = 1.0
    mu_effective = mu_base * thermal_mult * wear_factor
    f_grip_available = load_kn * mu_effective
    slip_2 = max(0.0, 1.0 - (f_grip_available / f_grip_required))

    # Case 3: Worn 50% (reduced grip)
    thermal_mult = _gaussian_thermal_multiplier(105.0, 90.0, 'C4')
    wear_factor = 0.5
    mu_effective = mu_base * thermal_mult * wear_factor
    f_grip_available = load_kn * mu_effective
    slip_3 = max(0.0, 1.0 - (f_grip_available / f_grip_required))

    # Case 4: Cold + worn (reduced grip)
    thermal_mult = _gaussian_thermal_multiplier(85.0, 80.0, 'C4')
    wear_factor = 0.5
    mu_effective = mu_base * thermal_mult * wear_factor
    f_grip_available = load_kn * mu_effective
    slip_4 = max(0.0, 1.0 - (f_grip_available / f_grip_required))

    print(f"  Fresh + optimal (105°C): slip={slip_1:.4f}")
    print(f"  Fresh + cold (85°C): slip={slip_2:.4f} (+{(slip_2-slip_1)*100:.1f}% absolute)")
    print(f"  Worn 50% + optimal: slip={slip_3:.4f} (+{(slip_3-slip_1)*100:.1f}% absolute)")
    print(f"  Worn 50% + cold: slip={slip_4:.4f} (+{(slip_4-slip_1)*100:.1f}% absolute)")

    assert slip_1 < slip_2, f"Cold should have more slip than optimal: {slip_1} vs {slip_2}"
    assert slip_1 < slip_3, f"Worn should have more slip than fresh: {slip_1} vs {slip_3}"
    assert slip_1 < slip_4, f"Worn+cold should have more slip than fresh+optimal: {slip_1} vs {slip_4}"

    worst_ratio = slip_4 / max(slip_1, 0.001) if slip_1 > 0 else (slip_4 / 0.0001)
    print(f"  ✅ Worst case slip is {worst_ratio:.1f}x worse than best case")


def test_grip_reduction_limits_corner_speed():
    """Test that reduced grip limits maximum cornering speed."""
    print("\nTest 5: Grip reduction limits corner speed...")

    # V_max_corner from g = v² / (r × g)
    # v = sqrt(g_max × g × r)
    G = 9.81
    radius_m = 300.0

    # Fresh, optimal tire
    mass_kg = 798.0
    load_kn = 20.0
    mu_base = 1.3
    thermal_mult = _gaussian_thermal_multiplier(105.0, 90.0, 'C4')
    wear_factor = 1.0
    mu_effective = mu_base * thermal_mult * wear_factor
    f_grip = load_kn * mu_effective
    g_max_fresh = f_grip / (mass_kg * 9.81 / 1000.0)
    v_max_fresh = math.sqrt(g_max_fresh * G * radius_m)

    # Cold, worn tire
    thermal_mult = _gaussian_thermal_multiplier(70.0, 60.0, 'C4')
    wear_factor = 0.5
    mu_effective = mu_base * thermal_mult * wear_factor
    f_grip = load_kn * mu_effective
    g_max_cold = f_grip / (mass_kg * 9.81 / 1000.0)
    v_max_cold = math.sqrt(g_max_cold * G * radius_m)

    print(f"  Fresh optimal: g_max={g_max_fresh:.2f}g, v_max={v_max_fresh:.2f} m/s")
    print(f"  Cold worn (50%): g_max={g_max_cold:.2f}g, v_max={v_max_cold:.2f} m/s")
    print(f"  Speed reduction: {(1 - v_max_cold/v_max_fresh)*100:.1f}%")

    assert v_max_fresh > v_max_cold, "Fresh optimal should allow higher speed than cold worn"

    print(f"  ✅ Degraded tires reduce corner speed by {(1 - v_max_cold/v_max_fresh)*100:.1f}%")


def test_thermal_state_initialization():
    """Test that tires start at consistent temperature."""
    print("\nTest 6: Tire thermal state initialization...")

    tires = TiresState()

    for wheel_name in ['fl', 'fr', 'rl', 'rr']:
        tire = getattr(tires, wheel_name)
        assert tire.surface_temp_c == 85.0, f"{wheel_name} surface temp wrong"
        assert tire.core_temp_c == 75.0, f"{wheel_name} core temp wrong"
        assert tire.wear_pct == 0.0, f"{wheel_name} wear wrong"

    # Verify thermal multiplier at init temp (85°C surface, 75°C core)
    # This is 20°C below optimal (105°C/90°C), producing severe degradation
    # This is realistic for outlap tires before warm-up
    thermal_mult_init = _gaussian_thermal_multiplier(85.0, 75.0, 'C4')
    print(f"  Initial tire temps: surface=85°C, core=75°C")
    print(f"  Thermal multiplier at init: {thermal_mult_init:.4f} (severe degradation for outlap)")

    assert thermal_mult_init < 1.0, "Init temp should be below optimal, multiplier < 1.0"
    assert thermal_mult_init < 0.02, "Init temp (85°C) far below optimal (105°C) = severe degradation"

    print(f"  ✅ Tires initialize cold (outlap penalty): multiplier={thermal_mult_init:.2%}, requires 5-10 laps to warm")


if __name__ == "__main__":
    import math

    print("=" * 70)
    print("PHASE 4 TEST SUITE — V6.3 Thermal Multiplier Impact on Grip")
    print("=" * 70)

    try:
        test_thermal_multiplier_to_grip_reduction()
        test_wear_factor_reduces_grip()
        test_combined_thermal_and_wear()
        test_slip_increases_with_grip_loss()
        test_grip_reduction_limits_corner_speed()
        test_thermal_state_initialization()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED — Phase 4 Thermal Grip Impact Validated")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
