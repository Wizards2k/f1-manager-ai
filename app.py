from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import numpy as np
import time
import random
from datetime import datetime, timedelta
from enum import Enum

# Importa configurazione
from config import (
    circuit_data, sectors_config, circuit_sectors, F1_TEAMS,
    SESSION_DURATION, UPDATE_INTERVAL, DEFAULT_GAME_SPEED, TARGET_SPEEDS
)

print("APP: Importata configurazione da config.py")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'f1-manager-secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Stati possibili per le auto durante le prove libere
class CarState(Enum):
    BOX = "BOX"
    OUT_LAP = "OUT LAP"
    HOT_LAP = "HOT LAP"
    IN_LAP = "IN LAP"

class RaceCar:
    def __init__(self, driver_number, driver_name, team_name, team_color):
        self.driver_number = driver_number
        self.driver_name = driver_name
        self.team_name = team_name
        self.team_color = team_color
        self.position_index = 0  # Posizione lungo il tracciato
        self.lap_times = []
        self.current_lap_start = time.time()
        self.speed = random.uniform(0.15, 0.25)  # Fattore velocità ridotto per movimento più realistico
        self.total_laps = 0
        self.distance_traveled = 0  # Distanza percorsa in metri
        
        # Nuovi attributi per prove libere
        self.state = CarState.BOX
        self.session_start_time = time.time()
        self.box_time_until = random.uniform(60, 300)  # Tempo prima della prima uscita (1-5 min)
        self.stint_laps_remaining = 0  # Giri rimanenti nella stint attuale
        self.stint_target_laps = random.randint(3, 6)  # Giri target per ogni stint
        self.total_session_laps = 0  # Giri totali in sessione
        self.last_lap_type = None
        
        # Attributi per tempi settoriali
        self.current_lap_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        self.best_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        self.last_sector_times = {'sector1': None, 'sector2': None, 'sector3': None}
        self.best_lap_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        self.current_lap_sector_start_time = time.time()
        self.last_sector_distance = 0
        self.sector3_start_time = None  # Tempo quando inizia il settore 3
        
    def get_position(self):
        """Restituisce coordinate attuali lungo il circuito"""
        if self.state == CarState.BOX:
            # Coordinate dei box (inizio circuito)
            return coordinates[0]
        return get_position_by_distance(self.distance_traveled)
    
    def update_position(self, dt):
        """Aggiorna posizione dell'auto basandosi sulla distanza e stato"""
        if is_paused:
            return  # Non muovere le auto se in pausa
            
        current_time = time.time()
        session_time = current_time - self.session_start_time
        
        # Applica moltiplicatore velocità di gioco al movimento
        adjusted_dt = dt * game_speed_multiplier
        
        # Logica stati per prove libere
        if self.state == CarState.BOX:
            if session_time >= self.box_time_until:
                self.exit_box()
            return
            
        elif self.state == CarState.OUT_LAP:
            # Out lap più lento (riscaldamento gomme) - velocità base
            base_speed_ms = (60 + self.speed * 20)  # 60-80 m/s
            actual_speed_ms = base_speed_ms * game_speed_multiplier
            old_distance = self.distance_traveled
            self.distance_traveled += actual_speed_ms * adjusted_dt
            
            # Controlla PRIMA passaggio settori, POI completamento giro
            self.check_sector_crossing(old_distance, self.distance_traveled)
            
            # Controlla completamento giro
            if self.distance_traveled >= circuit_length:
                self.distance_traveled = self.distance_traveled % circuit_length
                self.complete_lap(CarState.OUT_LAP)
                self.state = CarState.HOT_LAP
                self.current_lap_start = current_time
                
        elif self.state == CarState.HOT_LAP:
            # Hot lap a velocità massima - velocità base
            base_speed_ms = (70 + self.speed * 30)  # 70-100 m/s
            actual_speed_ms = base_speed_ms * game_speed_multiplier
            old_distance = self.distance_traveled
            self.distance_traveled += actual_speed_ms * adjusted_dt
            
            # Controlla PRIMA passaggio settori, POI completamento giro
            self.check_sector_crossing(old_distance, self.distance_traveled)
            
            # Controlla completamento giro
            if self.distance_traveled >= circuit_length:
                self.distance_traveled = self.distance_traveled % circuit_length
                self.complete_lap(CarState.HOT_LAP)
                self.stint_laps_remaining -= 1
                
                # Se ha finito i giri della stint, inizia rientro
                if self.stint_laps_remaining <= 0:
                    self.state = CarState.IN_LAP
                    self.current_lap_start = current_time
                    
        elif self.state == CarState.IN_LAP:
            # In lap più lento (raffreddamento) - velocità base
            base_speed_ms = (55 + self.speed * 15)  # 55-70 m/s
            actual_speed_ms = base_speed_ms * game_speed_multiplier
            old_distance = self.distance_traveled
            self.distance_traveled += actual_speed_ms * adjusted_dt
            
            # Controlla PRIMA passaggio settori, POI completamento giro
            self.check_sector_crossing(old_distance, self.distance_traveled)
            
            # Controlla completamento giro
            if self.distance_traveled >= circuit_length:
                self.distance_traveled = self.distance_traveled % circuit_length
                self.complete_lap(CarState.IN_LAP)
                self.enter_box()
                
    def check_sector_crossing(self, old_distance, new_distance):
        """Controlla se l'auto ha attraversato un settore e registra il tempo"""
        current_time = time.time()
        
        # Gestisce il wrap-around del circuito
        if old_distance > new_distance:  # Ha completato un giro
            old_distance = 0
            
        # Controlla attraversamento Sector 1
        sector1_distance = circuit_sectors['sector1']['distance']
        if old_distance < sector1_distance <= new_distance:
            # Calcola tempo simulato del settore 1 basato sulla distanza
            sector_distance = sector1_distance
            sector_time = self.calculate_simulated_sector_time(sector_distance, self.state)
            
            self.current_lap_sectors['sector1'] = sector_time
            self.last_sector_times['sector1'] = sector_time
            
            # Resetta settori successivi SOLO quando si inizia un nuovo giro (S1)
            self.current_lap_sectors['sector2'] = None
            self.current_lap_sectors['sector3'] = None
            
            # Aggiorna miglior settore se necessario
            if not self.best_sectors['sector1'] or sector_time < self.best_sectors['sector1']:
                self.best_sectors['sector1'] = sector_time
                
        # Controlla attraversamento Sector 2
        sector2_distance = circuit_sectors['sector2']['distance']
        if old_distance < sector2_distance <= new_distance:
            # Calcola tempo simulato del settore 2 basato sulla distanza del settore
            sector_distance = sector2_distance - circuit_sectors['sector1']['distance']
            sector_time = self.calculate_simulated_sector_time(sector_distance, self.state)
            
            self.current_lap_sectors['sector2'] = sector_time
            self.last_sector_times['sector2'] = sector_time
            
            # Inizia a tracciare il tempo per il settore 3
            self.sector3_start_time = current_time
            
            # Aggiorna miglior settore se necessario
            if not self.best_sectors['sector2'] or sector_time < self.best_sectors['sector2']:
                self.best_sectors['sector2'] = sector_time
                
        # Controlla attraversamento Sector 3 (fine giro)
        sector3_distance = circuit_sectors['sector3']['distance']
        if old_distance < sector3_distance <= new_distance:
            # Calcola tempo simulato del settore 3 basato sulla distanza del settore 3
            sector_distance = sector3_distance - circuit_sectors['sector2']['distance']
            sector_time = self.calculate_simulated_sector_time(sector_distance, self.state)
            
            self.current_lap_sectors['sector3'] = sector_time
            self.last_sector_times['sector3'] = sector_time
            
            # Aggiorna miglior settore se necessario
            if not self.best_sectors['sector3'] or sector_time < self.best_sectors['sector3']:
                self.best_sectors['sector3'] = sector_time
    
    def calculate_simulated_sector_time(self, sector_distance, lap_type):
        """Calcola tempo simulato per un settore basato sulla distanza e tipo di giro"""
        # Velocità media in m/s per tipo di giro
        if lap_type == CarState.OUT_LAP:
            avg_speed = random.uniform(65, 75)  # m/s
        elif lap_type == CarState.HOT_LAP:
            avg_speed = random.uniform(70, 80)  # m/s  
        elif lap_type == CarState.IN_LAP:
            avg_speed = random.uniform(60, 70)  # m/s
        else:
            avg_speed = random.uniform(68, 78)  # m/s
            
        # Calcola tempo base = distanza / velocità
        base_time = sector_distance / avg_speed
        
        # Aggiungi variazione casuale per realismo
        variation = random.uniform(-0.5, 0.5)
        
        return base_time + variation
                
    def exit_box(self):
        """Auto esce dai box per nuova stint"""
        self.state = CarState.OUT_LAP
        self.stint_laps_remaining = self.stint_target_laps
        self.current_lap_start = time.time()
        self.distance_traveled = 0
        
        # Resetta settori per nuovo stint
        self.current_lap_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        self.sector3_start_time = None
        
    def enter_box(self):
        """Auto rientra ai box"""
        self.state = CarState.BOX
        # Tempo ai box per la prossima uscita (5-20 minuti)
        self.box_time_until = time.time() - self.session_start_time + random.uniform(300, 1200)
        self.distance_traveled = 0
        
    def complete_lap(self, lap_type):
        """Registra tempo sul giro in base al tipo (tempi reali non influenzati da velocità gioco)"""
        lap_time = time.time() - self.current_lap_start
        
        # Tempi realistici in base al tipo di giro (sempre basati su velocità reale)
        if lap_type == CarState.OUT_LAP:
            # Out lap più lento
            realistic_lap_time = 85.0 + random.uniform(-2.0, 2.0)
        elif lap_type == CarState.HOT_LAP:
            # Hot lap con tempi migliori
            # Se abbiamo i 3 settori, rendi il lap time coerente con la somma dei settori
            s1 = self.current_lap_sectors.get('sector1')
            s2 = self.current_lap_sectors.get('sector2')
            s3 = self.current_lap_sectors.get('sector3')
            if s1 is not None and s2 is not None and s3 is not None:
                realistic_lap_time = (s1 + s2 + s3) + random.uniform(-0.15, 0.15)
            else:
                realistic_lap_time = 79.5 + random.uniform(-2.5, 2.5)
        elif lap_type == CarState.IN_LAP:
            # In lap più lento
            realistic_lap_time = 88.0 + random.uniform(-3.0, 3.0)
        else:
            realistic_lap_time = 80.0 + random.uniform(-3.0, 3.0)
            
        self.lap_times.append(realistic_lap_time)
        self.total_laps += 1
        self.total_session_laps += 1
        self.last_lap_type = lap_type
        
        # Aggiorna miglior tempo in sessione
        if not hasattr(self, 'best_lap_time') or realistic_lap_time < self.best_lap_time:
            self.best_lap_time = realistic_lap_time
            # Snapshot dei settori del best lap (stesso giro) per delta coerenti
            self.best_lap_sectors = {
                'sector1': self.current_lap_sectors.get('sector1'),
                'sector2': self.current_lap_sectors.get('sector2'),
                'sector3': self.current_lap_sectors.get('sector3')
            }
    

