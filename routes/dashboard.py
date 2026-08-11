from flask import Blueprint, jsonify, make_response, render_template

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
