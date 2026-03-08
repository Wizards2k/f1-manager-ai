# API Routes F1 Manager AI
import logging
import time
from flask import Flask, render_template, jsonify, send_from_directory, request
from typing import Optional
from pathlib import Path
import json

from data.teams import TEAMS
from models import CarState, CarPhase, TireCompound, DEFAULT_SETUP_CONFIG
from utils import (
    start_session_for_circuit,
    get_car_by_driver_number,
    set_player_team,
    race_cars,
    get_player_team_info,
    evaluate_setup,
    evaluate_setup_categories,
    mark_simulation_pending,
)
from services.setup_engine_service import SetupEngineService
from services.tyre_inventory_service import TyreInventoryService
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

tyre_inventory_service = TyreInventoryService()


def _load_reference_telemetry(circuit_id: str):
    if not circuit_id:
        return []
    root = Path(__file__).resolve().parents[1]
    telemetry_path = root / 'data' / 'circuits' / '2025' / f'{circuit_id}_Telemetry.json'
    if not telemetry_path.exists():
        return []
    try:
        payload = json.loads(telemetry_path.read_text(encoding='utf-8'))
    except Exception:
        return []
    points = payload.get('reference_lap', {}).get('telemetry_points', [])
    normalized = []
    for point in points:
        normalized.append({
            'distance_m': round(float(point.get('distance', 0.0)), 3),
            'dt_s': 0.0,
            'speed_kph': round(float(point.get('speed', 0.0)), 3),
            'throttle_pct': float(point.get('throttle', 0.0)),
            'brake_pct': float(point.get('brake', 0.0)),
            'drs_active': point.get('drs') in {10, 12, 14},
            'steering_angle_deg': 0.0,
            'target_g_lat': 0.0,
        })
    return normalized


def _load_circuit_telemetry_markers(circuit_id: str):
    if not circuit_id:
        return []
    root = Path(__file__).resolve().parents[1]
    telemetry_path = root / 'data' / 'circuits' / '2025' / f'{circuit_id}_Telemetry.json'
    if not telemetry_path.exists():
        return []
    try:
        payload = json.loads(telemetry_path.read_text(encoding='utf-8'))
    except Exception:
        return []
    sections = (((payload or {}).get('geometry') or {}).get('sections') or [])
    markers = []
    for section in sections:
        start_m = section.get('start_m')
        if start_m is None:
            continue
        kind = str(section.get('kind') or 'Section')
        kind_key = kind.strip().lower()
        corner_number = section.get('corner_number')
        is_corner = corner_number is not None or 'corner' in kind_key or kind_key.startswith('turn')
        if not is_corner:
            continue
        name = section.get('name') or section.get('id') or 'Section'
        short_label = f"T{corner_number}" if corner_number else name
        markers.append({
            'id': section.get('id') or name,
            'name': f"Turn {corner_number}" if corner_number else name,
            'short_label': short_label,
            'kind': kind,
            'corner_number': corner_number,
            'distance_m': round(float(start_m), 1),
        })
    return markers


