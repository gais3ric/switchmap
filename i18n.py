"""Переводы интерфейса.

Ключ перевода — исходный русский текст (как в gettext): _("Коммутаторы"). Переводы — в locales/<язык>.json:
    {"Коммутаторы": "Switches", "{n} порт": ["{n} port", "{n} ports"]}
Нет перевода — показывается русский текст (страница не ломается); tests/test_i18n.py следит, чтобы
переводы были полными.

Язык пользователя: выбранный в меню → cookie (до входа) → язык браузера (= язык системы) → английский.
Язык сервера (журнал, уведомления, тексты, которые сохраняются в базу) — в настройках, по умолчанию
язык системы сервера.
"""
import functools
import json
import locale
import os
import re
import string

import config

LANGUAGES = {  # код → название на самом языке (так его найдёт тот, кто не знает остальных)
    "ru": "Русский",
    "en": "English",
    "zh": "简体中文",
    "es": "Español",
    "de": "Deutsch",
    "fr": "Français",
}
SOURCE = "ru"
FALLBACK = "en"   # язык браузера не поддерживается
HTML_LANG = {"zh": "zh-CN"}

_catalogs = {}
_formatter = string.Formatter()


def catalog_dir():
    return os.path.join(config.resource_dir(), "locales")


def catalog(lang):
    if lang not in _catalogs:
        data = {}
        path = os.path.join(catalog_dir(), f"{lang}.json")
        if lang != SOURCE and os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                data = {k: v for k, v in json.load(f).items() if v not in ("", None, [])}
        _catalogs[lang] = data
    return _catalogs[lang]


def reload():
    _catalogs.clear()


def normalize(code):
    """'zh-Hans-CN', 'zh_CN', 'EN-us' → 'zh', 'en'; неизвестный → None."""
    if not code:
        return None
    base = re.split(r"[-_.@]", str(code).strip().lower())[0]
    return base if base in LANGUAGES else None


def negotiate(accept_language):
    """Лучший поддерживаемый язык из заголовка Accept-Language (язык системы/браузера)."""
    best, best_q = None, -1.0
    for i, part in enumerate((accept_language or "").split(",")):
        bits = part.strip().split(";")
        lang = normalize(bits[0])
        q = 1.0
        for b in bits[1:]:
            if b.strip().startswith("q="):
                try:
                    q = float(b.strip()[2:])
                except ValueError:
                    q = 0.0
        q -= i * 1e-6  # при равном q — порядок в заголовке
        if lang and q > best_q:
            best, best_q = lang, q
    return best


@functools.lru_cache(maxsize=1)
def system_language():
    """Язык системы, на которой работает сервер (для журнала и уведомлений по умолчанию)."""
    env = normalize(os.environ.get("SWITCHMAP_LANG"))
    if env:
        return env
    candidates = []
    try:
        candidates.append(locale.getlocale()[0])
    except ValueError:
        pass
    candidates += [os.environ.get(k) for k in ("LC_ALL", "LC_MESSAGES", "LANG")]
    if config.WINDOWS:
        try:
            import ctypes
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            candidates.insert(0, locale.windows_locale.get(lcid))
        except Exception:
            pass
    for c in candidates:
        lang = normalize(c)
        if lang:
            return lang
    return FALLBACK


# ─────────── Множественное число ───────────

def plural_index(lang, n):
    """Номер формы для числа n. ru: 1 порт / 2 порта / 5 портов; en, es, de: 1 / много;
    fr: 0 и 1 — единственное; zh: одна форма."""
    try:
        n = abs(int(n))
    except (TypeError, ValueError):
        n = 0
    if lang == "ru":
        if n % 10 == 1 and n % 100 != 11:
            return 0
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return 1
        return 2
    if lang == "zh":
        return 0
    if lang == "fr":
        return 0 if n <= 1 else 1
    return 0 if n == 1 else 1


def _format(text, kwargs):
    if not kwargs:
        return text
    try:
        return _formatter.vformat(text, (), _SafeDict(kwargs))
    except (ValueError, IndexError):
        return text


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def gettext(lang, msg, **kwargs):
    value = catalog(lang).get(msg) if lang != SOURCE else None
    if isinstance(value, list):
        value = value[0]
    return _format(value or msg, kwargs)


def ngettext(lang, n, one, few, many, **kwargs):
    """_n(5, "{n} порт", "{n} порта", "{n} портов") → «5 портов» / «5 ports». Ключ — первая форма."""
    kwargs.setdefault("n", n)
    if lang == SOURCE:
        forms = [one, few, many]
    else:
        value = catalog(lang).get(one)
        forms = value if isinstance(value, list) else [value] if value else [one, few, many]
        if value is None:
            lang = SOURCE
    i = min(plural_index(lang, n), len(forms) - 1)
    return _format(forms[i], kwargs)


# ─────────── Текущий язык ───────────

_server_lang = None  # язык сервера (настройка); None — язык системы


def set_server_language(lang):
    global _server_lang
    _server_lang = normalize(lang)


def server_language():
    return _server_lang or system_language()


def current_language():
    """Язык запроса (g.lang ставит app.py), вне запроса — язык сервера."""
    try:
        from flask import g, has_request_context
        if has_request_context() and getattr(g, "lang", None):
            return g.lang
    except ImportError:
        pass
    return server_language()


def _(msg, **kwargs):
    """Перевод на язык текущего пользователя (вне запроса — на язык сервера)."""
    return gettext(current_language(), msg, **kwargs)


def _n(n, one, few, many, **kwargs):
    return ngettext(current_language(), n, one, few, many, **kwargs)


def _s(msg, **kwargs):
    """Перевод на язык сервера — для текстов, которые сохраняются (журнал, события, уведомления)."""
    return gettext(server_language(), msg, **kwargs)


def _ns(n, one, few, many, **kwargs):
    return ngettext(server_language(), n, one, few, many, **kwargs)


def N_(msg):
    """Пометка «это переводимая строка» без перевода: для констант, переводятся при показе через _()."""
    return msg


def js_catalog(lang, keys):
    """Переводы строк, которые нужны скриптам на странице."""
    if lang == SOURCE:
        return {}
    cat = catalog(lang)
    return {k: cat[k] for k in keys if k in cat}


# ─────────── Строки из скриптов ───────────

# t("текст", {...}) и tn(число, "форма 1", "форма 2", "форма 5", {...}) — ключ — первая строка
JS_CALL = re.compile(r"""(?<![\w.$])(?:t\(|tn\([^,()]+(?:\([^()]*\))?[^,()]*,)\s*(['"`])((?:\\.|(?!\1).)*)\1""", re.S)


def js_keys():
    """Все строки t("…") / tn(n, "…", …) из static/*.js и шаблонов — их переводы передаются в браузер."""
    keys = set()
    root = config.resource_dir()
    for folder, ext in (("static", ".js"), ("templates", ".html")):
        base = os.path.join(root, folder)
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            if name.endswith(ext):
                with open(os.path.join(base, name), encoding="utf-8") as f:
                    for m in JS_CALL.finditer(f.read()):
                        keys.add(_unescape_js(m.group(2)))
    return sorted(keys)


def _unescape_js(s):
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), s)
