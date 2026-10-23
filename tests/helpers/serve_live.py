"""Копия приложения против snmpsim (127.0.0.1:161). Перед запуском — два опроса с интервалом 10 с.
argv: <рабочая папка с тестовой базой> <порт>"""
import json, os, sqlite3, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # папка проекта
HELPERS = os.path.dirname(os.path.abspath(__file__))
app_dir, port = sys.argv[1], int(sys.argv[2])
os.chdir(app_dir); sys.path[:0] = [ROOT, HELPERS]
import app as m

m.migrate_db()
import security; sqlite3.connect(m.DB).execute('DELETE FROM users').connection.commit(); security.create_user(m.DB, 'admin', 'adminpass123', 'admin')
m.ping_host = lambda ip, timeout=1: True
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM switches")
    for t in ("port_traffic", "switch_health", "port_events", "mac_table", "devices"):
        conn.execute(f"DELETE FROM {t}")
    ins = """INSERT INTO switches (id, name, ports, ip_address, snmp_community, switch_layout, patch_panels,
             connections, port_types, trunk_ports) VALUES (?, ?, ?, '127.0.0.1', ?, ?, '[]', '{}', '{}', '{}')"""
    conn.execute(ins, (1, "Ядро Cisco", 10, "public", "single"))
    conn.execute("UPDATE switches SET connections=? WHERE id=1", (json.dumps(
        {"7": {"name": "Склад принтер", "color": "red", "patchPanel": None, "patch": None}}),))
    conn.execute(ins, (2, "Доступ D-Link", 8, "edge2", "single"))
    conn.commit()
for _ in range(2):
    for sid in (1, 2):
        r = m.poll_switch_and_log_events(sid)
        if "error" in r:
            print("POLL ERROR", sid, r, flush=True)
    time.sleep(12)  # скорость считается по интервалу не короче 10 с
print("READY", flush=True)
m.app.run(port=port, debug=False, use_reloader=False)
