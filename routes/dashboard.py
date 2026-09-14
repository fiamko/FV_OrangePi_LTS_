from flask import Blueprint, current_app, jsonify, make_response, render_template, request

from models.state import current_data, data_lock
from services.dashboard_service import transform_mqtt_to_js


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    """Hlavni stranka dashboardu."""
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@dashboard_bp.route("/data")
def data():
    with data_lock:
        combined = transform_mqtt_to_js(current_data.copy())

    return jsonify(combined)


@dashboard_bp.route("/cerpadlo/toggle", methods=["POST"])
def cerpadlo_toggle():
    """Ruční přepnutí čerpadla (zaheslované). Nastaví ruční override na 60 minut."""
    if request.form.get("password", "") != current_app.config["SETTINGS_PASSWORD"]:
        return jsonify({"ok": False, "error": "Spatne heslo"}), 401

    import time as _time
    with data_lock:
        vystup = int(current_data.get("cerpadlo_vystup", 0) or 0)
        manual_state = vystup == 0  # stojí → zapni; běží → vypni
        current_data["cerpadlo_manual_state"] = manual_state
        current_data["cerpadlo_manual_until"] = _time.time() + 3600.0

    return jsonify({"ok": True, "state": "ON" if manual_state else "OFF", "manual_min": 60})
