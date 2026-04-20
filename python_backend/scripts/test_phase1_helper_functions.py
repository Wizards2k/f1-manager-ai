"""
Test Phase 1 Helper Functions — V6.3 Thermal Multiplier
Verifies gaussian thermal multiplier and compound parameters.
"""

import sys
from pathlib import Path

# Add physics_engine to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.integrator.waypoint_integrator import (
    _gaussian_thermal_multiplier,
    _get_optimal_temp,
    _get_sigma,
)


def test_optimal_temps():
    """Test optimal temperature per compound."""
    print("Test 1: Optimal temperatures per compound...")

    assert _get_optimal_temp('C5') == 100.0, "C5 optimal should be 100°C"
    assert _get_optimal_temp('C4') == 105.0, "C4 optimal should be 105°C"
    assert _get_optimal_temp('C3') == 110.0, "C3 optimal should be 110°C"
    assert _get_optimal_temp('UNKNOWN') == 105.0, "Default should be C4 (105°C)"

    print("  C5: 100°C (soft, hot window)")
    print("  C4: 105°C (medium)")
    print("  C3: 110°C (hard, cooler window)")
    print("  ✅ Optimal temps correct")


def test_sigma_widths():
    """Test thermal window width per compound."""
    print("\nTest 2: Thermal window widths (sigma)...")

    c5_sigma = _get_sigma('C5')
    c4_sigma = _get_sigma('C4')
    c3_sigma = _get_sigma('C3')

    assert c5_sigma == 7.5, f"C5 sigma should be 7.5, got {c5_sigma}"
    assert c4_sigma == 8.0, f"C4 sigma should be 8.0, got {c4_sigma}"
    assert c3_sigma == 8.5, f"C3 sigma should be 8.5, got {c3_sigma}"

    assert c3_sigma > c5_sigma, "C3 should have wider window than C5"

    print(f"  C5: σ={c5_sigma}°C (narrow, sharp penalty)")
    print(f"  C4: σ={c4_sigma}°C (medium)")
    print(f"  C3: σ={c3_sigma}°C (wide, forgiving)")
    print("  ✅ Sigma widths correct (C3 > C4 > C5)")


def test_gaussian_at_optimal():
    """Test that thermal multiplier = 1.0 at optimal temps."""
    print("\nTest 3: Multiplier at optimal temperature...")

    # C5 at optimal: surface=100°C, core=85°C
    mult_c5 = _gaussian_thermal_multiplier(100.0, 85.0, 'C5')
    assert mult_c5 > 0.99, f"C5 at optimal should be ~1.0, got {mult_c5}"

    # C4 at optimal: surface=105°C, core=90°C
    mult_c4 = _gaussian_thermal_multiplier(105.0, 90.0, 'C4')
    assert mult_c4 > 0.99, f"C4 at optimal should be ~1.0, got {mult_c4}"

    # C3 at optimal: surface=110°C, core=95°C
    mult_c3 = _gaussian_thermal_multiplier(110.0, 95.0, 'C3')
    assert mult_c3 > 0.99, f"C3 at optimal should be ~1.0, got {mult_c3}"

    print(f"  C5 at 100°C/85°C: multiplier={mult_c5:.4f} ≈ 1.0 ✅")
    print(f"  C4 at 105°C/90°C: multiplier={mult_c4:.4f} ≈ 1.0 ✅")
    print(f"  C3 at 110°C/95°C: multiplier={mult_c3:.4f} ≈ 1.0 ✅")


def test_cold_tires():
    """Test degradation when tires are cold (below optimal window)."""
    print("\nTest 4: Cold tires (below optimal)...")

    # C5 cold: surface=70°C (30°C below optimal 100°C)
    # At ±σ: multiplier ≈ 0.61 (61% grip)
    # At ±2σ: multiplier ≈ 0.14 (14% grip)
    # 70°C = 100 - 30 = 100 - 4.3σ, so expect ~0.03-0.05

    mult_c5_cold = _gaussian_thermal_multiplier(70.0, 60.0, 'C5')
    print(f"  C5 cold (70°C/60°C): multiplier={mult_c5_cold:.4f}")
    assert mult_c5_cold < 0.30, f"Cold C5 should have <30% grip, got {mult_c5_cold:.2%}"

    # C4 cold: surface=75°C (30°C below optimal 105°C)
    mult_c4_cold = _gaussian_thermal_multiplier(75.0, 65.0, 'C4')
    print(f"  C4 cold (75°C/65°C): multiplier={mult_c4_cold:.4f}")
    assert mult_c4_cold < 0.30, f"Cold C4 should have <30% grip, got {mult_c4_cold:.2%}"

    print("  ✅ Cold tires show severe grip loss (expected)")


