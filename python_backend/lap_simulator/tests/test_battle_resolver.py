"""
Tests for BattleResolver 2.0 – proximity detection, dirty air, battle resolution.
"""
import pytest
import random

from lap_simulator.battle_resolver import (
    BattleOutcome,
    BattlePair,
    BattleResolver,
    DIRTY_AIR_MAX_PENALTY,
    DIRTY_AIR_DECAY_M,
    ScenarioTag,
    compute_attack_chance,
    compute_dirty_air,
    detect_proximity_pairs,
    emit_battle_event,
    resolve_pair,
    tag_scenario,
)
from lap_simulator.data_types import (
    CarState,
    DriverSkills,
    SectionContext,
    SectionKind,
    SectionResult,
)
from lap_simulator.lap_simulator import CarEntry
from lap_simulator.data_types import AeroSetup


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def straight_section():
    return SectionContext(
        section_id="s01", name="Main Straight", kind=SectionKind.STRAIGHT,
        length_m=800.0, v_base_kph=300.0,
        heat_factor=0.2, cool_factor=1.2,
        braking_energy_mj=0.0,
    )


@pytest.fixture
def braking_section():
    return SectionContext(
        section_id="s02", name="T1 Braking", kind=SectionKind.SLOW_CORNER,
        length_m=100.0, v_base_kph=80.0,
        heat_factor=1.4, cool_factor=0.4,
        braking_energy_mj=1.2,
    )


@pytest.fixture
def corner_section():
    return SectionContext(
        section_id="s03", name="Turn 3", kind=SectionKind.MEDIUM_CORNER,
        length_m=150.0, v_base_kph=120.0,
        heat_factor=1.0, cool_factor=0.6,
        braking_energy_mj=0.1,
    )


def _make_entry(car_id, overtaking=70, defending=70, aggression=50):
    return CarEntry(
        car_id=car_id,
        state=CarState(car_id=car_id),
        aero_setup=AeroSetup(),
        driver_skills=DriverSkills(
            overtaking_skill=overtaking,
            defending_skill=defending,
            aggression=aggression,
        ),
    )


def _make_result(v_eff=300.0, grip_f=0.95, grip_r=0.95, ow=0.5, late_brake=False):
    return SectionResult(
        v_effective_kph=v_eff,
        effective_grip_front=grip_f,
        effective_grip_rear=grip_r,
        overtake_window=ow,
        late_brake_tag=late_brake,
    )


# ---------------------------------------------------------------------------
# Scenario tagging
# ---------------------------------------------------------------------------

class TestScenarioTag:
    def test_straight(self, straight_section):
        assert tag_scenario(straight_section) == ScenarioTag.STRAIGHT

    def test_heavy_braking(self, braking_section):
        assert tag_scenario(braking_section) == ScenarioTag.HEAVY_BRAKING

    def test_corner(self, corner_section):
        assert tag_scenario(corner_section) == ScenarioTag.CORNER

    def test_start_override(self, straight_section):
        assert tag_scenario(straight_section, is_start=True) == ScenarioTag.START_RESTART

    def test_blue_flag_override(self, straight_section):
        assert tag_scenario(straight_section, is_blue_flag=True) == ScenarioTag.BLUE_FLAG


# ---------------------------------------------------------------------------
# Dirty air
# ---------------------------------------------------------------------------

class TestDirtyAir:
    def test_close_behind_has_penalty(self, straight_section):
        penalty = compute_dirty_air(5.0, straight_section)
        assert penalty > 0

    def test_far_away_no_penalty(self, straight_section):
        penalty = compute_dirty_air(100.0, straight_section)
        assert penalty == 0.0

    def test_penalty_decays_with_distance(self, straight_section):
        close = compute_dirty_air(5.0, straight_section)
        mid = compute_dirty_air(20.0, straight_section)
        far = compute_dirty_air(35.0, straight_section)
        assert close > mid > far

    def test_corner_worse_than_straight(self, corner_section, straight_section):
        corner_penalty = compute_dirty_air(10.0, corner_section)
        straight_penalty = compute_dirty_air(10.0, straight_section)
        assert corner_penalty > straight_penalty

    def test_max_penalty_capped(self, corner_section):
        penalty = compute_dirty_air(1.0, corner_section)
        assert penalty <= DIRTY_AIR_MAX_PENALTY


# ---------------------------------------------------------------------------
# Proximity detection
# ---------------------------------------------------------------------------

