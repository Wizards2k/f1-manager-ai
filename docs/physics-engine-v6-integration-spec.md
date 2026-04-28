---
title: Physics Engine V6.4 — Specifica di Integrazione nel Ciclo di Gioco (Opzione A+)
date: 2026-04-28
version: 1.0
author: Claude Opus 4.7
status: 🟡 SPECIFICA — In attesa di implementazione
---

# Physics Engine V6.4 — Integrazione nel Ciclo di Gioco (Opzione A+)

## Sommario Esecutivo

Questo documento descrive la **specifica tecnica completa** per integrare il Physics Engine V6.4 nel ciclo di gioco esistente (SessionBridge V1) tramite l'**Opzione A+ (Adattatore Per-Sezione con Stato Persistente)**.

**Scoperta chiave**: `integrate_waypoint()` impiega solo **~0.1ms** per waypoint. L'approccio per-sezione è perfettamente fattibile: **~2.5ms/tick a game_speed 1x**, **~15ms a 6x**, ben dentro il budget di 100ms.

**Principio guida**: ogni sezione è calcolata al momento con i parametri correnti. Questo gestisce **nativamente** l'interazione in tempo reale del giocatore (push level, ERS, engine map) e gli eventi dinamici (battaglie, blue flags, pit stop, meteo).

---

## 1. Benchmark Performance

### 1.1 Risultati Reali (Monza, 1176 waypoints)

| Metrica | Valore |
|---|---|
| `integrate_waypoint()` avg | **0.096 ms** |
| `integrate_waypoint()` max | 0.280 ms |
| Giro completo (~1176 wp) | **113 ms** |
| Sezione (~39 wp) | **3.7 ms** |

### 1.2 Stima Tick Realistica

Assumendo: 20 auto, 30 sezioni/giro, tempo giro 90s, waypoints HD caricati in memoria.

| Game Speed | sim_dt | Sezioni completate/tick | Tempo calcolo/tick | Budget rimanente |
|---|---|---|---|---|
| 1x | 0.1s | 0.67 | **2.5 ms** | 97.5 ms |
| 2x | 0.2s | 1.33 | **5.0 ms** | 95.0 ms |
| 4x | 0.4s | 2.67 | **10.1 ms** | 89.9 ms |
| 6x | 0.6s | 4.00 | **15.1 ms** | 84.9 ms |

**Conclusione**: il calcolo fisico occupa solo il **2-15%** del budget tick. Largamente fattibile.

---

## 2. Architettura di Integrazione

### 2.1 Diagramma del Flusso

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SESSION BRIDGE (Loop Tick)                          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  TICK LOOP (ogni 100ms)                                                ││
│  │  Per ogni auto ON_TRACK:                                               ││
│  │    1. Accumula dt nella sezione corrente                               ││
│  │    2. Se sezione completata:                                           ││
│  │       a. Estrae waypoints HD della sezione                             ││
│  │       b. Per ogni waypoint: integrate_waypoint(physics_state)          ││
│  │       c. Aggrega risultati in SectionResult                            ││
│  │       d. Committa stato fisico in CarState                             ││
│  │    3. Interpola posizione per tick                                     ││
│  │    4. Gestisce eventi dinamici (battaglie, blue flags)                ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                          │                   │
│  ┌───────────────────────────────────────────────────────┘                   │
│  ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  FRONTEND (Socket.IO race_update)                                      ││
│  │  Formato dati INVARIATO — stesso di ora                                ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Componenti Principali

| Componente | File | Descrizione |
|---|---|---|
| `update_section_v6()` | `lap_simulator/update_section_v6.py` | Orchestratore che sostituisce `update_section()` |
| `SectionMapper` | `lap_simulator/physics_engine/integrator/section_mapper.py` | Estrae waypoints HD per una sezione |
| `StateAdapter` | `lap_simulator/physics_engine/integrator/state_adapter.py` | Traduce `CarState` ↔ `PhysicsState` |
| `PU_Context` persistente | Modificato in `CarTrackState` | Mantiene stato ERS tra le sezioni |

