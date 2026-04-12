# 📑 Specifica Tecnica: Implementazione Power Unit Stateful V5.4

**Versione**: 2.0 (Revisione completa)
**Data**: 2026-04-12
**Stato**: Draft — In attesa di implementazione
**Sostituisce**: "Ponte Fisico V5.1" (versione originale)

---

## 0. Motivazione e Contesto

Il motore V5.3 attuale tratta la Power Unit come un singolo scalare:
```python
effective_pu_kw = ICE_PEAK_POWER_KW + ERS_PEAK_POWER_KW * ers_power_fraction  # 910 kW costanti
```

Questo modello è **fisicamente incompleto**:
- ❌ Nessuna gestione SOC (la batteria non si scarica mai)
- ❌ Nessun bucket system (ERS erogato uniformemente)
- ❌ Nessun thermal clipping (nessun derating per temperatura)
- ❌ Nessun harvesting (la batteria non si ricarica in frenata)
- ❌ Nessuna mappa ICE/ERS (QUALIFY vs RACE vs ECONOMY)
- ❌ Nessun MGU-H direct path (energia termica ignorata)
- ❌ Nessuna curva di coppia RPM-dipendente (potenza costante)

Il sistema V2 (`power_unit.py` + `engine_penalty.py`) ha questi modelli, ma li applica come **penalty additiva** su `dt_s`, non come forza propulsiva. Questo è il "dramma": la PU non modifica la fisica, aggiunge secondi a posteriori.

**Obiettivo**: Integrare il modello PU nel `waypoint_integrator.py` come **forza propulsiva** ($F_{prop}$), non come penalty. La potenza erogata varia per sezione in base a mappa, SOC, bucket, temperatura e RPM.

---

## 1. Architettura a 3 Livelli

```
┌─────────────────────────────────────────────────────┐
│  LIVELLO 1: Reference Pull (Telemetria Reale)      │
│  Fonte: TracingInsights 2025 (_Telemetry.json)     │
│  Dati: RPM, nGear, Throttle%, Brake, Speed         │
│  → Lookup coppia diretta, massima accuratezza      │
│  → Attivo quando pu_lookup_blend > 0               │
├─────────────────────────────────────────────────────┤
│  LIVELLO 2: PU Stateful (Modello Fisico)          │
│  Stato: SOC, bucket, temperatura, deploy/harvest   │
│  → MGU-K deploy condizionato (bucket + SOC + temp) │
│  → MGU-H direct proporzionale (throttle × section) │
│  → Harvesting in frenata (brake → SOC)             │
│  → Thermal clipping (derating progressivo)         │
│  → Sempre attivo (è il cuore del modello)          │
├─────────────────────────────────────────────────────┤
│  LIVELLO 3: Synthetic Gearbox (Fallback)           │
│  Funzione: get_optimal_gear(v_ms) → G_ratio → RPM │
│  → Solo quando telemetria non disponibile          │
│  → Meno accurato ma funzionale                     │
│  → Attivo quando pu_lookup_blend == 0              │
└─────────────────────────────────────────────────────┘
```

**Regola di routing**:
- Se `pu_lookup_blend > 0` e Reference Pull disponibile → Livello 1 fornisce RPM/throttle
- Il Livello 2 è **sempre** attivo (gestisce SOC, bucket, thermal)
- Il Livello 3 è il fallback per RPM quando il Livello 1 non è disponibile

---

## 2. Stato della PU (PU_Context)

Il V5 è stateless — ogni giro è un'integrazione isolata. Per gestire la PU, serve uno stato trasportato tra waypoint.

### 2.1 Dataclass `PU_Context`

```python
@dataclass
class PU_Context:
    """Stato della Power Unit trasportato tra waypoint."""

    # --- Mappa attiva ---
    engine_map: str = "QUALIFY"  # QUALIFY, RACE, PRACTICE, SAFETY_CAR, ECONOMY, RECHARGE

    # --- Batteria (ES) ---
    soc_mj: float = 4.0          # Stato di carica attuale (MJ), max 4.0 per regolamento
    battery_capacity_mj: float = 4.0  # Capacità utile FIA

    # --- Bucket ERS (per giro) ---
    bucket_primary_remaining_mj: float = 0.0   # Rettilinei
    bucket_secondary_remaining_mj: float = 0.0 # Curve veloci
    bucket_exit_remaining_mj: float = 0.0      # Uscite curva
    bucket_primary_total_mj: float = 0.0
    bucket_secondary_total_mj: float = 0.0
    bucket_exit_total_mj: float = 0.0

    # --- MGU-H Direct ---
    mguh_direct_remaining_mj: float = 0.0  # Budget MGU-H direct per giro
    mguh_direct_total_mj: float = 0.0

    # --- Termica ---
    ers_temp_c: float = 55.0     # Temperatura ERS (°C)
    ice_temp_c: float = 95.0    # Temperatura ICE (°C)

    # --- Tracking per lap ---
    lap_deploy_mj: float = 0.0          # Totale deployato nel giro
    lap_harvest_mj: float = 0.0        # Totale recuperato nel giro
    lap_mguh_direct_mj: float = 0.0    # Totale MGU-H direct nel giro

    # --- Parametri mappa (da pu_maps.json) ---
    deploy_mj_per_lap: float = 4.0
    harvest_mj_per_lap: float = 1.3
    target_soc_end_lap: float = 0.05
    mguh_direct_ratio: float = 0.45
    mguh_power_kw: float = 42.0
    ers_output_kw: float = 160.0
    ice_power_pct_base: float = 1.10
    ice_power_pct_min: float = 1.08
    ice_power_pct_max: float = 1.12

    # --- Bucket percentuali ---
    bucket_primary_pct: float = 0.60
    bucket_secondary_pct: float = 0.30
    bucket_exit_pct: float = 0.10
    defense_reserve_mj: float = 0.0
```

