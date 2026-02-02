# Position utilities F1 Manager AI
import numpy as np
import config

coordinates = []
distances = []
_circuit_length = 0
_cached_circuit_id = None

def _extract_coordinates(data):
    if not data:
        return []
    if data.get('type') == 'FeatureCollection':
        return data['features'][0]['geometry']['coordinates']
    if data.get('type') == 'Feature':
        return data['geometry']['coordinates']
    raise ValueError('Invalid circuit data format')

def _rebuild_cache():
    global coordinates, distances, _circuit_length, _cached_circuit_id

    coords = _extract_coordinates(config.circuit_data)
    if not coords:
        coordinates = []
        distances = []
        _circuit_length = 0
        _cached_circuit_id = config.current_circuit
        return

    distances = []
    total_distance = 0
    for i in range(len(coords)):
        if i == 0:
            distances.append(0)
        else:
            lat1, lon1 = coords[i - 1][1], coords[i - 1][0]
            lat2, lon2 = coords[i][1], coords[i][0]
            dist = ((lat2 - lat1) * 111000) ** 2 + ((lon2 - lon1) * 111000 * np.cos(np.radians(lat1))) ** 2
            dist = np.sqrt(dist)
            total_distance += dist
            distances.append(total_distance)

    coordinates = coords
    _circuit_length = total_distance
    _cached_circuit_id = config.current_circuit

def _ensure_cache():
    if _cached_circuit_id != config.current_circuit or not coordinates:
        _rebuild_cache()

def circuit_length():
    """Restituisce la lunghezza del circuito corrente"""
    _ensure_cache()
    return _circuit_length

def get_position_by_distance(distance):
    """Restituisce coordinate basate sulla distanza percorsa"""
    _ensure_cache()
    if not coordinates:
        return [0, 0]
    # Normalizza distanza nel range del circuito
    normalized_distance = distance % _circuit_length
    
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

def get_car_position(car):
    """Restituisce coordinate attuali dell'auto lungo il circuito"""
    from models import CarState
    _ensure_cache()
    if not coordinates:
        return [0, 0]
    if car.state == CarState.BOX:
        # Coordinate dei box (inizio circuito)
        return coordinates[0]
    return get_position_by_distance(car.distance_traveled)
