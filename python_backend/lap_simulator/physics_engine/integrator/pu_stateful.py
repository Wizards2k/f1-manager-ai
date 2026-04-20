"""
Power Unit Stateful Model — V5.4

Replaces the flat-power V5.3 model (910 kW constant) with a torque-based,
stateful model that tracks SOC, buckets, thermal state, and MGU-H direct.

Reference: docs/physics-engine-v5.4-pu-stateful.md
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple


# ============================================================================
# Constants
# ============================================================================

# Transmission
R_WHEEL = 0.334          # m — F1 wheel radius
FINAL_DRIVE = 4.10       # Final drive ratio
DRIVETRAIN_EFFICIENCY = 0.96  # Calibratable for energy normalization

# Gear ratios (from EngineData2025.md)
GEAR_RATIOS = [2.53, 1.96, 1.63, 1.40, 1.22, 1.10, 1.01, 0.92]

# ICE Torque curve (from EngineData2025.md §4)
# (RPM, Torque_Nm)
ICE_TORQUE_LUT = [
    (0,     0),     # Electric launch
    (1500,  180),   # Turbo spooling
    (4000,  480),   # Traction zone
    (6500,  590),   # Peak acceleration
    (8500,  610),   # Mid-range sustain (MAX TORQUE)
    (10500, 575),   # Fuel flow limit hit
    (11500, 525),   # Optimal shift window
    (12500, 480),   # Power dropoff
    (13500, 400),   # Mechanical stress high
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

# Thermal model parameters (from ERS-ThermalClipping.md)
THERMAL_K_JOULE = 0.000012   # Heat generation coefficient (reduced for Phase 2)
THERMAL_H_V = 0.0040       # Cooling coefficient (increased for Phase 2)
THERMAL_C_TH = 18.0       # kJ/K
THERMAL_T_LIMIT = 115.0   # °C — clipping onset (raised for Phase 2)
THERMAL_T_MAX = 145.0     # °C — full shutdown (raised for Phase 2)
THERMAL_T_AMB = 30.0      # °C
THERMAL_SUBSTEP_S = 0.01  # s — minimum step for numerical stability

# ERS limits (FIA regulations 2025)
ERS_MAX_DEPLOY_MJ = 4.0
ERS_MAX_HARVEST_MJ = 2.0
BATTERY_CAPACITY_MJ = 4.0
MGUK_HARVEST_MAX_KW = 120.0  # Max MGU-K harvest power


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

    # ERS Buckets (per lap)
    bucket_primary_remaining_mj: float = 0.0
    bucket_secondary_remaining_mj: float = 0.0
    bucket_exit_remaining_mj: float = 0.0
    bucket_primary_total_mj: float = 0.0
    bucket_secondary_total_mj: float = 0.0
    bucket_exit_total_mj: float = 0.0
    bucket_sections_left: int = 0
    bucket_section_cap_mj: float = 0.0

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

    # Bucket percentages
    bucket_primary_pct: float = 0.60
    bucket_secondary_pct: float = 0.30
    bucket_exit_pct: float = 0.10
    defense_reserve_mj: float = 0.0

    # Dynamic SOC Floor (V2 integration)
    soc_floor_dynamic_pct: float = 0.0
    reserve_soc: float = 0.15
    late_soc_floor: float = 0.0

    # ERS Modes (V2 integration)
    ers_push_mode: bool = False
    ers_defense_mode: bool = False
    ers_recharge_mode: bool = False

    # Priority Scoring
    priority_score_threshold: float = 0.55

    # Spread (configurable)
    bucket_section_spread_lower: float = 0.8
    bucket_section_spread_upper: float = 1.2

    # Energy trace for telemetry
    energy_trace: list = field(default_factory=list)


# ============================================================================
# Initialization
# ============================================================================

def load_pu_maps(circuit_id: str) -> Optional[Dict]:
    """Load pu_maps.json for a circuit."""
    # Try config/circuits/derived/<cid>/pu_maps.json
    derived_path = Path(__file__).parent.parent.parent.parent.parent / "config" / "circuits" / "derived" / circuit_id / "pu_maps.json"
    if derived_path.exists():
        with open(derived_path) as f:
            return json.load(f)

    # Try python_backend/data/circuits/ derived path
    data_path = Path(__file__).parent.parent.parent.parent / "data" / "circuits" / "derived" / circuit_id / "pu_maps.json"
    if data_path.exists():
        with open(data_path) as f:
            return json.load(f)

    return None


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
    ctx.ice_power_pct_base = map_data.get("torque_ramp", 1.0)  # torque_ramp ≈ power_pct
    ctx.mguh_power_kw = map_data.get("mguh_power_kw", 42.0)

    # Budget parameters
    ctx.deploy_mj_per_lap = budget_data.get("deploy_mj_per_lap", 4.0)
    ctx.harvest_mj_per_lap = budget_data.get("harvest_mj_per_lap", 1.3)
    ctx.target_soc_end_lap = budget_data.get("target_soc_end_lap", 0.05)
    ctx.mguh_direct_ratio = budget_data.get("mguh_direct_ratio", 0.45)

    # Bucket allocation
    deploy_budget = ctx.deploy_mj_per_lap - budget_data.get("defense_reserve_mj", 0.0)
    ctx.bucket_primary_pct = budget_data.get("bucket_primary_pct", 0.60)
    ctx.bucket_secondary_pct = budget_data.get("bucket_secondary_pct", 0.30)
    ctx.bucket_exit_pct = budget_data.get("bucket_exit_pct", 0.10)
    ctx.defense_reserve_mj = budget_data.get("defense_reserve_mj", 0.0)
    pct_sum = ctx.bucket_primary_pct + ctx.bucket_secondary_pct + ctx.bucket_exit_pct

    if pct_sum > 0:
        ctx.bucket_primary_total_mj = deploy_budget * ctx.bucket_primary_pct / pct_sum
        ctx.bucket_secondary_total_mj = deploy_budget * ctx.bucket_secondary_pct / pct_sum
        ctx.bucket_exit_total_mj = deploy_budget * ctx.bucket_exit_pct / pct_sum
    else:
        ctx.bucket_primary_total_mj = deploy_budget
        ctx.bucket_secondary_total_mj = 0.0
        ctx.bucket_exit_total_mj = 0.0

    ctx.bucket_primary_remaining_mj = ctx.bucket_primary_total_mj
    ctx.bucket_secondary_remaining_mj = ctx.bucket_secondary_total_mj
    ctx.bucket_exit_remaining_mj = ctx.bucket_exit_total_mj

    # MGU-H direct budget (estimated from mguh_power_kw × lap_time)
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
    ctx.priority_score_threshold = 0.32 if is_qualy else 0.55

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
    """Select gear and compute RPM to keep RPM in 10500-11800 range.

    Returns:
        (gear_number, gear_ratio, rpm)
    """
    for i, gr in enumerate(GEAR_RATIOS):
        rpm = v_ms * 60.0 / (2.0 * math.pi * R_WHEEL) * gr * FINAL_DRIVE
        if 10500 <= rpm <= 12500:
            return i + 1, gr, rpm
        if rpm < 10500:
            # This gear gives RPM below optimal, but next gear would be too low
            return i + 1, gr, rpm

    # Fallback: highest gear
    gr = GEAR_RATIOS[-1]
    rpm = v_ms * 60.0 / (2.0 * math.pi * R_WHEEL) * gr * FINAL_DRIVE
    return 8, gr, rpm


def get_gear_ratio_from_n_gear(n_gear: int) -> float:
    """Return gear ratio from nGear (1-8)."""
    idx = max(0, min(n_gear - 1, 7))
    return GEAR_RATIOS[idx]


# ============================================================================
# Bucket Resolution
# ============================================================================

# Section kind → bucket mapping (from ERS-Bucket-Planner.md §3.2)
_BUCKET_MAP = {
    "Straight": "primary",
    "MediumStraight": "primary",
    "UltraFastCorner": "secondary",
    "FastCorner": "secondary",
    "MediumCorner": "exit",
    "SlowCorner": "exit",
    "VerySlowCorner": "exit",
}

# Section priority base scores (from driver_model.py V2)
SECTION_PRIORITY_BASE = {
    "Straight": 1.0,
    "MediumStraight": 0.85,
    "UltraFastCorner": 0.75,
    "FastCorner": 0.65,
    "MediumCorner": 0.5,
    "SlowCorner": 0.35,
    "VerySlowCorner": 0.25,
}


def _resolve_bucket(section_kind: str) -> str:
    """Map section_kind to ERS bucket: primary, secondary, or exit."""
    return _BUCKET_MAP.get(section_kind, "secondary")


def _get_bucket_remaining(pu_ctx: PU_Context, bucket: str) -> float:
    """Get remaining energy in the specified bucket."""
    if bucket == "primary":
        return pu_ctx.bucket_primary_remaining_mj
    elif bucket == "secondary":
        return pu_ctx.bucket_secondary_remaining_mj
    elif bucket == "exit":
        return pu_ctx.bucket_exit_remaining_mj
    return 0.0


def _consume_bucket(pu_ctx: PU_Context, bucket: str, energy_mj: float) -> None:
    """Consume energy from the specified bucket."""
    if bucket == "primary":
        pu_ctx.bucket_primary_remaining_mj = max(0.0, pu_ctx.bucket_primary_remaining_mj - energy_mj)
    elif bucket == "secondary":
        pu_ctx.bucket_secondary_remaining_mj = max(0.0, pu_ctx.bucket_secondary_remaining_mj - energy_mj)
    elif bucket == "exit":
        pu_ctx.bucket_exit_remaining_mj = max(0.0, pu_ctx.bucket_exit_remaining_mj - energy_mj)


def _count_sections_left(pu_ctx: PU_Context, bucket: str, lap_progress: float) -> int:
    """Estimate sections remaining in the current bucket.

    Uses the bucket's percentage of total sections and remaining progress.
    For Monza-like circuits with ~90% straights, primary gets ~90% of steps.
    """
    # Estimate total sections from energy trace (if available)
    total_sections_done = len(pu_ctx.energy_trace)
    if total_sections_done > 10:
        # Count how many sections of this bucket type we've seen so far
        bucket_pct_map = {
            "primary": pu_ctx.bucket_primary_pct,
            "secondary": pu_ctx.bucket_secondary_pct,
            "exit": pu_ctx.bucket_exit_pct,
        }
        bucket_pct = bucket_pct_map.get(bucket, 0.3)
        pct_sum = pu_ctx.bucket_primary_pct + pu_ctx.bucket_secondary_pct + pu_ctx.bucket_exit_pct
        if pct_sum > 0:
            bucket_pct = bucket_pct / pct_sum

        # Estimate total sections in lap from progress
        if lap_progress > 0.05:
            total_sections_estimate = int(total_sections_done / lap_progress)
        else:
            total_sections_estimate = max(total_sections_done * 10, 400)

        # Sections of this bucket remaining
        total_bucket_sections = int(total_sections_estimate * bucket_pct)
        bucket_done = int(total_sections_done * bucket_pct)
        sections_left = max(1, total_bucket_sections - bucket_done)
    else:
        # Fallback: rough estimate
        remaining_progress = max(0.01, 1.0 - lap_progress)
        total_sections_estimate = 400
        sections_left = max(1, int(remaining_progress * total_sections_estimate * 0.3))

    return sections_left


# ============================================================================
# Priority Scoring (V2 integration from driver_model.py)
# ============================================================================

def _estimate_section_priority(
    section_kind: str,
    section_length_m: float,
    drs_active: bool,
    push_mode: bool,
) -> float:
    """Estimate section priority for ERS deploy decision."""
    base = SECTION_PRIORITY_BASE.get(section_kind, 0.4)
    length_factor = _clamp(section_length_m / 350.0, 0.5, 1.3)
    score = base * length_factor
    if drs_active:
        score += 0.12
    if push_mode:
        score = score * 1.2 + 0.1
    return _clamp(score, 0.05, 1.2)


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
    """Compute MGU-H energy that goes to battery (not direct path).

    Returns energy stored in battery (MJ).
    """
    # ES bias = 1 - direct_ratio
    es_bias = 1.0 - pu_ctx.mguh_direct_ratio

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
# Propulsive Force (V5.4 — Full Bucket + SOC + Harvesting)
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
) -> float:
    """Compute propulsive force using V5.4 torque-based model with full bucket logic.

    This replaces the flat-power V5.3 model:
        OLD: f_engine = (ICE_PEAK + ERS_PEAK * fraction) * rpm_frac * throttle / v
        NEW: f_engine = (T_ICE + T_MGUK + T_MGUH) * G_ratio * FD * η / r_wheel
    """
    # 1. ICE Torque
    ice_torque = lookup_ice_torque(rpm, pu_ctx.ice_power_pct_base)

    # 2. Dynamic SOC Floor (V2 logic from driver_model.py)
    pu_ctx.soc_floor_dynamic_pct = (
        pu_ctx.reserve_soc - (pu_ctx.reserve_soc - pu_ctx.late_soc_floor) * lap_progress
    )

    # 3. Resolve bucket for this section (with overflow support)
    bucket = _resolve_bucket(section_kind)
    bucket_remaining = _get_bucket_remaining(pu_ctx, bucket)

    # 3b. Bucket overflow: if current bucket is empty, try to borrow from another
    if bucket_remaining < 0.001:
        # Find bucket with most remaining energy
        buckets_energy = {
            "primary": pu_ctx.bucket_primary_remaining_mj,
            "secondary": pu_ctx.bucket_secondary_remaining_mj,
            "exit": pu_ctx.bucket_exit_remaining_mj,
        }
        # Remove current bucket from candidates
        candidates = {k: v for k, v in buckets_energy.items() if k != bucket and v > 0.01}
        if candidates:
            overflow_bucket = max(candidates, key=candidates.get)
            bucket = overflow_bucket
            bucket_remaining = _get_bucket_remaining(pu_ctx, bucket)

    # 4. MGU-K Torque with bucket + SOC + priority constraints
    mguk_torque = 0.0
    battery_energy_mj = 0.0

    if bucket_remaining > 0 and pu_ctx.soc_mj > 0.01:
        # 4a. Dynamic cap with spread
        sections_left = _count_sections_left(pu_ctx, bucket, lap_progress)
        pu_ctx.bucket_sections_left = sections_left

        dynamic_cap_mj = bucket_remaining / max(sections_left, 1)

        # Apply spread_lower/upper (configurable, default 0.8/1.2)
        # In push mode, use upper spread for more aggressive deploy
        spread_lower = pu_ctx.bucket_section_spread_lower
        spread_upper = pu_ctx.bucket_section_spread_upper
        if pu_ctx.ers_push_mode:
            # Push mode: use upper spread (1.2x) for aggressive deploy
            pu_ctx.bucket_section_cap_mj = dynamic_cap_mj * spread_upper
        else:
            # Normal: use base cap (1.0x)
            pu_ctx.bucket_section_cap_mj = dynamic_cap_mj

        # 4b. Battery window: min of cap, SOC headroom, bucket remaining
        soc_headroom = max(
            pu_ctx.soc_mj - pu_ctx.soc_floor_dynamic_pct * pu_ctx.battery_capacity_mj,
            0.0
        )
        battery_window_mj = min(
            pu_ctx.bucket_section_cap_mj,
            soc_headroom,
            bucket_remaining
        )

        # 4c. Priority score threshold (V2 logic)
        priority_score = _estimate_section_priority(
            section_kind, section_length_m, drs_active, pu_ctx.ers_push_mode
        )
        threshold = pu_ctx.priority_score_threshold
        if pu_ctx.ers_push_mode:
            threshold = 0.32
        elif pu_ctx.ers_defense_mode:
            threshold = 0.42
        elif drs_active:
            threshold = 0.48

        # SOC deficit adjustment
        soc_pct = pu_ctx.soc_mj / pu_ctx.battery_capacity_mj
        soc_deficit = pu_ctx.soc_floor_dynamic_pct - soc_pct
        if soc_deficit > 0 and not pu_ctx.ers_push_mode:
            threshold += _clamp(soc_deficit * 1.2, 0.02, 0.2)

        # Deploy decision
        if priority_score >= threshold and (soc_pct > 0.12 or pu_ctx.ers_push_mode):
            # 4d. Compute MGU-K power from budget
            mguk_power_kw = min(pu_ctx.ers_output_kw, battery_window_mj * 1000.0 / dt_s)
            omega = rpm * 2.0 * math.pi / 60.0
            mguk_torque = mguk_power_kw * 1000.0 / max(omega, 1.0) if omega > 1.0 else 0.0

            # 4e. Thermal clipping
            thermal_eta = compute_thermal_eta(pu_ctx.ers_temp_c)
            mguk_torque *= thermal_eta

            # 4f. Consume bucket and SOC
            battery_energy_mj = mguk_power_kw * dt_s / 1000.0
            _consume_bucket(pu_ctx, bucket, battery_energy_mj)
            pu_ctx.soc_mj = max(0.0, pu_ctx.soc_mj - battery_energy_mj)
            pu_ctx.lap_deploy_mj += battery_energy_mj
    else:
        pu_ctx.bucket_sections_left = 0
        pu_ctx.bucket_section_cap_mj = 0.0

    # 5. MGU-H Direct Torque
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

    # 6. Harvesting (if braking)
    harvest_mj = 0.0
    if brake_pct > 5:
        harvest_mj = compute_mguk_harvest(pu_ctx, brake_pct, v_ms, dt_s)
        # Also MGU-H ES harvest (when not braking, throttle provides some)
    compute_mguh_es_harvest(pu_ctx, section_kind, throttle_pct, dt_s)

    # 7. Total torque
    total_torque = ice_torque + mguk_torque + mguh_torque

    # 8. Force at wheel
    f_engine = total_torque * gear_ratio * FINAL_DRIVE * DRIVETRAIN_EFFICIENCY / R_WHEEL

    # 9. Corner traction limit
    if is_corner:
        corner_factor = min(1.0, 1000.0 / max(radius_m, 100.0))
        f_engine *= corner_factor

    # 10. Driver skill
    f_engine *= driver_skill

    # 11. Energy trace
    pu_ctx.energy_trace.append({
        "dist_m": 0.0,  # Will be set by caller
        "rpm": round(rpm, 0),
        "ice_torque_nm": round(ice_torque, 1),
        "mguk_torque_nm": round(mguk_torque, 1),
        "mguh_torque_nm": round(mguh_torque, 1),
        "soc_mj": round(pu_ctx.soc_mj, 4),
        "deploy_mj": round(battery_energy_mj, 4),
        "mguh_direct_mj": round(mguh_energy_mj, 4),
        "harvest_mj": round(harvest_mj, 4),
        "bucket": bucket,
        "bucket_remaining_mj": round(_get_bucket_remaining(pu_ctx, bucket), 4),
        "ers_temp_c": round(pu_ctx.ers_temp_c, 1),
    })

    return f_engine


# ============================================================================
# Thermal Model (Phase 3 — stub for Phase 1)
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