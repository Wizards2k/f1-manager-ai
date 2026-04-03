"""
AeroPackage – Step 3 of update_section().

Computes aerodynamic forces: DF per axis, drag, aero balance,
handling penalty, under/oversteer signals, bump/kerb penalties,
cooling capacity and margin.

Reference: docs/lap-physics-spec-v0.5.md §3.3 Passo 3
           docs/AeroPackage.md §3
"""
from __future__ import annotations

from ..data_types import (
    AeroComponent,
    AeroForces,
    AeroSetup,
    CarState,
    CircuitConfig,
    EnvContext,
    SectionContext,
    SectionKind,
    clamp,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _component_df_drag(
    comp: AeroComponent,
    speed_factor: float,
) -> tuple[float, float]:
    """
    Compute DF and drag contribution for a single aero component.

    base_downforce / base_drag are "aero points" (scale ~0-50),
    NOT physical coefficients. speed_factor provides a small
    velocity-dependent modulation (0.8-1.1).

    df  = base_downforce * angle_term * speed_factor * damage_factor
    drag = base_drag * angle_term * damage_factor
    """
    delta_angle = comp.angle_deg - comp.angle_ref_deg
    
    # 1. Stallo Aerodinamico: oltre i +15 gradi l'ala satura e non genera più DF utile
    if delta_angle > 15.0:
        effective_delta_df = 15.0 + (delta_angle - 15.0) * 0.1
    elif delta_angle < -10.0:
        effective_delta_df = -10.0 + (delta_angle + 10.0) * 0.2
    else:
        effective_delta_df = delta_angle
        
    angle_term_df = 1.0 + comp.angle_sensitivity * effective_delta_df
    angle_term_df = max(angle_term_df, 0.1)

    # 2. Drag Indotto: inclinare troppo un'ala fuori progetto crea una resistenza esponenziale
    if delta_angle > 0:
        induced_penalty = (delta_angle / 20.0) ** 2
        angle_term_drag = 1.0 + comp.angle_sensitivity * delta_angle + (comp.angle_sensitivity * induced_penalty * 5.0)
    else:
        angle_term_drag = 1.0 + comp.angle_sensitivity * delta_angle
        
    angle_term_drag = max(angle_term_drag, 0.1)

    df = comp.base_downforce * angle_term_df * speed_factor * comp.damage_factor
    drag = comp.base_drag * angle_term_drag * comp.damage_factor
    return df, drag


def _suspension_mult(efficiency: float, rigidity: float) -> float:
    """
    Suspension multiplier on DF.
    susp_mult = 0.85 + 0.3 * (efficiency - 50) / 50
    Clamped [0.8, 1.2].
    efficiency is 0-1 in our model, so we scale to 0-100 internally.
    """
    eff_100 = efficiency * 100.0
    mult = 0.85 + 0.3 * (eff_100 - 50.0) / 50.0
    return clamp(mult, 0.8, 1.2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_forces(
    aero: AeroSetup,
    section: SectionContext,
    env: EnvContext,
    car_state: CarState,
    config: CircuitConfig,
    v_kph: float = 0.0,
    airflow_penalty: float = 0.0,
    drs_active: bool = False,
) -> AeroForces:
    """
    Compute all aerodynamic forces for the current section.

    Parameters
    ----------
    aero : AeroSetup       – car's aero configuration (from setup)
    section : SectionContext – current circuit section
    env : EnvContext         – environmental conditions
    car_state : CarState     – current mutable car state (for damage)
    config : CircuitConfig   – circuit tuning coefficients
    v_kph : float            – estimated speed (for dynamic pressure)
    airflow_penalty : float  – dirty air / wake penalty (0-1)
    drs_active : bool        – DRS open on this section
    """
    # Speed factor: small modulation so DF grows slightly with speed
    # At 200 kph → ~1.0, at 300 kph → ~1.05, at 100 kph → ~0.9
    v_ref_kph = 200.0
    speed_factor = clamp(0.8 + 0.2 * (v_kph / max(v_ref_kph, 1.0)), 0.8, 1.15)

    # --- Per-component DF and drag ---
    df_fw, drag_fw = _component_df_drag(aero.front_wing, speed_factor)
    df_rw, drag_rw = _component_df_drag(aero.rear_wing, speed_factor)
    df_bw, drag_bw = _component_df_drag(aero.beam_wing, speed_factor)
    df_ff, drag_ff = _component_df_drag(aero.front_floor, speed_factor)
    df_rf, drag_rf = _component_df_drag(aero.rear_floor, speed_factor)
    df_sp, drag_sp = _component_df_drag(aero.sidepods, speed_factor)
    df_ec, drag_ec = _component_df_drag(aero.engine_cover, speed_factor)
    df_b,  drag_b  = _component_df_drag(aero.b_wing, speed_factor)

    # DRS: reduce rear wing drag
    if drs_active and aero.rear_wing.drs_drag_reduction > 0:
        drag_rw *= (1.0 - aero.rear_wing.drs_drag_reduction)

    # --- Aggregate DF per axis (spec §4) ---
    df_front_raw = df_fw + df_ff + df_sp * 0.5
    df_rear_raw = df_rw + df_rf + df_ec + df_bw + df_b + df_sp * 0.5

    # --- Suspension multipliers ---
    susp_front_mult = _suspension_mult(
        aero.suspension_front.efficiency,
        aero.suspension_front.rigidity,
    )
    susp_rear_mult = _suspension_mult(
        aero.suspension_rear.efficiency,
        aero.suspension_rear.rigidity,
    )

    df_front_eff = (df_front_raw + aero.suspension_front.df_bonus) * susp_front_mult
    df_rear_eff = (df_rear_raw + aero.suspension_rear.df_bonus) * susp_rear_mult

    # --- Ride height penalty ---
    rh_pen_front = abs(aero.ride_height_front_mm - aero.ride_height_optimal_front_mm) * 0.02
    rh_pen_rear = abs(aero.ride_height_rear_mm - aero.ride_height_optimal_rear_mm) * 0.02
    df_front_eff *= max(0.7, 1.0 - rh_pen_front)
    df_rear_eff *= max(0.7, 1.0 - rh_pen_rear)

    # --- Damage penalties ---
    df_front_eff *= (1.0 - car_state.damage.df_loss * 0.5)
    df_rear_eff *= (1.0 - car_state.damage.df_loss * 0.5)

    df_total = df_front_eff + df_rear_eff

    # --- Drag ---
    drag_total = (drag_fw + drag_rw + drag_bw + drag_ff + drag_rf
                  + drag_sp + drag_ec + drag_b)
    drag_total *= (1.0 + car_state.damage.drag_increase)
    # Airflow penalty (dirty air) increases drag
    drag_eff = drag_total * (1.0 + airflow_penalty * 0.15)

    # --- Aero balance & handling penalty ---
    aero_balance = df_front_eff / max(df_total, 0.01)
    balance_target = 0.50
    balance_error = aero_balance - balance_target

    # Antiroll modulation
    antiroll_front_mod = 1.0 + (aero.antiroll_front_rigidity - 0.5) * 0.1
    antiroll_rear_mod = 1.0 + (aero.antiroll_rear_rigidity - 0.5) * 0.1

    front_mech_stiffness = (
        aero.suspension_front.rigidity * antiroll_front_mod
        + aero.antiroll_front_rigidity
    )
    rear_mech_stiffness = (
        aero.suspension_rear.rigidity * antiroll_rear_mod
        + aero.antiroll_rear_rigidity
    )
    mech_balance_shift = clamp((front_mech_stiffness - rear_mech_stiffness) * 0.22, -0.12, 0.12)

    wing_balance_shift = clamp(
        (aero.front_wing.angle_deg - aero.rear_wing.angle_deg) * 0.0032,
        -0.07,
        0.07,
    )
    rake_mm = aero.ride_height_rear_mm - aero.ride_height_front_mm
    rake_balance_shift = clamp((rake_mm - 12.0) * -0.0028, -0.05, 0.05)

    fuel_kg = max(getattr(car_state.pu, "fuel_kg", 0.0), 0.0)
    fuel_load_ratio = clamp(fuel_kg / 110.0, 0.0, 1.0)
    fuel_balance_shift = 0.025 * fuel_load_ratio

    mech_rear_excess = max(0.0, rear_mech_stiffness - front_mech_stiffness)
    rear_aero_support_deficit = max(0.0, aero.front_wing.angle_deg - aero.rear_wing.angle_deg)
    low_rake_instability = max(0.0, 12.0 - rake_mm)
    rear_instability_bias = clamp(
        mech_rear_excess * rear_aero_support_deficit * 0.16
        + mech_rear_excess * low_rake_instability * 0.025,
        0.0,
        0.16,
    )

    front_mech_excess = max(0.0, front_mech_stiffness - rear_mech_stiffness)
    rear_aero_support_excess = max(0.0, aero.rear_wing.angle_deg - aero.front_wing.angle_deg)
    high_rake_understeer = max(0.0, rake_mm - 12.0)

    understeer_signal = (
        max(0.0, balance_error)
        + front_mech_excess * 0.16
        + rear_aero_support_excess * 0.020
        + high_rake_understeer * 0.010
        + fuel_balance_shift * 0.35
    )
    oversteer_signal = (
        max(0.0, -balance_error)
        + mech_rear_excess * 0.18
        + rear_aero_support_deficit * 0.024
        + low_rake_instability * 0.012
        + rear_instability_bias
        + fuel_balance_shift * 0.20
    )

    combined_balance_error = (
        balance_error
        + mech_balance_shift
        + wing_balance_shift
        + rake_balance_shift
        + fuel_balance_shift
        + rear_instability_bias
    )

    handling_penalty = abs(combined_balance_error) * config.k_handling
    handling_penalty += car_state.damage.handling_penalty_damage
    handling_penalty = clamp(handling_penalty, 0.0, 0.5)

    # Under/oversteer signals
    understeer_level = clamp((understeer_signal - 0.035) * 3.8, 0.0, 1.0)
    oversteer_level = clamp((oversteer_signal - 0.035) * 4.2, 0.0, 1.0)

    # --- Bump / kerb penalties ---
    ride_height_low_factor = clamp(
        1.0 - (aero.ride_height_front_mm - 25.0) / 35.0, 0.0, 1.0
    )
    bump_penalty = (
        section.bumpiness_factor
        * config.damage_coeffs.shock_scaler_bumpiness
        * (1.0 + aero.suspension_front.rigidity)
        * ride_height_low_factor
    )
    kerb_impact = section.kerb_severity * config.damage_coeffs.shock_scaler_kerb_severity
    kerb_sev = section.kerb_severity

    # --- Cooling ---
    cooling_capacity = (
        aero.sidepods.cooling_contribution
        + aero.engine_cover.cooling_contribution
    )
    cooling_reduced = cooling_capacity * (1.0 - airflow_penalty * 0.3)

    return AeroForces(
        df_front_eff=df_front_eff,
        df_rear_eff=df_rear_eff,
        df_total=df_total,
        drag_eff=drag_eff,
        aero_balance=aero_balance,
        handling_penalty=handling_penalty,
        understeer_level=understeer_level,
        oversteer_level=oversteer_level,
        bump_penalty=bump_penalty,
        kerb_impact=kerb_impact,
        kerb_severity=kerb_sev,
        cooling_capacity=cooling_reduced,
        cooling_margin=0.0,  # computed after PU step
        airflow_penalty=airflow_penalty,
        drag_ref=30.0,       # reference drag for index normalization
    )