---

## 3. update_section_v6() — Specifica Completa

### 3.1 Firma

```python
def update_section_v6(
    car_state: CarState,
    aero_setup: AeroSetup,
    driver_skills: DriverSkills,
    section: SectionContext,
    env: EnvContext,
    config: CircuitConfig,
    push_level: int = 10,
    airflow_penalty: float = 0.0,
    traffic_v_max_kph: float = 0.0,
    delta_aero: float = 0.0,
    delta_grip: float = 0.0,
    apply_baseline_delta: bool = True,
    is_qualifying: bool = False,
    circuit_id: str = "default",
    driver_id: str = "default",
    lap_number: int = 1,
    setup_sliders: Optional[Dict[str, int]] = None,
    ideal_setup_sliders: Optional[Dict[str, int]] = None,
    # ── V6: Stato fisico persistente ──
    physics_state: Optional[PhysicsState] = None,
    waypoints_hd: Optional[List[Dict]] = None,
    # ── V6: Parametri dinamici (possono cambiare tra le sezioni) ──
    ers_mode: str = "STANDARD",
    engine_map: str = "RACE",
    dirty_air_factor: float = 0.0,
    drs_gap_ahead_s: Optional[float] = None,
) -> Tuple[SectionResult, PhysicsState]:
    """
    Calcola la fisica per una sezione usando il Physics Engine V6.4.
    
    Args:
        physics_state: Stato fisico persistente dall'ultima sezione.
                      Se None, inizializza uno stato nuovo.
        waypoints_hd: Lista waypoints HD del circuito (caricati una volta).
        ers_mode: Modalità ERS corrente (può cambiare tra le sezioni).
        engine_map: Mappa motore corrente (può cambiare tra le sezioni).
        dirty_air_factor: Fattore dirty air da battaglie (0-1).
        drs_gap_ahead_s: Gap all'auto davanti in secondi (per DRS in gara).
    
    Returns:
        Tuple[SectionResult, PhysicsState]: Risultato sezione + nuovo stato fisico.
    """
```

### 3.2 Algoritmo

```python
def update_section_v6(...):
    # 1. Inizializza PhysicsState se necessario
    if physics_state is None:
        physics_state = PhysicsState(
            velocity_ms=section.v_entry_kph / 3.6,
            distance_m=section_start_m,
            time_s=0.0,
        )
        # Inizializza stato gomme/freni da CarState
        StateAdapter.car_state_to_physics_state(car_state, physics_state)
    
    # 2. Estrae waypoints HD per questa sezione
    section_waypoints = SectionMapper.extract(
        waypoints_hd, 
        start_m=section_start_m, 
        end_m=section_end_m
    )
    
    # 3. Configura PU_Context per questa sezione
    pu_config = {"engine_map": engine_map}
    pu_ctx = init_pu_context(circuit_id, engine_map)
    
    # 4. Per ogni waypoint, integra la fisica
    section_start_time = physics_state.time_s
    max_velocity_in_section = 0.0
    
    for i, (wp, wp_next) in enumerate(zip(section_waypoints[:-1], section_waypoints[1:])):
        # DRS activation (V6.4)
        drs_enabled = (lap_number > 1 and not is_safety_car and 
                        (is_qualifying or (drs_gap_ahead_s is not None and drs_gap_ahead_s < 1.0)))
        
        physics_state = integrate_waypoint(
            state=physics_state,
            waypoint=wp,
            next_waypoint=wp_next,
            aero=aero_assembly,
            setup=aero_setup_dict,
            mass_kg=mass_kg,
            tyre_compound=compound,
            driver_skill=driver_skill,
            ers_power_fraction=ers_power_fraction,
            pu_config=pu_config,
            pu_ctx=pu_ctx,
            drs_enabled=drs_enabled,
            drs_gap_ahead_s=drs_gap_ahead_s,
            lap_number=lap_number,
            # ... altri parametri
        )
        
        max_velocity_in_section = max(max_velocity_in_section, physics_state.velocity_ms)
    
    # 5. Aggrega risultati in SectionResult
    section_dt = physics_state.time_s - section_start_time
    section_result = SectionResult(
        dt_s=section_dt,
        v_exit_kph=physics_state.velocity_ms * 3.6,
        v_max_kph=max_velocity_in_section * 3.6,
        v_entry_kph=section.v_entry_kph,
        v_effective_kph=(section.v_entry_kph + physics_state.velocity_ms * 3.6) / 2,
        telemetry_points=_extract_telemetry(physics_state),
        # ... altri campi
    )
    
    # 6. Committa stato fisico in CarState
    StateAdapter.physics_state_to_car_state(physics_state, car_state)
    
    return section_result, physics_state
```

