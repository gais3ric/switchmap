"""Уведомления: Telegram и почта на поддельных серверах, фильтры, повторы, мигание. argv: <рабочая папка с тестовой базой>"""
import html.parser, json, os, sqlite3, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
HELPERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers")
from datetime import datetime, timedelta
sys.stdout.reconfigure(encoding='utf-8')
app_dir = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
os.chdir(app_dir); sys.path[:0] = [ROOT, HELPERS]; sys.path.insert(0, here)
import fakenotify as fk
tg_srv, tg_url = fk.start_telegram()
os.environ["SWITCHMAP_TELEGRAM_API"] = tg_url
import app as m
import notify, security, fakesnmp
from authhelp import admin_client

fails = []
def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""))
    if not cond:
        fails.append(name)

m.prepare_database()
m.app.config["PROPAGATE_EXCEPTIONS"] = False
fakesnmp.install(m)
m.REACHABILITY_RECHECK_SEC = 0
with sqlite3.connect(m.DB) as conn:
    conn.execute("UPDATE switches SET ip_address='10.0.0.1', alert_state='{}', port_status_snapshot=NULL, connections='{}', trunk_ports='{}' WHERE id=1")
    conn.execute("UPDATE switches SET ip_address='' WHERE id != 1")
    conn.execute("DELETE FROM app_settings WHERE key LIKE 'notify_%'")
    conn.execute("DELETE FROM users")
    conn.commit()
c = admin_client(m)
J = {"Content-Type": "application/json"}

def post(url, body=None):
    r = c.post(url, data=json.dumps(body or {}), headers=J)
    return r.status_code, r.get_json()

def last_events(n=5):
    with sqlite3.connect(m.DB) as conn:
        return conn.execute("SELECT event_type, details FROM port_events ORDER BY id DESC LIMIT ?", (n,)).fetchall()

class TagCheck(html.parser.HTMLParser):
    """Telegram принимает только b, i, a, code, pre… и сбалансированные теги."""
    def __init__(self):
        super().__init__(); self.stack = []; self.bad = []
    def handle_starttag(self, tag, attrs):
        if tag not in ("b", "i", "a", "code", "pre", "u", "s"): self.bad.append(tag)
        self.stack.append(tag)
    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag: self.bad.append("/" + tag)
def valid_tg_html(text):
    p = TagCheck(); p.feed(text); p.close()
    return not p.bad and not p.stack

# ── Доступ и значения по умолчанию
r = c.get("/api/notify"); d = r.get_json()
check("GET /api/notify: по умолчанию всё выключено", r.status_code == 200 and not d["config"]["telegram"]["enabled"]
      and not d["config"]["email"]["enabled"] and d["config"]["telegram"]["has_token"] is False)
check("страница /notifications открывается", c.get("/notifications").status_code == 200)
security.create_user(m.DB, "viewer1", "Viewerpass1", "viewer")
from authhelp import login
v = login(m, "viewer1", "Viewerpass1")
check("наблюдатель: /api/notify и /notifications → 403",
      v.get("/api/notify").status_code == 403 and v.get("/notifications").status_code == 403
      and v.post("/api/notify", json={}).status_code == 403)
check("в навигации пункт есть у администратора и нет у наблюдателя",
      'href="/notifications"' in c.get("/").get_data(as_text=True) and 'href="/notifications"' not in v.get("/").get_data(as_text=True))

# ── Проверка формы
base_cfg = d["config"]
def cfg_with(**over):
    x = json.loads(json.dumps(base_cfg))
    for path, val in over.items():
        cur = x; keys = path.split("__")
        for k in keys[:-1]: cur = cur[k]
        cur[keys[-1]] = val
    return x
code, r = post("/api/notify", cfg_with(telegram__enabled=True))
check("Telegram без токена не включается", code == 400 and "токен" in r["error"], r)
code, r = post("/api/notify", cfg_with(email__recipients="admin@ok.ru, плохой адрес"))
check("неверный адрес получателя — ошибка", code == 400 and "плохой адрес" in r["error"], r)
code, r = post("/api/notify", cfg_with(base_url="10.0.0.5:5000"))
check("адрес для ссылок без http:// — ошибка", code == 400, r)

