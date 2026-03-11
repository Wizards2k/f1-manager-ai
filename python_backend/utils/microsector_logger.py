"""Micro-sector logging utilities for detailed lap analysis."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Disabled by default; set MICROSECTOR_DEBUG=1 to enable when needed
_FLAG = os.getenv("MICROSECTOR_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "microsector_debug.jsonl"


def _convert(value: Any) -> Any:
    if isinstance(value, (int, float, str)) or value is None:
        return value
    if isinstance(value, dict):
        return {k: _convert(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_convert(v) for v in value]
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "name"):
        return value.name
    return str(value)


def is_microsector_logging_enabled() -> bool:
    return _FLAG


def log_microsector(entry: Dict[str, Any]) -> None:
    if not _FLAG:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **_convert(entry),
    }
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


__all__ = ["log_microsector", "is_microsector_logging_enabled"]
