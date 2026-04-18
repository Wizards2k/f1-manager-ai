---
title: Physics Engine V5.4 — Power Unit Stateful Model
date: 2026-04-12
version: 5.4.0
status: SPECIFICA COMPLETA — PRONTA PER IMPLEMENTAZIONE
authors: F1 Manager AI Physics Team
references:
  - docs/ERS-Bucket-Planner.md
  - docs/ERS-Deployment-Strategy.md
  - docs/EngineData2025.md
  - python_backend/lap_simulator/driver_model.py
  - python_backend/lap_simulator/power_unit.py
---

# Physics Engine V5.4 — Power Unit Stateful Model

## 0. Sommario Esecutivo

Il V5.4 sostituisce il modello flat-power V5.3 (910 kW costanti) con un modello **Power Unit Stateful** fisicamente corretto:

- ✅ **Torque curve RPM-dipendente** (ICE + MGU-K separati)
- ✅ **Gestione SOC batteria** (4 MJ, si scarica/ricarica per giro)
- ✅ **Bucket system ERS** (Primary/Secondary/Exit con percentuali circuito-specifiche)
- ✅ **MGU-H direct path** (energia termica → MGU-K bypassando batteria)
- ✅ **Thermal clipping** (derating progressivo 102-122°C)
- ✅ **Harvesting in frenata** (MGU-K + MGU-H ES)
- ✅ **Mappe motore** (QUALIFY, RACE, PRACTICE, SAFETY_CAR)
- ✅ **Dynamic SOC Floor** (floor variabile con lap_progress)
- ✅ **Priority Scoring** (soglie push/defense/DRS)

**Stato V5.3**: Calibrato **0.21% errore medio** (24/24 circuiti <0.5%) ✅
- Best: Monza (0.01%), Worst: Imola (0.48%)
- Aero: front_wing/rear_wing per-circuit
- Suspension: 3 categorie (Monza/Monaco/Silverstone)
- mu_mechanical: 17 circuiti adjusted, 7 default
- Braking: 100% DF con margine 1.30 (P10)

**Target V5.4**: Mantenere <0.5% con modello stateful

---

## 0.1 Nota Importante: driver_skill vs push_level

- **`driver_skill`** (float, default 1.0): Moltiplicatore su grip E potenza nel physics engine
- **`push_level`** (int 1-10): Penalità **additiva**, NON nel physics engine
  - push=10 → zero penalty, push=1 → +1.6s/lap
  - Applicato via `push_penalty.py` **DOPO** la simulazione fisica

Il V5.4 non modifica questo comportamento — il modello PU calcola la forza propulsiva, poi `push_penalty.py` applica la penalità al lap time finale.

---

## 1. Architettura

### 1.1 Modello Concettuale

```
┌─────────────────────────────────────────────────────┐
│  PU Stateful (V5.4) — Modello Fisico Completo     │
│                                                     │
│  Input: RPM, throttle, brake, section_kind         │
│  Stato: SOC, bucket, temperatura, map              │
│  Output: F_prop (forza propulsiva alla ruota)      │
└─────────────────────────────────────────────────────┘
```

### 1.2 Formula Forza Propulsiva

$$F_{prop} = \frac{(T_{ICE} + T_{MGU\text{-}K}) \cdot G_{ratio} \cdot FD \cdot \eta}{r_{wheel}}$$

Dove:
- $T_{ICE}$ = coppia ICE da torque curve (RPM-dipendente)
- $T_{MGU\text{-}K}$ = coppia MGU-K (condizionata da bucket + SOC + thermal)
- $G_{ratio}$ = rapporto marcia (da telemetria o synthetic)
- $FD$ = final drive = 4.10
- $\eta$ = efficienza = 0.96
- $r_{wheel}$ = raggio ruota = 0.334 m

**Nota**: MGU-H direct è incluso in $T_{MGU\text{-}K}$, non è termine separato.

---

## 2. Stato PU (PU_Context)

### 2.1 Dataclass

