from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, Response, session, abort, g
from flask import has_request_context
import secrets
import sqlite3
import json
import logging
import os
import re
import subprocess
import threading
import concurrent.futures
from datetime import datetime, timedelta

import config

# Настройки запуска (файл switchmap.conf) читаются до всего остального: от них зависят пути и cookie
CONFIG_FILE = config.load()
DATA_DIR = config.data_dir()

import i18n
from i18n import N_, _, _n, _ns, _s
import audit
import discovery
import helpdocs
import maintenance
import netbox
import notify
import security
import updates
from xlsx import Sheet, write_xlsx, write_csv

log = logging.getLogger("switchmap")
app = Flask(__name__, root_path=config.resource_dir())
APP_VERSION = config.version()
DB = os.path.join(DATA_DIR, "switches.db")

# Секреты (ключ сессий и ключ шифрования паролей SNMPv3) — в файле switchmap.secret рядом с базой
_SECRETS = security.load_secrets(DB)
SECRET_BOX = security.SecretBox(_SECRETS["fernet"])
app.secret_key = _SECRETS["flask"]
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # За HTTPS (обратный прокси) включите SWITCHMAP_HTTPS=1 — cookie будет передаваться только по HTTPS
    SESSION_COOKIE_SECURE=os.environ.get("SWITCHMAP_HTTPS") == "1",
    SESSION_COOKIE_NAME="switchmap_session",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    MAX_CONTENT_LENGTH=512 * 1024 * 1024,  # загрузка резервной копии
)
SESSION_IDLE_HOURS = 12  # без «запомнить меня» сессия истекает через 12 часов бездействия

# За обратным прокси (Caddy, nginx, IIS) все запросы приходят с 127.0.0.1. SWITCHMAP_PROXY=1 — брать адрес
# клиента и схему из заголовков X-Forwarded-For/-Proto (для журнала и защиты от подбора пароля).
# Включайте, только если SwitchMap доступен лишь через прокси (SWITCHMAP_HOST=127.0.0.1): иначе адрес подделывается.
if os.environ.get("SWITCHMAP_PROXY") == "1":
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


# ─────────────────────────────────────────
# ДОСТУП: вход, роли, CSRF, защитные заголовки
# ─────────────────────────────────────────

PUBLIC_PATHS = {"/login", "/setup", "/favicon.ico", "/api/language"}
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# Что можно наблюдателю из изменяющих запросов: опрос и проверки, отметка событий, свой пароль, выход
VIEWER_WRITE_PREFIXES = ("/logout", "/api/port_events/mark_read", "/api/poll_snmp/", "/api/snmp_test/",
                         "/api/refresh_devices/", "/api/status_bulk", "/api/account/password")
# Только для администратора даже на чтение: пользователи и скачивание копий базы
ADMIN_GET_PREFIXES = ("/users", "/api/users", "/api/backups/", "/notifications", "/api/notify",
                      "/discover", "/api/discovery", "/api/netbox", "/add", "/api/update")
login_throttle = security.LoginThrottle()


def current_user():
    from flask import g, has_request_context
    return getattr(g, "user", None) if has_request_context() else None


def current_actor():
    """Для журнала: «имя · IP» (или только IP, если вход не выполнен)."""
    from flask import has_request_context
    if not has_request_context():
        return _s("система")
    user, ip = current_user(), request.remote_addr
    return f"{user['username']} · {ip}" if user else ip


def _wants_json():
    return request.path.startswith(("/api/", "/export/"))


def _deny(code, message):
    if _wants_json() or request.is_json:
        return jsonify({"ok": False, "error": message}), code
    return render_template("error.html", code=code, message=message), code


LANG_COOKIE = "switchmap_lang"


def request_language():
    """Язык до входа: выбранный ранее (cookie) → язык браузера, то есть системы → английский
    (браузер не сообщил язык вовсе — язык сервера). После входа его перекрывает язык из профиля, если он выбран."""
    chosen = i18n.normalize(request.cookies.get(LANG_COOKIE))
    if chosen:
        return chosen
    header = request.headers.get("Accept-Language")
    if not header:
        return i18n.server_language()
    return i18n.negotiate(header) or i18n.FALLBACK


@app.before_request
def access_control():
    from flask import g
    import time
    g.user = None
    path = request.path
    if path.startswith("/static/"):
        return None
    g.lang = request_language()
    if "csrf" not in session:
        session["csrf"] = security.new_csrf_token()

    uid = session.get("uid")
    if uid:
        user = security.get_user(DB, uid)
        now = time.time()
        idle_expired = not session.get("remember") and now - session.get("seen", now) > SESSION_IDLE_HOURS * 3600
        # Сессия недействительна, если пользователя удалили/заблокировали или сменили ему пароль
        if not user or user["disabled"] or idle_expired or session.get("pv") != user["session_version"]:
            for k in ("uid", "pv", "remember", "seen"):
                session.pop(k, None)
        else:
            g.user = user
            if user.get("language"):
                g.lang = user["language"]
            if now - session.get("seen", 0) > 60:
                session["seen"] = now

    if request.method in MUTATING:
        token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        if not security.csrf_matches(session.get("csrf"), token):
            return _deny(400, _("Сессия устарела — обновите страницу и повторите действие"))

    if path in PUBLIC_PATHS:
        return None
    if not g.user:
        if security.count_users(DB) == 0:
            return _deny(401, _("Требуется настройка")) if _wants_json() else redirect(url_for("setup"))
        if _wants_json():
            return jsonify({"ok": False, "error": _("Требуется вход")}), 401
        nxt = request.full_path if request.query_string else path
        return redirect(url_for("login", next=nxt))
    if g.user["role"] != "admin":
        if request.method in MUTATING and not path.startswith(VIEWER_WRITE_PREFIXES):
            return _deny(403, _("Недостаточно прав: действие доступно только администратору"))
        if request.method == "GET" and path.startswith(ADMIN_GET_PREFIXES):
            return _deny(403, _("Недостаточно прав: раздел доступен только администратору"))
    return None


# Сторонние библиотеки лежат в static/vendor (интернет браузеру не нужен): Chart.js 4.4.0, d3 7.9.0,
# pdfmake 0.2.7. Контрольные суммы (SRI) — те же, что у официальных файлов на CDN: изменённый файл
# браузер не выполнит. Шаблоны берут адрес и хэш отсюда (vendor_script).
VENDOR_SCRIPTS = {
    "chartjs": ("chart.umd.min.js", "sha384-e6nUZLBkQ86NJ6TVVKAeSaK8jWa3NhkYWZFomE39AvDbQWeie9PlQqM3pmYW5d1g"),
    "d3": ("d3.min.js", "sha384-CjloA8y00+1SDAUkjs099PVfnY2KmDC2BZnws9kh8D/lX1s46w6EPhpXdqMfjK6i"),
    "pdfmake": ("pdfmake.min.js", "sha384-VFQrHzqBh5qiJIU0uGU5CIW3+OWpdGGJM9LBnGbuIH2mkICcFZ7lPd/AAtI7SNf7"),
    "pdfmake_fonts": ("vfs_fonts.js", "sha384-/RlQG9uf0M2vcTw3CX7fbqgbj/h8wKxw7C3zu9/GxcBPRKOEcESxaxufwRXqzq6n"),
}


def vendor_scripts():
    """{имя: (адрес, integrity)} для шаблонов."""
    return {k: (url_for("static", filename="vendor/" + f), h) for k, (f, h) in VENDOR_SCRIPTS.items()}


def csp_nonce():
    """Одноразовый ключ страницы: выполняются только встроенные <script nonce="…"> этого ответа."""
    if "csp_nonce" not in g:
        g.csp_nonce = secrets.token_urlsafe(18)
    return g.csp_nonce


def build_csp(nonce=None):
    sources = ["'self'"] + ([f"'nonce-{nonce}'"] if nonce else [])
    return ("default-src 'self'; "
            f"script-src {' '.join(sources)}; "
            # Обработчики в атрибутах (onclick="…") и ссылки javascript: запрещены полностью
            "script-src-attr 'none'; "
            # Встроенные стили оставлены: выполнить код через style браузеры не позволяют
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
            "frame-ancestors 'none'; form-action 'self'; base-uri 'self'; object-src 'none'")


def _asset_version():
    """Метка для ссылок на app.js / ui.css / i18n.js: меняется вместе с файлами — после обновления браузер
    не возьмёт старые скрипты из кэша."""
    import hashlib
    h = hashlib.sha256()
    for name in ("app.js", "ui.css", "i18n.js"):
        try:
            with open(os.path.join(app.static_folder, name), "rb") as f:
                h.update(f.read())
        except OSError:
            pass
    return h.hexdigest()[:10]


ASSET_VERSION = _asset_version()


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Content-Security-Policy", build_csp(g.get("csp_nonce")))
    if not request.path.startswith("/static/"):
        # Страницы и API с данными сети не кэшируются (в том числе после выхода)
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.context_processor
def inject_user():
    user = current_user()
    lang = i18n.current_language()
    is_admin = bool(user and user["role"] == "admin")
    return {"current_user": user, "is_admin": is_admin,
            "update_info": updates.status(DB, APP_VERSION) if is_admin else None,
            "csrf_token": session.get("csrf", ""), "csp_nonce": csp_nonce(), "vendor_script": vendor_scripts(),
            "app_version": APP_VERSION, "asset_v": ASSET_VERSION, "lang": lang, "html_lang": i18n.HTML_LANG.get(lang, lang),
            "languages": i18n.LANGUAGES, "user_language": (user or {}).get("language", ""),
            "browser_lang": (i18n.negotiate(request.headers.get("Accept-Language")) or i18n.FALLBACK)
                            if has_request_context() else i18n.FALLBACK,
            "server_system_lang": i18n.system_language(),
            "js_i18n": {"lang": lang, "messages": i18n.js_catalog(lang, _JS_KEYS)}}


_JS_KEYS = i18n.js_keys()  # строки t("…") из скриптов: их переводы передаются на страницу
app.jinja_env.globals.update(_=i18n.jinja_gettext, _n=i18n.jinja_ngettext)


@app.route("/api/language", methods=["POST"])
def api_language():
    """Выбор языка: у вошедшего — в профиле, до входа — в cookie. "" — как в системе."""
    data = request.get_json(silent=True) or {}
    lang = data.get("language") or ""
    if lang and lang not in i18n.LANGUAGES:
        return jsonify({"ok": False, "error": _("Неизвестный язык")}), 400
    user = current_user()
    if user:
        security.set_language(DB, user["id"], lang)
    resp = jsonify({"ok": True, "language": lang})
    if lang:
        resp.set_cookie(LANG_COOKIE, lang, max_age=365 * 86400, samesite="Lax", httponly=True,
                        secure=app.config["SESSION_COOKIE_SECURE"])
    else:
        resp.delete_cookie(LANG_COOKIE)
    return resp


def _safe_next(target):
    """Только относительные адреса внутри приложения (защита от открытого редиректа)."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return url_for("index")


def _start_session(user, remember):
    import time
    session.clear()  # новая сессия при входе — защита от фиксации сессии
    session["uid"] = user["id"]
    session["pv"] = user["session_version"]
    session["remember"] = bool(remember)
    session["seen"] = time.time()
    session["csrf"] = security.new_csrf_token()
    session.permanent = bool(remember)


@app.route("/login", methods=["GET", "POST"])
def login():
    if security.count_users(DB) == 0:
        return redirect(url_for("setup"))
    if current_user():
        return redirect(_safe_next(request.args.get("next")))
    error, username = None, ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        ip = request.remote_addr
        wait = login_throttle.locked_for(ip, username)
        if wait:
            error = _("Слишком много неудачных попыток. Повторите через {wait} мин.", wait=wait // 60 + 1)
        else:
            user = security.authenticate(DB, username, request.form.get("password"))
            if user:
                login_throttle.success(ip, username)
                _start_session(user, request.form.get("remember"))
                return redirect(_safe_next(request.form.get("next")))
            locked = login_throttle.fail(ip, username)
            audit.log(DB, "login_failed", actor=ip, summary=_s("Пользователь «{username}»", username=username[:64])
                      + (_s(" — вход заблокирован на 5 минут") if locked else ""))
            error = _("Неверное имя пользователя или пароль") + (_(". Вход временно заблокирован на 5 минут.") if locked else "")
    return render_template("login.html", error=error, username=username,
                           next=request.values.get("next", "")), (401 if error else 200)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/setup", methods=["GET", "POST"])
def setup():
    """Первый запуск: создание администратора. Доступно, только пока нет ни одного пользователя."""
    if security.count_users(DB) > 0:
        return redirect(url_for("login"))
    error, username = None, request.form.get("username", "admin")
    if request.method == "POST":
        if request.form.get("password") != request.form.get("password2"):
            error = _("Пароли не совпадают")
        else:
            uid, error = security.create_user(DB, username, request.form.get("password"), "admin")
            if uid:
                user = security.get_user(DB, uid)
                _start_session(user, False)
                audit.log(DB, "user_create", actor=current_actor() or request.remote_addr,
                          summary=_s("Первый администратор «{username}»", username=user['username']))
                return redirect(url_for("index"))
    return render_template("login.html", setup=True, error=error, username=username), (400 if error else 200)


@app.route("/users")
def users_view():
    return render_template("users.html", roles={k: _(v) for k, v in security.ROLES.items()})


@app.route("/api/users")
def api_users():
    return jsonify([security.public(u) for u in security.list_users(DB)])


@app.route("/api/users", methods=["POST"])
def api_user_create():
    data = request.json or {}
    uid, error = security.create_user(DB, data.get("username"), data.get("password"), data.get("role", "viewer"))
    if error:
        return jsonify({"ok": False, "error": error}), 400
    user = security.get_user(DB, uid)
    audit.log(DB, "user_create", actor=current_actor(), summary=_s("«{username}», роль: {role_label}", username=user['username'], role_label=user['role_label']))
    return jsonify({"ok": True, "user": security.public(user)})


@app.route("/api/users/<int:user_id>", methods=["PATCH"])
def api_user_update(user_id):
    data = request.json or {}
    me = current_user()
    if user_id == me["id"] and (data.get("disabled") or data.get("role", "admin") != "admin"):
        return jsonify({"ok": False, "error": _("Нельзя понизить или заблокировать самого себя")}), 400
    before = security.get_user(DB, user_id)
    error = security.update_user(DB, user_id, role=data.get("role"), disabled=data.get("disabled"))
    if error:
        return jsonify({"ok": False, "error": error}), 400
    after = security.get_user(DB, user_id)
    changes = []
    if before["role"] != after["role"]:
        changes.append({"field": _s("Роль"), "before": _s(security.ROLES[before["role"]]),
                        "after": _s(security.ROLES[after["role"]])})
    if before["disabled"] != after["disabled"]:
        changes.append({"field": _s("Доступ"), "before": _s("заблокирован") if before["disabled"] else _s("активен"),
                        "after": _s("заблокирован") if after["disabled"] else _s("активен")})
    if changes:
        audit.log(DB, "user_update", actor=current_actor(), summary=f"«{after['username']}»: " + audit.summarize(changes),
                  changes=changes)
    return jsonify({"ok": True, "user": security.public(after)})


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def api_user_delete(user_id):
    if user_id == current_user()["id"]:
        return jsonify({"ok": False, "error": _("Нельзя удалить самого себя")}), 400
    user = security.get_user(DB, user_id)
    error = security.delete_user(DB, user_id)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    audit.log(DB, "user_delete", actor=current_actor(), summary=f"«{user['username']}»")
    return jsonify({"ok": True})


@app.route("/api/users/<int:user_id>/password", methods=["POST"])
def api_user_password(user_id):
    """Администратор задаёт пароль пользователю (все его сессии завершаются)."""
    error = security.set_password(DB, user_id, (request.json or {}).get("password"))
    if error:
        return jsonify({"ok": False, "error": error}), 400
    user = security.get_user(DB, user_id)
    if user_id == current_user()["id"]:
        session["pv"] = user["session_version"]
    audit.log(DB, "password_change", actor=current_actor(), summary=_s("Пароль пользователя «{username}» задан администратором", username=user['username']))
    return jsonify({"ok": True})


@app.route("/api/account/password", methods=["POST"])
def api_account_password():
    """Смена своего пароля: нужен текущий пароль. Другие сессии этого пользователя завершаются."""
    data = request.json or {}
    me = current_user()
    if not security.authenticate(DB, me["username"], data.get("current")):
        return jsonify({"ok": False, "error": _("Текущий пароль указан неверно")}), 400
    error = security.set_password(DB, me["id"], data.get("password"))
    if error:
        return jsonify({"ok": False, "error": error}), 400
    session["pv"] = security.get_user(DB, me["id"])["session_version"]
    audit.log(DB, "password_change", actor=current_actor(), summary=_s("«{username}» сменил свой пароль", username=me['username']))
    return jsonify({"ok": True})


# ─────────────────────────────────────────
# DB INIT & MIGRATION
# ─────────────────────────────────────────

def init_db():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS switches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            ports INTEGER,
            patch_panels TEXT,
            patch_position TEXT,
            connections TEXT,
            ip_address TEXT,
            snmp_community TEXT DEFAULT 'public',
            port_types TEXT DEFAULT '{}',
            trunk_ports TEXT DEFAULT '{}',
            switch_layout TEXT DEFAULT 'single',
            port_vlans TEXT DEFAULT '{}',
            vlan_colors TEXT DEFAULT '{}',
            port_status_snapshot TEXT DEFAULT '{}',
            cpu_usage REAL DEFAULT 0,
            ram_usage REAL DEFAULT 0,
            temperature REAL DEFAULT 0,
            last_poll_time TEXT
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            switch_id INTEGER,
            port_number INTEGER,
            ip TEXT,
            mac TEXT,
            hostname TEXT,
            is_online INTEGER DEFAULT 0,
            last_seen TEXT,
            notes TEXT,
            FOREIGN KEY (switch_id) REFERENCES switches(id)
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS port_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            switch_id INTEGER,
            ifindex TEXT,
            port_name TEXT,
            event_type TEXT,
            event_time TEXT,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (switch_id) REFERENCES switches(id)
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        create_stats_tables(c)
        conn.commit()


def create_stats_tables(c):
    """Таблицы SNMP-статистики. Вызывается и для новой, и для существующей базы."""
    c.execute("""
        CREATE TABLE IF NOT EXISTS port_traffic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            switch_id INTEGER,
            ifindex TEXT,
            timestamp TEXT,
            bytes_in INTEGER,
            bytes_out INTEGER,
            packets_in INTEGER,
            packets_out INTEGER,
            errors_in INTEGER,
            errors_out INTEGER,
            counter_bits INTEGER DEFAULT 32,
            FOREIGN KEY (switch_id) REFERENCES switches(id)
        )
        """)
    # Разрядность счётчиков байт (32 — ifInOctets, 64 — ifHCInOctets) нужна,
    # чтобы правильно учитывать переполнение при расчёте скорости
    c.execute("PRAGMA table_info(port_traffic)")
    if "counter_bits" not in [col[1] for col in c.fetchall()]:
        c.execute("ALTER TABLE port_traffic ADD COLUMN counter_bits INTEGER DEFAULT 32")
    c.execute("""
        CREATE TABLE IF NOT EXISTS switch_health (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            switch_id INTEGER,
            timestamp TEXT,
            cpu_usage REAL,
            ram_usage REAL,
            temperature REAL,
            FOREIGN KEY (switch_id) REFERENCES switches(id)
        )
        """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS poe_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            switch_id INTEGER,
            ifindex TEXT,
            timestamp TEXT,
            poe_enabled INTEGER,
            power_allocated REAL,
            power_consumed REAL,
            power_class INTEGER,
            FOREIGN KEY (switch_id) REFERENCES switches(id)
        )
        """)
    # Индексы под выборки истории (WHERE switch_id [AND ifindex] ORDER BY id DESC)
    c.execute("CREATE INDEX IF NOT EXISTS idx_port_traffic_switch_port ON port_traffic (switch_id, ifindex, id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_switch_health_switch ON switch_health (switch_id, id)")

    # Таблица MAC-адресов, увиденных при опросах, — для поиска «где подключено устройство»
    c.execute("""
        CREATE TABLE IF NOT EXISTS mac_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            switch_id INTEGER,
            mac TEXT,
            ifindex TEXT,
            port_number INTEGER,
            port_name TEXT,
            vlan TEXT,
            ip TEXT,
            hostname TEXT,
            port_mac_count INTEGER,
            first_seen TEXT,
            last_seen TEXT,
            UNIQUE (switch_id, mac)
        )
        """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_mac_table_mac ON mac_table (mac)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_mac_table_ip ON mac_table (ip)")

    # SNMPv3 и состояние оповещений по коммутатору; детали и номер порта у событий
    _add_column(c, "switches", "snmp_version", "TEXT DEFAULT '2c'")
    _add_column(c, "switches", "snmp_v3_user", "TEXT")
    _add_column(c, "switches", "snmp_v3_auth_proto", "TEXT DEFAULT 'none'")
    _add_column(c, "switches", "snmp_v3_auth_key", "TEXT")
    _add_column(c, "switches", "snmp_v3_priv_proto", "TEXT DEFAULT 'none'")
    _add_column(c, "switches", "snmp_v3_priv_key", "TEXT")
    _add_column(c, "switches", "snmp_v3_context", "TEXT")
    _add_column(c, "switches", "alert_state", "TEXT DEFAULT '{}'")
    _add_column(c, "switches", "model", "TEXT")          # производитель и модель (автообнаружение, NetBox)
    _add_column(c, "switches", "netbox_id", "INTEGER")   # связь с устройством NetBox
    _add_column(c, "port_events", "details", "TEXT")
    _add_column(c, "port_events", "port_number", "INTEGER")

    # Скорость за интервал сохраняется при опросе — для свёртки истории и графиков за период
    _add_column(c, "port_traffic", "in_mbps", "REAL")
    _add_column(c, "port_traffic", "out_mbps", "REAL")
    _add_column(c, "port_traffic", "interval_sec", "REAL")
    _add_column(c, "port_traffic", "errors_delta", "INTEGER")
    _add_column(c, "port_traffic", "rate_done", "INTEGER")
    maintenance.ensure_tables(c)
    audit.ensure_table(c)
    security.ensure_table(c)
    notify.ensure_table(c)


def _add_column(c, table, column, decl):
    c.execute(f"PRAGMA table_info({table})")
    if column not in [col[1] for col in c.fetchall()]:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def migrate_db():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("PRAGMA table_info(switches)")
        columns = [col[1] for col in c.fetchall()]

        if 'patch_panels' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN patch_panels TEXT")
            # Проверяем, есть ли колонка patch_ports в старых схемах
            c.execute("PRAGMA table_info(switches)")
            all_cols = [col[1] for col in c.fetchall()]
            has_patch_ports = 'patch_ports' in all_cols
            if has_patch_ports:
                c.execute("SELECT id, patch_ports, patch_position FROM switches")
                rows = c.fetchall()
                for row in rows:
                    switch_id, patch_ports, patch_position = row
                    patch_panels_data = [{"id": 1, "name": "Patch Panel 1",
                        "ports": patch_ports if patch_ports else 24,
                        "position": patch_position if patch_position else "below"}]
                    c.execute("UPDATE switches SET patch_panels = ? WHERE id = ?",
                              (json.dumps(patch_panels_data), switch_id))
            else:
                c.execute("SELECT id, patch_position FROM switches")
                rows = c.fetchall()
                for row in rows:
                    switch_id, patch_position = row
                    patch_panels_data = [{"id": 1, "name": "Patch Panel 1",
                        "ports": 24,
                        "position": patch_position if patch_position else "below"}]
                    c.execute("UPDATE switches SET patch_panels = ? WHERE id = ?",
                              (json.dumps(patch_panels_data), switch_id))
            conn.commit()

        if 'ip_address' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN ip_address TEXT")
            conn.commit()

        if 'snmp_community' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN snmp_community TEXT DEFAULT 'public'")
            conn.commit()

        if 'port_types' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN port_types TEXT DEFAULT '{}'")
            conn.commit()

        if 'trunk_ports' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN trunk_ports TEXT DEFAULT '{}'")
            conn.commit()

        if 'switch_layout' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN switch_layout TEXT DEFAULT 'single'")
            # Миграция: в старых схемах layout хранился в patch_position
            c.execute("SELECT id, patch_position FROM switches")
            rows = c.fetchall()
            for row in rows:
                switch_id, patch_position = row
                if patch_position in ('single', 'dual'):
                    c.execute("UPDATE switches SET switch_layout=? WHERE id=?",
                              (patch_position, switch_id))
            conn.commit()

        if 'port_vlans' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN port_vlans TEXT DEFAULT '{}'")
            conn.commit()

        if 'vlan_colors' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN vlan_colors TEXT DEFAULT '{}'")
            conn.commit()

        if 'port_status_snapshot' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN port_status_snapshot TEXT DEFAULT '{}'")
            conn.commit()

        if 'cpu_usage' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN cpu_usage REAL DEFAULT 0")
            conn.commit()

        if 'ram_usage' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN ram_usage REAL DEFAULT 0")
            conn.commit()

        if 'temperature' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN temperature REAL DEFAULT 0")
            conn.commit()

        if 'last_poll_time' not in columns:
            c.execute("ALTER TABLE switches ADD COLUMN last_poll_time TEXT")
            conn.commit()

        c.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            switch_id INTEGER,
            port_number INTEGER,
            ip TEXT,
            mac TEXT,
            hostname TEXT,
            is_online INTEGER DEFAULT 0,
            last_seen TEXT,
            notes TEXT,
            FOREIGN KEY (switch_id) REFERENCES switches(id)
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS port_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            switch_id INTEGER,
            ifindex TEXT,
            port_name TEXT,
            event_type TEXT,
            event_time TEXT,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (switch_id) REFERENCES switches(id)
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        # Таблицы статистики появились позже — в старых базах их нет
        create_stats_tables(c)
        conn.commit()


# ─────────────────────────────────────────
# PING & SNMP HELPERS
# ─────────────────────────────────────────

_PING_TARGET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:\-]{0,252}$")  # IP или имя; не «-ключ» команды ping


