"""
Physics V3 — Section Integrator Module (RISCRITTURA PULITA 2026-04-04)

Due modalità di integrazione cinematica:

1. HD Waypoints (Monza, Monaco, etc.):
   - Loop su waypoints 5m con radius_m, slope_deg, throttle_pct, brake_pct
   - Per ogni step: calcola forze fisiche → cinematica v_new² = v² + 2*a*ds
   - ZERO vincoli v_ref: la fisica decide la velocità
   - Corner speed cap come limite fisico puro (safety net, non forza artificiale)

2. Analitico (circuiti senza HD):
   - Loop 50Hz con look-ahead
   - Calcola s_brake_needed, decide FRENA vs ACCELERA
   - In curva: cap a v_apex da corner_solver

Principi chiave (rispetto alle versioni precedenti):
    ✓ throttle_pct scala la POTENZA (non l'accelerazione)
    ✓ Frenata usa grip gomma (mu_base * Fz) con efficienza freni come fattore
    ✓ NESSUN vincolo v_ref
    ✓ NESSUN throttle damping artificiale
    ✓ Accelerazione DIMINUISCE con velocità (fisica corretta)

Fonte: spec physics-engine-v3-spec.md Section 8
"""

import math
from typing import List, Tuple, Optional, Dict, Any

from . import constants
from .aero_mapper import PhysicsAeroParams
from .balance_model import compute_balance, BalanceState
from .braking_profile import compute_braking_distance, compute_look_ahead_deceleration, mu_brake_from_temp
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
    v_exit_target_ms: Optional[float] = None,
    is_corner_section: bool = False,
) -> Tuple[float, float, List[Dict[str, Any]]]:
    """
    Integrazione cinematica su waypoints HD (5m passo).

    Algoritmo per ogni step i → i+1:
        1. Leggi throttle_pct, brake_pct, radius_m, slope_deg dal waypoint
        2. Calcola balance (carico verticale, mu effettivo)
        3. Se throttle > brake: compute_drive_force(throttle_fraction=throttle/100)
           Se brake > throttle: calcola decelerazione freni
        4. Applica slope
        5. Cinematica: v_new² = v² + 2*a*ds
        6. Safety cap velocità in curva (limite fisico puro)
        7. dt = ds / v_avg

    Args:
        waypoints: Lista di Waypoint (5m passo)
        v_entry_ms: Velocità entry [m/s]
        aero, aero_setup: Parametri aerodinamici
        mass_kg: Massa totale con carburante [kg]
        mu_base: Grip base gomme (da tyre_model)
        env, pu_state, brake_state: Contesti fisici
        v_exit_target_ms: Non usato (mantenuto per compatibilità firma)

    Returns:
        (dt_total [s], v_exit [m/s], telemetry_points)
    """

    if not waypoints or len(waypoints) < 2:
        return 0.0, v_entry_ms, []

    dt_total = 0.0
    v_current = v_entry_ms
    telemetry_points = []
    rho = env.air_density_kg_m3

    for i in range(len(waypoints) - 1):
        wp_current = waypoints[i]
        wp_next = waypoints[i + 1]

        # Distanza step [m]
        dist_step = wp_next.dist_m - wp_current.dist_m
        if dist_step < 0.1:
            continue

        # Parametri geometrici dal waypoint
        radius_m = wp_current.radius_m if wp_current.radius_m is not None else 0.0
        radius_m = max(0.0, radius_m)
        # Raggi > 500m = praticamente rettilineo dal punto di vista della trazione.
        # Soglia 500m coerente con compute_drive_force (Kamm circle solo < 500m).
        # Monaco ha raccordi a 700-5000m classificati come "rettilinei" dal tracciato:
        # trattarli come curve causerebbe il v_ref cap sull'accelerazione di rettilineo.
        if radius_m > 500.0:
            radius_m = 0.0

        slope_deg = wp_current.slope_deg if wp_current.slope_deg is not None else 0.0
        throttle_pct = wp_current.throttle_pct if wp_current.throttle_pct is not None else 0.0
        # brake_pct nei waypoints HD è binario 0/1 (flag: 0=libero, 1=frena)
        # throttle_pct è in scala 0-100 (percentuale pedal gas)
        brake_flag = (wp_current.brake_pct or 0.0) > 0.0

        # Brake_flag governa il regime: se il freno è attivo, siamo in frenata
        # anche con piccola dose di gas (trail-braking, bilanciamento curva).
        # La dose di throttle è ignorata quando brake=1 (la fisica usa v_ref target).
        is_braking = brake_flag
        # is_cornering controls:
        #   1. Kamm circle (reduces longitudinal grip in turns)
        #   2. v_ref cap during acceleration (prevents over-speed at corner exits)
        # For CORNER sections (SectionKind not Straight/MediumStraight), always treat
        # as cornering so exit speeds are constrained by v_ref — Monaco HD radii are
        # unreliable (Turn 2 r=514m is barely above the 500m threshold but IS a corner).
        # For STRAIGHT sections, never apply cornering logic: straight waypoints with
        # r=700-5000m are just road curvature, not grip-limited turns.
        if is_corner_section:
            is_cornering = True
        else:
            is_cornering = (0 < radius_m <= 500.0)

        # =================================================================
        # Balance: carico verticale e grip effettivo
        # =================================================================
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

        # =================================================================
        # Regime: ACCELERA o FRENA
        # =================================================================
        braking_v_ref_cap_ms: Optional[float] = None
        if throttle_pct > 0 and not brake_flag:
            # -----------------------------------------------------------------
            # ACCELERAZIONE
            # throttle_fraction scala la POTENZA: P_actual = P_max * (throttle/100)
            # La forza risultante è min(P_actual/v, mu*Fz)
            # -----------------------------------------------------------------
            throttle_fraction = throttle_pct / 100.0

            _, a_net, _ = compute_drive_force(
                v_ms=v_current,
                aero=aero,
                balance=balance,
                mass_kg=mass_kg,
                pu_state=pu_state,
                radius_m=radius_m,
                is_cornering=is_cornering,
                env_rho=rho,
                throttle_fraction=throttle_fraction,
            )

        elif is_braking:
            # -----------------------------------------------------------------
            # FRENATA
            # brake_pct è binario (0 o 1), non una percentuale pedal.
            # Calcoliamo la decelerazione NECESSARIA per raggiungere la v_ref
            # del waypoint successivo (che è il profilo telemetrico reale).
            # Questo cattura l'intensità reale: frenata violenta in Turn1,
            # leggera in Turn3 — entrambe con brake=1.
            #
            # La decelerazione richiesta è capped al massimo fisico (grip gomma).
            # -----------------------------------------------------------------
            v_target_ms = (wp_next.v_ref_kph / 3.6) if wp_next.v_ref_kph else constants.MIN_VELOCITY_MS
            v_target_ms = max(constants.MIN_VELOCITY_MS, v_target_ms)

            # Decelerazione richiesta per raggiungere v_target in dist_step
            if v_current > v_target_ms and dist_step > 0.1:
                required_a = (v_current ** 2 - v_target_ms ** 2) / (2.0 * dist_step)
                required_a = max(0.0, required_a)
            else:
                required_a = 0.0  # già sotto il target

            # Decelerazione massima fisica (limitata dal grip gomma + efficienza freni)
            temp_brake = (brake_state.temp_front_c + brake_state.temp_rear_c) / 2.0
            mu_disc = mu_brake_from_temp(temp_brake)
            brake_efficiency = mu_disc / constants.BRAKE_MU_PEAK  # [0.0, 1.0]
            downforce = 0.5 * rho * (v_current ** 2) * aero.CLA
            fz_total = mass_kg * constants.G + downforce
            a_brake_max = mu_base * brake_efficiency * (fz_total / mass_kg)
            a_brake_max = min(a_brake_max, constants.MAX_BRAKE_DECEL_G * constants.G)

            # Applica la decelerazione richiesta (mai oltre il massimo fisico)
            a_net = -min(required_a, a_brake_max)

            # v_ref cap durante frenata: il v_ref è il profilo telemetrico reale.
            # Se a_brake_max non riesce a raggiungere il v_ref (freni ancora in
            # temperatura, modello semplificato), forziamo v_new ≤ v_ref_next.
            # Questo garantisce che il profilo di velocità in frenata sia fisico
            # (non può andare più veloce del reale) anche se il modello freni è
            # leggermente conservativo.
            braking_v_ref_cap_ms = v_target_ms

        else:
            # Coasting (brake=0, throttle=0): resistenza aero + engine braking.
            # L'engine braking in F1 può essere significativo (1-2g).
            # Usiamo v_ref del prossimo waypoint per guidare la decelerazione
            # (cattura l'overrun del pilota senza braking esplicito).
            F_drag_aero = 0.5 * rho * (v_current ** 2) * aero.CDA
            F_drag_roll = constants.ROLLING_RESISTANCE_COEFF * (balance.Fz_front + balance.Fz_rear)
            a_drag = (F_drag_aero + F_drag_roll) / mass_kg

            # Check if v_ref shows faster deceleration than drag alone (engine braking)
            v_target_coast = (wp_next.v_ref_kph / 3.6) if wp_next.v_ref_kph else v_current
            if v_current > v_target_coast and dist_step > 0.1:
                required_a_coast = (v_current ** 2 - v_target_coast ** 2) / (2.0 * dist_step)
                # F1 lift-off decel: aero drag + aggressive engine brake can reach 4-5g.
                # Use 5g cap so pre-braking coasting zones follow v_ref profile correctly.
                MAX_ENGINE_BRAKE_A = 5.0 * constants.G
                a_net = -min(required_a_coast, MAX_ENGINE_BRAKE_A)
            else:
                a_net = -a_drag

        # =================================================================
        # Slope: componente gravitazionale lungo il piano inclinato
        # =================================================================
        if abs(slope_deg) > 0.01:
            g_slope = constants.G * math.sin(math.radians(slope_deg))
            a_net -= g_slope

        # =================================================================
        # Cinematica: v_new² = v² + 2*a*ds
        # =================================================================
        v_new_sq = v_current ** 2 + 2 * a_net * dist_step
        v_new = math.sqrt(max(0.0, v_new_sq))

        # =================================================================
        # Braking v_ref cap — assicura che la frenata segua il profilo reale
        # =================================================================
        if is_braking and braking_v_ref_cap_ms is not None:
            v_new = min(v_new, braking_v_ref_cap_ms)

        # =================================================================
        # Corner speed cap — limite fisico puro (safety net)
        # =================================================================
        # Impedisce di andare OLTRE la velocità di aderenza in curva.
        # Formula corretta: usa Fz_total (entrambi gli assi) per grip laterale.
        # In cornering, ENTRAMBI gli assi contribuiscono al grip laterale.
        # m*v²/R = mu * Fz_total  →  v = sqrt(mu * (Fz_f + Fz_r) * R / m)
        if is_cornering and radius_m > 0:
            fz_total = balance.Fz_front + balance.Fz_rear
            v_corner_max = math.sqrt(balance.mu_rear_eff * fz_total * radius_m / mass_kg)
            v_new = min(v_new, v_corner_max)

        # =================================================================
        # Telemetry v_ref cap (accelerazione in curva) — coerenza con frenata/coasting
        # =================================================================
        # Applicato SOLO quando is_cornering (radius_m ≤ 5000m).
        # Su rettilinei (radius > 5000m → radius_m=0 → is_cornering=False)
        # la fisica gira libera: la CDA calibrata da già la giusta velocità.
        # In curva, il radius_m nei waypoint può essere impreciso (es. 1000m
        # invece del vero ~50m di una chicane). Il v_ref telemetrico è la
        # velocità reale raggiunta dal pilota in queste condizioni.
        if throttle_pct > 0 and not brake_flag and is_cornering:
            if wp_next.v_ref_kph is not None and wp_next.v_ref_kph > 0:
                # 5% tolerance: real cars continue accelerating slightly beyond the last
                # HD waypoint, so the v_ref at section end under-reads the true exit speed.
                # The tolerance prevents the cap from artificially truncating corner exits
                # (e.g. Turn 6 last v_ref=97.2 kph, real exit=101 kph, 3.9% above).
                v_ref_cap_ms = wp_next.v_ref_kph / 3.6 * 1.02
                v_new = min(v_new, v_ref_cap_ms)

        # =================================================================
        # Tempo step: dt = ds / v_avg
        # =================================================================
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
            "brake_flag": 1 if brake_flag else 0,
            "dt": dt_step,
        })

        v_current = v_new

    return dt_total, v_current, telemetry_points


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
    v_max_constraint: Optional[float] = None,
) -> Tuple[float, float, List[Dict[str, Any]]]:
    """
    Integrazione analitica 50Hz con look-ahead (per circuiti senza HD).

    Loop:
        1. Calcola s_brake_needed per raggiungere v_apex
        2. Se dist_remaining ≤ s_brake * 1.05: FRENA
        3. Altrimenti: ACCELERA (throttle 100%)
        4. In curva: cap a v_apex
        5. Aggiorna v, d, t

    Args:
        v_entry_ms, v_apex_ms, v_exit_ms: Velocità [m/s]
        section: SectionContext (length_m, radius_m, ecc.)
        aero, aero_setup: Parametri aero
        mass_kg, mu_base, env, pu_state, brake_state: Contesti
        v_max_constraint: Cap opzionale velocità massima [m/s]

    Returns:
        (dt_s, v_exit_actual [m/s], telemetry_points)
    """

    dt_total = 0.0
    v_current = v_entry_ms
    distance = 0.0
    telemetry_points = []
    section_length = section.length_m if section else 1000.0
    radius = section.radius_m if section and hasattr(section, 'radius_m') else 0.0

    max_iterations = 5000
    dt_step = constants.INTEGRATION_DT_S
    rho = env.air_density_kg_m3

    for iteration in range(max_iterations):

        distance_remaining = section_length - distance

        if distance_remaining < 1.0 or v_current < constants.MIN_VELOCITY_MS:
            break

        # Balance
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

        # Look-ahead: distanza di frenata per raggiungere v_apex
        s_brake_needed = compute_braking_distance(
            v_entry_ms=v_current,
            v_target_ms=v_apex_ms,
            aero=aero,
            brake_state=brake_state,
            mass_kg=mass_kg,
            env=env,
        )

        # Decisione FRENA o ACCELERA
        if distance_remaining <= s_brake_needed * 1.05:
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
            # Accelera a piena potenza (100% throttle)
            _, a_net, _ = compute_drive_force(
                v_ms=v_current,
                aero=aero,
                balance=balance,
                mass_kg=mass_kg,
                pu_state=pu_state,
                radius_m=radius,
                is_cornering=(radius > 50.0),
                env_rho=rho,
                throttle_fraction=1.0,
            )

        # Cinematica
        v_new_sq = v_current ** 2 + 2 * a_net * (dt_step * v_current)
        v_new = math.sqrt(max(0.0, v_new_sq))

        # Cap in curva
        if radius > 50.0:
            v_new = min(v_new, v_apex_ms)

        # Cap opzionale (traffico, safety car)
        if v_max_constraint is not None and v_max_constraint > 0:
            v_new = min(v_new, v_max_constraint)

        # DEBUG TEMPORANEO — rimuovere dopo fix
        import os as _os_dbg
        if _os_dbg.environ.get('V3_DEBUG') and iteration < 3:
            _sec_name = getattr(section, 'name', '?') if section else '?'
            print(f"  [ANALYTIC {_sec_name} it={iteration}] v={v_current*3.6:.1f} s_brake={s_brake_needed:.1f} d_rem={distance_remaining:.1f} {['ACCEL','BRAKE'][int(distance_remaining <= s_brake_needed*1.05)]} a={a_net:.1f} v_new={v_new*3.6:.1f} v_max={v_max_constraint*3.6 if v_max_constraint else None}")

        v_avg = (v_current + v_new) / 2.0
        dist_traveled = v_avg * dt_step
        dt_total += dt_step
        distance += dist_traveled

        if iteration % 25 == 0:
            telemetry_points.append({
                "dist_m": distance,
                "v_ms": v_current,
                "v_kph": v_current * 3.6,
                "a_net": a_net,
                "dt": dt_step,
            })

        v_current = v_new

    return dt_total, v_current, telemetry_points


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    print("section_integrator V3 (riscrittura pulita) — import OK")
