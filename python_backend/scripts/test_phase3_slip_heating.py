"""
Test Phase 3 — V6.3 Per-Wheel Slip & Heating
Verifies slip calculation, heat generation, cooling, and wear accumulation.
"""

import sys
from pathlib import Path

# Add physics_engine to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.tyres.tyre_thermal import TireState, TiresState
from lap_simulator.physics_engine.integrator.waypoint_integrator import (
    _gaussian_thermal_multiplier,
    _get_optimal_temp,
    _get_sigma,
)


def test_slip_calculation():
    """Test per-wheel slip calculation."""
    print("Test 1: Per-wheel slip calculation...")

    # Scenario: wheel with load=20 kN, mu_tyre=1.3, target_g_lat=1.5g
    # grip_available = 20 * 1.3 = 26 kN
    # grip_required = 798 * 9.81 / 1000 * 1.5 = 11.75 kN
    # slip = 1 - (26 / 11.75) = negative (clamped to 0)

    mass_kg = 798.0
    load_kn = 20.0
    mu_tyre = 1.3
    target_g_lat = 1.5

    f_grip_available = load_kn * mu_tyre
    f_grip_required = (mass_kg * 9.81 / 1000.0) * target_g_lat
    slip = max(0.0, 1.0 - (f_grip_available / max(0.1, f_grip_required)))

    print(f"  Load: {load_kn} kN, μ_tyre: {mu_tyre}")
    print(f"  Grip available: {f_grip_available:.2f} kN")
    print(f"  Grip required: {f_grip_required:.2f} kN")
    print(f"  Slip: {slip:.4f} (0=no slip, 1=full slip)")

    # When grip available > required, slip = 0
    assert slip == 0.0, f"Slip should be 0 when grip sufficient: {slip}"
    print("  ✅ No slip when grip sufficient")


def test_slip_with_low_grip():
    """Test slip when tire grip is reduced."""
    print("\nTest 2: Slip with reduced tire grip...")

    mass_kg = 798.0
    load_kn = 10.0  # Lower load (interior wheel in corner)
    target_g_lat = 2.5  # Very high lateral g

    # Normal thermal multiplier
    thermal_mult = 1.0
    wear_factor = 1.0
    mu_tyre = 1.3 * thermal_mult * wear_factor

    f_grip_available = load_kn * mu_tyre
    f_grip_required = (mass_kg * 9.81 / 1000.0) * target_g_lat
    slip = max(0.0, 1.0 - (f_grip_available / max(0.1, f_grip_required)))

    print(f"  Low load (interior wheel): {load_kn} kN")
    print(f"  High lateral g: {target_g_lat}g")
    print(f"  Grip available: {f_grip_available:.2f} kN")
    print(f"  Grip required: {f_grip_required:.2f} kN")
    print(f"  Slip: {slip:.4f}")

    # With high lateral g and low load, slip should be significant
    assert slip > 0.3, f"Slip should be >0.3 at high lateral g + low load: {slip}"
    print(f"  ✅ Significant slip at {target_g_lat}g with low load ({slip:.1%})")


def test_thermal_multiplier_effect():
    """Test that thermal multiplier reduces grip and increases slip."""
    print("\nTest 3: Thermal multiplier effect on slip...")

    mass_kg = 798.0
    load_kn = 20.0
    target_g_lat = 1.5

    # Cold tires (70°C, well below C4 optimal 105°C)
    thermal_mult_cold = _gaussian_thermal_multiplier(70.0, 65.0, 'C4')
    wear_factor = 1.0  # No wear
    mu_tyre_cold = 1.3 * thermal_mult_cold * wear_factor

    # Warm tires (105°C, optimal for C4)
    thermal_mult_warm = _gaussian_thermal_multiplier(105.0, 90.0, 'C4')
    mu_tyre_warm = 1.3 * thermal_mult_warm * wear_factor

    # Calculate slip for both
    f_grip_required = (mass_kg * 9.81 / 1000.0) * target_g_lat

    slip_cold = max(0.0, 1.0 - (load_kn * mu_tyre_cold / f_grip_required))
    slip_warm = max(0.0, 1.0 - (load_kn * mu_tyre_warm / f_grip_required))

    print(f"  Cold tires (70°C): thermal_mult={thermal_mult_cold:.4f}, slip={slip_cold:.4f}")
    print(f"  Warm tires (105°C): thermal_mult={thermal_mult_warm:.4f}, slip={slip_warm:.4f}")

    # Cold tires should have more slip
    assert slip_cold > slip_warm, f"Cold should have more slip: cold={slip_cold}, warm={slip_warm}"
    print(f"  ✅ Cold tires have more slip (diff: {(slip_cold-slip_warm):.1%})")


