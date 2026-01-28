# Configurazione F1 Manager AI
import json

# Carica dati del circuito di Monza
with open('monza_circuit.json', 'r') as f:
    circuit_data = json.load(f)

# Carica configurazione settori
with open('sectors_config.json', 'r') as f:
    sectors_config = json.load(f)

# Ottieni configurazione settori per il circuito corrente (Monza)
current_circuit = 'monza'
circuit_sectors = sectors_config[current_circuit]['sectors']

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
