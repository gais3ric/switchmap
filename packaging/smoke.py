"""Проверка собранной или установленной программы «снаружи», по HTTP.

    python packaging/smoke.py --exe dist/switchmap/switchmap.exe [--snmp]   запустить с пустой папкой данных
    python packaging/smoke.py --url http://127.0.0.1:5000 [--snmp]          уже работающая служба
    --password P  пароль администратора (если он уже создан — вход, иначе создание)
    --snmp        ещё и опрос SNMP v2c/v3 (нужен snmpsim на 127.0.0.1:161, см. tests/README.md)
    --expect-version X.Y.Z   версия, которую должна показать программа
    --skip-ping   не проверять ping (контейнер без ICMP)
Код выхода 0 — всё прошло. Используется в GitHub Actions после сборки и после установки пакета.
"""
import argparse
import http.cookiejar
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

results = []


def check(name, cond, info=""):
    results.append(bool(cond))
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""), flush=True)


class Client:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ""

    def request(self, path, data=None, json_body=None):
        headers = {}
        if json_body is not None:
            data = json.dumps(json_body).encode()
            headers = {"Content-Type": "application/json", "X-CSRF-Token": self.csrf}
        elif data is not None:
            data = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(self.base + path, data=data, headers=headers)
        try:
            with self.opener.open(req, timeout=30) as resp:
                body = resp.read()
                status, url = resp.status, resp.url
        except urllib.error.HTTPError as e:
            body, status, url = e.read(), e.code, e.url
        text = body.decode("utf-8", "replace")
        m = re.search(r'name="csrf-token" content="([^"]*)"', text) or re.search(r'name="csrf_token" value="([^"]*)"', text)
        if m and m.group(1):
            self.csrf = m.group(1)
        return status, url, text, body

    def json(self, path, body):
        status, _, text, _ = self.request(path, json_body=body)
        try:
            return status, json.loads(text)
        except ValueError:
            return status, {"raw": text[:300]}