### 2.2 Inizializzazione per giro

All'inizio di ogni giro in `integrate_lap_hd`, `PU_Context` viene inizializzato dai dati di `pu_maps.json`:

```python
def init_pu_context(circuit_id: str, engine_map: str) -> PU_Context:
    """Inizializza PU_Context dal file pu_maps.json del circuito."""
    pu_maps = load_pu_maps(circuit_id)  # config/circuits/derived/<cid>/pu_maps.json
    map_data = pu_maps["maps"][engine_map]
    budget_data = pu_maps["ers_budget"]["maps"][engine_map]

    ctx = PU_Context(engine_map=engine_map)
    ctx.soc_mj = 4.0  # Batteria piena a inizio giro qualifica

    # Parametri mappa
    ctx.deploy_mj_per_lap = budget_data["deploy_mj_per_lap"]
    ctx.harvest_mj_per_lap = budget_data["harvest_mj_per_lap"]
    ctx.target_soc_end_lap = budget_data["target_soc_end_lap"]
    ctx.mguh_direct_ratio = budget_data["mguh_direct_ratio"]
    ctx.ers_output_kw = map_data["ers_output_kw"]
    ctx.ice_power_pct_base = map_data["power_pct_base"]
    ctx.ice_power_pct_min = map_data["power_pct_min"]
    ctx.ice_power_pct_max = map_data["power_pct_max"]

    # MGU-H power (da _meta.mguh_profile o calcolato)
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
    ctx.mguh_direct_total_mj = ctx.mguh_power_kw * lap_time_estimate / 1000.0  # kW → MJ
    ctx.mguh_direct_remaining_mj = ctx.mguh_direct_total_mj

    return ctx
```

**Fonte dati**: `config/circuits/derived/<circuit_id>/pu_maps.json` — già esistente per tutti i 24 circuiti.

---

## 3. Calcolo della Forza Propulsiva ($F_{prop}$)

### 3.1 Formula Principale

La forza alla ruota sostituisce `f_engine = power / v`:

$$F_{prop} = \frac{(T_{ICE} + T_{MGU\text{-}K,eff}) \cdot G_{ratio} \cdot FD \cdot \eta}{r_{wheel}}$$

Dove:
- $T_{ICE}$ = coppia ICE dalla torque curve (RPM-dipendente)
- $T_{MGU\text{-}K,eff}$ = coppia MGU-K effettiva (include MGU-H direct)
- $G_{ratio}$ = rapporto marcia (da telemetria o synthetic gearbox)
- $FD$ = final drive = 4.10
- $\eta$ = efficienza trasmissione = 0.96 (calibrabile per normalizzazione)
- $r_{wheel}$ = raggio ruota = 0.334 m

**Nota**: $T_{MGU\text{-}H}$ **non** è nella formula come termine separato. L'MGU-H va al MGU-K via direct path — la sua potenza si somma alla potenza MGU-K, e la coppia risultante è inclusa in $T_{MGU\text{-}K,eff}$.

### 3.2 Calcolo RPM (Livello 1 vs Livello 3)

#### Livello 1: RPM da Telemetria (primario)

Se `pu_lookup_blend > 0` e il Reference Pull è disponibile, gli RPM sono interpolati dalla telemetria reale:

```python
# Già implementato in waypoint_integrator.py (V5.0)
if pu_lookup_blend > 0.0 and reference_pull is not None:
    rpm_real = interpolate_rpm_from_reference_pull(distance_m, reference_pull)
    rpm_fraction = 1.0 + pu_lookup_blend * (rpm_frac_real - 1.0)
```

Il Reference Pull contiene anche `nGear`, che permette di calcolare $G_{ratio}$:

```python
GEAR_RATIOS = [2.53, 1.96, 1.63, 1.40, 1.22, 1.10, 1.01, 0.92]  # Da EngineData2025.md
FINAL_DRIVE = 4.10

def get_gear_ratio_from_nGear(n_gear: int) -> float:
    """Ritorna il rapporto di marcia da nGear (1-8)."""
    idx = max(0, min(n_gear - 1, 7))
    return GEAR_RATIOS[idx]
```