# ── Telegram: поиск чатов
code, r = post("/api/notify/telegram/chats", {"config": cfg_with(telegram__token="wrong")})
check("неверный токен — понятная ошибка", r["ok"] is False and "токен" in r["error"], r)
code, r = post("/api/notify/telegram/chats", {"config": cfg_with(telegram__token=fk.TOKEN)})
check("«Найти чаты»: бот и два чата без повторов", r["ok"] and r["bot"]["username"] == "switchmap_test_bot"
      and sorted(x["id"] for x in r["chats"]) == ["-1009", "111"], r)
check("названия чатов понятные", any(x["title"] == "Иван (@ivan)" and x["kind"] == "личный чат" for x in r["chats"])
      and any(x["title"] == "Сетевики" and x["kind"] == "группа" for x in r["chats"]), r["chats"])

# ── Telegram: тест до сохранения
fk.TG.sent.clear()
code, r = post("/api/notify/test", {"channel": "telegram", "config": cfg_with(telegram__token=fk.TOKEN, telegram__chats=[{"id": "111", "title": "Иван"}])})
check("тестовое сообщение в Telegram", r["ok"] and len(fk.TG.sent) == 1 and "Тестовое сообщение" in fk.TG.sent[0]["text"]
      and fk.TG.sent[0]["parse_mode"] == "HTML" and valid_tg_html(fk.TG.sent[0]["text"]), r)
code, r = post("/api/notify/test", {"channel": "telegram", "config": cfg_with(telegram__token=fk.TOKEN, telegram__chats=[{"id": "-404"}])})
check("чат не найден — подсказка написать /start", r["ok"] is False and "/start" in r["error"], r)
fk.TG.fail = True
code, r = post("/api/notify/test", {"channel": "telegram", "config": cfg_with(telegram__token=fk.TOKEN, telegram__chats=[{"id": "111"}])})
fk.TG.fail = False
check("Telegram недоступен — понятная ошибка", r["ok"] is False and "временно недоступен" in r["error"], r)

# ── Сохранение: токен шифруется и не отдаётся
code, r = post("/api/notify", cfg_with(base_url="http://sm.local:5000", flap_limit=0, telegram__enabled=True, telegram__token=fk.TOKEN,
                                       telegram__chats=[{"id": "111", "title": "Иван"}]))
check("Telegram включён и сохранён", code == 200 and r["config"]["telegram"]["enabled"] and r["config"]["telegram"]["has_token"]
      and "token" not in r["config"]["telegram"], r)
with sqlite3.connect(m.DB) as conn:
    raw = conn.execute("SELECT value FROM app_settings WHERE key='notify_config'").fetchone()[0]
check("в базе токен зашифрован", fk.TOKEN not in raw and "enc:v1:" in raw)
code, r = post("/api/notify", r["config"])  # повторное сохранение без токена — прежний остаётся
check("пустое поле токена не стирает сохранённый", code == 200 and r["config"]["telegram"]["has_token"])
with sqlite3.connect(m.DB) as conn:
    a = conn.execute("SELECT summary, details FROM audit_log WHERE action='notify_settings' ORDER BY id DESC LIMIT 1").fetchone()
check("изменение настроек в журнале, без токена", a and "Telegram" in a[0] and fk.TOKEN not in a[1], a)

# ── Поток событий: опрос → событие → сообщение
fk.TG.sent.clear()
fakesnmp.STATE.update(fail=False, port2_up=False)
m.poll_switch_and_log_events(1)  # базовый снимок, событий нет
rep = m.dispatch_notifications()
check("без событий ничего не отправляется", not fk.TG.sent, rep)
fakesnmp.STATE["port2_up"] = True
m.poll_switch_and_log_events(1)
rep = m.dispatch_notifications()
check("порт поднялся → сообщение в Telegram", len(fk.TG.sent) == 1 and "порт 2" in fk.TG.sent[0]["text"]
      and "поднялся" in fk.TG.sent[0]["text"], fk.TG.sent)
check("в сообщении ссылка на коммутатор и порт", 'href="http://sm.local:5000/switch/1?port=2"' in fk.TG.sent[0]["text"], fk.TG.sent[0]["text"])
check("HTML сообщения корректный для Telegram", valid_tg_html(fk.TG.sent[0]["text"]))
m.dispatch_notifications()
check("повторная рассылка не дублирует", len(fk.TG.sent) == 1)

