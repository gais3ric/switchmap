"""Безопасность: секреты приложения, шифрование паролей SNMPv3, пользователи, защита от подбора, CSRF.

Секреты хранятся в файле switchmap.secret рядом с базой (не в базе — и не в её резервных копиях):
  flask  — ключ подписи cookie сессии;
  fernet — ключ шифрования паролей SNMPv3.
Если файл потерять, сессии сбросятся, а пароли SNMPv3 придётся ввести заново.
"""
import json
import os
import secrets
import sqlite3
import threading
import time
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

TS = "%Y-%m-%d %H:%M:%S"
ENC_PREFIX = "enc:v1:"
ROLES = {"admin": "Администратор", "viewer": "Наблюдатель"}
MIN_PASSWORD = 8


# ─────────────────────────────────────────
# Секреты и шифрование
# ─────────────────────────────────────────

def secrets_path(db):
    return os.path.join(os.path.dirname(os.path.abspath(db)), "switchmap.secret")


def load_secrets(db):
    """Читает файл секретов, при отсутствии — создаёт."""
    from cryptography.fernet import Fernet
    path = secrets_path(db)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("flask") and data.get("fernet"):
            return data
    data = {"flask": secrets.token_hex(32), "fernet": Fernet.generate_key().decode()}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return data


class SecretBox:
    """Шифрование строк (Fernet: AES-128-CBC + HMAC). Значения в базе — с префиксом enc:v1:."""

    def __init__(self, key):
        from cryptography.fernet import Fernet
        self._f = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, value):
        if value in (None, ""):
            return value
        if str(value).startswith(ENC_PREFIX):
            return value
        return ENC_PREFIX + self._f.encrypt(str(value).encode()).decode()

    def decrypt(self, value):
        """Расшифровывает; значения без префикса (старые) возвращает как есть. Чужой ключ → ''."""
        if not value or not str(value).startswith(ENC_PREFIX):
            return value
        from cryptography.fernet import InvalidToken
        try:
            return self._f.decrypt(str(value)[len(ENC_PREFIX):].encode()).decode()
        except InvalidToken:
            return ""


def encrypt_plaintext_snmp_keys(db, box):
    """Шифрует пароли SNMPv3, сохранённые до появления шифрования. Возвращает число полей."""
    n = 0
    with sqlite3.connect(db) as conn:
        cols = {c[1] for c in conn.execute("PRAGMA table_info(switches)")}
        if not {"snmp_v3_auth_key", "snmp_v3_priv_key"} <= cols:
            return 0
        for sid, auth, priv in conn.execute("SELECT id, snmp_v3_auth_key, snmp_v3_priv_key FROM switches").fetchall():
            new_auth, new_priv = box.encrypt(auth), box.encrypt(priv)
            if (new_auth, new_priv) != (auth, priv):
                conn.execute("UPDATE switches SET snmp_v3_auth_key=?, snmp_v3_priv_key=? WHERE id=?", (new_auth, new_priv, sid))
                n += (new_auth != auth) + (new_priv != priv)
        conn.commit()
    return n


# ─────────────────────────────────────────
# Пользователи
# ─────────────────────────────────────────

