"""Routes for the Engine Hub and ERS Map Manager."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, Optional

from flask import jsonify, render_template, request

from services.engine_ers_service import EngineERSService


engine_logger = logging.getLogger("engine_routes")


def _current_circuit_context() -> tuple[Optional[str], str]:
    import config

    requested_circuit = request.args.get("circuit")
    if requested_circuit:
        requested_circuit = requested_circuit.strip() or None

    current_circuit = requested_circuit or getattr(config, "current_circuit", None) or EngineERSService.DEFAULT_CIRCUIT_ID
    circuit_label = current_circuit or "No Active Circuit"

    if requested_circuit:
        try:
            catalog = EngineERSService.build_catalog(requested_circuit)
            circuit_label = catalog.get("circuit_name") or circuit_label
        except Exception:  # pragma: no cover - defensive guard for route rendering
            pass
    elif not getattr(config, "current_circuit", None):
        try:
            catalog = EngineERSService.build_catalog(current_circuit)
            circuit_label = catalog.get("circuit_name") or circuit_label
        except Exception:  # pragma: no cover - defensive guard for route rendering
            pass
    else:
        profile_getter = getattr(config, "get_current_circuit_profile", None)
        if callable(profile_getter):
            try:
                profile = profile_getter() or {}
            except Exception:  # pragma: no cover - defensive guard for route rendering
                profile = {}
            circuit_label = profile.get("name") or profile.get("circuit_name") or circuit_label
    return current_circuit, circuit_label


def _render_engine_section(
    *,
    section_title: str,
    section_subtitle: str,
    section_icon: str,
    section_status: str,
    section_tagline: str,
    section_focus: Iterable[str],
    back_url: str = "/engine",
) -> str:
    current_circuit, circuit_label = _current_circuit_context()
    circuit_query = _circuit_query_suffix(current_circuit)
    resolved_back_url = back_url
    if circuit_query and "circuit=" not in back_url:
        resolved_back_url = f"{back_url}{circuit_query}"
    return render_template(
        "engine-section.html",
        current_circuit=current_circuit,
        current_circuit_label=circuit_label,
        section_title=section_title,
        section_subtitle=section_subtitle,
        section_icon=section_icon,
        section_status=section_status,
        section_tagline=section_tagline,
        section_focus=list(section_focus),
        back_url=resolved_back_url,
        circuit_query=circuit_query,
    )


def _catalog_response(circuit_id: Optional[str], selected_map_id: Optional[str] = None) -> Dict[str, Any]:
    return EngineERSService.build_catalog(circuit_id, selected_map_id=selected_map_id)


def _serialize_catalog(catalog: Dict[str, Any]) -> str:
    return json.dumps(catalog, ensure_ascii=False)


def _circuit_query_suffix(circuit_id: Optional[str]) -> str:
    return f"?circuit={circuit_id}" if circuit_id else ""


def _json_from_request() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}


def _response_from_value_error(exc: ValueError, default_status: int = 400):
    message = str(exc)
    status = default_status
    if "already exists" in message:
        status = 409
    elif "cannot be deleted" in message:
        status = 403
    return jsonify({"ok": False, "error": message}), status


def register_engine_routes(app):
    """Register Engine Hub and ERS Map Manager routes."""

    @app.route("/engine")
    def engine_hub():
        current_circuit, circuit_label = _current_circuit_context()
        return render_template(
            "engine-hub.html",
            current_circuit=current_circuit,
            current_circuit_label=circuit_label,
            circuit_query=_circuit_query_suffix(current_circuit),
        )

    @app.route("/engine/development")
    def engine_development():
        return _render_engine_section(
            section_title="Engine Development",
            section_subtitle="Power Unit Research",
            section_icon="⚙️",
            section_status="Planned",
            section_tagline="Upgrade pipelines, reliability targets, and development milestones.",
            section_focus=(
                "Reliability development",
                "ICE upgrade planning",
                "Season-long performance roadmap",
            ),
        )

    @app.route("/engine/ice")
    def engine_ice_maps():
        return _render_engine_section(
            section_title="ICE Maps",
            section_subtitle="Combustion Maps",
            section_icon="🔥",
            section_status="Planned",
            section_tagline="ICE mapping presets for race pace, endurance, and thermal management.",
            section_focus=(
                "Power delivery curves",
                "Cooling balance",
                "Reliability-safe map tuning",
            ),
        )

    @app.route("/engine/ers")
    def engine_ers_maps():
        current_circuit, circuit_label = _current_circuit_context()
        selected_map_id = request.args.get("selected_map_id") or request.args.get("map")
        catalog = _catalog_response(current_circuit, selected_map_id=selected_map_id)
        return render_template(
            "ers-map-manager.html",
            current_circuit=current_circuit,
            current_circuit_label=circuit_label,
            ers_catalog=catalog,
            ers_catalog_json=_serialize_catalog(catalog),
            load_error="; ".join(catalog.get("errors", [])) if catalog.get("errors") else "",
            back_url=f"/engine{_circuit_query_suffix(current_circuit)}",
            circuit_options=EngineERSService.list_available_circuit_options(),
            selected_circuit_id=current_circuit,
        )

    @app.route("/engine/technicians")
    def engine_technicians():
        return _render_engine_section(
            section_title="Engine Technicians",
            section_subtitle="Engineering Crew",
            section_icon="👨\u200d🔧",
            section_status="Planned",
            section_tagline="Assign specialists to map development, reliability, and validation tasks.",
            section_focus=(
                "Engineer assignments",
                "Workload balance",
                "Validation support",
            ),
        )

    @app.route("/api/engine/ice/catalog")
    def api_engine_ice_catalog():
        import config

        requested_circuit = request.args.get("circuit")
        circuit_id = request.args.get("circuit_id") or requested_circuit or getattr(config, "current_circuit", None) or EngineERSService.DEFAULT_CIRCUIT_ID
        return jsonify(EngineERSService.build_ice_catalog(circuit_id))

    @app.route("/api/engine/ers/catalog")
    def api_engine_ers_catalog():
        import config

        requested_circuit = request.args.get("circuit")

        circuit_id = request.args.get("circuit_id") or requested_circuit or getattr(config, "current_circuit", None) or EngineERSService.DEFAULT_CIRCUIT_ID
        selected_map_id = request.args.get("selected_map_id") or request.args.get("map")
        return jsonify(_catalog_response(circuit_id, selected_map_id=selected_map_id))

    @app.route("/api/engine/ers/save", methods=["POST"])
    def api_engine_ers_save():
        import config

        payload = _json_from_request()
        circuit_id = str(payload.get("circuit_id") or getattr(config, "current_circuit", "") or EngineERSService.DEFAULT_CIRCUIT_ID).strip()
        map_id = str(payload.get("map_id") or "").strip()
        if not circuit_id:
            return jsonify({"ok": False, "error": "circuit_id is required"}), 400
        if not map_id:
            return jsonify({"ok": False, "error": "map_id is required"}), 400

        try:
            catalog = EngineERSService.save_map(
                circuit_id,
                map_id,
                map_updates=payload.get("map_data") or {},
                budget_updates=payload.get("budget_data") or {},
                budget_root_updates=payload.get("budget_root") or {},
            )
        except ValueError as exc:
            return _response_from_value_error(exc)
        except Exception as exc:  # pragma: no cover - defensive guard for persistence failures
            engine_logger.exception("ERS save failed for circuit=%s map=%s", circuit_id, map_id)
            return jsonify({"ok": False, "error": str(exc)}), 500

        return jsonify({
            "ok": True,
            "message": f"ERS map {map_id} saved successfully",
            "catalog": catalog,
            "selected_map_id": catalog.get("selected_map_id", map_id),
        })

    @app.route("/api/engine/ers/create", methods=["POST"])
    def api_engine_ers_create():
        import config

        payload = _json_from_request()
        circuit_id = str(payload.get("circuit_id") or getattr(config, "current_circuit", "") or EngineERSService.DEFAULT_CIRCUIT_ID).strip()
        map_id = str(payload.get("map_id") or "").strip()
        if not circuit_id:
            return jsonify({"ok": False, "error": "circuit_id is required"}), 400
        if not map_id:
            return jsonify({"ok": False, "error": "map_id is required"}), 400

        try:
            catalog = EngineERSService.create_map(
                circuit_id,
                map_id,
                source_map_id=payload.get("source_map_id"),
                map_updates=payload.get("map_data") or {},
                budget_updates=payload.get("budget_data") or {},
                budget_root_updates=payload.get("budget_root") or {},
            )
        except ValueError as exc:
            return _response_from_value_error(exc)
        except Exception as exc:  # pragma: no cover - defensive guard for persistence failures
            engine_logger.exception("ERS create failed for circuit=%s map=%s", circuit_id, map_id)
            return jsonify({"ok": False, "error": str(exc)}), 500

        return jsonify({
            "ok": True,
            "message": f"ERS map {map_id} created successfully",
            "catalog": catalog,
            "selected_map_id": catalog.get("selected_map_id", map_id),
        })

    @app.route("/api/engine/ers/delete", methods=["POST"])
    def api_engine_ers_delete():
        import config

        payload = _json_from_request()
        circuit_id = str(payload.get("circuit_id") or getattr(config, "current_circuit", "") or EngineERSService.DEFAULT_CIRCUIT_ID).strip()
        map_id = str(payload.get("map_id") or "").strip()
        if not circuit_id:
            return jsonify({"ok": False, "error": "circuit_id is required"}), 400
        if not map_id:
            return jsonify({"ok": False, "error": "map_id is required"}), 400

        try:
            catalog = EngineERSService.delete_map(circuit_id, map_id)
        except ValueError as exc:
            return _response_from_value_error(exc)
        except Exception as exc:  # pragma: no cover - defensive guard for persistence failures
            engine_logger.exception("ERS delete failed for circuit=%s map=%s", circuit_id, map_id)
            return jsonify({"ok": False, "error": str(exc)}), 500

        return jsonify({
            "ok": True,
            "message": f"ERS map {map_id} deleted successfully",
            "catalog": catalog,
            "selected_map_id": catalog.get("selected_map_id"),
        })
