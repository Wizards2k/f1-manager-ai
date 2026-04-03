---
title: Lap Physics Engine - Flow Diagrams
date: 2026-04-02
---

# Lap Physics Engine - Visual Flow Diagrams

## 1. Section Time Calculation - High Level

```
┌─────────────────────────────────────────────────────────────────┐
│                      update_section()                          │
│               (Computes time for ONE section)                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────────┐
         │  STEP 1-5: PRELIMINARY CALCULATIONS    │
         │  - Driver intent                       │
         │  - Aero forces (DF/Drag)              │
         │  - Power output (ICE+ERS)             │
         │  - Grip & braking efficiency          │
         └────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────────┐
         │  STEP 6: KINEMATICS INTEGRATION ⭐    │
         │  - Iterate over distance/waypoints    │
         │  - Apply forces (drag, throttle, etc) │
         │  - Calculate v_new, accumulate time   │
         │  Result: dt_s (physics-based time)    │
         └────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────────┐
         │   STEP 7: INTERNAL STATE UPDATE        │
         │   - Driver mental state                │
         │   - Tyre aging                         │
         └────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────────────────────────┐
         │        APPLY 8 PENALTY/BONUS SYSTEMS                   │
         │  ┌─────────────────────────────────────────────────┐   │
         │  │ 1. Fuel Penalty                                │   │
         │  │ 2. Tyre Penalty (compound/wear/temp)           │   │
         │  │ 3. Push Penalty (aggressive driving)           │   │
         │  │ 4. Engine Penalty (CV + map)                   │   │
         │  │ 5. Brake Penalty (duct + fade)                 │   │
         │  │ 6. Setup Penalty/Bonus (DF + drag)             │   │
         │  │ 7. ERS Bonus (energy deployment)               │   │
         │  │ 8. Baseline Modifier (aero/grip delta)         │   │
         │  └─────────────────────────────────────────────────┘   │
         └────────────────────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────────┐
         │   FINAL ASSEMBLY:                      │
         │   dt_final = max(                      │
         │     dt_s + penalties + bonuses,        │
         │     0.01s minimum                      │
         │   )                                    │
         └────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────────┐
         │   STEP 8: RETURN SectionResult         │
         │   - dt_s, v_exit, v_effective          │
         │   - All penalty breakdowns             │
         │   - Events (overtake, incidents)       │
         └────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────────┐
         │   car_state.lap_time_acc_s += dt_s     │
         │   (Accumulate to lap total)            │
         └────────────────────────────────────────┘
```

---

## 2. Kinematics Integration Loop (STEP 6 - The Core)

### HD Micro-Sector Mode (with waypoints)

```
for each waypoint in section.waypoints:
    ┌──────────────────────────────────────────────────┐
    │   INPUT: current speed v, distance to next WP    │
    └──────────────────────────────────────────────────┘
                         ↓
    ┌──────────────────────────────────────────────────┐
    │  Calculate Forces:                               │
    │  F_drag = 0.5*RHO*v²*CDA + rolling_resistance    │
    │  F_df = 0.5*RHO*v²*CLA                           │
    │  F_z = mass*g + F_df  (vertical load)            │
    └──────────────────────────────────────────────────┘
                         ↓
    ┌──────────────────────────────────────────────────┐
    │  Calculate Grip Limits:                          │
    │  F_lat_max = F_z * mu  (cornering)               │
    │  F_brake_max = F_z * mu * brake_eff              │
    │  F_drive_max = min(power_limit, grip_limit)      │
    │                                                  │
    │  If cornering: reduce F_drive by lateral demand │
    └──────────────────────────────────────────────────┘
                         ↓
    ┌──────────────────────────────────────────────────┐
    │  Apply Driver Inputs:                            │
    │  F_net = (F_drive - F_drag) * throttle_pct       │
    │        - F_brake_max * brake_pct                 │
    └──────────────────────────────────────────────────┘
                         ↓
    ┌──────────────────────────────────────────────────┐
    │  Kinematic Update:                               │
    │  a = F_net / mass                                │
    │  v_physics = sqrt(v² + 2*a*distance)             │
    │                                                  │
    │  If corner: cap to v_apex_limit                  │
    │                                                  │
    │  v_blended = 85% v_physics + 15% v_telemetry     │
    └──────────────────────────────────────────────────┘
                         ↓
    ┌──────────────────────────────────────────────────┐
    │  Accumulate Time:                                │
    │  v_avg = (v + v_new) / 2                         │
    │  dt_step = distance / v_avg                      │
    │  t_total += dt_step                              │
    │  v = v_new                                       │
    └──────────────────────────────────────────────────┘

Until end of section → dt_s = t_total
```

