from . import config as _config

__all__ = [
    'circuit_data', 'sectors_config', 'circuit_sectors', 'current_circuit',
    'set_current_circuit', 'load_circuit_data', 'get_current_circuit_profile',
    'F1_TEAMS', 'SESSION_DURATION', 'UPDATE_INTERVAL', 'DEFAULT_GAME_SPEED', 'TARGET_SPEEDS',
    'SECRET_KEY', 'SOCKETIO_CORS_ORIGINS'
]

def __getattr__(name):
    if name in __all__:
        return getattr(_config, name)
    raise AttributeError(f"module 'config' has no attribute '{name}'")
