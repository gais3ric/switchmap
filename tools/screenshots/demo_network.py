"""Демо-сеть для скриншотов README: данные SNMP-симулятора (snmpsim) для четырёх коммутаторов.

    python tools/screenshots/demo_network.py <папка для .snmprec>

Коммутаторы выбираются по community (имя файла): core, floor2, floor3, warehouse.
Все отвечают на 127.0.0.1:161; демо-сервер (demo_server.py) показывает им «настоящие» адреса 10.20.0.x.
"""
import os
import random
import sys

rnd = random.Random(7)

# имя, описание, sysObjectID, портов меди, портов SFP, uplink-порт, вендор
SWITCHES = {
    "core": dict(name="core-sw01", descr="Cisco IOS XE Software, Catalyst C9300-48P", obj="1.3.6.1.4.1.9.1.2494",
                 location="Server room, rack A1", copper=48, sfp=4, cisco=True, cpu=23, temp=41, mem=(1048576, 402000)),
    "floor2": dict(name="acc-floor2", descr="Cisco IOS Software, C2960X-24PS-L", obj="1.3.6.1.4.1.9.1.1208",
                   location="Floor 2, comms closet", copper=24, sfp=4, cisco=True, cpu=12, temp=38, mem=(524288, 201000)),
    "floor3": dict(name="acc-floor3", descr="D-Link DGS-1210-28 Gigabit Ethernet Switch", obj="1.3.6.1.4.1.171.10.76.17",
                   location="Floor 3, comms closet", copper=24, sfp=4, cisco=False, cpu=8, temp=None, mem=(262144, 98000)),
    "warehouse": dict(name="wh-sw01", descr="HPE Aruba 2530-24G Switch", obj="1.3.6.1.4.1.11.2.3.7.11.137",
                      location="Warehouse", copper=24, sfp=4, cisco=False, cpu=17, temp=None, mem=(262144, 141000)),
}
VLANS = {1: "default", 10: "Office", 20: "Voice", 30: "Servers", 40: "Printers", 50: "WiFi", 99: "Management"}

# LLDP: (коммутатор, порт) -> (sysName соседа, порт соседа)
LLDP = {
    ("core", 49): ("acc-floor2", "Gi1/0/25"), ("core", 50): ("acc-floor3", "25"), ("core", 51): ("wh-sw01", "25"),
    ("core", 47): ("fw-edge01", "port2"),
    ("floor2", 25): ("core-sw01", "Te1/1/1"), ("floor3", 25): ("core-sw01", "Te1/1/2"),
    ("warehouse", 25): ("core-sw01", "Te1/1/3"), ("warehouse", 5): ("ap-warehouse-01", "eth0"),
    ("floor2", 24): ("ap-floor2-01", "eth0"),
}


def mac(prefix, n):
    return prefix + [n >> 8 & 255, n & 255]


def plan(key, sw):
    """Порты: состояние, скорость, трафик (байт/с), описание, VLAN, MAC-адреса устройств, PoE."""
    total = sw["copper"] + sw["sfp"]
    ports = {}
    vendor_prefix = {"core": [0x00, 0x50, 0x56, 0x10], "floor2": [0x3C, 0x52, 0x82, 0x20],
                     "floor3": [0xF0, 0x1F, 0xAF, 0x30], "warehouse": [0x00, 0x1B, 0x63, 0x40]}[key]
    hosts = 0
    for p in range(1, total + 1):
        sfp = p > sw["copper"]
        info = dict(up=True, speed=10000 if sfp else 1000, rin=0, rout=0, alias="", vlan=10, macs=[], poe=None, errors=0)
        if sfp:
            info["up"] = p - sw["copper"] <= (3 if key == "core" else 1)
            info["vlan"] = 1
        else:
            r = rnd.random()
            if r < 0.22:
                info["up"] = False
            elif key == "core":
                info["vlan"] = 30
                info["rin"], info["rout"] = rnd.randint(2, 40) * 250_000, rnd.randint(2, 60) * 250_000
            else:
                info["vlan"] = 20 if p % 3 == 0 else 10
                info["rin"], info["rout"] = rnd.randint(1, 30) * 20_000, rnd.randint(1, 60) * 20_000
        if info["up"] and not sfp:
            hosts += 1
            n = 1 if info["vlan"] != 20 else 2  # телефон + компьютер за ним
            info["macs"] = [mac(vendor_prefix, hosts * 4 + i) for i in range(n)]
            if sw["cisco"] and info["vlan"] == 20:
                info["poe"] = rnd.choice([3800, 4100, 5200, 6100])
        ports[p] = info

    names = {
        "core": {1: "ESXi-01 vmnic0", 2: "ESXi-01 vmnic1", 3: "ESXi-02 vmnic0", 4: "ESXi-02 vmnic1", 5: "NAS-01",
                 6: "Backup server", 9: "1C database", 10: "Domain controller", 47: "Firewall fw-edge01",
                 49: "Uplink acc-floor2", 50: "Uplink acc-floor3", 51: "Uplink wh-sw01"},
        "floor2": {1: "Reception PC", 2: "Accounting PC-1", 3: "Accounting PC-2", 7: "Printer HP M428",
                   24: "Wi-Fi AP floor 2", 25: "Uplink core-sw01"},
        "floor3": {1: "Sales PC-1", 2: "Sales PC-2", 10: "Meeting room TV", 25: "Uplink core-sw01"},
        "warehouse": {1: "Label printer", 2: "Scanner station", 5: "Wi-Fi AP warehouse", 25: "Uplink core-sw01"},
    }[key]
    for p, alias in names.items():
        ports[p].update(up=True, alias=alias)
        if p in (24, 5) and "Wi-Fi" in alias:
            ports[p].update(vlan=50, rin=900_000, rout=2_400_000, poe=12800 if sw["cisco"] else None)
        if not ports[p]["macs"] and p <= sw["copper"]:
            ports[p]["macs"] = [mac(vendor_prefix, 200 + p)]
    if key == "core":
        ports[1].update(rin=78_000_000, rout=104_000_000)   # 85% от 1 Гбит/с — оповещение о загрузке
        ports[49].update(rin=310_000_000, rout=180_000_000)
        ports[5].update(rin=46_000_000, rout=21_000_000)
        ports[12]["errors"] = 4                             # ошибки на порту — плохой кабель
    for (k, p), _peer in LLDP.items():
        if k == key and ports[p]["vlan"] != 50:
            ports[p].update(up=True, vlan=1 if p > sw["copper"] else ports[p]["vlan"])
    return ports