class TestProximityDetection:
    def test_close_cars_detected(self, straight_section):
        cars = [
            ("car_a", 0.0, 310.0),   # leader
            ("car_b", 15.0, 315.0),   # 15m behind, faster
        ]
        pairs = detect_proximity_pairs(cars, straight_section, ScenarioTag.STRAIGHT)
        assert len(pairs) == 1
        assert pairs[0].attacker_id == "car_b"
        assert pairs[0].defender_id == "car_a"
        assert pairs[0].delta_v_kph == 5.0

    def test_far_cars_not_detected(self, straight_section):
        cars = [
            ("car_a", 0.0, 310.0),
            ("car_b", 100.0, 315.0),  # too far
        ]
        pairs = detect_proximity_pairs(cars, straight_section, ScenarioTag.STRAIGHT)
        assert len(pairs) == 0

    def test_multiple_pairs(self, straight_section):
        cars = [
            ("car_a", 0.0, 300.0),
            ("car_b", 10.0, 305.0),
            ("car_c", 8.0, 310.0),
        ]
        pairs = detect_proximity_pairs(cars, straight_section, ScenarioTag.STRAIGHT)
        assert len(pairs) == 2

    def test_corner_tighter_threshold(self, corner_section):
        cars = [
            ("car_a", 0.0, 120.0),
            ("car_b", 15.0, 125.0),  # 15m — within straight threshold but outside corner
        ]
        pairs = detect_proximity_pairs(cars, corner_section, ScenarioTag.CORNER)
        assert len(pairs) == 0  # corner threshold is 10m

    def test_dirty_air_computed_for_pairs(self, straight_section):
        cars = [
            ("car_a", 0.0, 310.0),
            ("car_b", 10.0, 315.0),
        ]
        pairs = detect_proximity_pairs(cars, straight_section, ScenarioTag.STRAIGHT)
        assert pairs[0].dirty_air_penalty > 0


# ---------------------------------------------------------------------------
# Attack chance
# ---------------------------------------------------------------------------

class TestAttackChance:
    def test_blue_flag_high_chance(self, straight_section):
        pair = BattlePair(
            attacker_id="a", defender_id="d",
            gap_m=10.0, delta_v_kph=5.0,
            scenario=ScenarioTag.BLUE_FLAG,
        )
        att_skills = DriverSkills(overtaking_skill=70)
        def_skills = DriverSkills(defending_skill=70)
        att_result = _make_result()
        def_result = _make_result()
        att_state = CarState(overtake_window=0.5)

        chance = compute_attack_chance(
            pair, att_skills, def_skills, att_result, def_result, att_state
        )
        assert chance >= 0.9

    def test_no_overtake_window_no_chance(self, straight_section):
        pair = BattlePair(
            attacker_id="a", defender_id="d",
            gap_m=10.0, delta_v_kph=10.0,
            scenario=ScenarioTag.STRAIGHT,
        )
        att_state = CarState(overtake_window=0.0)
        chance = compute_attack_chance(
            pair, DriverSkills(), DriverSkills(),
            _make_result(), _make_result(), att_state
        )
        assert chance == 0.0

    def test_higher_delta_v_higher_chance(self):
        pair_slow = BattlePair(
            attacker_id="a", defender_id="d",
            gap_m=10.0, delta_v_kph=4.0,
            scenario=ScenarioTag.STRAIGHT,
        )
        pair_fast = BattlePair(
            attacker_id="a", defender_id="d",
            gap_m=10.0, delta_v_kph=15.0,
            scenario=ScenarioTag.STRAIGHT,
        )
        att_state = CarState(overtake_window=0.6)
        skills = DriverSkills(overtaking_skill=70)
        def_skills = DriverSkills(defending_skill=70)
        result = _make_result(ow=0.6)

        c_slow = compute_attack_chance(pair_slow, skills, def_skills, result, result, att_state)
        c_fast = compute_attack_chance(pair_fast, skills, def_skills, result, result, att_state)
        assert c_fast > c_slow

    def test_corner_harder_than_straight(self):
        pair_str = BattlePair(
            attacker_id="a", defender_id="d",
            gap_m=10.0, delta_v_kph=10.0,
            scenario=ScenarioTag.STRAIGHT,
        )
        pair_crn = BattlePair(
            attacker_id="a", defender_id="d",
            gap_m=5.0, delta_v_kph=10.0,
            scenario=ScenarioTag.CORNER,
        )
        att_state = CarState(overtake_window=0.6)
        skills = DriverSkills(overtaking_skill=80)
        def_skills = DriverSkills(defending_skill=60)
        result = _make_result(ow=0.6)

        c_str = compute_attack_chance(pair_str, skills, def_skills, result, result, att_state)
        c_crn = compute_attack_chance(pair_crn, skills, def_skills, result, result, att_state)
        assert c_str > c_crn


# ---------------------------------------------------------------------------
# Battle resolution
# ---------------------------------------------------------------------------

