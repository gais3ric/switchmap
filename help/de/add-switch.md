---
title: Switches hinzufügen
category: devices
order: 1
summary: Manuell, per Netzsuche oder aus NetBox; was tun, wenn ein Switch nicht gefunden wird.
keywords: hinzufügen neuer switch suche erkennung scan bereich netz lldp
---
# Manuell {#manual}

1. Klicken Sie auf der Startseite auf **Switch hinzufügen**.
2. Geben Sie die Management-**IP-Adresse** und die SNMP-Einstellungen ein (Version, Community oder v3-Benutzer).
3. Klicken Sie auf **Prüfen und ausfüllen**. Antwortet der Switch, trägt SwitchMap Name, Portanzahl und Modell ein. Wenn nicht, sehen Sie den Grund (z. B. „falsches SNMPv3-Passwort“).
4. Fügen Sie bei Bedarf Patchpanels hinzu und klicken Sie auf **Switch anlegen**.

Sie können einen Switch auch ohne IP-Adresse hinzufügen — als Plan zur Kabeldokumentation. Dann gibt es aber keinen Portstatus, keine Auslastung und keine Gerätesuche.

# Netzsuche {#discovery}

Der Bereich **Suche und Import** (Radarsymbol) prüft viele Adressen auf einmal.

1. Geben Sie unter **Netze und Adressen** an, wo gesucht werden soll — durch Kommas oder Zeilenumbrüche getrennt:
   - ein Netz: `192.168.1.0/24`;
   - ein Bereich: `10.0.0.1-10.0.0.50` oder kürzer `10.0.0.1-50`;
   - einzelne Adressen: `10.0.5.7`.
2. Geben Sie die SNMP-Einstellungen an. Für v2c können Sie mehrere Communitys durch Kommas getrennt angeben — alle werden ausprobiert.
3. **LLDP-Nachbarn folgen**: Gefundene Switches melden die Adressen ihrer Nachbarn, und auch diese werden geprüft. So werden Switches in Netzen gefunden, die Sie nicht angegeben haben.
4. Klicken Sie auf **Suche starten**. Die Suche läuft auf dem Server — Sie können die Seite schließen und später zurückkehren.
5. Wählen Sie in der Ergebnistabelle die gewünschten Geräte aus, passen Sie bei Bedarf die Namen an und klicken Sie auf **Auswahl hinzufügen**.

Eine Suche prüft bis zu 4096 Adressen (ein /20-Netz). Bereits vorhandene Switches werden als „bereits vorhanden“ markiert und nicht doppelt angelegt.

> **Tipp:** Der Filter **Switches / Alle Geräte** — standardmäßig werden nur Geräte angezeigt, die wie Switches aussehen. Drucker, USVs und Server, die ebenfalls per SNMP antworten, sind ausgeblendet.

# Aus NetBox {#netbox}

Sind Ihre Switches bereits in NetBox erfasst, importieren Sie sie mit Namen, IP-Adressen und Portanzahl. Siehe [Import aus NetBox](/help/netbox).

# Ein Switch wird nicht gefunden {#not-found}

- Prüfen Sie, ob der Port **UDP 161** des Switches vom SwitchMap-Server aus erreichbar ist (Firewalls, ACLs am Switch).
- Stellen Sie sicher, dass SNMP am Switch aktiviert und der Zugriff von der Adresse des SwitchMap-Servers erlaubt ist — viele Modelle beantworten nur Anfragen von freigegebenen Adressen.
- Prüfen Sie Community bzw. v3-Zugangsdaten — Groß- und Kleinschreibung zählt.

Mehr: [Fehlerbehebung](/help/troubleshooting).