def ensure_table(c):
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE COLLATE NOCASE,
            password_hash TEXT,
            role TEXT DEFAULT 'viewer',
            disabled INTEGER DEFAULT 0,
            created TEXT,
            last_login TEXT,
            password_changed TEXT,
            session_version INTEGER DEFAULT 0
        )""")
    # Версия сессий растёт при каждой смене пароля — все выданные ранее сессии становятся недействительными
    if "session_version" not in [c[1] for c in c.execute("PRAGMA table_info(users)")]:
        c.execute("ALTER TABLE users ADD COLUMN session_version INTEGER DEFAULT 0")


def validate_username(name):
    name = (name or "").strip()
    if not (2 <= len(name) <= 64):
        return None, "Имя пользователя — от 2 до 64 символов"
    if any(ch.isspace() for ch in name):
        return None, "Имя пользователя не должно содержать пробелов"
    return name, None


def validate_password(password, username=None):
    if not password or len(password) < MIN_PASSWORD:
        return f"Пароль должен быть не короче {MIN_PASSWORD} символов"
    if username and password.lower() == username.lower():
        return "Пароль не должен совпадать с именем пользователя"
    return None


def count_users(db, admins_only=False):
    with sqlite3.connect(db) as conn:
        sql = "SELECT COUNT(*) FROM users WHERE disabled = 0" + (" AND role = 'admin'" if admins_only else "")
        try:
            return conn.execute(sql).fetchone()[0]
        except sqlite3.OperationalError:
            return 0


_COLS = "id, username, role, disabled, created, last_login, password_changed, session_version"


def _row(r):
    return {"id": r[0], "username": r[1], "role": r[2], "role_label": ROLES.get(r[2], r[2]), "disabled": bool(r[3]),
            "created": r[4], "last_login": r[5], "password_changed": r[6], "session_version": r[7] or 0}


def public(user):
    """Без служебных полей — для отдачи в браузер."""
    return {k: v for k, v in user.items() if k != "session_version"}


def list_users(db):
    with sqlite3.connect(db) as conn:
        rows = conn.execute(f"SELECT {_COLS} FROM users ORDER BY username COLLATE NOCASE").fetchall()
    return [_row(r) for r in rows]


def get_user(db, user_id):
    with sqlite3.connect(db) as conn:
        r = conn.execute(f"SELECT {_COLS} FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row(r) if r else None


def create_user(db, username, password, role="viewer"):
    """Возвращает (id, ошибка)."""
    username, err = validate_username(username)
    if err:
        return None, err
    err = validate_password(password, username)
    if err:
        return None, err
    if role not in ROLES:
        return None, "Неизвестная роль"
    now = datetime.now().strftime(TS)
    try:
        with sqlite3.connect(db) as conn:
            cur = conn.execute("""INSERT INTO users (username, password_hash, role, created, password_changed)
                                  VALUES (?, ?, ?, ?, ?)""", (username, generate_password_hash(password), role, now, now))
            conn.commit()
            return cur.lastrowid, None
    except sqlite3.IntegrityError:
        return None, "Пользователь с таким именем уже есть"


def set_password(db, user_id, password):
    user = get_user(db, user_id)
    if not user:
        return "Пользователь не найден"
    err = validate_password(password, user["username"])
    if err:
        return err
    with sqlite3.connect(db) as conn:
        conn.execute("""UPDATE users SET password_hash = ?, password_changed = ?,
                        session_version = COALESCE(session_version, 0) + 1 WHERE id = ?""",
                     (generate_password_hash(password), datetime.now().strftime(TS), user_id))
        conn.commit()
    return None


def update_user(db, user_id, role=None, disabled=None):
    """Меняет роль/блокировку. Последнего активного администратора понизить или заблокировать нельзя."""
    user = get_user(db, user_id)
    if not user:
        return "Пользователь не найден"
    new_role = role if role is not None else user["role"]
    new_disabled = bool(disabled) if disabled is not None else user["disabled"]
    if new_role not in ROLES:
        return "Неизвестная роль"
    losing_admin = user["role"] == "admin" and not user["disabled"] and (new_role != "admin" or new_disabled)
    if losing_admin and count_users(db, admins_only=True) <= 1:
        return "Нельзя понизить или заблокировать последнего администратора"
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE users SET role = ?, disabled = ? WHERE id = ?", (new_role, int(new_disabled), user_id))
        conn.commit()
    return None


def delete_user(db, user_id):
    user = get_user(db, user_id)
    if not user:
        return "Пользователь не найден"
    if user["role"] == "admin" and not user["disabled"] and count_users(db, admins_only=True) <= 1:
        return "Нельзя удалить последнего администратора"
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    return None


# Хэш-приманка: проверка пароля для несуществующего пользователя занимает столько же времени
_DUMMY_HASH = generate_password_hash("dummy-password-for-timing")


def authenticate(db, username, password):
    """Возвращает пользователя (dict) или None."""
    with sqlite3.connect(db) as conn:
        r = conn.execute(f"SELECT {_COLS}, password_hash FROM users WHERE username = ? COLLATE NOCASE",
                         ((username or "").strip(),)).fetchone()
    if not r:
        check_password_hash(_DUMMY_HASH, password or "")
        return None
    if not check_password_hash(r[8], password or "") or r[3]:
        return None
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().strftime(TS), r[0]))
        conn.commit()
    return _row(r[:8])


# ─────────────────────────────────────────
# Защита от подбора пароля
# ─────────────────────────────────────────

class LoginThrottle:
    """Не больше MAX_FAILS неудачных попыток за WINDOW секунд с одного IP для одного имени —
    затем блокировка на LOCK секунд. Хранится в памяти процесса."""
    MAX_FAILS, WINDOW, LOCK = 5, 600, 300

    def __init__(self):
        self._fails = {}
        self._locked = {}
        self._lock = threading.Lock()

    def _key(self, ip, username):
        return (ip or "?", (username or "").strip().lower())

    def locked_for(self, ip, username):
        """Сколько секунд ещё действует блокировка (0 — нет)."""
        with self._lock:
            until = self._locked.get(self._key(ip, username), 0)
            return max(0, int(until - time.time()))

    def fail(self, ip, username):
        key, now = self._key(ip, username), time.time()
        with self._lock:
            attempts = [t for t in self._fails.get(key, []) if now - t < self.WINDOW] + [now]
            self._fails[key] = attempts
            if len(attempts) >= self.MAX_FAILS:
                self._locked[key] = now + self.LOCK
                self._fails[key] = []
                return True
        return False

    def success(self, ip, username):
        key = self._key(ip, username)
        with self._lock:
            self._fails.pop(key, None)
            self._locked.pop(key, None)


# ─────────────────────────────────────────
# CSRF
# ─────────────────────────────────────────

def new_csrf_token():
    return secrets.token_urlsafe(32)


def csrf_matches(expected, provided):
    return bool(expected) and bool(provided) and secrets.compare_digest(str(expected), str(provided))
