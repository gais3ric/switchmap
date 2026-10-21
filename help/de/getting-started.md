---
title: Erste Schritte
category: start
order: 1
summary: Was SwitchMap kann und wie Sie Ihre Switches in 10 Minuten sehen.
keywords: start schnellstart einführung überblick
---
SwitchMap zeigt die Switches Ihres Netzes als übersichtlichen Plan: welche Ports belegt sind, wohin jedes Kabel führt, welches Gerät wo angeschlossen ist und ob ein Port überlastet ist. Die Daten kommen per SNMP direkt von den Switches — auf ihnen muss nichts installiert werden, nur SNMP aktiviert sein.

# Was Sie brauchen {#requirements}

- Einen Rechner oder Server mit SwitchMap, der die Switches im Netz erreicht (UDP-Port 161).
- SNMP auf den Switches mit Nur-Lese-Zugriff. Wie das bei verschiedenen Modellen geht: [SNMP auf Switches aktivieren](/help/snmp-vendors).
- Die Management-IP-Adressen der Switches. Sind es viele oder kennen Sie nicht alle, findet SwitchMap sie selbst.

# Schritt 1. Switches hinzufügen {#add}

Es gibt zwei Wege:

1. **Einzeln.** Klicken Sie auf der Startseite auf **Switch hinzufügen**, geben Sie IP-Adresse und SNMP-Einstellungen ein und klicken Sie auf **Prüfen und ausfüllen** — Name, Portanzahl und Modell werden automatisch eingetragen.
2. **Alle auf einmal.** Klicken Sie auf **Im Netz suchen** und geben Sie ein Netz an (z. B. `192.168.1.0/24`) — SwitchMap prüft jede Adresse und listet die gefundenen Switches auf. Wählen Sie die gewünschten aus und klicken Sie auf **Auswahl hinzufügen**.

Wenn Sie NetBox nutzen, können Sie Switches daraus importieren — siehe [Import aus NetBox](/help/netbox).

# Schritt 2. Switch abfragen {#poll}

Öffnen Sie einen Switch und klicken Sie auf **Per SNMP abfragen**. Nach wenigen Sekunden zeigt der Plan den Portstatus: helle Ports haben Link, blasse nicht. Die Tabelle **Ports** zeigt Geschwindigkeit, Auslastung, Fehler und VLAN jedes Ports.

Damit die Daten sich selbst aktualisieren, öffnen Sie die **Einstellungen** (Zahnrad unten links) und aktivieren die **Regelmäßige Abfrage**. Fünf Minuten genügen fast allen.

# Schritt 3. Verbindungen zeichnen {#connections}

Der Plan zeigt auch, was der Switch selbst nicht weiß: welcher Port über ein Patchpanel wohin führt. Klicken Sie auf **Bearbeiten**, fügen Sie ein Patchpanel hinzu, klicken Sie dann auf einen Switch-Port und einen Patchpanel-Port und beschriften Sie die Verbindung („Buchhaltung, Raum 214“). Mehr: [Portplan und Verbindungen](/help/port-map).

# Wie geht es weiter {#next}

- [Gerät suchen](/help/search) nach MAC, IP oder Name — sehen Sie, an welchem Port es hängt.
- [Benachrichtigungen](/help/notifications) per Telegram oder E-Mail, wenn ein Switch nicht erreichbar ist oder ein Port ausfällt.
- [Topologie](/help/topology) — ein Plan der Verbindungen zwischen Switches auf Basis von LLDP.
- [Benutzer](/help/users) — geben Sie Kollegen reinen Lesezugriff.

> **Tipp:** Jedes komplexe Feld hat ein **?**-Symbol — fahren Sie mit der Maus darüber, um eine kurze Erklärung zu sehen. Jede Seite hat oben rechts eine Hilfe-Schaltfläche für diese Seite.