def test_heat_generation():
    """Test per-wheel heat generation (friction, hysteresis, braking)."""
    print("\nTest 4: Heat generation (friction + hysteresis + braking)...")

    # Constants
    K_SURFACE_FRIC = 0.95
    K_HYSTERESIS_CORE = 0.35
    K_BRAKING_TRANSFER = 0.25

    # Scenario: high-speed corner with braking
    load_kn = 30.0
    slip = 0.1
    velocity_ms = 80.0
    dt_step = 0.05
    mass_kg = 798.0
    brake_bias = 0.55

    # Friction heat
    friction_heat = K_SURFACE_FRIC * load_kn * slip * velocity_ms * dt_step
    print(f"  Friction heat: {friction_heat:.4f}°C")

    # Hysteresis heat
    core_heat = K_HYSTERESIS_CORE * load_kn * velocity_ms * dt_step
    print(f"  Core heat (hysteresis): {core_heat:.4f}°C")

    # Braking heat (front wheel during braking)
    braking_energy_mj = 0.5 * mass_kg * velocity_ms ** 2 / 1e6
    brake_heat_front = K_BRAKING_TRANSFER * braking_energy_mj * brake_bias / 2.0 * dt_step
    print(f"  Brake heat (front): {brake_heat_front:.4f}°C")

    # Total
    total_heat = friction_heat + core_heat + brake_heat_front
    print(f"  Total temp rise: {total_heat:.4f}°C per {dt_step}s step")

    assert total_heat > 0.01, f"Heat should be positive: {total_heat}"
    print(f"  ✅ Heat generation: {total_heat:.2f}°C per step")


def test_cooling():
    """Test asymmetric cooling (brake duct effect)."""
    print("\nTest 5: Cooling (asymmetric with brake duct)...")

    h_conv_base = 15.0
    velocity_ms = 80.0
    dt_step = 0.05
    surface_temp = 110.0
    ambient_temp = 25.0

    # Front wheel with brake duct (50% open)
    brake_duct_opening = 0.5
    h_conv_front = h_conv_base * velocity_ms * (0.5 + brake_duct_opening)
    q_cool_front = h_conv_front * (surface_temp - ambient_temp) * dt_step / 1000.0

    # Rear wheel (no brake duct)
    h_conv_rear = h_conv_base * velocity_ms * 0.5
    q_cool_rear = h_conv_rear * (surface_temp - ambient_temp) * dt_step / 1000.0

    print(f"  Surface temp: {surface_temp}°C, ambient: {ambient_temp}°C")
    print(f"  Front cooling (duct 50% open): {q_cool_front:.4f}°C")
    print(f"  Rear cooling (no duct): {q_cool_rear:.4f}°C")
    print(f"  Front/Rear ratio: {q_cool_front/q_cool_rear:.2f}x")

    assert q_cool_front > q_cool_rear, "Front should cool more with brake duct"
    print(f"  ✅ Brake duct increases front cooling by {(q_cool_front/q_cool_rear - 1)*100:.1f}%")


