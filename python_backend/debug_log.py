"""Centralized debug logging for diagnostics."""
import json
import os
import tempfile
import threading
import time

_default_log_dir = os.path.join(os.path.dirname(__file__), 'logs')
LOG_PATH = os.environ.get('F1_DEBUG_LOG') or os.path.join(_default_log_dir, 'f1_setup_debug.log')
_log_lock = threading.Lock()

def log_debug_event(event, **fields):
    """Append a structured event line to the debug log file."""
    record = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'event': event,
    }
    for key, value in fields.items():
        try:
            json.dumps(value)
            record[key] = value
        except (TypeError, ValueError):
            record[key] = str(value)

    line = json.dumps(record, ensure_ascii=False)
    with _log_lock:
        os.makedirs(os.path.dirname(LOG_PATH) or '.', exist_ok=True)
        with open(LOG_PATH, 'a', encoding='utf-8') as handle:
            handle.write(line + '\n')
