from __future__ import annotations
"""
Practice Session Orchestrator – coordinates FP1/FP2/FP3.

Manages 18 AI + 2 player cars through a 60-minute practice session:
- Session clock with pause/fast-forward
- Tyre inventory (check-out/check-in, heat cycles, EOL)
- Pitlane queue with cooldown and priority
- Run scheduling and execution via LapSimulator + AIDriverEngine
- Run logging and event emission

Reference: docs/practice-session-orchestrator.md
           docs/tyre-allocation.md
"""

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .ai_data_types import (
    CarStatus,
    NotificationPriority,
    RunOutcome,
    RunProgram,
    SessionType,
)
from .data_types import TyreCompound

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_DURATION_S = 3600             # 60 minutes
PITLANE_COOLDOWN_S = 120             # min time between runs (tyre change + minor setup)
PITLANE_QUEUE_DELAY_S = 7            # avg delay per queued car
MAX_PITLANE_SLOTS = 20               # max cars on track simultaneously (full grid)
PITLANE_TRAVEL_S = 20                # time to traverse pitlane (in + out)
MIN_PIT_EXIT_GAP_S = 3.0             # enforce at least 3s between pit releases


# ---------------------------------------------------------------------------
# Tyre Inventory (tyre-allocation.md §2-§6)
# ---------------------------------------------------------------------------

class TyreSetStatus(str, Enum):
    NEW = "new"
    USED = "used"
    END_OF_LIFE = "eol"


@dataclass
class TyreSet:
    """A single set of tyres (4 wheels)."""
    set_id: str
    compound: TyreCompound
    heat_cycles: int = 0
    km_driven: float = 0.0
    status: TyreSetStatus = TyreSetStatus.NEW
    current_car_id: Optional[str] = None  # None = in inventory

    @property
    def is_available(self) -> bool:
        return self.status != TyreSetStatus.END_OF_LIFE and self.current_car_id is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "set_id": self.set_id,
            "compound": self.compound.value,
            "heat_cycles": self.heat_cycles,
            "km_driven": self.km_driven,
            "status": self.status.value,
            "current_car_id": self.current_car_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TyreSet:
        data["compound"] = TyreCompound(data["compound"])
        data["status"] = TyreSetStatus(data["status"])
        return cls(**data)


# Default allocation per tyre-allocation.md §2
DEFAULT_DRY_ALLOCATION = {
    TyreCompound.C1: 2,   # Hard
    TyreCompound.C2: 3,   # Medium
    TyreCompound.C3: 3,   # Medium (if C3 is medium for the event)
    TyreCompound.C4: 3,   # Soft-ish
    TyreCompound.C5: 8,   # Soft
}

DEFAULT_WET_ALLOCATION = {
    TyreCompound.INTERMEDIATE: 4,
    TyreCompound.WET: 3,
}

# Mapping from generic S/M/H to actual compounds (event-specific)
# This will be configured per event; defaults assume C3=M, C4=S
COMPOUND_ROLE_DEFAULT = {
    "hard": TyreCompound.C2,
    "medium": TyreCompound.C3,
    "soft": TyreCompound.C4,
}


