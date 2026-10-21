---
title: Die Oberfläche im Überblick
category: start
order: 2
summary: Wo was ist: Menü, Suche, Ereignisse, Einstellungen und Sprache.
keywords: menü navigation seiten symbole design sprache tastenkürzel
---
# Seitenmenü {#menu}

| Symbol | Bereich | Was dort ist |
|---|---|---|
| Server | Switches | Die Liste der Switches mit Erreichbarkeit, Auslastung und Alarmen. Hier werden neue hinzugefügt. |
| Diagramm | Topologie | Ein Plan der Verbindungen zwischen Switches auf Basis von LLDP. |
| Uhr | Änderungsprotokoll | Wer hat wann was geändert; Änderungen rückgängig machen. |
| Datenbank | Daten und Sicherungen | Aufbewahrung des Verlaufs, Sicherungen, Wiederherstellung. |
| Radar | Suche und Import | Netzsuche und NetBox-Import (nur Administratoren). |
| Papierflieger | Benachrichtigungen | Nachrichten per Telegram und E-Mail (nur Administratoren). |
| Lupe | Gerät suchen | Suche nach MAC, IP, Name und Portbeschreibung. |

Unten im Menü: **Hilfe**, der Schalter für helles/dunkles Design, **Einstellungen** (Abfrage und Alarmschwellen) und Ihr Profil.

# Profil und Sprache {#language}

Klicken Sie auf den Kreis mit Ihren Initialen unten im Menü. Dort können Sie das Passwort ändern, die Hilfe öffnen und die **Oberflächensprache** wählen. „Wie im System“ nutzt die Sprache des Browsers, die meist der Sprache des Betriebssystems entspricht.

Änderungsprotokoll, Ereignisse sowie Telegram- und E-Mail-Nachrichten werden in einer gemeinsamen Sprache geschrieben — ein Administrator wählt sie unter **Einstellungen → Sprache**.

# Ereignisse {#events}

Die Glocke in der oberen Leiste zeigt aktuelle Ereignisse: ein Port ist ausgefallen oder wieder aktiv, hohe Auslastung, Portfehler, ein Switch ist nicht erreichbar. Die Zahl an der Glocke ist die Anzahl ungelesener Ereignisse. Ein Klick auf ein Ereignis öffnet den Switch und hebt den Port hervor.

# Tastenkürzel {#keys}

| Tasten | Aktion |
|---|---|
| [[Strg]] + [[K]] oder [[/]] | Gerät suchen |
| [[Esc]] | Fenster oder Menü schließen |
| [[↑]] [[↓]] [[Enter]] | Suchergebnis auswählen |

# Rollen {#roles}

Ein **Administrator** darf alles. Ein **Betrachter** sieht alle Seiten und kann Switches abfragen, aber nichts ändern — die Bearbeiten-Schaltflächen sind für ihn ausgeblendet. Mehr: [Benutzer und Rollen](/help/users).
