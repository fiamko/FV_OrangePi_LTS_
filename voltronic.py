import serial
import time

class VoltronicInverter:
    def __init__(self, port, baudrate=2400, timeout=1):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout
        )

    def checksum(self, cmd):
        cs = 0
        for c in cmd:
            cs += ord(c)
        cs = cs & 0xFF
        return "{:02X}".format(cs)

    def send(self, cmd):
        full = cmd + self.checksum(cmd) + "\r"
        self.ser.write(full.encode("ascii"))
        time.sleep(0.2)
        return self.ser.read(128).decode(errors="ignore")

    def read_qpigs(self):
        resp = self.send("QPIGS")
        if "(" not in resp:
            return None

        try:
            data = resp.split("(")[1].split(")")[0].split(" ")
            return {
                "grid_voltage": float(data[0]),
                "grid_freq": float(data[1]),
                "ac_output_voltage": float(data[2]),
                "ac_output_freq": float(data[3]),
                "ac_output_va": float(data[4]),
                "ac_output_watt": float(data[5]),
                "load_percent": float(data[6]),
                "bus_voltage": float(data[7]),
                "battery_voltage": float(data[8]),
                "battery_charge_current": float(data[9]),
                "battery_capacity": float(data[10]),
                "pv_input_voltage": float(data[11]),
                "pv_input_current": float(data[12]),
                "pv_input_watt": float(data[13]),
            }
        except:
            return None