# Calcola distanze tra punti per movimento costante
coordinates = circuit_data['features'][0]['geometry']['coordinates']
distances = []
total_distance = 0
for i in range(len(coordinates)):
    if i == 0:
        distances.append(0)
    else:
        # Calcola distanza euclidea tra punti consecutivi
        lat1, lon1 = coordinates[i-1][1], coordinates[i-1][0]
        lat2, lon2 = coordinates[i][1], coordinates[i][0]
        # Conversione approssimativa in metri (1 grado ≈ 111km)
        dist = ((lat2 - lat1) * 111000) ** 2 + ((lon2 - lon1) * 111000 * np.cos(np.radians(lat1))) ** 2
        dist = np.sqrt(dist)
        total_distance += dist
        distances.append(total_distance)

# Normalizza distanze per movimento costante
circuit_length = total_distance

def get_position_by_distance(distance):
    """Restituisce coordinate basate sulla distanza percorsa"""
    # Normalizza distanza nel range del circuito
    normalized_distance = distance % circuit_length
    
    # Trova l'indice del segmento
    for i in range(len(distances) - 1):
        if distances[i] <= normalized_distance <= distances[i + 1]:
            # Interpolazione lineare tra punti
            t = (normalized_distance - distances[i]) / (distances[i + 1] - distances[i])
            lat1, lon1 = coordinates[i][1], coordinates[i][0]
            lat2, lon2 = coordinates[i + 1][1], coordinates[i + 1][0]
            lat = lat1 + t * (lat2 - lat1)
            lon = lon1 + t * (lon2 - lon1)
            return [lon, lat]
    
    return coordinates[0]

