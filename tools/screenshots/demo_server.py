"""Демо-сервер для скриншотов: база с демо-сетью, три настоящих опроса snmpsim и суточная история.

    python tools/screenshots/demo_server.py <рабочая папка> <порт>

Язык записей (события, журнал) — SWITCHMAP_LANG. Вход: admin / adminpass123.
"""
import json
import math
import os
import random
import sqlite3
import sys
import time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
work, port = sys.argv[1], int(sys.argv[2])
os.makedirs(work, exist_ok=True)
os.chdir(work)
sys.path[:0] = [ROOT, HERE]

# Демо-адреса 10.20.0.x → симулятор на 127.0.0.1 (community выбирает коммутатор)
from pysnmp.hlapi.v3arch import asyncio as snmp_hlapi  # noqa: E402
_create = snmp_hlapi.UdpTransportTarget.create.__func__


@classmethod
async def _demo_create(cls, address, *a, **k):
    host, p = address
    return await _create(cls, ("127.0.0.1" if host.startswith("10.20.") else host, p), *a, **k)


snmp_hlapi.UdpTransportTarget.create = _demo_create

import app as m  # noqa: E402
import security  # noqa: E402
from demo_network import SWITCHES, main as make_plans  # noqa: E402

m.ping_host = lambda ip, timeout=1: True
m.resolve_hostnames = lambda ips, budget_sec=5: {}
rnd = random.Random(3)

if os.path.exists(m.DB):
    os.remove(m.DB)
m.prepare_database()
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM users")
    conn.commit()
security.create_user(m.DB, "admin", "adminpass123", "admin")

plans = make_plans(os.path.join(work, "snmprec-copy"))  # те же данные, что у симулятора (тот же seed)
MODELS = {"core": "Cisco · C9300-48P", "floor2": "Cisco · C2960X-24PS-L", "floor3": "D-Link · DGS-1210-28",
          "warehouse": "HPE Aruba · 2530-24G"}
ids = {}
with sqlite3.connect(m.DB) as conn:
    for n, (key, sw) in enumerate(SWITCHES.items(), start=1):
        total = sw["copper"] + sw["sfp"]
        port_types = {str(p): "sfp" for p in range(sw["copper"] + 1, total + 1)}
        uplink = 49 if key == "core" else 25
        trunks = {str(p): True for p in ((49, 50, 51) if key == "core" else (uplink,))}
        panels, conns = [], {}
        if key in ("core", "floor2"):
            panels = [{"id": 1, "name": "PP-1" if key == "floor2" else "PP-A1", "ports": 24, "position": "above",
                       "layout": "single"}]
            colors = ["blue", "blue", "green", "yellow", "gray", "red"]
            for p, info in plans[key].items():
                if info["alias"] and p <= 24:
                    conns[str(p)] = {"name": info["alias"], "color": colors[p % len(colors)], "patchPanel": 1, "patch": p}
        cur = conn.execute(
            "INSERT INTO switches (name, ports, ip_address, snmp_community, switch_layout, patch_panels, connections, "
            "port_types, trunk_ports, model) VALUES (?, ?, ?, ?, 'double', ?, ?, ?, ?, ?)",
            (sw["name"], total, f"10.20.0.{n}", key, json.dumps(panels), json.dumps(conns), json.dumps(port_types),
             json.dumps(trunks), MODELS[key]))
        ids[key] = cur.lastrowid
    conn.commit()

# Три опроса с интервалом — появляются скорости, загрузка и оповещения
for i in range(3):
    for key, sid in ids.items():
        r = m.poll_switch_and_log_events(sid)
        if "error" in r:
            print("POLL ERROR", key, r, flush=True)
    if i < 2:
        time.sleep(12)


def day_factor(t):
    """Рабочий день: ночью 15%, днём до 100%, с шумом."""
    h = t.hour + t.minute / 60
    work = max(0.0, math.sin(math.pi * (h - 7.5) / 11)) if 7.5 <= h <= 18.5 else 0.0
    return 0.12 + rnd.random() * 0.06 + 0.82 * work * (0.85 + rnd.random() * 0.3)


