import json
import time

import paho.mqtt.client as mqtt

from ina226_mqtt import INA226
from models.state import current_data, data_lock
from services.controller_service import ControllerEngine
from services.history_service import HistoryRecorder
from services.settings_service import get_form_settings


# MQTT broker — ze secrets.py (neni v Gitu)
try:
    from secrets import MQTT_BROKER, MQTT_PORT
except ImportError:
    MQTT_BROKER = "localhost"
    MQTT_PORT = 1883

TOPIC_PREFIXES = ("menic/1/data/", "baterie/data/")


def on_connect(client, userdata, flags, rc, properties=None):
    if rc != 0:
        print(f"MQTT connect failed with code {rc}")
        return

    client.subscribe("menic/1/data")
    client.subscribe("menic/1/data/#")
    client.subscribe("baterie/data")
    client.subscribe("baterie/data/#")
    client.subscribe("fve/spotrebice/virivka/stav")
    client.subscribe("fve/spotrebice/podlaha2200/stav")
    client.subscribe("fve/spotrebice/podlaha2200/status")

def on_disconnect(client, userdata, rc, properties=None):
    if rc != 0:
        print(f"MQTT disconnected unexpectedly with code {rc}")


def on_message(client, userdata, msg):
    try:
        # === Speciální parsování: stav vířivky z ESP32 ===
        if msg.topic == "fve/spotrebice/virivka/stav":
            payload = json.loads(msg.payload.decode())
            if isinstance(payload, dict):
                proud_raw = float(payload.get("proud0", 0) or 0)
                # Filtr šumu: proud pod 0.05A (~11W) považujeme za nulu
                if proud_raw < 0.05:
                    proud_raw = 0.0
                with data_lock:
                    current_data["virivka_current"] = proud_raw
                    current_data["virivka_temperature"] = payload.get("teplota", 0)
                    current_data["virivka_relay1"] = payload.get("vystup1", 0)
                    current_data["virivka_relay2"] = payload.get("vystup2", 0)
                    current_data["virivka_status"] = payload.get("status", "OFF")
                    current_data["virivka_actual_w"] = round(proud_raw * 230.0, 1)
            return

        # === Speciální parsování: stav podlahovky 2200W z ESP32 ===
        if msg.topic == "fve/spotrebice/podlaha2200/stav":
            payload = json.loads(msg.payload.decode())
            if isinstance(payload, dict):
                vystup = int(payload.get("vystup", 0) or 0)
                with data_lock:
                    # Skutečný stav z ESP — pro animovanou čáru na dashboardu
                    current_data["heating1_actual"] = 2200.0 if vystup == 1 else 0.0
                    current_data["heating1_state_actual"] = vystup
                    current_data["podlahovka2200_vystup"] = vystup
                    current_data["podlahovka2200_duvod"] = payload.get("duvod", "")
            return

        if msg.topic == "fve/spotrebice/podlaha2200/status":
            payload = json.loads(msg.payload.decode())
            if isinstance(payload, dict) and payload.get("status") == "offline":
                with data_lock:
                    current_data["heating1_actual"] = 0.0
                    current_data["heating1_state_actual"] = 0
            return

        raw_payload = msg.payload.decode()
        payload = json.loads(raw_payload)

        if not isinstance(payload, dict):
            key = _key_from_topic(msg.topic)
            if not key:
                print("MQTT ERROR: payload is not a JSON object")
                return

            payload = {key: payload}

        with data_lock:
            current_data.update(payload)

    except json.JSONDecodeError:
        key = _key_from_topic(msg.topic)
        if not key:
            print("MQTT ERROR: payload is not JSON")
            return

        with data_lock:
            current_data[key] = msg.payload.decode()

    except Exception as error:
        print("MQTT ERROR:", error)


def _key_from_topic(topic):
    for prefix in TOPIC_PREFIXES:
        if topic.startswith(prefix):
            key = topic[len(prefix):].strip("/")
            return key or None
    return None


def mqtt_worker():
    # Jedno pomocne vlakno:
    # 1) posloucha MQTT data z menicu a baterie
    # 2) periodicky do MQTT doplnuje lokalni mereni z INA226
    # 3) vyhodnocuje pravidla vytizovani a publikuje pozadovane stavy spotrebicu
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    client.connect_async(MQTT_BROKER, MQTT_PORT, 60)

    client.loop_start()

    # Explicitni subscribe pro jistotu (i kdyz on_connect to udela taky)
    import time as _time
    _time.sleep(1)
    client.subscribe("fve/spotrebice/podlaha2200/stav")

    try:
        ina = INA226(client)
    except Exception as error:
        print("INA226 disabled:", error)
        ina = None

    controller = ControllerEngine()

    try:
        history = HistoryRecorder()
    except Exception as error:
        print("History disabled (database error):", error)
        history = None

    last_ina_read = 0.0
    last_history_write = 0.0
    ina_error_count = 0
    ina_retry_at = 0.0

    while True:
        try:
            now = time.time()
            settings = get_form_settings()

            if ina and now >= ina_retry_at and now - last_ina_read >= 4.0:
                data, error = ina.read()
                if error:
                    ina_error_count += 1
                    if ina_error_count == 1:
                        print("INA226 read error:", ina.last_error or error)
                    if ina_error_count >= 3:
                        print("INA226 temporarily disabled; retrying in 60 seconds")
                        ina_retry_at = now + 60.0
                        ina_error_count = 0
                elif isinstance(data, dict):
                    ina_error_count = 0
                    with data_lock:
                        current_data.update(data)
                last_ina_read = now

            controller.tick(client)

            sample_interval = max(float(settings.get("sample_interval_s", 10.0)), 1.0)
            if now - last_history_write >= sample_interval and history is not None:
                with data_lock:
                    snapshot = current_data.copy()
                history.record_snapshot(snapshot, settings)
                last_history_write = now

        except Exception as error:
            print("MQTT worker error:", error)

        time.sleep(1)
