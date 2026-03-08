"""Centralized debug logging for diagnostics."""
import json
import os
import threading
import time

_default_log_dir = os.path.join(os.path.dirname(__file__), 'logs')
LOG_PATH = os.environ.get('F1_DEBUG_LOG') or os.path.join(_default_log_dir, 'f1_setup_debug.log')
AI_TYRE_LOG_PATH = os.environ.get('F1_AI_TYRE_DEBUG_LOG') or os.path.join(_default_log_dir, 'ai_tyre_debug.log')
_log_lock = threading.Lock()


def _append_json_line(path, record):
    line = json.dumps(record, ensure_ascii=False)
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(line + '\n')

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

    with _log_lock:
        _append_json_line(LOG_PATH, record)
        if str(event).startswith('ai_tyre_'):
            _append_json_line(AI_TYRE_LOG_PATH, record)