---

## 4. SectionMapper — Estrazione Waypoints per Sezione

### 4.1 Firma

```python
class SectionMapper:
    """Estrae waypoints HD per una sezione del circuito."""
    
    @staticmethod
    def extract(
        waypoints_hd: List[Dict],
        start_m: float,
        end_m: float,
        inclusive: bool = True,
    ) -> List[Dict]:
        """
        Estrae i waypoints compresi tra start_m e end_m.
        
        Args:
            waypoints_hd: Lista waypoints HD del circuito (ordinati per distanza).
            start_m: Distanza iniziale della sezione [m].
            end_m: Distanza finale della sezione [m].
            inclusive: Se True, include i waypoints ai bordi.
        
        Returns:
            Lista waypoints HD per la sezione.
        """
```

### 4.2 Implementazione

```python
@staticmethod
def extract(waypoints_hd: List[Dict], start_m: float, end_m: float, inclusive: bool = True) -> List[Dict]:
    result = []
    for wp in waypoints_hd:
        dist = wp.get('dist_m', 0.0)
        if inclusive:
            if start_m <= dist <= end_m:
                result.append(wp)
        else:
            if start_m < dist < end_m:
                result.append(wp)
    
    # Assicura che ci sia almeno un waypoint
    if not result and waypoints_hd:
        # Trova il waypoint più vicino a start_m
        closest = min(waypoints_hd, key=lambda wp: abs(wp.get('dist_m', 0.0) - start_m))
        result.append(closest)
    
    return result
```

### 4.3 Caricamento Waypoints HD

I waypoints HD vengono caricati **una sola volta** all'inizio della sessione e memorizzati in `CarTrackState`:

```python
# In SessionBridge.init_session()
for car_id, ts in self._track_states.items():
    ts.circuit_waypoints = load_hd_waypoints(self.circuit_id)
```

---

## 5. StateAdapter — Traduzione Stato

### 5.1 CarState → PhysicsState

```python
class StateAdapter:
    """Traduce stato tra il mondo del Bridge (CarState) e Physics Engine (PhysicsState)."""
    
    @staticmethod
    def car_state_to_physics_state(car_state: CarState, physics_state: PhysicsState) -> None:
        """Inizializza PhysicsState da CarState (solo alla prima sezione)."""
        # Velocità
        physics_state.velocity_ms = car_state.v_current_ms
        
        # Gomme
        if car_state.tyres:
            for wp in WheelPosition:
                tyre = car_state.tyres.get(wp)
                if tyre:
                    wheel_attr = wp.name.lower()
                    tire_state = getattr(physics_state.tires_state, wheel_attr)
                    tire_state.surface_temp_c = tyre.surface_temp_c
                    tire_state.core_temp_c = tyre.core_temp_c
                    tire_state.wear_pct = tyre.wear_pct
                    tire_state.compound = tyre.compound.value
        
        # Freni
        if car_state.brakes:
            physics_state.brake_state.temp_front_c = car_state.brakes.temp_front_c
            physics_state.brake_state.temp_rear_c = car_state.brakes.temp_rear_c
        
        # Fuel (influenza massa)
        # La massa è gestita separatamente, ma il fuel è implicito in mass_kg
```

### 5.2 PhysicsState → CarState

