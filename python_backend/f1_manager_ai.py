# F1 Manager AI - Main Application
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import time
import logging

# Configura logging: console + file
import os
_log_dir = os.path.join(os.path.dirname(__file__), 'logs')
_log_path = os.environ.get('F1_SERVER_LOG') or os.path.join(_log_dir, 'server.log')
os.makedirs(os.path.dirname(_log_path) or '.', exist_ok=True)
_log_fmt = '%(asctime)s [%(levelname)s] %(message)s'
handlers = [
    logging.StreamHandler(),
    logging.FileHandler(_log_path, mode='w', encoding='utf-8'),
]
logging.basicConfig(level=logging.INFO, format=_log_fmt, handlers=handlers)
logging.captureWarnings(True)

# Align werkzeug/flask/socketio loggers with root handlers so startup and HTTP logs are captured
for name in ('werkzeug', 'flask.app', 'socketio', 'engineio'):
    lg = logging.getLogger(name)
    lg.handlers = handlers
    lg.setLevel(logging.INFO)
    lg.propagate = False

# Importa moduli specializzati
from config import SECRET_KEY, SOCKETIO_CORS_ORIGINS
from routes.api import register_routes
from utils import (
    race_cars, get_session_time_remaining, format_session_time,
    update_car_position, get_car_position, is_simulation_ready
)
from utils.game_logic import get_game_speed, get_pause_state, get_session_bests, mark_simulation_pending, is_v2_engine_active, get_session_bridge
from utils.pu_telemetry_logger import reset_pu_telemetry_log
from lap_simulator.update_section import reset_lap_debug_log

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = SECRET_KEY
CORS(app)
socketio = SocketIO(app, cors_allowed_origins=SOCKETIO_CORS_ORIGINS)

reset_pu_telemetry_log()
reset_lap_debug_log()
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

        current_pause_state = get_pause_state()

        # Aggiorna posizioni auto
        bridge = get_session_bridge()
        if bridge and bridge.active:
            # V2 engine: delegate to SessionBridge
            if not current_pause_state:
                sim_dt = dt * get_game_speed()
                bridge.tick(sim_dt)
            session_remaining = bridge.session_time_remaining
        else:
            # V1 engine: legacy update
            for car in race_cars:
                update_car_position(car, dt)
            session_remaining = get_session_time_remaining()
        
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
                'tire_temps': getattr(car, 'tire_temps', None),
                'tire_temp_window': getattr(car, 'tire_temp_window', None),
                'is_player_controlled': car.is_player_controlled,
                'player_config': car.player_config if car.is_player_controlled else None,
                'setup_recommendation': car.setup_feedback if car.is_player_controlled else None,
                'setup_categories': car.setup_feedback.get('categories') if car.is_player_controlled and car.setup_feedback else None,
                'has_setup_feedback': bool(getattr(car, 'setup_feedback_ready', False) and car.setup_feedback) if car.is_player_controlled else False,
                'setup_info_percent': round(getattr(car, 'setup_info_percent', 0), 1),
                'driver_feedback': car.last_driver_feedback if car.is_player_controlled else None,
                'fuel_percent': getattr(car, 'fuel_percent', None),
                'pace_level': getattr(car, 'pace_level', None),
                'ice_mode': getattr(car, 'ice_mode', None),
                'ers_mode': getattr(car, 'ers_mode', None),
                'stint_target_laps': getattr(car, 'stint_target_laps', None),
                'max_stint_laps': 150,
                'blue_flag': bridge.get_car_blue_flag(str(car.driver_number)) if bridge and bridge.active else False,
                'pu_stats': getattr(car, 'pu_stats', {}),
                'brake_diagnostics': getattr(car, 'brake_diagnostics', {}),
                'brake_cooling': getattr(car, 'brake_cooling', {}),
                'brake_thermal': getattr(car, 'brake_thermal', {}),
                'aero_balance': getattr(car, 'aero_balance', None),
                'drag_index': getattr(car, 'drag_index', None),
                'cooling_margin': getattr(car, 'cooling_margin', None),
                'tire_core_temps': getattr(car, 'tire_core_temps', {}),
                'tyre_states': getattr(car, 'tyre_states', {}),
                # AI debug fields for setup/tyre tooltip
                'ai_setup_score': getattr(car, 'ai_setup_score', None),
                'ai_setup_threshold': getattr(car, 'ai_setup_threshold', None),
                'ai_setup_complete': getattr(car, 'ai_setup_complete', False),
                'ai_total_runs': getattr(car, 'ai_total_runs', 0),
                'ai_min_runs_required': getattr(car, 'ai_min_runs_required', 0),
                'ai_tyre_set_id': getattr(car, 'ai_tyre_set_id', None),
                'ai_tyre_condition': getattr(car, 'ai_tyre_condition', None),
                'ai_tyre_heat_cycles': getattr(car, 'ai_tyre_heat_cycles', 0),
                'ai_program': getattr(car, 'ai_program', None),
            })
        
        session_flag = bridge.session_flag if bridge and bridge.active else 'green'
        battle_events = []
        if bridge and bridge.active and bridge.battle_events:
            battle_events = [
                {
                    'type': ev.event_type,
                    'attacker': ev.attacker_id,
                    'defender': ev.defender_id,
                    'section': ev.section_id,
                    'scenario': ev.scenario,
                    'outcome': ev.outcome,
                    'message': ev.message,
                }
                for ev in bridge.battle_events
            ]

        socketio.emit('race_update', {
            'cars': cars_data,
            'session_time_remaining': session_remaining,
            'session_time_formatted': format_session_time(session_remaining),
            'game_speed': {1.0: 1, 5.0: 2, 15.0: 4, 30.0: 6}.get(get_game_speed(), get_game_speed()),
            'is_paused': current_pause_state,
            'session_bests': get_session_bests(),
            'session_flag': session_flag,
            'battle_events': battle_events,
        })

        if bridge and bridge.active:
            event_feed = bridge.pop_event_feed()
            if event_feed:
                socketio.emit('event_feed', event_feed)

if __name__ == '__main__':
    # Avvia simulazione in background
    import threading
    simulation_thread = threading.Thread(target=race_simulation)
    simulation_thread.daemon = True
    simulation_thread.start()
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5001, allow_unsafe_werkzeug=True)
