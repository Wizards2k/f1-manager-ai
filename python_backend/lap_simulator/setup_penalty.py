"""
Setup Penalty/Bonus System – calculates per-section DF and drag penalties/bonuses.

Spec: docs/setup-penalty-bonus-malus.md

Flow:
  1. Load ideal setup (circuit baseline + team + driver offsets)
  2. Compare current setup sliders vs ideal
  3. Convert slider deltas to physical deltas
  4. Apply curve penalties (DF) on corner sections
  5. Apply drag penalties/bonuses on straight sections
  6. Cap totals per lap
  7. Return breakdown for telemetry
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default coefficients (fallback when penalty_profile.json has no setup_penalty block)
# ---------------------------------------------------------------------------

DEFAULT_SETUP_PENALTY_CONFIG = {
    "curve_caps": {
        "high_df": 1.5,      # Monaco, Budapest, Singapore
        "balanced": 1.0,     # Most circuits
        "low_drag": 0.6,     # Monza, Jeddah, Baku
    },
    "curve_coeffs": {
        "fast": 0.030,       # Ultrafast/fast corners
        "medium": 0.020,     # Medium corners
        "slow": 0.010,       # Slow corners
    },
    "bonus_coeffs": {
        "fast": -0.007,
        "medium": -0.005,
        "slow": -0.003,
    },
    "drag_coeff": 0.004,
    "drag_bonus_coeff": -0.003,
    "drag_caps": {
        "monza": {"penalty": 0.9, "bonus": -0.08},
        "spa": {"penalty": 0.8, "bonus": -0.06},
        "baku": {"penalty": 0.8, "bonus": -0.06},
        "default": {"penalty": 0.6, "bonus": -0.04},
    },
}


@dataclass
class SetupPenaltyConfig:
    """Circuit-specific setup penalty configuration."""
    curve_caps: Dict[str, float]
    curve_coeffs: Dict[str, float]
    bonus_coeffs: Dict[str, float]
    drag_coeff: float
    drag_bonus_coeff: float
    drag_caps: Dict[str, Dict[str, float]]
    circuit_category: str = "balanced"  # high_df, balanced, low_drag


@dataclass
class SetupPenaltyResult:
    """Per-section penalty/bonus breakdown."""
    df_curve_penalty_s: float = 0.0
    df_curve_bonus_s: float = 0.0
    drag_penalty_s: float = 0.0
    drag_bonus_s: float = 0.0
    setup_penalty_s: float = 0.0  # Total clamped


def load_setup_penalty_config(penalty_profile: Dict[str, Any]) -> SetupPenaltyConfig:
    """
    Load setup penalty config from penalty_profile.json.
    Falls back to defaults if setup_penalty block is missing.
    """
    setup_penalty_block = penalty_profile.get("setup_penalty", {})
    
    if not setup_penalty_block:
        logger.debug("No setup_penalty block in penalty_profile, using defaults")
        cfg = DEFAULT_SETUP_PENALTY_CONFIG
    else:
        cfg = setup_penalty_block
    
    # Determine circuit category from penalty_profile metadata or default to balanced
    circuit_category = penalty_profile.get("setup_penalty_category", "balanced")
    
    return SetupPenaltyConfig(
        curve_caps=cfg.get("curve_caps", DEFAULT_SETUP_PENALTY_CONFIG["curve_caps"]),
        curve_coeffs=cfg.get("curve_coeffs", DEFAULT_SETUP_PENALTY_CONFIG["curve_coeffs"]),
        bonus_coeffs=cfg.get("bonus_coeffs", DEFAULT_SETUP_PENALTY_CONFIG["bonus_coeffs"]),
        drag_coeff=cfg.get("drag_coeff", DEFAULT_SETUP_PENALTY_CONFIG["drag_coeff"]),
        drag_bonus_coeff=cfg.get("drag_bonus_coeff", DEFAULT_SETUP_PENALTY_CONFIG["drag_bonus_coeff"]),
        drag_caps=cfg.get("drag_caps", DEFAULT_SETUP_PENALTY_CONFIG["drag_caps"]),
        circuit_category=circuit_category,
    )


def compute_slider_delta(
    current_slider: int,
    ideal_slider: int,
) -> int:
    """
    Compute slider delta (current - ideal).
    Positive = more downforce/drag than ideal.
    Negative = less downforce/drag than ideal.
    """
    return current_slider - ideal_slider


def compute_curve_penalty(
    df_delta_slider: int,
    curve_speed_category: str,
    section_weight: float,
    config: SetupPenaltyConfig,
) -> Tuple[float, float]:
    """
    Compute DF curve penalty and bonus for a micro-waypoint.
    
    Args:
        df_delta_slider: slider delta (positive = more DF)
        curve_speed_category: "fast", "medium", "slow"
        section_weight: dt_micro / sum(dt_curve_sections)
        config: SetupPenaltyConfig
    
    Returns:
        (penalty_s, bonus_s) – both positive values, bonus is negative penalty
    """
    if df_delta_slider == 0:
        return 0.0, 0.0
    
    coeff = config.curve_coeffs.get(curve_speed_category, config.curve_coeffs["medium"])
    bonus_coeff = config.bonus_coeffs.get(curve_speed_category, config.bonus_coeffs["medium"])
    
    if df_delta_slider > 0:
        # More DF than ideal → penalty
        penalty = coeff * df_delta_slider * section_weight
        return penalty, 0.0
    else:
        # Less DF than ideal → bonus (negative penalty)
        bonus = bonus_coeff * abs(df_delta_slider) * section_weight
        return 0.0, bonus


def compute_drag_penalty(
    drag_delta_slider: int,
    straight_weight: float,
    config: SetupPenaltyConfig,
) -> Tuple[float, float]:
    """
    Compute drag penalty and bonus for a micro-waypoint on straight.
    
    Args:
        drag_delta_slider: slider delta (positive = more drag)
        straight_weight: dist_micro / 500m
        config: SetupPenaltyConfig
    
    Returns:
        (penalty_s, bonus_s)
    """
    if drag_delta_slider == 0:
        return 0.0, 0.0
    
    if drag_delta_slider > 0:
        # More drag than ideal → penalty
        penalty = config.drag_coeff * drag_delta_slider * straight_weight
        return penalty, 0.0
    else:
        # Less drag than ideal → bonus
        bonus = config.drag_bonus_coeff * abs(drag_delta_slider) * straight_weight
        return 0.0, bonus


def clamp_setup_penalties(
    df_curve_penalty: float,
    df_curve_bonus: float,
    drag_penalty: float,
    drag_bonus: float,
    config: SetupPenaltyConfig,
    circuit_id: str,
) -> SetupPenaltyResult:
    """
    Clamp penalties/bonuses per circuit and return aggregated result.
    
    Args:
        df_curve_penalty: accumulated DF curve penalty (s)
        df_curve_bonus: accumulated DF curve bonus (s, negative)
        drag_penalty: accumulated drag penalty (s)
        drag_bonus: accumulated drag bonus (s, negative)
        config: SetupPenaltyConfig
        circuit_id: circuit identifier for drag cap lookup
    
    Returns:
        SetupPenaltyResult with clamped values
    """
    # Clamp DF curve
    cap_curve = config.curve_caps.get(config.circuit_category, config.curve_caps["balanced"])
    df_curve_penalty = min(df_curve_penalty, cap_curve)
    df_curve_bonus = max(df_curve_bonus, -cap_curve * 0.1)  # Bonus cap ~10% of penalty cap
    
    # Clamp drag
    drag_cap_entry = config.drag_caps.get(circuit_id, config.drag_caps.get("default", {}))
    drag_penalty_cap = drag_cap_entry.get("penalty", 0.6)
    drag_bonus_cap = drag_cap_entry.get("bonus", -0.04)
    
    drag_penalty = min(drag_penalty, drag_penalty_cap)
    drag_bonus = max(drag_bonus, drag_bonus_cap)
    
    # Total setup penalty
    total = df_curve_penalty + df_curve_bonus + drag_penalty + drag_bonus
    
    return SetupPenaltyResult(
        df_curve_penalty_s=df_curve_penalty,
        df_curve_bonus_s=df_curve_bonus,
        drag_penalty_s=drag_penalty,
        drag_bonus_s=drag_bonus,
        setup_penalty_s=total,
    )
