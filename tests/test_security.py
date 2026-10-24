"""Безопасность: вход, роли, CSRF, сессии, шифрование SNMPv3, заголовки. argv: <рабочая папка с тестовой базой>"""
import io, os, re, sqlite3, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
HELPERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers")
sys.stdout.reconfigure(encoding='utf-8')
app_dir = sys.argv[1]
os.chdir(app_dir); sys.path[:0] = [ROOT, HELPERS]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as m
import security
import maintenance as mt

fails = []
def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""))
    if not cond:
        fails.append(name)

m.prepare_database()
m.app.config["PROPAGATE_EXCEPTIONS"] = False
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM users"); conn.execute("DELETE FROM audit_log"); conn.commit()

def csrf_of(c):
    with c.session_transaction() as s:
        return s.get("csrf")

def fresh():
    c = m.app.test_client()
    c.get("/login")
    return c

def do_login(c, user, pw, remember=False):
    data = {"username": user, "password": pw, "csrf_token": csrf_of(c)}
    if remember:
        data["remember"] = "1"
    return c.post("/login", data=data)

def authed(user, pw):
    c = fresh()
    r = do_login(c, user, pw)
    assert r.status_code == 302, r.status_code
    c.environ_base["HTTP_X_CSRF_TOKEN"] = csrf_of(c)
    return c

# ── Первый запуск
c = m.app.test_client()
r = c.get("/")
check("без пользователей → /setup", r.status_code == 302 and r.headers["Location"].endswith("/setup"), r.headers.get("Location"))
check("/login без пользователей → /setup", c.get("/login").headers.get("Location", "").endswith("/setup"))
r = c.post("/setup", data={"username": "root", "password": "short", "password2": "short", "csrf_token": csrf_of(c)})
check("короткий пароль администратора отклонён", r.status_code == 400 and "не короче 8" in r.get_data(as_text=True))
r = c.post("/setup", data={"username": "root", "password": "Rootpass123", "password2": "other12345", "csrf_token": csrf_of(c)})
check("несовпадающие пароли отклонены", r.status_code == 400)
r = c.post("/setup", data={"username": "root", "password": "Rootpass123", "password2": "Rootpass123", "csrf_token": csrf_of(c)})
check("создан первый администратор и выполнен вход", r.status_code == 302 and c.get("/").status_code == 200)
c2 = m.app.test_client()
check("повторный /setup недоступен", c2.get("/setup").headers.get("Location", "").endswith("/login"))
r = c2.post("/setup", data={"username": "evil", "password": "Evilpass123", "password2": "Evilpass123", "csrf_token": "x"})
check("POST /setup при существующих пользователях не создаёт админа", security.count_users(m.DB) == 1)

# ── Без входа всё закрыто
anon = m.app.test_client()
r = anon.get("/switch/1")
check("страница без входа → /login?next=", r.status_code == 302 and "/login?next=/switch/1" in r.headers["Location"], r.headers.get("Location"))
for url in ("/api/switch_health/1", "/api/search?q=aa", "/export/inventory.xlsx", "/api/backups/x.db", "/api/users"):
    r = anon.get(url)
    check(f"без входа {url} → 401 JSON", r.status_code == 401 and r.is_json, r.status_code)
check("статика доступна без входа", anon.get("/static/ui.css").status_code == 200)

# ── Вход: ошибки, блокировка, открытый редирект, фиксация сессии
c = fresh()
r = do_login(c, "root", "wrong-password")
check("неверный пароль → 401 и сообщение", r.status_code == 401 and "Неверное имя" in r.get_data(as_text=True))
check("неизвестный пользователь → то же сообщение", do_login(c, "nobody", "whatever1").status_code == 401)
for _ in range(4):
    do_login(c, "root", "wrong-password")
