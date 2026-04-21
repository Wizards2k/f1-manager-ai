"""
Engine Force Calculator - Modello V5.3 (flat) e V5.4 (stateful).
"""

import math
from typing import Dict, List, Any, Optional

# Import diretti dalle costanti
import sys
from pathlib import Path

# Aggiungi parent al path per import
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from core.constants import (
    G,
    ICE_IDLE_RPM,
    ICE_MAX_RPM,
    ICE_PEAK_POWER_KW,
    ERS_PEAK_POWER_KW,
    DRIVETRAIN_EFFICIENCY,
)

from integrator.pu_stateful_v2 import (
    PU_Context,
    get_optimal_gear,
    get_gear_ratio_from_n_gear,
    compute_f_engine_v54,
    update_thermal_state,
)


def compute_engine_force(
    velocity_ms: float,
    distance_m: float,
    waypoint: Dict[str, Any],
    next_waypoint: Dict[str, Any],
    mass_kg: float,
    tyre_compound: str,
    driver_skill: float,
    mu_base: Dict[str, float],
    throttle_pct: float,
    is_corner: bool,
    radius_m: float,
    ers_power_fraction: float,
    reference_pull: Optional[Dict[str, Any]],
    reference_pull_strength: float,
    pu_lookup_blend: float,
    pu_ctx: Optional[Any],
    waypoints: Optional[List[Dict[str, Any]]],
    waypoint_idx: int,
    dt_step: Optional[float] = None,
) -> float:
    """
    Calcola la forza motrice (F_engine) per un singolo waypoint.

    Supporta:
    - V5.3: Flat power model (legacy)
    - V5.4: PU stateful torque-based model
    - V5.0: Reference pull correction
    """

    if dt_step is None:
        dt_step = max(0.001, (next_waypoint.get("dist_m", waypoint.get("dist_m", 0) + 5) - waypoint.get("dist_m", 0)) / max(velocity_ms, 1.0))

    # Calcola rpm_fraction da Reference Pull (per-distanza)
    rpm_fraction = 1.0  # Default: potenza costante (V4)
    throttle_real_pct = throttle_pct  # Default: throttle dai waypoint
    rpm_current = 0.0  # V5.4: RPM for torque calculation
    gear_ratio_current = 1.0  # V5.4: Gear ratio for torque calculation

    if pu_lookup_blend > 0.0 and reference_pull is not None:
        ref_data = reference_pull.get("data", {})
        ref_dist = ref_data.get("dist_m", [])
        ref_rpm = ref_data.get("rpm", [])
        ref_throttle = ref_data.get("throttle_pct", [])
        ref_gear = ref_data.get("gear", [])

        if ref_dist and ref_rpm and len(ref_dist) > 1:
            # Interpola RPM reale alla distanza corrente
            current_dist = distance_m
            # Trova indice per interpolazione
            idx = 0
            for i in range(len(ref_dist) - 1):
                if ref_dist[i + 1] >= current_dist:
                    idx = i
                    break
            else:
                idx = len(ref_dist) - 2

            # Interpolazione lineare RPM
            if idx < len(ref_dist) - 1:
                d0 = ref_dist[idx]
                d1 = ref_dist[idx + 1]
                if d1 > d0:
                    t = (current_dist - d0) / (d1 - d0)
                    t = max(0.0, min(1.0, t))
                    rpm_real = ref_rpm[idx] * (1 - t) + ref_rpm[idx + 1] * t
                    # Throttle reale dalla telemetria (Opzione E+)
                    if ref_throttle and idx < len(ref_throttle) - 1:
                        throttle_real_pct = ref_throttle[idx] * (1 - t) + ref_throttle[idx + 1] * t
                        throttle_real_pct = max(0.0, min(100.0, throttle_real_pct))
                    # V5.4: nGear from reference pull
                    if ref_gear and idx < len(ref_gear) - 1:
                        n_gear_real = ref_gear[idx] * (1 - t) + ref_gear[idx + 1] * t
                        n_gear_int = max(1, min(8, int(round(n_gear_real))))
                        gear_ratio_current = get_gear_ratio_from_n_gear(n_gear_int)
                        rpm_current = rpm_real
                else:
                    rpm_real = ref_rpm[idx]
                    if ref_throttle and idx < len(ref_throttle):
                        throttle_real_pct = max(0.0, min(100.0, ref_throttle[idx]))
                    if ref_gear and idx < len(ref_gear):
                        n_gear_int = max(1, min(8, int(round(ref_gear[idx]))))
                        gear_ratio_current = get_gear_ratio_from_n_gear(n_gear_int)
                        rpm_current = rpm_real
            else:
                rpm_real = ref_rpm[idx]
                if ref_throttle and idx < len(ref_throttle):
                    throttle_real_pct = max(0.0, min(100.0, ref_throttle[idx]))
                if ref_gear and idx < len(ref_gear):
                    n_gear_int = max(1, min(8, int(round(ref_gear[idx]))))
                    gear_ratio_current = get_gear_ratio_from_n_gear(n_gear_int)
                    rpm_current = rpm_real

            # rpm_fraction: frazione di potenza disponibile a questo RPM
            # Potenza ICE segue curva: min a idle, max a peak RPM
            rpm_frac_real = max(0.3, min(1.0, (rpm_real - ICE_IDLE_RPM) / (ICE_MAX_RPM - ICE_IDLE_RPM)))
            # Blend tra potenza costante (rpm_frac=1.0) e RPM reale
            rpm_fraction = 1.0 + pu_lookup_blend * (rpm_frac_real - 1.0)

    # ============================================================
    # V5.4: PU Stateful Model (torque-based)
    # ============================================================
    f_engine = 0.0

    if pu_ctx is not None:
        # V5.4 mode: torque-based propulsive force

        # Get RPM and gear ratio
        if rpm_current > 0 and gear_ratio_current > 0:
            # From Reference Pull (Level 1)
            rpm = rpm_current
            gear_ratio = gear_ratio_current
        else:
            # Synthetic gearbox (Level 3 fallback)
            n_gear, gear_ratio, rpm = get_optimal_gear(velocity_ms)

        # Section kind for MGU-H factors
        section_kind = waypoint.get("section_kind", "Straight")

        # Lap progress for dynamic SOC floor
        total_dist = waypoint.get("dist_m", 0.0)
        lap_progress = min(1.0, total_dist / max(waypoint.get("circuit_length_m", 5000.0), 1.0))

        # Derive brake_pct for harvesting: if waypoint brake_pct is 0 (common in HD data),
        # estimate from throttle and look-ahead speed delta
        brake_pct_for_ers = waypoint.get("brake_pct", 0.0)
        if brake_pct_for_ers < 1 and throttle_real_pct < 20:
            # Look ahead 10-20 waypoints to find minimum speed in braking zone
            v_curr = waypoint.get("v_ref_kph", 0)
            v_min_ahead = v_curr
            look_ahead = min(20, len(waypoints) - waypoint_idx - 1) if waypoints else 1
            for la in range(1, look_ahead + 1):
                la_idx = waypoint_idx + la
                if la_idx < len(waypoints):
                    v_la = waypoints[la_idx].get("v_ref_kph", 0)
                    if v_la < v_min_ahead:
                        v_min_ahead = v_la
                    # Stop looking if speed starts increasing (end of braking zone)
                    if v_la > v_min_ahead * 1.02 and la > 3:
                        break

            if v_curr > 0 and v_min_ahead < v_curr * 0.95:
                # Significant speed drop ahead → braking zone
                speed_drop_frac = (v_curr - v_min_ahead) / v_curr
                # Scale: 10% drop = ~30% brake, 30% drop = ~80% brake
                brake_pct_for_ers = min(100, speed_drop_frac * 300)

        # Compute propulsive force using V5.4 model
        f_engine = compute_f_engine_v54(
            pu_ctx=pu_ctx,
            rpm=rpm,
            gear_ratio=gear_ratio,
            throttle_pct=throttle_real_pct,
            section_kind=section_kind,
            dt_s=dt_step,
            lap_progress=lap_progress,
            is_corner=is_corner,
            radius_m=radius_m,
            driver_skill=driver_skill,
            brake_pct=brake_pct_for_ers,
            drs_active=waypoint.get("drs_active", False),
            section_length_m=waypoint.get("section_length_m", 100.0),
            v_ms=velocity_ms,
            dist_m=waypoint.get("dist_m", 0.0),
        )

        # Update thermal state using instantaneous ERS power (not cumulative)
        # MGU-K power from last deploy + MGU-H power
        last_trace = pu_ctx.energy_trace[-1] if pu_ctx.energy_trace else {}
        mguk_power_kw = last_trace.get("deploy_mj", 0) * 1000.0 / max(dt_step, 0.001)
        mguh_power_kw = last_trace.get("mguh_direct_mj", 0) * 1000.0 / max(dt_step, 0.001)
        total_ers_power_kw = mguk_power_kw + mguh_power_kw
        update_thermal_state(pu_ctx, total_ers_power_kw, velocity_ms, dt_step)

        # Traction limit at low speed
        if velocity_ms <= 1.0:
            max_traction_force = mu_base.get(tyre_compound, 1.65) * mass_kg * G * 0.85
            f_engine = min(f_engine, max_traction_force)

        # Power limit: force cannot exceed P_max / v (same physics as V5.3)
        # This prevents V5.4 from having too much force at low speeds
        # compared to V5.3's power/v model. P_max = ICE peak + ERS peak.
        if velocity_ms > 1.0:
            ice_peak_kw = 750.0  # kW — approximate ICE peak power
            ers_peak_kw = pu_ctx.ers_output_kw if pu_ctx else 160.0
            p_max_kw = ice_peak_kw + ers_peak_kw
            max_force_from_power = p_max_kw * 1000.0 / velocity_ms
            f_engine = min(f_engine, max_force_from_power)

    else:
        # ============================================================
        # V5.3: Flat Power Model (legacy, backward compatible)
        # ============================================================
        effective_pu_kw = ICE_PEAK_POWER_KW + ERS_PEAK_POWER_KW * ers_power_fraction

        if is_corner:
            # In curva: potenza ridotta per trazione
            # Più curva stretta = meno potenza disponibile
            corner_factor = min(1.0, 1000.0 / max(radius_m, 100.0))
            power_available = effective_pu_kw * 1000 * rpm_fraction * (throttle_real_pct / 100.0) * corner_factor
        else:
            # In rettilineo: potenza massima
            power_available = effective_pu_kw * 1000 * rpm_fraction * (throttle_real_pct / 100.0)

        # Efficienza trasmissione e driver skill
        power_available *= DRIVETRAIN_EFFICIENCY
        power_available *= driver_skill

        # Forza motrice = Potenza / Velocità
        if velocity_ms > 1.0:
            f_engine = power_available / velocity_ms
        else:
            # A basse velocità (uscita curva), limita potenza per trazione
            f_engine = power_available / 1.0
            # Limita accelerazione per evitare wheel spin
            # FIX V4.4: Aumentato da 0.60 a 0.85 per permettere accelerazione in uscita curva
            max_traction_force = mu_base.get(tyre_compound, 1.65) * mass_kg * G * 0.85  # 85% grip posteriore
            f_engine = min(f_engine, max_traction_force)

    # ============================================================
    # V5.0: REFERENCE PULL - Correzione forza motrice da telemetria reale
    # ============================================================
    if reference_pull_strength > 0.0 and reference_pull is not None:
        ref_data = reference_pull.get("data", {})
        ref_dist = ref_data.get("dist_m", [])
        ref_speed = ref_data.get("speed_kph", [])
        if ref_dist and ref_speed and len(ref_dist) > 0:
            # Interpola velocità reale alla distanza corrente
            current_dist = distance_m
            ref_dist_arr = ref_dist
            ref_speed_arr = ref_speed
            # Trova indice più vicino
            idx = 0
            for i in range(len(ref_dist_arr) - 1):
                if ref_dist_arr[i + 1] >= current_dist:
                    idx = i
                    break
            else:
                idx = len(ref_dist_arr) - 2

            # Interpolazione lineare
            if idx < len(ref_dist_arr) - 1:
                d0 = ref_dist_arr[idx]
                d1 = ref_dist_arr[idx + 1]
                if d1 > d0:
                    t = (current_dist - d0) / (d1 - d0)
                    t = max(0.0, min(1.0, t))
                    v_ref_kph_real = ref_speed_arr[idx] * (1 - t) + ref_speed_arr[idx + 1] * t
                else:
                    v_ref_kph_real = ref_speed_arr[idx]
            else:
                v_ref_kph_real = ref_speed_arr[idx]

            v_ref_ms_real = v_ref_kph_real / 3.6
            v_sim_ms = velocity_ms

            # Correzione proporzionale alla differenza di velocità
            # Se la simulazione è più lenta del reale → aumenta forza motrice
            # Se la simulazione è più veloce → riduci forza motrice
            v_error = v_ref_ms_real - v_sim_ms  # Positivo = sim troppo lento

            # La correzione è proporzionale all'errore e alla massa
            # F_correction = strength * m * (v_error / v_ref) * g
            # Questo dà una correzione graduale che non domina la fisica
            if abs(v_ref_ms_real) > 1.0:
                f_correction = (reference_pull_strength * mass_kg * v_error
                                / max(v_ref_ms_real, 10.0) * G)
                # Limita la correzione a ±20% della forza motrice
                max_correction = abs(f_engine) * 0.20
                f_correction = max(-max_correction, min(max_correction, f_correction))
                f_engine += f_correction

    return f_engine
