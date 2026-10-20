"""Тесты: хранение истории, ряды за период, резервные копии, журнал, экспорт. argv: <рабочая папка с тестовой базой>"""
import io, json, os, re, sqlite3, sys, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
HELPERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers")
from datetime import datetime, timedelta
sys.stdout.reconfigure(encoding='utf-8')
app_dir = sys.argv[1]
os.chdir(app_dir); sys.path[:0] = [ROOT, HELPERS]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as m
import maintenance as mt

fails = []
def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""))
    if not cond:
        fails.append(name)

TS = "%Y-%m-%d %H:%M:%S"
# ── 0. Копия перед миграцией и версия схемы
for f in os.listdir(mt.backups_dir(m.DB)):
    os.remove(os.path.join(mt.backups_dir(m.DB), f))
m.prepare_database()
names = [b["name"] for b in mt.list_backups(m.DB)]
check("старая схема → копия перед миграцией", any("pre-migrate" in n for n in names), names)
m.prepare_database()
check("повторный запуск не плодит pre-migrate", sum("pre-migrate" in b["name"] for b in mt.list_backups(m.DB)) == 1)
import authhelp; c = authhelp.admin_client(m)
m.app.config["PROPAGATE_EXCEPTIONS"] = False

# ── 1. Свёртка истории: 10 дней, опрос раз в 5 минут, 10/5 Мбит/с, один час — 100 Мбит/с
now = datetime(2026, 10, 20, 12, 0, 0)
start = now - timedelta(days=10)
spike_hour = (now - timedelta(days=9)).replace(minute=0)
with sqlite3.connect(m.DB) as conn:
    for t in ("port_traffic", "port_traffic_hourly", "switch_health", "switch_health_hourly", "port_events"):
        conn.execute(f"DELETE FROM {t}")
    b_in = b_out = 0
    rows, health = [], []
    t = start
    while t < now:
        rate_in = 100 if spike_hour <= t < spike_hour + timedelta(hours=1) else 10  # интервал относится к часу своего окончания
        b_in += rate_in * 1_000_000 * 300 // 8
        b_out += 5 * 1_000_000 * 300 // 8
        rows.append((1, "3", t.strftime(TS), b_in, b_out, 0, 0, 64))
        health.append((1, t.strftime(TS), 20.0, 40.0, 45.0))
        t += timedelta(minutes=5)
    # старые записи без скорости (как до обновления) — их посчитает backfill
    conn.executemany("""INSERT INTO port_traffic (switch_id, ifindex, timestamp, bytes_in, bytes_out, errors_in, errors_out, counter_bits)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", rows)
    conn.executemany("INSERT INTO switch_health (switch_id, timestamp, cpu_usage, ram_usage, temperature) VALUES (?, ?, ?, ?, ?)", health)
    conn.execute("INSERT INTO port_events (switch_id, ifindex, port_name, event_type, event_time, is_read) VALUES (1, '3', 'x', 'up', ?, 1)",
                 ((now - timedelta(days=200)).strftime(TS),))
    conn.execute("INSERT INTO port_events (switch_id, ifindex, port_name, event_type, event_time, is_read) VALUES (1, '3', 'x', 'up', ?, 1)",
                 ((now - timedelta(days=1)).strftime(TS),))
    conn.commit()
total = len(rows)
st = mt.rollup_and_prune(m.DB, m.compute_traffic_rates, raw_days=7, hourly_days=365, events_days=90, now=now)
check("backfill посчитал скорость для всех старых записей", st["backfilled"] == total, st)
with sqlite3.connect(m.DB) as conn:
    raw_left = conn.execute("SELECT COUNT(*), MIN(timestamp) FROM port_traffic").fetchone()
    hourly = conn.execute("SELECT COUNT(*), AVG(in_avg), MAX(in_max) FROM port_traffic_hourly").fetchone()
    spike = conn.execute("SELECT in_avg, in_max, samples FROM port_traffic_hourly WHERE hour=?", (spike_hour.strftime(TS),)).fetchone()
    normal = conn.execute("SELECT in_avg, out_avg, samples FROM port_traffic_hourly WHERE hour=?",
                          ((spike_hour + timedelta(hours=5)).strftime(TS),)).fetchone()
    hh = conn.execute("SELECT COUNT(*), AVG(cpu_avg) FROM switch_health_hourly").fetchone()
    ev = conn.execute("SELECT COUNT(*) FROM port_events").fetchone()[0]
cutoff = (now - timedelta(days=7)).replace(minute=0).strftime(TS)
check("сырые старше 7 дней удалены", raw_left[1] >= cutoff and raw_left[0] == 7 * 288, raw_left)
check("почасовые: 72 часа (дни 8–10)", hourly[0] == 72, hourly)
check("обычный час: в среднем 10 / 5 Мбит/с, 12 опросов", normal and abs(normal[0] - 10) < 0.01 and abs(normal[1] - 5) < 0.01 and normal[2] == 12, normal)
check("пиковый час: среднее и пик 100 Мбит/с", spike and abs(spike[0] - 100) < 0.01 and abs(spike[1] - 100) < 0.01, spike)
check("здоровье свернуто по часам", hh[0] == 72 and abs(hh[1] - 20) < 0.01, hh)
check("события старше 90 дней удалены", ev == 1, ev)
st2 = mt.rollup_and_prune(m.DB, m.compute_traffic_rates, raw_days=7, now=now)
with sqlite3.connect(m.DB) as conn:
    again = conn.execute("SELECT COUNT(*), SUM(samples) FROM port_traffic_hourly").fetchone()
check("повторная свёртка ничего не дублирует", again[0] == 72 and st2["traffic_raw_deleted"] == 0, again)
st3 = mt.rollup_and_prune(m.DB, m.compute_traffic_rates, raw_days=6, now=now)
with sqlite3.connect(m.DB) as conn:
    h3 = conn.execute("SELECT COUNT(*), AVG(in_avg) FROM port_traffic_hourly").fetchone()
check("уменьшили срок — ещё 24 часа свернулось", h3[0] == 96 and st3["traffic_raw_deleted"] == 288, (h3, st3["traffic_raw_deleted"]))

# ── 2. Ряды за период
for period, expect_bucket in (("1h", 0), ("24h", 0), ("7d", 3600), ("30d", 3 * 3600), ("1y", 86400)):
    s = mt.traffic_series(m.DB, 1, "3", period, now=now)
    pts = s["points"]
    ins = [p["in_mbps"] for p in pts if p["in_mbps"] is not None]
    check(f"трафик {period}: корзина {expect_bucket}, точки есть, среднее ≈ 10", s["bucket_sec"] == expect_bucket and pts
          and all(abs(v - 10) < 0.6 or v > 10 for v in ins), (s["bucket_sec"], len(pts), ins[:3]))
s = mt.traffic_series(m.DB, 1, "3", "24h", now=now)
check("24h: 288 сырых точек", len(s["points"]) == 288, len(s["points"]))
s = mt.traffic_series(m.DB, 1, "3", "30d", now=now)
check("30d: пик 100 Мбит/с виден", max(p["in_mbps_max"] or 0 for p in s["points"]) >= 99.9)
check("30d: охват — все 10 дней (почасовые + сырые)", s["points"][0]["timestamp"] <= start.strftime(TS)[:10] + " 23:59:59")
s = mt.traffic_series(m.DB, 1, "3", "7d", now=now)
check("7d: ~168 часовых корзин", 160 <= len(s["points"]) <= 170, len(s["points"]))
h = mt.health_series(m.DB, 1, "30d", now=now)
check("здоровье 30d: CPU ≈ 20", h["bucket_sec"] == 10800 and all(abs(p["cpu_usage"] - 20) < 0.01 for p in h["points"] if p["cpu_usage"]), len(h["points"]))
r = c.get("/api/port_traffic/1/3?period=bad")
check("неизвестный период → 400", r.status_code == 400)
check("API периода отвечает", c.get("/api/port_traffic/1/3?period=7d").status_code == 200
      and c.get("/api/switch_health_history/1?period=1y").status_code == 200)

# ── 3. Настройки: частичное обновление
c.post("/api/settings", json={"poll_enabled": True, "poll_interval_minutes": 7})
c.post("/api/settings", json={"retention_raw_days": 3, "backup_keep": 2})
s = m.get_settings()
check("частичное сохранение не трогает опрос", s["poll_enabled"] and s["poll_interval_minutes"] == 7
      and s["retention_raw_days"] == 3 and s["backup_keep"] == 2, s)
c.post("/api/settings", json={"retention_raw_days": 500})
check("значения ограничены диапазоном", m.get_settings()["retention_raw_days"] == 90)
c.post("/api/settings", json={"poll_enabled": False})

# ── 4. Резервные копии
r = c.post("/api/backups").get_json()
check("создание копии", r["ok"] and mt.backup_path(m.DB, r["name"]), r)
for _ in range(3):
    c.post("/api/backups")
check("ротация: хранится backup_keep=2", len(mt.list_backups(m.DB)) == 2, len(mt.list_backups(m.DB)))
name = mt.list_backups(m.DB)[0]["name"]
d = c.get(f"/api/backups/{name}")
check("скачивание копии — файл SQLite", d.status_code == 200 and d.data[:16] == b"SQLite format 3\x00")
check("защита от ../ в имени", c.get("/api/backups/..%2Fswitches.db").status_code == 404 and mt.backup_path(m.DB, "../switches.db") is None)
with sqlite3.connect(m.DB) as conn:
    conn.execute("UPDATE switches SET name='Испорчено' WHERE id=1"); conn.commit()
r = c.post(f"/api/backups/{name}/restore").get_json()
check("восстановление из копии", r["ok"] and m.fetch_switch(1)["name"] != "Испорчено", r)
check("перед восстановлением сохранено текущее", any("before-restore" in b["name"] for b in mt.list_backups(m.DB)))
bad = c.post("/api/backups/upload", data={"file": (io.BytesIO(b"not a database at all"), "x.db")},
             content_type="multipart/form-data")
check("загрузка не-SQLite → 400 с объяснением", bad.status_code == 400 and "SQLite" in bad.get_json()["error"], bad.get_json())
other = os.path.join(app_dir, "other.db")
sqlite3.connect(other).execute("CREATE TABLE t (x)").connection.close()
bad2 = c.post("/api/backups/upload", data={"file": (open(other, "rb"), "other.db")}, content_type="multipart/form-data")
check("чужая база SQLite → 400", bad2.status_code == 400 and "коммутатор" in bad2.get_json()["error"], bad2.get_json())
good = c.post("/api/backups/upload", data={"file": (io.BytesIO(d.data), "my.db")}, content_type="multipart/form-data")
check("загрузка своей копии → восстановлено", good.status_code == 200 and good.get_json()["ok"], good.get_json())
check("временный файл загрузки удалён", not [f for f in os.listdir(mt.backups_dir(m.DB)) if f.endswith(".tmp")])
check("удаление копии", c.delete(f"/api/backups/{mt.list_backups(m.DB)[-1]['name']}").get_json()["ok"])

# ── 5. Журнал изменений
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM audit_log")
    conn.execute("UPDATE switches SET snmp_v3_auth_key='supersecret1', snmp_version='3', snmp_v3_user='u', snmp_v3_auth_proto='SHA' WHERE id=1")
    conn.commit()
sw = m.fetch_switch(1)
form = {"name": "Бухгалтерия (новое)", "port_count": str(sw["ports"]), "layout": "double", "patch_panels": sw["patch_panels"] or "[]",
        "connections": json.dumps({"5": {"name": "Касса", "color": "red", "patchPanel": None, "patch": None}}),
        "port_types": json.dumps({"52": "rj45"}), "trunk_ports": sw["trunk_ports"] or "{}", "ip_address": "10.1.1.1",
        "snmp_community": "public", "snmp_version": "3", "snmp_v3_user": "u", "snmp_v3_auth_proto": "SHA",
        "snmp_v3_auth_key": "newsecret22", "snmp_v3_priv_proto": "none", "snmp_v3_priv_key": "", "snmp_v3_context": ""}
c.post("/update/1", data=form)
e = c.get("/api/audit").get_json()
upd = e[0]
fields = [ch["field"] for ch in upd["changes"]]
check("журнал: запись об изменении", upd["action"] == "update" and upd["revertible"], upd["summary"])
check("журнал: название, IP, раскладка, подключение, тип порта", all(any(f.startswith(x) for f in fields)
      for x in ("Название", "IP-адрес", "Расположение", "Подключение порта 5", "Тип порта 52")), fields)
raw = json.dumps(c.get("/api/audit").get_json(), ensure_ascii=False) + c.get("/api/audit").get_data(as_text=True)
check("пароли SNMPv3 не попадают в журнал", "supersecret1" not in raw and "newsecret22" not in raw and "Пароль аутентификации" in raw)
r = c.post(f"/api/audit/{upd['id']}/revert").get_json()
sw2 = m.fetch_switch(1)
check("откат: значения вернулись", r["ok"] and sw2["name"] == sw["name"] and sw2["switch_layout"] == sw["switch_layout"]
      and sw2["ip_address"] == sw["ip_address"] and "5" not in json.loads(sw2["connections"] or "{}"), (sw2["name"], sw2["switch_layout"]))
check("откат: пароль не откатывается (остаётся новый, хранится зашифрованным)", m.SECRET_BOX.decrypt(sw2["snmp_v3_auth_key"]) == "newsecret22" and sw2["snmp_v3_auth_key"].startswith("enc:v1:"))
check("повторный откат той же записи → 409", c.post(f"/api/audit/{upd['id']}/revert").status_code == 409)
rev = c.get("/api/audit").get_json()[0]
r = c.post(f"/api/audit/{rev['id']}/revert").get_json()
check("отмена отката возвращает правку", r["ok"] and m.fetch_switch(1)["name"] == "Бухгалтерия (новое)")
c.post("/api/assign_device/1", json={"port_number": 5, "ip": "10.1.1.50", "mac": "aa:bb:cc:00:00:01", "hostname": "kassa"})
before_del = m.fetch_switch(1)
c.post("/delete/1")
check("удалён", m.fetch_switch(1) is None)
dl = [x for x in c.get("/api/audit").get_json() if x["action"] == "delete"][0]
r = c.post(f"/api/audit/{dl['id']}/revert").get_json()
restored = m.fetch_switch(r["switch_id"])
with sqlite3.connect(m.DB) as conn:
    devs = conn.execute("SELECT hostname FROM devices WHERE switch_id=?", (r["switch_id"],)).fetchall()
check("восстановление удалённого: настройки, подключения, устройство", restored and restored["name"] == before_del["name"]
      and "5" in json.loads(restored["connections"]) and devs == [("kassa",)], (r, devs))
acts = [x["action"] for x in c.get("/api/audit?limit=20").get_json()]
check("в журнале есть устройство, удаление, восстановление, настройки", {"device_assign", "delete", "restore_switch", "settings"} <= set(acts)
      or {"device_assign", "delete", "restore_switch"} <= set(acts), acts)
check("фильтр по действию", all(x["action"] == "delete" for x in c.get("/api/audit?action=delete").get_json()))

# ── 6. Экспорт
r = c.get(f"/export/switch/{restored['id']}.xlsx")
z = zipfile.ZipFile(io.BytesIO(r.data))
wb = z.read("xl/workbook.xml").decode()
sheet1 = z.read("xl/worksheets/sheet1.xml").decode()
check("xlsx коммутатора: 4 листа, корректный zip", r.status_code == 200 and z.testzip() is None
      and re.findall(r'<sheet name="([^"]+)"', wb) == ["Порты", "Подключения", "Патч-панели", "Устройства"], re.findall(r'<sheet name="([^"]+)"', wb))
check("xlsx: имя файла и заголовок", "attachment" in r.headers["Content-Disposition"] and ".xlsx" in r.headers["Content-Disposition"])
check("xlsx: порты 1..N и подключение «Касса»", sheet1.count("<row ") == restored["ports"] + 1 and "Касса" in sheet1)
import xml.dom.minidom
for n in z.namelist():
    if n.endswith(".xml") or n.endswith(".rels"):
        xml.dom.minidom.parseString(z.read(n))
check("xlsx: все XML-части разбираются", True)
r = c.get(f"/export/switch/{restored['id']}/connections.csv")
txt = r.data.decode("utf-8")
check("CSV: BOM, «;», кириллица", txt.startswith("﻿") and "Порт;Назначение" in txt and "Касса" in txt, txt[:80])
check("CSV: неизвестная таблица → 404", c.get(f"/export/switch/{restored['id']}/nope.csv").status_code == 404)
r = c.get("/export/inventory.xlsx")
wb = zipfile.ZipFile(io.BytesIO(r.data)).read("xl/workbook.xml").decode()
check("инвентарь: 4 листа", re.findall(r'<sheet name="([^"]+)"', wb) == ["Коммутаторы", "MAC-адреса", "События", "Журнал изменений"], wb[-300:])
for t in ("switches", "macs", "events", "audit"):
    check(f"CSV инвентаря {t}", c.get(f"/export/{t}.csv").status_code == 200)

# ── 7. Страницы
for url in ("/audit", "/audit?switch=2", "/maintenance"):
    check(f"страница {url}", c.get(url).status_code == 200)
st = c.get("/api/maintenance/stats").get_json()
check("статистика базы", st["file_size"] > 0 and "port_traffic_hourly" in st["tables"] and "settings" in st, list(st))

print("\nИТОГО:", "все проверки пройдены" if not fails else f"провалено {len(fails)}: {fails}")

