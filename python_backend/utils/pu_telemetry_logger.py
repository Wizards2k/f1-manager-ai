from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Set

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "pu_telemetry.log"
_ENABLED = os.getenv("DEBUG_PU_TELEMETRY", "0").lower() in {"1", "true", "yes", "on"}
def _normalize_car_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower().startswith("car"):
        text = text[3:]
    return text


_DRIVER_FILTERS = {
    _normalize_car_id(token)
    for token in os.getenv("PU_TELEMETRY_DRIVER", "16").split(",")
    if token.strip()
}


def _should_log_car(car_id: Any) -> bool:
    normalized = _normalize_car_id(car_id)
    if not normalized:
        return False
    if not _DRIVER_FILTERS:
        return True
    return normalized in _DRIVER_FILTERS
_SECTION_TRACKING: Dict[str, Dict[str, Set[str]]] = {}


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
    lap_deploy = _fmt_num(entry.get("lap_deploy_mj"), 3)
    harvest = _fmt_num(entry.get("lap_harvest_mj"), 3)
    mguh_direct_ratio = _fmt_num(entry.get("mguh_direct_ratio", 0.45), 3)
    mguh_es_ratio = _fmt_num(entry.get("mguh_es_ratio", 0.55), 3)
    lap_mguh_dir = entry.get("lap_mguh_direct_mj") or 0.0
    lap_mguh_es = entry.get("lap_mguh_es_mj") or 0.0
    mguh_dir = _fmt_num(lap_mguh_dir, 3)
    mguh_es = _fmt_num(lap_mguh_es, 3)
    mguh_total = _fmt_num(lap_mguh_dir + lap_mguh_es, 3)
    batt_budget = _fmt_num(entry.get("deploy_budget_total_mj"), 3)
    def_res = _fmt_num(entry.get("defense_reserve_available_mj"), 3)
    last_bucket = entry.get("bucket_key") or "none"
    bucket_type = entry.get("bucket_type") or last_bucket
    warnings = _fmt_warnings(entry.get("warnings"))
    section_deploy = _fmt_num(entry.get("deploy_mj"), 3)
    section_harvest = _fmt_num(entry.get("harvest_mj"), 3)
    bucket_budget_total = _fmt_num(entry.get("bucket_budget_total_mj"), 3)
    bucket_budget_remaining = _fmt_num(entry.get("bucket_budget_remaining_mj"), 3)
    bucket_section_cap = _fmt_num(entry.get("bucket_section_cap_mj"), 3)
    bucket_section_es = _fmt_num(entry.get("bucket_section_es_mj"), 3)
    bucket_section_dir = _fmt_num(entry.get("bucket_section_dir_mj"), 3)
    car_id = entry.get("car_id", "")
    lap = entry.get("lap", entry.get("lap_number", 0))
    sec = _extract_section_name(entry)
    ts = timestamp.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    return (
        f"{ts} INFO [PU] car={car_id} lap={lap} sec={sec} "
        f"soc={soc_mj}MJ ({soc_pct}%) deploy_ES={lap_deploy} harvest={harvest} "
        f"mguh_bias={mguh_direct_ratio}/{mguh_es_ratio} "
        f"mguh_dir={mguh_dir} mguh_es={mguh_es} mguh_total={mguh_total} "
        f"batt_budget={batt_budget} def_res={def_res} "
        f"bucket_type={bucket_type} Bucket_budget_Tot={bucket_budget_total} Bucket_budget_Remaing={bucket_budget_remaining} "
        f"Bucket_Section_CAP={bucket_section_cap} Bucket_Section_ES={bucket_section_es} "
        f"Bucket_Section_DIR={bucket_section_dir} last_bucket={last_bucket} "
        f"warnings={warnings} section_deploy={section_deploy} section_harvest={section_harvest}"
    )


def log_pu_section(entry: Dict[str, Any]) -> None:
    """Append a telemetry snapshot for the current PU section."""
    if not _ENABLED:
        return

    raw_car_id = entry.get("car_id")
    if not _should_log_car(raw_car_id):
        return
    car_id = _normalize_car_id(raw_car_id)
    if not car_id:
        return

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Reset file on each startup
    if not hasattr(log_pu_section, "_initialized"):
        with _LOG_FILE.open("w", encoding="utf-8") as fh:
            fh.write("")  # Create empty file
        _SECTION_TRACKING.clear()
        log_pu_section._initialized = True
    
    # Skip duplicate section entries (per car & lap)
    section_id = entry.get("section_id") or entry.get("section") or entry.get("sec")
    lap_number = entry.get("lap") or entry.get("lap_number") or entry.get("lap_id")
    if section_id is not None:
        lap_key = str(lap_number) if lap_number is not None else "__unknown__"
        state = _SECTION_TRACKING.get(car_id)
        if not state or lap_key not in state:
            state = {lap_key: set()}
            _SECTION_TRACKING[car_id] = state
        elif len(state) > 1:
            # Keep only current lap to avoid growth
            state.clear()
            state[lap_key] = set()

        seen_sections = state.setdefault(lap_key, set())
        if section_id in seen_sections:
            return
        seen_sections.add(section_id)

    payload = _convert(entry)
    timestamp = datetime.utcnow()
    line = _build_line(payload, timestamp)
    with _LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


__all__ = ["log_pu_section"]
