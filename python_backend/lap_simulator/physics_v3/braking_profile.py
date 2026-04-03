"""
Physics V3 — Braking Profile Module

Simula la frenata nel dettaglio:
- Temperatura freni e coefficiente attrito μ_brake(T)
- Distanza di frenata
- Look-ahead: decelerazione target per raggiungere v_target entro distanza disponibile

Fonte: spec physics-engine-v3-spec.md Section 6
"""

import math
from typing import Optional

from . import constants
from .aero_mapper import PhysicsAeroParams
from ..data_types import BrakeState, EnvContext


def mu_brake_from_temp(temp_c: float) -> float:
    """
    Interpola μ_brake da BRAKE_MU_MAP in base a temperatura.
    Usa interpolazione lineare tra i punti della mappa.

    Args:
        temp_c: Temperatura freni [°C]

    Returns:
        Coefficiente attrito freni μ_brake [0, 1]
    """
    return constants.interpolate_brake_mu(temp_c)


def compute_braking_distance(
    v_entry_ms: float,
    v_target_ms: float,
    aero: PhysicsAeroParams,
    brake_state: BrakeState,
    mass_kg: float,
    env: EnvContext,
) -> float:
    """
    Calcola la distanza di frenata da v_entry a v_target.

    Usa integrazione numerica della decelerazione:
        a_brake(v) = μ_brake(T) * (g + 0.5*ρ*v²*CLA/m)

    Args:
        v_entry_ms: Velocità iniziale [m/s]
        v_target_ms: Velocità target [m/s]
        aero: PhysicsAeroParams (CDA, CLA)
        brake_state: BrakeState (temperature_front, temperature_rear)
        mass_kg: Massa [kg]
        env: Contesto ambientale (air_density)

    Returns:
        Distanza di frenata [m]
    """

    if v_entry_ms <= v_target_ms or v_entry_ms < 1.0:
        return 0.0

    rho = env.air_density_kg_m3

    # ========================================================================
    # Integrazione numerica: 50Hz step (0.02s)
    # ========================================================================
    distance = 0.0
    v_current = v_entry_ms
    dt = constants.INTEGRATION_DT_S

    while v_current > v_target_ms + 0.1:  # Tolerance 0.1 m/s

        # Temperatura media (assumi degradazione termica lineare durante frenata)
        # Semplificazione: usa temperatura attuale (in realtà cambierebbe durante frenata)
        temp_brake = (brake_state.temp_front_c + brake_state.temp_rear_c) / 2.0
        mu_brake = mu_brake_from_temp(temp_brake)

        # Decelerazione istantanea
        # a = μ_brake * (g + 0.5*ρ*v²*CLA/m)
        dynamic_pressure = 0.5 * rho * (v_current ** 2)
        downforce = dynamic_pressure * aero.CLA
        fz = mass_kg * constants.G + downforce
        a_brake = mu_brake * (fz / mass_kg)

        # Clamp a MAX_BRAKE_DECEL_G per sicurezza
        a_brake = min(a_brake, constants.MAX_BRAKE_DECEL_G * constants.G)

        # Cinematica: s = v*t - 0.5*a*t²
        distance_step = v_current * dt - 0.5 * a_brake * (dt ** 2)
        distance_step = max(0, distance_step)

        distance += distance_step
        v_current -= a_brake * dt

        if v_current < constants.MIN_VELOCITY_MS:
            break

    return distance


def compute_look_ahead_deceleration(
    v_current_ms: float,
    v_target_ms: float,
    distance_remaining_m: float,
    aero: PhysicsAeroParams,
    brake_state: BrakeState,
    mass_kg: float,
    env: EnvContext,
) -> float:
    """
    Calcola la decelerazione richiesta per raggiungere v_target entro distance_remaining.

    Usa formula cinematica: v_target² = v_current² - 2*a*distance

    Args:
        v_current_ms: Velocità attuale [m/s]
        v_target_ms: Velocità target [m/s]
        distance_remaining_m: Distanza disponibile [m]
        aero, brake_state, mass_kg, env: Parametri freni

    Returns:
        Decelerazione richiesta [m/s²], clamped a range fisico
    """

    if distance_remaining_m < 1.0:
        # Distanza troppo corta → decelera massimo
        return constants.MAX_BRAKE_DECEL_G * constants.G

    # Formula: a = (v_current² - v_target²) / (2 * distance)
    a_required = (v_current_ms ** 2 - v_target_ms ** 2) / (2.0 * distance_remaining_m)
    a_required = max(0, a_required)

    # Clamp a limite massimo fisico
    a_max = constants.MAX_BRAKE_DECEL_G * constants.G
    a_required = min(a_required, a_max)

    return a_required


