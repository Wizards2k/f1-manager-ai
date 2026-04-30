---
title: Physics Engine V6.4 — Specifica di Integrazione nel Ciclo di Gioco (Opzione A+)
date: 2026-04-29
version: 2.1
author: Claude Sonnet 4.6
status: ✅ IMPLEMENTATA — 8/8 test PASS (commit eecd474, branch feature/lap-simulator-v6)
---

# Physics Engine V6.4 — Integrazione nel Ciclo di Gioco (Opzione A+)

## Sommario Esecutivo

Questo documento descrive la specifica tecnica per integrare il Physics Engine V6.4 nel ciclo di gioco tramite l'**Opzione A+ (Adattatore Per-Sezione con Stato Persistente)**.

**Principio guida**: ogni sezione è calcolata al momento con i parametri correnti. Il `PhysicsState` V6 persiste tra sezioni dello stesso stint, portando termica gomme, usura, SOC ERS e velocità attraverso tutti i giri.

**Aggiornamento v2.0** (2026-04-28): revisione basata su analisi del codebase reale (`session_bridge.py`, `battle_resolver.py`, `practice_session.py`). La maggior parte dell'infrastruttura multi-auto (BattleResolver, pit stop, ERS switching, blue flag, safety car) è già implementata. I gap reali sono 5 punti specifici di collegamento tra il motore V6 e il loop esistente.

---

## 1. Benchmark Performance

### 1.1 Risultati Reali (Monza, 1176 waypoints)

| Metrica | Valore |
|---|---|
| `integrate_waypoint()` avg | **0.096 ms** |
| `integrate_waypoint()` max | 0.280 ms |
| Giro completo (~1176 wp) | **113 ms** |
| Sezione (~39 wp) | **3.7 ms** |

### 1.2 Stima Tick Realistica (20 auto)

`sim_dt = 0.1s × game_speed`. Una sezione dura ~3s di sim time → ogni tick completa ~0.033 sezioni/auto. Con 20 auto e game_speed 1x:

| Game Speed | sim_dt | Sezioni/tick totali (20 auto) | Tempo calcolo/tick | Budget rimanente |
|---|---|---|---|---|
| 1x | 0.1s | ~0.67 | **~2.5 ms** | ~97.5 ms |
| 2x | 0.2s | ~1.33 | **~5.0 ms** | ~95.0 ms |
| 4x | 0.4s | ~2.67 | **~10 ms** | ~90 ms |
| 6x | 0.6s | ~4.00 | **~15 ms** | ~85 ms |

**Nota**: i tick sono stocastici — in un dato tick la maggior parte delle auto non completa una sezione. Il calcolo V6 (~3.7ms/sezione) avviene solo quando `section_time_acc >= effective_dt_ref`. Il budget è ampiamente rispettato.

---

## 2. Architettura Esistente e Punto di Inserimento V6

### 2.1 Tick Loop Attuale (session_bridge.py)

Il tick loop è già strutturato in 4 fasi:

```
SessionBridge.tick(sim_dt)
  ──────────────────────────────────────────────────────
  FASE 1: Advance time
    PSO.tick(sim_dt)                    # clock, flags, pitlane release
    _schedule_ai_runs()                 # schedule run AI da TeamSessionPlan
    QualifyingPhase advance             # Q1→Q2→Q3 se elapsed

  FASE 2: Move cars  [← UNICO PUNTO DI MODIFICA V6]
    _move_cars(sim_dt)
      per ogni auto ON_TRACK:
        accumula section_time_acc += sim_dt
        se sezione completata:
          chiama update_section()        # ← sostituire con update_section_v6()
          aggiorna posizione, settori, giri

  FASE 3: Separation / Battle
    _resolve_battles()
      raggruppa auto per sezione
      rileva prossimità (gap, delta_v)
      BattleResolver.resolve_section()  # sorpassi, side-by-side, collisioni
      compute_dirty_air()               # per ogni coppia in prossimità
      gestisce blue flag (per sessione)
      _enforce_min_gap()

  FASE 4: State commit
    _sync_phases()                      # sync RaceCar, emit socket events
```

### 2.2 Infrastruttura già implementata (NON da ricreare)

| Funzionalità | File | Note |
|---|---|---|
| **BattleResolver** (sorpassi, dirty air, side-by-side) | `lap_simulator/battle_resolver.py` | Chiamato in FASE 3, già integrato |
| **Blue flag** (practice hot lap + race lapped) | `session_bridge.py:_resolve_battles()` | Policy per-sessione già implementata |
| **Safety car** (blocco sorpassi) | `session_bridge.py:_resolve_battles()` | `if pso.clock.flag != GREEN: return` |
| **Pit stop** (player_box_now, tyre reset) | `session_bridge.py:player_box_now()` / `_complete_car_run()` | Include tyre reset, fuel, weekend_orchestrator |
| **ERS mode switching** | `session_bridge.py:ERS_MODE_TO_ENGINE_MAP` + `_sync_ers_mode_state()` | Mappatura canonica già definita |
| **Player push/ERS runtime** | `CarTrackState.selected_ers_mode`, `selected_active_map` | Aggiornati a ogni tick |
| **Team session plans** | `session_bridge.py:_build_team_plans()` | Batch randomizzato, stagger intra-team |
| **Weekend orchestrator** | `utils/weekend_orchestrator.py` | Q1/Q2/Q3 eliminazione, race state, transition machine |

### 2.3 Unico punto di modifica: `update_section()` → `update_section_v6()`

La sostituzione avviene in `_move_cars()` a riga ~1284 di `session_bridge.py`. Tutto il resto del loop (FASE 1, 3, 4) rimane invariato.

---

## 3. I 5 Gap Tecnici da Implementare