def register_routes(app):
    """Registra tutte le route API"""
    
    @app.route('/')
    def game_main_menu():
        return render_template('game-main-menu.html')

    @app.route('/circuits')
    def circuits_selection():
        return render_template('circuits.html')

    @app.route('/quick-race')
    def quick_race():
        """Quick Race - redirects to circuit selection"""
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

    @app.route('/api/session/reset', methods=['POST'])
    def reset_session_state():
        """Resetta la sessione corrente e riporta le auto allo stato iniziale."""
        mark_simulation_pending(reset_cars=True)
        return jsonify({'message': 'Session reset; select a circuit to start again.'})

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
                'tire_temps': getattr(car, 'tire_temps', None),
                'tire_temp_window': getattr(car, 'tire_temp_window', None),
                'is_player_controlled': car.is_player_controlled,
                'player_config': car.player_config if car.is_player_controlled else None,
                'setup_recommendation': car.setup_feedback if car.is_player_controlled else None,
                'brake_cooling': getattr(car, 'brake_cooling', {}),
            })
        return jsonify(cars_data)

    def _team_drivers(team):
        pilots = []
        if getattr(team, "pilota1", None):
            pilots.append(team.pilota1)
        if getattr(team, "pilota2", None):
            pilots.append(team.pilota2)
        if not pilots and hasattr(team, "piloti_titolari"):
            pilots.extend(team.piloti_titolari)
        if getattr(team, "pilota_riserva", None):
            pilots.append(team.pilota_riserva)
        return [
            {
                'number': pilot.numero_di_gara,
                'name': pilot.nome_completo,
                'abbrev': pilot.abbreviazione,
                'role': 'reserve' if pilot is getattr(team, 'pilota_riserva', None) else 'primary',
            }
            for pilot in pilots
        ]

    @app.route('/api/teams')
    def list_teams():
        payload = []
        for team in TEAMS:
            payload.append({
                'team_id': getattr(team, 'team_id', None),
                'team_name': team.nome_scuderia,
                'team_code': team.sigla_scuderia,
                'team_color': team.colore_team,
                'auto_id': getattr(team.auto, 'auto_id', None),
                'power_unit': getattr(team.power_unit, 'nome', None),
                'drivers': _team_drivers(team),
            })
        return jsonify(payload)

    @app.route('/api/player/team')
    def get_player_team():
        info = get_player_team_info()
        if not info:
            return jsonify({'message': 'No player team configured'}), 404
        # Include resolved driver names for convenience
        for team in TEAMS:
            if getattr(team, "team_id", None) == info['team_id']:
                info['drivers'] = _team_drivers(team)
                info['auto_id'] = getattr(team.auto, 'auto_id', None)
                info['power_unit'] = getattr(team.power_unit, 'nome', None)
                break
        return jsonify(info)

    @app.route('/api/driver/<driver_id>/tyre-inventory/<circuit_id>')
    def get_driver_tyre_inventory(driver_id, circuit_id):
        try:
            inventory = tyre_inventory_service.get_inventory(driver_id, circuit_id)
            return jsonify(inventory.to_dict())
        except FileNotFoundError as exc:
            return _error_response(str(exc), 404)
        except ValueError as exc:
            return _error_response(str(exc), 400)
        except Exception as exc:
            circuit_logger.exception("Failed to load tyre inventory", exc_info=exc)
            return _error_response('Failed to load tyre inventory', 500)

    @app.route('/api/driver/<driver_id>/tyre-usage', methods=['POST'])
    def update_driver_tyre_usage(driver_id):
        payload = request.get_json(silent=True) or {}
        circuit_id = payload.get('circuit_id')
        set_id = payload.get('set_id')
        if not circuit_id or not set_id:
            return _error_response('circuit_id and set_id are required')

        try:
            if 'available' in payload:
                tyre_set = tyre_inventory_service.mark_availability(
                    driver_id,
                    circuit_id,
                    set_id,
                    available=bool(payload.get('available')),
                )
            else:
                laps = payload.get('laps')
                if laps is None:
                    return _error_response('laps is required when updating wear')
                wear_factor = float(payload.get('wear_factor', 1.0))
                tyre_set = tyre_inventory_service.apply_usage(
                    driver_id,
                    circuit_id,
                    set_id,
                    laps=int(laps),
                    wear_factor=wear_factor,
                )

            return jsonify({
                'driver_id': driver_id,
                'circuit_id': circuit_id,
                'set': tyre_set.to_dict(),
            })
        except (ValueError, FileNotFoundError) as exc:
            return _error_response(str(exc), 400)
        except Exception as exc:
            circuit_logger.exception('Failed to update tyre usage', exc_info=exc)
            return _error_response('Failed to update tyre usage', 500)

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
        
        # Map button values to effective simulation speeds
        # 1x=1x, 2x=5x, 4x=15x, 6x=30x
        speed_map = {1.0: 1.0, 2.0: 5.0, 4.0: 15.0, 6.0: 30.0}
        effective_speed = speed_map.get(speed, speed)
        set_game_speed(effective_speed)
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

    ICE_MODE_CANONICAL = {
        'SAFETY_CAR': 'SAFETY_CAR',
        'PRACTICE': 'PRACTICE',
        'RACE': 'RACE',
        'QUALIFY': 'QUALIFY',
    }
    ICE_MODE_ALIASES = {
        'SAVE': 'SAFETY_CAR',
        'STANDARD': 'RACE',
        'PUSH': 'RACE',
        'QUALY': 'QUALIFY',
        'QUALIFYING': 'QUALIFY',
    }

    def _normalize_ers_mode(value: Optional[str]) -> Optional[str]:
        """Normalize ERS mode string to canonical name."""
        if not value:
            return None
        key = str(value).strip().replace(' ', '_').upper()
        # Map legacy names to new canonical names
        legacy_mapping = {
            'HARVEST': 'RECHARGE',
            'NEUTRAL': 'STANDARD',
            'DEPLOY': 'QUALIFY',
            'ATTACK': 'OVERTAKE',
        }
        # Direct canonical mapping
        canonical_modes = {
            'RECHARGE': 'RECHARGE',
            'STANDARD': 'STANDARD',
            'OVERTAKE': 'OVERTAKE',
            'QUALIFY': 'QUALIFY',
            'DEFENCE': 'DEFENCE',
        }
        # Check canonical first
        if key in canonical_modes:
            return canonical_modes[key]
        # Check legacy mapping
        return legacy_mapping.get(key)

    def _normalize_ice_mode(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        key = str(value).strip().replace(' ', '_').upper()
        if key in ICE_MODE_CANONICAL:
            return ICE_MODE_CANONICAL[key]
        return ICE_MODE_ALIASES.get(key)

    ERS_MODES = {'RECHARGE', 'STANDARD', 'OVERTAKE', 'QUALIFY', 'DEFENCE', 'HARVEST', 'NEUTRAL', 'DEPLOY', 'ATTACK'}
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
            'has_setup_feedback': bool(getattr(car, 'setup_feedback_ready', False) and car.setup_feedback),
            'setup_info_percent': round(getattr(car, 'setup_info_percent', 0), 1),
            'ideal_setup': car.player_config.get('ideal_setup'),
        }

    @app.route('/api/telemetry/compare')
    def get_telemetry_compare():
        from utils.game_logic import get_session_telemetry_store
        import config

        raw_car_ids = request.args.get('car_ids', '')
        lap_selector = request.args.get('lap', 'best')
        requested_ids = [item.strip() for item in raw_car_ids.split(',') if item.strip()]
        telemetry_store = get_session_telemetry_store()
        traces = []

        session_best = telemetry_store.build_session_best_trace() if telemetry_store else {}
        session_best_car_id = str(session_best.get('car_id')) if session_best else None

        for car_id in requested_ids:
            car = get_car_by_driver_number(int(car_id)) if car_id.isdigit() else None
            telemetry = telemetry_store.build_trace_payload(car_id, lap=lap_selector) if telemetry_store else {}
            points = telemetry.get('points', []) if telemetry else []
            traces.append({
                'car_id': car_id,
                'driver_number': car.driver_number if car else int(car_id) if car_id.isdigit() else car_id,
                'driver_name': car.driver_name if car else f'Driver #{car_id}',
                'team_name': car.team_name if car else None,
                'team_color': car.team_color if car else None,
                'lap_number': telemetry.get('lap_number') if telemetry else None,
                'lap_time_s': telemetry.get('lap_time_s') if telemetry else None,
                'lap_phase': telemetry.get('lap_phase') if telemetry else None,
                'is_session_best': bool(session_best_car_id and str(car_id) == session_best_car_id),
                'points': points,
            })
        circuit_id = getattr(config, 'current_circuit', None)

        return jsonify({
            'circuit_id': circuit_id,
            'lap': lap_selector,
            'session_best': {
                'car_id': session_best_car_id,
                'driver_number': int(session_best_car_id) if session_best_car_id and session_best_car_id.isdigit() else session_best_car_id,
                'lap_number': session_best.get('lap_number') if session_best else None,
                'lap_time_s': session_best.get('lap_time_s') if session_best else None,
            },
            'traces': traces,
        })

    @app.route('/api/telemetry/circuit-markers')
    def get_telemetry_circuit_markers():
        import config

        circuit_id = request.args.get('circuit_id') or getattr(config, 'current_circuit', None)
        markers = _load_circuit_telemetry_markers(circuit_id)
        return jsonify({
            'circuit_id': circuit_id,
            'markers': markers,
        })

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
            allowed_fields |= {'tyre_compound', 'tyre_set_id', 'fuel_percent', 'stint_target_laps'}

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
            normalized_ice = _normalize_ice_mode(payload['ice_mode'])
            if not normalized_ice:
                valid_values = ', '.join(sorted(ICE_MODE_CANONICAL.keys()))
                return _error_response(f'ice_mode must be one of: {valid_values}')
            car.ice_mode = normalized_ice
            car.player_config['ice_mode'] = normalized_ice
            updates_applied['ice_mode'] = normalized_ice

        if 'ers_mode' in payload:
            normalized_ers = _normalize_ers_mode(payload['ers_mode'])
            if not normalized_ers:
                valid_values = ', '.join(sorted({'RECHARGE', 'STANDARD', 'OVERTAKE', 'QUALIFY', 'DEFENCE'}))
                return _error_response(f'ers_mode must be one of: {valid_values}')
            car.ers_mode = normalized_ers
            car.player_config['ers_mode'] = normalized_ers
            updates_applied['ers_mode'] = normalized_ers

        if 'tyre_set_id' in payload:
            try:
                import config

                circuit_id = getattr(config, 'current_circuit', None)
                if not circuit_id:
                    return _error_response('Current circuit unavailable for tyre selection', 409)

                tyre_set_id = str(payload['tyre_set_id']).strip()
                inventory = tyre_inventory_service.get_inventory(str(driver_number), circuit_id)
                tyre_set = inventory.find_set(tyre_set_id)
                if tyre_set is None:
                    return _error_response(f'tyre_set_id {tyre_set_id} not found for driver {driver_number}')
                if not tyre_set.is_available:
                    return _error_response(f'tyre_set_id {tyre_set_id} is not available')

                car.player_config['tyre_set_id'] = tyre_set.set_id
                car.player_config['tyre_compound'] = tyre_set.compound
                updates_applied['tyre_set_id'] = tyre_set.set_id
                updates_applied['tyre_compound'] = tyre_set.compound
            except (ValueError, FileNotFoundError) as exc:
                return _error_response(str(exc), 400)

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
        car.reset_setup_info()
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
        car.reset_setup_info()
        log_debug_event(
            'setup_saved',
            driver=driver_number,
            state=str(car.state),
            fields=list(sanitized.keys()),
            total_laps=car.total_laps,
        )

        return jsonify({
            'message': 'Setup updated',
            'car': _serialize_player_car(car)
        })

    @app.route('/api/setup/ranges/<circuit_id>')
    def get_setup_ranges(circuit_id):
        payload = SetupEngineService.build_ranges_payload(circuit_id)
        return jsonify(payload)

    @app.route('/api/setup/validate', methods=['POST'])
    def validate_setup():
        payload = request.get_json(silent=True) or {}
        circuit_id = payload.get('circuit_id')
        setup_payload = payload.get('setup')
        result = SetupEngineService.validate_setup(setup_payload or {}, circuit_id)
        evaluation = SetupEngineService.evaluate(result.sanitized) if result.ok else {}
        return jsonify({
            'ok': result.ok,
            'errors': result.errors,
            'sanitized': result.sanitized,
            'physics': result.physics,
            'constraints': result.constraints,
            'circuit_key': result.circuit_key,
            'evaluation': evaluation,
        })

    @app.route('/api/setup/apply', methods=['POST'])
    def apply_setup():
        payload = request.get_json(silent=True) or {}
        driver_number = payload.get('driver_number')
        circuit_id = payload.get('circuit_id')
        setup_payload = payload.get('setup')
        if not isinstance(driver_number, int):
            return _error_response('driver_number must be an integer')
        if not isinstance(setup_payload, dict):
            return _error_response('setup payload must be an object')

        car, error = _get_player_car(driver_number)
        if error:
            return error
        if car.state != CarState.BOX:
            return _error_response('Car must be in BOX to edit setup', 409)

        validation = SetupEngineService.validate_setup(setup_payload, circuit_id)
        if not validation.ok:
            return jsonify({'ok': False, 'errors': validation.errors}), 400

        current_setup = car.player_config.setdefault('setup', {**DEFAULT_SETUP_CONFIG})
        current_setup.update(validation.sanitized)
        car.reset_setup_info()
        ideal_setup = SetupEngineService.build_ideal_setup(circuit_id, car)
        car.player_config['ideal_setup'] = ideal_setup

        return jsonify({
            'message': 'Setup applied',
            'car': _serialize_player_car(car),
            'ideal_setup': ideal_setup,
        })

    @app.route('/api/setup/ideal/<int:driver_number>')
    def get_ideal_setup(driver_number):
        circuit_id = request.args.get('circuit_id')
        car, error = _get_player_car(driver_number)
        if error:
            return error
        ideal = car.player_config.get('ideal_setup')
        if not ideal:
            ideal = SetupEngineService.build_ideal_setup(circuit_id, car)
            car.player_config['ideal_setup'] = ideal
        return jsonify({'ideal_setup': ideal, 'driver_number': driver_number})

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

        # V2 engine: delegate to SessionBridge
        from utils.game_logic import get_session_bridge
        bridge = get_session_bridge()
        if bridge and bridge.active:
            ok = bridge.player_send_out(
                car,
                compound=str(config.get('tyre_compound', car.current_tire.value)).lower(),
                fuel_percent=fuel_percent,
                stint_laps=target_laps,
            )
            if not ok:
                return _error_response('PITLANE QUEUE FULL', 409)
        else:
            # V1 engine: legacy
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

        # V2 engine: delegate to SessionBridge
        from utils.game_logic import get_session_bridge
        bridge = get_session_bridge()
        if bridge and bridge.active:
            bridge.player_box_now(car)
        else:
            car.state = CarState.IN_LAP
            car.stint_laps_remaining = 0

        return jsonify({
            'message': 'Box request acknowledged',
            'car': _serialize_player_car(car)
        })

    return app