# Суточная история: счётчики «назад» от первого настоящего опроса, шаг 5 минут
with sqlite3.connect(m.DB) as conn:
    for key, sid in ids.items():
        rows = conn.execute("SELECT ifindex, MIN(timestamp), bytes_in, bytes_out, counter_bits FROM port_traffic "
                            "WHERE switch_id=? GROUP BY ifindex", (sid,)).fetchall()
        hist = []
        for ifindex, ts, b_in, b_out, bits in rows:
            info = plans[key].get(int(ifindex)) if str(ifindex).isdigit() else None
            if not info or not info["up"]:
                continue
            mod = 2 ** (bits or 64)
            t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            for step in range(1, 289):
                t2 = t - timedelta(minutes=5 * step)
                f = day_factor(t2)
                b_in = (b_in - int(info["rin"] * f * 300)) % mod
                b_out = (b_out - int(info["rout"] * f * 300)) % mod
                hist.append((sid, ifindex, t2.strftime("%Y-%m-%d %H:%M:%S"), b_in, b_out, 0, 0, 0, 0, bits))
        conn.executemany("INSERT INTO port_traffic (switch_id, ifindex, timestamp, bytes_in, bytes_out, packets_in, "
                         "packets_out, errors_in, errors_out, counter_bits) VALUES (?,?,?,?,?,?,?,?,?,?)", hist)
        sw = SWITCHES[key]
        now = datetime.now()
        health = []
        for step in range(1, 289):
            t2 = now - timedelta(minutes=5 * step)
            f = day_factor(t2)
            health.append((sid, t2.strftime("%Y-%m-%d %H:%M:%S"), round(sw["cpu"] * (0.5 + f * 0.8), 1),
                           round(sw["mem"][1] / sw["mem"][0] * 100 + rnd.random() * 2, 1),
                           round(sw["temp"] - 1.2 + f * 1.6 + rnd.random() * 0.2, 1) if sw["temp"] else None))
        conn.executemany("INSERT INTO switch_health (switch_id, timestamp, cpu_usage, ram_usage, temperature) "
                         "VALUES (?,?,?,?,?)", health)
    # История должна идти по порядку id так же, как по времени (графики читают записи по id)
    for table, cols in (("port_traffic", "switch_id, ifindex, timestamp, bytes_in, bytes_out, packets_in, packets_out, "
                                         "errors_in, errors_out, counter_bits"),
                        ("switch_health", "switch_id, timestamp, cpu_usage, ram_usage, temperature")):
        rows = conn.execute(f"SELECT {cols} FROM {table} ORDER BY timestamp, id").fetchall()
        conn.execute(f"DELETE FROM {table}")
        conn.executemany(f"INSERT INTO {table} ({cols}) VALUES ({','.join('?' * len(cols.split(','))) })", rows)
    # Несколько событий за последние часы: порты падали и поднимались
    ev = []
    for key, p, hours in (("floor2", 7, 5.2), ("floor3", 10, 3.1), ("warehouse", 2, 1.4), ("floor2", 3, 0.6)):
        t = datetime.now() - timedelta(hours=hours)
        for typ, dt in (("down", 0), ("up", 7)):
            ev.append((ids[key], str(p), str(p), p, typ, (t + timedelta(minutes=dt)).strftime("%Y-%m-%d %H:%M:%S"), None,
                       1 if hours > 2 else 0))
    conn.executemany("INSERT INTO port_events (switch_id, ifindex, port_name, port_number, event_type, event_time, "
                     "details, is_read) VALUES (?,?,?,?,?,?,?,?)", ev)
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('update_check', '0')")
    conn.commit()

m.run_maintenance()  # скорости и почасовые итоги для вставленной истории
print("READY", flush=True)
m.app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)