```python
@dataclass
class PU_Context:
    """Stato Power Unit trasportato tra waypoint."""
    
    # Mappa attiva
    engine_map: str = "QUALIFY"
    
    # Batteria
    soc_mj: float = 4.0
    battery_capacity_mj: float = 4.0
    
    # Bucket ERS (per giro)
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
    
    # Termica
    ers_temp_c: float = 55.0
    ice_temp_c: float = 95.0
    
    # Tracking lap
    lap_deploy_mj: float = 0.0
    lap_harvest_mj: float = 0.0
    lap_mguh_direct_mj: float = 0.0
    
    # Parametri mappa
    deploy_mj_per_lap: float = 4.0
    harvest_mj_per_lap: float = 1.3
    target_soc_end_lap: float = 0.05
    mguh_direct_ratio: float = 0.45
    mguh_power_kw: float = 42.0
    ers_output_kw: float = 160.0
    ice_power_pct_base: float = 1.10
    
    # Bucket percentuali
    bucket_primary_pct: float = 0.60
    bucket_secondary_pct: float = 0.30
    bucket_exit_pct: float = 0.10
    defense_reserve_mj: float = 0.0
    
    # Dynamic SOC Floor (V2)
    soc_floor_dynamic_pct: float = 0.0
    reserve_soc: float = 0.15
    late_soc_floor: float = 0.0
    
    # ERS Modes (V2)
    ers_push_mode: bool = False
    ers_defense_mode: bool = False
    ers_recharge_mode: bool = False
    
    # Priority Scoring
    priority_score_threshold: float = 0.55
    
    # Spread (configurabile)
    bucket_section_spread_lower: float = 0.8
    bucket_section_spread_upper: float = 1.2
```

### 2.2 Inizializzazione

```python
def init_pu_context(circuit_id: str, engine_map: str) -> PU_Context:
    """Inizializza PU_Context da pu_maps.json."""
    pu_maps = load_pu_maps(circuit_id)
    map_data = pu_maps["maps"][engine_map]
    budget_data = pu_maps["ers_budget"]["maps"][engine_map]
    
    ctx = PU_Context(engine_map=engine_map)
    ctx.soc_mj = 4.0  # Batteria piena inizio giro
    
    # Parametri mappa
    ctx.deploy_mj_per_lap = budget_data["deploy_mj_per_lap"]
    ctx.harvest_mj_per_lap = budget_data["harvest_mj_per_lap"]
    ctx.target_soc_end_lap = budget_data["target_soc_end_lap"]
    ctx.mguh_direct_ratio = budget_data["mguh_direct_ratio"]
    ctx.ers_output_kw = map_data["ers_output_kw"]
    ctx.ice_power_pct_base = map_data["power_pct_base"]
    ctx.mguh_power_kw = map_data.get("mguh_power_kw", 42.0)
    
    # Bucket allocation
    deploy_budget = ctx.deploy_mj_per_lap - budget_data.get("defense_reserve_mj", 0.0)
    ctx.bucket_primary_pct = budget_data.get("bucket_primary_pct", 0.60)
    ctx.bucket_secondary_pct = budget_data.get("bucket_secondary_pct", 0.30)
    ctx.bucket_exit_pct = budget_data.get("bucket_exit_pct", 0.10)
    pct_sum = ctx.bucket_primary_pct + ctx.bucket_secondary_pct + ctx.bucket_exit_pct
    
    ctx.bucket_primary_total_mj = deploy_budget * ctx.bucket_primary_pct / pct_sum
    ctx.bucket_secondary_total_mj = deploy_budget * ctx.bucket_secondary_pct / pct_sum
    ctx.bucket_exit_total_mj = deploy_budget * ctx.bucket_exit_pct / pct_sum
    ctx.bucket_primary_remaining_mj = ctx.bucket_primary_total_mj
    ctx.bucket_secondary_remaining_mj = ctx.bucket_secondary_total_mj
    ctx.bucket_exit_remaining_mj = ctx.bucket_exit_total_mj
    
    # MGU-H direct budget
    lap_time_estimate = 90.0  # secondi (stimato)
    ctx.mguh_direct_total_mj = ctx.mguh_power_kw * lap_time_estimate / 1000.0
    ctx.mguh_direct_remaining_mj = ctx.mguh_direct_total_mj
    
    return ctx
```

**Fonte**: `config/circuits/derived/<circuit_id>/pu_maps.json` (già esistente per 24 circuiti)

---

## 3. Calcolo Coppia ICE

### 3.1 Torque Curve (da EngineData2025.md)

