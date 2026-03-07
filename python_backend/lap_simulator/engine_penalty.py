"""
Engine Penalty System – Step 6 integration for update_section().

Computes ICE+ERS power-based penalties/bonuses based on:
- Engine CV delta vs Mercedes reference (1008 CV)
- Engine map penalties (QUALY = 0 reference)
- Circuit-specific coefficients
- Applied only on straight sections

Reference: 20 CV = -0.2s bonus on medium-speed circuits
"""
from __future__ import annotations

from .data_types import (
    CircuitConfig,
    EngineMapName,
    SectionContext,
    SectionKind,
    clamp,
)

# Import engine map penalty flag
try:
    from utils.game_logic import ENABLE_ENGINE_MAP_PENALTIES
except ImportError:
    ENABLE_ENGINE_MAP_PENALTIES = True


# Section kinds where engine penalties apply (straights only)
STRAIGHT_KINDS = {
    SectionKind.STRAIGHT,
    SectionKind.MEDIUM_STRAIGHT,
    SectionKind.ULTRA_FAST_CORNER,  # High-speed corners benefit from power
}

# Default engine map penalties (QUALY = 0 reference)
DEFAULT_ENGINE_MAP_PENALTIES = {
    EngineMapName.QUALY: 0.0,      # Reference zero penalty
    EngineMapName.RICH: 0.12,      # +0.12s/lap
    EngineMapName.STANDARD: 0.25,  # +0.25s/lap
    EngineMapName.ECONOMY: 0.40,   # +0.40s/lap
    EngineMapName.WET: 0.18,       # +0.18s/lap
    EngineMapName.RECHARGE: 0.50   # +0.50s/lap
}


def compute_engine_penalty(
    team_cv: float,
    engine_map: EngineMapName,
    section: SectionContext,
    config: CircuitConfig,
) -> float:
    """
    Compute engine penalty/bonus for the current section.
    
    Args:
        team_cv: Team engine CV (from power_units.py)
        engine_map: Current engine map
        section: Current circuit section
        config: Circuit configuration
        
    Returns:
        Engine penalty in seconds (negative = bonus)
    """
    # Apply only on straight sections
    if section.kind not in STRAIGHT_KINDS:
        return 0.0
    
    # CV delta vs Mercedes reference
    cv_delta = team_cv - config.engine_reference_cv
    
    # Base engine penalty from CV delta (20 CV = -0.2s)
    cv_penalty = cv_delta * config.engine_penalty_coeff
    
    # Map penalty (QUALY = 0 reference)
    map_penalty = 0.0
    if ENABLE_ENGINE_MAP_PENALTIES:
        map_penalties = config.engine_map_penalties or DEFAULT_ENGINE_MAP_PENALTIES
        map_penalty = map_penalties.get(engine_map, 0.0)
    
    # Total engine penalty
    total_penalty = cv_penalty + map_penalty
    
    # No clamping for now - let penalties flow through
    return total_penalty


def get_engine_cv_for_team(team_code: str) -> float:
    """
    Get engine CV for a team from power_units.py data.
    
    Args:
        team_code: FIA team code (e.g., "RBR", "MER")
        
    Returns:
        Engine CV rating
    """
    # Hard-coded CV values based on power_units.py data to avoid import issues
    TEAM_ENGINE_CV = {
        "RBR": 1015.0,   # Honda RBPT HRC
        "RB": 995.0,     # Honda RBPT HRC  
        "MCL": 1008.0,   # Mercedes-AMG HPP
        "MER": 1018.0,   # Mercedes-AMG HPP
        "AST": 995.0,    # Mercedes-AMG HPP
        "WIL": 987.0,    # Mercedes-AMG HPP
        "FER": 1007.0,   # Ferrari 066/11
        "SAU": 987.0,    # Ferrari 066/11
        "HAAS": 982.0,   # Ferrari 066/11
        "ALP": 960.0,    # Renault E-Tech RE25
    }
    
    return TEAM_ENGINE_CV.get(team_code.upper(), 1008.0)  # Fallback to Mercedes reference


def validate_engine_coefficient(
    circuit_coeff: float,
    expected_cv_delta: float = 20.0,
    expected_penalty_s: float = 0.2
) -> bool:
    """
    Validate that circuit coefficient produces expected penalty.
    
    Args:
        circuit_coeff: Circuit engine penalty coefficient
        expected_cv_delta: CV delta to test (default 20 CV)
        expected_penalty_s: Expected penalty (default 0.2s)
        
    Returns:
        True if coefficient is correct
    """
    actual_penalty = expected_cv_delta * circuit_coeff
    tolerance = 0.01  # 10ms tolerance
    
    return abs(actual_penalty - expected_penalty_s) <= tolerance