r = do_login(c, "root", "Rootpass123")
check("после 5 неудач вход заблокирован даже с верным паролем", r.status_code == 401 and "Слишком много" in r.get_data(as_text=True))
check("неудачные входы — в журнале", any(e["action"] == "login_failed" for e in m.audit.entries(m.DB, limit=20)))
m.login_throttle.success("127.0.0.1", "root")  # снимаем блокировку для следующих проверок
c = fresh()
before = csrf_of(c)
r = c.post("/login", data={"username": "root", "password": "Rootpass123", "csrf_token": before, "next": "//evil.example/x"})
check("next=//evil → редирект на главную (не на чужой сайт)", r.status_code == 302 and r.headers["Location"] in ("/", "http://localhost/"), r.headers["Location"])
check("при входе выдаётся новый CSRF-токен (новая сессия)", csrf_of(c) != before)
c3 = fresh()
r = c3.post("/login", data={"username": "root", "password": "Rootpass123", "csrf_token": csrf_of(c3), "next": "/switch/1?port=3"})
check("next внутри приложения сохраняется", r.headers["Location"].endswith("/switch/1?port=3"))

# ── CSRF
admin = authed("root", "Rootpass123")
token = admin.environ_base.pop("HTTP_X_CSRF_TOKEN")
check("POST без CSRF → 400", admin.post("/api/settings", json={"retention_raw_days": 6}).status_code == 400)
check("POST с чужим CSRF → 400", admin.post("/api/settings", json={"retention_raw_days": 6}, headers={"X-CSRF-Token": "forged"}).status_code == 400)
check("POST с верным CSRF → 200", admin.post("/api/settings", json={"retention_raw_days": 6}, headers={"X-CSRF-Token": token}).status_code == 200)
r = admin.post("/update/1", data={"name": "x", "connections": "{}"})
check("форма без csrf_token → 400", r.status_code == 400)
check("выход тоже требует CSRF (нельзя разлогинить чужой ссылкой)", admin.post("/logout").status_code == 400)
admin.environ_base["HTTP_X_CSRF_TOKEN"] = token

# ── Управление пользователями
r = admin.post("/api/users", json={"username": "viewer1", "password": "Viewpass123", "role": "viewer"}).get_json()
check("создан наблюдатель", r["ok"] and r["user"]["role"] == "viewer", r)
viewer_id = r["user"]["id"]
check("дубликат имени (без учёта регистра) → 400", admin.post("/api/users", json={"username": "VIEWER1", "password": "Viewpass123"}).status_code == 400)
check("короткий пароль → 400", admin.post("/api/users", json={"username": "v2", "password": "123"}).status_code == 400)
check("пароль = имя → 400", admin.post("/api/users", json={"username": "samesame", "password": "samesame"}).status_code == 400)
root_id = [u for u in admin.get("/api/users").get_json() if u["username"] == "root"][0]["id"]
check("себя понизить нельзя", admin.patch(f"/api/users/{root_id}", json={"role": "viewer"}).status_code == 400)
check("себя удалить нельзя", admin.delete(f"/api/users/{root_id}").status_code == 400)
check("последнего администратора нельзя понизить (на уровне модуля)", security.update_user(m.DB, root_id, role="viewer") is not None)
check("в списке пользователей нет хэшей паролей", "password_hash" not in admin.get("/api/users").get_data(as_text=True))

# ── Права наблюдателя
viewer = authed("viewer1", "Viewpass123")
check("наблюдатель видит главную, коммутатор, журнал, данные", all(viewer.get(u).status_code == 200 for u in ("/", "/switch/1", "/audit", "/maintenance", "/topology")))
check("наблюдатель может экспортировать", viewer.get("/export/inventory.xlsx").status_code == 200)
check("наблюдатель может отметить события", viewer.post("/api/port_events/mark_read", json={"all": True}).status_code == 200)
check("наблюдатель может опросить по SNMP", viewer.post("/api/poll_snmp/1").status_code == 200)
for method, url, body in (("post", "/update/1", None), ("post", "/delete/1", None), ("post", "/api/settings", {"poll_enabled": True}),
                          ("post", "/api/backups", None), ("post", "/api/maintenance/run", {}), ("post", "/api/audit/1/revert", None),
                          ("post", "/api/set_vlan_color/1", {"vlan_id": "1", "color": "#fff"}), ("post", "/api/users", {"username": "x"}),
                          ("post", "/api/assign_device/1", {"port_number": 1}), ("post", "/add", None)):
    r = getattr(viewer, method)(url, json=body) if body is not None else getattr(viewer, method)(url)
    check(f"наблюдатель: {method.upper()} {url} → 403", r.status_code == 403, r.status_code)