```python
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

def lookup_ice_torque(rpm: float, ice_power_pct: float) -> float:
    """Interpola coppia ICE da LUT, scalata per mappa."""
    torque = interpolate_lut(ICE_TORQUE_LUT, rpm)
    return torque * ice_power_pct  # QUALIFY=1.10, RACE=0.95, etc.
```

### 3.2 RPM Calculation

**Livello 1 (primario)**: Da telemetria reale (Reference Pull)
```python
if pu_lookup_blend > 0 and reference_pull is not None:
    rpm = interpolate_rpm(distance_m, reference_pull)
    n_gear = interpolate_nGear(distance_m, reference_pull)
    gear_ratio = get_gear_ratio_from_nGear(n_gear)
```

**Livello 3 (fallback)**: Synthetic gearbox
```python
GEAR_RATIOS = [2.53, 1.96, 1.63, 1.40, 1.22, 1.10, 1.01, 0.92]

def get_optimal_gear(v_ms: float) -> tuple:
    """Seleziona marcia per mantenere RPM 10500-11800."""
    R_WHEEL = 0.334
    FINAL_DRIVE = 4.10
    
    for i, gr in enumerate(GEAR_RATIOS):
        rpm = v_ms * 60 / (2 * math.pi * R_WHEEL) * gr * FINAL_DRIVE
        if 10500 <= rpm <= 12500:
            return i + 1, gr, rpm
    
    return 8, GEAR_RATIOS[7], rpm
```

---

## 4. Calcolo Coppia MGU-K (Bucket + SOC + Thermal)

### 4.1 Algoritmo Principale

```python
def compute_mguk_torque(
    pu_ctx: PU_Context,
    section_kind: str,
    rpm: float,
    dt_s: float,
    lap_progress: float,
    priority_score: float
) -> float:
    """Calcola coppia MGU-K con vincoli bucket/SOC/thermal."""
    
    # 1. Dynamic SOC Floor (V2 logic)
    pu_ctx.soc_floor_dynamic_pct = (
        pu_ctx.reserve_soc - (pu_ctx.reserve_soc - pu_ctx.late_soc_floor) * lap_progress
    )
    
    # 2. Risolvi bucket
    bucket = _resolve_bucket(section_kind)
    bucket_remaining = _get_bucket_remaining(pu_ctx, bucket)
    
    if bucket_remaining <= 0:
        pu_ctx.bucket_sections_left = 0
        pu_ctx.bucket_section_cap_mj = 0.0
        return 0.0
    
    # 3. Cap dinamico con spread
    sections_left = _count_sections_left(pu_ctx, bucket)
    pu_ctx.bucket_sections_left = sections_left
    
    dynamic_cap_mj = bucket_remaining / max(sections_left, 1)
    
    spread_lower = pu_ctx.bucket_section_spread_lower
    spread_upper = pu_ctx.bucket_section_spread_upper
    
    pu_ctx.bucket_section_cap_mj = clamp(
        dynamic_cap_mj * spread_lower,
        dynamic_cap_mj * spread_upper,
        dynamic_cap_mj
    )
    
    # 4. Battery window
    soc_headroom = max(
        pu_ctx.soc_mj - pu_ctx.soc_floor_dynamic_pct * pu_ctx.battery_capacity_mj,
        0.0
    )
    battery_window_mj = min(
        pu_ctx.bucket_section_cap_mj,
        soc_headroom,
        bucket_remaining
    )
    
    # 5. Priority threshold
    threshold = pu_ctx.priority_score_threshold
    if pu_ctx.ers_push_mode:
        threshold = 0.32
    elif pu_ctx.ers_defense_mode:
        threshold = 0.42
    elif section_has_drs:
        threshold = 0.48
    
    soc_deficit = pu_ctx.soc_floor_dynamic_pct - (pu_ctx.soc_mj / pu_ctx.battery_capacity_mj)
    if soc_deficit > 0 and not pu_ctx.ers_push_mode:
        threshold += clamp(soc_deficit * 1.2, 0.02, 0.2)
    
    if priority_score < threshold:
        return 0.0
    
    # 6. Potenza → Coppia
    mguk_power_kw = min(pu_ctx.ers_output_kw, battery_window_mj * 1000.0 / dt_s)
    omega = rpm * 2 * math.pi / 60
    mguk_torque = mguk_power_kw * 1000.0 / max(omega, 1.0)
    
    # 7. Thermal clipping
    thermal_eta = _compute_thermal_eta(pu_ctx.ers_temp_c)
    mguk_torque *= thermal_eta
    
    # 8. Consuma bucket e SOC
    energy_used_mj = mguk_power_kw * dt_s / 1000.0
    _consume_bucket(pu_ctx, bucket, energy_used_mj)
    pu_ctx.soc_mj -= energy_used_mj
    pu_ctx.lap_deploy_mj += energy_used_mj
    
    return mguk_torque
```

