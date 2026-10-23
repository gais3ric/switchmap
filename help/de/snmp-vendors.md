---
title: SNMP auf Switches aktivieren
category: devices
order: 3
summary: Fertige Befehle für Cisco, HPE/Aruba, Juniper, MikroTik, Huawei, D-Link, TP-Link, Eltex und andere.
keywords: konfigurieren aktivieren snmp cisco ios catalyst hpe aruba procurve comware h3c juniper junos mikrotik routeros huawei d-link dlink tp-link eltex ubiquiti unifi lldp community
---
Unten steht die minimale Konfiguration: **Nur-Lese**-Zugriff, beschränkt auf die Adresse des SwitchMap-Servers, und aktiviertes **LLDP** für die [Topologie](/help/topology). In den Beispielen:

| Wert | Ersetzen durch |
|---|---|
| `192.168.1.10` | die IP-Adresse des SwitchMap-Servers |
| `MyStr0ngRO` | Ihre eigene Community (für v2c) |
| `swmap` | den SNMPv3-Benutzernamen |
| `AuthPass123`, `PrivPass123` | Ihre eigenen v3-Passwörter, mindestens 8 Zeichen |

> **Wichtig:** Die Befehle können je nach Modell und Firmwareversion leicht abweichen. Wird ein Befehl nicht angenommen, suchen Sie in der Herstellerdokumentation den Abschnitt „SNMP“ — die Parameter heißen ähnlich.

Fügen Sie den Switch nach der Einrichtung in SwitchMap hinzu und klicken Sie auf **Prüfen und ausfüllen** — so sehen Sie sofort, ob der Zugriff funktioniert.

# Cisco IOS und IOS-XE (Catalyst) {#cisco}

SNMP v2c:

```
configure terminal
access-list 10 permit 192.168.1.10
snmp-server community MyStr0ngRO RO 10
lldp run
end
write memory
```

SNMP v3 (empfohlen):

```
configure terminal
access-list 10 permit 192.168.1.10
snmp-server group SWMAP v3 priv access 10
snmp-server user swmap SWMAP v3 auth sha AuthPass123 priv aes 128 PrivPass123
lldp run
end
write memory
```

SNMPv3-Benutzer erscheinen nicht in `show running-config` — das ist normal. Prüfen mit: `show snmp user`.

Cisco führt für jedes VLAN eine eigene MAC-Tabelle – SwitchMap fragt jedes VLAN selbst ab. Bei v2c ist nichts einzurichten. Bei v3 erlauben Sie die VLAN-Kontexte: `snmp-server group SWMAP v3 priv context vlan- match prefix`, und lassen das Feld „Kontext“ in SwitchMap leer.

# Cisco Business und Small Business (CBS, SG) {#cisco-sb}

Weboberfläche: **SNMP → Engine ID** (Standard belassen), **SNMP → Communities** oder **SNMP → Users** (für v3). SNMP einschalten: **Security → TCP/UDP Services → SNMP Service**. LLDP: **Administration → Discovery – LLDP → Properties**.

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

`snmpv3 enable` fragt eventuell nach Anfangspasswörtern — geben Sie beliebige ein und entfernen Sie danach den Anfangsbenutzer `initial`.

# HPE Aruba CX (AOS-CX) {#aruba-cx}

```
configure
snmp-server vrf default
snmp-server community MyStr0ngRO
snmpv3 user swmap auth sha auth-pass plaintext AuthPass123 priv aes priv-pass plaintext PrivPass123
lldp
write memory
```

Läuft das Management über den mgmt-Port, verwenden Sie `snmp-server vrf mgmt`.

# HPE Comware und H3C (HPE 5130, 5140, 1950 u. a.) {#comware}

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

# Juniper (Junos, EX und QFX) {#juniper}

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

SNMP v3 (RouterOS 7): In RouterOS ist der Community-Name zugleich der v3-Benutzername.

```
/snmp community add name=swmap addresses=192.168.1.10/32 security=private authentication-protocol=SHA1 authentication-password=AuthPass123 encryption-protocol=AES encryption-password=PrivPass123
```

LLDP (RouterOS 7): `/ip neighbor discovery-settings set protocol=cdp,lldp,mndp`.

# Huawei (VRP, S-Serie) {#huawei}

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

Die letzten beiden Befehle fragen nach den Passwörtern.

# D-Link (DGS, DES) {#dlink}

Über die Kommandozeile (die meisten Modelle DGS-1210/3000/3100):

```
enable snmp
create snmp community MyStr0ngRO view CommunityView read_only
enable lldp
save
```

In der Weboberfläche: **Management → SNMP Settings** (SNMP aktivieren, Community oder v3-Benutzer hinzufügen). Für v3 ist die Weboberfläche bequemer.

# TP-Link (JetStream, Omada) {#tplink}

Weboberfläche: **Maintenance → SNMP → Global Config** — SNMP aktivieren; **SNMP → Community** — eine **read-only**-Community hinzufügen; für v3 — **SNMP User**. LLDP: **L2 Features → LLDP**. Switches unter einem Omada-Controller werden im Controller eingerichtet: **Settings → Services → SNMP**.

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

SNMP wird im UniFi-Controller aktiviert: **Settings → System → SNMP** (v1/v2c-Community oder v3-Benutzer). Die Einstellung gilt für alle Switches des Standorts.

# Prüfung vom Server aus {#check}

Mit den Net-SNMP-Werkzeugen können Sie den Zugriff so testen:

```
snmpget -v2c -c MyStr0ngRO 192.0.2.5 1.3.6.1.2.1.1.5.0
snmpget -v3 -l authPriv -u swmap -a SHA -A AuthPass123 -x AES -X PrivPass123 192.0.2.5 1.3.6.1.2.1.1.5.0
```

Die Antwort ist der Name des Switches. „Timeout“ bedeutet: kein Netzzugriff, falsche Community oder falscher Benutzer. Mehr: [Fehlerbehebung](/help/troubleshooting).
