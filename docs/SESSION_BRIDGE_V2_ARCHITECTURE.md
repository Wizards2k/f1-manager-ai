# Session Bridge v2 - Architettura Parallela per Validazione

## Panoramica

Questo documento descrive l'architettura parallela creata per validare il nuovo motore fisico v2 senza interferire con il motore v1 attuale in produzione.

## Architettura

```
python_backend/
├── utils/
│   ├── session_bridge.py          # Motore v1 (PRODUZIONE - INTATTO)
│   └── session_bridge_v2.py       # Motore v2 (VALIDAZIONE - PARALLELO)
├── lap_simulator/
│   ├── update_section.py          # Physics v1 (PRODUZIONE - INTATTO)
│   └── update_section_v2.py       # Physics v2 (VALIDAZIONE - PARALLELO)
└── lap_simulator_v2.py            # LapSimulator v2 (VALIDAZIONE - PARALLELO)

scripts/
└── compare_engines.py             # Script di confronto v1 vs v2
```

## File Creati

### 1. `session_bridge_v2.py`
- **Scopo**: Session Bridge parallelo per validazione
- **Status**: Struttura base creata, flag `ENABLE_V2_ENGINE = False`
- **Uso**: Quando `ENABLE_V2_ENGINE = True`, usa v2 invece di v1
- **Protezione**: Default disabilitato per non interferire con produzione

### 2. `update_section_v2.py`
- **Scopo**: Physics engine v2 parallelo
- **Status**: Struttura base creata, placeholder per implementazione
- **Uso**: Implementare fisica v2 pura (senza baseline telemetrica)
- **Protezione**: Non viene mai usato finché non implementato

### 3. `lap_simulator_v2.py`
- **Scopo**: LapSimulator v2 parallelo
- **Status**: Struttura base creata, placeholder per implementazione
- **Uso**: Implementare LapSimulator v2 per test CLI
- **Protezione**: Non viene mai usato finché non implementato

### 4. `compare_engines.py`
- **Scopo**: Script di confronto v1 vs v2
- **Status**: Funzionante con fallback a v1
- **Uso**: Confrontare risultati v1 vs v2 microsettore per microsettore
- **Output**: Report JSON con delta per sezione, settore, giro

## Come Usare

### Fase 1: Validazione Dati (Attuale)

```bash
# Analizzare qualità dati circuito
python3 scripts/validate_circuit_data.py jp-1962_suzuka
```

### Fase 2: Confronto Motori (Attuale)

```bash
# Confronto v1 vs v2 (v2 fallback a v1 per ora)
python3 scripts/compare_engines.py --circuit it-1922_monza --n-laps 1
python3 scripts/compare_engines.py --circuit jp-1962_suzuka --n-laps 1
python3 scripts/compare_engines.py --circuit mc-1929_monaco --n-laps 1
```

### Fase 3: Implementazione V2 (Futuro)

Quando implementi v2, modifica questi file:

1. **`lap_simulator_v2.py`**: Implementa fisica v2 pura
2. **`update_section_v2.py`**: Implementa physics loop v2
3. **`session_bridge_v2.py`**: Abilita `ENABLE_V2_ENGINE = True`

### Fase 4: Validazione (Futuro)

```bash
# Confronto v1 vs v2 con v2 implementato
python3 scripts/compare_engines.py --circuit it-1922_monza --n-laps 1
```

## Struttura V2 (Da Implementare)

### LapSimulatorV2

```python
class LapSimulatorV2:
    """LapSimulator v2 - Physics Engine Parallelo per Validazione."""
    
    def __init__(self, config: CircuitConfig, env: EnvContext):
        self.config = config
        self.env = env
        self.cars: Dict[str, CarEntryV2] = {}
    
    def run_lap(self) -> Dict[str, LapResultV2]:
        """Run one lap for all registered cars (v2)."""
        # Implementare fisica v2 pura
        pass
```

### update_section_v2