### Macro Mode (without waypoints - fallback)

```
while distance_traveled < section.length:
    ┌──────────────────────────────────────────────────┐
    │  Same force calculation as HD mode               │
    │  BUT: Use fixed dt_step = 0.05s                  │
    │  Integration: v_new = v + a*dt_step (Euler)      │
    │               d_step = v_avg*dt_step             │
    └──────────────────────────────────────────────────┘
```

---

## 3. Penalty Application - Detailed Flow

```
┌──────────────────────────────────────────────────┐
│          PENALTY CALCULATION PIPELINE             │
└──────────────────────────────────────────────────┘
                      ↓
    ┌──────────────────────────────────────────┐
    │  1. FUEL PENALTY                         │
    │     Condition: ALL sections              │
    │     Logic: extra_fuel * coeff * fraction │
    │     Max impact: ±0.003s per section      │
    └──────────────────────────────────────────┘
                      ↓
    ┌──────────────────────────────────────────┐
    │  2. TYRE PENALTY (3 sub-penalties)       │
    │     Condition: CURVES ONLY               │
    │     ├─ Compound (C1-C6): ±1.2s/lap       │
    │     ├─ Wear: +0.5s/lap (at 100% wear)    │
    │     └─ Temperature: ±0.5s/lap (extreme) │
    └──────────────────────────────────────────┘
                      ↓
    ┌──────────────────────────────────────────┐
    │  3. PUSH PENALTY                         │
    │     Condition: ALL sections              │
    │     Logic: nonlinear(push_level)         │
    │     Max impact: +0.5s/lap (push=1)       │
    └──────────────────────────────────────────┘
                      ↓
    ┌──────────────────────────────────────────┐
    │  4. ENGINE PENALTY (CV + Map)            │
    │     Condition: STRAIGHTS ONLY            │
    │     ├─ CV delta: -0.01s per CV           │
    │     └─ Map: +0.18s/lap (RACE), etc       │
    └──────────────────────────────────────────┘
                      ↓
    ┌──────────────────────────────────────────┐
    │  5. BRAKE PENALTY                        │
    │     Condition: braking_energy ≥ 0.05 MJ  │
    │     ├─ Duct: ±0.3s per unit closed       │
    │     └─ Fade: +0.05s per fade unit        │
    └──────────────────────────────────────────┘
                      ↓
    ┌──────────────────────────────────────────┐
    │  6. SETUP PENALTY/BONUS                  │
    │     Condition: IF setup_sliders provided │
    │                                          │
    │  a) DF Curve Penalty (corners only):     │
    │     ├─ Fast: -0.030s per delta unit      │
    │     ├─ Medium: -0.020s per delta unit    │
    │     └─ Slow: -0.010s per delta unit      │
    │     Caps: Monaco=1.5s, Monza=0.6s       │
    │                                          │
    │  b) DF Curve Bonus (if DF > target):     │
    │     ├─ Fast: -0.007s per delta unit      │
    │     ├─ Medium: -0.005s per delta unit    │
    │     └─ Slow: -0.003s per delta unit      │
    │                                          │
    │  c) Drag Penalty (straights only):       │
    │     0.004s per delta * straight_length   │
    │     Caps: Monza=0.9s, others=0.6s       │
    │                                          │
    │  d) Drag Bonus (if inside window):       │
    │     -0.004s per delta_neg                │
    │     Caps: Monza=-0.08s, others=-0.04s   │
    └──────────────────────────────────────────┘
                      ↓
    ┌──────────────────────────────────────────┐
    │  7. ERS BONUS (negative = faster)        │
    │     Condition: STRAIGHTS ONLY            │
    │     Logic: -0.125s per MJ deployed       │
    │     Max per section: -0.12s clamp        │
    └──────────────────────────────────────────┘
                      ↓
    ┌──────────────────────────────────────────┐
    │  8. BASELINE + AERO/GRIP DELTA           │
    │     Logic: ref_dt * (baseline + delta)   │
    │     Applied as multiplier to ref_dt      │
    └──────────────────────────────────────────┘
                      ↓
    ┌──────────────────────────────────────────┐
    │  SUM ALL PENALTIES:                      │
    │  dt_final = dt_base +                    │
    │            fuel + tyre + push +          │
    │            engine + brake +              │
    │            setup + ers_bonus             │
    └──────────────────────────────────────────┘
```

---