```python
    @staticmethod
    def physics_state_to_car_state(physics_state: PhysicsState, car_state: CarState) -> None:
        """Scrive stato fisico dal Physics Engine nel CarState del Bridge."""
        # Velocità
        car_state.v_current_ms = physics_state.velocity_ms
        
        # Gomme
        if physics_state.tires_state:
            for wp in WheelPosition:
                wheel_attr = wp.name.lower()
                tire_state = getattr(physics_state.tires_state, wheel_attr)
                if wp in car_state.tyres:
                    car_state.tyres[wp].surface_temp_c = tire_state.surface_temp_c
                    car_state.tyres[wp].core_temp_c = tire_state.core_temp_c
                    car_state.tyres[wp].wear_pct = tire_state.wear_pct
                    car_state.tyres[wp].grip_multiplier = tire_state.grip_multiplier
        
        # Freni
        if physics_state.brake_state and car_state.brakes:
            car_state.brakes.temp_front_c = physics_state.brake_state.temp_front_c
            car_state.brakes.temp_rear_c = physics_state.brake_state.temp_rear_c
            car_state.brakes.fade_level = physics_state.brake_fade_factor
```

---

## 6. Gestione Eventi Dinamici

L'approccio per-sezione gestisce **nativamente** gli eventi dinamici senza invalidazione o ricalcolo:

| Evento | Parametro | Effetto su `integrate_waypoint()` |
|---|---|---|
| **Cambio push level** | `push_level` | Influenza `v_max_corner` (safety factor) e throttle pace |
| **Cambio ERS mode** | `ers_mode` → `engine_map` | Cambia deploy ERS e potenza ICE nella prossima sezione |
| **Cambio engine map** | `engine_map` | Cambia potenza, consumo, e thermal profile |
| **Battaglia / dirty air** | `dirty_air_factor` | Riduce `v_max` e aumenta drag |
| **Blue flag** | `traffic_v_max_kph` | Limita velocità massima |
| **Pit stop** | `v_max` limitato | Bridge gestisce pit lane, Physics Engine riceve v_max=80kph |
| **Cambio meteo** | `env` | Modifica `mu_mechanical`, `air_density`, grip |
| **DRS** | `drs_gap_ahead_s` | Attiva DRS se gap < 1.0s e in zona DRS |

**Nessuna invalidazione necessaria**: ogni sezione è calcolata al momento con i parametri correnti.

---

## 7. SessionBridge V6 — File Separato

**Principio**: invece di modificare `session_bridge.py` esistente, si crea `session_bridge_v6.py` come copia con le modifiche V6. Questo permette:
- **Switch istantaneo** tra V1 e V6 cambiando un import
- **Rollback immediato** senza modifiche al codice V1
- **A/B testing** parallelo

### 7.1 Creazione session_bridge_v6.py

```bash
# Copia il file esistente
cp utils/session_bridge.py utils/session_bridge_v6.py
```

### 7.2 Modifiche a session_bridge_v6.py

#### CarTrackState — Nuovi Campi

```python
@dataclass
class CarTrackState:
    """Stato tracciamento auto nel bridge V6 (esistente + nuovi campi V6)."""
    
    # ... campi esistenti da session_bridge.py ...
    
    # ── V6: Stato fisico persistente ──
    physics_state: Optional[PhysicsState] = None
    
    # ── V6: Waypoints HD del circuito (caricati una volta) ──
    circuit_waypoints: Optional[List[Dict]] = None
    
    # ── V6: Parametri fisici correnti (per eventi dinamici) ──
    current_push_level: int = 10
    current_ers_mode: str = "STANDARD"
    current_engine_map: str = "RACE"
    dirty_air_factor: float = 0.0
```

#### _move_cars() — Integrazione V6

