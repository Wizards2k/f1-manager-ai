"""
AI Driver Engine – Strategic decision layer for AI cars in practice.

Manages run planning, setup seed generation, run configuration,
post-run analysis and setup refinement for 18 AI cars.

This is the STRATEGIC layer (per-run decisions).
driver_model.py is the TACTICAL layer (per-section decisions).

Reference: docs/ai-driver-engine-spec.md
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .ai_data_types import (
    AIDriverConfig,
    AITeamConfig,
    AIPracticeRunEvent,
    CarStatus,
    NotificationPriority,
    PIT_OVERHEAD_S,
    PIT_WORK_STATUS,
    PIT_WORK_TIMES,
    PitStop,
    PitWorkItem,
    PitWorkType,
    RUN_PROGRAM_DEFAULTS,
    RunOutcome,
    RunPlan,
    RunProgram,
    RunResult,
    RunTelemetrySummary,
    SESSION_PROGRAMS,
    SessionPlan,
    SessionType,
    SetupAdjustment,
)
from .data_types import (
    AeroSetup,
    CarState,
    CircuitConfig,
    DriverSkills,
    EngineMapName,
    ERSModeName,
    TyreCompound,
    TyreState,
    WheelPosition,
    clamp,
)
from .lap_simulator import CarEntry, LapResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRAFFIC_DELAY_MAX_S = 60.0            # max delay for traffic (spec §4)
SETUP_CONVERGENCE_THRESHOLD = 0.15    # all deltas below this = converged
SETUP_SEED_MAX_OFFSET = 0.20          # max slider offset from target (20%)


# ---------------------------------------------------------------------------
# Setup seed generation (spec §2)
# ---------------------------------------------------------------------------

def generate_setup_seed(
    circuit_config: CircuitConfig,
    team_config: AITeamConfig,
    driver_config: AIDriverConfig,
) -> AeroSetup:
    """
    Generate initial setup for an AI car based on team sim quality
    and driver sim affinity.

    Higher setup_seed_score → closer to optimal (less offset).

    Reference: ai-driver-engine-spec §2
    """
    score = 0.7 * team_config.simulation_efficiency + 0.3 * driver_config.sim_affinity
    # score 0-100 → offset_factor 0.20 (bad) to 0.02 (excellent)
    offset_factor = SETUP_SEED_MAX_OFFSET * (1.0 - score / 100.0)

    setup = AeroSetup()

    # Apply random offsets scaled by offset_factor
    # Aero: wing angles (AeroComponent.angle_deg)
    setup.front_wing.angle_deg += _seed_offset(offset_factor, 3.0)
    setup.rear_wing.angle_deg += _seed_offset(offset_factor, 2.0)

    # Ride height
    rh_offset_mm = _seed_offset(offset_factor, 5.0)
    setup.ride_height_front_mm += rh_offset_mm
    setup.ride_height_rear_mm += rh_offset_mm * 0.8

    # Suspension rigidity
    setup.suspension_front.rigidity += _seed_offset(offset_factor, 0.1)
    setup.suspension_rear.rigidity += _seed_offset(offset_factor, 0.1)

    # Antiroll
    setup.antiroll_front_rigidity += _seed_offset(offset_factor, 0.05)
    setup.antiroll_rear_rigidity += _seed_offset(offset_factor, 0.05)

    return setup


def _seed_offset(offset_factor: float, scale: float) -> float:
    """Generate a random offset within ±(offset_factor * scale)."""
    return random.uniform(-offset_factor * scale, offset_factor * scale)


# ---------------------------------------------------------------------------
# Session planning (spec §3)
# ---------------------------------------------------------------------------

def plan_session(
    session_type: SessionType,
    team_config: AITeamConfig,
    driver_config: AIDriverConfig,
    setup_converged: bool = False,
) -> SessionPlan:
    """
    Create a session plan with 2-3 runs based on session type and team tier.

    Top teams may add an extra run if time allows.
    FP3: skip setup validation if already converged.

    Reference: ai-driver-engine-spec §3
    """
    programs = list(SESSION_PROGRAMS.get(session_type, []))

    # FP3: skip second setup validation if converged
    if session_type == SessionType.FP3 and setup_converged and len(programs) > 1:
        programs = [programs[0]]  # just quali sim

    runs: List[RunPlan] = []
    for i, prog in enumerate(programs):
        run = _create_run_plan(prog, session_type, i + 1)
        runs.append(run)

    plan = SessionPlan(
        session_type=session_type,
        team_id=team_config.team_id,
        driver_id=driver_config.driver_id,
        runs=runs,
    )
    return plan


def _create_run_plan(
    program: RunProgram,
    session_type: SessionType,
    run_index: int,
) -> RunPlan:
    """Create a RunPlan from program defaults with session-aware tweaks."""
    defaults = RUN_PROGRAM_DEFAULTS[program]
    laps_lo, laps_hi = defaults["laps_range"]
    laps = random.randint(laps_lo, laps_hi)
    compound = _select_compound(program, session_type)

    return RunPlan(
        program=program,
        laps_planned=laps,
        fuel_kg=defaults["fuel_kg"],
        compound=compound,
        engine_map=defaults["engine_map"],
        ers_mode=defaults["ers_mode"],
        push_level=defaults["push_level"],
        objective=defaults["objective"],
        priority=run_index,
    )


def _select_compound(program: RunProgram, session_type: SessionType) -> TyreCompound:
    """Select tyre compound based on program and session (spec §4)."""
    if program == RunProgram.QUALI_SIM:
        return TyreCompound.C4  # soft for quali sim
    if program == RunProgram.TYRE_TEST:
        return TyreCompound.C4 if session_type != SessionType.FP1 else TyreCompound.C3
    if program == RunProgram.TYRE_DEG:
        if session_type == SessionType.FP1:
            return random.choice([TyreCompound.C2, TyreCompound.C3])
        if session_type == SessionType.FP2:
            return random.choice([TyreCompound.C3, TyreCompound.C4])
        return TyreCompound.C3
    if program == RunProgram.RACE_SIM:
        return TyreCompound.C2
    if program == RunProgram.RACE_TRIM:
        return random.choice([TyreCompound.C2, TyreCompound.C3])
    if program == RunProgram.AERO_TEST:
        return TyreCompound.C3
    if program == RunProgram.SETUP_VALIDATION:
        if session_type == SessionType.FP1:
            return random.choice([TyreCompound.C2, TyreCompound.C3])
        if session_type == SessionType.FP3:
            return TyreCompound.C3
        return TyreCompound.C3
    if session_type == SessionType.FP1:
        return random.choice([TyreCompound.C2, TyreCompound.C3])
    if session_type == SessionType.FP3:
        return random.choice([TyreCompound.C3, TyreCompound.C4])
    return TyreCompound.C3


# ---------------------------------------------------------------------------
# Run configuration (prepare CarEntry for LapSimulator)
# ---------------------------------------------------------------------------

def _apply_setup_overrides(target: AeroSetup, source: Optional[AeroSetup]) -> None:
    """Copy slider-style values from source into target without losing base aero data."""

    if not target or not source:
        return

    def _copy_component(dst, src):
        if not dst or not src:
            return
        for attr in ("angle_deg", "angle_ref_deg", "drag_sensitivity", "cooling_contribution"):
            if hasattr(src, attr):
                setattr(dst, attr, getattr(src, attr))

    _copy_component(target.front_wing, source.front_wing)
    _copy_component(target.rear_wing, source.rear_wing)
    _copy_component(target.beam_wing, source.beam_wing)
    _copy_component(target.front_floor, source.front_floor)
    _copy_component(target.rear_floor, source.rear_floor)
    _copy_component(target.sidepods, source.sidepods)
    _copy_component(target.engine_cover, source.engine_cover)
    _copy_component(target.b_wing, source.b_wing)

    if target.suspension_front and source.suspension_front:
        target.suspension_front.rigidity = source.suspension_front.rigidity
        target.suspension_front.efficiency = source.suspension_front.efficiency
    if target.suspension_rear and source.suspension_rear:
        target.suspension_rear.rigidity = source.suspension_rear.rigidity
        target.suspension_rear.efficiency = source.suspension_rear.efficiency

    target.antiroll_front_rigidity = source.antiroll_front_rigidity
    target.antiroll_rear_rigidity = source.antiroll_rear_rigidity
    target.ride_height_front_mm = source.ride_height_front_mm
    target.ride_height_rear_mm = source.ride_height_rear_mm
    target.ride_height_optimal_front_mm = source.ride_height_optimal_front_mm
    target.ride_height_optimal_rear_mm = source.ride_height_optimal_rear_mm


def configure_run(
    run_plan: RunPlan,
    car_id: str,
    aero_setup: AeroSetup,
    driver_skills: DriverSkills,
    base_entry: Optional[CarEntry] = None,
) -> CarEntry:
    """
    Configure a CarEntry ready for LapSimulator.run_laps() based on the run plan.

    Sets fuel load, push level, and engine map from the plan.
    """
    if base_entry is None:
        state = CarState(car_id=car_id)
        entry = CarEntry(
            car_id=car_id,
            state=state,
            aero_setup=aero_setup,
            driver_skills=driver_skills,
            push_level=run_plan.push_level,
        )
    else:
        entry = base_entry
        entry.car_id = car_id
        entry.state.car_id = car_id
        entry.driver_skills = driver_skills

        _apply_setup_overrides(entry.aero_setup, aero_setup)

    state = entry.state
    state.pu.fuel_kg = run_plan.fuel_kg
    if run_plan.engine_map is not None:
        state.pu.active_map = run_plan.engine_map
    if run_plan.ers_mode is not None:
        state.ers_mode = run_plan.ers_mode.value

    compound = run_plan.compound or TyreCompound.C3
    state.tyres = {
        wp: TyreState(wheel_pos=wp, compound=compound) for wp in WheelPosition
    }
    for tyre in state.tyres.values():
        tyre.surface_temp_c = 100.0
        tyre.core_temp_c = 95.0
        tyre.wear_pct = 0.0
        tyre.lap_age = 0

    entry.push_level = run_plan.push_level
    return entry


# ---------------------------------------------------------------------------
# Post-run analysis (spec §5)
# ---------------------------------------------------------------------------

def analyze_run(
    run_plan: RunPlan,
    lap_results: List[LapResult],
    driver_config: AIDriverConfig,
    aero_setup: AeroSetup,
) -> RunResult:
    """
    Analyze completed run results and propose setup adjustments.

    Extracts telemetry summary, evaluates setup deltas, and generates
    adjustment proposals based on driver feedback accuracy.

    Reference: ai-driver-engine-spec §5
    """
    if not lap_results:
        return RunResult(
            run_plan=run_plan,
            outcome=RunOutcome.ABORTED,
            abort_reason="No lap results",
        )

    # Build telemetry summary
    telemetry = _build_telemetry_summary(lap_results)

    # Evaluate setup feedback signals
    _compute_setup_deltas(telemetry, lap_results)

    # Determine if setup has converged
    converged = (
        abs(telemetry.aero_balance_delta) < SETUP_CONVERGENCE_THRESHOLD
        and abs(telemetry.drag_index_delta) < SETUP_CONVERGENCE_THRESHOLD
        and abs(telemetry.brake_cooling_delta) < SETUP_CONVERGENCE_THRESHOLD
        and abs(telemetry.traction_index_delta) < SETUP_CONVERGENCE_THRESHOLD
    )

    # Generate setup adjustments if not converged
    adjustments: List[SetupAdjustment] = []
    if not converged and run_plan.program in (
        RunProgram.SETUP_VALIDATION, RunProgram.TYRE_DEG
    ):
        adjustments = _propose_adjustments(
            telemetry, driver_config, aero_setup
        )

    # Determine outcome
    outcome = RunOutcome.SUCCESS
    if telemetry.total_laps < run_plan.laps_planned:
        outcome = RunOutcome.PARTIAL

    return RunResult(
        run_plan=run_plan,
        outcome=outcome,
        telemetry=telemetry,
        setup_adjustments=adjustments,
        setup_converged=converged,
    )


def _build_telemetry_summary(lap_results: List[LapResult]) -> RunTelemetrySummary:
    """Extract condensed telemetry from lap results."""
    times = [lr.lap_time_s for lr in lap_results if lr.lap_time_s > 0]
    if not times:
        return RunTelemetrySummary()

    best = min(times)
    avg = sum(times) / len(times)
    last = lap_results[-1]

    # Average grip from last lap's section results
    grips_f = [sr.effective_grip_front for sr in last.section_results]
    grips_r = [sr.effective_grip_rear for sr in last.section_results]
    avg_gf = sum(grips_f) / max(len(grips_f), 1)
    avg_gr = sum(grips_r) / max(len(grips_r), 1)

    fuel_used = lap_results[0].fuel_kg - last.fuel_kg if len(lap_results) > 1 else 0.0

    return RunTelemetrySummary(
        best_lap_time_s=best,
        avg_lap_time_s=avg,
        total_laps=len(lap_results),
        fuel_used_kg=fuel_used,
        avg_tyre_wear_pct=last.avg_tyre_wear_pct,
        avg_tyre_temp_c=last.avg_tyre_temp_surface_c,
        avg_grip_front=avg_gf,
        avg_grip_rear=avg_gr,
    )


def _compute_setup_deltas(
    telemetry: RunTelemetrySummary,
    lap_results: List[LapResult],
) -> None:
    """Compute setup feedback deltas from telemetry data."""
    if not lap_results:
        return

    last = lap_results[-1]

    # Aero balance: front grip vs rear grip imbalance
    grip_balance = telemetry.avg_grip_front - telemetry.avg_grip_rear
    telemetry.aero_balance_delta = grip_balance  # + = too much front

    # Drag index: inferred from straight speed vs expected
    # Simplified: if avg lap time is high, drag might be too much
    telemetry.drag_index_delta = 0.0  # neutral until we have reference

    # Traction: rear grip relative to front
    telemetry.traction_index_delta = -grip_balance  # inverse of balance

    # Brake cooling: inferred from brake temps in last lap
    # High temps → brakes too hot → need more cooling
    brake_events = [e for e in last.events if "brake" in e.event_type.lower()]
    telemetry.brake_cooling_delta = len(brake_events) * 0.1


def _propose_adjustments(
    telemetry: RunTelemetrySummary,
    driver_config: AIDriverConfig,
    aero_setup: AeroSetup,
) -> List[SetupAdjustment]:
    """
    Propose setup adjustments based on telemetry deltas.

    Feedback accuracy depends on driver sim_affinity + mechanical_sympathy.
    Higher skill → more accurate adjustments.

    Reference: ai-driver-engine-spec §5
    """
    adjustments: List[SetupAdjustment] = []

    # Feedback accuracy: 0.5 (bad) to 1.0 (excellent)
    accuracy = 0.5 + (driver_config.sim_affinity + driver_config.mechanical_sympathy) / 400.0
    accuracy = clamp(accuracy, 0.5, 1.0)

    # Aero balance: adjust front wing angle
    if abs(telemetry.aero_balance_delta) > SETUP_CONVERGENCE_THRESHOLD:
        direction = -1.0 if telemetry.aero_balance_delta > 0 else 1.0
        magnitude = abs(telemetry.aero_balance_delta) * accuracy * 1.5
        new_angle = aero_setup.front_wing.angle_deg + direction * magnitude
        adjustments.append(SetupAdjustment(
            slider_name="front_wing_angle",
            old_value=aero_setup.front_wing.angle_deg,
            new_value=round(new_angle, 2),
            reason="Aero balance correction",
        ))

    # Traction: adjust rear antiroll
    if abs(telemetry.traction_index_delta) > SETUP_CONVERGENCE_THRESHOLD:
        direction = 1.0 if telemetry.traction_index_delta > 0 else -1.0
        magnitude = abs(telemetry.traction_index_delta) * accuracy * 0.03
        new_antiroll = aero_setup.antiroll_rear_rigidity + direction * magnitude
        adjustments.append(SetupAdjustment(
            slider_name="antiroll_rear",
            old_value=aero_setup.antiroll_rear_rigidity,
            new_value=round(new_antiroll, 3),
            reason="Traction adjustment",
        ))

    # Brake cooling: adjust duct opening (via brake state, simplified)
    if telemetry.brake_cooling_delta > SETUP_CONVERGENCE_THRESHOLD:
        adjustments.append(SetupAdjustment(
            slider_name="brake_duct_opening",
            old_value=0.5,
            new_value=round(min(0.5 + telemetry.brake_cooling_delta * accuracy * 0.2, 1.0), 2),
            reason="Brake cooling increase",
        ))

    return adjustments


def apply_adjustments(
    aero_setup: AeroSetup,
    adjustments: List[SetupAdjustment],
) -> AeroSetup:
    """Apply proposed setup adjustments to the AeroSetup."""
    for adj in adjustments:
        if adj.slider_name == "front_wing_angle":
            aero_setup.front_wing.angle_deg = adj.new_value
        elif adj.slider_name == "rear_wing_angle":
            aero_setup.rear_wing.angle_deg = adj.new_value
        elif adj.slider_name == "antiroll_rear":
            aero_setup.antiroll_rear_rigidity = adj.new_value
        elif adj.slider_name == "antiroll_front":
            aero_setup.antiroll_front_rigidity = adj.new_value
        elif adj.slider_name == "ride_height_front":
            aero_setup.ride_height_front_mm = adj.new_value
        elif adj.slider_name == "ride_height_rear":
            aero_setup.ride_height_rear_mm = adj.new_value
        # brake_duct_opening handled by CarState.brakes, not AeroSetup
    return aero_setup


# ---------------------------------------------------------------------------
# Pit work calculation (spec §4.1)
# ---------------------------------------------------------------------------

def compute_pit_stop(
    has_tyre_change: bool = True,
    has_refuel: bool = True,
    fuel_kg: float = 50.0,
    setup_adjustments: int = 0,
    has_brake_duct_change: bool = False,
    has_wing_replace: bool = False,
    has_inspection: bool = False,
) -> PitStop:
    """
    Compute pit stop duration from work items.

    Formula: total = max(work_durations) + PIT_OVERHEAD_S
    Parallel work: team works on different areas simultaneously.

    Reference: ai-driver-engine-spec §4.1
    """
    items: List[PitWorkItem] = []

    if has_tyre_change:
        lo, hi = PIT_WORK_TIMES[PitWorkType.TYRE_CHANGE]
        items.append(PitWorkItem(PitWorkType.TYRE_CHANGE, random.uniform(lo, hi)))

    if has_refuel:
        # Refuel time scales with fuel amount (~1 s/kg, clamped to range)
        lo, hi = PIT_WORK_TIMES[PitWorkType.REFUEL]
        refuel_time = clamp(fuel_kg * 1.0, lo, hi)
        items.append(PitWorkItem(PitWorkType.REFUEL, refuel_time))

    if setup_adjustments > 0:
        if setup_adjustments <= 2:
            lo, hi = PIT_WORK_TIMES[PitWorkType.SETUP_MINOR]
        else:
            lo, hi = PIT_WORK_TIMES[PitWorkType.SETUP_MAJOR]
        items.append(PitWorkItem(
            PitWorkType.SETUP_MINOR if setup_adjustments <= 2 else PitWorkType.SETUP_MAJOR,
            random.uniform(lo, hi),
        ))

    if has_brake_duct_change:
        lo, hi = PIT_WORK_TIMES[PitWorkType.BRAKE_DUCT]
        items.append(PitWorkItem(PitWorkType.BRAKE_DUCT, random.uniform(lo, hi)))

    if has_wing_replace:
        lo, hi = PIT_WORK_TIMES[PitWorkType.WING_REPLACE]
        items.append(PitWorkItem(PitWorkType.WING_REPLACE, random.uniform(lo, hi)))

    if has_inspection:
        lo, hi = PIT_WORK_TIMES[PitWorkType.INSPECTION]
        items.append(PitWorkItem(PitWorkType.INSPECTION, random.uniform(lo, hi)))

    # If no work items, just overhead (quick stop)
    if not items:
        return PitStop(
            total_duration_s=PIT_OVERHEAD_S,
            status_label=CarStatus.BOX_READY,
            description="Quick stop",
        )

    # Total = max(durations) + overhead (parallel work)
    max_duration = max(item.duration_s for item in items)
    total = max_duration + PIT_OVERHEAD_S

    # Status label = label of the longest work item
    longest_item = max(items, key=lambda x: x.duration_s)
    status_label = PIT_WORK_STATUS.get(longest_item.work_type, CarStatus.BOX_CHECK)

    # Human-readable description
    work_names = {
        PitWorkType.TYRE_CHANGE: "Tyre change",
        PitWorkType.REFUEL: "Refuel",
        PitWorkType.SETUP_MINOR: "Setup adj.",
        PitWorkType.SETUP_MAJOR: "Setup (major)",
        PitWorkType.BRAKE_DUCT: "Brake duct",
        PitWorkType.WING_REPLACE: "Wing replace",
        PitWorkType.INSPECTION: "Inspection",
    }
    desc_parts = [work_names.get(item.work_type, item.work_type.value) for item in items]
    description = " + ".join(desc_parts) + f" (~{int(total)}s)"

    return PitStop(
        work_items=items,
        total_duration_s=total,
        status_label=status_label,
        description=description,
    )


# ---------------------------------------------------------------------------
# Event generation (spec §7)
# ---------------------------------------------------------------------------

def emit_run_event(
    event_type: str,
    team_config: AITeamConfig,
    driver_config: AIDriverConfig,
    run_plan: Optional[RunPlan] = None,
    run_result: Optional[RunResult] = None,
    message: str = "",
    priority: NotificationPriority = NotificationPriority.NORMAL,
) -> AIPracticeRunEvent:
    """Create an AI practice run event for HUD/telemetry/QA."""
    return AIPracticeRunEvent(
        event_type=event_type,
        team_id=team_config.team_id,
        driver_id=driver_config.driver_id,
        program=run_plan.program.value if run_plan else "",
        laps=run_plan.laps_planned if run_plan else 0,
        compound=run_plan.compound.value if run_plan else "",
        fuel_kg=run_plan.fuel_kg if run_plan else 0.0,
        engine_map=run_plan.engine_map.value if run_plan else "",
        ers_mode=run_plan.ers_mode.value if run_plan else "",
        outcome=run_result.outcome.value if run_result else "",
        message=message,
        priority=priority.value,
    )


# ---------------------------------------------------------------------------
# AIDriverEngine – main orchestrator class
# ---------------------------------------------------------------------------

class AIDriverEngine:
    """
    Manages the full practice session lifecycle for one AI car.

    Usage:
        engine = AIDriverEngine(circuit_config, team_config, driver_config, driver_skills)
        session_plan = engine.start_session(SessionType.FP1)
        while engine.has_next_run():
            run_plan = engine.next_run()
            car_entry = engine.configure_current_run()
            # ... run with LapSimulator ...
            engine.complete_run(lap_results)
        summary = engine.session_summary()
    """

    def __init__(
        self,
        circuit_config: CircuitConfig,
        team_config: AITeamConfig,
        driver_config: AIDriverConfig,
        driver_skills: DriverSkills,
    ):
        self.circuit_config = circuit_config
        self.team_config = team_config
        self.driver_config = driver_config
        self.driver_skills = driver_skills

        # Setup state
        self.aero_setup: AeroSetup = generate_setup_seed(
            circuit_config, team_config, driver_config
        )
        self.setup_converged: bool = False

        # Session state
        self.session_plan: Optional[SessionPlan] = None
        self.current_run_idx: int = 0
        self.run_results: List[RunResult] = []
        self.events: List[AIPracticeRunEvent] = []
        self.elapsed_s: float = 0.0
        self.car_status: CarStatus = CarStatus.BOX_READY
        self.last_pit_stop: Optional[PitStop] = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(self, session_type: SessionType) -> SessionPlan:
        """Initialize session plan and reset state."""
        self.session_plan = plan_session(
            session_type, self.team_config, self.driver_config,
            setup_converged=self.setup_converged,
        )
        self.current_run_idx = 0
        self.run_results = []
        self.events = []
        self.elapsed_s = 0.0

        logger.info(
            "AI %s/%s: planned %d runs for %s",
            self.team_config.team_id,
            self.driver_config.driver_id,
            len(self.session_plan.runs),
            session_type.value,
        )
        return self.session_plan

    def has_next_run(self) -> bool:
        """Check if there are more runs to execute."""
        if self.session_plan is None:
            return False
        if self.current_run_idx >= len(self.session_plan.runs):
            return False
        if self.elapsed_s >= self.session_plan.session_duration_s:
            return False
        return True

    def next_run(self) -> Optional[RunPlan]:
        """Get the next run plan."""
        if not self.has_next_run():
            return None
        return self.session_plan.runs[self.current_run_idx]

    def configure_current_run(self, base_entry: Optional[CarEntry] = None) -> Optional[CarEntry]:
        """Configure a CarEntry for the current run plan."""
        run_plan = self.next_run()
        if run_plan is None:
            return None

        car_id = f"{self.team_config.team_id}_{self.driver_config.driver_id}"
        entry = configure_run(
            run_plan, car_id, self.aero_setup, self.driver_skills, base_entry=base_entry
        )

        # Emit start event
        event = emit_run_event(
            "ai_run_started", self.team_config, self.driver_config,
            run_plan=run_plan,
            message=f"Starting {run_plan.program.value} ({run_plan.laps_planned} laps)",
            priority=NotificationPriority.LOW,
        )
        self.events.append(event)
        self.car_status = CarStatus.OUT_LAP

        return entry

    def complete_run(self, lap_results: List[LapResult]) -> RunResult:
        """
        Analyze completed run, apply setup adjustments, advance to next run.

        Returns the RunResult with telemetry and proposed adjustments.
        """
        run_plan = self.next_run()
        if run_plan is None:
            return RunResult(outcome=RunOutcome.ABORTED, abort_reason="No active run")

        # Analyze
        result = analyze_run(
            run_plan, lap_results, self.driver_config, self.aero_setup
        )
        self.run_results.append(result)

        # Apply adjustments if any
        if result.setup_adjustments:
            self.aero_setup = apply_adjustments(
                self.aero_setup, result.setup_adjustments
            )
            adj_event = emit_run_event(
                "ai_setup_adjustment", self.team_config, self.driver_config,
                run_plan=run_plan,
                message=f"Adjusted {len(result.setup_adjustments)} sliders",
            )
            self.events.append(adj_event)

        # Update convergence
        was_converged = self.setup_converged
        if result.setup_converged:
            self.setup_converged = True

        # Emit completion event
        event = emit_run_event(
            "ai_run_completed", self.team_config, self.driver_config,
            run_plan=run_plan, run_result=result,
            message=f"Run complete \u2013 best: {result.telemetry.best_lap_time_s:.1f}s",
        )
        self.events.append(event)

        # Setup convergence notification
        if result.setup_converged and not was_converged:
            conv_event = emit_run_event(
                "ai_setup_converged", self.team_config, self.driver_config,
                run_plan=run_plan,
                message="Setup OK \u2013 all targets in range",
                priority=NotificationPriority.HIGH,
            )
            self.events.append(conv_event)

        # Compute pit stop duration from actual work items
        n_adjustments = len(result.setup_adjustments)
        has_brake_adj = any(
            a.slider_name == "brake_duct_opening" for a in result.setup_adjustments
        )
        pit_stop = compute_pit_stop(
            has_tyre_change=True,
            has_refuel=True,
            fuel_kg=run_plan.fuel_kg,
            setup_adjustments=n_adjustments,
            has_brake_duct_change=has_brake_adj,
        )
        self.last_pit_stop = pit_stop
        self.car_status = pit_stop.status_label

        # Emit pit work events
        pit_start_event = emit_run_event(
            "ai_pit_work_started", self.team_config, self.driver_config,
            run_plan=run_plan,
            message=f"Pit: {pit_stop.description}",
        )
        self.events.append(pit_start_event)

        pit_end_event = emit_run_event(
            "ai_pit_work_complete", self.team_config, self.driver_config,
            run_plan=run_plan,
            message="Work complete \u2013 ready to go",
        )
        self.events.append(pit_end_event)

        # Advance time (run laps + pit stop duration)
        run_time_s = sum(lr.lap_time_s for lr in lap_results)
        self.elapsed_s += run_time_s + pit_stop.total_duration_s
        self.car_status = CarStatus.BOX_READY

        # Advance to next run
        self.current_run_idx += 1

        logger.info(
            "AI %s/%s: run %d/%d complete (%s), best=%.1fs, converged=%s",
            self.team_config.team_id,
            self.driver_config.driver_id,
            self.current_run_idx,
            len(self.session_plan.runs) if self.session_plan else 0,
            result.outcome.value,
            result.telemetry.best_lap_time_s,
            result.setup_converged,
        )

        return result

    def session_summary(self) -> Dict:
        """Return a summary of the completed session."""
        return {
            "team_id": self.team_config.team_id,
            "driver_id": self.driver_config.driver_id,
            "session_type": self.session_plan.session_type.value if self.session_plan else "",
            "runs_completed": len(self.run_results),
            "runs_planned": len(self.session_plan.runs) if self.session_plan else 0,
            "setup_converged": self.setup_converged,
            "elapsed_s": round(self.elapsed_s, 1),
            "best_lap_s": min(
                (r.telemetry.best_lap_time_s for r in self.run_results
                 if r.telemetry.best_lap_time_s > 0),
                default=0.0,
            ),
            "total_adjustments": sum(
                len(r.setup_adjustments) for r in self.run_results
            ),
            "events": len(self.events),
        }
