import json
import time

from models.state import current_data, data_lock
from services.settings_service import get_form_settings


DEVICE_RULES = [
    {
        "name": "heating3",
        "label": "Podlaha 300W",
        "on_key": "zapni4",
        "off_key": "vypni4",
        "metric": "selected",
        "topic": "fve/spotrebice/podlaha300/set",
        "display_key": "heating3",
        "power": 300.0,
    },
    {
        "name": "heating2",
        "label": "Podlaha 2000W",
        "on_key": "zapni2",
        "off_key": "vypni2",
        "metric": "selected",
        "topic": "fve/spotrebice/podlaha2000/set",
        "display_key": "heating2",
        "power": 2000.0,
    },
    {
        "name": "heating1",
        "label": "Podlaha 2200W",
        "on_key": "zapni3",
        "off_key": "vypni3",
        "metric": "selected",
        "topic": "fve/spotrebice/podlaha2200/set",
        "display_key": "heating1",
        "power": 2200.0,
    },
    {
        "name": "boiler",
        "label": "Bojler",
        "on_key": "zapni_bojler",
        "off_key": "vypni_bojler",
        "metric": "selected",
        "topic": "fve/spotrebice/bojler/set",
        "display_key": "boiler",
        "power_setting": "power_bojler",
    },
    {
        "name": "virivka",
        "label": "Virivka",
        "on_key": "zapni_virivka",
        "off_key": "vypni_virivka",
        "metric": "selected",
        "topic": "fve/spotrebice/virivka/set",
        "display_key": "virivka",
        "power_setting": "power_virivka",
    },
    {
        "name": "menic2_rele",
        "label": "Menic 2",
        "on_key": "zapni_rele",
        "off_key": "vypni_rele",
        "metric": "pv_total",
        "topic": "fve/menic2/set",
        "state_key": "menic2_rele_state",
    },
]


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class ControllerEngine:
    def __init__(self):
        self.device_states = {rule["name"]: False for rule in DEVICE_RULES}
        self.last_change = {rule["name"]: 0.0 for rule in DEVICE_RULES}
        self.initial_state_sent = False

    def _get_metrics(self, snapshot, selected_metric):
        metric_key = selected_metric if selected_metric in {"batteryVoltage", "batteryFlow", "inaB_V"} else "batteryVoltage"
        return {
            "batteryVoltage": _safe_float(snapshot.get("battery_voltage"), 0.0),
            "batteryFlow": _safe_float(snapshot.get("battery_capacity"), 0.0),
            "inaB_V": _safe_float(snapshot.get("inaB_V"), 0.0),
            "pv_total": _safe_float(snapshot.get("pv_power"), 0.0) + _safe_float(snapshot.get("pv_power2"), 0.0),
            "selected": metric_key,
        }

    def _publish_state(self, client, rule, enabled, source_name, source_value, settings):
        payload = {
            "device": rule["name"],
            "label": rule["label"],
            "state": "ON" if enabled else "OFF",
            "enabled": enabled,
            "source": source_name,
            "source_value": round(source_value, 2),
            "on_threshold": settings[rule["on_key"]],
            "off_threshold": settings[rule["off_key"]],
            "hystereze_s": settings["hystereze_s"],
            "updated_at": int(time.time()),
        }
        client.publish(rule["topic"], json.dumps(payload), retain=True)

    def _publish_snapshot(self, client):
        payload = {
            name: {
                "enabled": enabled,
                "updated_at": int(self.last_change[name]),
            }
            for name, enabled in self.device_states.items()
        }
        client.publish("fve/controller/states", json.dumps(payload), retain=True)

    def _set_dashboard_value(self, rule, enabled, settings):
        display_key = rule.get("display_key")
        state_key = rule.get("state_key")
        if state_key:
            current_data[state_key] = 1 if enabled else 0

        if not display_key:
            return

        power = rule.get("power")
        if power is None:
            power = settings.get(rule.get("power_setting", ""), 0.0)

        current_data[display_key] = float(power) if enabled else 0.0
        current_data[f"{display_key}_state"] = 1 if enabled else 0

    def tick(self, client):
        settings = get_form_settings()

        with data_lock:
            snapshot = current_data.copy()

        metrics = self._get_metrics(snapshot, settings.get("rizeni_podle"))
        selected_metric_name = metrics["selected"]
        selected_metric_value = metrics[selected_metric_name]
        hysteresis_s = max(_safe_float(settings.get("hystereze_s"), 0.0), 0.0)
        now = time.time()
        changed = False
        publish_queue = []

        with data_lock:
            for rule in DEVICE_RULES:
                metric_name = selected_metric_name if rule["metric"] == "selected" else rule["metric"]
                source_value = metrics[metric_name]
                on_threshold = _safe_float(settings.get(rule["on_key"]), 0.0)
                off_threshold = _safe_float(settings.get(rule["off_key"]), 0.0)
                current_state = self.device_states[rule["name"]]
                next_state = current_state
                elapsed = now - self.last_change[rule["name"]]

                if current_state:
                    if source_value <= off_threshold and elapsed >= hysteresis_s:
                        next_state = False
                else:
                    if source_value >= on_threshold and elapsed >= hysteresis_s:
                        next_state = True

                self._set_dashboard_value(rule, next_state, settings)

                if next_state == current_state:
                    if not self.initial_state_sent:
                        publish_queue.append((rule, next_state, metric_name, source_value, settings))
                    continue

                self.device_states[rule["name"]] = next_state
                self.last_change[rule["name"]] = now
                publish_queue.append((rule, next_state, metric_name, source_value, settings))
                changed = True

            current_data["controller_source"] = selected_metric_name
            current_data["controller_value"] = selected_metric_value

        # MQTT publish OUTSIDE the lock, aby nezablokoval Flask endpointy
        for args in publish_queue:
            self._publish_state(client, *args)

        if changed or not self.initial_state_sent:
            self._publish_snapshot(client)
            self.initial_state_sent = True