def snmprec(key, sw, ports, all_plans):
    rows = []
    add = lambda oid, t, v: rows.append((oid, t, v))
    add("1.3.6.1.2.1.1.1.0", 4, sw["descr"])
    add("1.3.6.1.2.1.1.2.0", 6, sw["obj"])
    add("1.3.6.1.2.1.1.3.0", 67, 412345600)
    add("1.3.6.1.2.1.1.5.0", 4, sw["name"])
    add("1.3.6.1.2.1.1.6.0", 4, sw["location"])
    total = len(ports)
    for p, i in ports.items():
        sfp = p > sw["copper"]
        if sw["cisco"]:
            name = f"Te1/1/{p - sw['copper']}" if sfp else f"Gi1/0/{p}"
            descr = ("TenGigabitEthernet" if sfp else "GigabitEthernet") + name[2:]
        else:
            name = str(p)
            descr = f"{sw['descr'].split(' Switch')[0].split(' Gigabit')[0]} Port {p}"
        add(f"1.3.6.1.2.1.2.2.1.1.{p}", 2, p)
        add(f"1.3.6.1.2.1.2.2.1.2.{p}", 4, descr)
        add(f"1.3.6.1.2.1.2.2.1.3.{p}", 2, 6)
        add(f"1.3.6.1.2.1.2.2.1.5.{p}", 66, min(i["speed"] * 1_000_000, 4294967295))
        add(f"1.3.6.1.2.1.2.2.1.7.{p}", 2, 1)
        add(f"1.3.6.1.2.1.2.2.1.8.{p}", 2, 1 if i["up"] else 2)
        rin, rout = (i["rin"], i["rout"]) if i["up"] else (0, 0)
        add(f"1.3.6.1.2.1.2.2.1.10.{p}", "65:numeric", f"rate={max(rin, 1)},wrap=1,atime=1")
        add(f"1.3.6.1.2.1.2.2.1.14.{p}", "65:numeric" if i["errors"] else 65,
            f"rate={i['errors']},atime=1" if i["errors"] else 0)
        add(f"1.3.6.1.2.1.2.2.1.16.{p}", "65:numeric", f"rate={max(rout, 1)},wrap=1,atime=1")
        add(f"1.3.6.1.2.1.2.2.1.20.{p}", 65, 0)
        add(f"1.3.6.1.2.1.31.1.1.1.1.{p}", 4, name)
        add(f"1.3.6.1.2.1.31.1.1.1.6.{p}", "70:numeric", f"rate={max(rin, 1)},atime=1")
        add(f"1.3.6.1.2.1.31.1.1.1.10.{p}", "70:numeric", f"rate={max(rout, 1)},atime=1")
        add(f"1.3.6.1.2.1.31.1.1.1.15.{p}", 66, i["speed"])
        add(f"1.3.6.1.2.1.31.1.1.1.18.{p}", "4x", i["alias"].encode().hex())
        add(f"1.3.6.1.2.1.17.1.4.1.2.{p}", 2, p)
        add(f"1.3.6.1.2.1.17.7.1.4.5.1.1.{p}", 66, i["vlan"])
    add("1.3.6.1.2.1.17.1.2.0", 2, total)
    for v, vname in VLANS.items():
        add(f"1.3.6.1.2.1.17.7.1.4.3.1.1.{v}", 4, vname)

    # Таблица MAC (dot1dTpFdb): свои устройства + на uplink-портах — устройства соседей
    fdb = {}
    for p, i in ports.items():
        for m in i["macs"]:
            fdb[tuple(m)] = p
    for (k, p), (peer, _port) in LLDP.items():
        if k != key:
            continue
        peer_key = next((pk for pk, s in SWITCHES.items() if s["name"] == peer), None)
        if peer_key:
            for pi in all_plans[peer_key].values():
                for m in pi["macs"]:
                    fdb.setdefault(tuple(m), p)
    for m, p in sorted(fdb.items()):
        dotted = ".".join(str(x) for x in m)
        add(f"1.3.6.1.2.1.17.4.3.1.1.{dotted}", "4x", "".join(f"{x:02x}" for x in m))
        add(f"1.3.6.1.2.1.17.4.3.1.2.{dotted}", 2, p)
    # ARP на ядре: IP-адреса устройств
    if key == "core":
        n = 10
        for k2, pl in all_plans.items():
            for pi in pl.values():
                for m in pi["macs"]:
                    n += 1
                    net = {10: 10, 20: 20, 30: 30, 40: 40, 50: 50}.get(pi["vlan"], 10)
                    add(f"1.3.6.1.2.1.4.22.1.2.1.10.20.{net}.{n % 250 + 2}", "4x", "".join(f"{x:02x}" for x in m))

    # LLDP-соседи (lldpRemTable: timeMark.localPort.index)
    for (k, p), (peer, peer_port) in LLDP.items():
        if k != key:
            continue
        idx = f"0.{p}.1"
        base = "1.0.8802.1.1.2.1.4.1.1"
        add(f"{base}.2.{idx}", 2, p)
        add(f"{base}.5.{idx}", "4x", "".join(f"{rnd.randint(0, 255):02x}" for _ in range(6)))
        add(f"{base}.7.{idx}", 4, peer_port)
        add(f"{base}.8.{idx}", 4, peer_port)
        add(f"{base}.9.{idx}", 4, peer)

    # Здоровье — как у настоящих устройств: у каждого производителя свои таблицы
    size, used = sw["mem"]
    if sw["cisco"]:   # CISCO-PROCESS-MIB, CISCO-MEMORY-POOL-MIB, CISCO-ENVMON-MIB
        add("1.3.6.1.4.1.9.9.109.1.1.1.1.7.1", 66, sw["cpu"])
        add("1.3.6.1.4.1.9.9.48.1.1.1.5.1", 66, used * 1024)
        add("1.3.6.1.4.1.9.9.48.1.1.1.6.1", 66, (size - used) * 1024)
        if sw["temp"]:
            add("1.3.6.1.4.1.9.9.13.1.3.1.3.1", 66, sw["temp"])
    elif "D-Link" in sw["descr"]:   # DLINK-AGENT-MIB: проценты
        add("1.3.6.1.4.1.171.12.1.1.6.2.0", 2, sw["cpu"])
        add("1.3.6.1.4.1.171.12.1.1.9.1.4.1", 2, round(used / size * 100))
    else:   # HPE ProCurve / Aruba
        add("1.3.6.1.4.1.11.2.14.11.5.1.9.6.1.0", 2, sw["cpu"])
        add("1.3.6.1.4.1.11.2.14.11.5.1.1.2.1.1.1.5.1", 66, size * 1024)
        add("1.3.6.1.4.1.11.2.14.11.5.1.1.2.1.1.1.7.1", 66, used * 1024)
    # PoE
    for p, i in ports.items():
        if i["poe"]:
            add(f"1.3.6.1.2.1.105.1.1.1.1.3.1.{p}", 2, 1)
            add(f"1.3.6.1.2.1.105.1.1.1.1.6.1.{p}", 2, 3)
            add(f"1.3.6.1.4.1.9.9.402.1.2.1.9.1.{p}", 66, i["poe"])

    def key_of(row):
        return tuple(int(x) for x in row[0].split("."))
    return "\n".join(f"{o}|{t}|{v}" for o, t, v in sorted(rows, key=key_of)) + "\n"


def main(out):
    os.makedirs(out, exist_ok=True)
    plans = {k: plan(k, sw) for k, sw in SWITCHES.items()}
    for k, sw in SWITCHES.items():
        with open(os.path.join(out, f"{k}.snmprec"), "w", encoding="utf-8", newline="\n") as f:
            f.write(snmprec(k, sw, plans[k], plans))
    return plans


if __name__ == "__main__":
    main(sys.argv[1])
    print("ok")
