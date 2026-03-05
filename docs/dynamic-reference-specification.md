# Specifiche Tecniche: Sistema di Reference Dinamica per Performance Team

## 1. Overview

Il sistema di Reference Dinamica permette ai team di superare la reference di performance originale (McLaren) e diventare essi stessi il nuovo riferimento per il calcolo dei delta di performance. Questo sistema è evolutivo e supporta lo sviluppo progressivo delle componenti auto durante la stagione.

## 2. Architettura del Sistema

### 2.1 Componenti Principali

```
TeamReference (Dynamic)
├── reference_team_code: str          # Team più veloce corrente
├── reference_lap_time_s: float       # Tempo di riferimento
├── reference_auto: Auto             # Auto di riferimento
├── reference_pilot: Pilota          # Pilota di riferimento
└── last_updated: datetime           # Timestamp ultimo aggiornamento

DynamicDeltaCalculator
├── calculate_physical_deltas()       # Delta fisici componenti
├── scale_to_target_gaps()           # Scaling per performance target
└── determine_reference_team()        # Logica selezione reference

SessionBridge Integration
├── create_reference_context()       # Inizializza reference
├── update_reference_if_needed()      # Aggiorna reference dinamica
└── build_car_entries_with_ref()     # Costruzione CarEntry con reference
```

### 2.2 Flusso di Calcolo

1. **Determinazione Reference**: Team con performance migliore diventa reference
2. **Calcolo Delta Fisici**: Differenze componenti vs reference team
3. **Scaling Performance**: Aggiustamento per target gap di bilanciamento
4. **Applicazione Penalty**: Sistema esistente applica delta dinamici

## 3. Data Types Specification

### 3.1 TeamReference

```python
@dataclass
class TeamReference:
    """Contesto di riferimento dinamico per calcolo performance."""
    reference_team_code: str           # Codice team riferimento (es. "FER")
    reference_lap_time_s: float        # Tempo giro di riferimento
    reference_auto: Auto              # Auto con componenti sviluppate
    reference_pilot: Pilota           # Pilota con skill attuali
    circuit_id: str                   # Circuito di riferimento
    session_type: str                  # FP1/FP2/FP3/QUALI/RACE
    last_updated: datetime            # Timestamp ultimo aggiornamento
    performance_score: float = 0.0    # Score performance per ranking
    
    def is_valid_for_session(self, session_type: str, circuit_id: str) -> bool:
        """Verifica se reference è valida per sessione corrente."""
        return (self.session_type == session_type and 
                self.circuit_id == circuit_id and
                (datetime.now() - self.last_updated).total_seconds() < 3600)
```

### 3.2 DeltaCalculationResult

```python
@dataclass
class DeltaCalculationResult:
    """Risultato calcolo delta dinamici."""
    team_code: str
    reference_team_code: str
    delta_aero_physical: float         # Delta fisico aerodinamico
    delta_grip_physical: float         # Delta fisico grip
    delta_aero_scaled: float           # Delta scalato per target
    delta_grip_scaled: float           # Delta scalato per target
    target_gap_pct: float              # Gap target vs reference
    performance_score: float           # Score performance team
    is_reference: bool = False         # True se questo team è reference
```

## 4. Algoritmi di Calcolo

### 4.1 Determinazione Reference Team

```python
def determine_reference_team(
    team_performances: Dict[str, float], 
    circuit_id: str,
    session_type: str
) -> str:
    """
    Determina il team più veloce come reference.
    
    Args:
        team_performances: Dict {team_code: lap_time_s}
        circuit_id: ID circuito corrente
        session_type: Tipo sessione
    
    Returns:
        Codice team reference
    """
    # Filtra team validi per sessione
    valid_teams = {
        code: time for code, time in team_performances.items()
        if is_team_eligible(code, session_type)
    }
    
    if not valid_teams:
        return "MCL"  # Fallback a McLaren originale
    
    # Team con tempo migliore diventa reference
    return min(valid_teams.keys(), key=lambda k: valid_teams[k])
```

### 4.2 Calcolo Delta Fisici

