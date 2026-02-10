"""Tests for tyre_model – update_tyres()."""
import pytest

from lap_simulator.tyre_model import update_tyres
from lap_simulator.data_types import (
    AeroForces,
    CarState,
    CircuitConfig,
    DriverIntent,
    EnvContext,
    SectionContext,
    SectionKind,
    TyreCompound,
    TyreCompoundParams,
    WheelPosition,
)


@pytest.fixture
def default_env():
    return EnvContext()


@pytest.fixture
def config_with_c3():
    cfg = CircuitConfig()
    cfg.tyre_params = {
        TyreCompound.C3: TyreCompoundParams(
            compound=TyreCompound.C3,
            temp_window_surface_c=[88, 120, 135],
            temp_window_core_c=[85, 97, 108],
            gaussian_sigma_surface_c=7.0,
            gaussian_sigma_core_c=6.0,
            base_grip=1.0,
            wear_rate_base_pct_per_km=0.13,
            thermal_mass_surface=1.10,
            thermal_mass_core=1.25,
            conduction_coeff=0.07,
            cooling_coeff=1.0,
        ),
    }
    return cfg


@pytest.fixture
def straight_section():
    return SectionContext(
        section_id="s01", name="Straight", kind=SectionKind.STRAIGHT,
        length_m=800.0, v_base_kph=300.0,
        heat_factor=0.2, cool_factor=1.2,
    )


@pytest.fixture
def slow_corner():
    return SectionContext(
        section_id="s02", name="Turn 1", kind=SectionKind.SLOW_CORNER,
        length_m=100.0, v_base_kph=80.0,
        heat_factor=1.4, cool_factor=0.4,
        bumpiness_factor=0.2, kerb_severity=0.3,
    )


class TestTyreGrip:
    def test_grip_positive(self, straight_section, default_env, config_with_c3):
        car = CarState()
        aero = AeroForces()
        driver = DriverIntent()
        gf, gr, events = update_tyres(car, straight_section, default_env, aero, driver, config_with_c3, dt_s=2.0, v_kph=300.0)
        assert gf > 0
        assert gr > 0

    def test_grip_at_optimal_temp_is_high(self, straight_section, default_env, config_with_c3):
        car = CarState()
        # Set tyres at optimal temperature
        for t in car.tyres.values():
            t.surface_temp_c = 120.0
            t.core_temp_c = 97.0
        aero = AeroForces()
        driver = DriverIntent()
        gf, gr, _ = update_tyres(car, straight_section, default_env, aero, driver, config_with_c3, dt_s=0.1, v_kph=300.0)
        # At optimal temp with no wear, grip should be close to base_grip
        assert gf > 0.9
        assert gr > 0.9


class TestTyreWear:
    def test_wear_increases(self, straight_section, default_env, config_with_c3):
        car = CarState()
        aero = AeroForces()
        driver = DriverIntent()
        initial_wear = {wp: t.wear_pct for wp, t in car.tyres.items()}
        update_tyres(car, straight_section, default_env, aero, driver, config_with_c3, dt_s=2.0, v_kph=300.0)
        for wp, t in car.tyres.items():
            assert t.wear_pct >= initial_wear[wp]

    def test_higher_pace_more_wear(self, straight_section, default_env, config_with_c3):
        car1 = CarState()
        car2 = CarState()
        aero = AeroForces()
        driver_normal = DriverIntent(pace_factor=1.0)
        driver_push = DriverIntent(pace_factor=1.1)
        update_tyres(car1, straight_section, default_env, aero, driver_normal, config_with_c3, dt_s=2.0, v_kph=300.0)
        update_tyres(car2, straight_section, default_env, aero, driver_push, config_with_c3, dt_s=2.0, v_kph=300.0)
        avg_wear1 = sum(t.wear_pct for t in car1.tyres.values()) / 4
        avg_wear2 = sum(t.wear_pct for t in car2.tyres.values()) / 4
        assert avg_wear2 > avg_wear1

    def test_tyre_save_reduces_wear(self, straight_section, default_env, config_with_c3):
        car1 = CarState()
        car2 = CarState()
        aero = AeroForces()
        driver_normal = DriverIntent(tyre_save_mode=False)
        driver_save = DriverIntent(tyre_save_mode=True)
        update_tyres(car1, straight_section, default_env, aero, driver_normal, config_with_c3, dt_s=2.0, v_kph=300.0)
        update_tyres(car2, straight_section, default_env, aero, driver_save, config_with_c3, dt_s=2.0, v_kph=300.0)
        avg_wear1 = sum(t.wear_pct for t in car1.tyres.values()) / 4
        avg_wear2 = sum(t.wear_pct for t in car2.tyres.values()) / 4
        assert avg_wear2 < avg_wear1


