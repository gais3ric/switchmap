"""Жизненный цикл данных: свёртка истории, сроки хранения, ряды для графиков, резервные копии.

Сырые опросы (port_traffic, switch_health) хранятся N дней. Более старые сворачиваются
в почасовые агрегаты (среднее, взвешенное по длительности интервала, и пик) и удаляются.
"""
import math
import os
import re
import sqlite3
from datetime import datetime, timedelta

from i18n import N_, _

TS = "%Y-%m-%d %H:%M:%S"


# ─────────────────────────────────────────
# Схема
# ─────────────────────────────────────────

def ensure_tables(c):
    """Таблицы агрегатов. Вызывается из create_stats_tables (новая и старая база)."""
    c.execute("""
        CREATE TABLE IF NOT EXISTS port_traffic_hourly (
            switch_id INTEGER, ifindex TEXT, hour TEXT,
            in_avg REAL, out_avg REAL, in_max REAL, out_max REAL,
            errors INTEGER, weight REAL, samples INTEGER,
            PRIMARY KEY (switch_id, ifindex, hour)
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS switch_health_hourly (
            switch_id INTEGER, hour TEXT,
            cpu_avg REAL, cpu_max REAL, ram_avg REAL, ram_max REAL, temp_avg REAL, temp_max REAL,
            samples INTEGER,
            PRIMARY KEY (switch_id, hour)
        )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_port_traffic_ts ON port_traffic (timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_switch_health_ts ON switch_health (timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_port_events_time ON port_events (event_time)")


def _parse(ts):
    return datetime.strptime(ts, TS)


def _floor_hour(dt):
    return dt.replace(minute=0, second=0, microsecond=0)


# ─────────────────────────────────────────
# Скорость для старых записей (до того, как её стали сохранять при опросе)
# ─────────────────────────────────────────

def backfill_rates(conn, compute_traffic_rates):
    """Считает in/out Мбит/с для записей port_traffic без rate_done. Возвращает число записей."""
    pairs = conn.execute("SELECT DISTINCT switch_id, ifindex FROM port_traffic WHERE rate_done IS NULL").fetchall()
    done = 0
    for switch_id, ifindex in pairs:
        rows = conn.execute("""
            SELECT id, timestamp, bytes_in, bytes_out, errors_in, errors_out, counter_bits, rate_done
            FROM port_traffic WHERE switch_id=? AND ifindex=? ORDER BY id""", (switch_id, ifindex)).fetchall()
        prev = None
        updates = []
        for r in rows:
            rec = {"timestamp": r[1], "bytes_in": r[2], "bytes_out": r[3], "errors_in": r[4],
                   "errors_out": r[5], "counter_bits": r[6] or 32}
            if r[7] is None:
                if prev is None:
                    updates.append((None, None, None, None, r[0]))
                else:
                    rate = compute_traffic_rates([dict(rec), dict(prev)])[0]
                    err = None
                    if rate["errors_in_delta"] is not None and rate["errors_out_delta"] is not None:
                        err = rate["errors_in_delta"] + rate["errors_out_delta"]
                    updates.append((rate["in_mbps"], rate["out_mbps"], rate["interval_sec"], err, r[0]))
            prev = rec
        conn.executemany("""UPDATE port_traffic SET in_mbps=?, out_mbps=?, interval_sec=?, errors_delta=?, rate_done=1
                            WHERE id=?""", updates)
        done += len(updates)
    return done


# ─────────────────────────────────────────
# Свёртка и очистка
# ─────────────────────────────────────────

def rollup_and_prune(db, compute_traffic_rates, raw_days=7, hourly_days=365, events_days=90, now=None, vacuum=False):
    """Сворачивает сырые данные старше raw_days в почасовые, удаляет устаревшее.
    Граница выравнивается по началу часа: все записи одного часа сворачиваются вместе."""
    now = now or datetime.now()
    raw_cutoff = _floor_hour(now - timedelta(days=raw_days)).strftime(TS)
    hourly_cutoff = (now - timedelta(days=hourly_days)).strftime("%Y-%m-%d %H:00:00")
    events_cutoff = (now - timedelta(days=events_days)).strftime(TS)
    stats = {}
    with sqlite3.connect(db, timeout=30) as conn:
        stats["backfilled"] = backfill_rates(conn, compute_traffic_rates)

        cur = conn.execute("""
            INSERT INTO port_traffic_hourly (switch_id, ifindex, hour, in_avg, out_avg, in_max, out_max, errors, weight, samples)
            SELECT switch_id, ifindex, substr(timestamp, 1, 13) || ':00:00' AS h,
                   SUM(in_mbps * interval_sec) / SUM(interval_sec), SUM(out_mbps * interval_sec) / SUM(interval_sec),
                   MAX(in_mbps), MAX(out_mbps), SUM(COALESCE(errors_delta, 0)), SUM(interval_sec), COUNT(*)
            FROM port_traffic
            WHERE timestamp < ? AND in_mbps IS NOT NULL AND interval_sec > 0
            GROUP BY switch_id, ifindex, h
            ON CONFLICT(switch_id, ifindex, hour) DO UPDATE SET
                in_avg = (in_avg * weight + excluded.in_avg * excluded.weight) / (weight + excluded.weight),
                out_avg = (out_avg * weight + excluded.out_avg * excluded.weight) / (weight + excluded.weight),
                in_max = MAX(in_max, excluded.in_max), out_max = MAX(out_max, excluded.out_max),
                errors = errors + excluded.errors, weight = weight + excluded.weight, samples = samples + excluded.samples
        """, (raw_cutoff,))
        stats["traffic_hours"] = cur.rowcount
        stats["traffic_raw_deleted"] = conn.execute("DELETE FROM port_traffic WHERE timestamp < ?", (raw_cutoff,)).rowcount

        cur = conn.execute("""
            INSERT INTO switch_health_hourly (switch_id, hour, cpu_avg, cpu_max, ram_avg, ram_max, temp_avg, temp_max, samples)
            SELECT switch_id, substr(timestamp, 1, 13) || ':00:00' AS h,
                   AVG(NULLIF(cpu_usage, 0)), MAX(NULLIF(cpu_usage, 0)), AVG(NULLIF(ram_usage, 0)), MAX(NULLIF(ram_usage, 0)),
                   AVG(NULLIF(temperature, 0)), MAX(NULLIF(temperature, 0)), COUNT(*)
            FROM switch_health WHERE timestamp < ?
            GROUP BY switch_id, h
            ON CONFLICT(switch_id, hour) DO UPDATE SET
                cpu_avg = (COALESCE(cpu_avg, 0) * samples + COALESCE(excluded.cpu_avg, 0) * excluded.samples) / (samples + excluded.samples),
                ram_avg = (COALESCE(ram_avg, 0) * samples + COALESCE(excluded.ram_avg, 0) * excluded.samples) / (samples + excluded.samples),
                temp_avg = (COALESCE(temp_avg, 0) * samples + COALESCE(excluded.temp_avg, 0) * excluded.samples) / (samples + excluded.samples),
                cpu_max = MAX(cpu_max, excluded.cpu_max), ram_max = MAX(ram_max, excluded.ram_max),
                temp_max = MAX(temp_max, excluded.temp_max), samples = samples + excluded.samples
        """, (raw_cutoff,))
        stats["health_hours"] = cur.rowcount
        stats["health_raw_deleted"] = conn.execute("DELETE FROM switch_health WHERE timestamp < ?", (raw_cutoff,)).rowcount

        stats["traffic_hourly_deleted"] = conn.execute(
            "DELETE FROM port_traffic_hourly WHERE hour < ?", (hourly_cutoff,)).rowcount
        stats["health_hourly_deleted"] = conn.execute(
            "DELETE FROM switch_health_hourly WHERE hour < ?", (hourly_cutoff,)).rowcount
        stats["events_deleted"] = conn.execute(
            "DELETE FROM port_events WHERE event_time < ?", (events_cutoff,)).rowcount
        conn.commit()
    if vacuum:
        with sqlite3.connect(db, timeout=30) as conn:
            conn.execute("VACUUM")
    stats["time"] = now.strftime(TS)
    return stats


def db_stats(db):
    """Размер базы и объём данных по таблицам — для страницы «Данные»."""
    tables = ("switches", "port_traffic", "port_traffic_hourly", "switch_health", "switch_health_hourly",
              "port_events", "mac_table", "audit_log", "devices")
    out = {"file_size": os.path.getsize(db) if os.path.exists(db) else 0, "tables": {}}
    with sqlite3.connect(db, timeout=30) as conn:
        existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in tables:
            out["tables"][t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] if t in existing else 0
        out["raw_range"] = conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM port_traffic").fetchone()
        if "port_traffic_hourly" in existing:
            out["hourly_range"] = conn.execute("SELECT MIN(hour), MAX(hour) FROM port_traffic_hourly").fetchone()
    return out


# ─────────────────────────────────────────
# Ряды для графиков за период
# ─────────────────────────────────────────

# период → (длительность, сек; размер корзины, сек; None — сырые точки опросов)
PERIODS = {
    "1h":  (3600, None),
    "6h":  (6 * 3600, None),
    "24h": (86400, None),
    "7d":  (7 * 86400, 3600),
    "30d": (30 * 86400, 3 * 3600),
    "1y":  (365 * 86400, 86400),
}
MAX_RAW_POINTS = 720


def _bucket_start(dt, bucket_sec):
    epoch = datetime(2000, 1, 1)
    secs = int((dt - epoch).total_seconds())
    return epoch + timedelta(seconds=secs - secs % bucket_sec)


def _aggregate(records, bucket_sec, fields):
    """records — [{time: datetime, weight, <f>_avg, <f>_max, errors?}] → корзины с взвешенным средним."""
    buckets = {}
    for r in records:
        key = _bucket_start(r["time"], bucket_sec)
        b = buckets.setdefault(key, {"w": 0.0, "errors": 0, "sum": {f: 0.0 for f in fields},
                                     "wf": {f: 0.0 for f in fields}, "max": {f: None for f in fields}})
        w = r.get("weight") or 1.0
        b["w"] += w
        b["errors"] += r.get("errors") or 0
        for f in fields:
            avg, mx = r.get(f + "_avg"), r.get(f + "_max")
            if avg is not None:
                b["sum"][f] += avg * w
                b["wf"][f] += w
            if mx is not None:
                b["max"][f] = mx if b["max"][f] is None else max(b["max"][f], mx)
    points = []
    for key in sorted(buckets):
        b = buckets[key]
        p = {"timestamp": key.strftime(TS), "errors": b["errors"]}
        for f in fields:
            p[f] = round(b["sum"][f] / b["wf"][f], 3) if b["wf"][f] else None
            p[f + "_max"] = round(b["max"][f], 3) if b["max"][f] is not None else None
        points.append(p)
    return points


def traffic_series(db, switch_id, ifindex, period, now=None):
    """Скорость порта за период. Сырые точки — для коротких периодов, корзины — для длинных."""
    span, bucket = PERIODS.get(period, PERIODS["24h"])
    now = now or datetime.now()
    start = now - timedelta(seconds=span)
    start_s = start.strftime(TS)
    with sqlite3.connect(db, timeout=30) as conn:
        raw = conn.execute("""
            SELECT timestamp, in_mbps, out_mbps, interval_sec, errors_delta FROM port_traffic
            WHERE switch_id=? AND ifindex=? AND timestamp >= ? AND rate_done = 1 AND interval_sec > 0
            ORDER BY timestamp""", (switch_id, ifindex, start_s)).fetchall()
        hourly = [] if bucket is None else conn.execute("""
            SELECT hour, in_avg, out_avg, in_max, out_max, errors, weight FROM port_traffic_hourly
            WHERE switch_id=? AND ifindex=? AND hour >= ? ORDER BY hour""",
            (switch_id, ifindex, _floor_hour(start).strftime(TS))).fetchall()

    if bucket is None and len(raw) > MAX_RAW_POINTS:
        bucket = max(60, int(math.ceil(span / 360 / 60.0)) * 60)
    if bucket is None:
        points = [{"timestamp": t, "in_mbps": i, "out_mbps": o, "interval_sec": dt, "errors": e}
                  for t, i, o, dt, e in raw]
        return {"period": period, "bucket_sec": 0, "points": points}

    records = [{"time": _parse(h), "weight": w, "in_mbps_avg": i, "out_mbps_avg": o, "in_mbps_max": imx,
                "out_mbps_max": omx, "errors": e} for h, i, o, imx, omx, e, w in hourly]
    records += [{"time": _parse(t), "weight": dt, "in_mbps_avg": i, "out_mbps_avg": o, "in_mbps_max": i,
                 "out_mbps_max": o, "errors": e} for t, i, o, dt, e in raw]
    return {"period": period, "bucket_sec": bucket, "points": _aggregate(records, bucket, ("in_mbps", "out_mbps"))}


def health_series(db, switch_id, period, now=None):
    """CPU/RAM/температура за период."""
    span, bucket = PERIODS.get(period, PERIODS["24h"])
    now = now or datetime.now()
    start = now - timedelta(seconds=span)
    with sqlite3.connect(db, timeout=30) as conn:
        raw = conn.execute("""
            SELECT timestamp, cpu_usage, ram_usage, temperature FROM switch_health
            WHERE switch_id=? AND timestamp >= ? ORDER BY timestamp""", (switch_id, start.strftime(TS))).fetchall()
        hourly = [] if bucket is None else conn.execute("""
            SELECT hour, cpu_avg, cpu_max, ram_avg, ram_max, temp_avg, temp_max, samples FROM switch_health_hourly
            WHERE switch_id=? AND hour >= ? ORDER BY hour""", (switch_id, _floor_hour(start).strftime(TS))).fetchall()

    nz = lambda v: v if v else None  # 0 — датчик не ответил
    if bucket is None and len(raw) > MAX_RAW_POINTS:
        bucket = max(60, int(math.ceil(span / 360 / 60.0)) * 60)
    if bucket is None:
        return {"period": period, "bucket_sec": 0, "points": [
            {"timestamp": t, "cpu_usage": nz(c), "ram_usage": nz(r), "temperature": nz(tp)} for t, c, r, tp in raw]}

    records = [{"time": _parse(h), "weight": s, "cpu_usage_avg": ca, "cpu_usage_max": cm, "ram_usage_avg": ra,
                "ram_usage_max": rm, "temperature_avg": ta, "temperature_max": tm} for h, ca, cm, ra, rm, ta, tm, s in hourly]
    records += [{"time": _parse(t), "weight": 1, "cpu_usage_avg": nz(c), "cpu_usage_max": nz(c), "ram_usage_avg": nz(r),
                 "ram_usage_max": nz(r), "temperature_avg": nz(tp), "temperature_max": nz(tp)} for t, c, r, tp in raw]
    return {"period": period, "bucket_sec": bucket,
            "points": _aggregate(records, bucket, ("cpu_usage", "ram_usage", "temperature"))}


# ─────────────────────────────────────────
# Резервные копии
# ─────────────────────────────────────────

BACKUP_RE = re.compile(r"^switches-(\d{8}-\d{6})(?:-([a-z0-9-]+))?\.db$")
BACKUP_REASONS = {
    "manual": N_("вручную"), "auto": N_("автоматически"), "startup": N_("при запуске"),
    "pre-migrate": N_("перед обновлением базы"), "before-restore": N_("перед восстановлением"),
}


def backups_dir(db):
    path = os.path.join(os.path.dirname(os.path.abspath(db)), "backups")
    os.makedirs(path, exist_ok=True)
    return path


def create_backup(db, reason="manual"):
    """Согласованная копия через SQLite backup API (безопасно при параллельной записи)."""
    reason = re.sub(r"[^a-z0-9-]", "", reason.lower()) or "manual"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"switches-{stamp}-{reason}.db"
    path = os.path.join(backups_dir(db), name)
    n = 1
    while os.path.exists(path):  # две копии в одну секунду
        n += 1
        name = f"switches-{stamp}-{reason}-{n}.db"
        path = os.path.join(backups_dir(db), name)
    src = sqlite3.connect(db, timeout=30)
    dst = sqlite3.connect(path)
    try:
        src.backup(dst)
        # Копия — самостоятельный файл без -wal/-shm: её можно скачать, перенести, открыть только на чтение
        dst.execute("PRAGMA journal_mode=DELETE")
    finally:
        dst.close()
        src.close()
    return name


def list_backups(db):
    items = []
    folder = backups_dir(db)
    for name in os.listdir(folder):
        m = BACKUP_RE.match(name)
        if not m:
            continue
        reason = (m.group(2) or "manual")
        reason_key = re.sub(r"-\d+$", "", reason)
        items.append({
            "name": name,
            "size": os.path.getsize(os.path.join(folder, name)),
            "time": datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").strftime(TS),
            "reason": _(BACKUP_REASONS[reason_key]) if reason_key in BACKUP_REASONS else reason_key,
            "reason_key": reason_key,
        })
    return sorted(items, key=lambda x: x["name"], reverse=True)


def backup_path(db, name):
    """Путь к копии по имени; None, если имя не наше (защита от ../ и чужих файлов)."""
    if not BACKUP_RE.match(name or ""):
        return None
    path = os.path.join(backups_dir(db), name)
    return path if os.path.isfile(path) else None


def prune_backups(db, keep):
    removed = []
    for item in list_backups(db)[keep:]:
        os.remove(os.path.join(backups_dir(db), item["name"]))
        removed.append(item["name"])
    return removed


def last_backup_age_hours(db):
    items = list_backups(db)
    if not items:
        return None
    return (datetime.now() - _parse(items[0]["time"])).total_seconds() / 3600


def validate_backup_file(path):
    """Текст ошибки или None: файл должен быть базой SQLite SwitchMap."""
    try:
        with open(path, "rb") as f:
            if f.read(16) != b"SQLite format 3\x00":
                return _("файл не является базой SQLite")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                return _("база повреждена (integrity_check)")
            cols = {r[1] for r in conn.execute("PRAGMA table_info(switches)")}
            if not {"id", "name", "ports"} <= cols:
                return _("в файле нет таблицы коммутаторов SwitchMap")
        finally:
            conn.close()
    except sqlite3.Error as e:
        return _("не удалось открыть базу: {e}", e=e)
    return None


def restore_backup(db, path):
    """Заменяет содержимое базы копией. Перед этим сохраняет текущее состояние."""
    error = validate_backup_file(path)
    if error:
        raise ValueError(error)
    safety = create_backup(db, "before-restore")
    src = sqlite3.connect(path)
    dst = sqlite3.connect(db, timeout=30)
    try:
        src.backup(dst)
        enable_wal(dst)  # копия могла быть в обычном режиме — рабочей базе возвращаем WAL
    finally:
        dst.close()
        src.close()
    return safety


def enable_wal(conn):
    """Режим WAL: чтение не ждёт записи (страницы открываются, пока идёт опрос). Хранится в самом файле базы."""
    try:
        return conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    except sqlite3.Error:
        return None