for url in ("/users", "/api/users", "/api/backups/anything.db"):
    check(f"наблюдатель: GET {url} → 403", viewer.get(url).status_code == 403)
html = viewer.get("/").get_data(as_text=True)
check("у наблюдателя на странице класс role-viewer", 'class="role-viewer' in html)

# ── Сессии: смена пароля, блокировка, бездействие, «запомнить меня»
r = viewer.post("/api/account/password", json={"current": "wrong", "password": "Newview1234"})
check("смена своего пароля: неверный текущий → 400", r.status_code == 400)
other = authed("viewer1", "Viewpass123")  # вторая сессия того же пользователя
r = viewer.post("/api/account/password", json={"current": "Viewpass123", "password": "Newview1234"})
check("смена своего пароля", r.get_json()["ok"])
check("текущая сессия продолжает работать", viewer.get("/").status_code == 200)
check("другая сессия того же пользователя завершена", other.get("/").status_code == 302)
check("вход с новым паролем", do_login(fresh(), "viewer1", "Newview1234").status_code == 302)
admin.post(f"/api/users/{viewer_id}/password", json={"password": "Resetpass123"})
check("пароль задан администратором → сессии пользователя завершены", viewer.get("/").status_code == 302)
viewer = authed("viewer1", "Resetpass123")
admin.patch(f"/api/users/{viewer_id}", json={"disabled": True})
check("блокировка → сессия завершена", viewer.get("/").status_code == 302)
check("заблокированный не может войти", do_login(fresh(), "viewer1", "Resetpass123").status_code == 401)
admin.patch(f"/api/users/{viewer_id}", json={"disabled": False})
viewer = authed("viewer1", "Resetpass123")
with viewer.session_transaction() as s:
    s["seen"] = time.time() - 13 * 3600
check("13 часов бездействия без «запомнить» → вход заново", viewer.get("/").status_code == 302)
c = fresh()
r = do_login(c, "viewer1", "Resetpass123", remember=True)
cookie = r.headers.get("Set-Cookie", "")
check("«запомнить меня» — постоянная cookie на 30 дней", "Expires=" in cookie, cookie[:80])
with c.session_transaction() as s:
    s["seen"] = time.time() - 13 * 3600
check("с «запомнить» 13 часов бездействия не разлогинивают", c.get("/").status_code == 200)
r = do_login(fresh(), "root", "Rootpass123")
cookie = r.headers.get("Set-Cookie", "")
check("cookie сессии: HttpOnly и SameSite=Lax, без Expires", "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Expires=" not in cookie, cookie)
check("удаление пользователя", admin.delete(f"/api/users/{viewer_id}").get_json()["ok"])
acts = {e["action"] for e in m.audit.entries(m.DB, limit=100)}
check("действия с пользователями — в журнале", {"user_create", "user_update", "user_delete", "password_change"} <= acts, acts)
check("в журнале — имя пользователя", any(e["actor"].startswith("root ·") for e in m.audit.entries(m.DB, limit=20)))

# ── Шифрование паролей SNMPv3
sw = m.fetch_switch(1)
form = {"csrf_token": token, "name": sw["name"], "connections": sw["connections"] or "{}", "port_types": "{}", "trunk_ports": "{}",
        "ip_address": "10.0.0.1", "snmp_community": "public", "snmp_version": "3", "snmp_v3_user": "u1",
        "snmp_v3_auth_proto": "SHA", "snmp_v3_auth_key": "Authsecret99", "snmp_v3_priv_proto": "AES128",
        "snmp_v3_priv_key": "Privsecret99", "snmp_v3_context": ""}