Prima di poter chiamare `update_section_v6()`, cinque componenti mancanti devono essere creati o collegati. Sono descritti in dettaglio nelle sezioni successive.

| # | Gap | Dove | Impatto se mancante |
|---|---|---|---|
| **G1** | `compute_v_max_corners()` non precomputata | `init_session()` | Fisica curve incorretta (nessun limite v_max) |
| **G2** | `PhysicsState` assente da `CarTrackState` | `CarTrackState` | Nessuna persistenza tra sezioni (termica/usura persa) |
| **G3** | `PU_Context` reinizializzato per sezione | `update_section_v6()` | SOC ERS azzerato ogni ~3s: modello ERS completamente sbagliato |
| **G4** | `dirty_air_factor` non pipe da FASE 3 a FASE 2 | `_resolve_battles()` → `CarTrackState` → `_move_cars()` | Dirty air calcolato ma mai passato alla fisica V6 |
| **G5** | `drs_gap_ahead_s` non pipe da FASE 3 a FASE 2 | `_resolve_battles()` → `CarTrackState` → `_move_cars()` | DRS attivato/disattivato senza conoscere il gap reale |

---

## 4. G1 — `compute_v_max_corners()`: Precomputazione Dual-Pass

### 4.1 Problema

Il Physics Engine V6 usa un'architettura **dual-pass**:
1. **Planning phase**: `compute_v_max_corners(waypoints_hd, aero, setup, mass)` → calcola il vettore `v_max_corner[n_waypoints]` per l'intero circuito
2. **Integration phase**: `integrate_waypoint()` usa `v_max_corner` come vincolo per ogni waypoint

Se `v_max_corner` non è precomputato, `integrate_waypoint()` non ha i limiti di velocità in curva e produce lap time fisicamente scorretti.

### 4.2 Soluzione: precompute a `init_session()`