#### Livello 3: Synthetic Gearbox (fallback)

Quando la telemetria non è disponibile, si seleziona la marcia per mantenere RPM nel range ottimale:

```python
def get_optimal_gear(v_ms: float) -> tuple:
    """Seleziona marcia e calcola RPM per mantenere RPM nel range 10500-11800."""
    R_WHEEL = 0.334
    FINAL_DRIVE = 4.10
    GEAR_RATIOS = [2.53, 1.96, 1.63, 1.40, 1.22, 1.10, 1.01, 0.92]

    best_gear = 8
    best_rpm = 0
    for i, gr in enumerate(GEAR_RATIOS):
        rpm = v_ms * 60 / (2 * math.pi * R_WHEEL) * gr * FINAL_DRIVE
        if 10500 <= rpm <= 12500:
            best_gear = i + 1
            best_rpm = rpm
            break
        elif rpm < 10500:
            best_gear = i + 1
            best_rpm = rpm

    return best_gear, GEAR_RATIOS[best_gear - 1], best_rpm
```

### 3.3 ICE Torque (Curva RPM-Dipendente)

La coppia ICE è determinata dalla torque curve di `EngineData2025.md`, con interpolazione lineare:

```python
# Torque curve lookup (da EngineData2025.md §4)
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
    """Interpola la coppia ICE dalla LUT, scalata per mappa motore."""
    # Interpolazione lineare nella LUT
    torque = interpolate_lut(ICE_TORQUE_LUT, rpm)
    # Scala per mappa: QUALIFY=1.10, RACE=0.95, PRACTICE=0.80, SAFETY_CAR=0.40
    return torque * ice_power_pct
```

**Fuel Flow Penalty**: Oltre 10.500 RPM, la coppia scende linearmente (già catturato nella LUT: 610 Nm @ 8500 → 480 Nm @ 12500).

### 3.4 MGU-K Effettiva (Bucket + SOC + Thermal)

La coppia MGU-K è condizionata da **tre vincoli in AND**:

```python
def compute_mguk_torque(pu_ctx: PU_Context, section_kind: str, rpm: float) -> float:
    """Calcola la coppia MGU-K effettiva per la sezione corrente."""

    # 1. Risolvi bucket per la sezione
    bucket = _resolve_bucket(section_kind, pu_ctx)
    bucket_remaining = _get_bucket_remaining(pu_ctx, bucket)

    # 2. Se il bucket è esaurito, niente deploy
    if bucket_remaining <= 0:
        return 0.0

    # 3. Se SOC è al minimo, niente deploy da batteria
    if pu_ctx.soc_mj <= 0.1:
        return 0.0  # Solo MGU-H direct può ancora erogare

    # 4. Calcola cap dinamico per sezione
    sections_left = _count_sections_left(pu_ctx, bucket)
    dynamic_cap_mj = bucket_remaining / max(sections_left, 1)
    battery_window_mj = min(dynamic_cap_mj, pu_ctx.soc_mj, bucket_remaining)

    # 5. Calcola potenza MGU-K da budget
    # P = E / dt  →  T = P / ω  dove ω = RPM × 2π/60
    mguk_power_kw = min(pu_ctx.ers_output_kw, battery_window_mj * 1000.0 / dt_s)
    omega = rpm * 2 * math.pi / 60
    mguk_torque = mguk_power_kw * 1000.0 / max(omega, 1.0)  # kW → W, poi T = P/ω

    # 6. Thermal clipping
    thermal_eta = _compute_thermal_eta(pu_ctx.ers_temp_c)
    mguk_torque *= thermal_eta

    # 7. Consuma bucket e SOC
    energy_used_mj = mguk_power_kw * dt_s / 1000.0
    _consume_bucket(pu_ctx, bucket, energy_used_mj)
    pu_ctx.soc_mj -= energy_used_mj
    pu_ctx.lap_deploy_mj += energy_used_mj

    return mguk_torque
```

### 3.5 MGU-H Direct Path

L'MGU-H invia energia **direttamente** al MGU-K bypassando la batteria. Questa energia:
- ✅ È disponibile anche quando SOC = 0
- ✅ NON consuma il budget batteria (4 MJ/giro)
- ✅ NON consuma i bucket ERS
- ❌ È limitata dalla temperatura (thermal clipping)
- ❌ Dipende dal carico motore (throttle %) e dal tipo di sezione

