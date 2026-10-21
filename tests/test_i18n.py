"""Языки и справка: полнота переводов, выбор языка, страницы на каждом языке без русского текста,
статьи справки на всех языках с одинаковыми разделами и рабочими ссылками.
argv: <рабочая папка с тестовой базой>"""
import os, re, sqlite3, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
sys.stdout.reconfigure(encoding='utf-8')
work = sys.argv[1]
os.chdir(work); sys.path[:0] = [ROOT]

fails = []
def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""))
    if not cond:
        fails.append(name)

CYR = re.compile(r"[А-Яа-яЁё]")

# ── Каталоги: всё обёрнуто, всё переведено, подстановки совпадают
r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "locales", "tool.py"), "check"], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
check("каталоги переводов полные (locales/tool.py check)", r.returncode == 0, (r.stdout + r.stderr)[-1500:])

import i18n
import helpdocs
import app as m
import security

LANGS = list(i18n.LANGUAGES)
check("шесть языков", LANGS == ["ru", "en", "zh", "es", "de", "fr"] or sorted(LANGS) == sorted(["ru", "en", "zh", "es", "de", "fr"]), LANGS)

# ── Выбор языка по заголовку браузера
for header, want in [("zh-CN,zh;q=0.9,en;q=0.8", "zh"), ("de-AT", "de"), ("fr-CA,fr;q=0.9", "fr"), ("es-419", "es"),
                     ("pt-BR,pt;q=0.9", None), ("pt-BR,de;q=0.5", "de"), ("ru-RU,ru;q=0.9,en-US;q=0.8", "ru"),
                     ("en-US,ru;q=0.9", "en"), ("", None)]:
    check(f"Accept-Language «{header}» → {want}", i18n.negotiate(header) == want, i18n.negotiate(header))

# ── Множественное число
check("ru: 1 порт / 3 порта / 11 портов / 22 порта",
      [i18n.ngettext("ru", n, "{n} порт", "{n} порта", "{n} портов") for n in (1, 3, 11, 22)]
      == ["1 порт", "3 порта", "11 портов", "22 порта"])
en = [i18n.ngettext("en", n, "{n} порт", "{n} порта", "{n} портов") for n in (1, 3)]
check("en: формы множественного числа из каталога", not any(CYR.search(s) for s in en) and en[0] != en[1], en)

# ── Подготовка: администратор и латинские имена коммутаторов (данные пользователя не переводятся)
m.prepare_database()
with sqlite3.connect(m.DB) as conn:
    conn.execute("DELETE FROM users"); conn.execute("DELETE FROM audit_log")
    conn.execute("UPDATE switches SET name = 'Switch ' || id")
    conn.commit()
security.create_user(m.DB, "root", "Rootpass123", "admin")

def csrf_of(c):
    with c.session_transaction() as s:
        return s.get("csrf")

def client(accept=None):
    c = m.app.test_client()
    if accept is not None:
        c.environ_base["HTTP_ACCEPT_LANGUAGE"] = accept
    c.get("/login")
    return c

def login(c):
    r = c.post("/login", data={"username": "root", "password": "Rootpass123", "csrf_token": csrf_of(c)})
    assert r.status_code == 302, r.status_code
    c.environ_base["HTTP_X_CSRF_TOKEN"] = csrf_of(c)
    return c

def html_lang(text):
    mt = re.search(r'<html[^>]*\blang="([\w-]+)"', text)
    return mt.group(1).split("-")[0] if mt else None

def leaked(text):
    """Русский текст на странице, кроме скриптов, стилей и названия «Русский» в списке языков."""
    text = re.sub(r"<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->", " ", text, flags=re.S)
    text = text.replace(i18n.LANGUAGES["ru"], "")
    return sorted({mt.group(0).strip()[:80] for mt in re.finditer(r"[^<>\"]*[А-Яа-яЁё][^<>\"]*", text)})

# ── Язык до входа
c = client("de-DE,de;q=0.9")
check("страница входа на языке браузера (de)", html_lang(c.get("/login").get_data(as_text=True)) == "de")
c = client("pt-BR")
check("незнакомый язык браузера → английский", html_lang(c.get("/login").get_data(as_text=True)) == "en")
c = m.app.test_client()
check("браузер не сообщил язык → язык сервера (ru)", html_lang(c.get("/login").get_data(as_text=True)) == "ru")
c = client("de-DE")
r = c.post("/api/language", json={"language": "zh"}, headers={"X-CSRF-Token": csrf_of(c)})
check("выбор языка до входа сохраняется в cookie", r.status_code == 200 and html_lang(c.get("/login").get_data(as_text=True)) == "zh")
r = c.post("/api/language", json={"language": "xx"}, headers={"X-CSRF-Token": csrf_of(c)})
check("неизвестный язык отклонён, ошибка на языке пользователя",
      r.status_code == 400 and not CYR.search(r.get_json().get("error", "")), r.get_json())

# ── Язык в профиле важнее браузера
c = login(client("en-US"))
c.post("/api/language", json={"language": "fr"})
check("язык из профиля важнее языка браузера", html_lang(c.get("/").get_data(as_text=True)) == "fr")
c2 = login(client("en-US"))
check("язык профиля действует и в новом сеансе", html_lang(c2.get("/").get_data(as_text=True)) == "fr")
c.post("/api/language", json={"language": ""})
check("«как в системе» — снова язык браузера", html_lang(c.get("/").get_data(as_text=True)) == "en")

