"""
Physics V3 — Aero Mapper Module

Converte AeroSetup (aero_points, slider values) → PhysicsAeroParams (CLA, CDA fisici).

La mapping usa una calibrazione basata su baseline strutturale:
- CLA_BASE = 3.20 m² (setup neutro, 160 aero points)
- CDA_BASE_STRUCT = 0.55 m² (telaio + ruote, non aerodinamico)
- Sensitivity: CLA_SENSITIVITY = 0.020 m²/punto, CDA_SENSITIVITY = 0.015 m²/punto

Fonte: spec physics-engine-v3-spec.md Section 3
"""

from dataclasses import dataclass
from typing import Optional
import math

from . import constants
from ..data_types import AeroSetup, EnvContext, AeroForces
from ..aero_package import compute_forces


# ============================================================================
# PhysicsAeroParams — Output dataclass
# ============================================================================

@dataclass
class PhysicsAeroParams:
    """Physical aero parameters for V3 solver."""

    # Downforce and drag [m²]
    CLA: float                          # Downforce coefficient area
    CDA: float                          # Drag coefficient area
    CLA_front: float                    # DL distribution — front
    CLA_rear: float                     # DL distribution — rear
    aero_balance: float                 # CLA_front / CLA (target 0.45–0.55)

    # Secondary effects
    ground_effect_bonus: float          # Multiplier [0.85, 1.15] from ride_height
    understeer_grip_penalty: float      # Reduction factor [0.0, 1.0] for mu_front
    oversteer_grip_penalty: float       # Reduction factor [0.0, 1.0] for mu_rear

    # DRS state
    CDA_drs_open: float                 # Drag with DRS open (rear flap)

    # Metadata
    setup_quality_score: float          # 0.0–1.0, proximity to optimal setup

    def __repr__(self) -> str:
        return (
            f"PhysicsAeroParams(CLA={self.CLA:.2f}m², CDA={self.CDA:.2f}m², "
            f"balance={self.aero_balance:.2f}, GE_bonus={self.ground_effect_bonus:.2f})"
        )


# ============================================================================
# Aero Mapper Main Function
# ============================================================================

