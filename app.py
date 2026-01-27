from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import numpy as np
import time
import random
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'f1-manager-secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Carica dati del circuito di Monza
with open('monza_circuit.json', 'r') as f:
    circuit_data = json.load(f)

# Configurazione team e piloti F1 2025 con numeri reali ufficiali
F1_TEAMS = {
    'Red Bull Racing': {
        'color': '#1E41FF', 
        'drivers': {
            33: 'Max Verstappen',
            30: 'Liam Lawson'
        }
    },
    'Ferrari': {
        'color': '#DC0000', 
        'drivers': {
            16: 'Charles Leclerc',
            44: 'Lewis Hamilton'
        }
    },
    'Mercedes': {
        'color': '#00D2BE', 
        'drivers': {
            63: 'George Russell',
            12: 'Andrea Kimi Antonelli'
        }
    },
    'McLaren': {
        'color': '#FF8700', 
        'drivers': {
            4: 'Lando Norris',
            81: 'Oscar Piastri'
        }
    },
    'Alpine': {
        'color': '#0090FF', 
        'drivers': {
            10: 'Pierre Gasly',
            7: 'Jack Doohan'
        }
    },
    'Aston Martin': {
        'color': '#006F62', 
        'drivers': {
            14: 'Fernando Alonso',
            18: 'Lance Stroll'
        }
    },
    'Williams': {
        'color': '#005AFF', 
        'drivers': {
            23: 'Alexander Albon',
            55: 'Carlos Sainz Jnr'
        }
    },
    'Racing Bulls': {
        'color': '#2B4562', 
        'drivers': {
            22: 'Yuki Tsunoda',
            6: 'Isack Hadjar'
        }
    },
    'Sauber': {
        'color': '#52E252', 
        'drivers': {
            27: 'Nico Hulkenberg',
            5: 'Gabriel Bortoleto'
        }
    },
    'Haas': {
        'color': '#FFFFFF', 
        'drivers': {
            87: 'Oliver Bearman',
            31: 'Esteban Ocon'
        }
    }
}

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
        
    def get_position(self):
        """Restituisce coordinate attuali lungo il circuito"""
        return get_position_by_distance(self.distance_traveled)
    
    def update_position(self, dt):
        """Aggiorna posizione dell'auto basandosi sulla distanza"""
        # Velocità in metri al secondo (circa 250-350 km/h)
        speed_ms = (70 + self.speed * 30)  # 70-100 m/s
        
        # Aggiorna distanza percorsa
        self.distance_traveled += speed_ms * dt
        
        # Controlla completamento giro
        if self.distance_traveled >= circuit_length:
            self.distance_traveled = self.distance_traveled % circuit_length
            self.complete_lap()
    
    def complete_lap(self):
        """Registra tempo sul giro"""
        lap_time = time.time() - self.current_lap_start
        # Aggiungi variazione per tempi realistici (80 secondi ± 3 secondi)
        realistic_lap_time = 80.0 + random.uniform(-3.0, 3.0)
        self.lap_times.append(realistic_lap_time)
        self.current_lap_start = time.time()
        self.total_laps += 1

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

# Inizializza 20 auto (2 per team) con posizioni sfalsate
race_cars = []
car_index = 0
for team_name, team_data in F1_TEAMS.items():
    for driver_num, driver_name in team_data['drivers'].items():
        car = RaceCar(driver_num, driver_name, team_name, team_data['color'])
        # Posizione iniziale sfalsata per evitare sovrapposizione
        # Ogni auto parte a circa 150 metri di distanza l'una dall'altra
        car.distance_traveled = car_index * 150
        car_index += 1
        race_cars.append(car)

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
                'last_lap_time': car.lap_times[-1] if car.lap_times else None
            })
        
        socketio.emit('race_update', {'cars': cars_data})

if __name__ == '__main__':
    # Avvia simulazione in background
    import threading
    simulation_thread = threading.Thread(target=race_simulation)
    simulation_thread.daemon = True
    simulation_thread.start()
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)
