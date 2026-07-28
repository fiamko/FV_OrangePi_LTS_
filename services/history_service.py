import sqlite3
import time
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "fve_history.db"

LOAD_BIT_MAP = {
    "bojler_state": 0,
    "heating3_state": 1,
    "heating2_state": 2,
    "heating1_state": 3,
    "virivka_state": 4,
    "menic2_rele_state": 5,
}

def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


class HistoryRecorder:
    def __init__(self):
        self.db_path = DB_PATH
        self.connection = sqlite3.connect(self.db_path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self._ensure_schema()

    def _ensure_schema(self):
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS telemetry_raw (
                ts INTEGER PRIMARY KEY,
                pv1_w INTEGER NOT NULL,
                pv2_w INTEGER NOT NULL,
                inv1_w INTEGER NOT NULL,
                inv2_w INTEGER NOT NULL,
                bat_v REAL NOT NULL,
                bat_a REAL NOT NULL,
                house_w INTEGER NOT NULL,
                loads_mask INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS telemetry_hourly (
                hour_ts INTEGER PRIMARY KEY,
                pv1_wh REAL NOT NULL,
                pv2_wh REAL NOT NULL,
                inv1_wh REAL NOT NULL,
                inv2_wh REAL NOT NULL,
                house_wh REAL NOT NULL,
                bojler_seconds_on INTEGER NOT NULL,
                podlaha300_seconds_on INTEGER NOT NULL,
                podlaha2000_seconds_on INTEGER NOT NULL,
                podlaha2200_seconds_on INTEGER NOT NULL,
                virivka_seconds_on INTEGER NOT NULL,
                menic2_seconds_on INTEGER NOT NULL,
                bojler_wh REAL NOT NULL,
                podlaha300_wh REAL NOT NULL,
                podlaha2000_wh REAL NOT NULL,
                podlaha2200_wh REAL NOT NULL,
                virivka_wh REAL NOT NULL,
                bat_charge_ah REAL NOT NULL,
                bat_discharge_ah REAL NOT NULL,
                battery_cycles_eq REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS telemetry_daily (
                day_ts INTEGER PRIMARY KEY,
                pv1_wh REAL NOT NULL,
                pv2_wh REAL NOT NULL,
                inv1_wh REAL NOT NULL,
                inv2_wh REAL NOT NULL,
                house_wh REAL NOT NULL,
                bojler_seconds_on INTEGER NOT NULL,
                podlaha300_seconds_on INTEGER NOT NULL,
                podlaha2000_seconds_on INTEGER NOT NULL,
                podlaha2200_seconds_on INTEGER NOT NULL,
                virivka_seconds_on INTEGER NOT NULL,
                menic2_seconds_on INTEGER NOT NULL,
                bojler_wh REAL NOT NULL,
                podlaha300_wh REAL NOT NULL,
                podlaha2000_wh REAL NOT NULL,
                podlaha2200_wh REAL NOT NULL,
                virivka_wh REAL NOT NULL,
                bat_charge_ah REAL NOT NULL,
                bat_discharge_ah REAL NOT NULL,
                battery_cycles_eq REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS telemetry_yearly (
                year_ts INTEGER PRIMARY KEY,
                pv1_wh REAL NOT NULL,
                pv2_wh REAL NOT NULL,
                inv1_wh REAL NOT NULL,
                inv2_wh REAL NOT NULL,
                house_wh REAL NOT NULL,
                bojler_seconds_on INTEGER NOT NULL,
                podlaha300_seconds_on INTEGER NOT NULL,
                podlaha2000_seconds_on INTEGER NOT NULL,
                podlaha2200_seconds_on INTEGER NOT NULL,
                virivka_seconds_on INTEGER NOT NULL,
                menic2_seconds_on INTEGER NOT NULL,
                bojler_wh REAL NOT NULL,
                podlaha300_wh REAL NOT NULL,
                podlaha2000_wh REAL NOT NULL,
                podlaha2200_wh REAL NOT NULL,
                virivka_wh REAL NOT NULL,
                bat_charge_ah REAL NOT NULL,
                bat_discharge_ah REAL NOT NULL,
                battery_cycles_eq REAL NOT NULL
            );
            """
        )
        self.connection.commit()

    def _build_loads_mask(self, snapshot):
        mask = 0

        for key, bit in LOAD_BIT_MAP.items():
            if _safe_int(snapshot.get(key), 0) > 0:
                mask |= 1 << bit

        return mask

    def _extract_house_w(self, snapshot):
        # Aktivni vykon (W) ma prednost pred zdanlivym (VA).
        # Ochrana: max 20 kW (nesmyslne hodnoty = sum ze seriove linky).
        for key in ("output_active_power", "output_apparent_power", "house_w", "load_power"):
            val = snapshot.get(key)
            if val is not None and val != 0:
                w = _safe_int(val, 0)
                if 0 < w <= 20000:
                    return w
        return 0

    def _extract_battery_current(self, snapshot):
        charging = _safe_float(snapshot.get("battery_charging_current"), 0.0)
        discharging = _safe_float(snapshot.get("battery_discharge_current"), 0.0)

        # Ochrana proti nesmyslnym hodnotam (max ±100 A pro 3kW menic).
        if 0 < charging <= 100.0:
            return charging
        if 0 < discharging <= 100.0:
            return -discharging

        fallback = _safe_float(snapshot.get("inaB_A", snapshot.get("battery_current", 0.0)), 0.0)
        if -100.0 <= fallback <= 100.0:
            return fallback
        return 0.0

    def _aggregate_row(self, snapshot, settings):
        interval_s = max(_safe_float(settings.get("sample_interval_s"), 10.0), 1.0)
        interval_h = interval_s / 3600.0
        battery_capacity_ah = max(_safe_float(settings.get("battery_capacity_ah"), 300.0), 1.0)
        bat_a = self._extract_battery_current(snapshot)

        charge_ah = bat_a * interval_h if bat_a > 0 else 0.0
        discharge_ah = abs(bat_a) * interval_h if bat_a < 0 else 0.0

        row = {
            "pv1_wh": _safe_int(snapshot.get("pv_power"), 0) * interval_h,
            "pv2_wh": _safe_int(snapshot.get("pv_power2"), 0) * interval_h,
            "inv1_wh": _safe_int(snapshot.get("output_apparent_power"), 0) * interval_h,
            "inv2_wh": _safe_int(snapshot.get("output_active_power2"), 0) * interval_h,
            "house_wh": self._extract_house_w(snapshot) * interval_h,
            "bojler_seconds_on": interval_s if _safe_int(snapshot.get("boiler_state"), 0) else 0,
            "podlaha300_seconds_on": interval_s if _safe_int(snapshot.get("heating3_state"), 0) else 0,
            "podlaha2000_seconds_on": interval_s if _safe_int(snapshot.get("heating2_state"), 0) else 0,
            "podlaha2200_seconds_on": interval_s if _safe_int(snapshot.get("heating1_state"), 0) else 0,
            "virivka_seconds_on": interval_s if _safe_int(snapshot.get("virivka_state"), 0) else 0,
            "menic2_seconds_on": interval_s if _safe_int(snapshot.get("menic2_rele_state"), 0) else 0,
            "bojler_wh": _safe_float(settings.get("power_bojler"), 2000.0) * interval_h if _safe_int(snapshot.get("boiler_state"), 0) else 0.0,
            "podlaha300_wh": _safe_float(settings.get("power_podlaha300"), 300.0) * interval_h if _safe_int(snapshot.get("heating3_state"), 0) else 0.0,
            "podlaha2000_wh": _safe_float(settings.get("power_podlaha2000"), 2000.0) * interval_h if _safe_int(snapshot.get("heating2_state"), 0) else 0.0,
            "podlaha2200_wh": _safe_float(settings.get("power_podlaha2200"), 2200.0) * interval_h if _safe_int(snapshot.get("heating1_state"), 0) else 0.0,
            "virivka_wh": _safe_float(settings.get("power_virivka"), 2300.0) * interval_h if _safe_int(snapshot.get("virivka_state"), 0) else 0.0,
            "bat_charge_ah": charge_ah,
            "bat_discharge_ah": discharge_ah,
            "battery_cycles_eq": discharge_ah / battery_capacity_ah,
        }

        return row

    def _start_of_hour(self, ts):
        parts = time.localtime(ts)
        return int(time.mktime((parts.tm_year, parts.tm_mon, parts.tm_mday, parts.tm_hour, 0, 0, 0, 0, -1)))

    def _start_of_day(self, ts):
        parts = time.localtime(ts)
        return int(time.mktime((parts.tm_year, parts.tm_mon, parts.tm_mday, 0, 0, 0, 0, 0, -1)))

    def _start_of_year(self, ts):
        parts = time.localtime(ts)
        return int(time.mktime((parts.tm_year, 1, 1, 0, 0, 0, 0, 0, -1)))

    def _upsert_aggregate(self, table, time_column, bucket_ts, row):
        sql = f"""
            INSERT INTO {table} (
                {time_column},
                pv1_wh, pv2_wh, inv1_wh, inv2_wh, house_wh,
                bojler_seconds_on, podlaha300_seconds_on, podlaha2000_seconds_on,
                podlaha2200_seconds_on, virivka_seconds_on, menic2_seconds_on,
                bojler_wh, podlaha300_wh, podlaha2000_wh, podlaha2200_wh,
                virivka_wh, bat_charge_ah, bat_discharge_ah, battery_cycles_eq
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT({time_column}) DO UPDATE SET
                pv1_wh = pv1_wh + excluded.pv1_wh,
                pv2_wh = pv2_wh + excluded.pv2_wh,
                inv1_wh = inv1_wh + excluded.inv1_wh,
                inv2_wh = inv2_wh + excluded.inv2_wh,
                house_wh = house_wh + excluded.house_wh,
                bojler_seconds_on = bojler_seconds_on + excluded.bojler_seconds_on,
                podlaha300_seconds_on = podlaha300_seconds_on + excluded.podlaha300_seconds_on,
                podlaha2000_seconds_on = podlaha2000_seconds_on + excluded.podlaha2000_seconds_on,
                podlaha2200_seconds_on = podlaha2200_seconds_on + excluded.podlaha2200_seconds_on,
                virivka_seconds_on = virivka_seconds_on + excluded.virivka_seconds_on,
                menic2_seconds_on = menic2_seconds_on + excluded.menic2_seconds_on,
                bojler_wh = bojler_wh + excluded.bojler_wh,
                podlaha300_wh = podlaha300_wh + excluded.podlaha300_wh,
                podlaha2000_wh = podlaha2000_wh + excluded.podlaha2000_wh,
                podlaha2200_wh = podlaha2200_wh + excluded.podlaha2200_wh,
                virivka_wh = virivka_wh + excluded.virivka_wh,
                bat_charge_ah = bat_charge_ah + excluded.bat_charge_ah,
                bat_discharge_ah = bat_discharge_ah + excluded.bat_discharge_ah,
                battery_cycles_eq = battery_cycles_eq + excluded.battery_cycles_eq
        """

        self.connection.execute(
            sql,
            (
                bucket_ts,
                row["pv1_wh"],
                row["pv2_wh"],
                row["inv1_wh"],
                row["inv2_wh"],
                row["house_wh"],
                int(row["bojler_seconds_on"]),
                int(row["podlaha300_seconds_on"]),
                int(row["podlaha2000_seconds_on"]),
                int(row["podlaha2200_seconds_on"]),
                int(row["virivka_seconds_on"]),
                int(row["menic2_seconds_on"]),
                row["bojler_wh"],
                row["podlaha300_wh"],
                row["podlaha2000_wh"],
                row["podlaha2200_wh"],
                row["virivka_wh"],
                row["bat_charge_ah"],
                row["bat_discharge_ah"],
                row["battery_cycles_eq"],
            ),
        )

    def record_snapshot(self, snapshot, settings):
        now_ts = int(time.time())
        row = self._aggregate_row(snapshot, settings)

        self.connection.execute(
            """
            INSERT OR REPLACE INTO telemetry_raw (
                ts, pv1_w, pv2_w, inv1_w, inv2_w, bat_v, bat_a, house_w, loads_mask
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_ts,
                _safe_int(snapshot.get("pv_power"), 0),
                _safe_int(snapshot.get("pv_power2"), 0),
                _safe_int(snapshot.get("output_apparent_power"), 0),
                _safe_int(snapshot.get("output_active_power2"), 0),
                _safe_float(snapshot.get("battery_voltage"), 0.0),
                self._extract_battery_current(snapshot),
                self._extract_house_w(snapshot),
                self._build_loads_mask(snapshot),
            ),
        )

        self._upsert_aggregate("telemetry_hourly", "hour_ts", self._start_of_hour(now_ts), row)
        self._upsert_aggregate("telemetry_daily", "day_ts", self._start_of_day(now_ts), row)
        self._upsert_aggregate("telemetry_yearly", "year_ts", self._start_of_year(now_ts), row)
        self.connection.commit()