### 4.2 Bucket Resolution

```python
def _resolve_bucket(section_kind: str) -> str:
    """Mappa section_kind → bucket."""
    if section_kind in ("Straight", "MediumStraight"):
        return "primary"
    
    if section_kind in ("UltraFastCorner", "FastCorner"):
        return "secondary"
    
    # Curve lente/uscite → exit
    return "exit"
```

---

## 5. MGU-H Direct Path

### 5.1 Algoritmo

```python
SECTION_MGUH_FACTORS = {
    "Straight": 1.00,
    "MediumStraight": 0.90,
    "UltraFastCorner": 0.85,
    "FastCorner": 0.75,
    "MediumCorner": 0.60,
    "SlowCorner": 0.45,
    "VerySlowCorner": 0.35,
}

def compute_mguh_direct_torque(
    pu_ctx: PU_Context,
    section_kind: str,
    throttle_pct: float,
    rpm: float,
    dt_s: float
) -> float:
    """Calcola coppia MGU-H direct (bypass batteria)."""
    
    # 1. Fattori sezione e throttle
    section_factor = SECTION_MGUH_FACTORS.get(section_kind, 0.5)
    throttle_factor = throttle_pct / 100.0
    
    # 2. Potenza MGU-H
    mguh_power_kw = pu_ctx.mguh_power_kw * section_factor * throttle_factor
    
    # 3. Thermal clipping
    thermal_eta = _compute_thermal_eta(pu_ctx.ers_temp_c)
    mguh_power_kw *= thermal_eta
    
    # 4. Budget check
    energy_mj = mguh_power_kw * dt_s / 1000.0
    pu_ctx.mguh_direct_section_mj = energy_mj
    
    if energy_mj > pu_ctx.mguh_direct_remaining_mj:
        energy_mj = pu_ctx.mguh_direct_remaining_mj
        mguh_power_kw = energy_mj * 1000.0 / dt_s
        pu_ctx.mguh_direct_section_mj = energy_mj
    
    # 5. Potenza → Coppia
    omega = rpm * 2 * math.pi / 60
    mguh_torque = mguh_power_kw * 1000.0 / max(omega, 1.0)
    
    # 6. Aggiorna stato
    pu_ctx.mguh_direct_remaining_mj -= energy_mj
    pu_ctx.lap_mguh_direct_mj += energy_mj
    
    return mguh_torque
```

### 5.2 Proprietà Chiave

- ✅ Disponibile anche quando SOC = 0
- ✅ NON consuma budget batteria (4 MJ/giro)
- ✅ NON consuma bucket ERS
- ❌ Limitato da temperatura (thermal clipping)
- ❌ Dipende da throttle % e section_kind

---

## 6. Harvesting (Ricarica Batteria)

### 6.1 MGU-K Harvest (Frenata)

```python
def compute_mguk_harvest(
    pu_ctx: PU_Context,
    brake_pct: float,
    v_ms: float,
    dt_s: float
) -> float:
    """Calcola energia recuperata in frenata."""
    
    if brake_pct < 5:
        return 0.0
    
    # Potenza recupero (max 120 kW MGU-K)
    harvest_power_kw = 120.0 * (brake_pct / 100.0)
    
    # Limite budget per giro
    remaining_harvest_mj = pu_ctx.harvest_mj_per_lap - pu_ctx.lap_harvest_mj
    if remaining_harvest_mj <= 0:
        return 0.0
    
    max_energy_mj = harvest_power_kw * dt_s / 1000.0
    energy_mj = min(max_energy_mj, remaining_harvest_mj)
    
    # Overflow check (batteria piena)
    headroom_mj = pu_ctx.battery_capacity_mj - pu_ctx.soc_mj
    energy_stored_mj = min(energy_mj, headroom_mj)
    
    # Aggiorna stato
    pu_ctx.soc_mj += energy_stored_mj
    pu_ctx.lap_harvest_mj += energy_mj
    
    return energy_stored_mj
```

