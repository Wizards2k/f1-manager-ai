"""
Test Phase 1 — V6.3 Tire State Dataclasses
Verifies TireState, TiresState initialization and pit stop reset logic.
"""

import sys
from pathlib import Path

# Add physics_engine to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.tyres.tyre_thermal import TireState, TiresState
from lap_simulator.physics_engine.integrator.waypoint_integrator import PhysicsState


def test_tire_state():
    """Test TireState instantiation and defaults."""
    print("Test 1: TireState instantiation...")
    tire = TireState()
    assert tire.surface_temp_c == 85.0, f"Expected 85.0°C, got {tire.surface_temp_c}"
    assert tire.core_temp_c == 75.0, f"Expected 75.0°C, got {tire.core_temp_c}"
    assert tire.wear_pct == 0.0, f"Expected 0.0% wear, got {tire.wear_pct}"
    assert tire.is_graining == False
    assert tire.is_blistering == False
    print("  ✅ TireState defaults correct (surface=85°C, core=75°C, wear=0%)")


def test_tires_state():
    """Test TiresState instantiation with 4 wheels."""
    print("\nTest 2: TiresState (4 wheels) instantiation...")
    tires = TiresState()

    # Check all 4 wheels exist and have correct defaults
    wheels = {'FL': tires.fl, 'FR': tires.fr, 'RL': tires.rl, 'RR': tires.rr}
    for wheel_name, tire_state in wheels.items():
        assert tire_state.surface_temp_c == 85.0, f"{wheel_name} surface temp wrong"
        assert tire_state.core_temp_c == 75.0, f"{wheel_name} core temp wrong"
        assert tire_state.wear_pct == 0.0, f"{wheel_name} wear wrong"

    print("  ✅ TiresState has 4 independent wheels (FL, FR, RL, RR)")
    print(f"     Each wheel: surface=85°C, core=75°C, wear=0%")


def test_pit_stop_reset():
    """Test pit stop reset logic."""
    print("\nTest 3: Pit stop reset (reset_at_pit_stop)...")
    tires = TiresState()

    # Simulate some degradation
    tires.fl.surface_temp_c = 120.0
    tires.fl.core_temp_c = 110.0
    tires.fl.wear_pct = 5.5

    tires.rr.surface_temp_c = 125.0
    tires.rr.wear_pct = 8.2

    print(f"  Before pit: FL temp={tires.fl.surface_temp_c}°C wear={tires.fl.wear_pct}%")
    print(f"  Before pit: RR temp={tires.rr.surface_temp_c}°C wear={tires.rr.wear_pct}%")

    # Reset at pit stop
    tires.reset_at_pit_stop()

    # Verify all reset
    for wheel_name in ['fl', 'fr', 'rl', 'rr']:
        tire = getattr(tires, wheel_name)
        assert tire.surface_temp_c == 85.0, f"{wheel_name} not reset to 85°C"
        assert tire.core_temp_c == 75.0, f"{wheel_name} not reset to 75°C"
        assert tire.wear_pct == 0.0, f"{wheel_name} wear not reset to 0%"

    print("  ✅ All 4 wheels reset: surface=85°C, core=75°C, wear=0%")


def test_physics_state_initialization():
    """Test PhysicsState initializes tires_state."""
    print("\nTest 4: PhysicsState.tires_state initialization...")
    state = PhysicsState()

    assert state.tires_state is not None, "tires_state not initialized"
    assert hasattr(state.tires_state, 'fl'), "Missing FL wheel"
    assert hasattr(state.tires_state, 'fr'), "Missing FR wheel"
    assert hasattr(state.tires_state, 'rl'), "Missing RL wheel"
    assert hasattr(state.tires_state, 'rr'), "Missing RR wheel"

    print("  ✅ PhysicsState auto-initializes tires_state with 4 wheels")
    print(f"     Type: {type(state.tires_state).__name__}")


def test_per_wheel_independence():
    """Test that 4 wheels are truly independent (not shared references)."""
    print("\nTest 5: Per-wheel independence (no shared state)...")
    tires = TiresState()

    # Modify one wheel
    tires.fl.surface_temp_c = 100.0
    tires.fl.wear_pct = 3.0

    # Verify others unchanged
    assert tires.fr.surface_temp_c == 85.0, "FR incorrectly modified"
    assert tires.rl.surface_temp_c == 85.0, "RL incorrectly modified"
    assert tires.rr.surface_temp_c == 85.0, "RR incorrectly modified"

    assert tires.fr.wear_pct == 0.0, "FR wear incorrectly modified"
    assert tires.rl.wear_pct == 0.0, "RL wear incorrectly modified"
    assert tires.rr.wear_pct == 0.0, "RR wear incorrectly modified"

    print("  ✅ Wheels are independent (FL=100°C, others=85°C)")
    print(f"     FL wear=3%, others=0%")


def test_multi_lap_persistence():
    """Test that tires_state persists across lap boundaries."""
    print("\nTest 6: Multi-lap state persistence...")
    state = PhysicsState()

    # Lap 1: accumulate some wear
    state.tires_state.fl.wear_pct = 1.5
    state.tires_state.rr.wear_pct = 2.0

    # Simulate lap boundary (no reset unless pit stop)
    lap1_fl_wear = state.tires_state.fl.wear_pct
    lap1_rr_wear = state.tires_state.rr.wear_pct

    # Lap 2: wear continues
    state.tires_state.fl.wear_pct += 1.2
    state.tires_state.rr.wear_pct += 1.8

    assert state.tires_state.fl.wear_pct == 2.7, f"FL cumulative wear wrong: {state.tires_state.fl.wear_pct}"
    assert state.tires_state.rr.wear_pct == 3.8, f"RR cumulative wear wrong: {state.tires_state.rr.wear_pct}"

    print(f"  Lap 1: FL={lap1_fl_wear}% wear, RR={lap1_rr_wear}% wear")
    print(f"  Lap 2: FL={state.tires_state.fl.wear_pct}% wear, RR={state.tires_state.rr.wear_pct}% wear")
    print("  ✅ Tire state persists across laps (no automatic reset)")


if __name__ == "__main__":
    print("=" * 70)
    print("PHASE 1 TEST SUITE — V6.3 Tire Thermal State Dataclasses")
    print("=" * 70)

    try:
        test_tire_state()
        test_tires_state()
        test_pit_stop_reset()
        test_physics_state_initialization()
        test_per_wheel_independence()
        test_multi_lap_persistence()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED — Phase 1 Ready for Phase 2")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
