"""
Physics V3 — Acceleration Profile Module

Modella l'accelerazione usando il cerchio di trazione (Kamm circle):
    F_total_available = μ * Fz (grip limit)
    F_lat_required = m * v²/R (in curva)
    F_long_available = sqrt(F_total² - F_lat²)  [traction circle]

    F_drive = min(P/v, F_long_available)
    a_net = (F_drive - F_drag) / m

Gestisce anche wheelspin e ERS deployment.

Fonte: spec physics-engine-v3-spec.md Section 7
"""

import math
from typing import Tuple

from . import constants
from .aero_mapper import PhysicsAeroParams
from .balance_model import BalanceState
from ..data_types import PUState


def compute_drive_force(
    v_ms: float,
    aero: PhysicsAeroParams,
    balance: BalanceState,
    mass_kg: float,
    pu_state: PUState,
    radius_m: float = 0.0,
    is_cornering: bool = False,
    env_rho: float = constants.RHO_SEA_LEVEL,
) -> Tuple[float, float, bool]:
    """
    Calcola la forza di trazione disponibile considerando il cerchio di trazione.

    Algoritmo:
    1. F_total = μ_rear * Fz_rear (grip limit posteriore, quello che limita)
    2. Se in curva: F_lat = m * v²/R (forza laterale richiesta)
    3. F_long_available = sqrt(F_total² - F_lat²)  [Kamm circle]
    4. P_total = (ICE + ERS) * drivetrain_efficiency
    5. F_drive_power = P_total / v
    6. F_drive = min(F_drive_power, F_long_available)
    7. Check wheelspin: se F_drive > limit → loss 15%

    Args:
        v_ms: Velocità [m/s]
        aero: PhysicsAeroParams
        balance: BalanceState (mu_rear_eff)
        mass_kg: Massa [kg]
        pu_state: Stato power unit (potenza ICE + ERS in kW)
        radius_m: Raggio curva [m] (0 per rettilineo)
        is_cornering: Se true, applica Kamm circle

    Returns:
        (F_drive_actual, a_net, wheelspin_flag)
    """

    if v_ms < constants.MIN_VELOCITY_MS:
        return 0.0, 0.0, False

    # ========================================================================
    # STEP 1: Grip limit (forza verticale asse posteriore)
    # ========================================================================
    # Il grip è limitato dall'asse posteriore (rear wheels sono quelli che spingono)
    F_grip_max = balance.mu_rear_eff * balance.Fz_rear

    # ========================================================================
    # STEP 2: Forza laterale richiesta (in curva vera, non corner largo)
    # ========================================================================
    # Apply Kamm circle ONLY for real corners (radius < 200m)
    # Wide turns (e.g. Parabolica 668m) are essentially straights for traction circle
    if is_cornering and radius_m > 0.1 and radius_m < 200.0:
        F_lat_required = mass_kg * (v_ms ** 2) / radius_m
        F_lat_required = min(F_lat_required, F_grip_max * 0.95)  # Non può superare grip
    else:
        F_lat_required = 0.0

    # ========================================================================
    # STEP 3: Traction circle (Kamm) — forza longitudinale disponibile
    # ========================================================================
    if F_lat_required > 0:
        # sqrt(F_total² - F_lat²)
        if F_lat_required >= F_grip_max * 0.99:
            # Saturo in laterale, niente spinta longitudinale
            F_long_available = 0.0
        else:
            F_long_available_sq = F_grip_max ** 2 - F_lat_required ** 2
            F_long_available = math.sqrt(max(0, F_long_available_sq))
    else:
        F_long_available = F_grip_max

    # ========================================================================
    # STEP 4: Potenza disponibile da motore
    # ========================================================================
    # P_total = (ICE_kw + ERS_kw) * drivetrain_efficiency
    P_ice = pu_state.ice_power_kw
    P_ers = pu_state.ers_output_kw if pu_state.ers_output_kw > 0 else 0
    P_total_kw = (P_ice + P_ers) * constants.DRIVETRAIN_EFFICIENCY
    P_total_w = P_total_kw * 1000.0

    # F_drive da potenza: P = F * v => F = P / v
    if v_ms > constants.MIN_VELOCITY_MS:
        F_drive_power = P_total_w / v_ms
    else:
        F_drive_power = 0.0

    # ========================================================================
    # STEP 5: Forza di trazione attuale (minore tra potenza e grip)
    # ========================================================================
    F_traction_limit = F_long_available * 1.05  # 5% buffer per wheelspin detection
    wheelspin = F_drive_power > F_traction_limit

    if wheelspin:
        # Wheelspin → perde 15% di trazione
        F_drive = F_long_available * 0.85
    else:
        F_drive = min(F_drive_power, F_long_available)

    # ========================================================================
    # STEP 6: Forza di resistenza (aero drag + rolling resistance)
    # ========================================================================
    # F_drag = 0.5 * ρ * v² * CDA + Crr * Fz
    rho = env_rho  # Air density from environment (or default sea level)
    F_drag_aero = 0.5 * rho * (v_ms ** 2) * aero.CDA
    F_drag_rolling = constants.ROLLING_RESISTANCE_COEFF * balance.Fz_rear
    F_drag_total = F_drag_aero + F_drag_rolling

    # ========================================================================
    # STEP 7: Accelerazione netta
    # ========================================================================
    F_net = F_drive - F_drag_total
    a_net = F_net / mass_kg if mass_kg > 0 else 0.0

    # Clamp a MAX_BRAKE_DECEL_G per sicurezza (non può accelerare più di frenare)
    a_net = max(-constants.MAX_BRAKE_DECEL_G * constants.G, a_net)
    a_net = min(constants.MAX_BRAKE_DECEL_G * constants.G, a_net)

    return F_drive, a_net, wheelspin