class TyreInventory:
    """
    Manages tyre sets for one team across a weekend.

    Implements check-out/check-in per tyre-allocation.md §6.
    """

    def __init__(
        self,
        team_id: str,
        allocation: Optional[Dict[TyreCompound, int]] = None,
        eol_threshold: int = 5,
    ):
        self.team_id = team_id
        self.eol_threshold = eol_threshold
        self.sets: Dict[str, TyreSet] = {}
        self._next_id = 0

        alloc = allocation or {**DEFAULT_DRY_ALLOCATION, **DEFAULT_WET_ALLOCATION}
        for compound, count in alloc.items():
            for _ in range(count):
                sid = f"{team_id}_{compound.value}_{self._next_id}"
                self._next_id += 1
                self.sets[sid] = TyreSet(set_id=sid, compound=compound)

    def available_sets(self, compound: Optional[TyreCompound] = None) -> List[TyreSet]:
        """List available sets, optionally filtered by compound."""
        return [
            s for s in self.sets.values()
            if s.is_available and (compound is None or s.compound == compound)
        ]

    def new_sets(self, compound: Optional[TyreCompound] = None) -> List[TyreSet]:
        """List new (unused) sets."""
        return [
            s for s in self.available_sets(compound)
            if s.status == TyreSetStatus.NEW
        ]

    def used_sets(self, compound: Optional[TyreCompound] = None) -> List[TyreSet]:
        """List used but available sets."""
        return [
            s for s in self.available_sets(compound)
            if s.status == TyreSetStatus.USED
        ]

    def checkout(
        self,
        car_id: str,
        compound: TyreCompound,
        prefer_new: bool = True,
    ) -> Optional[TyreSet]:
        """
        Reserve a tyre set for a car.

        Returns the TyreSet or None if unavailable.
        """
        candidates = self.available_sets(compound)
        if not candidates:
            return None

        if prefer_new:
            new = [s for s in candidates if s.status == TyreSetStatus.NEW]
            if new:
                candidates = new

        # Pick the one with fewest heat cycles
        candidates.sort(key=lambda s: s.heat_cycles)
        chosen = candidates[0]
        chosen.current_car_id = car_id
        return chosen

    def checkin(self, set_id: str, km_driven: float = 0.0) -> None:
        """
        Return a tyre set after a run. Increments heat_cycles.
        """
        ts = self.sets.get(set_id)
        if ts is None:
            return
        ts.current_car_id = None
        ts.heat_cycles += 1
        ts.km_driven += km_driven
        if ts.status == TyreSetStatus.NEW:
            ts.status = TyreSetStatus.USED
        if ts.heat_cycles >= self.eol_threshold:
            ts.status = TyreSetStatus.END_OF_LIFE

    def summary(self) -> Dict[str, Any]:
        """Inventory summary for UI."""
        by_compound: Dict[str, dict] = {}
        for s in self.sets.values():
            key = s.compound.value
            if key not in by_compound:
                by_compound[key] = {"new": 0, "used": 0, "eol": 0, "in_use": 0}
            if s.current_car_id:
                by_compound[key]["in_use"] += 1
            elif s.status == TyreSetStatus.NEW:
                by_compound[key]["new"] += 1
            elif s.status == TyreSetStatus.USED:
                by_compound[key]["used"] += 1
            else:
                by_compound[key]["eol"] += 1
        return by_compound

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "eol_threshold": self.eol_threshold,
            "sets": {k: s.to_dict() for k, s in self.sets.items()},
            "_next_id": self._next_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TyreInventory:
        inv = cls(team_id=data["team_id"], allocation={}, eol_threshold=data["eol_threshold"])
        inv.sets = {k: TyreSet.from_dict(v) for k, v in data["sets"].items()}
        inv._next_id = data["_next_id"]
        return inv


# ---------------------------------------------------------------------------
# Session Clock (spec §2.1, §2.3)
# ---------------------------------------------------------------------------

