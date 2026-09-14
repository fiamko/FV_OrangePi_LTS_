#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eWeLink LAN bridge pro Sonoff oběhové čerpadlo (FVE systém FIAM).

Ovládá Sonoff (eWeLink firmware) přes LAN mód — HTTP POST na /zeroconf/<command>.
Data jsou šifrována AES-128-CBC (klíč = MD5(devicekey), náhodné IV, PKCS7 padding).
Stejný kód funguje i v DIY módu (bez devicekey = nešifrovaně).

Protokol podle referenční implementace AlexxIT/SonoffLAN:
  custom_components/sonoff/core/ewelink/local.py

MQTT:
  subscribe  fve/spotrebice/cerpadlo/set     (příkaz z OPI ControllerEngine; čte "enabled")
  publish    fve/spotrebice/cerpadlo/stav    {"status":"ZAP"/"OFF","vystup":0/1,"duvod":"..."}
  publish    fve/spotrebice/cerpadlo/status  {"status":"online"/"offline"}  (Last Will, retained)

Konfigurace: ewelink_config.json ve stejném adresáři (deviceid, devicekey, host, ...).
Test bez MQTT:  python3 ewelink_mqtt.py --test on|off|state
"""

import base64
import hashlib
import json
import os
import sys
import time
from http.client import HTTPConnection

import paho.mqtt.client as mqtt
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ewelink_config.json")

DEFAULTS = {
    "deviceid": "",
    "devicekey": "",
    "host": "192.168.0.132",
    "port": 8081,
    "mqtt_broker": "localhost",
    "mqtt_port": 1883,
    "cmd_topic": "fve/spotrebice/cerpadlo/set",
    "state_topic": "fve/spotrebice/cerpadlo/stav",
    "status_topic": "fve/spotrebice/cerpadlo/status",
    "poll_interval_s": 10,
}


def load_config():
    cfg = DEFAULTS.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8-sig") as fh:
                cfg.update(json.load(fh))
        except Exception as exc:
            print(f"[ewelink] chyba cteni {CONFIG_PATH}: {exc}")
    return cfg


def encrypt_payload(payload, devicekey):
    """Zašifruje payload["data"] pro eWeLink LAN mód (AES-128-CBC)."""
    plaintext = json.dumps(payload["data"]).encode("utf-8")
    key = hashlib.md5(devicekey.encode("utf-8")).digest()
    iv = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))
    payload["encrypt"] = True
    payload["iv"] = base64.b64encode(iv).decode("utf-8")
    payload["data"] = base64.b64encode(ciphertext).decode("utf-8")
    return payload


def decrypt_data(payload, devicekey):
    """Dešifruje odpověď zařízení a vrátí dict parametrů."""
    key = hashlib.md5(devicekey.encode("utf-8")).digest()
    iv = base64.b64decode(payload["iv"])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = base64.b64decode(payload["data"])
    plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
    return json.loads(plaintext.decode("utf-8"))


class EwelinkDevice:
    def __init__(self, cfg):
        self.deviceid = cfg["deviceid"]
        self.devicekey = cfg.get("devicekey", "")
        self.host = cfg["host"]
        self.port = int(cfg["port"])
        self._seq = int(time.time() * 1000) & 0x7FFFFFFF

    def _seq_next(self):
        self._seq = (self._seq + 1) & 0x7FFFFFFF
        return str(self._seq)

    def _post(self, command, params):
        payload = {
            "sequence": self._seq_next(),
            "deviceid": self.deviceid,
            "selfApikey": "123",
            "data": params,
        }
        if self.devicekey:
            payload = encrypt_payload(payload, self.devicekey)

        body = json.dumps(payload)
        for attempt in (1, 2):
            conn = HTTPConnection(self.host, self.port, timeout=6)
            try:
                conn.request(
                    "POST",
                    f"/zeroconf/{command}",
                    body=body,
                    headers={
                        "Content-Type": "application/json",
                        "Connection": "close",
                    },
                )
                resp = conn.getresponse()
                raw = resp.read()
                if not raw:
                    return None, f"HTTP {resp.status} prazdna odpoved"
                data = json.loads(raw.decode("utf-8"))
                if data.get("error") != 0:
                    return None, f"error={data.get('error')} {data.get('msg', '')}"
                if self.devicekey and data.get("iv"):
                    data["data"] = decrypt_data(data, self.devicekey)
                return data, None
            except (ConnectionResetError, BrokenPipeError, OSError) as exc:
                # zařízení má jedno-vláknový web server, občas resetuje spojení
                if attempt == 1:
                    time.sleep(0.15)
                    continue
                return None, f"spojeni: {exc}"
            except Exception as exc:
                return None, f"chyba: {exc}"
            finally:
                conn.close()
        return None, "spojeni selhalo"

    def set_switch(self, on):
        return self._post("switch", {"switch": "on" if on else "off"})

    def get_state(self):
        return self._post("getState", {})

    @staticmethod
    def parse_switch_state(resp):
        """Z odpovědi vyčte True (on) / False (off) / None (neznámý)."""
        try:
            data = resp.get("data", {})
            if isinstance(data, str):
                data = json.loads(data)
            sw = data.get("switch")
            if sw is None:
                return None
            return sw in ("on", "1", 1, True)
        except Exception:
            return None


class MdnsStateListener(ServiceListener):
    """Naslouchá mDNS broadcastu zařízení a dešifruje aktuální stav relé."""

    def __init__(self, deviceid, devicekey, on_state):
        self.deviceid = deviceid
        self.devicekey = devicekey
        self.on_state = on_state

    def _handle(self, zc, type_, name):
        if self.deviceid not in name:
            return
        info = zc.get_service_info(type_, name)
        if not info:
            return
        props = {}
        for k, v in info.properties.items():
            kk = k.decode() if isinstance(k, bytes) else k
            vv = v.decode() if isinstance(v, bytes) else v
            props[kk] = vv
        raw = "".join(props.get("data%d" % i, "") for i in range(1, 5))
        if not raw or not props.get("encrypt"):
            return
        try:
            data = decrypt_data({"data": raw, "iv": props.get("iv", "")}, self.devicekey)
        except Exception:
            return
        sw = data.get("switch")
        if sw is not None:
            self.on_state(sw in ("on", "1", 1, True))

    def add_service(self, zc, type_, name):
        self._handle(zc, type_, name)

    def update_service(self, zc, type_, name):
        self._handle(zc, type_, name)


def _cli():
    cfg = load_config()
    dev = EwelinkDevice(cfg)
    if len(sys.argv) >= 3 and sys.argv[1] == "--test":
        action = sys.argv[2]
        if action in ("on", "off"):
            resp, err = dev.set_switch(action == "on")
            print(f"set {action} -> err={err!r}")
            if err is None:
                print("switch =", dev.parse_switch_state(resp))
            return 0 if err is None else 1
        if action == "state":
            resp, err = dev.get_state()
            print(f"getState -> err={err!r}")
            if err is None:
                print("switch =", dev.parse_switch_state(resp))
            return 0 if err is None else 1
    print("Pouziti: python3 ewelink_mqtt.py [--test on|off|state]")
    print("Bez argumentu bezi jako MQTT bridge.")
    return 0


def main():
    cfg = load_config()
    if not cfg.get("deviceid"):
        print("[ewelink] CHYBA: deviceid neni nastaven v ewelink_config.json")
        return 1
    if not cfg.get("devicekey"):
        print("[ewelink] VAROVANI: devicekey neni nastaven — LAN mód vyžaduje device key.")
        print("[ewelink]          (DIY mód bez klíče funguje, LAN mód bez klíče ne.)")

    device = EwelinkDevice(cfg)
    state = {"last": None}  # poslední známý stav relé (True/False/None)

    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqttc.will_set(cfg["status_topic"], json.dumps({"status": "offline"}), retain=True)

    def publish_state(on, reason):
        payload = {
            "status": "ZAP" if on else "OFF",
            "vystup": 1 if on else 0,
            "duvod": reason,
        }
        mqttc.publish(cfg["state_topic"], json.dumps(payload), retain=True)

    def publish_online():
        mqttc.publish(cfg["status_topic"], json.dumps({"status": "online"}), retain=True)

    def apply_switch(on, reason):
        resp, err = device.set_switch(on)
        if err:
            print(f"[ewelink] set_switch({on}) chyba: {err}")
            return False
        # Zařízení nevrací stav v odpovědi (jen {"error":0}) → sledujeme zadaný stav.
        state["last"] = on
        publish_state(on, reason)
        print(f"[ewelink] rele -> {'ON' if on else 'OFF'} ({reason})")
        return True

    def on_mdns_state(on):
        # skutečný stav ze zařízení (mDNS broadcast) — detekuje i ruční změny
        if state["last"] != on:
            state["last"] = on
            publish_state(on, "Stav ze zarizeni")
            print(f"[ewelink] stav ze zarizeni (mDNS): {'ON' if on else 'OFF'}")

    def on_connect(client, userdata, flags, rc, properties=None):
        if rc != 0:
            print(f"[ewelink] MQTT connect fail rc={rc}")
            return
        client.subscribe(cfg["cmd_topic"])
        publish_online()
        print(f"[ewelink] MQTT pripojeno, subscribe {cfg['cmd_topic']}")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except Exception as exc:
            print(f"[ewelink] spatny JSON v {msg.topic}: {exc}")
            return
        enabled = payload.get("enabled")
        if enabled is None:
            enabled = payload.get("state") == "ON" or payload.get("switch") == "on"
        apply_switch(bool(enabled), "Rizeno OPI")

    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    mqttc.connect(cfg["mqtt_broker"], int(cfg["mqtt_port"]), 60)
    mqttc.loop_start()

    # mDNS: čtení skutečného stavu relé ze zařízení
    zc = Zeroconf()
    browser = ServiceBrowser(
        zc, "_ewelink._tcp.local.",
        MdnsStateListener(device.deviceid, device.devicekey, on_mdns_state),
    )

    poll_interval = max(float(cfg["poll_interval_s"]), 5)
    last_poll = 0.0
    device_online = False
    try:
        while True:
            time.sleep(1)
            now = time.time()
            if now - last_poll >= poll_interval:
                last_poll = now
                # Health check: getState vrati {"error":0}, kdyz je zarizeni dosazitelne.
                # (stav rele se z mDNS na OPI necte — multicast neprochazi)
                _, err = device.get_state()
                online = err is None
                if online != device_online:
                    device_online = online
                    mqttc.publish(cfg["status_topic"], json.dumps({"status": "online" if online else "offline"}), retain=True)
                    print(f"[ewelink] zarizeni {'online' if online else 'offline'}")
    except KeyboardInterrupt:
        pass
    finally:
        mqttc.loop_stop()
        mqttc.publish(cfg["status_topic"], json.dumps({"status": "offline"}), retain=True)
        zc.close()


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--test":
        sys.exit(_cli())
    sys.exit(main())
