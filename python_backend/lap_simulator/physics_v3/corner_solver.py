"""
Physics V3 — Corner Solver Module

Calcola la velocità di apex (v_apex) in una curva usando equazione fisica.

Formula:
    Accelerazione centripeta = v²/R
    Grip disponibile: Fz_eff = m*g + 0.5*ρ*v²*CLA
    Forza laterale limit: F_lat_max = μ * Fz_eff / m

    A equilibrio: v²/R = μ * (g + 0.5*ρ*v²*CLA/m)

    Riarrangiato come quadratica:
        A*v⁴ + B*v² + C = 0

    Risolvibile con radice quadratica (sostituzione w = v²)

Fonte: spec physics-engine-v3-spec.md Section 5
"""

import math
from typing import Optional, Tuple

from . import constants
from .aero_mapper import PhysicsAeroParams
from .balance_model import BalanceState


def solve_corner_apex_speed(
    radius_m: float,
    aero: PhysicsAeroParams,
    balance: BalanceState,
    mass_kg: float,
    mu_base: float,
    env_rho: float,
    banking_deg: float = 0.0,
) -> float:
    """
    Risolve v_apex usando equazione fisica della forza centripeta + downforce.

    Equazione:
        v²/R = [μ * (m*g + 0.5*ρ*v²*CLA)] / m

    Riarrangiata a quadratica in w = v²:
        A*w² + B*w + C = 0
        where:
            A = 0.5 * ρ * CLA / (m * R)
            B = -μ * (g + 0.5*ρ*v²*CLA/m) = ...  [semplificato]
            C = -μ * m * g

    Args:
        radius_m: Raggio della curva [m] (0 per rettilineo, non usare)
        aero: PhysicsAeroParams (CLA)
        balance: BalanceState (mu_front_eff, mu_rear_eff)
        mass_kg: Massa totale [kg]
        mu_base: Base grip coefficient (dalla tyre_model)
        env_rho: Densità aria [kg/m³]
        banking_deg: Banking della pista [°] (default 0 per tracciati flat)

    Returns:
        Velocità di apex [m/s], clamped a range fisico
    """

    if radius_m < 0.1:
        return 0.0

    # ========================================================================
    # Grip effettivo: media pesata tra asse ant/post
    # (in una curva, di solito usa il posterior grip che limita l'oversteer)
    # ========================================================================
    mu_eff = min(balance.mu_front_eff, balance.mu_rear_eff)
    if mu_eff < 0.1:
        mu_eff = mu_base  # Fallback a base se calcolato male

    # ========================================================================
    # Banking effect (se pista in banking)
    # ========================================================================
    if abs(banking_deg) > 0.1:
        banking_rad = math.radians(banking_deg)
        # Componente gravity ridotta da banking
        g_eff = constants.G * math.cos(banking_rad)
        # Gravity banking assist (spinge verso curva)
        g_banking = constants.G * math.sin(banking_rad)
    else:
        g_eff = constants.G
        g_banking = 0.0

    # ========================================================================
    # Risolvi quadratica: A*w² + B*w + C = 0 dove w = v²
    # ========================================================================
    # Formula con downforce:
    #   v²/R = μ * (g + 0.5*ρ*v²*CLA/m)
    #
    # Riarrangiato:
    #   v_apex² = (μ * m * g) / (m/R - 0.5*ρ*CLA*μ)
    #
    # Ensure denominatore > 0 per soluzione reale

    rho = env_rho
    cla = aero.CLA

    # Implementa la formula corretta con downforce
    # Denominatore: m/R - 0.5*ρ*CLA*μ
    A = mass_kg / radius_m - 0.5 * rho * cla * mu_eff

    if A > 0:
        # Numeratore: μ * m * g
        C = mu_eff * mass_kg * constants.G
        v_apex_sq = C / A
        v_apex = math.sqrt(max(0, v_apex_sq))
    else:
        # Fallback: formula semplificata senza downforce
        v_apex_sq = mu_eff * constants.G * radius_m
        v_apex = math.sqrt(max(0, v_apex_sq))

    # ========================================================================
    # Clamp a range fisico
    # ========================================================================
    # Minimo: velocità sicurezza
    v_min = 5.0  # m/s (~18 kph)

    # Massimo: MAX_LATERAL_G constraint
    v_max = math.sqrt(constants.MAX_LATERAL_G * radius_m * g_eff)

    v_apex = max(v_min, min(v_max, v_apex))

    return v_apex


def estimate_v_entry_exit(
    v_apex: float,
    braking_distance: float,
    acceleration_distance: float,
    dv_per_meter: float = 0.01,
) -> Tuple[float, float]:
    """
    Stima le velocità di entry e exit in base a v_apex e distanze di frenata/accelerazione.

    Semplificazione: assume decelerazione/accelerazione costante.

    Args:
        v_apex: Velocità di apex [m/s]
        braking_distance: Distanza per raggiungere v_apex dalla entry [m]
        acceleration_distance: Distanza per accelerare da v_apex all'exit [m]
        dv_per_meter: Rate decelerazione [m/s per meter] (default 0.01)

    Returns:
        (v_entry, v_exit) [m/s]
    """

    if braking_distance > 0:
        # v_entry² = v_apex² + 2*a*d
        # a = dv_per_meter * g (simplificato)
        a_brake = dv_per_meter * constants.G
        v_entry_sq = v_apex ** 2 + 2 * a_brake * braking_distance
        v_entry = math.sqrt(max(0, v_entry_sq))
    else:
        v_entry = v_apex

    if acceleration_distance > 0:
        a_accel = dv_per_meter * constants.G * 0.5  # Meno di frenata
        v_exit_sq = v_apex ** 2 + 2 * a_accel * acceleration_distance
        v_exit = math.sqrt(max(0, v_exit_sq))
    else:
        v_exit = v_apex

    return v_entry, v_exit


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    from .balance_model import compute_balance
    from ..data_types import AeroSetup, EnvContext

    # Setup test
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

    test_setup = AeroSetup()
    test_env = EnvContext(
        air_temp_c=20.0,
        track_temp_c=40.0,
        air_density_kg_m3=1.225,
        wind_speed_kph=5.0,
        rain_intensity=0.0,
        track_rubber_level=0.8,
        water_film_level=0.0,
    )

    # Compute balance first
    balance = compute_balance(
        mu_base=1.65,
        aero=test_aero,
        aero_setup=test_setup,
        v_ms=30.0,
        radius_m=668.0,
        mass_kg=798.0,
        env=test_env,
        a_long_g=0.0,
    )

    # Solve apex speed
    v_apex = solve_corner_apex_speed(
        radius_m=668.0,
        aero=test_aero,
        balance=balance,
        mass_kg=798.0,
        mu_base=1.65,
        env_rho=test_env.air_density_kg_m3,
        banking_deg=0.0,
    )

    print(f"Monaco Turn 1 (R=668m):")
    print(f"  v_apex = {v_apex:.1f} m/s = {v_apex*3.6:.1f} kph")
    print(f"  Expected: ~45 m/s (~160 kph)")