```python
# Fattori MGU-H per tipo di sezione (da power_unit.py V2)
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
    rpm: float
) -> float:
    """Calcola la coppia MGU-H direct per la sezione corrente."""

    # 1. Fattore sezione (meno MGU-H in curva, massimo in rettilineo)
    section_factor = SECTION_MGUH_FACTORS.get(section_kind, 0.5)

    # 2. Proporzionale al throttle (non binario!)
    # A throttle 0% → niente MGU-H direct
    # A throttle 100% → massimo MGU-H direct
    throttle_factor = throttle_pct / 100.0

    # 3. Potenza MGU-H effettiva
    mguh_power_kw = pu_ctx.mguh_power_kw * section_factor * throttle_factor

    # 4. Thermal clipping (stesso derating del MGU-K)
    thermal_eta = _compute_thermal_eta(pu_ctx.ers_temp_c)
    mguh_power_kw *= thermal_eta

    # 5. Budget check
    energy_mj = mguh_power_kw * dt_s / 1000.0
    if energy_mj > pu_ctx.mguh_direct_remaining_mj:
        energy_mj = pu_ctx.mguh_direct_remaining_mj
        mguh_power_kw = energy_mj * 1000.0 / dt_s

    # 6. Converti potenza → coppia
    omega = rpm * 2 * math.pi / 60
    mguh_torque = mguh_power_kw * 1000.0 / max(omega, 1.0)

    # 7. Aggiorna stato
    pu_ctx.mguh_direct_remaining_mj -= energy_mj
    pu_ctx.lap_mguh_direct_mj += energy_mj

    return mguh_torque
```

**Nota**: La coppia MGU-H direct è **inclusa** in $T_{MGU\text{-}K,eff}$, non è un termine separato nella formula di $F_{prop}$.

### 3.6 Bucket Resolution

I file `_HD.json` contengono `section_kind` ma non `bucket_hint` o `corner_exit`. La mappatura sezione→bucket usa euristiche:

```python
def _resolve_bucket(section_kind: str, prev_brake_pct: float, throttle_pct: float) -> str:
    """Determina il bucket ERS per la sezione corrente."""
    # Rettilinei → Primary
    if section_kind in ("Straight", "MediumStraight"):
        return "primary"

    # Uscita curva: era in frenata, ora accelera → Exit
    if prev_brake_pct > 30 and throttle_pct > 50:
        return "exit"

    # Curve veloci → Secondary
    if section_kind in ("UltraFastCorner", "FastCorner"):
        return "secondary"

    # Curve lente → Exit (priorità alla trazione in uscita)
    if section_kind in ("MediumCorner", "SlowCorner", "VerySlowCorner"):
        return "exit"

    # Default
    return "secondary"
```

---

## 4. Harvesting (Ricarica Batteria)

Il documento originale non menzionava il harvesting. Questo è **critico** per il realismo:

- Senza harvesting, il SOC scende monotonamente → la batteria si svuota
- Non c'è clipping → il modello è irrealistico
- Non c'è differenza tra qualifica (SOC→0) e gara (SOC→neutral)

### 4.1 MGU-K Harvest (Frenata → Batteria)

```python
def compute_mguk_harvest(
    pu_ctx: PU_Context,
    brake_pct: float,
    v_ms: float,
    dt_s: float
) -> float:
    """Calcola l'energia recuperata in frenata e aggiorna SOC."""

    if brake_pct < 5:
        return 0.0  # Niente frenata, niente recupero

    # Potenza di recupero proporzionale alla frenata e velocità
    # Max 120 kW MGU-K, ma limitato a 2 MJ/giro per regolamento
    harvest_power_kw = 120.0 * (brake_pct / 100.0)  # Scalare con intensità frenata

    # Limita per budget rimanente
    remaining_harvest_mj = pu_ctx.harvest_mj_per_lap - pu_ctx.lap_harvest_mj
    if remaining_harvest_mj <= 0:
        return 0.0  # Limite regolamentare raggiunto

    max_energy_mj = harvest_power_kw * dt_s / 1000.0
    energy_mj = min(max_energy_mj, remaining_harvest_mj)

    # Overflow: se batteria piena, l'energia è dissipata
    headroom_mj = pu_ctx.battery_capacity_mj - pu_ctx.soc_mj
    energy_stored_mj = min(energy_mj, headroom_mj)
    energy_wasted_mj = energy_mj - energy_stored_mj  # Dissipata se batteria piena

    # Aggiorna stato
    pu_ctx.soc_mj += energy_stored_mj
    pu_ctx.lap_harvest_mj += energy_mj  # Conta tutto, anche dissipato

    return energy_stored_mj
```

### 4.2 MGU-H Harvest (Scarico → Batteria)

L'MGU-H può anche ricaricare la batteria (non solo direct path). La quota ES è determinata da `mguh_es_bias`:

```python
def compute_mguh_es_harvest(
    pu_ctx: PU_Context,
    section_kind: str,
    throttle_pct: float,
    dt_s: float
) -> float:
    """Calcola l'energia MGU-H che va alla batteria (non direct path)."""
    # MGU-H ES bias = 1 - direct_ratio
    es_bias = 1.0 - pu_ctx.mguh_direct_ratio

    # Stima potenza MGU-H totale per la sezione
    section_factor = SECTION_MGUH_FACTORS.get(section_kind, 0.5)
    throttle_factor = throttle_pct / 100.0
    mguh_total_power_kw = pu_ctx.mguh_power_kw * section_factor * throttle_factor

    # Quota ES
    mguh_es_power_kw = mguh_total_power_kw * es_bias
    energy_mj = mguh_es_power_kw * dt_s / 1000.0

    # Overflow check
    headroom_mj = pu_ctx.battery_capacity_mj - pu_ctx.soc_mj
    energy_stored_mj = min(energy_mj, headroom_mj)

    pu_ctx.soc_mj += energy_stored_mj
    return energy_stored_mj
```