### 6.2 MGU-H ES Harvest

```python
def compute_mguh_es_harvest(
    pu_ctx: PU_Context,
    section_kind: str,
    throttle_pct: float,
    dt_s: float
) -> float:
    """Calcola energia MGU-H che va a batteria (non direct)."""
    
    es_bias = 1.0 - pu_ctx.mguh_direct_ratio
    
    section_factor = SECTION_MGUH_FACTORS.get(section_kind, 0.5)
    throttle_factor = throttle_pct / 100.0
    
    mguh_total_power_kw = pu_ctx.mguh_power_kw * section_factor * throttle_factor
    mguh_es_power_kw = mguh_total_power_kw * es_bias
    
    energy_mj = mguh_es_power_kw * dt_s / 1000.0
    
    headroom_mj = pu_ctx.battery_capacity_mj - pu_ctx.soc_mj
    energy_stored_mj = min(energy_mj, headroom_mj)
    
    pu_ctx.soc_mj += energy_stored_mj
    return energy_stored_mj
```

---

## 7. Modello Termico

### 7.1 Bilancio Termico

$$T_{ers}^{(t+dt)} = T_{ers}^{(t)} + \frac{\dot{Q}_{gen} - \dot{Q}_{cool}}{C_{th}} \cdot dt$$

Dove:
- $\dot{Q}_{gen} = k_{joule} \cdot P_{elec}^2$ (Joule heating)
- $\dot{Q}_{cool} = h_v \cdot v_{car} \cdot (T_{ers} - T_{amb})$ (convective cooling)
- $C_{th} = 18.0$ kJ/K

### 7.2 Parametri

| Parametro | Valore | Unità |
|-----------|--------|-------|
| T_limit (inizio clipping) | 102.0 | °C |
| T_max (shutdown) | 122.0 | °C |
| k_joule | 0.000045 | - |
| h_v | 0.0025 | - |
| C_th | 18.0 | kJ/K |
| T_amb | 30.0 | °C |

### 7.3 Derating Factor

```python
def _compute_thermal_eta(ers_temp_c: float) -> float:
    """Calcola fattore efficienza termica."""
    T_LIMIT = 102.0
    T_MAX = 122.0
    
    if ers_temp_c < T_LIMIT:
        return 1.0
    elif ers_temp_c >= T_MAX:
        return 0.0
    else:
        return 1.0 - (ers_temp_c - T_LIMIT) / (T_MAX - T_LIMIT)
```

### 7.4 Update Termico (Sub-stepping)

```python
THERMAL_SUBSTEP_S = 0.01  # s

def update_thermal_state(
    pu_ctx: PU_Context,
    p_elec_kw: float,
    v_ms: float,
    dt_s: float
):
    """Aggiorna temperatura ERS con sub-stepping."""
    K_JOULE = 0.000045
    H_V = 0.0025
    C_TH = 18.0
    T_AMB = 30.0
    
    n_steps = max(1, int(math.ceil(dt_s / THERMAL_SUBSTEP_S)))
    sub_dt = dt_s / n_steps
    
    for _ in range(n_steps):
        q_gen = K_JOULE * (p_elec_kw ** 2)
        q_cool = H_V * v_ms * (pu_ctx.ers_temp_c - T_AMB)
        delta_t = (q_gen - q_cool) / (C_TH * 1000.0) * sub_dt
        
        pu_ctx.ers_temp_c += delta_t
        pu_ctx.ers_temp_c = max(T_AMB, min(pu_ctx.ers_temp_c, 150.0))
```

---

## 8. Integrazione in waypoint_integrator.py

### 8.1 Interfaccia

```python
def integrate_lap_hd(
    ...
    ers_power_fraction: float = 1.0,  # Legacy V5.3
    pu_config: Optional[Dict] = None,  # V5.4: {"engine_map": "QUALIFY"}
    ...
):
    if pu_config is not None:
        # V5.4 mode: PU stateful
        pu_ctx = init_pu_context(
            circuit_id=circuit_id,
            engine_map=pu_config.get("engine_map", "QUALIFY")
        )
    else:
        # V5.3 mode: flat power (backward compat)
        pu_ctx = None
```

### 8.2 Flusso per Waypoint

