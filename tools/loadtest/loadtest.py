"""Нагрузочная проверка: N коммутаторов в симуляторе SNMP, полный цикл опроса, страницы и база.

    python tools/loadtest/loadtest.py 300 [--polls 2] [--keep]

Нужен snmpsim (как для тестов: tests/.snmpsim или SNMPSIM_BIN). Все коммутаторы отвечают на 127.0.0.1:161,
различаются community; в приложении у них адреса 10.30.x.y (перенаправляются на симулятор).
Важно: симулятор на одном ядре отвечает медленнее настоящих коммутаторов, а сеть — быстрее (нет задержек),
поэтому абсолютные цифры — ориентир; главное — как время растёт с числом коммутаторов.
"""
import argparse
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tools", "screenshots"), os.path.join(ROOT, "tests")]


def make_network(n, out):
    """snmprec для n коммутаторов: чередуются Cisco 48+4 и D-Link 24+4, ~70% портов заняты."""
    import demo_network as dn
    rnd = random.Random(11)
    os.makedirs(out, exist_ok=True)
    specs = {}
    for i in range(n):
        cisco = i % 2 == 0
        key = f"sw{i:04d}"
        sw = dict(name=f"acc-{i:04d}", descr="Cisco IOS Software, C2960X-48FPS-L" if cisco else "D-Link DGS-1210-28",
                  obj="1.3.6.1.4.1.9.1.1208" if cisco else "1.3.6.1.4.1.171.10.76.17", location=f"Building {i // 20}",
                  copper=48 if cisco else 24, sfp=4, cisco=cisco, cpu=rnd.randint(5, 40),
                  temp=rnd.randint(35, 48) if cisco else None, mem=(524288, rnd.randint(150000, 300000)))
        ports = {}
        for p in range(1, sw["copper"] + sw["sfp"] + 1):
            sfp = p > sw["copper"]
            up = (p == sw["copper"] + 1) if sfp else rnd.random() < 0.7
            macs = [[0x02, i >> 8 & 255, i & 255, 0, p, k] for k in range(1 if rnd.random() < 0.8 else 2)] if up and not sfp else []
            ports[p] = dict(up=up, speed=10000 if sfp else 1000, rin=rnd.randint(1, 50) * 20_000 if up else 0,
                            rout=rnd.randint(1, 80) * 20_000 if up else 0, alias=f"Room {p}" if up and rnd.random() < 0.3 else "",
                            vlan=rnd.choice((10, 10, 10, 20, 30)) if not sfp else 1, macs=macs,
                            poe=rnd.choice((None, 3800, 5200)) if cisco and up and not sfp else None, errors=0)
        specs[key] = (sw, ports)
        with open(os.path.join(out, f"{key}.snmprec"), "w", encoding="utf-8", newline="\n") as f:
            f.write(dn.snmprec(key, sw, ports, {}))
    return specs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int)
    ap.add_argument("--polls", type=int, default=2)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix=f"switchmap-load{a.n}-")
    t0 = time.time()
    specs = make_network(a.n, os.path.join(tmp, "data"))
    print(f"сеть: {a.n} коммутаторов, {sum(len(p) for _s, p in specs.values())} портов, {time.time() - t0:.0f} с", flush=True)

    from run_all import find_snmpsim
    sim = subprocess.Popen([find_snmpsim(), f"--data-dir={os.path.join(tmp, 'data')}", "--agent-udpv4-endpoint=127.0.0.1:161",
                            f"--cache-dir={os.path.join(tmp, 'cache')}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    work = os.path.join(tmp, "work")
    os.makedirs(work)
    os.chdir(work)
    os.environ.setdefault("SWITCHMAP_UPDATE_CHECK", "0")
    try:
        from pysnmp.hlapi.v3arch import asyncio as h
        create = h.UdpTransportTarget.create.__func__

        @classmethod
        async def redirect(cls, address, *args, **kw):
            host, port = address
            return await create(cls, ("127.0.0.1" if host.startswith("10.30.") else host, port), *args, **kw)
        h.UdpTransportTarget.create = redirect

        import app as m
        import security
        m.ping_host = lambda ip, timeout=1: True
        m.resolve_hostnames = lambda ips, budget_sec=5: {}
        m.prepare_database()
        security.create_user(m.DB, "admin", "adminpass123", "admin")
        with sqlite3.connect(m.DB) as conn:
            for i, (key, (sw, ports)) in enumerate(specs.items()):
                conn.execute("INSERT INTO switches (name, ports, ip_address, snmp_community, switch_layout, patch_panels, "
                             "connections, port_types, trunk_ports) VALUES (?, ?, ?, ?, 'double', '[]', '{}', '{}', '{}')",
                             (sw["name"], len(ports), f"10.30.{i // 250}.{i % 250 + 1}", key))
            conn.commit()

        # симулятор готов, когда отвечает первый коммутатор
        for _ in range(120):
            if not m.poll_switch_snmp("10.30.0.1", "sw0000", 52).get("error"):
                break
            time.sleep(1)

        def db_bytes():
            with sqlite3.connect(m.DB) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                return conn.execute("PRAGMA page_count").fetchone()[0] * conn.execute("PRAGMA page_size").fetchone()[0]

        def db_size():
            return db_bytes()

        results, sizes = {}, []
        for k in range(a.polls):
            if k:
                time.sleep(5)
            sizes.append(db_size())
            t = time.time()
            m.scheduled_poll_all_switches()
            dt = time.time() - t
            sizes.append(db_size())
            results[f"poll{k + 1}"] = dt
            print(f"полный опрос #{k + 1}: {dt:.0f} с ({dt / a.n:.2f} с на коммутатор)", flush=True)
        with sqlite3.connect(m.DB) as conn:
            errors = conn.execute("SELECT COUNT(*) FROM switches WHERE last_poll_time IS NULL").fetchone()[0]
            rows = conn.execute("SELECT COUNT(*) FROM port_traffic").fetchone()[0]
            macs = conn.execute("SELECT COUNT(*) FROM mac_table").fetchone()[0]
        per_poll = (sizes[-1] - sizes[1]) / max(1, a.polls - 1) if a.polls > 1 else sizes[-1] - sizes[0]
        print(f"не опрошено: {errors}; записей трафика: {rows}; MAC в таблице: {macs}", flush=True)

        # Интерфейс на заполненной базе
        c = m.app.test_client()
        c.get("/login")
        with c.session_transaction() as s:
            csrf = s["csrf"]
        c.post("/login", data={"username": "admin", "password": "adminpass123", "csrf_token": csrf})
        with c.session_transaction() as s:  # после входа — новая сессия и новый токен
            c.environ_base["HTTP_X_CSRF_TOKEN"] = s["csrf"]

        def timed(label, fn, repeat=3):
            best = None
            for _ in range(repeat):
                t = time.time()
                r = fn()
                dt = time.time() - t
                best = dt if best is None else min(best, dt)
            code = getattr(r, "status_code", "")
            print(f"  {label:<38} {best * 1000:7.0f} мс  {code}", flush=True)
            results[label] = best
        print("интерфейс:")
        timed("главная (все коммутаторы)", lambda: c.get("/"))
        timed("страница коммутатора", lambda: c.get("/switch/1"))
        timed("загрузка портов (API)", lambda: c.get("/api/port_load/1"))
        timed("поиск по MAC", lambda: c.get("/api/search?q=02:00:05:00:07"))
        timed("поиск по тексту", lambda: c.get("/api/search?q=Room 12"))
        timed("события (колокольчик)", lambda: c.get("/api/port_events"))
        timed("журнал изменений", lambda: c.get("/api/audit"))
        timed("выгрузка всей сети в Excel", lambda: c.get("/export/inventory.xlsx"), repeat=1)
        timed("топология (LLDP со всех)", lambda: c.get("/api/topology"), repeat=1)
        timed("доступность (ping всех)", lambda: c.post("/api/status_bulk", json={"switches": [{"id": i + 1} for i in range(a.n)]}), repeat=1)
        timed("обслуживание базы", lambda: m.run_maintenance(), repeat=1)

        print(f"база: {db_bytes() / 1e6:.1f} МБ; прирост за опрос: {per_poll / 1e6:.2f} МБ; неделя подробных данных при опросе "
              f"раз в 5 мин: ~{per_poll * 288 * 7 / 1e9:.2f} ГБ (дальше — почасовая свёртка)", flush=True)
    finally:
        sim.terminate()
        os.chdir(ROOT)
        if not a.keep:
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print("папка:", tmp)


if __name__ == "__main__":
    main()
