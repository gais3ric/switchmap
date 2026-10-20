"""SNMPv3 в форме добавления, автообнаружение (настоящий snmpsim на 127.0.0.1), NetBox (поддельный).
argv: <рабочая папка с тестовой базой>"""
import json, os, sqlite3, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
HELPERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers")
sys.stdout.reconfigure(encoding='utf-8')
app_dir = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
os.chdir(app_dir); sys.path[:0] = [ROOT, HELPERS]; sys.path.insert(0, here)
import app as m
import discovery, netbox, security
import fakenetbox as fnb
from authhelp import admin_client, login

fails = []
def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""))
    if not cond:
        fails.append(name)

m.prepare_database()
m.app.config["PROPAGATE_EXCEPTIONS"] = False
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM switches"); conn.execute("DELETE FROM app_settings WHERE key='netbox_config'")
    conn.execute("DELETE FROM users"); conn.commit()
c = admin_client(m)
security.create_user(m.DB, "viewer1", "Viewerpass1", "viewer")
v = login(m, "viewer1", "Viewerpass1")
J = {"Content-Type": "application/json"}
def post(url, body=None, client=None):
    r = (client or c).post(url, data=json.dumps(body or {}), headers=J)
    return r.status_code, r.get_json()
def row(sid):
    return m.fetch_switch(sid)
V3 = {"snmp_version": "3", "snmp_v3_user": "simuser", "snmp_v3_auth_proto": "SHA", "snmp_v3_auth_key": "authpass123",
      "snmp_v3_priv_proto": "AES128", "snmp_v3_priv_key": "privpass123", "snmp_v3_context": "public"}

# ── Доступ
check("наблюдатель: /discover, /add, API поиска и NetBox закрыты",
      v.get("/discover").status_code == 403 and v.get("/add").status_code == 403 and v.get("/api/netbox").status_code == 403
      and post("/api/snmp_probe", {"ip_address": "127.0.0.1"}, v)[0] == 403
      and post("/api/discovery/start", {"ranges": "127.0.0.1"}, v)[0] == 403)
page = c.get("/discover").get_data(as_text=True)
check("страница /discover открывается, в меню пункт есть", 'id="tab-scan"' in page and 'href="/discover"' in page)
check("в окне добавления есть выбор версии SNMP и «Проверить и заполнить»",
      'name="snmp_version"' in c.get("/").get_data(as_text=True) and "Проверить и заполнить" in c.get("/").get_data(as_text=True)
      and 'name="snmp_v3_priv_proto"' in c.get("/add").get_data(as_text=True))

# ── «Проверить и заполнить»
code, r = post("/api/snmp_probe", {"ip_address": "127.0.0.1", "snmp_version": "2c", "snmp_community": "public"})
check("проверка v2c: имя, производитель, модель, порты", r["ok"] and r["sys_name"] == "sim-cisco" and r["vendor"] == "Cisco"
      and "C2960X" in r["model_label"] and r["ports"] == 10 and r["is_switch"] and r["location"] == "Server room, rack 2", r)
code, r = post("/api/snmp_probe", {"ip_address": "127.0.0.1", **V3})
check("проверка v3 authPriv", r["ok"] and r["auth"] == "SNMPv3 authPriv" and r["sys_name"] == "sim-cisco", r)
code, r = post("/api/snmp_probe", {"ip_address": "127.0.0.1", **V3, "snmp_v3_auth_key": "wrongpass99"})
check("v3 с неверным паролем — понятная ошибка", not r["ok"] and "неверный пароль" in r["error"], r)
code, r = post("/api/snmp_probe", {"ip_address": "127.0.0.1", **V3, "snmp_v3_priv_key": "short"})
check("v3 с коротким паролем — ошибка до опроса", not r["ok"] and "не короче 8" in r["error"], r)
code, r = post("/api/snmp_probe", {"ip_address": ""})
check("без IP — подсказка", not r["ok"] and "IP" in r["error"])

