---
title: Lap Physics Engine - Complete Analysis
date: 2026-04-02
version: v2.0
---

# Lap Physics Engine - Complete Technical Analysis

## Executive Summary

The lap time calculation is a **multi-stage penalty-based system** operating on per-section granularity. It follows a reference lap time (from telemetry) and applies **8 independent penalty/bonus systems** to derive the actual time.

**Core Equation (line 813 in update_section.py):**
```python
dt_s = max(dt_s + ref_dt * total_penalty + fuel_delta_s + tyre_delta_s + 
           push_delta_s + engine_delta_s + brake_delta_s + ers_bonus_s + 
           setup_penalty_s, 0.01)
```

---

## 1. Architecture Overview

### 1.1 Execution Flow (LapSimulator)

```
register_cars() 
    ↓
run_lap()
    ├─ For each section:
    │   ├─ update_section() → computes dt_s
    │   ├─ accumulates dt to car_state.lap_time_acc_s
    │   └─ collects SectionResult (penalties, speeds, events)
    ├─ Final sector tracking
    └─ Returns LapResult with lap_time_s = sum of all dt_s
```

**Key File:** [lap_simulator.py:220-356](python_backend/lap_simulator/lap_simulator.py#L220-L356)

---

## 2. Section Time Calculation - The 8 Steps

Each section time `dt_s` is computed through **8 sequential physics steps**:

### STEP 1: Input & Speed State
- **Location:** update_section.py:170-179
- **Purpose:** Establish baseline section speed from car's current state
- **Key Variables:**
  - `v_base`: section's natural speed from telemetry
  - `v_entry`: car's current speed entering section
  - **Correction:** If car speed > section entry speed, reset to entry (prevents ghosting)

### STEP 2: Driver Decision (Pilot Input)
- **Location:** driver_model.compute_inputs()
- **Purpose:** Compute driver's intentions based on skill, mental state, section type
- **Outputs:**
  - `driver_intent.pace_factor` - aggressiveness (0.92-1.08)
  - `driver_intent.throttle_pct` - pedal position
  - `driver_intent.brake_intensity` - braking force request

### STEP 3: Aero Forces
- **Location:** aero_package.compute_forces()
- **Purpose:** Calculate downforce and drag based on setup and speed
- **Key Physics:**
  - Downforce: `F_df = 0.5 * RHO * v² * CLA_REF`
  - Drag: `F_drag = 0.5 * RHO * v² * CDA_REF + rolling_resistance`
  - **DRS effect:** -20% drag (`CDA_REF *= 0.8`)
  - Handling penalty from aero imbalance

### STEP 4: Power Unit (ICE + ERS)
- **Location:** power_unit.generate_output()
- **Purpose:** Compute available power based on driver demand and fuel/ERS state
- **Outputs:**
  - `ice_power_kw` - internal combustion power
  - `ers_output_kw` - electric power deployment
  - Energy consumption tracking

### STEP 5: Tyres & Brakes
- **Location:** tyre_model.update_tyres() & brake_system.update_brakes()
- **Purpose:** Calculate grip availability and braking efficiency
- **Grip Model:**
  ```python
  mu = 1.6 * (grip_avg ** 2.0) * (1.0 - handling_penalty)
  ```
- **Braking:** Efficiency based on temperature, duct settings, degradation

### STEP 6: Pure Kinematics Integration ⭐ (The Core)
- **Location:** update_section.py:269-597
- **Purpose:** Integrate acceleration over section with realistic physics

#### Approach 1: HD Micro-Sector Integration (if waypoints available)
```python
for each waypoint:
    # Calculate forces
    F_drag = 0.5 * RHO * v² * CDA + rolling_resistance
    F_df = 0.5 * RHO * v² * CLA
    F_z = mass * g + F_df
    
    # Grip circle (traction limited)
    F_lat_max = F_z * mu
    F_drive_max_power = (power_kw * 1000) / v
    F_drive_max_grip = F_z * mu (or reduced if cornering)
    
    # Net force with throttle/brake
    F_net = (F_drive - F_drag) * throttle_pct - brake_limit * brake_pct
    
    # Kinematics
    a = F_net / mass
    v_new = sqrt(v² + 2 * a * dist_step)
    
    # Apply constraints
    if corner: v_new = min(v_new, v_apex_limit)
    v_new = blend(v_physics, v_telemetry_ref, 0.85/0.15)  # 85% physics, 15% telemetry
    
    # Time accumulation
    v_avg = (v + v_new) / 2
    dt_step = dist_step / v_avg
    t += dt_step
```

#### Approach 2: Macro Integration (if no waypoints)
```python
while distance < section.length:
    # Same physics calculation but with dt_step = 0.05s fixed time steps
    # Integration via simple Euler: v_new = v + a * dt_step
```

#### Key Physical Parameters (Calibrated for F1 2025)
- **Mass:** 798 kg + fuel (realistic)
- **Mechanical grip:** μ = 1.6 (baseline, degraded by wear)
- **Air density:** From environment context
- **Reference downforce:** Circuit-specific (Monaco 230, Monza 80)
- **CDA reference:** 1.10 m² (base) + aero setup scaling (×0.015)
- **CLA reference:** aero setup scaling (×0.020)

#### Exit Speed Capping
```python
v_exit_cap = v_telemetry * (0.97 + 0.06 * pace_factor)

# In corners: scale by car's aero advantage
if is_corner:
    speed_ratio = v_apex_calculated / v_min_telemetry
    speed_ratio = clamp(0.85, 1.15)  # ±15% max
    v_exit_cap *= speed_ratio

v_exit = min(v_physics, v_exit_cap)
```

### STEP 7: Internal State Update
- **Location:** update_mental_state()
- **Purpose:** Update driver fatigue, confidence, mental state
- **Inputs:** Section performance ratio, event severity

### STEP 8: Return
- **Location:** update_section.py:979-1049
- **Purpose:** Assemble SectionResult with all telemetry

---

## 3. Penalty/Bonus Systems (8 Independent Components)

After physics integration computes base `dt_s`, **8 penalty systems** adjust the time:

### 3.1 Fuel Penalty
```python
extra_fuel = max(0, current_fuel - reference_fuel)
fuel_delta_s = penalty_coeff * extra_fuel * section_fraction

# Example (Suzuka): 3.5e-5 coeff, 0.25 extra kg, 1/24 fraction ≈ +0.00037s per section
```
- **Reasoning:** Extra mass → extra drag
- **Applied on:** ALL sections
- **Scaling:** Per-section fraction based on circuit length

### 3.2 Tyre Penalty (3 components)
Applied **ONLY on curve sections** (line 620-694):

**a) Compound Penalty**
```python
compound_delta = config.tyre_compound_deltas[current_compound] * section_weight
# C1=+1.2s, C2=+0.55s, C3=0.0s (ref), C4=-0.5s, C5=-1.1s, C6=-1.55s per lap
# Distributed: /n_curves (e.g., Suzuka has 7 curves)
```

