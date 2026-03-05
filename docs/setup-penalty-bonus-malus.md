# Setup Penalty Bonus/Malus Specification
This document defines how circuit-specific setup data is converted into per-section penalties and limited bonuses (DF/drag) before updating the LapSimulator.

## 1. Objectives
1. Utilise existing circuit/teams data (`penalty_profile.json`, `setup_mapping_v2.json`, `team_offsets.json`) to derive ideal slider targets.
2. Apply penalties only on curve microsections when the setup deviates from those targets.
3. Introduce capped bonuses (negative penalties) for cars that exceed the circuit DF/drag targets while staying in the valid window, so aero developments are rewarded.

## 2. Data Sources
| Source | Purpose |
| --- | --- |
| `config/circuits/derived/<id>/penalty_profile.json` | Circuit stats (power_bias, straight length, `n_curve_sections`, future `setup_sensitivity`).
| `config/setup/setup_mapping_v2.json` | Range/step for each slider, cluster metrics (load class, corner density).
| `config/setup/setup_ranges/<id>.json` | Baseline slider targets per circuit.
| `config/setup/team_offsets.json` | Team/pilot offsets (DNA + preference).

Derived structures:
- `ideal_setup_circuit[field] = setup_ranges[circuit].target`
- `ideal_setup_team[field] = clamp(ideal_circuit + team_offset + driver_offset)`
- `circuit_coeffs = {df_curve_fast, df_curve_medium, df_curve_slow, drag_per_500m, caps}` – stored under a new `setup_penalty` block inside each `penalty_profile.json` when available.

## 3. Flow Overview
```
Setup sliders → map_slider_to_physics() → compare vs ideal_setup_team
                                        ↓
                              delta_slider[field]
                                        ↓
                        compute_setup_penalty(delta, circuit_coeffs)
```
- Only the LapSimulator consumes the penalty/bonus result (`setup_penalty_s` per section, aggregated per lap).
- UI/telemetry receives the breakdown via `PerformancePenalties.setup`.

## 4. Curve Penalty (malus)
- Apply **only** on micro-waypoints belonging to sections where `SectionKind ∈ CORNER_KINDS`.
- For each slider contributing to DF front/rear (front wing, rear wing, beam, ride heights, antiroll, suspensions), compute `delta = actual - ideal` (in slider points) and sign.
- Split into front vs rear components; convert slider delta to physical delta with existing SetupEngine formulas before weighting.
- Per microstep penalty:
  - Fast/Ultrafast curve: `0.030 s * |delta| * section_weight`
  - Medium curve: `0.020 s * |delta| * section_weight`
  - Slow/Very slow: `0.010 s * |delta| * section_weight`
  - `section_weight = dt_ref_micro / Σ dt_ref_curve`.
- Circuit caps (per lap):
  - High DF (Monaco, Budapest, Singapore): `cap_curve_penalty = +1.5 s`
  - Low drag (Monza, Jeddah, Baku): `cap_curve_penalty = +0.6 s`
  - Balanced circuits: `cap_curve_penalty = +1.0 s`

## 5. Curve Bonus (DF)
- Triggered when the physical DF exceeds the target (slider delta positive) but remains within the allowed window (no validation error).
- Per microstep bonus:
  - Fast/Ultrafast: `-0.007 s * delta_pos * section_weight`
  - Medium: `-0.005 s * delta_pos * section_weight`
  - Slow: `-0.003 s * delta_pos * section_weight`
- Lap caps:
  - High DF circuits: `cap_curve_bonus = -0.10 s`
  - Low drag circuits: `cap_curve_bonus = -0.05 s`

> Quotes are negative penalties; totals cannot exceed the cap.

## 6. Drag Penalty/Bonus (straights)
- Evaluate only on straight/medium-straight microsections.
- Compute equivalent straight length: `straight_weight = dist_step / 500m`.
- Penalty for slider above target (extra drag): `+0.004 s * delta_pos * straight_weight`.
- Bonus for slider below target (drag-efficient): `-0.003 s * delta_neg * straight_weight`.
- Lap caps:
  - Monza: `drag_penalty_cap +0.9 s`, `drag_bonus_cap -0.08 s`
  - Spa, Baku: `+0.8 s / -0.06 s`
  - Others: `+0.6 s / -0.04 s`

## 7. Aggregation & Storage
- For every section the LapSimulator stores:
  - `df_curve_penalty_s`
  - `df_curve_bonus_s`
  - `drag_penalty_s`
  - `drag_bonus_s`
  - `setup_penalty_s = clamp(sum, cap_total)`
- `PerformancePenalties.setup` keeps the lap cumulative values and exposes them to telemetry/UI.

## 8. Implementation Notes
1. Extend `penalty_profile.json` to include a `setup_penalty` block:
   ```json
   "setup_penalty": {
     "curve_caps": {"high_df": 1.5, "balanced": 1.0, "low_drag": 0.6},
     "curve_coeffs": {"fast": 0.030, "medium": 0.020, "slow": 0.010},
     "bonus_coeffs": {"fast": -0.007, "medium": -0.005, "slow": -0.003},
     "drag_coeff": 0.004,
     "drag_bonus_coeff": -0.003,
     "drag_caps": {"monza": {"penalty": 0.9, "bonus": -0.08}, ...}
   }
   ```
2. Add helper `compute_setup_bonus()` to the new module `setup_penalty.py` and integrate inside `update_section()`.
3. Tests: create fixtures for Monza/Monaco verifying penalties and bonuses respond to slider delta and honour caps.

## 9. References to Update
- `docs/penalty-overhaul-spec.md` → add subsection describing the setup factor (malus + bonus) referencing this spec.
- `docs/setup-engine-spec-v0.1.md` → mention that map_slider_to_physics now feeds the bonus/malus system and telemetry outputs negative penalties when hardware exceeds targets.

## 10. Open Questions / Next Steps
- Whether drag bonuses should also influence engine penalty (dirty air effect) or remain independent.
- Future integration with aero upgrade tree (auto-adjust ideal windows when new packages unlock).
