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


# ============================================================================
# API pro grafy
# ============================================================================

def _vytizeni_wh(row):
    """Soucet vsech vytizovacich spotrebicu [Wh]."""
    return (float(row[7] or 0) + float(row[8] or 0) + float(row[9] or 0) +
            float(row[10] or 0) + float(row[11] or 0))


def get_graph_data(period):
    """Vrati JSON-ready data pro Chart.js grafy."""
    if not Path(DB_PATH).exists():
        return _empty_graph()

    now = int(time.time())
    conn = sqlite3.connect(DB_PATH)

    try:
        cur = conn.cursor()

        if period == "today":
            parts = time.localtime(now)
            start = int(time.mktime((parts.tm_year, parts.tm_mon, parts.tm_mday, 0, 0, 0, 0, 0, -1)))
            rows = cur.execute(
                "SELECT ts, pv1_w, pv2_w, house_w FROM telemetry_raw WHERE ts >= ? ORDER BY ts",
                (start,)
            ).fetchall()
            return _bucket_raw(rows, 300)

        elif period == "24h":
            start = now - 86400
            rows = cur.execute(
                """SELECT hour_ts, pv1_wh, pv2_wh, house_wh, 0,0,0,
                          bojler_wh, podlaha300_wh, podlaha2000_wh, podlaha2200_wh, virivka_wh,
                          battery_cycles_eq
                   FROM telemetry_hourly WHERE hour_ts >= ? ORDER BY hour_ts""",
                (start,)
            ).fetchall()
            return _pack_graph_rows(rows, "hour")

        elif period in ("30d", "1y"):
            days = 365 if period == "1y" else 30
            start = now - (days * 86400)
            rows = cur.execute(
                """SELECT day_ts, pv1_wh, pv2_wh, house_wh, 0,0,0,
                          bojler_wh, podlaha300_wh, podlaha2000_wh, podlaha2200_wh, virivka_wh,
                          battery_cycles_eq
                   FROM telemetry_daily WHERE day_ts >= ? ORDER BY day_ts""",
                (start,)
            ).fetchall()
            return _pack_graph_rows(rows, "day")

        else:  # all
            rows = cur.execute(
                """SELECT day_ts, pv1_wh, pv2_wh, house_wh, 0,0,0,
                          bojler_wh, podlaha300_wh, podlaha2000_wh, podlaha2200_wh, virivka_wh,
                          battery_cycles_eq
                   FROM telemetry_daily ORDER BY day_ts"""
            ).fetchall()
            return _pack_graph_rows(rows, "day")
    finally:
        conn.close()


def _empty_graph():
    return {"labels": [], "pv1": [], "pv2": [], "house": [], "vytizeni": [], "bat_cycles": []}


def _bucket_raw(rows, bucket_s):
    """Agregace raw dat do bucketu (pro dnesni graf)."""
    if not rows:
        return _empty_graph()

    labels, pv1, pv2, house, vytizeni, bat = [], [], [], [], [], []
    bucket_start = None
    sum_pv1 = sum_pv2 = sum_house = 0
    count = 0

    for ts, pv1w, pv2w, house_w in rows:
        b = (ts // bucket_s) * bucket_s
        if bucket_start is None:
            bucket_start = b
        if b != bucket_start:
            n = max(count, 1)
            labels.append(time.strftime("%H:%M", time.localtime(bucket_start)))
            pv1.append(round(sum_pv1 / n))
            pv2.append(round(sum_pv2 / n))
            house.append(round(sum_house / n))
            vytizeni.append(0)  # estimated from hourly later
            bat.append(0)
            bucket_start = b
            sum_pv1 = sum_pv2 = sum_house = 0
            count = 0
        sum_pv1 += (pv1w or 0)
        sum_pv2 += (pv2w or 0)
        sum_house += (house_w or 0)
        count += 1

    if count > 0:
        labels.append(time.strftime("%H:%M", time.localtime(bucket_start)))
        pv1.append(round(sum_pv1 / count))
        pv2.append(round(sum_pv2 / count))
        house.append(round(sum_house / count))
        vytizeni.append(0)
        bat.append(0)

    return {"labels": labels, "pv1": pv1, "pv2": pv2, "house": house,
            "vytizeni": vytizeni, "bat_cycles": bat}


def _pack_graph_rows(rows, period):
    """Prevod agregovanych radku na grafy."""
    labels, pv1, pv2, house, vytizeni, bat = [], [], [], [], [], []
    fmt = {"hour": "%H:00", "day": "%d.%m.", "year": "%Y"}.get(period, "%d.%m.")

    for r in rows:
        ts = r[0]
        labels.append(time.strftime(fmt, time.localtime(ts)))
        pv1.append(round(float(r[1] or 0)))
        pv2.append(round(float(r[2] or 0)))
        house.append(round(float(r[3] or 0)))
        vytizeni.append(round(_vytizeni_wh(r)))
        bat.append(round(float(r[12] or 0), 3))

    return {"labels": labels, "pv1": pv1, "pv2": pv2, "house": house,
            "vytizeni": vytizeni, "bat_cycles": bat}


def export_csv(period):
    """Export dat jako CSV string."""
    if not Path(DB_PATH).exists():
        return "timestamp,pv1_w,pv2_w,house_w\n"

    now = int(time.time())
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    periods_sql = {
        "today": ("telemetry_raw", "ts", now - 86400),
        "24h": ("telemetry_hourly", "hour_ts", now - 86400),
        "30d": ("telemetry_daily", "day_ts", now - (30 * 86400)),
        "1y": ("telemetry_daily", "day_ts", now - (365 * 86400)),
        "all": ("telemetry_daily", "day_ts", 0),
    }

    table, col, start = periods_sql.get(period, ("telemetry_daily", "day_ts", 0))

    rows = cur.execute(
        f"""SELECT {col}, pv1_wh, pv2_wh, house_wh,
                   bojler_wh, podlaha300_wh, podlaha2000_wh, podlaha2200_wh, virivka_wh,
                   battery_cycles_eq
            FROM {table} WHERE {col} >= ? ORDER BY {col}""",
        (start,)
    ).fetchall()
    conn.close()

    csv = "timestamp,pv1_wh,pv2_wh,house_wh,bojler_wh,podlaha300_wh,podlaha2000_wh,podlaha2200_wh,virivka_wh,vytizeni_wh,battery_cycles\n"
    for r in rows:
        vyt = (float(r[5] or 0) + float(r[6] or 0) + float(r[7] or 0) + float(r[8] or 0) + float(r[9] or 0))
        csv += f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]},{r[5]},{r[6]},{r[7]},{r[8]},{round(vyt)},{round(float(r[10] or 0), 3)}\n"

    return csv
