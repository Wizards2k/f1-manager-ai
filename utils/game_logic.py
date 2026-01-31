# Game Logic F1 Manager AI
import time
import random
import threading
from config import circuit_sectors, SESSION_DURATION

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

# Inizializza 20 auto (2 per team) con posizioni sfalsate
race_cars = []
car_index = 0
from config import F1_TEAMS
from models import RaceCar

for team_name, team_data in F1_TEAMS.items():
    for driver_num, driver_name in team_data['drivers'].items():
        car = RaceCar(driver_num, driver_name, team_name, team_data['color'])
        # Posizione iniziale sfalsata per evitare sovrapposizione
        # Ogni auto parte a circa 150 metri di distanza l'una dall'altra
        car.distance_traveled = car_index * 150
        # Inizializza tempi di uscita diversi per ogni auto
        car.session_start_time = session_start_time
        car.box_time_until = random.uniform(30, 300)  # Prima uscita tra 30s-5min
        car_index += 1
        race_cars.append(car)

def reset_cars_for_session(start_time):
    """Rimette tutte le auto ai box con uscite scaglionate."""
    global car_index
    car_index = 0
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
        car.current_lap_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        car.last_sector_times = {'sector1': None, 'sector2': None, 'sector3': None}
        car.best_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        car.best_lap_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        car.stint_laps_remaining = car.stint_target_laps
        car.sector3_start_time = None
        car_index += 1

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