check("сохранение SNMPv3", admin.post("/update/1", data=form).status_code == 302)
with sqlite3.connect(m.DB) as conn:
    raw = conn.execute("SELECT snmp_v3_auth_key, snmp_v3_priv_key FROM switches WHERE id=1").fetchone()
check("пароли SNMPv3 в базе зашифрованы", all(v.startswith("enc:v1:") for v in raw) and "Authsecret99" not in "".join(raw), raw[0][:20])
auth = m.SnmpAuth.from_row(m.fetch_switch(1))
check("для опроса пароли расшифровываются", auth.auth_key == "Authsecret99" and auth.priv_key == "Privsecret99")
form2 = dict(form, snmp_v3_auth_key="", snmp_v3_priv_key="")
admin.post("/update/1", data=form2)
with sqlite3.connect(m.DB) as conn:
    raw2 = conn.execute("SELECT snmp_v3_auth_key, snmp_v3_priv_key FROM switches WHERE id=1").fetchone()
check("пустое поле — пароль не меняется (тот же шифротекст)", raw2 == raw)
page = admin.get("/switch/1").get_data(as_text=True)
check("пароли не попадают на страницу", "Authsecret99" not in page and "enc:v1:" not in page)
backup = mt.create_backup(m.DB, "manual")
with sqlite3.connect(mt.backup_path(m.DB, backup)) as conn:
    braw = conn.execute("SELECT snmp_v3_auth_key FROM switches WHERE id=1").fetchone()[0]
check("в резервной копии пароли тоже зашифрованы", braw.startswith("enc:v1:"))
with sqlite3.connect(m.DB) as conn:
    conn.execute("UPDATE switches SET snmp_v3_auth_key='PlainOld123' WHERE id=1"); conn.commit()
n = security.encrypt_plaintext_snmp_keys(m.DB, m.SECRET_BOX)
check("старые открытые пароли шифруются при запуске", n == 1 and m.SnmpAuth.from_row(m.fetch_switch(1)).auth_key == "PlainOld123")
from cryptography.fernet import Fernet
check("чужой ключ не расшифровывает (пустая строка, без падения)", security.SecretBox(Fernet.generate_key()).decrypt(raw[0]) == "")
check("файл ключей рядом с базой, вне backups", os.path.exists(security.secrets_path(m.DB))
      and not any(f.endswith(".secret") for f in os.listdir(mt.backups_dir(m.DB))))

# ── Восстановление старой копии без пользователей
old = os.path.join(app_dir, "old_nousers.db")
src = sqlite3.connect(m.DB); dst = sqlite3.connect(old); src.backup(dst); src.close()
dst.execute("DROP TABLE users"); dst.commit(); dst.close()
r = admin.post("/api/backups/upload", data={"file": (open(old, "rb"), "old.db")}, content_type="multipart/form-data")
check("восстановление копии без пользователей", r.status_code == 200 and r.get_json()["ok"], r.get_json())
check("администратор сохранён (нет окна для захвата /setup)", security.count_users(m.DB, admins_only=True) >= 1
      and anon.get("/setup").headers.get("Location", "").endswith("/login"))
check("сессия администратора продолжает работать", admin.get("/").status_code == 200)

# ── Заголовки и прочее
r = admin.get("/")
h = r.headers
check("CSP, X-Frame-Options, nosniff, Referrer-Policy", "default-src 'self'" in h.get("Content-Security-Policy", "")
      and "frame-ancestors 'none'" in h["Content-Security-Policy"] and h.get("X-Frame-Options") == "DENY"
      and h.get("X-Content-Type-Options") == "nosniff" and h.get("Referrer-Policy") == "same-origin")
check("страницы не кэшируются", h.get("Cache-Control") == "no-store")

# ── Защита от внедрения кода (CSP без 'unsafe-inline')
csp = h["Content-Security-Policy"]
script_src = next(p for p in csp.split(";") if p.strip().startswith("script-src "))
nonce = re.search(r"'nonce-([\w-]+)'", script_src)
check("script-src: без 'unsafe-inline' и 'unsafe-eval', с nonce", "unsafe-inline" not in script_src
      and "unsafe-eval" not in script_src and nonce, script_src)
