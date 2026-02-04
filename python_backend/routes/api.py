# API Routes F1 Manager AI
import logging
import time
from flask import Flask, render_template, jsonify, send_from_directory, request

from data.teams import TEAMS
from models import CarState, TireCompound, DEFAULT_SETUP_CONFIG
from utils import (
    start_session_for_circuit,
    get_car_by_driver_number,
    set_player_team,
    race_cars,
    get_player_team_info,
    evaluate_setup,
    evaluate_setup_categories,
)
from utils.debug_log import log_debug_event


circuit_logger = logging.getLogger('circuit_api')
if not circuit_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    circuit_logger.addHandler(handler)
    circuit_logger.propagate = False
circuit_logger.setLevel(logging.INFO)


def _find_team_by_id(team_id: int):
    for team in TEAMS:
        if getattr(team, "team_id", None) == team_id:
            return team
    return None


def _error_response(message: str, status: int = 400):
    return jsonify({'error': message}), status

def register_routes(app):
    """Registra tutte le route API"""
    
    @app.route('/')
    def circuits_selection():
        return render_template('circuits.html')

    @app.route('/race')
    def index():
        return render_template('index.html')

    @app.route('/circuit')
    def circuit_v3():
        return render_template('index-v3.html')

    @app.route('/circuits/<path:filename>')
    def serve_circuit_files(filename):
        return send_from_directory('python_backend/circuits', filename)

    @app.route('/api/circuit')
    def get_circuit():
        """Restituisce dati del circuito richiesta senza modificare lo stato."""
        from flask import request
        import config

        circuit_id = request.args.get('circuit')
        try:
            if circuit_id:
                data = config.load_circuit_data(circuit_id)
            else:
                data = config.circuit_data
            circuit_logger.info(
                "GET /api/circuit from %s (session=%s, requested=%s)",
                request.remote_addr,
                getattr(config, 'current_circuit', None),
                circuit_id,
            )
        except FileNotFoundError:
            return jsonify({'error': f'Circuit file not found: {circuit_id}'}), 404

        return jsonify(data)

    @app.route('/api/circuit/<circuit_id>')
    def get_selected_circuit(circuit_id):
        """Carica i dati del circuito selezionato"""
        from flask import request
        import config

        circuit_data = config.set_current_circuit(circuit_id)
        start_session_for_circuit()
        circuit_logger.info(
            "GET /api/circuit/%s from %s (new circuit=%s)",
            circuit_id,
            request.remote_addr,
            getattr(config, 'current_circuit', None),
        )
        return jsonify(circuit_data)

    @app.route('/api/load_circuit', methods=['POST'])
    def load_circuit():
        """Carica dinamicamente il circuito nel backend"""
        try:
            from flask import request
            import config

            circuit_id = request.json.get('circuit_id') if request.is_json else None
            if not circuit_id:
                return jsonify({'error': 'Circuit ID required'}), 400

            circuit_data = config.set_current_circuit(circuit_id)
            start_session_for_circuit()
            circuit_logger.info(
                "POST /api/load_circuit from %s (new circuit=%s)",
                request.remote_addr,
                getattr(config, 'current_circuit', None),
            )
            return jsonify({
                'message': f'Circuit {circuit_id} loaded successfully',
                'circuit_id': circuit_id,
                'features': len(circuit_data.get('features', []))
            })
        except FileNotFoundError:
            return jsonify({'error': f'Circuit file not found: {circuit_id}'}), 404
        except Exception as e:
            return jsonify({'error': f'Failed to load circuit: {str(e)}'}), 500

    @app.route('/api/cars')
    def get_cars():
        """Restituisce posizioni attuali delle auto"""
        from utils import race_cars, get_car_position
        
        cars_data = []
        for car in race_cars:
            pos = get_car_position(car)
            cars_data.append({
                'driver_number': car.driver_number,
                'driver_name': car.driver_name,
                'team_name': car.team_name,
                'team_color': car.team_color,
                'position': pos,
                'lap_times': car.lap_times[-5:],  # Ultimi 5 tempi
                'total_laps': car.total_laps,
                'current_tire': car.current_tire.value,
                'tire_age': car.tire_age,
                'tire_wear': car.tire_wear,
                'is_player_controlled': car.is_player_controlled,
                'player_config': car.player_config if car.is_player_controlled else None,
                'setup_recommendation': car.setup_feedback if car.is_player_controlled else None,
            })
        return jsonify(cars_data)

    @app.route('/api/teams')
    def list_teams():
        payload = []
        for team in TEAMS:
            payload.append({
                'team_id': getattr(team, 'team_id', None),
                'team_name': team.nome_scuderia,
                'team_code': team.sigla_scuderia,
                'team_color': team.colore_team,
                'drivers': [
                    {
                        'number': pilot.numero_di_gara,
                        'name': pilot.nome_completo,
                        'abbrev': pilot.abbreviazione,
                    }
                    for pilot in team.piloti_titolari
                ]
            })
        return jsonify(payload)

    @app.route('/api/player/team')
    def get_player_team():
        info = get_player_team_info()
        if not info:
            return jsonify({'message': 'No player team configured'}), 404
        # Include resolved driver names for convenience
        driver_details = []
        for team in TEAMS:
            if getattr(team, "team_id", None) == info['team_id']:
                driver_details = [
                    {
                        'number': pilot.numero_di_gara,
                        'name': pilot.nome_completo,
                        'abbrev': pilot.abbreviazione,
                    }
                    for pilot in team.piloti_titolari
                ]
                break
        info['drivers'] = driver_details
        return jsonify(info)

    @app.route('/api/toggle_pause', methods=['POST'])
    def toggle_pause_route():
        """Attiva/disattiva la pausa"""
        from utils.game_logic import toggle_pause
        is_paused_state = toggle_pause()
        return jsonify({
            'message': 'Game ' + ('paused' if is_paused_state else 'resumed'),
            'is_paused': is_paused_state
        })

    @app.route('/api/set_speed', methods=['POST'])
    def set_speed():
        """Imposta la velocità di gioco"""
        from utils.game_logic import set_game_speed
        
        speed = float(request.json.get('speed', 1.0))
        
        if speed not in [1.0, 2.0, 4.0, 6.0]:
            return jsonify({'error': 'Speed must be 1.0, 2.0, 4.0, or 6.0'}), 400
        
        set_game_speed(speed)
        return jsonify({
            'message': f'Game speed set to {speed}x',
            'speed': speed
        })
    
    @app.route('/api/player/team/select', methods=['POST'])
    def select_player_team():
        payload = request.get_json(silent=True) or {}
        team_id = payload.get('team_id')
        if not isinstance(team_id, int):
            return _error_response('team_id must be an integer')
        team = _find_team_by_id(team_id)
        if not team:
            return _error_response('Team not found', 404)

        set_player_team(team_id)
        driver_numbers = [car.driver_number for car in race_cars if car.is_player_controlled]
        return jsonify({
            'team_id': team_id,
            'team_name': team.nome_scuderia,
            'driver_numbers': driver_numbers,
        })

    ICE_MODES = {'Save', 'Standard', 'Push'}
    ERS_MODES = {'Harvest', 'Neutral', 'Deploy', 'Overtake'}
    TYRE_MAP = {compound.value: compound for compound in (TireCompound.SOFT, TireCompound.MEDIUM, TireCompound.HARD)}

    def _get_player_car(driver_number: int):
        car = get_car_by_driver_number(driver_number)
        if not car:
            return None, _error_response('Car not found', 404)
        if not car.is_player_controlled:
            return None, _error_response('Car is not player controlled', 400)
        return car, None

    def _serialize_player_car(car):
        return {
            'driver_number': car.driver_number,
            'state': car.state.value if isinstance(car.state, CarState) else str(car.state),
            'player_config': car.player_config,
            'fuel_percent': car.fuel_percent,
            'pace_level': car.pace_level,
            'ice_mode': car.ice_mode,
            'ers_mode': car.ers_mode,
            'stint_target_laps': car.stint_target_laps,
            'stint_laps_remaining': car.stint_laps_remaining,
            'max_stint_laps': car.compute_max_stint_laps(car.player_config.get('fuel_percent', car.fuel_percent)),
            'stint_laps_target': car.player_config.get('stint_target_laps', car.stint_target_laps),
            'setup': car.player_config.get('setup', {**DEFAULT_SETUP_CONFIG}),
            'setup_recommendation': car.setup_feedback or {},
        }

    def _validate_setup_payload(setup_payload):
        if not isinstance(setup_payload, dict):
            return None, 'setup payload must be an object'
        extra_fields = set(setup_payload.keys()) - set(DEFAULT_SETUP_CONFIG.keys())
        if extra_fields:
            return None, f"Unknown setup fields: {', '.join(sorted(extra_fields))}"
        sanitized = {}
        for field, default_value in DEFAULT_SETUP_CONFIG.items():
            if field not in setup_payload:
                continue
            try:
                value = int(setup_payload[field])
            except (TypeError, ValueError):
                return None, f"{field} must be an integer"
            value = max(1, min(100, value))
            sanitized[field] = value
        if not sanitized:
            return None, 'Provide at least one setup field to update'
        return sanitized, None

    @app.route('/api/player/car/<int:driver_number>/configure', methods=['POST'])
    def configure_player_car(driver_number):
        payload = request.get_json(silent=True) or {}
        if not payload:
            return _error_response('Missing configuration payload')

        car, error = _get_player_car(driver_number)
        if error:
            return error

        is_in_box = car.state == CarState.BOX
        allowed_fields = {'pace_level', 'ice_mode', 'ers_mode'}
        if is_in_box:
            allowed_fields |= {'tyre_compound', 'fuel_percent', 'stint_target_laps'}

        invalid_fields = [key for key in payload.keys() if key not in allowed_fields]
        if invalid_fields:
            return _error_response(f'Fields not allowed in current state: {", ".join(invalid_fields)}')

        updates_applied = {}

        def clamp(value, low, high):
            return max(low, min(high, value))

        if 'pace_level' in payload:
            try:
                pace = int(payload['pace_level'])
            except (TypeError, ValueError):
                return _error_response('pace_level must be an integer')
            pace = clamp(pace, 1, 10)
            car.pace_level = pace
            car.player_config['pace_level'] = pace
            updates_applied['pace_level'] = pace

        if 'ice_mode' in payload:
            ice_mode = str(payload['ice_mode']).title()
            if ice_mode not in ICE_MODES:
                return _error_response(f'ice_mode must be one of: {", ".join(sorted(ICE_MODES))}')
            car.ice_mode = ice_mode
            car.player_config['ice_mode'] = ice_mode
            updates_applied['ice_mode'] = ice_mode

        if 'ers_mode' in payload:
            ers_mode = str(payload['ers_mode']).title()
            if ers_mode not in ERS_MODES:
                return _error_response(f'ers_mode must be one of: {", ".join(sorted(ERS_MODES))}')
            car.ers_mode = ers_mode
            car.player_config['ers_mode'] = ers_mode
            updates_applied['ers_mode'] = ers_mode

        if 'tyre_compound' in payload:
            compound_key = str(payload['tyre_compound']).lower()
            compound = TYRE_MAP.get(compound_key)
            if not compound:
                return _error_response('tyre_compound must be one of: soft, medium, hard')
            car.player_config['tyre_compound'] = compound.value
            updates_applied['tyre_compound'] = compound.value

        effective_fuel = car.player_config.get('fuel_percent', car.fuel_percent)
        if 'fuel_percent' in payload:
            try:
                fuel_percent = int(payload['fuel_percent'])
            except (TypeError, ValueError):
                return _error_response('fuel_percent must be an integer')
            fuel_percent = clamp(fuel_percent, 1, 100)
            car.fuel_percent = fuel_percent
            car.player_config['fuel_percent'] = fuel_percent
            effective_fuel = fuel_percent
            updates_applied['fuel_percent'] = fuel_percent

        max_stint_laps = car.compute_max_stint_laps(effective_fuel)
        if 'stint_target_laps' in payload:
            try:
                stint_target = int(payload['stint_target_laps'])
            except (TypeError, ValueError):
                return _error_response('stint_target_laps must be an integer')
            if stint_target < 1 or stint_target > max_stint_laps:
                return _error_response(f'stint_target_laps must be between 1 and {max_stint_laps}')
            car.player_config['stint_target_laps'] = stint_target
            updates_applied['stint_target_laps'] = stint_target

        if not updates_applied:
            return _error_response('No valid fields provided for current state')

        return jsonify({
            'message': 'Configuration updated',
            'car': _serialize_player_car(car),
            'updated_fields': updates_applied,
        })

    @app.route('/api/player/car/<int:driver_number>/setup/save', methods=['POST'])
    def save_player_setup(driver_number):
        payload = request.get_json(silent=True) or {}
        setup_payload = payload.get('setup')
        sanitized, error_msg = _validate_setup_payload(setup_payload)
        if error_msg:
            return _error_response(error_msg)

        car, error = _get_player_car(driver_number)
        if error:
            return error

        if car.state != CarState.BOX:
            return _error_response('Car must be in BOX to edit setup', 409)

        current_setup = car.player_config.setdefault('setup', {**DEFAULT_SETUP_CONFIG})
        current_setup.update(sanitized)
        log_debug_event(
            'setup_saved',
            driver=driver_number,
            state=str(car.state),
            fields=list(sanitized.keys()),
            total_laps=car.total_laps,
        )

        return jsonify({
            'message': 'Setup stored',
            'car': _serialize_player_car(car),
            'updated_fields': sanitized,
        })

    @app.route('/api/player/car/<int:driver_number>/setup', methods=['POST'])
    def update_player_setup(driver_number):
        payload = request.get_json(silent=True) or {}
        setup_payload = payload.get('setup')
        sanitized, error_msg = _validate_setup_payload(setup_payload)
        if error_msg:
            return _error_response(error_msg)

        car, error = _get_player_car(driver_number)
        if error:
            return error

        if car.state != CarState.BOX:
            return _error_response('Car must be in BOX to edit setup', 409)

        current_setup = car.player_config.setdefault('setup', {**DEFAULT_SETUP_CONFIG})
        current_setup.update(sanitized)
        log_debug_event(
            'setup_request',
            driver=driver_number,
            state=str(car.state),
            last_lap_type=car.last_lap_type.value if isinstance(car.last_lap_type, CarState) else car.last_lap_type,
            fields=list(sanitized.keys()),
            total_laps=car.total_laps,
        )
        # Provide setup feedback only after la vettura ha completato almeno un HOT_LAP
        if car.has_completed_hot_lap:
            recommendation = evaluate_setup(current_setup)
            categories = evaluate_setup_categories(current_setup)
            car.setup_feedback = recommendation
            car.setup_feedback['categories'] = categories
            log_debug_event(
                'setup_feedback_sent',
                driver=driver_number,
                state=str(car.state),
                last_lap_type=car.last_lap_type.value if isinstance(car.last_lap_type, CarState) else car.last_lap_type,
                has_completed_hot_lap=car.has_completed_hot_lap,
                fields=len(recommendation.get('fields', {})),
            )
        else:
            # Keep existing feedback; add placeholder message
            placeholder_msg = 'Awaiting on-track data: complete a hot lap for feedback.'
            if not car.setup_feedback:
                car.setup_feedback = {
                    'status': 'missing',
                    'message': placeholder_msg,
                    'tone': 'neutral',
                    'fields': {key: {'status': 'missing', 'range': None} for key in DEFAULT_SETUP_CONFIG.keys()}
                }
            else:
                car.setup_feedback.setdefault('status', 'pending')
                car.setup_feedback.setdefault('message', placeholder_msg)
            log_debug_event(
                'setup_feedback_placeholder',
                driver=driver_number,
                state=str(car.state),
                last_lap_type=car.last_lap_type.value if isinstance(car.last_lap_type, CarState) else car.last_lap_type,
                has_completed_hot_lap=car.has_completed_hot_lap,
            )

        return jsonify({
            'message': 'Setup updated',
            'car': _serialize_player_car(car)
        })

    @app.route('/api/player/car/<int:driver_number>/send_out', methods=['POST'])
    def send_player_car_out(driver_number):
        car, error = _get_player_car(driver_number)
        if error:
            return error
        if car.state != CarState.BOX:
            return _error_response('Car must be in BOX to send out', 409)

        config = car.player_config
        compound = TYRE_MAP.get(str(config.get('tyre_compound', car.current_tire.value)).lower())
        if not compound:
            return _error_response('Invalid tyre_compound in player config')

        fuel_percent = config.get('fuel_percent', car.fuel_percent)
        max_stint_laps = car.compute_max_stint_laps(fuel_percent)
        target_laps = config.get('stint_target_laps', car.stint_target_laps)
        target_laps = max(1, min(max_stint_laps, target_laps))

        car.set_tire_compound(compound)
        car.fuel_percent = fuel_percent
        car.pace_level = config.get('pace_level', car.pace_level)
        car.ice_mode = config.get('ice_mode', car.ice_mode)
        car.ers_mode = config.get('ers_mode', car.ers_mode)
        car.stint_target_laps = target_laps
        car.stint_laps_remaining = target_laps
        car.state = CarState.BOX
        car.box_time_until = car.session_start_time or time.time()
        car.exit_box()

        return jsonify({
            'message': 'Car sent out',
            'car': _serialize_player_car(car)
        })

    @app.route('/api/player/car/<int:driver_number>/box', methods=['POST'])
    def request_box(driver_number):
        car, error = _get_player_car(driver_number)
        if error:
            return error

        if car.state == CarState.BOX:
            return jsonify({'message': 'Car already in BOX', 'car': _serialize_player_car(car)})

        car.state = CarState.IN_LAP
        car.stint_laps_remaining = 0

        return jsonify({
            'message': 'Box request acknowledged',
            'car': _serialize_player_car(car)
        })

    return app
