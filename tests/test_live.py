"""Полный опрос через настоящий SNMP (snmpsim на 127.0.0.1:161). argv: <рабочая папка с тестовой базой>"""
import json, os, sqlite3, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
HELPERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers")
sys.stdout.reconfigure(encoding='utf-8')
app_dir = sys.argv[1]
os.chdir(app_dir); sys.path[:0] = [ROOT, HELPERS]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as m

m.migrate_db()
m.app.config["PROPAGATE_EXCEPTIONS"] = False
import authhelp; c = authhelp.admin_client(m)
fails = []
def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""))
    if not cond:
        fails.append(name)

with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM switches")
    for t in ("port_traffic", "switch_health", "port_events", "mac_table", "devices"):
        conn.execute(f"DELETE FROM {t}")
    ins = """INSERT INTO switches (id, name, ports, ip_address, snmp_community, switch_layout, patch_panels, connections,
             port_types, trunk_ports, snmp_version, snmp_v3_user, snmp_v3_auth_proto, snmp_v3_auth_key,
             snmp_v3_priv_proto, snmp_v3_priv_key, snmp_v3_context)
             VALUES (?, ?, ?, '127.0.0.1', ?, 'single', '[]', ?, '{}', '{}', ?, ?, ?, ?, ?, ?, ?)"""
    conn.execute(ins, (1, "Ядро Cisco", 10, "public", json.dumps({"7": {"name": "Склад принтер", "color": "red", "patchPanel": None, "patch": None}}),
                       "2c", None, "none", None, "none", None, None))
    conn.execute(ins, (2, "Доступ D-Link", 8, "edge2", "{}", "2c", None, "none", None, "none", None, None))
    conn.execute(ins, (3, "Ядро Cisco (v3)", 10, "x", "{}", "3", "simuser", "SHA", "authpass123", "AES128", "privpass123", "public"))
    conn.execute(ins, (4, "Неверный v3", 10, "x", "{}", "3", "simuser", "SHA", "wrongpass99", "AES128", "privpass123", "public"))
    conn.commit()

# ── Проверка подключения
d = c.post("/api/snmp_test/1").get_json()
check("snmp_test v2c: sysName", d.get("ok") and d.get("sys_name") == "sim-cisco", d)
d = c.post("/api/snmp_test/3").get_json()
check("snmp_test v3 authPriv", d.get("ok") and d.get("auth") == "SNMPv3 authPriv", d)
d = c.post("/api/snmp_test/4").get_json()
check("snmp_test v3 неверный пароль → понятная ошибка", not d.get("ok") and "неверный пароль" in d.get("error", ""), d)

# ── Два опроса с интервалом
t0 = time.time()
r1 = c.post("/api/poll_snmp/1").get_json()
poll_time = time.time() - t0
check("опрос 1 без ошибки", "error" not in r1, str(r1)[:200])
check(f"опрос занимает секунды, а не минуты ({poll_time:.1f} с)", poll_time < 20, poll_time)
h = c.get("/api/switch_health/1").get_json()
check("Cisco: CPU, память и температура из таблиц Cisco (95%, 40%, 45 °C)",
      h["cpu_usage"] == 95 and abs(h["ram_usage"] - 40) < 0.1 and h["temperature"] == 45, h)
c.post("/api/poll_snmp/2"); c.post("/api/poll_snmp/3")
r4 = c.post("/api/poll_snmp/4").get_json()
check("опрос с неверным паролем v3 → ошибка, снимок не тронут", "error" in r4 and "неверный пароль" in r4["error"], r4)
time.sleep(12)  # скорость считается по интервалу не короче 10 с
for sid in (1, 2, 3):
    c.post(f"/api/poll_snmp/{sid}")
c.post("/api/poll_snmp/1")  # третий опрос — повторных оповещений быть не должно

# ── Сопоставление портов (Cisco: ifIndex 10101…, Fa0 и Vlan1 не на схеме)
by_if = {k: v for k, v in r1.items()}
check("Gi1/0/1 → порт 1, Gi1/0/8 → порт 8", by_if["10101"]["port"] == 1 and by_if["10108"]["port"] == 8)
check("Gi1/1/1 → порт 9, Gi1/1/2 → порт 10", by_if["10109"]["port"] == 9 and by_if["10110"]["port"] == 10)
check("Fa0 (mgmt) и Vlan1 без номера порта", by_if["1"]["port"] is None and by_if["1001"]["port"] is None)
check("ifAlias по-русски", by_if["10103"]["alias"] == "Бухгалтерия ПК-1", by_if["10103"]["alias"])
check("скорость из ifHighSpeed", by_if["10103"]["speed"] == 1000, by_if["10103"]["speed"])
check("VLAN: порт 3 → 10 (buh) — исправленный OID dot1qPvid", (by_if["10103"]["vlan"] or {}).get("id") == "10"
      and by_if["10103"]["vlan"].get("name") == "buh", by_if["10103"]["vlan"])