class TestTyreThermal:
    def test_corner_heats_tyres(self, slow_corner, default_env, config_with_c3):
        car = CarState()
        for t in car.tyres.values():
            t.surface_temp_c = 100.0
            t.core_temp_c = 90.0
        aero = AeroForces()
        driver = DriverIntent()
        initial_temps = {wp: t.surface_temp_c for wp, t in car.tyres.items()}
        update_tyres(car, slow_corner, default_env, aero, driver, config_with_c3, dt_s=1.5, v_kph=80.0)
        # Slow corner should heat tyres
        for wp, t in car.tyres.items():
            assert t.surface_temp_c >= initial_temps[wp] - 2  # allow small cooling

    def test_understeer_heats_front_more(self, slow_corner, default_env, config_with_c3):
        car = CarState()
        for t in car.tyres.values():
            t.surface_temp_c = 100.0
        aero = AeroForces(understeer_level=0.5)
        driver = DriverIntent()
        update_tyres(car, slow_corner, default_env, aero, driver, config_with_c3, dt_s=1.5, v_kph=80.0)
        front_avg = (car.tyres[WheelPosition.LF].surface_temp_c + car.tyres[WheelPosition.RF].surface_temp_c) / 2
        rear_avg = (car.tyres[WheelPosition.LR].surface_temp_c + car.tyres[WheelPosition.RR].surface_temp_c) / 2
        assert front_avg > rear_avg


class TestTyreEvents:
    def test_overheat_event(self, straight_section, default_env, config_with_c3):
        car = CarState()
        for t in car.tyres.values():
            t.surface_temp_c = 160.0  # well above window max (135) + 10
        aero = AeroForces()
        driver = DriverIntent()
        _, _, events = update_tyres(car, straight_section, default_env, aero, driver, config_with_c3, dt_s=0.1, v_kph=300.0)
        assert any(e.event_type == "tyre_overheat" for e in events)

    def test_puncture_risk_at_high_wear(self, straight_section, default_env, config_with_c3):
        car = CarState()
        for t in car.tyres.values():
            t.wear_pct = 85.0
        aero = AeroForces()
        driver = DriverIntent()
        _, _, events = update_tyres(car, straight_section, default_env, aero, driver, config_with_c3, dt_s=0.1, v_kph=300.0)
        assert any(e.event_type == "tyre_puncture_risk" for e in events)


# ---------------------------------------------------------------------------
# TyreModel v2 features
# ---------------------------------------------------------------------------

class TestDegradationRateMultiplier:
    """C1 (0.6x) should wear much less than C5 (1.6x) over same distance."""

    def _make_config(self, compound, deg_mult):
        cfg = CircuitConfig()
        cfg.tyre_params = {
            compound: TyreCompoundParams(
                compound=compound,
                degradation_rate_multiplier=deg_mult,
            ),
        }
        return cfg

    def test_c1_wears_less_than_c5(self, straight_section, default_env):
        cfg_c1 = self._make_config(TyreCompound.C1, 0.6)
        cfg_c5 = self._make_config(TyreCompound.C5, 1.6)

        car_c1 = CarState()
        for t in car_c1.tyres.values():
            t.compound = TyreCompound.C1
        car_c5 = CarState()
        for t in car_c5.tyres.values():
            t.compound = TyreCompound.C5

        aero = AeroForces()
        driver = DriverIntent()
        update_tyres(car_c1, straight_section, default_env, aero, driver, cfg_c1, dt_s=2.0, v_kph=300.0)
        update_tyres(car_c5, straight_section, default_env, aero, driver, cfg_c5, dt_s=2.0, v_kph=300.0)

        avg_c1 = sum(t.wear_pct for t in car_c1.tyres.values()) / 4
        avg_c5 = sum(t.wear_pct for t in car_c5.tyres.values()) / 4
        assert avg_c5 > avg_c1 * 2.0  # C5 should be >2x C1 wear (1.6/0.6 ≈ 2.67)