class SessionFlag(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass
class SessionClock:
    """
    Official session timer with pause/fast-forward support.
    """
    duration_s: int = SESSION_DURATION_S
    elapsed_s: float = 0.0
    speed_multiplier: float = 1.0     # 1=normal, 2/4/6=fast-forward
    paused: bool = False
    flag: SessionFlag = SessionFlag.GREEN

    @property
    def remaining_s(self) -> float:
        return max(0.0, self.duration_s - self.elapsed_s)

    @property
    def is_finished(self) -> bool:
        return self.elapsed_s >= self.duration_s

    def tick(self, real_dt_s: float = 1.0) -> float:
        """
        Advance the clock by real_dt_s (scaled by speed_multiplier).

        Returns the simulated time elapsed this tick.
        """
        if self.paused or self.is_finished:
            return 0.0
        sim_dt = real_dt_s * self.speed_multiplier
        self.elapsed_s = min(self.elapsed_s + sim_dt, self.duration_s)
        return sim_dt

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def set_speed(self, multiplier: float) -> None:
        self.speed_multiplier = max(1.0, min(multiplier, 6.0))

    def set_flag(self, flag: SessionFlag) -> None:
        prev = self.flag
        self.flag = flag
        # Red flag suspends the clock
        if flag == SessionFlag.RED and not self.paused:
            self.paused = True
        # Returning to green resumes the clock (if it was paused by a flag)
        if flag == SessionFlag.GREEN and prev in (SessionFlag.RED, SessionFlag.YELLOW):
            self.paused = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duration_s": self.duration_s,
            "elapsed_s": self.elapsed_s,
            "speed_multiplier": self.speed_multiplier,
            "paused": self.paused,
            "flag": self.flag.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SessionClock:
        data["flag"] = SessionFlag(data["flag"])
        return cls(**data)


# ---------------------------------------------------------------------------
# Pitlane Queue (spec §3.2)
# ---------------------------------------------------------------------------

class PitlanePriority(int, Enum):
    PLAYER = 0          # highest
    AI_CRITICAL = 1     # quali sim, last run
    AI_STANDARD = 2     # normal


@dataclass
class PitlaneRequest:
    """A request to exit the pitlane."""
    car_id: str
    team_id: str
    priority: PitlanePriority = PitlanePriority.AI_STANDARD
    requested_at_s: float = 0.0
    release_at_s: float = 0.0         # when the car can actually exit
    is_player: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "car_id": self.car_id,
            "team_id": self.team_id,
            "priority": self.priority.value,
            "requested_at_s": self.requested_at_s,
            "release_at_s": self.release_at_s,
            "is_player": self.is_player,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PitlaneRequest:
        data["priority"] = PitlanePriority(data["priority"])
        return cls(**data)


class PitlaneQueue:
    """
    Manages pitlane exit queue with priority and cooldown.
    """

    def __init__(self):
        self.queue: List[PitlaneRequest] = []
        self.active_exits: List[PitlaneRequest] = []
        self.next_slot_time: Dict[str, float] = {}  # car_id → earliest next exit
        self._last_release_time: float = -MIN_PIT_EXIT_GAP_S

    def request_exit(
        self,
        car_id: str,
        team_id: str,
        current_time_s: float,
        priority: PitlanePriority = PitlanePriority.AI_STANDARD,
        is_player: bool = False,
    ) -> PitlaneRequest:
        """Queue a car for pitlane exit."""
        # Enforce cooldown
        earliest = current_time_s if is_player else self.next_slot_time.get(car_id, 0.0)
        release_at = max(current_time_s, earliest)

        # Queue delay based on current queue size
        queue_delay = len(self.active_exits) * PITLANE_QUEUE_DELAY_S
        release_at += queue_delay

        req = PitlaneRequest(
            car_id=car_id,
            team_id=team_id,
            priority=priority,
            requested_at_s=current_time_s,
            release_at_s=release_at,
            is_player=is_player,
        )
        self.queue.append(req)
        self.queue.sort(key=lambda r: (r.priority.value, r.release_at_s))
        return req

    def process_tick(self, current_time_s: float) -> List[PitlaneRequest]:
        """
        Release cars whose release_at_s has passed.

        Returns list of cars released this tick.
        Player cars always bypass the slot limit.
        """
        released: List[PitlaneRequest] = []
        remaining: List[PitlaneRequest] = []

        for req in self.queue:
            slots_ok = req.is_player or len(self.active_exits) < MAX_PITLANE_SLOTS
            gap_ok = req.is_player or (current_time_s - self._last_release_time) >= MIN_PIT_EXIT_GAP_S
            can_release = (
                req.release_at_s <= current_time_s
                and slots_ok
                and gap_ok
            )
            if can_release:
                released.append(req)
                self.active_exits.append(req)
                self._last_release_time = current_time_s
            else:
                remaining.append(req)

        self.queue = remaining
        return released

    def car_returned(self, car_id: str, current_time_s: float, *, is_player: bool = False) -> None:
        """Mark a car as returned to the pits. Sets cooldown."""
        self.active_exits = [r for r in self.active_exits if r.car_id != car_id]
        if not is_player:
            self.next_slot_time[car_id] = current_time_s + PITLANE_COOLDOWN_S

    def is_car_queued(self, car_id: str) -> bool:
        return any(r.car_id == car_id for r in self.queue)

    def is_car_on_track(self, car_id: str) -> bool:
        return any(r.car_id == car_id for r in self.active_exits)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "queue": [r.to_dict() for r in self.queue],
            "active_exits": [r.to_dict() for r in self.active_exits],
            "next_slot_time": self.next_slot_time,
            "_last_release_time": self._last_release_time,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PitlaneQueue:
        pq = cls()
        pq.queue = [PitlaneRequest.from_dict(r) for r in data["queue"]]
        pq.active_exits = [PitlaneRequest.from_dict(r) for r in data["active_exits"]]
        pq.next_slot_time = data["next_slot_time"]
        pq._last_release_time = data["_last_release_time"]
        return pq


# ---------------------------------------------------------------------------
# Practice Run Record (spec §4.1)
# ---------------------------------------------------------------------------

@dataclass
class PracticeRunRecord:
    """Log entry for a completed practice run."""
    run_id: int = 0
    car_id: str = ""
    team_id: str = ""
    driver_name: str = ""
    program: RunProgram = RunProgram.SETUP_VALIDATION
    compound: TyreCompound = TyreCompound.C3
    tyre_set_id: str = ""
    fuel_kg: float = 0.0
    laps_planned: int = 0
    laps_completed: int = 0
    start_time_s: float = 0.0
    end_time_s: float = 0.0
    best_lap_s: float = 0.0
    outcome: RunOutcome = RunOutcome.SUCCESS
    abort_reason: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items()}
        d["program"] = self.program.value
        d["compound"] = self.compound.value
        d["outcome"] = self.outcome.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PracticeRunRecord:
        data["program"] = RunProgram(data["program"])
        data["compound"] = TyreCompound(data["compound"])
        data["outcome"] = RunOutcome(data["outcome"])
        return cls(**data)