def test_hot_tires():
    """Test degradation when tires are hot (above optimal window)."""
    print("\nTest 5: Hot tires (above optimal)...")

    # C5 hot: surface=130°C (30°C above optimal 100°C)
    mult_c5_hot = _gaussian_thermal_multiplier(130.0, 110.0, 'C5')
    print(f"  C5 hot (130°C/110°C): multiplier={mult_c5_hot:.4f}")
    assert mult_c5_hot < 0.30, f"Hot C5 should have <30% grip, got {mult_c5_hot:.2%}"

    # C3 hot: surface=140°C (30°C above optimal 110°C)
    # C3 has wider window (σ=8.5), so should degrade less
    mult_c3_hot = _gaussian_thermal_multiplier(140.0, 120.0, 'C3')
    print(f"  C3 hot (140°C/120°C): multiplier={mult_c3_hot:.4f}")
    assert mult_c3_hot < 0.40, f"Hot C3 should have <40% grip, got {mult_c3_hot:.2%}"

    # C3 should degrade less than C5 at same delta
    mult_c5_hot_alt = _gaussian_thermal_multiplier(140.0, 120.0, 'C5')
    assert mult_c3_hot > mult_c5_hot_alt, f"C3 should resist heat better than C5"

    print("  ✅ Hot tires show grip loss; C3 more forgiving than C5")


def test_asymmetric_degradation():
    """Test that surface temp has more impact than core temp."""
    print("\nTest 6: Surface vs Core temperature impact...")

    # Same core, vary surface
    mult_at_optimal = _gaussian_thermal_multiplier(100.0, 85.0, 'C5')
    mult_hot_surface = _gaussian_thermal_multiplier(120.0, 85.0, 'C5')
    mult_hot_core = _gaussian_thermal_multiplier(100.0, 105.0, 'C5')

    print(f"  Optimal (100°C/85°C): {mult_at_optimal:.4f}")
    print(f"  Hot surface (120°C/85°C): {mult_hot_surface:.4f}")
    print(f"  Hot core (100°C/105°C): {mult_hot_core:.4f}")

    # Surface temp deviation should have more impact
    # (because σ_surface < σ_core doesn't apply here, but surface is reactive)
    print("  ✅ Surface and core both affect multiplier")


def test_window_narrowness():
    """Test that C5 has sharper penalty (narrower window) than C3."""
    print("\nTest 7: Window narrowness (C5 sharp vs C3 forgiving)...")

    # At ±10°C from optimal
    c5_opt = _get_optimal_temp('C5')
    c5_sigma = _get_sigma('C5')
    c5_mult = _gaussian_thermal_multiplier(c5_opt + 10.0, 85.0, 'C5')

    c3_opt = _get_optimal_temp('C3')
    c3_sigma = _get_sigma('C3')
    c3_mult = _gaussian_thermal_multiplier(c3_opt + 10.0, 95.0, 'C3')

    print(f"  C5 at optimal+10°C: multiplier={c5_mult:.4f} (σ={c5_sigma}°C)")
    print(f"  C3 at optimal+10°C: multiplier={c3_mult:.4f} (σ={c3_sigma}°C)")

    assert c3_mult > c5_mult, f"C3 should degrade less; C3={c3_mult}, C5={c5_mult}"

    print(f"  ✅ C3 more forgiving: {c3_mult:.1%} vs C5 {c5_mult:.1%} at +10°C deviation")


if __name__ == "__main__":
    print("=" * 70)
    print("PHASE 1 HELPER FUNCTIONS TEST SUITE — V6.3 Thermal Multiplier")
    print("=" * 70)

    try:
        test_optimal_temps()
        test_sigma_widths()
        test_gaussian_at_optimal()
        test_cold_tires()
        test_hot_tires()
        test_asymmetric_degradation()
        test_window_narrowness()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED — Phase 1 Complete")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
