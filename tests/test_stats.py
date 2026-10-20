"""Бэкенд-тесты окна статистики на копии проекта. argv: <рабочая папка с тестовой базой> <existing|fresh>"""
import os, sqlite3, sys, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
HELPERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers")
sys.stdout.reconfigure(encoding='utf-8')
here = os.path.dirname(os.path.abspath(__file__))
app_dir, mode = sys.argv[1], sys.argv[2]
os.chdir(app_dir)
sys.path[:0] = [ROOT, HELPERS]
sys.path.insert(0, here)
import app as m
import fakesnmp

# Повторяем логику запуска из if __name__ == "__main__"
if mode == "fresh":
    if os.path.exists(m.DB):
        os.remove(m.DB)
    m.init_db()
    with sqlite3.connect(m.DB) as conn:
        conn.execute("INSERT INTO switches (name, ports, patch_panels, switch_layout, connections) VALUES ('Test', 8, '[]', 'single', '{}')")
        conn.commit()
else:
    m.migrate_db()

fakesnmp.install(m)
m.app.config["PROPAGATE_EXCEPTIONS"] = False
import authhelp; c = authhelp.admin_client(m)
fails = []

def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info else ""))
    if not cond:
        fails.append(name)

def get(url, method="get"):
    r = getattr(c, method)(url)
    try:
        return r.status_code, r.get_json()
    except Exception:
        return r.status_code, r.get_data(as_text=True)[:300]

with sqlite3.connect(m.DB) as conn:
    sid = conn.execute("SELECT id FROM switches ORDER BY id LIMIT 1").fetchone()[0]
    conn.execute("UPDATE switches SET ip_address='10.0.0.1' WHERE id=?", (sid,))
    conn.commit()

r = c.get(f"/switch/{sid}")
html = r.get_data(as_text=True)
check("страница коммутатора 200", r.status_code == 200, r.status_code)
check("Chart.js подключён", "chart.umd.min.js" in html)
check("старая страница удалена (404)", c.get(f"/switch/{sid}/stats").status_code == 404)

s, d = get(f"/api/stats_ports/{sid}")
check("порты до опроса: пустой список", s == 200 and d == [], (s, d))
s, d = get(f"/api/poe_status/{sid}")
check("PoE до опроса: пусто", s == 200 and d == {}, (s, d))
s, d = get(f"/api/switch_health_history/{sid}")
check("история до опроса: 200", s == 200, (s, d))
s, d = get(f"/api/switch_health/{sid}")
check("health до опроса", s == 200 and d.get("last_poll_time") is None, (s, d))
check("несуществующий коммутатор -> 404",
      c.get("/api/stats_ports/999999").status_code == 404 and c.get("/api/poe_status/999999").status_code == 404)

s, d = get(f"/api/poll_snmp/{sid}", "post")
check("SNMP-опрос 200", s == 200 and isinstance(d, dict) and "error" not in d, (s, str(d)[:200]))

s, ports = get(f"/api/stats_ports/{sid}")
check("порты после опроса", s == 200 and isinstance(ports, list) and len(ports) == 9, (s, ports))
if isinstance(ports, list) and ports:
    check("порты отсортированы по ifIndex", [p["ifindex"] for p in ports] == sorted([p["ifindex"] for p in ports], key=int), [p["ifindex"] for p in ports])

s, poe = get(f"/api/poe_status/{sid}")
check("PoE после опроса", s == 200 and isinstance(poe, dict) and set(poe) == {"1", "2", "3", "4"}, (s, poe))
if isinstance(poe, dict) and len(poe) == 4:
    check("PoE порт 2: delivering, 6.5 W", poe["2"]["poe"]["state"] == "delivering" and poe["2"]["poe"]["power_consumed"] == 6.5, poe["2"])
    check("PoE порт 1: searching, мощность неизвестна", poe["1"]["poe"]["state"] == "searching" and poe["1"]["poe"]["power_consumed"] is None, poe["1"])
    check("PoE порт 3: fault", poe["3"]["poe"]["state"] == "fault", poe["3"])
    check("PoE порт 4: выключен админом", poe["4"]["poe"]["state"] == "disabled" and poe["4"]["poe"]["enabled"] is False, poe["4"])

s, h = get(f"/api/switch_health/{sid}")
check("health после опроса", s == 200 and h.get("cpu_usage", 0) > 0 and h.get("last_poll_time"), (s, h))
check("RAM считается только по hrStorageRam (~40%, а не ~89%)", 35 < h.get("ram_usage", 0) < 45, h.get("ram_usage"))
s, t = get(f"/api/port_traffic/{sid}/3?limit=5")
check("трафик порта 3", s == 200 and isinstance(t, list) and len(t) == 1, (s, t))

fakesnmp.STATE["port2_up"] = True
s, d = get(f"/api/poll_snmp/{sid}", "post")
check("второй опрос 200", s == 200, s)
with sqlite3.connect(m.DB) as conn:
    ev = conn.execute("SELECT ifindex, event_type FROM port_events WHERE switch_id=?", (sid,)).fetchall()
check("событие 'порт 2 поднялся' записано", ("2", "up") in ev, ev)
s, hist = get(f"/api/switch_health_history/{sid}")
check("история: 2 записи", s == 200 and isinstance(hist, list) and len(hist) == 2, (s, hist))
s, t = get(f"/api/port_traffic/{sid}/3")
check("трафик: 2 записи", s == 200 and isinstance(t, list) and len(t) == 2, (s, t))

s, d = get(f"/api/duplicate_macs/{sid}")
check("дубликаты MAC 200", s == 200 and isinstance(d, list), (s, d))

for bad in ("/api/port_traffic/%d/3?limit=abc" % sid, "/api/switch_health_history/%d?limit=-5" % sid):
    s, d = get(bad)
    check("некорректный limit не роняет сервер: " + bad, s == 200, (s, str(d)[:100]))

print("\nИТОГО:", "все проверки пройдены" if not fails else f"провалено {len(fails)}: {fails}")
