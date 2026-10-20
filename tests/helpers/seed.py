"""Тестовая база в рабочей папке: два коммутатора, как в типичной установке, и «старая» версия схемы —
чтобы при первом запуске сработали миграция и резервная копия перед ней.
argv: <рабочая папка>"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # папка проекта
work = sys.argv[1]
os.makedirs(work, exist_ok=True)
os.chdir(work)
sys.path.insert(0, ROOT)
import app as m  # noqa: E402  (ключи switchmap.secret создаются в рабочей папке)

if os.path.exists(m.DB):
    os.remove(m.DB)
m.init_db()
m.migrate_db()
with sqlite3.connect(m.DB) as conn:
    cols = "id, name, ports, ip_address, snmp_community, switch_layout, patch_panels, connections, port_types, trunk_ports"
    conn.execute(f"INSERT INTO switches ({cols}) VALUES (1, 'Офис, 2 этаж', 52, '', 'public', 'single', '[]', '{{}}', "
                 "'{\"52\":\"sfp\"}', '{\"50\":true,\"52\":true}')")
    conn.execute(f"INSERT INTO switches ({cols}) VALUES (2, 'Серверная', 48, '', 'public', 'double', '[]', '{{}}', '{{}}', '{{}}')")
    conn.execute("INSERT INTO app_settings (key, value) VALUES ('schema_version', '4') "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value")
    conn.commit()
print("seed:", os.path.abspath(m.DB))