# Variabili globali per la sessione
session_start_time = time.time()
session_start_real_time = time.time()  # Tempo reale di inizio
game_speed_multiplier = 1.0  # Moltiplicatore velocità di gioco
accumulated_game_time = 0.0  # Tempo di gioco accumulato
last_speed_change_time = time.time()  # Tempo dell'ultimo cambio velocità
total_paused_time = 0.0  # Tempo totale passato in pausa
pause_start_time = None  # Quando è iniziata la pausa corrente
is_paused = False  # Stato di pausa corrente

def get_session_time_remaining():
    """Restituisce il tempo rimanente della sessione (aggiustato per velocità gioco e pause)"""
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
    
    # Calcola tempo accumulato fino ad ora
    current_real_time = time.time()
    if not is_paused:
        elapsed_since_last_change = current_real_time - last_speed_change_time
        accumulated_game_time += elapsed_since_last_change * game_speed_multiplier
    
    # Aggiorna velocità e tempo di cambio
    game_speed_multiplier = multiplier
    last_speed_change_time = current_real_time
    
    return game_speed_multiplier

def toggle_pause():
    """Attiva/disattiva la pausa"""
    global is_paused, pause_start_time, total_paused_time, accumulated_game_time, last_speed_change_time
    
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

# Inizializza 20 auto (2 per team) con posizioni sfalsate
race_cars = []
car_index = 0
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

