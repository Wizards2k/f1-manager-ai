"""
Physics V3 — Acceleration Profile Module (RISCRITTURA PULITA 2026-04-04)

Formula fondamentale (Gemini spec + fisica Newtoniana):

    F_down    = 0.5 * ρ * v² * CLA                  [downforce aerodinamico]
    Fz_rear   = peso_statico_post + F_down_post       [carico verticale posteriore]
    F_grip    = μ_rear * Fz_rear                      [limite grip asse posteriore]

    Cerchio di Kamm (in curva reale, R < 500m):
        F_lat  = m * v²/R                             [forza laterale centripeta]
        F_long = sqrt(F_grip² - F_lat²)               [trazione longitudinale disponibile]

    Potenza (scalata per throttle del pilota):
        P_wheels = (ICE + ERS) * eff * throttle_frac  [potenza alle ruote]
        F_power  = P_wheels / v                        [F = P/v]

    Trazione effettiva (la minore tra potenza e grip):
        F_drive = min(F_power, F_long)

    Forze resistive:
        F_drag = 0.5 * ρ * v² * CDA + Crr * Fz_rear

    Accelerazione netta:
        a_net = (F_drive - F_drag) / m

Perché è corretto:
    - A bassa velocità: F_power >> F_grip → grip limita (gomme, non motore)
    - Ad alta velocità: F_power decresce (P/v), drag aumenta → potenza limita
    - L'accelerazione DIMINUISCE con la velocità (fisica corretta!)
    - Throttle scala la POTENZA (non l'accelerazione post-hoc)

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
    throttle_fraction: float = 1.0,
) -> Tuple[float, float, bool]:
    """
    Calcola la forza di trazione e l'accelerazione netta.

    Args:
        v_ms: Velocità corrente [m/s]
        aero: Parametri aerodinamici (CLA, CDA)
        balance: Stato bilancio auto (mu_rear_eff, Fz_rear, Fz_front)
        mass_kg: Massa totale con carburante [kg]
        pu_state: Stato power unit (ICE kW, ERS kW)
        radius_m: Raggio curva [m] (0 per rettilineo)
        is_cornering: True se in curva (applica cerchio di Kamm)
        env_rho: Densità aria [kg/m³]
        throttle_fraction: Throttle pilota [0.0, 1.0] — scala la potenza

    Returns:
        (F_drive [N], a_net [m/s²], wheelspin_flag)
    """

    if v_ms < constants.MIN_VELOCITY_MS:
        return 0.0, 0.0, False

    # =========================================================================
    # STEP 1: Grip disponibile (asse posteriore — quello che traziona)
    # =========================================================================
    F_grip_max = balance.mu_rear_eff * balance.Fz_rear

    # =========================================================================
    # STEP 2: Cerchio di Kamm — curve reali (R < 500m)
    # =========================================================================
    # Non si applica a curve larghissime (Parabolica Monza R=668m, praticamente rettilineo
    # dal punto di vista della trazione). Soglia 500m è fisicamente ragionevole:
    # una curva F1 "vera" che assorbe grip laterale significativo è R < 500m.
    if is_cornering and 0 < radius_m < 500.0:
        F_lat = mass_kg * (v_ms ** 2) / radius_m
        F_lat = min(F_lat, F_grip_max * 0.95)  # non può superare il grip totale
        F_long_available = math.sqrt(max(0.0, F_grip_max ** 2 - F_lat ** 2))
    else:
        F_long_available = F_grip_max

    # =========================================================================
    # STEP 3: Potenza alle ruote (scalata per throttle pilota)
    # =========================================================================
    # throttle_fraction scalata la POTENZA, non l'accelerazione.
    # Questo è fisicamente corretto: l'ECU scala la coppia del motore.
    P_ice = pu_state.ice_power_kw
    P_ers = max(0.0, pu_state.ers_output_kw)
    P_wheels_max = (P_ice + P_ers) * constants.DRIVETRAIN_EFFICIENCY * 1000.0  # [W]
    P_actual = P_wheels_max * max(0.0, min(1.0, throttle_fraction))

    F_drive_power = P_actual / v_ms  # F = P/v

    # =========================================================================
    # STEP 4: Trazione effettiva — min(potenza, grip)
    # =========================================================================
    # Se F_power > F_grip: le gomme slittano (wheelspin)
    # La trazione è semplicemente limitata al grip disponibile (TC in F1).
    # Non c'è penalità addizionale: il TC previene lo slittamento in modo pulito.
    wheelspin = F_drive_power > F_long_available
    F_drive = min(F_drive_power, F_long_available)

    # =========================================================================
    # STEP 5: Forze resistive (aero drag + rolling resistance)
    # =========================================================================
    # F_drag_aero = 0.5 * ρ * v² * CDA   (drag aerodinamico)
    # F_roll      = Crr * Fz              (resistenza rotolamento)
    F_drag_aero = 0.5 * env_rho * (v_ms ** 2) * aero.CDA
    F_drag_roll = constants.ROLLING_RESISTANCE_COEFF * (balance.Fz_front + balance.Fz_rear)
    F_drag = F_drag_aero + F_drag_roll

    # =========================================================================
    # STEP 6: Accelerazione netta
    # =========================================================================
    F_net = F_drive - F_drag
    a_net = F_net / mass_kg

    # Clamp di sicurezza numerica
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

    Returns:
        Deploy fraction [0.0, 1.0]
    """
    if section_kind is None:
        return 0.3

    section_kind_lower = section_kind.lower()

    if pu_state.ers_energy_mj > 3.8:
        return 1.0

    if "straight" in section_kind_lower:
        return 1.0
    elif "fast_corner" in section_kind_lower or "ultra_fast" in section_kind_lower:
        return 0.6
    elif "slow_corner" in section_kind_lower or "very_slow" in section_kind_lower:
        return 0.1
    else:
        return 0.3


