"""Utilities for persisting lap-time debug data for offline analysis."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

TELEMETRY_DIR = Path(__file__).resolve().parent.parent / "telemetry"
TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = TELEMETRY_DIR / "lap_debug.jsonl"


def _sanitize(entry: Dict[str, Any]) -> Dict[str, Any]:
    def convert(value: Any):
        if isinstance(value, (int, float, str)) or value is None:
            return value
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        if isinstance(value, list):
            return [convert(v) for v in value]
        if hasattr(value, "value"):
            return value.value
        if hasattr(value, "name"):
            return value.name
        return str(value)

    return {k: convert(v) for k, v in entry.items()}


def log_lap_debug(entry: Dict[str, Any]) -> None:
    """Append a JSONL record with lap debug information."""
    payload = _sanitize({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **entry,
    })
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


__all__ = ["log_lap_debug", "LOG_FILE"]
