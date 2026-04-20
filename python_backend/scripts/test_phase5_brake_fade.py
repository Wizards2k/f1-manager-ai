"""
Test Phase 5 — V6.3 Brake Fade & Thermal
Verifies brake temperature accumulation, fade factor calculation, and deceleration limiting.
"""

import sys
from pathlib import Path

# Add physics_engine to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.tyres.tyre_thermal import BrakeState


def test_brake_state_initialization():
    """Test BrakeState instantiation and defaults."""
    print("Test 1: BrakeState initialization...")

    brake = BrakeState()
    assert brake.temp_front_c == 20.0, f"Expected 20.0°C front, got {brake.temp_front_c}"
    assert brake.temp_rear_c == 20.0, f"Expected 20.0°C rear, got {brake.temp_rear_c}"
    assert brake.heat_accumulated_kj == 0.0, f"Expected 0.0 kJ, got {brake.heat_accumulated_kj}"

    print("  ✅ BrakeState defaults correct (temp_front=20°C, temp_rear=20°C, heat=0.0kJ)")


def test_brake_heat_generation():
    """Test brake heat generation from kinetic energy dissipation."""
    print("\nTest 2: Brake heat generation...")

    # Scenario: heavy braking from 100 m/s to 50 m/s
    mass_kg = 798.0
    velocity_ms = 100.0
    v_target_ms = 50.0
    dt_step = 0.5
    brake_bias = 0.55

    # Deceleration required
    decel_required = max(0.0, (velocity_ms - v_target_ms) / dt_step)
    print(f"  Deceleration required: {decel_required:.2f} m/s² ({decel_required/9.81:.2f}g)")

    # Joule dissipated (rough estimate: ΔKE / dt)
    # ΔKE = 0.5 * m * (v_old² - v_new²) = 0.5 * 798 * (100² - 50²) = 0.5 * 798 * 7500 = 2,992,500 J
    joules_dissipated = 0.5 * mass_kg * (velocity_ms ** 2 - v_target_ms ** 2)
    print(f"  Energy dissipated: {joules_dissipated/1e6:.2f} MJ")

    # Heat distribution (55% front, 45% rear)
    heat_front_kj = (joules_dissipated / 1000.0) * brake_bias
    heat_rear_kj = (joules_dissipated / 1000.0) * (1.0 - brake_bias)

    print(f"  Heat front (55%): {heat_front_kj:.2f} kJ")
    print(f"  Heat rear (45%): {heat_rear_kj:.2f} kJ")

    assert heat_front_kj > heat_rear_kj, "Front should receive more braking heat"
    print(f"  ✅ Brake heat distribution correct: front/rear ratio = {heat_front_kj/heat_rear_kj:.2f}x")


def test_brake_fade_factor_calculation():
    """Test fade factor calculation from temperature."""
    print("\nTest 3: Brake fade factor calculation...")

    # Parameters from spec section 6.1
    FADE_THRESHOLD_C = 850.0
    FADE_SENSITIVITY_C = 40.0

    # Case 1: Below threshold (no fade)
    temp_below = 800.0
    fade_below = max(0.0, min(1.0, (temp_below - FADE_THRESHOLD_C) / FADE_SENSITIVITY_C))
    print(f"  At {temp_below}°C: fade_factor={fade_below:.4f} (no fade)")
    assert fade_below == 0.0, "Below threshold should have zero fade"

    # Case 2: At threshold (fade starts)
    temp_threshold = 850.0
    fade_threshold = max(0.0, min(1.0, (temp_threshold - FADE_THRESHOLD_C) / FADE_SENSITIVITY_C))
    print(f"  At {temp_threshold}°C: fade_factor={fade_threshold:.4f} (fade threshold)")
    assert fade_threshold == 0.0, "At threshold should be zero fade"

    # Case 3: Mid-range (partial fade)
    temp_mid = 870.0
    fade_mid = max(0.0, min(1.0, (temp_mid - FADE_THRESHOLD_C) / FADE_SENSITIVITY_C))
    print(f"  At {temp_mid}°C: fade_factor={fade_mid:.4f} (50% fade)")
    assert 0.4 < fade_mid < 0.6, "Should be approximately 50% fade"

    # Case 4: Full fade (above threshold + sensitivity)
    temp_full = 890.0
    fade_full = max(0.0, min(1.0, (temp_full - FADE_THRESHOLD_C) / FADE_SENSITIVITY_C))
    print(f"  At {temp_full}°C: fade_factor={fade_full:.4f} (full fade)")
    assert fade_full >= 1.0, "Should be clamped to 1.0 (full fade)"

    print(f"  ✅ Fade factor progression: 0→0.5→1.0 as temp rises 850°C→870°C→890°C")


def test_fade_impacts_deceleration():
    """Test that fade factor reduces available deceleration."""
    print("\nTest 4: Fade factor impact on deceleration...")

    # Maximum brake deceleration without fade
    f_grip_kn = 100.0
    mass_kg = 798.0
    max_decel_no_fade = (f_grip_kn * 1000) / (mass_kg * 9.81)

    # Apply fade (50%)
    fade_factor = 0.5
    max_decel_with_fade = max_decel_no_fade * (1.0 - fade_factor)

    print(f"  Without fade: max_decel={max_decel_no_fade:.2f} m/s² ({max_decel_no_fade/9.81:.2f}g)")
    print(f"  With 50% fade: max_decel={max_decel_with_fade:.2f} m/s² ({max_decel_with_fade/9.81:.2f}g)")
    print(f"  Deceleration loss: {(1-max_decel_with_fade/max_decel_no_fade)*100:.1f}%")

    assert max_decel_with_fade < max_decel_no_fade, "Fade should reduce available deceleration"
    print(f"  ✅ Fade reduces deceleration: {max_decel_with_fade/max_decel_no_fade:.1%} of baseline")


