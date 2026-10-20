"""Журнал изменений: кто, когда и что поменял. Позволяет откатить правку коммутатора
и восстановить удалённый коммутатор вместе с подключениями и устройствами.

В таблице хранятся:
  details — видимая часть (список изменений «было → стало»), отдаётся в браузер;
  revert  — служебные данные для отката (прежние значения, снимок удалённого), в браузер не отдаётся.
"""
import json
import sqlite3
from datetime import datetime

from i18n import N_, _, _ns, _s

TS = "%Y-%m-%d %H:%M:%S"

ACTIONS = {
    "create": N_("Создан коммутатор"),
    "update": N_("Изменён коммутатор"),
    "delete": N_("Удалён коммутатор"),
    "restore_switch": N_("Восстановлен коммутатор"),
    "revert": N_("Откат изменения"),
    "device_assign": N_("Устройство привязано"),
    "device_remove": N_("Устройство отвязано"),
    "vlan_color": N_("Цвет VLAN"),
    "settings": N_("Настройки"),
    "db_restore": N_("База восстановлена из копии"),
    "user_create": N_("Пользователь создан"),
    "user_update": N_("Пользователь изменён"),
    "user_delete": N_("Пользователь удалён"),
    "password_change": N_("Смена пароля"),
    "login_failed": N_("Неудачный вход"),
    "notify_settings": N_("Уведомления"),
    "netbox_settings": N_("Настройки NetBox"),
}

# Простые поля коммутатора: колонка → подпись
FIELDS = (
    ("name", N_("Название")),
    ("ports", N_("Количество портов")),
    ("switch_layout", N_("Расположение портов")),
    ("ip_address", N_("IP-адрес")),
    ("model", N_("Модель")),
    ("snmp_community", "SNMP community"),
    ("snmp_version", N_("Версия SNMP")),
    ("snmp_v3_user", N_("Пользователь SNMPv3")),
    ("snmp_v3_auth_proto", N_("Аутентификация SNMPv3")),
    ("snmp_v3_priv_proto", N_("Шифрование SNMPv3")),
    ("snmp_v3_context", N_("Контекст SNMPv3")),
)
SECRET_FIELDS = (("snmp_v3_auth_key", N_("Пароль аутентификации SNMPv3")), ("snmp_v3_priv_key", N_("Пароль шифрования SNMPv3")))
JSON_FIELDS = ("connections", "port_types", "trunk_ports", "patch_panels")
LAYOUTS = {"single": N_("1 строка"), "double": N_("2 строки")}
PORT_TYPES = {"rj45": "RJ-45", "sfp": "SFP"}


def ensure_table(c):
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT, actor TEXT,
            switch_id INTEGER, switch_name TEXT,
            action TEXT, summary TEXT,
            details TEXT, revert TEXT,
            reverted_by INTEGER
        )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_switch ON audit_log (switch_id, id)")


