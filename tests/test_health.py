"""CPU, память и температура коммутаторов разных производителей (без сети: ответы SNMP подставляются).
argv: <рабочая папка с тестовой базой>"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(sys.argv[1]); sys.path[:0] = [ROOT]

fails = []
def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""))
    if not cond:
        fails.append(name)

import app as m

CPU_PROC = "1.3.6.1.4.1.9.9.109.1.1.1.1.7"
DEVICES = {
    # Cisco Catalyst 2960: только свои таблицы, температуры нет (только состояние)
    "cisco-2960": ({f"{CPU_PROC}.1": 12, "1.3.6.1.4.1.9.9.48.1.1.1.5.1": 30_000_000, "1.3.6.1.4.1.9.9.48.1.1.1.6.1": 70_000_000,
                    "1.3.6.1.4.1.9.9.48.1.1.1.5.2": 5_000_000, "1.3.6.1.4.1.9.9.48.1.1.1.6.2": 5_000_000},
                   {"cpu_usage": 12, "ram_usage": 30, "temperature": 0}),
    # Cisco старой прошивки: cpmCPUTotal1min; температура через CISCO-ENVMON
    "cisco-old": ({"1.3.6.1.4.1.9.9.109.1.1.1.1.4.1": 7, "1.3.6.1.4.1.9.9.48.1.1.1.5.1": 1, "1.3.6.1.4.1.9.9.48.1.1.1.6.1": 3,
                   "1.3.6.1.4.1.9.9.13.1.3.1.3.1005": 38},
                  {"cpu_usage": 7, "ram_usage": 25, "temperature": 38}),
    # Cisco IOS-XE: память в ENHANCED-MEMPOOL, температура в CISCO-ENTITY-SENSOR (тип 8, точность 0)
    "cisco-xe": ({f"{CPU_PROC}.7000": 4, "1.3.6.1.4.1.9.9.221.1.1.1.1.7.7000.1": 600, "1.3.6.1.4.1.9.9.221.1.1.1.1.8.7000.1": 400,
                  "1.3.6.1.4.1.9.9.91.1.1.1.1.1.1010": 8, "1.3.6.1.4.1.9.9.91.1.1.1.1.4.1010": 44,
                  "1.3.6.1.4.1.9.9.91.1.1.1.1.1.1011": 12, "1.3.6.1.4.1.9.9.91.1.1.1.1.4.1011": 5000},
                 {"cpu_usage": 4, "ram_usage": 60, "temperature": 44}),
    # MikroTik RouterOS 7: HOST-RESOURCES (только RAM-строки) и таблица датчиков (единица 1 — °C)
    "mikrotik": ({"1.3.6.1.2.1.25.3.3.1.2.1": 3, "1.3.6.1.2.1.25.3.3.1.2.2": 5,
                  "1.3.6.1.2.1.25.2.3.1.2.65536": "1.3.6.1.2.1.25.2.1.2", "1.3.6.1.2.1.25.2.3.1.4.65536": 1024,
                  "1.3.6.1.2.1.25.2.3.1.5.65536": 1000, "1.3.6.1.2.1.25.2.3.1.6.65536": 250,
                  "1.3.6.1.2.1.25.2.3.1.2.131072": "1.3.6.1.2.1.25.2.1.4", "1.3.6.1.2.1.25.2.3.1.4.131072": 1024,
                  "1.3.6.1.2.1.25.2.3.1.5.131072": 1000, "1.3.6.1.2.1.25.2.3.1.6.131072": 900,
                  "1.3.6.1.4.1.14988.1.1.3.100.1.3.17": 49, "1.3.6.1.4.1.14988.1.1.3.100.1.4.17": 1,
                  "1.3.6.1.4.1.14988.1.1.3.100.1.3.13": 24, "1.3.6.1.4.1.14988.1.1.3.100.1.4.13": 4},
                 {"cpu_usage": 4, "ram_usage": 25, "temperature": 49}),
    # MikroTik RouterOS 6: температура в десятых долях градуса
    "mikrotik-v6": ({"1.3.6.1.2.1.25.3.3.1.2.1": 9, "1.3.6.1.4.1.14988.1.1.3.10.0": 415},
                    {"cpu_usage": 9, "ram_usage": 0, "temperature": 41.5}),
    # D-Link DGS: DLINK-AGENT-MIB (проценты)
    "dlink": ({"1.3.6.1.4.1.171.12.1.1.6.2.0": 11, "1.3.6.1.4.1.171.12.1.1.9.1.4.1": 47},
              {"cpu_usage": 11, "ram_usage": 47, "temperature": 0}),
    # HPE ProCurve / Aruba
    "hpe": ({"1.3.6.1.4.1.11.2.14.11.5.1.9.6.1.0": 6, "1.3.6.1.4.1.11.2.14.11.5.1.1.2.1.1.1.5.1": 200,
             "1.3.6.1.4.1.11.2.14.11.5.1.1.2.1.1.1.7.1": 50},
            {"cpu_usage": 6, "ram_usage": 25, "temperature": 0}),
    # Huawei: таблица сущностей, у большинства строк нули — берём заполненную
    "huawei": ({"1.3.6.1.4.1.2011.5.25.31.1.1.1.1.5.67108867": 0, "1.3.6.1.4.1.2011.5.25.31.1.1.1.1.5.67108873": 21,
                "1.3.6.1.4.1.2011.5.25.31.1.1.1.1.7.67108873": 63, "1.3.6.1.4.1.2011.5.25.31.1.1.1.1.11.67108873": 52},
               {"cpu_usage": 21, "ram_usage": 63, "temperature": 52}),
    # Juniper EX
    "juniper": ({"1.3.6.1.4.1.2636.3.1.13.1.8.9.1.0.0": 14, "1.3.6.1.4.1.2636.3.1.13.1.11.9.1.0.0": 33,
                 "1.3.6.1.4.1.2636.3.1.13.1.7.9.1.0.0": 40},
                {"cpu_usage": 14, "ram_usage": 33, "temperature": 40}),
    # Cisco Business / Eltex MES (RADLAN-MIB) и TP-Link JetStream
    "eltex": ({"1.3.6.1.4.1.89.1.8.0": 17}, {"cpu_usage": 17, "ram_usage": 0, "temperature": 0}),
    "tplink": ({"1.3.6.1.4.1.11863.6.4.1.1.1.1.3.1": 8, "1.3.6.1.4.1.11863.6.4.1.2.1.1.2.1": 39},
               {"cpu_usage": 8, "ram_usage": 39, "temperature": 0}),
    # Стандартный ENTITY-SENSOR-MIB с точностью 1 знак (412 → 41.2 °C)
    "entity-sensor": ({"1.3.6.1.2.1.99.1.1.1.1.5": 8, "1.3.6.1.2.1.99.1.1.1.3.5": 1, "1.3.6.1.2.1.99.1.1.1.4.5": 412},
                      {"cpu_usage": 0, "ram_usage": 0, "temperature": 41.2}),
    "nothing": ({}, {"cpu_usage": 0, "ram_usage": 0, "temperature": 0}),
}

walks = []
current = {}
def fake_walk(ip, auth, oid, timeout=3):
    walks.append(oid)
    prefix = oid + "."
    return [(k, v) for k, v in sorted(current.items()) if k.startswith(prefix)]

m.snmp_walk = fake_walk
for name, (data, want) in DEVICES.items():
    current = data
    m._health_source_cache.clear()
    got = m.poll_switch_health(f"10.0.0.{len(walks) % 250}", "public")
    ok = all(abs(got[k] - v) < 0.06 for k, v in want.items())
    check(f"{name}: CPU {want['cpu_usage']}%, память {want['ram_usage']}%, температура {want['temperature']}",
          ok, got if not ok else "")

# Повторный опрос: только найденные источники, неподдерживаемое не перебирается каждый раз
current = DEVICES["cisco-2960"][0]
m._health_source_cache.clear()
walks.clear(); m.poll_switch_health("10.9.9.1", "public"); first = len(walks)
walks.clear(); r = m.poll_switch_health("10.9.9.1", "public"); second = len(walks)
check("повторный опрос — только запомненные источники", second <= 4 and second < first and r["cpu_usage"] == 12,
      {"первый": first, "повторный": second})
check("температуры нет — повторно не ищется в течение часа",
      not any(w.startswith(("1.3.6.1.4.1.9.9.13", "1.3.6.1.2.1.99", "1.3.6.1.4.1.14988")) for w in walks), walks)
m._health_source_cache["10.9.9.1"]["temp"] = ("", 0)  # прошёл час
walks.clear(); m.poll_switch_health("10.9.9.1", "public")
check("через час — проверяется снова", any(w.startswith("1.3.6.1.4.1.9.9.13") for w in walks))
# Источник перестал отвечать (обновили прошивку) — находится другой
current = DEVICES["mikrotik"][0]
r = m.poll_switch_health("10.9.9.1", "public")
check("сменился источник — находится новый", r["cpu_usage"] == 4 and m._health_source_cache["10.9.9.1"]["cpu"][0] == "host-resources", r)
current = {f"{CPU_PROC}.1": 250}
m._health_source_cache.clear()
check("CPU больше 100% не бывает", m.poll_switch_health("10.9.9.2", "public")["cpu_usage"] == 100)

print(f"\nИТОГО: {'провалено ' + str(len(fails)) if fails else 'все проверки пройдены'}")
sys.exit(1 if fails else 0)