```python
def calculate_physical_deltas(team_code: str, reference_team_code: str) -> tuple[float, float]:
    """
    Calcola delta fisici basati sulle componenti auto.
    
    Formula:
    delta_aero = (DF_ref - DF_team) / DF_ref
    delta_grip = (Grip_ref - Grip_team) / Grip_ref
    """
    team_auto = TEAM_BY_CODE[team_code].auto
    ref_auto = TEAM_BY_CODE[reference_team_code].auto
    
    # Downforce totale
    team_df = sum_component_downforce(team_auto.aero_package)
    ref_df = sum_component_downforce(ref_auto.aero_package)
    delta_aero = (ref_df - team_df) / ref_df if ref_df > 0 else 0.0
    
    # Grip totale
    team_grip = team_auto.grip_base or 1.0
    ref_grip = ref_auto.grip_base or 1.0
    delta_grip = (ref_grip - team_grip) / ref_grip if ref_grip > 0 else 0.0
    
    # Clamp per limiti realistici
    delta_aero = clamp(delta_aero, -0.05, 0.05)
    delta_grip = clamp(delta_grip, -0.08, 0.08)
    
    return delta_aero, delta_grip
```

### 4.3 Scaling per Target Gap

```python
def scale_deltas_to_target(
    delta_aero: float,
    delta_grip: float, 
    target_gap_pct: float,
    config: CircuitConfig
) -> tuple[float, float]:
    """
    Scala delta fisici per raggiungere target gap di bilanciamento.
    
    Formula:
    scaled_delta = (target_gap * share) / k_coefficient
    """
    # Determine contribution shares
    total_abs = abs(delta_aero) + abs(delta_grip)
    if total_abs < 1e-4:
        aero_share, grip_share = 0.6, 0.4  # Default split
    else:
        aero_share = abs(delta_aero) / total_abs
        grip_share = abs(delta_grip) / total_abs
    
    # Scale to target gap
    max_delta = 4.0  # Safety limit
    scaled_aero = (target_gap_pct * aero_share) / (config.k_aero_penalty or 1.0)
    scaled_grip = (target_gap_pct * grip_share) / (config.k_grip_penalty or 1.0)
    
    # Apply limits
    scaled_aero = clamp(scaled_aero, -max_delta, max_delta)
    scaled_grip = clamp(scaled_grip, -max_delta, max_delta)
    
    return scaled_aero, scaled_grip
```

## 5. Integrazione con Sistema Esistente

### 5.1 Modifiche a run_sim_teams.py

```python
def run_teams_simulation_dynamic(
    circuit_id: str = "gb-1948_silverstone_HD",
    use_dynamic_reference: bool = True
) -> Dict[str, Any]:
    """Run simulazione con reference dinamica."""
    
    # Fase 1: Calcolo performance base tutti team
    base_performances = {}
    for team_code in EXPECTED_GAPS.keys():
        entry = build_car_entry_baseline(team_code, circuit_id, config)
        result = simulate_single_lap(entry, config)
        base_performances[team_code] = result.lap_time_s
    
    # Fase 2: Determinazione reference
    if use_dynamic_reference:
        reference_team = determine_reference_team(base_performances, circuit_id, "QUALI")
    else:
        reference_team = "MCL"  # Reference fissa originale
    
    # Fase 3: Calcolo delta dinamici vs reference
    dynamic_results = {}
    for team_code in EXPECTED_GAPS.keys():
        delta_aero, delta_grip = calculate_physical_deltas(team_code, reference_team)
        
        # Target gap aggiustato vs reference
        target_gap = EXPECTED_GAPS[team_code] - EXPECTED_GAPS.get(reference_team, 0.0)
        target_gap_pct = target_gap / 100.0
        
        # Scaling per performance
        scaled_aero, scaled_grip = scale_deltas_to_target(
            delta_aero, delta_grip, target_gap_pct, config
        )
        
        # Simulazione con delta dinamici
        entry = build_car_entry_dynamic(
            team_code, circuit_id, config, 
            scaled_aero, scaled_grip, 
            apply_baseline_delta=False
        )
        result = simulate_single_lap(entry, config)
        dynamic_results[team_code] = result
    
    return {
        "reference_team": reference_team,
        "base_performances": base_performances,
        "dynamic_results": dynamic_results,
        "gap_analysis": analyze_gaps(dynamic_results, reference_team)
    }
```

### 5.2 SessionBridge Integration