# ── Добавление с SNMPv3 через форму
with m.app.test_request_context():
    pass
cs = c.get("/").get_data(as_text=True)
r = c.post("/add", data={"name": "Ядро v3", "ports": "10", "switch_layout": "single", "ip_address": "127.0.0.1",
                         "patch_panels_data": "[]", "model": "Cisco · C2960X", **V3})
with sqlite3.connect(m.DB) as conn:
    conn.row_factory = sqlite3.Row
    sw = conn.execute("SELECT * FROM switches WHERE name='Ядро v3'").fetchone()
check("форма: коммутатор с v3 создан", r.status_code == 302 and sw and sw["snmp_version"] == "3" and sw["snmp_v3_user"] == "simuser"
      and sw["snmp_v3_priv_proto"] == "AES128" and sw["snmp_v3_context"] == "public" and sw["model"] == "Cisco · C2960X")
check("пароли v3 в базе зашифрованы", sw["snmp_v3_auth_key"].startswith("enc:v1:") and sw["snmp_v3_priv_key"].startswith("enc:v1:")
      and m.SECRET_BOX.decrypt(sw["snmp_v3_auth_key"]) == "authpass123")
d = c.post(f"/api/snmp_test/{sw['id']}").get_json()
check("созданный v3-коммутатор отвечает", d["ok"] and d["auth"] == "SNMPv3 authPriv", d)
r = m.poll_switch_and_log_events(sw["id"])
check("и полностью опрашивается", isinstance(r, dict) and "error" not in r and len(r) >= 8, str(r)[:150])
with sqlite3.connect(m.DB) as conn:
    a = conn.execute("SELECT summary FROM audit_log WHERE action='create' ORDER BY id DESC LIMIT 1").fetchone()[0]
check("журнал: модель, порты, IP, SNMPv3", "C2960X" in a and "10 портов" in a or "10 порт" in a and "SNMPv3 authPriv" in a, a)
r = c.post("/add", data={"name": "Плохой v3", "ports": "8", "ip_address": "10.0.0.9", **V3, "snmp_v3_auth_key": "123"})
check("форма: неверный v3 → 400, не создан", r.status_code == 400 and "не короче 8" in r.get_data(as_text=True)
      and not m.fetch_switch(sw["id"] + 1))
r = c.post("/add", data={"name": "Простой", "ports": "24", "ip_address": "10.0.0.20", "snmp_community": "edge2",
                         "snmp_v3_user": "мусор"})
with sqlite3.connect(m.DB) as conn:
    conn.row_factory = sqlite3.Row
    simple = conn.execute("SELECT * FROM switches WHERE name='Простой'").fetchone()
check("форма v2c: старые поля работают, v3 не сохраняется", r.status_code == 302 and simple["snmp_version"] == "2c"
      and simple["snmp_community"] == "edge2" and simple["snmp_v3_user"] is None and simple["patch_panels"] != "[]")
code, r = post("/api/snmp_probe", {"ip_address": "127.0.0.1", "snmp_community": "public"})
check("проверка предупреждает: IP уже добавлен", r["existing"] and r["existing"]["name"] == "Ядро v3", r.get("existing"))

# ── Разбор адресов
ips, err = discovery.parse_targets("10.0.0.0/30, 10.0.1.5-7\n10.0.2.1-10.0.2.2 10.0.0.1")
check("разбор: сеть, диапазоны, повторы", ips == ["10.0.0.1", "10.0.0.2", "10.0.1.5", "10.0.1.6", "10.0.1.7", "10.0.2.1", "10.0.2.2"], ips)
check("разбор: ошибки понятные", "Не понимаю" in discovery.parse_targets("10.0.0.300")[1]
      and "слишком" in discovery.parse_targets("10.0.0.0/8")[1].lower() and discovery.parse_targets("")[1]
      and "конец меньше" in discovery.parse_targets("10.0.0.9-10.0.0.1")[1])
