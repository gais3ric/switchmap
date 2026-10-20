"""Уведомления о событиях в Telegram и на почту.

Как это работает:
  * события по-прежнему пишутся в port_events (колокольчик в интерфейсе);
  * dispatch() раз в минуту и после каждого планового опроса берёт новые события,
    фильтрует их по настройкам канала и отправляет одним сообщением на канал;
  * у каждого канала свой курсор (id последнего обработанного события). Курсор
    сдвигается только после успешной отправки — если сеть пропала, сообщение уйдёт
    позже, с нарастающей паузой между попытками;
  * «мигающий» порт (много переключений за час) не заваливает сообщениями: одно
    предупреждение и пауза по этому порту на час.

Настройки — в app_settings: notify_config (пароль почты и токен бота зашифрованы),
notify_state (курсоры, ошибки, паузы). История отправок — в таблице notify_log.
"""
import html
import json
import os
import smtplib
import socket
import sqlite3
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr

TS = "%Y-%m-%d %H:%M:%S"
CHANNELS = ("telegram", "email")
CHANNEL_LABELS = {"telegram": "Telegram", "email": "Почта"}

# Группы событий, которые можно включать по отдельности
EVENT_GROUPS = {
    "switch": ("switch_down", "switch_up"),
    "port": ("down", "up"),
    "util": ("util_high", "util_ok"),
    "errors": ("errors_high", "errors_ok"),
    "health": ("cpu_high", "cpu_ok", "temp_high", "temp_ok"),
}
GROUP_LABELS = {
    "switch": "Коммутатор недоступен / снова доступен",
    "port": "Порт упал / поднялся",
    "util": "Высокая загрузка порта",
    "errors": "Ошибки на порту",
    "health": "CPU и температура коммутатора",
}
RECOVERY = {"switch_up", "up", "util_ok", "errors_ok", "cpu_ok", "temp_ok"}
# Что отправляется и в тихие часы
CRITICAL = {"switch_down", "switch_up", "temp_high"}
# Событие восстановления → событие, с которого началась проблема (для «длилось N мин»)
PAIRS = {"up": "down", "util_ok": "util_high", "errors_ok": "errors_high", "cpu_ok": "cpu_high", "temp_ok": "temp_high"}

LABELS = {
    "switch_down": "коммутатор недоступен", "switch_up": "коммутатор снова доступен",
    "down": "порт упал", "up": "порт поднялся",
    "util_high": "высокая загрузка", "util_ok": "загрузка в норме",
    "errors_high": "ошибки на порту", "errors_ok": "ошибки прекратились",
    "cpu_high": "высокая загрузка CPU", "cpu_ok": "CPU в норме",
    "temp_high": "перегрев", "temp_ok": "температура в норме",
}
SEVERITY_MARK = {"critical": "🔴", "warning": "🟠", "ok": "🟢", "info": "🔵"}

FLAP_WINDOW_MIN = 60     # окно подсчёта переключений порта
FLAP_MUTE_MIN = 60       # пауза по «мигающему» порту
STALE_HOURS = 24         # события старше — не отправляем поштучно, только число
BATCH_LIMIT = 500        # событий за один проход
MAX_LINES = 40           # строк в одном сообщении, остальное — «и ещё N»
RICH_BUDGET = 3000       # примерный объём строк событий, чтобы с заголовком и примечаниями уложиться в лимит Telegram
BACKOFF_MIN = (1, 2, 5, 10, 30, 60)
LOG_KEEP = 300
TELEGRAM_LIMIT = 4096

DEFAULT_CHANNEL = {
    "enabled": False,
    "events": ["switch", "port", "util", "errors", "health"],
    "recovery": True,
    "important_only": False,
    "quiet": {"enabled": False, "from": "23:00", "to": "08:00"},
}
DEFAULT_CONFIG = {
    "base_url": "",
    "flap_limit": 6,
    "telegram": {**DEFAULT_CHANNEL, "token": "", "chats": [], "proxy": ""},
    "email": {**DEFAULT_CHANNEL, "events": ["switch", "health"], "host": "", "port": 465, "security": "ssl",
              "verify": True, "username": "", "password": "", "sender": "", "recipients": ""},
}
SECRET_KEYS = {"telegram": "token", "email": "password"}

_lock = threading.Lock()


class NotifyError(Exception):
    """Понятная пользователю ошибка отправки."""


# ─────────────────────────────────────────
# Хранение
# ─────────────────────────────────────────

def ensure_table(c):
    c.execute("""
        CREATE TABLE IF NOT EXISTS notify_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT, channel TEXT, ok INTEGER,
            events INTEGER, title TEXT, error TEXT
        )""")


def _get_json(db, key):
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    try:
        data = json.loads(row[0]) if row and row[0] else {}
    except (TypeError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


def _put_json(db, key, value):
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value, ensure_ascii=False)))
        conn.commit()


def _merge(default, data):
    out = {}
    for k, v in default.items():
        if isinstance(v, dict):
            out[k] = _merge(v, data.get(k) if isinstance(data.get(k), dict) else {})
        else:
            out[k] = data.get(k, v)
    return out