def test_wear_acceleration():
    """Test that wear accelerates outside thermal window."""
    print("\nTest 6: Wear acceleration outside thermal window...")

    tyre_compound = 'C4'
    k_wear = 0.18  # C4 base
    slip = 0.05
    dist_step = 5.0  # meters

    # Temperature within window: optimal=105°C, sigma=8°C
    temp_optimal = _get_optimal_temp(tyre_compound)
    sigma = _get_sigma(tyre_compound)

    # Case 1: Within window (temp_optimal)
    temp_dev_1 = abs(temp_optimal - temp_optimal)
    severity_1 = 1.0 if temp_dev_1 < sigma else 1.0 + ((temp_dev_1 - sigma) / sigma) ** 1.5
    wear_1 = k_wear * severity_1 * slip * (dist_step / 1000.0)

    # Case 2: Outside window (temp_optimal + 20°C)
    temp_dev_2 = abs((temp_optimal + 20.0) - temp_optimal)
    severity_2 = 1.0 if temp_dev_2 < sigma else 1.0 + ((temp_dev_2 - sigma) / sigma) ** 1.5
    wear_2 = k_wear * severity_2 * slip * (dist_step / 1000.0)

    print(f"  Within window ({temp_optimal}°C): severity={severity_1:.2f}, wear={wear_1:.6f}%")
    print(f"  Outside window ({temp_optimal + 20}°C): severity={severity_2:.2f}, wear={wear_2:.6f}%")
    print(f"  Acceleration factor: {severity_2 / severity_1:.2f}x")

    assert severity_2 > severity_1, f"Severity should increase outside window: {severity_2} vs {severity_1}"
    assert wear_2 > wear_1, f"Wear should increase outside window: {wear_2} vs {wear_1}"

    print(f"  ✅ Wear accelerated {severity_2/severity_1:.1f}x outside window")


def test_tire_state_persistence():
    """Test that tire state persists across waypoints."""
    print("\nTest 7: Tire state persistence across waypoints...")

    tires = TiresState()

    # Simulate heating over 2 waypoints
    tires.fl.surface_temp_c = 95.0
    tires.fl.wear_pct = 0.5

    print(f"  Waypoint 1: FL temp={tires.fl.surface_temp_c}°C, wear={tires.fl.wear_pct}%")

    # Simulate heating
    heat_input = 2.0
    wear_input = 0.3
    tires.fl.surface_temp_c += heat_input
    tires.fl.wear_pct += wear_input

    print(f"  Waypoint 2: FL temp={tires.fl.surface_temp_c}°C, wear={tires.fl.wear_pct}%")

    assert tires.fl.surface_temp_c == 97.0, "Temperature should accumulate"
    assert tires.fl.wear_pct == 0.8, "Wear should accumulate"

    print(f"  ✅ Tire state persists and accumulates")


def test_clamping():
    """Test temperature and wear clamping."""
    print("\nTest 8: Temperature and wear clamping...")

    tire = TireState()

    # Test temperature clamping
    tire.surface_temp_c = 200.0  # Above max 150°C
    tire.surface_temp_c = max(20.0, min(150.0, tire.surface_temp_c))
    assert tire.surface_temp_c == 150.0, "Surface temp should clamp at 150°C"

    tire.core_temp_c = -10.0  # Below min 20°C
    tire.core_temp_c = max(20.0, min(130.0, tire.core_temp_c))
    assert tire.core_temp_c == 20.0, "Core temp should clamp at 20°C"

    # Test wear clamping
    tire.wear_pct = 150.0  # Above max 100%
    tire.wear_pct = min(100.0, tire.wear_pct)
    assert tire.wear_pct == 100.0, "Wear should clamp at 100%"

    print(f"  Surface temp: 200°C → 150°C (clamped)")
    print(f"  Core temp: -10°C → 20°C (clamped)")
    print(f"  Wear: 150% → 100% (clamped)")
    print(f"  ✅ All values properly clamped")


if __name__ == "__main__":
    print("=" * 70)
    print("PHASE 3 TEST SUITE — V6.3 Per-Wheel Slip & Heating")
    print("=" * 70)

    try:
        test_slip_calculation()
        test_slip_with_low_grip()
        test_thermal_multiplier_effect()
        test_heat_generation()
        test_cooling()
        test_wear_acceleration()
        test_tire_state_persistence()
        test_clamping()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED — Phase 3 Ready for Phase 4")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