```python
def update_section_v2(
    car_state: CarState,
    aero_setup: AeroSetup,
    driver_skills: DriverSkills,
    section: SectionContext,
    env: EnvContext,
    config: CircuitConfig,
    push_level: int = 10,
    # ... altri parametri
) -> SectionResult:
    """
    Compute physics for one car traversing one section (v2 - pure physics).
    
    Questa funzione implementa la fisica pura senza baseline telemetrica come target.
    Calcola forze reali e integra cinematicamente.
    """
    # Implementare fisica v2 pura:
    # 1. Calcolo forze fisiche reali (F_drive, F_drag, F_brake, F_lat)
    # 2. Integrazione cinematica (non baseline telemetrica)
    # 3. Validazione contro v1
    pass
```

## Test Case di Validazione

### Test Case 1: Monza (Low Downforce)
**Setup**: FW=15, RW=11 (low DF)
**Expected**:
- Low drag → high v_max (360+ km/h)
- Low downforce → low v_apex (curve veloci)
- Lap time ~79s

### Test Case 2: Monaco (High Downforce)
**Setup**: FW=80, RW=80 (high DF)
**Expected**:
- High drag → low v_max (280 km/h)
- High downforce → high v_apex (curve lente)
- Lap time ~71s

### Test Case 3: Suzuka (Balanced)
**Setup**: FW=55, RW=54 (medium DF)
**Expected**:
- Medium drag → medium v_max (340 km/h)
- Medium downforce → medium v_apex
- Lap time ~87s

## Output Confronto

### Report JSON
```json
{
  "timestamp": "2026-04-02T...",
  "circuit_id": "it-1922_monza",
  "comparison": {
    "lap_time_delta_s": 0.0,
    "sector_deltas_s": [
      {"sector": 1, "v1_s": 26.5, "v2_s": 26.5, "delta_s": 0.0},
      {"sector": 2, "v1_s": 25.0, "v2_s": 25.0, "delta_s": 0.0},
      {"sector": 3, "v1_s": 27.5, "v2_s": 27.5, "delta_s": 0.0}
    ],
    "section_deltas_s": [
      {"section_idx": 0, "section_id": "sec_01", "v1_dt_s": 0.5, "v2_dt_s": 0.5, "delta_dt_s": 0.0},
      ...
    ]
  }
}
```

## Roadmap di Implementazione

| Fase | Attività | File | Tempo |
|------|----------|------|-------|
| 1 | Validazione dati | `validate_circuit_data.py` | 2 giorni |
| 2 | Implementazione v2 | `lap_simulator_v2.py`, `update_section_v2.py` | 5 giorni |
| 3 | Confronto v1 vs v2 | `compare_engines.py` | 1 giorno |
| 4 | Validazione test case | `compare_engines.py` | 2 giorni |
| 5 | Documentazione | `docs/v2-implementation.md` | 1 giorno |

**Totale**: ~2 settimane

## Prossimi Step

1. ✅ Creare struttura parallela (session_bridge_v2.py, update_section_v2.py, lap_simulator_v2.py)
2. ✅ Creare script di confronto (compare_engines.py)
3. ✅ Validare dati circuiti (validate_circuit_data.py)
4. ⏳ Implementare fisica v2 pura in `update_section_v2.py`
5. ⏳ Implementare LapSimulatorV2 in `lap_simulator_v2.py`
6. ⏳ Abilitare `ENABLE_V2_ENGINE = True` in `session_bridge_v2.py`
7. ⏳ Validare confronto v1 vs v2 con test case noti

## Note Importanti

- **session_bridge.py** = motore v1 (PRODUZIONE - INTATTO)
- **session_bridge_v2.py** = motore v2 (VALIDAZIONE - PARALLELO)
- **ENABLE_V2_ENGINE = False** = default, non interferisce con produzione
- **ENABLE_V2_ENGINE = True** = abilita v2 per validazione

## Conclusione

L'architettura parallela permette di:
1. Sviluppare v2 senza interferire con v1
2. Confrontare v1 vs v2 microsettore per microsettore
3. Validare che v2 produca risultati fisicamente coerenti
4. Introdurre v2 in produzione solo quando convalidato

**Status**: Struttura base creata, pronto per implementazione v2.
