import paho.mqtt.client as mqtt
import json
import time

try:
    import smbus2
except ImportError:
    smbus2 = None

I2C_BUS = 1
INA_ADDR = 0x40

REG_CONFIG   = 0x00
REG_BUS_V    = 0x02
REG_POWER    = 0x03
REG_CURRENT  = 0x04
REG_CALIB    = 0x05

CONFIG_64AVG = 0x4E7F

CURRENT_LSB = 200.0 / 32768.0
POWER_LSB = CURRENT_LSB * 25
BUS_LSB = 1.25 / 1000
CURRENT_CORR = 1.0

CALIBRATION = 2184     #2202   #1365

MQTT_TOPIC = "baterie/data"


class INA226:
    def __init__(self, mqtt_client=None):
        if smbus2 is None:
            raise RuntimeError("Python modul smbus2 neni dostupny")

        self.bus = smbus2.SMBus(I2C_BUS)
        self.addr = INA_ADDR
        self.initialized = False
        self.last_error = None

        self.mqtt = mqtt_client
        if self.mqtt is None:
            # MQTT broker — ze secrets.py (neni v Gitu)
            try:
                from secrets import MQTT_BROKER, MQTT_PORT
                broker = MQTT_BROKER
                port = MQTT_PORT
            except ImportError:
                broker = "localhost"
                port = 1883
            self.mqtt = mqtt.Client()
            self.mqtt.connect(broker, port, 60)

    def write_reg(self, reg, val):
        self.bus.write_i2c_block_data(self.addr, reg,
            [(val >> 8) & 0xFF, val & 0xFF])

    def read_reg(self, reg):
        try:
            d = self.bus.read_i2c_block_data(self.addr, reg, 2)
            self.last_error = None
            return (d[0] << 8) | d[1]
        except Exception as e:
            self.last_error = f"Chyba cteni registru {reg}: {e}"
            self.initialized = False
            return None

    def init(self):
        try:
            # 1. Reset čipu (bit 15 v Reg 00) - vrátí vše do výchozího stavu
            self.write_reg(REG_CONFIG, 0x8000)
            time.sleep(0.01) # Krátká pauza na reset

            # 2. Zápis kalibrace (Reg 05) - MUSÍ být před čtením proudu/výkonu
            self.write_reg(REG_CALIB, CALIBRATION)
            time.sleep(0.01)

            # 3. Zápis konfigurace (Reg 00)
            # Hodnota 27463 (0x6B47) = 512 vzorků, 2.116ms, kontinuálně
            self.write_reg(REG_CONFIG, 27463)
            time.sleep(0.01)

            self.initialized = True
            return True
        except Exception as e:
            self.last_error = f"Chyba inicializace INA226: {e}"
            self.initialized = False
            return False

    def read(self):
        try:
            raw = self.read_reg(REG_CURRENT)
            if raw is None:
                return {"inaB_V":"ERR","inaB_A":"ERR","inaB_W":"ERR"}, "ERR"
            if not self.initialized:
                if not self.init():
                    return {"inaB_V":"ERR","inaB_A":"ERR","inaB_W":"ERR"}, "ERR"

            raw_voltage = self.read_reg(REG_BUS_V)
            raw_current = self.read_reg(REG_CURRENT)
            raw_power = self.read_reg(REG_POWER)
            if raw_voltage is None or raw_current is None or raw_power is None:
                return {"inaB_V":"ERR","inaB_A":"ERR","inaB_W":"ERR"}, "ERR"

            v = raw_voltage * BUS_LSB
            if raw_current > 32767:
                raw_current -= 65536
            a = -raw_current * CURRENT_LSB * CURRENT_CORR
            w = raw_power * POWER_LSB

            data = {
                "inaB_V": round(v, 2),
                "inaB_A": round(a, 2),
                "inaB_W": round(w, 0)
            }

            self.publish(data)
            return data, None

        except Exception as error:
            self.last_error = f"Chyba cteni INA226: {error}"
            self.initialized = False
            return {"inaB_V":"ERR","inaB_A":"ERR","inaB_W":"ERR"}, "ERR"

    def publish(self, data):
        self.mqtt.publish(MQTT_TOPIC, json.dumps(data), retain=True)