def ping_host(ip, timeout=1):
    if not ip:
        return None
    if not _PING_TARGET.match(str(ip)):
        return False
    try:
        # Кросс-платформенная команда ping
        import platform
        param = "-n" if platform.system().lower() == "windows" else "-c"
        timeout_param = "-w" if platform.system().lower() == "windows" else "-W"
        timeout_value = str(timeout * 1000) if platform.system().lower() == "windows" else str(timeout)
        
        result = subprocess.run(
            ["ping", param, "1", timeout_param, timeout_value, ip],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout + 1)
        return result.returncode == 0
    except Exception:
        return False


class SnmpAuth:
    """Учётные данные SNMP коммутатора: v2c (community) или v3 (USM).
    Во все функции опроса передаётся вместо строки community; строка тоже
    принимается и означает v2c — так старый код продолжает работать."""

    AUTH_PROTOCOLS = ("none", "MD5", "SHA", "SHA224", "SHA256", "SHA384", "SHA512")
    PRIV_PROTOCOLS = ("none", "DES", "3DES", "AES128", "AES192", "AES256")

    def __init__(self, version="2c", community="public", user="",
                 auth_proto="none", auth_key="", priv_proto="none", priv_key="", context=""):
        self.version = "3" if str(version) == "3" else "2c"
        # Контекст SNMPv3: обычно пустой; нужен, например, Cisco для данных по VLAN (vlan-10)
        self.context = (context or "") if self.version == "3" else ""
        self.community = community or "public"
        self.user = user or ""
        self.auth_proto = auth_proto if auth_proto in self.AUTH_PROTOCOLS else "none"
        self.auth_key = auth_key or ""
        self.priv_proto = priv_proto if priv_proto in self.PRIV_PROTOCOLS else "none"
        self.priv_key = priv_key or ""

    @classmethod
    def from_row(cls, row):
        """row — sqlite3.Row или dict со столбцами таблицы switches."""
        get = (lambda k: row[k] if k in row.keys() else None) if hasattr(row, "keys") else row.get
        # Пароли SNMPv3 хранятся зашифрованными (enc:v1:…) — расшифровываем только для опроса
        return cls(get("snmp_version") or "2c", get("snmp_community") or "public",
                   get("snmp_v3_user"), get("snmp_v3_auth_proto") or "none", SECRET_BOX.decrypt(get("snmp_v3_auth_key")),
                   get("snmp_v3_priv_proto") or "none", SECRET_BOX.decrypt(get("snmp_v3_priv_key")), get("snmp_v3_context"))

    def validate(self):
        """Текст ошибки настройки или None. Требования RFC 3414: ключи от 8 символов,
        шифрование без аутентификации (noAuthPriv) не допускается."""
        if self.version != "3":
            return None
        if not self.user:
            return _("SNMPv3: не указано имя пользователя")
        if self.auth_proto == "none" and self.priv_proto != "none":
            return _("SNMPv3: шифрование нельзя включить без аутентификации")
        if self.auth_proto != "none" and len(self.auth_key) < 8:
            return _("SNMPv3: пароль аутентификации должен быть не короче 8 символов")
        if self.priv_proto != "none" and len(self.priv_key) < 8:
            return _("SNMPv3: пароль шифрования должен быть не короче 8 символов")
        return None

    def to_pysnmp(self):
        import pysnmp.hlapi.v3arch.asyncio as h
        if self.version != "3":
            return h.CommunityData(self.community, mpModel=1)
        auth = {"none": h.usmNoAuthProtocol, "MD5": h.usmHMACMD5AuthProtocol, "SHA": h.usmHMACSHAAuthProtocol,
                "SHA224": h.usmHMAC128SHA224AuthProtocol, "SHA256": h.usmHMAC192SHA256AuthProtocol,
                "SHA384": h.usmHMAC256SHA384AuthProtocol, "SHA512": h.usmHMAC384SHA512AuthProtocol}
        priv = {"none": h.usmNoPrivProtocol, "DES": h.usmDESPrivProtocol, "3DES": h.usm3DESEDEPrivProtocol,
                "AES128": h.usmAesCfb128Protocol, "AES192": h.usmAesCfb192Protocol, "AES256": h.usmAesCfb256Protocol}
        return h.UsmUserData(
            self.user,
            authKey=self.auth_key if self.auth_proto != "none" else None,
            privKey=self.priv_key if self.priv_proto != "none" else None,
            authProtocol=auth[self.auth_proto], privProtocol=priv[self.priv_proto])

    def describe(self):
        if self.version != "3":
            return "SNMPv2c"
        level = "authPriv" if self.priv_proto != "none" else "authNoPriv" if self.auth_proto != "none" else "noAuthNoPriv"
        return f"SNMPv3 {level}"


def _as_snmp_auth(auth):
    return auth if isinstance(auth, SnmpAuth) else SnmpAuth("2c", auth or "public")


# Понятные сообщения для частых ошибок pysnmp
_SNMP_ERROR_HINTS = (
    ("timeout", N_("коммутатор не ответил (проверьте IP, доступность UDP 161, версию SNMP и community/пользователя)")),
    ("before timeout", N_("коммутатор не ответил (проверьте IP, доступность UDP 161, версию SNMP и community/пользователя)")),
    ("unknown usm user", N_("неизвестный пользователь SNMPv3")),
    ("unknownusername", N_("неизвестный пользователь SNMPv3")),
    ("pdu digest", N_("неверный пароль аутентификации SNMPv3 или протокол аутентификации")),
    ("wrongdigest", N_("неверный пароль аутентификации SNMPv3 или протокол аутентификации")),
    ("ciphertext is broken", N_("неверный пароль шифрования SNMPv3 или протокол шифрования")),
    ("decryption", N_("неверный пароль шифрования SNMPv3 или протокол шифрования")),
    ("ciphering services not available", N_("для SNMPv3 с шифрованием установите пакет cryptography: pip install cryptography")),
    ("unsupported security level", N_("уровень безопасности SNMPv3 не поддерживается коммутатором для этого пользователя")),
    ("unsupportedseclevel", N_("уровень безопасности SNMPv3 не поддерживается коммутатором для этого пользователя")),
)


def _humanize_snmp_error(text):
    low = str(text).lower()
    for needle, hint in _SNMP_ERROR_HINTS:
        if needle in low:
            return f"{_(hint)} ({text})"
    return str(text)


# SNMP-запросы выполняются в постоянных рабочих потоках: у каждого свой цикл asyncio и свой SnmpEngine.
# Раньше на каждый запрос создавались новый поток и новый движок (~0,1 с), а коммутатор — это ~24 запроса.
SNMP_WORKERS = max(4, int(os.environ.get("SWITCHMAP_SNMP_WORKERS", "32") or 32))
SNMP_BULK_REPETITIONS = 25   # строк таблицы за один запрос GETBULK
_snmp_pool = None
_snmp_pool_lock = threading.Lock()
_snmp_local = threading.local()


def _snmp_executor():
    global _snmp_pool
    with _snmp_pool_lock:
        if _snmp_pool is None:
            _snmp_pool = concurrent.futures.ThreadPoolExecutor(max_workers=SNMP_WORKERS, thread_name_prefix="snmp")
        return _snmp_pool


def _snmp_thread_state():
    """Цикл asyncio и SnmpEngine этого рабочего потока (создаются один раз)."""
    state = getattr(_snmp_local, "state", None)
    if state is None:
        import asyncio
        from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Служебная задача таймеров pysnmp живёт, пока жив движок; при выходе из программы она «уничтожается
        # незавершённой» — это не ошибка, в журнал не пишем
        loop.set_exception_handler(lambda lp, ctx: None if "destroyed but it is pending" in str(ctx.get("message"))
                                   else lp.default_exception_handler(ctx))
        state = _snmp_local.state = (loop, SnmpEngine())
    return state


def snmp_walk_ex(ip, auth, oid, timeout=3):
    """SNMP walk. Возвращает (список (oid, value), текст ошибки или None).
    auth — SnmpAuth или строка community (v2c). Работает с pysnmp 7.x.
    Таблица читается пачками (GETBULK); если устройство пачки не понимает — по одной строке (GETNEXT)."""
    try:
        from pysnmp.hlapi.v3arch.asyncio import (
            UdpTransportTarget, ContextData, ObjectType, ObjectIdentity, walk_cmd, bulk_walk_cmd)
    except ImportError:
        return [], _("pysnmp не установлен. Выполните: pip install pysnmp")

    auth = _as_snmp_auth(auth)

    async def _walk(engine, bulk):
        results, error = [], None
        # lexicographicMode=False: только запрошенная ветка. По умолчанию pysnmp
        # продолжает walk до конца MIB — медленно и с чужими данными в результате.
        walker = None
        try:
            transport = await UdpTransportTarget.create((ip, 161), timeout=timeout, retries=1)
            target = (engine, auth.to_pysnmp(), transport, ContextData(contextName=auth.context))
            walker = (bulk_walk_cmd(*target, 0, SNMP_BULK_REPETITIONS, ObjectType(ObjectIdentity(oid)), lexicographicMode=False)
                      if bulk else walk_cmd(*target, ObjectType(ObjectIdentity(oid)), lexicographicMode=False))
            async for (errorIndication, errorStatus, errorIndex, varBinds) in walker:
                if errorIndication or errorStatus:
                    if not results:
                        error = str(errorIndication or errorStatus.prettyPrint())
                    break
                for varBind in varBinds:
                    results.append((str(varBind[0]), varBind[1]))
        finally:
            if walker is not None:
                await walker.aclose()
        return results, error

    def run_in_worker():
        loop, engine = _snmp_thread_state()
        results, error = loop.run_until_complete(_walk(engine, bulk=True))
        # Пачки не прошли (старая прошивка, ошибка tooBig и т. п.) — повторяем построчно.
        # По таймауту не повторяем: устройство просто не отвечает, ждать вдвое дольше незачем.
        if error and not results and "timeout" not in error.lower() and "no snmp response" not in error.lower():
            results, error = loop.run_until_complete(_walk(engine, bulk=False))
        return results, error

    future = _snmp_executor().submit(run_in_worker)
    try:
        result, error = future.result(timeout=timeout * 4 + 5)
        return result, (_humanize_snmp_error(error) if error else None)
    except concurrent.futures.TimeoutError:
        log.warning(_s("SNMP {ip}: нет ответа ({oid})", ip=ip, oid=oid))
        return [], _humanize_snmp_error("timeout")
    except Exception as e:
        log.warning("SNMP %s: %s", ip, e)
        return [], _humanize_snmp_error(e)

def snmp_walk(ip, auth, oid, timeout=3):
    """SNMP walk без текста ошибки: при любой проблеме — пустой список."""
    return snmp_walk_ex(ip, auth, oid, timeout)[0]


_ETHERNET_IF_TYPES = {6, 62, 69, 117}  # ethernetCsmacd, fastEther, fastEtherFX, gigabitEthernet


def _name_numbers(name):
    import re
    return tuple(int(n) for n in re.findall(r"\d+", name or ""))


def map_ifindex_to_port(interfaces, port_count=None):
    """Сопоставляет ifIndex с номером физического порта на схеме (1..N).
    interfaces: {ifindex: {"name": ifName или ifDescr, "type": ifType или None}}.
    1) Если все Ethernet-интерфейсы имеют ifIndex 1..N — номер порта = ifIndex
       (типичные D-Link, TP-Link, HP и т. п.; так приложение работало и раньше).
    2) Иначе нумеруем по порядку: интерфейсы с «/» в имени (Gi1/0/1, ge-0/0/5),
       отсортированные по числам в имени, — так получаются Cisco (ifIndex 10101…)
       и Juniper; служебные Fa0/mgmt без «/» в нумерацию не попадают.
    Возвращает {ifindex: номер порта}."""
    types_known = any(i.get("type") is not None for i in interfaces.values())
    if types_known:
        cand = [idx for idx, i in interfaces.items() if i.get("type") in _ETHERNET_IF_TYPES]
    else:
        cand = list(interfaces)
    if not cand:
        return {}

    def as_int(idx):
        try:
            return int(idx)
        except (TypeError, ValueError):
            return None

    ints = [as_int(i) for i in cand]
    if port_count and all(n is not None and 1 <= n <= port_count for n in ints):
        return {idx: int(idx) for idx in cand}

    slashed = [idx for idx in cand if "/" in (interfaces[idx].get("name") or "")]
    if len(slashed) * 2 >= len(cand):
        ordered = sorted(slashed, key=lambda i: (_name_numbers(interfaces[i].get("name")), as_int(i) or 0))
    else:
        ordered = sorted(cand, key=lambda i: (as_int(i) is None, as_int(i) or 0, str(i)))
    if port_count:
        ordered = ordered[:port_count]
    return {idx: n for n, idx in enumerate(ordered, start=1)}


_hostname_cache = {}  # ip -> (hostname, время)
_HOSTNAME_TTL = 3600


def resolve_hostnames(ips, budget_sec=5):
    """Обратный DNS для списка IP: параллельно, с кэшем на час и общим лимитом времени.
    Раньше имена резолвились по одному, и опрос с сотнями MAC мог идти минутами."""
    import socket
    import time
    now = time.time()
    result, todo = {}, []
    for ip in set(i for i in ips if i):
        cached = _hostname_cache.get(ip)
        if cached and now - cached[1] < _HOSTNAME_TTL:
            result[ip] = cached[0]
        else:
            todo.append(ip)
    if todo:
        def lookup(ip):
            try:
                return ip, socket.gethostbyaddr(ip)[0]
            except Exception:
                return ip, ""
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=min(16, len(todo)))
        futures = [pool.submit(lookup, ip) for ip in todo]
        try:
            for f in concurrent.futures.as_completed(futures, timeout=budget_sec):
                ip, name = f.result()
                result[ip] = name
                _hostname_cache[ip] = (name, now)
        except concurrent.futures.TimeoutError:
            pass  # не успевшие IP останутся без имени до следующего опроса
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    return result