check("разбор: /32 и /31", discovery.parse_targets("10.0.0.5/32")[0] == ["10.0.0.5"] and len(discovery.parse_targets("10.0.0.4/31")[0]) == 2)
check("производитель по sysObjectID", discovery.vendor_from_oid("1.3.6.1.4.1.9.1.1208") == "Cisco"
      and discovery.vendor_from_oid("1.3.6.1.4.1.99999.1") == "enterprise 99999" and discovery.vendor_from_oid("") == "")
check("LLDP: адреса соседей из OID", discovery.parse_lldp_mgmt_ips(
      [("1.0.8802.1.1.2.1.4.2.1.3.0.5.1.1.4.10.0.0.7", 2), ("1.0.8802.1.1.2.1.4.2.1.3.0.5.2.2.16.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1", 2)]) == ["10.0.0.7"])

# ── Поиск по сети (настоящий SNMP): 127.0.0.1 отвечает, .2–.4 — нет; LLDP ведёт на 127.0.0.5
def wait_job(job_id, limit=120):
    t0 = time.time()
    while time.time() - t0 < limit:
        j = c.get(f"/api/discovery/{job_id}").get_json()
        if j["status"] != "running":
            return j
        time.sleep(0.5)
    return j
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM switches"); conn.commit()
t0 = time.time()
code, j = post("/api/discovery/start", {"ranges": "127.0.0.1-4", "snmp_version": "2c", "snmp_community": "wrong, public",
                                        "follow_lldp": True})
check("поиск запущен", code == 200 and j["status"] == "running" and j["total"] == 4, j)
code2, j2 = post("/api/discovery/start", {"ranges": "127.0.0.1"})
check("второй поиск одновременно — нельзя", code2 == 409 and "уже идёт" in j2["error"], j2)
cur = c.get("/api/discovery/current").get_json()
check("текущий поиск виден после перезагрузки страницы", cur and cur["id"] == j["id"])
j = wait_job(j["id"])
elapsed = time.time() - t0
f = j["found"][0] if j["found"] else {}
check("найден один коммутатор, второй community подошёл", len(j["found"]) == 1 and f["ip"] == "127.0.0.1"
      and f["cred_label"] == "v2c · public" and f["sys_name"] == "sim-cisco" and f["is_switch"], j["found"])
check("по LLDP добавлен сосед 127.0.0.5 (проверен, не ответил)", j["total"] == 5 and j["done"] == 5, (j["total"], j["done"]))
check("учётные данные в ответ не попадают", "cred" not in f and "public" not in json.dumps({k: v for k, v in f.items() if k != "cred_label"}))
check(f"поиск по 5 адресам занял разумное время ({elapsed:.1f} с)", elapsed < 40)
code, r = post(f"/api/discovery/{j['id']}/add", {"items": [{"ip": "127.0.0.1", "name": "Ядро (найдено)", "ports": 10}]})
new = m.fetch_switch(r["added"][0]["id"]) if r.get("added") else {}
check("добавление найденного: имя, IP, community, модель, без патч-панели", new and new["name"] == "Ядро (найдено)"
      and new["ip_address"] == "127.0.0.1" and new["snmp_community"] == "public" and "Cisco" in new["model"]
      and new["patch_panels"] == "[]", new)
code, r = post(f"/api/discovery/{j['id']}/add", {"items": [{"ip": "127.0.0.1", "name": "Дубль"}]})
check("повторное добавление пропущено", not r["added"] and "уже есть" in r["skipped"][0], r)
j = c.get(f"/api/discovery/{j['id']}").get_json()
check("в результатах отмечено «уже есть»", j["found"][0]["existing"]["name"] == "Ядро (найдено)")

