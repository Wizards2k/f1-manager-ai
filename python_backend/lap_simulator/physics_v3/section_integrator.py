"""
Physics V3 — Section Integrator Module

Due modalità di integrazione cinematica:

1. HD Waypoints (Monaco, Imola, etc.):
   - Loop su 5m waypoints con radius_m, slope_deg, camber_deg, throttle_pct/brake_pct
   - 50Hz step per step (50-400 step per sezione)
   - Massima accuratezza

2. Analitico (circuiti senza HD):
   - Loop 50Hz con look-ahead
   - Calcola s_brake_needed, decide FRENA vs ACCELERA
   - Converge in 100-200 step

Fonte: spec physics-engine-v3-spec.md Section 8
"""

import math
from typing import List, Tuple, Optional, Dict, Any

from . import constants
from .aero_mapper import PhysicsAeroParams
from .balance_model import compute_balance, BalanceState
from .braking_profile import compute_braking_distance, compute_look_ahead_deceleration
from .acceleration_profile import compute_drive_force
from .corner_solver import solve_corner_apex_speed
from ..data_types import SectionContext, Waypoint, BrakeState, PUState, EnvContext, AeroSetup


def integrate_section_hd(
    waypoints: List[Waypoint],
    v_entry_ms: float,
    aero: PhysicsAeroParams,
    aero_setup: AeroSetup,
    mass_kg: float,
    mu_base: float,
    env: EnvContext,
    pu_state: PUState,
    brake_state: BrakeState,
) -> Tuple[float, float, List[Dict[str, Any]]]:
    """
    Integrazione cinematica su waypoints HD (5m passo).

    Per ogni waypoint:
    1. Leggi radius_m, slope_deg, throttle_pct/brake_pct
    2. compute_balance() con v_current, radius
    3. Regime da throttle/brake waypoint
    4. Cinematica: v_new² = v² + 2*a*dist_step
    5. dt_step = dist_step / v_avg

    Args:
        waypoints: Lista di Waypoint (5m passo)
        v_entry_ms: Velocità entry [m/s]
        aero, aero_setup: Parametri aerodinamici
        mass_kg: Massa [kg]
        mu_base: Base grip coefficient
        env, pu_state, brake_state: Contesti fisici

    Returns:
        (dt_total, v_exit, telemetry_points)
    """

    if not waypoints or len(waypoints) < 2:
        return 0.0, v_entry_ms, []

    dt_total = 0.0
    v_current = v_entry_ms
    telemetry_points = []

    for i in range(len(waypoints) - 1):
        wp_current = waypoints[i]
        wp_next = waypoints[i + 1]

        # Distanza step [m]
        dist_step = wp_next.dist_m - wp_current.dist_m
        if dist_step < 0.1:
            continue

        # Radius da waypoint (0 per rettilineo)
        radius_m = wp_current.radius_m if wp_current.radius_m is not None else 0.0
        radius_m = max(0.0, radius_m)

        # Slope [°]
        slope_deg = wp_current.slope_deg if wp_current.slope_deg is not None else 0.0

        # ====================================================================
        # Compute balance con v_current e radius
        # ====================================================================
        is_cornering = radius_m > 50.0  # Curva se R > 50m

        balance = compute_balance(
            mu_base=mu_base,
            aero=aero,
            aero_setup=aero_setup,
            v_ms=v_current,
            radius_m=radius_m,
            mass_kg=mass_kg,
            env=env,
            a_long_g=0.0,
        )

        # ====================================================================
        # Regime: throttle vs brake da waypoint (0-100%)
        # ====================================================================
        throttle_pct = wp_current.throttle_pct if wp_current.throttle_pct else 0.0
        brake_pct = wp_current.brake_pct if wp_current.brake_pct else 0.0

        # Se throttle > brake: accelera
        # Se brake > throttle: frena
        net_regime = throttle_pct - brake_pct

        if net_regime > 0:
            # Accelerazione
            _, a_net, _ = compute_drive_force(
                v_ms=v_current,
                aero=aero,
                balance=balance,
                mass_kg=mass_kg,
                pu_state=pu_state,
                radius_m=radius_m,
                is_cornering=is_cornering,
            )
            a_net *= (net_regime / 100.0)  # Scale 0-100%
        else:
            # Frenata
            # a_decel = compute_look_ahead_deceleration(...)
            a_net = -constants.MAX_BRAKE_DECEL_G * constants.G * (abs(net_regime) / 100.0)

        # Applica slope (gravità lungo il pendio)
        g_slope = constants.G * math.sin(math.radians(slope_deg))
        a_net -= g_slope

        # ====================================================================
        # Cinematica: v_new² = v² + 2*a*s
        # ====================================================================
        v_new_sq = v_current ** 2 + 2 * a_net * dist_step
        v_new = math.sqrt(max(0, v_new_sq))

        # Clamp a v_ref del waypoint (da telemetria)
        if wp_current.v_ref_kph is not None:
            v_ref_ms = wp_current.v_ref_kph / 3.6
            v_new = min(v_new, v_ref_ms * 1.05)  # Allow 5% margin

        # ====================================================================
        # Tempo step: dt = dist / v_avg
        # ====================================================================
        v_avg = (v_current + v_new) / 2.0
        if v_avg > constants.MIN_VELOCITY_MS:
            dt_step = dist_step / v_avg
        else:
            dt_step = 0.0

        dt_total += dt_step

        # Telemetry
        telemetry_points.append({
            "dist_m": wp_current.dist_m,
            "v_ms": v_current,
            "v_kph": v_current * 3.6,
            "a_net": a_net,
            "radius_m": radius_m,
            "throttle_pct": throttle_pct,
            "brake_pct": brake_pct,
            "dt": dt_step,
        })

        v_current = v_new

    v_exit = v_current
    return dt_total, v_exit, telemetry_points


