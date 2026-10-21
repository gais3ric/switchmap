---
title: Benutzer und Rollen
category: admin
order: 1
summary: Administratoren und Betrachter, Passwörter, Sperren und was tun, wenn ein Passwort vergessen wurde.
keywords: benutzer rolle administrator betrachter passwort anmeldung sperren zurücksetzen vergessen sitzung
---
# Rollen {#roles}

| Rolle | Darf |
|---|---|
| **Administrator** | Alles: Switches anlegen und ändern, Einstellungen, Benachrichtigungen, Benutzer, Sicherungen wiederherstellen |
| **Betrachter** | Alle Seiten ansehen, Switches abfragen, Geräte suchen, Erreichbarkeit prüfen. Ändert nichts |

Die Betrachter-Rolle passt für Bereitschaftsdienst, Support und Dienstleister. Die Bearbeiten-Schaltflächen sind für sie ausgeblendet, und der Server prüft die Rechte zusätzlich bei jeder Aktion.

# Benutzer hinzufügen {#add}

Bereich **Benutzer** (Profilmenü → **Benutzer**, nur Administratoren) → **Benutzer hinzufügen**: Name, Rolle, ein Passwort mit mindestens 8 Zeichen. Teilen Sie dem Benutzer das Passwort mit — ändern kann er es selbst im Profilmenü.

# Sperren und Passwörter {#manage}

- **Sperren** — der Benutzer verliert sofort den Zugriff, bleibt aber in der Liste (seine Aktionen im Protokoll bleiben erhalten).
- **Passwort setzen** — ein neues Passwort; alle Sitzungen des Benutzers auf anderen Rechnern werden beendet.
- Der letzte Administrator kann nicht gelöscht, gesperrt oder herabgestuft werden — so gibt es immer einen Weg, sich anzumelden.

Nach 5 fehlgeschlagenen Anmeldeversuchen hintereinander wird die Anmeldung für diesen Namen von dieser Adresse vorübergehend gesperrt. Fehlversuche werden im Änderungsprotokoll erfasst.

# Administratorpasswort vergessen {#reset}

Setzen Sie ein neues Passwort über die Kommandozeile des Servers, auf dem SwitchMap installiert ist:

| System | Befehl |
|---|---|
| Windows (als Administrator) | `& "C:\Program Files\SwitchMap\switchmap.exe" reset-password admin` |
| Linux | `sudo switchmap reset-password admin` |
| Aus dem Quellcode | `python app.py reset-password admin` |

Gibt es keinen Benutzer mit diesem Namen, bietet der Befehl an, einen Administrator anzulegen.

# Sitzungen {#sessions}

Ohne **30 Tage angemeldet bleiben** endet eine Sitzung nach 12 Stunden Inaktivität, mit dieser Option nach 30 Tagen.