## 4. Penalty Matrix - When Applied

```
System           │ STRAIGHT │ CURVE │ BRAKING │ Notes
─────────────────┼──────────┼───────┼─────────┼──────────────────
Fuel             │    ✓     │   ✓   │    ✓    │ All sections
Tyre             │    ✗     │   ✓   │    ✓    │ Curves only
Push             │    ✓     │   ✓   │    ✓    │ All sections
Engine           │    ✓     │   ✗   │    ✗    │ Straight only
Brake Penalty    │    ✗     │   ✗   │    ✓    │ If energy ≥0.05MJ
DF Curve Penalty │    ✗     │   ✓   │    ✓    │ Curve sections
Drag Penalty     │    ✓     │   ✗   │    ✗    │ Straight only
ERS Bonus        │    ✓     │   ✗   │    ✗    │ Straight only
```

---

## 5. Lap Time Accumulation

```
┌─────────────────────────────────────┐
│   LapSimulator.run_lap()            │
│   (Multi-section loop)              │
└─────────────────────────────────────┘
           ↓
    for i = 1 to N_SECTIONS:
           ↓
    ┌──────────────────────────────────┐
    │ update_section(car, section_i)   │
    │ Returns: SectionResult with dt_s │
    └──────────────────────────────────┘
           ↓
    car_state.lap_time_acc_s += dt_s
           ↓
    sector_tracking:
      if distance >= sector_marker:
          sector_time = lap_time_acc_s - sector_start
          add to sector_times[]
           ↓
    NEXT SECTION
           ↓
    ┌──────────────────────────────────┐
    │ Final Lap Result:                │
    │ lap_time_s = lap_time_acc_s      │
    │ sector_times = [S1, S2, S3]      │
    │ section_results = [all results]  │
    └──────────────────────────────────┘
```

---

## 6. Corner Speed Limit Calculation

```
┌──────────────────────────────────────────┐
│  For each corner section:                │
└──────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────┐
│ Extract corner radius from section JSON  │
│ (If not available, reverse-engineer      │
│  from telemetry v_min using force eq.)   │
└──────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────┐
│ Grip calculation:                        │
│ mu = 1.6 * grip_factor² * handling_mod   │
│                                          │
│ where:                                   │
│  grip_factor = effective grip (0-1)      │
│  handling_mod = aero balance penalty     │
└──────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────┐
│ Force balance at apex:                   │
│ v_apex = sqrt((mu*m*g) / denom)          │
│                                          │
│ where denom includes:                    │
│  - Weight transfer (m/R)                 │
│  - Downforce effect (0.5*RHO*CLA)        │
└──────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────┐
│ Apply driver pace_factor (0.92-1.08)     │
│ v_apex *= pace_factor                    │
└──────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────┐
│ Clamp to valid range:                    │
│ v_apex = min(v_physics, v_telemetry)     │
│ Clamp: 0.85-1.15× relative to telemetry  │
└──────────────────────────────────────────┘
         ↓
During section traversal:
  v_physics = sqrt(v² + 2*a*dist)
  if v_physics > v_apex:
      v_physics = v_apex (cornering limit)
```

---

## 7. Setup Penalty Logic Tree

```
IF ENABLE_SETUP_PENALTIES:
    │
    ├─ Load ideal_setup from circuit config
    ├─ Calculate slider_deltas vs ideal
    ├─ Compute DF_delta and Drag_delta
    │
    └─ Check if setup is within valid window?
       │
       ├─ YES (within window):
       │   │
       │   ├─ DF CURVES: 
       │   │   └─ Apply BONUS if DF > target (-0.007s fast)
       │   │   └─ Apply NO PENALTY
       │   │
       │   └─ DRAG STRAIGHTS:
       │       ├─ Apply BONUS if drag < target (-0.004s)
       │       └─ Apply MALUS if drag > target (+0.004s)
       │
       └─ NO (outside window):
           │
           ├─ DF CURVES:
           │   └─ Apply PENALTY for ANY deviation (-0.030s fast)
           │
           └─ DRAG STRAIGHTS:
               └─ Apply PENALTY for ANY deviation (+0.004s)

Final: Clamp total by circuit category
  Monaco (high-DF): ±1.5s DF, ±0.08s drag
  Monza (low-drag): ±0.6s DF, ±0.09s drag
  Others (balanced): ±1.0s DF, ±0.06s drag
```

---

## 8. Data Flow Between Components