```python
class SessionBridge:
    def __init__(self):
        self.team_reference: Optional[TeamReference] = None
        self.delta_calculator = DynamicDeltaCalculator()
    
    def init_session(self, circuit_id: str, race_cars: List[RaceCar], session_type: str):
        """Inizializza sessione con reference dinamica."""
        # Calcola performance iniziali tutti team
        initial_performances = self._compute_initial_performances(race_cars)
        
        # Determina reference team
        reference_team_code = determine_reference_team(
            initial_performances, circuit_id, session_type
        )
        
        # Crea contesto reference
        self.team_reference = TeamReference(
            reference_team_code=reference_team_code,
            reference_lap_time_s=initial_performances[reference_team_code],
            reference_auto=self._get_team_auto(reference_team_code),
            reference_pilot=self._get_team_pilot(reference_team_code),
            circuit_id=circuit_id,
            session_type=session_type,
            last_updated=datetime.now()
        )
    
    def create_car_entry(self, race_car: RaceCar) -> CarEntry:
        """Crea CarEntry usando reference dinamica."""
        if not self.team_reference:
            # Fallback a sistema originale
            return self._create_car_entry_legacy(race_car)
        
        # Calcola delta vs reference dinamica
        delta_result = self.delta_calculator.calculate_deltas(
            race_car.team_name, self.team_reference.reference_team_code
        )
        
        return CarEntry(
            car_id=race_car.driver_number,
            state=self._create_car_state(race_car),
            aero_setup=self._create_aero_setup(race_car),
            driver_skills=self._create_driver_skills(race_car),
            push_level=1.0,
            delta_aero=delta_result.delta_aero_scaled,
            delta_grip=delta_result.delta_grip_scaled,
            apply_baseline_delta=False  # Reference è dinamica
        )
```

## 6. Gestione Sviluppo Componenti

### 6.1 Aggiornamento Reference con Sviluppo

```python
def update_reference_with_development(
    current_reference: TeamReference,
    team_developments: Dict[str, TeamDevelopment]
) -> TeamReference:
    """
    Aggiorna reference se un team sviluppa componenti superiori.
    
    Trigger:
    - Team supera performance reference corrente
    - Sviluppo componenti significativo (>5% improvement)
    """
    # Calcola nuove performance con sviluppi
    updated_performances = {}
    for team_code, development in team_developments.items():
        performance = compute_performance_with_development(
            team_code, development
        )
        updated_performances[team_code] = performance
    
    # Controlla se qualche team supera reference
    current_ref_perf = updated_performances.get(current_reference.reference_team_code, float('inf'))
    best_team = min(updated_performances.keys(), key=lambda k: updated_performances[k])
    
    if updated_performances[best_team] < current_ref_perf * 0.98:  # 2% improvement
        # Nuova reference
        return TeamReference(
            reference_team_code=best_team,
            reference_lap_time_s=updated_performances[best_team],
            reference_auto=team_developments[best_team].developed_auto,
            reference_pilot=team_developments[best_team].current_pilot,
            circuit_id=current_reference.circuit_id,
            session_type=current_reference.session_type,
            last_updated=datetime.now(),
            performance_score=compute_performance_score(best_team, team_developments[best_team])
        )
    
    return current_reference  # Mantieni reference attuale
```

### 6.2 Team Development Tracking

```python
@dataclass
class TeamDevelopment:
    """Tracciamento sviluppo componenti team."""
    team_name: str
    base_auto: Auto                    # Auto iniziale
    developed_auto: Auto              # Auto con sviluppi
    development_level: Dict[str, float]  # Livello sviluppo per componente
    development_timestamp: datetime   # Timestamp ultimo sviluppo
    
    def get_improvement_percentage(self) -> float:
        """Calcola miglioramento percentuale totale."""
        base_df = sum_component_downforce(self.base_auto.aero_package)
        dev_df = sum_component_downforce(self.developed_auto.aero_package)
        df_improvement = (dev_df - base_df) / base_df if base_df > 0 else 0.0
        
        base_grip = self.base_auto.grip_base or 1.0
        dev_grip = self.developed_auto.grip_base or 1.0
        grip_improvement = (dev_grip - base_grip) / base_grip if base_grip > 0 else 0.0
        
        return (df_improvement + grip_improvement) / 2.0
```

## 7. Configurazione e Parametri

### 7.1 Parametri di Sistema