**b) Wear Penalty**
```python
# Nonlinear scaling
if wear <= 50%:  wear_penalty_lap = coeff * 0.5 * (wear/10)
else:            wear_penalty_lap = base + coeff * 0.5 * ((wear-50)/10) * 3.0

# Distributed by section weight
```

**c) Temperature Penalty**
```python
# Out of optimal window (e.g., 80-100-120°C for C3)
if temp < cold_limit:  penalty = (cold_limit - temp) * 0.0005
if temp > hot_limit:   penalty = (temp - hot_limit) * 0.0005 (or 0.001 if blistered)
```

### 3.3 Push Penalty
```python
push_delta_s = compute_push_penalty_per_section(
    push_level,        # 1-10 (10=zero penalty)
    driver_skills,     # pace, race_craft, consistency
    section_length,
    circuit_length,
    is_qualifying
)
# Increases non-linearly with push (push=1 is ~0.5s/lap penalty)
```

**Reasoning:** Lower push = safer, higher mental state  
**Applied on:** ALL sections, scales with circuit length

### 3.4 Engine Penalty (CV + Map)
```python
# CV penalty (20 CV = -0.2s on straights)
cv_delta = team_cv - mercedes_reference_cv  # MER=1018, RBR=1015, RB=995
cv_penalty = cv_delta * config.engine_penalty_coeff

# Map penalty (reference = QUALIFY)
map_penalty:
  QUALIFY: 0.0s (reference)
  RACE:    +0.18s per lap
  PRACTICE: +0.35s per lap
  SAFETY_CAR: +0.55s per lap

total_engine_penalty = cv_penalty + map_penalty
```

