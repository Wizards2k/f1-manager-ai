"""
Setup Penalty/Bonus System v2 – Implements spec from docs/setup-penalty-bonus-malus.md

Key differences from v1:
1. Loads ideal setup from setup_ranges/<circuit>.json (not hardcoded 50)
2. Applies team/driver offsets from team_offsets.json
3. Converts slider delta to physical delta using SetupEngineService
4. Applies DF penalty ONLY on curve sections
5. Applies drag penalty/bonus ONLY on straight sections
6. Validates setup is within window before applying bonus
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class IdealSetup:
    """Ideal setup for a circuit, including team/driver offsets."""
    circuit_targets: Dict[str, int]  # From setup_ranges
    team_offsets: Dict[str, int]     # From team_offsets
    driver_offsets: Dict[str, int]   # From team_offsets
    ideal_sliders: Dict[str, int]    # Final ideal (targets + offsets, clamped)
    df_ref: float = 70.0             # Circuit-specific downforce reference
    drag_ref: float = 30.0           # Circuit-specific drag reference


def load_setup_ranges(circuit_id: str) -> Dict[str, Any]:
    """Load setup ranges/targets for a circuit from setup_ranges/<circuit_id>.json"""
    project_root = Path(__file__).resolve().parent.parent.parent
    ranges_file = project_root / "config" / "setup" / "setup_ranges" / f"{circuit_id}.json"
    
    if not ranges_file.exists():
        logger.warning(f"Setup ranges file not found: {ranges_file}, using defaults")
        return {}
    
    with open(ranges_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data.get("ranges", {})


def load_team_offsets() -> Dict[str, Any]:
    """Load team and driver offsets from team_offsets.json"""
    project_root = Path(__file__).resolve().parent.parent.parent
    offsets_file = project_root / "config" / "setup" / "team_offsets.json"
    
    if not offsets_file.exists():
        logger.warning(f"Team offsets file not found: {offsets_file}")
        return {}
    
    with open(offsets_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Remove metadata
    return {k: v for k, v in data.items() if k != "_meta"}


def build_ideal_setup(
    circuit_id: str,
    team_name: Optional[str] = None,
    driver_name: Optional[str] = None,
    df_ref: Optional[float] = None,
    drag_ref: Optional[float] = None,
) -> IdealSetup:
    """
    Build ideal setup for a circuit, optionally with team/driver offsets.
    
    Args:
        circuit_id: Circuit identifier (e.g., "jp-1962_suzuka")
        team_name: Team name (e.g., "McLaren F1 Team")
        driver_name: Driver name (e.g., "Lando Norris")
        df_ref: Circuit-specific downforce reference (fallback to 70.0)
        drag_ref: Circuit-specific drag reference (fallback to 30.0)
    
    Returns:
        IdealSetup with circuit targets, offsets, and final ideal sliders
    """
    # Load circuit targets
    ranges = load_setup_ranges(circuit_id)
    circuit_targets = {
        slider_name: data.get("target", 50)
        for slider_name, data in ranges.items()
    }
    
    # Load team/driver offsets
    team_offsets_data = load_team_offsets()
    team_offsets = {}
    driver_offsets = {}
    
    if team_name and team_name in team_offsets_data:
        team_data = team_offsets_data[team_name]
        team_offsets = team_data.get("team", {})
        
        if driver_name and "drivers" in team_data:
            driver_offsets = team_data["drivers"].get(driver_name, {})
    
    # Build final ideal sliders (targets + offsets, clamped to valid range)
    ideal_sliders = {}
    for slider_name, target in circuit_targets.items():
        # Apply offsets
        ideal = target
        ideal += team_offsets.get(slider_name, 0)
        ideal += driver_offsets.get(slider_name, 0)
        
        # Clamp to valid range
        if slider_name in ranges:
            min_val = ranges[slider_name].get("min", 0)
            max_val = ranges[slider_name].get("max", 100)
            ideal = max(min_val, min(max_val, ideal))
        
        ideal_sliders[slider_name] = ideal
    
    return IdealSetup(
        circuit_targets=circuit_targets,
        team_offsets=team_offsets,
        driver_offsets=driver_offsets,
        ideal_sliders=ideal_sliders,
        df_ref=df_ref or 70.0,
        drag_ref=drag_ref or 30.0,
    )


def compute_slider_delta(
    current_sliders: Dict[str, int],
    ideal_sliders: Dict[str, int],
) -> Dict[str, int]:
    """
    Compute slider deltas (current - ideal) for all sliders.
    
    Args:
        current_sliders: Current setup slider values
        ideal_sliders: Ideal setup slider values
    
    Returns:
        Dictionary of slider deltas
    """
    deltas = {}
    for slider_name in ideal_sliders:
        current = current_sliders.get(slider_name, ideal_sliders[slider_name])
        ideal = ideal_sliders[slider_name]
        deltas[slider_name] = current - ideal
    
    return deltas


def compute_df_delta_from_sliders(
    slider_deltas: Dict[str, int],
) -> Tuple[int, int]:
    """
    Compute DF delta from wing/suspension slider deltas.
    
    Returns:
        (df_front_delta, df_rear_delta)
    """
    # Wings and suspension contribute to DF
    df_front_sliders = ['front_wing', 'ride_height_front', 'suspension_front', 'antiroll_front']
    df_rear_sliders = ['rear_wing', 'ride_height_rear', 'suspension_rear', 'antiroll_rear']
    
    df_front_delta = sum(slider_deltas.get(s, 0) for s in df_front_sliders)
    df_rear_delta = sum(slider_deltas.get(s, 0) for s in df_rear_sliders)
    
    return df_front_delta, df_rear_delta


def compute_drag_delta_from_sliders(
    slider_deltas: Dict[str, int],
) -> int:
    """
    Compute drag delta from wing slider deltas.
    
    Wings are primary drag contributors.
    """
    drag_sliders = ['front_wing', 'rear_wing', 'beam_wing']
    return sum(slider_deltas.get(s, 0) for s in drag_sliders)


def is_setup_within_window(
    current_sliders: Dict[str, int],
    circuit_id: str,
) -> bool:
    """
    Check if setup is within valid window (no validation errors).
    
    Setup WITHIN window = no penalty
    Setup OUTSIDE window = penalty
    """
    ranges = load_setup_ranges(circuit_id)
    
    for slider_name, value in current_sliders.items():
        if slider_name not in ranges:
            continue
        
        min_val = ranges[slider_name].get("min", 0)
        max_val = ranges[slider_name].get("max", 100)
        
        # If ANY slider is outside bounds, setup is invalid
        if value < min_val or value > max_val:
            return False
    
    return True


def compute_setup_window_quality(
    current_sliders: Dict[str, int],
    circuit_id: str,
) -> float:
    ranges = load_setup_ranges(circuit_id)
    if not ranges:
        return 0.0

    weighted_score = 0.0
    total_weight = 0.0

    for slider_name, cfg in ranges.items():
        if slider_name not in current_sliders:
            continue

        value = current_sliders[slider_name]
        min_val = cfg.get("min", 0)
        max_val = cfg.get("max", 100)
        target = cfg.get("target", value)
        tolerance = max(1.0, float(cfg.get("tolerance", 10)))
        weight = max(0.1, float(cfg.get("weight", 1.0)))

        if value < min_val or value > max_val:
            slider_score = 0.0
        else:
            delta = abs(float(value) - float(target))
            slider_score = max(0.0, 1.0 - delta / tolerance)
            window_center = (float(min_val) + float(max_val)) * 0.5
            half_window = max(1.0, (float(max_val) - float(min_val)) * 0.5)
            center_score = max(0.0, 1.0 - abs(float(value) - window_center) / half_window)
            slider_score = slider_score * 0.75 + center_score * 0.25

        weighted_score += slider_score * weight
        total_weight += weight

    if total_weight <= 0.0:
        return 0.0

    return max(0.0, min(1.0, weighted_score / total_weight))


def compute_df_curve_penalty(
    df_delta: int,
    curve_speed_category: str,
    section_weight: float,
    circuit_category: str,
    within_window: bool = False,
) -> Tuple[float, float]:
    """
    Compute DF curve penalty or bonus.
    
    Spec §4-5:
    - If OUTSIDE window: Penalty for ANY deviation (symmetric)
    - If INSIDE window: Bonus only if DF > target (delta_pos)
    
    Args:
        df_delta: DF delta (current - ideal)
        curve_speed_category: fast/medium/slow
        section_weight: normalized section weight
        circuit_category: high_df/balanced/low_drag
        within_window: True if setup is within valid window
    
    Returns:
        (penalty_s, bonus_s) – both positive values
    """
    if df_delta == 0:
        return 0.0, 0.0
    
    # Coefficients from spec
    penalty_coeffs = {
        "fast": 0.030,
        "medium": 0.020,
        "slow": 0.010,
    }
    bonus_coeffs = {
        "fast": -0.007,
        "medium": -0.005,
        "slow": -0.003,
    }
    
    coeff = penalty_coeffs.get(curve_speed_category, penalty_coeffs["medium"])
    bonus_coeff = bonus_coeffs.get(curve_speed_category, bonus_coeffs["medium"])
    
    if within_window:
        # Setup INSIDE window: Bonus only if DF > target (delta_pos)
        # Spec §5: "Triggered when the physical DF exceeds the target (slider delta positive)"
        if df_delta > 0:
            # More DF than ideal = bonus (negative penalty)
            bonus = bonus_coeff * df_delta * section_weight
            return 0.0, bonus
        else:
            # Less DF than ideal = nothing (not penalized, just not ideal)
            return 0.0, 0.0
    else:
        # Setup OUTSIDE window: Penalty for ANY deviation (symmetric)
        penalty = coeff * abs(df_delta) * section_weight
        return penalty, 0.0


def compute_drag_penalty(
    drag_delta: int,
    straight_weight: float,
    within_window: bool = False,
) -> Tuple[float, float]:
    """
    Compute drag penalty or bonus/malus.
    
    Spec §6 + Extension:
    - If OUTSIDE window: Penalty for ANY deviation (symmetric)
    - If INSIDE window: Bonus if drag < target, Malus if drag > target
    
    Args:
        drag_delta: Drag delta (current - ideal)
        straight_weight: normalized straight weight
        within_window: True if setup is within valid window
    
    Returns:
        (penalty_s, bonus_s) – both positive values
    """
    if drag_delta == 0:
        return 0.0, 0.0
    
    # Coefficients from spec
    penalty_coeff = 0.004
    bonus_coeff = -0.004  # Symmetric to penalty
    
    if within_window:
        # Setup INSIDE window: Bonus if drag < target, Malus if drag > target
        if drag_delta < 0:
            # Less drag than ideal = bonus (negative penalty)
            bonus = bonus_coeff * abs(drag_delta) * straight_weight
            return 0.0, bonus
        elif drag_delta > 0:
            # More drag than ideal = malus (positive penalty)
            penalty = penalty_coeff * drag_delta * straight_weight
            return penalty, 0.0
        else:
            # Drag = ideal = nothing
            return 0.0, 0.0
    else:
        # Setup OUTSIDE window: Penalty for ANY deviation (symmetric)
        penalty = penalty_coeff * abs(drag_delta) * straight_weight
        return penalty, 0.0


def clamp_penalties(
    df_penalty: float,
    df_bonus: float,
    drag_penalty: float,
    drag_bonus: float,
    circuit_category: str,
    circuit_id: str,
) -> Tuple[float, float, float, float, float]:
    """
    Clamp penalties/bonuses per circuit caps.
    
    Spec §4-6:
    - DF curve caps: high_df=1.5s, balanced=1.0s, low_drag=0.6s
    - DF bonus caps: high_df=-0.10s, low_drag=-0.05s
    - Drag caps: circuit-specific
    
    Returns:
        (df_penalty_clamped, df_bonus_clamped, drag_penalty_clamped, drag_bonus_clamped, total)
    """
    # DF curve caps
    df_curve_caps = {
        "high_df": 1.5,
        "balanced": 1.0,
        "low_drag": 0.6,
    }
    df_curve_cap = df_curve_caps.get(circuit_category, 1.0)
    df_penalty = min(df_penalty, df_curve_cap)
    
    # DF bonus caps
    df_bonus_caps = {
        "high_df": -0.10,
        "low_drag": -0.05,
    }
    df_bonus_cap = df_bonus_caps.get(circuit_category, -0.04)
    df_bonus = max(df_bonus, df_bonus_cap)
    
    # Drag caps (circuit-specific)
    drag_caps = {
        "monza": {"penalty": 0.9, "bonus": -0.08},
        "spa": {"penalty": 0.8, "bonus": -0.06},
        "baku": {"penalty": 0.8, "bonus": -0.06},
    }
    drag_cap_entry = drag_caps.get(circuit_id, {"penalty": 0.6, "bonus": -0.04})
    drag_penalty = min(drag_penalty, drag_cap_entry["penalty"])
    drag_bonus = max(drag_bonus, drag_cap_entry["bonus"])
    
    # Total
    total = df_penalty + df_bonus + drag_penalty + drag_bonus
    
    return df_penalty, df_bonus, drag_penalty, drag_bonus, total