def load_config(db):
    """Настройки с подставленными значениями по умолчанию. Секреты — зашифрованные, как в базе."""
    return _merge(DEFAULT_CONFIG, _get_json(db, "notify_config"))


def load_state(db):
    state = _get_json(db, "notify_state")
    for ch in CHANNELS:
        state.setdefault(ch, {})
    return state


def save_state(db, state):
    _put_json(db, "notify_state", state)


def _clean_time(value, default):
    try:
        return datetime.strptime(str(value).strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        return default


def _clean_chats(chats):
    out, seen = [], set()
    for c in chats if isinstance(chats, list) else []:
        if isinstance(c, (str, int)):
            c = {"id": c}
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id", "")).strip()
        if not cid or cid in seen or not cid.lstrip("-").isdigit() and not cid.startswith("@"):
            continue
        seen.add(cid)
        out.append({"id": cid, "title": str(c.get("title") or "")[:100]})
    return out[:20]


def sanitize(incoming, current, box):
    """Проверяет и нормализует настройки из формы. Пустой секрет — оставить прежний.
    Возвращает (config, error)."""
    cfg = _merge(DEFAULT_CONFIG, {})
    base = str(incoming.get("base_url") or "").strip().rstrip("/")
    if base and not base.lower().startswith(("http://", "https://")):
        return None, "Адрес SwitchMap должен начинаться с http:// или https://"
    cfg["base_url"] = base[:300]
    try:
        cfg["flap_limit"] = max(0, min(100, int(incoming.get("flap_limit", 6))))
    except (TypeError, ValueError):
        cfg["flap_limit"] = 6
    for ch in CHANNELS:
        src = incoming.get(ch) if isinstance(incoming.get(ch), dict) else {}
        cur = current.get(ch, {})
        dst = cfg[ch]
        dst["enabled"] = bool(src.get("enabled"))
        dst["events"] = [g for g in EVENT_GROUPS if g in (src.get("events") or [])]
        dst["recovery"] = bool(src.get("recovery", True))
        dst["important_only"] = bool(src.get("important_only"))
        q = src.get("quiet") if isinstance(src.get("quiet"), dict) else {}
        dst["quiet"] = {"enabled": bool(q.get("enabled")), "from": _clean_time(q.get("from"), "23:00"),
                        "to": _clean_time(q.get("to"), "08:00")}
        secret_key = SECRET_KEYS[ch]
        secret = str(src.get(secret_key) or "").strip()
        if src.get(secret_key + "_clear"):
            dst[secret_key] = ""
        elif secret:
            dst[secret_key] = box.encrypt(secret)
        else:
            dst[secret_key] = cur.get(secret_key, "")
        if ch == "telegram":
            dst["chats"] = _clean_chats(src.get("chats"))
            proxy = str(src.get("proxy") or "").strip()
            if proxy and not proxy.lower().startswith(("http://", "https://")):
                return None, "Прокси указывается как http://адрес:порт"
            dst["proxy"] = proxy[:300]
            if dst["enabled"] and (not dst["token"] or not dst["chats"]):
                return None, "Для Telegram нужны токен бота и хотя бы один чат"
        else:
            dst["host"] = str(src.get("host") or "").strip()[:200]
            try:
                dst["port"] = max(1, min(65535, int(src.get("port") or 465)))
            except (TypeError, ValueError):
                return None, "Порт почтового сервера — число от 1 до 65535"
            dst["security"] = src.get("security") if src.get("security") in ("ssl", "starttls", "none") else "ssl"
            dst["verify"] = bool(src.get("verify", True))
            dst["username"] = str(src.get("username") or "").strip()[:200]
            dst["sender"] = str(src.get("sender") or "").strip()[:200]
            rcpts = _split_addresses(src.get("recipients"))
            bad = [a for a in rcpts if not _valid_address(a)]
            if bad:
                return None, f"Неверный адрес получателя: {bad[0]}"
            dst["recipients"] = ", ".join(rcpts)
            sender = dst["sender"] or dst["username"]
            if sender and not _valid_address(parseaddr(sender)[1]):
                return None, "Адрес отправителя указан неверно"
            if dst["enabled"] and (not dst["host"] or not rcpts or not sender):
                return None, "Для почты нужны сервер, отправитель и хотя бы один получатель"
    return cfg, None


def save_config(db, cfg):
    """Сохраняет настройки. Канал, который только что включили, начинает с текущего
    момента — старые события не рассылаются."""
    with _lock:
        before = load_config(db)
        state = load_state(db)
        for ch in CHANNELS:
            if cfg[ch]["enabled"] and not before[ch]["enabled"]:
                state[ch] = {"cursor": _max_event_id(db)}
        _put_json(db, "notify_config", cfg)
        save_state(db, state)


def public_config(cfg):
    """Для браузера: секреты не отдаём, только признак, что они заданы."""
    out = json.loads(json.dumps(cfg))
    for ch, key in SECRET_KEYS.items():
        out[ch]["has_" + key] = bool(out[ch].pop(key, ""))
    return out


def describe_changes(before, after):
    """Список изменений для журнала (без секретов)."""
    changes = []

    def add(field, b, a):
        if b != a:
            changes.append({"field": field, "before": b, "after": a})

    yn = lambda v: "да" if v else "нет"
    add("Адрес SwitchMap для ссылок", before["base_url"] or "—", after["base_url"] or "—")
    add("Порог «мигания» порта", str(before["flap_limit"]), str(after["flap_limit"]))
    for ch in CHANNELS:
        b, a, name = before[ch], after[ch], CHANNEL_LABELS[ch]
        add(f"{name}: включено", yn(b["enabled"]), yn(a["enabled"]))
        groups = lambda c: ", ".join(GROUP_LABELS[g].lower() for g in c["events"]) or "—"
        add(f"{name}: события", groups(b), groups(a))
        add(f"{name}: о восстановлении", yn(b["recovery"]), yn(a["recovery"]))
        add(f"{name}: только важные порты", yn(b["important_only"]), yn(a["important_only"]))
        quiet = lambda c: f"{c['quiet']['from']}–{c['quiet']['to']}" if c["quiet"]["enabled"] else "выкл."
        add(f"{name}: тихие часы", quiet(b), quiet(a))
        key = SECRET_KEYS[ch]
        if b[key] != a[key]:
            changes.append({"field": f"{name}: {'токен бота' if ch == 'telegram' else 'пароль'}",
                            "before": "•••" if b[key] else "—", "after": "изменён" if a[key] else "удалён"})
        if ch == "telegram":
            chats = lambda c: ", ".join(x["title"] or x["id"] for x in c["chats"]) or "—"
            add(f"{name}: чаты", chats(b), chats(a))
            add(f"{name}: прокси", b["proxy"] or "—", a["proxy"] or "—")
        else:
            add(f"{name}: сервер", f"{b['host']}:{b['port']} ({b['security']})" if b["host"] else "—",
                f"{a['host']}:{a['port']} ({a['security']})" if a["host"] else "—")
            add(f"{name}: логин", b["username"] or "—", a["username"] or "—")
            add(f"{name}: получатели", b["recipients"] or "—", a["recipients"] or "—")
    return changes


def _max_event_id(db):
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT COALESCE(MAX(id), 0) FROM port_events").fetchone()[0]


def write_log(db, channel, ok, events, title, error=""):
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO notify_log (time, channel, ok, events, title, error) VALUES (?, ?, ?, ?, ?, ?)",
                     (datetime.now().strftime(TS), channel, 1 if ok else 0, events, title[:300], (error or "")[:500]))
        conn.execute("DELETE FROM notify_log WHERE id <= (SELECT MAX(id) FROM notify_log) - ?", (LOG_KEEP,))
        conn.commit()