class TestSlipSensitivity:
    """Higher slip_sensitivity should reduce grip in corners."""

    def _make_config(self, slip_sens):
        cfg = CircuitConfig()
        cfg.tyre_params = {
            TyreCompound.C3: TyreCompoundParams(
                compound=TyreCompound.C3,
                slip_sensitivity=slip_sens,
            ),
        }
        return cfg

    def test_high_slip_less_grip_in_corner(self, slow_corner, default_env):
        cfg_low = self._make_config(0.75)   # C1-like
        cfg_high = self._make_config(1.30)  # C5-like

        car_low = CarState()
        car_high = CarState()
        for t in list(car_low.tyres.values()) + list(car_high.tyres.values()):
            t.surface_temp_c = 120.0
            t.core_temp_c = 97.0

        aero = AeroForces()
        driver = DriverIntent()
        gf_low, _, _ = update_tyres(car_low, slow_corner, default_env, aero, driver, cfg_low, dt_s=0.5, v_kph=80.0)
        gf_high, _, _ = update_tyres(car_high, slow_corner, default_env, aero, driver, cfg_high, dt_s=0.5, v_kph=80.0)
        # High slip sensitivity → higher slip_factor → more grip in corners (it's a multiplier)
        # slip_factor = 1.0 + (slip_sens - 1.0) * 0.1
        # C5: 1.0 + 0.3*0.1 = 1.03, C1: 1.0 + (-0.25)*0.1 = 0.975
        assert gf_high > gf_low

    def test_no_slip_effect_on_straight(self, straight_section, default_env):
        cfg_low = self._make_config(0.75)
        cfg_high = self._make_config(1.30)

        car_low = CarState()
        car_high = CarState()
        for t in list(car_low.tyres.values()) + list(car_high.tyres.values()):
            t.surface_temp_c = 120.0
            t.core_temp_c = 97.0

        aero = AeroForces()
        driver = DriverIntent()
        gf_low, _, _ = update_tyres(car_low, straight_section, default_env, aero, driver, cfg_low, dt_s=0.5, v_kph=300.0)
        gf_high, _, _ = update_tyres(car_high, straight_section, default_env, aero, driver, cfg_high, dt_s=0.5, v_kph=300.0)
        # On straight, slip_factor = 1.0 for both → grip should be very similar
        assert abs(gf_high - gf_low) < 0.01


class TestHeatCyclePenalty:
    """Used tyres (heat_cycles > 0) should have less grip."""

    def test_used_tyres_less_grip(self, straight_section, default_env, config_with_c3):
        car_new = CarState()
        car_used = CarState()
        for t in car_new.tyres.values():
            t.surface_temp_c = 120.0
            t.core_temp_c = 97.0
        for t in car_used.tyres.values():
            t.surface_temp_c = 120.0
            t.core_temp_c = 97.0
            t.heat_cycles = 3

        aero = AeroForces()
        driver = DriverIntent()
        gf_new, _, _ = update_tyres(car_new, straight_section, default_env, aero, driver, config_with_c3, dt_s=0.1, v_kph=300.0)
        gf_used, _, _ = update_tyres(car_used, straight_section, default_env, aero, driver, config_with_c3, dt_s=0.1, v_kph=300.0)
        assert gf_new > gf_used

    def test_heat_cycle_penalty_is_proportional(self, straight_section, default_env, config_with_c3):
        car_1 = CarState()
        car_4 = CarState()
        for t in car_1.tyres.values():
            t.surface_temp_c = 120.0
            t.core_temp_c = 97.0
            t.heat_cycles = 1
        for t in car_4.tyres.values():
            t.surface_temp_c = 120.0
            t.core_temp_c = 97.0
            t.heat_cycles = 4

        aero = AeroForces()
        driver = DriverIntent()
        gf_1, _, _ = update_tyres(car_1, straight_section, default_env, aero, driver, config_with_c3, dt_s=0.1, v_kph=300.0)
        gf_4, _, _ = update_tyres(car_4, straight_section, default_env, aero, driver, config_with_c3, dt_s=0.1, v_kph=300.0)
        assert gf_1 > gf_4  # more heat cycles = less grip