# v3-поиск
code, j = post("/api/discovery/start", {"ranges": "127.0.0.1", **V3})
j = wait_job(j["id"])
check("поиск с SNMPv3", len(j["found"]) == 1 and j["found"][0]["cred_label"] == "v3 · simuser", j["found"])
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM switches"); conn.commit()
code, r = post(f"/api/discovery/{j['id']}/add", {"items": [{"ip": "127.0.0.1", "name": "v3 найден", "ports": 10}]})
new = m.fetch_switch(r["added"][0]["id"])
check("найденный по v3 добавлен с паролями (зашифрованы) и опрашивается", new["snmp_version"] == "3"
      and new["snmp_v3_auth_key"].startswith("enc:v1:") and new["snmp_v3_context"] == "public"
      and "error" not in m.poll_switch_and_log_events(new["id"]))
code, r = post("/api/discovery/start", {"ranges": "127.0.0.1", **V3, "snmp_v3_user": ""})
check("поиск с неполным v3 — ошибка", code == 400 and "пользовател" in r["error"], r)
code, r = post("/api/discovery/start", {"ranges": "10.0.0.0/8"})
check("слишком большая сеть — ошибка", code == 400, r)

# Остановка поиска (большой диапазон без ответов)
code, j = post("/api/discovery/start", {"ranges": "127.0.1.0/24", "snmp_community": "public"})
time.sleep(1.5)
post(f"/api/discovery/{j['id']}/cancel")
j = wait_job(j["id"], 30)
check("поиск можно остановить", j["status"] == "cancelled" and j["done"] < j["total"], (j["status"], j["done"], j["total"]))

# Обход LLDP на подставном опросе: цепочка из трёх коммутаторов
def fake_probe(ip, auth):
    chain = {"10.5.0.1": ["10.5.0.2"], "10.5.0.2": ["10.5.0.3", "10.5.0.1"], "10.5.0.3": []}
    if ip in chain:
        return {"ok": True, "sys_name": "sw-" + ip[-1], "is_switch": True, "ports": 24, "lldp_ips": chain[ip], "vendor": "", "model": ""}
    return {"ok": False}
job, _ = discovery.start(["10.5.0.1"], [m.SnmpAuth("2c", "public")], ["v2c · public"], fake_probe, follow_lldp=True)
for _ in range(50):
    if job.status != "running": break
    time.sleep(0.1)
pub = job.public()
check("LLDP: по цепочке найдены все три, без зацикливания", [f["ip"] for f in pub["found"]] == ["10.5.0.1", "10.5.0.2", "10.5.0.3"]
      and pub["total"] == 3 and pub["found"][2]["via"] == "sw-2", pub["found"])

# ── NetBox
srv, nb_url = fnb.start()
code, r = post("/api/netbox/test", {"config": {"url": nb_url, "token": "wrong"}})
check("NetBox: неверный токен — понятная ошибка", not r["ok"] and "токен" in r["error"], r)
code, r = post("/api/netbox/test", {"config": {"url": "netbox.local", "token": "x"}})
check("NetBox: адрес без http — ошибка", not r["ok"] and "http" in r["error"], r)
code, r = post("/api/netbox/test", {"config": {"url": "http://127.0.0.1:1", "token": "0123456789abcdef"}})
check("NetBox недоступен — понятная ошибка", not r["ok"] and "Нет связи" in r["error"], r)
fnb.NB.html_mode = True
code, r = post("/api/netbox/test", {"config": {"url": nb_url, "token": "0123456789abcdef"}})
fnb.NB.html_mode = False
check("по адресу не NetBox — понятная ошибка", not r["ok"] and "не NetBox" in r["error"], r)
code, r = post("/api/netbox/test", {"config": {"url": nb_url + "/api/", "token": "Token 0123456789abcdef"}})
check("NetBox: подключение, версия, справочники (адрес с /api/ и префиксом Token)", r["ok"] and r["version"] == "4.2.3"
      and r["devices"] == 265 and [s["slug"] for s in r["options"]["sites"]] == ["hq", "wh", "branch"]
      and r["options"]["roles"][0]["slug"] == "access" and r["options"]["tags"][0]["slug"] == "monitor", r)