def log_entries(db, limit=50):
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT id, time, channel, ok, events, title, error FROM notify_log "
                            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"id": r[0], "time": r[1], "channel": r[2], "channel_label": CHANNEL_LABELS.get(r[2], r[2]),
             "ok": bool(r[3]), "events": r[4], "title": r[5] or "", "error": r[6] or ""} for r in rows]


# ─────────────────────────────────────────
# Отбор событий и текст сообщения
# ─────────────────────────────────────────

def _in_quiet_hours(quiet, now):
    if not quiet.get("enabled"):
        return False
    start, end, cur = quiet["from"], quiet["to"], now.strftime("%H:%M")
    if start == end:
        return False
    return start <= cur < end if start < end else (cur >= start or cur < end)


def _parse_ts(value):
    try:
        return datetime.strptime(value, TS)
    except (TypeError, ValueError):
        return None


def _plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def _duration(minutes):
    minutes = int(round(minutes))
    if minutes < 1:
        return "меньше минуты"
    if minutes < 60:
        return f"{minutes} мин"
    hours, mins = divmod(minutes, 60)
    if hours < 48:
        return f"{hours} ч {mins} мин" if mins else f"{hours} ч"
    return f"{hours // 24} дн {hours % 24} ч"


def _switch_info(conn):
    """id → {name, ip, important: set(ifindex), aliases}. Важный порт — с описанием (ifAlias),
    подключением на схеме или помеченный как транк."""
    info = {}
    for sid, name, ip, snapshot, connections, trunks in conn.execute(
            "SELECT id, name, ip_address, port_status_snapshot, connections, trunk_ports FROM switches"):
        try:
            snap = json.loads(snapshot) if snapshot else {}
        except (TypeError, ValueError):
            snap = {}
        try:
            conns = json.loads(connections) if connections else {}
        except (TypeError, ValueError):
            conns = {}
        try:
            trunk = json.loads(trunks) if trunks else {}
        except (TypeError, ValueError):
            trunk = {}
        marked = {str(k) for k, v in conns.items() if v} | {str(k) for k, v in trunk.items() if v}
        important, aliases = set(), {}
        for ifindex, port in snap.items():
            if not isinstance(port, dict):
                continue
            alias = (port.get("alias") or "").strip()
            if alias:
                aliases[str(ifindex)] = alias
            if alias or str(port.get("port") or "") in marked:
                important.add(str(ifindex))
        info[sid] = {"name": name or f"Коммутатор {sid}", "ip": ip or "", "important": important, "aliases": aliases}
    return info


