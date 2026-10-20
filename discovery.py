"""Автообнаружение коммутаторов: перебор адресов по SNMP в фоне.

Поиск идёт в отдельном потоке (несколько адресов параллельно); браузер раз в секунду
спрашивает прогресс. Учётные данные SNMP (в том числе пароли v3) остаются на сервере —
в браузер уходит только подпись «v2c · public» / «v3 · user».
"""
import concurrent.futures
import ipaddress
import logging
import re
import threading
import uuid
from datetime import datetime

from i18n import _

MAX_HOSTS = 4096         # адресов за один поиск (≈ сеть /20)
WORKERS = 32             # одновременных SNMP-запросов
KEEP_JOBS = 5

# Номер производителя (enterprise) из sysObjectID → название
VENDORS = {
    9: "Cisco", 11: "HPE", 43: "3Com", 45: "Avaya", 171: "D-Link", 207: "Allied Telesis", 311: "Microsoft",
    674: "Dell", 890: "Zyxel", 1916: "Extreme", 1991: "Brocade", 2011: "Huawei", 2272: "Nortel", 2636: "Juniper",
    3902: "ZTE", 3955: "Linksys", 4413: "Broadcom", 4526: "Netgear", 5624: "Enterasys", 6027: "Dell (Force10)",
    6486: "Alcatel-Lucent", 6527: "Nokia", 8072: "Linux (net-snmp)", 10002: "Ubiquiti", 11863: "TP-Link",
    12356: "Fortinet", 14823: "Aruba", 14988: "MikroTik", 25506: "H3C", 27514: "QTECH", 30065: "Arista",
    35265: "Eltex", 40418: "SNR", 41112: "Ubiquiti", 47196: "HPE Aruba", 25053: "Ruckus", 22610: "A10",
}


def vendor_from_oid(oid):
    m = re.match(r"^\.?1\.3\.6\.1\.4\.1\.(\d+)", str(oid or ""))
    if not m:
        return ""
    num = int(m.group(1))
    return VENDORS.get(num, f"enterprise {num}")


def short_model(sys_descr, vendor=""):
    """Первая строка sysDescr без лишнего — для подписи модели."""
    text = " ".join(str(sys_descr or "").split())
    text = re.split(r"(?i)\b(copyright|compiled|technical support)\b", text)[0].strip(" ,;")
    if len(text) > 90:
        text = text[:87].rstrip() + "…"
    return text


def parse_targets(text, limit=MAX_HOSTS):
    """Адреса из строки: 10.0.0.0/24, 10.0.0.1-10.0.0.50, 10.0.0.1-50, отдельные IP.
    Разделители — запятая, пробел, перевод строки. Возвращает (список IP, ошибка)."""
    ips, seen = [], set()

    def add(ip):
        s = str(ip)
        if s not in seen:
            seen.add(s)
            ips.append(s)

    for token in re.split(r"[\s,;]+", text or ""):
        if not token:
            continue
        try:
            if "/" in token:
                net = ipaddress.ip_network(token, strict=False)
                if net.version != 4:
                    return None, _("Поддерживаются только IPv4-адреса: {token}", token=token)
                if net.num_addresses > limit * 4:
                    return None, _("Сеть {token} слишком большая — разбейте её на части до /20", token=token)
                hosts = list(net.hosts()) if net.num_addresses > 2 else list(net)
                for ip in hosts:
                    add(ip)
            elif "-" in token:
                start_s, end_s = token.split("-", 1)
                start = ipaddress.IPv4Address(start_s)
                if "." not in end_s:  # 10.0.0.1-50
                    end_s = start_s.rsplit(".", 1)[0] + "." + end_s
                end = ipaddress.IPv4Address(end_s)
                if end < start:
                    return None, _("В диапазоне {token} конец меньше начала", token=token)
                if int(end) - int(start) >= limit * 4:
                    return None, _("Диапазон {token} слишком большой", token=token)
                for n in range(int(start), int(end) + 1):
                    add(ipaddress.IPv4Address(n))
            else:
                add(ipaddress.IPv4Address(token))
        except (ValueError, ipaddress.AddressValueError):
            return None, _("Не понимаю адрес «{token}». Примеры: 192.168.1.0/24, 10.0.0.1-10.0.0.50, 10.0.0.7", token=token)
        if len(ips) > limit:
            return None, _("Слишком много адресов (больше {limit}). Сузьте диапазон", limit=limit)
    if not ips:
        return None, _("Укажите, где искать: сеть, диапазон или адреса")
    return ips, None