def log(db, action, *, actor=None, switch_id=None, switch_name=None, summary="", changes=None, revert=None):
    with sqlite3.connect(db) as conn:
        cur = conn.execute("""
            INSERT INTO audit_log (time, actor, switch_id, switch_name, action, summary, details, revert)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now().strftime(TS), actor, switch_id, switch_name, action, summary,
             json.dumps({"changes": changes or []}, ensure_ascii=False),
             json.dumps(revert, ensure_ascii=False) if revert is not None else None))
        conn.commit()
        return cur.lastrowid


def _load(value, default):
    try:
        data = json.loads(value) if value else default
    except (TypeError, ValueError):
        return default
    return data if isinstance(data, type(default)) else default


def _fmt(col, value):
    if value in (None, ""):
        return "—"
    if col == "switch_layout":
        return _s(LAYOUTS[value]) if value in LAYOUTS else value
    if col == "snmp_version":
        return "v3" if str(value) == "3" else "v2c"
    return str(value)


def _port_sort(key):
    return (0, int(key)) if str(key).isdigit() else (1, str(key))


def diff_switch(before, after):
    """Список изменений между двумя строками switches (dict). Возвращает (changes, revert_fields)."""
    changes, revert = [], {}
    for col, label in FIELDS:
        b, a = before.get(col), after.get(col)
        if (b or None) != (a or None) and str(b or "") != str(a or ""):
            changes.append({"field": _s(label), "before": _fmt(col, b), "after": _fmt(col, a)})
            revert[col] = b
    for col, label in SECRET_FIELDS:
        if (before.get(col) or "") != (after.get(col) or ""):
            changes.append({"field": _s(label), "before": "•••" if before.get(col) else "—",
                            "after": _s("изменён") if after.get(col) else _s("удалён")})

    # Подключения портов
    bc, ac = _load(before.get("connections"), {}), _load(after.get("connections"), {})
    conn_changed = False
    for port in sorted(set(bc) | set(ac), key=_port_sort):
        b, a = bc.get(port), ac.get(port)
        if b == a:
            continue
        conn_changed = True
        describe = lambda c: (f"{c.get('name') or '—'}" +
                              (_s(" (напрямую)") if c.get("patchPanel") is None else _s(" → панель {patchPanel}, порт {patch}", patchPanel=c.get('patchPanel'), patch=c.get('patch'))))
        changes.append({"field": _s("Подключение порта {port}", port=port),
                        "before": describe(b) if b else "—", "after": describe(a) if a else _s("удалено")})
    if conn_changed:
        revert["connections"] = before.get("connections")

    # Типы портов и транки
    bt, at = _load(before.get("port_types"), {}), _load(after.get("port_types"), {})
    if bt != at:
        for port in sorted(set(bt) | set(at), key=_port_sort):
            if (bt.get(port) or "rj45") != (at.get(port) or "rj45"):
                changes.append({"field": _s("Тип порта {port}", port=port), "before": PORT_TYPES.get(bt.get(port) or "rj45", bt.get(port)),
                                "after": PORT_TYPES.get(at.get(port) or "rj45", at.get(port))})
        revert["port_types"] = before.get("port_types")
    btr, atr = _load(before.get("trunk_ports"), {}), _load(after.get("trunk_ports"), {})
    if {k for k, v in btr.items() if v} != {k for k, v in atr.items() if v}:
        for port in sorted(set(btr) | set(atr), key=_port_sort):
            if bool(btr.get(port)) != bool(atr.get(port)):
                changes.append({"field": _s("Транк на порту {port}", port=port), "before": _s("да") if btr.get(port) else _s("нет"),
                                "after": _s("да") if atr.get(port) else _s("нет")})
        revert["trunk_ports"] = before.get("trunk_ports")

    # Патч-панели
    bp = {str(p.get("id")): p for p in _load(before.get("patch_panels"), []) if isinstance(p, dict)}
    ap = {str(p.get("id")): p for p in _load(after.get("patch_panels"), []) if isinstance(p, dict)}
    if bp != ap:
        describe = lambda p: f"{p.get('name')}, " + _ns(p.get('ports') or 0, "{n} порт", "{n} порта", "{n} портов")
        for pid in sorted(set(bp) | set(ap), key=_port_sort):
            b, a = bp.get(pid), ap.get(pid)
            if b != a:
                changes.append({"field": _s("Патч-панель «{name}»", name=(a or b).get('name')),
                                "before": describe(b) if b else "—", "after": describe(a) if a else _s("удалена")})
        revert["patch_panels"] = before.get("patch_panels")
    return changes, revert


def summarize(changes, limit=3):
    if not changes:
        return _s("без изменений")
    names = [c["field"] for c in changes[:limit]]
    rest = len(changes) - limit
    return ", ".join(names) + (_s(" и ещё {rest}", rest=rest) if rest > 0 else "")


def entries(db, switch_id=None, action=None, limit=50, before_id=None):
    where, params = [], []
    if switch_id:
        where.append("switch_id = ?"); params.append(switch_id)
    if action:
        where.append("action = ?"); params.append(action)
    if before_id:
        where.append("id < ?"); params.append(before_id)
    sql = "SELECT id, time, actor, switch_id, switch_name, action, summary, details, revert IS NOT NULL, reverted_by FROM audit_log"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    with sqlite3.connect(db) as conn:
        rows = conn.execute(sql, params + [limit]).fetchall()
    return [{
        "id": r[0], "time": r[1], "actor": r[2] or "", "switch_id": r[3], "switch_name": r[4] or "",
        "action": r[5], "action_label": _(ACTIONS[r[5]]) if r[5] in ACTIONS else r[5], "summary": r[6] or "",
        "changes": _load(r[7], {}).get("changes", []),
        "revertible": bool(r[8]) and r[5] in ("update", "delete", "revert") and not r[9],
        "reverted_by": r[9],
    } for r in rows]


def get_revert(db, entry_id):
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT action, switch_id, switch_name, revert, reverted_by FROM audit_log WHERE id=?",
                           (entry_id,)).fetchone()
    if not row:
        return None
    return {"action": row[0], "switch_id": row[1], "switch_name": row[2],
            "revert": _load(row[3], {}), "reverted_by": row[4]}


def mark_reverted(db, entry_id, by_id):
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE audit_log SET reverted_by=? WHERE id=?", (by_id, entry_id))
        conn.commit()
