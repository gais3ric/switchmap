"""Проверка новых версий: разбор ответа, ошибки сети, «скрыть», права, настройка и запрет в switchmap.conf.
Вместо GitHub — локальный сервер. argv: <рабочая папка с тестовой базой>"""
import json, os, sqlite3, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
sys.stdout.reconfigure(encoding='utf-8')
work = sys.argv[1]
os.chdir(work); sys.path[:0] = [ROOT]

fails = []
def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""))
    if not cond:
        fails.append(name)

ANSWERS = {
    "/new": (200, {"tag_name": "v9.1.0", "html_url": "https://github.com/gais3ric/switchmap/releases/tag/v9.1.0"}),
    "/same": (200, {"tag_name": "v1.0.0", "html_url": "https://github.com/gais3ric/switchmap/releases/tag/v1.0.0"}),
    "/evil": (200, {"tag_name": "v9.2.0", "html_url": "javascript:alert(1)"}),
    "/notag": (200, {"name": "что-то"}),
    "/missing": (404, {"message": "Not Found"}),
    "/limit": (403, {"message": "rate limit"}),
}
seen = {}

class Fake(BaseHTTPRequestHandler):
    def do_GET(self):
        seen["ua"] = self.headers.get("User-Agent")
        if self.path == "/text":
            body, code = b"<html>not json</html>", 200
        else:
            code, data = ANSWERS.get(self.path, (500, {}))
            body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_port}"

import updates
import app as m
import security

# ── Сравнение версий
check("v1.2.10 новее 1.2.9", updates.is_newer("v1.2.10", "1.2.9"))
check("1.0.0 не новее 1.0.0", not updates.is_newer("1.0.0", "1.0.0"))
check("сборка из исходников (dev) не предлагает обновлений", not updates.is_newer("9.0.0", "dev"))
check("мусор вместо версии — не новее", not updates.is_newer("latest", "1.0.0"))

m.prepare_database()
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM users"); conn.execute("DELETE FROM app_settings WHERE key LIKE 'update_%'"); conn.commit()
security.create_user(m.DB, "root", "Rootpass123", "admin")
security.create_user(m.DB, "viewer", "Viewpass123", "viewer")
m.APP_VERSION = "1.0.0"

# ── Проверка напрямую
s = updates.check(m.DB, "1.0.0", BASE + "/new")
check("новая версия найдена", s["newer"] and s["latest"] == "9.1.0" and s["show"] and not s["error"], s)
check("ссылка на страницу релиза", s["url"].endswith("/v9.1.0"), s["url"])
check("сервер получил User-Agent с версией", seen.get("ua") == "SwitchMap/1.0.0", seen.get("ua"))
s = updates.check(m.DB, "1.0.0", BASE + "/missing")
check("ошибка (404) — понятный текст, последняя версия не забыта", "404" in s["error"] and s["latest"] == "9.1.0" and s["newer"], s)
s = updates.check(m.DB, "1.0.0", BASE + "/limit")
check("ограничение GitHub (403) — понятный текст", "403" in s["error"], s["error"])
s = updates.check(m.DB, "1.0.0", BASE + "/text")
check("не JSON — ошибка", s["error"] != "", s["error"])
s = updates.check(m.DB, "1.0.0", BASE + "/notag")
check("нет номера версии — ошибка", s["error"] != "", s["error"])
s = updates.check(m.DB, "1.0.0", "http://127.0.0.1:1/nothing")
check("нет связи — ошибка, без падения", s["error"] != "", s["error"])
s = updates.check(m.DB, "1.0.0", BASE + "/evil")
check("небезопасная ссылка заменяется страницей релизов", s["url"] == updates.RELEASES_PAGE, s["url"])
s = updates.check(m.DB, "1.0.0", BASE + "/same")
check("та же версия — обновления нет", not s["newer"] and not s["show"] and s["latest"] == "1.0.0", s)

# ── Интерфейс и API
def csrf_of(c):
    with c.session_transaction() as ss:
        return ss.get("csrf")

def login(user, pw):
    c = m.app.test_client()
    c.get("/login")
    r = c.post("/login", data={"username": user, "password": pw, "csrf_token": csrf_of(c)})
    assert r.status_code == 302, r.status_code
    c.environ_base["HTTP_X_CSRF_TOKEN"] = csrf_of(c)
    c.environ_base["HTTP_ACCEPT_LANGUAGE"] = "ru"
    return c

os.environ["SWITCHMAP_UPDATE_URL"] = BASE + "/new"
admin = login("root", "Rootpass123")
r = admin.post("/api/update/check")
check("«Проверить сейчас» (администратор)", r.status_code == 200 and r.get_json()["newer"], r.get_json())
page = admin.get("/").get_data(as_text=True)
check("администратор видит плашку о новой версии", 'id="updateBar"' in page and "9.1.0" in page)
check("и отметку в меню профиля", 'class="update-dot"' in page)
viewer = login("viewer", "Viewpass123")
vpage = viewer.get("/").get_data(as_text=True)
check("наблюдатель плашку не видит", 'id="updateBar"' not in vpage and "update-dot" not in vpage)
check("наблюдателю API обновлений закрыт", viewer.get("/api/update").status_code == 403
      and viewer.post("/api/update/check").status_code == 403)

r = admin.post("/api/update/dismiss", json={"version": "9.1.0"})
page = admin.get("/").get_data(as_text=True)
check("«Скрыть» убирает плашку этой версии", r.status_code == 200 and 'id="updateBar"' not in page)
check("отметка «доступна 9.1.0» в меню остаётся", "9.1.0" in page)
os.environ["SWITCHMAP_UPDATE_URL"] = BASE + "/evil"
admin.post("/api/update/check")
check("о следующей версии напоминает снова", 'id="updateBar"' in admin.get("/").get_data(as_text=True))

# ── Настройка и запрет в switchmap.conf
check("по умолчанию проверка включена", admin.get("/api/settings").get_json()["update_check"] is True)
r = admin.post("/api/settings", json={"update_check": False})
check("выключается в настройках", r.get_json()["update_check"] is False and m.get_settings()["update_check"] is False)
audit_rows = sqlite3.connect(m.DB).execute("SELECT summary FROM audit_log WHERE action='settings' ORDER BY id DESC LIMIT 1").fetchone()
check("изменение записано в журнал", audit_rows and "обновлений" in audit_rows[0], audit_rows)
admin.post("/api/settings", json={"update_check": True})
os.environ["SWITCHMAP_UPDATE_CHECK"] = "0"
check("SWITCHMAP_UPDATE_CHECK=0: проверка выключена", m.get_settings()["update_check"] is False)
r = admin.post("/api/update/check")
check("SWITCHMAP_UPDATE_CHECK=0: «Проверить сейчас» запрещено", r.status_code == 403, r.status_code)
check("SWITCHMAP_UPDATE_CHECK=0: флажок в настройках недоступен",
      'id="updateCheckInput" disabled' in admin.get("/").get_data(as_text=True))
del os.environ["SWITCHMAP_UPDATE_CHECK"]

srv.shutdown()
print(f"\nИТОГО: {'провалено ' + str(len(fails)) if fails else 'все проверки пройдены'}")
sys.exit(1 if fails else 0)
