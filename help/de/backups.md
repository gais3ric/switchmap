---
title: Daten, Sicherungen und Änderungsprotokoll
category: data
order: 1
summary: Wie lange der Verlauf aufbewahrt wird, Sicherungen erstellen und wiederherstellen, Änderungsprotokoll und Rücknahme.
keywords: sicherung backup wiederherstellen aufbewahrung verlauf protokoll audit rückgängig umzug datenbank komprimieren
---
# Aufbewahrung des Verlaufs {#retention}

Bereich **Daten und Sicherungen** (Datenbanksymbol). Jede Abfrage speichert Verkehr, Fehler und Portstatus. Damit die Datenbank nicht endlos wächst:

| Daten | Standard | Was danach passiert |
|---|---|---|
| Detaillierter Verlauf (jede Abfrage) | 7 Tage | Wird zu Stundenwerten zusammengefasst (Mittel und Maximum) |
| Stündlicher Verlauf | 365 Tage | Wird gelöscht |
| Ereignisse | 90 Tage | Werden gelöscht |

Die Datenbankwartung läuft automatisch stündlich. **Wartung jetzt ausführen** startet sie sofort; **Datenbankdatei komprimieren** gibt nach dem Löschen alter Daten Speicherplatz frei.

# Sicherungen {#backups}

- **Tägliche automatische Sicherung** — einmal täglich; aufbewahrt werden so viele Sicherungen wie unter **Aufzubewahrende Sicherungen** angegeben (standardmäßig 14), ältere werden gelöscht.
- **Sicherung erstellen** — manuell, z. B. vor größeren Änderungen.
- Eine Sicherung entsteht außerdem automatisch: beim Start einer neuen Version, wenn sich die Datenbankstruktur ändert, und vor dem Wiederherstellen einer anderen Sicherung.

Jede Sicherung kann **heruntergeladen**, **wiederhergestellt** oder **gelöscht** werden. **Aus Datei wiederherstellen** lädt eine früher heruntergeladene oder auf einem anderen Server erstellte Sicherung hoch.

> **Wichtig:** Sicherungen liegen auf derselben Platte wie die Datenbank (Ordner `backups` im Datenordner). Laden Sie sie regelmäßig herunter oder kopieren Sie den Ordner auf einen anderen Server — Kopien neben der Datenbank überstehen keinen Plattendefekt.

Die Schlüssel (Datei `switchmap.secret`) sind **nicht** in den Sicherungen enthalten — eine Sicherung lässt sich also gefahrlos aufbewahren und weitergeben. Ohne diese Datei müssen jedoch die SNMPv3-, E-Mail-, Telegram- und NetBox-Passwörter aus der Sicherung neu eingegeben werden. Bewahren Sie `switchmap.secret` getrennt an einem sicheren Ort auf.

# Wiederherstellung {#restore}

Klicken Sie neben der gewünschten Sicherung auf **Wiederherstellen**. Die aktuelle Datenbank wird vorher in eine eigene Sicherung gespeichert („vor der Wiederherstellung“), sodass sich eine Wiederherstellung durch Zurückspielen dieser Sicherung rückgängig machen lässt. Benutzer und ihre Passwörter werden nicht zurückgesetzt, wenn die Sicherung keine enthält.

# Umzug auf einen anderen Server {#move}

1. Stoppen Sie SwitchMap auf dem alten Server.
2. Kopieren Sie `switches.db` und `switchmap.secret` aus dem Datenordner.
3. Installieren Sie SwitchMap auf dem neuen Server, stoppen Sie den Dienst, legen Sie die Dateien in dessen Datenordner und starten Sie den Dienst.

Wo der Datenordner liegt — siehe [Installation und Konfiguration](/help/installation#files).

# Änderungsprotokoll {#audit}

Der Bereich **Änderungsprotokoll** (Uhrsymbol) zeigt, wer wann was geändert hat: Switches, Verbindungen, Einstellungen, Benutzer und auch fehlgeschlagene Anmeldeversuche. Einträge lassen sich nach Switch und Art filtern.

**Rückgängig machen** neben einer Switch-Änderung stellt die vorherigen Werte wieder her. Ein gelöschter Switch lässt sich mit seinen Verbindungen und Geräten **wiederherstellen**.
