# Specifiche Sistema Allocazione Gomme con Tracking Individuale

## Overview
Sistema completo per la gestione delle allocazioni gomme F1 2025 con tracking individuale dei set per ogni auto, inclusa usura percentuale e stato disponibilità.

## 1. Architettura del Sistema

### 1.1 Struttura Dati

#### Telemetry Data Extension
Ogni file `*_Telemetry.json` viene esteso con la sezione `tyre_allocation`:

```json
{
  "metadata": { ... },
  "geometry": { ... },
  "tyres": { ... },
  "tyre_allocation": {
    "weekend_type": "standard|sprint",
    "dry_allocation": {
      "soft": 8,
      "medium": 3,
      "hard": 2
    },
    "wet_allocation": {
      "intermediate": 5,
      "wet": 2
    },
    "special_rules": {
      "mandatory_race_compounds": 2,
      "q3_soft_reserve": true,
      "practice_returns": 2,
      "monaco_extra_wet": false,
      "monaco_mandatory_sets": 2
    },
    "circuit_characteristics": {
      "wear_profile": "low|medium|high",
      "degradation_factor": 1.0,
      "thermal_stress": "low|medium|high"
    }
  },
  "fuel_mass": { ... }
}
```

#### Tyre Set Management
```python
class TyreSet:
    def __init__(self, set_id: str, compound: str, initial_condition: float = 100.0):
        self.set_id = set_id                    # "S1", "M2", "H1", etc.
        self.compound = compound                # "soft", "medium", "hard", "intermediate", "wet"
        self.condition = initial_condition       # 0-100% usura
        self.heat_cycles = 0                    # cicli termici
        self.laps_completed = 0                 # giri completati
        self.session_history = []               # storico utilizzi
        self.is_available = True                # disponibilità
        self.is_q3_reserve = False              # set riservato Q3
        
class DriverTyreInventory:
    def __init__(self, driver_id: str, circuit_allocation: dict):
        self.driver_id = driver_id
        self.circuit_allocation = circuit_allocation
        self.tyre_sets = self._initialize_sets()
```

### 1.2 Configurazioni per Tipo di Weekend

#### Standard Weekend
```json
{
  "weekend_type": "standard",
  "dry_allocation": { "soft": 8, "medium": 3, "hard": 2 },
  "wet_allocation": { "intermediate": 5, "wet": 2 },
  "special_rules": {
    "mandatory_race_compounds": 2,
    "q3_soft_reserve": true,
    "practice_returns": 2
  }
}
```

#### Sprint Weekend
```json
{
  "weekend_type": "sprint",
  "dry_allocation": { "soft": 6, "medium": 4, "hard": 2 },
  "wet_allocation": { "intermediate": 6, "wet": 2 },
  "special_rules": {
    "mandatory_race_compounds": 2,
    "practice_returns": 2
  }
}
```

#### Monaco - Regole Speciali
```json
{
  "weekend_type": "standard",
  "dry_allocation": { "soft": 8, "medium": 3, "hard": 2 },
  "wet_allocation": { "intermediate": 5, "wet": 3 },
  "special_rules": {
    "mandatory_race_compounds": 3,
    "q3_soft_reserve": true,
    "practice_returns": 2,
    "monaco_extra_wet": true,
    "monaco_mandatory_sets": 3
  }
}
```

## 2. API Endpoints

### 2.1 Get Driver Tyre Inventory
```
GET /api/driver/{driver_id}/tyre-inventory/{circuit_id}
```

**Response:**
```json
{
  "driver_id": "lec",
  "circuit_id": "mc-1929_monaco",
  "allocation": { ... },
  "sets": [
    {
      "set_id": "S1",
      "compound": "soft",
      "condition": 100.0,
      "heat_cycles": 0,
      "laps_completed": 0,
      "is_available": true,
      "is_q3_reserve": false
    },
    ...
  ]
}
```

### 2.2 Update Tyre Usage
```
POST /api/driver/{driver_id}/tyre-usage
```

**Request:**
```json
{
  "set_id": "S1",
  "laps": 15,
  "wear_factor": 1.2,
  "session_type": "race"
}
```

