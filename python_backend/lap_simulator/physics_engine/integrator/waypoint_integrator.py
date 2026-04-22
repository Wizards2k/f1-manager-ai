"""
Waypoint Integrator - Facade module for backward compatibility.

All functions have been extracted to focused submodules:
- integrator.state: PhysicsState dataclass
- integrator.waypoint: integrate_waypoint()
- integrator.lap_hd: integrate_lap_hd()
- integrator.race_orchestrator: StintConfig, StintResult, simulate_stint, simulate_race

This module re-exports everything for backward compatibility.
"""

# Re-export PhysicsState
from .state import PhysicsState

# Re-export core functions
from .waypoint import integrate_waypoint
from .lap_hd import integrate_lap_hd

# Re-export race orchestrator (V6.4)
from .race_orchestrator import StintConfig, StintResult, simulate_stint, simulate_race

# Re-export I/O helpers (used by tests/scripts)
from .io import load_hd_waypoints, load_reference_sections, find_section_id_by_distance, load_soft_compound

# Re-export physics helpers (used by tests/scripts)
from .physics import compute_v_max_corners, get_circuit_elevation_m

# Keep __all__ explicit for clarity
__all__ = [
    "PhysicsState",
    "integrate_waypoint",
    "integrate_lap_hd",
    "StintConfig",
    "StintResult",
    "simulate_stint",
    "simulate_race",
    "load_hd_waypoints",
    "load_reference_sections",
    "find_section_id_by_distance",
    "load_soft_compound",
    "compute_v_max_corners",
    "get_circuit_elevation_m",
]
