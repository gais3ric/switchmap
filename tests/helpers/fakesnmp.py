"""Подставной SNMP-агент: возвращает реалистичные ответы walk для app.snmp_walk."""
import itertools

_tick = itertools.count(1)
STATE = {"port2_up": False, "fail": False}

PORTS = {str(i): f"GigabitEthernet0/{i}" for i in range(1, 9)}
PORTS["10101"] = "Vlan1"  # не-физический интерфейс с большим ifIndex


def make_walk():
    def snmp_walk(ip, community, oid, timeout=3):
        if STATE["fail"]:
            return []
        n = STATE.setdefault("n", 0)
        base = "1.3.6.1.2.1.2.2.1"
        def per_port(fn):
            return [(f"{oid}.{i}", fn(i)) for i in PORTS]
        if oid == base + ".2":
            return per_port(lambda i: PORTS[i])
        if oid == base + ".8":
            return per_port(lambda i: 1 if (i != "2" or STATE["port2_up"]) else 2)
        if oid == base + ".5":
            return per_port(lambda i: 1_000_000_000)
        if oid in (base + ".10", base + ".16"):
            STATE["n"] = n + (1 if oid.endswith(".10") else 0)
            return per_port(lambda i: (int(i) % 50 + 1) * 1_000_000 * (STATE["n"]))
        # 64-битные счётчики ifXTable — у всех портов, кроме 5 (на нём проверяем 32-битный путь)
        if oid in ("1.3.6.1.2.1.31.1.1.1.6", "1.3.6.1.2.1.31.1.1.1.10"):
            return [(f"{oid}.{i}", (int(i) % 50 + 1) * 1_000_000 * (STATE["n"] + 1) + 10 ** 10)
                    for i in PORTS if i != "5"]
        if oid in (base + ".11", base + ".17"):
            return per_port(lambda i: 1000 * STATE["n"])
        if oid in (base + ".14", base + ".20"):
            return per_port(lambda i: STATE["n"] if i == "3" else 0)
        # PoE: index = group.port
        if oid == "1.3.6.1.2.1.105.1.1.1.1.3":  # AdminEnable
            return [(f"{oid}.1.1", 1), (f"{oid}.1.2", 1), (f"{oid}.1.3", 1), (f"{oid}.1.4", 2)]
        if oid == "1.3.6.1.2.1.105.1.1.1.1.6":  # DetectionStatus: 2 searching, 3 delivering, 4 fault, 1 disabled
            return [(f"{oid}.1.1", 2), (f"{oid}.1.2", 3), (f"{oid}.1.3", 4), (f"{oid}.1.4", 1)]
        if oid == "1.3.6.1.2.1.105.1.1.1.1.5":  # PowerPairs — не мощность!
            return [(f"{oid}.1.{i}", 1) for i in ("1", "2", "3", "4")]
        if oid == "1.3.6.1.4.1.9.9.402.1.2.1.9" and STATE.get("cisco_power", True):
            return [(f"{oid}.1.2", 6500)]
        # FDB / bridge / ARP
        mac1 = bytes([0, 0x11, 0x22, 0x33, 0x44, 0x55])
        if oid == "1.3.6.1.2.1.17.4.3.1.1":
            return [(f"{oid}.0.17.34.51.68.85", mac1)]
        if oid == "1.3.6.1.2.1.17.4.3.1.2":
            return [(f"{oid}.0.17.34.51.68.85", 4)]
        if oid == "1.3.6.1.2.1.17.1.4.1.2":
            return [(f"{oid}.{i}", int(i)) for i in ("1", "2", "3", "4")]
        if oid == "1.3.6.1.2.1.4.22.1.2":
            return []
        # Health
        if oid == "1.3.6.1.2.1.25.3.3.1.2":
            return [(f"{oid}.1", 10 + STATE["n"] % 7), (f"{oid}.2", 20)]
        # hrStorage: строка 1 — RAM (40%), строка 2 — флеш/диск (90%), не должна учитываться
        if oid == "1.3.6.1.2.1.25.2.3.1.2":
            return [(f"{oid}.1", "1.3.6.1.2.1.25.2.1.2"), (f"{oid}.2", "1.3.6.1.2.1.25.2.1.4")]
        if oid == "1.3.6.1.2.1.25.2.3.1.4":
            return [(f"{oid}.1", 1024), (f"{oid}.2", 1024)]
        if oid == "1.3.6.1.2.1.25.2.3.1.5":
            return [(f"{oid}.1", 1000), (f"{oid}.2", 100000)]
        if oid == "1.3.6.1.2.1.25.2.3.1.6":
            return [(f"{oid}.1", 400 + STATE["n"] * 5), (f"{oid}.2", 90000)]
        if oid == "1.3.6.1.4.1.9.9.13.1.3.1.3":
            return [(f"{oid}.1", 42)]
        return []
    return snmp_walk


def install(m):
    walk = make_walk()
    m.snmp_walk = walk
    m.snmp_walk_ex = lambda ip, auth, oid, timeout=3: (walk(ip, auth, oid, timeout), None)
    m.ping_host = lambda ip, timeout=1: True