**Response:**
```json
{
  "updated": true,
  "new_condition": 82.0,
  "wear_applied": 18.0
}
```

### 2.3 Get Circuit Tyre Allocation
```
GET /api/circuit/{circuit_id}/tyre-allocation
```

## 3. Frontend Integration

### 3.1 Tab Gomme Structure
La nuova tab "Gomme" nel setup modal include:

1. **Header Allocazione**: Tipo weekend, compound selection
2. **Compound Cards**: Visualizzazione compound Pirelli con colori
3. **Inventory Grid**: Cards individuali per ogni set
4. **Special Rules**: Regole speciali del circuito

### 3.2 Set Card UI
Ogni card set include:

- **Set ID**: "S1", "M2", "H1", "I1", "W1"
- **Badge Status**: Q3 reserve, unavailable
- **Wear Indicator**: Cerchio progressivo con percentuale
- **Details**: Cicli termici, giri completati, stato usura
- **Color Coding**: Rosso (soft), Giallo (medium), Bianco (hard), Verde (intermediate), Blu (wet)

### 3.3 Wear Status Levels
- **Nuovo** (90-100%): Verde brillante
- **Leggero** (60-89%): Verde chiaro
- **Usato** (30-59%): Arancione
- **Critico** (0-29%): Rosso

## 4. Sistema di Persistenza

### 4.1 File Storage
```json
// data/tyre_inventories.json
{
  "lec_mc-1929_monaco": {
    "driver_id": "lec",
    "circuit_id": "mc-1929_monaco",
    "sets": [...],
    "last_updated": "2026-03-08T14:24:00Z"
  }
}
```

### 4.2 Auto-save Events
- Dopo ogni session (FP1, FP2, FP3, Q, R)
- Quando usura set cambia significativamente (>5%)
- Al cambio circuito

## 5. Business Logic

### 5.1 Wear Calculation
```python
def calculate_wear(base_wear: float, laps: int, compound: str, circuit_characteristics: dict) -> float:
    compound_multiplier = {
        'soft': 1.5,
        'medium': 1.0,
        'hard': 0.7,
        'intermediate': 0.8,
        'wet': 0.6
    }
    
    wear_factor = (
        base_wear * 
        laps * 
        compound_multiplier[compound] * 
        circuit_characteristics['degradation_factor']
    )
    
    return min(wear_factor, 100.0)
```

### 5.2 Set Availability Rules
- Set disponibili: condition > 30%
- Set usati: condition <= 30%
- Set Q3 reserve: solo per qualifiche
- Restituzione FP: 2 set dopo ogni practice session

### 5.2.1 AI Practice Reuse Policy
- Ogni auto AI utilizza un inventario gomme per-driver e per-circuito, separato da quello delle altre vetture.
- Durante le Practice l'AI prova a riutilizzare lo stesso set del run precedente se:
  - il compound richiesto dal programma è lo stesso,
  - il set è ancora disponibile,
  - la `condition` del set è maggiore o uguale al 40%.
- Se il set precedente non è più riutilizzabile, l'AI seleziona il miglior set disponibile dello stesso compound.
- Un set con `condition < 40%` non può essere usato nell'uscita successiva dell'AI.
- Il riuso viene gestito a livello di inventario (`TyreInventoryService`) e non viene esposto nella UI standard del giocatore.

### 5.3 Race Strategy Validation
```python
def validate_race_strategy(inventory: DriverTyreInventory, planned_sets: list) -> dict:
    mandatory_compounds = inventory.circuit_allocation['special_rules']['mandatory_race_compounds']
    
    used_compounds = set()
    for set_id in planned_sets:
        tyre_set = find_set(inventory.tyre_sets, set_id)
        if tyre_set and tyre_set.is_available:
            used_compounds.add(tyre_set.compound)
    
    return {
        'valid': len(used_compounds) >= mandatory_compounds,
        'compounds_used': list(used_compounds),
        'required_compounds': mandatory_compounds
    }
```

## 6. Integration Points

