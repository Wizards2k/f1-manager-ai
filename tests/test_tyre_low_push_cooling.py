from python_backend.lap_simulator.data_types import (
    AeroForces,
    CarState,
    CircuitConfig,
    DriverIntent,
    EnvContext,
    SectionContext,
    SectionKind,
    TyreCompound,
    TyreCompoundParams,
)
from python_backend.lap_simulator.tyre_model import update_tyres


def _build_config() -> CircuitConfig:
    return CircuitConfig(
        circuit_id="test_track",
        name="Test Track",
        sections=[],
        sector_markers_m=[0.0, 1000.0, 2000.0, 3000.0],
        tyre_compounds={
            TyreCompound.C3: TyreCompoundParams(
                base_grip=1.0,
                wear_rate_base_pct_per_km=1.0,
                degradation_rate_multiplier=1.0,
                cooling_coeff=1.2,
                temp_opt_surface=100.0,
                temp_opt_core=92.0,
                gaussian_sigma_surface_c=18.0,
                gaussian_sigma_core_c=14.0,
                thermal_mass_surface=1.0,
                thermal_mass_core=1.2,
                conduction_coeff=0.9,
                slip_sensitivity=1.0,
                heat_cycle_grip_penalty=0.01,
                graining_surface_delta_c=-12.0,
                graining_core_delta_c=-10.0,
                graining_min_duration_s=6.0,
                blister_surface_delta_c=8.0,
                blister_core_delta_c=6.0,
                blister_min_duration_s=4.0,
            )
        },
    )


def test_low_push_levels_cool_tyres_more_than_high_push():
    config = _build_config()
    env = EnvContext(air_temp_c=24.0, track_temp_c=30.0)
    aero = AeroForces()
    section = SectionContext(
        section_id="s1",
        name="Main Straight",
        kind=SectionKind.STRAIGHT,
        length_m=900.0,
        v_base_kph=250.0,
        heat_factor=0.75,
        cool_factor=1.2,
        braking_energy_mj=0.1,
    )

    car_low = CarState(car_id="low_push")
    car_high = CarState(car_id="high_push")
    for tyre in list(car_low.tyres.values()) + list(car_high.tyres.values()):
        tyre.compound = TyreCompound.C3
        tyre.surface_temp_c = 118.0
        tyre.core_temp_c = 103.0

    low_driver = DriverIntent(pace_factor=0.82, push_level=1)
    high_driver = DriverIntent(pace_factor=1.02, push_level=8)

    update_tyres(car_low, section, env, aero, low_driver, config, dt_s=2.0, v_kph=240.0)
    update_tyres(car_high, section, env, aero, high_driver, config, dt_s=2.0, v_kph=240.0)

    low_surface_avg = sum(tyre.surface_temp_c for tyre in car_low.tyres.values()) / 4.0
    high_surface_avg = sum(tyre.surface_temp_c for tyre in car_high.tyres.values()) / 4.0

    assert low_surface_avg < high_surface_avg


def test_push_five_high_tyre_management_cools_slightly_more():
    config = _build_config()
    env = EnvContext(air_temp_c=24.0, track_temp_c=30.0)
    aero = AeroForces()
    section = SectionContext(
        section_id="s1",
        name="Main Straight",
        kind=SectionKind.STRAIGHT,
        length_m=900.0,
        v_base_kph=250.0,
        heat_factor=0.75,
        cool_factor=1.2,
        braking_energy_mj=0.1,
    )

    car_high_skill = CarState(car_id="high_skill")
    car_normal_skill = CarState(car_id="normal_skill")
    for tyre in list(car_high_skill.tyres.values()) + list(car_normal_skill.tyres.values()):
        tyre.compound = TyreCompound.C3
        tyre.surface_temp_c = 118.0
        tyre.core_temp_c = 103.0

    high_skill_driver = DriverIntent(pace_factor=0.9, push_level=5, tyre_management_skill=96)
    normal_skill_driver = DriverIntent(pace_factor=0.9, push_level=5, tyre_management_skill=70)

    update_tyres(car_high_skill, section, env, aero, high_skill_driver, config, dt_s=2.0, v_kph=240.0)
    update_tyres(car_normal_skill, section, env, aero, normal_skill_driver, config, dt_s=2.0, v_kph=240.0)

    high_skill_avg = sum(tyre.surface_temp_c for tyre in car_high_skill.tyres.values()) / 4.0
    normal_skill_avg = sum(tyre.surface_temp_c for tyre in car_normal_skill.tyres.values()) / 4.0

    assert high_skill_avg < normal_skill_avg
