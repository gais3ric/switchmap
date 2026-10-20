"""Копия приложения с настоящим snmpsim (127.0.0.1) и поддельным NetBox. argv: <рабочая папка с тестовой базой> <порт>"""
import os, sqlite3, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # папка проекта
HELPERS = os.path.dirname(os.path.abspath(__file__))
here = os.path.dirname(os.path.abspath(__file__))
app_dir, port = sys.argv[1], int(sys.argv[2])
os.chdir(app_dir); sys.path[:0] = [ROOT, HELPERS]; sys.path.insert(0, here)
import fakenetbox
_, nb_url = fakenetbox.start()
import app as m
import security
from flask import jsonify

m.prepare_database()
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM users")
    conn.execute("DELETE FROM switches")
    conn.execute("DELETE FROM app_settings WHERE key='netbox_config'")
    conn.execute("INSERT INTO switches (name, ports, ip_address, patch_panels, connections) VALUES ('Этаж 2', 24, '10.0.0.1', '[]', '{}')")
    conn.commit()
security.create_user(m.DB, "admin", "adminpass123", "admin")


@m.app.route("/__test/nb")
def t_nb():
    return jsonify({"url": nb_url})


print("READY", flush=True)
m.app.run(port=port, debug=False, use_reloader=False, threaded=True)