```json
{
    "reference_update_threshold": 0.02,
    "max_delta_aero": 0.05,
    "max_delta_grip": 0.08,
    "default_aero_share": 0.6,
    "default_grip_share": 0.4,
    "reference_validity_hours": 1,
    "development_check_interval": 300,
    "fallback_reference_team": "MCL"
}
```

### 7.2 Expected Gaps Dinamici

```json
{
    "baseline_gaps": {
        "MCL": 0.0, "RBR": 0.8, "FER": 1.2, "MER": 1.8,
        "AST": 2.5, "ALP": 3.2, "HAAS": 4.1, "WIL": 4.8,
        "SAU": 5.5, "RB": 6.8
    },
    "gap_tolerance": 0.1,
    "min_gap_significance": 0.05,
    "scaling_factors": {
        "aero_importance": 0.7,
        "grip_importance": 0.3
    }
}
```

## 8. Testing e Validazione

### 8.1 Test Cases

```python
class TestDynamicReference:
    """Test suite per sistema reference dinamica."""
    
    def test_mclaren_baseline_compatibility(self):
        """Verifica compatibilità con sistema McLaren baseline."""
        
    def test_team_becomes_reference(self):
        """Test team che supera McLaren diventa reference."""
        
    def test_multiple_reference_changes(self):
        """Test cambiamenti multipli reference durante stagione."""
        
    def test_development_impact(self):
        """Test impatto sviluppo componenti su delta."""
        
    def test_fallback_behavior(self):
        """Test fallback a reference fissa in caso di errori."""
```

### 8.2 Metriche di Validazione

```python
@dataclass
class ValidationMetrics:
    """Metriche per validazione sistema."""
    reference_stability: float
    delta_accuracy: float
    development_responsiveness: float
    backward_compatibility: float
    performance_consistency: float
```

## 9. Monitoraggio e Diagnostica

### 9.1 Logging e Tracing

```python
class DynamicReferenceLogger:
    """Logging specifico per sistema reference dinamica."""
    
    def log_reference_change(self, old_ref: str, new_ref: str, reason: str):
        
    def log_delta_calculation(self, team: str, deltas: DeltaCalculationResult):
        
    def log_development_impact(self, team: str, improvement_pct: float):
        
    def log_performance_anomaly(self, team: str, expected: float, actual: float):
```

### 9.2 Dashboard di Monitoraggio

```python
@dataclass
class ReferenceStatus:
    """Stato corrente sistema reference per dashboard."""
    current_reference: str
    reference_lap_time: float
    last_update: datetime
    team_rankings: List[Tuple[str, float]]
    pending_developments: List[str]
    system_health: Dict[str, float]
```

## 10. Deployment e Rollout

### 10.1 Fasi di Implementazione

1. **Fase 1 - Foundation** (2 settimane)
   - Implementazione data types
   - DynamicDeltaCalculator base
   - Test suite iniziale

2. **Fase 2 - Integration** (2 settimane)
   - Integrazione SessionBridge
   - Modifiche run_sim_teams.py
   - Test compatibilità backward

3. **Fase 3 - Development Tracking** (1 settimana)
   - Team development tracking
   - Aggiornamento automatico reference
   - Validazione scenari sviluppo

4. **Fase 4 - Production** (1 settimana)
   - Monitoraggio e logging
   - Dashboard operativa
   - Documentazione completa

### 10.2 Feature Flag

```json
{
    "dynamic_reference_enabled": false,
    "force_mclaren_reference": false,
    "development_tracking_enabled": false,
    "verbose_logging": false
}
```

## 11. Manutenzione e Evoluzione

### 11.1 Procedure di Manutenzione

- **Aggiornamento Expected Gaps**: Trimestrale basato su dati reali
- **Calibrazione Parametri**: Mensile per accuratezza delta
- **Validazione Reference**: Settimanale per coerenza sistema
- **Backup Configurazioni**: Giornaliero per sicurezza

### 11.2 Roadmap Futura

- **Multi-Circuit Reference**: Reference diverse per circuito
- **Session-Specific Reference**: Reference per tipo sessione
- **Machine Learning Scaling**: ML per ottimizzazione delta
- **Real-Time Reference Updates**: Aggiornamenti in tempo reale

---

**Version**: 1.0  
**Data**: 2025-01-XX  
**Autore**: F1 Manager AI Team  
**Stato**: Specification Ready for Implementation
