"""
Grip Model - Calcolo grip totale laterale e longitudinale.
"""

import math
from typing import Dict, Any, Optional

from core.constants import G, RHO_SEA_LEVEL


def compute_grip_forces(
    velocity_ms: float,
    mass_kg: float,
    tyre_compound: str,
    driver_skill: float,
    mu_base: Dict[str, float],
    aero_forces: Any,
    aero_calibration: Optional[Dict[str, Any]],
    reference_pull: Optional[Dict[str, Any]],
    suspension_effects: Optional[Dict[str, float]],
    waypoint: Dict[str, Any],
    is_corner: bool,
    radius_m: float,
    is_throttle: bool,
    is_braking: bool,
) -> Dict[str, float]:
    """
    Calcola le forze di grip laterale e longitudinale.

    Returns:
        dict con chiavi:
        - mu_base_val: grip coefficient finale
        - f_grip_total_lateral: grip laterale totale [N]
        - f_grip_total_longitudinal: grip longitudinale totale [N]
        - f_grip_total: grip attivo (dipende da stato frenata/accelerazione/curva) [N]
        - v_max_corner_ms: velocità max in curva [m/s]
        - longitudinal_traction_bonus: fattore bonus trazione
    """

    # Grip base dal compound (senza penalità empiriche)
    mu_base_val = mu_base.get(tyre_compound, 1.65)

    # V5.0: Se abbiamo mu_mechanical dalla calibrazione aero, usiamo quello.
    aero_cal_mu_mechanical = None
    if aero_calibration is not None:
        aero_cal_mu_mechanical = aero_calibration.get("mu_mechanical")
        if aero_cal_mu_mechanical is not None:
            try:
                aero_cal_mu_mechanical = float(aero_cal_mu_mechanical)
            except (TypeError, ValueError):
                aero_cal_mu_mechanical = None

    if aero_cal_mu_mechanical is not None and aero_cal_mu_mechanical > 0:
        calibration_compound = "C3"  # Default fallback
        if aero_calibration is not None:
            calibration_compound = aero_calibration.get("calibration_compound", "C3")
        cal_mu = mu_base.get(calibration_compound, 1.82)
        target_mu = mu_base.get(tyre_compound, 1.65)
        compound_ratio = target_mu / cal_mu if cal_mu > 0 else 1.0
        mu_base_val = aero_cal_mu_mechanical * compound_ratio
    elif reference_pull is not None:
        ref_mu_mechanical = reference_pull.get("mu_mechanical", 0.0)
        if 1.5 < ref_mu_mechanical < 2.0:
            compound_scale = mu_base_val / mu_base.get(tyre_compound, 1.65)
            mu_base_val = ref_mu_mechanical * compound_scale

    # Applica track_grip_factor da telemetry_mu (ora è fisso per circuito)
    track_grip_factor = waypoint.get('telemetry_mu', 1.0)
    if track_grip_factor is not None and track_grip_factor > 0:
        mu_base_val *= track_grip_factor

    # Applica driver skill (pilota migliore → sfrutta meglio il grip)
    mu_base_val *= driver_skill

    # Applica effetto sospensioni sul grip meccanico
    susp_fx = suspension_effects or {}
    mu_base_val *= susp_fx.get('mechanical_grip_factor', 1.0)

    # Calcola downforce (contata UNA SOLA VOLTA qui)
    f_downforce = aero_forces.f_downforce

    # Carico verticale totale = peso + downforce
    f_vertical = mass_kg * G + f_downforce  # N
    f_vertical_kn = f_vertical / 1000.0  # kN

    # ============================================================
    # PHYSICS FIX V4.2 #2: Load Sensitivity Separata (Long vs Lat)
    # ============================================================
    load_sensitivity_k = 0.010  # FIX V4.16: era 0.00008, poi 0.003, poi 0.006

    # Load factor per grip laterale (curva) - full sensitivity
    lat_load_factor = 1.0 - (load_sensitivity_k * f_vertical_kn)
    lat_load_factor = max(0.75, min(1.0, lat_load_factor))  # Clamp tra 0.75 e 1.0

    # Load factor per grip longitudinale (trazione/frenata) - half sensitivity
    long_load_factor = 1.0 - (load_sensitivity_k * 0.5 * f_vertical_kn)
    long_load_factor = max(0.85, min(1.0, long_load_factor))  # Clamp tra 0.85 e 1.0

    # Grip totale laterale (usato per v_max in curva)
    f_grip_total_lateral = mu_base_val * f_vertical * lat_load_factor

    # Applica penalità ARB sospensioni sul grip laterale
    corner_grip_penalty = susp_fx.get('corner_grip_penalty', 0.0)
    if corner_grip_penalty > 0.0:
        f_grip_total_lateral *= (1.0 - corner_grip_penalty)

    # Grip totale longitudinale (usato per trazione/frenata)
    f_grip_total_longitudinal = mu_base_val * f_vertical * long_load_factor

    # ============================================================
    # PHYSICS FIX V4.3 #2: Traction Bonus (Differenziale - Exit Speed)
    # ============================================================
    v_kph = velocity_ms * 3.6
    steering_angle_deg = abs(waypoint.get('steering_angle_deg', 0.0))

    longitudinal_traction_bonus = 1.0
    # Applica solo per curve strette (Monaco/Suzuka), non per Monza
    # FIX V4.4: Esteso da 120 a 160 km/h per coprire marce medie di circuiti veloci (Spa, Silverstone)
    if v_kph < 160.0 and steering_angle_deg < 25.0 and is_throttle and radius_m < 60.0 and radius_m > 0.0:
        # Bonus del 20% per simulare differenziale che massimizza spinta
        longitudinal_traction_bonus = 1.20
        f_grip_total_longitudinal *= longitudinal_traction_bonus

    # Load transfer in frenata/accelerazione (usa grip longitudinale)
    if is_braking:
        # Frenata: load transfer anteriore → grip posteriore ridotto
        braking_stability = susp_fx.get('braking_stability_factor', 1.0)
        load_transfer_factor = 0.85 * braking_stability  # -15% base + penalità sospensioni
        f_grip_total = f_grip_total_longitudinal * load_transfer_factor
    elif is_throttle:
        # Accelerazione: load transfer posteriore → grip posteriore aumentato
        load_transfer_factor = 1.05  # +5% grip posteriore
        f_grip_total = f_grip_total_longitudinal * load_transfer_factor
    else:
        # In curva costante, usa grip laterale
        f_grip_total = f_grip_total_lateral

    # ============================================================
    # 5. VELOCITÀ MASSIMA IN CURVA - Solo dalla fisica (grip limit)
    # ============================================================
    if is_corner:
        cu = min(0.95, 0.35 + radius_m / 150.0)
        v_max_corner_ms = math.sqrt(
            f_grip_total_lateral * cu * radius_m / mass_kg
        )
    else:
        v_max_corner_ms = 999.0  # Nessun limite in rettilineo

    return {
        "mu_base_val": mu_base_val,
        "f_grip_total_lateral": f_grip_total_lateral,
        "f_grip_total_longitudinal": f_grip_total_longitudinal,
        "f_grip_total": f_grip_total,
        "v_max_corner_ms": v_max_corner_ms,
        "longitudinal_traction_bonus": longitudinal_traction_bonus,
    }
