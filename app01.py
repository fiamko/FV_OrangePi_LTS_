#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask server pro FVE dashboard."""

import threading

from flask import Flask, send_from_directory, request, jsonify, redirect

from routes.dashboard import dashboard_bp
from routes.settings import settings_bp
from routes.statistics import statistics_bp
from services.mqtt_service import mqtt_worker


# Heslo pro ulozeni nastaveni — ze souboru secrets.py (NIKDY necommitovat!).
# Po naklonovani repozitare:  cp secrets.example.py secrets.py  a vypln skutecne heslo.
try:
    from secrets import SETTINGS_PASSWORD
except ImportError:
    SETTINGS_PASSWORD = "zmen-toto-heslo"

app = Flask(__name__)
app.config["SETTINGS_PASSWORD"] = SETTINGS_PASSWORD
app.register_blueprint(dashboard_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(statistics_bp)

STATIC_DIR = "static"


@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/manifest.json")
def manifest():
    host = request.host.lower()
    if "fv-peter" in host:
        return send_from_directory(STATIC_DIR, "manifest-web.json")
    return send_from_directory(STATIC_DIR, "manifest.json")


@app.route("/favicon.ico")
def favicon():
    host = request.host.lower()
    ico = "favicon-web.ico" if "fv-peter" in host else "favicon-lan.ico"
    return redirect(f"/static/icons/{ico}")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)


mqtt_thread = threading.Thread(target=mqtt_worker, daemon=True)
mqtt_thread.start()


if __name__ == "__main__":
    print("Spoustim Flask server pro vizualni test...")
    print("Otevrete prohlizec na: http://192.168.0.191:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
