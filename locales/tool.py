"""Инструмент переводов.

    python locales/tool.py lint       русский текст, не обёрнутый в перевод (_(), t(), …) — файл:строка
    python locales/tool.py extract    собрать строки и обновить locales/<язык>.json (новые — пустые, лишние — удаляются)
    python locales/tool.py check      все ли переводы на месте, совпадают ли {подстановки}
    python locales/tool.py missing XX непереведённые строки языка XX (JSON) — для работы над переводом

Где ищутся строки:
    Python   _("…"), _n(n, "…", "…", "…"), _s(…), _ns(…), N_("…")
    шаблоны  {{ _("…") }}, {{ _n(…) }}, а в <script> — t("…"), tn(n, "…", …)
    static   t("…"), tn(n, "…", "…", "…")
    справка  help/ru/*.md — статьи переводятся целиком (help/<язык>/*.md), см. help/README.md
"""
import ast
import io
import json
import os
import re
import sys
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
I18N = os.path.join(ROOT, "locales")
PY_FILES = ["app.py", "audit.py", "config.py", "discovery.py", "maintenance.py", "netbox.py", "notify.py",
            "security.py", "xlsx.py", "helpdocs.py", "updates.py"]
CYR = re.compile(r"[А-Яа-яЁё]")
PLURAL_FORMS = {"en": 2, "es": 2, "de": 2, "fr": 2, "zh": 1}
PY_FUNCS = {"_": 1, "_s": 1, "N_": 1, "_n": 3, "_ns": 3}


def rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def template_files():
    base = os.path.join(ROOT, "templates")
    return sorted(os.path.join(base, n) for n in os.listdir(base) if n.endswith(".html"))


def static_files():
    base = os.path.join(ROOT, "static")
    return sorted(os.path.join(base, n) for n in os.listdir(base) if n.endswith(".js"))


# ─────────── Python ───────────

class PyStrings(ast.NodeVisitor):
    """Строки-аргументы _() и подобных; плюс все остальные строки с кириллицей (для lint)."""

    def __init__(self):
        self.messages = []      # (msgid, plural_forms or None, line)
        self.wrapped = set()    # id() узлов-строк внутри вызовов перевода
        self.skip = set()       # docstring, журнал, исключения разработчика

    def visit_Call(self, node):
        name = node.func.id if isinstance(node.func, ast.Name) else None
        attr = node.func.attr if isinstance(node.func, ast.Attribute) else None
        if name in PY_FUNCS:
            n = PY_FUNCS[name]
            args = node.args[1:1 + n] if n == 3 else node.args[:1]
            strs = [a.value for a in args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if len(strs) == len(args) and strs:
                self.messages.append((strs[0], strs if n == 3 else None, node.lineno))
            for a in args:
                self.wrapped.add(id(a))
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._docstring(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef

    def visit_Module(self, node):
        self._docstring(node)
        self.generic_visit(node)

    def _docstring(self, node):
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
            self.skip.add(id(node.body[0].value))


def scan_python(path):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    v = PyStrings()
    v.visit(tree)
    bare = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and CYR.search(node.value):
            if id(node) not in v.wrapped and id(node) not in v.skip:
                bare.append((node.lineno, node.value))
        if isinstance(node, ast.JoinedStr) and id(node) not in v.skip:
            text = "".join(p.value for p in node.values if isinstance(p, ast.Constant))
            if CYR.search(text):
                bare.append((node.lineno, "f-строка: " + text))
    # i18n: ignore — строка нарочно без перевода (например, раскладка клавиатуры)
    lines = src.splitlines()
    bare = [(ln, t) for ln, t in bare if "i18n: ignore" not in lines[ln - 1]]
    return v.messages, sorted(set(bare))


# ─────────── Шаблоны и скрипты ───────────

JINJA_CALL = re.compile(r"""\b(_|_n)\(\s*(?:[^,()'"]+(?:\([^()]*\))?\s*,\s*)?(['"])((?:\\.|(?!\2).)*)\2""")
JINJA_PLURAL = re.compile(r"""\b_n\(\s*[^,]+,\s*(['"])((?:\\.|(?!\1).)*)\1\s*,\s*(['"])((?:\\.|(?!\3).)*)\3\s*,\s*(['"])((?:\\.|(?!\5).)*)\5""")
JS_CALL = re.compile(r"""(?<![\w.$])(t|tn)\(\s*(?:[^,()'"`]+(?:\([^()]*\))?[^,()'"`]*,\s*)?(['"`])((?:\\.|(?!\2).)*)\2""", re.S)
JS_PLURAL = re.compile(r"""(?<![\w.$])tn\(\s*[^,()]+(?:\([^()]*\))?[^,()]*,\s*(['"`])((?:\\.|(?!\1).)*)\1\s*,\s*(['"`])((?:\\.|(?!\3).)*)\3\s*,\s*(['"`])((?:\\.|(?!\5).)*)\5""", re.S)


def unescape(s):
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), s)