def compute_dynamic_brake_bias(
    base_bias: float,
    brake_pressure_pct: float,
    bmig_name: str = "standard",
) -> float:
    """
    Calcola il bias freni dinamico durante la frenata.

    Durante la staccata, il driver regola il bias dinamicamente:
    - Attacco (100% pressione): +2–4% anteriore (stabilità massima)
    - Rilascio (50% pressione): bias_base
    - Trail braking (10% pressione): -1.5–3% posteriore (aiuta rotazione)

    Args:
        base_bias: Bias di base [0.48, 0.65] (% sul davanti)
        brake_pressure_pct: Pressione pedale [0–100%]
        bmig_name: Profilo driver ("standard", "aggressive", "smooth")

    Returns:
        Bias dinamico [0.48, 0.65]
    """

    if brake_pressure_pct > 90.0:
        # Attacco: +3% anteriore
        offset = 0.03
    elif brake_pressure_pct < 15.0:
        # Trail braking: -2% posteriore
        offset = -0.02
    else:
        # Rilascio: interpolazione lineare
        frac = (brake_pressure_pct - 15.0) / (90.0 - 15.0)
        offset = -0.02 + frac * 0.05  # da -0.02 a +0.03

    # Applica profilo driver
    if bmig_name == "aggressive":
        offset *= 1.3  # Driver più aggressivo
    elif bmig_name == "smooth":
        offset *= 0.6  # Driver più dolce

    bias_dynamic = base_bias + offset
    bias_dynamic = max(0.48, min(0.65, bias_dynamic))

    return bias_dynamic


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    from ..data_types import BrakeState

    # Test brake distance
    brake_state = BrakeState(
        temp_front_c=700.0,
        temp_rear_c=650.0,
        wear_front_pct=0.0,
        wear_rear_pct=0.0,
        fade_level=0.0,
        duct_opening=0.45,
        bias_front_pct=0.54,
    )

    test_aero = PhysicsAeroParams(
        CLA=3.20,
        CDA=1.10,
        CLA_front=1.60,
        CLA_rear=1.60,
        aero_balance=0.50,
        ground_effect_bonus=1.0,
        understeer_grip_penalty=0.0,
        oversteer_grip_penalty=0.0,
        CDA_drs_open=1.10,
        setup_quality_score=1.0,
    )

    test_env = EnvContext(
        air_temp_c=20.0,
        track_temp_c=40.0,
        air_density_kg_m3=1.225,
        wind_speed_kph=5.0,
        rain_intensity=0.0,
        track_rubber_level=0.8,
        water_film_level=0.0,
    )

    # Test braking distance: 300 kph → 100 kph
    v_entry = 300.0 / 3.6  # m/s
    v_target = 100.0 / 3.6
    distance = compute_braking_distance(
        v_entry_ms=v_entry,
        v_target_ms=v_target,
        aero=test_aero,
        brake_state=brake_state,
        mass_kg=798.0,
        env=test_env,
    )

    print(f"Braking distance 300→100 kph: {distance:.1f} m")
    print(f"Expected: ~100–120 m (freni ottimali)")

    # Test dinamico bias
    bias_attack = compute_dynamic_brake_bias(0.54, 95.0)
    bias_release = compute_dynamic_brake_bias(0.54, 50.0)
    bias_trail = compute_dynamic_brake_bias(0.54, 10.0)
    print(f"\nDynamic brake bias:")
    print(f"  Attack (95%): {bias_attack:.3f}")
    print(f"  Release (50%): {bias_release:.3f}")
    print(f"  Trail (10%): {bias_trail:.3f}")
