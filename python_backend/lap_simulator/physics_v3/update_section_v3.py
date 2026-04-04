"""
Physics V3 — Update Section V3 Module (Main Orchestrator)

Funzione principale: update_section_v3()
Firma identica a update_section V1, ma orchestra i moduli V3 invece delle penalità additive.

10-Step Pipeline:
1. Input/v_entry — velocità entry, massa con fuel
2. Driver inputs — compute_inputs() [RIUSATO da driver_model]
3. Aero mapping — AeroSetup → PhysicsAeroParams
4. Power output — generate_output() [RIUSATO da power_unit]
5a. Tyre update — update_tyres() [RIUSATO da tyre_model]
5b. Brake update — update_brakes() [RIUSATO da brake_system]
6. Balance — compute_balance() con v_current, radius
7. Corner apex — solve_corner_apex_speed()
8. Integration — integrate_section_hd() o integrate_section_analytic()
9. Traffic/airflow cap — applica limiti da dirty air
10. SectionResult assembly — stessa struttura V1

Compatibilità: Input/Output identico a V1, internamente tutto V3.

Fonte: spec physics-engine-v3-spec.md Section 9-10
"""

from typing import Dict, List, Optional, Any
import logging

from . import constants
from .aero_mapper import map_aero_setup
from .balance_model import compute_balance
from .corner_solver import solve_corner_apex_speed
from .braking_profile import compute_braking_distance, compute_look_ahead_deceleration
from .acceleration_profile import compute_drive_force
from .section_integrator import integrate_section_hd, integrate_section_analytic

# Moduli riusati (copie V3 nella stessa cartella)
from .driver_model_v3 import compute_inputs
from .power_unit_v3 import generate_output
from .tyre_model_v3 import update_tyres
from .brake_system_v3 import update_brakes
from .aero_package_v3 import compute_forces

from ..data_types import (
    CarState,
    AeroSetup,
    DriverSkills,
    SectionContext,
    EnvContext,
    CircuitConfig,
    SectionResult,
    SectionEvent,
)

logger = logging.getLogger(__name__)


