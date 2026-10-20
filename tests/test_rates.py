"""Тесты расчёта скорости трафика. argv: <рабочая папка с тестовой базой>"""
import os, sqlite3, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
HELPERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers")
sys.stdout.reconfigure(encoding='utf-8')
here = os.path.dirname(os.path.abspath(__file__))
app_dir = sys.argv[1]
os.chdir(app_dir)
sys.path[:0] = [ROOT, HELPERS]
sys.path.insert(0, here)
import app as m
import fakesnmp

fails = []
def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""))
    if not cond:
        fails.append(name)

def row(ts, b_in, b_out, e_in=0, e_out=0, bits=32):
    return {"timestamp": ts, "bytes_in": b_in, "bytes_out": b_out, "errors_in": e_in, "errors_out": e_out, "counter_bits": bits}

# ── _counter_delta
cd = m._counter_delta
check("обычный прирост", cd(1500, 1000, 32) == 500)
check("32 бита: одно переполнение", cd(100, 2**32 - 100, 32) == 200, cd(100, 2**32 - 100, 32))
check("64 бита: уменьшение = сброс → None", cd(100, 10**12, 64) is None)
big = 2**63 + 5
check("64 бита: значения > 2^63 через хранение со знаком",
      cd(m._to_sqlite_int(big + 1000), m._to_sqlite_int(big), 64) == 1000)
check("_to_sqlite_int влезает в SQLite", -2**63 <= m._to_sqlite_int(2**64 - 1) < 2**63)
check("None → None", cd(None, 5, 32) is None)

# ── compute_traffic_rates (записи от новых к старым)
r = m.compute_traffic_rates([
    row("2026-10-19 10:05:00", 1000 + 75_000_000, 1000 + 37_500_000, 7, 1, 64),  # +75 МБ за 300 с = 2 Мбит/с
    row("2026-10-19 10:00:00", 1000, 1000, 2, 0, 64),
])
check("скорость: 75 МБ за 5 мин = 2 Мбит/с", r[0]["in_mbps"] == 2.0 and r[0]["out_mbps"] == 1.0, r[0])
check("интервал 300 с", r[0]["interval_sec"] == 300)
check("ошибки за интервал", r[0]["errors_in_delta"] == 5 and r[0]["errors_out_delta"] == 1)
check("у самой старой записи скорости нет", r[1]["interval_sec"] is None and r[1]["in_mbps"] is None)

r = m.compute_traffic_rates([row("2026-10-19 10:05:00", 50, 50, 0, 0, 64), row("2026-10-19 10:00:00", 10**9, 10**9, 9, 9, 64)])
check("перезагрузка (64 бита): скорость None, интервал есть", r[0]["in_mbps"] is None and r[0]["interval_sec"] == 300, r[0])
check("перезагрузка: ошибки уменьшились → None", r[0]["errors_in_delta"] is None)

r = m.compute_traffic_rates([row("2026-10-19 10:00:00", 2000, 2000), row("2026-10-19 10:00:00", 1000, 1000)])
check("два опроса в одну секунду: интервала нет", r[0]["interval_sec"] is None)

r = m.compute_traffic_rates([row("2026-10-19 10:05:00", 2000, 2000, bits=64), row("2026-10-19 10:00:00", 1000, 1000, bits=32)])
check("сменилась разрядность счётчика: скорость не считаем", r[0]["in_mbps"] is None)

r = m.compute_traffic_rates([row("2026-10-19 10:01:00", 100, 100), row("2026-10-19 10:00:00", 2**32 - 7_499_900, 2**32 - 100)])
check("32 бита: переполнение даёт верную скорость (7.5 МБ/60 с = 1 Мбит/с)", r[0]["in_mbps"] == 1.0, r[0])

r = m.compute_traffic_rates([row("bad", 1, 1), row("2026-10-19 10:00:00", 0, 0)])
check("кривая метка времени не роняет расчёт", r[0]["interval_sec"] is None)

# ── миграция: старая таблица без counter_bits
with sqlite3.connect(m.DB) as conn:
    conn.execute("DROP TABLE IF EXISTS port_traffic")
    conn.execute("""CREATE TABLE port_traffic (id INTEGER PRIMARY KEY AUTOINCREMENT, switch_id INTEGER, ifindex TEXT,
        timestamp TEXT, bytes_in INTEGER, bytes_out INTEGER, packets_in INTEGER, packets_out INTEGER,
        errors_in INTEGER, errors_out INTEGER)""")
    conn.execute("INSERT INTO port_traffic (switch_id, ifindex, timestamp, bytes_in, bytes_out, errors_in, errors_out) VALUES (1,'7','2026-10-19 09:55:00',0,0,0,0)")
    conn.commit()
m.migrate_db()
with sqlite3.connect(m.DB) as conn:
    cols = [c[1] for c in conn.execute("PRAGMA table_info(port_traffic)")]
    old_bits = conn.execute("SELECT counter_bits FROM port_traffic WHERE ifindex='7'").fetchone()[0]
check("миграция добавила counter_bits", "counter_bits" in cols, cols)
check("старые записи считаются 32-битными", old_bits == 32, old_bits)

# ── опрос: 64 бита там, где есть ifHC*, 32 — где нет
fakesnmp.install(m)
with sqlite3.connect(m.DB) as conn:
    conn.execute("UPDATE switches SET ip_address='10.0.0.1' WHERE id=1")
    conn.commit()
import authhelp; c = authhelp.admin_client(m)
check("опрос 200", c.post("/api/poll_snmp/1").status_code == 200)
with sqlite3.connect(m.DB) as conn:
    bits = dict(conn.execute("SELECT ifindex, counter_bits FROM port_traffic WHERE switch_id=1 AND timestamp > '2026-10-19 10:00:00'").fetchall())
check("порт 3 сохранён с 64-битным счётчиком", bits.get("3") == 64, bits)
check("порт 5 (нет ifHC) — с 32-битным", bits.get("5") == 32, bits)

# ── API: история с точным расчётом
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM port_traffic WHERE ifindex='99'")
    for i in range(6):  # 6 опросов раз в 5 минут, по 37.5 МБ входящих = 1 Мбит/с
        conn.execute("""INSERT INTO port_traffic (switch_id, ifindex, timestamp, bytes_in, bytes_out, errors_in, errors_out, counter_bits)
                        VALUES (1, '99', ?, ?, ?, ?, 0, 64)""",
                     (f"2026-10-19 11:{i*5:02d}:00", i * 37_500_000, i * 75_000_000, i))
    conn.commit()
d = c.get("/api/port_traffic/1/99?limit=3").get_json()
check("limit=3 → 3 записи", len(d) == 3, len(d))
check("все 3 записи со скоростью (берётся limit+1 строк)", all(x["in_mbps"] == 1.0 and x["out_mbps"] == 2.0 for x in d), d)
check("порядок от новых к старым", d[0]["timestamp"] > d[-1]["timestamp"])
d = c.get("/api/port_traffic/1/99?limit=100").get_json()
check("limit больше истории → 6 записей, у старейшей нет скорости", len(d) == 6 and d[-1]["in_mbps"] is None)

print("\nИТОГО:", "все проверки пройдены" if not fails else f"провалено {len(fails)}: {fails}")
