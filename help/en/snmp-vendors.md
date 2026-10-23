---
title: Enabling SNMP on switches
category: devices
order: 3
summary: Ready-to-use commands for Cisco, HPE/Aruba, Juniper, MikroTik, Huawei, D-Link, TP-Link, Eltex and others.
keywords: configure enable snmp cisco ios catalyst hpe aruba procurve comware h3c juniper junos mikrotik routeros huawei d-link dlink tp-link eltex ubiquiti unifi lldp community
---
Below is the minimal configuration: **read-only** access, restricted to the SwitchMap server address, plus **LLDP** enabled for the [topology](/help/topology). In the examples:

| Value | Replace with |
|---|---|
| `192.168.1.10` | the IP address of the SwitchMap server |
| `MyStr0ngRO` | your own community (for v2c) |
| `swmap` | the SNMPv3 user name |
| `AuthPass123`, `PrivPass123` | your own v3 passwords, at least 8 characters |

> **Important:** commands may differ slightly depending on the model and firmware version. If a command is not accepted, look for the “SNMP” section in the vendor documentation — the parameter names will be similar.

After configuring, add the switch in SwitchMap and click **Check and fill in** — you will see right away whether access works.

# Cisco IOS and IOS-XE (Catalyst) {#cisco}

SNMP v2c:

```
configure terminal
access-list 10 permit 192.168.1.10
snmp-server community MyStr0ngRO RO 10
lldp run
end
write memory
```

SNMP v3 (recommended):

```
configure terminal
access-list 10 permit 192.168.1.10
snmp-server group SWMAP v3 priv access 10
snmp-server user swmap SWMAP v3 auth sha AuthPass123 priv aes 128 PrivPass123
lldp run
end
write memory
```

SNMPv3 users are not shown in `show running-config` — that is normal. To check: `show snmp user`.

Cisco keeps a separate MAC table for each VLAN — SwitchMap queries every VLAN by itself. Over v2c nothing needs to be configured. Over v3 allow the VLAN contexts: `snmp-server group SWMAP v3 priv context vlan- match prefix`, and leave the «Context» field in SwitchMap empty.

# Cisco Business and Small Business (CBS, SG) {#cisco-sb}

Web interface: **SNMP → Engine ID** (keep the default), **SNMP → Communities** or **SNMP → Users** (for v3). To turn SNMP on: **Security → TCP/UDP Services → SNMP Service**. LLDP: **Administration → Discovery – LLDP → Properties**.

# HPE Aruba (ArubaOS-Switch, ProCurve) {#aruba}

```
configure
snmp-server community "MyStr0ngRO" operator restricted
snmpv3 enable
snmpv3 user swmap auth sha AuthPass123 priv aes PrivPass123
snmpv3 group operatorauth user swmap sec-model ver3
lldp run
write memory
```

`snmpv3 enable` may ask for initial passwords — enter any, then remove the initial user `initial`.

# HPE Aruba CX (AOS-CX) {#aruba-cx}

```
configure
snmp-server vrf default
snmp-server community MyStr0ngRO
snmpv3 user swmap auth sha auth-pass plaintext AuthPass123 priv aes priv-pass plaintext PrivPass123
lldp
write memory
```

If management goes through the mgmt port, use `snmp-server vrf mgmt`.

# HPE Comware and H3C (HPE 5130, 5140, 1950 and others) {#comware}

```
system-view
snmp-agent
snmp-agent sys-info version v2c v3
snmp-agent community read MyStr0ngRO
snmp-agent group v3 swmap-grp privacy
snmp-agent usm-user v3 swmap swmap-grp simple authentication-mode sha AuthPass123 privacy-mode aes128 PrivPass123
lldp global enable
save
```

# Juniper (Junos, EX and QFX) {#juniper}

SNMP v2c:

```
set snmp community MyStr0ngRO authorization read-only
set snmp community MyStr0ngRO clients 192.168.1.10/32
set protocols lldp interface all
commit
```

SNMP v3:

```
set snmp v3 usm local-engine user swmap authentication-sha authentication-password AuthPass123
set snmp v3 usm local-engine user swmap privacy-aes128 privacy-password PrivPass123
set snmp v3 vacm security-to-group security-model usm security-name swmap group swmap-grp
set snmp v3 vacm access group swmap-grp default-context-prefix security-model any security-level privacy read-view all
set snmp view all oid .1 include
commit
```

# MikroTik (RouterOS) {#mikrotik}

SNMP v2c:

```
/snmp set enabled=yes
/snmp community set [find default=yes] name=MyStr0ngRO addresses=192.168.1.10/32 read-access=yes write-access=no
```

SNMP v3 (RouterOS 7): in RouterOS the community name is also the v3 user name.

```
/snmp community add name=swmap addresses=192.168.1.10/32 security=private authentication-protocol=SHA1 authentication-password=AuthPass123 encryption-protocol=AES encryption-password=PrivPass123
```

LLDP (RouterOS 7): `/ip neighbor discovery-settings set protocol=cdp,lldp,mndp`.

# Huawei (VRP, S series) {#huawei}

```
system-view
snmp-agent
snmp-agent sys-info version v2c v3
snmp-agent community read cipher MyStr0ngRO
snmp-agent group v3 swmap-grp privacy
snmp-agent usm-user v3 swmap group swmap-grp
snmp-agent usm-user v3 swmap authentication-mode sha
snmp-agent usm-user v3 swmap privacy-mode aes128
lldp enable
save
```

The last two commands prompt for the passwords.

# D-Link (DGS, DES) {#dlink}

From the command line (most DGS-1210/3000/3100 models):

```
enable snmp
create snmp community MyStr0ngRO view CommunityView read_only
enable lldp
save
```

In the web interface: **Management → SNMP Settings** (enable SNMP, add a community or a v3 user). For v3 the web interface is more convenient.

# TP-Link (JetStream, Omada) {#tplink}

Web interface: **Maintenance → SNMP → Global Config** — enable SNMP; **SNMP → Community** — add a **read-only** community; for v3 — **SNMP User**. LLDP: **L2 Features → LLDP**. Switches managed by an Omada controller are configured in the controller: **Settings → Services → SNMP**.

# Eltex (MES) {#eltex}

```
configure
snmp-server server
snmp-server community MyStr0ngRO ro 192.168.1.10
lldp run
end
write
```

# Ubiquiti UniFi {#unifi}

SNMP is enabled in the UniFi controller: **Settings → System → SNMP** (v1/v2c community or a v3 user). The setting applies to all switches of the site.

# Checking from the server {#check}

If you have the Net-SNMP tools, you can test access like this:

```
snmpget -v2c -c MyStr0ngRO 192.0.2.5 1.3.6.1.2.1.1.5.0
snmpget -v3 -l authPriv -u swmap -a SHA -A AuthPass123 -x AES -X PrivPass123 192.0.2.5 1.3.6.1.2.1.1.5.0
```

The reply is the switch name. “Timeout” means no network access, a wrong community or a wrong user. More: [Troubleshooting](/help/troubleshooting).
