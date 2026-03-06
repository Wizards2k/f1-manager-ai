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
- **If OUTSIDE window**: Penalty for ANY deviation (symmetric): `+0.004 s * |delta| * straight_weight`.
- **If INSIDE window**: 
  - Bonus for slider below target (drag-efficient): `-0.004 s * delta_neg * straight_weight`.
  - Malus for slider above target (extra drag): `+0.004 s * delta_pos * straight_weight`.
- Lap caps:
  - Monza: `drag_penalty_cap +0.9 s`, `drag_bonus_cap -0.08 s`
  - Spa, Baku: `+0.8 s / -0.06 s`
  - Others: `+0.6 s / -0.04 s`

> **Trade-off Logic**: Creates realistic setup strategies where increasing wings gives curve bonuses but drag malus, and vice versa.

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
     "drag_bonus_coeff": -0.004,
     "drag_caps": {"monza": {"penalty": 0.9, "bonus": -0.08}, ...}
   }
   ```
2. **New module**: `setup_penalty_v2.py` with complete implementation:
   - `load_setup_ranges()` and `load_team_offsets()`
   - `build_ideal_setup()` with team/driver offsets
   - `compute_df_curve_penalty()` and `compute_drag_penalty()`
   - `clamp_penalties()` per circuit-specific caps
3. **Integration**: Modified `update_section()` to call penalty functions with `within_window` parameter
4. **Tests**: `scripts/test_setup_penalties.py` with Suzuka results showing realistic trade-offs

## 9. Implementation Results (Suzuka 2025)
| Setup | Time | Gap | Status |
|-------|------|-----|--------|
| Ideal (within window) | 88.256s | 0.000s | ✅ Baseline |
| Max DF (outside) | 89.818s | +1.562s | 🔴 Penalty |
| Min DF (outside) | 90.134s | +1.878s | 🔴 Penalty |
| Monaco (outside) | 88.817s | +0.561s | 🔴 Penalty |
| Monza (outside) | 88.873s | +0.617s | 🔴 Penalty |
| DF Bonus (within, DF>target) | 88.274s | +0.018s | ⚠️ Malus > Bonus |

**Key Insights**:
- Trade-off working: DF Bonus +0.018s (drag malus > curve bonus on Suzuka)
- Realistic magnitudes: 0.018s trade-off, +1.5s to +1.9s penalties
- Circuit-specific strategies: high-DF circuits favor curve bonuses, low-drag favor drag bonuses

## 9.1. Circuit-Specific Aero Reference Values

The system now uses **real telemetry data** to calculate circuit-specific DF and drag reference values based on `power_bias`:

| Power Bias | Circuit Type | DF Ref | Drag Ref | Logic |
|------------|--------------|--------|----------|-------|
| **< 0.63** | Technical circuits | 78-85 | 32-35 | Accept more drag for downforce |
| **> 0.65** | Power circuits | 65-70 | 25-28 | Prioritize speed over downforce |
| **0.63-0.65** | Balanced circuits | 74 | 30 | Compromise approach |

**Real Examples**:
- **Budapest** (power_bias=0.620): DF=78.5, Drag=32.3 (technical = accept drag)
- **Monza** (power_bias=0.660): DF=69.5, Drag=27.7 (power = want less drag)
- **Imola** (power_bias≈0.55): DF=85.0, Drag=35.0 (very technical = max DF/drag)

Values are calculated dynamically from telemetry data for all 24 circuits.

## 10. Files Modified
- `python_backend/lap_simulator/setup_penalty_v2.py` (NEW)
- `python_backend/lap_simulator/update_section.py` (integration)
- `python_backend/lap_simulator/data_types.py` (SectionResult fields)
- `python_backend/lap_simulator/lap_simulator.py` (CarEntry setup_sliders)
- `python_backend/utils/adapter.py` (racecar_to_car_entry)
- `scripts/test_setup_penalties.py` (comprehensive test suite)
- `config/setup/team_offsets.json` (JSON format fix)
- `scripts/generate_aero_references.py` (NEW - circuit-specific aero values)
- `config/circuits/derived/*/penalty_profile.json` (aero_reference values for all 24 circuits)

## 11. References to Update
- `docs/penalty-overhaul-spec.md` → add subsection describing the setup factor (malus + bonus) referencing this spec.
- `docs/setup-engine-spec-v0.1.md` → mention that map_slider_to_physics now feeds the bonus/malus system and telemetry outputs negative penalties when hardware exceeds targets.

## 12. Open Questions / Next Steps
- Whether drag bonuses should also influence engine penalty (dirty air effect) or remain independent.
- Future integration with aero upgrade tree (auto-adjust ideal windows when new packages unlock).
