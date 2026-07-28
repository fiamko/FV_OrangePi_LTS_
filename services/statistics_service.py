import sqlite3
import time
from pathlib import Path

from services.history_service import DB_PATH


def _fetchone(cursor, query, params=()):
    row = cursor.execute(query, params).fetchone()
    return row if row else (0,) * 15


def _sum_hours(seconds_value):
    return round(float(seconds_value) / 3600.0, 2)


def _sum_kwh(wh_value):
    return round(float(wh_value) / 1000.0, 2)


def _load_range(cursor, table, time_column, ts_from):
    return _fetchone(
        cursor,
        f"""
        SELECT
            COALESCE(SUM(pv1_wh), 0),
            COALESCE(SUM(pv2_wh), 0),
            COALESCE(SUM(house_wh), 0),
            COALESCE(SUM(bojler_wh), 0),
            COALESCE(SUM(podlaha300_wh), 0),
            COALESCE(SUM(podlaha2000_wh), 0),
            COALESCE(SUM(podlaha2200_wh), 0),
            COALESCE(SUM(virivka_wh), 0),
            COALESCE(SUM(battery_cycles_eq), 0),
            COALESCE(SUM(bojler_seconds_on), 0),
            COALESCE(SUM(podlaha300_seconds_on), 0),
            COALESCE(SUM(podlaha2000_seconds_on), 0),
            COALESCE(SUM(podlaha2200_seconds_on), 0),
            COALESCE(SUM(virivka_seconds_on), 0),
            COALESCE(SUM(menic2_seconds_on), 0)
        FROM {table}
        WHERE {time_column} >= ?
        """,
        (ts_from,),
    )


def _pack_period(row):
    (
        pv1_wh,
        pv2_wh,
        house_wh,
        bojler_wh,
        podlaha300_wh,
        podlaha2000_wh,
        podlaha2200_wh,
        virivka_wh,
        battery_cycles_eq,
        bojler_seconds_on,
        podlaha300_seconds_on,
        podlaha2000_seconds_on,
        podlaha2200_seconds_on,
        virivka_seconds_on,
        menic2_seconds_on,
    ) = row

    return {
        "pv1_kwh": _sum_kwh(pv1_wh),
        "pv2_kwh": _sum_kwh(pv2_wh),
        "pv_total_kwh": _sum_kwh(pv1_wh + pv2_wh),
        "house_kwh": _sum_kwh(house_wh),
        "bojler_kwh": _sum_kwh(bojler_wh),
        "podlaha300_kwh": _sum_kwh(podlaha300_wh),
        "podlaha2000_kwh": _sum_kwh(podlaha2000_wh),
        "podlaha2200_kwh": _sum_kwh(podlaha2200_wh),
        "virivka_kwh": _sum_kwh(virivka_wh),
        "battery_cycles": round(float(battery_cycles_eq), 3),
        "bojler_h": _sum_hours(bojler_seconds_on),
        "podlaha300_h": _sum_hours(podlaha300_seconds_on),
        "podlaha2000_h": _sum_hours(podlaha2000_seconds_on),
        "podlaha2200_h": _sum_hours(podlaha2200_seconds_on),
        "virivka_h": _sum_hours(virivka_seconds_on),
        "menic2_h": _sum_hours(menic2_seconds_on),
    }


def get_statistics_overview():
    """Vraci zakladni statisticky prehled pro sablonu."""
    if not Path(DB_PATH).exists():
        empty = _pack_period((0,) * 15)
        return {"today": empty, "last_24h": empty, "last_30d": empty}

    now = int(time.time())
    parts = time.localtime(now)
    start_today = int(time.mktime((parts.tm_year, parts.tm_mon, parts.tm_mday, 0, 0, 0, 0, 0, -1)))
    last_24h = now - 86400
    last_30d = now - (30 * 86400)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    today = _pack_period(_load_range(cur, "telemetry_hourly", "hour_ts", start_today))
    recent = _pack_period(_load_range(cur, "telemetry_hourly", "hour_ts", last_24h))
    monthly = _pack_period(_load_range(cur, "telemetry_daily", "day_ts", last_30d))

    conn.close()

    return {
        "today": today,
        "last_24h": recent,
        "last_30d": monthly,
    }


def get_hourly_details(limit=24):
    """Vraci hodinove agregace za poslednich 24 hodin."""
    if not Path(DB_PATH).exists():
        return []

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT
            hour_ts,
            pv1_wh, pv2_wh, house_wh, battery_cycles_eq,
            bojler_seconds_on, virivka_seconds_on
        FROM telemetry_hourly
        ORDER BY hour_ts DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()

    output = []
    for hour_ts, pv1_wh, pv2_wh, house_wh, battery_cycles_eq, bojler_seconds_on, virivka_seconds_on in rows:
        output.append(
            {
                "label": time.strftime("%d.%m %H:00", time.localtime(hour_ts)),
                "pv1_kwh": _sum_kwh(pv1_wh),
                "pv2_kwh": _sum_kwh(pv2_wh),
                "house_kwh": _sum_kwh(house_wh),
                "battery_cycles": round(float(battery_cycles_eq), 3),
                "bojler_h": _sum_hours(bojler_seconds_on),
                "virivka_h": _sum_hours(virivka_seconds_on),
            }
        )

    return output