check("обработчики в атрибутах запрещены (script-src-attr 'none')", "script-src-attr 'none'" in csp)
check("скрипты только со своего сервера (никаких CDN в CSP)", "https://" not in csp and "http://" not in csp, csp)
import hashlib, base64
bad_sri = []
for key, (fname, sri) in m.VENDOR_SCRIPTS.items():
    data = open(os.path.join(ROOT, "static", "vendor", fname), "rb").read()
    if "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode() != sri:
        bad_sri.append(fname)
check("библиотеки в static/vendor совпадают с контрольными суммами", not bad_sri, bad_sri)
with m.app.test_request_context():
    d3_url = m.vendor_scripts()["d3"][0]
r_vendor = admin.get(d3_url)
check("библиотека отдаётся сервером", r_vendor.status_code == 200 and len(r_vendor.data) > 100000)
nonce2 = re.search(r"'nonce-([\w-]+)'", admin.get("/").headers["Content-Security-Policy"])
check("nonce новый на каждый ответ", nonce2 and nonce2.group(1) != nonce.group(1))
check("JSON-ответы без nonce", "nonce-" not in admin.get("/api/settings").headers["Content-Security-Policy"])

anon = m.app.test_client()
pages = {"/": admin, "/switch/1": admin, "/switch/2": admin, "/topology": admin, "/audit": admin, "/maintenance": admin,
         "/users": admin, "/notifications": admin, "/discover": admin, "/add": admin, "/no-such-page": admin, "/login": anon}
problems = []
for url, client in pages.items():
    resp = client.get(url)
    html = resp.get_data(as_text=True)
    page_nonce = re.search(r"'nonce-([\w-]+)'", resp.headers["Content-Security-Policy"])
    for tag in re.findall(r"<script\b[^>]*>", html):
        if "src=" in tag:
            if "https://" in tag or "http://" in tag:
                problems.append(f"{url}: скрипт со стороннего сервера: {tag}")
            if "/vendor/" in tag and 'integrity="sha384-' not in tag:
                problems.append(f"{url}: библиотека без integrity: {tag}")
        elif not page_nonce or f'nonce="{page_nonce.group(1)}"' not in tag:
            problems.append(f"{url}: встроенный скрипт без nonce: {tag}")
    for attr in re.findall(r"""<[^>]+\son[a-z]+\s*=\s*["'][^>]*>""", html):
        problems.append(f"{url}: обработчик в атрибуте: {attr[:80]}")
    if "javascript:" in html:
        problems.append(f"{url}: ссылка javascript:")
check(f"страницы ({len(pages)}): встроенные скрипты с nonce, библиотеки свои и с integrity, нет onclick и javascript:", not problems, problems[:5])
check("на страницах нет ссылок на CDN (шрифты, стили, скрипты)", not any(
    re.search(r"""<(script|link|img|iframe)\b[^>]*\s(src|href)=["']https?://""", c.get(u).get_data(as_text=True))
    for u, c in pages.items()))

home = admin.get("/").get_data(as_text=True)
check("склонение: «52 порта», «48 портов», на странице коммутатора тоже", "52 порта" in home and "48 портов" in home
      and "52 портов" not in home and "52 порта" in admin.get("/switch/1").get_data(as_text=True))

static_js = "".join(open(os.path.join(ROOT, "static", n), encoding="utf-8").read() for n in ("app.js", "switch_view.js", "events.js"))
code_only = re.sub(r"//[^\n]*", "", static_js)
check("скрипты не создают onclick в разметке", not re.search(r"""\son[a-z]+\s*=\s*["'`]""", code_only))
check("статика кэшируется", "no-store" not in (admin.get("/static/ui.css").headers.get("Cache-Control") or ""))
r = admin.get("/no-such-page")
check("404 — страница ошибки", r.status_code == 404 and "Не найдено" in r.get_data(as_text=True))
check("API 404 — JSON", admin.get("/api/no-such").is_json)
src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
check("debug=True больше нигде не включается", not re.search(r"app\.run\([^)]*debug\s*=\s*True", src))
check("по умолчанию слушаем только 127.0.0.1", 'os.environ.get("SWITCHMAP_HOST", "127.0.0.1")' in src)

