"""Запуск копии приложения с подставным SNMP. argv: <рабочая папка с тестовой базой> <порт>"""
import os, sqlite3, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # папка проекта
HELPERS = os.path.dirname(os.path.abspath(__file__))
here = os.path.dirname(os.path.abspath(__file__))
app_dir, port = sys.argv[1], int(sys.argv[2])
os.chdir(app_dir)
sys.path[:0] = [ROOT, HELPERS]
sys.path.insert(0, here)
import app as m
import fakesnmp

m.migrate_db()
import security; sqlite3.connect(m.DB).execute('DELETE FROM users').connection.commit(); security.create_user(m.DB, 'admin', 'adminpass123', 'admin')
fakesnmp.install(m)
from datetime import datetime, timedelta
with sqlite3.connect(m.DB) as conn:
    conn.execute("UPDATE switches SET ip_address='10.0.0.1' WHERE id=1")
    conn.execute("UPDATE switches SET ip_address='' WHERE id=2")  # сценарий «коммутатор без IP»
    # История порта 3: 12 опросов раз в 5 минут, нагрузка меняется, на 7-м — перезагрузка
    now = datetime.now()
    b_in = b_out = 1_000_000_000
    errs = 0
    for i in range(12):
        ts = (now - timedelta(minutes=5 * (12 - i))).strftime("%Y-%m-%d %H:%M:%S")
        if i == 7:
            b_in = b_out = 1000  # сброс счётчиков
        else:
            b_in += (20 + 15 * (i % 4)) * 1_000_000 * 300 // 8   # 20..65 Мбит/с
            b_out += (5 + 3 * (i % 3)) * 1_000_000 * 300 // 8    # 5..11 Мбит/с
        errs += 3 if i == 9 else 0
        conn.execute("""INSERT INTO port_traffic (switch_id, ifindex, timestamp, bytes_in, bytes_out,
                        packets_in, packets_out, errors_in, errors_out, counter_bits)
                        VALUES (1, '3', ?, ?, ?, 0, 0, ?, 0, 64)""", (ts, b_in, b_out, errs))
    conn.commit()
m.run_maintenance()  # как при запуске приложения: скорость для засеянной истории
m.app.run(port=port, debug=False, use_reloader=False)

