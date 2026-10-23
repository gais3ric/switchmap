"""Интеграция с NetBox (только чтение из NetBox).

  * подключение: адрес NetBox и API-токен (токен хранится зашифрованным);
  * импорт: устройства NetBox по фильтрам (сайт, роль, тег) → коммутаторы SwitchMap;
  * связь: у коммутатора хранится netbox_id — по нему синхронизируются имя и IP
    и строится ссылка «Открыть в NetBox».

Поддерживаются NetBox 3.x и 4.x: токены старого вида (заголовок «Token …») и новые
v2-токены nbt_… (заголовок «Bearer …»).
"""
import json
import socket
import sqlite3
import ssl
import urllib.error
import urllib.parse
import urllib.request

from i18n import _

PAGE = 250
MAX_DEVICES = 5000

DEFAULT_CONFIG = {
    "url": "", "token": "", "verify": True,
    "site": "", "role": "", "tag": "", "only_active": True,
    "update_existing": True, "auto_sync": False,
}


class NetBoxError(Exception):
    pass


# ─────────────────────────────────────────
# Настройки
# ─────────────────────────────────────────

def load_config(db):
    with sqlite3.connect(db, timeout=30) as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key='netbox_config'").fetchone()
    try:
        data = json.loads(row[0]) if row and row[0] else {}
    except (TypeError, ValueError):
        data = {}
    return {k: data.get(k, v) for k, v in DEFAULT_CONFIG.items()} | {"last_sync": data.get("last_sync", ""),
                                                                    "last_sync_result": data.get("last_sync_result", "")}


def save_config(db, cfg):
    with sqlite3.connect(db, timeout=30) as conn:
        conn.execute("INSERT INTO app_settings (key, value) VALUES ('netbox_config', ?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(cfg, ensure_ascii=False),))
        conn.commit()


def sanitize(incoming, current, box):
    """Настройки из формы. Пустой токен — оставить сохранённый. Возвращает (cfg, ошибка)."""
    cfg = dict(current)
    url = str(incoming.get("url", current["url"]) or "").strip().rstrip("/")
    if url.endswith("/api"):
        url = url[:-4]
    if url and not url.lower().startswith(("http://", "https://")):
        return None, _("Адрес NetBox должен начинаться с http:// или https://")
    cfg["url"] = url[:300]
    token = str(incoming.get("token") or "").strip()
    if incoming.get("token_clear"):
        cfg["token"] = ""
    elif token:
        if token.lower().startswith(("token ", "bearer ")):
            token = token.split(" ", 1)[1].strip()
        cfg["token"] = box.encrypt(token)
    for key in ("verify", "only_active", "update_existing", "auto_sync"):
        if key in incoming:
            cfg[key] = bool(incoming[key])
    for key in ("site", "role", "tag"):
        if key in incoming:
            cfg[key] = str(incoming[key] or "").strip()[:100]
    return cfg, None


def public_config(cfg):
    out = dict(cfg)
    out["has_token"] = bool(out.pop("token", ""))
    return out


def device_url(cfg, netbox_id):
    return f"{cfg['url']}/dcim/devices/{netbox_id}/" if cfg.get("url") and netbox_id else ""


# ─────────────────────────────────────────
# HTTP
# ─────────────────────────────────────────

def _auth_header(token):
    return f"Bearer {token}" if token.startswith("nbt_") else f"Token {token}"


def api_get(cfg, box, path, params=None, timeout=20):
    if not cfg.get("url"):
        raise NetBoxError(_("Не указан адрес NetBox"))
    token = box.decrypt(cfg["token"]) if cfg.get("token") else ""
    if not token:
        raise NetBoxError(_("Не указан API-токен NetBox"))
    query = urllib.parse.urlencode(params or {}, doseq=True)
    url = f"{cfg['url']}/api/{path.strip('/')}/" + (f"?{query}" if query else "")
    req = urllib.request.Request(url, headers={"Authorization": _auth_header(token), "Accept": "application/json"})
    context = ssl.create_default_context()
    if not cfg.get("verify", True):
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            body = resp.read().decode("utf-8")
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8") or "{}").get("detail", "")
        except (ValueError, AttributeError):
            pass
        if e.code in (401, 403):
            raise NetBoxError(_("NetBox не принял токен") + (f" ({detail})" if detail else "") +
                              _(". Проверьте токен и что у него есть право на чтение"))
        if e.code == 404:
            raise NetBoxError(_("По адресу {url} не найден API NetBox — проверьте адрес", url=cfg['url']))
        raise NetBoxError(_("NetBox ответил ошибкой HTTP {code}", code=e.code) + (f": {detail}" if detail else ""))
    except ssl.SSLCertVerificationError as e:
        raise NetBoxError(_("Сертификат NetBox не прошёл проверку ({verify_message}). Если у NetBox самоподписанный сертификат, снимите галочку «Проверять сертификат»", verify_message=e.verify_message))
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, ssl.SSLCertVerificationError):
            raise NetBoxError(_("Сертификат NetBox не прошёл проверку ({verify_message}). Если у NetBox самоподписанный сертификат, снимите галочку «Проверять сертификат»", verify_message=reason.verify_message))
        raise NetBoxError(_("Нет связи с NetBox ({url}): {reason}", url=cfg['url'], reason=reason))
    if "json" not in ctype:
        raise NetBoxError(_("По адресу {url} ответил не NetBox (получена веб-страница вместо API)", url=cfg['url']))
    try:
        return json.loads(body)
    except ValueError:
        raise NetBoxError(_("NetBox вернул некорректный ответ"))


