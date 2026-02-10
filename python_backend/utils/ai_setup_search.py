"""
AI Setup Search Engine — §2 of ai-Setup-Search.md

Implements the full loop:
  1. Generate baseline setup_config from team simulator_quality (§2.1)
  2. After each run, adjust real sliders based on feedback + pilot skill (§2.6)
  3. Recalculate setup score via evaluate_setup_categories (§2.3)
  4. Check convergence threshold based on perfezionismo (§2.4)
"""
from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from models import DEFAULT_SETUP_CONFIG
from utils.setup_engine import (
    evaluate_setup,
    evaluate_setup_categories,
    _resolve_field_params,
    BASE_FIELD_PARAMS,
)


# ---------------------------------------------------------------------------
# §2.6 — Pilot quality categories
# ---------------------------------------------------------------------------

_PILOT_CATEGORIES = [
    # (min_skill, label, precision_mult, variance_sigma, error_prob)
    (85, "elite",        1.05, 0.10, 0.05),
    (70, "solido",       1.00, 0.20, 0.10),
    (55, "incostante",   0.90, 0.40, 0.18),
    (0,  "sperimentale", 0.80, 0.60, 0.25),
]


def _get_pilot_category(ricerca_assetto: int) -> Tuple[str, float, float, float]:
    """Return (label, precision_mult, variance_sigma, error_prob)."""
    for min_skill, label, prec, sigma, err in _PILOT_CATEGORIES:
        if ricerca_assetto >= min_skill:
            return label, prec, sigma, err
    last = _PILOT_CATEGORIES[-1]
    return last[1], last[2], last[3], last[4]


# ---------------------------------------------------------------------------
# §2.6 — Feedback indicator → slider mapping
# ---------------------------------------------------------------------------

# Three macro indicators and which sliders they affect
_INDICATOR_SLIDER_MAP: Dict[str, List[str]] = {
    "cornering_balance": [
        "front_wing", "rear_wing", "beam_wing",
        "suspension_front", "suspension_rear",
    ],
    "straight_line_efficiency": [
        "front_wing", "rear_wing", "beam_wing",
        "ride_height_front", "ride_height_rear",
    ],
    "traction_stability": [
        "suspension_rear", "antiroll_rear",
        "ride_height_rear", "antiroll_front",
    ],
}

# Base step per component type (§2.6 point 3)
_BASE_STEP: Dict[str, float] = {
    "front_wing": 2.0,
    "rear_wing": 2.0,
    "beam_wing": 1.5,
    "ride_height_front": 1.5,
    "ride_height_rear": 1.5,
    "suspension_front": 1.0,
    "suspension_rear": 1.0,
    "antiroll_front": 1.0,
    "antiroll_rear": 1.0,
    "brake_balance": 1.0,
    "brake_duct": 1.0,
}


# ---------------------------------------------------------------------------
# §2.1 — Baseline generation
# ---------------------------------------------------------------------------

def generate_baseline_setup(
    simulator_quality: int,
    rng: Optional[random.Random] = None,
) -> Dict[str, int]:
    """
    Generate an initial setup_config based on team simulator quality.

    Higher simulator_quality → sliders closer to circuit optimal.
    Lower → more random deviation from optimal.

    Returns a dict with the same keys as DEFAULT_SETUP_CONFIG.
    """
    if rng is None:
        rng = random.Random()

    setup: Dict[str, int] = {}
    # Calibrated quadratic: sim_q → noise_mult (gaussian σ = tolerance * noise_mult)
    # Produces avg baseline scores: top(88)≈7.0, mid(72)≈6.0, back(60)≈5.0
    sq = float(simulator_quality)
    noise_mult = 0.001920 * sq * sq - 0.343393 * sq + 16.462857
    noise_mult = max(0.3, noise_mult)  # safety floor

    for field_name in DEFAULT_SETUP_CONFIG:
        params = _resolve_field_params(field_name)
        optimal = params["optimal"]
        tolerance = params["tolerance"]
        field_range = params.get("range", (0, 100))

        deviation = rng.gauss(0, tolerance * noise_mult)
        value = int(round(optimal + deviation))
        value = max(field_range[0], min(field_range[1], value))
        setup[field_name] = value

    return setup


