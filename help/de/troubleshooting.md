---
title: Fehlerbehebung
category: problems
order: 1
summary: Ein Switch antwortet nicht, SNMPv3-Fehler, keine MAC-Adressen, Benachrichtigungen kommen nicht an und mehr.
keywords: fehler funktioniert nicht keine antwort timeout snmp v3 passwort benutzer mac keine daten benachrichtigungen kommen nicht an telegram e-mail portfehler langsam
---
# Ein Switch antwortet nicht per SNMP {#no-response}

„Keine Antwort vom Switch“ bedeutet, dass innerhalb der vorgesehenen Zeit keine Antwort kam. Schritt für Schritt:

1. **Besteht eine Verbindung?** Klicken Sie auf der Switch-Seite auf **Erreichbarkeit prüfen**. „Nicht erreichbar“ heißt: keine Antwort per SNMP und auf Ping – das Problem liegt im Netz, an der Stromversorgung oder an der Adresse. „Nur Ping“ heißt: Das Netz funktioniert, das Problem liegt bei SNMP (Schritte 2–5).
2. **Ist UDP 161 offen?** Eine Firewall zwischen SwitchMap-Server und Switch muss UDP 161 zum Switch und die Antworten zurück durchlassen.
3. **Ist die Serveradresse am Switch erlaubt?** Viele Switches antworten per SNMP nur Adressen aus einer Liste (ACL). Tragen Sie die IP des SwitchMap-Servers ein.
4. **Stimmen die Zugangsdaten?** Community und Passwörter unterscheiden Groß- und Kleinschreibung. Ein Switch, der eine falsche Community erhält, schweigt einfach — der Fehler sieht also aus wie fehlende Verbindung.
5. **Ist SNMP überhaupt aktiviert?** Siehe [SNMP aktivieren](/help/snmp-vendors).

> **Tipp:** Funktioniert Ping, SNMP aber nicht, sind es fast immer die Punkte 3–5. SwitchMap sagt das direkt im Ereignis „Switch nicht erreichbar“.

# Ein getrennter Switch antwortet auf Ping {#fake-ping}

Der Status **Online** bedeutet, dass der Switch per SNMP geantwortet hat. Antwortet er nur auf Ping, lautet der Status **Nur Ping** (gelb).

Zeigt ein sicher getrennter Switch „Nur Ping“, antwortet jemand anderes auf den Ping. Das tun VPNs und Proxys im TUN-Modus (Happ, v2rayN, sing-box und andere): Sie fangen den Datenverkehr ab und beantworten Ping für jede Adresse. Prüfen Sie vom Server aus: `ping 10.123.45.67` – „antwortet“ eine nicht existierende Adresse, ist das die Ursache. Nehmen Sie lokale Netze vom VPN aus (Einstellung „LAN umgehen“ oder Routen für 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) oder schalten Sie den TUN-Modus aus.

# SNMPv3-Fehler {#v3}

| Meldung | Was prüfen |
|---|---|
| unbekannter SNMPv3-Benutzer | Den Benutzernamen; ob der Benutzer am Switch existiert |
| falsches Authentifizierungspasswort oder -protokoll | Passwort und Algorithmus (SHA, SHA-256, MD5) |
| falsches Verschlüsselungspasswort oder -protokoll | Passwort und Verschlüsselungsalgorithmus (AES128, DES) |
| Sicherheitsstufe nicht unterstützt | Die Gruppe am Switch hat eine andere Stufe: z. B. wurde der Benutzer ohne Verschlüsselung angelegt, in SwitchMap ist sie aber aktiviert |

# Keine MAC-Adressen oder VLANs {#no-mac}

- Geräte erscheinen erst, wenn ihre MAC-Adressen in der Tabelle des Switches stehen: Das Gerät muss eingeschaltet sein und Daten senden.
- Bei **Cisco** werden die MAC-Adressen jedes VLANs getrennt gespeichert – SwitchMap fragt jedes VLAN selbst ab. Bei SNMPv3 erlauben Sie auf dem Switch die VLAN-Kontexte und lassen das Feld „Kontext“ leer (siehe [Cisco](/help/snmp-vendors#cisco)).
- Einfache und nicht verwaltbare („Smart“-)Switches liefern die MAC-Tabelle manchmal gar nicht per SNMP.

# Keine Portauslastung {#no-util}

Die Auslastung wird aus der Differenz der Verkehrszähler zwischen zwei Abfragen berechnet. Nach der ersten Abfrage gibt es sie noch nicht — warten Sie die zweite ab oder aktivieren Sie die [regelmäßige Abfrage](/help/monitoring#polling).

# Portfehler {#port-errors}

Steigende Empfangs- und Sendefehler deuten meist auf ein physisches Problem hin:

- ein beschädigtes oder zu langes Kabel, ein schlechter Stecker, eine defekte Netzwerkdose;
- eine Abweichung bei Geschwindigkeit oder Duplex (eine Seite auf „auto“, die andere fest eingestellt);
- ein defektes SFP-Modul oder ein verschmutzter Glasfaserstecker.

Tauschen Sie zuerst das Patchkabel und prüfen Sie die Geschwindigkeitseinstellungen an beiden Enden.

# Benachrichtigungen kommen nicht an {#notifications}

1. Ist die **Regelmäßige Abfrage** in den **Einstellungen** aktiviert? Ohne Abfragen keine Ereignisse.
2. Ist der Kanal aktiviert und sind auf der Seite **Benachrichtigungen** die richtigen Ereignisse gewählt?
3. Sehen Sie sich den **Versandverlauf** unten auf der Seite an — dort steht die Fehlerursache.
4. **Telegram:** Der Server braucht Zugang zu `api.telegram.org` (HTTPS). Fehlt er, richten Sie einen Proxy ein.
5. **E-Mail:** Gmail, Yandex, Mail.ru und Outlook verlangen ein App-Passwort, nicht Ihr normales Passwort.
6. Prüfen Sie die Filter: **Nur wichtige Ports**, **Ruhezeiten**, **Flatternder Port**.

# Anmeldung nicht möglich {#login}

- Nach 5 Fehlversuchen wird die Anmeldung für diesen Namen für 5 Minuten gesperrt.
- Ein vergessenes Administratorpasswort wird über die Kommandozeile des Servers gesetzt — siehe [Benutzer](/help/users#reset).

# Wo das Programmprotokoll liegt {#logs}

Details zu Störungen stehen im Programmprotokoll: `logs\switchmap.log` im Datenordner (siehe [Installation und Konfiguration](/help/installation#files)). Unter Linux zusätzlich `journalctl -u switchmap`. Für ein ausführlicheres Protokoll setzen Sie `SWITCHMAP_LOG_LEVEL=DEBUG` in der Einstellungsdatei und starten den Dienst neu.
