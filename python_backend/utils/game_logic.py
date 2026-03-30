# Game Logic F1 Manager AI
import time
import random
import threading
from typing import Optional
from config import circuit_sectors, SESSION_DURATION
from utils.weekend_orchestrator import (
    WeekendOrchestrator,
    WeekendSessionType,
    normalize_weekend_session_type,
)

# --- V2 Engine flag ---
USE_NEW_ENGINE = True
session_bridge = None  # SessionBridge instance (lazy init)
session_telemetry_store = None
weekend_orchestrator = None

# --- Penalty System flags ---
USE_NEW_PENALTY_SYSTEM = True      # Master toggle per tutto il sistema penalty

# Toggle per singolo sistema
ENABLE_FUEL_PENALTIES = True       # Calcolo penalty peso carburante
ENABLE_TYRE_PENALTIES = True       # Penalty compound, usura, temperatura
ENABLE_DRIVER_SKILL_PENALTIES = True  # Penalty push level + modulazione skill pilota
ENABLE_ENGINE_PENALTIES = True     # Penalty CV motore + mappe ICE
ENABLE_ENGINE_MAP_PENALTIES = True # Solo penalty mappe motore (QUALY/STANDARD/etc)
ENABLE_ERS_PENALTIES = True        # Penalty modalità ERS (RECHARGE/OVERTAKE/etc)
ENABLE_BRAKE_PENALTIES = True      # Penalty duct + fade freni
ENABLE_SETUP_PENALTIES = True     # Penalty/bonus assetto (DF/Drag trade-off)

# Performance optimization flags
ENABLE_PENALTY_CACHE = False      # Use pre-computed penalty cache (default: off)

# ERS bonus and thermal clipping
ENABLE_ERS_BONUS = True           # ERS energy deployment → time bonus (negative penalty)

# Lock per sincronizzare accessi alle variabili globali
state_lock = threading.Lock()

# Variabili globali per la sessione
session_start_time = time.time()
session_start_real_time = time.time()  # Tempo reale di inizio
game_speed_multiplier = 1.0  # Moltiplicatore velocità di gioco
accumulated_game_time = 0.0  # Tempo di gioco accumulato
last_speed_change_time = time.time()  # Tempo dell'ultimo cambio velocità
total_paused_time = 0.0  # Tempo totale passato in pausa
pause_start_time = None  # Quando è iniziata la pausa corrente
is_paused = False  # Stato di pausa corrente
simulation_ready = False  # Parte solo dopo la selezione del circuito

# Inizializza 20 auto (2 per team) con posizioni sfalsate
from data.teams import TEAMS
from models import RaceCar
from utils.debug_log import log_debug_event

race_cars = []
car_index = 0
player_team_id = None
player_driver_numbers = set()
DEFAULT_PLAYER_TEAM_SIGLA = "FER"

def _team_primary_pilots(team):
    return [p for p in (getattr(team, "pilota1", None), getattr(team, "pilota2", None)) if p]


for team in TEAMS:
    for pilot in _team_primary_pilots(team):
        car = RaceCar(pilot=pilot, team=team)
        car.distance_traveled = car_index * 150
        car.session_start_time = session_start_time
        car.box_time_until = random.uniform(30, 300)
        car_index += 1
        race_cars.append(car)

# Session best times (across all cars)
session_best_lap = None  # Best lap time in session
session_best_sectors = {'sector1': None, 'sector2': None, 'sector3': None}  # Best sector times in session

def reset_session_bests():
    """Reset session bests for new session"""
    global session_best_lap, session_best_sectors
    session_best_lap = None
    session_best_sectors = {'sector1': None, 'sector2': None, 'sector3': None}


def _bridge_session_type_for_weekend(session_type: str) -> str:
    try:
        weekend_session_type = normalize_weekend_session_type(session_type)
    except ValueError:
        return WeekendSessionType.FP1.value

    # Qualifying sessions map to Q1 for SessionBridge
    if weekend_session_type in {WeekendSessionType.Q1, WeekendSessionType.Q2, WeekendSessionType.Q3}:
        return 'QUALIFYING'

    if weekend_session_type == WeekendSessionType.RACE:
        return WeekendSessionType.RACE.value

    if weekend_session_type in {
        WeekendSessionType.FP1,
        WeekendSessionType.FP2,
        WeekendSessionType.FP3,
    }:
        return weekend_session_type.value

    return WeekendSessionType.FP1.value


def is_simulation_ready():
    """Indica se la simulazione può avanzare (circuito selezionato)."""
    with state_lock:
        return simulation_ready