def estimate_max_acceleration(
    v_ms: float,
    aero: PhysicsAeroParams,
    mass_kg: float,
    pu_state: PUState,
    env_rho: float = constants.RHO_SEA_LEVEL,
) -> float:
    """
    Stima accelerazione massima teorica in rettilineo (throttle = 100%).

    Returns:
        Accelerazione massima [m/s²]
    """
    if v_ms < constants.MIN_VELOCITY_MS:
        return 0.0

    P_total_w = (pu_state.ice_power_kw + max(0, pu_state.ers_output_kw)) * constants.DRIVETRAIN_EFFICIENCY * 1000.0
    F_drag = 0.5 * env_rho * (v_ms ** 2) * aero.CDA + constants.ROLLING_RESISTANCE_COEFF * mass_kg * constants.G
    F_drive = P_total_w / v_ms
    F_net = F_drive - F_drag

    a = F_net / mass_kg if mass_kg > 0 else 0.0
    return min(constants.MAX_BRAKE_DECEL_G * constants.G, max(0.0, a))


# =============================================================================
# Test / Validazione
# =============================================================================

if __name__ == "__main__":
    from ..data_types import PUState, AeroSetup, EnvContext
    from .balance_model import compute_balance, BalanceState

    # Costanti test
    test_aero = PhysicsAeroParams(
        CLA=2.90,
        CDA=1.20,
        CLA_front=1.45,
        CLA_rear=1.45,
        aero_balance=0.50,
        ground_effect_bonus=1.0,
        understeer_grip_penalty=0.0,
        oversteer_grip_penalty=0.0,
        CDA_drs_open=1.20,
        setup_quality_score=1.0,
    )

    test_balance = BalanceState(
        mu_front_eff=1.80,
        mu_rear_eff=1.80,
        load_transfer_lat=0.0,
        load_transfer_long=0.0,
        a_lat_g=0.0,
        a_long_g=0.0,
        balance_label="neutral",
        Fz_front=5500.0,
        Fz_rear=6200.0,
        load_transfer_lat_front=0.0,
        load_transfer_lat_rear=0.0,
    )

    test_pu = PUState(
        active_map="QUALIFY",
        ers_mode="QUALIFY",
        ice_temp_c=80.0,
        ice_power_kw=550.0,
        ers_energy_mj=3.0,
        ers_output_kw=120.0,
        fuel_kg=12.0,
    )

    mass = 810.0  # kg (798 dry + 12 fuel)

    print("=" * 70)
    print("VALIDAZIONE: Profilo accelerazione (deve DIMINUIRE con v)")
    print("=" * 70)
    print(f"{'Velocità':>10} {'F_power':>10} {'F_grip':>10} {'F_drive':>10} {'F_drag':>10} {'a_net':>8}")
    print("-" * 70)

    for v_kph in [100, 150, 200, 250, 300, 340]:
        v_ms = v_kph / 3.6
        F_drive, a_net, wheelspin = compute_drive_force(
            v_ms=v_ms,
            aero=test_aero,
            balance=test_balance,
            mass_kg=mass,
            pu_state=test_pu,
            radius_m=0.0,
            is_cornering=False,
            throttle_fraction=1.0,
        )
        P_w = (550 + 120) * 0.895 * 1000
        F_power = P_w / v_ms
        F_drag = 0.5 * 1.175 * v_ms ** 2 * 1.20 + 0.011 * 11700
        F_grip = 1.80 * 6200
        print(f"{v_kph:>10} {F_power:>10.0f} {F_grip:>10.0f} {F_drive:>10.0f} "
              f"{F_drag:>10.0f} {a_net:>8.2f}")

    print("-" * 70)
    print("Obiettivo: a_net deve DIMINUIRE da sinistra a destra")
    print("v_max attesa: ~340-360 kph (quando a_net ≈ 0)")