def poll_switch_snmp(ip, community, port_count=None):
    """
    Расширенный SNMP-опрос коммутатора:
    - Статус портов (up/down), номер порта на схеме, описание (ifAlias), скорость
    - Устройства на портах (MAC, IP, hostname)
    - VLAN
    - Трафик портов (bytes/packets in/out, errors)
    - PoE статус
    community — SnmpAuth или строка community (v2c).
    """
    port_status = {}

    # Базовая информация о портах. По первому запросу понимаем, отвечает ли коммутатор.
    ifdescr_data, first_error = snmp_walk_ex(ip, community, "1.3.6.1.2.1.2.2.1.2")  # ifDescr
    if not ifdescr_data:
        return {"error": "SNMP: " + (first_error or _("коммутатор не вернул список интерфейсов"))}
    ifstatus_data = snmp_walk(ip, community, "1.3.6.1.2.1.2.2.1.8")  # ifOperStatus
    ifspeed_data = snmp_walk(ip, community, "1.3.6.1.2.1.2.2.1.5")   # ifSpeed, бит/с (до 4.2 Гбит/с)
    iftype_data = snmp_walk(ip, community, "1.3.6.1.2.1.2.2.1.3")    # ifType
    ifname_data = snmp_walk(ip, community, "1.3.6.1.2.1.31.1.1.1.1")    # ifName (Gi1/0/1)
    ifhighspeed_data = snmp_walk(ip, community, "1.3.6.1.2.1.31.1.1.1.15")  # ifHighSpeed, Мбит/с
    ifalias_data = snmp_walk(ip, community, "1.3.6.1.2.1.31.1.1.1.18")  # ifAlias — описание порта

    # Трафик портов. 64-битные счётчики (IF-MIB ifXTable) предпочтительнее:
    # 32-битный ifInOctets на 1 Гбит/с переполняется примерно за 34 секунды.
    ifhc_in_octets = snmp_walk(ip, community, "1.3.6.1.2.1.31.1.1.1.6")   # ifHCInOctets
    ifhc_out_octets = snmp_walk(ip, community, "1.3.6.1.2.1.31.1.1.1.10") # ifHCOutOctets
    ifin_octets = snmp_walk(ip, community, "1.3.6.1.2.1.2.2.1.10")   # ifInOctets
    ifout_octets = snmp_walk(ip, community, "1.3.6.1.2.1.2.2.1.16")  # ifOutOctets
    ifin_ucast = snmp_walk(ip, community, "1.3.6.1.2.1.2.2.1.11")    # ifInUcastPkts
    ifout_ucast = snmp_walk(ip, community, "1.3.6.1.2.1.2.2.1.17")   # ifOutUcastPkts
    ifin_errors = snmp_walk(ip, community, "1.3.6.1.2.1.2.2.1.14")   # ifInErrors
    ifout_errors = snmp_walk(ip, community, "1.3.6.1.2.1.2.2.1.20")  # ifOutErrors

    # PoE (Power over Ethernet) - RFC 3621, индекс строки: <группа>.<порт>
    poe_admin = snmp_walk(ip, community, "1.3.6.1.2.1.105.1.1.1.1.3")   # pethPsePortAdminEnable: 1=true, 2=false
    poe_status = snmp_walk(ip, community, "1.3.6.1.2.1.105.1.1.1.1.6")  # pethPsePortDetectionStatus
    # В RFC 3621 нет потребления по портам — берём из CISCO-POWER-ETHERNET-EXT-MIB
    # (cpeExtPsePortPwrConsumption, мВт). На других вендорах мощность будет неизвестна.
    poe_consumed = snmp_walk(ip, community, "1.3.6.1.4.1.9.9.402.1.2.1.9")

    port_names = {}
    port_speeds = {}
    port_traffic = {}
    port_poe = {}

    if ifdescr_data:
        for oid_str, val in ifdescr_data:
            idx = oid_str.split(".")[-1]
            port_names[idx] = str(val)

    if ifspeed_data:
        for oid_str, val in ifspeed_data:
            idx = oid_str.split(".")[-1]
            # Скорость в bps, конвертируем в Mbps
            port_speeds[idx] = int(val) / 1_000_000 if val else 0
    # ifSpeed упирается в 4294 Мбит/с, для 10G+ правильное значение только в ifHighSpeed
    for oid_str, val in ifhighspeed_data:
        try:
            if int(val) > 0:
                port_speeds[oid_str.split(".")[-1]] = int(val)
        except (TypeError, ValueError):
            pass

    port_types = {}
    for oid_str, val in iftype_data:
        try:
            port_types[oid_str.split(".")[-1]] = int(val)
        except (TypeError, ValueError):
            pass
    if_names = {oid_str.split(".")[-1]: snmp_value_text(val) for oid_str, val in ifname_data}
    port_aliases = {oid_str.split(".")[-1]: snmp_value_text(val) for oid_str, val in ifalias_data}

    # Собираем статистику трафика
    def build_dict(data):
        result = {}
        if data:
            for oid_str, val in data:
                idx = oid_str.split(".")[-1]
                result[idx] = int(val) if val else 0
        return result

    hc_in_octets = build_dict(ifhc_in_octets)
    hc_out_octets = build_dict(ifhc_out_octets)
    traffic_in_octets = build_dict(ifin_octets)
    traffic_out_octets = build_dict(ifout_octets)
    traffic_in_packets = build_dict(ifin_ucast)
    traffic_out_packets = build_dict(ifout_ucast)
    errors_in = build_dict(ifin_errors)
    errors_out = build_dict(ifout_errors)

    for idx in set(traffic_in_octets) | set(hc_in_octets):
        use_hc = idx in hc_in_octets and idx in hc_out_octets
        port_traffic[idx] = {
            "bytes_in": hc_in_octets[idx] if use_hc else traffic_in_octets.get(idx, 0),
            "bytes_out": hc_out_octets[idx] if use_hc else traffic_out_octets.get(idx, 0),
            "counter_bits": 64 if use_hc else 32,
            "packets_in": traffic_in_packets.get(idx, 0),
            "packets_out": traffic_out_packets.get(idx, 0),
            "errors_in": errors_in.get(idx, 0),
            "errors_out": errors_out.get(idx, 0)
        }

    # PoE данные. Номер порта PoE (последнее число индекса) на большинстве
    # коммутаторов совпадает с ifIndex, но стандарт этого не гарантирует.
    POE_STATES = {1: "disabled", 2: "searching", 3: "delivering", 4: "fault", 5: "test", 6: "fault"}
    if isinstance(poe_status, list) and poe_status:
        admin = {}
        if isinstance(poe_admin, list):
            for oid_str, val in poe_admin:
                admin[oid_str.split(".")[-1]] = (int(val) == 1)

        for oid_str, val in poe_status:
            idx = oid_str.split(".")[-1]
            try:
                status = int(val)
            except (ValueError, TypeError):
                status = 0
            port_poe[idx] = {
                "enabled": admin.get(idx, True),
                "status": status,
                "state": POE_STATES.get(status, "unknown"),
                "power_consumed": None  # Вт; None — коммутатор не сообщает
            }

        if isinstance(poe_consumed, list):
            for oid_str, val in poe_consumed:
                idx = oid_str.split(".")[-1]
                if idx in port_poe:
                    try:
                        port_poe[idx]["power_consumed"] = int(val) / 1000  # мВт → Вт
                    except (ValueError, TypeError):
                        pass

    if ifstatus_data:
        for oid_str, val in ifstatus_data:
            idx = oid_str.split(".")[-1]
            port_status[idx] = {
                "name": port_names.get(idx, f"Port {idx}"),
                "up": int(val) == 1,
                "speed": port_speeds.get(idx, 0),
                "devices": [],
                "traffic": port_traffic.get(idx, {}),
                "poe": port_poe.get(idx)
            }

    port_numbers = map_ifindex_to_port(
        {idx: {"name": if_names.get(idx) or port_names.get(idx), "type": port_types.get(idx)}
         for idx in port_status},
        port_count)

    # Индекс PoE (pethPsePortIndex) у одних коммутаторов совпадает с ifIndex,
    # у других (Cisco: 1.<порт>) — это номер порта. Выбираем то, что подходит.
    if port_poe and not set(port_poe) <= set(port_status):
        by_port = {str(n): idx for idx, n in port_numbers.items()}
        for info in port_status.values():
            info["poe"] = None
        for poe_idx, poe in port_poe.items():
            if poe_idx in by_port:
                port_status[by_port[poe_idx]]["poe"] = poe

    fdb_mac = snmp_walk(ip, community, "1.3.6.1.2.1.17.4.3.1.1")
    fdb_port = snmp_walk(ip, community, "1.3.6.1.2.1.17.4.3.1.2")
    bridge_port_data = snmp_walk(ip, community, "1.3.6.1.2.1.17.1.4.1.2")
    arp_data = snmp_walk(ip, community, "1.3.6.1.2.1.4.22.1.2")

    # VLAN: dot1qPvid (PVID по dot1dBasePort) и dot1qVlanStaticName (имя по VLAN ID).
    # Раньше здесь по ошибке опрашивался 1.0.8802.1.1.2.1.4.1.1.5 — это LLDP chassis ID соседей.
    pvid_data = snmp_walk(ip, community, "1.3.6.1.2.1.17.7.1.4.5.1.1")
    vlan_name_data = snmp_walk(ip, community, "1.3.6.1.2.1.17.7.1.4.3.1.1")

    mac_to_bridge_port = {}
    if fdb_mac and fdb_port:
        port_by_suffix = {}
        for oid_str, val in fdb_port:
            suffix = ".".join(oid_str.split(".")[-6:])
            port_by_suffix[suffix] = int(val)
        for oid_str, val in fdb_mac:
            suffix = ".".join(oid_str.split(".")[-6:])
            mac_bytes = bytes(val)
            mac_str = ":".join(f"{b:02x}" for b in mac_bytes)
            bp = port_by_suffix.get(suffix)
            if bp:
                mac_to_bridge_port[mac_str] = bp
    if not mac_to_bridge_port:
        # Многие коммутаторы с VLAN отдают таблицу MAC только в Q-BRIDGE-MIB:
        # dot1qTpFdbPort, индекс <fdbId>.<6 байт MAC>, значение — bridge port
        for oid_str, val in snmp_walk(ip, community, "1.3.6.1.2.1.17.7.1.2.2.1.2"):
            try:
                octets = [int(x) for x in oid_str.split(".")[-6:]]
                bp = int(val)
            except (TypeError, ValueError):
                continue
            if bp:
                mac_to_bridge_port[":".join(f"{b:02x}" for b in octets)] = bp

    bridge_to_ifindex = {}
    if bridge_port_data:
        for oid_str, val in bridge_port_data:
            bp = int(oid_str.split(".")[-1])
            bridge_to_ifindex[bp] = str(int(val))

    vlan_names = {}
    if vlan_name_data:
        for oid_str, val in vlan_name_data:
            vlan_id = oid_str.split(".")[-1]
            try:
                name = bytes(val).decode("utf-8", errors="replace") if not isinstance(val, str) else val
            except Exception:
                name = str(val)
            vlan_names[vlan_id] = name.strip()

    port_vlan = {}
    if pvid_data:
        for oid_str, val in pvid_data:
            try:
                bp = int(oid_str.split(".")[-1])
                vlan_id = str(int(val))
            except (ValueError, TypeError):
                continue
            ifindex = bridge_to_ifindex.get(bp, str(bp))
            port_vlan[ifindex] = {"id": vlan_id, "name": vlan_names.get(vlan_id, "")}

    ip_by_mac = {}
    if arp_data:
        for oid_str, val in arp_data:
            parts = oid_str.split(".")
            device_ip = ".".join(parts[-4:])
            mac_bytes = bytes(val)
            mac_str = ":".join(f"{b:02x}" for b in mac_bytes)
            ip_by_mac[mac_str] = device_ip

    hostnames = resolve_hostnames(ip_by_mac.get(mac, "") for mac in mac_to_bridge_port)
    port_devices = {}
    for mac, bp in mac_to_bridge_port.items():
        ifindex = bridge_to_ifindex.get(bp, str(bp))
        device_ip = ip_by_mac.get(mac, "")
        hostname = hostnames.get(device_ip, "") if device_ip else ""
        if ifindex not in port_devices:
            port_devices[ifindex] = []
        port_devices[ifindex].append({"mac": mac, "ip": device_ip, "hostname": hostname})

    final = {}
    for ifindex, info in port_status.items():
        final[ifindex] = {
            "name": info["name"],
            "up": info["up"],
            "speed": info.get("speed", 0),
            "port": port_numbers.get(ifindex),
            "alias": port_aliases.get(ifindex, ""),
            "devices": port_devices.get(ifindex, []),
            "vlan": port_vlan.get(ifindex),
            "traffic": info.get("traffic", {}),
            "poe": info.get("poe")
        }
    return final


def _snmp_num(val):
    """Число из ответа SNMP (Integer, Gauge, строка «23»); None, если не число."""
    try:
        return float(int(val))
    except (TypeError, ValueError):
        try:
            return float(str(val).strip())
        except (TypeError, ValueError):
            return None


def _snmp_index_values(rows, depth=1):
    """{индекс: число} по последним depth частям OID."""
    out = {}
    for oid, val in rows or []:
        num = _snmp_num(val)
        if num is not None:
            out[".".join(oid.split(".")[-depth:])] = num
    return out


# ── Источники показателей «здоровья»: сначала таблицы производителей, потом стандартные.
# Каждая функция получает walk(oid) и возвращает число или None. Какой источник сработал, запоминается
# для коммутатора — дальше опрашивается только он (если перестал отвечать — снова перебор).

def _h_avg(walk, oid):
    vals = [v for v in _snmp_index_values(walk(oid)).values()]
    return sum(vals) / len(vals) if vals else None


def _h_max_nonzero(walk, oid, limit=None):
    vals = [v for v in _snmp_index_values(walk(oid)).values() if v > 0 and (limit is None or v < limit)]
    return max(vals) if vals else None


def _h_cisco_cpu(walk):
    # CISCO-PROCESS-MIB: cpmCPUTotal1minRev, на старых IOS — cpmCPUTotal1min
    return _h_avg(walk, "1.3.6.1.4.1.9.9.109.1.1.1.1.7") or _h_avg(walk, "1.3.6.1.4.1.9.9.109.1.1.1.1.4")


def _h_pair_percent(walk, used_oid, other_oid, other_is_free):
    used, other = _snmp_index_values(walk(used_oid)), _snmp_index_values(walk(other_oid))
    common = [i for i in used if i in other]
    if not common:
        return None
    u = sum(used[i] for i in common)
    total = u + sum(other[i] for i in common) if other_is_free else sum(other[i] for i in common)
    return u / total * 100 if total > 0 else None


def _h_cisco_mem(walk):
    # CISCO-MEMORY-POOL-MIB: пул процессора (индекс 1) used/free; IOS-XE — CISCO-ENHANCED-MEMPOOL-MIB
    used = _snmp_index_values(walk("1.3.6.1.4.1.9.9.48.1.1.1.5"))
    free = _snmp_index_values(walk("1.3.6.1.4.1.9.9.48.1.1.1.6"))
    if "1" in used and "1" in free and used["1"] + free["1"] > 0:
        return used["1"] / (used["1"] + free["1"]) * 100
    return _h_pair_percent(walk, "1.3.6.1.4.1.9.9.221.1.1.1.1.7", "1.3.6.1.4.1.9.9.221.1.1.1.1.8", True)


def _h_host_mem(walk):
    # HOST-RESOURCES-MIB: только строки hrStorageRam (в таблице есть и диски, и swap)
    types = walk("1.3.6.1.2.1.25.2.3.1.2")
    ram = {oid.split(".")[-1] for oid, val in types or [] if str(val).strip(".").endswith("1.3.6.1.2.1.25.2.1.2")}
    units = _snmp_index_values(walk("1.3.6.1.2.1.25.2.3.1.4"))
    size = _snmp_index_values(walk("1.3.6.1.2.1.25.2.3.1.5"))
    used = _snmp_index_values(walk("1.3.6.1.2.1.25.2.3.1.6"))
    idx = [i for i in size if i in used and (not ram or i in ram)]
    total = sum(size[i] * units.get(i, 1) for i in idx)
    return sum(used[i] * units.get(i, 1) for i in idx) / total * 100 if total > 0 else None


def _h_entity_sensor_temp(walk, base):
    # ENTITY-SENSOR-MIB (стандартная и Cisco): тип 8 — градусы Цельсия; значение с учётом точности
    types = _snmp_index_values(walk(base + ".1"))
    values = _snmp_index_values(walk(base + ".4"))
    precision = _snmp_index_values(walk(base + ".3"))
    temps = [values[i] / (10 ** precision.get(i, 0)) for i, kind in types.items() if kind == 8 and i in values]
    temps = [x for x in temps if 0 < x < 150]
    return max(temps) if temps else None


def _h_mikrotik_temp(walk):
    # RouterOS 7: таблица датчиков (единица 1 — °C); RouterOS 6: температура в десятых долях градуса
    units = _snmp_index_values(walk("1.3.6.1.4.1.14988.1.1.3.100.1.4"))
    values = _snmp_index_values(walk("1.3.6.1.4.1.14988.1.1.3.100.1.3"))
    temps = [values[i] for i, unit in units.items() if unit == 1 and i in values and 0 < values[i] < 150]
    if temps:
        return max(temps)
    raw = _h_max_nonzero(walk, "1.3.6.1.4.1.14988.1.1.3.10")
    return raw / 10 if raw and raw > 150 else raw


HEALTH_SOURCES = {
    "cpu": [
        ("cisco", _h_cisco_cpu),
        ("host-resources", lambda w: _h_avg(w, "1.3.6.1.2.1.25.3.3.1.2")),
        ("juniper", lambda w: _h_max_nonzero(w, "1.3.6.1.4.1.2636.3.1.13.1.8")),
        ("huawei", lambda w: _h_max_nonzero(w, "1.3.6.1.4.1.2011.5.25.31.1.1.1.1.5")),
        ("comware", lambda w: _h_max_nonzero(w, "1.3.6.1.4.1.25506.2.6.1.1.1.1.6")),
        ("hpe", lambda w: _h_avg(w, "1.3.6.1.4.1.11.2.14.11.5.1.9.6.1")),
        ("radlan", lambda w: _h_avg(w, "1.3.6.1.4.1.89.1.8")),                   # Cisco SB, Eltex MES
        ("dlink", lambda w: _h_avg(w, "1.3.6.1.4.1.171.12.1.1.6.2")),
        ("tplink", lambda w: _h_avg(w, "1.3.6.1.4.1.11863.6.4.1.1.1.1.3")),
    ],
    "mem": [
        ("cisco", _h_cisco_mem),
        ("host-resources", _h_host_mem),
        ("juniper", lambda w: _h_max_nonzero(w, "1.3.6.1.4.1.2636.3.1.13.1.11")),
        ("huawei", lambda w: _h_max_nonzero(w, "1.3.6.1.4.1.2011.5.25.31.1.1.1.1.7")),
        ("comware", lambda w: _h_max_nonzero(w, "1.3.6.1.4.1.25506.2.6.1.1.1.1.8")),
        ("hpe", lambda w: _h_pair_percent(w, "1.3.6.1.4.1.11.2.14.11.5.1.1.2.1.1.1.7",
                                          "1.3.6.1.4.1.11.2.14.11.5.1.1.2.1.1.1.5", False)),
        ("dlink", lambda w: _h_avg(w, "1.3.6.1.4.1.171.12.1.1.9.1.4")),
        ("tplink", lambda w: _h_avg(w, "1.3.6.1.4.1.11863.6.4.1.2.1.1.2")),
    ],
    "temp": [
        ("cisco", lambda w: _h_max_nonzero(w, "1.3.6.1.4.1.9.9.13.1.3.1.3", 150)),
        ("cisco-sensor", lambda w: _h_entity_sensor_temp(w, "1.3.6.1.4.1.9.9.91.1.1.1.1")),
        ("entity-sensor", lambda w: _h_entity_sensor_temp(w, "1.3.6.1.2.1.99.1.1.1")),
        ("juniper", lambda w: _h_max_nonzero(w, "1.3.6.1.4.1.2636.3.1.13.1.7", 150)),
        ("huawei", lambda w: _h_max_nonzero(w, "1.3.6.1.4.1.2011.5.25.31.1.1.1.1.11", 150)),
        ("comware", lambda w: _h_max_nonzero(w, "1.3.6.1.4.1.25506.2.6.1.1.1.1.12", 150)),
        ("mikrotik", _h_mikrotik_temp),
        ("dlink", lambda w: _h_max_nonzero(w, "1.3.6.1.4.1.171.12.11.1.8.1.2", 150)),
    ],
}
_health_source_cache = {}  # ip -> {"cpu": (источник или "" — не поддерживается, время проверки), ...}
HEALTH_RECHECK_SEC = 3600   # неподдерживаемый показатель перепроверяется раз в час, а не каждый опрос


def poll_switch_health(ip, community):
    """CPU, память (%) и температура (°C) коммутатора. 0 — коммутатор этот показатель не сообщает."""
    import time
    walk = lambda oid: snmp_walk(ip, community, oid)
    known = _health_source_cache.setdefault(ip, {})
    health = {"cpu_usage": 0, "ram_usage": 0, "temperature": 0}
    now = time.time()
    for metric, field in (("cpu", "cpu_usage"), ("mem", "ram_usage"), ("temp", "temperature")):
        cached, checked = known.get(metric, (None, 0))
        if cached == "" and now - checked < HEALTH_RECHECK_SEC:
            continue
        sources = HEALTH_SOURCES[metric]
        if cached:
            sources = [s for s in sources if s[0] == cached] + [s for s in sources if s[0] != cached]
        found = ""
        for name, fn in sources:
            try:
                value = fn(walk)
            except Exception as e:
                log.debug(_s("Показатель {metric} ({source}) не разобран: {error}", metric=metric, source=name, error=e))
                value = None
            if value is not None and value > 0:
                health[field] = round(min(value, 100.0) if metric != "temp" else value, 1)
                found = name
                break
        known[metric] = (found, now)
    return health

def detect_duplicate_macs(switch_id):
    """
    Обнаружение дублирующихся MAC-адресов на разных портах.
    Возвращает список дубликатов: [{mac, ports: [port1, port2, ...]}]
    """
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT mac, GROUP_CONCAT(port_number) as ports, COUNT(*) as count
            FROM devices
            WHERE switch_id = ? AND mac IS NOT NULL AND mac != ''
            GROUP BY mac
            HAVING count > 1
        """, (switch_id,))
        rows = c.fetchall()

    duplicates = []
    for mac, ports_str, count in rows:
        ports = [int(p) for p in ports_str.split(',')]
        duplicates.append({
            "mac": mac,
            "ports": ports,
            "count": count
        })

    return duplicates


# ─────────────────────────────────────────
# PORT EVENTS / ALERTING
# ─────────────────────────────────────────

def diff_and_log_port_events(switch_id, previous_snapshot, new_status):
    """
    Сравнивает предыдущий снимок статусов портов (ifOperStatus) с только что
    полученным по SNMP. Для каждого порта, сменившего up→down или down→up,
    пишет запись в port_events. Возвращает новый снимок для сохранения
    в switches.port_status_snapshot.

    previous_snapshot: {ifindex: {"up": bool, "name": str}}
    new_status: результат poll_switch_snmp(), {ifindex: {"up": bool, "name": str, ...}}
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    events = []
    new_snapshot = {}

    for ifindex, info in new_status.items():
        up_now = bool(info.get("up"))
        port_name = info.get("name") or f"Port {ifindex}"
        new_snapshot[ifindex] = {"up": up_now, "name": port_name}

        prev = previous_snapshot.get(ifindex)
        if prev is None:
            # Первый опрос этого порта — базовая точка, без алерта.
            continue

        up_before = bool(prev.get("up"))
        if up_before != up_now:
            events.append({
                "ifindex": ifindex,
                "port_name": port_name,
                "port_number": info.get("port"),
                "event_type": "up" if up_now else "down",
                "event_time": now
            })

    insert_port_events(switch_id, events)
    return new_snapshot


