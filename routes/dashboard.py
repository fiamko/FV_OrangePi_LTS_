from flask import Blueprint, jsonify, render_template

from models.state import current_data, data_lock
from services.dashboard_service import transform_mqtt_to_js


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    """Hlavni stranka dashboardu."""
    return render_template("index.html")


@dashboard_bp.route("/data")
def data():
    # Frontend si saha pouze sem. Tady se spoji posledni MQTT data do jednoho JSONu.
    with data_lock:
        combined = transform_mqtt_to_js(current_data.copy())

    return jsonify(combined)