def _flap_count(conn, switch_id, ifindex, now):
    since = (now - timedelta(minutes=FLAP_WINDOW_MIN)).strftime(TS)
    return conn.execute("SELECT COUNT(*) FROM port_events WHERE switch_id=? AND ifindex=? AND event_type IN ('up','down') "
                        "AND event_time >= ?", (switch_id, ifindex, since)).fetchone()[0]


def _problem_duration(conn, ev):
    """Сколько длилась проблема, закончившаяся событием восстановления ev."""
    start_type = PAIRS.get(ev["event_type"])
    if not start_type:
        return None
    if ev["ifindex"] is None:
        row = conn.execute("SELECT event_time FROM port_events WHERE switch_id=? AND ifindex IS NULL AND event_type=? "
                           "AND id < ? ORDER BY id DESC LIMIT 1", (ev["switch_id"], start_type, ev["id"])).fetchone()
    else:
        row = conn.execute("SELECT event_time FROM port_events WHERE switch_id=? AND ifindex=? AND event_type=? "
                           "AND id < ? ORDER BY id DESC LIMIT 1", (ev["switch_id"], ev["ifindex"], start_type, ev["id"])).fetchone()
    start, end = _parse_ts(row[0]) if row else None, _parse_ts(ev["event_time"])
    if not start or not end or end < start:
        return None
    return (end - start).total_seconds() / 60


def select_events(conn, rows, ch_cfg, flap_limit, mutes, now):
    """Отбирает события для канала. Возвращает (items, notes): items — события
    (с подписью порта и длительностью), notes — служебные строки (мигающий порт, пропуски)."""
    allowed = set()
    for g in ch_cfg["events"]:
        allowed.update(EVENT_GROUPS.get(g, ()))
    if not ch_cfg["recovery"]:
        allowed -= RECOVERY
    quiet = _in_quiet_hours(ch_cfg["quiet"], now)
    info = _switch_info(conn)
    stale_before = now - timedelta(hours=STALE_HOURS)
    now_s = now.strftime(TS)

    items, notes, stale, quiet_skipped = [], [], 0, 0
    flapping_now = {}
    for ev in rows:
        etype = ev["event_type"]
        if etype not in allowed:
            continue
        sw = info.get(ev["switch_id"], {"name": f"Коммутатор {ev['switch_id']}", "ip": "", "important": set(), "aliases": {}})
        is_port = ev["ifindex"] is not None
        if is_port and ch_cfg["important_only"] and str(ev["ifindex"]) not in sw["important"]:
            continue
        ts = _parse_ts(ev["event_time"])
        if ts and ts < stale_before:
            stale += 1
            continue
        if quiet and etype not in CRITICAL:
            quiet_skipped += 1
            continue
        if etype in ("up", "down") and flap_limit:
            key = f"{ev['switch_id']}:{ev['ifindex']}"
            if mutes.get(key, "") > now_s:
                continue
            count = _flap_count(conn, ev["switch_id"], ev["ifindex"], now)
            if count >= flap_limit:
                mutes[key] = (now + timedelta(minutes=FLAP_MUTE_MIN)).strftime(TS)
                flapping_now[key] = (ev, sw, count)
                continue
        item = dict(ev)
        item["switch_name"], item["switch_ip"] = sw["name"], sw["ip"]
        item["alias"] = sw["aliases"].get(str(ev["ifindex"]), "") if is_port else ""
        item["duration"] = _problem_duration(conn, ev) if etype in PAIRS else None
        items.append(item)

    # Мигающие порты: убираем их обычные события из этой пачки, вместо них — одна строка
    if flapping_now:
        items = [i for i in items if not (i["event_type"] in ("up", "down")
                                          and f"{i['switch_id']}:{i['ifindex']}" in flapping_now)]
        for key, (ev, sw, count) in flapping_now.items():
            notes.append({"severity": "warning", "switch_id": ev["switch_id"], "switch_name": sw["name"],
                          "port_number": ev["port_number"], "text":
                          f"{sw['name']}: порт {_port_label(ev, sw['aliases'].get(str(ev['ifindex']), ''))} нестабилен — "
                          f"{count} переключений за час. Уведомления по нему приостановлены на час."})
    if stale:
        notes.append({"severity": "info", "text": f"Пропущено старых событий (больше {STALE_HOURS} ч назад): {stale}. "
                                                  "Они есть в журнале событий SwitchMap."})
    if quiet_skipped and items:
        notes.append({"severity": "info", "text": f"Тихие часы: некритичных событий не отправлено — {quiet_skipped}."})
    return items, notes


def _port_label(ev, alias=""):
    parts = []
    if ev.get("port_number"):
        parts.append(str(ev["port_number"]))
    name = ev.get("port_name") or ""
    if name and name != str(ev.get("port_number")):
        parts.append(name)
    label = " · ".join(parts) or str(ev.get("ifindex"))
    return f"{label} «{alias}»" if alias else label


