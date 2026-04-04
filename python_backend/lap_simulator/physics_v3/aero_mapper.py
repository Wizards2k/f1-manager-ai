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
from typing import Optional, Tuple
import math

from . import constants
from ..data_types import AeroSetup, EnvContext, AeroForces
from ..aero_package import compute_forces


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _compute_balance_penalties(
    aero_balance: float,
    fw_angle: float = 0.0,      # reserved for future components
    rw_angle: float = 0.0,      # reserved for future components
    aero_setup: AeroSetup = None,  # reserved for future components
    fuel_kg: float = 0.0,       # reserved for future components
) -> Tuple[float, float, float]:
    """
    Calcola understeer/oversteer grip penalty dal bilanciamento aerodinamico.

    Il valore aero_balance (CLA_fw / CLA_total) è il singolo indicatore di
    bilanciamento. Attualmente è movimentato solo dalle ali; in futuro
    includerà floor, bwing, sidepods, fuel load, ARB.

    Target neutro: WEIGHT_DIST_FRONT = 0.455
      Il downforce anteriore deve corrispondere alla distribuzione peso statica.
      Se l'auto pesa 45.5% sull'anteriore, anche il DF deve bilanciarsi lì.

      aero_balance > 0.455 → DF anteriore in eccesso → sottosterzo
      aero_balance < 0.455 → DF posteriore in eccesso → sovrasterzo

    Zona neutra ±0.02 (range 0.435–0.475): nessuna penalità.
    Oltre la zona neutra: penalità lineare che scala fino a 1.0 a ±0.10.

    Returns:
        (understeer_grip_penalty, oversteer_grip_penalty, setup_quality_score)
    """
    # Target fisico: distribuzione peso statica anteriore F1 2025
    BALANCE_TARGET = 0.455
    NEUTRAL_BAND = 0.020    # ±2% → zona neutra senza penalità
    MAX_DEVIATION = 0.10    # ±10% → penalità massima (1.0)

    deviation = aero_balance - BALANCE_TARGET

    if abs(deviation) <= NEUTRAL_BAND:
        # Zona neutra: setup bilanciato, nessuna penalità
        understeer_penalty = 0.0
        oversteer_penalty = 0.0
    elif deviation > 0:
        # DF anteriore eccedente → sottosterzo
        understeer_penalty = _clamp(
            (deviation - NEUTRAL_BAND) / (MAX_DEVIATION - NEUTRAL_BAND),
            0.0, 1.0
        )
        oversteer_penalty = 0.0
    else:
        # DF posteriore eccedente → sovrasterzo
        oversteer_penalty = _clamp(
            (-deviation - NEUTRAL_BAND) / (MAX_DEVIATION - NEUTRAL_BAND),
            0.0, 1.0
        )
        understeer_penalty = 0.0

    # Setup quality: 1.0 al centro della zona neutra, scende linearmente
    quality_score = _clamp(
        1.0 - max(0.0, abs(deviation) - NEUTRAL_BAND) / (MAX_DEVIATION - NEUTRAL_BAND),
        0.0, 1.0
    )

    return understeer_penalty, oversteer_penalty, quality_score


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
    config = None,
    fuel_kg: float = 0.0,
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
        config: CircuitConfig (optional, for compute_forces)

    Returns:
        PhysicsAeroParams con tutti i parametri fisici calcolati
    """

    fw = aero_setup.front_wing
    rw = aero_setup.rear_wing

    # ========================================================================
    # FAST PATH: Wing angle → Cl/Cd physics (spec Section 3 — Gemini)
    # When wing angles are explicitly set, compute CLA/CDA directly from the
    # spec anchor points (4°→Cl=2.8/Cd=0.7; 30°→Cl=5.2/Cd=1.4).
    # Team df/drag modifiers are stored in base_downforce / base_drag fields.
    # This makes setup physics-driven: the optimal setup emerges from the physics.
    # ========================================================================
    if fw.angle_deg > 0 or rw.angle_deg > 0:
        fw_angle = max(4.0, fw.angle_deg)
        rw_angle = max(4.0, rw.angle_deg)

        # McLaren team modifiers: efficiency_factor=df modifier, base_drag=drag modifier
        fw_df_mod = fw.efficiency_factor if fw.efficiency_factor > 0 else 1.0
        fw_drag_mod = fw.base_drag if fw.base_drag > 0 else 1.0
        rw_df_mod = rw.efficiency_factor if rw.efficiency_factor > 0 else 1.0
        rw_drag_mod = rw.base_drag if rw.base_drag > 0 else 1.0

        # Interpolation [0=4°, 1=30°]
        t_fw = max(0.0, min(1.0, (fw_angle - 4.0) / 26.0))
        t_rw = max(0.0, min(1.0, (rw_angle - 4.0) / 26.0))

        # Per-wing CLA (spec: total 2.80 at 4°, 5.20 at 30°; FW≈45%, RW≈55%)
        cla_fw_phys = (1.27 + t_fw * 0.96) * fw_df_mod
        cla_rw_phys = (1.53 + t_rw * 1.44) * rw_df_mod
        cla_phys = max(constants.CLA_MIN, min(constants.CLA_MAX, cla_fw_phys + cla_rw_phys))

        # Per-wing CDA (spec: wings 0.70 at 4°, 1.40 at 30°; FW≈35%, RW≈65%)
        cda_fw_phys = (0.245 + t_fw * 0.245) * fw_drag_mod
        cda_rw_phys = (0.455 + t_rw * 0.455) * rw_drag_mod
        cda_phys = max(constants.CDA_MIN, min(constants.CDA_MAX,
                       cda_fw_phys + cda_rw_phys + constants.CDA_FLOOR_WHEELS))

        # DRS
        cda_drs_phys = cda_phys * (1.0 - constants.DRS_DRAG_REDUCTION_FACTOR)
        if drs_active:
            cda_phys = cda_drs_phys

        # Aero balance from actual per-wing downforce
        aero_bal_phys = cla_fw_phys / max(cla_phys, 0.01)
        cla_front_phys = cla_phys * aero_bal_phys
        cla_rear_phys = cla_phys * (1.0 - aero_bal_phys)

        # Ground effect
        rh_avg = (aero_setup.ride_height_front_mm + aero_setup.ride_height_rear_mm) / 2.0
        rh_opt = (aero_setup.ride_height_optimal_front_mm + aero_setup.ride_height_optimal_rear_mm) / 2.0
        rh_delta_n = (rh_avg - rh_opt) / max(rh_opt, 1.0)
        ge_phys = max(0.85, min(1.15, 1.0 + 0.15 * (1.0 - rh_delta_n ** 2)))

        # Grip penalties — modello multi-fattore (V1 ported)
        us_pen, os_pen, q_score = _compute_balance_penalties(
            aero_balance=aero_bal_phys,
            fw_angle=fw_angle,
            rw_angle=rw_angle,
            aero_setup=aero_setup,
            fuel_kg=fuel_kg,
        )

        return PhysicsAeroParams(
            CLA=cla_phys,
            CDA=cda_phys,
            CLA_front=cla_front_phys,
            CLA_rear=cla_rear_phys,
            aero_balance=aero_bal_phys,
            ground_effect_bonus=ge_phys,
            understeer_grip_penalty=us_pen,
            oversteer_grip_penalty=os_pen,
            CDA_drs_open=cda_drs_phys,
            setup_quality_score=q_score,
        )

    # ========================================================================
    # STEP 1: Compute aero forces via existing V1 function
    # ========================================================================
    # Questo chiama il compute_forces di aero_package che produce df_total,
    # drag_total in unità "aero_points" (scala 0-70).
    #
    # Per il test, se car_state è None, usiamo un dummy state con damage=0

    from ..data_types import CarState, DamageState

    # Dummy car state per compute_forces se necessario
    from ..data_types import SectionContext, DamageCoeffs, SectionKind

    car_state_for_compute = CarState()
    car_state_for_compute.damage = DamageState()

    # Dummy section context per compute_forces se necessario
    section_for_compute = SectionContext(
        section_id="test",
        name="test",
        length_m=500.0,
        v_base_kph=v_estimate_kph,
        v_entry_kph=v_estimate_kph,
        v_exit_kph=v_estimate_kph,
        v_min_kph=v_estimate_kph * 0.8,
        dt_ref_s=1.0,
        kind=SectionKind.STRAIGHT,
        bumpiness_factor=0.0,
    )

    # Dummy config if not provided
    if config is None:
        config = type('DummyConfig', (), {
            'k_handling': 0.8,
            'k_df': 0.15,
            'k_drag': 0.10,
            'k_drag_curve': 0.05,
            'k_power': 0.12,
            'damage_coeffs': DamageCoeffs(),
        })()

    aero_forces: AeroForces = compute_forces(
        aero=aero_setup,
        section=section_for_compute,
        env=env,
        car_state=car_state_for_compute,
        config=config,
        v_kph=v_estimate_kph,
        airflow_penalty=0.0,
        drs_active=drs_active,
    )

    df_total_aero_points = aero_forces.df_total
    drag_total_aero_points = aero_forces.drag_eff
    aero_balance_from_forces = aero_forces.aero_balance  # df_front / df_total

    # Guard: aero_balance=0.0 means compute_forces had no wing data → neutral fallback
    if aero_balance_from_forces <= 0.01:
        aero_balance_from_forces = 0.42

    # ========================================================================
    # STEP 2: Converti aero_points → CLA, CDA fisici (calibration)
    # ========================================================================
    # Formula baseline (spec Section 3):
    #   CLA = CLA_BASE + (df_total - 160) * CLA_SENSITIVITY
    #   CDA = CDA_BASE_STRUCT + drag_total * CDA_SENSITIVITY
    #
    # FALLBACK: Se compute_forces() ritorna 0 (AeroComponent.base_downforce non
    # configurato), usa il setup NEUTRO come stima conservativa invece di CDA_MIN.
    # CDA_NEUTRAL (1.05 m²) dà v_max ≈ 348 kph a Monza con P=600kW, coerente
    # con la telemetria di riferimento.

    if df_total_aero_points == 0 and drag_total_aero_points == 0:
        # Nessun dato aero_points → calcola da angoli ali (spec Gemini Section 3)
        fw_angle = aero_setup.front_wing.angle_deg
        rw_angle = aero_setup.rear_wing.angle_deg
        fw_eff = aero_setup.front_wing.efficiency_factor    # McLaren df modifier
        rw_eff = aero_setup.rear_wing.efficiency_factor

        if fw_angle > 0 or rw_angle > 0:
            # CLA per ala: 1.40 m² a 4°, 2.60 m² a 30° (spec Gemini quadratica linearizzata)
            cla_fw_base = max(0.5, 1.40 + (fw_angle - 4.0) / 26.0 * 1.20)
            cla_rw_base = max(0.5, 1.40 + (rw_angle - 4.0) / 26.0 * 1.20)
            cla_fw = cla_fw_base * fw_eff
            cla_rw = cla_rw_base * rw_eff
            cla = max(constants.CLA_MIN, min(constants.CLA_MAX, cla_fw + cla_rw))
            aero_balance_from_forces = cla_fw / max(cla, 0.01)

            # CDA: drag quadratico spec + drag carrozzeria
            fw_drag_mod = aero_setup.front_wing.base_drag if aero_setup.front_wing.base_drag else 1.0
            rw_drag_mod = aero_setup.rear_wing.base_drag if aero_setup.rear_wing.base_drag else 1.0
            avg_drag_mod = (fw_drag_mod + rw_drag_mod) / 2.0
            cla_total_for_drag = cla_fw_base + cla_rw_base
            cda_wings = (0.414 + 0.0365 * cla_total_for_drag ** 2) * avg_drag_mod
            cda = max(constants.CDA_MIN, min(constants.CDA_MAX, cda_wings + constants.CDA_BODY_DRAG))
        else:
            # Nessun angolo configurato → fallback al setup neutro con balance neutro
            cla = constants.CLA_NEUTRAL
            cda = constants.CDA_NEUTRAL
            aero_balance_from_forces = 0.5  # FIXED: era 0.0 → causava oversteer_penalty=1.0
    else:
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
    # STEP 5: DRS drag reduction
    # ========================================================================
    cda_drs_open = cda * (1.0 - constants.DRS_DRAG_REDUCTION_FACTOR)
    if drs_active:
        cda = cda_drs_open

    # ========================================================================
    # STEP 6: Understeer/oversteer penalty + quality — modello multi-fattore
    # ========================================================================
    # Usa angoli ali dal setup (0 se non impostati → fallback neutro)
    _fw_angle = aero_setup.front_wing.angle_deg or 0.0
    _rw_angle = aero_setup.rear_wing.angle_deg or 0.0
    understeer_penalty, oversteer_penalty, quality_score = _compute_balance_penalties(
        aero_balance=aero_balance_from_forces,
        fw_angle=_fw_angle,
        rw_angle=_rw_angle,
        aero_setup=aero_setup,
        fuel_kg=fuel_kg,
    )

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
