"""Centralized debug logging for temporary diagnostics."""
import json
import os
import threading
import time

LOG_PATH = os.environ.get('F1_DEBUG_LOG', '/tmp/f1_setup_debug.log')
_log_lock = threading.Lock()

def log_debug_event(event, **fields):
    """Append a structured event line to the debug log."""
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
        with open(LOG_PATH, 'a', encoding='utf-8') as handle:
            handle.write(line + '\n')
