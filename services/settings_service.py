import json
from pathlib import Path

# ESP zařízení — ze secrets.py (neni v Gitu), jinak prazdny seznam
try:
    from secrets import ESP_DEVICES
except ImportError:
    ESP_DEVICES = []


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
SEASON_NAMES = ("jaro", "leto", "podzim", "zima")

DEFAULT_FORM_SETTINGS = {
    "zapni4": 26.75,
    "vypni4": 26.50,
    "zapni2": 26.80,
    "vypni2": 26.60,
    "zapni3": 26.90,
    "vypni3": 26.70,
    "zapni_bojler": 27.00,
    "vypni_bojler": 26.80,
    "zapni_virivka": 27.10,
    "vypni_virivka": 26.90,
    "zapni_rele": 2500.0,
    "vypni_rele": 1800.0,
    "hystereze_s": 30.0,
    "rizeni_podle": "batteryVoltage",
    "power_bojler": 2000.0,
    "power_virivka": 2000.0,
    "power_podlaha300": 300.0,
    "power_podlaha2000": 2000.0,
    "power_podlaha2200": 2200.0,
    "battery_capacity_ah": 300.0,
    "sample_interval_s": 10.0,
}

PAIR_RULES = [
    ("zapni4", "vypni4", "Podlaha 300W"),
    ("zapni2", "vypni2", "Podlaha 2000W"),
    ("zapni3", "vypni3", "Podlaha 2200W"),
    ("zapni_bojler", "vypni_bojler", "Bojler"),
    ("zapni_virivka", "vypni_virivka", "Virivka"),
    ("zapni_rele", "vypni_rele", "Menic 2"),
]


def load_runtime_config():
    """Nacte zakladni runtime konfiguraci ze souboru config.json."""
    if not CONFIG_PATH.exists():
        return {}

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}


def _normalize_settings(source_data):
    settings = DEFAULT_FORM_SETTINGS.copy()

    for key, default_value in DEFAULT_FORM_SETTINGS.items():
        if key not in source_data:
            continue

        if isinstance(default_value, str):
            settings[key] = str(source_data[key])
        else:
            settings[key] = float(source_data[key])

    return settings


def _extract_profile_map(config_data):
    profiles = config_data.get("season_profiles", {})
    normalized = {}

    for season in SEASON_NAMES:
        normalized[season] = _normalize_settings(profiles.get(season, {}))

    return normalized


def get_form_settings(profile=None):
    """Vraci hodnoty pro formular nastaveni."""
    config_data = load_runtime_config()

    # Sloučení ESP zařízení ze secrets (mají přednost před config.json)
    if ESP_DEVICES:
        config_data["esp_devices"] = ESP_DEVICES

    if profile:
        profiles = _extract_profile_map(config_data)
        return profiles.get(profile, DEFAULT_FORM_SETTINGS.copy())

    return _normalize_settings(config_data)


def get_season_profiles():
    """Vraci vsechny sezonni profily v jednotnem tvaru."""
    return _extract_profile_map(load_runtime_config())


def validate_settings(settings):
    """Vraci seznam chyb pro zadane hodnoty nastaveni."""
    errors = []

    for on_key, off_key, label in PAIR_RULES:
        if float(settings[on_key]) <= float(settings[off_key]):
            errors.append(f"{label}: zapinaci mez musi byt vyssi nez vypinaci.")

    if float(settings["hystereze_s"]) < 0:
        errors.append("Hystereze musi byt nulova nebo kladna.")

    if float(settings["sample_interval_s"]) <= 0:
        errors.append("Interval vzorkovani musi byt kladny.")

    if float(settings["battery_capacity_ah"]) <= 0:
        errors.append("Kapacita baterie musi byt kladna.")

    if settings["rizeni_podle"] not in {"batteryVoltage", "batteryFlow", "inaB_V"}:
        errors.append("Neznamy zdroj rizeni.")

    return errors


def parse_form_settings(form_data):
    """Prevede formular na interni slovnik a provede typovou konverzi."""
    parsed = {}

    for key, default_value in DEFAULT_FORM_SETTINGS.items():
        raw_value = form_data.get(key, default_value)
        if isinstance(default_value, str):
            parsed[key] = str(raw_value)
        else:
            parsed[key] = float(raw_value)

    return parsed


def save_form_settings(form_data):
    """Ulozi aktivni hodnoty formulare do config.json a zachova ostatni klice."""
    config_data = load_runtime_config()
    updated_settings = parse_form_settings(form_data)
    errors = validate_settings(updated_settings)

    if errors:
        return updated_settings, errors

    config_data.update(updated_settings)

    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config_data, handle, ensure_ascii=False, indent=4)
        handle.write("\n")

    return updated_settings, []


def save_season_profile(form_data, season):
    """Ulozi zobrazenou konfiguraci jako vybrany sezonni profil."""
    config_data = load_runtime_config()
    profiles = _extract_profile_map(config_data)
    updated_settings = parse_form_settings(form_data)
    errors = validate_settings(updated_settings)

    if errors:
        return updated_settings, errors

    profiles[season] = updated_settings
    config_data["season_profiles"] = profiles

    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config_data, handle, ensure_ascii=False, indent=4)
        handle.write("\n")

    return updated_settings, []


def reset_form_settings():
    """Vrati formularove hodnoty na vychozi stav a ulozi je do config.json."""
    config_data = load_runtime_config()
    config_data.update(DEFAULT_FORM_SETTINGS)

    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config_data, handle, ensure_ascii=False, indent=4)
        handle.write("\n")

    return DEFAULT_FORM_SETTINGS.copy()