def insert_port_events(switch_id, events):
    """events: [{ifindex, port_name, port_number?, event_type, event_time, details?}]"""
    if not events:
        return
    with sqlite3.connect(DB) as conn:
        conn.executemany("""
            INSERT INTO port_events (switch_id, ifindex, port_name, port_number, event_type, event_time, details, is_read)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, [(switch_id, e.get("ifindex"), e.get("port_name"), e.get("port_number"), e["event_type"],
               e["event_time"], e.get("details")) for e in events])
        conn.commit()


def _fmt_mbps(v):
    if v is None:
        return "—"
    if v >= 1000:
        return _("{v:.2f} Гбит/с", v=v / 1000)
    if v >= 1:
        return _("{v:.1f} Мбит/с", v=v)
    return _("{v:.0f} Кбит/с", v=v * 1000)


def evaluate_port_alerts(port, prev_alerts, settings, now):
    """Пороговые оповещения по порту с гистерезисом: событие при превышении и одно —
    при возврате в норму, без повторов на каждом опросе.
    port — запись снимка (name, port, up, util, in_mbps, out_mbps, errors_delta).
    Возвращает (новое состояние оповещений, список событий)."""
    alerts = dict(prev_alerts or {})
    events = []
    base = {"ifindex": port["ifindex"], "port_name": port["name"], "port_number": port.get("port"), "event_time": now}

    limit = settings["alert_util_percent"]
    util = port.get("util")
    if limit and util is not None:
        if not alerts.get("util") and util >= limit:
            alerts["util"] = True
            events.append({**base, "event_type": "util_high", "details":
                           _s("Загрузка {util:.0f}% (↓ {in_mbps}, ↑ {out_mbps}), порог {limit}%", util=util, in_mbps=_fmt_mbps(port.get('in_mbps')), out_mbps=_fmt_mbps(port.get('out_mbps')), limit=limit)})
        elif alerts.get("util") and util < max(limit - 10, limit * 0.9):
            alerts["util"] = False
            events.append({**base, "event_type": "util_ok", "details": _s("Загрузка снизилась до {util:.0f}%", util=util)})
    elif alerts.get("util") and (not limit or not port.get("up")):
        alerts["util"] = False  # порог выключили или порт упал — тихо сбрасываем

    limit = settings["alert_errors_per_poll"]
    errs = port.get("errors_delta")
    if limit and errs is not None:
        if not alerts.get("errors") and errs >= limit:
            alerts["errors"] = True
            events.append({**base, "event_type": "errors_high", "details":
                           _s("{errs} ошибок с прошлого опроса, порог {limit}", errs=errs, limit=limit)})
        elif alerts.get("errors") and errs < limit:
            alerts["errors"] = False
            events.append({**base, "event_type": "errors_ok", "details": _s("Ошибок с прошлого опроса: {errs}", errs=errs)})
    elif alerts.get("errors") and not limit:
        alerts["errors"] = False
    return {k: v for k, v in alerts.items() if v}, events


def evaluate_health_alerts(health, prev_state, settings, now):
    """Оповещения по CPU и температуре коммутатора. Значение 0 — датчик не ответил, пропускаем."""
    state = dict(prev_state or {})
    events = []
    checks = (
        ("cpu", "alert_cpu_percent", health.get("cpu_usage"), "CPU", "%", 10),
        ("temp", "alert_temp_c", health.get("temperature"), _s("Температура"), "°C", 5),
    )
    for key, setting, value, label, unit, hysteresis in checks:
        limit = settings[setting]
        if not limit or not value:
            if not limit:
                state.pop(key, None)
            continue
        base = {"ifindex": None, "port_name": label, "port_number": None, "event_time": now}
        if not state.get(key) and value >= limit:
            state[key] = True
            events.append({**base, "event_type": f"{key}_high", "details": _s("{label}: {value:.0f}{unit}, порог {limit}{unit}", label=label, value=value, unit=unit, limit=limit)})
        elif state.get(key) and value < limit - hysteresis:
            state.pop(key, None)
            events.append({**base, "event_type": f"{key}_ok", "details": _s("{label} вернулась в норму: {value:.0f}{unit}", label=label, value=value, unit=unit)})
    return state, events


def update_mac_table(switch_id, result, now):
    """Сохраняет MAC-адреса последнего опроса. Порт, где MAC виден вместе со многими
    другими (port_mac_count), скорее всего uplink — поиск показывает его ниже."""
    rows = []
    for ifindex, info in result.items():
        if not isinstance(info, dict):
            continue
        devices = info.get("devices") or []
        vlan = (info.get("vlan") or {}).get("id")
        for dev in devices:
            if dev.get("mac"):
                rows.append((switch_id, dev["mac"].lower(), ifindex, info.get("port"), info.get("name"),
                             vlan, dev.get("ip") or None, dev.get("hostname") or None, len(devices), now, now))
    with sqlite3.connect(DB) as conn:
        conn.executemany("""
            INSERT INTO mac_table (switch_id, mac, ifindex, port_number, port_name, vlan, ip, hostname,
                                   port_mac_count, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(switch_id, mac) DO UPDATE SET
                ifindex=excluded.ifindex, port_number=excluded.port_number, port_name=excluded.port_name,
                vlan=excluded.vlan, ip=COALESCE(excluded.ip, mac_table.ip),
                hostname=COALESCE(excluded.hostname, mac_table.hostname),
                port_mac_count=excluded.port_mac_count, last_seen=excluded.last_seen
        """, rows)
        # Не видели больше 30 дней — устройство, скорее всего, убрали
        conn.execute("DELETE FROM mac_table WHERE switch_id=? AND last_seen < datetime(?, '-30 days')", (switch_id, now))
        conn.commit()


# ─────────────────────────────────────────
# НАСТРОЙКИ / ПЛАНИРОВЩИК ПЕРИОДИЧЕСКОГО SNMP-ОПРОСА
# ─────────────────────────────────────────

DEFAULT_POLL_INTERVAL_MINUTES = 5
scheduler = None
_poll_job_id = "periodic_snmp_poll"


# Пороги оповещений: (ключ, значение по умолчанию, минимум, максимум). 0 — оповещение выключено.
ALERT_THRESHOLDS = (
    ("alert_util_percent", 80, 0, 100),     # загрузка порта, % от скорости порта
    ("alert_errors_per_poll", 10, 0, 10**9),  # ошибок на порту (вход + выход) между опросами
    ("alert_cpu_percent", 90, 0, 100),      # загрузка CPU коммутатора, %
    ("alert_temp_c", 70, 0, 150),           # температура коммутатора, °C
)


# Хранение данных и резервные копии
DATA_SETTINGS = (
    ("retention_raw_days", 7, 1, 90),         # сырые опросы, дней (дальше — почасовые агрегаты)
    ("retention_hourly_days", 365, 7, 3650),  # почасовые агрегаты, дней
    ("retention_events_days", 90, 7, 3650),   # события, дней
    ("backup_auto", 1, 0, 1),                 # ежедневная автокопия базы
    ("backup_keep", 14, 1, 365),              # сколько копий хранить
)
INT_SETTINGS = (("poll_interval_minutes", DEFAULT_POLL_INTERVAL_MINUTES, 1, 1440),) + ALERT_THRESHOLDS + DATA_SETTINGS


def _int_setting(raw, default, lo, hi):
    try:
        return max(lo, min(hi, int(float(raw))))
    except (TypeError, ValueError):
        return default


def get_settings():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT key, value FROM app_settings")
        rows = dict(c.fetchall())
    settings = {"poll_enabled": rows.get("poll_enabled", "0") == "1"}
    for key, default, lo, hi in INT_SETTINGS:
        settings[key] = _int_setting(rows.get(key, default), default, lo, hi)
    # Язык сервера: журнал, события, уведомления, экспорт по расписанию. "" — язык системы сервера
    lang = rows.get("server_language", "")
    settings["server_language"] = lang if lang in i18n.LANGUAGES else ""
    # Проверка новых версий (раз в день, GitHub); SWITCHMAP_UPDATE_CHECK=0 запрещает её совсем
    settings["update_check"] = rows.get("update_check", "1") == "1" and updates.allowed()
    return settings


def save_settings(updates):
    """Сохраняет только переданные ключи (частичное обновление) с проверкой диапазонов."""
    values = []
    if "poll_enabled" in updates:
        values.append(("poll_enabled", "1" if updates["poll_enabled"] else "0"))
    if "update_check" in updates:
        values.append(("update_check", "1" if updates["update_check"] else "0"))
    for key, default, lo, hi in INT_SETTINGS:
        if key in updates:
            values.append((key, str(_int_setting(updates[key], default, lo, hi))))
    if "server_language" in updates:
        lang = updates["server_language"] if updates["server_language"] in i18n.LANGUAGES else ""
        values.append(("server_language", lang))
        i18n.set_server_language(lang)
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.executemany(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            values
        )
        conn.commit()


POLL_WORKERS = max(1, int(os.environ.get("SWITCHMAP_POLL_WORKERS", "8") or 8))  # коммутаторов одновременно
MIN_RATE_INTERVAL_SEC = 10  # скорость порта — по интервалу не короче этого (время хранится с точностью до секунды)


def scheduled_poll_all_switches():
    """Опрашивает по SNMP все коммутаторы с заданным IP. Вызывается планировщиком."""
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM switches WHERE ip_address IS NOT NULL AND ip_address != ''")
        switch_ids = [row[0] for row in c.fetchall()]

    def poll_one(switch_id):
        try:
            poll_switch_and_log_events(switch_id)
        except Exception as e:
            log.exception(_s("Периодический опрос: ошибка опроса коммутатора {id}: {error}", id=switch_id, error=e))

    _periodic_poll_running.set()
    try:
        # Несколько коммутаторов одновременно: недоступный (ждём таймаут) не задерживает остальных
        workers = max(1, min(POLL_WORKERS, len(switch_ids)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="poll") as pool:
            list(pool.map(poll_one, switch_ids))
    finally:
        _periodic_poll_running.clear()
    # События всех коммутаторов этого опроса — одним сообщением
    _safe_job(dispatch_notifications)


_periodic_poll_running = threading.Event()


def dispatch_notifications(force=False):
    """Пока идёт плановый опрос, ежеминутная рассылка ждёт его конца — чтобы не разрывать пачку событий."""
    if _periodic_poll_running.is_set() and not force:
        return {"skipped": _("идёт плановый опрос")}
    return notify.dispatch(DB, SECRET_BOX)


_maintenance_lock = threading.Lock()


def run_maintenance(vacuum=False):
    """Свёртка истории и очистка по срокам хранения из настроек. Не запускается параллельно сама с собой."""
    if not _maintenance_lock.acquire(blocking=False):
        return {"skipped": _("обслуживание уже выполняется")}
    try:
        s = get_settings()
        return maintenance.rollup_and_prune(
            DB, compute_traffic_rates, raw_days=s["retention_raw_days"], hourly_days=s["retention_hourly_days"],
            events_days=s["retention_events_days"], vacuum=vacuum)
    finally:
        _maintenance_lock.release()


def auto_backup_if_due(reason="auto", max_age_hours=23):
    """Ежедневная копия базы, если включена; лишние старые копии удаляются."""
    s = get_settings()
    if not s["backup_auto"]:
        return None
    age = maintenance.last_backup_age_hours(DB)
    if age is not None and age < max_age_hours:
        return None
    name = maintenance.create_backup(DB, reason)
    maintenance.prune_backups(DB, s["backup_keep"])
    return name


def scheduled_update_check():
    if get_settings()["update_check"]:
        updates.check(DB, APP_VERSION)


def _safe_job(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as e:
        log.exception(_s("Фоновая задача {name}: {error}", name=fn.__name__, error=e))


def apply_scheduler_settings():
    """Пере(создаёт) задачи планировщика согласно текущим настройкам в БД."""
    global scheduler
    if scheduler is None:
        return
    settings = get_settings()
    if scheduler.get_job(_poll_job_id):
        scheduler.remove_job(_poll_job_id)
    if settings["poll_enabled"]:
        scheduler.add_job(
            scheduled_poll_all_switches,
            "interval",
            minutes=max(1, settings["poll_interval_minutes"]),
            id=_poll_job_id,
            replace_existing=True
        )
    # Обслуживание базы и автокопия работают всегда, независимо от опроса
    scheduler.add_job(_safe_job, "interval", hours=1, args=[run_maintenance],
                      id="maintenance", replace_existing=True)
    scheduler.add_job(_safe_job, "interval", hours=1, args=[auto_backup_if_due],
                      id="auto_backup", replace_existing=True)
    # NetBox: имена и IP связанных коммутаторов (если включено в настройках NetBox)
    scheduler.add_job(_safe_job, "interval", hours=1, args=[scheduled_netbox_sync],
                      id="netbox_sync", replace_existing=True, max_instances=1, coalesce=True)
    # Новые версии: раз в день, первая проверка — через пару минут после запуска
    if settings["update_check"]:
        if not scheduler.get_job("update_check"):
                scheduler.add_job(_safe_job, "interval", hours=24, args=[scheduled_update_check], id="update_check",
                              replace_existing=True, max_instances=1, coalesce=True,
                              next_run_time=datetime.now() + timedelta(minutes=2))
    elif scheduler.get_job("update_check"):
        scheduler.remove_job("update_check")
    # Уведомления: события ручных опросов и повторные попытки после ошибок сети
    scheduler.add_job(_safe_job, "interval", minutes=1, args=[dispatch_notifications],
                      id="notify", replace_existing=True, max_instances=1, coalesce=True)


SCHEMA_VERSION = 6  # увеличивать при изменении схемы — перед миграцией создаётся резервная копия


def prepare_database():
    """Запуск: новая база — создаём; старая — копия перед миграцией (если схема устарела), миграция."""
    if not os.path.exists(DB):
        init_db()
    else:
        try:
            with sqlite3.connect(DB) as conn:
                row = conn.execute("SELECT value FROM app_settings WHERE key='schema_version'").fetchone()
            stored = int(row[0]) if row else 0
        except sqlite3.Error:
            stored = 0
        if stored < SCHEMA_VERSION:
            name = maintenance.create_backup(DB, "pre-migrate")
            log.info(_s("Резервная копия перед обновлением базы: {path}", path=os.path.join(maintenance.backups_dir(DB), name)))
        migrate_db()
    with sqlite3.connect(DB) as conn:
        conn.execute("INSERT INTO app_settings (key, value) VALUES ('schema_version', ?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))
        conn.commit()
    conn = sqlite3.connect(DB)
    try:
        mode = maintenance.enable_wal(conn)
    finally:
        conn.close()
    if mode != "wal":
        log.warning(_s("Режим WAL для базы не включён ({mode}): при нагрузке возможны задержки", mode=mode))
    i18n.set_server_language(get_settings()["server_language"])
    encrypted = security.encrypt_plaintext_snmp_keys(DB, SECRET_BOX)
    if encrypted:
        log.info(_s("Зашифровано паролей SNMPv3: {n}", n=encrypted))
    _safe_job(auto_backup_if_due, "startup")
    # Первое обслуживание — в фоне, чтобы не задерживать запуск (на большой базе это может занять время)
    threading.Thread(target=_safe_job, args=(run_maintenance,), daemon=True).start()


def load_server_language():
    """Язык сервера из настроек — для журнала до prepare_database (новой базы ещё может не быть)."""
    try:
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT value FROM app_settings WHERE key='server_language'").fetchone()
        i18n.set_server_language(row[0] if row and row[0] in i18n.LANGUAGES else "")
    except sqlite3.Error:
        pass


def init_scheduler():
    global scheduler
    if scheduler is not None:
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        log.error(_s("APScheduler не установлен — периодический опрос не работает. Выполните: pip install apscheduler"))
        return
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.start()
    apply_scheduler_settings()


# ─────────────────────────────────────────
# LLDP / TOPOLOGY HELPERS
# ─────────────────────────────────────────

def snmp_value_text(value):
    """Convert pysnmp OctetString/Integer values to a readable string."""
    try:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace").strip("\x00").strip()
        # pysnmp OctetString behaves like bytes in many versions
        if hasattr(value, "asOctets"):
            return bytes(value.asOctets()).decode("utf-8", errors="replace").strip("\x00").strip()
        return str(value).strip()
    except Exception:
        return str(value)


def snmp_id_text(value):
    """LLDP chassis/port ID: часто это MAC в виде 6 байт — показываем aa:bb:cc:dd:ee:ff, а не «кракозябры»."""
    raw = None
    if isinstance(value, bytes):
        raw = value
    elif hasattr(value, "asOctets"):
        try:
            raw = bytes(value.asOctets())
        except Exception:
            raw = None
    if raw is not None and raw and not all(32 <= b < 127 for b in raw):
        try:
            text = raw.decode("utf-8")
            if text.isprintable():
                return text.strip()
        except UnicodeDecodeError:
            pass
        return ":".join(f"{b:02x}" for b in raw)
    return snmp_value_text(value)


def poll_switch_lldp(ip, community):
    """
    Read standard IEEE 802.1AB LLDP remote-neighbor information.
    Returns links local_port -> remote chassis/sysName/port.
    """
    if not ip:
        return []

    # lldpRemTable:
    # .1 = timeMark, .2 = localPortNum, .3 = remIndex
    base = "1.0.8802.1.1.2.1.4.1.1"
    local_data = snmp_walk(ip, community, f"{base}.2")
    chassis_data = snmp_walk(ip, community, f"{base}.5")
    port_data = snmp_walk(ip, community, f"{base}.7")
    port_desc_data = snmp_walk(ip, community, f"{base}.8")
    sysname_data = snmp_walk(ip, community, f"{base}.9")

    if not local_data:
        return []

    def key(oid):
        parts = oid.split(".")
        return ".".join(parts[-3:])

    def build(rows):
        return {key(oid): snmp_value_text(val) for oid, val in (rows or [])}

    local = build(local_data)
    chassis = {key(oid): snmp_id_text(val) for oid, val in (chassis_data or [])}
    remote_port = {key(oid): snmp_id_text(val) for oid, val in (port_data or [])}
    remote_desc = build(port_desc_data)
    remote_name = build(sysname_data)

    links = []
    for k, local_port in local.items():
        # Prefer sysName, fall back to chassis ID. This still gives us
        # a visible "unknown" neighbor when the remote device isn't in DB.
        neighbor_name = remote_name.get(k, "")
        chassis_id = chassis.get(k, "")
        port_id = remote_port.get(k, "")
        port_desc = remote_desc.get(k, "")

        if not neighbor_name and not chassis_id:
            continue

        links.append({
            "local_port": str(local_port),
            "remote_name": neighbor_name,
            "remote_chassis": chassis_id,
            "remote_port": port_id or port_desc,
        })

    return links


def collect_topology():
    """Build a graph from configured switches + LLDP neighbors + assigned devices."""
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        snmp_auth_by_id = {r["id"]: SnmpAuth.from_row(r) for r in conn.execute("SELECT * FROM switches")}
        conn.row_factory = None
        c = conn.cursor()
        c.execute("SELECT id, name, ports, ip_address, snmp_community FROM switches ORDER BY id")
        switches = c.fetchall()
        c.execute("""
            SELECT id, switch_id, port_number, ip, mac, hostname, is_online, last_seen, notes
            FROM devices ORDER BY switch_id, port_number
        """)
        devices = c.fetchall()

    nodes = []
    links = []
    switch_by_name = {}
    switch_by_id = {}

    for sid, name, ports, ip, community in switches:
        node_id = f"switch:{sid}"
        node = {
            "id": node_id,
            "type": "switch",
            "switch_id": sid,
            "name": name or f"Switch {sid}",
            "ip": ip or "",
            "ports": ports or 0,
            "status": "unknown"
        }
        nodes.append(node)
        switch_by_id[sid] = node
        if name:
            switch_by_name[name.strip().lower()] = node

    # Assigned endpoints are useful on the global map even though LLDP
    # normally only gives us infrastructure neighbors.
    for did, sid, port, ip, mac, hostname, is_online, last_seen, notes in devices:
        parent = switch_by_id.get(sid)
        if not parent:
            continue
        label = hostname or ip or mac or f"Device {did}"
        node_id = f"device:{did}"
        nodes.append({
            "id": node_id,
            "type": "server",
            "device_id": did,
            "switch_id": sid,
            "port": port,
            "name": label,
            "ip": ip or "",
            "mac": mac or "",
            "status": "online" if is_online else "offline",
            "last_seen": last_seen or "",
            "notes": notes or ""
        })
        links.append({
            "id": f"device-link:{did}",
            "source": parent["id"],
            "target": node_id,
            "type": "endpoint",
            "local_port": str(port)
        })

    # LLDP polling in parallel so one slow switch doesn't make the map
    # feel like it was designed by a committee of network engineers.
    def poll_one(sw):
        sid, name, ports, ip, community = sw
        auth = snmp_auth_by_id.get(sid)
        if not ip or not auth or auth.validate():
            return sid, []
        return sid, poll_switch_lldp(ip, auth)

    lldp_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(2 * POLL_WORKERS, len(switches)))) as executor:
        futures = [executor.submit(poll_one, sw) for sw in switches]
        for future in futures:
            try:
                sid, result = future.result(timeout=25)
                lldp_results[sid] = result
            except Exception as e:
                log.warning("LLDP: %s", e)

    # De-duplicate physical links. Both sides normally report each other.
    seen_pairs = set()
    unknown_nodes = {}

    for sid, neighbors in lldp_results.items():
        local_node = switch_by_id.get(sid)
        if not local_node:
            continue

        for n in neighbors:
            remote_name = (n.get("remote_name") or "").strip()
            remote_chassis = (n.get("remote_chassis") or "").strip()
            remote_node = switch_by_name.get(remote_name.lower()) if remote_name else None

            if remote_node:
                target_id = remote_node["id"]
                pair_key = tuple(sorted((local_node["id"], target_id)))
                # Keep a single edge, but include local/remote ports from the
                # first observation. If both sides are available, the UI can
                # still show a useful physical link.
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                links.append({
                    "id": f"lldp:{local_node['id']}:{target_id}",
                    "source": local_node["id"],
                    "target": target_id,
                    "type": "lldp",
                    "local_port": n.get("local_port", ""),
                    "remote_port": n.get("remote_port", ""),
                    "neighbor": remote_name
                })
            else:
                # Unknown neighbor: keep it on the graph so LLDP data is not
                # silently thrown away. It has no detail-page link.
                unknown_key = remote_chassis or remote_name or f"unknown:{sid}:{n.get('local_port','')}"
                target_id = f"lldp:{unknown_key}"
                if target_id not in unknown_nodes:
                    unknown_nodes[target_id] = {
                        "id": target_id,
                        "type": "unknown",
                        "name": remote_name or _("Неизвестный LLDP-узел"),
                        "chassis": remote_chassis,
                        "status": "unknown"
                    }
                    nodes.append(unknown_nodes[target_id])
                edge_key = (local_node["id"], target_id, n.get("local_port", ""))
                if edge_key not in seen_pairs:
                    seen_pairs.add(edge_key)
                    links.append({
                        "id": f"lldp:{local_node['id']}:{target_id}:{n.get('local_port','')}",
                        "source": local_node["id"],
                        "target": target_id,
                        "type": "lldp",
                        "local_port": n.get("local_port", ""),
                        "remote_port": n.get("remote_port", ""),
                        "neighbor": remote_name or remote_chassis
                    })

    return {"nodes": nodes, "links": links}

# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

def switch_overview(row, unread_by_switch):
    """Сводка по коммутатору для таблицы на главной: порты, загрузка, оповещения."""
    try:
        snapshot = json.loads(row["port_status_snapshot"] or "{}")
    except (ValueError, TypeError):
        snapshot = {}
    try:
        health_alerts = json.loads(row["alert_state"] or "{}")
    except (ValueError, TypeError):
        health_alerts = {}
    ports = [p for p in snapshot.values() if isinstance(p, dict) and p.get("port")]
    utils = [p["util"] for p in ports if isinstance(p.get("util"), (int, float))]
    alerts = sum(len(p.get("alerts") or {}) for p in ports) + len([v for v in health_alerts.values() if v])
    return {
        "id": row["id"],
        "name": row["name"] or f"Switch {row['id']}",
        "ip": row["ip_address"] or "",
        "model": row["model"] if "model" in row.keys() else "",
        "ports": row["ports"] or 0,
        "snmp": "v3" if (row["snmp_version"] or "2c") == "3" else "v2c",
        "last_poll": row["last_poll_time"],
        "cpu": row["cpu_usage"] or None,
        "temperature": row["temperature"] or None,
        "polled": bool(ports),
        "ports_up": sum(1 for p in ports if p.get("up")),
        "ports_seen": len(ports),
        "max_util": max(utils) if utils else None,
        "alerts": alerts,
        "unread": unread_by_switch.get(row["id"], 0),
    }


@app.route("/")
def index():
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM switches ORDER BY name COLLATE NOCASE").fetchall()
        unread = dict(conn.execute(
            "SELECT switch_id, COUNT(*) FROM port_events WHERE is_read = 0 GROUP BY switch_id").fetchall())
    switches = [switch_overview(r, unread) for r in rows]
    summary = {
        "total": len(switches),
        "with_ip": sum(1 for s in switches if s["ip"]),
        "ports_up": sum(s["ports_up"] for s in switches),
        "ports_seen": sum(s["ports_seen"] for s in switches),
        "alerts": sum(s["alerts"] for s in switches),
        "unread": sum(unread.values()),
    }
    return render_template("index.html", switches=switches, summary=summary,
                           util_threshold=get_settings()["alert_util_percent"])


def snmp_auth_from_form(f, current=None):
    """SnmpAuth из полей формы (snmp_version, snmp_community, snmp_v3_*). Пустой пароль v3 —
    взять сохранённый у current (строка switches). Возвращает (auth, текст ошибки или None)."""
    def saved(col):
        return SECRET_BOX.decrypt(current[col]) if current is not None and current[col] else ""
    auth = SnmpAuth(
        f.get("snmp_version") or "2c", (f.get("snmp_community") or "").strip() or "public",
        (f.get("snmp_v3_user") or "").strip(),
        f.get("snmp_v3_auth_proto") or "none", f.get("snmp_v3_auth_key") or saved("snmp_v3_auth_key"),
        f.get("snmp_v3_priv_proto") or "none", f.get("snmp_v3_priv_key") or saved("snmp_v3_priv_key"),
        (f.get("snmp_v3_context") or "").strip())
    return auth, auth.validate()


def snmp_columns(auth):
    """Колонки switches для учётных данных SNMP; пароли v3 — зашифрованные."""
    v3 = auth.version == "3"
    return {
        "snmp_version": auth.version, "snmp_community": auth.community,
        "snmp_v3_user": (auth.user or None) if v3 else None,
        "snmp_v3_auth_proto": auth.auth_proto if v3 else "none",
        "snmp_v3_auth_key": SECRET_BOX.encrypt(auth.auth_key) if v3 and auth.auth_proto != "none" else None,
        "snmp_v3_priv_proto": auth.priv_proto if v3 else "none",
        "snmp_v3_priv_key": SECRET_BOX.encrypt(auth.priv_key) if v3 and auth.priv_proto != "none" else None,
        "snmp_v3_context": (auth.context or None) if v3 else None,
    }


def create_switch_record(name, ports, ip_address, auth, layout="single", patch_panels="[]", model=None,
                         netbox_id=None, source=""):
    """Создаёт коммутатор и пишет запись в журнал. Возвращает id."""
    cols = {"name": name, "ports": ports, "patch_panels": patch_panels, "patch_position": None, "switch_layout": layout,
            "connections": "{}", "ip_address": ip_address or "", "port_types": "{}", "trunk_ports": "{}",
            "model": model or None, "netbox_id": netbox_id, **snmp_columns(auth)}
    with sqlite3.connect(DB) as conn:
        cur = conn.execute(f"INSERT INTO switches ({', '.join(cols)}) VALUES ({', '.join('?' for _c in cols)})",
                           list(cols.values()))
        new_id = cur.lastrowid
        conn.commit()
    ports_label = _ns(ports, "{n} порт", "{n} порта", "{n} портов")
    summary = ", ".join(x for x in (source, model, ports_label,f"IP {ip_address}" if ip_address else "",
                                    auth.describe() if auth.version == "3" else "") if x)
    audit.log(DB, "create", actor=current_actor(), switch_id=new_id, switch_name=name, summary=summary)
    return new_id


def _clamp_ports(value, default=24):
    try:
        return max(1, min(96, int(value)))
    except (TypeError, ValueError):
        return default


@app.route("/add", methods=["GET", "POST"])
def add_switch():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        ports = _clamp_ports(request.form.get("ports"))
        switch_layout = request.form.get("switch_layout", "single")
        ip_address = request.form.get("ip_address", "").strip()
        auth, error = snmp_auth_from_form(request.form)
        if not name or error:
            return _deny(400, error or _("Укажите название коммутатора"))

        patch_panels_data = request.form.get("patch_panels_data")
        has_patch = request.form.get("has_patch_panel", "1")
        if patch_panels_data is not None:
            patch_panels = patch_panels_data if patch_panels_data else json.dumps([])
        elif has_patch == "0":
            patch_panels = json.dumps([])
        else:
            patch_ports = int(request.form.get("patch_ports", 24))
            patch_position = request.form.get("patch_position", "below")
            patch_panels = json.dumps([{
                "id": 1, "name": "Patch Panel 1",
                "ports": patch_ports, "position": patch_position, "layout": "single"
            }])

        model = (request.form.get("model") or "").strip()[:120] or None
        create_switch_record(name, ports, ip_address, auth, switch_layout, patch_panels, model)
        return redirect(url_for("index"))

    return render_template("add_switch.html")


@app.route("/switch/<int:switch_id>")
def switch_view(switch_id):
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        # sqlite3.Row: шаблон обращается к колонкам по имени (switch['patch_panels']).
        # Порядок колонок в старых базах зависит от миграций, номера ненадёжны.
        c.row_factory = sqlite3.Row
        c.execute("SELECT * FROM switches WHERE id=?", (switch_id,))
        switch = c.fetchone()
        if not switch:
            return _deny(404, _("Коммутатор не найден"))
        c.row_factory = None
        c.execute("SELECT * FROM devices WHERE switch_id=? ORDER BY port_number", (switch_id,))
        devices_rows = c.fetchall()

    netbox_link = netbox.device_url(netbox.load_config(DB), switch["netbox_id"]) if "netbox_id" in switch.keys() else ""
    return render_template("switch_view.html", switch=switch, devices=devices_rows, netbox_link=netbox_link)


def fetch_switch(switch_id):
    """Строка switches как dict или None."""
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM switches WHERE id=?", (switch_id,)).fetchone()
    return dict(row) if row else None


@app.route("/update/<int:switch_id>", methods=["POST"])
def update_switch(switch_id):
    before = fetch_switch(switch_id)
    if before is None:
        return _deny(404, _("Коммутатор не найден"))
    connections = request.form.get("connections", "{}")
    name = request.form.get("name", "")
    port_count = request.form.get("port_count")
    layout = request.form.get("layout")
    patch_panels = request.form.get("patch_panels")
    ip_address = request.form.get("ip_address", "").strip()
    snmp_community = request.form.get("snmp_community", "public").strip() or "public"
    port_types = request.form.get("port_types", "{}")
    trunk_ports = request.form.get("trunk_ports", "{}")

    # SNMPv3: пустой пароль в форме — «оставить сохранённый» (пароли в браузер не отдаются)
    snmp_update = None
    if "snmp_version" in request.form:
        with sqlite3.connect(DB) as conn:
            conn.row_factory = sqlite3.Row
            current = conn.execute("SELECT * FROM switches WHERE id=?", (switch_id,)).fetchone()
        if current is None:
            return _deny(404, _("Коммутатор не найден"))
        f = request.form
        auth = SnmpAuth(
            f.get("snmp_version", "2c"), snmp_community, f.get("snmp_v3_user", "").strip(),
            f.get("snmp_v3_auth_proto", "none"), f.get("snmp_v3_auth_key") or SECRET_BOX.decrypt(current["snmp_v3_auth_key"]),
            f.get("snmp_v3_priv_proto", "none"), f.get("snmp_v3_priv_key") or SECRET_BOX.decrypt(current["snmp_v3_priv_key"]),
            f.get("snmp_v3_context", "").strip())
        error = auth.validate()
        if error:
            return _("Настройки не сохранены: {error}. <a href='/switch/{switch_id}'>Вернуться</a>", error=error, switch_id=switch_id), 400

        def stored_key(new_value, current_value, proto):
            # Неизменённый пароль оставляем как есть (тот же шифротекст — журнал не увидит «изменения»)
            if proto == "none":
                return None
            return SECRET_BOX.encrypt(new_value) if new_value else current_value
        snmp_update = (auth.version, auth.user or None, auth.auth_proto,
                       stored_key(f.get("snmp_v3_auth_key"), current["snmp_v3_auth_key"], auth.auth_proto), auth.priv_proto,
                       stored_key(f.get("snmp_v3_priv_key"), current["snmp_v3_priv_key"], auth.priv_proto),
                       auth.context or None, switch_id)

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        if snmp_update:
            c.execute("""UPDATE switches SET snmp_version=?, snmp_v3_user=?, snmp_v3_auth_proto=?, snmp_v3_auth_key=?,
                         snmp_v3_priv_proto=?, snmp_v3_priv_key=?, snmp_v3_context=? WHERE id=?""", snmp_update)
        if port_count and layout and patch_panels is not None:
            port_count = int(port_count)
            c.execute("""
                UPDATE switches SET connections=?, name=?, ports=?, switch_layout=?,
                patch_panels=?, ip_address=?, snmp_community=?, port_types=?, trunk_ports=? WHERE id=?
            """, (connections, name, port_count, layout, patch_panels, ip_address, snmp_community, port_types, trunk_ports, switch_id))
        elif port_count and layout:
            port_count = int(port_count)
            c.execute("""
                UPDATE switches SET connections=?, name=?, ports=?, switch_layout=?,
                ip_address=?, snmp_community=?, port_types=?, trunk_ports=? WHERE id=?
            """, (connections, name, port_count, layout, ip_address, snmp_community, port_types, trunk_ports, switch_id))
        else:
            c.execute("""
                UPDATE switches SET connections=?, name=?, ip_address=?, snmp_community=?, port_types=?, trunk_ports=? WHERE id=?
            """, (connections, name, ip_address, snmp_community, port_types, trunk_ports, switch_id))
        conn.commit()

    after = fetch_switch(switch_id)
    changes, revert_fields = audit.diff_switch(before, after)
    if changes:
        audit.log(DB, "update", actor=current_actor(), switch_id=switch_id, switch_name=after["name"],
                  summary=audit.summarize(changes), changes=changes,
                  revert={"fields": revert_fields} if revert_fields else None)
    return redirect(url_for("switch_view", switch_id=switch_id))


# Таблицы, где хранятся данные коммутатора
SWITCH_TABLES = ("devices", "port_events", "port_traffic", "switch_health", "poe_status", "mac_table",
                 "port_traffic_hourly", "switch_health_hourly")


@app.route("/delete/<int:switch_id>", methods=["POST"])
def delete_switch(switch_id):
    row = fetch_switch(switch_id)
    with sqlite3.connect(DB) as conn:
        devices = conn.execute("SELECT * FROM devices WHERE switch_id=?", (switch_id,)).fetchall()
        dev_cols = [c[1] for c in conn.execute("PRAGMA table_info(devices)")]
        c = conn.cursor()
        c.execute("DELETE FROM switches WHERE id=?", (switch_id,))
        # Вместе с коммутатором удаляем всё, что к нему относится
        for table in SWITCH_TABLES:
            c.execute(f"DELETE FROM {table} WHERE switch_id=?", (switch_id,))
        conn.commit()
    if row:
        # Снимок для восстановления: настройки, подключения, патч-панели, привязанные устройства
        audit.log(DB, "delete", actor=current_actor(), switch_id=switch_id, switch_name=row["name"],
                  summary=_ns(row['ports'], "{n} порт", "{n} порта", "{n} портов") + (f", IP {row['ip_address']}" if row["ip_address"] else ""),
                  revert={"switch": row, "devices": [dict(zip(dev_cols, d)) for d in devices]})
    return redirect(url_for("index"))


# ─────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────

@app.route("/topology")
def topology_view():
    return render_template("topology.html")


# ─────────────────────────────────────────
# СПРАВКА
# ─────────────────────────────────────────

def _help_nav(lang):
    items = helpdocs.articles(lang)
    return [{"key": key, "label": _(label), "articles": [a for a in items if a["category"] == key]}
            for key, label in helpdocs.CATEGORIES if any(a["category"] == key for a in items)]


@app.route("/help")
@app.route("/help/<slug>")
def help_page(slug=None):
    lang = i18n.current_language()
    items = helpdocs.articles(lang)
    if not items:
        abort(404)
    article = helpdocs.get(lang, slug or "getting-started") or items[0]
    if slug and article["slug"] != slug:
        abort(404)
    body, toc = helpdocs.render(article["body"])
    return render_template("help.html", article=article, body=body, toc=toc, nav=_help_nav(lang),
                           search_index=helpdocs.search_index(lang),
                           other_lang=article["lang"] != lang and i18n.LANGUAGES.get(article["lang"]))


@app.route("/api/topology")
def api_topology():
    try:
        return jsonify(collect_topology())
    except Exception as e:
        log.exception(_s("Топология: {error}", error=e))
        return jsonify({"error": str(e), "nodes": [], "links": []}), 500


@app.route("/api/status/<int:switch_id>")
def api_status(switch_id):
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT ip_address FROM switches WHERE id=?", (switch_id,))
        row = c.fetchone()
    if not row or not row[0]:
        return jsonify({"status": "unknown", "message": _("IP не задан")})
    ip = row[0]
    online = ping_host(ip)
    return jsonify({"status": "online" if online else "offline", "ip": ip})


@app.route("/api/status_bulk", methods=["POST"])
def api_status_bulk():
    """Доступность коммутаторов по ping. Адреса — только из базы (браузер присылает лишь номера):
    иначе любой вошедший мог бы заставить сервер пинговать что угодно и сколько угодно."""
    data = request.get_json(silent=True) or {}
    ids = []
    for sw in (data.get("switches") or [])[:5000]:
        try:
            ids.append(int(sw.get("id") if isinstance(sw, dict) else sw))
        except (TypeError, ValueError):
            continue
    results = {str(i): "unknown" for i in ids}
    if not ids:
        return jsonify(results)
    with sqlite3.connect(DB) as conn:
        rows = conn.execute(f"SELECT id, ip_address FROM switches WHERE id IN ({','.join('?' * len(set(ids)))})",
                            list(set(ids))).fetchall()
    targets = [(str(sid), ip) for sid, ip in rows if ip]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        for sid, online in zip([s for s, _ip in targets], pool.map(lambda t: ping_host(t[1]), targets)):
            results[sid] = "online" if online else "offline"
    return jsonify(results)


REACHABILITY_RECHECK_SEC = 3  # пауза перед повторной проверкой, чтобы единичная потеря пакета не давала тревогу


def track_reachability(switch_id, row, ip, auth, result, now):
    """События «коммутатор недоступен / снова доступен» по результату SNMP-опроса.
    Перед тревогой — повторный опрос и ping (по ping видно, сеть это или настройки SNMP).
    Возвращает (результат опроса — возможно, повторного, состояние оповещений коммутатора)."""
    import time
    try:
        state = json.loads(row["alert_state"] or "{}")
    except (ValueError, TypeError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    failed = isinstance(result, dict) and "error" in result
    if failed and not state.get("unreachable"):
        time.sleep(REACHABILITY_RECHECK_SEC)
        result = poll_switch_snmp(ip, auth, row["ports"])
        failed = isinstance(result, dict) and "error" in result

    event = None
    if failed and not state.get("unreachable"):
        state["unreachable"] = now
        reason = str(result["error"]).removeprefix("SNMP: ")
        event = {"event_type": "switch_down", "details": _s("Нет ответа по SNMP ({reason}). ", reason=reason) + (
            _s("По ping отвечает — проверьте настройки SNMP на коммутаторе.") if ping_host(ip)
            else _s("По ping тоже не отвечает."))}
    elif not failed and state.get("unreachable"):
        since = datetime.strptime(state.pop("unreachable"), "%Y-%m-%d %H:%M:%S")
        minutes = (datetime.strptime(now, "%Y-%m-%d %H:%M:%S") - since).total_seconds() / 60
        event = {"event_type": "switch_up", "details": _s("Был недоступен {minutes}", minutes=notify._duration(minutes))}
    if event:
        insert_port_events(switch_id, [{**event, "ifindex": None, "port_name": _s("Коммутатор"),
                                        "port_number": None, "event_time": now}])
        with sqlite3.connect(DB) as conn:
            conn.execute("UPDATE switches SET alert_state=? WHERE id=?", (json.dumps(state), switch_id))
            conn.commit()
    return result, state


def poll_switch_and_log_events(switch_id):
    """
    Опрашивает коммутатор по SNMP, обновляет port_vlans/port_status_snapshot,
    пишет события в port_events при смене статуса портов, сохраняет трафик и health.
    Используется и HTTP-эндпоинтом, и фоновым планировщиком.
    Возвращает результат poll_switch_snmp() (или {"error": ...}).
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM switches WHERE id=?", (switch_id,)).fetchone()
        # Последняя запись трафика по каждому порту — для скорости и загрузки
        prev_traffic = {r["ifindex"]: dict(r) for r in conn.execute("""
            SELECT pt.* FROM port_traffic pt
            JOIN (SELECT ifindex, MAX(id) AS mid FROM port_traffic WHERE switch_id=? GROUP BY ifindex) last
              ON pt.id = last.mid
        """, (switch_id,))}
        # Время хранится с точностью до секунды: по интервалу в 1–2 с скорость ошиблась бы в разы.
        # Если прошлый замер слишком свежий (опрос подряд), сравниваем с более ранним.
        cutoff = (datetime.now() - timedelta(seconds=MIN_RATE_INTERVAL_SEC)).strftime("%Y-%m-%d %H:%M:%S")
        for ifindex in [i for i, r in prev_traffic.items() if (r["timestamp"] or "") > cutoff]:
            older = conn.execute("SELECT * FROM port_traffic WHERE switch_id=? AND ifindex=? AND timestamp<=? "
                                 "ORDER BY id DESC LIMIT 1", (switch_id, ifindex, cutoff)).fetchone()
            if older:
                prev_traffic[ifindex] = dict(older)
            else:
                prev_traffic.pop(ifindex)

    if not row or not row["ip_address"]:
        return {"error": _("IP адрес коммутатора не задан")}

    ip, snapshot_raw = row["ip_address"], row["port_status_snapshot"]
    auth = SnmpAuth.from_row(row)
    config_error = auth.validate()
    if config_error:
        return {"error": config_error}
    result = poll_switch_snmp(ip, auth, row["ports"])
    result, alert_state = track_reachability(switch_id, row, ip, auth, result, now)

    if isinstance(result, dict) and "error" not in result:
        settings = get_settings()
        port_vlans = {}
        for ifindex, info in result.items():
            if isinstance(info, dict) and info.get("vlan"):
                # На схеме порты нумеруются физически; ifIndex — только если номер неизвестен
                port_vlans[str(info.get("port") or ifindex)] = info["vlan"]

        try:
            previous_snapshot = json.loads(snapshot_raw) if snapshot_raw else {}
        except (ValueError, TypeError):
            previous_snapshot = {}

        new_snapshot = diff_and_log_port_events(switch_id, previous_snapshot, result)

        alert_events = []
        rates_by_if = {}  # ifindex → (in, out, interval, errors) для записи в port_traffic
        for ifindex, info in result.items():
            if not isinstance(info, dict) or ifindex not in new_snapshot:
                continue
            snap = new_snapshot[ifindex]
            # PoE кладём в снимок, чтобы окно статистики показывало его без нового SNMP-опроса
            if info.get("poe"):
                snap["poe"] = info["poe"]
            snap.update({"port": info.get("port"), "alias": info.get("alias") or "",
                         "speed": info.get("speed") or 0})

            # Скорость и загрузка относительно предыдущего опроса
            traffic = info.get("traffic") or {}
            prev = prev_traffic.get(ifindex)
            if traffic and prev:
                cur = {"timestamp": now, "bytes_in": _to_sqlite_int(traffic.get("bytes_in", 0)),
                       "bytes_out": _to_sqlite_int(traffic.get("bytes_out", 0)),
                       "errors_in": traffic.get("errors_in", 0), "errors_out": traffic.get("errors_out", 0),
                       "counter_bits": traffic.get("counter_bits", 32)}
                prev = {**prev, "counter_bits": prev.get("counter_bits") or 32}
                rate = compute_traffic_rates([cur, prev])[0]
                err_delta = None
                if rate["errors_in_delta"] is not None and rate["errors_out_delta"] is not None:
                    err_delta = rate["errors_in_delta"] + rate["errors_out_delta"]
                rates_by_if[ifindex] = (rate["in_mbps"], rate["out_mbps"], rate["interval_sec"], err_delta)
                if rate["interval_sec"]:
                    snap["in_mbps"], snap["out_mbps"] = rate["in_mbps"], rate["out_mbps"]
                    if rate["errors_in_delta"] is not None and rate["errors_out_delta"] is not None:
                        snap["errors_delta"] = rate["errors_in_delta"] + rate["errors_out_delta"]
                    if snap["speed"] and rate["in_mbps"] is not None:
                        snap["util"] = round(max(rate["in_mbps"], rate["out_mbps"]) / snap["speed"] * 100, 1)
            elif traffic and isinstance(previous_snapshot.get(ifindex), dict):
                # Опрос сразу после предыдущего: скорость считать не по чему — оставляем последнюю известную
                for key in ("in_mbps", "out_mbps", "util", "errors_delta"):
                    if key in previous_snapshot[ifindex]:
                        snap[key] = previous_snapshot[ifindex][key]
            snap["load_time"] = now

            prev_alerts = (previous_snapshot.get(ifindex) or {}).get("alerts")
            alerts, events = evaluate_port_alerts({**snap, "ifindex": ifindex}, prev_alerts, settings, now)
            if alerts:
                snap["alerts"] = alerts
            alert_events.extend(events)
        insert_port_events(switch_id, alert_events)
        update_mac_table(switch_id, result, now)

        # Сохраняем статистику трафика портов
        with sqlite3.connect(DB) as conn:
            c = conn.cursor()
            for ifindex, info in result.items():
                if isinstance(info, dict) and info.get("traffic"):
                    traffic = info["traffic"]
                    in_mbps, out_mbps, interval, err_delta = rates_by_if.get(ifindex, (None, None, None, None))
                    c.execute("""
                        INSERT INTO port_traffic
                        (switch_id, ifindex, timestamp, bytes_in, bytes_out, packets_in, packets_out,
                         errors_in, errors_out, counter_bits, in_mbps, out_mbps, interval_sec, errors_delta, rate_done)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (switch_id, ifindex, now,
                          _to_sqlite_int(traffic.get("bytes_in", 0)),
                          _to_sqlite_int(traffic.get("bytes_out", 0)),
                          traffic.get("packets_in", 0),
                          traffic.get("packets_out", 0),
                          traffic.get("errors_in", 0),
                          traffic.get("errors_out", 0),
                          traffic.get("counter_bits", 32),
                          in_mbps, out_mbps, interval, err_delta))

            c.execute("UPDATE switches SET port_vlans=?, port_status_snapshot=?, last_poll_time=? WHERE id=?",
                      (json.dumps(port_vlans), json.dumps(new_snapshot), now, switch_id))
            conn.commit()

        # Опрашиваем здоровье коммутатора
        health = poll_switch_health(ip, auth)
        if health:
            state, events = evaluate_health_alerts(health, alert_state, settings, now)
            insert_port_events(switch_id, events)
            with sqlite3.connect(DB) as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO switch_health (switch_id, timestamp, cpu_usage, ram_usage, temperature)
                    VALUES (?, ?, ?, ?, ?)
                """, (switch_id, now, health["cpu_usage"], health["ram_usage"], health["temperature"]))

                c.execute("""
                    UPDATE switches SET cpu_usage=?, ram_usage=?, temperature=?, alert_state=? WHERE id=?
                """, (health["cpu_usage"], health["ram_usage"], health["temperature"], json.dumps(state), switch_id))
                conn.commit()

    return result


@app.route("/api/poll_snmp/<int:switch_id>", methods=["POST"])
def api_poll_snmp(switch_id):
    return jsonify(poll_switch_and_log_events(switch_id))


@app.route("/api/snmp_test/<int:switch_id>", methods=["POST"])
def api_snmp_test(switch_id):
    """Проверка SNMP с сохранёнными настройками: читает sysName и sysDescr."""
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM switches WHERE id=?", (switch_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": _("Коммутатор не найден")}), 404
    if not row["ip_address"]:
        return jsonify({"ok": False, "error": _("IP адрес коммутатора не задан")})
    auth = SnmpAuth.from_row(row)
    error = auth.validate()
    if error:
        return jsonify({"ok": False, "error": error, "auth": auth.describe()})
    name, error = snmp_walk_ex(row["ip_address"], auth, "1.3.6.1.2.1.1.5")
    if not name:
        return jsonify({"ok": False, "error": error or _("коммутатор не вернул sysName"), "auth": auth.describe()})
    descr = snmp_walk(row["ip_address"], auth, "1.3.6.1.2.1.1.1")
    return jsonify({"ok": True, "auth": auth.describe(), "sys_name": snmp_value_text(name[0][1]),
                    "sys_descr": snmp_value_text(descr[0][1]) if descr else ""})