def ers_deployment_strategy(
    v_ms: float,
    section_kind: str,
    pu_state: PUState,
) -> float:
    """
    Determina la frazione di ERS da deploy nel prossimo dt.

    Strategia:
    - Rettilineo (STRAIGHT): deploy massimo (100%)
    - Uscita curva (FAST_CORNER): deploy parziale (60%) per evitare wheelspin
    - Curva normale (MEDIUM_CORNER): deploy minimo (20%)
    - Frenata (trailing): harvest (regen, negative deploy)

    Args:
        v_ms: Velocità [m/s]
        section_kind: Tipo sezione ("straight", "fast_corner", "slow_corner", etc.)
        pu_state: Stato power unit (battery SOC, ERS energy)

    Returns:
        Deploy fraction [0.0, 1.0] dove 0 = no deploy, 1 = max deploy
    """

    # Default: sezione sconosciuta → deploy conservativo
    if section_kind is None:
        return 0.3

    section_kind_lower = section_kind.lower()

    # Check battery SOC — se troppo carica, rilascia energia
    if pu_state.ers_energy_mj > 3.8:  # Batteria quasi piena
        return 1.0  # Deploy massimo per svuotare

    # Strategia per tipo sezione
    if "straight" in section_kind_lower or "medium_straight" in section_kind_lower:
        return 1.0  # Rettilineo: deploy massimo

    elif "fast_corner" in section_kind_lower or "ultra_fast" in section_kind_lower:
        return 0.6  # Curva veloce: deploy parziale (cauto con wheelspin)

    elif "slow_corner" in section_kind_lower or "very_slow" in section_kind_lower:
        return 0.1  # Curva lenta: deploy minimo (quasi no)

    else:
        return 0.3  # Sconosciuto: conservativo


def estimate_max_acceleration(
    v_ms: float,
    aero: PhysicsAeroParams,
    mass_kg: float,
    pu_state: PUState,
    env_rho: float = constants.RHO_SEA_LEVEL,
) -> float:
    """
    Stima l'accelerazione massima in rettilineo (no traction circle limit).

    Args:
        v_ms: Velocità [m/s]
        aero: PhysicsAeroParams (CDA)
        mass_kg: Massa [kg]
        pu_state: Stato power unit

    Returns:
        Accelerazione massima [m/s²]
    """

    if v_ms < constants.MIN_VELOCITY_MS:
        return 0.0

    # Power disponibile
    P_total_kw = (pu_state.ice_power_kw + max(0, pu_state.ers_output_kw)) * constants.DRIVETRAIN_EFFICIENCY
    P_total_w = P_total_kw * 1000.0

    # Drag
    rho = env_rho  # Air density from environment (or default sea level)
    F_drag = 0.5 * rho * (v_ms ** 2) * aero.CDA + constants.ROLLING_RESISTANCE_COEFF * mass_kg * constants.G

    # Force
    F_drive = P_total_w / v_ms if v_ms > 0 else 0
    F_net = F_drive - F_drag

    a = F_net / mass_kg if mass_kg > 0 else 0
    return min(constants.MAX_BRAKE_DECEL_G * constants.G, max(0, a))


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    from ..data_types import PUState

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

    test_balance = BalanceState(
        mu_front_eff=1.65,
        mu_rear_eff=1.65,
        load_transfer_lat=0.0,
        load_transfer_long=0.0,
        a_lat_g=0.0,
        a_long_g=0.0,
        balance_label="neutral",
        Fz_front=4000.0,
        Fz_rear=4800.0,
        load_transfer_lat_front=0.0,
        load_transfer_lat_rear=0.0,
    )

    test_pu = PUState(
        active_map="RACE",
        ers_mode="DEPLOY",
        ice_temp_c=80.0,
        ice_power_kw=750.0,
        ers_energy_mj=2.0,
        ers_output_kw=160.0,
        fuel_kg=50.0,
    )

    # Test rettilineo a 100 m/s
    F_drive, a_net, wheelspin = compute_drive_force(
        v_ms=100.0,
        aero=test_aero,
        balance=test_balance,
        mass_kg=798.0,
        pu_state=test_pu,
        radius_m=0.0,
        is_cornering=False,
    )

    print(f"Straight line acceleration (100 m/s):")
    print(f"  F_drive = {F_drive:.0f} N")
    print(f"  a_net = {a_net:.2f} m/s² = {a_net/constants.G:.2f}g")
    print(f"  Wheelspin: {wheelspin}")
