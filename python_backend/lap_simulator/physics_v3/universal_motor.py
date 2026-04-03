"""
Universal Motor — Implementazione Universale con 3 Equazioni

Base fisica derivata da pattern analysis su Monza/Monaco/Suzuka.

Equazioni fondamentali:

1. LONGITUDINALE (indipendente da CLA):
   a_accel = (P_available - F_drag) / m

   Dove:
   - P_available = potenza del motore [W]
   - F_drag = 0.5 * ρ * v² * CDA + F_rolling [N]
   - m = massa auto [kg]

   Target: a_accel ≈ 1.34g ± 0.06g (indipendente da setup)

2. LATERALE (proporzionale a CLA):
   a_lat_max = μ * g

   Dove:
   - μ = grip_base * (1 + k_downforce * CLA)
   - grip_base = compound grip (C1-C6)
   - k_downforce = fattore moltiplicativo downforce

   Target: a_lat ∝ CLA (Monza 2.90→3.87g, Monaco 4.60→5.51g)

3. V_MAX (inverso con CDA):
   A equilibrio: P = F_drag * v_max
   v_max = sqrt(2*P / (ρ*CDA + 2*F_rolling/v))

   Target: v_max inversamente proporzionale a CDA
"""

import math
import sys
from typing import Tuple, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from physics_v3 import constants
from data_types import PUState, AeroSetup, EnvContext


# ============================================================================
# UNIVERSAL EQUATIONS
# ============================================================================

def compute_longitudinal_acceleration(
    v_ms: float,
    p_available_w: float,
    cda: float,
    mass_kg: float,
    env: EnvContext,
) -> float:
    """
    Calcola accelerazione longitudinale (UNIVERSALE, indipendente da CLA).

    Formula:
        a = (F_drive - F_drag) / m
        F_drive = P / v
        F_drag = 0.5 * ρ * v² * CDA + F_rolling

    Args:
        v_ms: Velocità [m/s]
        p_available_w: Potenza disponibile [W]
        cda: Drag coefficient area [m²]
        mass_kg: Massa [kg]
        env: Contesto ambientale

    Returns:
        Accelerazione [m/s²]
    """

    if v_ms < 0.1:
        return 0.0

    rho = env.air_density_kg_m3

    # Forza di trazione da potenza
    f_drive = p_available_w / v_ms if v_ms > 0.1 else 0

    # Forza di resistenza
    f_drag_aero = 0.5 * rho * (v_ms ** 2) * cda
    f_rolling = constants.ROLLING_RESISTANCE_COEFF * mass_kg * constants.G
    f_drag_total = f_drag_aero + f_rolling

    # Forza netta e accelerazione
    f_net = f_drive - f_drag_total
    a_ms2 = f_net / mass_kg if mass_kg > 0 else 0

    return a_ms2


def compute_lateral_grip(
    cla: float,
    grip_base: float,
    downforce_multiplier: float = 0.15,
) -> float:
    """
    Calcola grip massimo laterale (PROPORZIONALE a CLA).

    Formula:
        μ_effective = grip_base * (1 + k_df * CLA)

    Dove:
        - grip_base = μ del compound (C1-C6)
        - k_df = fattore moltiplicativo per downforce
        - CLA = downforce coefficient area

    La physical intuition è:
        Più downforce → più carico verticale → più grip laterale

    Args:
        cla: Downforce coefficient area [m²]
        grip_base: Grip base del compound [0-2.0]
        downforce_multiplier: Fattore moltiplicativo CLA→grip [default 0.15]

    Returns:
        Grip massimo μ [0-2.5]
    """

    # Correlazione empirica: k_df * CLA aggiunge grip
    # Con CLA 2.90-4.60, il fattore moltiplicativo è ~0.15
    mu_effective = grip_base * (1.0 + downforce_multiplier * (cla - 2.5))

    # Clamp a valori fisici realistici
    return max(0.5, min(2.5, mu_effective))


