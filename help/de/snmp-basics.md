---
title: Was ist SNMP
category: devices
order: 2
summary: Einfach erklärt: Versionen v2c und v3, Community, Benutzer und Passwörter, Sicherheit.
keywords: snmp v2c v3 community benutzer authentifizierung verschlüsselung sha aes md5 des kontext sicherheit udp 161
---
**SNMP** (Simple Network Management Protocol) ist der Standardweg, ein Netzgerät nach seinem Zustand zu fragen: Portliste, welche Ports aktiv sind, wie viel Verkehr geflossen ist, welche MAC-Adressen sichtbar sind, CPU-Last und Temperatur. Praktisch alle verwaltbaren Switches unterstützen es.

SwitchMap **liest** nur Daten — es ändert nie etwas an den Switches. Nur-Lese-Zugriff genügt.

Anfragen gehen an den **UDP-Port 161** des Switches.

# v2c oder v3 {#v2c-or-v3}

| | SNMP v2c | SNMP v3 |
|---|---|---|
| Wie der Zugriff geprüft wird | Über ein gemeinsames Passwort — die **Community** | Benutzer und Passwort |
| Datenverschlüsselung | Keine — alles geht im Klartext | Ja (AES, DES) |
| Einrichtung | Eine Zeile am Switch | Einige Zeilen |
| Wann wählen | Ein isoliertes Management-Netz | In allen anderen Fällen |

> **Wichtig:** Die Community `public` kennt jeder. Wenn Sie v2c nutzen, legen Sie eine eigene starke Community fest und beschränken Sie den SNMP-Zugriff auf die Adresse des SwitchMap-Servers.

# Community {#community}

Eine Community ist einfach eine Zeichenkette, die der Switch mit der empfangenen vergleicht. Zum Lesen wird meist eine Community mit **RO**-Rechten (nur lesen) angelegt. In SwitchMap kommt sie in das Feld **Community**. Bei der Netzsuche können Sie mehrere durch Kommas getrennt angeben.

# SNMPv3 {#snmpv3}

Bei v3 wird am Switch ein **Benutzer** mit zwei Passwörtern angelegt:

- **Authentifizierung** (SHA, SHA-256 und andere, das veraltete MD5) beweist, dass die Anfrage von Ihnen kommt und unterwegs nicht verändert wurde.
- **Verschlüsselung** (AES128 und andere, das veraltete DES) verbirgt den Inhalt der Antworten.

Sicherheitsstufen:

| Stufe | Authentifizierung | Verschlüsselung |
|---|---|---|
| noAuthNoPriv | nein | nein |
| authNoPriv | ja | nein |
| authPriv | ja | ja — empfohlen |

Geben Sie in SwitchMap denselben **Algorithmus** und dieselben **Passwörter** wie am Switch an. Passwörter müssen mindestens 8 Zeichen lang sein (vom Standard vorgeschrieben).

Der **Kontext** bleibt meist leer. Er wird z. B. bei Cisco-Switches benötigt, wo die MAC-Tabelle eines VLANs über den Kontext `vlan-10` gelesen wird.

SNMPv3-Passwörter werden in der SwitchMap-Datenbank verschlüsselt gespeichert, der Schlüssel liegt in einer separaten Datei, `switchmap.secret`.

# Was SwitchMap liest {#what}

| Daten | Quelle (MIB) |
|---|---|
| Name, Beschreibung, Standort | SNMPv2-MIB (system) |
| Ports, Status, Geschwindigkeit, Verkehrs- und Fehlerzähler | IF-MIB |
| Portbeschreibungen (ifAlias) | IF-MIB |
| MAC-Adressen an den Ports | BRIDGE-MIB, Q-BRIDGE-MIB |
| Port-VLANs | Q-BRIDGE-MIB |
| Nachbarn | LLDP-MIB |
| CPU, Speicher, Temperatur | verschieden — je nach Hersteller |
| PoE | POWER-ETHERNET-MIB |

Fehlen einzelne Daten, liefert der Switch sie nicht per SNMP oder dafür wird ein anderer Kontext benötigt. Alles andere funktioniert trotzdem.