def strip_comments(text, kind):
    """Комментарии заменяются пробелами той же длины (номера строк сохраняются)."""
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))
    if kind == "html":
        text = re.sub(r"\{#.*?#\}", blank, text, flags=re.S)
        text = re.sub(r"<!--.*?-->", blank, text, flags=re.S)
        # стили не переводятся
        text = re.sub(r"(<style\b[^>]*>)(.*?)(</style>)", lambda m: m.group(1) + blank(re.match(r"(?s).*", m.group(2))) + m.group(3), text, flags=re.S)
    # JS-комментарии (в шаблонах — внутри <script>, но и в разметке // встречается редко — только в URL)
    def js_blank(segment):
        segment = re.sub(r"/\*.*?\*/", blank, segment, flags=re.S)
        return re.sub(r"(?m)(^|[^:'\"`\\])//[^\n]*", lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), segment)
    if kind == "js":
        return js_blank(text)
    return re.sub(r"(<script\b[^>]*>)(.*?)(</script>)", lambda m: m.group(1) + js_blank(m.group(2)) + m.group(3), text, flags=re.S)


def remove_calls(text, kind):
    """Убирает из текста все вызовы перевода — то, что осталось с кириллицей, не переведено."""
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))
    pattern = JS_PLURAL.pattern + "|" + JS_CALL.pattern if kind == "js" else None
    text = JS_PLURAL.sub(blank, text)
    text = JS_CALL.sub(blank, text)
    if kind == "html":
        text = JINJA_PLURAL.sub(blank, text)
        text = JINJA_CALL.sub(blank, text)
    return text


def scan_markup(path):
    kind = "js" if path.endswith(".js") else "html"
    original = open(path, encoding="utf-8").read().splitlines()
    text = strip_comments("\n".join(original), kind)
    messages = []
    for regex, plural in ((JS_PLURAL, True), (JINJA_PLURAL, True)):
        if regex is JINJA_PLURAL and kind == "js":
            continue
        for m in regex.finditer(text):
            g = m.groups()
            forms = [unescape(g[1]), unescape(g[3]), unescape(g[5])]
            messages.append((forms[0], forms, text.count("\n", 0, m.start()) + 1))
    for regex in ((JS_CALL,) if kind == "js" else (JS_CALL, JINJA_CALL)):
        for m in regex.finditer(text):
            if m.group(1) in ("tn", "_n"):
                continue
            messages.append((unescape(m.group(3)), None, text.count("\n", 0, m.start()) + 1))
    rest = remove_calls(text, kind)
    bare = []
    for i, line in enumerate(rest.splitlines(), 1):
        if CYR.search(line) and "i18n: ignore" not in original[i - 1]:
            bare.append((i, line.strip()[:140]))
    return messages, bare


def collect():
    messages, bare = {}, []
    for path in [os.path.join(ROOT, f) for f in PY_FILES]:
        msgs, b = scan_python(path)
        for msgid, forms, line in msgs:
            messages.setdefault(msgid, {"forms": forms, "where": []})["where"].append(f"{rel(path)}:{line}")
        bare += [(rel(path), ln, t) for ln, t in b]
    for path in template_files() + static_files():
        msgs, b = scan_markup(path)
        for msgid, forms, line in msgs:
            entry = messages.setdefault(msgid, {"forms": forms, "where": []})
            entry["forms"] = entry["forms"] or forms
            entry["where"].append(f"{rel(path)}:{line}")
        bare += [(rel(path), ln, t) for ln, t in b]
    return messages, bare


