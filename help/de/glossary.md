---
title: Glossar
category: start
order: 3
summary: Einfache Erklärungen der Netzwerkbegriffe, die in SwitchMap vorkommen.
keywords: glossar begriffe was ist vlan trunk uplink mac ip lldp snmp sfp poe patchpanel ifalias duplex
---
| Begriff | Was es ist |
|---|---|
| **Switch** | Ein Gerät, an das Computer, Telefone, Access Points und andere Switches per Kabel angeschlossen werden. Es leitet Daten zwischen ihnen weiter |
| **Port** | Eine Buchse am Switch für ein Kabel |
| **Link** | Der Port ist verbunden und am anderen Ende ist ein eingeschaltetes Gerät |
| **Patchpanel** | Eine Buchsenleiste im Rack, an der die Kabel aus den Büros ankommen. Mit dem Switch wird sie über kurze Kabel (Patchkabel) verbunden |
| **RJ-45** | Der übliche Kupfer-Netzwerkstecker (Twisted Pair) |
| **SFP** | Ein Steckplatz für ein austauschbares Modul — meist Glasfaser, für größere Entfernungen und Geschwindigkeiten |
| **MAC-Adresse** | Die eindeutige „Seriennummer“ eines Netzgeräts, z. B. `00:1A:2B:3C:4D:5E`. Ein Switch merkt sich, welche MAC hinter welchem Port liegt |
| **IP-Adresse** | Die Adresse eines Geräts im Netz, z. B. `192.168.1.25` |
| **VLAN** | Ein logisches „Teilnetz“ im Switch: Ports verschiedener VLANs sehen sich nicht direkt. Z. B. VLAN 10 für die Buchhaltung, VLAN 20 für Telefone |
| **Trunk** | Ein Port, der mehrere VLANs gleichzeitig führt — meist die Verbindung zu einem anderen Switch |
| **Uplink** | Ein Port, der „nach oben“ führt — zu einem anderen Switch oder zum Netzkern |
| **SNMP** | Das Protokoll, mit dem SwitchMap den Switch nach seinem Zustand fragt. Siehe [Was ist SNMP](/help/snmp-basics) |
| **Community** | Das „Passwort“ von SNMP v2c |
| **LLDP** | Ein Protokoll, mit dem benachbarte Geräte einander über sich informieren. Daraus wird die [Topologie](/help/topology) aufgebaut |
| **Portbeschreibung (ifAlias)** | Eine in der Switch-Konfiguration gesetzte Portbeschriftung (z. B. „uplink-core“) |
| **Portauslastung** | Wie viel Prozent der Portgeschwindigkeit der Verkehr belegt |
| **Portfehler** | Bei der Übertragung beschädigte Daten. Meist ein Zeichen für ein schlechtes Kabel oder einen schlechten Stecker |
| **Geschwindigkeit und Duplex** | Die Portgeschwindigkeit (100 Mbit/s, 1 Gbit/s, 10 Gbit/s) und der Modus „gleichzeitig in beide Richtungen“. Sie müssen an beiden Kabelenden übereinstimmen |
| **PoE** | Stromversorgung von Geräten (Telefone, Kameras, Access Points) über das Netzwerkkabel |
| **Ping** | Eine einfache Prüfung: Antwortet das Gerät im Netz? |
| **NetBox** | Ein Inventarsystem für Netzwerkgeräte. SwitchMap kann Switches daraus [importieren](/help/netbox) |
