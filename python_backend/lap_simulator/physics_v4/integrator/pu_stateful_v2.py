"""
Power Unit Stateful Model — V5.4 (Deployment Zones)

Replaces the flat-power V5.3 model with a torque-based, stateful model that
uses pre-computed deployment zones instead of per-waypoint bucket logic.

Architecture:
  1. Pre-compute: analyze waypoints → identify straights & corner exits
  2. Allocate: distribute deploy budget across zones (primary/exit)
  3. During lap: if dist_m in a deployment zone → deploy at target power
  4. Harvesting: MGU-K during braking, MGU-H ES when throttle > 0

Reference: docs/physics-engine-v5.4-pu-stateful.md
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================================
# Constants
# ============================================================================

# Transmission
R_WHEEL = 0.334          # m — F1 wheel radius
FINAL_DRIVE = 4.10       # Final drive ratio
DRIVETRAIN_EFFICIENCY = 0.96  # Calibratable for energy normalization

# Gear ratios (from EngineData2025.md)
GEAR_RATIOS = [2.53, 1.96, 1.63, 1.40, 1.22, 1.10, 1.01, 0.92]

# ICE Torque curve — calibrated to match V5.3 baseline (~750 kW avg)
# Flatter curve: less low-end torque (traction-limited anyway), more mid-high range
# This prevents V5.4 from being too fast on slow circuits (Monaco)
# where V5.3's power/v model gives high force but is traction-capped
# (RPM, Torque_Nm)
ICE_TORQUE_LUT = [
    (0,     0),     # Electric launch
    (1500,  160),   # Turbo spooling
    (4000,  454),   # Traction zone (+8% for corner exit power)
    (6500,  588),   # Peak acceleration (+5% for mid-range)
    (8500,  676),   # Mid-range sustain (MAX TORQUE)
    (10500, 656),   # Fuel flow limit hit
    (11500, 616),   # Optimal shift window
    (12500, 566),   # Power dropoff
    (13500, 476),   # Mechanical stress high
]

# MGU-H section factors (from power_unit.py V2)
SECTION_MGUH_FACTORS = {
    "Straight": 1.00,
    "MediumStraight": 0.90,
    "UltraFastCorner": 0.85,
    "FastCorner": 0.75,
    "MediumCorner": 0.60,
    "SlowCorner": 0.45,
    "VerySlowCorner": 0.35,
}

# Thermal model parameters
THERMAL_K_JOULE = 0.000012   # Heat generation coefficient
THERMAL_H_V = 0.0040        # Cooling coefficient
THERMAL_C_TH = 18.0         # kJ/K
THERMAL_T_LIMIT = 115.0     # °C — clipping onset
THERMAL_T_MAX = 145.0       # °C — full shutdown
THERMAL_T_AMB = 30.0        # °C
THERMAL_SUBSTEP_S = 0.01    # s — minimum step for numerical stability

# ERS limits (FIA regulations 2025)
ERS_MAX_DEPLOY_MJ = 4.0
ERS_MAX_HARVEST_MJ = 2.0
BATTERY_CAPACITY_MJ = 4.0
MGUK_HARVEST_MAX_KW = 120.0  # Max MGU-K harvest power

# Circuit type → deploy split (primary/exit)
CIRCUIT_TYPE_SPLITS = {
    "low_df": {"primary_pct": 0.85, "exit_pct": 0.15},   # Monza, Spa
    "medium_df": {"primary_pct": 0.70, "exit_pct": 0.30}, # Austin, Barcelona
    "high_df": {"primary_pct": 0.55, "exit_pct": 0.45},   # Monaco, Hungary
}

# Default split
DEFAULT_DEPLOY_SPLIT = {"primary_pct": 0.75, "exit_pct": 0.25}


# ============================================================================
# Deployment Zone
# ============================================================================

@dataclass
class DeploymentZone:
    """A pre-computed zone where ERS energy is deployed."""
    name: str = ""
    start_m: float = 0.0       # Start distance (m)
    end_m: float = 0.0         # End distance (m)
    zone_type: str = "primary"  # "primary" (straights) or "exit" (corner exits)
    allocated_mj: float = 0.0   # Energy allocated to this zone
    target_power_kw: float = 0.0  # Target MGU-K power in this zone
    remaining_mj: float = 0.0   # Energy remaining (consumed during lap)


# ============================================================================
# PU_Context — State transported between waypoints
# ============================================================================

@dataclass
class PU_Context:
    """Power Unit state transported between waypoints."""

    # Active map
    engine_map: str = "QUALIFY"

    # Battery (ES)
    soc_mj: float = 4.0
    battery_capacity_mj: float = 4.0

    # Deployment Zones (pre-computed)
    deployment_zones: List[DeploymentZone] = field(default_factory=list)
    circuit_length_m: float = 5000.0

    # MGU-H Direct
    mguh_direct_remaining_mj: float = 0.0
    mguh_direct_total_mj: float = 0.0
    mguh_direct_section_mj: float = 0.0

    # Thermal
    ers_temp_c: float = 55.0
    ice_temp_c: float = 95.0

    # Lap tracking
    lap_deploy_mj: float = 0.0
    lap_harvest_mj: float = 0.0
    lap_mguh_direct_mj: float = 0.0

    # Map parameters (from pu_maps.json)
    deploy_mj_per_lap: float = 4.0
    harvest_mj_per_lap: float = 1.3
    target_soc_end_lap: float = 0.05
    mguh_direct_ratio: float = 0.45
    mguh_power_kw: float = 42.0
    ers_output_kw: float = 160.0
    ice_power_pct_base: float = 1.10

    # Deploy split (primary vs exit)
    deploy_primary_pct: float = 0.75
    deploy_exit_pct: float = 0.25

    # Dynamic SOC Floor
    soc_floor_dynamic_pct: float = 0.0
    reserve_soc: float = 0.15
    late_soc_floor: float = 0.0

    # ERS Modes
    ers_push_mode: bool = False
    ers_defense_mode: bool = False

    # Energy trace for telemetry
    energy_trace: list = field(default_factory=list)


# ============================================================================
# Initialization
# ============================================================================

def load_pu_maps(circuit_id: str) -> Optional[Dict]:
    """Load pu_maps.json for a circuit."""
    derived_path = Path(__file__).parent.parent.parent.parent.parent / "config" / "circuits" / "derived" / circuit_id / "pu_maps.json"
    if derived_path.exists():
        with open(derived_path) as f:
            return json.load(f)

    data_path = Path(__file__).parent.parent.parent.parent / "data" / "circuits" / "derived" / circuit_id / "pu_maps.json"
    if data_path.exists():
        with open(data_path) as f:
            return json.load(f)

    return None


def load_waypoints(circuit_id: str) -> Optional[List[Dict]]:
    """Load HD waypoints for a circuit."""
    wp_path = Path(__file__).parent.parent.parent.parent.parent / "python_backend" / "data" / "circuits" / "2025" / f"{circuit_id}_HD.json"
    if wp_path.exists():
        with open(wp_path) as f:
            data = json.load(f)
        return data.get("waypoints", [])
    return None


def _classify_circuit(waypoints: List[Dict]) -> str:
    """Classify circuit as low_df, medium_df, or high_df based on straight characteristics.
    
    Uses both straight ratio AND average straight length to distinguish:
    - Monaco has many short "straights" (100-200m) between corners → high_df
    - Monza/Spa have long straights (500m+) → low_df
    - Austin has medium straights → medium_df
    """
    total = len(waypoints)
    if total == 0:
        return "medium_df"

    # Find straight sections and their lengths
    straight_sections = []
    in_straight = False
    straight_start = 0
    
    for i, w in enumerate(waypoints):
        is_straight = w.get("section_kind", "") in ("Straight", "MediumStraight")
        if is_straight and not in_straight:
            straight_start = w.get("dist_m", 0)
            in_straight = True
        elif not is_straight and in_straight:
            straight_end = waypoints[i - 1].get("dist_m", 0) if i > 0 else straight_start
            length = straight_end - straight_start
            if length > 50:  # Ignore very short sections
                straight_sections.append(length)
            in_straight = False
    
    # Handle straight that wraps around end of lap
    if in_straight:
        straight_end = waypoints[-1].get("dist_m", 0)
        length = straight_end - straight_start
        if length > 50:
            straight_sections.append(length)
    
    straight_count = sum(1 for w in waypoints if w.get("section_kind", "") in ("Straight", "MediumStraight"))
    straight_ratio = straight_count / total
    
    # Average straight length (0 if no straights)
    avg_straight_length = sum(straight_sections) / len(straight_sections) if straight_sections else 0
    
    # Classification based on straight characteristics:
    # Use both average straight length AND maximum straight length
    # Monaco has short straights (avg 248m, max 555m) → high_df
    # Austin has medium straights (avg 429m, max 1052m) → medium_df
    # Monza/Spa have long straights (avg 700m+, max 1100m+) → low_df
    max_straight_length = max(straight_sections) if straight_sections else 0
    
    if avg_straight_length > 500 or max_straight_length > 1200:
        return "low_df"      # Monza, Spa — very long straights
    elif avg_straight_length > 300 or max_straight_length > 800:
        return "medium_df"   # Austin, Barcelona — medium straights
    else:
        return "high_df"     # Monaco, Hungary — short straights, tight corners


def compute_deployment_zones(
    waypoints: List[Dict],
    deploy_mj_per_lap: float,
    ers_output_kw: float,
    circuit_type: str = "medium_df",
    engine_map: str = "QUALIFY",
) -> List[DeploymentZone]:
    """Analyze waypoints and generate deployment zones.

    Strategy:
    - Identify straights (primary zones) and corner exits (exit zones)
    - Allocate deploy budget based on circuit type split
    - Each zone gets a target power proportional to its length and allocation
    - In QUALIFY: deploy aggressively (full power in zones)
    - In RACE: deploy conservatively (save energy for defense)
    
    V5.4.2: Exit zones deploy at high power (85% of ers_output_kw)
    with throttle threshold at 5% (was 10%), making them effective
    for corner exit acceleration.
    """
    if not waypoints:
        return []

    # Get split for circuit type
    split = CIRCUIT_TYPE_SPLITS.get(circuit_type, DEFAULT_DEPLOY_SPLIT)
    primary_pct = split["primary_pct"]
    exit_pct = split["exit_pct"]

    # In QUALIFY, push more energy to straights
    if engine_map == "QUALIFY":
        primary_pct = min(0.90, primary_pct + 0.10)
        exit_pct = 1.0 - primary_pct

    # Identify straight segments (consecutive Straight/MediumStraight waypoints)
    zones: List[DeploymentZone] = []
    circuit_length = waypoints[-1].get("dist_m", 5000.0)

    # --- Find primary zones (straights) ---
    i = 0
    while i < len(waypoints):
        wp = waypoints[i]
        section = wp.get("section_kind", "Straight")
        if section in ("Straight", "MediumStraight"):
            start_dist = wp.get("dist_m", 0.0)
            # Extend until section changes
            while i < len(waypoints) and waypoints[i].get("section_kind", "") in ("Straight", "MediumStraight"):
                i += 1
            end_dist = waypoints[min(i, len(waypoints) - 1)].get("dist_m", start_dist + 50.0)
            length = end_dist - start_dist

            # Only create zones for meaningful straights (> 50m)
            if length > 50:
                zones.append(DeploymentZone(
                    name=f"Straight_{len(zones)+1}",
                    start_m=start_dist,
                    end_m=end_dist,
                    zone_type="primary",
                    allocated_mj=0.0,  # Will be allocated below
                    target_power_kw=0.0,
                    remaining_mj=0.0,
                ))
        else:
            i += 1

    # --- Find exit zones (corner exits → next straight) ---
    for j in range(1, len(waypoints) - 1):
        prev_section = waypoints[j - 1].get("section_kind", "")
        curr_section = waypoints[j].get("section_kind", "")
        next_section = waypoints[j + 1].get("section_kind", "") if j + 1 < len(waypoints) else ""

        # Corner exit: current is corner, next is straight
        is_corner = curr_section not in ("Straight", "MediumStraight")
        next_is_straight = next_section in ("Straight", "MediumStraight")

        if is_corner and next_is_straight:
            # Check if there's already an exit zone near this distance
            dist = waypoints[j].get("dist_m", 0.0)
            already_exists = any(
                abs(z.start_m - dist) < 120 and z.zone_type == "exit"
                for z in zones
            )
            if not already_exists:
                # Exit zone: from this waypoint to ~120m after (wider for better acceleration)
                exit_start = dist
                exit_end = min(dist + 120, circuit_length)
                zones.append(DeploymentZone(
                    name=f"Exit_{len(zones)+1}",
                    start_m=exit_start,
                    end_m=exit_end,
                    zone_type="exit",
                    allocated_mj=0.0,
                    target_power_kw=0.0,
                    remaining_mj=0.0,
                ))

    # --- Allocate energy across zones ---
    primary_zones = [z for z in zones if z.zone_type == "primary"]
    exit_zones = [z for z in zones if z.zone_type == "exit"]

    # Total primary and exit length
    total_primary_length = sum(z.end_m - z.start_m for z in primary_zones)
    total_exit_length = sum(z.end_m - z.start_m for z in exit_zones)

    # Allocate budget
    primary_budget = deploy_mj_per_lap * primary_pct
    exit_budget = deploy_mj_per_lap * exit_pct

    # Estimate average speed for time calculation
    if circuit_type == "low_df":
        avg_speed_primary = 85.0   # m/s (~306 km/h) — Monza, Spa
        avg_speed_exit = 55.0      # m/s (~198 km/h)
    elif circuit_type == "high_df":
        avg_speed_primary = 50.0   # m/s (~180 km/h) — Monaco, Hungary
        avg_speed_exit = 35.0      # m/s (~126 km/h)
    else:  # medium_df
        avg_speed_primary = 70.0   # m/s (~252 km/h) — Austin, Barcelona
        avg_speed_exit = 45.0      # m/s (~162 km/h)

    # Distribute within each type proportional to estimated time in zone
    total_primary_time = sum((z.end_m - z.start_m) / avg_speed_primary for z in primary_zones) if primary_zones else 1.0
    total_exit_time = sum((z.end_m - z.start_m) / avg_speed_exit for z in exit_zones) if exit_zones else 1.0

    # Circuit-type dependent boost factors for QUALIFY mode
    PRIMARY_BOOST_FACTORS = {
        "low_df": 2.5,      # Monza, Spa — long straights, need more boost
        "medium_df": 2.2,   # Austin, Barcelona — balanced
        "high_df": 2.0,     # Monaco, Hungary — short zones, less boost needed
    }
    primary_boost = PRIMARY_BOOST_FACTORS.get(circuit_type, 2.0)

    if engine_map == "QUALIFY":
        # QUALIFY: compute base power level from budget / total time
        primary_base_power = primary_budget / max(total_primary_time, 0.01) * 1000.0
        exit_base_power = exit_budget / max(total_exit_time, 0.01) * 1000.0

        for z in primary_zones:
            length = z.end_m - z.start_m
            time_in_zone = length / avg_speed_primary
            frac = time_in_zone / max(total_primary_time, 0.01)
            z.allocated_mj = primary_budget * frac
            # Target power: base power * boost factor, capped at ers_output_kw
            z.target_power_kw = min(ers_output_kw, primary_base_power * primary_boost)
            z.remaining_mj = z.allocated_mj

        for z in exit_zones:
            length = z.end_m - z.start_m
            time_in_zone = length / avg_speed_exit
            frac = time_in_zone / max(total_exit_time, 0.01)
            z.allocated_mj = exit_budget * frac
            # Exit zones: deploy at 85% of ers_output_kw for strong corner exit acceleration
            # This is much higher than the base power to ensure effective deployment
            z.target_power_kw = min(ers_output_kw * 0.85, exit_base_power * 3.0)
            z.remaining_mj = z.allocated_mj

    else:
        # RACE: conservative deployment, save energy for defense
        for z in primary_zones:
            length = z.end_m - z.start_m
            time_in_zone = length / avg_speed_primary
            frac = time_in_zone / max(total_primary_time, 0.01)
            z.allocated_mj = primary_budget * frac
            z.target_power_kw = min(ers_output_kw * 0.85, z.allocated_mj / max(time_in_zone, 0.01) * 1000.0)
            z.remaining_mj = z.allocated_mj

        for z in exit_zones:
            length = z.end_m - z.start_m
            time_in_zone = length / avg_speed_exit
            frac = time_in_zone / max(total_exit_time, 0.01)
            z.allocated_mj = exit_budget * frac
            z.target_power_kw = min(ers_output_kw * 0.70, z.allocated_mj / max(time_in_zone, 0.01) * 1000.0)
            z.remaining_mj = z.allocated_mj

    return zones


def init_pu_context(circuit_id: str, engine_map: str = "QUALIFY") -> PU_Context:
    """Initialize PU_Context from pu_maps.json for the given circuit and map."""
    pu_maps = load_pu_maps(circuit_id)

    ctx = PU_Context(engine_map=engine_map)
    ctx.soc_mj = BATTERY_CAPACITY_MJ  # Battery full at start of lap

    if pu_maps is None:
        # Fallback: use defaults (already set in dataclass)
        return ctx

    # Map data (top-level maps)
    map_data = pu_maps.get("maps", {}).get(engine_map, {})
    # Budget data (ers_budget.maps)
    budget_data = pu_maps.get("ers_budget", {}).get("maps", {}).get(engine_map, {})

    # If budget_data is empty, fall back to map_data for budget fields
    if not budget_data:
        budget_data = map_data

    # Map parameters
    ctx.ers_output_kw = map_data.get("ers_output_kw", 160.0)
    ctx.ice_power_pct_base = map_data.get("torque_ramp", 1.0)
    ctx.mguh_power_kw = map_data.get("mguh_power_kw", 42.0)

    # Budget parameters
    ctx.deploy_mj_per_lap = budget_data.get("deploy_mj_per_lap", 4.0)
    ctx.harvest_mj_per_lap = budget_data.get("harvest_mj_per_lap", 1.3)
    ctx.target_soc_end_lap = budget_data.get("target_soc_end_lap", 0.05)
    ctx.mguh_direct_ratio = budget_data.get("mguh_direct_ratio", 0.45)

    # Deploy split from bucket percentages (reuse existing config)
    ctx.deploy_primary_pct = budget_data.get("bucket_primary_pct", 0.75)
    ctx.deploy_exit_pct = budget_data.get("bucket_exit_pct", 0.25)

    # MGU-H direct budget
    meta = pu_maps.get("_meta", {})
    stats = meta.get("stats", {})
    lap_time_estimate = stats.get("lap_time_s", 90.0)
    mguh_profile = meta.get("mguh_profile", {})
    ctx.mguh_direct_total_mj = mguh_profile.get("direct_mj",
                                                   ctx.mguh_power_kw * lap_time_estimate / 1000.0)
    ctx.mguh_direct_remaining_mj = ctx.mguh_direct_total_mj

    # Dynamic SOC Floor initialization
    is_qualy = engine_map == "QUALIFY"
    min_soc_clamp = 0.02 if is_qualy else 0.2
    ctx.reserve_soc = _clamp(ctx.target_soc_end_lap + 0.10, min_soc_clamp + 0.05, 0.98)
    ctx.late_soc_floor = _clamp(ctx.target_soc_end_lap - 0.12, 0.02, 0.90)

    # ERS mode defaults
    ctx.ers_push_mode = is_qualy

    # Compute deployment zones from waypoints
    waypoints = load_waypoints(circuit_id)
    if waypoints:
        ctx.circuit_length_m = waypoints[-1].get("dist_m", 5000.0)
        circuit_type = _classify_circuit(waypoints)
        ctx.deployment_zones = compute_deployment_zones(
            waypoints=waypoints,
            deploy_mj_per_lap=ctx.deploy_mj_per_lap,
            ers_output_kw=ctx.ers_output_kw,
            circuit_type=circuit_type,
            engine_map=engine_map,
        )

    return ctx


# ============================================================================
# ICE Torque
# ============================================================================

def interpolate_lut(lut: list, x: float) -> float:
    """Linear interpolation in a look-up table [(x, y), ...]."""
    if x <= lut[0][0]:
        return lut[0][1]
    if x >= lut[-1][0]:
        return lut[-1][1]

    for i in range(len(lut) - 1):
        x0, y0 = lut[i]
        x1, y1 = lut[i + 1]
        if x0 <= x <= x1:
            if x1 == x0:
                return y0
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)

    return lut[-1][1]


def lookup_ice_torque(rpm: float, ice_power_pct: float) -> float:
    """Interpolate ICE torque from LUT, scaled by engine map."""
    torque = interpolate_lut(ICE_TORQUE_LUT, rpm)
    return torque * ice_power_pct


# ============================================================================
# Synthetic Gearbox (Level 3 fallback)
# ============================================================================

def get_optimal_gear(v_ms: float) -> Tuple[int, float, float]:
    """Select gear and compute RPM to keep RPM in 10500-11800 range."""
    for i, gr in enumerate(GEAR_RATIOS):
        rpm = v_ms * 60.0 / (2.0 * math.pi * R_WHEEL) * gr * FINAL_DRIVE
        if 10500 <= rpm <= 12500:
            return i + 1, gr, rpm
        if rpm < 10500:
            return i + 1, gr, rpm

    gr = GEAR_RATIOS[-1]
    rpm = v_ms * 60.0 / (2.0 * math.pi * R_WHEEL) * gr * FINAL_DRIVE
    return 8, gr, rpm


def get_gear_ratio_from_n_gear(n_gear: int) -> float:
    """Return gear ratio from nGear (1-8)."""
    idx = max(0, min(n_gear - 1, 7))
    return GEAR_RATIOS[idx]


# ============================================================================
# Zone Lookup
# ============================================================================

def _find_deployment_zone(pu_ctx: PU_Context, dist_m: float) -> Optional[DeploymentZone]:
    """Find the deployment zone that contains this distance.

    Handles wrap-around (dist_m near circuit_length).
    """
    for zone in pu_ctx.deployment_zones:
        if zone.start_m <= dist_m <= zone.end_m:
            return zone
        # Handle wrap-around for zones near end of lap
        if zone.end_m > pu_ctx.circuit_length_m:
            if dist_m >= zone.start_m or dist_m <= (zone.end_m % pu_ctx.circuit_length_m):
                return zone
    return None


# ============================================================================
# Harvesting
# ============================================================================

def compute_mguk_harvest(
    pu_ctx: PU_Context,
    brake_pct: float,
    v_ms: float,
    dt_s: float,
) -> float:
    """Compute energy recovered from braking and update SOC.

    Returns energy stored in battery (MJ).
    """
    if brake_pct < 5:
        return 0.0

    # Harvest power proportional to brake intensity (max 120 kW MGU-K)
    harvest_power_kw = MGUK_HARVEST_MAX_KW * (brake_pct / 100.0)

    # Limit by per-lap harvest budget
    remaining_harvest_mj = pu_ctx.harvest_mj_per_lap - pu_ctx.lap_harvest_mj
    if remaining_harvest_mj <= 0:
        return 0.0

    max_energy_mj = harvest_power_kw * dt_s / 1000.0
    energy_mj = min(max_energy_mj, remaining_harvest_mj)

    # Overflow: if battery full, energy is dissipated
    headroom_mj = pu_ctx.battery_capacity_mj - pu_ctx.soc_mj
    energy_stored_mj = min(energy_mj, headroom_mj)

    # Update state
    pu_ctx.soc_mj += energy_stored_mj
    pu_ctx.lap_harvest_mj += energy_mj  # Count all, even dissipated

    return energy_stored_mj


def compute_mguh_es_harvest(
    pu_ctx: PU_Context,
    section_kind: str,
    throttle_pct: float,
    dt_s: float,
) -> float:
    """Compute MGU-H energy that goes to battery (not direct path)."""
    es_bias = 1.0 - pu_ctx.mguh_direct_ratio
    if es_bias <= 0:
        return 0.0

    section_factor = SECTION_MGUH_FACTORS.get(section_kind, 0.5)
    throttle_factor = throttle_pct / 100.0

    mguh_total_power_kw = pu_ctx.mguh_power_kw * section_factor * throttle_factor
    mguh_es_power_kw = mguh_total_power_kw * es_bias
    energy_mj = mguh_es_power_kw * dt_s / 1000.0

    # Overflow check
    headroom_mj = pu_ctx.battery_capacity_mj - pu_ctx.soc_mj
    energy_stored_mj = min(energy_mj, headroom_mj)

    pu_ctx.soc_mj += energy_stored_mj
    return energy_stored_mj


# ============================================================================
# Propulsive Force (V5.4 — Deployment Zones)
# ============================================================================

def compute_f_engine_v54(
    pu_ctx: PU_Context,
    rpm: float,
    gear_ratio: float,
    throttle_pct: float,
    section_kind: str,
    dt_s: float,
    lap_progress: float,
    is_corner: bool,
    radius_m: float,
    driver_skill: float = 1.0,
    brake_pct: float = 0.0,
    drs_active: bool = False,
    section_length_m: float = 100.0,
    v_ms: float = 80.0,
    dist_m: float = 0.0,
) -> float:
    """Compute propulsive force using V5.4 torque-based model with deployment zones.

    Architecture:
    - Pre-computed deployment zones define WHERE and HOW MUCH to deploy
    - If dist_m is in a zone → deploy at target_power_kw (up to SOC/budget limit)
    - If dist_m is NOT in a zone → no MGU-K deploy (only ICE + MGU-H direct)
    - Harvesting happens during braking regardless of zones
    """
    # 1. ICE Torque (scaled by throttle — driver lifts off = less engine power)
    # In V5.3, throttle directly scales the power: P = P_max * rpm_frac * throttle
    # In V5.4, we must do the same: ICE torque is zero when throttle is zero,
    # and scales linearly with throttle position.
    throttle_factor_ice = max(throttle_pct / 100.0, 0.0)
    ice_torque = lookup_ice_torque(rpm, pu_ctx.ice_power_pct_base) * throttle_factor_ice

    # 2. Dynamic SOC Floor
    pu_ctx.soc_floor_dynamic_pct = (
        pu_ctx.reserve_soc - (pu_ctx.reserve_soc - pu_ctx.late_soc_floor) * lap_progress
    )

    # 3. MGU-K Torque — Deployment Zone logic
    mguk_torque = 0.0
    battery_energy_mj = 0.0
    zone_name = "none"

    # Find if we're in a deployment zone
    zone = _find_deployment_zone(pu_ctx, dist_m)

    if zone is not None and zone.remaining_mj > 0.001 and pu_ctx.soc_mj > 0.01:
        zone_name = zone.zone_type

        # SOC headroom: how much battery we can use
        soc_headroom_mj = max(
            pu_ctx.soc_mj - pu_ctx.soc_floor_dynamic_pct * pu_ctx.battery_capacity_mj,
            0.0
        )

        if soc_headroom_mj > 0.01 or pu_ctx.ers_push_mode:
            # Compute target power for this step
            target_power_kw = zone.target_power_kw

            # Throttle modulation: reduce deploy if throttle < 100%
            # V5.4.1: Lowered threshold from 10% to 5% because primary zones
            # now extend backward into corner exits where throttle is low but
            # the car is already accelerating
            throttle_factor = min(throttle_pct / 100.0, 1.0)
            if throttle_factor < 0.05:
                target_power_kw = 0.0
            else:
                target_power_kw *= throttle_factor

            # Compute energy for this step
            step_energy_mj = target_power_kw * dt_s / 1000.0

            # Limit by zone remaining budget
            step_energy_mj = min(step_energy_mj, zone.remaining_mj)

            # Limit by SOC headroom
            step_energy_mj = min(step_energy_mj, soc_headroom_mj)

            # In push mode, allow using more SOC (down to 2%)
            if pu_ctx.ers_push_mode and step_energy_mj < target_power_kw * dt_s / 1000.0 * 0.5:
                push_headroom = max(pu_ctx.soc_mj - 0.02 * pu_ctx.battery_capacity_mj, 0.0)
                step_energy_mj = min(target_power_kw * dt_s / 1000.0, push_headroom, zone.remaining_mj)

            # Thermal clipping
            thermal_eta = compute_thermal_eta(pu_ctx.ers_temp_c)
            step_energy_mj *= thermal_eta

            # Convert energy to torque
            if step_energy_mj > 0.0001 and dt_s > 0:
                mguk_power_kw = step_energy_mj * 1000.0 / dt_s
                omega = rpm * 2.0 * math.pi / 60.0
                mguk_torque = mguk_power_kw * 1000.0 / max(omega, 1.0) if omega > 1.0 else 0.0

                # Update state
                battery_energy_mj = step_energy_mj
                zone.remaining_mj = max(0.0, zone.remaining_mj - step_energy_mj)
                pu_ctx.soc_mj = max(0.0, pu_ctx.soc_mj - step_energy_mj)
                pu_ctx.lap_deploy_mj += step_energy_mj

    elif pu_ctx.ers_push_mode and pu_ctx.soc_mj > 0.02 * pu_ctx.battery_capacity_mj and throttle_pct > 30:
        # QUALIFY fallback: zones exhausted but SOC still has energy
        # Deploy at moderate power on straights — this is surplus energy
        # that wasn't allocated to zones, use it wisely
        if section_kind in ("Straight", "MediumStraight"):
            zone_name = "overflow"
            soc_headroom = max(pu_ctx.soc_mj - 0.02 * pu_ctx.battery_capacity_mj, 0.0)
            # Calculate remaining lap fraction to pace the overflow energy
            remaining_lap_frac = max(0.01, 1.0 - lap_progress)
            # Target: spread remaining SOC across remaining lap time
            # Estimate remaining time from lap progress
            remaining_time_s = max(1.0, (1.0 - lap_progress) * 80.0)  # ~80s lap estimate
            overflow_power_kw = min(
                pu_ctx.ers_output_kw * 0.60,  # Cap at 60% of max
                soc_headroom * 1000.0 / remaining_time_s  # Pace to last the lap
            ) * (throttle_pct / 100.0)
            step_energy_mj = min(overflow_power_kw * dt_s / 1000.0, soc_headroom)

            if step_energy_mj > 0.0001 and dt_s > 0:
                thermal_eta = compute_thermal_eta(pu_ctx.ers_temp_c)
                step_energy_mj *= thermal_eta
                mguk_power_kw = step_energy_mj * 1000.0 / dt_s
                omega = rpm * 2.0 * math.pi / 60.0
                mguk_torque = mguk_power_kw * 1000.0 / max(omega, 1.0) if omega > 1.0 else 0.0

                battery_energy_mj = step_energy_mj
                pu_ctx.soc_mj = max(0.0, pu_ctx.soc_mj - step_energy_mj)
                pu_ctx.lap_deploy_mj += step_energy_mj

    # 4. MGU-H Direct Torque (always available when throttle > 0)
    section_factor = SECTION_MGUH_FACTORS.get(section_kind, 0.5)
    throttle_factor = throttle_pct / 100.0
    mguh_power_kw = pu_ctx.mguh_power_kw * section_factor * throttle_factor

    # Thermal clipping
    thermal_eta = compute_thermal_eta(pu_ctx.ers_temp_c)
    mguh_power_kw *= thermal_eta

    # Budget check
    mguh_energy_mj = mguh_power_kw * dt_s / 1000.0
    pu_ctx.mguh_direct_section_mj = mguh_energy_mj
    if mguh_energy_mj > pu_ctx.mguh_direct_remaining_mj:
        mguh_energy_mj = pu_ctx.mguh_direct_remaining_mj
        mguh_power_kw = mguh_energy_mj * 1000.0 / dt_s if dt_s > 0 else 0.0
        pu_ctx.mguh_direct_section_mj = mguh_energy_mj

    omega = rpm * 2.0 * math.pi / 60.0
    mguh_torque = mguh_power_kw * 1000.0 / max(omega, 1.0) if omega > 1.0 else 0.0

    # Update MGU-H direct state
    pu_ctx.mguh_direct_remaining_mj = max(0.0, pu_ctx.mguh_direct_remaining_mj - mguh_energy_mj)
    pu_ctx.lap_mguh_direct_mj += mguh_energy_mj

    # 5. Harvesting (if braking)
    harvest_mj = 0.0
    if brake_pct > 5:
        harvest_mj = compute_mguk_harvest(pu_ctx, brake_pct, v_ms, dt_s)
    # MGU-H ES harvest (when throttle > 0, not during braking)
    compute_mguh_es_harvest(pu_ctx, section_kind, throttle_pct, dt_s)

    # 6. Total torque
    total_torque = ice_torque + mguk_torque + mguh_torque

    # 7. Force at wheel
    f_engine = total_torque * gear_ratio * FINAL_DRIVE * DRIVETRAIN_EFFICIENCY / R_WHEEL

    # 8. Power limit: force cannot exceed total_power / v
    # This is physically correct and prevents V5.4 from having too much
    # force at low speeds compared to V5.3's power/v model.
    # Total power = ICE power + MGU-K power + MGU-H power
    if v_ms > 1.0:
        ice_power_kw = ice_torque * rpm * 2.0 * math.pi / 60.0 / 1000.0
        mguk_power_actual_kw = mguk_torque * rpm * 2.0 * math.pi / 60.0 / 1000.0
        mguh_power_actual_kw = mguh_torque * rpm * 2.0 * math.pi / 60.0 / 1000.0
        total_power_kw = ice_power_kw + mguk_power_actual_kw + mguh_power_actual_kw
        max_force_from_power = total_power_kw * 1000.0 / v_ms
        f_engine = min(f_engine, max_force_from_power)

    # 9. Corner traction limit
    if is_corner:
        corner_factor = min(1.0, 1000.0 / max(radius_m, 100.0))
        f_engine *= corner_factor

    # 9. Driver skill
    f_engine *= driver_skill

    # 10. Energy trace
    pu_ctx.energy_trace.append({
        "dist_m": round(dist_m, 1),
        "rpm": round(rpm, 0),
        "ice_torque_nm": round(ice_torque, 1),
        "mguk_torque_nm": round(mguk_torque, 1),
        "mguh_torque_nm": round(mguh_torque, 1),
        "soc_mj": round(pu_ctx.soc_mj, 4),
        "deploy_mj": round(battery_energy_mj, 4),
        "mguh_direct_mj": round(mguh_energy_mj, 4),
        "harvest_mj": round(harvest_mj, 4),
        "zone": zone_name,
        "zone_remaining_mj": round(zone.remaining_mj, 4) if zone else 0.0,
        "ers_temp_c": round(pu_ctx.ers_temp_c, 1),
    })

    return f_engine


# ============================================================================
# Thermal Model
# ============================================================================

def compute_thermal_eta(ers_temp_c: float) -> float:
    """Compute thermal efficiency factor (1.0 = no clipping, 0.0 = shutdown)."""
    if ers_temp_c < THERMAL_T_LIMIT:
        return 1.0
    elif ers_temp_c >= THERMAL_T_MAX:
        return 0.0
    else:
        return 1.0 - (ers_temp_c - THERMAL_T_LIMIT) / (THERMAL_T_MAX - THERMAL_T_LIMIT)


def update_thermal_state(
    pu_ctx: PU_Context,
    p_elec_kw: float,
    v_ms: float,
    dt_s: float,
) -> None:
    """Update ERS temperature with sub-stepping for numerical stability."""
    n_steps = max(1, int(math.ceil(dt_s / THERMAL_SUBSTEP_S)))
    sub_dt = dt_s / n_steps

    for _ in range(n_steps):
        q_gen = THERMAL_K_JOULE * (p_elec_kw ** 2)
        q_cool = THERMAL_H_V * v_ms * max(pu_ctx.ers_temp_c - THERMAL_T_AMB, 0.0)
        delta_t = (q_gen - q_cool) / (THERMAL_C_TH * 1000.0) * sub_dt

        pu_ctx.ers_temp_c += delta_t
        pu_ctx.ers_temp_c = max(THERMAL_T_AMB, min(pu_ctx.ers_temp_c, 150.0))


# ============================================================================
# Utility
# ============================================================================

def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))