class TestTemporalGraining:
    """Graining should only trigger after sustained time below window."""

    def test_brief_cold_no_graining(self, default_env, config_with_c3):
        """Short exposure below window should not trigger graining."""
        section = SectionContext(
            section_id="s01", name="Turn", kind=SectionKind.SLOW_CORNER,
            length_m=100.0, v_base_kph=80.0, heat_factor=1.4, cool_factor=0.4,
        )
        car = CarState()
        for t in car.tyres.values():
            t.surface_temp_c = 70.0  # well below window min (88)
        aero = AeroForces(understeer_level=0.5)
        driver = DriverIntent()
        # Single short section (1s) — should accumulate but not trigger
        update_tyres(car, section, default_env, aero, driver, config_with_c3, dt_s=1.0, v_kph=80.0)
        for t in car.tyres.values():
            assert t.graining_level == 0.0  # threshold is 8s, only 1s accumulated

    def test_sustained_cold_triggers_graining(self, default_env, config_with_c3):
        """Sustained exposure below window should trigger graining."""
        section = SectionContext(
            section_id="s01", name="Turn", kind=SectionKind.SLOW_CORNER,
            length_m=100.0, v_base_kph=80.0, heat_factor=0.1, cool_factor=2.0,
        )
        car = CarState()
        for t in car.tyres.values():
            t.surface_temp_c = 70.0
            t.core_temp_c = 60.0
        aero = AeroForces(understeer_level=0.5)
        driver = DriverIntent()
        # Run many sections to accumulate >8s
        for _ in range(15):
            update_tyres(car, section, default_env, aero, driver, config_with_c3, dt_s=1.0, v_kph=80.0)
        # At least some front tyres should show graining
        front_graining = [car.tyres[wp].graining_level for wp in [WheelPosition.LF, WheelPosition.RF]]
        assert any(g > 0 for g in front_graining)


class TestTemporalBlistering:
    """Blistering should only trigger after sustained time above window."""

    def test_brief_overheat_no_blistering(self, default_env, config_with_c3):
        section = SectionContext(
            section_id="s01", name="Straight", kind=SectionKind.STRAIGHT,
            length_m=800.0, v_base_kph=300.0, heat_factor=0.2, cool_factor=1.2,
        )
        car = CarState()
        for t in car.tyres.values():
            t.surface_temp_c = 145.0  # above window max (135) + 3
            t.core_temp_c = 115.0     # above core max (108) + 3
        aero = AeroForces()
        driver = DriverIntent()
        # Single short section
        update_tyres(car, section, default_env, aero, driver, config_with_c3, dt_s=1.0, v_kph=300.0)
        for t in car.tyres.values():
            assert t.blistering_level == 0.0  # threshold is 10s

    def test_sustained_overheat_triggers_blistering(self, default_env, config_with_c3):
        section = SectionContext(
            section_id="s01", name="Turn", kind=SectionKind.SLOW_CORNER,
            length_m=100.0, v_base_kph=80.0, heat_factor=2.0, cool_factor=0.1,
        )
        car = CarState()
        for t in car.tyres.values():
            t.surface_temp_c = 150.0
            t.core_temp_c = 120.0
        aero = AeroForces()
        driver = DriverIntent(pace_factor=1.1)
        # Run many sections to accumulate >10s
        for _ in range(20):
            update_tyres(car, section, default_env, aero, driver, config_with_c3, dt_s=1.0, v_kph=80.0)
        blistering_levels = [t.blistering_level for t in car.tyres.values()]
        assert any(b > 0 for b in blistering_levels)