# ── Каждая страница на каждом языке
slugs = [a["slug"] for a in helpdocs.articles("ru")]
PAGES = ["/", "/add", "/switch/1", "/topology", "/discover", "/notifications", "/maintenance", "/audit",
         "/users", "/help"] + [f"/help/{s}" for s in slugs]
for lang in LANGS:
    c = login(client(lang))
    bad, leaks = [], {}
    for page in PAGES:
        resp = c.get(page)
        text = resp.get_data(as_text=True)
        if resp.status_code != 200 or html_lang(text) != lang:

            bad.append(f"{page}: {resp.status_code} lang={html_lang(text)}")
        if lang != "ru":
            found = leaked(text)
            if found:
                leaks[page] = found[:3]
    check(f"{lang}: {len(PAGES)} страниц открываются на этом языке", not bad, bad[:5])
    if lang != "ru":
        check(f"{lang}: на страницах нет русского текста", not leaks, leaks)
    # Строки для скриптов: все переведены
    keys = i18n.js_keys()
    cat = i18n.js_catalog(lang, keys)
    missing = [k for k in keys if lang != "ru" and not cat.get(k)]
    check(f"{lang}: все строки для скриптов переведены ({len(keys)})", not missing, missing[:5])

    # Выгрузки тоже собираются на языке пользователя
    for url in ("/export/switch/1.xlsx", "/export/switch/1/ports.csv", "/export/inventory.xlsx"):
        check(f"{lang}: выгрузка {url}", c.get(url).status_code == 200)

# «_» — функция перевода: имя переменной «_» в коде её перекрывает (так сломалась выгрузка Excel)
shadow = []
for name in os.listdir(ROOT):
    if name.endswith(".py"):
        for i, line in enumerate(open(os.path.join(ROOT, name), encoding="utf-8"), 1):
            if re.search(r"\bfor\b[^:]*(?<![\w.])_(?!\w)[^:]*\bin\b|^\s*(?:[\w, ]+,\s*)?_\s*(?:,[\w, ]+)?=[^=]", line):
                shadow.append(f"{name}:{i}: {line.strip()[:80]}")
check("в коде нет переменных с именем «_»", not shadow, shadow)

c = login(client("en"))
r = c.get("/help/nope")
check("несуществующая статья → 404", r.status_code == 404)

# ── Справка: на каждом языке свои статьи, разделы совпадают с русскими, ссылки ведут на существующие разделы
def anchors_of(body):
    html, _ = helpdocs.render(body)
    return html, set(re.findall(r'id="([\w-]+)"', html))

ru = {a["slug"]: anchors_of(a["body"])[1] for a in helpdocs.articles("ru")}
check("справка: статей на русском не меньше 16", len(ru) >= 16, len(ru))
for lang in LANGS:
    arts = {a["slug"]: a for a in helpdocs.articles(lang)}
    own = sorted(s for s, a in arts.items() if a["lang"] == lang)
    check(f"справка {lang}: все статьи переведены", sorted(ru) == own, sorted(set(ru) - set(own)))
    anchors, html = {}, {}
    for slug, a in arts.items():
        html[slug], anchors[slug] = anchors_of(a["body"])
    diff = {s: sorted(ru[s] ^ anchors[s]) for s in ru if s in anchors and ru[s] != anchors[s]}
    check(f"справка {lang}: разделы совпадают с русскими", not diff, diff)
    broken = []
    for slug, h in html.items():
        for target, anc in re.findall(r'href="/help/([\w-]+)(?:#([\w-]+))?"', h):
            if target not in arts or (anc and anc not in anchors[target]):
                broken.append(f"{slug} → {target}#{anc}")
    check(f"справка {lang}: ссылки между статьями работают", not broken, broken[:5])
    if lang != "ru":
        cyr = [s for s, a in arts.items() if CYR.search(a["title"] + a["summary"] + a["body"])]
        check(f"справка {lang}: нет русского текста", not cyr, cyr)
    titles = [a for a in arts.values() if not a["title"] or a["title"] == a["slug"] or not a["summary"]]
    check(f"справка {lang}: у статей есть заголовок и описание", not titles, [a["slug"] for a in titles])

# Подсказки и ссылки в шаблонах ведут на существующие статьи и разделы
broken = []
for name in os.listdir(os.path.join(ROOT, "templates")):
    text = open(os.path.join(ROOT, "templates", name), encoding="utf-8").read()
    for s, anc in re.findall(r"tip\([^)]*?\),\s*'([\w-]+)'(?:,\s*'([\w-]+)')?\)", text):
        if s not in ru or (anc and anc not in ru[s]):
            broken.append(f"{name}: tip → {s}#{anc}")
    for s, anc in re.findall(r'href="/help/([\w-]+)(?:#([\w-]+))?"', text):
        if s not in ru or (anc and anc not in ru[s]):
            broken.append(f"{name}: {s}#{anc}")
    for s in re.findall(r"help_slug = '([\w-]+)'", text):
        if s not in ru:
            broken.append(f"{name}: help_slug {s}")
check("подсказки и ссылки на справку в шаблонах ведут на существующие разделы", not broken, broken)

# Поиск по справке на каждом языке
for lang, word in [(l, "snmp") for l in LANGS]:
    idx = helpdocs.search_index(lang)
    check(f"индекс поиска справки {lang}", len(idx) >= 16 and any(word in str(e) for e in idx), len(idx))

print(f"\nИТОГО: {'провалено ' + str(len(fails)) if fails else 'все проверки пройдены'}")
sys.exit(1 if fails else 0)
