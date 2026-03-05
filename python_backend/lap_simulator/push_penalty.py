"""
Driver Push Penalty Calculator

Implements realistic driver push penalty system where push=10 is zero reference,
levels 9→1 form monotonic bands with stochastic ranges, and penalties are
modulated by driver skills differently for Qualifying vs Race.

Reference: docs/penalty-overhaul-spec.md
"""
import random
from typing import Dict

from .data_types import CircuitConfig


def compute_push_penalty(
    push_level: int,
    driver_qualifica: int,
    driver_gara: int,
    driver_costanza: int,
    is_qualifying: bool,
    circuit_id: str,
    driver_id: str,
    lap_number: int,
    config: CircuitConfig
) -> float:
    """
    Compute per-lap push penalty in seconds.
    
    Args:
        push_level: 1..10 (10 = zero penalty reference)
        driver_qualifica: 0-100 driver qualification skill
        driver_gara: 0-100 driver race skill
        driver_costanza: 0-100 driver regularity/consistency
        is_qualifying: True for qualifying, False for race
        circuit_id: Circuit identifier for RNG seed
        driver_id: Driver identifier for RNG seed
        lap_number: Lap number for RNG seed
        config: Circuit configuration with penalty parameters
        
    Returns:
        Per-lap penalty in seconds (always >= 0)
    """
    # Validate push level range
    if push_level < 1 or push_level > 10:
        raise ValueError(f"push_level must be 1..10, got {push_level}")
    
    # Push level 10 = zero penalty
    if push_level >= 10:
        return 0.0
    
    # Step 1: Get base center for this push level
    # Centers array is for levels 1..9 (index 0..8)
    center = config.push_penalty_centers[push_level - 1]
    
    # Step 2: Compute band width based on driver regularity
    # Base half-width per level (tighter at higher push levels)
    w_base = config.push_penalty_base_width - (push_level - 1) * config.push_penalty_width_decay
    
    # Modulate by driver regularity (costanza 0-100)
    costanza_factor = 1.0 - (driver_costanza / 100.0) * 0.7  # 0.3 to 1.0
    w_half = w_base * costanza_factor
    
    # Step 3: Compute skill reduction
    # Different skill weights for Quali vs Race
    if is_qualifying:
        skill_weight = 0.7  # Qualifying more dependent on raw speed
        skill_factor = (driver_qualifica / 100.0) * skill_weight
    else:
        skill_weight = 1.0  # Race more dependent on racecraft
        skill_factor = (driver_gara / 100.0) * skill_weight
    
    # Apply skill reduction (better drivers suffer less penalty)
    # BUT: Push level 1 always gets maximum penalty (no skill reduction)
    if push_level == 1:
        skill_reduction = 1.0  # No reduction for maximum push
    else:
        skill_reduction = 1.0 - skill_factor * 0.5  # Max 50% reduction
    
    # Step 4: Generate deterministic random offset within band
    seed = hash(f"{circuit_id}_{driver_id}_{lap_number}")
    rng = random.Random(seed)
    offset = rng.uniform(-w_half, w_half)
    
    # Final per-lap penalty
    penalty_lap = (center + offset) * skill_reduction
    penalty_lap = max(0.0, penalty_lap)  # Never negative
    
    return penalty_lap


def compute_push_penalty_per_section(
    push_level: int,
    driver_qualifica: int,
    driver_gara: int,
    driver_costanza: int,
    is_qualifying: bool,
    circuit_id: str,
    driver_id: str,
    lap_number: int,
    section_length_m: float,
    circuit_length_m: float,
    config: CircuitConfig
) -> float:
    """
    Compute push penalty for a specific section.
    
    Args:
        section_length_m: Length of this section in meters
        circuit_length_m: Total circuit length in meters
        Other args: same as compute_push_penalty()
        
    Returns:
        Section penalty in seconds
    """
    # Get per-lap penalty
    penalty_lap = compute_push_penalty(
        push_level, driver_qualifica, driver_gara, driver_costanza,
        is_qualifying, circuit_id, driver_id, lap_number, config
    )
    
    # Distribute proportionally to section length
    section_fraction = section_length_m / circuit_length_m
    penalty_section = penalty_lap * section_fraction
    
    return penalty_section


# Pre-computed penalty centers for validation
PENALTY_CENTERS = [1.60, 1.45, 1.30, 1.15, 1.00, 0.85, 0.70, 0.55, 0.40]
MIN_GAP_BETWEEN_LEVELS = 0.15  # Minimum gap between adjacent levels
MAX_PENALTY_L1 = 1.60  # Maximum penalty at push=1