def parse_lldp_mgmt_ips(rows):
    """IPv4-адреса управления соседей из lldpRemManAddrTable (адрес закодирован в OID)."""
    out = []
    for oid, _ in rows or []:
        parts = str(oid).split(".")
        # …4.2.1.<col>.<timeMark>.<localPort>.<remIndex>.<subtype>.<len>.<a>.<b>.<c>.<d>
        if len(parts) >= 6 and parts[-6] == "1" and parts[-5] == "4":
            ip = ".".join(parts[-4:])
            try:
                addr = ipaddress.IPv4Address(ip)
            except ValueError:
                continue
            if not (addr.is_unspecified or addr.is_multicast or ip == "127.0.0.1"):
                out.append(ip)
    return out


class Job:
    def __init__(self, targets, creds, labels, follow_lldp, actor):
        self.id = uuid.uuid4().hex[:12]
        self.targets = targets
        self.creds = creds          # [SnmpAuth] — только на сервере
        self.labels = labels        # подписи учётных данных для браузера
        self.follow_lldp = follow_lldp
        self.actor = actor
        self.status = "running"
        self.total = len(targets)
        self.done = 0
        self.found = []
        self.started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.finished = ""
        self.error = ""
        self.cancel = threading.Event()
        self.lock = threading.Lock()
        self.added = set()          # IP, уже добавленные из этого поиска

    def public(self, existing_by_ip=None):
        existing_by_ip = existing_by_ip or {}
        with self.lock:
            found = [dict(f) for f in self.found]
        for f in found:
            f.pop("cred", None)
            ex = existing_by_ip.get(f["ip"])
            f["existing"] = {"id": ex[0], "name": ex[1]} if ex else None
        found.sort(key=lambda f: tuple(int(x) for x in f["ip"].split(".")))
        return {"id": self.id, "status": self.status, "total": self.total, "done": self.done, "found": found,
                "started": self.started, "finished": self.finished, "error": self.error, "follow_lldp": self.follow_lldp}


_jobs = {}
_jobs_lock = threading.Lock()


def running_job():
    with _jobs_lock:
        return next((j for j in _jobs.values() if j.status == "running"), None)


def get_job(job_id):
    with _jobs_lock:
        return _jobs.get(job_id)


def start(targets, creds, labels, probe, follow_lldp=False, actor=""):
    """probe(ip, auth) → dict с ok/… (см. app.probe_switch). Возвращает (job, ошибка)."""
    if running_job():
        return None, _("Поиск уже идёт — дождитесь окончания или остановите его")
    job = Job(targets, creds, labels, follow_lldp, actor)
    with _jobs_lock:
        _jobs[job.id] = job
        for old in sorted(_jobs.values(), key=lambda j: j.started)[:-KEEP_JOBS]:
            _jobs.pop(old.id, None)
    threading.Thread(target=_run, args=(job, probe), daemon=True, name=f"discovery-{job.id}").start()
    return job, None


def _scan(job, ip, probe):
    for idx, auth in enumerate(job.creds):
        if job.cancel.is_set():
            return None
        try:
            r = probe(ip, auth)
        except Exception as e:  # один сбойный адрес не должен ронять весь поиск
            logging.getLogger("switchmap.discovery").warning("%s: %s", ip, e)
            return None
        if r and r.get("ok"):
            r["cred"] = idx
            r["cred_label"] = job.labels[idx]
            return r
    return None


def _run(job, probe):
    seen = set(job.targets)
    via = {}
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS)
    try:
        pending = {pool.submit(_scan, job, ip, probe): ip for ip in job.targets}
        while pending:
            done, _pending = concurrent.futures.wait(pending, timeout=0.5, return_when=concurrent.futures.FIRST_COMPLETED)
            if job.cancel.is_set():
                for f in pending:
                    f.cancel()
                break
            for fut in done:
                ip = pending.pop(fut)
                try:
                    r = fut.result()
                except Exception:
                    r = None
                with job.lock:
                    job.done += 1
                    if r:
                        item = {k: r.get(k) for k in ("sys_name", "sys_descr", "vendor", "model", "ports", "is_switch",
                                                      "location", "cred", "cred_label")}
                        item["ip"] = ip
                        item["via"] = via.get(ip, "")
                        job.found.append(item)
                # Соседи по LLDP — новые адреса для поиска (только у коммутаторов)
                if r and job.follow_lldp and r.get("is_switch"):
                    for n_ip in r.get("lldp_ips") or []:
                        if n_ip not in seen and len(seen) < MAX_HOSTS:
                            seen.add(n_ip)
                            via[n_ip] = r.get("sys_name") or ip
                            with job.lock:
                                job.total += 1
                            pending[pool.submit(_scan, job, n_ip, probe)] = n_ip
        job.status = "cancelled" if job.cancel.is_set() else "done"
    except Exception as e:
        job.status, job.error = "error", str(e)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        job.finished = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
