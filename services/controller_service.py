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
        "label": "Virivka R1",
        "on_key": "zapni_virivka",
        "off_key": "vypni_virivka",
        "metric": "selected",
        "topic": "fve/spotrebice/virivka/set",  # sdílený topic s virivka2
        "display_key": "virivka",
        "power_setting": "power_virivka",
    },
    {
        "name": "virivka2",
        "label": "Virivka R2",
        "on_key": "zapni_virivka2",
        "off_key": "vypni_virivka2",
        "metric": "selected",
        "topic": "fve/spotrebice/virivka/set",  # sdílený topic s virivka
        "display_key": "virivka2",
        "power_setting": "power_virivka2",
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
        # Čerpadlo (eWeLink) — vlastní logika mimo DEVICE_RULES
        self.device_states["cerpadlo"] = False
        self.last_change["cerpadlo"] = 0.0
        self.cerpadlo_ohrev_accum = 0.0
        self.cerpadlo_last_tick = time.time()
        self.cerpadlo_last_day = None
        self.cerpadlo_on_since = None
        self.cerpadlo_low_delta_since = time.time()

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

    def _publish_virivka_combined(self, client, settings, source_name, source_value):
        r1 = self.device_states.get("virivka", False)
        r2 = self.device_states.get("virivka2", False)
        payload = {
            "relay1": 1 if r1 else 0,
            "relay2": 1 if r2 else 0,
            "source": source_name,
            "source_value": round(source_value, 2),
            "updated_at": int(time.time()),
        }
        client.publish("fve/spotrebice/virivka/set", json.dumps(payload), retain=True)

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

    def _publish_cerpadlo(self, client, enabled, settings, delta_t, ohrev_min):
        payload = {
            "device": "cerpadlo",
            "label": "Cerpadlo",
            "state": "ON" if enabled else "OFF",
            "enabled": enabled,
            "source": "ohrev_kumulativni",
            "source_value": round(ohrev_min, 1),
            "off_threshold": _safe_float(settings.get("cerpadlo_vypni_deltaT", 10.0), 10.0),
            "ohrev_min": round(ohrev_min, 1),
            "max_min": _safe_float(settings.get("cerpadlo_max_min", 45.0), 45.0),
            "delta_t": round(delta_t, 1),
            "updated_at": int(time.time()),
        }
        client.publish("fve/spotrebice/cerpadlo/set", json.dumps(payload), retain=True)

    def _tick_cerpadlo(self, client, settings, snapshot, now):
        # Logika čerpadla:
        #  - akumuluje dobu, kdy KOTEL TOPÍ (heating1_state_actual == 1)
        #  - čerpadlo ZAPNE až po kumulativním ohřevu max_min minut
        #  - čerpadlo VYPNE, když ΔT (vstup-výstup) klesne pod vypni_deltaT
        #    (teplo je rozvedeno) → reset kumulativního ohřevu
        #  - o půlnoci se kumulativní ohřev resetuje
        vypni_deltaT = _safe_float(settings.get("cerpadlo_vypni_deltaT", 10.0), 10.0)
        max_min = _safe_float(settings.get("cerpadlo_max_min", 45.0), 45.0)
        min_beh_min = _safe_float(settings.get("cerpadlo_min_beh_min", 60.0), 60.0)
        off_persist_min = _safe_float(settings.get("cerpadlo_off_persist_min", 2.0), 2.0)

        esp_online = bool(snapshot.get("podlahovka2200_online", False))
        t_vstup = _safe_float(snapshot.get("podlahovka2200_teplota_vstup"), 0.0)
        t_vystup = _safe_float(snapshot.get("podlahovka2200_teplota_vystup"), 0.0)
        teploty_valid = esp_online and t_vstup > 0.0 and t_vystup > 0.0
        delta_t = t_vstup - t_vystup
        kotel_topi = int(snapshot.get("heating1_state_actual", 0) or 0) == 1

        current = bool(self.device_states.get("cerpadlo", False))
        max_s = max_min * 60.0
        min_beh_s = min_beh_min * 60.0
        off_persist_s = off_persist_min * 60.0

        elapsed = now - self.cerpadlo_last_tick
        self.cerpadlo_last_tick = now

        # Reset kumulativního ohřevu o půlnoci
        today = time.strftime("%Y-%m-%d", time.localtime(now))
        if self.cerpadlo_last_day != today:
            self.cerpadlo_last_day = today
            self.cerpadlo_ohrev_accum = 0.0

        # Akumulace doby, kdy kotel topí
        if kotel_topi:
            self.cerpadlo_ohrev_accum += elapsed

        # Ruční override (z /cerpadlo/toggle)
        manual_until = _safe_float(snapshot.get("cerpadlo_manual_until"), 0.0)
        manual_state = bool(snapshot.get("cerpadlo_manual_state", False))
        manual_active = now < manual_until

        next_state = current
        if manual_active:
            next_state = manual_state
        elif current:
            # po zapnutí musí čerpadlo běžet aspoň min_beh_min, než se začne
            # kontrolovat ΔT (jinak by se hned po zapnutí vypnulo — malé ΔT)
            beh_s = now - self.cerpadlo_on_since if self.cerpadlo_on_since else 0.0
            # Vypnutí jen při platných datech a když ΔT drží pod mezí souvisle
            # off_persist_min — jinak jediný šumový vzorek (0/0) čerpadlo zbytečně
            # vypne a vynuluje kumulativní ohřev.
            low_delta = beh_s >= min_beh_s and teploty_valid and delta_t < vypni_deltaT
            if low_delta:
                if now - self.cerpadlo_low_delta_since >= off_persist_s:
                    next_state = False
                    self.cerpadlo_ohrev_accum = 0.0
            else:
                self.cerpadlo_low_delta_since = now
        else:
            if self.cerpadlo_ohrev_accum >= max_s:
                next_state = True

        current_data["cerpadlo_deltaT"] = round(delta_t, 1)
        current_data["cerpadlo_ohrev_min"] = round(self.cerpadlo_ohrev_accum / 60.0, 1)
        current_data["cerpadlo_kotel_topi"] = 1 if kotel_topi else 0
        current_data["cerpadlo_manual"] = 1 if manual_active else 0

        if next_state != current:
            self.device_states["cerpadlo"] = next_state
            self.last_change["cerpadlo"] = now
            self.cerpadlo_on_since = now if next_state else None
            self._publish_cerpadlo(client, next_state, settings, delta_t, self.cerpadlo_ohrev_accum / 60.0)
            return True
        return False

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

        # Ochrana vytěžování: když z měniče neteče žádný odběr (domácnost je
        # přepnutá na veřejnou síť), blokovat spínání spotřebičů, aby netopily
        # ze sítě. Odběr se bere z MQTT klíče output_active_power (W).
        ochrana_odberu = bool(settings.get("ochrana_odberu", True))
        odber_limit_w = _safe_float(settings.get("odber_limit_w", 10.0), 10.0)
        inverter_load_w = _safe_float(snapshot.get("output_active_power", 0.0), 0.0)
        odber_blok = ochrana_odberu and inverter_load_w < odber_limit_w

        with data_lock:
            for rule in DEVICE_RULES:
                # Virivka pravidla — jen dashboard, MQTT publish se dělá kombinovaně na konci
                if rule["name"] in ("virivka", "virivka2"):
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

                    if odber_blok:
                        next_state = False

                    self._set_dashboard_value(rule, next_state, settings)

                    if next_state != current_state:
                        self.device_states[rule["name"]] = next_state
                        self.last_change[rule["name"]] = now
                        changed = True
                    continue

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

                # Menic 2 je z ochrany odberu vyjmut — ovlada se rucne/prepojovanim.
                if odber_blok and rule["name"] != "menic2_rele":
                    next_state = False

                self._set_dashboard_value(rule, next_state, settings)

                if next_state == current_state:
                    if not self.initial_state_sent:
                        self._publish_state(client, rule, next_state, metric_name, source_value, settings)
                    continue

                self.device_states[rule["name"]] = next_state
                self.last_change[rule["name"]] = now
                self._publish_state(client, rule, next_state, metric_name, source_value, settings)
                changed = True

            # Virivka: publikovat obě relé v jedné zprávě
            self._publish_virivka_combined(client, settings, selected_metric_name, selected_metric_value)

            # Čerpadlo (eWeLink): logika podle ΔT kotle a kumulativního času
            if self._tick_cerpadlo(client, settings, snapshot, now):
                changed = True

            current_data["controller_source"] = selected_metric_name
            current_data["controller_value"] = selected_metric_value

        if changed or not self.initial_state_sent:
            self._publish_snapshot(client)
            self.initial_state_sent = True