def _severity(etype):
    if etype in RECOVERY:
        return "ok"
    if etype in ("switch_down", "down", "cpu_high", "temp_high"):
        return "critical"
    return "warning"


def _collapse(items):
    """Несколько переключений одного порта в одной пачке — одной строкой."""
    out, seen = [], {}
    for it in items:
        if it["event_type"] in ("up", "down"):
            key = (it["switch_id"], it["ifindex"])
            if key in seen:
                first = seen[key]
                first["flips"] = first.get("flips", 1) + 1
                first["final"] = it["event_type"]
                first["event_time_last"] = it["event_time"]
                continue
            seen[key] = it
        out.append(it)
    return out


def _short_time(value, now):
    ts = _parse_ts(value)
    if not ts:
        return value or ""
    return ts.strftime("%H:%M") if ts.date() == now.date() else ts.strftime("%d.%m %H:%M")


def _line(it, now):
    """(severity, текст строки без названия коммутатора) для одного события."""
    etype = it["event_type"]
    if it.get("flips"):
        final = it["final"]
        sev = "ok" if final == "up" else "critical"
        text = (f"порт {_port_label(it, it['alias'])} переключался {it['flips']} {_plural(it['flips'], 'раз', 'раза', 'раз')}, сейчас "
                f"{'работает' if final == 'up' else 'не работает'}")
        return sev, text, _short_time(it.get("event_time_last") or it["event_time"], now)
    label = LABELS.get(etype, etype)
    if it["ifindex"] is not None:
        text = f"порт {_port_label(it, it['alias'])} — {label.removeprefix('порт ')}"
    else:
        text = label[:1].upper() + label[1:]
    details = (it.get("details") or "").strip()
    if details:
        text += f": {details}"
    if it.get("duration") is not None and etype != "switch_up":
        text += f" (длилось {_duration(it['duration'])})"
    return _severity(etype), text, _short_time(it["event_time"], now)


def build_message(items, notes, base_url, now=None):
    """Текст сообщения. Возвращает dict: title, text (обычный текст), html (для Telegram/почты)."""
    now = now or datetime.now()
    items = _collapse(items)
    switches = {}
    for it in items:
        switches.setdefault(it["switch_id"], []).append(it)

    if len(items) == 1 and not notes:
        it = items[0]
        if it.get("flips"):
            title = f"{it['switch_name']}: порт {_port_label(it, it['alias'])} переключался"
        else:
            label = LABELS.get(it["event_type"], it["event_type"])
            title = (f"{it['switch_name']}: порт {_port_label(it, it['alias'])} — {label.removeprefix('порт ')}"
                     if it["ifindex"] is not None else f"{it['switch_name']}: {label}")
    elif items:
        n = len(items)
        word = _plural(n, "событие", "события", "событий")
        title =(f"{next(iter(switches.values()))[0]['switch_name']}: {n} {word}" if len(switches) == 1
                 else f"{n} {word} на {len(switches)} коммутаторах")
    else:
        title = notes[0]["text"] if notes else "SwitchMap"
    if len(title) > 150:
        title = title[:147] + "…"

    def link(switch_id, port=None):
        if not base_url:
            return ""
        return f"{base_url}/switch/{switch_id}" + (f"?port={urllib.parse.quote(str(port))}" if port else "")

    plain, rich, shown, size = [], [], 0, 0
    full = lambda: shown >= MAX_LINES or size > RICH_BUDGET  # Telegram режет сообщения длиннее 4096 символов
    for sid, group in switches.items():
        if full():
            break
        first = group[0]
        head = first["switch_name"] + (f" ({first['switch_ip']})" if first["switch_ip"] else "")
        url = link(sid)
        plain.append(head + (f" — {url}" if url else ""))
        rich.append(f"<b>{html.escape(head)}</b>" + (f' · <a href="{html.escape(url)}">открыть</a>' if url else ""))
        for it in group:
            if full():
                break
            sev, text, at = _line(it, now)
            mark = SEVERITY_MARK[sev]
            plain.append(f"  {mark} {at}  {text}")
            purl = link(sid, it.get("port_number")) if it.get("port_number") else ""
            body = html.escape(text)
            rich.append(f"{mark} <code>{at}</code> " + (f'<a href="{html.escape(purl)}">{body}</a>' if purl else body))
            size += len(rich[-1])
            shown += 1
        plain.append("")
        rich.append("")
    if shown < len(items):
        rest = len(items) - shown
        plain.append(f"…и ещё {rest}. Полный список — в журнале событий SwitchMap.")
        rich.append(f"<i>…и ещё {rest}. Полный список — в журнале событий SwitchMap.</i>")
    for note in notes:
        mark = SEVERITY_MARK[note["severity"]]
        plain.append(f"{mark} {note['text']}")
        rich.append(f"{mark} <i>{html.escape(note['text'])}</i>")
    return {"title": title, "text": "\n".join(plain).strip(), "html": "\n".join(rich).strip(), "count": len(items)}


# ─────────────────────────────────────────
# Отправка
# ─────────────────────────────────────────

