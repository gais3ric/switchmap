"""Запуск тестов SwitchMap. Каждый набор работает во временной папке со своей тестовой базой —
рабочая база (switches.db) и ключи (switchmap.secret) не затрагиваются.

    python tests/run_all.py              быстрые тесты (около минуты)
    python tests/run_all.py --live       + опрос по настоящему SNMP (нужен snmpsim, см. tests/README.md)
    python tests/run_all.py --browser    + проверки в браузере (нужны Node.js и Google Chrome)
    python tests/run_all.py --all        всё сразу
    python tests/run_all.py -k notify    только наборы, в названии которых есть «notify»
    -v — показывать вывод каждого набора целиком, --keep — не удалять рабочие папки
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

TESTS = os.path.dirname(os.path.abspath(__file__))
HELPERS = os.path.join(TESTS, "helpers")
BROWSER = os.path.join(TESTS, "browser")
PY = sys.executable

# (название, скрипт, аргументы, нужен snmpsim)
BACKEND = [
    ("stats-existing", "test_stats.py", ["existing"], False),
    ("stats-fresh", "test_stats.py", ["fresh"], False),
    ("rates", "test_rates.py", [], False),
    ("data", "test_data.py", [], False),
    ("security", "test_security.py", [], False),
    ("notify", "test_notify.py", [], False),
    ("config", "test_config.py", [], False),
    ("i18n", "test_i18n.py", [], False),
    ("live", "test_live.py", [], True),
    ("import", "test_import.py", [], True),
]
# (название, сценарий, тестовый сервер, нужен snmpsim)
BROWSER_SUITES = [
    ("e2e", "e2e.js", "serve.py", False),
    ("e2e_core", "e2e_core.js", "serve.py", False),
    ("e2e_auth", "e2e_auth.js", "serve.py", False),
    ("e2e_notify", "e2e_notify.js", "serve_notify.py", False),
    ("e2e_csp", "e2e_csp.js", "serve.py", False),
    ("e2e_features", "e2e_features.js", "serve_live.py", True),
    ("e2e_ui", "e2e_ui.js", "serve_live.py", True),
    ("e2e_data", "e2e_data.js", "serve_live.py", True),
    ("e2e_import", "e2e_import.js", "serve_import.py", True),
]


def env():
    e = dict(os.environ)
    e["PYTHONIOENCODING"] = "utf-8"
    # Тесты проверяют русские тексты: язык сервера — русский (браузер в тестах тоже запускается с --lang=ru-RU)
    e.setdefault("SWITCHMAP_LANG", "ru")
    return e


def seed(work):
    r = subprocess.run([PY, "-I", os.path.join(HELPERS, "seed.py"), work], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env())
    if r.returncode:
        raise RuntimeError("не удалось создать тестовую базу:\n" + r.stdout + r.stderr)


def summary(output):
    total = next((l for l in reversed(output.splitlines()) if "ИТОГО" in l), "")
    fails = [l for l in output.splitlines() if l.startswith(("FAIL", "СЦЕНАРИЙ УПАЛ", "Traceback"))]
    ok = "все проверки пройдены" in total
    return ok, total.strip() or "нет итоговой строки (набор упал?)", fails


def report(name, ok, total, fails, output, verbose, seconds):
    mark = "OK  " if ok else "FAIL"
    print(f"{mark} {name:<16} {seconds:5.1f} с  {total}")
    if verbose or not ok:
        lines = output.splitlines() if verbose else fails or output.splitlines()[-25:]
        for line in lines:
            print("       " + line)


# ─────────── snmpsim ───────────

def find_snmpsim():
    explicit = os.environ.get("SNMPSIM_BIN")
    candidates = [explicit] if explicit else []
    candidates += [shutil.which("snmpsim-command-responder"),
                   os.path.join(TESTS, ".snmpsim", "Scripts", "snmpsim-command-responder.exe"),
                   os.path.join(TESTS, ".snmpsim", "bin", "snmpsim-command-responder")]
    return next((c for c in candidates if c and os.path.exists(c)), None)


def start_snmpsim():
    exe = find_snmpsim()
    if not exe:
        return None, ("snmpsim не найден. Установите его в отдельное окружение:\n"
                      "    python -m venv tests\\.snmpsim\n    tests\\.snmpsim\\Scripts\\pip install snmpsim pysmi cryptography\n"
                      "или укажите путь в переменной SNMPSIM_BIN")
    log = open(os.path.join(tempfile.gettempdir(), "switchmap-snmpsim.log"), "w")
    proc = subprocess.Popen([exe, f"--data-dir={os.path.join(TESTS, 'snmpsim', 'data')}",
                             "--agent-udpv4-endpoint=127.0.0.1:161", "--v3-user=simuser", "--v3-auth-key=authpass123",
                             "--v3-auth-proto=SHA", "--v3-priv-key=privpass123", "--v3-priv-proto=AES"],
                            stdout=log, stderr=subprocess.STDOUT)
    time.sleep(7)
    if proc.poll() is not None:
        return None, f"snmpsim не запустился (порт 161 занят?), журнал: {log.name}"
    return proc, None


# ─────────── браузер ───────────

def find_node():
    return shutil.which("node") or next((p for p in (r"C:\Program Files\nodejs\node.exe",) if os.path.exists(p)), None)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_port(port, proc, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def run_browser_suite(script, server, work, node):
    port = free_port()
    log = open(os.path.join(work, "server.log"), "w", encoding="utf-8")
    srv = subprocess.Popen([PY, "-I", os.path.join(HELPERS, server), work, str(port)], stdout=log, stderr=subprocess.STDOUT,
                           cwd=work, env=env())
    try:
        if not wait_port(port, srv, 120):
            log.close()
            return "СЦЕНАРИЙ УПАЛ: тестовый сервер не запустился\n" + open(log.name, encoding="utf-8", errors="replace").read()[-3000:]
        shots = os.path.join(work, "shots")
        os.makedirs(shots, exist_ok=True)
        r = subprocess.run([node, script, f"http://127.0.0.1:{port}", shots], cwd=BROWSER, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=900)
        return r.stdout + r.stderr
    finally:
        srv.terminate()
        try:
            srv.wait(10)
        except subprocess.TimeoutExpired:
            srv.kill()
        log.close()


def main():
    ap = argparse.ArgumentParser(description="Тесты SwitchMap")
    ap.add_argument("--live", action="store_true", help="тесты с настоящим SNMP (snmpsim)")
    ap.add_argument("--browser", action="store_true", help="проверки в браузере")
    ap.add_argument("--all", action="store_true", help="всё")
    ap.add_argument("-k", default="", help="только наборы, в названии которых есть эта строка")
    ap.add_argument("-v", action="store_true", help="подробный вывод")
    ap.add_argument("--keep", action="store_true", help="не удалять рабочие папки")
    a = ap.parse_args()
    live = a.live or a.all
    browser = a.browser or a.all

    plan = [("py", n, s, args, need) for n, s, args, need in BACKEND if live or not need]
    if browser:
        plan += [("js", n, s, srv, need) for n, s, srv, need in BROWSER_SUITES if live or not need]
    plan = [p for p in plan if a.k in p[1]]
    if not plan:
        print("Нет наборов для запуска")
        return 1

    sim = None
    if any(p[4] for p in plan):
        sim, error = start_snmpsim()
        if error:
            print(error)
            return 1
    node = None
    if any(p[0] == "js" for p in plan):
        node = find_node()
        if not node:
            print("Node.js не найден — установите его с nodejs.org")
            return 1
        if not os.path.isdir(os.path.join(BROWSER, "node_modules")):
            print("Сначала установите зависимости браузерных тестов:  cd tests/browser && npm install")
            return 1

    failed = []
    t_all = time.time()
    try:
        for kind, name, script, extra, _ in plan:
            work = tempfile.mkdtemp(prefix=f"switchmap-{name}-")
            t0 = time.time()
            try:
                seed(work)
                if kind == "py":
                    r = subprocess.run([PY, "-I", os.path.join(TESTS, script), work, *extra], cwd=work, capture_output=True,
                                       text=True, encoding="utf-8", errors="replace", env=env(), timeout=900)
                    output = r.stdout + r.stderr
                else:
                    output = run_browser_suite(script, extra, work, node)
            except Exception as e:
                output = f"СЦЕНАРИЙ УПАЛ: {e}"
            ok, total, fails = summary(output)
            report(name, ok, total, fails, output, a.v, time.time() - t0)
            if not ok:
                failed.append(name)
            if a.keep or not ok:
                print(f"       рабочая папка: {work}") if not ok or a.v else None
            else:
                shutil.rmtree(work, ignore_errors=True)
    finally:
        if sim:
            sim.terminate()

    print(f"\n{'Всё прошло' if not failed else 'Провалены: ' + ', '.join(failed)} — {len(plan)} наборов за {time.time() - t_all:.0f} с")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
