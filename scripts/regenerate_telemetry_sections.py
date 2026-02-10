#!/usr/bin/env python3
"""
Regenerate circuit sections from raw telemetry points.

Produces v2 sections with:
- 100% circuit coverage (no gaps)
- Natural boundaries (brake start, apex, acceleration end)
- Real avg_speed, dt_ref, braking_energy, DRS, radius

Reference: docs/telemetry-sections-v2-spec.md
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants / thresholds
# ---------------------------------------------------------------------------

BRAKE_THRESHOLD = 5.0          # % brake pressure to count as braking
THROTTLE_LOW = 20.0            # below = coasting / braking
THROTTLE_HIGH = 80.0           # above = full acceleration
MIN_SECTION_LENGTH_M = 30.0    # merge sections shorter than this
MIN_SPEED_DROP_PCT = 0.15      # v_min/v_max < 0.85 → corner
CAR_MASS_KG = 798.0            # F1 2024 minimum weight
SMOOTHING_WINDOW = 5           # points for speed smoothing
DRS_ACTIVE_VALUES = {10, 12, 14}  # FastF1 DRS active codes

# Section kind thresholds (aligned with derive_setup_clusters.py)
# v_slow: < 80 kph   (chicane strette, Monaco hairpin)
# low:    80-130 kph  (hairpin, chicane)
# medium: 130-200 kph (curve a media velocità)
# high:   200-270 kph (curve ad alta velocità)
# ultra:  >= 270 kph  (flat-out, quasi rettifilo)
VSLOW_CORNER_MAX_KPH = 80.0
SLOW_CORNER_MAX_KPH = 130.0
MEDIUM_CORNER_MAX_KPH = 200.0
FAST_CORNER_MAX_KPH = 270.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TelemetryPoint:
    idx: int
    distance: float
    speed: float
    timestamp: float
    throttle: float
    brake: float
    gear: int
    drs: int
    x: float
    y: float
    # derived
    speed_smooth: float = 0.0


@dataclass
class BrakeEvent:
    """A contiguous zone where the car is braking or coasting before apex."""
    start_idx: int
    end_idx: int
    apex_idx: int = -1
    apex_speed: float = 0.0
    entry_speed: float = 0.0


@dataclass
class SectionV2:
    section_id: str = ""
    name: str = ""
    kind: str = "Straight"
    start_m: float = 0.0
    end_m: float = 0.0
    length_m: float = 0.0
    corner_number: int = 0

    v_entry_kph: float = 0.0
    v_exit_kph: float = 0.0
    v_min_kph: float = 0.0
    v_max_kph: float = 0.0
    avg_speed_kph: float = 0.0
    dt_ref_s: float = 0.0

    braking_energy_mj: float = 0.0
    drs_active: bool = False
    radius_m: Optional[float] = None

    heat_factor: float = 1.0
    cool_factor: float = 1.0
    bumpiness_factor: float = 0.0
    kerb_severity: float = 0.0

    point_start_idx: int = 0
    point_end_idx: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.section_id,
            "name": self.name,
            "kind": self.kind,
            "start_m": round(self.start_m, 1),
            "end_m": round(self.end_m, 1),
            "length_m": round(self.length_m, 1),
            "corner_number": self.corner_number,
            "v_entry_kph": round(self.v_entry_kph, 1),
            "v_exit_kph": round(self.v_exit_kph, 1),
            "v_min_kph": round(self.v_min_kph, 1),
            "v_max_kph": round(self.v_max_kph, 1),
            "avg_speed": round(self.avg_speed_kph, 1),
            "dt_ref_s": round(self.dt_ref_s, 4),
            "braking_energy_mj": round(self.braking_energy_mj, 3),
            "drs_active": self.drs_active,
            "radius_m": round(self.radius_m, 1) if self.radius_m else None,
            "heat_factor": round(self.heat_factor, 2),
            "cool_factor": round(self.cool_factor, 2),
            "bumpiness_factor": self.bumpiness_factor,
            "kerb_severity": self.kerb_severity,
            "telemetry_point_start_idx": self.point_start_idx,
            "telemetry_point_end_idx": self.point_end_idx,
        }


# ---------------------------------------------------------------------------
# Step 1: Load and smooth telemetry
# ---------------------------------------------------------------------------

def load_points(telemetry_data: Dict[str, Any], circuit_length: float) -> List[TelemetryPoint]:
    raw = telemetry_data["reference_lap"]["telemetry_points"]
    # Sort by distance (original, monotonically increasing even past circuit_length)
    sorted_raw = sorted(raw, key=lambda x: x["distance"])
    points = []
    for i, p in enumerate(sorted_raw):
        dist = max(0.0, p["distance"])
        points.append(TelemetryPoint(
            idx=i,
            distance=dist,
            speed=p["speed"],
            timestamp=p["timestamp"],
            throttle=p.get("throttle", 0),
            brake=p.get("brake", 0),
            gear=int(p.get("gear", 0)),
            drs=int(p.get("drs", 0)),
            x=p.get("x", 0),
            y=p.get("y", 0),
        ))

    # Smooth speed
    n = len(points)
    hw = SMOOTHING_WINDOW // 2
    for i in range(n):
        lo = max(0, i - hw)
        hi = min(n, i + hw + 1)
        points[i].speed_smooth = sum(p.speed for p in points[lo:hi]) / (hi - lo)

    return points


# ---------------------------------------------------------------------------
# Step 2: Detect brake events and apexes
# ---------------------------------------------------------------------------

def detect_brake_events(points: List[TelemetryPoint]) -> List[BrakeEvent]:
    """Find contiguous zones where car is braking or decelerating."""
    events: List[BrakeEvent] = []
    n = len(points)
    i = 0

    while i < n:
        # Look for start of braking zone
        if points[i].brake > BRAKE_THRESHOLD or (
            points[i].throttle < THROTTLE_LOW and i > 0 and
            points[i].speed_smooth < points[max(0, i-1)].speed_smooth - 2
        ):
            start = i
            # Find end of braking zone: where throttle recovers
            j = i + 1
            while j < n and (
                points[j].brake > BRAKE_THRESHOLD or
                points[j].throttle < THROTTLE_HIGH
            ):
                j += 1
                # Safety: don't let a single brake event span more than 40% of circuit
                if j < n and (points[j].distance - points[start].distance) > (
                    points[-1].distance * 0.4
                ):
                    break

            end = min(j, n - 1)

            # Find apex (minimum speed) in this zone
            apex_idx = start
            apex_speed = points[start].speed_smooth
            for k in range(start, end + 1):
                if k < n and points[k].speed_smooth < apex_speed:
                    apex_speed = points[k].speed_smooth
                    apex_idx = k

            entry_speed = points[start].speed_smooth

            # Only count as brake event if speed drops significantly
            if entry_speed > 0 and (entry_speed - apex_speed) / entry_speed > 0.10:
                events.append(BrakeEvent(
                    start_idx=start,
                    end_idx=end,
                    apex_idx=apex_idx,
                    apex_speed=apex_speed,
                    entry_speed=entry_speed,
                ))

            i = end + 1
        else:
            i += 1

    return events


# ---------------------------------------------------------------------------
# Step 3: Define section boundaries
# ---------------------------------------------------------------------------

def define_sections(
    points: List[TelemetryPoint],
    brake_events: List[BrakeEvent],
    circuit_length: float,
) -> List[SectionV2]:
    """
    Create sections from brake events.

    Strategy: each brake event defines a "corner section" (from brake start
    to throttle recovery). Everything between two corner sections is a
    "straight section".
    """
    sections: List[SectionV2] = []
    n = len(points)
    corner_num = 0

    # Sort brake events by start distance
    brake_events = sorted(brake_events, key=lambda e: points[e.start_idx].distance)

    prev_end_idx = 0  # index of the first point of the next section

    for be_i, be in enumerate(brake_events):
        brake_start_idx = be.start_idx
        brake_end_idx = be.end_idx

        # --- Straight section before this brake event ---
        if brake_start_idx > prev_end_idx:
            sections.append(_build_section(
                points, prev_end_idx, brake_start_idx,
                kind_hint="Straight", corner_number=0,
            ))

        # --- Corner section (brake + apex + acceleration) ---
        corner_num += 1
        sections.append(_build_section(
            points, brake_start_idx, brake_end_idx,
            kind_hint="Corner", corner_number=corner_num,
        ))

        prev_end_idx = brake_end_idx

    # --- Final straight (from last brake event to end of circuit) ---
    if prev_end_idx < n - 1:
        sections.append(_build_section(
            points, prev_end_idx, n - 1,
            kind_hint="Straight", corner_number=0,
        ))

    # Normalize section boundaries to [0, circuit_length]
    # Telemetry points may extend beyond circuit_length (wrap-around),
    # so we scale proportionally: raw_range → [0, circuit_length]
    if sections:
        raw_start = sections[0].start_m
        raw_end = sections[-1].end_m
        raw_total = raw_end - raw_start

        if raw_total > 0 and abs(raw_total - circuit_length) > 1.0:
            scale = circuit_length / raw_total
            for s in sections:
                s.start_m = (s.start_m - raw_start) * scale
                s.end_m = (s.end_m - raw_start) * scale
        else:
            # Already fits, just shift to start at 0
            offset = raw_start
            for s in sections:
                s.start_m -= offset
                s.end_m -= offset

        # Ensure exact boundaries
        sections[0].start_m = 0.0
        sections[-1].end_m = circuit_length

        # Ensure contiguous
        for i in range(1, len(sections)):
            sections[i].start_m = sections[i - 1].end_m

        # Recalculate lengths
        for s in sections:
            s.length_m = s.end_m - s.start_m

        # Remove degenerate sections
        sections = [s for s in sections if s.length_m > 1.0]

        if sections:
            sections[-1].end_m = circuit_length
            sections[-1].length_m = sections[-1].end_m - sections[-1].start_m

    # Merge tiny sections
    sections = _merge_tiny_sections(sections, points, MIN_SECTION_LENGTH_M)

    # Assign IDs and names
    corner_counter = 0
    straight_counter = 0
    for i, s in enumerate(sections):
        if "Corner" in s.kind:
            corner_counter += 1
            s.corner_number = corner_counter
            s.section_id = f"sec_{i+1:02d}"
            s.name = f"Turn {corner_counter}"
        else:
            straight_counter += 1
            s.section_id = f"sec_{i+1:02d}"
            s.name = f"Straight {straight_counter}"

    return sections


def _build_section(
    points: List[TelemetryPoint],
    start_idx: int,
    end_idx: int,
    kind_hint: str = "Straight",
    corner_number: int = 0,
) -> SectionV2:
    """Build a section from a range of telemetry points."""
    start_idx = max(0, start_idx)
    end_idx = min(len(points) - 1, end_idx)

    pts = points[start_idx:end_idx + 1]
    if not pts:
        return SectionV2()

    start_m = pts[0].distance
    end_m = pts[-1].distance
    length_m = max(end_m - start_m, 0.1)

    speeds = [p.speed for p in pts]
    v_min = min(speeds)
    v_max = max(speeds)
    v_entry = pts[0].speed
    v_exit = pts[-1].speed

    # Weighted average speed (by distance)
    total_weight = 0.0
    weighted_speed = 0.0
    for i in range(len(pts) - 1):
        ds = pts[i + 1].distance - pts[i].distance
        if ds > 0:
            avg_v = (pts[i].speed + pts[i + 1].speed) / 2.0
            weighted_speed += avg_v * ds
            total_weight += ds
    avg_speed = weighted_speed / max(total_weight, 0.01)

    # dt_ref by integration
    dt_ref = 0.0
    for i in range(len(pts) - 1):
        ds = pts[i + 1].distance - pts[i].distance
        if ds > 0:
            v_avg_ms = ((pts[i].speed + pts[i + 1].speed) / 2.0) / 3.6
            if v_avg_ms > 0.5:
                dt_ref += ds / v_avg_ms

    # Braking energy: ΔKE from entry to min speed
    v_entry_ms = v_entry / 3.6
    v_min_ms = v_min / 3.6
    braking_energy = 0.0
    if v_entry_ms > v_min_ms:
        braking_energy = 0.5 * CAR_MASS_KG * (v_entry_ms**2 - v_min_ms**2) / 1e6

    # DRS
    drs_active = any(p.drs in DRS_ACTIVE_VALUES for p in pts)

    # Radius (circle fit on curve points)
    radius = _compute_radius(pts) if kind_hint == "Corner" else None

    # Classify
    kind = _classify_section(v_min, v_max, v_entry, v_exit, pts, kind_hint)

    # Heat/cool factors
    heat_factor, cool_factor = _heat_cool_factors(kind)

    return SectionV2(
        kind=kind,
        start_m=start_m,
        end_m=end_m,
        length_m=length_m,
        corner_number=corner_number,
        v_entry_kph=v_entry,
        v_exit_kph=v_exit,
        v_min_kph=v_min,
        v_max_kph=v_max,
        avg_speed_kph=avg_speed,
        dt_ref_s=dt_ref,
        braking_energy_mj=braking_energy,
        drs_active=drs_active,
        radius_m=radius,
        heat_factor=heat_factor,
        cool_factor=cool_factor,
        point_start_idx=start_idx,
        point_end_idx=end_idx,
    )


def _classify_section(
    v_min: float, v_max: float,
    v_entry: float, v_exit: float,
    pts: List[TelemetryPoint],
    kind_hint: str,
) -> str:
    """Classify section using 5-tier system from derive_setup_clusters.py.

    Corners: VerySlowCorner / SlowCorner / MediumCorner / FastCorner / UltraFastCorner
    Straights: Straight / MediumStraight
    """
    if kind_hint == "Straight":
        speed_ratio = v_min / max(v_max, 1)
        if speed_ratio > 0.80:
            return "Straight"
        return "MediumStraight"

    # Corner classification by apex speed (v_min)
    if v_min < VSLOW_CORNER_MAX_KPH:
        return "VerySlowCorner"
    elif v_min < SLOW_CORNER_MAX_KPH:
        return "SlowCorner"
    elif v_min < MEDIUM_CORNER_MAX_KPH:
        return "MediumCorner"
    elif v_min < FAST_CORNER_MAX_KPH:
        return "FastCorner"
    else:
        return "UltraFastCorner"


def _heat_cool_factors(kind: str) -> Tuple[float, float]:
    """Return (heat_factor, cool_factor) per section kind."""
    table = {
        "Straight":         (0.2, 1.2),
        "MediumStraight":   (0.4, 1.0),
        "VerySlowCorner":   (1.5, 0.3),
        "SlowCorner":       (1.3, 0.4),
        "MediumCorner":     (1.0, 0.6),
        "FastCorner":       (0.8, 0.8),
        "UltraFastCorner":  (0.5, 1.0),
    }
    return table.get(kind, (1.0, 1.0))


def _compute_radius(pts: List[TelemetryPoint]) -> Optional[float]:
    """Compute approximate curve radius from x,y coordinates using circle fit."""
    coords = [(p.x, p.y) for p in pts if p.x != 0 or p.y != 0]
    if len(coords) < 3:
        return None

    # Use three-point circle method on start, middle, end
    p1 = coords[0]
    p2 = coords[len(coords) // 2]
    p3 = coords[-1]

    ax, ay = p1
    bx, by = p2
    cx, cy = p3

    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-10:
        return None

    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d

    radius = math.sqrt((ax - ux)**2 + (ay - uy)**2)

    if radius > 5000:
        return None  # effectively straight

    return radius


def _merge_tiny_sections(
    sections: List[SectionV2],
    points: List[TelemetryPoint],
    min_length: float,
) -> List[SectionV2]:
    """Merge sections shorter than min_length into their neighbors."""
    if not sections:
        return sections

    merged: List[SectionV2] = [sections[0]]
    for i in range(1, len(sections)):
        s = sections[i]
        if s.length_m < min_length and merged:
            # Merge into previous section
            prev = merged[-1]
            prev.end_m = s.end_m
            prev.length_m = prev.end_m - prev.start_m
            prev.v_exit_kph = s.v_exit_kph
            prev.v_max_kph = max(prev.v_max_kph, s.v_max_kph)
            prev.v_min_kph = min(prev.v_min_kph, s.v_min_kph)
            prev.dt_ref_s += s.dt_ref_s
            prev.braking_energy_mj += s.braking_energy_mj
            prev.drs_active = prev.drs_active or s.drs_active
            prev.point_end_idx = s.point_end_idx
            # Recalculate avg_speed
            if prev.dt_ref_s > 0:
                prev.avg_speed_kph = (prev.length_m / prev.dt_ref_s) * 3.6
        else:
            merged.append(s)

    return merged


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_sections(
    sections: List[SectionV2],
    circuit_length: float,
    lap_time: float,
) -> List[str]:
    """Validate sections against constraints from spec §4.2."""
    errors: List[str] = []

    if not sections:
        errors.append("No sections generated")
        return errors

    # 1. Total coverage
    total_length = sum(s.length_m for s in sections)
    if abs(total_length - circuit_length) > 5.0:
        errors.append(f"Coverage gap: Σlength={total_length:.1f}m vs circuit={circuit_length:.1f}m (delta={total_length-circuit_length:.1f}m)")

    # 2. Total dt_ref
    total_dt = sum(s.dt_ref_s for s in sections)
    if abs(total_dt - lap_time) > 1.0:
        errors.append(f"Time gap: Σdt_ref={total_dt:.3f}s vs lap_time={lap_time:.3f}s (delta={total_dt-lap_time:.3f}s)")

    # 3. No gaps
    for i in range(1, len(sections)):
        gap = sections[i].start_m - sections[i-1].end_m
        if abs(gap) > 1.0:
            errors.append(f"Gap between sec {i} and {i+1}: {gap:.1f}m")

    # 4. Speed continuity
    for i in range(1, len(sections)):
        delta_v = abs(sections[i].v_entry_kph - sections[i-1].v_exit_kph)
        if delta_v > 15:
            errors.append(f"Speed discontinuity sec {i}-{i+1}: {delta_v:.1f} kph")

    # 5. Corner v_min < v_entry and v_min < v_exit
    for s in sections:
        if "Corner" in s.kind:
            if s.v_min_kph > s.v_entry_kph + 5:
                errors.append(f"{s.name}: v_min ({s.v_min_kph:.0f}) > v_entry ({s.v_entry_kph:.0f})")

    # 6. Section lengths positive
    for s in sections:
        if s.length_m <= 0:
            errors.append(f"{s.name}: non-positive length {s.length_m:.1f}m")

    return errors


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def regenerate_sections(telemetry_data: Dict[str, Any]) -> Tuple[List[SectionV2], List[str]]:
    """Full pipeline: load → detect → define → validate."""
    circuit_length = telemetry_data["geometry"]["circuit_length"]
    lap_time = telemetry_data["reference_lap"]["lap_time"]

    points = load_points(telemetry_data, circuit_length)
    brake_events = detect_brake_events(points)
    sections = define_sections(points, brake_events, circuit_length)
    errors = validate_sections(sections, circuit_length, lap_time)

    return sections, errors


def apply_to_telemetry(
    telemetry_data: Dict[str, Any],
    sections: List[SectionV2],
) -> Dict[str, Any]:
    """Replace geometry.sections in telemetry data with v2 sections."""
    telemetry_data["geometry"]["sections"] = [s.to_dict() for s in sections]
    telemetry_data["geometry"]["sections_version"] = "v2"
    return telemetry_data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--circuit-id", help="Single circuit ID (e.g. it-1922_monza)")
    parser.add_argument("--all", action="store_true", help="Regenerate all circuits")
    parser.add_argument("--validate", action="store_true", help="Validate only, don't write")
    parser.add_argument("--dry-run", action="store_true", help="Show output without writing")
    parser.add_argument("--data-dir", default="python_backend/data/circuits",
                        help="Directory containing Telemetry JSON files")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    if args.circuit_id:
        files = [data_dir / f"{args.circuit_id}_Telemetry.json"]
    elif args.all:
        files = sorted(data_dir.glob("*_Telemetry.json"))
    else:
        parser.error("Specify --circuit-id or --all")
        return

    total_ok = 0
    total_err = 0

    for fpath in files:
        if not fpath.exists():
            print(f"❌ File not found: {fpath}")
            total_err += 1
            continue

        cid = fpath.stem.replace("_Telemetry", "")
        telem = json.loads(fpath.read_text())

        sections, errors = regenerate_sections(telem)

        # Summary
        total_length = sum(s.length_m for s in sections)
        total_dt = sum(s.dt_ref_s for s in sections)
        circuit_length = telem["geometry"]["circuit_length"]
        lap_time = telem["reference_lap"]["lap_time"]
        n_corners = sum(1 for s in sections if "Corner" in s.kind)
        n_straights = sum(1 for s in sections if "Straight" in s.kind or "MediumStraight" in s.kind)

        status = "✅" if not errors else "⚠️"
        print(f"\n{status} {cid}: {len(sections)} sections ({n_corners} corners, {n_straights} straights)")
        print(f"   Coverage: {total_length:.1f}m / {circuit_length:.1f}m ({total_length/circuit_length*100:.1f}%)")
        print(f"   Time:     {total_dt:.3f}s / {lap_time:.3f}s (delta={total_dt-lap_time:+.3f}s)")

        if errors:
            for e in errors:
                print(f"   ⚠️  {e}")
            total_err += 1
        else:
            total_ok += 1

        # Print sections
        print(f"\n   {'#':>2} {'Name':25s} {'Kind':14s} {'Start':>7s} {'End':>7s} {'Len':>6s} {'v_avg':>6s} {'v_min':>6s} {'v_max':>6s} {'dt_ref':>7s} {'brake_E':>8s} {'DRS':>4s} {'R':>6s}")
        print(f"   {'-'*115}")
        for i, s in enumerate(sections):
            r_str = f"{s.radius_m:.0f}" if s.radius_m else "-"
            drs_str = "DRS" if s.drs_active else ""
            print(f"   {i+1:2d} {s.name:25s} {s.kind:14s} {s.start_m:7.1f} {s.end_m:7.1f} {s.length_m:6.1f} {s.avg_speed_kph:6.1f} {s.v_min_kph:6.1f} {s.v_max_kph:6.1f} {s.dt_ref_s:7.3f} {s.braking_energy_mj:7.3f}  {drs_str:>3s} {r_str:>6s}")

        # Write
        if not args.validate and not args.dry_run and not errors:
            telem = apply_to_telemetry(telem, sections)
            fpath.write_text(json.dumps(telem, indent=2, ensure_ascii=False))
            print(f"   💾 Written to {fpath.name}")

    print(f"\n{'='*60}")
    print(f"Results: {total_ok} OK, {total_err} errors, {len(files)} total")


if __name__ == "__main__":
    main()