# ── ping: адреса только из базы, без «ключей» команды и без неограниченного числа потоков
pinged = []
orig_ping = m.ping_host
m.ping_host = lambda ip, timeout=1: pinged.append(ip) or True
orig_walk = m.snmp_walk
m.snmp_walk = lambda ip, auth, oid, timeout=3: pinged.append("snmp:" + ip) or [("1.3.6.1.2.1.1.3.0", 1)]
with sqlite3.connect(m.DB) as conn:
    conn.execute("UPDATE switches SET ip_address='10.9.9.9' WHERE id=1")
    conn.commit()
v = authed("viewer1", "Viewpass123") if security.get_user(m.DB, viewer_id) and not security.get_user(m.DB, viewer_id)["disabled"] else admin
r = v.post("/api/status_bulk", json={"switches": [{"id": 1, "ip": "8.8.8.8"}, {"id": 999999, "ip": "1.1.1.1"}]}).get_json()
check("status_bulk: адрес берётся из базы, а не из запроса", pinged == ["snmp:10.9.9.9"] and r == {"1": "online", "999999": "unknown"},
      (pinged, r))
pinged.clear()
t0 = time.time()
r = v.post("/api/status_bulk", json={"switches": [{"id": i} for i in range(20000)]})
check("status_bulk: огромный список не запускает тысячи проверок", r.status_code == 200 and len(pinged) <= 1
      and time.time() - t0 < 10, (len(pinged), round(time.time() - t0, 1)))
# VPN/прокси в режиме TUN отвечает на ping за любой адрес — без ответа по SNMP это не «онлайн»
m.snmp_walk = lambda ip, auth, oid, timeout=3: []
r = v.post("/api/status_bulk", json={"switches": [1]}).get_json()
check("ping есть, SNMP нет — «только ping», а не «онлайн»", r == {"1": "ping"}, r)
m.ping_host = lambda ip, timeout=1: False
check("нет ни SNMP, ни ping — недоступен", v.get("/api/status/1").get_json().get("status") == "offline")
m.snmp_walk = orig_walk
m.ping_host = orig_ping
check("ping не принимает «-ключи» и мусор вместо адреса",
      m.ping_host("-t") is False and m.ping_host("1.2.3.4; rm -rf /") is False and m.ping_host("--help") is False)

r = admin.post("/api/set_vlan_color/1", json={"vlan_id": "10", "color": "red;}</style><script>alert(1)</script>"})
check("цвет VLAN: только #RGB или имя цвета", r.status_code == 400, r.status_code)
r = admin.post("/api/set_vlan_color/1", json={"vlan_id": "10", "color": "#3fa9f5"})
check("цвет VLAN #RGB сохраняется", r.status_code == 200, r.status_code)
sv = open(os.path.join(ROOT, "static", "switch_view.js"), encoding="utf-8").read()
check("имя VLAN с коммутатора экранируется", "escapeHtml(vlans[id])" in sv)

import xlsx
csv_text = xlsx.write_csv(["a"], [["=HYPERLINK(\"http://evil\")"], ["@SUM(1)"], ["-"], [-5]]).decode("utf-8-sig")
check("CSV: формулы из данных коммутатора не выполняются в Excel", "'=HYPERLINK" in csv_text and "'@SUM" in csv_text
      and "\r\n-\r\n" in csv_text and "\r\n-5\r\n" in csv_text, csv_text)

r = admin.post("/logout")
check("выход", r.status_code == 302 and admin.get("/").status_code == 302)

print("\nИТОГО:", "все проверки пройдены" if not fails else f"провалено {len(fails)}: {fails}")