# ---------------------------------------------------------------------------
# Session Event (spec §6)
# ---------------------------------------------------------------------------

class PracticeEventType(str, Enum):
    RUN_START = "RUN_START"
    RUN_END = "RUN_END"
    RUN_ABORT = "RUN_ABORT"
    FLAG_CHANGE = "FLAG_CHANGE"
    TYRE_INVENTORY_UPDATE = "TYRE_INVENTORY_UPDATE"
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    CAR_EXIT_PIT = "CAR_EXIT_PIT"
    CAR_ENTER_PIT = "CAR_ENTER_PIT"


@dataclass
class PracticeEvent:
    """Event emitted by the orchestrator."""
    event_type: PracticeEventType
    time_s: float = 0.0
    car_id: str = ""
    team_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    priority: NotificationPriority = NotificationPriority.NORMAL


# ---------------------------------------------------------------------------
# Car Session State
# ---------------------------------------------------------------------------

class CarPhase(str, Enum):
    """Where the car is in the session lifecycle."""
    IN_GARAGE = "in_garage"
    PIT_QUEUE = "pit_queue"
    PIT_EXIT = "pit_exit"
    ON_TRACK = "on_track"
    PIT_ENTRY = "pit_entry"
    PIT_WORK = "pit_work"


@dataclass
class CarSessionState:
    """Tracks a car's state within the practice session."""
    car_id: str
    team_id: str
    driver_name: str = ""
    is_player: bool = False
    phase: CarPhase = CarPhase.IN_GARAGE
    current_run_id: int = -1
    current_tyre_set_id: str = ""
    laps_this_run: int = 0
    laps_planned: int = 0
    run_start_time_s: float = 0.0
    pit_work_end_s: float = 0.0       # when pit work finishes
    runs_completed: int = 0
    best_lap_s: float = 0.0
    next_available_s: float = 0.0     # earliest time this car can start a new run
    blue_flag: bool = False            # True when a leader is approaching this car

    def to_dict(self) -> Dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items()}
        d["phase"] = self.phase.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CarSessionState:
        data["phase"] = CarPhase(data["phase"])
        return cls(**data)


# ---------------------------------------------------------------------------
# Practice Session Orchestrator (spec §1-§7)
# ---------------------------------------------------------------------------

