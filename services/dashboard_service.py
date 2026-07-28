from models.state import current_data


def transform_mqtt_to_js(mqtt_data):
    # Prevod syrovych MQTT klicu do nazvu, ktere ocekava frontend dashboardu.
    out = {}

    def safe_float(val):
        try:
            return float(val)
        except Exception:
            return 0.0

    out["pvPower1"] = float(mqtt_data.get("pv_power", 0) or 0)
    out["pvPower2"] = float(mqtt_data.get("pv_power2", 0) or 0)
    out["inv1Power"] = float(mqtt_data.get("output_apparent_power", 0) or 0)
    out["inv2Power"] = float(mqtt_data.get("output_active_power2", 0) or 0)
    out["load"] = float(mqtt_data.get("output_load_percent", 0) or 0)
    out["load2"] = float(mqtt_data.get("output_active_power2", 0) or 0)
    out["batVoltage"] = float(mqtt_data.get("battery_voltage", 25.0) or 25.0)
    out["battery_Flow"] = float(mqtt_data.get("battery_capacity", 100.0) or 10.0)
    out["inab_V"] = safe_float(mqtt_data.get("inaB_V", 0))
    out["inab_A"] = safe_float(mqtt_data.get("inaB_A", 0))
    out["inab_W"] = safe_float(mqtt_data.get("inaB_W", 0))
    out["chrging"] = float(mqtt_data.get("battery_charging_current", 0) or 0)
    out["dischrging"] = float(mqtt_data.get("battery_discharge_current", 0) or 0)
    out["chrging2"] = float(mqtt_data.get("battery_charging_current2", 0) or 0)
    out["dischrging2"] = float(mqtt_data.get("battery_discharge_current2", 0) or 0)
    out["boiler"] = float(current_data.get("boiler", 0) or 0)
    out["heating1"] = float(current_data.get("heating1", 0) or 0)  # OPI příkaz (číslo)
    out["heating1Actual"] = float(current_data.get("heating1_actual", 0) or 0)  # ESP stav (čára)
    out["heating1HasFeedback"] = "heating1_actual" in current_data  # true když ESP existuje
    out["podlahovka2200Duvod"] = mqtt_data.get("podlahovka2200_duvod", "")  # důvod z ESP
    out["heating2"] = float(current_data.get("heating2", 0) or 0)
    out["heating3"] = float(current_data.get("heating3", 0) or 0)
    # Vířivka — změřený výkon z ESP32 (skutečný odběr, i když je 0!)
    # Nominalni hodnotu z controlleru použijeme jen když ESP nedodal ŽÁDNÁ data.
    virivka_has_esp_data = "virivka_actual_w" in mqtt_data
    virivka_actual = float(mqtt_data.get("virivka_actual_w", 0) or 0)
    if virivka_has_esp_data:
        out["virivka"] = virivka_actual  # skutečná hodnota z ESP — i 0 W!
    else:
        out["virivka"] = float(current_data.get("virivka", 0) or 0)  # fallback: nominál
    out["virivkaActualW"] = virivka_actual
    out["virivkaOPI"] = float(current_data.get("virivka", 0) or 0)  # OPI příkaz (pro barvu)
    out["virivkaTemp"] = round(float(mqtt_data.get("virivka_temperature", 0) or 0), 1)
    out["virivkaStatus"] = mqtt_data.get("virivka_status", "OFF")
    out["menic2Enabled"] = float(current_data.get("menic2_rele_state", 0) or 0)

    return out
