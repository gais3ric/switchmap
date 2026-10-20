"""Тесты: файл настроек, папка данных, журнал работы, режим WAL, запуск сервера отдельным процессом.
argv: <рабочая папка с тестовой базой>"""
import os, shutil, socket, sqlite3, subprocess, sys, time, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
sys.stdout.reconfigure(encoding='utf-8')
work = sys.argv[1]
os.chdir(work); sys.path[:0] = [ROOT]

fails = []
def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""))
    if not cond:
        fails.append(name)

import config

# ── Разбор файла настроек
text = "﻿# комментарий\nSWITCHMAP_PORT = 5055\nSWITCHMAP_HOST=\"0.0.0.0\"\n\nбез знака равно\nSWITCHMAP_HTTPS='1'\n"
parsed = config.parse_config(text)
check("файл настроек: КЛЮЧ=значение, кавычки, комментарии, BOM",
      parsed == {"SWITCHMAP_PORT": "5055", "SWITCHMAP_HOST": "0.0.0.0", "SWITCHMAP_HTTPS": "1"}, parsed)

conf = os.path.join(work, "test.conf")
with open(conf, "w", encoding="utf-8") as f:
    f.write("SWITCHMAP_TEST_A=из файла\nSWITCHMAP_TEST_B=из файла\n")
os.environ["SWITCHMAP_TEST_A"] = "из окружения"
config.load(conf)
check("переменные окружения важнее файла", os.environ["SWITCHMAP_TEST_A"] == "из окружения"
      and os.environ["SWITCHMAP_TEST_B"] == "из файла")
check("нет файла — не ошибка", config.load(os.path.join(work, "нет.conf")) is None)

# ── Пути по умолчанию
check("из исходников: данные в текущей папке", config.default_data_dir() == os.getcwd())
config.FROZEN = True
if os.name == "nt":
    check("установленная программа (Windows): данные в ProgramData",
          config.default_data_dir().lower().endswith(r"programdata\switchmap"), config.default_data_dir())
    check("установленная программа (Windows): настройки там же",
          config.default_config_path().lower().endswith(r"programdata\switchmap\switchmap.conf"))
else:
    check("установленная программа (Linux): /var/lib/switchmap и /etc/switchmap",
          config.default_data_dir() == "/var/lib/switchmap" and config.default_config_path() == "/etc/switchmap/switchmap.conf")
config.FROZEN = False

# ── Сервер отдельным процессом: своя папка данных и файл настроек, журнал, WAL
def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

data = os.path.join(work, "данные с пробелом")
port = free_port()
conf = os.path.join(work, "switchmap.conf")
with open(conf, "w", encoding="utf-8") as f:
    f.write(f"# настройки теста\nSWITCHMAP_PORT={port}\nSWITCHMAP_DATA={data}\n")
env = dict(os.environ, SWITCHMAP_CONFIG=conf, PYTHONIOENCODING="utf-8")
env.pop("SWITCHMAP_DATA", None)
other = os.path.join(work, "чужая папка")  # запуск не из папки данных — как у службы
os.makedirs(other, exist_ok=True)
app_py = os.path.join(ROOT, "app.py")

r = subprocess.run([sys.executable, app_py, "--version"], capture_output=True, text=True, encoding="utf-8", env=env, cwd=other)
check("--version", r.returncode == 0 and r.stdout.strip(), r.stdout + r.stderr)
r = subprocess.run([sys.executable, app_py, "--paths"], capture_output=True, text=True, encoding="utf-8", env=env, cwd=other)
check("--paths показывает папку данных и файл настроек", r.returncode == 0 and data in r.stdout and conf in r.stdout,
      r.stdout + r.stderr)
r = subprocess.run([sys.executable, app_py, "no-such-command"], capture_output=True, text=True, encoding="utf-8", env=env, cwd=other)
check("неизвестная команда — подсказка и код 2", r.returncode == 2 and "reset-password" in r.stdout)

proc = subprocess.Popen([sys.executable, app_py], env=env, cwd=other, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    status, t0 = None, time.time()
    while time.time() - t0 < 60 and status is None:
        if proc.poll() is not None:
            break
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/login", timeout=2) as resp:
                status = resp.status
        except OSError:
            time.sleep(0.5)
    check("сервер запустился на порту из файла настроек", status == 200, status)
    db = os.path.join(data, "switches.db")
    check("база, ключи и копии — в папке данных, не в текущей",
          os.path.isfile(db) and os.path.isfile(os.path.join(data, "switchmap.secret"))
          and os.path.isdir(os.path.join(data, "backups")) and not os.path.exists(os.path.join(other, "switches.db")),
          os.listdir(data) if os.path.isdir(data) else "нет папки")
    with sqlite3.connect(db) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    check("база в режиме WAL", mode == "wal", mode)
    log_file = os.path.join(data, "logs", "switchmap.log")
    log_text = open(log_file, encoding="utf-8").read() if os.path.isfile(log_file) else ""
    check("журнал работы в logs/switchmap.log", "SwitchMap" in log_text and f":{port}" in log_text, log_text[-500:])
finally:
    proc.terminate()
    try:
        proc.wait(15)
    except subprocess.TimeoutExpired:
        proc.kill()
    out = proc.stdout.read().decode("utf-8", "replace") if proc.stdout else ""
check("в консоль тоже пишется", "SwitchMap" in out, out[-300:])

# ── Резервные копии и восстановление в режиме WAL
import maintenance as mt
db = os.path.join(work, "switches.db")  # тестовая база из seed.py
with sqlite3.connect(db) as conn:
    mt.enable_wal(conn)
    conn.execute("UPDATE switches SET name='До копии' WHERE id=1")
name = mt.create_backup(db, "manual")
path = mt.backup_path(db, name)
with sqlite3.connect(path) as conn:
    bmode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    bname = conn.execute("SELECT name FROM switches WHERE id=1").fetchone()[0]
check("копия — обычный самостоятельный файл (без WAL) с последними изменениями", bmode == "delete" and bname == "До копии",
      (bmode, bname))
check("рядом с копией нет -wal/-shm", not [f for f in os.listdir(mt.backups_dir(db)) if f.endswith(("-wal", "-shm"))])
check("копия проходит проверку перед восстановлением", mt.validate_backup_file(path) is None)
with sqlite3.connect(db) as conn:
    conn.execute("UPDATE switches SET name='После копии' WHERE id=1")
mt.restore_backup(db, path)
with sqlite3.connect(db) as conn:
    restored = conn.execute("SELECT name FROM switches WHERE id=1").fetchone()[0]
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
check("восстановление: данные из копии, база снова в WAL", restored == "До копии" and mode == "wal", (restored, mode))

print(f"\nИТОГО: {'провалено ' + str(len(fails)) if fails else 'все проверки пройдены'}")
sys.exit(1 if fails else 0)