def _http_json(url, data=None, proxy="", timeout=15):
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})]
    opener = urllib.request.build_opener(*handlers)
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"} if body else {})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        if e.code == 407:
            raise NotifyError("Прокси требует логин и пароль: укажите их в адресе прокси")
        try:
            data = json.loads(e.read().decode("utf-8") or "{}")
        except ValueError:
            data = {}
        if isinstance(data, dict) and "ok" in data:
            return data
        if e.code >= 500:
            raise NotifyError(f"Сервер Telegram временно недоступен (HTTP {e.code}) — сообщение уйдёт при следующей попытке")
        raise NotifyError(f"Telegram ответил ошибкой HTTP {e.code}" + (" — возможно, мешает прокси" if proxy else ""))
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        reason = getattr(e, "reason", e)
        hint = " через прокси " + proxy if proxy else ""
        raise NotifyError(f"Нет связи с api.telegram.org{hint}: {reason}. Проверьте доступ в интернет с сервера "
                          "SwitchMap или укажите прокси.")


# Можно указать собственный сервер Bot API (telegram-bot-api) — например, если Telegram доступен только через него
TELEGRAM_API = os.environ.get("SWITCHMAP_TELEGRAM_API", "https://api.telegram.org").rstrip("/")


def _tg_call(token, method, payload=None, proxy=""):
    if not token:
        raise NotifyError("Не указан токен бота")
    resp = _http_json(f"{TELEGRAM_API}/bot{token}/{method}", payload, proxy)
    if resp.get("ok"):
        return resp.get("result")
    code, desc = resp.get("error_code"), resp.get("description") or "неизвестная ошибка"
    if code in (401, 404):
        raise NotifyError("Telegram не принял токен бота — проверьте, что он скопирован целиком")
    err = NotifyError(_tg_error_text(desc))
    err.parameters = resp.get("parameters") or {}
    raise err


def _tg_error_text(desc):
    low = desc.lower()
    if "chat not found" in low:
        return "Чат не найден: напишите боту /start или добавьте бота в группу"
    if "bot was blocked" in low:
        return "Пользователь заблокировал бота — разблокируйте его в Telegram"
    if "kicked" in low or "not a member" in low:
        return "Бот удалён из группы — добавьте его снова"
    if "too many requests" in low:
        return "Telegram просит подождать (слишком много сообщений)"
    if "upgraded to a supergroup" in low:
        return "Группа стала супергруппой — номер чата изменился"
    return f"Telegram: {desc}"


def telegram_bot_info(token, proxy=""):
    me = _tg_call(token, "getMe", proxy=proxy)
    return {"username": me.get("username", ""), "name": me.get("first_name", "")}


def telegram_find_chats(token, proxy=""):
    """Чаты, где боту писали или куда его добавили (Telegram хранит такие обновления сутки)."""
    updates = _tg_call(token, "getUpdates", {"allowed_updates": ["message", "my_chat_member", "channel_post"],
                                             "timeout": 0}, proxy) or []
    chats = {}
    for upd in updates:
        for key in ("message", "my_chat_member", "channel_post", "edited_message"):
            chat = (upd.get(key) or {}).get("chat")
            if not chat:
                continue
            if chat.get("type") == "private":
                title = " ".join(x for x in (chat.get("first_name"), chat.get("last_name")) if x)
                if chat.get("username"):
                    title += f" (@{chat['username']})"
            else:
                title = chat.get("title") or ""
            kind = {"private": "личный чат", "group": "группа", "supergroup": "группа", "channel": "канал"}.get(chat.get("type"), "")
            chats[str(chat["id"])] = {"id": str(chat["id"]), "title": title.strip() or str(chat["id"]), "kind": kind}
    return list(chats.values())


def _tg_html(msg):
    # Одно событие — заголовок повторял бы текст; для пачки заголовок — сводка
    text = f"<b>{html.escape(msg['title'])}</b>\n\n{msg['html']}" if msg["count"] > 1 else msg["html"]
    if len(text) > TELEGRAM_LIMIT:
        cut = text[:TELEGRAM_LIMIT - 80]
        cut = cut[:cut.rfind("\n")] if "\n" in cut else cut
        text = cut + "\n<i>…сообщение сокращено, полный список — в SwitchMap</i>"
    return text


def send_telegram(cfg, box, msg):
    """Отправляет во все чаты. Возвращает (доставлено, ошибки, новые id чатов после миграции групп)."""
    token = box.decrypt(cfg["token"]) if cfg.get("token") else ""
    if not token:
        raise NotifyError("Не указан токен бота")
    if not cfg["chats"]:
        raise NotifyError("Не выбран ни один чат")
    text = _tg_html(msg)
    delivered, errors, migrated = 0, [], {}
    for chat in cfg["chats"]:
        cid = chat["id"]
        for _ in range(2):
            try:
                _tg_call(token, "sendMessage", {"chat_id": cid, "text": text, "parse_mode": "HTML",
                                                "disable_web_page_preview": True}, cfg.get("proxy", ""))
                delivered += 1
                break
            except NotifyError as e:
                new_id = getattr(e, "parameters", {}).get("migrate_to_chat_id")
                if new_id and str(new_id) != cid:
                    migrated[chat["id"]] = str(new_id)
                    cid = str(new_id)
                    continue
                errors.append(f"{chat.get('title') or chat['id']}: {e}")
                break
    return delivered, errors, migrated