def api_list(cfg, box, path, params=None, limit=MAX_DEVICES):
    """Все объекты списка с учётом постраничной выдачи."""
    items, offset = [], 0
    while True:
        page = api_get(cfg, box, path, {**(params or {}), "limit": PAGE, "offset": offset})
        results = page.get("results") or []
        items.extend(results)
        offset += len(results)
        if not results or offset >= (page.get("count") or 0) or len(items) >= limit:
            return items[:limit]


# ─────────────────────────────────────────
# Чтение из NetBox
# ─────────────────────────────────────────

def test_connection(cfg, box):
    status = api_get(cfg, box, "status")
    devices = api_get(cfg, box, "dcim/devices", {"limit": 1})
    return {"version": status.get("netbox-version") or "", "devices": devices.get("count", 0)}


def options(cfg, box):
    def simple(path):
        return [{"slug": x.get("slug"), "name": x.get("name") or x.get("slug")} for x in api_list(cfg, box, path, {"brief": 1}, 1000)]
    return {"sites": simple("dcim/sites"), "roles": simple("dcim/device-roles"), "tags": simple("extras/tags")}


def _ip(obj):
    addr = (obj or {}).get("address") if isinstance(obj, dict) else None
    return addr.split("/")[0] if addr else ""


def normalize(d):
    role = d.get("role") or d.get("device_role") or {}
    dtype = d.get("device_type") or {}
    status = d.get("status") or {}
    return {
        "id": d.get("id"),
        "name": d.get("name") or d.get("display") or f"device-{d.get('id')}",
        "ip": _ip(d.get("primary_ip4")) or _ip(d.get("primary_ip")),
        "site": (d.get("site") or {}).get("name", ""),
        "role": role.get("name", ""),
        "manufacturer": (dtype.get("manufacturer") or {}).get("name", ""),
        "model": dtype.get("model", ""),
        "status": status.get("label") or status.get("value") or "",
        "interfaces": d.get("interface_count"),
    }


def fetch_devices(cfg, box):
    params = {}
    for key in ("site", "role", "tag"):
        if cfg.get(key):
            params[key] = cfg[key]
    if cfg.get("only_active"):
        params["status"] = "active"
    return [normalize(d) for d in api_list(cfg, box, "dcim/devices", params)]


def fetch_by_ids(cfg, box, ids):
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), 100):
        for d in api_list(cfg, box, "dcim/devices", {"id": ids[i:i + 100]}):
            out[d["id"]] = normalize(d)
    return out


def physical_ports(cfg, box, device_id):
    """Число физических интерфейсов (без VLAN, LAG и виртуальных)."""
    try:
        return api_get(cfg, box, "dcim/interfaces", {"device_id": device_id, "kind": "physical", "limit": 1}).get("count")
    except NetBoxError:
        return None


# ─────────────────────────────────────────
# Сопоставление с коммутаторами SwitchMap
# ─────────────────────────────────────────

def plan(devices, switches):
    """Для каждого устройства NetBox — что с ним будет при импорте.
    switches: [{id, name, ip_address, netbox_id}]. Связь ищется по netbox_id, затем по IP, затем по имени."""
    by_nb = {s["netbox_id"]: s for s in switches if s.get("netbox_id")}
    by_ip = {s["ip_address"]: s for s in switches if s.get("ip_address")}
    by_name = {(s["name"] or "").strip().lower(): s for s in switches if s.get("name")}
    out = []
    for d in devices:
        sw, how = by_nb.get(d["id"]), "netbox"
        if not sw and d["ip"]:
            sw, how = by_ip.get(d["ip"]), "ip"
        if not sw:
            sw, how = by_name.get(d["name"].strip().lower()), "name"
        if sw and sw.get("netbox_id") and sw["netbox_id"] != d["id"]:
            sw, how = None, None  # коммутатор уже связан с другим устройством NetBox
        item = dict(d)
        if sw:
            changes = []
            if (sw["name"] or "") != d["name"]:
                changes.append({"field": _("Название"), "before": sw["name"] or "—", "after": d["name"]})
            if d["ip"] and (sw["ip_address"] or "") != d["ip"]:
                changes.append({"field": _("IP-адрес"), "before": sw["ip_address"] or "—", "after": d["ip"]})
            item["match"] = {"switch_id": sw["id"], "switch_name": sw["name"], "by": how, "changes": changes}
        else:
            item["match"] = None
        out.append(item)
    return out