# Падение порта: длительность при подъёме
fakesnmp.STATE["port2_up"] = False
m.poll_switch_and_log_events(1)
with sqlite3.connect(m.DB) as conn:  # «упал» 25 минут назад
    conn.execute("UPDATE port_events SET event_time=? WHERE id=(SELECT MAX(id) FROM port_events)",
                 ((datetime.now() - timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()
fakesnmp.STATE["port2_up"] = True
m.poll_switch_and_log_events(1)
fk.TG.sent.clear()
m.dispatch_notifications()
t = fk.TG.sent[0]["text"] if fk.TG.sent else ""
check("два события одной пачкой: переключался 2 раза", len(fk.TG.sent) == 1 and "переключался 2 раза" in t, t)

# ── Коммутатор недоступен / доступен
fk.TG.sent.clear()
fakesnmp.STATE["fail"] = True
m.poll_switch_and_log_events(1)
ev = last_events(1)[0]
check("SNMP не отвечает → событие switch_down с ping", ev[0] == "switch_down" and "ping отвечает" in ev[1], ev)
m.poll_switch_and_log_events(1)
check("повторный неудачный опрос — без нового события", last_events(1)[0][0] == "switch_down"
      and sum(1 for e in last_events(3) if e[0] == "switch_down") == 1)
ov = c.get("/").get_data(as_text=True)
m.dispatch_notifications()
check("сообщение «коммутатор недоступен»", len(fk.TG.sent) == 1 and "недоступен" in fk.TG.sent[0]["text"], fk.TG.sent)
fakesnmp.STATE["fail"] = False
m.poll_switch_and_log_events(1)
ev = last_events(1)[0]
check("опрос снова успешен → switch_up «Был недоступен …»", ev[0] == "switch_up" and "Был недоступен" in ev[1], ev)
with sqlite3.connect(m.DB) as conn:
    st = json.loads(conn.execute("SELECT alert_state FROM switches WHERE id=1").fetchone()[0])
check("признак недоступности снят", "unreachable" not in st, st)
m.dispatch_notifications()
check("сообщение «снова доступен»", len(fk.TG.sent) == 2 and "снова доступен" in fk.TG.sent[1]["text"], fk.TG.sent[-1:])

# Одиночный сбой: повторная проверка спасает от ложной тревоги
calls = {"n": 0}
orig = m.poll_switch_snmp
def flaky(*a, **k):
    calls["n"] += 1
    return {"error": "SNMP: timeout"} if calls["n"] == 1 else orig(*a, **k)
m.poll_switch_snmp = flaky
before = last_events(1)
m.poll_switch_and_log_events(1)
m.poll_switch_snmp = orig
check("единичный сбой опроса не даёт тревоги (повторная проверка)", calls["n"] == 2 and last_events(1) == before, calls)

# ── Ошибка сети: курсор не сдвигается, повтор позже, «Повторить сейчас»
fk.TG.sent.clear()
fk.TG.fail = True
fakesnmp.STATE["port2_up"] = False
m.poll_switch_and_log_events(1)
rep = m.dispatch_notifications()
st = notify.status(m.DB)["telegram"]
check("ошибка отправки: статус, следующая попытка, событие ждёт", "ошибка" in rep.get("telegram", "") and st["fails"] == 1
      and st["next_try"] and st["pending"] >= 1, (rep, st))
rep = m.dispatch_notifications()
check("до следующей попытки не ломимся", rep.get("telegram") == "ждёт повтора", rep)
fk.TG.fail = False
fakesnmp.STATE["port2_up"] = True
m.poll_switch_and_log_events(1)
code, r = post("/api/notify/retry")
check("«Повторить сейчас»: накопленное ушло одним сообщением", len(fk.TG.sent) == 1 and r["status"]["telegram"]["fails"] == 0
      and "переключался" in fk.TG.sent[0]["text"], (r.get("report"), fk.TG.sent))
log = c.get("/api/notify/log").get_json()
check("история: есть и ошибка, и успешная отправка", any(not x["ok"] for x in log) and log[0]["ok"], log[:3])

# ── Почта: SMTP без шифрования с логином
srv, port = fk.start_smtp("none", "mon@test.ru", "apppass")
email_cfg = dict(enabled=False, host="127.0.0.1", port=port, security="none", username="mon@test.ru", password="apppass",
                 recipients="a@test.ru, b@test.ru", events=["switch", "health"])
def ecfg(**over):
    x = cfg_with(**{f"email__{k}": v for k, v in {**email_cfg, **over}.items()})
    x["telegram"] = r_cfg["telegram"]; x["base_url"] = r_cfg["base_url"]; x["flap_limit"] = r_cfg["flap_limit"]
    return x
r_cfg = c.get("/api/notify").get_json()["config"]
fk.Mailbox.messages.clear()
code, r = post("/api/notify/test", {"channel": "email", "config": ecfg()})
msg = fk.Mailbox.messages[0]["msg"] if fk.Mailbox.messages else None
check("тестовое письмо доставлено двум получателям", r["ok"] and msg is not None and fk.Mailbox.messages[0]["to"] == ["a@test.ru", "b@test.ru"], r)
check("письмо: тема, отправитель, текст и HTML", msg and msg["Subject"] == "[SwitchMap] проверка уведомлений"
      and "mon@test.ru" in msg["From"] and msg.get_body(("plain",)) and msg.get_body(("html",))
      and "Тестовое сообщение" in msg.get_body(("plain",)).get_content())
code, r = post("/api/notify/test", {"channel": "email", "config": ecfg(password="wrong")})
check("неверный пароль — подсказка про пароль приложения", r["ok"] is False and "пароль приложения" in r["error"], r)
code, r = post("/api/notify/test", {"channel": "email", "config": ecfg(recipients="x@bad.test")})
check("получатель отклонён — понятная ошибка", r["ok"] is False and "x@bad.test" in r["error"], r)
code, r = post("/api/notify/test", {"channel": "email", "config": ecfg(port=1)})
check("сервер недоступен — понятная ошибка", r["ok"] is False and "127.0.0.1:1" in r["error"], r)

ctx = fk.make_cert()
ssl_srv, ssl_port = fk.start_smtp("ssl", "mon@test.ru", "apppass", ctx)
code, r = post("/api/notify/test", {"channel": "email", "config": ecfg(port=ssl_port, security="ssl", verify=False)})
check("SSL (самоподписанный сертификат, проверка выключена)", r["ok"], r)
code, r = post("/api/notify/test", {"channel": "email", "config": ecfg(port=ssl_port, security="ssl", verify=True)})
check("SSL с проверкой сертификата — подсказка снять галочку", r["ok"] is False and "сертификат" in r["error"].lower(), r)
tls_srv, tls_port = fk.start_smtp("starttls", "mon@test.ru", "apppass", ctx)
code, r = post("/api/notify/test", {"channel": "email", "config": ecfg(port=tls_port, security="starttls", verify=False)})
check("STARTTLS", r["ok"], r)
code, r = post("/api/notify/test", {"channel": "email", "config": ecfg(port=ssl_port, security="none")})
check("перепутан тип шифрования — понятная ошибка", r["ok"] is False and ("шифрован" in r["error"] or "порт" in r["error"]), r)
nologin_srv, nologin_port = fk.start_smtp("none")
code, r = post("/api/notify/test", {"channel": "email", "config": ecfg(port=nologin_port, username="", password="", sender="SwitchMap <noc@corp.local>")})
check("корпоративный сервер без логина", r["ok"] and "noc@corp.local" in fk.Mailbox.messages[-1]["msg"]["From"], r)

# ── Фильтры почты: только «коммутатор» и «CPU/температура»
code, r = post("/api/notify", ecfg(enabled=True))
check("почта включена", code == 200 and r["config"]["email"]["enabled"] and r["config"]["email"]["has_password"], r)
fk.Mailbox.messages.clear(); fk.TG.sent.clear()
fakesnmp.STATE["port2_up"] = False
m.poll_switch_and_log_events(1)
m.dispatch_notifications()
check("новый канал не получает старые события, порт — только в Telegram", not fk.Mailbox.messages and len(fk.TG.sent) == 1)
fakesnmp.STATE["fail"] = True
m.poll_switch_and_log_events(1)
m.dispatch_notifications()
mm = fk.Mailbox.messages
check("недоступность коммутатора — на почту", len(mm) == 1 and "недоступен" in mm[0]["msg"]["Subject"], [x["msg"]["Subject"] for x in mm])
check("в письме ссылка", mm and "http://sm.local:5000/switch/1" in mm[0]["msg"].get_body(("html",)).get_content())

# Без сообщений о восстановлении
cfg_now = c.get("/api/notify").get_json()["config"]
cfg_now["email"]["recovery"] = False
post("/api/notify", cfg_now)
fakesnmp.STATE["fail"] = False
m.poll_switch_and_log_events(1)
m.dispatch_notifications()
check("«о восстановлении» выключено — письма нет, в Telegram есть", len(fk.Mailbox.messages) == 1
      and "снова доступен" in fk.TG.sent[-1]["text"])

# ── Только важные порты
cfg_now = c.get("/api/notify").get_json()["config"]
cfg_now["telegram"]["important_only"] = True
post("/api/notify", cfg_now)
fk.TG.sent.clear()
fakesnmp.STATE["port2_up"] = True
m.poll_switch_and_log_events(1)
m.dispatch_notifications()
check("«только важные»: порт без описания пропущен", not fk.TG.sent)
with sqlite3.connect(m.DB) as conn:
    conn.execute("""UPDATE switches SET connections='{"2": {"name": "Бухгалтерия"}}' WHERE id=1"""); conn.commit()
fakesnmp.STATE["port2_up"] = False
m.poll_switch_and_log_events(1)
m.dispatch_notifications()
check("«только важные»: порт с подключением на схеме — отправлен", len(fk.TG.sent) == 1 and "порт 2" in fk.TG.sent[0]["text"])

# ── Тихие часы: ночью только аварии
cfg_now = c.get("/api/notify").get_json()["config"]
cfg_now["telegram"]["important_only"] = False
cfg_now["telegram"]["quiet"] = {"enabled": True, "from": "00:00", "to": "23:59"}
post("/api/notify", cfg_now)
fk.TG.sent.clear()
fakesnmp.STATE["port2_up"] = True
m.poll_switch_and_log_events(1)
m.dispatch_notifications()
check("тихие часы: событие порта не отправлено", not fk.TG.sent)
fakesnmp.STATE["fail"] = True
m.poll_switch_and_log_events(1)
m.dispatch_notifications()
check("тихие часы: недоступность коммутатора отправлена", len(fk.TG.sent) == 1 and "недоступен" in fk.TG.sent[0]["text"])
fakesnmp.STATE["fail"] = False
m.poll_switch_and_log_events(1)
cfg_now["telegram"]["quiet"]["enabled"] = False
post("/api/notify", cfg_now)
m.dispatch_notifications()

# ── Мигающий порт
cfg_now = c.get("/api/notify").get_json()["config"]; cfg_now["flap_limit"] = 6; post("/api/notify", cfg_now)
fk.TG.sent.clear()
now = datetime.now()
with sqlite3.connect(m.DB) as conn:
    for i in range(6):
        conn.execute("INSERT INTO port_events (switch_id, ifindex, port_name, port_number, event_type, event_time, is_read) "
                     "VALUES (1, '4', 'GigabitEthernet0/4', 4, ?, ?, 0)",
                     ("down" if i % 2 == 0 else "up", (now - timedelta(minutes=30 - i)).strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
m.dispatch_notifications()
t = fk.TG.sent[0]["text"] if fk.TG.sent else ""
check("мигающий порт: одно предупреждение вместо 6 сообщений", len(fk.TG.sent) == 1 and "нестабилен" in t and "6 переключений" in t, t)
with sqlite3.connect(m.DB) as conn:
    conn.execute("INSERT INTO port_events (switch_id, ifindex, port_name, port_number, event_type, event_time, is_read) "
                 "VALUES (1, '4', 'GigabitEthernet0/4', 4, 'down', ?, 0)", (now.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()
m.dispatch_notifications()
check("пока порт на паузе — молчим", len(fk.TG.sent) == 1)

# ── Миграция группы в супергруппу
cfg_now = c.get("/api/notify").get_json()["config"]; cfg_now["flap_limit"] = 0
cfg_now["telegram"]["chats"] = [{"id": "-500", "title": "Старая группа"}]
post("/api/notify", cfg_now)
fk.TG.sent.clear()
code, r = post("/api/notify/test", {"channel": "telegram", "config": cfg_now})
check("тест в мигрировавшую группу доходит", r["ok"] and fk.TG.sent and str(fk.TG.sent[-1]["chat_id"]) == "-1005000", r)
fakesnmp.STATE["port2_up"] = not fakesnmp.STATE["port2_up"]
m.poll_switch_and_log_events(1)
m.dispatch_notifications()
chats = c.get("/api/notify").get_json()["config"]["telegram"]["chats"]
check("после рассылки номер чата обновлён на новый", chats and chats[0]["id"] == "-1005000", chats)

# ── Частичная доставка: один чат из двух недоступен
cfg_now = c.get("/api/notify").get_json()["config"]
cfg_now["telegram"]["chats"] = [{"id": "111", "title": "Иван"}, {"id": "-404", "title": "Удалённая группа"}]
post("/api/notify", cfg_now)
fakesnmp.STATE["port2_up"] = not fakesnmp.STATE["port2_up"]
m.poll_switch_and_log_events(1)
rep = m.dispatch_notifications()
st = notify.status(m.DB)["telegram"]
check("частичная доставка: успех с предупреждением, без повтора", "доставлено в чатов: 1" in rep.get("telegram", "")
      and st["fails"] == 0 and "Удалённая группа" in st["warning"], (rep, st))

# ── Большая пачка: сообщение в лимите Telegram
fk.TG.sent.clear()
with sqlite3.connect(m.DB) as conn:
    for i in range(120):
        conn.execute("INSERT INTO port_events (switch_id, ifindex, port_name, port_number, event_type, event_time, details, is_read) "
                     "VALUES (1, NULL, 'CPU', NULL, ?, ?, ?, 0)", ("cpu_high" if i % 2 == 0 else "cpu_ok",
                     now.strftime("%Y-%m-%d %H:%M:%S"), "CPU: 95% <script>&" * 3))
    conn.commit()
m.dispatch_notifications()
t = fk.TG.sent[0]["text"] if fk.TG.sent else ""
check("120 событий: одно сообщение до 4096 символов, «и ещё…»", len(fk.TG.sent) == 1 and len(t) <= 4096 and ("и ещё" in t)
      and valid_tg_html(t) and "<script>" not in t, (len(fk.TG.sent), len(t)))

# ── Включение канала заново не рассылает накопленное
cfg_now = c.get("/api/notify").get_json()["config"]
cfg_now["telegram"]["enabled"] = False
post("/api/notify", cfg_now)
fakesnmp.STATE["port2_up"] = not fakesnmp.STATE["port2_up"]
m.poll_switch_and_log_events(1)
cfg_now["telegram"]["enabled"] = True
post("/api/notify", cfg_now)
fk.TG.sent.clear()
m.dispatch_notifications()
check("выключили и включили — старые события не приходят", not fk.TG.sent)

# ── Экспорт событий понимает новые типы
from xlsx import Sheet
tables = m.inventory_export_tables()
ev_rows = tables["events"][2]
check("экспорт: «коммутатор недоступен» подписан по-русски", any(r[4] == "коммутатор недоступен" for r in ev_rows))

# ── Настоящий api.telegram.org (если есть интернет): неверный токен → понятная ошибка
notify.TELEGRAM_API = "https://api.telegram.org"
if os.environ.get("SWITCHMAP_TEST_INTERNET") != "1":
    print("INFO проверка настоящего api.telegram.org пропущена (SWITCHMAP_TEST_INTERNET=1 — включить)")
else:
  try:
    notify.telegram_bot_info("123:fake")
    print("INFO настоящий Telegram: неожиданно принял токен")
  except notify.NotifyError as e:
    print("INFO настоящий Telegram:", e)

print("\nИТОГО:", "все проверки пройдены" if not fails else f"провалено {len(fails)}: {fails}")
