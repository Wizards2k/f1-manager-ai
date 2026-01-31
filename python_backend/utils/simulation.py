# Simulation Logic F1 Manager AI
import time
import random
import config
from models import CarState
from utils.position import circuit_length
from utils.game_logic import update_session_bests
from utils.performance import project_sector_time

def update_car_position(car, dt):
    """Aggiorna posizione dell'auto basandosi sulla distanza e stato"""
    from utils.game_logic import is_paused, game_speed_multiplier
    
    if is_paused:
        return  # Non muovere le auto se in pausa
        
    current_time = time.time()
    session_time = current_time - car.session_start_time
    
    # Applica moltiplicatore velocità di gioco SOLO al tempo (non doppio)
    adjusted_dt = dt * game_speed_multiplier
    
    # Logica stati per prove libere
    if car.state == CarState.BOX:
        if session_time >= car.box_time_until:
            car.exit_box()
        return
        
    elif car.state == CarState.OUT_LAP:
        # Out lap più lento (riscaldamento gomme) - velocità base
        base_speed_ms = (60 + car.speed * 20)  # 60-80 m/s
        old_distance = car.distance_traveled
        car.distance_traveled += base_speed_ms * adjusted_dt
        
        # Controlla PRIMA passaggio settori, POI completamento giro
        check_car_sector_crossing(car, old_distance, car.distance_traveled)
        
        # Controlla completamento giro
        current_circuit_length = circuit_length()
        if car.distance_traveled >= current_circuit_length:
            car.distance_traveled = car.distance_traveled % current_circuit_length
            car.complete_lap(CarState.OUT_LAP)
            car.state = CarState.HOT_LAP
            car.current_lap_start = current_time
                
    elif car.state == CarState.HOT_LAP:
        # Hot lap a velocità massima - velocità base
        base_speed_ms = (70 + car.speed * 30)  # 70-100 m/s
        old_distance = car.distance_traveled
        car.distance_traveled += base_speed_ms * adjusted_dt
        
        # Controlla PRIMA passaggio settori, POI completamento giro
        check_car_sector_crossing(car, old_distance, car.distance_traveled)
        
        # Controlla completamento giro
        current_circuit_length = circuit_length()
        if car.distance_traveled >= current_circuit_length:
            car.distance_traveled = car.distance_traveled % current_circuit_length
            car.complete_lap(CarState.HOT_LAP)
            car.stint_laps_remaining -= 1
                
            # Se ha finito i giri della stint, inizia rientro
            if car.stint_laps_remaining <= 0:
                car.state = CarState.IN_LAP
                car.current_lap_start = current_time
                    
    elif car.state == CarState.IN_LAP:
        # In lap più lento (raffreddamento) - velocità base
        base_speed_ms = (55 + car.speed * 15)  # 55-70 m/s
        old_distance = car.distance_traveled
        car.distance_traveled += base_speed_ms * adjusted_dt
        
        # Controlla PRIMA passaggio settori, POI completamento giro
        check_car_sector_crossing(car, old_distance, car.distance_traveled)
        
        # Controlla completamento giro
        current_circuit_length = circuit_length()
        if car.distance_traveled >= current_circuit_length:
            car.distance_traveled = car.distance_traveled % current_circuit_length
            car.complete_lap(CarState.IN_LAP)
            car.enter_box()

def check_car_sector_crossing(car, old_distance, new_distance):
    """Controlla se l'auto ha attraversato un settore e registra il tempo"""
    current_time = time.time()
    
    # Gestisce il wrap-around del circuito
    if old_distance > new_distance:  # Ha completato un giro
        old_distance = 0
        
    if not config.circuit_sectors:
        return

    # Controlla attraversamento Sector 1
    sector1_distance = config.circuit_sectors['sector1']['distance']
    if old_distance < sector1_distance <= new_distance:
        # Calcola tempo simulato del settore 1 basato sulla distanza
        sector_distance = sector1_distance
        if getattr(car, 'current_lap_debug', None) is None:
            car.current_lap_debug = {
                'lap_sequence': car.total_laps + 1,
                'sectors': [],
            }
        sector_time = calculate_simulated_sector_time(car, sector_distance, car.state)
        
        car.current_lap_sectors['sector1'] = sector_time
        car.last_sector_times['sector1'] = sector_time
        
        # Resetta settori successivi SOLO quando si inizia un nuovo giro (S1)
        car.current_lap_sectors['sector2'] = None
        car.current_lap_sectors['sector3'] = None
        
        # Aggiorna miglior settore se necessario
        if not car.best_sectors['sector1'] or sector_time < car.best_sectors['sector1']:
            car.best_sectors['sector1'] = sector_time
            # Aggiorna anche session best
            update_session_bests(car)
            
    # Controlla attraversamento Sector 2
    sector2_distance = config.circuit_sectors['sector2']['distance']
    if old_distance < sector2_distance <= new_distance:
        # Calcola tempo simulato del settore 2 basato sulla distanza del settore
        sector_distance = sector2_distance - config.circuit_sectors['sector1']['distance']
        sector_time = calculate_simulated_sector_time(car, sector_distance, car.state)
        
        car.current_lap_sectors['sector2'] = sector_time
        car.last_sector_times['sector2'] = sector_time
        
        # Inizia a tracciare il tempo per il settore 3
        car.sector3_start_time = current_time
        
        # Aggiorna miglior settore se necessario
        if not car.best_sectors['sector2'] or sector_time < car.best_sectors['sector2']:
            car.best_sectors['sector2'] = sector_time
            # Aggiorna anche session best
            update_session_bests(car)
            
    # Controlla attraversamento Sector 3 (fine giro)
    sector3_distance = config.circuit_sectors['sector3']['distance']
    if old_distance < sector3_distance <= new_distance:
        # Calcola tempo simulato del settore 3 basato sulla distanza del settore 3
        sector_distance = sector3_distance - config.circuit_sectors['sector2']['distance']
        sector_time = calculate_simulated_sector_time(car, sector_distance, car.state)
        
        car.current_lap_sectors['sector3'] = sector_time
        car.last_sector_times['sector3'] = sector_time
        
        # Aggiorna miglior settore se necessario
        if not car.best_sectors['sector3'] or sector_time < car.best_sectors['sector3']:
            car.best_sectors['sector3'] = sector_time
            # Aggiorna anche session best
            update_session_bests(car)

def calculate_simulated_sector_time(car, sector_distance, lap_type):
    """Calcola il tempo del settore usando il modello prestazionale."""
    debug_bucket = getattr(car, "current_lap_debug", None)
    return project_sector_time(car, sector_distance, lap_type, debug_bucket)