def start_session_for_circuit(session_type: str = "FP1"):
    """Resetta lo stato partendo dal circuito appena caricato e avvia la sessione."""
    global session_start_time, session_start_real_time, accumulated_game_time
    global last_speed_change_time, pause_start_time, is_paused, simulation_ready
    global game_speed_multiplier
    global session_bridge
    global session_telemetry_store
    global weekend_orchestrator

    start_time = time.time()
    with state_lock:
        session_start_time = start_time
        session_start_real_time = start_time
        accumulated_game_time = 0.0
        last_speed_change_time = start_time
        game_speed_multiplier = 1.0
        pause_start_time = None
        is_paused = False
        simulation_ready = True

    reset_cars_for_session(start_time)

    # Initialize V2 engine if enabled
    weekend_orchestrator = None
    if USE_NEW_ENGINE:
        try:
            import config as cfg
            circuit_id = getattr(cfg, 'current_circuit', None)
            if circuit_id:
                try:
                    requested_weekend_session = normalize_weekend_session_type(session_type)
                except ValueError:
                    requested_weekend_session = WeekendSessionType.FP1
                bridge_session_type = _bridge_session_type_for_weekend(requested_weekend_session.value)
                import logging
                logging.getLogger(__name__).info(
                    "V2 engine: Initializing WeekendOrchestrator/SessionBridge for circuit %s (%s)",
                    circuit_id,
                    requested_weekend_session.value,
                )
                from services.tyre_inventory_service import TyreInventoryService
                from utils.session_bridge import SessionBridge
                TyreInventoryService().reset_inventories_for_circuit(circuit_id)
                from utils.session_telemetry_store import SessionTelemetryStore
                session_telemetry_store = SessionTelemetryStore(circuit_id=circuit_id)
                weekend_orchestrator = WeekendOrchestrator().start(
                    circuit_id=circuit_id,
                    session_type=requested_weekend_session,
                    metadata={"bridge_session_type": bridge_session_type},
                )
                session_bridge = SessionBridge()
                session_bridge.telemetry_store = session_telemetry_store
                logging.getLogger(__name__).info("V2 engine: SessionBridge created, initializing session...")
                ok = session_bridge.init_session(circuit_id, race_cars, session_type=bridge_session_type)
                logging.getLogger(__name__).info("V2 engine: SessionBridge init returned %s", ok)
                if not ok:
                    logging.getLogger(__name__).warning("V2 engine: SessionBridge init failed")
                    session_bridge = None
                    session_telemetry_store = None
                    weekend_orchestrator = None
            else:
                import logging
                logging.getLogger(__name__).warning("V2 engine: No circuit_id found")
        except Exception as e:
            import logging
            import traceback
            logging.getLogger(__name__).error("V2 engine init failed: %s", e)
            logging.getLogger(__name__).error("V2 engine traceback: %s", traceback.format_exc())
            session_bridge = None
            session_telemetry_store = None
            weekend_orchestrator = None

    return start_time


def mark_simulation_pending(reset_cars=False):
    """Segna la simulazione come in attesa di selezione circuito."""
    global simulation_ready, session_start_time, session_start_real_time
    global accumulated_game_time, last_speed_change_time, pause_start_time, is_paused
    global game_speed_multiplier
    global weekend_orchestrator

    start_time = time.time()
    with state_lock:
        simulation_ready = False
        session_start_time = start_time
        session_start_real_time = start_time
        accumulated_game_time = 0.0
        last_speed_change_time = start_time
        pause_start_time = None
        is_paused = False

    if reset_cars:
        reset_cars_for_session(start_time)
    weekend_orchestrator = None

def reset_cars_for_session(start_time):
    """Rimette tutte le auto ai box con uscite scaglionate."""
    global car_index
    car_index = 0
    
    # Reset session bests
    reset_session_bests()
    
    for car in race_cars:
        car.state = car.state.__class__.BOX
        car.distance_traveled = car_index * 150
        car.session_start_time = start_time
        car.box_time_until = random.uniform(30, 300)
        car.current_lap_start = None
        car.lap_times = []
        car.total_laps = 0
        car.total_session_laps = 0
        car.last_lap_type = None
        car.has_completed_hot_lap = False
        car.current_lap_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        car.last_sector_times = {'sector1': None, 'sector2': None, 'sector3': None}
        car.best_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        car.best_lap_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        car.stint_laps_remaining = car.stint_target_laps
        car.sector3_start_time = None
        if car.is_player_controlled:
            log_debug_event('car_reset', driver=car.driver_number, team=getattr(car.team, 'nome_scuderia', None))
        car_index += 1


def get_car_by_driver_number(driver_number: int) -> Optional[RaceCar]:
    return next((car for car in race_cars if car.driver_number == driver_number), None)


def set_player_team(team_id: int):
    global player_team_id, player_driver_numbers
    player_team_id = team_id
    player_driver_numbers = set()
    for car in race_cars:
        is_player_car = getattr(car.team, "team_id", None) == team_id
        car.is_player_controlled = is_player_car
        if is_player_car:
            player_driver_numbers.add(car.driver_number)
            car.box_time_until = float("inf")


def get_player_team_id() -> Optional[int]:
    return player_team_id


def get_player_driver_numbers():
    return set(player_driver_numbers)


def initialize_default_player_team():
    for team in TEAMS:
        if getattr(team, "sigla_scuderia", "").upper() == DEFAULT_PLAYER_TEAM_SIGLA:
            team_id = getattr(team, "team_id", None)
            if team_id is not None:
                set_player_team(team_id)
            break


