import datetime
import subprocess

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


@dashboard_bp.route("/balanc/toggle", methods=["POST"])
def balanc_toggle():
    """Ruční aktivace/zrušení balancování (zaheslované).

    První klik (off -> waiting): čeká na dosažení napětí balanc_voltaz.
    Další klik (waiting/balancing -> off): okamžitě zruší balancování.
    """
    if request.form.get("password", "") != current_app.config["SETTINGS_PASSWORD"]:
        return jsonify({"ok": False, "error": "Spatne heslo"}), 401

    with data_lock:
        state = current_data.get("balanc_state", "off")
        if state == "off":
            current_data["balanc_state"] = "waiting"
            current_data.pop("balanc_deadline", None)
            current_data.pop("balanc_remaining_s", None)
            new_state = "waiting"
        else:
            current_data["balanc_state"] = "off"
            current_data.pop("balanc_deadline", None)
            current_data.pop("balanc_remaining_s", None)
            new_state = "off"

    return jsonify({"ok": True, "state": new_state})


CERT_FILE = "/etc/caddy/fve-bundle.crt"
STATUS_FILE = "/home/fiam/.lego/renewal-status.txt"


def _cert_status():
    days_left = None
    not_after = None
    try:
        out = subprocess.check_output(
            ["openssl", "x509", "-in", CERT_FILE, "-noout", "-enddate"],
            stderr=subprocess.DEVNULL, timeout=5,
        ).decode().strip()
        raw = out.split("=", 1)[1].replace(" GMT", "").strip()
        dt = datetime.datetime.strptime(raw, "%b %d %H:%M:%S %Y")
        dt = dt.replace(tzinfo=datetime.timezone.utc)
        days_left = (dt - datetime.datetime.now(datetime.timezone.utc)).days
        not_after = dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    result = "unknown"
    last_run = None
    detail = ""
    try:
        with open(STATUS_FILE) as fh:
            parts = fh.read().strip().split("|")
        if parts and parts[0]:
            result = parts[0]
        if len(parts) > 1:
            last_run = parts[1]
        if len(parts) > 2:
            detail = parts[2]
    except Exception:
        pass

    return {
        "days_left": days_left,
        "not_after": not_after,
        "result": result,
        "last_run": last_run,
        "detail": detail,
    }


@dashboard_bp.route("/cert-status")
def cert_status():
    return jsonify(_cert_status())