def _split_addresses(value):
    if isinstance(value, list):
        value = ",".join(str(v) for v in value)
    return [a.strip() for a in str(value or "").replace(";", ",").replace("\n", ",").split(",") if a.strip()][:20]


def _valid_address(addr):
    addr = addr.strip()
    if "@" not in addr or " " in addr:
        return False
    local, _, domain = addr.rpartition("@")
    return bool(local) and "." in domain and not domain.startswith(".") and not domain.endswith(".")


def _email_html(msg):
    body = msg["html"].replace("\n", "<br>\n")
    return (f'<div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;line-height:1.55;color:#1f2430">'
            f'<div style="font-size:16px;font-weight:600;margin-bottom:12px">{html.escape(msg["title"])}</div>'
            f'{body}'
            f'<div style="margin-top:18px;font-size:12px;color:#8a90a0">Это сообщение отправил SwitchMap. '
            f'Настроить уведомления можно на странице «Уведомления».</div></div>')


def send_email(cfg, box, msg):
    rcpts = _split_addresses(cfg["recipients"])
    if not cfg["host"]:
        raise NotifyError("Не указан почтовый сервер")
    if not rcpts:
        raise NotifyError("Не указан ни один получатель")
    sender = cfg["sender"] or cfg["username"]
    if not sender:
        raise NotifyError("Не указан адрес отправителя")
    sender_name, sender_addr = parseaddr(sender)

    em = EmailMessage()
    em["Subject"] = f"[SwitchMap] {msg['title']}"
    em["From"] = formataddr((sender_name or "SwitchMap", sender_addr))
    em["To"] = ", ".join(rcpts)
    em["Date"] = formatdate(localtime=True)
    em["Message-ID"] = make_msgid(domain=sender_addr.rpartition("@")[2] or None)
    em.set_content(msg["text"] + "\n\n— SwitchMap")
    em.add_alternative(_email_html(msg), subtype="html")

    context = ssl.create_default_context()
    if not cfg.get("verify", True):
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    password = box.decrypt(cfg["password"]) if cfg.get("password") else ""
    where = f"{cfg['host']}:{cfg['port']}"
    try:
        if cfg["security"] == "ssl":
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20, context=context)
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=20)
        with server:
            server.ehlo()
            if cfg["security"] == "starttls":
                server.starttls(context=context)
                server.ehlo()
            if cfg["username"]:
                server.login(cfg["username"], password)
            refused = server.send_message(em, from_addr=sender_addr, to_addrs=rcpts)
    except smtplib.SMTPAuthenticationError:
        raise NotifyError("Сервер отклонил логин или пароль. Для Gmail, Яндекса и Mail.ru нужен «пароль приложения», "
                          "а не обычный пароль от почты")
    except smtplib.SMTPNotSupportedError:
        raise NotifyError("Сервер не поддерживает вход по паролю на этом порту — попробуйте другой тип шифрования")
    except smtplib.SMTPRecipientsRefused as e:
        raise NotifyError("Сервер не принял получателей: " + ", ".join(e.recipients))
    except smtplib.SMTPSenderRefused as e:
        raise NotifyError(f"Сервер не принял отправителя {e.sender}: обычно отправитель должен совпадать с логином")
    except ssl.SSLCertVerificationError as e:
        raise NotifyError(f"Сертификат сервера {where} не прошёл проверку ({e.verify_message}). Для внутреннего "
                          "сервера с самоподписанным сертификатом снимите галочку «Проверять сертификат»")
    except ssl.SSLError as e:
        raise NotifyError(f"Ошибка SSL при подключении к {where}: {e.reason or e}. Обычно порт 465 — SSL, 587 — STARTTLS, "
                          "25 — без шифрования")
    except smtplib.SMTPServerDisconnected:
        raise NotifyError(f"Сервер {where} разорвал соединение — проверьте порт и тип шифрования")
    except smtplib.SMTPException as e:
        raise NotifyError(f"Почтовый сервер ответил ошибкой: {e}")
    except socket.gaierror:
        raise NotifyError(f"Сервер {cfg['host']} не найден — проверьте адрес")
    except (socket.timeout, TimeoutError):
        raise NotifyError(f"Сервер {where} не ответил за 20 секунд — проверьте адрес, порт и доступ из сети")
    except OSError as e:
        raise NotifyError(f"Не удалось подключиться к {where}: {e.strerror or e}")
    if refused:
        raise NotifyError("Часть получателей не принята: " + ", ".join(refused))
    return len(rcpts)


def send(channel, cfg, box, msg):
    """Отправка в канал. Возвращает (описание результата, предупреждение или '', миграции чатов)."""
    if channel == "telegram":
        delivered, errors, migrated = send_telegram(cfg, box, msg)
        if not delivered:
            raise NotifyError("; ".join(errors) or "не доставлено")
        return f"доставлено в чатов: {delivered}", "; ".join(errors), migrated
    count = send_email(cfg, box, msg)
    return f"получателей: {count}", "", {}


