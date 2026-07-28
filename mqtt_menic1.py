#!/usr/bin/env python3
import serial
import time
import paho.mqtt.client as mqtt
import json
from datetime import datetime

# MQTT broker — ze secrets.py (neni v Gitu)
try:
    from secrets import MQTT_BROKER, MQTT_PORT
except ImportError:
    MQTT_BROKER = 'localhost'  # fallback: běží na stejném OPI
    MQTT_PORT = 1883

# Konfigurace
PORT = '/dev/ttyUSB0'
MQTT_TOPIC = 'menic/1/data'  # všechna data pošleme do jednoho topicu jako JSON

# Mapování hodnot pro PI30 (prvních 17)
NAZVY = [
    ("grid_voltage", "V"),          # 0
    ("grid_frequency", "Hz"),        # 1
    ("output_voltage", "V"),         # 2
    ("output_frequency", "Hz"),      # 3
    ("output_apparent_power", "VA"), # 4
    ("output_active_power", "W"),    # 5
    ("output_load_percent", "%"),    # 6
    ("bus_voltage", "V"),            # 7
    ("battery_voltage", "V"),        # 8
    ("battery_charging_current", "A"), # 9
    ("battery_capacity", "%"),       # 10
    ("temperature", "C"),             # 11
    ("pv_current", "A"),              # 12
    ("pv_voltage", "V"),              # 13
    ("battery_voltage_scc", "V"),     # 14
    ("battery_discharge_current", "A"), # 15
    ("device_status", ""),            # 16
]

# Filtr: omezí extrémní skoky na max ±20 % předchozí hodnoty
# Klíče, které se filtrují (ostatní procházejí beze změny)
FILTER_KEYS = [
    "grid_voltage", "grid_frequency",
    "output_voltage", "output_frequency",
    "output_apparent_power", "output_active_power",
    "bus_voltage", "battery_voltage",
    "battery_charging_current", "battery_discharge_current",
    "pv_current", "pv_voltage", "battery_voltage_scc",
    "pv_power", "output_load_percent",
]
_prev = {}  # předchozí hodnoty pro filtr

# Absolutní limity — cokoliv nad se zahodí (vrátí se předchozí hodnota)
MAX_LIMITS = {
    "grid_voltage": 300, "grid_frequency": 60,
    "output_voltage": 300, "output_frequency": 60,
    "output_apparent_power": 10000, "output_active_power": 10000,
    "bus_voltage": 500, "battery_voltage": 65,
    "battery_charging_current": 120, "battery_discharge_current": 120,
    "pv_current": 100, "pv_voltage": 500, "battery_voltage_scc": 65,
    "pv_power": 10000, "output_load_percent": 150,
}

# Přísnější omezení skoků pro napětí (max ±10 % místo ±20 %)
TIGHT_KEYS = {"grid_voltage", "output_voltage", "bus_voltage",
              "battery_voltage", "battery_voltage_scc", "pv_voltage"}

def filtruj(key, nova):
    """Absolutní limit + omezení skoků (10 % pro napětí, 20 % pro zbytek)."""
    if key not in _prev:
        _prev[key] = nova
        return nova

    # Absolutní nesmysl → vrať předchozí hodnotu
    limit = MAX_LIMITS.get(key)
    if limit is not None and abs(nova) > limit:
        return _prev[key]

    stare = _prev[key]
    if stare == 0:
        _prev[key] = nova
        return nova

    tight = key in TIGHT_KEYS
    pomer = nova / stare if stare != 0 else 1.0
    if tight:
        if pomer > 1.10:       nova = stare * 1.10
        elif pomer < 0.90:     nova = stare * 0.90
    else:
        if pomer > 2.0:        nova = stare * 1.2
        elif pomer < 0.5:      nova = stare * 0.8
    _prev[key] = nova
    return nova


def nacti_data(port):
    try:
        ser = serial.Serial(port, 2400, timeout=3)
        cmd = b'QPIGS\xb7\xa9\r'
        ser.write(cmd)
        response = ser.read_until(b'\r')
        ser.close()

        raw = response.decode('ascii', errors='ignore').strip()
        if raw.startswith('('):
            values = raw[1:].split(' ')
            return values
        else:
            print(f"Divná odpověď: {raw}")
            return None
    except Exception as e:
        print(f"Chyba čtení: {e}")
        return None

def main():
    # Připojení k MQTT brokeru
    client = mqtt.Client()
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print(f"Připojeno k MQTT brokeru {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        print(f"Chyba připojení k MQTT: {e}")
        return

    client.loop_start()
    print(f"Spouštím monitorování měniče/1 na {PORT}")

    while True:
        values = nacti_data(PORT)
        if values and len(values) >= 17:
            # Sestavíme dictionary s daty
            data = {}
            data['timestamp'] = datetime.now().isoformat()

            # Standardní hodnoty
            for i in range(17):
                nazev, jednotka = NAZVY[i]
                # Převod na číslo pokud možno
                try:
                    if '.' in values[i]:
                        data[nazev] = float(values[i])
                    else:
                        data[nazev] = int(values[i])
                except:
                    data[nazev] = values[i]

            # Specifické hodnoty
            if len(values) > 17:
                # Hodnota 19 je výkon panelů, ale občas obsahuje písmeno
                try:
                    val = values[19].strip()
                    while val and not val[-1].isdigit():
                        val = val[:-1]
                    if val:
                        data['pv_power'] = int(val)
                    else:
                        data['pv_power'] = 0
                except:
                    data['pv_power'] = 0
                # Ostatní pro úplnost
                data['specific_17'] = values[17]
                data['specific_18'] = values[18]
                # data['specific_20'] = values[20]

            # Aplikuj filtr na všechny relevantní klíče
            for key in FILTER_KEYS:
                if key in data and isinstance(data[key], (int, float)):
                    data[key] = filtruj(key, data[key])

            # Odeslání do MQTT
            try:
                payload = json.dumps(data)
                client.publish(MQTT_TOPIC, payload)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Odesláno: {data['output_active_power']}W, baterie: {data['battery_voltage']}V, PV: {data.get('pv_power', '?')}W")
            except Exception as e:
                print(f"Chyba MQTT: {e}")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Chyba čtení")

        time.sleep(5)  # čekej 5 sekund

if __name__ == "__main__":
    main()