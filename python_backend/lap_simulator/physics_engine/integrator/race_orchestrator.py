"""
Race Orchestrator - V6.4 Multi-lap stint simulation with full state carryover.

Manages the complete lifecycle of a stint (set of consecutive laps):
- Fuel consumption carryover (mass decreases each lap)
- Tire thermal state carryover (temps + wear)
- Brake thermal state carryover
- PU state carryover (battery SOC, ERS deployment)
- DRS activation logic (gap-based, zone-based)
- Pit stop simulation (tire change, fuel top-up, time penalty)

Usage:
    from lap_simulator.physics_engine.integrator.race_orchestrator import (
        StintConfig, simulate_stint
    )

    config = StintConfig(
        circuit_id="it-1922_monza",
        compound="C3",
        fuel_start_kg=110.0,
        stint_laps=20,
        engine_map="RACE",
    )
    result = simulate_stint(config)
    for lap in result.lap_results:
        print(f"Lap {lap['lap_num']}: {lap['lap_time_s']:.3f}s "
              f"fuel={lap['fuel_remaining_kg']:.1f}kg "
              f"wear_FL={lap['tire_wear']['FL']:.1f}%")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from lap_simulator.physics_engine.integrator.lap_hd import integrate_lap_hd
from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StintConfig:
    """Configuration for a single stint (set of consecutive laps)."""

    # Circuit & compound
    circuit_id: str = "it-1922_monza"
    compound: str = "C3"

    # Fuel
    fuel_start_kg: float = 110.0  # Starting fuel load [kg]

    # Stint length
    stint_laps: int = 20

    # Power Unit
    engine_map: str = "RACE"  # QUALIFY, RACE, PRACTICE, SAFETY_CAR
    push_level: int = 8  # 1-10 (1=extreme save, 10=quali push)

    # Aero
    aero_setup: Optional[Dict[str, float]] = None
    aero_calibration: Optional[Dict[str, Any]] = None

    # Driver
    driver_skill: float = 1.0

    # Suspension
    suspension_setup: Optional[Dict[str, float]] = None

    # DRS
    drs_enabled: bool = True
    # Gap to car ahead in seconds. None = no gap info (qualifying: DRS always in zones)
    # In race mode, DRS activates only when gap < 1.0s
    drs_gap_ahead_s: Optional[float] = None

    # Pit stop
    pit_lap: Optional[int] = None  # Lap number to pit (None = no pit)
    pit_time_s: float = 23.0  # Pit stop time penalty [s] (typical F1: 20-25s)
    pit_fuel_add_kg: float = 0.0  # Fuel added at pit stop [kg]
    pit_new_compound: Optional[str] = None  # New compound at pit stop (None = same)

    # Safety car
    is_safety_car: bool = False  # Safety car active (disables DRS)

    # ERS
    ers_power_fraction: float = 0.5

    # Initial conditions (for multi-stint continuation)
    initial_tire_temps: Optional[Dict[str, float]] = None
    cumulative_tire_wear: Optional[Dict[str, float]] = None


@dataclass
class StintResult:
    """Results from a complete stint simulation."""

    lap_results: List[Dict[str, Any]] = field(default_factory=list)
    total_time_s: float = 0.0
    final_fuel_kg: float = 0.0
    final_tire_temps: Optional[Dict[str, float]] = None
    final_tire_wear: Optional[Dict[str, float]] = None
    pit_stop_lap: Optional[int] = None
    pit_stop_time_s: float = 0.0
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DRY_MASS_KG = 798.0  # F1 2025 minimum dry weight (no driver, no fuel)
MIN_FUEL_KG = 5.0     # Minimum fuel before engine cuts out


# ─────────────────────────────────────────────────────────────────────────────
# Main simulation
# ─────────────────────────────────────────────────────────────────────────────

def simulate_stint(config: StintConfig) -> StintResult:
    """
    Run a multi-lap stint with full state carryover.

    This is the primary entry point for race simulation. It manages:
    - Fuel consumption and mass reduction per lap
    - Tire thermal state carryover (temps + wear)
    - DRS activation based on gap and zone
    - Pit stop simulation with tire reset and time penalty
    - Safety car DRS disable

    Args:
        config: StintConfig with all stint parameters

    Returns:
        StintResult with lap-by-lap results and final state
    """
    result = StintResult()

    # Aero calibration
    aero_calibration = config.aero_calibration
    if aero_calibration is None:
        aero_calibration = get_aero_calibration(config.circuit_id)

    # Aero setup defaults
    aero_setup = config.aero_setup
    if aero_setup is None:
        aero_setup = {"front_wing": 20.0, "rear_wing": 22.0, "b_wing": 10.0}

    # PU config
    pu_config = {"engine_map": config.engine_map}

    # State carryover variables
    current_fuel_kg = config.fuel_start_kg
    current_tire_temps = config.initial_tire_temps  # None = cold tires (default 85°C)
    cumulative_wear = config.cumulative_tire_wear  # None = fresh tires (0%)
    current_compound = config.compound
    did_pit = False

    for lap_num in range(1, config.stint_laps + 1):
        # ── Pit stop logic ──────────────────────────────────────────────
        if config.pit_lap is not None and lap_num == config.pit_lap:
            # Reset tires to fresh
            current_tire_temps = None  # Fresh tires = default temps
            cumulative_wear = None  # Fresh tires = 0% wear
            # Change compound if specified
            if config.pit_new_compound:
                current_compound = config.pit_new_compound
            # Add fuel
            current_fuel_kg += config.pit_fuel_add_kg
            did_pit = True

        # ── Fuel check ─────────────────────────────────────────────────
        if current_fuel_kg < MIN_FUEL_KG:
            result.error = f"Fuel depleted at lap {lap_num}: {current_fuel_kg:.1f}kg remaining"
            break

        # ── DRS gap simulation ─────────────────────────────────────────
        # In a real race, the gap varies per lap. For now, use the config
        # value. Future: integrate with race position tracker.
        drs_gap = config.drs_gap_ahead_s

        # ── Lap simulation ─────────────────────────────────────────────
        try:
            lap_result = integrate_lap_hd(
                circuit_id=config.circuit_id,
                aero_setup=aero_setup,
                mass_kg=DRY_MASS_KG + current_fuel_kg,
                tyre_compound=current_compound,
                driver_skill=config.driver_skill,
                push_level=config.push_level,
                aero_calibration=aero_calibration,
                suspension_setup=config.suspension_setup,
                ers_power_fraction=config.ers_power_fraction,
                pu_config=pu_config,
                # V6.4: Multi-lap carryover
                initial_tire_temps=current_tire_temps,
                cumulative_tire_wear=cumulative_wear,
                initial_fuel_kg=current_fuel_kg,
                # V6.4: DRS activation
                drs_enabled=config.drs_enabled,
                drs_gap_ahead_s=drs_gap,
                lap_number=lap_num,
                is_safety_car=config.is_safety_car,
            )
        except Exception as e:
            result.error = f"Lap {lap_num}: {type(e).__name__}: {str(e)[:200]}"
            break

        # ── Extract carryover state ────────────────────────────────────
        lap_time = lap_result.get("lap_time_s", 0)

        # Add pit stop time penalty on the pit lap
        if config.pit_lap is not None and lap_num == config.pit_lap:
            lap_time += config.pit_time_s
            result.pit_stop_lap = lap_num
            result.pit_stop_time_s = config.pit_time_s

        # Fuel carryover
        fuel_remaining = lap_result.get("fuel_remaining_kg")
        if fuel_remaining is not None:
            current_fuel_kg = fuel_remaining
        else:
            # Fallback: estimate from consumed (shouldn't happen with V6.4)
            consumed = lap_result.get("fuel_consumed_kg", 0)
            current_fuel_kg -= consumed

        # Tire carryover
        current_tire_temps = lap_result.get("final_tire_temps")
        cumulative_wear = lap_result.get("cumulative_tire_wear")

        # ── Build lap result ────────────────────────────────────────────
        lap_entry = {
            "lap_num": lap_num,
            "lap_time_s": lap_time,
            "fuel_remaining_kg": current_fuel_kg,
            "fuel_consumed_kg": lap_result.get("fuel_consumed_kg", 0),
            "tire_temps": current_tire_temps,
            "tire_wear": cumulative_wear,
            "v_max_kph": lap_result.get("v_max_kph", 0),
            "v_avg_kph": lap_result.get("v_avg_kph", 0),
            "sector_times": lap_result.get("sector_times", []),
            "compound": current_compound,
            "is_pit_lap": config.pit_lap is not None and lap_num == config.pit_lap,
        }

        # PU state
        if "pu_v54" in lap_result:
            lap_entry["pu_v54"] = lap_result["pu_v54"]

        result.lap_results.append(lap_entry)
        result.total_time_s += lap_time

    # ── Final state ─────────────────────────────────────────────────────
    result.final_fuel_kg = current_fuel_kg
    result.final_tire_temps = current_tire_temps
    result.final_tire_wear = cumulative_wear

    return result


def simulate_race(
    circuit_id: str,
    total_laps: int,
    stints: List[StintConfig],
) -> Dict[str, Any]:
    """
    Simulate a complete race with multiple stints.

    Each stint represents a tire life segment (between pit stops).
    Stints are run sequentially, with state carryover between them.

    Args:
        circuit_id: Circuit identifier
        total_laps: Total race laps
        stints: List of StintConfig, one per stint segment

    Returns:
        Dict with:
            - total_time_s: Total race time
            - lap_results: List of all lap results
            - stint_results: List of StintResult objects
            - total_pit_stops: Number of pit stops
    """
    all_laps = []
    stint_results = []
    total_time = 0.0
    total_pit_stops = 0

    # Carryover state between stints
    carryover_fuel = None
    carryover_temps = None
    carryover_wear = None

    for stint_idx, stint_config in enumerate(stints):
        # Apply carryover from previous stint
        if carryover_fuel is not None:
            stint_config.fuel_start_kg = carryover_fuel
        if carryover_temps is not None:
            stint_config.initial_tire_temps = carryover_temps
        if carryover_wear is not None:
            stint_config.cumulative_tire_wear = carryover_wear

        # Ensure circuit_id is set
        stint_config.circuit_id = stint_config.circuit_id or circuit_id

        # Run stint
        stint_result = simulate_stint(stint_config)
        stint_results.append(stint_result)

        # Collect lap results
        all_laps.extend(stint_result.lap_results)
        total_time += stint_result.total_time_s

        # Count pit stops
        if stint_result.pit_stop_lap is not None:
            total_pit_stops += 1

        # Carryover for next stint
        carryover_fuel = stint_result.final_fuel_kg
        carryover_temps = stint_result.final_tire_temps
        carryover_wear = stint_result.final_tire_wear

    return {
        "total_time_s": total_time,
        "lap_results": all_laps,
        "stint_results": stint_results,
        "total_pit_stops": total_pit_stops,
        "total_laps": len(all_laps),
    }