**Applied on:** STRAIGHT sections only (line 30-34)

### 3.5 Brake Penalty (Duct + Fade)
```python
# ONLY on sections with braking_energy >= 0.05 MJ

# Duct penalty
if duct_opening < min_open:
    penalty = (min_open - duct_opening) * 0.3  # Overheating
elif duct_opening > max_open:
    penalty = (duct_opening - max_open) * 0.2  # Drag

# Fade penalty (temperature-based)
fade_level = max((front_temp - threshold) / 15°C, 
                 (rear_temp - threshold) / 15°C)
fade_penalty = fade_level * 0.05  # base
if critical_section: fade_penalty *= 1.5  # multiplier

total_brake_penalty = duct_penalty + fade_penalty
```

### 3.6 Setup Penalty/Bonus (DF + Drag)
**Reference:** [docs/setup-penalty-bonus-malus.md](setup-penalty-bonus-malus.md)

#### DF Curve Penalty (ONLY on corners)
```python
# If OUTSIDE valid window: penalty for any deviation
penalty_coeff:
    fast/ultrafast_corner: 0.030 s per delta * section_weight
    medium_corner: 0.020 s per delta * section_weight
    slow_corner: 0.010 s per delta * section_weight

# Capped per lap by circuit (e.g., Monaco=1.5s, Monza=0.6s, others=1.0s)
```

#### DF Curve Bonus (ONLY if inside window AND DF > target)
```python
bonus_coeff:
    fast: -0.007 s per delta
    medium: -0.005 s per delta
    slow: -0.003 s per delta

# Capped (e.g., Monaco=-0.10s, Monza=-0.05s)
```

#### Drag Penalty/Bonus (ONLY on straights)
```python
straight_weight = section_length / 500m

# If OUTSIDE window: penalty
penalty = 0.004 s * |delta| * straight_weight

# If INSIDE window:
if drag < target: bonus = -0.004 s * delta_neg * straight_weight
if drag > target: malus = 0.004 s * delta_pos * straight_weight

# Capped per lap (Monza: ±0.9s/±0.08s, others: ±0.6s/±0.04s)
```

### 3.7 ERS Bonus (Negative = Time Gain)
```python
total_energy_deployed = battery_deploy_mj + mguh_direct_mj
ers_bonus = -total_energy_deployed * 0.125  # -0.125s per MJ

# Applied ONLY on straights
# Clamped to max 0.12s per section (avoid unrealistic single-section gain)

# Example: 4 MJ/lap over 8 straights = 0.5s/straight = ~0.5s bonus per lap
```

### 3.8 Baseline Delta (Aero/Grip Modulation)
```python
delta_penalty = clamp(
    k_aero_penalty * delta_aero + k_grip_penalty * delta_grip,
    -0.05, 0.30
)

# Applied as: ref_dt * total_penalty
# where total_penalty = baseline + delta_penalty
```

---

## 4. Final Time Assembly