```
                   ┌─────────────────┐
                   │  CircuitConfig  │
                   │  - sections     │
                   │  - penalties    │
                   │  - references   │
                   └────────┬────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ↓                 ↓                 ↓
    ┌──────────┐      ┌──────────┐    ┌──────────────┐
    │ CarState │      │AeroSetup │    │ DriverSkills │
    │ - speed  │      │- wings   │    │- pace        │
    │- fuel    │      │- balance │    │- consistency │
    │- tyres   │      └──────────┘    └──────────────┘
    └────┬─────┘
         │
         ↓
    ┌──────────────────────┐
    │  update_section()    │
    │  (8-step physics)    │
    └────────┬─────────────┘
             │
      ┌──────┴──────┬──────────┬────────────┐
      │             │          │            │
      ↓             ↓          ↓            ↓
   [Aero]       [Power]    [Tyres]     [Driver]
   Forces       Output     Grip        Mental
      │             │          │            │
      └──────┬──────┴──────────┴────────────┘
             │
             ↓
        ┌──────────────────┐
        │ Kinematics Loop  │
        │ (integrate accel)│
        │ Output: dt_base  │
        └────────┬─────────┘
                 │
      ┌──────────┴──────────┐
      │                     │
      ↓                     ↓
  [Apply Penalties]  [Apply Bonuses]
   fuel, tyre        ers, setup
   push, engine       DF curve
   brake, etc
      │                     │
      └──────────┬──────────┘
                 │
                 ↓
            ┌─────────────┐
            │  dt_final   │
            │ (clamped    │
            │  to 0.01s)  │
            └──────┬──────┘
                   │
                   ↓
            ┌─────────────────┐
            │ SectionResult   │
            │ - dt_s          │
            │ - v_exit        │
            │ - penalties[]   │
            │ - events[]      │
            └─────────────────┘
```

---

## 9. Example: Penalty Cascade for One Section

```
Section: Suzuka sec_05 (Turn 5, medium-speed right-hander)

Input State:
  - Speed entry: 157 kph
  - Setup: FW=30, RW=25 (below ideal 40/35)
  - Fuel: 65 kg (15 kg over reference)
  - Tyres: C2 compound, 45% wear, 110°C (optimal 95°C)
  - Engine: RBR, RACE map
  - Push: Level 7

Step 6 Physics Integration:
  dt_base_computed = 2.156 seconds

Apply Penalties:
  └─ Fuel penalty:     +0.0004s (65 kg, 1/18 sections)
  └─ Tyre penalties:
     ├─ Compound (C2):  +0.031s (0.55s/lap, 1/7 curves)
     ├─ Wear (45%):     +0.019s (distributed)
     └─ Temperature:    +0.008s (10°C too hot)
  └─ Push penalty:     +0.018s (level 7, this curve)
  └─ Engine penalty:   0.0s (not a straight)
  └─ Brake penalty:    0.0s (no significant braking)
  └─ Setup penalty:    -0.024s (DF low, inside window → bonus)
  └─ ERS bonus:        0.0s (not a straight)
  └─ Baseline delta:   +0.002s (aero/grip mod)

Total Penalties: +0.054s
Final dt_s: 2.156 + 0.054 = 2.210 seconds

vs. Optimal (same section):
  Base + Penalties ≈ 2.054s → Gap = +0.156s (7%)
```

---

## 10. Edge Cases & Special Handling

```
EDGE CASE 1: Speed Cap When Transitioning Sections
  if car_speed > section.v_entry:
      car_speed = section.v_entry  # Braking between sections
      Reason: Prevent ghosting through tight entries

EDGE CASE 2: Exit Speed Validation
  v_exit_cap = v_telemetry * (0.97 + 0.06 * pace_factor)
  if is_corner:
      v_exit_cap *= clamp(v_apex_calc / v_min_telem, 0.85, 1.15)
  Reason: Allow aero advantage, prevent extreme advantage

EDGE CASE 3: Minimum Time Clamp
  dt_s = max(dt_s, 0.01s)
  Reason: Never allow negative or zero section times

EDGE CASE 4: No Waypoints Fallback
  if not section.waypoints:
      Use macro integration (Euler, 0.05s steps)
  Reason: HD data may not always be available

EDGE CASE 5: Zero Brake Energy
  if section.braking_energy_mj < 0.05:
      skip brake penalty
  Reason: Avoid penalties on rolling-speed sections

EDGE CASE 6: Penalty Cache Miss
  if cache_disabled or section_not_in_cache:
      recompute section fractions on-the-fly
  Reason: Graceful degradation if cache unavailable
```

---

**Last Updated:** 2026-04-02