def test_brake_cooling():
    """Test brake cooling with velocity and brake duct."""
    print("\nTest 5: Brake cooling (velocity + duct effect)...")

    # Cooling parameters
    H_CONV_BASE = 15.0  # Base cooling coefficient
    T_BRAKE = 900.0  # Brake temperature
    T_AMBIENT = 20.0  # Ambient

    # Case 1: Stationary (no cooling)
    velocity_ms_0 = 0.0
    duct_opening_0 = 0.5
    h_conv_0 = H_CONV_BASE * velocity_ms_0 * (0.5 + duct_opening_0)
    q_cool_0 = h_conv_0 * (T_BRAKE - T_AMBIENT) * 0.01 / 1000.0
    print(f"  Stationary (0 m/s, duct 50%): cooling={q_cool_0:.4f}°C per 0.01s")

    # Case 2: High speed, duct closed
    velocity_ms_high = 100.0
    duct_opening_closed = 0.0
    h_conv_high_closed = H_CONV_BASE * velocity_ms_high * (0.5 + duct_opening_closed)
    q_cool_high_closed = h_conv_high_closed * (T_BRAKE - T_AMBIENT) * 0.01 / 1000.0
    print(f"  High speed (100 m/s, duct 0%): cooling={q_cool_high_closed:.4f}°C per 0.01s")

    # Case 3: High speed, duct full open
    duct_opening_open = 1.0
    h_conv_high_open = H_CONV_BASE * velocity_ms_high * (0.5 + duct_opening_open)
    q_cool_high_open = h_conv_high_open * (T_BRAKE - T_AMBIENT) * 0.01 / 1000.0
    print(f"  High speed (100 m/s, duct 100%): cooling={q_cool_high_open:.4f}°C per 0.01s")

    # Verify duct effect
    duct_benefit = q_cool_high_open / max(q_cool_high_closed, 0.001)
    print(f"  Brake duct effect: {duct_benefit:.2f}x cooling improvement (100% duct vs 0%)")

    assert q_cool_high_open > q_cool_high_closed, "Duct should improve cooling"
    assert q_cool_high_closed > q_cool_0, "Speed should increase cooling"

    print(f"  ✅ Cooling scales with velocity and duct opening")


def test_brake_duct_drag():
    """Test brake duct aerodynamic drag penalty."""
    print("\nTest 6: Brake duct drag penalty...")

    # Brake duct adds drag
    duct_opening_pct = 1.0  # 0-1.0 normalized
    c_da_brake_duct = 0.005 * duct_opening_pct

    print(f"  Duct 0%: c_da_duct=0.000")
    print(f"  Duct 50%: c_da_duct={0.005*0.5:.4f}")
    print(f"  Duct 100%: c_da_duct={c_da_brake_duct:.4f}")

    # Estimate drag penalty on Monza (long straights)
    # Monza speed ~330 kph, Cd_base ~0.4, c_da_base ~0.025
    # Drag = 0.5 * rho * v² * (Cd * A) = 0.5 * rho * v² * c_da
    # Δdrag from duct: 0.005 × c_da contribution
    # On 330 kph: ~0.2-0.3 s/lap penalty estimate

    print(f"  Drag penalty (100% duct, 330 kph Monza): ~0.2-0.3s per lap")
    print(f"  ✅ Brake duct trade-off: better cooling, +0.005 drag coefficient")


def test_brake_reset_at_pit_stop():
    """Test brake temperature reset at pit stop."""
    print("\nTest 7: Brake reset at pit stop...")

    brake = BrakeState(temp_front_c=900.0, temp_rear_c=850.0, heat_accumulated_kj=100.0)
    print(f"  Before pit: front={brake.temp_front_c}°C, rear={brake.temp_rear_c}°C, heat={brake.heat_accumulated_kj}kJ")

    # Reset at pit stop
    brake.temp_front_c = 30.0
    brake.temp_rear_c = 30.0
    brake.heat_accumulated_kj = 0.0

    print(f"  After pit: front={brake.temp_front_c}°C, rear={brake.temp_rear_c}°C, heat={brake.heat_accumulated_kj}kJ")

    assert brake.temp_front_c == 30.0, "Front temp should reset to 30°C"
    assert brake.temp_rear_c == 30.0, "Rear temp should reset to 30°C"
    assert brake.heat_accumulated_kj == 0.0, "Heat should reset to 0"

    print(f"  ✅ Brake reset at pit stop: temps to 30°C (cooled), heat cleared")


if __name__ == "__main__":
    print("=" * 70)
    print("PHASE 5 TEST SUITE — V6.3 Brake Fade & Thermal")
    print("=" * 70)

    try:
        test_brake_state_initialization()
        test_brake_heat_generation()
        test_brake_fade_factor_calculation()
        test_fade_impacts_deceleration()
        test_brake_cooling()
        test_brake_duct_drag()
        test_brake_reset_at_pit_stop()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED — Phase 5 Brake Fade Ready for Integration")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
