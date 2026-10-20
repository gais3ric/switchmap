"""Где лежат данные и настройки запуска, журнал работы.

Порядок поиска настроек: переменные окружения → файл настроек → значения по умолчанию.
Файл настроек — строки «КЛЮЧ=значение» (как у systemd EnvironmentFile), # — комментарий:
    Windows (установленная программа): C:\\ProgramData\\SwitchMap\\switchmap.conf
    Linux (пакет deb/rpm):             /etc/switchmap/switchmap.conf
    из исходников:                     switchmap.conf в текущей папке
    другой путь:                       переменная SWITCHMAP_CONFIG
Папка данных (база, ключи, резервные копии, журнал) — SWITCHMAP_DATA, по умолчанию
C:\\ProgramData\\SwitchMap, /var/lib/switchmap или текущая папка (из исходников).
"""
import logging
import logging.handlers
import os
import sys

FROZEN = bool(getattr(sys, "frozen", False))  # собранная программа (PyInstaller), а не запуск из исходников
WINDOWS = os.name == "nt"

KNOWN_KEYS = ("SWITCHMAP_HOST", "SWITCHMAP_PORT", "SWITCHMAP_HTTPS", "SWITCHMAP_DATA", "SWITCHMAP_LOG_DIR",
              "SWITCHMAP_LOG_LEVEL", "SWITCHMAP_LOG_CONSOLE", "SWITCHMAP_THREADS", "SWITCHMAP_TELEGRAM_API")


def _program_data():
    return os.path.join(os.environ.get("PROGRAMDATA") or r"C:\ProgramData", "SwitchMap")


def default_config_path():
    if os.environ.get("SWITCHMAP_CONFIG"):
        return os.environ["SWITCHMAP_CONFIG"]
    if not FROZEN:
        return os.path.abspath("switchmap.conf")
    return os.path.join(_program_data(), "switchmap.conf") if WINDOWS else "/etc/switchmap/switchmap.conf"


def default_data_dir():
    if not FROZEN:
        return os.getcwd()
    return _program_data() if WINDOWS else "/var/lib/switchmap"


def parse_config(text):
    """«КЛЮЧ=значение» построчно; кавычки вокруг значения снимаются, пустые строки и # пропускаются."""
    values = {}
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load(path=None):
    """Читает файл настроек в os.environ. Уже заданные переменные окружения важнее файла."""
    path = path or default_config_path()
    loaded = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8-sig") as f:
            loaded = parse_config(f.read())
        for key, value in loaded.items():
            os.environ.setdefault(key, value)
    return path if loaded or os.path.isfile(path) else None


def data_dir():
    path = os.path.abspath(os.environ.get("SWITCHMAP_DATA") or default_data_dir())
    os.makedirs(path, exist_ok=True)
    drop_root_to_owner(path)
    return path


def drop_root_to_owner(path):
    """Linux: запуск от root (например, «sudo switchmap reset-password admin») — работаем от имени владельца
    папки данных (пользователь службы switchmap). Иначе файлы базы стали бы принадлежать root и служба
    не смогла бы в них писать."""
    if WINDOWS or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return False
    st = os.stat(path)
    if st.st_uid == 0:
        return False
    import pwd
    try:
        user = pwd.getpwuid(st.st_uid)
        os.initgroups(user.pw_name, st.st_gid)
        home = user.pw_dir
    except KeyError:
        os.setgroups([])
        home = path
    os.setgid(st.st_gid)
    os.setuid(st.st_uid)
    os.environ["HOME"] = home
    return True


def resource_dir():
    """Папка с templates/ и static/: внутри собранной программы или рядом с исходниками."""
    return getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))


def version():
    """Версия: файл VERSION (кладётся при сборке) или «dev»."""
    try:
        with open(os.path.join(resource_dir(), "VERSION"), encoding="utf-8") as f:
            return f.read().strip() or "dev"
    except OSError:
        return "dev"


_logging_ready = False


def setup_logging(data, console=True):
    """Журнал работы: logs/switchmap.log в папке данных (5 файлов по 5 МБ) и, если есть, консоль."""
    global _logging_ready
    if _logging_ready:
        return None
    _logging_ready = True
    level = getattr(logging, os.environ.get("SWITCHMAP_LOG_LEVEL", "INFO").upper(), logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(level)
    log_dir = os.environ.get("SWITCHMAP_LOG_DIR") or os.path.join(data, "logs")
    log_file = None
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "switchmap.log")
        handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5,
                                                       encoding="utf-8", delay=True)
        handler.setFormatter(fmt)
        root.addHandler(handler)
    except OSError as e:
        print(f"Журнал в файл недоступен ({log_dir}): {e}", file=sys.stderr)
        log_file = None
    # Служба Windows пишет консоль в свой файл — там журнал не нужен второй раз (SWITCHMAP_LOG_CONSOLE=0)
    console = console and os.environ.get("SWITCHMAP_LOG_CONSOLE", "1") != "0"
    if console and sys.stderr is not None:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(fmt)
        root.addHandler(stream)
    # Шум сторонних библиотек — только предупреждения
    for name in ("apscheduler", "pysnmp", "urllib3"):
        logging.getLogger(name).setLevel(max(level, logging.WARNING))
    return log_file