---

## 5. Modello Termico e Derating

### 5.1 Bilancio Termico

Ad ogni waypoint, la temperatura ERS evolve:

$$T_{ers}^{(t+dt)} = T_{ers}^{(t)} + \frac{\dot{Q}_{gen} - \dot{Q}_{cool}}{C_{th}} \cdot dt$$

Dove:
- $\dot{Q}_{gen} = k_{joule} \cdot P_{elec}^2$ (calore per effetto Joule)
- $\dot{Q}_{cool} = h_v \cdot v_{car} \cdot (T_{ers} - T_{amb})$ (raffreddamento convettivo)
- $C_{th} = 18.0$ kJ/K (capacità termica)

### 5.2 Parametri

| Parametro | Simbolo | Valore | Unità |
|:---|:---:|:---:|:---:|
| Soglia Inizio Clipping | $T_{limit}$ | 102.0 | °C |
| Soglia Taglio Totale | $T_{max}$ | 122.0 | °C |
| Coefficiente Joule | $k_{joule}$ | 0.000045 | - |
| Coeff. Raffreddamento | $h_v$ | 0.0025 | - |
| Capacità Termica | $C_{th}$ | 18.0 | kJ/K |
| Temperatura Ambiente | $T_{amb}$ | 30.0 | °C |

### 5.3 Derating Factor ($\eta_{th}$)

```python
def _compute_thermal_eta(ers_temp_c: float) -> float:
    """Calcola il fattore di efficienza termica."""
    T_LIMIT = 102.0
    T_MAX = 122.0

    if ers_temp_c < T_LIMIT:
        return 1.0
    elif ers_temp_c >= T_MAX:
        return 0.0
    else:
        return 1.0 - (ers_temp_c - T_LIMIT) / (T_MAX - T_LIMIT)
```

### 5.4 Update Termico per Waypoint

I file HD sono campionati a **5 metri**. A 340 km/h l'auto percorre 5 m in circa **0.053 secondi**. Questo dt è sufficiente per la cinematica, ma il modello termico (con $k_{joule} \cdot P^2$) può oscillare se il passo è troppo grande (aliasing numerico).

**Soluzione**: Sub-stepping termico. Se `dt_s > 0.02s`, dividere il calcolo termico in step da `THERMAL_SUBSTEP_S = 0.01s`:

```python
THERMAL_SUBSTEP_S = 0.01  # s — passo minimo per stabilità termica

def update_thermal_state(pu_ctx: PU_Context, p_elec_kw: float, v_ms: float, dt_s: float):
    """Aggiorna la temperatura ERS per il waypoint corrente, con sub-stepping."""
    K_JOULE = 0.000045
    H_V = 0.0025
    C_TH = 18.0  # kJ/K
    T_AMB = 30.0

    # Sub-stepping per stabilità numerica
    n_steps = max(1, int(math.ceil(dt_s / THERMAL_SUBSTEP_S)))
    sub_dt = dt_s / n_steps

    for _ in range(n_steps):
        q_gen = K_JOULE * (p_elec_kw ** 2)  # W
        q_cool = H_V * v_ms * (pu_ctx.ers_temp_c - T_AMB)  # W
        delta_t = (q_gen - q_cool) / (C_TH * 1000.0) * sub_dt  # kJ/K → J/K

        pu_ctx.ers_temp_c += delta_t
        pu_ctx.ers_temp_c = max(T_AMB, min(pu_ctx.ers_temp_c, 150.0))  # Clamp
```

**Nota**: Il sub-stepping è applicato **solo** al modello termico. La cinematica (forze, accelerazione, velocità) rimane al passo originale di 5 m. Questo perché il modello termico ha una dinamica più veloce (effetto Joule quadratico) rispetto alla cinematica.

---

## 6. Flusso di Integrazione nel Waypoint Integrator

### 6.1 Interfaccia con `integrate_lap_hd`

Aggiungere un parametro opzionale `pu_config` per attivare il modello stateful:

```python
def integrate_lap_hd(
    ...
    ers_power_fraction: float = 1.0,  # Legacy fallback (V5.3 compat)
    pu_config: Optional[Dict] = None,  # NUOVO: attiva modello PU stateful
    ...
):
    if pu_config is not None:
        # Modalità V5.4: PU stateful con torque curve, bucket, thermal
        pu_ctx = init_pu_context(
            circuit_id=circuit_id,
            engine_map=pu_config.get("engine_map", "QUALIFY")
        )
    else:
        # Modalità V5.3 legacy: ers_power_fraction come prima
        pu_ctx = None
```