def map_aero_setup(
    aero_setup: AeroSetup,
    env: EnvContext,
    v_estimate_kph: float = 200.0,
    drs_active: bool = False,
) -> PhysicsAeroParams:
    """
    Converte AeroSetup (UI sliders/aero_points) → PhysicsAeroParams (fisici).

    Pipeline:
    1. Chiama aero_package.compute_forces() per ottenere df_total, drag_total (aero_points)
    2. Converte aero_points → CLA, CDA fisici
    3. Calcola distribuzione front/rear da aero_balance
    4. Calcola ground_effect_bonus da ride_height
    5. Calcola understeer/oversteer grip penalty da aero_balance deviazione
    6. Assembla PhysicsAeroParams

    Args:
        aero_setup: Configurazione assetto (da UI o setup file)
        env: Contesto ambientale (temperatura, pressione, umidità)
        v_estimate_kph: Velocità stimata per speed_factor (default 200 kph)
        drs_active: Se DRS attivo (riduce CDA)

    Returns:
        PhysicsAeroParams con tutti i parametri fisici calcolati
    """

    # ========================================================================
    # STEP 1: Compute aero forces via existing V1 function
    # ========================================================================
    # Questo chiama il compute_forces di aero_package che produce df_total,
    # drag_total in unità "aero_points" (scala 0-70).
    #
    # Per il test, se car_state è None, usiamo un dummy state con damage=0

    from ..data_types import CarState, DamageState

    # Dummy car state per compute_forces se necessario
    car_state_for_compute = CarState()
    car_state_for_compute.damage = DamageState()

    aero_forces: AeroForces = compute_forces(
        aero=aero_setup,
        section=None,  # v3/aero_mapper non ha sezione specifica
        env=env,
        car_state=car_state_for_compute,
        config=None,
        v_kph=v_estimate_kph,
        airflow_penalty=0.0,
        drs_active=drs_active,
    )

    df_total_aero_points = aero_forces.df_total
    drag_total_aero_points = aero_forces.drag_eff
    aero_balance_from_forces = aero_forces.aero_balance  # df_front / df_total

    # ========================================================================
    # STEP 2: Converti aero_points → CLA, CDA fisici (calibration)
    # ========================================================================
    # Formula baseline (spec Section 3):
    #   CLA = CLA_BASE + (df_total - 160) * CLA_SENSITIVITY
    #   CDA = CDA_BASE_STRUCT + drag_total * CDA_SENSITIVITY

    cla = constants.CLA_NEUTRAL + (df_total_aero_points - 160.0) * constants.CLA_SENSITIVITY
    cda = constants.CDA_BASE_STRUCT + drag_total_aero_points * constants.CDA_SENSITIVITY

    # Clamp a range fisico
    cla = max(constants.CLA_MIN, min(constants.CLA_MAX, cla))
    cda = max(constants.CDA_MIN, min(constants.CDA_MAX, cda))

    # ========================================================================
    # STEP 3: Distribuzione front/rear di downforce
    # ========================================================================
    # Da aero_forces.aero_balance (ratio front/total, target ~0.45–0.55)

    cla_front = cla * aero_balance_from_forces
    cla_rear = cla * (1.0 - aero_balance_from_forces)

    # ========================================================================
    # STEP 4: Ground effect bonus da ride_height
    # ========================================================================
    # Altezza ottimale:
    #   Se ride_height == ride_height_optimal → bonus massimo (1.15)
    #   Se ride_height >> ride_height_optimal → penalty (0.85)

    ride_height_avg = (
        (aero_setup.ride_height_front_mm + aero_setup.ride_height_rear_mm) / 2.0
    )
    ride_height_opt_avg = (
        (aero_setup.ride_height_optimal_front_mm + aero_setup.ride_height_optimal_rear_mm) / 2.0
    )

    rh_delta_mm = ride_height_avg - ride_height_opt_avg
    rh_delta_normalized = rh_delta_mm / max(ride_height_opt_avg, 1.0)

    # Parabola: massimo a delta=0, penalty ai due estremi
    ge_bonus = 1.0 + 0.15 * (1.0 - (rh_delta_normalized ** 2))
    ge_bonus = max(0.85, min(1.15, ge_bonus))

    # ========================================================================
    # STEP 5: Understeer/oversteer grip penalty da aero_balance
    # ========================================================================
    # Se aero_balance devia da 0.50 (neutro):
    #   - Verso 0.40 (ali posteriori): oversteer grip penalty su rear
    #   - Verso 0.60 (ali anteriori): understeer grip penalty su front
    # Penalty monotona da aero_balance deviazione.

    aero_balance_deviation = abs(aero_balance_from_forces - 0.50)  # |balance - 0.5|
    grip_penalty_magnitude = aero_balance_deviation * 2.0  # scala [0, 1]
    grip_penalty_magnitude = min(1.0, grip_penalty_magnitude)

    if aero_balance_from_forces < 0.45:
        # Ali posteriori → oversteer
        understeer_penalty = 0.0
        oversteer_penalty = grip_penalty_magnitude
    elif aero_balance_from_forces > 0.55:
        # Ali anteriori → understeer
        understeer_penalty = grip_penalty_magnitude
        oversteer_penalty = 0.0
    else:
        # Neutro
        understeer_penalty = 0.0
        oversteer_penalty = 0.0

    # ========================================================================
    # STEP 6: DRS drag reduction
    # ========================================================================
    # Se DRS attivo: CDA_drs = CDA * (1 - DRS_DRAG_REDUCTION_FACTOR)

    if drs_active:
        cda_drs_open = cda * (1.0 - constants.DRS_DRAG_REDUCTION_FACTOR)
    else:
        cda_drs_open = cda

    # ========================================================================
    # STEP 7: Setup quality score (optional, per feedback)
    # ========================================================================
    # Semplice metrica: quanto è vicino il setup alla configurazione "neutra"
    # Neutra = aero_balance ~0.50, ride_height ~optimal, moderate wing angles

    quality_score = 1.0  # Default perfect
    # Ridotto se aero_balance troppo sbilanciato
    if aero_balance_deviation > 0.05:
        quality_score -= (aero_balance_deviation - 0.05) * 0.5
    # Ridotto se ride_height fuori dalla finestra
    if abs(rh_delta_mm) > 5.0:
        quality_score -= abs(rh_delta_mm) / 100.0

    quality_score = max(0.0, min(1.0, quality_score))

    # ========================================================================
    # STEP 8: Assembla PhysicsAeroParams
    # ========================================================================

    return PhysicsAeroParams(
        CLA=cla,
        CDA=cda,
        CLA_front=cla_front,
        CLA_rear=cla_rear,
        aero_balance=aero_balance_from_forces,
        ground_effect_bonus=ge_bonus,
        understeer_grip_penalty=understeer_penalty,
        oversteer_grip_penalty=oversteer_penalty,
        CDA_drs_open=cda_drs_open,
        setup_quality_score=quality_score,
    )