initialize_default_player_team()


def get_player_team_info():
    if player_team_id is None:
        return None
    for team in TEAMS:
        if getattr(team, "team_id", None) == player_team_id:
            return {
                "team_id": player_team_id,
                "team_name": team.nome_scuderia,
                "team_code": team.sigla_scuderia,
                "driver_numbers": list(player_driver_numbers),
            }
    return {
        "team_id": player_team_id,
        "team_name": "Unknown",
        "team_code": DEFAULT_PLAYER_TEAM_SIGLA,
        "driver_numbers": list(player_driver_numbers),
    }

def get_session_time_remaining():
    """Restituisce il tempo rimanente della sessione (aggiustato per velocità gioco e pause)"""
    global is_paused, accumulated_game_time, last_speed_change_time
    
    with state_lock:
        if is_paused:
            # Se in pausa, ritorna il tempo accumulato
            remaining = max(0, SESSION_DURATION - accumulated_game_time)
            return remaining
        
        # Calcola tempo trascorso dall'ultimo cambio velocità
        current_real_time = time.time()
        if pause_start_time:
            # Se attualmente in pausa, non contare questo tempo
            elapsed_since_last_change = 0
        else:
            elapsed_since_last_change = current_real_time - last_speed_change_time
        
        # Calcola tempo totale di gioco
        current_game_time = accumulated_game_time + (elapsed_since_last_change * game_speed_multiplier)
        remaining = max(0, SESSION_DURATION - current_game_time)
        return remaining

def format_session_time(seconds):
    """Formatta il tempo della sessione in MM:SS"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def set_game_speed(multiplier):
    """Imposta la velocità di gioco"""
    global game_speed_multiplier, accumulated_game_time, last_speed_change_time
    
    with state_lock:
        # Calcola tempo accumulato fino ad ora
        current_real_time = time.time()
        if not is_paused:
            elapsed_since_last_change = current_real_time - last_speed_change_time
            accumulated_game_time += elapsed_since_last_change * game_speed_multiplier
        
        # Aggiorna velocità e tempo di cambio
        game_speed_multiplier = multiplier
        last_speed_change_time = current_real_time
        
        return game_speed_multiplier

def get_game_speed():
    """Restituisce la velocità di gioco corrente"""
    with state_lock:
        return game_speed_multiplier

def toggle_pause():
    """Attiva/disattiva la pausa"""
    global is_paused, pause_start_time, total_paused_time, accumulated_game_time, last_speed_change_time
    
    with state_lock:
        if is_paused:
            # Riprendi il gioco
            if pause_start_time:
                total_paused_time += time.time() - pause_start_time
            pause_start_time = None
            is_paused = False
            last_speed_change_time = time.time()  # Resetta tempo per nuovo calcolo
            return False
        else:
            # Metti in pausa
            # Calcola tempo accumulato prima della pausa
            current_real_time = time.time()
            elapsed_since_last_change = current_real_time - last_speed_change_time
            accumulated_game_time += elapsed_since_last_change * game_speed_multiplier
            
            pause_start_time = current_real_time
            is_paused = True
            return True

def get_pause_state():
    """Restituisce lo stato di pausa corrente in modo thread-safe"""
    with state_lock:
        return is_paused

# Session best times (across all cars)
session_best_lap = None  # Best lap time in session
session_best_sectors = {'sector1': None, 'sector2': None, 'sector3': None}  # Best sector times in session

def update_session_bests(car):
    """Update session best times when a car completes a lap or sector"""
    global session_best_lap, session_best_sectors
    
    # Update best lap
    if hasattr(car, 'best_lap_time') and car.best_lap_time is not None:
        if session_best_lap is None or car.best_lap_time < session_best_lap:
            session_best_lap = car.best_lap_time
    
    # Update best sectors
    for sector in ['sector1', 'sector2', 'sector3']:
        sector_time = car.best_sectors.get(sector)
        if sector_time is not None:
            if session_best_sectors[sector] is None or sector_time < session_best_sectors[sector]:
                session_best_sectors[sector] = sector_time

def get_session_bests():
    """Get current session best times"""
    return {
        'best_lap': session_best_lap,
        'best_sectors': session_best_sectors.copy()
    }


def get_session_bridge():
    """Return the active SessionBridge (V2 engine) or None."""
    return session_bridge


def get_session_telemetry_store():
    """Return the active session telemetry store or None."""
    return session_telemetry_store


def get_weekend_orchestrator():
    """Return the active weekend orchestrator or None."""
    return weekend_orchestrator


def set_weekend_orchestrator(orchestrator):
    """Set the active weekend orchestrator."""
    global weekend_orchestrator
    weekend_orchestrator = orchestrator
    return weekend_orchestrator


def is_v2_engine_active() -> bool:
    """Check if V2 engine is active and running."""
    return session_bridge is not None and session_bridge.active
