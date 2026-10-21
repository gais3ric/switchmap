---
title: Benachrichtigungen per Telegram und E-Mail
category: monitoring
order: 2
summary: Wie man einen Bot anlegt, einen Chat findet, E-Mail einrichtet und nicht in Nachrichten versinkt.
keywords: benachrichtigungen alarme telegram bot botfather chat gruppe e-mail smtp gmail yandex app-passwort ruhezeiten flatternder port
---
Benachrichtigungen melden dieselben Ereignisse wie die Glocke: ein Switch ist nicht erreichbar, ein Port ausgefallen, hohe Auslastung, Fehler, Überhitzung. Eingerichtet werden sie auf der Seite **Benachrichtigungen** (Papierflieger-Symbol, nur Administratoren).

> **Wichtig:** Ereignisse entstehen nur bei Abfragen. Aktivieren Sie die **Regelmäßige Abfrage** in den **Einstellungen**, sonst gibt es nichts zu melden.

# Telegram {#telegram}

1. Öffnen Sie in Telegram **@BotFather**, senden Sie `/newbot` und wählen Sie einen Namen für den Bot. BotFather antwortet mit einem **Token** wie `123456789:AAH…` — fügen Sie es unter **Bot-Token** ein.
2. Senden Sie Ihrem Bot eine beliebige Nachricht (z. B. `/start`). Für eine Gruppe: Fügen Sie den Bot der Gruppe hinzu und schreiben Sie dort etwas.
3. Klicken Sie auf **Chats suchen** und fügen Sie den gewünschten Chat hinzu. Eine Chat-ID können Sie auch manuell eingeben: Gruppen-IDs beginnen mit einem Minus.
4. Aktivieren Sie den Kanal, wählen Sie die Ereignisse und klicken Sie auf **Speichern**. **Testnachricht senden** prüft, ob alles funktioniert.

Der SwitchMap-Server braucht HTTPS-Zugang zu `api.telegram.org`. Geht er über einen Proxy ins Internet, tragen Sie diesen unter **HTTP-Proxy** ein (`http://proxy:3128` oder `http://login:passwort@proxy:3128`).

# E-Mail {#email}

1. Klicken Sie auf die Schaltfläche Ihres Maildienstes — Server, Port und Verschlüsselung werden eingetragen. Für einen Firmenserver geben Sie sie selbst ein.
2. **Login** ist meist die E-Mail-Adresse. **App-Passwort** — siehe unten.
3. **Empfänger** — eine oder mehrere Adressen, durch Kommas getrennt.
4. Klicken Sie auf **Test-E-Mail senden**, dann auf **Speichern**.

| Port | Verschlüsselung |
|---|---|
| 465 | SSL |
| 587 | STARTTLS |
| 25 | Keine (nur interne Server) |

> **Wichtig:** Gmail, Yandex, Mail.ru und Outlook akzeptieren nicht Ihr normales Postfach-Passwort. Legen Sie in den Sicherheitseinstellungen des Postfachs ein **App-Passwort** an und verwenden Sie dieses.

# Nicht zu viele Nachrichten {#filters}

| Einstellung | Was sie bewirkt |
|---|---|
| Auswahl der Ereignisse | Z. B. nur „Switch nicht erreichbar“ und „Port ausgefallen“ |
| Wiederherstellungsmeldungen | Ob „Port aktiv“, „wieder erreichbar“ gemeldet wird |
| Nur wichtige Ports | Nur Ports mit Beschreibung am Switch, Verbindung im Plan oder Trunk — ohne Benutzerrechner |
| Ruhezeiten | Nachts kommen nur kritische Ereignisse |
| Flatternder Port | Ein Port, der stündlich oft aus- und angeht, erzeugt eine einzige Warnung statt Dutzender Nachrichten |

Mehrere Ereignisse einer Abfrage kommen in einer Nachricht. Waren Netz oder Telegram nicht erreichbar, werden die Nachrichten später gesendet — SwitchMap versucht es weiter. Alte Ereignisse (älter als ein Tag) werden nicht nachgeschickt — sie stehen im Ereignisprotokoll.

# Versandverlauf {#log}

Unten auf der Seite: die zuletzt gesendeten Nachrichten und Fehler. Die Fehlerursache wird in einfachen Worten erklärt: „Telegram hat das Token abgelehnt“, „der Server hat Login oder Passwort abgelehnt“ usw.