def update_section_v3(
    car_state: CarState,
    aero_setup: AeroSetup,
    driver_skills: DriverSkills,
    section: SectionContext,
    env: EnvContext,
    config: CircuitConfig,
    push_level: int = 10,
    airflow_penalty: float = 0.0,
    traffic_v_max_kph: float = 0.0,
    delta_aero: float = 0.0,
    delta_grip: float = 0.0,
    apply_baseline_delta: bool = True,
    is_qualifying: bool = False,
    circuit_id: str = "default",
    driver_id: str = "default",
    lap_number: int = 1,
    setup_sliders: Optional[Dict[str, int]] = None,
    ideal_setup_sliders: Optional[Dict[str, int]] = None,
) -> SectionResult:
    """
    Physics V3 update_section — Orchestratore principale.

    Firma identica a update_section V1, interno completamente V3 newtoniano.

    Args:
        car_state: Stato auto (v_current, tyres, brakes, pu, ecc.)
        aero_setup: Configurazione aerodinamica
        driver_skills: Abilità driver
        section: SectionContext (lunghezza, radius, velocità target, ecc.)
        env: Contesto ambientale (temperatura, umidità, densità aria)
        config: CircuitConfig (configurazione circuito globale)
        push_level: Aggressività driver (0-20, default 10)
        airflow_penalty: Penalità da dirty air (0-0.15)
        traffic_v_max_kph: Cap di velocità da traffico (0 = nessun limite)
        is_qualifying: Se qualifica (no fuel consumption, ecc.)
        circuit_id: ID circuito ("it-1922_monza", ecc.)
        driver_id: ID driver
        lap_number: Numero giro
        setup_sliders: Setup slider values (optional)
        ideal_setup_sliders: Ideal setup per circuito (optional)

    Returns:
        SectionResult con dt_s, v_exit, events, penalties, telemetry
    """

    events: List[SectionEvent] = []

    try:
        # ====================================================================
        # STEP 1: Input — velocità entry, massa con fuel
        # ====================================================================
        v_entry_ms = car_state.v_current_ms if car_state.v_current_ms > 0 else 1.0
        mass_kg = constants.MASS_DRY_KG + car_state.pu.fuel_kg

        # ====================================================================
        # STEP 2: Driver inputs [RIUSATO driver_model.compute_inputs()]
        # ====================================================================
        driver_intent = compute_inputs(
            skills=driver_skills,
            mental=car_state.driver_mental,
            section=section,
            env=env,
            car_state=car_state,
            config=config,
            push_level=push_level / 10.0,  # Normalizza 0-20 → 0-2
            lap_number=lap_number,
        )

        # ====================================================================
        # STEP 3: Aero mapping — AeroSetup → PhysicsAeroParams
        # ====================================================================
        physics_aero = map_aero_setup(
            aero_setup=aero_setup,
            env=env,
            v_estimate_kph=section.v_base_kph if hasattr(section, 'v_base_kph') else 200.0,
            drs_active=section.drs_available if hasattr(section, 'drs_available') else False,
            config=config,
        )

        # ====================================================================
        # STEP 4: Power output [RIUSATO power_unit.generate_output()]
        # ====================================================================
        aero_forces = compute_forces(
            aero=aero_setup,
            section=section,
            env=env,
            car_state=car_state,
            config=config,
            v_kph=section.v_base_kph if hasattr(section, 'v_base_kph') else 200.0,
            airflow_penalty=airflow_penalty,
            drs_active=section.drs_available if hasattr(section, 'drs_available') else False,
        )

        pu_state_updated, pu_events = generate_output(
            pu_state=car_state.pu,
            driver_intent=driver_intent,
            aero_forces=aero_forces,
            section=section,
            env=env,
            config=config,
            dt_estimate_s=section.dt_ref_s if hasattr(section, 'dt_ref_s') else 1.0,
        )
        events.extend(pu_events)

        # ====================================================================
        # STEP 5a: Tyre update [RIUSATO tyre_model.update_tyres()]
        # ====================================================================
        mu_grip_front, mu_grip_rear, tyre_events = update_tyres(
            car_state=car_state,
            section=section,
            env=env,
            aero=aero_forces,
            driver=driver_intent,
            config=config,
            dt_s=section.dt_ref_s if hasattr(section, 'dt_ref_s') else 1.0,
            v_kph=section.v_base_kph if hasattr(section, 'v_base_kph') else 200.0,
            aero_setup=aero_setup,
            setup_sliders=setup_sliders,
        )
        # update_tyres() usa una scala interna normalizzata (C3=1.0, C5=1.12).
        # Per la fisica newtoniana servono i valori assoluti di mu (C3=1.70, C5=1.90).
        # Fattore conversione = MU_BASE["C3"] = 1.70 (C3 è il compound di riferimento
        # con base_grip=1.0 nella tyre model e 1.70 nella scala fisica).
        MU_PHYSICS_SCALE = constants.MU_BASE.get("C3", 1.70)
        mu_base = (mu_grip_front + mu_grip_rear) / 2.0 * MU_PHYSICS_SCALE
        events.extend(tyre_events)

        # ====================================================================
        # STEP 5b: Brake update [RIUSATO brake_system.update_brakes()]
        # ====================================================================
        braking_efficiency, brake_events, brake_snapshot = update_brakes(
            car_state=car_state,
            section=section,
            env=env,
            aero=aero_forces,
            driver=driver_intent,
            config=config,
            dt_s=section.dt_ref_s if hasattr(section, 'dt_ref_s') else 1.0,
            v_kph=section.v_base_kph if hasattr(section, 'v_base_kph') else 200.0,
            driver_skills=driver_skills,
        )
        events.extend(brake_events)
        brake_state = car_state.brakes

        # ====================================================================
        # STEP 6: Balance — load transfer e grip effettivo
        # ====================================================================
        balance = compute_balance(
            mu_base=mu_base,
            aero=physics_aero,
            aero_setup=aero_setup,
            v_ms=v_entry_ms,
            radius_m=section.radius_m if hasattr(section, 'radius_m') and section.radius_m else 0.0,
            mass_kg=mass_kg,
            env=env,
            a_long_g=0.0,
        )

        # ====================================================================
        # STEP 7: Corner apex speed
        # Priorità: v_min_kph (telemetria reale) > corner_solver (fisica) > v_exit
        #
        # v_min_kph è il dato del GIOCO: la velocità minima reale nel settore.
        # Per chicane (Turn 1/2): v_min è l'apex, v_exit è dopo la riaccelerazione.
        # Per sezioni senza raggio (Turn 3): v_min = v_exit, nessuna curva stretta.
        # Usare v_exit come apex per queste sezioni causava errori +20% (frenata a 0).
        # ====================================================================
        section_radius = section.radius_m if hasattr(section, 'radius_m') and section.radius_m else 0.0

        v_min_kph = getattr(section, 'v_min_kph', None)
        if v_min_kph is not None and v_min_kph > 0:
            # PRIORITÀ 1: v_min dalla telemetria (dato reale del gioco)
            v_apex_ms = v_min_kph / 3.6
        elif section_radius > 0.1:
            # PRIORITÀ 2: calcolo fisico se abbiamo il raggio
            v_apex_ms = solve_corner_apex_speed(
                radius_m=section_radius,
                aero=physics_aero,
                balance=balance,
                mass_kg=mass_kg,
                mu_base=mu_base,
                env_rho=env.air_density_kg_m3,
                banking_deg=0.0,
            )
        else:
            # FALLBACK: sezione senza raggio né v_min (caso degenere)
            v_apex_ms = section.v_exit_kph / 3.6 if hasattr(section, 'v_exit_kph') and section.v_exit_kph > 0 else 30.0

        # ====================================================================
        # STEP 8: Integrazione cinematica — HD o analitica
        # ====================================================================
        section_length = section.length_m if hasattr(section, 'length_m') else 500.0

        # Usa v_exit da telemetria come velocity constraint se disponibile
        # Questo garantisce che l'accelerazione rispetti i limiti fisici della sezione
        v_exit_constraint = section.v_exit_kph / 3.6 if hasattr(section, 'v_exit_kph') and section.v_exit_kph > 0 else None

        if section.waypoints and len(section.waypoints) > 5:
            # HD waypoints disponibili
            # Usa v_exit da telemetria come vincolo HARD per correggere waypoint v_ref inaccurati
            v_exit_target = section.v_exit_kph / 3.6 if hasattr(section, 'v_exit_kph') and section.v_exit_kph > 0 else None

            dt_s, v_exit_ms, telemetry = integrate_section_hd(
                waypoints=section.waypoints,
                v_entry_ms=v_entry_ms,
                aero=physics_aero,
                aero_setup=aero_setup,
                mass_kg=mass_kg,
                mu_base=mu_base,
                env=env,
                pu_state=pu_state_updated,
                brake_state=brake_state,
                v_exit_target_ms=v_exit_target,
            )
        else:
            # Analitica — se v_exit_constraint disponibile, usalo per limitare accelerazione
            v_exit_target = section.v_exit_kph / 3.6 if hasattr(section, 'v_exit_kph') else v_apex_ms
            dt_s, v_exit_ms, telemetry = integrate_section_analytic(
                v_entry_ms=v_entry_ms,
                v_apex_ms=v_apex_ms,
                v_exit_ms=v_exit_target,
                section=section,
                aero=physics_aero,
                aero_setup=aero_setup,
                mass_kg=mass_kg,
                mu_base=mu_base,
                env=env,
                pu_state=pu_state_updated,
                brake_state=brake_state,
                v_max_constraint=v_exit_constraint if hasattr(section, 'v_exit_kph') else None,
            )

        # ====================================================================
        # DEBUG TEMPORANEO: stampa parametri chiave per diagnosi
        # TODO: RIMUOVERE dopo fix Turn 2/3
        import os as _os
        if _os.environ.get('V3_DEBUG'):
            print(f"  [V3DEBUG] {section.name}: v_entry={v_entry_ms*3.6:.1f} v_apex={v_apex_ms*3.6:.1f} v_max={v_exit_constraint*3.6 if v_exit_constraint else None} → dt={dt_s:.3f}s v_exit={v_exit_ms*3.6:.1f}")

        # ====================================================================
        # STEP 9: Traffic/airflow cap (stesso V1)
        # ====================================================================
        if traffic_v_max_kph > 0:
            v_exit_ms = min(v_exit_ms, traffic_v_max_kph / 3.6)

        # ====================================================================
        # STEP 10: SectionResult assembly — stessa struttura V1
        # ====================================================================
        result = SectionResult(
            dt_s=dt_s,
            v_exit_kph=v_exit_ms * 3.6,
            v_entry_kph=v_entry_ms * 3.6,
            v_effective_kph=v_exit_ms * 3.6,
            v_max_kph=(v_apex_ms * 3.6) if v_apex_ms > 0 else section.v_max_kph if hasattr(section, 'v_max_kph') else 300.0,
            telemetry_points=telemetry,
            events=events,
            braking_efficiency=braking_efficiency,
            df_available=physics_aero.CLA,
            drag_eff=physics_aero.CDA,
            power_kw=(pu_state_updated.ice_power_kw + pu_state_updated.ers_output_kw),
            effective_grip_front=balance.mu_front_eff,
            effective_grip_rear=balance.mu_rear_eff,
            handling_penalty=0.0,
            # Penalties (compatibilità V1, non usati in V3 pura)
            fuel_penalty_s=0.0,
            tyre_penalty_s=0.0,
            push_penalty_s=0.0,
            engine_penalty_s=0.0,
            brake_penalty_s=0.0,
            setup_penalty_s=0.0,
            df_curve_penalty_s=0.0,
            df_curve_bonus_s=0.0,
            drag_penalty_s=0.0,
            drag_bonus_s=0.0,
            ers_bonus_s=0.0,
        )

        return result

    except Exception as e:
        logger.error(f"update_section_v3 error: {str(e)}")
        raise


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("update_section_v3 module loaded (import test)")
