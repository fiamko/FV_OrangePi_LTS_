from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for

from services.settings_service import (
    get_form_settings,
    get_season_profiles,
    load_runtime_config,
    reset_form_settings,
    save_form_settings,
    save_season_profile,
)


settings_bp = Blueprint("settings", __name__)


def _check_password():
    """Vrati True, pokud je heslo spravne."""
    return request.form.get("password", "") == current_app.config["SETTINGS_PASSWORD"]


@settings_bp.route("/getSettings")
def get_settings():
    """Vraci aktivni hodnoty formulare nastaveni pro frontend."""
    return jsonify(get_form_settings())


@settings_bp.route("/nastaveni")
def nastaveni():
    """Stranka nastaveni s predvyplnenymi hodnotami."""
    selected_profile = request.args.get("profile", "").strip().lower() or None
    settings = get_form_settings(selected_profile)
    config_data = load_runtime_config()
    esp_devices = config_data.get("esp_devices", [])
    return render_template(
        "settings.html",
        settings=settings,
        selected_profile=selected_profile,
        errors=[],
        season_profiles=get_season_profiles(),
        esp_devices=esp_devices,
    )


@settings_bp.route("/uloz", methods=["POST"])
def uloz():
    """Zpracovani formulare, ulozeni nebo ulozeni profilu."""
    if not _check_password():
        return redirect(url_for("dashboard.index"))

    action = request.form.get("action", "save_active")
    selected_profile = request.form.get("selected_profile", "").strip().lower() or None
    config_data = load_runtime_config()
    esp_devices = config_data.get("esp_devices", [])

    if action.startswith("save_profile:"):
        season = action.split(":", 1)[1]
        settings, errors = save_season_profile(request.form, season)
        if errors:
            return render_template(
                "settings.html",
                settings=settings,
                selected_profile=selected_profile,
                errors=errors,
                season_profiles=get_season_profiles(),
                esp_devices=esp_devices,
            )

        return redirect(url_for("settings.nastaveni", profile=season))

    settings, errors = save_form_settings(request.form)
    if errors:
        return render_template(
            "settings.html",
            settings=settings,
            selected_profile=selected_profile,
            errors=errors,
            season_profiles=get_season_profiles(),
            esp_devices=esp_devices,
        )

    return redirect(url_for("dashboard.index"))


@settings_bp.route("/reset-settings", methods=["POST"])
def reset_settings():
    """Vrati hodnoty nastaveni na vychozi stav."""
    if not _check_password():
        return redirect(url_for("dashboard.index"))
    reset_form_settings()
    return redirect(url_for("settings.nastaveni"))