def probe_switch(ip, auth, timeout=2, details=True):
    """Что отвечает по этому адресу: имя, описание, производитель, число портов, коммутатор ли это.
    Сначала один короткий запрос (sysDescr) — недоступные адреса отсеиваются быстро."""
    descr, error = snmp_walk_ex(ip, auth, "1.3.6.1.2.1.1.1", timeout)
    if not descr:
        return {"ok": False, "error": error or _("нет ответа по SNMP")}

    def scalar(oid):
        rows = snmp_walk(ip, auth, oid, timeout)
        return snmp_value_text(rows[0][1]) if rows else ""

    sys_descr = snmp_value_text(descr[0][1])
    out = {"ok": True, "sys_descr": sys_descr, "sys_name": scalar("1.3.6.1.2.1.1.5"),
           "location": scalar("1.3.6.1.2.1.1.6"), "auth": auth.describe()}
    out["vendor"] = discovery.vendor_from_oid(scalar("1.3.6.1.2.1.1.2"))
    out["model"] = discovery.short_model(sys_descr)
    if details:
        names = {oid.rsplit(".", 1)[-1]: snmp_value_text(v) for oid, v in snmp_walk(ip, auth, "1.3.6.1.2.1.2.2.1.2", timeout)}
        types = {}
        for oid, v in snmp_walk(ip, auth, "1.3.6.1.2.1.2.2.1.3", timeout):
            try:
                types[oid.rsplit(".", 1)[-1]] = int(v)
            except (TypeError, ValueError):
                pass
        interfaces = {idx: {"name": names.get(idx, ""), "type": types.get(idx)} for idx in names}
        out["ports"] = len(map_ifindex_to_port(interfaces)) if interfaces else 0
        bridge = snmp_walk(ip, auth, "1.3.6.1.2.1.17.1.2", timeout)  # dot1dBaseNumPorts
        try:
            bridge_ports = int(bridge[0][1]) if bridge else 0
        except (TypeError, ValueError):
            bridge_ports = 0
        # Мост с портами — коммутатор; много Ethernet-портов без BRIDGE-MIB (бывает у v3 без контекста) — тоже
        out["is_switch"] = bridge_ports > 0 or out["ports"] >= 8
        out["lldp_ips"] = discovery.parse_lldp_mgmt_ips(snmp_walk(ip, auth, "1.0.8802.1.1.2.1.4.2.1.3", timeout))
    return out


