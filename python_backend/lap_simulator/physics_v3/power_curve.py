"""
Power Curve Model — Potenza ICE in funzione di RPM/velocità

In F1 2025, la potenza NON è costante a tutte le velocità:
- A basse velocità (bassi RPM): potenza massima
- A medie velocità (10,500-11,000 RPM): PICCO di potenza
- Ad alte velocità (11,000-15,000 RPM): potenza DIMINUISCE

Questo è critico per il rettilineo DRS dove il motore raggiunge RPM limite.
"""

import math
from typing import Tuple

# ============================================================================
# Curva di Potenza F1 2025 (ICE)
# ============================================================================

# RPM di riferimento e potenza (normalizzata da dati FIA/telemetria)
POWER_CURVE_POINTS = [
    (3000, 0.60),      # 3k RPM: 60% potenza max (36% per motori piccoli)
    (6000, 0.85),      # 6k RPM: 85% potenza
    (9000, 0.95),      # 9k RPM: 95% potenza
    (10500, 1.00),     # 10.5k RPM: 100% potenza (PICCO)
    (11000, 0.98),     # 11k RPM: 98% (inizia calo)
    (12000, 0.92),     # 12k RPM: 92% (turbo regolazione)
    (13000, 0.85),     # 13k RPM: 85%
    (14000, 0.78),     # 14k RPM: 78%
    (14500, 0.74),     # 14.5k RPM: 74% (velocità alta strada)
    (15000, 0.68),     # 15k RPM: 68% (limitatore)
]


def get_power_factor(rpm: float) -> float:
    """
    Ritorna il fattore di potenza (0-1) in funzione dei RPM.

    Interpolazione lineare sulla curva di potenza realistica F1.

    Args:
        rpm: RPM del motore

    Returns:
        Fattore di potenza [0.0, 1.0] dove 1.0 = potenza massima
    """

    # Clamp ai limiti
    if rpm <= POWER_CURVE_POINTS[0][0]:
        return POWER_CURVE_POINTS[0][1]
    if rpm >= POWER_CURVE_POINTS[-1][0]:
        return POWER_CURVE_POINTS[-1][1]

    # Interpola tra i punti
    for i in range(len(POWER_CURVE_POINTS) - 1):
        rpm1, power1 = POWER_CURVE_POINTS[i]
        rpm2, power2 = POWER_CURVE_POINTS[i + 1]

        if rpm1 <= rpm <= rpm2:
            # Interpolazione lineare
            frac = (rpm - rpm1) / (rpm2 - rpm1)
            return power1 + frac * (power2 - power1)

    return POWER_CURVE_POINTS[-1][1]


def estimate_rpm_from_speed(v_kph: float, gear: int = 7) -> float:
    """
    Stima gli RPM dalla velocità usando rapporti di marcia F1 2025.

    Rapporti di marcia tipici F1 (Monza):
    - 1ª: 3.91
    - 2ª: 2.36
    - 3ª: 1.78
    - 4ª: 1.30
    - 5ª: 1.00
    - 6ª: 0.84
    - 7ª: 0.64 (usato tipicamente in rettilineo)

    Formula: RPM = v_kph * (gear_ratio / final_drive) / (wheel_circumference * 60)

    Args:
        v_kph: Velocità in km/h
        gear: Marcia (1-7, default 7 per rettilineo)

    Returns:
        RPM stimate
    """

    GEAR_RATIOS = {
        1: 3.91,
        2: 2.36,
        3: 1.78,
        4: 1.30,
        5: 1.00,
        6: 0.84,
        7: 0.64,
    }

    FINAL_DRIVE = 3.4  # Rapporto ponte finale tipico
    WHEEL_DIAMETER_M = 0.67  # Gomme F1 standard
    WHEEL_CIRCUMFERENCE_M = math.pi * WHEEL_DIAMETER_M

    gear_ratio = GEAR_RATIOS.get(gear, GEAR_RATIOS[7])

    # RPM = (v_kph / 3.6) [m/s] / wheel_circumference [m] * 60 [s/min] * gear_ratio * final_drive
    v_ms = v_kph / 3.6
    rpm = (v_ms / WHEEL_CIRCUMFERENCE_M) * 60 * gear_ratio * FINAL_DRIVE

    return rpm


def get_ice_power_kw(v_kph: float, ice_max_power_kw: float = 950.0, gear: int = 7) -> float:
    """
    Calcola la potenza ICE disponibile a una certa velocità.

    Tiene conto della curva di potenza reale che diminuisce ad alti RPM.

    Args:
        v_kph: Velocità in km/h
        ice_max_power_kw: Potenza massima ICE (default 950 kW)
        gear: Marcia (default 7)

    Returns:
        Potenza disponibile in kW
    """

    rpm = estimate_rpm_from_speed(v_kph, gear)
    power_factor = get_power_factor(rpm)
    return ice_max_power_kw * power_factor


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("Power Curve Model Test")
    print("="*70)

    print("\n[1] POWER FACTOR vs RPM")
    for rpm in [3000, 6000, 9000, 10500, 11000, 12000, 13000, 14000, 14500, 15000]:
        factor = get_power_factor(rpm)
        print(f"    {rpm:5} RPM: {factor:.2%} of peak")

    print("\n[2] RPM vs VELOCITÀ (7ª marcia)")
    for v_kph in [100, 200, 300, 320, 340, 347, 360]:
        rpm = estimate_rpm_from_speed(v_kph, gear=7)
        power_kw = get_ice_power_kw(v_kph, ice_max_power_kw=950, gear=7)
        print(f"    {v_kph:3.0f} km/h: {rpm:6.0f} RPM → {power_kw:6.0f} kW ({power_kw/950:.1%})")

    print("\n[3] IMPATTO SUL RETTILINEO DRS")
    print(f"    A 321.6 km/h (entry): {get_ice_power_kw(321.6):.0f} kW")
    print(f"    A 347.0 km/h (exit):  {get_ice_power_kw(347.0):.0f} kW")
    print(f"    Perdita di potenza:   {950 - get_ice_power_kw(347.0):.0f} kW ({(950-get_ice_power_kw(347.0))/950*100:.1f}%)")

    print("\n[4] V_MAX TEORICO CON POWER CURVE")
    # Calcola v_max dove potenza = drag
    # A equilibrio: P(v) = 0.5 * rho * v² * CDA + F_rolling
    # Per il rettilineo DRS: CDA_drs = 0.825, rolling ≈ 86 N

    CDA_DRS = 0.825
    RHO = 1.225
    F_ROLLING = 86  # N

    # Ricerca iterativa di v_max
    v_low = 300 / 3.6  # m/s
    v_high = 450 / 3.6  # m/s

    for iteration in range(30):
        v_mid_ms = (v_low + v_high) / 2
        v_mid_kph = v_mid_ms * 3.6

        p_available_kw = get_ice_power_kw(v_mid_kph, ice_max_power_kw=950, gear=7)
        p_available_w = p_available_kw * 1000

        f_drag = 0.5 * RHO * (v_mid_ms ** 2) * CDA_DRS + F_ROLLING
        p_drag = f_drag * v_mid_ms

        if p_drag < p_available_w:
            v_low = v_mid_ms
        else:
            v_high = v_mid_ms

    v_max_with_curve_kph = v_mid_kph
    v_max_with_curve_ms = v_mid_ms

    print(f"    V_max teorico CON power curve: {v_max_with_curve_kph:.1f} km/h ({v_max_with_curve_ms:.2f} m/s)")
    print(f"    Realtà (telemetria):           347.0 km/h")
    print(f"    Errore:                        {v_max_with_curve_kph - 347:.1f} km/h")