```python
for i in range(len(waypoints) - 1):
    # ... calcolo aero, grip (invariato) ...
    
    if pu_ctx is not None:
        # === V5.4 PU STATEFUL ===
        
        # 1. RPM (telemetria o synthetic)
        if pu_lookup_blend > 0 and reference_pull:
            rpm = interpolate_rpm(distance_m, reference_pull)
            n_gear = interpolate_nGear(distance_m, reference_pull)
            gear_ratio = get_gear_ratio_from_nGear(n_gear)
        else:
            n_gear, gear_ratio, rpm = get_optimal_gear(state.velocity_ms)
        
        # 2. ICE Torque
        ice_torque = lookup_ice_torque(rpm, pu_ctx.ice_power_pct_base)
        
        # 3. MGU-K Torque (bucket + SOC + thermal)
        mguk_torque = compute_mguk_torque(
            pu_ctx, section_kind, rpm, dt_step, lap_progress, priority_score
        )
        
        # 4. MGU-H Direct Torque
        mguh_torque = compute_mguh_direct_torque(
            pu_ctx, section_kind, throttle_pct, rpm, dt_step
        )
        
        # 5. Forza propulsiva
        total_torque = ice_torque + mguk_torque + mguh_torque
        f_engine = total_torque * gear_ratio * FINAL_DRIVE * DRIVETRAIN_EFFICIENCY / R_WHEEL
        
        # 6. Harvesting (se frenata)
        if brake_pct > 5:
            compute_mguk_harvest(pu_ctx, brake_pct, state.velocity_ms, dt_step)
            compute_mguh_es_harvest(pu_ctx, section_kind, throttle_pct, dt_step)
        
        # 7. Update termico
        p_elec_kw = (mguk_torque + mguh_torque) * rpm * 2 * math.pi / 60 / 1000.0
        update_thermal_state(pu_ctx, p_elec_kw, state.velocity_ms, dt_step)
        
    else:
        # === V5.3 LEGACY (flat power) ===
        effective_pu_kw = ICE_PEAK_POWER_KW + ERS_PEAK_POWER_KW * ers_power_fraction
        power_available = effective_pu_kw * 1000 * rpm_fraction * (throttle_pct / 100.0)
        power_available *= DRIVETRAIN_EFFICIENCY * driver_skill
        
        if state.velocity_ms > 1.0:
            f_engine = power_available / state.velocity_ms
        else:
            f_engine = power_available / 1.0
```

---

## 9. Backward Compatibility

### 9.1 V5.3 Mode (Default)

```python
integrate_lap_hd(..., pu_config=None)
# → Comportamento identico a V5.3 (ers_power_fraction)
# → validate_v53.py funziona senza modifiche
```

### 9.2 V5.4 Mode

```python
integrate_lap_hd(..., pu_config={"engine_map": "QUALIFY"})
# → PU stateful con torque curve, bucket, thermal
```

---

## 10. Validazione

### 10.1 Test Non-Regressione

1. `validate_v53.py` con `pu_config=None` → deve dare 0.21% (V5.3)
2. `validate_v53.py` con `pu_config={"engine_map": "QUALIFY"}` → errore < 0.5%

### 10.2 Test Funzionali

1. **SOC Test**: Fine giro qualifica → SOC ≈ 0.05 (quasi vuoto)
2. **Thermal Test**: Monza → ers_temp_c sale verso 102°C rettilinei
3. **Bucket Test**: Primary si esaurisce su rettilinei, Exit su uscite
4. **Mappe Test**: QUALIFY < RACE < PRACTICE < SAFETY_CAR (tempi crescenti)
5. **Harvest Test**: Frenata → SOC aumenta (se headroom)

### 10.3 Circuiti Riferimento

- **Monza**: Test thermal (rettilinei lunghi)
- **Monaco**: Test bucket Exit (tante curve lente)
- **Suzuka**: Test bilanciamento (misto veloce)
- **Spa**: Test MGU-H direct (settori veloci)
- **Austin**: Test outlier (già problematico V5.3)

---

## 11. Implementazione — Fasi

### Fase 1: PU_Context + Torque Model (in-progress)
- [ ] Creare `PU_Context` dataclass in `waypoint_integrator.py`
- [ ] Implementare `init_pu_context()`
- [ ] Implementare `lookup_ice_torque()` con ICE_TORQUE_LUT
- [ ] Implementare `get_optimal_gear()` (synthetic gearbox)
- [ ] Aggiungere `pu_config` parametro a `integrate_lap_hd()`
- [ ] **Test**: `pu_config=None` → comportamento V5.3 identico

