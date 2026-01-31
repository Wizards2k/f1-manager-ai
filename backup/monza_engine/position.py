# Position utilities F1 Manager AI
import numpy as np
from config import circuit_data

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

def get_car_position(car):
    """Restituisce coordinate attuali dell'auto lungo il circuito"""
    from models import CarState
    
    if car.state == CarState.BOX:
        # Coordinate dei box (inizio circuito)
        return coordinates[0]
    return get_position_by_distance(car.distance_traveled)