**Line 813 - Core Calculation:**
```python
dt_s = max(
    dt_s  # Physics-based base time
    + ref_dt * total_penalty  # Baseline + aero/grip modulation
    + fuel_delta_s  # +0.00037s per 0.25kg extra
    + tyre_delta_s  # Up to +0.5s/lap (wear/temp/compound)
    + push_delta_s  # Up to +0.5s/lap (push=1)
    + engine_delta_s  # Up to +0.18s/lap (race map) + CV delta
    + brake_delta_s  # Up to +0.5s/lap (bad setup)
    + ers_bonus_s  # Up to -0.5s/lap (full deployment)
    + setup_penalty_s,  # Up to ±1.5s/lap
    0.01  # Minimum time per section
)

car_state.lap_time_acc_s += dt_s
```

**Lap Time = Σ(dt_s) for all sections**

---

## 5. Example Lap Time Calculation (Suzuka)

### Reference Baseline (Optimal Setup)
```
Circuit: Suzuka (5.807 km, 18 sections, 7 curves)
Telemetry reference lap: 88.256s

Break-down by section type:
- Straights (5 sec): ~15.2s
- Slow corners (4 sec): ~24.1s
- Medium corners (6 sec): ~38.2s
- Fast corners (3 sec): ~10.8s
```

### Penalties Applied (Suboptimal Setup)
```
Fuel penalty: +0.1s (60kg vs 50kg reference)
Tyre penalty: +0.3s (C2 compound, 30% wear, 105°C on C3 window)
Push penalty: +0.2s (push=8 on difficult sections)
Engine penalty: +0.08s (RBR vs MER reference, race map)
Brake penalty: +0.15s (duct too open)
Setup penalty: +0.25s (DF too low for Suzuka, drag too high)
ERS bonus: -0.15s (full deployment on straights)

Total penalties: +0.84s
Final lap time: 88.256 + 0.84 = 89.10s
```

---

## 6. Key Calibration Points

### Physics Constants (F1 2025)
| Parameter | Value | Source |
|-----------|-------|--------|
| Dry mass | 798 kg | Technical regulations |
| Mechanical grip (baseline) | μ = 1.6 | Calibrated vs telemetry |
| Air density | Context-dependent | Environment |
| Rolling resistance | 0.015 × F_z | F1 baseline |
| DRS drag reduction | -20% | Spec |
| Reference DF (circuit-based) | 65-85 units | Telemetry analysis |

### Penalty Coefficients
| System | Coefficient | Per Unit |
|--------|-------------|----------|
| Fuel | 3.5e-5 s/kg | Per section |
| Tyre wear | 0.12 × 0.5 | Per 10% wear, curve sections |
| Engine CV | -0.01 s/CV | Straight sections only |
| Engine map (RACE) | +0.18 s | Per lap |
| Brake duct | 0.3s per unit (close) | Per section |
| Brake fade | 0.05 s/fade_unit | Base |
| Push level | ~0.05s per push level | Nonlinear |
| ERS energy | -0.125 s/MJ | Straight sections |

### Circuit-Specific Reference Values
```json
{
  "Monza": {"df_ref": 69.5, "drag_ref": 27.7},
  "Suzuka": {"df_ref": 65.0, "drag_ref": 25.0},
  "Monaco": {"df_ref": 78.5, "drag_ref": 32.3},
  "Spa": {"df_ref": 72.0, "drag_ref": 28.5}
}
```

---

## 7. Important Implementation Details

### 7.1 Telemetry Blending (Waypoint Mode)
The system uses a **soft constraint** to telemetry, not a hard cap:
```python
v_reference = waypoint.v_ref_kph
v_target = v_reference * pace_factor
v_physics_only = sqrt(v² + 2*a*dist)

v_new = (v_physics_only * 0.85) + (v_target * 0.15)
# 85% from physics, 15% from telemetry reference
```

**Why 85/15?** Allows setup/driver differences to emerge while preventing unrealistic divergence.

### 7.2 Corner Speed Calculation
For each corner, the system calculates a physically realistic apex speed:

```python
# From force balance at corner
v_apex_limit = sqrt((mu * mass * 9.81) / denominator)

where:
denominator = (mass / radius) - (0.5 * mu * RHO * CLA_REF)

# Applied with driver pace_factor (0.92-1.08)
v_apex_limit *= driver_intent.pace_factor

# Compare vs telemetry minimum for validation
# Use stricter of the two
```

