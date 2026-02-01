# Configurazione F1 Manager AI
import json
import os

# Carica configurazione settori legacy
with open('sectors_config.json', 'r') as f:
    sectors_config = json.load(f)

# Carica profili circuito estesi (tempi e parametri superficie)
try:
    with open(os.path.join('config', 'circuit_info.json'), 'r') as f:
        circuit_profiles = json.load(f)
except FileNotFoundError:
    circuit_profiles = {}

# Circuito corrente (default Monza)
current_circuit = None
circuit_data = None
circuit_sectors = None
current_circuit_profile = None

def _resolve_circuit_file(circuit_id):
    circuits_path = os.path.join('circuits', f'{circuit_id}.json')
    if circuit_id and os.path.exists(circuits_path):
        return circuits_path
    return None

def set_current_circuit(circuit_id):
    """Imposta circuito corrente e settori solo quando esplicitamente richiesto."""
    global current_circuit, circuit_data, circuit_sectors, current_circuit_profile

    if not circuit_id:
        raise ValueError('Circuit ID is required')

    circuit_file = _resolve_circuit_file(circuit_id)
    if not circuit_file:
        raise FileNotFoundError('No circuit file found')

    with open(circuit_file, 'r') as f:
        circuit_data = json.load(f)

    current_circuit = circuit_id
    current_circuit_profile = circuit_profiles.get(current_circuit)

    if current_circuit_profile and current_circuit_profile.get('sectors'):
        circuit_sectors = current_circuit_profile['sectors']
    elif current_circuit in sectors_config:
        circuit_sectors = sectors_config[current_circuit]['sectors']
    else:
        circuit_sectors = sectors_config['monza']['sectors']

    return circuit_data


def load_circuit_data(circuit_id):
    """Restituisce i dati del circuito richiesto senza aggiornare lo stato globale."""
    circuit_file = _resolve_circuit_file(circuit_id)
    if not circuit_file:
        raise FileNotFoundError(f'No circuit file found for {circuit_id}')

    with open(circuit_file, 'r') as f:
        return json.load(f)


def get_current_circuit_profile():
    """Restituisce il profilo esteso del circuito corrente (se disponibile)."""
    return current_circuit_profile

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

# Costanti di gioco
SESSION_DURATION = 3600  # 1 ora in secondi
UPDATE_INTERVAL = 0.1  # 100ms update rate
DEFAULT_GAME_SPEED = 60.0
TARGET_SPEEDS = {
    'OUT_LAP': 70,  # m/s (~252 km/h)
    'HOT_LAP': 90,  # m/s (~324 km/h)
    'IN_LAP': 75   # m/s (~270 km/h)
}

# Costanti Flask
SECRET_KEY = 'f1-manager-secret'
SOCKETIO_CORS_ORIGINS = "*"

print("CONFIG: Caricate costanti F1 Manager AI")
