"""
Test Phase 2 — V6.3 Per-Wheel Load Distribution
Verifies lateral and brake load transfer calculations.
"""

import sys
from pathlib import Path

# Add physics_engine to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.integrator.waypoint_integrator import calculate_per_wheel_loads


def test_straight_line():
    """Test load distribution on straight (no lateral transfer)."""
    print("Test 1: Straight line (no cornering)...")

    # Straight: velocity=100 m/s, radius=999999m, no brake
    loads = calculate_per_wheel_loads(
        velocity_ms=100.0,
        radius_m=999999.0,
        mass_kg=798.0,
        f_downforce=100000.0,  # 100 kN downforce
        v_target_ms=100.0,  # No braking
        dt_step=0.05,
    )

    # On straight: all wheels equal (symmetric)
    fl, fr, rl, rr = loads['FL'], loads['FR'], loads['RL'], loads['RR']

    # Static: 45% front, 55% rear
    # FL=FR should be roughly equal (45%/2 = 22.5% each)
    # RL=RR should be roughly equal (55%/2 = 27.5% each)

    print(f"  FL={fl:.2f} kN, FR={fr:.2f} kN (front)")
    print(f"  RL={rl:.2f} kN, RR={rr:.2f} kN (rear)")

    # Check symmetry
    assert abs(fl - fr) < 0.5, f"Front wheels not symmetric: FL={fl}, FR={fr}"
    assert abs(rl - rr) < 0.5, f"Rear wheels not symmetric: RL={rl}, RR={rr}"
    assert rl > fl, f"Rear should be heavier than front: RL={rl}, FL={fl}"

    print(f"  ✅ Straight: symmetrical distribution (front={fl+fr:.1f}kN, rear={rl+rr:.1f}kN)")


def test_high_speed_corner():
    """Test lateral load transfer in high-speed corner."""
    print("\nTest 2: High-speed corner (lateral load transfer)...")

    # Corner: velocity=100 m/s, radius=500m, no brake
    # This generates ~2.0g lateral acceleration
    loads = calculate_per_wheel_loads(
        velocity_ms=100.0,
        radius_m=500.0,
        mass_kg=798.0,
        f_downforce=100000.0,
        v_target_ms=100.0,  # No braking
        dt_step=0.05,
    )

    fl, fr, rl, rr = loads['FL'], loads['FR'], loads['RL'], loads['RR']
    print(f"  FL={fl:.2f} kN, FR={fr:.2f} kN (front)")
    print(f"  RL={rl:.2f} kN, RR={rr:.2f} kN (rear)")

    # In a right turn (positive g_lateral):
    # Exterior wheels (FL, RL) should have higher load
    # Interior wheels (FR, RR) should have lower load
    assert fl > fr, f"FL should be heavier than FR in corner: FL={fl}, FR={fr}"
    assert rl > rr, f"RL should be heavier than RR in corner: RL={rl}, RR={rr}"

    # Load transfer should be significant (~20-30% difference)
    fl_fr_diff = (fl - fr) / (fl + fr) * 100
    rl_rr_diff = (rl - rr) / (rl + rr) * 100

    print(f"  FL/FR asymmetry: {fl_fr_diff:.1f}%")
    print(f"  RL/RR asymmetry: {rl_rr_diff:.1f}%")
    print(f"  ✅ Lateral transfer: exterior wheels +{fl_fr_diff:.1f}% (FL/FR), +{rl_rr_diff:.1f}% (RL/RR)")


def test_braking():
    """Test brake load transfer during deceleration."""
    print("\nTest 3: Braking with deceleration...")

    # Braking: strong deceleration from 100 m/s to 50 m/s
    # dt_step = 0.5s → decel = 50/0.5 = 10 m/s²
    loads = calculate_per_wheel_loads(
        velocity_ms=100.0,
        radius_m=999999.0,  # Straight (no lateral)
        mass_kg=798.0,
        f_downforce=100000.0,
        v_target_ms=50.0,  # Heavy braking
        dt_step=0.5,
    )

    fl, fr, rl, rr = loads['FL'], loads['FR'], loads['RL'], loads['RR']
    print(f"  FL={fl:.2f} kN, FR={fr:.2f} kN (front)")
    print(f"  RL={rl:.2f} kN, RR={rr:.2f} kN (rear)")

    # During braking:
    # Front wheels should be loaded more (brake load transfer)
    # Rear wheels should be loaded less
    total_front = fl + fr
    total_rear = rl + rr

    assert total_front > total_rear, f"Front should be heavier during braking: front={total_front}, rear={total_rear}"

    front_rear_ratio = total_front / max(total_rear, 1.0)
    print(f"  Front/Rear ratio during braking: {front_rear_ratio:.2f}")
    print(f"  ✅ Brake transfer: front +{(front_rear_ratio-1)*100:.1f}% vs rear")


def test_combined_corner_and_braking():
    """Test combined lateral + brake load transfer."""
    print("\nTest 4: Combined corner + braking...")

    # Hard braking into corner
    loads = calculate_per_wheel_loads(
        velocity_ms=80.0,
        radius_m=300.0,  # Tight corner
        mass_kg=798.0,
        f_downforce=120000.0,
        v_target_ms=50.0,  # Heavy braking
        dt_step=0.3,
    )

    fl, fr, rl, rr = loads['FL'], loads['FR'], loads['RL'], loads['RR']
    print(f"  FL={fl:.2f} kN, FR={fr:.2f} kN (front)")
    print(f"  RL={rl:.2f} kN, RR={rr:.2f} kN (rear)")

    # Expected: FL should be HIGHEST (exterior + brake transfer)
    # RR should be LOWEST (interior - brake transfer)
    assert fl == max(fl, fr, rl, rr), f"FL should be highest: FL={fl}, max={max(fl, fr, rl, rr)}"
    assert rr == min(fl, fr, rl, rr), f"RR should be lowest: RR={rr}, min={min(fl, fr, rl, rr)}"

    print(f"  FL (max): {fl:.2f} kN, RR (min): {rr:.2f} kN")
    print(f"  Asymmetry: {(fl-rr)/fl*100:.1f}%")
    print(f"  ✅ Combined: FL max, RR min (realistic extreme load distribution)")


def test_load_clamping():
    """Test that loads don't go negative (wheel liftoff clamp)."""
    print("\nTest 5: Load clamping (no negative loads)...")

    # Extreme: high-g lateral with low mass (simulating potential liftoff)
    loads = calculate_per_wheel_loads(
        velocity_ms=150.0,
        radius_m=200.0,  # Very tight
        mass_kg=500.0,   # Light (unrealistic but tests clamping)
        f_downforce=50000.0,
        v_target_ms=150.0,
        dt_step=0.05,
    )

    fl, fr, rl, rr = loads['FL'], loads['FR'], loads['RL'], loads['RR']

    # All loads must be > 0 (clamped to 0.1 kN minimum)
    assert all(load >= 0.1 for load in [fl, fr, rl, rr]), \
        f"Some loads are below minimum: FL={fl}, FR={fr}, RL={rl}, RR={rr}"

    print(f"  FL={fl:.2f} kN, FR={fr:.2f} kN, RL={rl:.2f} kN, RR={rr:.2f} kN")
    print(f"  ✅ All loads ≥ 0.1 kN (clamping works)")


if __name__ == "__main__":
    print("=" * 70)
    print("PHASE 2 TEST SUITE — V6.3 Per-Wheel Load Distribution")
    print("=" * 70)

    try:
        test_straight_line()
        test_high_speed_corner()
        test_braking()
        test_combined_corner_and_braking()
        test_load_clamping()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED — Phase 2 Ready for Phase 3")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