class TestResolve:
    def test_blocked_when_low_chance(self):
        random.seed(42)
        pair = BattlePair(
            attacker_id="a", defender_id="d",
            gap_m=20.0, delta_v_kph=4.0,
            scenario=ScenarioTag.STRAIGHT,
        )
        att = _make_entry("a", overtaking=50, defending=50)
        defe = _make_entry("d", overtaking=50, defending=80)
        att.state.overtake_window = 0.3
        att_r = _make_result(ow=0.3)
        def_r = _make_result()

        resolved = resolve_pair(pair, att.driver_skills, defe.driver_skills,
                                att_r, def_r, att.state, defe.state)
        assert resolved.outcome in (BattleOutcome.BLOCKED, BattleOutcome.NO_BATTLE)

    def test_overtake_with_high_advantage(self):
        random.seed(42)
        pair = BattlePair(
            attacker_id="a", defender_id="d",
            gap_m=10.0, delta_v_kph=20.0,
            scenario=ScenarioTag.STRAIGHT,
        )
        att = _make_entry("a", overtaking=90, defending=50)
        defe = _make_entry("d", overtaking=50, defending=40)
        att.state.overtake_window = 0.8
        att_r = _make_result(ow=0.8, grip_f=1.0, grip_r=1.0, late_brake=True)
        def_r = _make_result(grip_f=0.8, grip_r=0.8)

        resolved = resolve_pair(pair, att.driver_skills, defe.driver_skills,
                                att_r, def_r, att.state, defe.state)
        assert resolved.outcome == BattleOutcome.OVERTAKE_SUCCESS

    def test_cooldown_prevents_attempt(self):
        pair = BattlePair(
            attacker_id="a", defender_id="d",
            gap_m=10.0, delta_v_kph=15.0,
            scenario=ScenarioTag.STRAIGHT,
        )
        att = _make_entry("a")
        defe = _make_entry("d")
        att.state.attack_cooldown = 3  # on cooldown
        att.state.overtake_window = 0.8

        resolved = resolve_pair(pair, att.driver_skills, defe.driver_skills,
                                _make_result(), _make_result(),
                                att.state, defe.state)
        assert resolved.outcome == BattleOutcome.NO_BATTLE

    def test_blue_flag_forces_pass(self):
        random.seed(42)
        pair = BattlePair(
            attacker_id="a", defender_id="d",
            gap_m=10.0, delta_v_kph=5.0,
            scenario=ScenarioTag.BLUE_FLAG,
        )
        att = _make_entry("a")
        defe = _make_entry("d")
        att.state.overtake_window = 0.5

        resolved = resolve_pair(pair, att.driver_skills, defe.driver_skills,
                                _make_result(), _make_result(),
                                att.state, defe.state)
        assert resolved.outcome == BattleOutcome.OVERTAKE_SUCCESS


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestBattleEvents:
    def test_event_has_correct_fields(self, straight_section):
        pair = BattlePair(
            attacker_id="car_a", defender_id="car_b",
            gap_m=10.0, delta_v_kph=8.0,
            scenario=ScenarioTag.STRAIGHT,
            outcome=BattleOutcome.OVERTAKE_SUCCESS,
            attack_chance=0.72,
        )
        event = emit_battle_event(pair, straight_section)
        assert event.event_type == "battle_overtake_success"
        assert event.attacker_id == "car_a"
        assert event.section_id == "s01"
        assert "straight" in event.message.lower() or "overtake" in event.message.lower()


# ---------------------------------------------------------------------------
# Full BattleResolver integration
# ---------------------------------------------------------------------------