@app.route('/api/toggle_pause', methods=['POST'])
def toggle_pause_route():
    """Attiva/disattiva la pausa"""
    is_paused_state = toggle_pause()
    return jsonify({
        'message': 'Game ' + ('paused' if is_paused_state else 'resumed'),
        'is_paused': is_paused_state
    })

@app.route('/api/set_speed', methods=['POST'])
def set_speed():
    """Imposta la velocità di gioco"""
    from flask import request
    speed = float(request.json.get('speed', 1.0))
    
    if speed not in [1.0, 2.0, 4.0, 6.0]:
        return jsonify({'error': 'Speed must be 1.0, 2.0, 4.0, or 6.0'}), 400
    
    set_game_speed(speed)
    return jsonify({
        'message': f'Game speed set to {speed}x',
        'speed': speed
    })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/circuit')
def get_circuit():
    """Restituisce dati del circuito"""
    return jsonify(circuit_data)

@app.route('/api/cars')
def get_cars():
    """Restituisce posizioni attuali delle auto"""
    cars_data = []
    for car in race_cars:
        pos = car.get_position()
        cars_data.append({
            'driver_number': car.driver_number,
            'driver_name': car.driver_name,
            'team_name': car.team_name,
            'team_color': car.team_color,
            'position': pos,
            'lap_times': car.lap_times[-5:],  # Ultimi 5 tempi
            'total_laps': car.total_laps
        })
    return jsonify(cars_data)

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # Resetta variabili di sessione per nuovo client
    global accumulated_game_time, last_speed_change_time, session_start_time, session_start_real_time
    accumulated_game_time = 0.0
    last_speed_change_time = time.time()
    session_start_time = time.time()
    session_start_real_time = time.time()
    print('Session variables reset for new client')
    emit('connected', {'data': 'Connected to F1 Manager AI'})

def race_simulation():
    """Loop principale della simulazione"""
    while True:
        dt = 0.1  # 100ms update rate
        time.sleep(dt)
        
        # Aggiorna posizioni auto
        for car in race_cars:
            car.update_position(dt)
        
        # Invia aggiornamenti ai client
        session_remaining = get_session_time_remaining()
        cars_data = []
        for car in race_cars:
            pos = car.get_position()
            cars_data.append({
                'driver_number': car.driver_number,
                'driver_name': car.driver_name,
                'team_name': car.team_name,
                'team_color': car.team_color,
                'position': pos,
                'lap_times': car.lap_times[-5:],
                'total_laps': car.total_laps,
                'state': car.state.value,
                'session_laps': car.total_session_laps,
                'stint_laps_remaining': car.stint_laps_remaining,
                'last_lap_type': car.last_lap_type.value if car.last_lap_type else None,
                'last_lap_time': car.lap_times[-1] if car.lap_times else None,
                'best_lap_time': getattr(car, 'best_lap_time', None),
                'last_sector_times': getattr(car, 'last_sector_times', {}),
                'current_lap_sectors': getattr(car, 'current_lap_sectors', {}),
                'best_sectors': getattr(car, 'best_sectors', {}),
                'best_lap_sectors': getattr(car, 'best_lap_sectors', {})
            })
        
        socketio.emit('race_update', {
            'cars': cars_data,
            'session_time_remaining': session_remaining,
            'session_time_formatted': format_session_time(session_remaining),
            'game_speed': game_speed_multiplier,
            'is_paused': is_paused
        })

if __name__ == '__main__':
    # Avvia simulazione in background
    import threading
    simulation_thread = threading.Thread(target=race_simulation)
    simulation_thread.daemon = True
    simulation_thread.start()
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)