def test_message(base_url):
    now = datetime.now()
    text = ("Тестовое сообщение. Если вы его видите — уведомления настроены правильно.\n"
            f"Время сервера: {now.strftime('%d.%m.%Y %H:%M:%S')}")
    rich = "✅ " + html.escape(text)
    if base_url:
        text += f"\nSwitchMap: {base_url}"
        rich += f'\n<a href="{html.escape(base_url)}">Открыть SwitchMap</a>'
    return {"title": "проверка уведомлений", "text": text, "html": rich, "count": 1}


# ─────────────────────────────────────────
# Рассылка новых событий
# ─────────────────────────────────────────

def dispatch(db, box, now=None, sender=None):
    """Отправляет накопившиеся события во включённые каналы. sender — для тестов.
    Возвращает {канал: итог}."""
    if not _lock.acquire(blocking=False):
        return {"skipped": "рассылка уже идёт"}
    try:
        return _dispatch(db, box, now or datetime.now(), sender or send)
    finally:
        _lock.release()


def _dispatch(db, box, now, sender):
    cfg = load_config(db)
    state = load_state(db)
    now_s = now.strftime(TS)
    report = {}
    for ch in CHANNELS:
        ch_cfg = cfg[ch]
        if not ch_cfg["enabled"]:
            continue
        st = state[ch]
        if "cursor" not in st:
            st["cursor"] = _max_event_id(db)
        if st.get("next_try") and st["next_try"] > now_s:
            report[ch] = "ждёт повтора"
            continue
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute(
                "SELECT id, switch_id, ifindex, port_name, port_number, event_type, event_time, details "
                "FROM port_events WHERE id > ? ORDER BY id LIMIT ?", (st["cursor"], BATCH_LIMIT))]
            if not rows:
                continue
            mutes = state.setdefault("mutes_" + ch, {})
            items, notes = select_events(conn, rows, ch_cfg, cfg["flap_limit"], mutes, now)
        last_id = rows[-1]["id"]
        if not items and not [n for n in notes if n["severity"] != "info"]:
            st["cursor"] = last_id
            report[ch] = "нечего отправлять"
            continue
        msg = build_message(items, notes, cfg["base_url"], now)
        try:
            result, warning, migrated = sender(ch, ch_cfg, box, msg)
        except NotifyError as e:
            fails = st.get("fails", 0) + 1
            st.update(fails=fails, last_error=str(e), last_error_time=now_s,
                      next_try=(now + timedelta(minutes=BACKOFF_MIN[min(fails, len(BACKOFF_MIN)) - 1])).strftime(TS))
            if fails <= 3 or fails % 10 == 0:
                write_log(db, ch, False, msg["count"], msg["title"], str(e))
            report[ch] = f"ошибка: {e}"
            continue
        except Exception as e:  # неожиданная ошибка не должна ломать планировщик
            st.update(fails=st.get("fails", 0) + 1, last_error=f"Внутренняя ошибка: {e}", last_error_time=now_s,
                      next_try=(now + timedelta(minutes=5)).strftime(TS))
            write_log(db, ch, False, msg["count"], msg["title"], f"Внутренняя ошибка: {e}")
            report[ch] = f"ошибка: {e}"
            continue
        if migrated:
            _apply_chat_migration(db, migrated)
        st.update(cursor=last_id, fails=0, next_try="", last_ok=now_s, last_warning=warning)
        if not warning:
            st.pop("last_error", None)
        write_log(db, ch, True, msg["count"], msg["title"], warning)
        report[ch] = result
    # Паузы по мигающим портам — отдельно для каждого канала
    for ch in CHANNELS:
        key = "mutes_" + ch
        if key in state:
            state[key] = {k: v for k, v in state[key].items() if v > now_s}
    save_state(db, state)
    return report


def _apply_chat_migration(db, migrated):
    cfg = load_config(db)
    for chat in cfg["telegram"]["chats"]:
        if chat["id"] in migrated:
            chat["id"] = migrated[chat["id"]]
    _put_json(db, "notify_config", cfg)


def status(db):
    """Состояние каналов для страницы настроек."""
    cfg, state = load_config(db), load_state(db)
    out = {}
    for ch in CHANNELS:
        st = state.get(ch, {})
        pending = 0
        if cfg[ch]["enabled"] and "cursor" in st:
            with sqlite3.connect(db) as conn:
                pending = conn.execute("SELECT COUNT(*) FROM port_events WHERE id > ?", (st["cursor"],)).fetchone()[0]
        out[ch] = {"enabled": cfg[ch]["enabled"], "last_ok": st.get("last_ok", ""), "last_error": st.get("last_error", ""),
                   "last_error_time": st.get("last_error_time", ""), "fails": st.get("fails", 0),
                   "next_try": st.get("next_try", ""), "pending": pending, "warning": st.get("last_warning", "")}
    return out


def retry_now(db):
    """Сбросить паузу между попытками — «Повторить сейчас»."""
    with _lock:
        state = load_state(db)
        for ch in CHANNELS:
            state[ch]["next_try"] = ""
        save_state(db, state)