### 7.3 Penalty Cache (Optional)
If `ENABLE_PENALTY_CACHE=True`, pre-computed values avoid recalculation:
- Section fraction (fuel penalty distribution)
- Section weight (tyre penalty distribution)
- Section kind (curve vs straight detection)

### 7.4 Multiple Session Types
The engine supports 3 session phases with different engine map penalties:

| Session | Engine Map | Penalty |
|---------|-----------|---------|
| Qualifying | QUALIFY | 0.0s |
| Race | RACE | +0.18s per lap |
| Practice | PRACTICE | +0.35s per lap |
| Safety Car | SC | +0.55s per lap |

---

## 8. Debug Logging

### Enable Penalty Logging
```bash
export DEBUG_PENALTIES=1
export PENALTY_LOG_DRIVER_IDS="CAR_001,CAR_002"
python -m routes.api
```

Output format:
```
[PEN] car=CAR_001 sec=sec_08 push=8.0 map=RACE ... 
[PEN] engine_result sec=sec_08 cv=1015.0 cv_delta=+7.0 cv_penalty=+0.070s
```

### Enable Lap Time Logging
```bash
export LAP_DEBUG_ENABLED=1
python -m routes.api
```

Logs to `logs/lap_times_debug.log` with per-section breakdown.

---

## 9. Design Philosophy

### 1. **Reference-Based Penalties**
All penalties are applied as **deltas to telemetry**, not absolute calculations. This:
- Anchors to real-world lap times
- Allows setup/driver differences to be meaningful
- Prevents unrealistic extremes

### 2. **Modular Penalty System**
8 independent penalty systems that:
- Can be enabled/disabled via flags
- Have independent calibration
- Don't interact (additive model)
- Are logged separately for debugging

### 3. **Physics-First with Telemetry Guardrails**
- Kinematic integration is physically realistic
- Exit speeds are validated against telemetry
- Blending 85% physics + 15% telemetry reference

### 4. **Circuit-Aware Coefficients**
- Different penalty caps per circuit (high-DF vs low-drag)
- Setup sensitivity varies by power_bias
- Corner speed categories (fast/medium/slow)

---

## 10. Future Improvements

### Potential Enhancements
1. **Aero Upgrade Tree Integration** - auto-adjust setup penalties when new packages unlock
2. **Wear-Based Brake Penalties** - brake material degradation over stint
3. **Weather Aerodynamics** - rain reduces effective DF/drag scaling
4. **Driver Fatigue** - mental state affects maximum achievable push
5. **Fuel Consumption Modeling** - dynamic fuel burn based on throttle/speed profile
6. **Setup Optimization AI** - suggest slider positions to minimize penalties

---

## Appendix: File Cross-Reference

| File | Purpose |
|------|---------|
| [lap_simulator.py](python_backend/lap_simulator/lap_simulator.py) | Main loop orchestrator |
| [update_section.py](python_backend/lap_simulator/update_section.py) | **Core physics engine** (8 steps) |
| [engine_penalty.py](python_backend/lap_simulator/engine_penalty.py) | CV + map penalties |
| [brake_penalty.py](python_backend/lap_simulator/brake_penalty.py) | Duct + fade penalties |
| [setup_penalty_v2.py](python_backend/lap_simulator/setup_penalty_v2.py) | DF/drag penalties |
| [brake_system.py](python_backend/lap_simulator/brake_system.py) | Braking physics |
| [tyre_model.py](python_backend/lap_simulator/tyre_model.py) | Grip calculation |
| [aero_package.py](python_backend/lap_simulator/aero_package.py) | Downforce/drag |
| [power_unit.py](python_backend/lap_simulator/power_unit.py) | ICE + ERS system |
| [driver_model.py](python_backend/lap_simulator/driver_model.py) | Driver inputs |

---

**Last Updated:** 2026-04-02  
**Status:** Production Ready (Wave 2 complete, ERS/Engine/Brake/Setup penalties integrated)
