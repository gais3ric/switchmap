---
title: Ein Gerät im Netz finden
category: monitoring
order: 4
summary: Wie man nach MAC, IP oder Name herausfindet, an welchem Port ein Gerät hängt.
keywords: suche finden gerät mac ip name hostname port beschreibung uplink trunk wo angeschlossen
---
Das Suchfeld in der oberen Leiste (oder [[Strg]] + [[K]]) durchsucht alle Switches gleichzeitig:

- **MAC-Adresse** — vollständig oder teilweise, mit oder ohne Doppelpunkte: `00:1a:2b`, `001a2b3c`;
- **IP-Adresse** oder ein Teil davon;
- **Gerätename** (sofern per DNS auflösbar);
- **Portbeschreibung** am Switch (ifAlias) und Verbindungsbeschriftungen im Plan.

Das Ergebnis ist ein Switch und ein Port. Ein Klick öffnet den Switch und hebt den Port im Plan hervor.

# Woher die Daten kommen {#data}

Ein Switch merkt sich, welche MAC-Adressen er an jedem Port sieht. SwitchMap liest diese Tabellen bei jeder SNMP-Abfrage. Deshalb:

- wird ein Gerät nur gefunden, wenn es bei der letzten Abfrage im Netz war;
- aktualisieren sich die Daten bei aktivierter regelmäßiger Abfrage von selbst.
- **IP-Adresse und Name** sind nur bekannt, wenn der Switch die IP des Geräts kennt. Ein gewöhnlicher Switch (Layer 2) kennt nur die IPs der Geräte, die mit dem Switch selbst kommuniziert haben – am zuverlässigsten ist daher die Suche nach der **MAC-Adresse**.

Ein Gerät, das immer gefunden werden soll (auch ausgeschaltet), lässt sich manuell **einem Port zuweisen** — siehe [Portplan](/help/port-map#devices).

# Die Markierung Uplink {#uplink}

Wird ein Gerät an einem Port gesehen, an dem auch viele andere MAC-Adressen auftauchen, oder ist der Port als Trunk markiert, ist es höchstwahrscheinlich nicht der Port, an dem das Gerät hängt, sondern eine Verbindung zu einem anderen Switch. Solche Ergebnisse sind als **uplink** markiert und stehen weiter unten. Suchen Sie dieselbe MAC am nächsten Switch — dort ist der tatsächliche Port.
