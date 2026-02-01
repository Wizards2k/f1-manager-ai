# API Routes F1 Manager AI
import logging
from flask import Flask, render_template, jsonify, send_from_directory
from utils import start_session_for_circuit


circuit_logger = logging.getLogger('circuit_api')
if not circuit_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    circuit_logger.addHandler(handler)
    circuit_logger.propagate = False
circuit_logger.setLevel(logging.INFO)

def register_routes(app):
    """Registra tutte le route API"""
    
    @app.route('/')
    def circuits_selection():
        return render_template('circuits.html')

    @app.route('/race')
    def index():
        return render_template('index.html')

    @app.route('/circuits/<path:filename>')
    def serve_circuit_files(filename):
        return send_from_directory('circuits', filename)

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
                'tire_wear': car.tire_wear
            })
        return jsonify(cars_data)

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
        from flask import request
        from utils.game_logic import set_game_speed
        
        speed = float(request.json.get('speed', 1.0))
        
        if speed not in [1.0, 2.0, 4.0, 6.0]:
            return jsonify({'error': 'Speed must be 1.0, 2.0, 4.0, or 6.0'}), 400
        
        set_game_speed(speed)
        return jsonify({
            'message': f'Game speed set to {speed}x',
            'speed': speed
        })
    
    return app