def _model_label(vendor, model):
    if vendor and model and vendor.split()[0].lower() in model.lower():
        return model
    return " · ".join(x for x in (vendor, model) if x)


@app.route("/api/snmp_probe", methods=["POST"])
def api_snmp_probe():
    """Проверка SNMP по данным формы (ещё не сохранённого коммутатора)."""
    data = request.get_json(silent=True) or {}
    ip = (data.get("ip_address") or "").strip()
    if not ip:
        return jsonify({"ok": False, "error": _("Укажите IP-адрес")})
    auth, error = snmp_auth_from_form(data)
    if error:
        return jsonify({"ok": False, "error": error})
    r = probe_switch(ip, auth, timeout=3)
    if r.get("ok"):
        r["model_label"] = _model_label(r.get("vendor"), r.get("model"))
        r.pop("lldp_ips", None)
        with sqlite3.connect(DB) as conn:
            dup = conn.execute("SELECT id, name FROM switches WHERE ip_address=?", (ip,)).fetchone()
        r["existing"] = {"id": dup[0], "name": dup[1]} if dup else None
    return jsonify(r)


# ─────────────────────────────────────────
# АВТООБНАРУЖЕНИЕ — только администратор
# ─────────────────────────────────────────

@app.route("/discover")
def discover_page():
    nb = netbox.load_config(DB)
    return render_template("discover.html", netbox_ready=bool(nb["url"] and nb["token"]))


def _existing_by_ip():
    with sqlite3.connect(DB) as conn:
        return {ip: (sid, name) for sid, name, ip in
                conn.execute("SELECT id, name, ip_address FROM switches WHERE ip_address IS NOT NULL AND ip_address != ''")}


def _discovery_credentials(data):
    """Список SnmpAuth для перебора: v2c — несколько community через запятую, v3 — одна учётная запись."""
    if (data.get("snmp_version") or "2c") == "3":
        auth, error = snmp_auth_from_form(data)
        return ([auth], [f"v3 · {auth.user}"], None) if not error else (None, None, error)
    names = [c.strip() for c in str(data.get("snmp_community") or "public").split(",") if c.strip()][:5] or ["public"]
    return [SnmpAuth("2c", c) for c in names], [f"v2c · {c}" for c in names], None


@app.route("/api/discovery/start", methods=["POST"])
def api_discovery_start():
    data = request.get_json(silent=True) or {}
    targets, error = discovery.parse_targets(data.get("ranges"))
    if error:
        return jsonify({"error": error}), 400
    creds, labels, error = _discovery_credentials(data)
    if error:
        return jsonify({"error": error}), 400
    job, error = discovery.start(targets, creds, labels, lambda ip, auth: probe_switch(ip, auth, timeout=1),
                                 follow_lldp=bool(data.get("follow_lldp")), actor=current_actor())
    if error:
        return jsonify({"error": error}), 409
    return jsonify(job.public(_existing_by_ip()))


@app.route("/api/discovery/current")
def api_discovery_current():
    job = discovery.running_job()
    return jsonify(job.public(_existing_by_ip()) if job else None)


@app.route("/api/discovery/<job_id>")
def api_discovery_status(job_id):
    job = discovery.get_job(job_id)
    if not job:
        return jsonify({"error": _("Поиск не найден — возможно, сервер перезапускался. Запустите поиск заново")}), 404
    return jsonify(job.public(_existing_by_ip()))


@app.route("/api/discovery/<job_id>/cancel", methods=["POST"])
def api_discovery_cancel(job_id):
    job = discovery.get_job(job_id)
    if job:
        job.cancel.set()
    return jsonify({"ok": True})


@app.route("/api/discovery/<job_id>/add", methods=["POST"])
def api_discovery_add(job_id):
    """Добавить выбранные найденные устройства. body: {items: [{ip, name, ports}]}"""
    job = discovery.get_job(job_id)
    if not job:
        return jsonify({"error": _("Поиск не найден — запустите его заново")}), 404
    found = {f["ip"]: f for f in job.found}
    existing = _existing_by_ip()
    added, skipped = [], []
    for item in (request.get_json(silent=True) or {}).get("items") or []:
        ip = str(item.get("ip") or "")
        f = found.get(ip)
        if not f:
            continue
        if ip in existing:
            skipped.append(_("{ip}: уже есть («{name}»)", ip=ip, name=existing[ip][1]))
            continue
        name = (str(item.get("name") or "").strip() or f.get("sys_name") or ip)[:100]
        ports = _clamp_ports(item.get("ports") or f.get("ports"))
        new_id = create_switch_record(name, ports, ip, job.creds[f["cred"]], "double" if ports >= 24 else "single",
                                      model=_model_label(f.get("vendor"), f.get("model")) or None,
                                      source=_s("Автообнаружение"))
        existing[ip] = (new_id, name)
        added.append({"id": new_id, "name": name, "ip": ip})
    return jsonify({"added": added, "skipped": skipped})


# ─────────────────────────────────────────
# NETBOX — только администратор
# ─────────────────────────────────────────

def _netbox_payload(extra=None):
    cfg = netbox.load_config(DB)
    with sqlite3.connect(DB) as conn:
        linked = conn.execute("SELECT COUNT(*) FROM switches WHERE netbox_id IS NOT NULL").fetchone()[0]
    return {"config": netbox.public_config(cfg), "linked": linked, **(extra or {})}


def _netbox_form_config():
    data = request.get_json(silent=True) or {}
    cfg, error = netbox.sanitize(data.get("config") if isinstance(data.get("config"), dict) else data,
                                 netbox.load_config(DB), SECRET_BOX)
    return data, cfg, error


@app.route("/api/netbox")
def api_netbox_get():
    return jsonify(_netbox_payload())


@app.route("/api/netbox", methods=["POST"])
def api_netbox_save():
    before = netbox.load_config(DB)
    _nb, cfg, error = _netbox_form_config()
    if error:
        return jsonify({"error": error}), 400
    netbox.save_config(DB, cfg)
    changes = []
    yn = lambda v: _("да") if v else _("нет")
    for key, label, fmt in (("url", _("Адрес NetBox"), str), ("verify", _("Проверять сертификат"), yn),
                            ("auto_sync", _("Синхронизация раз в час"), yn)):
        if before[key] != cfg[key]:
            changes.append({"field": label, "before": fmt(before[key]) or "—", "after": fmt(cfg[key]) or "—"})
    if before["token"] != cfg["token"]:
        changes.append({"field": _s("Токен NetBox"), "before": "•••" if before["token"] else "—",
                        "after": _s("изменён") if cfg["token"] else _s("удалён")})
    if changes:
        audit.log(DB, "netbox_settings", actor=current_actor(), summary=audit.summarize(changes), changes=changes)
    return jsonify(_netbox_payload())


@app.route("/api/netbox/test", methods=["POST"])
def api_netbox_test():
    _nb, cfg, error = _netbox_form_config()
    if error:
        return jsonify({"ok": False, "error": error})
    try:
        info = netbox.test_connection(cfg, SECRET_BOX)
        opts = netbox.options(cfg, SECRET_BOX)
    except netbox.NetBoxError as e:
        return jsonify({"ok": False, "error": str(e)})
    return jsonify({"ok": True, **info, "options": opts})


def _switch_rows():
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT id, name, ip_address, netbox_id FROM switches")]


@app.route("/api/netbox/preview", methods=["POST"])
def api_netbox_preview():
    _nb, cfg, error = _netbox_form_config()
    if error:
        return jsonify({"ok": False, "error": error})
    try:
        devices = netbox.fetch_devices(cfg, SECRET_BOX)
    except netbox.NetBoxError as e:
        return jsonify({"ok": False, "error": str(e)})
    # Фильтры запоминаем — в следующий раз откроются те же
    saved = netbox.load_config(DB)
    saved.update({k: cfg[k] for k in ("site", "role", "tag", "only_active", "update_existing")})
    netbox.save_config(DB, saved)
    items = netbox.plan(devices, _switch_rows())
    for it in items:
        it["url"] = netbox.device_url(cfg, it["id"])
    return jsonify({"ok": True, "devices": items})


def _apply_netbox_changes(switch_id, device, actor_note):
    """Обновить имя и IP связанного коммутатора по данным NetBox; изменения — в журнал."""
    before = fetch_switch(switch_id)
    with sqlite3.connect(DB) as conn:
        conn.execute("UPDATE switches SET name=?, ip_address=?, netbox_id=? WHERE id=?",
                     (device["name"], device["ip"] or before["ip_address"], device["id"], switch_id))
        conn.commit()
    after = fetch_switch(switch_id)
    changes, revert = audit.diff_switch(before, after)
    if changes:
        audit.log(DB, "update", actor=actor_note, switch_id=switch_id, switch_name=after["name"],
                  summary=_s("Из NetBox: ") + audit.summarize(changes), changes=changes,
                  revert={"fields": revert} if revert else None)
    return changes


@app.route("/api/netbox/import", methods=["POST"])
def api_netbox_import():
    """body: {ids: [...], update_existing: bool, snmp: {snmp_version, snmp_community, …}}"""
    data = request.get_json(silent=True) or {}
    cfg = netbox.load_config(DB)
    ids = [int(i) for i in data.get("ids") or [] if str(i).isdigit()][:1000]
    if not ids:
        return jsonify({"ok": False, "error": _("Не выбрано ни одного устройства")})
    auth, error = snmp_auth_from_form(data.get("snmp") or {})
    if error:
        return jsonify({"ok": False, "error": error})
    try:
        devices = netbox.fetch_by_ids(cfg, SECRET_BOX, ids)
    except netbox.NetBoxError as e:
        return jsonify({"ok": False, "error": str(e)})
    plan = {p["id"]: p for p in netbox.plan(list(devices.values()), _switch_rows())}
    created, linked, updated, unchanged = [], [], [], 0
    for dev_id in ids:
        p = plan.get(dev_id)
        if not p:
            continue
        if p["match"]:
            sid = p["match"]["switch_id"]
            if data.get("update_existing", True):
                changes = _apply_netbox_changes(sid, p, current_actor())
                (updated if changes else linked).append({"id": sid, "name": p["name"]})
            else:
                with sqlite3.connect(DB) as conn:
                    conn.execute("UPDATE switches SET netbox_id=? WHERE id=?", (dev_id, sid))
                    conn.commit()
                linked.append({"id": sid, "name": p["match"]["switch_name"]})
            continue
        ports = netbox.physical_ports(cfg, SECRET_BOX, dev_id) or p.get("interfaces") or 24
        ports = _clamp_ports(ports)
        new_id = create_switch_record(p["name"][:100], ports, p["ip"], auth, "double" if ports >= 24 else "single",
                                      model=_model_label(p["manufacturer"], p["model"]) or None, netbox_id=dev_id,
                                      source=_s("Импорт из NetBox"))
        created.append({"id": new_id, "name": p["name"]})
    return jsonify({"ok": True, "created": created, "linked": linked, "updated": updated})


def netbox_sync(actor=_("NetBox (синхронизация)")):
    """Обновляет имена и IP связанных коммутаторов. Возвращает итог для отображения."""
    cfg = netbox.load_config(DB)
    with sqlite3.connect(DB) as conn:
        rows = conn.execute("SELECT id, name, netbox_id FROM switches WHERE netbox_id IS NOT NULL").fetchall()
    if not rows:
        return {"checked": 0, "updated": [], "missing": []}
    devices = netbox.fetch_by_ids(cfg, SECRET_BOX, [r[2] for r in rows])
    updated, missing = [], []
    for sid, name, nb_id in rows:
        d = devices.get(nb_id)
        if not d:
            missing.append({"id": sid, "name": name})
            continue
        if _apply_netbox_changes(sid, d, actor):
            updated.append({"id": sid, "name": d["name"]})
    result = {"checked": len(rows), "updated": updated, "missing": missing}
    saved = netbox.load_config(DB)
    saved["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saved["last_sync_result"] = (_("проверено {rows}, обновлено {updated}", rows=len(rows), updated=len(updated)) +
                                 (_(", нет в NetBox: {missing}", missing=len(missing)) if missing else ""))
    netbox.save_config(DB, saved)
    return result