class PracticeSessionOrchestrator:
    """
    Coordinates an entire FP1/FP2/FP3 practice session.

    Manages clock, pitlane, tyre inventory, and run scheduling
    for all registered cars (AI + player).

    Usage:
        orch = PracticeSessionOrchestrator(session_type, circuit_config)
        orch.register_team(team_id, car_ids, ...)
        orch.start_session()
        while not orch.is_finished:
            orch.tick()
    """

    def __init__(
        self,
        session_type: SessionType,
        duration_s: int = SESSION_DURATION_S,
    ):
        self.session_type = session_type
        self.clock = SessionClock(duration_s=duration_s)
        self.pitlane = PitlaneQueue()

        self.cars: Dict[str, CarSessionState] = {}
        self.inventories: Dict[str, TyreInventory] = {}  # team_id → inventory
        self.run_log: List[PracticeRunRecord] = []
        self.events: List[PracticeEvent] = []
        self._next_run_id = 0
        self._started = False
        self._flag_clear_at_s: float = 0.0   # auto-clear yellow/red after this time
        self.energy_guidance: Dict[str, Any] = {}
        self.regen_profile: Dict[str, Any] = {}
        self.brake_profile: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_team(
        self,
        team_id: str,
        car_ids: List[str],
        driver_names: Optional[List[str]] = None,
        player_car_ids: Optional[set] = None,
        allocation: Optional[Dict[TyreCompound, int]] = None,
    ) -> None:
        """Register a team with its cars and tyre inventory."""
        _player_ids = player_car_ids or set()
        inv = TyreInventory(team_id, allocation=allocation)
        self.inventories[team_id] = inv

        names = driver_names or [f"Driver_{i}" for i in range(len(car_ids))]
        for i, car_id in enumerate(car_ids):
            self.cars[car_id] = CarSessionState(
                car_id=car_id,
                team_id=team_id,
                driver_name=names[i] if i < len(names) else f"Driver_{i}",
                is_player=(car_id in _player_ids),
            )

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    @property
    def is_finished(self) -> bool:
        return self.clock.is_finished

    def start_session(self) -> None:
        """Start the session clock."""
        self._started = True
        self._emit(PracticeEventType.SESSION_START, message=f"{self.session_type.value} started")

    def tick(self, real_dt_s: float = 1.0) -> List[PracticeEvent]:
        """
        Advance the session by one tick.

        Returns events emitted during this tick.
        """
        if not self._started or self.is_finished:
            return []

        tick_events: List[PracticeEvent] = []
        events_before = len(self.events)

        sim_dt = self.clock.tick(real_dt_s)
        if sim_dt <= 0 and self.clock.flag != SessionFlag.RED:
            return []

        now = self.clock.elapsed_s

        # Auto-clear yellow flag after timer expires
        if (self.clock.flag == SessionFlag.YELLOW
                and self._flag_clear_at_s > 0
                and now >= self._flag_clear_at_s):
            self.set_session_flag(SessionFlag.GREEN)
            self._flag_clear_at_s = 0.0

        # Process pitlane releases (blocked only under RED)
        if self.clock.flag != SessionFlag.RED:
            released = self.pitlane.process_tick(now)
            for req in released:
                css = self.cars.get(req.car_id)
                if not css:
                    continue
                css.phase = CarPhase.ON_TRACK
                css.next_available_s = now + PITLANE_TRAVEL_S
                self._emit(
                    PracticeEventType.CAR_EXIT_PIT,
                    car_id=req.car_id, team_id=css.team_id,
                    message=f"{css.driver_name} exits pit",
                )

        # Check pit work completion
        for css in self.cars.values():
            if css.phase == CarPhase.PIT_WORK and now >= css.pit_work_end_s:
                css.phase = CarPhase.IN_GARAGE
                css.next_available_s = max(css.next_available_s, now)

        # Check session end
        if self.clock.is_finished:
            # Abort all on-track runs
            for css in self.cars.values():
                if css.phase == CarPhase.ON_TRACK:
                    self._abort_run(css, "Session time expired")
            self._emit(PracticeEventType.SESSION_END, message=f"{self.session_type.value} finished")

        # Red flag: force all cars back and clear pit queue
        if self.clock.flag == SessionFlag.RED:
            for css in self.cars.values():
                if css.phase == CarPhase.ON_TRACK:
                    self._abort_run(css, "Red flag")
                elif css.phase == CarPhase.PIT_QUEUE:
                    css.phase = CarPhase.IN_GARAGE
            self.pitlane.queue.clear()

        tick_events = self.events[events_before:]
        return tick_events

    # ------------------------------------------------------------------
    # Run management
    # ------------------------------------------------------------------

    def request_run(
        self,
        car_id: str,
        program: RunProgram,
        compound: TyreCompound,
        fuel_kg: float,
        laps_planned: int,
        prefer_new_tyres: bool = True,
    ) -> Optional[PracticeRunRecord]:
        """
        Request a practice run for a car.

        Validates tyre availability, creates run record, queues for pitlane.
        Returns the run record or None if blocked.
        """
        css = self.cars.get(car_id)
        if css is None:
            return None

        now = self.clock.elapsed_s

        if css.phase not in (CarPhase.IN_GARAGE, CarPhase.PIT_WORK):
            logger.warning("Car %s not in garage (phase=%s)", car_id, css.phase)
            return None

        if not css.is_player and now < css.next_available_s:
            logger.info(
                "Car %s cooldown active (ready at %.1fs)", car_id, css.next_available_s
            )
            return None

        # Check tyre availability
        inv = self.inventories.get(css.team_id)
        if inv is None:
            return None

        tyre_set = inv.checkout(car_id, compound, prefer_new=prefer_new_tyres)
        if tyre_set is None:
            logger.warning("No %s tyres available for %s", compound.value, car_id)
            return None

        # Create run record
        run_id = self._next_run_id
        self._next_run_id += 1

        record = PracticeRunRecord(
            run_id=run_id,
            car_id=car_id,
            team_id=css.team_id,
            driver_name=css.driver_name,
            program=program,
            compound=compound,
            tyre_set_id=tyre_set.set_id,
            fuel_kg=fuel_kg,
            laps_planned=laps_planned,
            start_time_s=self.clock.elapsed_s,
            notes=self._build_run_notes(program),
        )

        # Update car state
        css.current_run_id = run_id
        css.current_tyre_set_id = tyre_set.set_id
        css.laps_planned = laps_planned
        css.laps_this_run = 0
        css.run_start_time_s = now
        css.phase = CarPhase.PIT_QUEUE

        # Queue for pitlane
        priority = PitlanePriority.PLAYER if css.is_player else PitlanePriority.AI_STANDARD
        if program == RunProgram.QUALI_SIM:
            priority = PitlanePriority.AI_CRITICAL

        self.pitlane.request_exit(
            car_id=car_id,
            team_id=css.team_id,
            current_time_s=now,
            priority=priority,
            is_player=css.is_player,
        )

        self._emit(
            PracticeEventType.RUN_START,
            car_id=car_id, team_id=css.team_id,
            data={"program": program.value, "compound": compound.value,
                  "fuel_kg": fuel_kg, "laps": laps_planned},
            message=f"{css.driver_name}: {program.value} on {compound.value}",
        )

        return record

    # ------------------------------------------------------------------
    # Circuit calibration helpers
    # ------------------------------------------------------------------

    def set_circuit_calibration(
        self,
        *,
        energy_guidance: Optional[Dict[str, Any]] = None,
        regen_profile: Optional[Dict[str, Any]] = None,
        brake_profile: Optional[Dict[str, Any]] = None,
    ) -> None:
        if energy_guidance:
            self.energy_guidance = energy_guidance
        if regen_profile:
            self.regen_profile = regen_profile
        if brake_profile:
            self.brake_profile = brake_profile

    def _build_run_notes(self, program: RunProgram) -> str:
        parts: List[str] = []
        if self.energy_guidance:
            deploy = self.energy_guidance.get("deploy_limit_mj")
            harvest = self.energy_guidance.get("harvest_limit_mj")
            warnings = self.energy_guidance.get("warnings", [])
            parts.append(
                f"ERS budget {deploy}MJ/{harvest}MJ"
            )
            if warnings:
                parts.append(f"warnings: {', '.join(warnings[:2])}")
        if self.regen_profile:
            bias = self.regen_profile.get("regen_migration_bias")
            potential = self.regen_profile.get("potential_mj_per_lap")
            parts.append(f"Regen bias {bias:+.2f}, pot {potential} MJ")
        if self.brake_profile:
            parts.append(
                f"Brake base {self.brake_profile.get('regen_brake_base')}, duct {self.brake_profile.get('duct_recommendation')}"
            )
        if not parts:
            return ""
        return f"[{program.value}] " + " | ".join(parts)

    def complete_run(
        self,
        car_id: str,
        laps_completed: int,
        best_lap_s: float,
        km_driven: float = 0.0,
        pit_work_duration_s: float = 0.0,
    ) -> Optional[PracticeRunRecord]:
        """
        Mark a run as completed. Returns the finalized run record.
        """
        css = self.cars.get(car_id)
        if css is None or css.current_run_id < 0:
            return None

        now = self.clock.elapsed_s

        # Return tyres
        inv = self.inventories.get(css.team_id)
        if inv and css.current_tyre_set_id:
            inv.checkin(css.current_tyre_set_id, km_driven=km_driven)

        # Remove from active exits
        self.pitlane.car_returned(car_id, now, is_player=css.is_player)

        # Create record
        outcome = RunOutcome.SUCCESS if laps_completed >= css.laps_planned else RunOutcome.PARTIAL
        record = PracticeRunRecord(
            run_id=css.current_run_id,
            car_id=car_id,
            team_id=css.team_id,
            driver_name=css.driver_name,
            compound=TyreCompound.C3,  # will be set from request
            tyre_set_id=css.current_tyre_set_id,
            laps_planned=css.laps_planned,
            laps_completed=laps_completed,
            start_time_s=css.run_start_time_s,
            end_time_s=now,
            best_lap_s=best_lap_s,
            outcome=outcome,
        )
        self.run_log.append(record)

        # Update best lap
        if best_lap_s > 0 and (css.best_lap_s <= 0 or best_lap_s < css.best_lap_s):
            css.best_lap_s = best_lap_s

        css.runs_completed += 1
        css.laps_this_run = laps_completed

        # Pit work phase + cooldown
        cooldown_end = now + PITLANE_COOLDOWN_S
        if pit_work_duration_s > 0:
            css.phase = CarPhase.PIT_WORK
            css.pit_work_end_s = now + pit_work_duration_s
            css.next_available_s = (
                now if css.is_player else max(cooldown_end, css.pit_work_end_s)
            )
        else:
            css.phase = CarPhase.IN_GARAGE
            css.next_available_s = (
                now if css.is_player else max(cooldown_end, css.next_available_s)
            )

        css.current_run_id = -1
        css.current_tyre_set_id = ""

        self._emit(
            PracticeEventType.RUN_END,
            car_id=car_id, team_id=css.team_id,
            data={"laps": laps_completed, "best_lap_s": round(best_lap_s, 3),
                  "outcome": outcome.value},
            message=f"{css.driver_name}: run complete – {best_lap_s:.1f}s",
        )

        self._emit(
            PracticeEventType.TYRE_INVENTORY_UPDATE,
            team_id=css.team_id,
            data=inv.summary() if inv else {},
        )

        return record

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def session_summary(self) -> Dict[str, Any]:
        """Summary for UI/QA."""
        return {
            "session_type": self.session_type.value,
            "elapsed_s": round(self.clock.elapsed_s, 1),
            "remaining_s": round(self.clock.remaining_s, 1),
            "flag": self.clock.flag.value,
            "total_runs": len(self.run_log),
            "cars_on_track": sum(
                1 for c in self.cars.values() if c.phase == CarPhase.ON_TRACK
            ),
            "cars_in_garage": sum(
                1 for c in self.cars.values() if c.phase == CarPhase.IN_GARAGE
            ),
        }

    def leaderboard(self) -> List[Dict[str, Any]]:
        """Current session leaderboard sorted by best lap."""
        entries = []
        for css in self.cars.values():
            if css.best_lap_s > 0:
                entries.append({
                    "car_id": css.car_id,
                    "driver": css.driver_name,
                    "team": css.team_id,
                    "best_lap_s": css.best_lap_s,
                    "runs": css.runs_completed,
                    "phase": css.phase.value,
                })
        entries.sort(key=lambda e: e["best_lap_s"])
        return entries

    def car_can_run(self, car_id: str) -> bool:
        """Check if a car is eligible to start a new run."""
        css = self.cars.get(car_id)
        if css is None:
            return False
        if css.phase not in (CarPhase.IN_GARAGE,):
            return False
        if self.clock.is_finished:
            return False
        if self.clock.flag == SessionFlag.RED:
            return False
        # Enforce cooldown between runs
        if self.clock.elapsed_s < css.next_available_s:
            return False
        return True

    def set_blue_flag(self, car_id: str, active: bool) -> None:
        """Set or clear blue flag for a specific car."""
        css = self.cars.get(car_id)
        if css is None:
            return
        if css.blue_flag != active:
            css.blue_flag = active
            self._emit(
                PracticeEventType.FLAG_CHANGE,
                car_id=car_id, team_id=css.team_id,
                data={"flag": "blue", "active": active},
                message=f"{css.driver_name}: blue flag {'shown' if active else 'cleared'}",
            )

    def set_session_flag(self, flag: SessionFlag, duration_s: float = 0.0) -> None:
        """
        Change the session-wide flag state.

        GREEN: normal session, pit releases allowed.
        YELLOW: no new pit releases, cars on track continue at reduced pace.
                Auto-clears after duration_s (default: random 60-120s).
        RED: session suspended — clock paused, all cars forced back, pit queue cleared.
        """
        prev = self.clock.flag
        if flag == prev:
            return
        self.clock.set_flag(flag)

        # Set auto-recovery timer for yellow flag
        if flag == SessionFlag.YELLOW:
            if duration_s <= 0:
                duration_s = random.uniform(60.0, 120.0)
            self._flag_clear_at_s = self.clock.elapsed_s + duration_s
        elif flag == SessionFlag.GREEN:
            self._flag_clear_at_s = 0.0

        self._emit(
            PracticeEventType.FLAG_CHANGE,
            data={"flag": flag.value, "previous": prev.value},
            message=f"Flag changed: {prev.value} → {flag.value}",
            priority=NotificationPriority.HIGH,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _abort_run(self, css: CarSessionState, reason: str) -> None:
        """Abort a car's current run."""
        if css.current_tyre_set_id:
            inv = self.inventories.get(css.team_id)
            if inv:
                inv.checkin(css.current_tyre_set_id)

        self.pitlane.car_returned(css.car_id, self.clock.elapsed_s)

        record = PracticeRunRecord(
            run_id=css.current_run_id,
            car_id=css.car_id,
            team_id=css.team_id,
            driver_name=css.driver_name,
            laps_completed=css.laps_this_run,
            start_time_s=css.run_start_time_s,
            end_time_s=self.clock.elapsed_s,
            outcome=RunOutcome.ABORTED,
            abort_reason=reason,
        )
        self.run_log.append(record)

        css.phase = CarPhase.IN_GARAGE
        css.current_run_id = -1
        css.current_tyre_set_id = ""
        css.laps_this_run = 0
        css.next_available_s = (
            self.clock.elapsed_s
            if css.is_player
            else max(css.next_available_s, self.clock.elapsed_s + PITLANE_COOLDOWN_S)
        )

        self._emit(
            PracticeEventType.RUN_ABORT,
            car_id=css.car_id, team_id=css.team_id,
            data={"reason": reason},
            message=f"{css.driver_name}: run aborted – {reason}",
            priority=NotificationPriority.HIGH,
        )

    def _emit(
        self,
        event_type: PracticeEventType,
        car_id: str = "",
        team_id: str = "",
        data: Optional[Dict[str, Any]] = None,
        message: str = "",
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> None:
        self.events.append(PracticeEvent(
            event_type=event_type,
            time_s=self.clock.elapsed_s,
            car_id=car_id,
            team_id=team_id,
            data=data or {},
            message=message,
            priority=priority,
        ))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize orchestrator state for saving."""
        return {
            "session_type": self.session_type.value,
            "clock": self.clock.to_dict(),
            "pitlane": self.pitlane.to_dict(),
            "cars": {k: v.to_dict() for k, v in self.cars.items()},
            "inventories": {k: v.to_dict() for k, v in self.inventories.items()},
            "run_log": [r.to_dict() for r in self.run_log],
            "_next_run_id": self._next_run_id,
            "_started": self._started,
            "_flag_clear_at_s": self._flag_clear_at_s,
            "energy_guidance": self.energy_guidance,
            "regen_profile": self.regen_profile,
            "brake_profile": self.brake_profile,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PracticeSessionOrchestrator:
        """Initialize orchestrator from serialized state."""
        st = SessionType(data["session_type"])
        pso = cls(session_type=st)
        pso.clock = SessionClock.from_dict(data["clock"])
        pso.pitlane = PitlaneQueue.from_dict(data["pitlane"])
        pso.cars = {k: CarSessionState.from_dict(v) for k, v in data["cars"].items()}
        pso.inventories = {k: TyreInventory.from_dict(v) for k, v in data["inventories"].items()}
        pso.run_log = [PracticeRunRecord.from_dict(r) for r in data.get("run_log", [])]
        pso._next_run_id = data.get("_next_run_id", 0)
        pso._started = data.get("_started", False)
        pso._flag_clear_at_s = data.get("_flag_clear_at_s", 0.0)
        pso.energy_guidance = data.get("energy_guidance", {})
        pso.regen_profile = data.get("regen_profile", {})
        pso.brake_profile = data.get("brake_profile", {})
        return pso