code, r = post("/api/netbox/test", {"config": {"url": nb_url, "token": "nbt_abc.secretpart"}})
check("NetBox: токен v2 (nbt_…) — заголовок Bearer", r["ok"], r)
code, r = post("/api/netbox", {"url": nb_url, "token": "0123456789abcdef", "verify": True})
check("настройки NetBox сохранены, токен не отдаётся", code == 200 and r["config"]["has_token"] and "token" not in r["config"]
      and r["config"]["url"] == nb_url)
with sqlite3.connect(m.DB) as conn:
    raw = conn.execute("SELECT value FROM app_settings WHERE key='netbox_config'").fetchone()[0]
check("токен NetBox в базе зашифрован", "0123456789abcdef" not in raw and "enc:v1:" in raw)

# Коммутаторы SwitchMap для сопоставления
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM switches")
    conn.execute("INSERT INTO switches (id, name, ports, ip_address, patch_panels, connections) VALUES (50, 'Этаж 2', 24, '10.0.0.1', '[]', '{}')")
    conn.execute("INSERT INTO switches (id, name, ports, ip_address, patch_panels, connections) VALUES (51, 'Склад', 24, '', '[]', '{}')")
    conn.commit()
code, r = post("/api/netbox/preview", {"config": {"role": "access"}})
devs = {d["name"]: d for d in r.get("devices", [])}
check("предпросмотр: роль access и только активные", r["ok"] and set(devs) == {"core-sw1", "floor2-sw", "СКЛАД", "branch-sw"}, list(devs))
check("сопоставление: по IP и по названию (без учёта регистра)", devs["floor2-sw"]["match"]["by"] == "ip"
      and devs["floor2-sw"]["match"]["changes"][0]["after"] == "floor2-sw" and devs["СКЛАД"]["match"]["by"] == "name"
      and devs["core-sw1"]["match"] is None, devs["floor2-sw"]["match"])
check("ссылка на устройство в NetBox", devs["core-sw1"]["url"] == f"{nb_url}/dcim/devices/1/")
code, r = post("/api/netbox/preview", {"config": {"role": "", "only_active": True}})
check("постраничная загрузка (264 активных из 265)", r["ok"] and len(r["devices"]) == 264, len(r.get("devices", [])))
code, r = post("/api/netbox/preview", {"config": {"role": "", "site": "", "tag": "monitor"}})
check("фильтр по тегу", [d["name"] for d in r["devices"]] == ["core-sw1"])
check("фильтры запомнены", netbox.load_config(m.DB)["tag"] == "monitor")

code, r = post("/api/netbox/import", {"ids": [1, 2, 3], "update_existing": True,
                                      "snmp": {"snmp_version": "2c", "snmp_community": "nbcomm"}})
check("импорт: 1 создан, 1 обновлён по IP, 1 связан по имени", r["ok"] and len(r["created"]) == 1 and len(r["updated"]) == 2,
      r)
with sqlite3.connect(m.DB) as conn:
    conn.row_factory = sqlite3.Row
    core = conn.execute("SELECT * FROM switches WHERE netbox_id=1").fetchone()
    fl2 = conn.execute("SELECT * FROM switches WHERE id=50").fetchone()
    wh = conn.execute("SELECT * FROM switches WHERE id=51").fetchone()
check("новый: имя, IP, физические порты, модель, SNMP, связь", core and core["name"] == "core-sw1" and core["ip_address"] == "10.1.0.1"
      and core["ports"] == 52 and core["model"] == "Cisco · C9300-48P" and core["snmp_community"] == "nbcomm"
      and core["switch_layout"] == "double", dict(core) if core else None)