**Backward compatibility**: Se `pu_config` è `None`, il comportamento è identico al V5.3 (`ers_power_fraction` globale). Questo garantisce che `validate_v53.py` continui a funzionare senza modifiche.

### 6.2 Flusso per Waypoint

Per ogni waypoint nel loop di integrazione:

```python
# Nel loop principale di integrate_lap_hd:
for i in range(len(waypoints) - 1):
    # ... calcolo aero, grip, ecc. (invariato) ...

    if pu_ctx is not None:
        # === MODELLO PU V5.4 ===

        # 1. Ottieni RPM (da Reference Pull o Synthetic Gearbox)
        if pu_lookup_blend > 0 and reference_pull is not None:
            rpm = interpolate_rpm(distance_m, reference_pull)
            n_gear = interpolate_nGear(distance_m, reference_pull)
            gear_ratio = get_gear_ratio_from_nGear(n_gear)
        else:
            n_gear, gear_ratio, rpm = get_optimal_gear(state.velocity_ms)

        # 2. ICE Torque
        ice_torque = lookup_ice_torque(rpm, pu_ctx.ice_power_pct_base)

        # 3. MGU-K Torque (condizionato da bucket + SOC + thermal)
        mguk_torque = compute_mguk_torque(pu_ctx, section_kind, rpm)

        # 4. MGU-H Direct Torque (condizionato da throttle + section + thermal)
        mguh_direct_torque = compute_mguh_direct_torque(
            pu_ctx, section_kind, throttle_pct, rpm
        )

        # 5. Forza propulsiva totale
        total_torque = ice_torque + mguk_torque + mguh_direct_torque
        f_engine = total_torque * gear_ratio * FINAL_DRIVE * DRIVETRAIN_EFFICIENCY / R_WHEEL

        # 6. Harvesting (se in frenata)
        if brake_pct > 5:
            compute_mguk_harvest(pu_ctx, brake_pct, state.velocity_ms, dt_step)
            compute_mguh_es_harvest(pu_ctx, section_kind, throttle_pct, dt_step)

        # 7. Update termico
        p_elec_kw = (mguk_torque + mguh_direct_torque) * rpm * 2 * math.pi / 60 / 1000.0
        update_thermal_state(pu_ctx, p_elec_kw, state.velocity_ms, dt_step)

    else:
        # === MODELLO V5.3 LEGACY ===
        effective_pu_kw = ICE_PEAK_POWER_KW + ERS_PEAK_POWER_KW * ers_power_fraction
        power_available = effective_pu_kw * 1000 * rpm_fraction * (throttle_pct / 100.0)
        power_available *= DRIVETRAIN_EFFICIENCY
        power_available *= driver_skill
        if state.velocity_ms > 1.0:
            f_engine = power_available / state.velocity_ms
        else:
            f_engine = power_available / 1.0
```

---

## 7. Calibrazione e Normalizzazione

### 7.1 Preservare la Calibrazione V5.3

Il V5.3 è calibrato a 0.21% errore medio con `ers_power_fraction=1.0` (910 kW costanti). Il nuovo modello PU avrà potenza variabile per sezione. **Come garantiamo che il tempo giro non cambi?**

**Principio**: L'energia totale erogata nel giro V5.4 deve essere uguale a quella del V5.3:

$$E_{V5.4} = \sum_{i=1}^{N} (P_{ICE,i} + P_{MGU\text{-}K,i} + P_{MGU\text{-}H,i}) \cdot dt_i = E_{V5.3} = 910 \text{ kW} \times t_{lap}$$

Se l'energia totale diverge, si scala $\eta$ (efficienza trasmissione):

```python
# Dopo il giro, calcola energia totale erogata
energy_v54 = sum(p_engine * dt for each waypoint)
energy_v53 = 910000 * lap_time_s  # W × s = J

# Fattore di correzione
eta_correction = energy_v53 / energy_v54
DRIVETRAIN_EFFICIENCY_V54 = 0.96 * eta_correction
```

### 7.2 Validazione

1. **Test di non-regressione**: Eseguire `validate_v53.py` con `pu_config=None` → deve dare 0.21% come prima
2. **Test PU stateful**: Eseguire `validate_v53.py` con `pu_config={"engine_map": "QUALIFY"}` → errore < 0.5%
3. **Test mappe**: QUALIFY < RACE < PRACTICE < SAFETY_CAR (tempi crescenti)
4. **Test SOC**: A fine giro qualifica, SOC ≈ target_soc_end_lap (0.05 = quasi vuoto)
5. **Test thermal**: A Monza, ers_temp_c sale verso 102°C nei rettilinei lunghi

### 7.3 Calibrazione per Circuito

