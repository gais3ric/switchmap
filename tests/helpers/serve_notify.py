"""Копия приложения с подставными SNMP, Telegram и SMTP для браузерных тестов. argv: <рабочая папка с тестовой базой> <порт>"""
import os, sqlite3, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # папка проекта
HELPERS = os.path.dirname(os.path.abspath(__file__))
here = os.path.dirname(os.path.abspath(__file__))
app_dir, port = sys.argv[1], int(sys.argv[2])
os.chdir(app_dir); sys.path[:0] = [ROOT, HELPERS]; sys.path.insert(0, here)
import fakenotify as fk
_, tg_url = fk.start_telegram()
os.environ["SWITCHMAP_TELEGRAM_API"] = tg_url
_, smtp_port = fk.start_smtp("none", "mon@test.ru", "apppass")
import app as m
import fakesnmp, security
from flask import jsonify

m.prepare_database()
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM users")
    conn.execute("DELETE FROM app_settings WHERE key LIKE 'notify_%'")
    conn.execute("UPDATE switches SET ip_address='10.0.0.1', alert_state='{}', port_status_snapshot=NULL WHERE id=1")
    conn.execute("UPDATE switches SET ip_address='' WHERE id != 1")
    conn.commit()
security.create_user(m.DB, "admin", "adminpass123", "admin")
fakesnmp.install(m)
m.REACHABILITY_RECHECK_SEC = 0
m.poll_switch_and_log_events(1)  # базовый снимок


@m.app.route("/__test/info")
def t_info():
    return jsonify({"smtp_port": smtp_port, "token": fk.TOKEN, "tg_sent": fk.TG.sent,
                    "mail": [x["msg"]["Subject"] for x in fk.Mailbox.messages]})


@m.app.route("/__test/flip", methods=["POST"])
def t_flip():
    fakesnmp.STATE["port2_up"] = not fakesnmp.STATE["port2_up"]
    m.poll_switch_and_log_events(1)
    return jsonify({"ok": True})


@m.app.route("/__test/down", methods=["POST"])
def t_down():
    fakesnmp.STATE["fail"] = True
    m.poll_switch_and_log_events(1)
    fakesnmp.STATE["fail"] = False
    return jsonify({"ok": True})


@m.app.route("/__test/tgfail/<int:on>", methods=["POST"])
def t_tgfail(on):
    fk.TG.fail = bool(on)
    return jsonify({"ok": True})


m.app.run(port=port, debug=False, use_reloader=False, threaded=True)