def integrate_section_analytic(
    v_entry_ms: float,
    v_apex_ms: float,
    v_exit_ms: float,
    section: SectionContext,
    aero: PhysicsAeroParams,
    aero_setup: AeroSetup,
    mass_kg: float,
    mu_base: float,
    env: EnvContext,
    pu_state: PUState,
    brake_state: BrakeState,
) -> Tuple[float, float, List[Dict[str, Any]]]:
    """
    Integrazione analitica 50Hz con look-ahead (per circuiti senza HD).

    Loop:
    1. Calcola s_brake_needed per raggiungere v_apex
    2. Se dist_remaining ≤ s_brake * 1.05: FRENA
    3. Altrimenti: ACCELERA
    4. In curva: clamp v a v_apex
    5. Aggiorna v, d, t

    Args:
        v_entry_ms, v_apex_ms, v_exit_ms: Velocità [m/s]
        section: SectionContext (length_m, radius_m, ecc.)
        aero, aero_setup: Parametri aero
        mass_kg, mu_base, env, pu_state, brake_state: Contesti

    Returns:
        (dt_s, v_exit_actual, telemetry_points)
    """

    dt_total = 0.0
    v_current = v_entry_ms
    distance = 0.0
    telemetry_points = []
    section_length = section.length_m if section else 1000.0
    radius = section.radius_m if section and hasattr(section, 'radius_m') else 0.0

    max_iterations = 5000
    dt_step = constants.INTEGRATION_DT_S

    for iteration in range(max_iterations):

        distance_remaining = section_length - distance

        if distance_remaining < 1.0 or v_current < constants.MIN_VELOCITY_MS:
            break

        # ====================================================================
        # Compute balance
        # ====================================================================
        balance = compute_balance(
            mu_base=mu_base,
            aero=aero,
            aero_setup=aero_setup,
            v_ms=v_current,
            radius_m=radius,
            mass_kg=mass_kg,
            env=env,
            a_long_g=0.0,
        )

        # ====================================================================
        # Look-ahead: s_brake_needed per raggiungere v_apex
        # ====================================================================
        s_brake_needed = compute_braking_distance(
            v_entry_ms=v_current,
            v_target_ms=v_apex_ms,
            aero=aero,
            brake_state=brake_state,
            mass_kg=mass_kg,
            env=env,
        )

        # ====================================================================
        # Decisione FRENA vs ACCELERA
        # ====================================================================
        if distance_remaining <= s_brake_needed * 1.05:
            # Frena per raggiungere v_apex
            a_decel = compute_look_ahead_deceleration(
                v_current_ms=v_current,
                v_target_ms=v_apex_ms,
                distance_remaining_m=distance_remaining,
                aero=aero,
                brake_state=brake_state,
                mass_kg=mass_kg,
                env=env,
            )
            a_net = -a_decel
        else:
            # Accelera
            _, a_net, _ = compute_drive_force(
                v_ms=v_current,
                aero=aero,
                balance=balance,
                mass_kg=mass_kg,
                pu_state=pu_state,
                radius_m=radius,
                is_cornering=radius > 50.0,
            )

        # ====================================================================
        # Cinematica
        # ====================================================================
        v_new_sq = v_current ** 2 + 2 * a_net * (dt_step * v_current)
        v_new = math.sqrt(max(0, v_new_sq))

        # Clamp a v_apex se in curva
        if radius > 50.0:
            v_new = min(v_new, v_apex_ms)

        # ====================================================================
        # Tempo e distanza
        # ====================================================================
        v_avg = (v_current + v_new) / 2.0
        dist_traveled = v_avg * dt_step
        dt_total += dt_step
        distance += dist_traveled

        # Telemetry sample ogni 0.5s
        if iteration % 25 == 0:
            telemetry_points.append({
                "dist_m": distance,
                "v_ms": v_current,
                "v_kph": v_current * 3.6,
                "a_net": a_net,
                "dt": dt_step,
            })

        v_current = v_new

    v_exit_actual = v_current
    return dt_total, v_exit_actual, telemetry_points


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("section_integrator module loaded")