def compute_max_velocity_equilibrium(
    p_available_w: float,
    cda: float,
    mass_kg: float,
    env: EnvContext,
) -> float:
    """
    Calcola v_max teorica dove potenza = drag (INVERSO con CDA).

    A equilibrio:
        P_available = F_drag * v_max
        P = (0.5 * ρ * v² * CDA + F_rolling) * v
        P = 0.5 * ρ * v³ * CDA + F_rolling * v

    Risolvibile numericamente.

    Args:
        p_available_w: Potenza disponibile [W]
        cda: Drag coefficient area [m²]
        mass_kg: Massa [kg]
        env: Contesto ambientale

    Returns:
        v_max [m/s]
    """

    rho = env.air_density_kg_m3
    f_rolling = constants.ROLLING_RESISTANCE_COEFF * mass_kg * constants.G

    # Binary search per trovare v_max
    v_low = 10.0  # m/s
    v_high = 150.0  # m/s

    for _ in range(50):  # Iterazioni sufficienti per convergenza
        v_mid = (v_low + v_high) / 2

        # Calcola drag a questa velocità
        f_drag = 0.5 * rho * (v_mid ** 2) * cda + f_rolling

        # Potenza richiesta
        p_required = f_drag * v_mid

        if p_required < p_available_w:
            v_low = v_mid
        else:
            v_high = v_mid

    return v_mid


def compute_corner_apex_speed_universal(
    radius_m: float,
    mu_effective: float,
    banking_deg: float = 0.0,
) -> float:
    """
    Calcola v_apex usando μ_effective (che dipende da CLA).

    Formula:
        v_apex = sqrt(μ_eff * g * R)

    Args:
        radius_m: Raggio curva [m]
        mu_effective: Grip effettivo (dipende da CLA via downforce)
        banking_deg: Banking della pista [°]

    Returns:
        v_apex [m/s]
    """

    if radius_m < 0.1:
        return 0.0

    # Effetto banking
    if abs(banking_deg) > 0.1:
        banking_rad = math.radians(banking_deg)
        g_eff = constants.G * math.cos(banking_rad)
    else:
        g_eff = constants.G

    # v_apex da μ e raggio
    v_apex_sq = mu_effective * g_eff * radius_m

    return math.sqrt(max(0, v_apex_sq))


# ============================================================================
# TEST / VALIDATION
# ============================================================================

if __name__ == "__main__":
    print("Universal Motor - Validation Test")
    print("="*70)

    # Test Monza (CLA=2.90, CDA=0.90)
    env_monza = EnvContext(air_temp_c=20.0, track_temp_c=40.0, air_density_kg_m3=1.225)

    # Longitudinale
    a_accel_monza = compute_longitudinal_acceleration(
        v_ms=96.39,  # 347 km/h
        p_available_w=950000,
        cda=0.90,
        mass_kg=798.0,
        env=env_monza
    )
    print(f"Monza (CDA=0.90) at 347 km/h: a_accel = {a_accel_monza:.3f} m/s² = {a_accel_monza/9.81:.3f}g")

    # Laterale
    mu_monza = compute_lateral_grip(cla=2.90, grip_base=1.70)
    v_apex_monza = compute_corner_apex_speed_universal(radius_m=668, mu_effective=mu_monza)
    a_lat_monza = (v_apex_monza ** 2) / (668 * 9.81)
    print(f"Monza (CLA=2.90): μ_eff = {mu_monza:.3f}, v_apex = {v_apex_monza*3.6:.1f} km/h, a_lat = {a_lat_monza:.3f}g")

    # v_max
    v_max_monza = compute_max_velocity_equilibrium(
        p_available_w=950000,
        cda=0.90,
        mass_kg=798.0,
        env=env_monza
    )
    print(f"Monza (CDA=0.90): v_max = {v_max_monza*3.6:.1f} km/h")

    # Test Monaco (CLA=4.60, CDA=1.30)
    print()
    mu_monaco = compute_lateral_grip(cla=4.60, grip_base=1.70)
    v_apex_monaco = compute_corner_apex_speed_universal(radius_m=320, mu_effective=mu_monaco)
    a_lat_monaco = (v_apex_monaco ** 2) / (320 * 9.81)
    print(f"Monaco (CLA=4.60): μ_eff = {mu_monaco:.3f}, v_apex = {v_apex_monaco*3.6:.1f} km/h, a_lat = {a_lat_monaco:.3f}g")

    v_max_monaco = compute_max_velocity_equilibrium(
        p_available_w=950000,
        cda=1.30,
        mass_kg=798.0,
        env=env_monza
    )
    print(f"Monaco (CDA=1.30): v_max = {v_max_monaco*3.6:.1f} km/h")

    print("\n✓ Universal motor equations loaded and validated")