def compute_setup_score(setup_values: Dict[str, int]) -> float:
    """
    Compute the overall setup score on a 0–10 scale.

    Uses evaluate_setup() which returns a penalty-based raw score:
      0.0 = all sliders at optimal, negative = worse.
    Practical range: 0.0 (perfect) to about -2.5 (very bad).
    Mapping: score_10 = 10 + raw * 3.5, clamped [0, 10].
    """
    result = evaluate_setup(setup_values)
    raw = result.get("score", -1.0)
    score_10 = 10.0 + raw * 3.5
    return round(max(0.0, min(10.0, score_10)), 2)


def compute_convergence_threshold(perfezionismo: int) -> float:
    """
    §2.4 — Convergence threshold per driver.

    base_threshold = 8.1, offset by perfezionismo.
    Perfezionismo 60 → 8.10  (pragmatic, accepts "good enough")
    Perfezionismo 75 → 8.15
    Perfezionismo 85 → 8.19
    Perfezionismo 95 → 8.23  (perfectionist, wants near-optimal)
    """
    return 8.1 + (perfezionismo - 60) / 280.0


# ---------------------------------------------------------------------------
# §2.6 — Feedback analysis (from current setup vs optimal)
# ---------------------------------------------------------------------------

def _compute_feedback_indicators(
    setup_values: Dict[str, int],
) -> Dict[str, float]:
    """
    Compute three macro feedback indicators with sign and intensity.

    Each indicator is in range [-1, +1]:
      - cornering_balance: negative = understeer, positive = oversteer
      - straight_line_efficiency: negative = too much drag, positive = good
      - traction_stability: negative = poor traction, positive = good

    Intensity reflects how far from optimal the related sliders are.
    """
    indicators: Dict[str, float] = {}

    # Cornering balance: front_wing vs rear_wing balance relative to optimal
    fw_params = _resolve_field_params("front_wing")
    rw_params = _resolve_field_params("rear_wing")
    fw_delta = (setup_values.get("front_wing", 50) - fw_params["optimal"]) / max(1, fw_params["tolerance"])
    rw_delta = (setup_values.get("rear_wing", 50) - rw_params["optimal"]) / max(1, rw_params["tolerance"])
    # Positive cornering = too much front relative to rear (understeer tendency)
    cornering = (fw_delta - rw_delta) * 0.5
    indicators["cornering_balance"] = max(-1.0, min(1.0, cornering))

    # Straight-line efficiency: high rear wing + high ride height = drag
    bw_params = _resolve_field_params("beam_wing")
    rhf_params = _resolve_field_params("ride_height_front")
    rhr_params = _resolve_field_params("ride_height_rear")
    drag_penalty = (
        (setup_values.get("rear_wing", 50) - rw_params["optimal"]) / max(1, rw_params["tolerance"]) * 0.4
        + (setup_values.get("beam_wing", 50) - bw_params["optimal"]) / max(1, bw_params["tolerance"]) * 0.3
        + (setup_values.get("ride_height_front", 50) - rhf_params["optimal"]) / max(1, rhf_params["tolerance"]) * 0.15
        + (setup_values.get("ride_height_rear", 50) - rhr_params["optimal"]) / max(1, rhr_params["tolerance"]) * 0.15
    )
    indicators["straight_line_efficiency"] = max(-1.0, min(1.0, -drag_penalty))

    # Traction stability: suspension_rear, antiroll_rear, ride_height_rear
    sr_params = _resolve_field_params("suspension_rear")
    ar_params = _resolve_field_params("antiroll_rear")
    traction = (
        -(setup_values.get("suspension_rear", 50) - sr_params["optimal"]) / max(1, sr_params["tolerance"]) * 0.4
        - (setup_values.get("antiroll_rear", 50) - ar_params["optimal"]) / max(1, ar_params["tolerance"]) * 0.3
        - (setup_values.get("ride_height_rear", 50) - rhr_params["optimal"]) / max(1, rhr_params["tolerance"]) * 0.3
    )
    indicators["traction_stability"] = max(-1.0, min(1.0, traction))

    return indicators


# ---------------------------------------------------------------------------
# §2.6 — Slider adjustment algorithm
# ---------------------------------------------------------------------------