check("существующий по IP: переименован и связан", fl2["name"] == "floor2-sw" and fl2["netbox_id"] == 2 and fl2["ports"] == 24)
check("существующий по имени: связан, IP не стёрт", wh["netbox_id"] == 3 and wh["name"] == "СКЛАД" and wh["ip_address"] == "")
with sqlite3.connect(m.DB) as conn:
    au = conn.execute("SELECT actor, summary FROM audit_log WHERE action='update' AND switch_id=50 ORDER BY id DESC").fetchone()
    cr = conn.execute("SELECT summary FROM audit_log WHERE action='create' ORDER BY id DESC").fetchone()
check("журнал: импорт и обновление из NetBox", "NetBox" in au[1] and "Импорт из NetBox" in cr[0], (au, cr))
code, r = post("/api/netbox/preview", {"config": {"role": "access", "tag": ""}})
devs = {d["name"]: d for d in r["devices"]}
check("после импорта все трое связаны, изменений нет", all(devs[n]["match"] and devs[n]["match"]["by"] == "netbox"
      and not devs[n]["match"]["changes"] for n in ("core-sw1", "floor2-sw", "СКЛАД")))
code, r = post("/api/netbox/import", {"ids": [1], "snmp": {"snmp_version": "3", "snmp_v3_user": ""}})
check("импорт с неполным v3 — ошибка", not r["ok"] and "SNMPv3" in r["error"], r)
code, r = post("/api/netbox/import", {"ids": [5], "snmp": V3})
nb5 = m.fetch_switch(r["created"][0]["id"])
check("импорт с SNMPv3: пароли зашифрованы, без IP, 10 портов", nb5["snmp_version"] == "3" and nb5["ip_address"] == ""
      and nb5["ports"] == 10 and nb5["snmp_v3_auth_key"].startswith("enc:v1:"))

# Синхронизация
fnb.NB.devices[0]["name"] = "core-sw1-new"; fnb.NB.devices[0]["primary_ip4"] = {"address": "10.1.0.11/24"}
fnb.NB.devices = [d for d in fnb.NB.devices if d["id"] != 3]
code, r = post("/api/netbox/sync")
core = m.fetch_switch(core["id"])
check("синхронизация: имя и IP обновлены, удалённое из NetBox отмечено", r["ok"] and r["checked"] == 4 and len(r["updated"]) == 1
      and core["name"] == "core-sw1-new" and core["ip_address"] == "10.1.0.11" and r["missing"][0]["name"] == "СКЛАД", r)
check("итог синхронизации сохранён", "обновлено 1" in netbox.load_config(m.DB)["last_sync_result"])
code, r = post("/api/netbox", {"auto_sync": True})
check("автосинхронизация включается, адрес и токен сохраняются", r["config"]["auto_sync"] and r["config"]["url"] == nb_url
      and r["config"]["has_token"])
fnb.NB.devices[0]["name"] = "core-sw1-auto"
m.scheduled_netbox_sync()
check("плановая синхронизация работает", m.fetch_switch(core["id"])["name"] == "core-sw1-auto")
page = c.get(f"/switch/{core['id']}").get_data(as_text=True)
check("на странице коммутатора — модель и ссылка в NetBox", f'href="{nb_url}/dcim/devices/1/"' in page and "C9300-48P" in page)
check("на главной — модель под IP", "Cisco · C9300-48P" in c.get("/").get_data(as_text=True))
code, r = post(f"/api/netbox/unlink/{core['id']}")
check("отвязка", m.fetch_switch(core["id"])["netbox_id"] is None)

# Откат обновления из NetBox через журнал
with sqlite3.connect(m.DB) as conn:
    entry = conn.execute("SELECT id FROM audit_log WHERE action='update' AND switch_id=50 ORDER BY id DESC").fetchone()[0]
r = c.post(f"/api/audit/{entry}/revert")
check("изменение из NetBox откатывается через журнал", r.status_code == 200 and m.fetch_switch(50)["name"] == "Этаж 2", r.get_json())

print("\nИТОГО:", "все проверки пройдены" if not fails else f"провалено {len(fails)}: {fails}")
