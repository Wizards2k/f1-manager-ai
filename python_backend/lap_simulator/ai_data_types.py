"""
AI Driver Engine – Data types for practice session AI behavior.

Defines run programs, plans, team configuration and run results
used by the AIDriverEngine to manage 18 AI cars during practice.

Reference: docs/ai-driver-engine-spec.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .data_types import EngineMapName, ERSModeName, TyreCompound


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SessionType(str, Enum):
    FP1 = "FP1"
    FP2 = "FP2"
    FP3 = "FP3"


class RunProgram(str, Enum):
    """Practice run programs as defined in ai-driver-engine-spec §3."""
    SETUP_VALIDATION = "SetupValidation"
    TYRE_DEG = "TyreDeg"
    QUALI_SIM = "QualiSim"
    RACE_TRIM = "RaceTrim"
    AERO_RND = "AeroRnD"          # placeholder


class RunOutcome(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    ABORTED = "aborted"


class PitWorkType(str, Enum):
    """Types of pit box work as defined in ai-driver-engine-spec §4.1."""
    TYRE_CHANGE = "TYRE_CHANGE"
    REFUEL = "REFUEL"
    SETUP_MINOR = "SETUP_MINOR"
    SETUP_MAJOR = "SETUP_MAJOR"
    BRAKE_DUCT = "BRAKE_DUCT"
    WING_REPLACE = "WING_REPLACE"
    INSPECTION = "INSPECTION"


class CarStatus(str, Enum):
    """Car status labels for UI (ai-driver-engine-spec §4.2)."""
    OUT_LAP = "Out Lap"
    HOT_LAP = "Hot Lap"
    IN_LAP = "In Lap"
    BOX_TYRES = "Box - Tyres"
    BOX_FUEL = "Box - Fuel"
    BOX_SETUP = "Box - Setup"
    BOX_CHECK = "Box - Check"
    BOX_READY = "Box - Ready"


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Pit work times (spec §4.1) — (min_s, max_s)
# ---------------------------------------------------------------------------

PIT_WORK_TIMES: Dict[PitWorkType, tuple] = {
    PitWorkType.TYRE_CHANGE:  (25, 30),
    PitWorkType.REFUEL:       (40, 60),
    PitWorkType.SETUP_MINOR:  (60, 90),
    PitWorkType.SETUP_MAJOR:  (120, 180),
    PitWorkType.BRAKE_DUCT:   (45, 60),
    PitWorkType.WING_REPLACE: (90, 120),
    PitWorkType.INSPECTION:   (30, 45),
}

PIT_OVERHEAD_S: float = 15.0  # pitlane entry + positioning + exit

# Map PitWorkType → CarStatus label shown during that work
PIT_WORK_STATUS: Dict[PitWorkType, CarStatus] = {
    PitWorkType.TYRE_CHANGE:  CarStatus.BOX_TYRES,
    PitWorkType.REFUEL:       CarStatus.BOX_FUEL,
    PitWorkType.SETUP_MINOR:  CarStatus.BOX_SETUP,
    PitWorkType.SETUP_MAJOR:  CarStatus.BOX_SETUP,
    PitWorkType.BRAKE_DUCT:   CarStatus.BOX_SETUP,
    PitWorkType.WING_REPLACE: CarStatus.BOX_SETUP,
    PitWorkType.INSPECTION:   CarStatus.BOX_CHECK,
}


# ---------------------------------------------------------------------------
# Team & driver AI config
# ---------------------------------------------------------------------------

@dataclass
class AITeamConfig:
    """AI-specific team parameters for practice behavior."""
    team_id: str = ""
    team_name: str = ""
    simulation_efficiency: int = 70    # 0-100, quality of sim department
    budget_tier: str = "midfield"      # "top" / "midfield" / "backmarker"
    max_runs_per_session: int = 3


@dataclass
class AIDriverConfig:
    """AI-specific driver parameters for practice behavior."""
    driver_id: str = ""
    driver_name: str = ""
    sim_affinity: int = 60             # 0-100, how well driver uses sim data
    # These map to DriverSkills fields used by the refinement loop
    setup_finding_skill: int = 60      # mirrors DriverSkills.setup_finding
    tyre_management_skill: int = 70    # mirrors DriverSkills.tyre_management
    mechanical_sympathy: int = 60      # feedback accuracy


# ---------------------------------------------------------------------------
# Run planning
# ---------------------------------------------------------------------------

@dataclass
class RunPlan:
    """A single planned run in a practice session."""
    program: RunProgram
    laps_planned: int = 5
    fuel_kg: float = 60.0
    compound: TyreCompound = TyreCompound.C3
    engine_map: EngineMapName = EngineMapName.STANDARD
    ers_mode: ERSModeName = ERSModeName.BALANCED
    push_level: float = 0.95           # AI push level for this run
    objective: str = ""                # human-readable objective
    priority: int = 1                  # 1=high, 3=low


# Run program defaults (from spec §3 + §6)
RUN_PROGRAM_DEFAULTS: Dict[RunProgram, dict] = {
    RunProgram.SETUP_VALIDATION: dict(
        laps_range=(3, 6),
        fuel_kg=50.0,
        compound=TyreCompound.C3,  # Medium equivalent
        engine_map=EngineMapName.STANDARD,
        ers_mode=ERSModeName.BALANCED,
        push_level=7,  # Conservative setup validation
        objective="Validate setup seed vs real data",
    ),
    RunProgram.TYRE_DEG: dict(
        laps_range=(6, 9),
        fuel_kg=75.0,
        compound=TyreCompound.C4,    # Soft equivalent
        engine_map=EngineMapName.STANDARD,
        ers_mode=ERSModeName.HARVEST,
        push_level=8,  # Medium pace for tyre testing
        objective="Measure tyre degradation and brake temps",
    ),
    RunProgram.QUALI_SIM: dict(
        laps_range=(3, 4),       # out + push + cool
        fuel_kg=15.0,
        compound=TyreCompound.C4,    # Soft equivalent
        engine_map=EngineMapName.QUALY,
        ers_mode=ERSModeName.ATTACK,
        push_level=10,  # Maximum attack for qualifying
        objective="Calibrate qualifying reference time",
    ),
    RunProgram.RACE_TRIM: dict(
        laps_range=(5, 8),
        fuel_kg=95.0,
        compound=TyreCompound.C2,    # Hard equivalent
        engine_map=EngineMapName.STANDARD,
        ers_mode=ERSModeName.BALANCED,
        push_level=8,  # Race pace
        objective="Validate full-tank race behavior",
    ),
    RunProgram.AERO_RND: dict(
        laps_range=(3, 5),
        fuel_kg=40.0,
        compound=TyreCompound.C3,  # Medium equivalent
        engine_map=EngineMapName.STANDARD,
        ers_mode=ERSModeName.BALANCED,
        push_level=6,  # Low pace for aero testing
        objective="Correlate aero/R&D upgrade (placeholder)",
    ),
}

# Session program templates (from spec §3 table)
SESSION_PROGRAMS: Dict[SessionType, List[RunProgram]] = {
    SessionType.FP1: [
        RunProgram.SETUP_VALIDATION,
        RunProgram.SETUP_VALIDATION,
        RunProgram.TYRE_DEG,
    ],
    SessionType.FP2: [
        RunProgram.TYRE_DEG,
        RunProgram.QUALI_SIM,
        RunProgram.RACE_TRIM,
    ],
    SessionType.FP3: [
        RunProgram.QUALI_SIM,
        RunProgram.SETUP_VALIDATION,  # only if setup not converged
    ],
}


@dataclass
class SessionPlan:
    """Complete plan for a practice session."""
    session_type: SessionType
    team_id: str = ""
    driver_id: str = ""
    runs: List[RunPlan] = field(default_factory=list)
    session_duration_s: float = 3600.0  # 60 minutes


# ---------------------------------------------------------------------------
# Run results & telemetry summary
# ---------------------------------------------------------------------------

@dataclass
class RunTelemetrySummary:
    """Condensed telemetry from a completed run."""
    best_lap_time_s: float = 0.0
    avg_lap_time_s: float = 0.0
    total_laps: int = 0
    fuel_used_kg: float = 0.0
    avg_tyre_wear_pct: float = 0.0
    avg_tyre_temp_c: float = 0.0
    max_brake_temp_c: float = 0.0
    avg_grip_front: float = 0.0
    avg_grip_rear: float = 0.0
    # Setup feedback signals (delta vs target)
    aero_balance_delta: float = 0.0    # + = too much front DF
    drag_index_delta: float = 0.0      # + = too much drag
    traction_index_delta: float = 0.0  # + = too much rear grip
    brake_cooling_delta: float = 0.0   # + = brakes too hot


@dataclass
class SetupAdjustment:
    """A single setup slider adjustment proposed by the AI."""
    slider_name: str = ""
    old_value: float = 0.0
    new_value: float = 0.0
    reason: str = ""


@dataclass
class RunResult:
    """Result of a completed AI practice run."""
    run_plan: Optional[RunPlan] = None
    outcome: RunOutcome = RunOutcome.SUCCESS
    telemetry: RunTelemetrySummary = field(default_factory=RunTelemetrySummary)
    setup_adjustments: List[SetupAdjustment] = field(default_factory=list)
    setup_converged: bool = False      # all indices in target range
    abort_reason: str = ""


# ---------------------------------------------------------------------------
# AI practice run event (for logging / HUD)
# ---------------------------------------------------------------------------

@dataclass
class PitWorkItem:
    """A single piece of work to be done in the pit box."""
    work_type: PitWorkType
    duration_s: float = 0.0            # actual duration (randomised from range)


@dataclass
class PitStop:
    """A complete pit stop with one or more work items."""
    work_items: List[PitWorkItem] = field(default_factory=list)
    total_duration_s: float = 0.0      # max(durations) + PIT_OVERHEAD_S
    status_label: CarStatus = CarStatus.BOX_CHECK
    description: str = ""              # human-readable, e.g. "Tyre change + Setup adj."


@dataclass
class AIPracticeRunEvent:
    """Event emitted by AI Driver Engine for HUD/telemetry/QA."""
    event_type: str = ""               # ai_run_started, ai_run_completed, etc.
    team_id: str = ""
    driver_id: str = ""
    program: str = ""
    laps: int = 0
    compound: str = ""
    fuel_kg: float = 0.0
    engine_map: str = ""
    ers_mode: str = ""
    outcome: str = ""
    message: str = ""
    priority: str = NotificationPriority.NORMAL.value