def placeholders(text):
    return sorted(set(re.findall(r"\{(\w+)\}", text)))


def load(lang):
    path = os.path.join(I18N, f"{lang}.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(lang, data):
    with open(os.path.join(I18N, f"{lang}.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def languages():
    from i18n import LANGUAGES, SOURCE
    return [l for l in LANGUAGES if l != SOURCE]


def cmd_lint():
    _, bare = collect()
    for path, line, text in bare:
        print(f"{path}:{line}: {text}")
    print(f"\nНе обёрнуто в перевод: {len(bare)}", file=sys.stderr)
    return 1 if bare else 0


def cmd_extract():
    messages, _ = collect()
    for lang in languages():
        old = load(lang)
        new = {}
        for msgid, info in messages.items():
            value = old.get(msgid)
            if info["forms"]:
                n = PLURAL_FORMS.get(lang, 2)
                if not isinstance(value, list) or len(value) != n:
                    value = (value if isinstance(value, list) else [value or ""])[:n]
                    value += [""] * (n - len(value))
            elif isinstance(value, list):
                value = value[0]
            new[msgid] = value if value is not None else ""
        save(lang, new)
        empty = sum(1 for v in new.values() if v in ("", None) or (isinstance(v, list) and "" in v))
        print(f"{lang}: строк {len(new)}, без перевода {empty}, удалено {len(set(old) - set(new))}")
    return 0


def problems(lang, messages):
    data = load(lang)
    out = []
    for msgid, info in messages.items():
        value = data.get(msgid)
        values = value if isinstance(value, list) else [value]
        if value is None or any(v in ("", None) for v in values):
            out.append(f"{lang}: нет перевода: {msgid!r} ({info['where'][0]})")
            continue
        if info["forms"] and (not isinstance(value, list) or len(value) != PLURAL_FORMS.get(lang, 2)):
            out.append(f"{lang}: нужно форм множественного числа {PLURAL_FORMS.get(lang, 2)}: {msgid!r}")
        want = placeholders(" ".join(info["forms"] or [msgid]))
        for v in values:
            got = placeholders(v)
            # {n} в формах множественного числа можно опустить («one switch»), остальные — обязательны
            if [p for p in want if p != "n" or not info["forms"]] != [p for p in got if p != "n" or not info["forms"]] \
                    and not (set(got) <= set(want) and set(want) - set(got) <= {"n"}):
                out.append(f"{lang}: подстановки {want} ≠ {got}: {msgid!r} → {v!r}")
        if not info["forms"] and lang != "ru" and CYR.search(" ".join(values)):
            out.append(f"{lang}: в переводе кириллица: {msgid!r}")
    for extra in set(data) - set(messages):
        out.append(f"{lang}: лишняя строка (запустите extract): {extra!r}")
    return out


def cmd_check():
    messages, bare = collect()
    out = [f"не обёрнуто в перевод: {p}:{l}: {t}" for p, l, t in bare]
    for lang in languages():
        out += problems(lang, messages)
    for line in out:
        print(line)
    print(f"\nСтрок: {len(messages)}, замечаний: {len(out)}", file=sys.stderr)
    return 1 if out else 0


def cmd_missing(lang):
    messages, _ = collect()
    data = load(lang)
    todo = {}
    for msgid, info in messages.items():
        v = data.get(msgid)
        if v in ("", None) or (isinstance(v, list) and "" in v):
            todo[msgid] = info["forms"] or ""
    print(json.dumps(todo, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "lint":
        sys.exit(cmd_lint())
    if cmd == "extract":
        sys.exit(cmd_extract())
    if cmd == "missing":
        sys.exit(cmd_missing(sys.argv[2]))
    sys.exit(cmd_check())