```python
def _move_cars(self, sim_dt: float) -> None:
    # ... codice esistente da session_bridge.py ...
    
    for car_id, ts in list(self._track_states.items()):
        # ... check PSO phase, pit exit, etc. ...
        
        # ── V6: Sincronizza parametri dinamici ──
        ts.current_push_level = entry.push_level
        ts.current_ers_mode = _normalize_ers_mode_name(ts.selected_ers_mode) or "STANDARD"
        ts.current_engine_map = _resolve_engine_map_for_ers_mode(ts.selected_ers_mode) or "RACE"
        
        # ── V6: Chiama update_section_v6() ──
        result, ts.physics_state = update_section_v6(
            car_state=entry.state,
            aero_setup=entry.aero_setup,
            driver_skills=entry.driver_skills,
            section=section,
            env=self.env,
            config=self.circuit_config,
            push_level=entry.push_level,
            # ... altri parametri ...
            physics_state=ts.physics_state,
            waypoints_hd=ts.circuit_waypoints,
            ers_mode=ts.current_ers_mode,
            engine_map=ts.current_engine_map.value if hasattr(ts.current_engine_map, 'value') else str(ts.current_engine_map),
            dirty_air_factor=ts.dirty_air_factor,
            drs_gap_ahead_s=self._get_drs_gap_ahead(car_id),
            lap_number=ts.lap_number,
        )
        
        # ... resto del codice identico a session_bridge.py ...
```

### 7.3 Switch V1/V6 — game_logic_v6.py

**Principio**: invece di modificare `game_logic.py`, si crea `game_logic_v6.py` che importa il bridge V6.

```python
# utils/game_logic_v6.py
"""Game Logic con Physics Engine V6.

Questo file è una copia di game_logic.py che usa session_bridge_v6 invece di session_bridge.
Per tornare al V1, basta cambiare l'import in f1_manager_ai.py:
    from utils.game_logic import ...          # V1
    from utils.game_logic_v6 import ...       # V6
"""

from utils.game_logic import *  # Importa tutto dal V1

# Override: usa SessionBridge V6
from utils.session_bridge_v6 import SessionBridge as SessionBridgeV6

def get_session_bridge():
    """Restituisce il SessionBridge V6."""
    global session_bridge
    if session_bridge is None:
        session_bridge = SessionBridgeV6()
    return session_bridge

# Flag per logging/debug
USE_PHYSICS_ENGINE_V6 = True
```

### 7.4 Switch in f1_manager_ai.py

```python
# Per usare V1:
from utils.game_logic import get_session_bridge, get_game_speed, ...

# Per usare V6:
from utils.game_logic_v6 import get_session_bridge, get_game_speed, ...
```

**Nessuna altra modifica necessaria** — `f1_manager_ai.py` chiama `get_session_bridge()` che restituisce l'istanza corretta (V1 o V6).

---

## 8. Piano di Implementazione

### Fase 1: SectionMapper (1 giorno)
- [ ] Creare `lap_simulator/physics_engine/integrator/section_mapper.py`
- [ ] Implementare `SectionMapper.extract()`
- [ ] Test con tutti i 24 circuiti

### Fase 2: StateAdapter (1-2 giorni)
- [ ] Creare `lap_simulator/physics_engine/integrator/state_adapter.py`
- [ ] Implementare `car_state_to_physics_state()`
- [ ] Implementare `physics_state_to_car_state()`
- [ ] Test bidirezionale con dati reali

### Fase 3: update_section_v6() (2-3 giorni)
- [ ] Creare `lap_simulator/update_section_v6.py`
- [ ] Implementare firma compatibile con `update_section()`
- [ ] Integrare `integrate_waypoint()` per ogni waypoint
- [ ] Aggregare risultati in `SectionResult`
- [ ] Gestire PU_Context persistente

### Fase 4: Integrazione Bridge (1-2 giorni)
- [ ] Copiare `session_bridge.py` → `session_bridge_v6.py`
- [ ] Aggiungere campi V6 a `CarTrackState` in `session_bridge_v6.py`
- [ ] Modificare `_move_cars()` in `session_bridge_v6.py` per usare `update_section_v6()`
- [ ] Creare `game_logic_v6.py` con import di `session_bridge_v6`
- [ ] Test switch V1/V6 cambiando import in `f1_manager_ai.py`