I parametri per-circuito sono già in `config/circuits/derived/<cid>/pu_maps.json`:
- `deploy_mj_per_lap`, `harvest_mj_per_lap` → bilancio energetico
- `bucket_primary_pct`, `bucket_secondary_pct`, `bucket_exit_pct` → distribuzione ERS
- `mguh_direct_ratio`, `mguh_power_kw` → MGU-H per circuito
- `ers_output_kw` → potenza MGU-K massima

**Non serve ricalibrare sospensioni o mu_mechanical** — questi sono indipendenti dalla PU.

---

## 8. Mappe Motore e Parametri

### 8.1 Mappe Disponibili

| Mappa | ICE Power % | ERS Deploy | ERS Harvest | SOC Target | Note |
|:---|:---:|:---:|:---:|:---:|:---|
| **QUALIFY** | 1.08-1.12 | 4.0 MJ | 0.5-0.8 MJ | 0.05 | Batteria quasi vuota a fine giro |
| **RACE** | 0.90-1.00 | 3.4-3.7 MJ | 1.0-1.3 MJ | 0.40 | Bilanciato, SOC stabile |
| **PRACTICE** | 0.75-0.85 | 2.6 MJ | 1.8 MJ | 0.72 | Conservativo |
| **SAFETY_CAR** | 0.40 | 0.6 MJ | 2.2 MJ | 0.92 | Ricarica batteria |
| **ECONOMY** | 0.75-0.85 | 1.5 MJ | 2.0 MJ | 0.80 | Lift and coast |
| **RECHARGE** | 0.40 | 0.5 MJ | 2.0 MJ | 0.98 | VSC/In-lap |

### 8.2 Effetto Atteso sui Tempi

Su Monza (riferimento V5.3: 78.869s con QUALIFY):

| Mappa | Tempo Atteso | Delta vs QUALIFY | Note |
|:---|:---:|:---:|:---|
| QUALIFY | ~78.87s | 0.0s | Riferimento |
| RACE | ~79.5s | +0.6s | Meno ERS, meno ICE |
| PRACTICE | ~80.5s | +1.6s | Molto meno potenza |
| SAFETY_CAR | ~83.0s | +4.1s | Minimo deploy |

Questi delta sono **stime** — vanno validati con il modello.

---

## 9. Dati di Riferimento

### 9.1 Fonti Telemetria

| Fonte | Dati | Uso |
|:---|:---|:---|
| `TracingInsights-Archive/2025` | RPM, nGear, Speed, Throttle, Brake, DRS | Reference Pull (Livello 1) |
| `_Telemetry.json` (locale) | Sezioni, v_ref, throttle, brake | Già usato nel V5.3 |
| `pu_maps.json` (per-circuito) | Mappe, bucket, MGU-H, budget | Parametri PU (Livello 2) |
| `EngineData2025.md` | Torque curve, gear ratios | ICE model + Synthetic Gearbox |

### 9.2 Dati TracingInsights Disponibili

La telemetria estratta contiene per ogni punto:
```json
{
  "rpm": [...],       // RPM reali (5000-12500)
  "gear": [...],      // nGear (1-8) → G_ratio
  "throttle": [...],  // Throttle % (0-100)
  "brake": [...],     // Brake (0/1)
  "speed": [...],     // Speed (km/h)
  "drs": [...]        // DRS status
}
```

**Impatto**: Con `nGear` + `RPM` reali, possiamo calcolare $G_{ratio}$ reale e validare il synthetic gearbox. Il synthetic gearbox rimane come fallback per circuiti senza telemetria.

---

## 10. Implementazione — Piano di Esecuzione

### Fase 1: PU_Context + Torque Model (1-2 giorni)
1. Creare `PU_Context` dataclass in `waypoint_integrator.py`
2. Implementare `init_pu_context()` con caricamento da `pu_maps.json`
3. Implementare torque curve lookup (`ICE_TORQUE_LUT`)
4. Implementare `get_optimal_gear()` (synthetic gearbox)
5. Aggiungere `pu_config` parametro a `integrate_lap_hd()`
6. **Test**: Verificare che `pu_config=None` → comportamento V5.3 identico

### Fase 2: Bucket + SOC + Harvesting (1-2 giorni)
1. Implementare `_resolve_bucket()` con euristiche
2. Implementare `compute_mguk_torque()` con bucket + SOC
3. Implementare `compute_mguk_harvest()` e `compute_mguh_es_harvest()`
4. Implementare `compute_mguh_direct_torque()` (MGU-H direct)
5. **Test**: Verificare SOC a fine giro ≈ target

### Fase 3: Thermal Model (1 giorno)
1. Implementare `update_thermal_state()`
2. Implementare `_compute_thermal_eta()`
3. Integrare thermal clipping in MGU-K e MGU-H
4. **Test**: Verificare temperatura a Monza (deve salire nei rettilinei)