check("PoE Cisco (индекс 1.<порт>): порт 2 подаёт 6.5 Вт", (by_if["10102"]["poe"] or {}).get("state") == "delivering"
      and by_if["10102"]["poe"]["power_consumed"] == 6.5, by_if["10102"]["poe"])
check("MAC из Q-BRIDGE: ПК на порту 3 с IP", any(d["mac"] == "00:11:22:33:44:55" and d["ip"] == "192.0.2.50"
                                              for d in by_if["10103"]["devices"]), by_if["10103"]["devices"])

# ── Загрузка портов
load = c.get("/api/port_load/1").get_json()
p3, p9 = load["ports"].get("3", {}), load["ports"].get("9", {})
check("порт 3: ~40 Мбит/с, загрузка ~4%", p3.get("in_mbps") and 25 < p3["in_mbps"] < 55 and 2 < p3["util"] < 6, p3)
check("порт 9 (uplink): загрузка ≥ 80%", (p9.get("util") or 0) >= 80, p9)
check("порт 5 выключен", load["ports"].get("5", {}).get("up") is False)
check("на схеме 10 портов (без Fa0/Vlan1)", sorted(map(int, load["ports"])) == list(range(1, 11)), sorted(load["ports"]))
d2 = c.get("/api/port_load/2").get_json()
check("D-Link: ifIndex = номер порта, 8 портов", sorted(map(int, d2["ports"])) == list(range(1, 9)), sorted(d2["ports"]))
d3 = c.get("/api/port_load/3").get_json()
check("v3-коммутатор опрашивается так же", (d3["ports"].get("9", {}).get("util") or 0) >= 80, d3["ports"].get("9"))

# ── Оповещения
ev = c.get("/api/port_events?limit=100").get_json()
kinds = [(e["switch_id"], e["event_type"], e["port_number"]) for e in ev]
check("util_high на порту 9 Cisco — ровно одно (гистерезис)", kinds.count((1, "util_high", 9)) == 1, kinds)
check("CPU 95% → cpu_high (один раз)", kinds.count((1, "cpu_high", None)) == 1, kinds)
check("ошибки на порту 4 D-Link → errors_high", (2, "errors_high", 4) in kinds, kinds)
check("у событий есть детали", all(e["details"] for e in ev if e["event_type"] != "up" and e["event_type"] != "down"),
      [e["details"] for e in ev][:4])

# ── Поиск
def first(q):
    res = c.get("/api/search", query_string={"q": q}).get_json()
    return res, (res[0] if res else {})
for q in ("00:11:22:33:44:55", "00-11-22-33-44-55", "0011.2233.4455", "001122334455", "112233", "192.0.2.50", "192.0.2"):
    res, top = first(q)
    check(f"поиск «{q}»: первым — Cisco порт 3 (не uplink)", top.get("switch_id") in (1, 3) and top.get("port") == 3
          and not top.get("uplink"), [(r["switch_id"], r["port"], r["uplink"]) for r in res])
res, _ = first("00:11:22:33:44:55")
check("тот же MAC на D-Link порт 8 помечен как uplink и стоит ниже",
      any(r["switch_id"] == 2 and r["port"] == 8 and r["uplink"] for r in res) and res[-1]["uplink"], [(r["switch_id"], r["port"], r["uplink"]) for r in res])
res, top = first("бухгалтерия")
check("поиск по описанию порта (ifAlias, без учёта регистра)", top.get("kind") == "port" and top.get("port") == 3, res)
res, top = first("склад")
check("поиск по названию подключения", top.get("kind") == "port" and top.get("port") == 7 and top.get("switch_id") == 1, res)
check("короткий запрос — пусто", c.get("/api/search?q=a").get_json() == [])
check("спецсимволы LIKE не ломают поиск", c.get("/api/search?q=%25_%25").status_code == 200)

# ── Удаление коммутатора чистит связанные таблицы
c.post("/delete/2")
with sqlite3.connect(m.DB) as conn:
    left = sum(conn.execute(f"SELECT COUNT(*) FROM {t} WHERE switch_id=2").fetchone()[0]
               for t in ("port_traffic", "port_events", "mac_table", "switch_health"))
check("удаление коммутатора убирает его историю", left == 0, left)

print("\nИТОГО:", "все проверки пройдены" if not fails else f"провалено {len(fails)}: {fails}")
