---
title: Portplan und Verbindungen
category: devices
order: 4
summary: Wie man den Switch-Plan liest, Verbindungen über Patchpanels zeichnet und Trunks und VLANs markiert.
keywords: plan port farbe patchpanel verbindung kabel trunk sfp rj45 vlan bearbeiten pdf export rack
---
# Den Plan lesen {#read}

Die Switch-Seite zeigt die **Rackansicht**: den Switch selbst und seine Patchpanels, Port für Port wie an der Frontblende.

| Was Sie sehen | Was es bedeutet |
|---|---|
| Heller Port | Link vorhanden — etwas ist angeschlossen und eingeschaltet |
| Blasser Port | Kein Link (laut letzter Abfrage) |
| Farbiger Balken unten am Port | Portauslastung: bis 30 %, bis 60 %, bis zur Schwelle und darüber — Farben in der Legende über dem Plan |
| Roter Rahmen | Auslastung über der Alarmschwelle |
| Buchstabe **T** neben der Nummer | Der Port ist als Trunk markiert (Uplink zu einem anderen Switch) |
| Port mit „Lasche“ unten | SFP (Glasfaser); ein normaler ist RJ-45 (Kupfer) |
| Farbige Markierung am Port | Das VLAN des Ports (VLANs können Farben erhalten) |

Fahren Sie mit der Maus über einen Port, um einen Tooltip zu sehen: Schnittstellenname, Beschreibung, Geschwindigkeit, Auslastung, Fehler und angeschlossene Geräte. Der Schalter **Portauslastung** blendet die farbigen Balken ein und aus.

# Verbindungen über Patchpanels {#connections}

Ein Switch weiß nicht, wohin ein Kabel nach dem Patchpanel führt. Sie wissen es — zeichnen Sie es einmal:

1. Klicken Sie auf **Bearbeiten**.
2. Gibt es noch keine Patchpanels — **Einstellungen → Patchpanels → Patchpanel hinzufügen**: Name, Portanzahl, Position (über oder unter dem Switch).
3. Klicken Sie auf einen Switch-Port und dann auf einen Patchpanel-Port.
4. Geben Sie an, wohin die Leitung führt („Raum 214, Drucker“), und die Kabelfarbe.
5. Klicken Sie auf **Speichern**.

Führt ein Kabel ohne Patchpanel direkt zu einem Gerät, klicken Sie mit rechts auf den Port → **Direkt zuweisen…**

Alle Verbindungen stehen unter **Einstellungen → Switch → Portverbindungen**. Dort lassen sie sich bearbeiten oder löschen.

# Porttyp und Trunk {#trunk}

Rechtsklick auf einen Switch-Port:

- **RJ-45 (Kupfer)** oder **SFP (Glasfaser)** — nur das Aussehen im Plan;
- **Als Trunk markieren** — für einen Port, an dem ein anderer Switch hängt. Trunks zählen bei [Benachrichtigungen](/help/notifications) als wichtige Ports, und die Gerätesuche versteht, dass hinter einem solchen Port ein ganzes Netz liegt und nicht ein Gerät.

# VLAN {#vlan}

Nach einer SNMP-Abfrage listet **Einstellungen → VLAN** die VLANs des Switches. Klicken Sie auf das Farbfeld neben einem VLAN und wählen Sie eine Farbe — die Markierungen der Ports dieses VLANs im Plan erhalten diese Farbe. Der VLAN-Filter blendet alle anderen Ports blass. Das VLAN jedes Ports steht auch in der Tabelle **Ports**.

# Geräte an den Ports {#devices}

Nach einem Klick auf **Per SNMP abfragen** öffnet sich rechts das Feld **Ports und Geräte (SNMP)**: alle Schnittstellen und die MAC-Adressen, die der Switch an jedem Port sieht, mit IP und Name, sofern ermittelbar. Klicken Sie im Feld auf einen Port, um seine Geräteliste aufzuklappen. **Port zuweisen** heftet ein Gerät mit Ihrer Notiz an einen Port — die [Suche](/help/search) findet es dann auch, wenn es ausgeschaltet ist.

# Export {#export}

Das Menü **Export**:

- **Excel** — Ports, Verbindungen, Patchpanels und Geräte auf getrennten Blättern;
- **PDF-Datenblatt** — ein Verbindungsplan zum Ausdrucken oder für einen Dienstleister;
- **CSV** — einzelne Tabellen für eigene Berichte;
- **Änderungsverlauf** — alle Änderungen an diesem Switch im [Protokoll](/help/backups#audit).