def scheduled_netbox_sync():
    cfg = netbox.load_config(DB)
    if cfg["auto_sync"] and cfg["url"] and cfg["token"]:
        try:
            netbox_sync()
        except netbox.NetBoxError as e:
            saved = netbox.load_config(DB)
            saved["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            saved["last_sync_result"] = _("ошибка: {e}", e=e)
            netbox.save_config(DB, saved)


@app.route("/api/netbox/sync", methods=["POST"])
def api_netbox_sync():
    try:
        result = netbox_sync(actor=current_actor())
    except netbox.NetBoxError as e:
        return jsonify({"ok": False, "error": str(e)})
    return jsonify({"ok": True, **result, **_netbox_payload()})


@app.route("/api/netbox/unlink/<int:switch_id>", methods=["POST"])
def api_netbox_unlink(switch_id):
    with sqlite3.connect(DB) as conn:
        conn.execute("UPDATE switches SET netbox_id=NULL WHERE id=?", (switch_id,))
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/port_load/<int:switch_id>")
def api_port_load(switch_id):
    """Загрузка портов из последнего опроса — для тепловой карты на схеме коммутатора.
    Ключ — номер физического порта на схеме."""
    snapshot = load_port_snapshot(switch_id)
    if snapshot is None:
        return jsonify({"error": _("Коммутатор не найден")}), 404
    ports = {}
    for ifindex, info in snapshot.items():
        if not isinstance(info, dict) or not info.get("port"):
            continue
        ports[str(info["port"])] = {
            "ifindex": ifindex, "name": info.get("name"), "alias": info.get("alias") or "",
            "up": bool(info.get("up")), "speed": info.get("speed") or 0,
            "in_mbps": info.get("in_mbps"), "out_mbps": info.get("out_mbps"), "util": info.get("util"),
            "errors_delta": info.get("errors_delta"), "alerts": info.get("alerts") or {},
            "time": info.get("load_time")
        }
    return jsonify({"util_threshold": get_settings()["alert_util_percent"], "ports": ports})


UPLINK_MAC_THRESHOLD = 5  # если на порту больше MAC-адресов — это, скорее всего, uplink/транк


def _like_escape(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_network(q, limit=50):
    """Поиск по всем коммутаторам: MAC (любой формат), IP, имя хоста,
    описание порта (ifAlias) и названия подключений.
    Возвращает список результатов; более вероятные (не uplink, свежие) — первыми."""
    import re
    q = (q or "").strip()
    if len(q) < 2:
        return []
    hex_only = re.sub(r"[\s:.\-]", "", q.lower())
    is_mac = bool(re.fullmatch(r"[0-9a-f]{4,12}", hex_only)) and bool(re.fullmatch(r"[0-9a-fA-F:.\-\s]+", q))
    is_ip = bool(re.fullmatch(r"\d{1,3}(\.\d{0,3}){1,3}", q))
    text_like = f"%{_like_escape(q.lower())}%"

    results = []
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        switches = {r["id"]: r for r in conn.execute("SELECT * FROM switches")}

        def trunk_ports(sw):
            try:
                return {str(k) for k, v in json.loads(sw["trunk_ports"] or "{}").items() if v}
            except (ValueError, TypeError, AttributeError):
                return set()

        # 1. MAC-адреса из опросов
        where, params = [], []
        if is_mac:
            where.append("replace(mac, ':', '') LIKE ? ESCAPE '\\'")
            params.append(f"%{hex_only}%")
        if is_ip:
            where.append("ip LIKE ? ESCAPE '\\'")
            params.append(f"{_like_escape(q)}%")
        if not is_mac and not is_ip:
            where.append("lower(hostname) LIKE ? ESCAPE '\\'")
            params.append(text_like)
        for r in conn.execute(f"SELECT * FROM mac_table WHERE {' OR '.join(where)} ORDER BY last_seen DESC LIMIT ?",
                              params + [limit * 4]):
            sw = switches.get(r["switch_id"])
            if not sw:
                continue
            uplink = (r["port_mac_count"] or 0) > UPLINK_MAC_THRESHOLD or str(r["port_number"]) in trunk_ports(sw)
            results.append({"kind": "mac", "switch_id": sw["id"], "switch_name": sw["name"],
                            "port": r["port_number"], "port_name": r["port_name"], "mac": r["mac"],
                            "ip": r["ip"] or "", "hostname": r["hostname"] or "", "vlan": r["vlan"] or "",
                            "last_seen": r["last_seen"], "uplink": uplink, "mac_count": r["port_mac_count"] or 0})

        # 2. Устройства, привязанные к портам вручную
        dev_like = f"%{hex_only}%" if is_mac else text_like
        for r in conn.execute("""SELECT * FROM devices WHERE replace(lower(mac), ':', '') LIKE ? ESCAPE '\\'
                                 OR lower(ip) LIKE ? ESCAPE '\\' OR lower(hostname) LIKE ? ESCAPE '\\'
                                 OR lower(notes) LIKE ? ESCAPE '\\' LIMIT ?""",
                              (dev_like, text_like, text_like, text_like, limit)):
            sw = switches.get(r["switch_id"])
            if sw:
                results.append({"kind": "device", "switch_id": sw["id"], "switch_name": sw["name"],
                                "port": r["port_number"], "mac": r["mac"] or "", "ip": r["ip"] or "",
                                "hostname": r["hostname"] or "", "notes": r["notes"] or "",
                                "last_seen": r["last_seen"] or "", "uplink": False})

    # 3. Описания портов с коммутатора и названия подключений (поиск по подстроке, без учёта регистра)
    if not is_mac and not is_ip:
        needle = q.lower()
        for sw in switches.values():
            try:
                snapshot = json.loads(sw["port_status_snapshot"] or "{}")
            except (ValueError, TypeError):
                snapshot = {}
            for info in snapshot.values():
                if isinstance(info, dict) and info.get("port") and needle in (info.get("alias") or "").lower():
                    results.append({"kind": "port", "switch_id": sw["id"], "switch_name": sw["name"],
                                    "port": info["port"], "port_name": info.get("name"), "label": info["alias"],
                                    "source": _("описание на коммутаторе"), "uplink": False})
            try:
                connections = json.loads(sw["connections"] or "{}")
            except (ValueError, TypeError):
                connections = {}
            for port, conn_info in (connections.items() if isinstance(connections, dict) else []):
                name = (conn_info or {}).get("name") if isinstance(conn_info, dict) else None
                if name and needle in name.lower():
                    results.append({"kind": "port", "switch_id": sw["id"], "switch_name": sw["name"],
                                    "port": int(port) if str(port).isdigit() else port, "label": name,
                                    "source": _("подключение в приложении"), "uplink": False})

    # Сначала конечные порты, потом uplink; внутри группы — самые свежие (сортировка устойчивая)
    results.sort(key=lambda r: r.get("last_seen") or "", reverse=True)
    results.sort(key=lambda r: (r["uplink"], {"device": 0, "mac": 1, "port": 2}[r["kind"]]))
    return results[:limit]


@app.route("/api/search")
def api_search():
    return jsonify(search_network(request.args.get("q", "")))


@app.route("/api/set_vlan_color/<int:switch_id>", methods=["POST"])
def api_set_vlan_color(switch_id):
    data = request.json or {}
    vlan_id = str(data.get("vlan_id", "")).strip()
    color = (data.get("color") or "").strip()
    if color and not re.fullmatch(r"#[0-9A-Fa-f]{3,8}|[A-Za-z]{3,20}", color):
        return jsonify({"ok": False, "error": _("Неверный цвет")}), 400
    if not vlan_id:
        return jsonify({"error": _("Не указан VLAN ID")}), 400

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT vlan_colors FROM switches WHERE id=?", (switch_id,))
        row = c.fetchone()
        colors = {}
        if row and row[0]:
            try:
                colors = json.loads(row[0])
            except (ValueError, TypeError):
                colors = {}
        if color:
            colors[vlan_id] = color
        else:
            colors.pop(vlan_id, None)
        c.execute("UPDATE switches SET vlan_colors=? WHERE id=?",
                  (json.dumps(colors), switch_id))
        conn.commit()

    sw = fetch_switch(switch_id) or {}
    audit.log(DB, "vlan_color", actor=current_actor(), switch_id=switch_id, switch_name=sw.get("name"),
              summary=f"VLAN {vlan_id}: {color or _s('цвет сброшен')}")
    return jsonify({"success": True, "vlan_colors": colors})


@app.route("/api/assign_device/<int:switch_id>", methods=["POST"])
def api_assign_device(switch_id):
    data = request.json or {}
    port_number = data.get("port_number")
    ip = data.get("ip", "")
    mac = data.get("mac", "")
    hostname = data.get("hostname", "")
    notes = data.get("notes", "")
    if not port_number:
        return jsonify({"error": _("Не указан номер порта")}), 400

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_online = 1 if ping_host(ip) else 0

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM devices WHERE switch_id=? AND port_number=?",
                  (switch_id, port_number))
        existing = c.fetchone()
        if existing:
            c.execute("""UPDATE devices SET ip=?, mac=?, hostname=?, notes=?, is_online=?, last_seen=?
                WHERE switch_id=? AND port_number=?""",
                (ip, mac, hostname, notes, is_online, now, switch_id, port_number))
        else:
            c.execute("""INSERT INTO devices (switch_id, port_number, ip, mac, hostname, notes, is_online, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (switch_id, port_number, ip, mac, hostname, notes, is_online, now))
        conn.commit()
    sw = fetch_switch(switch_id) or {}
    audit.log(DB, "device_assign", actor=current_actor(), switch_id=switch_id, switch_name=sw.get("name"),
              summary=_s("Порт {port_number}: ", port_number=port_number) + (" · ".join(x for x in (hostname, ip, mac) if x) or _s("устройство")))
    return jsonify({"success": True, "is_online": bool(is_online)})


@app.route("/api/remove_device/<int:switch_id>/<int:port_number>", methods=["POST"])
def api_remove_device(switch_id, port_number):
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        dev = c.execute("SELECT ip, mac, hostname FROM devices WHERE switch_id=? AND port_number=?",
                        (switch_id, port_number)).fetchone()
        c.execute("DELETE FROM devices WHERE switch_id=? AND port_number=?",
                  (switch_id, port_number))
        conn.commit()
    if dev:
        sw = fetch_switch(switch_id) or {}
        audit.log(DB, "device_remove", actor=current_actor(), switch_id=switch_id, switch_name=sw.get("name"),
                  summary=_s("Порт {port_number}: ", port_number=port_number) + (" · ".join(x for x in (dev[2], dev[0], dev[1]) if x) or _s("устройство")))
    return jsonify({"success": True})


@app.route("/api/refresh_devices/<int:switch_id>", methods=["POST"])
def api_refresh_devices(switch_id):
    """Обновляет онлайн-статус всех устройств коммутатора"""
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT id, ip FROM devices WHERE switch_id=?", (switch_id,))
        devices = c.fetchall()

    if not devices:
        return jsonify({})

    results = {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def ping_device(dev_id, ip):
        """Только ping — без записи в БД, безопасно для потоков"""
        online = ping_host(ip) if ip else None
        return dev_id, online

    # Параллельный ping через ThreadPoolExecutor для контроля потоков
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(devices))) as executor:
        futures = [executor.submit(ping_device, d[0], d[1]) for d in devices]
        for future in concurrent.futures.as_completed(futures, timeout=10):
            try:
                dev_id, online = future.result()
                results[dev_id] = online
            except Exception as e:
                log.warning(_s("Ping устройства: {error}", error=e))

    # Последовательная запись в БД — один писатель, изолированная транзакция
    with sqlite3.connect(DB, timeout=10, isolation_level='IMMEDIATE') as conn:
        c = conn.cursor()
        for dev_id, online in results.items():
            if online is not None:
                c.execute("UPDATE devices SET is_online=?, last_seen=? WHERE id=?",
                          (1 if online else 0, now, dev_id))
        conn.commit()

    return jsonify({str(k): v for k, v in results.items()})


@app.route("/api/port_events")
def api_port_events():
    """Список событий port up/down, самые новые первыми."""
    unread_only = request.args.get("unread_only") == "1"
    try:
        limit = int(request.args.get("limit", 50))
    except (ValueError, TypeError):
        limit = 50

    query = """
        SELECT pe.id, pe.switch_id, sw.name, pe.ifindex, pe.port_name,
               pe.event_type, pe.event_time, pe.is_read, pe.details, pe.port_number
        FROM port_events pe
        LEFT JOIN switches sw ON sw.id = pe.switch_id
    """
    if unread_only:
        query += " WHERE pe.is_read = 0"
    query += " ORDER BY pe.id DESC LIMIT ?"

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute(query, (limit,))
        rows = c.fetchall()

    events = [{
        "id": r[0],
        "switch_id": r[1],
        "switch_name": r[2] or f"Switch {r[1]}",
        "ifindex": r[3],
        "port_name": r[4],
        "event_type": r[5],
        "event_time": r[6],
        "is_read": bool(r[7]),
        "details": r[8] or "",
        "port_number": r[9]
    } for r in rows]

    return jsonify(events)


@app.route("/api/port_events/unread_count")
def api_port_events_unread_count():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM port_events WHERE is_read = 0")
        count = c.fetchone()[0]
    return jsonify({"count": count})


@app.route("/api/port_events/mark_read", methods=["POST"])
def api_port_events_mark_read():
    """Помечает события прочитанными. body: {"ids": [1,2,3]} или {"all": true}"""
    data = request.json or {}
    ids = data.get("ids")
    mark_all = data.get("all", False)

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        if mark_all or not ids:
            c.execute("UPDATE port_events SET is_read = 1 WHERE is_read = 0")
        else:
            # Валидация: ids должен быть списком целых чисел
            if not isinstance(ids, list):
                return jsonify({"error": _("ids должен быть массивом")}), 400
            try:
                validated_ids = [int(x) for x in ids]
            except (ValueError, TypeError):
                return jsonify({"error": _("ids должен содержать только числа")}), 400

            if validated_ids:
                placeholders = ",".join("?" for _v in validated_ids)
                c.execute(f"UPDATE port_events SET is_read = 1 WHERE id IN ({placeholders})", validated_ids)
        conn.commit()

    return jsonify({"success": True})


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify(get_settings())


SETTING_LABELS = {
    "poll_enabled": N_("Периодический опрос"), "poll_interval_minutes": N_("Интервал опроса, мин"),
    "alert_util_percent": N_("Порог загрузки порта, %"), "alert_errors_per_poll": N_("Порог ошибок"),
    "alert_cpu_percent": N_("Порог CPU, %"), "alert_temp_c": N_("Порог температуры, °C"),
    "retention_raw_days": N_("Хранить сырые данные, дней"), "retention_hourly_days": N_("Хранить почасовые данные, дней"),
    "retention_events_days": N_("Хранить события, дней"), "backup_auto": N_("Автокопия базы"), "backup_keep": N_("Хранить копий"),
    "server_language": N_("Язык журнала и уведомлений"), "update_check": N_("Проверка обновлений"),
}


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    """Частичное обновление: меняются только переданные ключи."""
    data = request.json or {}
    before = get_settings()
    known = {"poll_enabled", "server_language", "update_check"} | {k for k, *_rest in INT_SETTINGS}
    save_settings({k: v for k, v in data.items() if k in known})
    after = get_settings()
    apply_scheduler_settings()

    def fmt(k, v):
        if isinstance(v, bool):
            return _s("да") if v else _s("нет")
        if k == "server_language":
            return i18n.LANGUAGES.get(v) or _s("как в системе")
        return str(v)
    changes = [{"field": _s(SETTING_LABELS[k]) if k in SETTING_LABELS else k, "before": fmt(k, before[k]), "after": fmt(k, after[k])}
               for k in after if before.get(k) != after.get(k)]
    if changes:
        audit.log(DB, "settings", actor=current_actor(), summary=audit.summarize(changes), changes=changes)
    return jsonify(after)


@app.route("/api/update")
def api_update_status():
    return jsonify(updates.status(DB, APP_VERSION))


@app.route("/api/update/check", methods=["POST"])
def api_update_check():
    """«Проверить сейчас» — работает и при выключенной ежедневной проверке, но не при SWITCHMAP_UPDATE_CHECK=0."""
    if not updates.allowed():
        return jsonify({"ok": False, "error": _("Проверка обновлений отключена в файле настроек сервера")}), 403
    return jsonify(updates.check(DB, APP_VERSION))


@app.route("/api/update/dismiss", methods=["POST"])
def api_update_dismiss():
    """Скрыть напоминание об этой версии (о следующей — напомнит снова)."""
    updates.dismiss(DB, str((request.get_json(silent=True) or {}).get("version", ""))[:20])
    return jsonify({"ok": True})


# ─────────────────────────────────────────
# УВЕДОМЛЕНИЯ (Telegram, почта) — только администратор
# ─────────────────────────────────────────

@app.route("/notifications")
def notifications_page():
    return render_template("notifications.html", groups={k: _(v) for k, v in notify.GROUP_LABELS.items()})


def _notify_payload():
    return {"config": notify.public_config(notify.load_config(DB)), "status": notify.status(DB),
            "default_base_url": request.host_url.rstrip("/")}


@app.route("/api/notify")
def api_notify_get():
    return jsonify(_notify_payload())


@app.route("/api/notify", methods=["POST"])
def api_notify_save():
    before = notify.load_config(DB)
    cfg, error = notify.sanitize(request.get_json(silent=True) or {}, before, SECRET_BOX)
    if error:
        return jsonify({"error": error}), 400
    notify.save_config(DB, cfg)
    changes = notify.describe_changes(before, cfg)
    if changes:
        audit.log(DB, "notify_settings", actor=current_actor(), summary=audit.summarize(changes), changes=changes)
    return jsonify(_notify_payload())


def _notify_form_config():
    """Настройки из формы без сохранения — чтобы проверить их до «Сохранить»."""
    data = request.get_json(silent=True) or {}
    incoming = data.get("config") if isinstance(data.get("config"), dict) else {}
    for ch in notify.CHANNELS:  # проверка одного канала не должна упираться в незаполненный другой
        if isinstance(incoming.get(ch), dict):
            incoming[ch] = {**incoming[ch], "enabled": False}
    return data, notify.sanitize(incoming, notify.load_config(DB), SECRET_BOX)


@app.route("/api/notify/test", methods=["POST"])
def api_notify_test():
    data, (cfg, error) = _notify_form_config()
    channel = data.get("channel")
    if channel not in notify.CHANNELS:
        return jsonify({"error": _("Неизвестный канал")}), 400
    if error:
        return jsonify({"ok": False, "error": error})
    try:
        result, warning, _retry = notify.send(channel, cfg[channel], SECRET_BOX, notify.test_message(cfg["base_url"]))
    except notify.NotifyError as e:
        notify.write_log(DB, channel, False, 0, _("Проверка уведомлений"), str(e))
        return jsonify({"ok": False, "error": str(e)})
    notify.write_log(DB, channel, True, 0, _("Проверка уведомлений"), warning)
    return jsonify({"ok": True, "result": result, "warning": warning})


@app.route("/api/notify/telegram/chats", methods=["POST"])
def api_notify_telegram_chats():
    _cfg_all, (cfg, error) = _notify_form_config()
    if error:
        return jsonify({"ok": False, "error": error})
    tg = cfg["telegram"]
    token = SECRET_BOX.decrypt(tg["token"]) if tg["token"] else ""
    try:
        bot = notify.telegram_bot_info(token, tg["proxy"])
        chats = notify.telegram_find_chats(token, tg["proxy"])
    except notify.NotifyError as e:
        return jsonify({"ok": False, "error": str(e)})
    return jsonify({"ok": True, "bot": bot, "chats": chats})


@app.route("/api/notify/log")
def api_notify_log():
    return jsonify(notify.log_entries(DB, limit=50))


@app.route("/api/notify/retry", methods=["POST"])
def api_notify_retry():
    notify.retry_now(DB)
    report = dispatch_notifications(force=True)
    return jsonify({"report": report, **_notify_payload()})


def _to_sqlite_int(value):
    """SQLite хранит только знаковые 64-битные числа. Counter64 выше 2^63
    сохраняем в дополнительном коде — при расчёте разницы по модулю 2^64 это не мешает."""
    value = int(value or 0)
    return value - 2 ** 64 if value >= 2 ** 63 else value


def _counter_delta(cur, prev, bits):
    """Прирост SNMP-счётчика между двумя опросами или None, если его нельзя посчитать.
    32 бита: уменьшение считаем одним переполнением (2^32 байт — это всего 4 ГБ).
    64 бита: переполнение практически невозможно, уменьшение = сброс счётчика
    (перезагрузка коммутатора или порта) — такой интервал пропускаем."""
    if cur is None or prev is None:
        return None
    modulus = 2 ** bits
    cur_u, prev_u = cur % modulus, prev % modulus
    if cur_u >= prev_u:
        return cur_u - prev_u
    return cur_u + modulus - prev_u if bits == 32 else None


def compute_traffic_rates(rows):
    """rows — записи port_traffic от новых к старым (dict с timestamp, bytes_*, errors_*, counter_bits).
    Для каждой записи, кроме самой старой, добавляет скорость за интервал до предыдущего опроса:
    interval_sec, in_mbps, out_mbps, errors_in_delta, errors_out_delta (None — посчитать нельзя)."""
    for i, row in enumerate(rows):
        rate = {"interval_sec": None, "in_mbps": None, "out_mbps": None,
                "errors_in_delta": None, "errors_out_delta": None}
        prev = rows[i + 1] if i + 1 < len(rows) else None
        if prev is not None:
            try:
                dt = (datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
                      - datetime.strptime(prev["timestamp"], "%Y-%m-%d %H:%M:%S")).total_seconds()
            except (TypeError, ValueError):
                dt = 0
            bits = row.get("counter_bits") or 32
            if dt > 0 and bits == (prev.get("counter_bits") or 32):
                rate["interval_sec"] = dt
                d_in = _counter_delta(row["bytes_in"], prev["bytes_in"], bits)
                d_out = _counter_delta(row["bytes_out"], prev["bytes_out"], bits)
                if d_in is not None and d_out is not None:
                    rate["in_mbps"] = round(d_in * 8 / dt / 1_000_000, 3)
                    rate["out_mbps"] = round(d_out * 8 / dt / 1_000_000, 3)
                for key in ("errors_in", "errors_out"):
                    cur_e, prev_e = row.get(key), prev.get(key)
                    if cur_e is not None and prev_e is not None and cur_e >= prev_e:
                        rate[key + "_delta"] = cur_e - prev_e
        row.update(rate)
    return rows


@app.route("/api/port_traffic/<int:switch_id>/<ifindex>", methods=["GET"])
def api_port_traffic(switch_id, ifindex):
    """История трафика порта за последние N опросов (от новых к старым)
    со скоростью в Мбит/с за каждый интервал между опросами.
    С параметром period (1h, 6h, 24h, 7d, 30d, 1y) — ряд за период по возрастанию времени:
    сырые точки или корзины со средним и пиком (из почасовых агрегатов)."""
    period = request.args.get("period")
    if period:
        if period not in maintenance.PERIODS:
            return jsonify({"error": _("Неизвестный период")}), 400
        return jsonify(maintenance.traffic_series(DB, switch_id, ifindex, period))
    try:
        limit = int(request.args.get("limit", 100))
    except (ValueError, TypeError):
        limit = 100
    limit = max(1, min(limit, 1000))

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        # Берём на одну запись больше: она нужна для скорости у самой старой из N
        c.execute("""
            SELECT timestamp, bytes_in, bytes_out, packets_in, packets_out, errors_in, errors_out, counter_bits
            FROM port_traffic
            WHERE switch_id = ? AND ifindex = ?
            ORDER BY id DESC
            LIMIT ?
        """, (switch_id, ifindex, limit + 1))
        rows = c.fetchall()

    data = compute_traffic_rates([{
        "timestamp": r[0],
        "bytes_in": r[1],
        "bytes_out": r[2],
        "packets_in": r[3],
        "packets_out": r[4],
        "errors_in": r[5],
        "errors_out": r[6],
        "counter_bits": r[7] or 32
    } for r in rows])[:limit]

    return jsonify(data)


@app.route("/api/switch_health/<int:switch_id>", methods=["GET"])
def api_switch_health(switch_id):
    """Получить текущее состояние здоровья коммутатора"""
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT cpu_usage, ram_usage, temperature, last_poll_time
            FROM switches
            WHERE id = ?
        """, (switch_id,))
        row = c.fetchone()

    if not row:
        return jsonify({"error": _("Коммутатор не найден")}), 404

    return jsonify({
        "cpu_usage": row[0] or 0,
        "ram_usage": row[1] or 0,
        "temperature": row[2] or 0,
        "last_poll_time": row[3]
    })


@app.route("/api/switch_health_history/<int:switch_id>", methods=["GET"])
def api_switch_health_history(switch_id):
    """История CPU/RAM/температуры. С параметром period — ряд за период (см. api_port_traffic)."""
    period = request.args.get("period")
    if period:
        if period not in maintenance.PERIODS:
            return jsonify({"error": _("Неизвестный период")}), 400
        return jsonify(maintenance.health_series(DB, switch_id, period))
    try:
        limit = int(request.args.get("limit", 100))
    except (ValueError, TypeError):
        limit = 100
    limit = max(1, min(limit, 1000))

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT timestamp, cpu_usage, ram_usage, temperature
            FROM switch_health
            WHERE switch_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (switch_id, limit))
        rows = c.fetchall()

    data = [{
        "timestamp": r[0],
        "cpu_usage": r[1],
        "ram_usage": r[2],
        "temperature": r[3]
    } for r in rows]

    return jsonify(data)


@app.route("/api/duplicate_macs/<int:switch_id>", methods=["GET"])
def api_duplicate_macs(switch_id):
    """Получить список дублирующихся MAC-адресов"""
    duplicates = detect_duplicate_macs(switch_id)
    return jsonify(duplicates)


def load_port_snapshot(switch_id):
    """Снимок портов из последнего SNMP-опроса: {ifindex: {"up", "name", "poe"?}} или None."""
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT port_status_snapshot FROM switches WHERE id=?", (switch_id,))
        row = c.fetchone()
    if not row:
        return None
    try:
        snapshot = json.loads(row[0]) if row[0] else {}
    except (ValueError, TypeError):
        snapshot = {}
    return snapshot if isinstance(snapshot, dict) else {}


def _ifindex_sort_key(ifindex):
    return (0, int(ifindex)) if str(ifindex).isdigit() else (1, str(ifindex))


@app.route("/api/stats_ports/<int:switch_id>", methods=["GET"])
def api_stats_ports(switch_id):
    """Список портов из последнего SNMP-опроса (для выбора порта в окне статистики)"""
    snapshot = load_port_snapshot(switch_id)
    if snapshot is None:
        return jsonify({"error": _("Коммутатор не найден")}), 404

    ports = [{"ifindex": idx, "name": info.get("name") or f"Port {idx}",
              "port": info.get("port"), "alias": info.get("alias") or ""}
             for idx, info in sorted(snapshot.items(), key=lambda kv: _ifindex_sort_key(kv[0]))
             if isinstance(info, dict)]
    return jsonify(ports)