### Fase 4: Calibrazione + Validazione (1-2 giorni)
1. Normalizzazione energetica (scala η se necessario)
2. Validazione su 5 circuiti (Monza, Monaco, Suzuka, Spa, Austin)
3. Test mappe: QUALIFY < RACE < PRACTICE < SAFETY_CAR
4. Aggiornare `validate_v53.py` con opzione `--pu-config`
5. **Target**: Errore < 0.5% con QUALIFY map

### Fase 5: CHECK SETUP Tests (TUTTI dopo V5.4 completato)

**Importante**: Tutti e 6 i test CHECK SETUP devono essere eseguiti **dopo** che il modello PU V5.4 è completamente implementato e validato. Questo perché il modello PU influenza la forza motrice in ogni test — anche i test che non variano la mappa ICE/ERS dipendono dalla corretta modellazione della potenza per avere risultati fisicamente significativi.

**Baseline comune**: McLaren, Norris, Fuel 20kg, Push 10, ICE Qualify, ERS Qualify, Soft compound del circuito

**Circuiti di test**: Monza, Monaco, Suzuka, Spa, Austin

1. **Aero sweep**: Variazione front_wing/rear_wing → delta tempo giro
2. **Suspension sweep**: Variazione spring/ARB/ride_height → delta tempo giro
3. **Fuel load**: 5kg, 10kg, 20kg, 50kg, 110kg → delta tempo giro
4. **Tyre compounds**: C1-C6 su 5 circuiti → delta tempo giro
5. **ICE/ERS mapping**: QUALIFY, RACE, PRACTICE, SAFETY_CAR → delta tempo giro
6. **Push level**: 1-10 → delta tempo giro (penalità additiva via push_penalty.py)

---

## Appendice A: Costanti Fisiche

```python
# Power Unit
ICE_PEAK_POWER_KW = 750.0       # kW (~1000 hp) a 10500 RPM
ERS_PEAK_POWER_KW = 160.0       # kW MGU-K (regolamento 2025)
ERS_MAX_DEPLOY_MJ = 4.0         # MJ deploy max per giro
ERS_MAX_HARVEST_MJ = 2.0        # MJ harvest MGU-K max per giro
BATTERY_CAPACITY_MJ = 4.0       # MJ capacità utile FIA

# Trasmissione
R_WHEEL = 0.334                 # m raggio ruota F1
FINAL_DRIVE = 4.10              # Rapporto finale
DRIVETRAIN_EFFICIENCY = 0.96    # Efficienza trasmissione (calibrabile)
GEAR_RATIOS = [2.53, 1.96, 1.63, 1.40, 1.22, 1.10, 1.01, 0.92]

# Termica
THERMAL_K_JOULE = 0.000045
THERMAL_H_V = 0.0025
THERMAL_C_TH = 18.0             # kJ/K
THERMAL_T_LIMIT = 102.0         # °C
THERMAL_T_MAX = 122.0           # °C
THERMAL_T_AMB = 30.0            # °C

# MGU-H Section Factors
SECTION_MGUH_FACTORS = {
    "Straight": 1.00,
    "MediumStraight": 0.90,
    "UltraFastCorner": 0.85,
    "FastCorner": 0.75,
    "MediumCorner": 0.60,
    "SlowCorner": 0.45,
    "VerySlowCorner": 0.35,
}
```

## Appendice B: Torque Curve ICE (da EngineData2025.md)

| RPM | ICE Torque (Nm) | MGU-K Torque (Nm) | Totale (Nm) | Note |
|:---:|:---:|:---:|:---:|:---|
| 0 | 0 | 200 | 200 | Electric launch |
| 1500 | 180 | 200 | 380 | Turbo spooling |
| 4000 | 480 | 200 | 680 | Traction zone |
| 6500 | 590 | 176 | 766 | Peak acceleration |
| 8500 | 610 | 134 | 744 | Max torque ICE |
| 10500 | 575 | 109 | 684 | Fuel flow limit |
| 11500 | 525 | 99 | 624 | Shift window |
| 12500 | 480 | 91 | 571 | Power dropoff |
| 13500 | 400 | 85 | 485 | Over-rev |

**Nota**: I valori MGU-K nella tabella sono a **potenza massima** (120 kW). Nel modello V5.4, la coppia MGU-K effettiva è scalata per bucket/SOC/thermal.

## Appendice C: Fonti Documentazione

| Documento | Contenuto | Uso nella specifica |
|:---|:---|:---|
| `EngineData2025.md` | Torque curve, gear ratios, fuel flow | §3.3, §3.2, Appendice B |
| `ERS-Bucket-Planner.md` | Bucket system, cap dinamico | §3.4, §3.6 |
| `PU-Engine-MGU-H.md` | MGU-H direct path, limiti regolamentari | §3.5 |
| `ERS-ThermalClipping.md` | Modello termico, derating | §5 |
| `pu-energy-model.md` | SOC tracking, UI, mappe | §2, §8 |
| `engine-penalty-system.md` | Penalty system V2 (da NON usare) | §0 (contesto) |
| `TracingInsights-Archive/2025` | RPM, nGear, throttle reali | §3.2, §9 |