# ============================================================================
# Helper: Analisi aero setup (per debug/feedback)
# ============================================================================

def analyze_aero_setup(
    aero_setup: AeroSetup,
    physics_aero: PhysicsAeroParams,
) -> dict:
    """
    Analizza un aero setup e fornisce feedback su equilibrio e qualità.

    Returns:
        Dict con metriche di analisi:
        - balance_quality: "neutral" | "understeer_bias" | "oversteer_bias"
        - ground_effect_quality: "optimal" | "too_high" | "too_low"
        - wing_asymmetry: float [0, 1] — quanto è asimmetrico
        - grip_penalties: {understeer: float, oversteer: float}
    """

    # Analizza aero_balance
    if physics_aero.aero_balance < 0.45:
        balance_quality = "oversteer_bias"
    elif physics_aero.aero_balance > 0.55:
        balance_quality = "understeer_bias"
    else:
        balance_quality = "neutral"

    # Analizza ground effect
    if physics_aero.ground_effect_bonus > 1.10:
        ge_quality = "optimal"
    elif physics_aero.ground_effect_bonus < 0.95:
        ge_quality = "too_high"
    else:
        ge_quality = "acceptable"

    # Wing asymmetry (front_wing vs rear_wing angle delta)
    wing_asymmetry = (
        abs(aero_setup.front_wing.angle_deg - aero_setup.rear_wing.angle_deg) / 20.0
    )
    wing_asymmetry = min(1.0, wing_asymmetry)

    return {
        "balance_quality": balance_quality,
        "ground_effect_quality": ge_quality,
        "wing_asymmetry": wing_asymmetry,
        "grip_penalties": {
            "understeer": physics_aero.understeer_grip_penalty,
            "oversteer": physics_aero.oversteer_grip_penalty,
        },
        "setup_quality_score": physics_aero.setup_quality_score,
    }


# ============================================================================
# Test / Validation
# ============================================================================

if __name__ == "__main__":
    from ..lap_simulator import config_loader
    from ..data_types import EnvContext

    # Test setup conversion
    test_aero_setup = AeroSetup()
    test_env = EnvContext(
        air_temp_c=20.0,
        track_temp_c=40.0,
        air_density_kg_m3=1.225,
        wind_speed_kph=5.0,
        rain_intensity=0.0,
        track_rubber_level=0.8,
        water_film_level=0.0,
    )

    physics_aero = map_aero_setup(test_aero_setup, test_env, v_estimate_kph=200.0)
    print(f"Aero mapping result: {physics_aero}")

    analysis = analyze_aero_setup(test_aero_setup, physics_aero)
    print(f"Setup analysis: {analysis}")