### 6.1 Backend QA / Debug Logging
- Gli eventi di debug gomme AI vengono scritti nel log generale `python_backend/logs/f1_setup_debug.log`.
- Gli stessi eventi vengono duplicati in `python_backend/logs/ai_tyre_debug.log` per facilitare le verifiche QA senza mischiarli agli altri eventi setup.
- Eventi attualmente tracciati:
  - `ai_tyre_reserved`
  - `ai_tyre_reserve_failed`
  - `ai_tyre_released`
  - `ai_tyre_stint_completed`
  - `ai_tyre_stint_update_failed`
- I log QA sono backend-only e non espongono in UI l'usura delle gomme AI.

### 6.1 Game Logic Integration
```python
# In game_logic.py
class CarState:
    def __init__(self):
        # ... existing attributes ...
        self.tyre_inventory = None
        self.current_tyre_set = None
        
    def initialize_tyre_inventory(self, circuit_allocation: dict):
        self.tyre_inventory = DriverTyreInventory(self.driver_id, circuit_allocation)
        
    def select_tyre_set(self, set_id: str):
        tyre_set = find_set(self.tyre_inventory.tyre_sets, set_id)
        if tyre_set and tyre_set.is_available:
            self.current_tyre_set = tyre_set
            return True
        return False
```

### 6.2 Session Orchestrator Integration
```python
# Session flow con tyre tracking
def start_session(driver_id: str, circuit_id: str, session_type: str):
    inventory = load_driver_inventory(driver_id, circuit_id)
    
    # Applica regole restituzione per practice sessions
    if session_type in ['FP1', 'FP2', 'FP3']:
        return_sets_after_practice(inventory, 2)
    
    # Gestione set Q3 per qualifiche
    if session_type == 'Q3':
        handle_q3_soft_reserve(inventory)
```

## 7. Testing Strategy

### 7.1 Unit Tests
- TyreSet creation and wear calculation
- DriverTyreInventory initialization
- Wear status level transitions
- API endpoint responses

### 7.2 Integration Tests
- Complete tyre allocation flow
- Session progression with set returns
- Race strategy validation
- UI tab rendering with real data

### 7.3 E2E Scenarios
- Full weekend simulation (FP1→FP2→FP3→Q→R)
- Sprint weekend flow
- Monaco special rules validation
- Multi-driver inventory management

## 8. Performance Considerations

### 8.1 Data Loading
- Lazy loading di tyre inventories
- Cache per telemetry data
- Batch updates per wear calculation

### 8.2 UI Optimization
- Virtual scrolling per inventory grid
- Debounced wear updates
- Progressive rendering di set cards

## 9. Security & Validation

### 9.1 Input Validation
- Set ID format validation
- Compound type checking
- Wear percentage bounds (0-100)

### 9.2 Data Integrity
- Atomic updates per tyre set
- Backup before major changes
- Audit trail per session

## 10. Future Enhancements

### 10.1 Advanced Features
- Tyre temperature tracking
- Compound performance prediction
- AI strategy recommendations
- Historical wear patterns

### 10.2 Visual Improvements
- 3D tyre visualization
- Interactive wear heatmaps
- Real-time wear animation
- Strategy planning tools

## 11. Migration Plan

### 11.1 Phase 1: Backend Setup
1. Extend telemetry JSON files
2. Implement tyre set models
3. Create API endpoints
4. Setup persistence layer

### 11.2 Phase 2: Frontend Integration
1. Build tyre tab UI
2. Implement inventory grid
3. Add wear visualization
4. Integrate with setup modal

### 11.3 Phase 3: Testing & Refinement
1. Unit and integration testing
2. E2E scenario validation
3. Performance optimization
4. Documentation completion

## 12. Success Metrics

### 12.1 Functional Metrics
- 100% telemetry files updated
- All tyre sets trackable individually
- Real-time wear updates working
- Complete UI functionality

### 12.2 Performance Metrics
- API response time < 100ms
- UI rendering < 200ms
- Memory usage < 50MB for inventories
- 100% test coverage for core logic

---

**Version**: 1.0  
**Last Updated**: 2026-03-08  
**Author**: F1 Manager AI Team  
**Status**: Specification Complete
