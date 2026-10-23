"""Cisco Catalyst: таблица MAC по каждому VLAN (community@VLAN / контекст vlan-N), VLAN портов из CISCO-VLAN-MEMBERSHIP.
Без сети: ответы SNMP подставляются. argv: <рабочая папка с тестовой базой>"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(sys.argv[1]); sys.path[:0] = [ROOT]

fails = []
def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""))
    if not cond:
        fails.append(name)

import app as m

IFS = {"10101": "GigabitEthernet0/1", "10102": "GigabitEthernet0/2", "10103": "GigabitEthernet0/3"}
COMMON = {}
for idx, name in IFS.items():
    COMMON[f"1.3.6.1.2.1.2.2.1.8.{idx}"] = 1          # ifOperStatus
    COMMON[f"1.3.6.1.2.1.2.2.1.2.{idx}"] = name       # ifDescr
    COMMON[f"1.3.6.1.2.1.2.2.1.3.{idx}"] = 6          # ifType
    COMMON[f"1.3.6.1.2.1.31.1.1.1.1.{idx}"] = "Gi0/" + idx[-1]
COMMON.update({
    "1.3.6.1.4.1.9.9.46.1.3.1.1.2.1.1": 1, "1.3.6.1.4.1.9.9.46.1.3.1.1.2.1.10": 1,
    "1.3.6.1.4.1.9.9.46.1.3.1.1.2.1.1002": 1,                       # служебный — не опрашивается
    "1.3.6.1.4.1.9.9.46.1.3.1.1.4.1.1": "default", "1.3.6.1.4.1.9.9.46.1.3.1.1.4.1.10": "OFFICE",
    "1.3.6.1.4.1.9.9.68.1.2.2.1.2.10101": 1, "1.3.6.1.4.1.9.9.68.1.2.2.1.2.10102": 10,
    "1.3.6.1.4.1.9.9.68.1.2.2.1.2.10103": 10,
})
MAC1, MAC2, MAC3 = (0, 0x11, 0x22, 0x33, 0x44, 1), (0, 0x11, 0x22, 0x33, 0x44, 2), (0, 0x11, 0x22, 0x33, 0x44, 3)
def sfx(mac): return ".".join(map(str, mac))
VLAN1 = {"1.3.6.1.2.1.17.1.4.1.2.1": 10101, f"1.3.6.1.2.1.17.4.3.1.1.{sfx(MAC1)}": bytes(MAC1),
         f"1.3.6.1.2.1.17.4.3.1.2.{sfx(MAC1)}": 1}
VLAN10 = {"1.3.6.1.2.1.17.1.4.1.2.2": 10102, "1.3.6.1.2.1.17.1.4.1.2.3": 10103,
          f"1.3.6.1.2.1.17.4.3.1.1.{sfx(MAC2)}": bytes(MAC2), f"1.3.6.1.2.1.17.4.3.1.2.{sfx(MAC2)}": 2,
          f"1.3.6.1.2.1.17.4.3.1.1.{sfx(MAC3)}": bytes(MAC3), f"1.3.6.1.2.1.17.4.3.1.2.{sfx(MAC3)}": 3}
# Без индекса VLAN Catalyst отвечает данными VLAN 1
VIEWS = {"public": {**COMMON, **VLAN1}, "public@1": {**COMMON, **VLAN1}, "public@10": {**COMMON, **VLAN10},
         "v3:": {**COMMON, **VLAN1}, "v3:vlan-1": {**COMMON, **VLAN1}, "v3:vlan-10": {**COMMON, **VLAN10}}

walks = []
def fake_walk_ex(ip, auth, oid, timeout=3):
    auth = m._as_snmp_auth(auth)
    view = VIEWS.get(f"v3:{auth.context}" if auth.version == "3" else auth.community, {})
    walks.append((view is not None and (auth.context or auth.community), oid))
    prefix = oid + "."
    return [(k, v) for k, v in sorted(view.items()) if k.startswith(prefix)], None
m.snmp_walk_ex = fake_walk_ex

def devices(result):
    return {info["port"]: sorted(d["mac"] for d in info["devices"]) for info in result.values()}

r = m.poll_switch_snmp("10.1.1.1", "public", 3)
d = devices(r)
check("MAC в VLAN 1 найден", d.get(1) == ["00:11:22:33:44:01"], d)
check("MAC в VLAN 10 найдены (community@10)", d.get(2) == ["00:11:22:33:44:02"] and d.get(3) == ["00:11:22:33:44:03"], d)
check("служебные VLAN 1002–1005 не опрашиваются", not any(c == "public@1002" for c, _o in walks))
vl = {info["port"]: info["vlan"] for info in r.values()}
check("VLAN порта и имя из CISCO-VLAN-MEMBERSHIP / VTP",
      vl.get(1) == {"id": "1", "name": "default"} and vl.get(2) == {"id": "10", "name": "OFFICE"}, vl)

v3 = m.SnmpAuth("3", user="mon", auth_proto="SHA", auth_key="authpass123")
d = devices(m.poll_switch_snmp("10.1.1.2", v3, 3))
check("SNMPv3: VLAN 10 через контекст vlan-10", d.get(2) == ["00:11:22:33:44:02"], d)
check("SNMPv3 с заданным контекстом — опрос как настроено",
      m.snmp_vlan_auth(m.SnmpAuth("3", user="mon", context="vlan-5"), 10) is None)
check("community@VLAN не портит исходные данные", m.snmp_vlan_auth(v3, 10) is not v3 and v3.context == "")

# Повторный опрос в режиме «раз в час»: таблица портов VLAN берётся из памяти, MAC читаются заново
walks.clear()
m.poll_switch_snmp("10.1.1.1", "public", 3, refresh_static=False)
check("раз в час: MAC по VLAN читаются каждый опрос",
      ("public@10", "1.3.6.1.2.1.17.4.3.1.2") in walks)
check("раз в час: справочные таблицы VLAN из памяти",
      ("public@10", "1.3.6.1.2.1.17.1.4.1.2") not in walks and not any(o == m.CISCO_VTP_VLAN_STATE for _c, o in walks))

# Не Cisco: лишних запросов по VLAN нет
VIEWS["public"] = {k: v for k, v in VIEWS["public"].items() if not k.startswith("1.3.6.1.4.1.9.")}
walks.clear()
d = devices(m.poll_switch_snmp("10.1.1.3", "public", 3))
check("не Cisco: опрос по VLAN не выполняется", not any("@" in str(c) for c, _o in walks) and d.get(1) == ["00:11:22:33:44:01"], d)

print(f"\nИТОГО: {'провалено ' + str(len(fails)) if fails else 'все проверки пройдены'}")
sys.exit(1 if fails else 0)
