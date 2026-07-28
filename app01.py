#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask server pro FVE dashboard."""

import threading

from flask import Flask, send_from_directory, request, jsonify, redirect

from routes.dashboard import dashboard_bp
from routes.settings import settings_bp
from routes.statistics import statistics_bp
from services.mqtt_service import mqtt_worker


# Heslo pro ulozeni nastaveni — nacteno ze secrets.py (neni v Gitu)
try:
    from secrets import SETTINGS_PASSWORD
except ImportError:
    SETTINGS_PASSWORD = "CHANGE_ME"
    print("VAROVANI: secrets.py nenalezen! Pouzivam vychozi heslo 'CHANGE_ME'.")
    print("Zkopiruj secrets.example.py do secrets.py a nastav vlastni heslo.")

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
    return response


@app.route("/manifest.json")
def serve_manifest():
    """Dynamický manifest — jiná ikona/název pro LAN vs. internet."""
    host = request.host.lower()
    is_tunnel = "fv-peter" in host

    return jsonify({
        "name": "ExtWeb - Elektrárna" if is_tunnel else "IntWeb - Elektrárna",
        "short_name": "ExtWeb" if is_tunnel else "IntWeb",
        "description": "Dashboard FV elektrarny (internet)" if is_tunnel
                       else "Dashboard FV elektrarny (LAN)",
        "start_url": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#000000",
        "theme_color": "#003366" if is_tunnel else "#228B22",
        "icons": [
            {"src": "/static/icons/icon-web-192.png",
             "sizes": "192x192", "type": "image/png",
             "purpose": "any maskable"}
            if is_tunnel else
            {"src": "/static/icons/icon-lan-192.png",
             "sizes": "192x192", "type": "image/png",
             "purpose": "any maskable"},
            {"src": "/static/icons/icon-web-512.png",
             "sizes": "512x512", "type": "image/png",
             "purpose": "any maskable"}
            if is_tunnel else
            {"src": "/static/icons/icon-lan-512.png",
             "sizes": "512x512", "type": "image/png",
             "purpose": "any maskable"},
        ]
    })


@app.route("/favicon.ico")
def serve_favicon():
    """Dynamický favicon — jiné ICO pro LAN vs. internet."""
    host = request.host.lower()
    ico = "favicon-web.ico" if "fv-peter" in host else "favicon-lan.ico"
    return redirect(f"/static/icons/{ico}")


@app.route("/static/<path:filename>")
def serve_static(filename):
    """Obsluha statickych souboru (CSS, JS, ikony)."""
    return send_from_directory(STATIC_DIR, filename)


mqtt_thread = threading.Thread(target=mqtt_worker, daemon=True)
mqtt_thread.start()


if __name__ == "__main__":
    print("Spoustim Flask server pro vizualni test...")
    print("Otevrete prohlizec na: http://192.168.0.191:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
