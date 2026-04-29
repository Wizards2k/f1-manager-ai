"""
update_section_v6 — Orchestratore per-sezione con Physics Engine V6.

Sostituisce update_section() in _move_cars() quando USE_PHYSICS_V6=1.

Architettura dual-pass:
  - Planning: v_max_corner precomputata in init_session() (condivisa)
  - Integration: integrate_waypoint() per-waypoint con PhysicsState persistente

Riferimento: docs/physics-engine-v6-integration-spec.md §9
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from lap_simulator.data_types import (
    AeroSetup,
    CarState,
    CircuitConfig,
    DriverSkills,
    EnvContext,
    SectionContext,
    SectionResult,
)

logger = logging.getLogger(__name__)

# Fuel flow rate (kg/s at full throttle). Consistent with lap_hd.py.
_MAX_FLOW_KG_PS = 0.0277
_DRY_MASS_KG = 798.0  # F1 2025 minimum dry weight


def _build_aero_assembly(aero_setup: AeroSetup, aero_calibration: Optional[Dict]):
    """Costruisce AeroAssembly da AeroSetup (V1 sim) per il V6 engine."""
    from lap_simulator.physics_engine.aero.aero_assembly import AeroAssembly

    aero = AeroAssembly()
    angles = {
        "front_wing": getattr(getattr(aero_setup, "front_wing", None), "angle_deg", 20.0),
        "rear_wing": getattr(getattr(aero_setup, "rear_wing", None), "angle_deg", 22.0),
        "b_wing": getattr(getattr(aero_setup, "b_wing", None), "angle_deg", 10.0),
    }
    aero.set_component_angles(angles)

    if aero_calibration:
        k_wing = aero_calibration.get("k_wing_coupling")
        if k_wing:
            try:
                aero.set_k_wing_coupling(float(k_wing))
            except (TypeError, ValueError):
                pass
    return aero


def _driver_skill_scalar(driver_skills: DriverSkills) -> float:
    """Converte DriverSkills (1-100) in scalar float [0.0, 1.0] per integrate_waypoint."""
    raw_pace = getattr(driver_skills, "raw_pace", 70)
    consistency = getattr(driver_skills, "consistency", 70)
    return max(0.5, min(1.0, (raw_pace * 0.6 + consistency * 0.4) / 100.0))


def update_section_v6(
    car_state: CarState,
    aero_setup: AeroSetup,
    driver_skills: DriverSkills,
    section: SectionContext,
    env: EnvContext,
    config: CircuitConfig,
    push_level: int = 10,
    delta_aero: float = 0.0,
    delta_grip: float = 0.0,
    apply_baseline_delta: bool = True,
    is_qualifying: bool = False,
    circuit_id: str = "default",
    lap_number: int = 1,
    # ── Dati condivisi a livello SessionBridge (precomputati in init_session) ──
    hd_waypoints: Optional[List[Dict]] = None,
    v_max_corner_array: Optional[List[float]] = None,
    brake_needed: Optional[List] = None,
    section_wp_index: Optional[Dict[int, Tuple[int, int]]] = None,
    section_idx: int = 0,
    reference_sections: Optional[Dict] = None,
    aero_calibration: Optional[Dict] = None,
    circuit_calibration: Optional[Dict] = None,
    air_density: float = 1.225,
    # ── Stato persistente (da CarTrackState) ──
    physics_state: Optional[Any] = None,
    pu_ctx: Optional[Any] = None,
    # ── Parametri dinamici (aggiornati da FASE 3, tick precedente) ──
    engine_map: str = "RACE",
    dirty_air_factor: float = 0.0,
    drs_gap_ahead_s: Optional[float] = None,
    is_safety_car: bool = False,
) -> Tuple[SectionResult, Any, Any]:
    """
    Calcola fisica V6 per una sezione, restituisce (SectionResult, PhysicsState, PU_Context).

    PhysicsState e PU_Context sono persistenti tra sezioni (non reinizializzati).
    """
    from lap_simulator.physics_engine.integrator.state import PhysicsState
    from lap_simulator.physics_engine.integrator.waypoint import integrate_waypoint
    from lap_simulator.physics_engine.integrator.pu_stateful_v2 import init_pu_context, PU_Context
    from lap_simulator.physics_engine.integrator.io import find_section_id_by_distance
    from lap_simulator.physics_engine.core.constants import MU_BASE, MAX_BRAKE_DECEL_G, MAX_LATERAL_G
    from lap_simulator.physics_engine.integrator.state_adapter import StateAdapter

    # ── 1. Estrai waypoints della sezione ──
    section_waypoints: List[Dict] = []
    start_idx = 0
    end_idx = 0

    if hd_waypoints and section_wp_index is not None:
        bounds = section_wp_index.get(section_idx)
        if bounds:
            start_idx, end_idx = bounds
            section_waypoints = hd_waypoints[start_idx:end_idx]

    if not section_waypoints:
        # Nessun waypoint V6 per questa sezione: fallback al risultato placeholder
        logger.debug("update_section_v6: no waypoints for section %d, using placeholder", section_idx)
        dt_ref = section.dt_ref_s if section.dt_ref_s > 0 else 3.0
        return (
            SectionResult(dt_s=dt_ref, v_exit_kph=section.v_exit_kph, v_entry_kph=section.v_entry_kph),
            physics_state,
            pu_ctx,
        )

    # ── 2. Init PhysicsState (solo alla prima sezione del stint) ──
    if physics_state is None:
        entry_v_ms = max(1.0, getattr(car_state, "v_current_ms", 0.0))
        if entry_v_ms < 5.0:
            entry_v_ms = section.v_entry_kph / 3.6 if section.v_entry_kph > 0 else 50.0
        physics_state = PhysicsState(velocity_ms=entry_v_ms)
        StateAdapter.car_state_to_physics_state(car_state, physics_state)

    # ── 3. Init PU_Context (solo alla prima sezione del stint) ──
    if pu_ctx is None:
        try:
            pu_ctx = init_pu_context(circuit_id=circuit_id, engine_map=engine_map)
        except Exception as exc:
            logger.warning("update_section_v6: init_pu_context failed: %s", exc)
            pu_ctx = PU_Context(engine_map=engine_map)

    # ── 4. Costruisci AeroAssembly dall'assetto corrente ──
    aero = _build_aero_assembly(aero_setup, aero_calibration)

    # ── 5. Setup mu_base e costanti circuito ──
    mu_base_local = MU_BASE.copy()
    if circuit_calibration:
        mu_override = circuit_calibration.get("mu_override")
        if mu_override:
            mu_base_local.update(mu_override)

    max_brake_g = MAX_BRAKE_DECEL_G
    max_lateral_g = MAX_LATERAL_G
    if circuit_calibration:
        if circuit_calibration.get("max_brake_decel_g"):
            max_brake_g = float(circuit_calibration["max_brake_decel_g"])
        if circuit_calibration.get("max_lateral_g"):
            max_lateral_g = float(circuit_calibration["max_lateral_g"])

    # ── 6. Setup aero_calibration per il compound corrente ──
    cal = dict(aero_calibration) if aero_calibration else {}
    if circuit_calibration:
        soft_compound = circuit_calibration.get("calibration_compound", "C3")
        cal.setdefault("calibration_compound", soft_compound)

    # ── 7. Calcola driver_skill scalar e massa ──
    driver_skill = _driver_skill_scalar(driver_skills)
    # Tyre compound da car_state (usa il primo wheel disponibile)
    tyre_compound = "C3"
    tyres = getattr(car_state, "tyres", {}) or {}
    if tyres:
        first_tyre = next(iter(tyres.values()), None)
        if first_tyre is not None:
            compound_obj = getattr(first_tyre, "compound", None)
            tyre_compound = compound_obj.value if hasattr(compound_obj, "value") else str(compound_obj)

    # Massa: usa 720kg come riferimento fisso (il carburante sarà gestito in V6.5+)
    mass_kg = 720.0

    # ── 8. DRS e safety car ──
    drs_enabled = is_qualifying or (lap_number > 1 and not is_safety_car)

    # ── 9. Loop waypoints: integra fisica ──
    time_at_section_start = physics_state.time_s
    v_entry_ms = physics_state.velocity_ms
    v_max_ms = physics_state.velocity_ms
    total_fuel_delta_kg = 0.0

    flow_map_multiplier = 1.0
    if pu_ctx:
        map_name = getattr(pu_ctx, "engine_map", "RACE").upper()
        if map_name == "RACE":
            flow_map_multiplier = 0.90
        elif map_name == "PRACTICE":
            flow_map_multiplier = 0.85
        elif map_name in ("SAFETY_CAR", "ECONOMY"):
            flow_map_multiplier = 0.40

    # Costruisci setup dict una volta (angoli ali)
    aero_setup_dict = {
        "front_wing": getattr(getattr(aero_setup, "front_wing", None), "angle_deg", 20.0),
        "rear_wing": getattr(getattr(aero_setup, "rear_wing", None), "angle_deg", 22.0),
        "b_wing": getattr(getattr(aero_setup, "b_wing", None), "angle_deg", 10.0),
    }

    for i in range(start_idx, end_idx - 1):
        if i + 1 >= len(hd_waypoints):
            break
        wp = hd_waypoints[i]
        wp_next = hd_waypoints[i + 1]

        # Section guidance per braking/corner logic
        section_guidance = None
        section_exit_guidance = None
        section_entry_guidance = None
        if reference_sections:
            dist_m = wp.get("dist_m", 0.0)
            next_dist_m = wp_next.get("dist_m", 0.0)
            cur_sec_id = find_section_id_by_distance(reference_sections, dist_m)
            next_sec_id = find_section_id_by_distance(reference_sections, next_dist_m)
            section_guidance = reference_sections.get(cur_sec_id)
            if cur_sec_id and cur_sec_id != next_sec_id:
                section_exit_guidance = section_guidance
                section_entry_guidance = reference_sections.get(next_sec_id)

        prev_time_s = physics_state.time_s
        physics_state = integrate_waypoint(
            state=physics_state,
            waypoint=wp,
            next_waypoint=wp_next,
            aero=aero,
            setup=aero_setup_dict,
            mass_kg=mass_kg,
            tyre_compound=tyre_compound,
            driver_skill=driver_skill,
            mu_base=mu_base_local,
            max_brake_decel_g=max_brake_g,
            max_lateral_g=max_lateral_g,
            aero_calibration=cal,
            section_guidance=section_guidance,
            section_exit_guidance=section_exit_guidance,
            section_entry_guidance=section_entry_guidance,
            waypoints=hd_waypoints,
            waypoint_idx=i,
            pu_config={"engine_map": engine_map},
            pu_ctx=pu_ctx,
            v_max_corner_array=v_max_corner_array,
            brake_needed=brake_needed,
            air_density=air_density,
            circuit_id=circuit_id,
            drs_enabled=drs_enabled,
            drs_gap_ahead_s=drs_gap_ahead_s,
            lap_number=lap_number,
            is_safety_car=is_safety_car,
        )

        v_max_ms = max(v_max_ms, physics_state.velocity_ms)

        # Consuma carburante (stesso modello di lap_hd.py)
        dt_step = physics_state.time_s - prev_time_s
        if dt_step > 0:
            throttle_pace_eff = 0.85 + (max(1, min(10, push_level)) / 10.0) * 0.15
            raw_throttle = float(wp.get("throttle_pct", 0)) / 100.0
            if getattr(physics_state, "is_throttle", False):
                throttle_intensity = throttle_pace_eff * raw_throttle
            else:
                throttle_intensity = 0.05
            total_fuel_delta_kg += _MAX_FLOW_KG_PS * throttle_intensity * flow_map_multiplier * dt_step

    # ── 10. Sync PhysicsState → CarState ──
    StateAdapter.physics_state_to_car_state(physics_state, car_state)

    # ── 11. Costruisci SectionResult ──
    section_dt = physics_state.time_s - time_at_section_start
    if section_dt <= 0:
        # Fallback: usa dt_ref dalla sezione
        section_dt = section.dt_ref_s if section.dt_ref_s > 0 else 3.0

    v_exit_ms = physics_state.velocity_ms
    v_exit_kph = v_exit_ms * 3.6
    v_entry_kph = v_entry_ms * 3.6
    v_max_kph = v_max_ms * 3.6

    section_length_m = section.length_m if section.length_m > 0 else 200.0
    v_effective_kph = (section_length_m / section_dt) * 3.6 if section_dt > 0 else v_entry_kph

    # Telemetry: raccogli solo i punti della sezione corrente
    telemetry_points = list(physics_state.telemetry_points or [])

    section_result = SectionResult(
        dt_s=section_dt,
        v_exit_kph=v_exit_kph,
        v_entry_kph=v_entry_kph,
        v_effective_kph=v_effective_kph,
        v_max_kph=v_max_kph,
        telemetry_points=telemetry_points,
        # Segnali per BattleResolver (stima da fisica)
        braking_efficiency=0.9,
        section_progress=1.0,
    )

    # Pulisci telemetria da physics_state per evitare accumulo infinito
    physics_state.telemetry_points = []

    return section_result, physics_state, pu_ctx