@app.route("/api/poe_status/<int:switch_id>", methods=["GET"])
def api_poe_status(switch_id):
    """Получить статус PoE для всех портов коммутатора из последнего SNMP-опроса"""
    snapshot = load_port_snapshot(switch_id)
    if snapshot is None:
        return jsonify({"error": _("Коммутатор не найден")}), 404

    poe_data = {}
    for ifindex, info in sorted(snapshot.items(), key=lambda kv: _ifindex_sort_key(kv[0])):
        if isinstance(info, dict) and info.get("poe"):
            poe_data[ifindex] = {
                "port_name": info.get("name"),
                "poe": info["poe"]
            }

    return jsonify(poe_data)


# ─────────────────────────────────────────
# ЖУРНАЛ ИЗМЕНЕНИЙ
# ─────────────────────────────────────────

@app.route("/audit")
def audit_view():
    with sqlite3.connect(DB) as conn:
        switches = conn.execute("SELECT id, name FROM switches ORDER BY name COLLATE NOCASE").fetchall()
    return render_template("audit.html", switches=switches, actions={k: _(v) for k, v in audit.ACTIONS.items()})


@app.route("/api/audit")
def api_audit():
    def to_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    limit = max(1, min(to_int(request.args.get("limit")) or 50, 500))
    return jsonify(audit.entries(DB, switch_id=to_int(request.args.get("switch_id")),
                                 action=request.args.get("action") or None, limit=limit,
                                 before_id=to_int(request.args.get("before_id"))))


def _switch_columns():
    with sqlite3.connect(DB) as conn:
        return [c[1] for c in conn.execute("PRAGMA table_info(switches)")]


@app.route("/api/audit/<int:entry_id>/revert", methods=["POST"])
def api_audit_revert(entry_id):
    """Откат изменения коммутатора или восстановление удалённого."""
    info = audit.get_revert(DB, entry_id)
    if not info:
        return jsonify({"ok": False, "error": _("Запись журнала не найдена")}), 404
    if info["reverted_by"]:
        return jsonify({"ok": False, "error": _("Это изменение уже отменено")}), 409
    data, actor = info["revert"], request.remote_addr

    if info["action"] in ("update", "revert"):
        fields = {k: v for k, v in (data.get("fields") or {}).items() if k in _switch_columns() and k != "id"}
        before = fetch_switch(info["switch_id"])
        if not before:
            return jsonify({"ok": False, "error": _("Коммутатор уже удалён — сначала восстановите его")}), 409
        if not fields:
            return jsonify({"ok": False, "error": _("Нечего откатывать")}), 400
        with sqlite3.connect(DB) as conn:
            conn.execute(f"UPDATE switches SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?",
                         list(fields.values()) + [info["switch_id"]])
            conn.commit()
        after = fetch_switch(info["switch_id"])
        changes, revert_fields = audit.diff_switch(before, after)
        new_id = audit.log(DB, "revert", actor=actor, switch_id=info["switch_id"], switch_name=after["name"],
                           summary=_s("Отмена записи №{entry_id}: ", entry_id=entry_id) + audit.summarize(changes), changes=changes,
                           revert={"fields": revert_fields} if revert_fields else None)
        audit.mark_reverted(DB, entry_id, new_id)
        return jsonify({"ok": True, "switch_id": info["switch_id"], "entry_id": new_id})

    if info["action"] == "delete":
        snap = data.get("switch") or {}
        cols = [c for c in _switch_columns() if c in snap]
        if not snap or "name" not in snap:
            return jsonify({"ok": False, "error": _("В записи нет данных для восстановления")}), 400
        with sqlite3.connect(DB) as conn:
            if conn.execute("SELECT 1 FROM switches WHERE id=?", (snap.get("id"),)).fetchone():
                cols = [c for c in cols if c != "id"]  # id уже занят — получим новый
            cur = conn.execute(f"INSERT INTO switches ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                               [snap[c] for c in cols])
            new_switch_id = cur.lastrowid
            dev_cols = [c[1] for c in conn.execute("PRAGMA table_info(devices)") if c[1] != "id"]
            for d in data.get("devices") or []:
                d = {**d, "switch_id": new_switch_id}
                use = [c for c in dev_cols if c in d]
                conn.execute(f"INSERT INTO devices ({', '.join(use)}) VALUES ({', '.join('?' * len(use))})",
                             [d[c] for c in use])
            conn.commit()
        new_id = audit.log(DB, "restore_switch", actor=actor, switch_id=new_switch_id, switch_name=snap["name"],
                           summary=_s("Из записи №{entry_id}: настройки, подключения, патч-панели, устройства", entry_id=entry_id))
        audit.mark_reverted(DB, entry_id, new_id)
        return jsonify({"ok": True, "switch_id": new_switch_id, "entry_id": new_id})

    return jsonify({"ok": False, "error": _("Это действие нельзя отменить")}), 400


# ─────────────────────────────────────────
# ДАННЫЕ: ОБСЛУЖИВАНИЕ И РЕЗЕРВНЫЕ КОПИИ
# ─────────────────────────────────────────

@app.route("/maintenance")
def maintenance_view():
    return render_template("maintenance.html")


@app.route("/api/maintenance/stats")
def api_maintenance_stats():
    stats = maintenance.db_stats(DB)
    stats["backups"] = maintenance.list_backups(DB)
    stats["settings"] = {k: v for k, v in get_settings().items() if k in {s[0] for s in DATA_SETTINGS}}
    return jsonify(stats)


@app.route("/api/maintenance/run", methods=["POST"])
def api_maintenance_run():
    vacuum = bool((request.json or {}).get("vacuum"))
    return jsonify(run_maintenance(vacuum=vacuum))


@app.route("/api/backups", methods=["POST"])
def api_backup_create():
    name = maintenance.create_backup(DB, "manual")
    maintenance.prune_backups(DB, get_settings()["backup_keep"])
    return jsonify({"ok": True, "name": name, "backups": maintenance.list_backups(DB)})


@app.route("/api/backups/<name>")
def api_backup_download(name):
    path = maintenance.backup_path(DB, name)
    if not path:
        return _("Копия не найдена"), 404
    return send_file(path, as_attachment=True, download_name=name, mimetype="application/octet-stream")


@app.route("/api/backups/<name>", methods=["DELETE"])
def api_backup_delete(name):
    path = maintenance.backup_path(DB, name)
    if not path:
        return jsonify({"ok": False, "error": _("Копия не найдена")}), 404
    os.remove(path)
    return jsonify({"ok": True, "backups": maintenance.list_backups(DB)})


def _restore_from(path, source_label):
    # Пользователи — не часть «данных сети»: если в копии их нет (она старше входа по паролю),
    # возвращаем текущих, иначе после восстановления любой смог бы создать себе администратора.
    with sqlite3.connect(DB) as conn:
        # id тоже возвращаем: по нему сессии узнают пользователя, иначе всех бы выкинуло из системы
        current_users = conn.execute("""SELECT id, username, password_hash, role, disabled, created, last_login,
                                        password_changed, session_version FROM users""").fetchall()
    try:
        safety = maintenance.restore_backup(DB, path)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    migrate_db()  # копия могла быть сделана старой версией приложения
    if security.count_users(DB, admins_only=True) == 0 and current_users:
        with sqlite3.connect(DB) as conn:
            conn.execute("DELETE FROM users")  # в копии могли быть только наблюдатели — заменяем целиком
            conn.executemany("""INSERT INTO users (id, username, password_hash, role, disabled, created, last_login,
                                password_changed, session_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", current_users)
            conn.commit()
    security.encrypt_plaintext_snmp_keys(DB, SECRET_BOX)
    apply_scheduler_settings()
    audit.log(DB, "db_restore", actor=current_actor(),
              summary=_s("Из {source_label}. Текущая база перед этим сохранена: {safety}", source_label=source_label, safety=safety))
    return jsonify({"ok": True, "safety_backup": safety})


@app.route("/api/backups/<name>/restore", methods=["POST"])
def api_backup_restore(name):
    path = maintenance.backup_path(DB, name)
    if not path:
        return jsonify({"ok": False, "error": _("Копия не найдена")}), 404
    return _restore_from(path, _("копии {name}", name=name))


@app.route("/api/backups/upload", methods=["POST"])
def api_backup_upload():
    """Восстановление из загруженного файла .db."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": _("Файл не выбран")}), 400
    tmp = os.path.join(maintenance.backups_dir(DB), f"upload-{datetime.now():%Y%m%d-%H%M%S}.tmp")
    f.save(tmp)
    try:
        return _restore_from(tmp, _("файла {filename}", filename=f.filename))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ─────────────────────────────────────────
# ЭКСПОРТ (Excel, CSV)
# ─────────────────────────────────────────

def _json(value, default):
    try:
        data = json.loads(value) if value else default
    except (TypeError, ValueError):
        return default
    return data if isinstance(data, type(default)) else default


def _r(v, digits=2):
    return round(v, digits) if isinstance(v, (int, float)) else v


def switch_export_tables(switch_id):
    """Таблицы коммутатора: {ключ: (заголовок листа, колонки, строки)}."""
    sw = fetch_switch(switch_id)
    if not sw:
        return None
    snapshot = _json(sw.get("port_status_snapshot"), {})
    by_port = {str(p["port"]): p for p in snapshot.values() if isinstance(p, dict) and p.get("port")}
    conns = _json(sw.get("connections"), {})
    types = _json(sw.get("port_types"), {})
    trunks = _json(sw.get("trunk_ports"), {})
    vlans = _json(sw.get("port_vlans"), {})
    panels = _json(sw.get("patch_panels"), [])
    panel_names = {str(p.get("id")): p.get("name") for p in panels if isinstance(p, dict)}

    def where(c):
        if c.get("patchPanel") is None:
            return _("напрямую")
        return _("{patchPanel}, порт {patch}", patchPanel=panel_names.get(str(c.get('patchPanel')), _('панель {id}', id=c.get('patchPanel'))), patch=c.get('patch'))

    ports = []
    for n in range(1, (sw.get("ports") or 0) + 1):
        p, c, v = by_port.get(str(n), {}), conns.get(str(n)) or {}, vlans.get(str(n)) or {}
        poe = p.get("poe") or {}
        ports.append([n, p.get("name"), p.get("alias"), c.get("name"),
                      "SFP" if types.get(str(n)) == "sfp" else "RJ-45", bool(trunks.get(str(n))),
                      ("up" if p.get("up") else "down") if p else None, p.get("speed") or None,
                      _r(p.get("util"), 1), _r(p.get("in_mbps")), _r(p.get("out_mbps")), p.get("errors_delta"),
                      v.get("id"), v.get("name"), poe.get("state"), _r(poe.get("power_consumed"), 1)])
    connections = [[int(k) if str(k).isdigit() else k, c.get("name"), c.get("color"), where(c)]
                   for k, c in sorted(conns.items(), key=lambda kv: audit._port_sort(kv[0])) if isinstance(c, dict)]
    panel_rows = [[p.get("id"), p.get("name"), p.get("ports"), _("2 строки") if p.get("layout") == "double" else _("1 строка"),
                   _("над коммутатором") if p.get("position") == "above" else _("под коммутатором")]
                  for p in panels if isinstance(p, dict)]
    with sqlite3.connect(DB) as conn:
        manual = conn.execute("""SELECT port_number, mac, ip, hostname, notes, last_seen FROM devices
                                 WHERE switch_id=? ORDER BY port_number""", (switch_id,)).fetchall()
        macs = conn.execute("""SELECT port_number, mac, ip, hostname, vlan, port_mac_count, last_seen, port_name
                               FROM mac_table WHERE switch_id=? ORDER BY port_number, mac""", (switch_id,)).fetchall()
    devices = [[p, m, i, h, None, _("привязано вручную"), None, notes, seen] for p, m, i, h, notes, seen in manual]
    devices += [[p, m, i, h, vl, _("SNMP (таблица MAC)"), (cnt or 0) > UPLINK_MAC_THRESHOLD or bool(trunks.get(str(p))), None, seen]
                for p, m, i, h, vl, cnt, seen, _unused in macs]
    return sw, {
        "ports": (_("Порты"), [_("Порт"), _("Интерфейс"), _("Описание (ifAlias)"), _("Подключение"), _("Тип"), _("Транк"), _("Статус"),
                            _("Скорость, Мбит/с"), _("Загрузка, %"), _("Вход, Мбит/с"), _("Выход, Мбит/с"), _("Ошибки за интервал"),
                            "VLAN", _("Имя VLAN"), "PoE", _("PoE, Вт")], ports),
        "connections": (_("Подключения"), [_("Порт"), _("Назначение"), _("Цвет"), _("Куда")], connections),
        "patch_panels": (_("Патч-панели"), ["ID", _("Название"), _("Портов"), _("Расположение"), _("Позиция")], panel_rows),
        "devices": (_("Устройства"), [_("Порт"), "MAC", "IP", _("Имя хоста"), "VLAN", _("Источник"), "Uplink", _("Заметки"),
                                   _("Последний раз")], devices),
    }


def inventory_export_tables():
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM switches ORDER BY name COLLATE NOCASE").fetchall()
        unread = dict(conn.execute("SELECT switch_id, COUNT(*) FROM port_events WHERE is_read=0 GROUP BY switch_id").fetchall())
        conn.row_factory = None
        macs = conn.execute("""SELECT s.name, m.port_number, m.port_name, m.mac, m.ip, m.hostname, m.vlan,
                                      m.port_mac_count, m.first_seen, m.last_seen
                               FROM mac_table m LEFT JOIN switches s ON s.id = m.switch_id
                               ORDER BY s.name, m.port_number""").fetchall()
        events = conn.execute("""SELECT e.event_time, s.name, e.port_number, e.port_name, e.event_type, e.details, e.is_read
                                 FROM port_events e LEFT JOIN switches s ON s.id = e.switch_id
                                 ORDER BY e.id DESC LIMIT 10000""").fetchall()
    overview = [switch_overview(r, unread) for r in rows]
    switches = [[s["name"], s["ip"], s["snmp"], s["ports"], s["ports_up"] if s["polled"] else None,
                 s["ports_seen"] if s["polled"] else None, _r(s["max_util"], 1), s["alerts"], s["unread"],
                 _r(s["cpu"], 1), _r(s["temperature"], 1), s["last_poll"]] for s in overview]
    labels = notify.LABELS
    log = audit.entries(DB, limit=10000)
    return {
        "switches": (_("Коммутаторы"), [_("Название"), "IP", "SNMP", _("Портов"), _("Порты up"), _("Порты по SNMP"), _("Пиковая загрузка, %"),
                                     _("Активные оповещения"), _("Непрочитанные события"), "CPU, %", _("Температура, °C"),
                                     _("Последний опрос")], switches),
        "macs": (_("MAC-адреса"), [_("Коммутатор"), _("Порт"), _("Интерфейс"), "MAC", "IP", _("Имя хоста"), "VLAN", _("MAC на порту"),
                                _("Впервые"), _("Последний раз")], [list(m) for m in macs]),
        "events": (_("События"), [_("Время"), _("Коммутатор"), _("Порт"), _("Интерфейс / датчик"), _("Событие"), _("Детали"), _("Прочитано")],
                   [[t, s, p, pn, labels.get(et, et), d, bool(rd)] for t, s, p, pn, et, d, rd in events]),
        "audit": (_("Журнал изменений"), [_("Время"), _("Источник"), _("Коммутатор"), _("Действие"), _("Описание")],
                  [[e["time"], e["actor"], e["switch_name"], e["action_label"], e["summary"]] for e in log]),
    }


def _download(data, filename, mimetype):
    import io
    return send_file(io.BytesIO(data), as_attachment=True, download_name=filename, mimetype=mimetype)


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _file_slug(text):
    import re
    return re.sub(r'[\\/:*?"<>|\s]+', "_", str(text or "")).strip("_")[:60] or "switch"


@app.route("/export/switch/<int:switch_id>.xlsx")
def export_switch_xlsx(switch_id):
    res = switch_export_tables(switch_id)
    if not res:
        return _deny(404, _("Коммутатор не найден"))
    sw, tables = res
    data = write_xlsx([Sheet(t, h, r) for t, h, r in tables.values()])
    return _download(data, f"{_file_slug(sw['name'])}_{datetime.now():%Y-%m-%d}.xlsx", XLSX_MIME)


@app.route("/export/switch/<int:switch_id>/<table>.csv")
def export_switch_csv(switch_id, table):
    res = switch_export_tables(switch_id)
    if not res:
        return _deny(404, _("Коммутатор не найден"))
    sw, tables = res
    if table not in tables:
        return _deny(404, _("Страница не найдена"))
    _title, headers, rows = tables[table]
    return _download(write_csv(headers, rows), f"{_file_slug(sw['name'])}_{table}_{datetime.now():%Y-%m-%d}.csv",
                     "text/csv")


@app.route("/export/inventory.xlsx")
def export_inventory_xlsx():
    data = write_xlsx([Sheet(t, h, r) for t, h, r in inventory_export_tables().values()])
    return _download(data, f"switchmap_inventory_{datetime.now():%Y-%m-%d}.xlsx", XLSX_MIME)


@app.route("/export/<table>.csv")
def export_inventory_csv(table):
    tables = inventory_export_tables()
    if table not in tables:
        return _deny(404, _("Страница не найдена"))
    _title, headers, rows = tables[table]
    return _download(write_csv(headers, rows), f"switchmap_{table}_{datetime.now():%Y-%m-%d}.csv",
                     "text/csv")


@app.errorhandler(404)
def not_found(_e):
    return _deny(404, _("Страница не найдена"))


@app.errorhandler(413)
def too_large(_e):
    return _deny(413, _("Файл слишком большой"))


def cli_reset_password(username):
    """python app.py reset-password <имя> — новый пароль, если администратор его забыл.
    Работает только из консоли сервера (у кого есть консоль, у того и так есть доступ к базе)."""
    import getpass
    prepare_database()
    with sqlite3.connect(DB) as conn:
        row = conn.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
    if not row:
        uid, error = None, None
        if input(_s("Пользователя «{name}» нет. Создать администратора? [y/N] ", name=username)).strip().lower() != "y":
            return 1
    password = getpass.getpass(_s("Новый пароль: "))
    if password != getpass.getpass(_s("Повторите: ")):
        print(_s("Пароли не совпадают"))
        return 1
    if row:
        error = security.set_password(DB, row[0], password)
        if not error:
            security.update_user(DB, row[0], disabled=False)
    else:
        uid, error = security.create_user(DB, username, password, "admin")
    if error:
        print(error)
        return 1
    audit.log(DB, "password_change", actor=_s("консоль сервера"), summary=_s("Пароль «{username}» задан из командной строки", username=username))
    print(_s("Готово. Все сессии этого пользователя завершены."))
    return 0


USAGE = N_("""SwitchMap {version}

  switchmap                         запустить сервер
  switchmap reset-password <имя>    задать пароль пользователю (или создать администратора)
  switchmap --version               версия
  switchmap --paths                 где лежат база, настройки и журнал
""")


def _stop_on_sigterm():
    """systemd и службы останавливают процесс сигналом SIGTERM — завершаемся так же, как по Ctrl+C."""
    import signal

    def handler(_signum, _frame):
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGTERM, handler)
    except (ValueError, OSError, AttributeError):
        pass


def serve_forever():
    # Адрес и порт: SWITCHMAP_HOST (по умолчанию 127.0.0.1 — только этот компьютер;
    # 0.0.0.0 — доступ из сети), SWITCHMAP_PORT (по умолчанию 5000).
    host = os.environ.get("SWITCHMAP_HOST", "127.0.0.1")
    port = int(os.environ.get("SWITCHMAP_PORT", "5000"))
    threads = max(4, int(os.environ.get("SWITCHMAP_THREADS", "8")))
    log_file = config.setup_logging(DATA_DIR)
    load_server_language()  # журнал — на языке сервера с первой строки
    log.info(_s("SwitchMap {version}, данные: {data}, настройки: {config}, журнал: {log}", version=APP_VERSION,
                data=DATA_DIR, config=CONFIG_FILE or _s("нет файла (значения по умолчанию)"),
                log=log_file or _s("только консоль")))
    prepare_database()
    init_scheduler()
    log.info(_s("Адрес: {url}", url=f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}"))
    if security.count_users(DB) == 0:
        log.info(_s("Первый запуск: откройте адрес выше и создайте администратора."))
    _stop_on_sigterm()
    try:
        try:
            from waitress import serve
        except ImportError:
            log.warning(_s("waitress не установлен (pip install waitress) — используется встроенный сервер Flask без отладки."))
            # Отладчик Flask (debug=True) не включаем никогда: он позволяет выполнить код на сервере
            app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
        else:
            serve(app, host=host, port=port, threads=threads, ident="SwitchMap")
    except KeyboardInterrupt:
        pass
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        log.info(_s("SwitchMap остановлен"))
    return 0


def main(argv):
    if argv[:1] in (["--version"], ["-V"]):
        print(APP_VERSION)
        return 0
    if argv[:1] in (["--help"], ["-h"], ["help"]):
        print(_s(USAGE, version=APP_VERSION))
        return 0
    if argv[:1] == ["--paths"]:
        load_server_language()
        rows = [(_s("Данные"), DATA_DIR), (_s("База"), DB), (_s("Ключи"), security.secrets_path(DB)),
                (_s("Копии"), maintenance.backups_dir(DB)),
                (_s("Настройки"), CONFIG_FILE or config.default_config_path() + " " + _s("(файла нет)")),
                (_s("Журнал"), os.environ.get("SWITCHMAP_LOG_DIR") or os.path.join(DATA_DIR, "logs"))]
        width = max(len(k) for k, _v in rows) + 2
        print("\n".join(f"{k + ':':<{width}}{v}" for k, v in rows))
        return 0
    if len(argv) >= 2 and argv[0] == "reset-password":
        return cli_reset_password(argv[1])
    if argv:
        print(_s(USAGE, version=APP_VERSION))
        return 2
    return serve_forever()


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
