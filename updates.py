"""Проверка новых версий: раз в день — последний релиз на GitHub.

Сервер сам ничего не скачивает и не устанавливает: администратор видит в интерфейсе «Доступна версия X.Y.Z»
и ссылку на страницу релиза. Проверку можно выключить в настройках, а для закрытых сетей — совсем
(SWITCHMAP_UPDATE_CHECK=0 в switchmap.conf). Адрес — SWITCHMAP_UPDATE_URL (например, своё зеркало);
ответ — в формате GitHub API: {"tag_name": "v1.2.3", "html_url": "https://…"}.
Прокси — из переменных окружения HTTPS_PROXY / NO_PROXY.
"""
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime

from i18n import _s

DEFAULT_URL = "https://api.github.com/repos/gais3ric/switchmap/releases/latest"
RELEASES_PAGE = "https://github.com/gais3ric/switchmap/releases"
KEYS = ("update_latest", "update_url", "update_checked_at", "update_error", "update_dismissed")


def allowed():
    """Проверка не запрещена администратором сервера (switchmap.conf)."""
    return os.environ.get("SWITCHMAP_UPDATE_CHECK", "1").strip().lower() not in ("0", "no", "false", "off")


def source_url():
    return os.environ.get("SWITCHMAP_UPDATE_URL", "").strip() or DEFAULT_URL


def parse_version(text):
    """'v1.2.3' → (1, 2, 3); всё, что не похоже на X.Y.Z (в том числе «dev»), — None."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (text or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)


def _read(db):
    with sqlite3.connect(db, timeout=30) as conn:
        rows = conn.execute(f"SELECT key, value FROM app_settings WHERE key IN ({','.join('?' * len(KEYS))})",
                            KEYS).fetchall()
    return dict(rows)


def _write(db, values):
    with sqlite3.connect(db, timeout=30) as conn:
        conn.executemany("INSERT INTO app_settings (key, value) VALUES (?, ?) "
                         "ON CONFLICT(key) DO UPDATE SET value=excluded.value", list(values.items()))
        conn.commit()


def fetch_latest(url=None, current="dev", timeout=10):
    """(версия, ссылка на страницу релиза) или исключение с понятным текстом."""
    req = urllib.request.Request(url or source_url(), headers={
        "Accept": "application/vnd.github+json", "User-Agent": f"SwitchMap/{current}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read(1_000_000).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(_s("релизов пока нет или репозиторий закрыт (HTTP 404)"))
        if e.code in (403, 429):
            raise RuntimeError(_s("GitHub временно ограничил запросы (HTTP {code}), повторим позже", code=e.code))
        raise RuntimeError(f"HTTP {e.code}")
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise RuntimeError(_s("нет связи с сервером обновлений: {reason}", reason=reason))
    except ValueError:
        raise RuntimeError(_s("сервер обновлений вернул не JSON"))
    tag = data.get("tag_name") if isinstance(data, dict) else None
    if not parse_version(tag):
        raise RuntimeError(_s("в ответе нет номера версии"))
    link = data.get("html_url") or ""
    if not link.startswith("https://"):
        link = RELEASES_PAGE
    return tag.lstrip("v"), link


def check(db, current, url=None):
    """Проверить сейчас и запомнить результат. Ошибка сети не стирает последнюю известную версию."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        latest, link = fetch_latest(url, current)
        _write(db, {"update_latest": latest, "update_url": link, "update_checked_at": now, "update_error": ""})
    except RuntimeError as e:
        _write(db, {"update_checked_at": now, "update_error": str(e)})
    return status(db, current)


def dismiss(db, version):
    _write(db, {"update_dismissed": version or ""})


def status(db, current):
    s = _read(db)
    latest = s.get("update_latest", "")
    newer = is_newer(latest, current)
    return {
        "current": current, "latest": latest, "url": s.get("update_url") or RELEASES_PAGE,
        "checked_at": s.get("update_checked_at", ""), "error": s.get("update_error", ""),
        "newer": newer, "show": newer and s.get("update_dismissed") != latest, "allowed": allowed(),
    }