### Fase 5: Eventi Dinamici (1-2 giorni)
- [ ] Passare parametri dinamici a `update_section_v6()`
- [ ] Gestire dirty_air_factor da battaglie
- [ ] Gestire DRS gap-based
- [ ] Test con scenari: cambio push, battaglia, pit stop

### Fase 6: Testing e Validazione (2-3 giorni)
- [ ] Test comparativo V1 vs V6: tempi giri
- [ ] Test performance: 20 auto a game_speed 1x-6x
- [ ] Test frontend: formato dati invariato
- [ ] Test regressione: qualifica, gara, practice
- [ ] Test interazione giocatore in tempo reale

**Totale stimato**: 8-13 giorni

---

## 9. Rischi e Mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| Performance insufficiente | Bassa | Alto | Benchmark conferma ~2.5ms/tick. Se necessario: caching aero forces, ottimizzazione loop |
| Incompatibilità stato | Media | Medio | Mappatura esplicita con fallback, test unitari per ogni campo |
| Regressione frontend | Bassa | Alto | Flag feature toggle `USE_PHYSICS_ENGINE_V6`, fallback automatico a V1 |
| PU_Context tra sezioni | Media | Medio | Persistere `PU_Context` in `CarTrackState`, test ERS deploy/harvest |
| Mapper sezione-waypoint inaccurato | Media | Medio | Verificare con tutti i circuiti, usare `find_section_id_by_distance()` come fallback |
| Stato gomme diverso tra V1 e V6 | Media | Medio | Test comparativo usura/temperatura, calibrazione parametri |

---

## 10. Conclusione

L'**Opzione A+ (Adattatore Per-Sezione con Stato Persistente)** è la soluzione raccomandata per integrare il Physics Engine V6.4 nel ciclo di gioco. I benchmark reali confermano:

- **Performance eccellente**: ~2.5ms/tick a 1x, ~15ms a 6x
- **Eventi dinamici nativi**: ogni sezione calcolata al momento
- **Interazione giocatore**: cambio push/ERS/engine map si riflette immediatamente
- **Stato carryover**: `PhysicsState` persiste tra le sezioni
- **Frontend inalterato**: formato dati `race_update` non cambia
- **Fallback sicuro**: flag feature toggle per tornare al V1 istantaneamente

Il Physics Engine V6.4 è pronto. Questa specifica descrive il "collante" architetturale necessario per l'integrazione.

---

## Appendice A: File da Creare/Modificare

| File | Azione | Descrizione |
|---|---|---|
| `lap_simulator/update_section_v6.py` | **CREARE** | Orchestratore per-sezione |
| `lap_simulator/physics_engine/integrator/section_mapper.py` | **CREARE** | Mapper sezione-waypoint |
| `lap_simulator/physics_engine/integrator/state_adapter.py` | **CREARE** | Adattatore stato |
| `utils/session_bridge_v6.py` | **CREARE** | Copia di `session_bridge.py` con integrazione V6 |
| `utils/game_logic_v6.py` | **CREARE** | Copia di `game_logic.py` con flag `USE_PHYSICS_ENGINE_V6` |

## Appendice B: Dipendenze

- `lap_simulator/physics_engine/integrator/waypoint.py` — `integrate_waypoint()`
- `lap_simulator/physics_engine/integrator/state.py` — `PhysicsState`
- `lap_simulator/physics_engine/integrator/io.py` — `load_hd_waypoints()`
- `lap_simulator/physics_engine/integrator/pu_stateful_v2.py` — `PU_Context`, `init_pu_context()`
- `lap_simulator/physics_engine/aero/aero_assembly.py` — `AeroAssembly`
- `lap_simulator/data_types.py` — `CarState`, `SectionResult`, `SectionContext`

---

**Documento:** Specifica di Integrazione Opzione A+  
**Redatto:** 2026-04-28  
**Version:** 1.0  
**Status:** 🟡 SPECIFICA — In attesa di implementazione