`v_max_corner` dipende da: circuito (waypoints HD), assetto aero, massa. **Non cambia durante la gara** (l'assetto è fisso in parc fermé). Va calcolato una volta per circuito.

```python
# In SessionBridge.init_session() — dopo il caricamento sezioni
from lap_simulator.physics_v4.integrator.waypoint_integrator import compute_v_max_corners
from lap_simulator.physics_v4.integrator.io import load_hd_waypoints

# Carica waypoints HD (condivisi per tutte le auto dello stesso circuito)
self._hd_waypoints: List[Dict] = load_hd_waypoints(circuit_id)

# Precomputa v_max_corner con assetto di riferimento (aero neutro, 720kg)
# Ogni auto usa il proprio assetto in update_section_v6(), ma la precomputa
# può essere per-auto se necessario (costo: ~1ms × 20 auto = trascurabile)
self._v_max_corner_array: List[float] = compute_v_max_corners(
    waypoints_hd=self._hd_waypoints,
    aero_assembly=AeroAssembly.from_default(circuit_id),
    mass_kg=720.0,
    air_density=calculate_air_density(self.circuit_config.elevation_m),
)
```

**Nota**: se l'assetto del giocatore varia significativamente (es. Monaco vs Monza), si può ricalcolare `v_max_corner` per-auto a `player_send_out()` e salvarlo in `CarTrackState`. Il costo è ~1ms una tantum.

### 4.3 Waypoints HD: condivisi a livello SessionBridge

I waypoints HD sono uguali per tutte le auto (stessa pista). Si caricano una volta e si condividono:

```python
# In SessionBridge: un solo attributo condiviso
self._hd_waypoints: List[Dict] = []      # caricato in init_session()
self._v_max_corner_array: List[float] = []  # precomputato in init_session()
```

`update_section_v6()` li riceve come parametri (non li ricarica).

**Nota**: l'implementazione v1.0 della spec poneva i waypoints in `CarTrackState` per-auto — questo è ridondante e spreca memoria (20 copie identiche da ~1MB ciascuna).

---

## 5. G2 — `PhysicsState`: Persistenza in `CarTrackState`

### 5.1 Nuovi campi in `CarTrackState`

Solo 4 campi vanno aggiunti al dataclass esistente:

```python
@dataclass
class CarTrackState:
    """Esistente + 4 nuovi campi V6."""

    # ... tutti i campi esistenti invariati ...

    # ── V6 (G2): Stato fisico persistente tra sezioni ──
    physics_state: Optional[PhysicsState] = None

    # ── V6 (G3): PU_Context persistente tra sezioni ──
    pu_ctx: Optional[Any] = None  # PU_Context da pu_stateful_v2

    # ── V6 (G4+G5): Dati inter-auto aggiornati da FASE 3, letti da FASE 2 ──
    dirty_air_factor: float = 0.0           # da BattleResult.dirty_air_penalties
    drs_gap_ahead_s: Optional[float] = None # gap auto davanti in secondi
```

### 5.2 Ciclo di vita di `physics_state`

| Evento | Azione su `physics_state` |
|---|---|
| Prima uscita dai box | `None` → inizializzato da `StateAdapter.car_state_to_physics_state()` |
| Fine sezione (normale) | Aggiornato da `update_section_v6()` e restituito |
| Pit stop (cambio gomme) | Reset parziale: temp gomme → 85°C, wear → 0%, `fuel_remaining_kg` aggiornato |
| Fine stint / rientro box | `physics_state = None` (reset completo per il prossimo stint) |
| Inizio nuovo giro | Nessun reset — velocità e stato fisico continuano naturalmente |

### 5.3 StateAdapter

```python
class StateAdapter:
    """Traduce stato tra CarState (Bridge) e PhysicsState (V6 engine)."""

    @staticmethod
    def car_state_to_physics_state(car_state: CarState, physics_state: PhysicsState) -> None:
        """Chiamato SOLO alla prima sezione (init). Non usare a ogni sezione."""
        physics_state.velocity_ms = car_state.v_current_ms
        if car_state.tyres:
            for wp in WheelPosition:
                tyre = car_state.tyres.get(wp)
                if tyre:
                    tire_state = getattr(physics_state.tires_state, wp.name.lower())
                    tire_state.surface_temp_c = tyre.surface_temp_c
                    tire_state.core_temp_c = tyre.core_temp_c
                    tire_state.wear_pct = tyre.wear_pct
                    tire_state.compound = tyre.compound.value
        if car_state.brakes:
            physics_state.brake_state.temp_front_c = car_state.brakes.temp_front_c
            physics_state.brake_state.temp_rear_c = car_state.brakes.temp_rear_c

    @staticmethod
    def physics_state_to_car_state(physics_state: PhysicsState, car_state: CarState) -> None:
        """Chiamato DOPO ogni sezione completata per sincronizzare il CarState."""
        car_state.v_current_ms = physics_state.velocity_ms
        if physics_state.tires_state:
            for wp in WheelPosition:
                tire_state = getattr(physics_state.tires_state, wp.name.lower())
                if wp in car_state.tyres:
                    car_state.tyres[wp].surface_temp_c = tire_state.surface_temp_c
                    car_state.tyres[wp].core_temp_c = tire_state.core_temp_c
                    car_state.tyres[wp].wear_pct = tire_state.wear_pct
                    car_state.tyres[wp].grip_multiplier = tire_state.grip_multiplier
        if physics_state.brake_state and car_state.brakes:
            car_state.brakes.temp_front_c = physics_state.brake_state.temp_front_c
            car_state.brakes.temp_rear_c = physics_state.brake_state.temp_rear_c
            car_state.brakes.fade_level = physics_state.brake_fade_factor

    @staticmethod
    def apply_pit_stop_reset(physics_state: PhysicsState, new_compound: str, fuel_added_kg: float) -> None:
        """Reset parziale dopo pit stop: nuove gomme + carburante."""
        for wp_name in ("fl", "fr", "rl", "rr"):
            tire_state = getattr(physics_state.tires_state, wp_name)
            tire_state.surface_temp_c = 85.0   # temp pit lane
            tire_state.core_temp_c = 70.0
            tire_state.wear_pct = 0.0
            tire_state.compound = new_compound
        physics_state.fuel_remaining_kg += fuel_added_kg
```

---

## 6. G3 — `PU_Context`: Persistenza e Hot-Swap Engine Map

### 6.1 Problema nella spec v1.0

Il codice originale della spec chiamava `init_pu_context(circuit_id, engine_map)` **all'inizio di ogni sezione**. Questo azzera il SOC della batteria (~2-4 MJ) ogni ~3 secondi di sim time: il modello ERS è completamente inutilizzabile.

### 6.2 Soluzione: `pu_ctx` persistente in `CarTrackState`

```python
# In update_section_v6(): NON fare init_pu_context() per sezione

def update_section_v6(
    ...
    pu_ctx: Optional[PU_Context] = None,  # passato da CarTrackState.pu_ctx
    engine_map: str = "RACE",
    ...
) -> Tuple[SectionResult, PhysicsState, PU_Context]:

    # PU_Context viene dall'esterno (persistente tra sezioni)
    # viene SOLO aggiornato da integrate_waypoint(), non ricreato

    for i, (wp, wp_next) in enumerate(zip(section_waypoints[:-1], section_waypoints[1:])):
        physics_state, pu_ctx = integrate_waypoint(
            ...
            pu_ctx=pu_ctx,       # stesso contesto attraverso tutti i waypoints
            pu_config={"engine_map": engine_map},
            ...
        )

    return section_result, physics_state, pu_ctx   # pu_ctx aggiornato restituito
```

```python
# In _move_cars() — session_bridge_v6.py
result, ts.physics_state, ts.pu_ctx = update_section_v6(
    ...
    pu_ctx=ts.pu_ctx,      # persistente da sezione precedente
    engine_map=ts.current_engine_map,
    ...
)
```

### 6.3 Inizializzazione `pu_ctx`

```python
# In player_send_out() / _dispatch_ai_run() — quando l'auto esce dai box
ts.pu_ctx = init_pu_context(circuit_id=self.circuit_id, engine_map=initial_engine_map)
```

### 6.4 Hot-swap engine map (cambio ERS mode dal giocatore)

Quando il giocatore cambia ERS mode (es. RACE → QUALIFY), il `pu_ctx` corrente ha un SOC preciso che non va perso. La procedura corretta:

```python
def _hot_swap_engine_map(ts: CarTrackState, new_engine_map: str, circuit_id: str) -> None:
    """Cambia engine map preservando il SOC corrente."""
    if ts.pu_ctx is None:
        ts.pu_ctx = init_pu_context(circuit_id, new_engine_map)
        return
    # Preserva SOC, aggiorna i parametri della mappa
    current_soc_mj = ts.pu_ctx.soc_mj  # salva SOC
    ts.pu_ctx = init_pu_context(circuit_id, new_engine_map)
    ts.pu_ctx.soc_mj = current_soc_mj  # ripristina SOC
```

Questa funzione va chiamata in `_sync_ers_mode_state()` quando rileva un cambio di mappa.

---

## 7. G4 — Pipe `dirty_air_factor`: FASE 3 → `CarTrackState` → FASE 2

### 7.1 Situazione attuale

`BattleResolver.resolve_section()` calcola già `BattleResult.dirty_air_penalties: Dict[str, float]` per ogni auto in prossimità. Questo valore viene usato per le decisioni di battaglia (attacco/difesa) ma **non viene passato a `update_section()`** in FASE 2, perché la fisica V1 non ne ha bisogno.

Per V6 invece, `dirty_air_factor` influenza la portanza e il drag in `integrate_waypoint()`.

### 7.2 Soluzione: salvataggio in `CarTrackState` a fine FASE 3

```python
# In _resolve_battles() — dopo resolve_section() — AGGIUNTA V6
def _resolve_battles(self) -> None:
    # ... codice esistente invariato fino alla chiamata BattleResolver ...

    result: BattleResult = self.battle_resolver.resolve_section(
        cars_in_section=cars_with_gaps,
        section=section,
        car_entries=car_entries_in_section,
        section_results=section_results_in_section,
        blue_flag_cars=blue_flag_car_ids,
    )

    # ── V6: salva dirty_air_factor in CarTrackState per il prossimo tick ──
    for car_id_in_section, _, _ in cars_in_section_list:
        ts = self._track_states.get(car_id_in_section)
        if ts is not None:
            ts.dirty_air_factor = result.dirty_air_penalties.get(car_id_in_section, 0.0)

    # ... resto del codice esistente ...
```

### 7.3 Lettura in `_move_cars()` FASE 2

```python
# In _move_cars() — quando si chiama update_section_v6()
result, ts.physics_state, ts.pu_ctx = update_section_v6(
    ...
    dirty_air_factor=ts.dirty_air_factor,  # ← aggiornato dalla FASE 3 del tick precedente
    ...
)
# Il dirty_air_factor del tick corrente sarà aggiornato in FASE 3
# → latenza di 1 tick (~100ms real time) è accettabile
```

**Latenza accettata**: il `dirty_air_factor` usato in FASE 2 è quello calcolato in FASE 3 del tick *precedente* (ritardo ~100ms real time × game_speed). È fisicamente appropriato: la turbolenza della sezione precedente influenza quella corrente.

---

## 8. G5 — Pipe `drs_gap_ahead_s`: FASE 3 → `CarTrackState` → FASE 2

### 8.1 Situazione attuale

`_resolve_battles()` calcola già `on_track_progress` (posizione assoluta di ogni auto) e i gap tra coppie adiacenti. Il gap in secondi si calcola banalmente come `gap_m / v_effective_ms`. Questo dato non viene però salvato per uso in `update_section()`.

### 8.2 Soluzione: calcolo e salvataggio del gap in secondi

```python
# In _resolve_battles() — dopo aver costruito on_track_progress
# on_track_progress: List[Tuple[car_id, CarTrackState, total_progress_m]]
# ordinato per posizione decrescente (leader prima)

on_track_progress.sort(key=lambda x: x[2], reverse=True)

for i, (car_id, ts, progress) in enumerate(on_track_progress):
    if i == 0:
        ts.drs_gap_ahead_s = None  # leader, nessuno davanti
    else:
        leader_id, leader_ts, leader_progress = on_track_progress[i - 1]
        gap_m = leader_progress - progress
        if gap_m < 0:  # wrap-around circuito
            gap_m += self.circuit_config.circuit_length_m
        # Velocità media delle due auto per convertire in secondi
        v_follower = ts.car_entry.state.v_current_ms if ts.car_entry else 50.0
        v_leader = leader_ts.car_entry.state.v_current_ms if leader_ts.car_entry else 50.0
        v_avg = (v_follower + v_leader) / 2.0 if v_avg > 0 else 50.0
        ts.drs_gap_ahead_s = gap_m / max(v_avg, 1.0)
```

### 8.3 Lettura in `_move_cars()` FASE 2

```python
result, ts.physics_state, ts.pu_ctx = update_section_v6(
    ...
    drs_gap_ahead_s=ts.drs_gap_ahead_s,  # ← aggiornato dalla FASE 3 del tick precedente
    ...
)
```

---

## 9. `update_section_v6()` — Specifica Corretta

### 9.1 Firma

```python
def update_section_v6(
    car_state: CarState,
    aero_setup: AeroSetup,
    driver_skills: DriverSkills,
    section: SectionContext,
    env: EnvContext,
    config: CircuitConfig,
    push_level: int = 10,
    delta_aero: float = 0.0,
    delta_grip: float = 0.0,
    apply_baseline_delta: bool = True,
    is_qualifying: bool = False,
    circuit_id: str = "default",
    lap_number: int = 1,
    # ── V6: Dati condivisi (a livello SessionBridge, non per-auto) ──
    waypoints_hd: Optional[List[Dict]] = None,
    v_max_corner_array: Optional[List[float]] = None,
    # ── V6: Stato persistente (da CarTrackState) ──
    physics_state: Optional[PhysicsState] = None,
    pu_ctx: Optional[PU_Context] = None,
    # ── V6: Parametri dinamici (da CarTrackState, aggiornati da FASE 3) ──
    engine_map: str = "RACE",
    dirty_air_factor: float = 0.0,
    drs_gap_ahead_s: Optional[float] = None,
    is_safety_car: bool = False,
) -> Tuple[SectionResult, PhysicsState, PU_Context]:
```

### 9.2 Algoritmo Corretto

```python
def update_section_v6(...):
    # ── 1. Init PhysicsState solo alla prima sezione ──
    if physics_state is None:
        physics_state = PhysicsState(velocity_ms=section.v_entry_kph / 3.6)
        StateAdapter.car_state_to_physics_state(car_state, physics_state)

    # ── 2. Init PU_Context solo al primo uso (NON reinizializzare per sezione) ──
    if pu_ctx is None:
        pu_ctx = init_pu_context(circuit_id, engine_map)

    # ── 3. Estrae waypoints della sezione (da vettore condiviso) ──
    section_waypoints = SectionMapper.extract(
        waypoints_hd, start_m=section_start_m, end_m=section_end_m
    )

    # ── 4. Loop waypoints: integra la fisica ──
    section_start_time = physics_state.time_s

    for wp, wp_next in zip(section_waypoints[:-1], section_waypoints[1:]):
        drs_enabled = (
            lap_number > 1
            and not is_safety_car
            and (is_qualifying or (drs_gap_ahead_s is not None and drs_gap_ahead_s < 1.0))
        )
        physics_state, pu_ctx = integrate_waypoint(
            state=physics_state,
            waypoint=wp,
            next_waypoint=wp_next,
            v_max_corner=v_max_corner_array[wp["waypoint_idx"]] if v_max_corner_array else None,
            aero_assembly=aero_assembly,
            setup=aero_setup_dict,
            mass_kg=mass_kg,
            tyre_compound=compound,
            driver_skill=driver_skill,
            push_level=push_level,
            pu_ctx=pu_ctx,              # ← STESSO pu_ctx attraverso tutti i waypoint
            pu_config={"engine_map": engine_map},
            dirty_air_factor=dirty_air_factor,
            drs_enabled=drs_enabled,
            drs_gap_ahead_s=drs_gap_ahead_s,
            lap_number=lap_number,
        )

    # ── 5. Aggrega in SectionResult ──
    section_dt = physics_state.time_s - section_start_time
    section_result = SectionResult(
        dt_s=section_dt,
        v_exit_kph=physics_state.velocity_ms * 3.6,
        v_entry_kph=section.v_entry_kph,
        # ... altri campi dalla physics_state ...
    )

    # ── 6. Sync PhysicsState → CarState (per compatibilità V1 downstream) ──
    StateAdapter.physics_state_to_car_state(physics_state, car_state)

    return section_result, physics_state, pu_ctx   # pu_ctx aggiornato
```

---

## 10. SectionMapper — Estrazione Waypoints per Sezione

### 10.1 Implementazione con Index Pre-calcolato

Per evitare il linear scan O(n) su 1176 waypoints a ogni sezione, l'indice per sezione viene pre-calcolato a `init_session()`:

```python
# In SessionBridge.init_session() — dopo load_hd_waypoints()
self._section_wp_index: Dict[int, Tuple[int, int]] = {}  # section_idx → (start_wp_idx, end_wp_idx)
for sec_idx, section in enumerate(self.sections):
    start_m = self._section_end_m[sec_idx] - section.length_m
    end_m = self._section_end_m[sec_idx]
    start_idx = bisect.bisect_left(wp_distances, start_m)
    end_idx = bisect.bisect_right(wp_distances, end_m)
    self._section_wp_index[sec_idx] = (start_idx, end_idx)
```

```python
class SectionMapper:
    @staticmethod
    def extract_by_index(
        waypoints_hd: List[Dict],
        start_idx: int,
        end_idx: int,
    ) -> List[Dict]:
        """O(1) extraction usando indici pre-calcolati."""
        result = waypoints_hd[start_idx:end_idx]
        if not result:
            # fallback: restituisce il waypoint più vicino
            mid = (start_idx + end_idx) // 2
            return [waypoints_hd[max(0, min(mid, len(waypoints_hd) - 1))]]
        return result
```

---

## 11. Integrazione in `session_bridge_v6.py`

**Strategia**: creare `session_bridge_v6.py` come copia di `session_bridge.py` con le sole modifiche V6. Il flag `USE_PHYSICS_ENGINE_V6` in `game_logic_v6.py` permette il rollback istantaneo.

### 11.1 Modifiche a `_move_cars()` (unica modifica sostanziale)

```python
# In _move_cars() — session_bridge_v6.py (sostituzione della chiamata update_section)

# ── V6: legge parametri dinamici aggiornati da FASE 3 ──
# ts.selected_active_map è il campo reale in CarTrackState (EngineMapName)
engine_map_str = (
    ts.selected_active_map.value
    if hasattr(ts.selected_active_map, "value")
    else str(ts.selected_active_map or "RACE")
)

# ── V6: chiama update_section_v6() invece di update_section() ──
result, ts.physics_state, ts.pu_ctx = update_section_v6(
    car_state=entry.state,
    aero_setup=entry.aero_setup,
    driver_skills=entry.driver_skills,
    section=section,
    env=self.env,
    config=self.circuit_config,
    push_level=entry.push_level,
    delta_aero=getattr(entry, "delta_aero", 0.0),
    delta_grip=getattr(entry, "delta_grip", 0.0),
    apply_baseline_delta=getattr(entry, "apply_baseline_delta", True),
    is_qualifying=is_qualifying_session,
    circuit_id=self.circuit_id,
    lap_number=ts.lap_number,
    # ── Dati condivisi (a livello bridge) ──
    waypoints_hd=self._hd_waypoints,
    v_max_corner_array=self._v_max_corner_array,
    section_wp_index=self._section_wp_index,
    section_idx=ts.current_section_idx,
    # ── Stato persistente ──
    physics_state=ts.physics_state,
    pu_ctx=ts.pu_ctx,
    # ── Parametri dinamici (da FASE 3 tick precedente) ──
    engine_map=engine_map_str,
    dirty_air_factor=ts.dirty_air_factor,
    drs_gap_ahead_s=ts.drs_gap_ahead_s,
    # self.pso.clock.flag è il campo reale (SessionFlag enum)
    is_safety_car=(
        self.pso.clock.flag != SessionFlag.GREEN
        if self.pso and self.pso.clock else False
    ),
)
```

### 11.2 Aggiunta a `_resolve_battles()` (pipe G4 + G5)

Due punti di inserimento distinti nel metodo esistente:

**G4 — dentro il loop per-sezione** (subito dopo `result = self.battle_resolver.resolve_section(...)`):

```python
# ── V6 G4: pipe dirty_air_penalties → CarTrackState.dirty_air_factor ──
# Nota: all'inizio di _resolve_battles() resettare dirty_air_factor = 0.0
# per tutte le auto (i.e., for cts in self._track_states.values(): cts.dirty_air_factor = 0.0)
# poi qui, dentro il loop delle sezioni, sovrascrivere solo le auto in battaglia:
for car_id_da, penalty in result.dirty_air_penalties.items():
    ts_da = self._track_states.get(car_id_da)
    if ts_da is not None:
        ts_da.dirty_air_factor = float(penalty)
```

**G5 — alla fine di `_resolve_battles()`** (dopo il loop sezioni, usa `on_track_progress` già calcolato nel metodo):

```python
# ── V6 G5: calcola drs_gap_ahead_s per ogni auto in pista ──
# on_track_progress: List[Tuple[car_id, ts, total_progress]] — già calcolato nel metodo
# total_progress = ts.lap_number * circuit_m + ts.distance_in_lap
on_track_sorted = sorted(on_track_progress, key=lambda x: x[2], reverse=True)
# reverse=True → indice 0 = leader (più avanzato), indice -1 = ultimo
for i, (car_id, ts, progress) in enumerate(on_track_sorted):
    if i == 0:
        # Leader: nessuna auto direttamente davanti nel senso DRS
        ts.drs_gap_ahead_s = None
    else:
        _, car_ahead_ts, car_ahead_progress = on_track_sorted[i - 1]
        gap_m = car_ahead_progress - progress  # sempre >= 0 (sort decrescente)
        v_follower = getattr(getattr(ts.car_entry, "state", None), "v_current_ms", 50.0)
        v_leader = getattr(getattr(car_ahead_ts.car_entry, "state", None), "v_current_ms", 50.0)
        v_avg = max((v_follower + v_leader) / 2.0, 1.0)
        ts.drs_gap_ahead_s = gap_m / v_avg
```

### 11.3 Aggiunta a `init_session()` (G1)

**Posizione**: aggiungere DOPO la costruzione di `self._section_end_m` (che avviene dopo `self.sections = self.circuit_config.sections`). Il pre-indice richiede `_section_end_m` già popolato.

```python
# Import paths reali (il modulo si chiama physics_engine, non physics_v4)
import bisect
from lap_simulator.physics_engine.integrator.io import load_hd_waypoints
from lap_simulator.physics_engine.integrator.physics import compute_v_max_corners
from lap_simulator.physics_engine.aero.aero_assembly import AeroAssembly as PhysAero
from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration
from lap_simulator.physics_engine.calibration.circuit_calibration import get_circuit_calibration
from lap_simulator.physics_engine.core.constants import MU_BASE

# Carica waypoints HD e calibrazione circuito
self._hd_waypoints = load_hd_waypoints(circuit_id)
self._aero_calibration = get_aero_calibration(circuit_id)
circuit_cal = get_circuit_calibration(circuit_id) or {}
self._mu_override = circuit_cal.get("mu_override")

# Pre-calcola sezione → indice waypoints (O(1) lookup in _move_cars)
# Richiede self._section_end_m già costruito nel blocco precedente
wp_distances = [wp.get("dist_m", 0.0) for wp in self._hd_waypoints]
self._section_wp_index: Dict[int, Tuple[int, int]] = {}
for sec_idx, sec in enumerate(self.sections):
    start_m = self._section_end_m[sec_idx] - sec.length_m
    end_m = self._section_end_m[sec_idx]
    s_idx = bisect.bisect_left(wp_distances, start_m)
    e_idx = bisect.bisect_right(wp_distances, end_m)
    self._section_wp_index[sec_idx] = (s_idx, e_idx)

# Precomputa v_max_corner con assetto neutro (firma reale di compute_v_max_corners)
# Firma: compute_v_max_corners(waypoints, aero, mu_cal, mass_kg, circuit_id=None)
ref_aero = PhysAero()
ref_aero.set_component_angles({"front_wing": 20.0, "rear_wing": 22.0, "b_wing": 10.0})
if self._aero_calibration:
    k_wing = self._aero_calibration.get("k_wing_coupling")
    if k_wing:
        ref_aero.set_k_wing_coupling(float(k_wing))
mu_cal = MU_BASE.get("C3", 1.82)  # grip di riferimento (C3 = mescola media)
if self._mu_override:
    mu_cal = next(iter(self._mu_override.values()), mu_cal)  # usa primo override disponibile
self._v_max_corner_array = compute_v_max_corners(
    waypoints=self._hd_waypoints,
    aero=ref_aero,
    mu_cal=mu_cal,
    mass_kg=720.0,          # massa di riferimento (media tra vuoto e pieno carburante)
    circuit_id=circuit_id,
)
```

In caso di errore (file HD mancante), inizializzare i tre attributi a lista/dict vuota e loggare un warning.

### 11.4 Reset `pu_ctx` a ogni uscita dai box

```python
# In player_send_out() e _dispatch_ai_run() — prima di aggiungere ts a _track_states
ts.physics_state = None            # G2: reset stato fisico
ts.pu_ctx = init_pu_context(       # G3: init pu_ctx fresco a inizio stint
    circuit_id=self.circuit_id,
    engine_map=initial_engine_map,
)
ts.dirty_air_factor = 0.0          # G4
ts.drs_gap_ahead_s = None          # G5
```

---

## 12. Gestione Eventi Dinamici

Il loop esistente gestisce **già nativamente** gli eventi di gioco. La tabella mostra come ogni evento arriva a `update_section_v6()`:

| Evento | Gestito da | Come arriva a update_section_v6() |
|---|---|---|
| **Cambio push level** (giocatore) | `player_runtime_state` / `CarEntry.push_level` | Parametro `push_level` — effetto immediato alla prossima sezione |
| **Cambio ERS mode** (giocatore) | `_sync_ers_mode_state()` → `ts.selected_ers_mode` | `engine_map=ts.current_engine_map` + `_hot_swap_engine_map()` per SOC |
| **Dirty air da battaglia** | `BattleResolver` in FASE 3 | `ts.dirty_air_factor` → `dirty_air_factor` (G4, ritardo 1 tick) |
| **DRS gap** | Calcolato in FASE 3 da `on_track_progress` | `ts.drs_gap_ahead_s` → `drs_gap_ahead_s` (G5, ritardo 1 tick) |
| **Blue flag** | `_resolve_battles()` già implementato | Nessuna modifica necessaria per V6 |
| **Safety car** | `pso.clock.flag != GREEN` già implementato | `is_safety_car=(self.pso.clock.flag != SessionFlag.GREEN if self.pso else False)` |
| **Pit stop** (giocatore) | `player_box_now()` → `_complete_car_run()` già implementato | Reset `ts.physics_state` + `StateAdapter.apply_pit_stop_reset()` |
| **Fuel carryover** | `physics_state.fuel_remaining_kg` (V6 engine) | Persiste naturalmente in `PhysicsState` tra i giri |

---

## 13. Piano di Implementazione — COMPLETATO ✅

### Fase 1 — Precompute V6 a init_session() ✅
- [x] `load_hd_waypoints()` in `init_session()` → `self._hd_waypoints`
- [x] `compute_v_max_corners()` → `self._v_max_corner_array`
- [x] Pre-indice sezione → waypoints (`self._section_wp_index` con `bisect`)
- [x] `_brake_needed` calcolato via `compute_braking_zones_v6`
- [x] Densità aria ISA (`_air_density`) da `calculate_air_density(elevation_m)`
- [x] Try/except graceful: se fallisce, `_v6_physics_ready = False` e V1 resta attivo

### Fase 2 — `CarTrackState`: 4 nuovi campi ✅
- [x] Aggiunto `physics_state`, `pu_ctx`, `dirty_air_factor`, `drs_gap_ahead_s`
- [x] Aggiornato `to_dict()` / `from_dict()` per serializzazione save/load
- [x] Reset dei 4 campi in `player_send_out()` e `_dispatch_ai_run()`

### Fase 3 — `StateAdapter` e pit stop reset ✅
- [x] Creato `lap_simulator/physics_engine/integrator/state_adapter.py`
- [x] Implementato `car_state_to_physics_state()`, `physics_state_to_car_state()`, `apply_pit_stop_reset()`
- [x] Mapping wheel LF/RF/LR/RR ↔ fl/fr/rl/rr tra CarState e PhysicsState

### Fase 4 — `update_section_v6()` ✅
- [x] Creato `lap_simulator/update_section_v6.py`
- [x] Firma compatibile con `update_section()` + parametri V6 aggiuntivi
- [x] Estrazione waypoints O(1) via `section_wp_index[section_idx]`
- [x] Loop waypoints con `pu_ctx` passato e restituito (non reinizializzato)
- [x] `_hot_swap_engine_map()` in `_sync_ers_mode_state()` (preserva SOC)
- [x] Telemetria pulita dopo ogni sezione (evita accumulo infinito)

### Fase 5 — Pipe G4+G5 in `_resolve_battles()` ✅
- [x] Reset `dirty_air_factor = 0.0` per tutte le auto a inizio `_resolve_battles()`
- [x] Salvataggio `dirty_air_factor` in `CarTrackState` dopo `resolve_section()`
- [x] Calcolo e salvataggio `drs_gap_ahead_s` da `on_track_progress` (gap_m / v_avg)

### Fase 6 — Integrazione Bridge ✅
- [x] Feature flag `USE_PHYSICS_V6 = os.getenv("USE_PHYSICS_V6", "0")` in `session_bridge.py`
- [x] Branch V6 in `_move_cars()`: HOT_LAP + `_v6_physics_ready` → `update_section_v6()`
- [x] Fallback V1 automatico se `_v6_physics_ready=False` o fase non HOT_LAP

### Fase 7 — Testing e Validazione ✅
- [x] T1: lap time V6=81.496s vs ref=81.433s → delta 0.1% ✅
- [x] T2: termica gomme persiste tra 6 sezioni (non azzera) ✅
- [x] T3: SOC QUALIFY 4.000 → 0.080 MJ (monotonicamente decrescente) ✅
- [x] T3b: QUALIFY deploya >= RACE (4.023 vs 3.124 MJ) ✅
- [x] T4: dirty_air_factor pipe G4 funziona correttamente ✅
- [x] T5: DRS gap=0.5s→True, gap=2.0s→False ✅
- [x] T6: pit stop reset FL 85°C 0% wear, freni 20°C ✅
- [x] T7: performance 20 auto 6x → avg 11.7ms/tick, worst=46.7ms < 50ms ✅

**Completato**: 2026-04-29 | **Commit implementazione**: `3ddf393` | **Commit test suite**: `eecd474`

---

## 14. Rischi e Mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| `v_max_corner_array` sbagliato per assetti estremi | Media | Medio | Precompute con assetto neutro come baseline; ricalcolo per-auto opzionale a `player_send_out()` |
| `pu_ctx` corrotto dopo save/load | Media | Medio | `to_dict()`/`from_dict()` per `PU_Context`; se manca, reinit fresco a resume |
| Lap time V6 diverge da V1 > 1s | Bassa | Alto | Test comparativo obbligatorio in Fase 7 prima del deploy |
| Performance > 50ms/tick a 6x | Bassa | Alto | Il modello a-sezioni non calcola V6 ogni tick ma solo quando sezione completata |
| `dirty_air_factor` ritardo 1 tick | Bassa | Basso | Fisicamente accettabile: la turbolenza persiste da una sezione all'altra |
| `drs_gap_ahead_s` impreciso per sorpasso completato | Media | Basso | DRS segue la posizione aggiornata — se sorpasso in tick precedente, gap aggiornato correttamente in FASE 3 |

---

## 15. Conclusione

L'integrazione richiede **5 modifiche specifiche** al codebase esistente. L'infrastruttura multi-auto (BattleResolver, pit stop, ERS switching, blue flag, safety car, team scheduling) è **già implementata e non va toccata**.

Il "collante" da aggiungere è:

```
init_session():
  G1 → load_hd_waypoints + compute_v_max_corners + pre-index sezioni

CarTrackState:
  G2 → physics_state: Optional[PhysicsState]
  G3 → pu_ctx: Optional[PU_Context]
  G4 → dirty_air_factor: float
  G5 → drs_gap_ahead_s: Optional[float]

_resolve_battles() (aggiunta a fine metodo):
  G4 → salva BattleResult.dirty_air_penalties in ts.dirty_air_factor
  G5 → calcola gap_m / v_avg e salva in ts.drs_gap_ahead_s

_move_cars() (sostituzione chiamata update_section):
  update_section() → update_section_v6(
      waypoints_hd=self._hd_waypoints,
      v_max_corner_array=self._v_max_corner_array,
      physics_state=ts.physics_state,
      pu_ctx=ts.pu_ctx,
      dirty_air_factor=ts.dirty_air_factor,
      drs_gap_ahead_s=ts.drs_gap_ahead_s,
  )
```

---

## 16. Test Suite — Risultati Completi (commit eecd474)

**File:** `python_backend/test_v6_integration.py` — 8/8 PASS

| Test | Descrizione | Risultato |
|---|---|---|
| **T1** | Lap time V6 section-by-section vs `integrate_lap_hd()` | 81.496s vs 81.433s, delta **0.1%** ✅ |
| **T2** | Tyre thermal persistence: temp accumula tra 6 sezioni | Mai resettata tra sezioni ✅ |
| **T3** | SOC ERS QUALIFY: monotonicamente decrescente | 4.000 → 0.080 MJ (depleted 4.023 MJ) ✅ |
| **T3b** | QUALIFY deploya >= RACE | 4.023 MJ vs 3.124 MJ ✅ |
| **T4** | Dirty air pipe G4 | `dirty_air_factor > 0` correttamente propagato ✅ |
| **T5** | DRS activation | gap=0.5s → DRS=True, gap=2.0s → DRS=False ✅ |
| **T6** | Pit stop reset | FL 85°C, wear 0%, freni 20°C ✅ |
| **T7** | Performance 20 auto 6x game_speed | avg 11.7ms/tick, E[tick]=23ms, worst=46.7ms < 50ms ✅ |

**Bug fix identificato e risolto:** `Waypoint.telemetry_mu` mancante nel dataclass causava `TypeError` in `load_circuit_config()`. Aggiunto `telemetry_mu: float = 0.0` in `data_types.py`.

---

## Appendice A: File Creati/Modificati

| File | Azione | Descrizione |
|---|---|---|
| `lap_simulator/update_section_v6.py` | **CREATO** (commit 3ddf393) | Orchestratore per-sezione con V6 engine |
| `lap_simulator/physics_engine/integrator/state_adapter.py` | **CREATO** (commit 3ddf393) | Traduzione CarState ↔ PhysicsState + pit reset |
| `utils/session_bridge.py` | **MODIFICATO** (commit 3ddf393) | Feature flag USE_PHYSICS_V6, CarTrackState G2-G5, init_session G1, _move_cars branch V6/V1, _resolve_battles pipe G4+G5 |
| `lap_simulator/data_types.py` | **MODIFICATO** (commit eecd474) | Aggiunto `Waypoint.telemetry_mu: float = 0.0` |
| `test_v6_integration.py` | **CREATO** (commit eecd474) | Suite 8 test di integrazione (8/8 PASS) |

## Appendice B: Dipendenze V6 Engine

Il modulo fisico si trova in `lap_simulator/physics_engine/` (non `physics_v4`).

| Import | Simbolo |
|---|---|
| `lap_simulator.physics_engine.integrator.waypoint` | `integrate_waypoint()` |
| `lap_simulator.physics_engine.integrator.state` | `PhysicsState` |
| `lap_simulator.physics_engine.integrator.io` | `load_hd_waypoints()` |
| `lap_simulator.physics_engine.integrator.physics` | `compute_v_max_corners()` |
| `lap_simulator.physics_engine.integrator.pu_stateful_v2` | `PU_Context`, `init_pu_context()` |
| `lap_simulator.physics_engine.aero.aero_assembly` | `AeroAssembly` |
| `lap_simulator.physics_engine.calibration.aero_calibration` | `get_aero_calibration()` |
| `lap_simulator.physics_engine.calibration.circuit_calibration` | `get_circuit_calibration()` |
| `lap_simulator.physics_engine.core.constants` | `MU_BASE`, `calculate_air_density()` |
| `lap_simulator.data_types` | `CarState`, `SectionResult`, `SectionContext` |

Nota: `waypoint_integrator.py` è un facade di backward-compat che re-esporta tutto dal package — usare i moduli diretti sopra.

---

**Documento:** Specifica di Integrazione Opzione A+  
**Redatto:** 2026-04-28  
**Aggiornato:** 2026-04-29 (v2.1 — implementazione completa, 8/8 test PASS)  
**Version:** 2.1  
**Status:** ✅ IMPLEMENTATA — commit 3ddf393 (G1-G5) + eecd474 (8/8 test), branch feature/lap-simulator-v6
