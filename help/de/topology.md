---
title: Netztopologie
category: monitoring
order: 3
summary: Ein Plan der Verbindungen zwischen Switches auf Basis von LLDP: wie man ihn aktiviert und liest.
keywords: topologie karte netzplan lldp nachbarn cdp verbindungen graph
---
Die Seite **Topologie** zeigt, welcher Switch über welche Ports mit welchem verbunden ist. Die Daten stammen aus **LLDP** — einem Protokoll, mit dem benachbarte Geräte einander über sich informieren.

# Was Sie brauchen {#requirements}

1. LLDP auf den Switches aktivieren — Befehle für verschiedene Hersteller stehen unter [SNMP aktivieren](/help/snmp-vendors). Bei vielen Modellen ist es standardmäßig an.
2. Die Switches müssen in SwitchMap mit IP-Adresse und SNMP-Zugriff angelegt sein.

# Den Plan lesen {#read}

Die Legende steht in einer Ecke des Plans:

| Markierung | Was es ist |
|---|---|
| Blauer Balken | Ein Switch aus SwitchMap; der Punkt zeigt, ob er erreichbar ist |
| Hellblauer Balken | Ein Server oder ein einem Port zugewiesenes Gerät |
| Oranger Balken | Ein unbekannter LLDP-Nachbar — ein Gerät, das nicht in SwitchMap ist (Access Point, IP-Telefon, anderer Switch) |
| Durchgezogene Linie | Eine physische Verbindung laut LLDP |
| Gestrichelte Linie | Ein manuell einem Port zugewiesenes Gerät |

Fahren Sie mit der Maus über eine Linie, um die Ports an beiden Enden zu sehen.

Ziehen Sie den Plan mit der Maus, zoomen Sie mit dem Mausrad, und die Schaltfläche **Einpassen** holt den ganzen Plan zurück auf den Bildschirm. Ein Klick auf einen Switch öffnet eine Karte mit der Schaltfläche **Switch öffnen**.

> **Tipp:** Mit aktiviertem **LLDP-Nachbarn folgen** bei der [Netzsuche](/help/add-switch#discovery) findet SwitchMap die Switches, die auf diesem Plan als Nachbarn auftauchen, selbst.

# Wenn keine Verbindungen erscheinen {#empty}

- LLDP ist am Switch oder an einzelnen Ports deaktiviert.
- Der Switch liefert LLDP-MIB nicht per SNMP (bei einfachen Modellen).
- Manche Cisco-Geräte nutzen standardmäßig nur CDP — aktivieren Sie LLDP mit `lldp run`.
