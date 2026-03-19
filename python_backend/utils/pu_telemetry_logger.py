from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "pu_telemetry.log"
_ENABLED = os.getenv("DEBUG_PU_TELEMETRY", "0").lower() in {"1", "true", "yes", "on"}
_DRIVER_FILTER = os.getenv("PU_TELEMETRY_DRIVER", "16").strip() or "16"


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


def _fmt_num(value: Any, digits: int = 3, default: str = "0.000") -> str:
    try:
        if value is None:
            return default
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return default


def _fmt_warnings(value: Any) -> str:
    if not value:
        return "[]"
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        values = list(value)
        if not values:
            return "[]"
        head = str(values[0])
        remaining = len(values) - 1
        return head if remaining <= 0 else f"{head} (+{remaining} more)"
    return str(value)


def _extract_section_name(entry: Dict[str, Any]) -> str:
    section_id = entry.get("section_id") or entry.get("section") or entry.get("section_name")
    if section_id:
        return str(section_id)
    idx = entry.get("section_index")
    if isinstance(idx, int):
        return f"sec_{idx + 1:02d}"
    return "sec_00"


def _build_line(entry: Dict[str, Any], timestamp: datetime) -> str:
    soc_mj = _fmt_num(entry.get("battery_soc_mj"), 3)
    soc_pct = _fmt_num(entry.get("battery_soc_pct"), 1, "0.0")
    deploy = _fmt_num(entry.get("lap_deploy_mj"), 3)
    harvest = _fmt_num(entry.get("lap_harvest_mj"), 3)
    mguh_dir = _fmt_num(entry.get("lap_mguh_direct_mj"), 3)
    mguh_es = _fmt_num(entry.get("lap_mguh_es_mj"), 3)
    mguh_remaining = _fmt_num(entry.get("mguh_direct_remaining_mj"), 3)
    batt_budget = _fmt_num(entry.get("deploy_budget_total_mj"), 3)
    def_res = _fmt_num(entry.get("defense_reserve_available_mj"), 3)
    last_bucket = entry.get("bucket_key") or "none"
    warnings = _fmt_warnings(entry.get("warnings"))
    section_deploy = _fmt_num(entry.get("deploy_mj"), 3)
    section_harvest = _fmt_num(entry.get("harvest_mj"), 3)
    car_id = entry.get("car_id", "")
    lap = entry.get("lap", entry.get("lap_number", 0))
    sec = _extract_section_name(entry)
    ts = timestamp.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    return (
        f"{ts} INFO [PU] car={car_id} lap={lap} sec={sec} "
        f"soc={soc_mj}MJ ({soc_pct}%) deploy={deploy} harvest={harvest} "
        f"mguh_dir={mguh_dir} mguh_es={mguh_es} mguh_remaining={mguh_remaining} "
        f"batt_budget={batt_budget} def_res={def_res} last_bucket={last_bucket} "
        f"warnings={warnings} section_deploy={section_deploy} section_harvest={section_harvest}"
    )


def log_pu_section(entry: Dict[str, Any]) -> None:
    """Append a telemetry snapshot for the current PU section."""
    if not _ENABLED:
        return

    car_id = str(entry.get("car_id", ""))
    if car_id != _DRIVER_FILTER:
        return

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Reset file on each startup
    if not hasattr(log_pu_section, "_initialized"):
        with _LOG_FILE.open("w", encoding="utf-8") as fh:
            fh.write("")  # Create empty file
        log_pu_section._initialized = True
    
    payload = _convert(entry)
    timestamp = datetime.utcnow()
    line = _build_line(payload, timestamp)
    with _LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


__all__ = ["log_pu_section"]