### Fase 2: Bucket + SOC + Harvesting
- [ ] Implementare `_resolve_bucket()` con euristiche
- [ ] Implementare `compute_mguk_torque()` con bucket + SOC
- [ ] Implementare `compute_mguk_harvest()` e `compute_mguh_es_harvest()`
- [ ] Implementare `compute_mguh_direct_torque()`
- [ ] **Test**: SOC fine giro ≈ target_soc_end_lap

### Fase 3: Thermal Model
- [ ] Implementare `update_thermal_state()` con sub-stepping
- [ ] Implementare `_compute_thermal_eta()`
- [ ] Integrare thermal clipping in MGU-K e MGU-H
- [ ] **Test**: Monza → temperatura sale rettilinei

### Fase 4: Calibration + Validation
- [ ] Normalizzazione energetica (scala η se necessario)
- [ ] Validazione 5 circuiti (Monza, Monaco, Suzuka, Spa, Austin)
- [ ] Test mappe: QUALIFY < RACE < PRACTICE < SAFETY_CAR
- [ ] Aggiornare `validate_v53.py` con `--pu-config`
- [ ] **Target**: Errore < 0.5% con QUALIFY

### Fase 5: CHECK SETUP Tests (dopo V5.4 completato)

**Importante**: Tutti e 6 i test devono essere eseguiti **DOPO** che il modello PU V5.4 è completamente implementato e validato. Il modello PU influenza la forza motrice in ogni test.

**Baseline comune**: McLaren, Norris, Fuel 20kg, Push 10, ICE Quali, ERS Quali, Soft compound

**Circuiti di test**: Monza, Monaco, Suzuka, Spa, Austin

1. **Aero sweep**: Variazione front_wing/rear_wing → delta tempo giro
2. **Suspension sweep**: Variazione spring/ARB/ride_height → delta tempo giro
3. **Fuel load**: 5kg, 10kg, 20kg, 50kg, 110kg → delta tempo giro
4. **Tyre compounds**: C1-C6 su 5 circuiti → delta tempo giro
5. **ICE/ERS mapping**: QUALIFY, RACE, PRACTICE, SAFETY_CAR → delta tempo giro
6. **Push level**: 1-10 → delta tempo giro (penalità additiva via push_penalty.py)

**Nota**: Il test #5 (ICE/ERS mapping) dipende direttamente dal modello PU V5.4. I test #1-4 e #6 usano il modello PU ma non variano le mappe motore.

---

## Appendice A: Costanti

```python
# Power Unit
ICE_PEAK_POWER_KW = 750.0
ERS_PEAK_POWER_KW = 160.0
ERS_MAX_DEPLOY_MJ = 4.0
ERS_MAX_HARVEST_MJ = 2.0
BATTERY_CAPACITY_MJ = 4.0

# Trasmissione
R_WHEEL = 0.334
FINAL_DRIVE = 4.10
DRIVETRAIN_EFFICIENCY = 0.96
GEAR_RATIOS = [2.53, 1.96, 1.63, 1.40, 1.22, 1.10, 1.01, 0.92]

# Termica
THERMAL_K_JOULE = 0.000045
THERMAL_H_V = 0.0025
THERMAL_C_TH = 18.0
THERMAL_T_LIMIT = 102.0
THERMAL_T_MAX = 122.0
THERMAL_T_AMB = 30.0
```

## Appendice B: Mappe Motore

| Mappa | ICE % | ERS Deploy | ERS Harvest | SOC Target |
|-------|-------|------------|-------------|------------|
| QUALIFY | 1.08-1.12 | 4.0 MJ | 0.5-0.8 MJ | 0.05 |
| RACE | 0.90-1.00 | 3.4-3.7 MJ | 1.0-1.3 MJ | 0.40 |
| PRACTICE | 0.75-0.85 | 2.6 MJ | 1.8 MJ | 0.72 |
| SAFETY_CAR | 0.40 | 0.6 MJ | 2.2 MJ | 0.92 |

---

**Author**: F1 Manager AI Physics Team  
**Last Updated**: 2026-04-12  
**Version**: 5.4.0  
**Status**: SPECIFICA COMPLETA — PRONTA PER IMPLEMENTAZIONE