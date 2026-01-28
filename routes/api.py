# API Routes F1 Manager AI
from flask import Flask, render_template, jsonify

def register_routes(app):
    """Registra tutte le route API"""
    
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/circuit')
    def get_circuit():
        """Restituisce dati del circuito"""
        from config import circuit_data
        return jsonify(circuit_data)

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
                'total_laps': car.total_laps
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
