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
    # sim_quality 90 → noise_factor 0.35, 72 → 0.72, 60 → 0.96
    # Quadratic scaling so top teams are noticeably closer to optimal
    linear = 1.0 - (simulator_quality / 100.0)
    noise_factor = linear * 2.4  # amplify: 0.10→0.24 ... 0.40→0.96

    for field_name in DEFAULT_SETUP_CONFIG:
        params = _resolve_field_params(field_name)
        optimal = params["optimal"]
        tolerance = params["tolerance"]
        field_range = params.get("range", (0, 100))

        # Max deviation: top teams deviate ~0.5*tolerance, back ~2*tolerance
        max_dev = tolerance * (0.5 + noise_factor * 1.8)
        deviation = rng.gauss(0, max_dev * 0.6)
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

    base_threshold = 8.5, offset by perfezionismo.
    Perfezionismo 60 → 8.50  (pragmatic, accepts "good enough")
    Perfezionismo 75 → 8.63
    Perfezionismo 85 → 8.71
    Perfezionismo 95 → 8.88  (perfectionist, wants near-optimal)
    """
    return 8.5 + (perfezionismo - 60) / 280.0


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

    1. Compute feedback indicators from current setup vs optimal
    2. For each indicator, adjust mapped sliders using pilot skill
    3. Apply precision multiplier, gaussian variance, and random errors
    4. Return (new_setup, changes_dict)
    """
    if rng is None:
        rng = random.Random()

    cat_label, precision_mult, sigma, error_prob = _get_pilot_category(ricerca_assetto)
    skill_mult = 0.6 + (ricerca_assetto / 100.0) * 0.8

    indicators = _compute_feedback_indicators(setup_values)
    new_setup = dict(setup_values)
    changes: Dict[str, float] = {}

    # Track which sliders have been adjusted to avoid double-counting
    adjusted: Dict[str, float] = {}

    for indicator_name, intensity in indicators.items():
        if abs(intensity) < 0.05:
            continue  # No meaningful feedback

        slider_names = _INDICATOR_SLIDER_MAP.get(indicator_name, [])
        for slider in slider_names:
            if slider not in DEFAULT_SETUP_CONFIG:
                continue

            params = _resolve_field_params(slider)
            optimal = params["optimal"]
            current = new_setup.get(slider, 50)
            field_range = params.get("range", (0, 100))

            # Direction: move toward optimal
            raw_delta = optimal - current
            if abs(raw_delta) < 1:
                continue  # Already close enough

            base_step = _BASE_STEP.get(slider, 1.0)

            # Delta = base_step * |intensity| * skill_mult * precision
            delta_mag = base_step * abs(intensity) * skill_mult * precision_mult

            # Add gaussian noise (variance)
            noise = rng.gauss(0, sigma) * base_step * 0.5
            delta_mag += noise

            # Direction: sign of raw_delta (toward optimal)
            direction = 1.0 if raw_delta > 0 else -1.0

            # Random error: with error_prob, flip direction or pick wrong slider
            if rng.random() < error_prob:
                if rng.random() < 0.5:
                    direction *= -1  # Wrong direction
                else:
                    delta_mag *= rng.uniform(1.5, 2.5)  # Overshoot

            delta = direction * max(0.5, abs(delta_mag))

            # Accumulate (don't overshoot past optimal)
            prev_accumulated = adjusted.get(slider, 0.0)
            total_delta = prev_accumulated + delta
            # Clamp so we don't overshoot optimal by too much
            new_val = current + total_delta
            new_val = max(field_range[0], min(field_range[1], new_val))
            adjusted[slider] = new_val - current

    # Apply accumulated changes
    for slider, total_delta in adjusted.items():
        old_val = setup_values.get(slider, 50)
        new_val = int(round(old_val + total_delta))
        params = _resolve_field_params(slider)
        field_range = params.get("range", (0, 100))
        new_val = max(field_range[0], min(field_range[1], new_val))
        new_setup[slider] = new_val
        if new_val != old_val:
            changes[slider] = round(new_val - old_val, 1)

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

        # Adjust sliders
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