def adjust_setup_after_run(
    setup_values: Dict[str, int],
    ricerca_assetto: int,
    rng: Optional[random.Random] = None,
) -> Tuple[Dict[str, int], Dict[str, float]]:
    """
    AI pilot adjusts real setup sliders after a run.

    Direct per-slider approach: each slider moves toward its optimal value.
    The fraction of the gap closed per run depends on pilot skill category
    (precision, variance, error probability).

    Returns (new_setup, changes_dict).
    """
    if rng is None:
        rng = random.Random()

    cat_label, precision_mult, sigma, error_prob = _get_pilot_category(ricerca_assetto)
    # Base correction fraction: how much of the gap to optimal is closed per run
    # Elite closes ~26%, Sperimentale ~20%
    base_fraction = 0.25 * precision_mult

    new_setup = dict(setup_values)
    changes: Dict[str, float] = {}

    for slider in DEFAULT_SETUP_CONFIG:
        params = _resolve_field_params(slider)
        optimal = params["optimal"]
        current = setup_values.get(slider, 50)
        field_range = params.get("range", (0, 100))

        gap = optimal - current
        if abs(gap) < 1:
            continue  # Already at optimal

        # Correction = fraction of gap + gaussian noise
        correction = gap * base_fraction
        noise = rng.gauss(0, sigma * abs(gap) * 0.15)
        correction += noise

        # Random error: with error_prob, flip direction or overshoot
        if rng.random() < error_prob:
            if rng.random() < 0.5:
                correction = -correction  # Wrong direction
            else:
                correction *= rng.uniform(1.8, 3.0)  # Overshoot

        new_val = int(round(current + correction))
        new_val = max(field_range[0], min(field_range[1], new_val))
        new_setup[slider] = new_val
        if new_val != current:
            changes[slider] = float(new_val - current)

    return new_setup, changes


# ---------------------------------------------------------------------------
# §2.3 — Full run cycle: adjust → recalc score → check threshold
# ---------------------------------------------------------------------------

@dataclass
class SetupRunResult:
    """Result of one AI setup search iteration."""
    run_index: int
    session: str
    program: str
    score_before: float
    score_after: float
    threshold: float
    setup_complete: bool
    slider_changes: Dict[str, float] = field(default_factory=dict)
    setup_snapshot: Dict[str, int] = field(default_factory=dict)


@dataclass
class AISetupState:
    """Persistent state for one AI car's setup search across FP1–FP3."""
    car_id: str
    driver_name: str
    team_name: str
    simulator_quality: int
    ricerca_assetto: int
    perfezionismo: int
    setup_config: Dict[str, int] = field(default_factory=dict)
    setup_score: float = 0.0
    threshold: float = 7.5
    setup_complete: bool = False
    run_history: List[SetupRunResult] = field(default_factory=list)
    total_runs: int = 0
    completion_run: Optional[int] = None
    completion_session: Optional[str] = None
    _rng: Optional[random.Random] = field(default=None, repr=False)

    def initialize(self, seed: Optional[int] = None):
        """Generate baseline setup and compute initial score."""
        self._rng = random.Random(seed)
        self.setup_config = generate_baseline_setup(self.simulator_quality, self._rng)
        self.setup_score = compute_setup_score(self.setup_config)
        self.threshold = compute_convergence_threshold(self.perfezionismo)
        self.setup_complete = self.setup_score >= self.threshold

    def process_run(self, session: str, program: str) -> SetupRunResult:
        """
        Execute one setup search iteration:
        1. Record score before
        2. Adjust sliders based on feedback + pilot skill
        3. Recalculate score
        4. Check threshold
        """
        self.total_runs += 1
        score_before = self.setup_score
        changes: Dict[str, float] = {}

        # Only adjust sliders if setup is not yet complete
        if not self.setup_complete:
            new_setup, changes = adjust_setup_after_run(
                self.setup_config,
                self.ricerca_assetto,
                self._rng,
            )
            self.setup_config = new_setup
            self.setup_score = compute_setup_score(self.setup_config)

        # Check convergence
        if not self.setup_complete and self.setup_score >= self.threshold:
            self.setup_complete = True
            self.completion_run = self.total_runs
            self.completion_session = session

        result = SetupRunResult(
            run_index=self.total_runs,
            session=session,
            program=program,
            score_before=score_before,
            score_after=self.setup_score,
            threshold=self.threshold,
            setup_complete=self.setup_complete,
            slider_changes=changes,
            setup_snapshot=dict(self.setup_config),
        )
        self.run_history.append(result)
        return result