class TestBattleResolverIntegration:
    def test_resolve_section_with_two_cars(self, straight_section):
        random.seed(42)
        resolver = BattleResolver()

        att = _make_entry("fast_car", overtaking=85)
        defe = _make_entry("slow_car", defending=60)
        att.state.overtake_window = 0.7

        cars_in_section = [
            ("slow_car", 0.0, 290.0),
            ("fast_car", 15.0, 310.0),
        ]
        entries = {"fast_car": att, "slow_car": defe}
        results = {
            "fast_car": _make_result(v_eff=310.0, ow=0.7, grip_f=0.98, grip_r=0.98),
            "slow_car": _make_result(v_eff=290.0, ow=0.3, grip_f=0.85, grip_r=0.85),
        }

        battle_result = resolver.resolve_section(
            cars_in_section, straight_section, entries, results
        )

        # Should detect dirty air
        assert "fast_car" in battle_result.dirty_air_penalties

        # Should have at least one battle pair
        assert len(battle_result.pairs) >= 1
        assert len(battle_result.events) >= 1

    def test_no_battle_when_far_apart(self, straight_section):
        resolver = BattleResolver()

        att = _make_entry("fast_car")
        defe = _make_entry("slow_car")

        cars_in_section = [
            ("slow_car", 0.0, 290.0),
            ("fast_car", 100.0, 310.0),  # too far
        ]
        entries = {"fast_car": att, "slow_car": defe}
        results = {
            "fast_car": _make_result(),
            "slow_car": _make_result(),
        }

        battle_result = resolver.resolve_section(
            cars_in_section, straight_section, entries, results
        )
        assert len(battle_result.pairs) == 0

    def test_blue_flag_in_resolver(self, straight_section):
        random.seed(42)
        resolver = BattleResolver()

        leader = _make_entry("leader")
        backmarker = _make_entry("backmarker")
        leader.state.overtake_window = 0.5

        cars_in_section = [
            ("backmarker", 0.0, 280.0),
            ("leader", 10.0, 300.0),
        ]
        entries = {"leader": leader, "backmarker": backmarker}
        results = {
            "leader": _make_result(v_eff=300.0, ow=0.5),
            "backmarker": _make_result(v_eff=280.0),
        }

        battle_result = resolver.resolve_section(
            cars_in_section, straight_section, entries, results,
            blue_flag_cars=["backmarker"],
        )

        # Blue flag should force pass
        assert any(p.outcome == BattleOutcome.OVERTAKE_SUCCESS for p in battle_result.pairs)

    def test_multi_car_lap_with_battles(self):
        """Full lap with 3 cars and BattleResolver enabled in LapSimulator."""
        from lap_simulator.lap_simulator import LapSimulator, LapResult
        from lap_simulator.data_types import CircuitConfig, EnvContext, TyreCompound, TyreCompoundParams

        random.seed(42)

        # Minimal circuit: 3 sections
        cfg = CircuitConfig(
            circuit_id="test",
            sections=[
                SectionContext(
                    section_id="s1", name="Straight", kind=SectionKind.STRAIGHT,
                    length_m=800.0, v_base_kph=300.0,
                    heat_factor=0.2, cool_factor=1.2, dt_ref_s=9.6,
                ),
                SectionContext(
                    section_id="s2", name="T1", kind=SectionKind.SLOW_CORNER,
                    length_m=100.0, v_base_kph=80.0,
                    heat_factor=1.4, cool_factor=0.4, braking_energy_mj=1.0, dt_ref_s=4.5,
                ),
                SectionContext(
                    section_id="s3", name="Back Straight", kind=SectionKind.MEDIUM_STRAIGHT,
                    length_m=500.0, v_base_kph=250.0,
                    heat_factor=0.4, cool_factor=1.0, dt_ref_s=7.2,
                ),
            ],
            sector_markers_m=[0.0, 900.0],
            tyre_params={
                TyreCompound.C3: TyreCompoundParams(compound=TyreCompound.C3),
            },
        )
        env = EnvContext()

        sim = LapSimulator(cfg, env, enable_battles=True)
        assert sim.battle_resolver is not None

        # Register 3 cars with different speeds
        fast = _make_entry("fast", overtaking=85)
        fast.push_level = 1.05
        mid = _make_entry("mid", overtaking=70, defending=70)
        mid.push_level = 1.0
        slow = _make_entry("slow", overtaking=50, defending=80)
        slow.push_level = 0.95

        sim.register_cars([fast, mid, slow])

        results = sim.run_lap()
        assert len(results) == 3
        assert all(isinstance(r, LapResult) for r in results.values())

        # All cars should have valid lap times
        for cid, r in results.items():
            assert r.lap_time_s > 0
            assert len(r.section_results) == 3

        # Fast car should be faster than slow
        assert results["fast"].lap_time_s < results["slow"].lap_time_s

    def test_single_car_no_battles(self):
        """Single car with enable_battles=True should still work (no battles)."""
        from lap_simulator.lap_simulator import LapSimulator
        from lap_simulator.data_types import CircuitConfig, EnvContext, TyreCompound, TyreCompoundParams

        cfg = CircuitConfig(
            circuit_id="test",
            sections=[
                SectionContext(
                    section_id="s1", name="Straight", kind=SectionKind.STRAIGHT,
                    length_m=800.0, v_base_kph=300.0,
                    heat_factor=0.2, cool_factor=1.2, dt_ref_s=9.6,
                ),
            ],
            tyre_params={TyreCompound.C3: TyreCompoundParams(compound=TyreCompound.C3)},
        )
        sim = LapSimulator(cfg, EnvContext(), enable_battles=True)
        sim.register_car(_make_entry("solo"))
        results = sim.run_lap()
        assert "solo" in results
        assert results["solo"].lap_time_s > 0