def wait_up(base, proc=None, timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc is not None and proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(base + "/login", timeout=3):
                return True
        except urllib.error.HTTPError:
            return True
        except OSError:
            time.sleep(0.5)
    return False


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_checks(base, password, snmp, expect_version, ping=True, existing=False):
    c = Client(base)
    status, url, text, _ = c.request("/login")
    if existing:
        check("после обновления пользователи на месте (нет повторной настройки)", "/setup" not in url, url)
    if "/setup" in url:
        c.request("/setup")
        status, url, text, _ = c.request("/setup", data={"username": "admin", "password": password, "password2": password,
                                                          "csrf_token": c.csrf})
        check("первый запуск: администратор создан", status == 200 and "/setup" not in url and "/login" not in url, url)
    else:
        status, url, text, _ = c.request("/login", data={"username": "admin", "password": password, "csrf_token": c.csrf})
        check("вход администратора", status == 200 and "/login" not in url, url)

    for page in ("/", "/topology", "/maintenance", "/audit", "/users", "/notifications", "/discover", "/help",
                 "/help/snmp-vendors"):
        status, _, text, _ = c.request(page)
        check(f"страница {page}", status == 200 and "Traceback" not in text and "</html>" in text, status)
    status, _, text, _ = c.request("/")
    if expect_version:
        check(f"программа показывает версию {expect_version}", expect_version in text)
    scripts = re.findall(r'<script[^>]+src="(/static/[^"]+)"', text)
    bad = [s for s in scripts if c.request(s)[0] != 200]
    check("скрипты и стили отдаются", scripts and not bad, bad)
    status, _, _, body = c.request("/static/vendor/d3.min.js")
    check("библиотеки внутри программы (без интернета)", status == 200 and len(body) > 100000, status)
    c.json("/api/language", {"language": "en"})
    status, _, text, _ = c.request("/")
    check("переводы внутри программы (английский интерфейс)", "Switches" in text and "Коммутаторы" not in text)
    status, _, text, _ = c.request("/help/getting-started")
    check("справка на английском", status == 200 and "Getting started" in text, status)
    c.json("/api/language", {"language": ""})

    if snmp:
        status, r = c.json("/api/snmp_probe", {"ip_address": "127.0.0.1", "snmp_version": "2c", "snmp_community": "public"})
        check("SNMP v2c: опрос симулятора", r.get("ok") and r.get("ports"), r)
        status, r = c.json("/api/snmp_probe", {"ip_address": "127.0.0.1", "snmp_version": "3", "snmp_v3_user": "simuser",
                                               "snmp_v3_auth_proto": "SHA", "snmp_v3_auth_key": "authpass123",
                                               "snmp_v3_priv_proto": "AES128", "snmp_v3_priv_key": "privpass123",
                                               "snmp_v3_context": "public"})
        check("SNMP v3 (SHA/AES): опрос симулятора", r.get("ok") and r.get("ports"), r)
        status, url, _, _ = c.request("/add", data={"name": "Smoke", "ports": "10", "ip_address": "127.0.0.1",
                                                    "snmp_version": "2c", "snmp_community": "public", "has_patch": "0",
                                                    "csrf_token": c.csrf})
        ids = [int(x) for x in re.findall(r'/switch/(\d+)', c.request("/")[2])]
        check("коммутатор добавлен", status == 200 and ids, url)
        if ids:
            status, r = c.json(f"/api/poll_snmp/{max(ids)}", {})
            check("полный опрос коммутатора (порты, трафик, события)", status == 200 and "error" not in r,
                  {k: r.get(k) for k in ("error", "ports") if k in r} if isinstance(r, dict) else r)
    if ping:
        status, r = c.json("/api/status_bulk", {"switches": [{"id": 1, "ip": "127.0.0.1"}]})
        check("ping работает (127.0.0.1 доступен)", r.get("1") == "online", r)
    status, r = c.json("/api/backups", {})
    check("резервная копия создаётся", r.get("ok"), r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe")
    ap.add_argument("--url")
    ap.add_argument("--password", default="Smoke-test-123")
    ap.add_argument("--snmp", action="store_true")
    ap.add_argument("--expect-version")
    ap.add_argument("--skip-ping", action="store_true", help="контейнер без ping/ICMP")
    ap.add_argument("--existing", action="store_true", help="после обновления: администратор уже должен быть")
    a = ap.parse_args()
    if bool(a.exe) == bool(a.url):
        ap.error("укажите --exe или --url")

    proc = data = None
    if a.exe:
        r = subprocess.run([a.exe, "--version"], capture_output=True, text=True)
        check("--version", r.returncode == 0 and (not a.expect_version or r.stdout.strip() == a.expect_version),
              r.stdout.strip() or r.stderr[-300:])
        data = tempfile.mkdtemp(prefix="switchmap-smoke-")
        port = free_port()
        env = dict(os.environ, SWITCHMAP_DATA=data, SWITCHMAP_PORT=str(port),
                   SWITCHMAP_CONFIG=os.path.join(data, "нет-такого.conf"))
        log = open(os.path.join(data, "console.log"), "wb")
        proc = subprocess.Popen([a.exe], env=env, cwd=tempfile.gettempdir(), stdout=log, stderr=subprocess.STDOUT)
        base = f"http://127.0.0.1:{port}"
    else:
        base = a.url
    try:
        up = wait_up(base, proc)
        check("сервер отвечает", up, base)
        if up:
            run_checks(base, a.password, a.snmp, a.expect_version, ping=not a.skip_ping, existing=a.existing)
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()
            log.close()
            log_file = os.path.join(data, "logs", "switchmap.log")
            text = open(log_file, encoding="utf-8", errors="replace").read() if os.path.isfile(log_file) else ""
            check("журнал создан, в нём нет ошибок", text and "Traceback" not in text and " ERROR " not in text,
                  text[-1500:] or open(log.name, encoding="utf-8", errors="replace").read()[-1500:])
    failed = results.count(False)
    print(f"\nИТОГО: {'провалено ' + str(failed) if failed else 'все проверки пройдены'} ({len(results)} проверок)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
