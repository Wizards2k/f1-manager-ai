# F1 Manager AI - Main Application
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import time
import logging

# Configura logging per vedere INFO
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Importa moduli specializzati
from config import SECRET_KEY, SOCKETIO_CORS_ORIGINS
from routes.api import register_routes
from utils import (
    race_cars, get_session_time_remaining, format_session_time,
    update_car_position, get_car_position, is_simulation_ready
)
from utils.game_logic import get_game_speed, get_pause_state, get_session_bests, mark_simulation_pending

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = SECRET_KEY
CORS(app)
socketio = SocketIO(app, cors_allowed_origins=SOCKETIO_CORS_ORIGINS)

register_routes(app)
mark_simulation_pending(reset_cars=True)

@socketio.on('connect')
def handle_connect():
    emit('connected', {'data': 'Connected to F1 Manager AI'})

def race_simulation():
    """Loop principale della simulazione"""
    while True:
        dt = 0.1  # 100ms update rate
        time.sleep(dt)
        
        if not is_simulation_ready():
            continue

        # Aggiorna posizioni auto
        for car in race_cars:
            update_car_position(car, dt)
        
        # Invia aggiornamenti ai client
        session_remaining = get_session_time_remaining()
        current_pause_state = get_pause_state()
        
        cars_data = []
        for car in race_cars:
            pos = get_car_position(car)
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
                'best_lap_sectors': getattr(car, 'best_lap_sectors', {}),
                'current_tire': car.current_tire.value,
                'tire_age': car.tire_age,
                'tire_wear': car.tire_wear,
                'is_player_controlled': car.is_player_controlled,
                'player_config': car.player_config if car.is_player_controlled else None,
                'setup_recommendation': car.setup_feedback if car.is_player_controlled else None,
                'fuel_percent': getattr(car, 'fuel_percent', None),
                'pace_level': getattr(car, 'pace_level', None),
                'ice_mode': getattr(car, 'ice_mode', None),
                'ers_mode': getattr(car, 'ers_mode', None),
                'stint_target_laps': getattr(car, 'stint_target_laps', None),
            })
        
        socketio.emit('race_update', {
            'cars': cars_data,
            'session_time_remaining': session_remaining,
            'session_time_formatted': format_session_time(session_remaining),
            'game_speed': get_game_speed(),
            'is_paused': current_pause_state,
            'session_bests': get_session_bests()
        })

if __name__ == '__main__':
    # Avvia simulazione in background
    import threading
    simulation_thread = threading.Thread(target=race_simulation)
    simulation_thread.daemon = True
    simulation_thread.start()
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5001, allow_unsafe_werkzeug=True)
