---
title: Installation und Konfiguration
category: admin
order: 2
summary: Installationsprogramme für Windows und Linux, der Dienst, die Einstellungsdatei, Netzzugriff, HTTPS, Updates.
keywords: installieren installationsprogramm dienst windows linux deb rpm ubuntu debian rhel einstellungen switchmap.conf port https caddy proxy zertifikat update protokoll logs
---
# Installation {#install}

Die Installationsprogramme liegen im Bereich **Releases** des SwitchMap-Repositorys. Python muss nicht installiert werden: Es ist im Programm enthalten.

| System | Datei | Installation |
|---|---|---|
| Windows 10/11, Server 2016+ | `SwitchMap-Setup-X.Y.Z.exe` | Als Administrator ausführen |
| Debian 12+, Ubuntu 22.04+ | `switchmap_X.Y.Z-1_amd64.deb` | `sudo apt install ./switchmap_X.Y.Z-1_amd64.deb` |
| RHEL, AlmaLinux, Rocky Linux 9+ | `switchmap-X.Y.Z-1.x86_64.rpm` | `sudo dnf install ./switchmap-X.Y.Z-1.x86_64.rpm` |

Das Windows-Installationsprogramm fragt, von wo SwitchMap geöffnet werden darf — nur von diesem Rechner oder aus dem Netz (dann öffnet es den Port in der Firewall) — und nach der Portnummer.

> **Tipp:** Windows zeigt eventuell die SmartScreen-Warnung „Unbekannter Herausgeber“ — das Installationsprogramm ist nicht mit einem kostenpflichtigen Zertifikat signiert. Klicken Sie auf **Weitere Informationen → Trotzdem ausführen**.

Öffnen Sie nach der Installation `http://localhost:5000` und legen Sie einen Administrator an.

# Dienst {#service}

SwitchMap läuft als Dienst: Es startet mit dem System und nach einem Absturz neu.

| Aktion | Windows (PowerShell als Administrator) | Linux |
|---|---|---|
| Status | `Get-Service SwitchMap` | `systemctl status switchmap` |
| Neu starten | `Restart-Service SwitchMap` | `sudo systemctl restart switchmap` |
| Stoppen | `Stop-Service SwitchMap` | `sudo systemctl stop switchmap` |

Unter Windows läuft der Dienst unter dem eingeschränkten Konto **LocalService**; unter Linux als eigener Benutzer `switchmap`, der nur in seinen Datenordner schreiben darf.

# Dateien {#files}

| | Windows | Linux |
|---|---|---|
| Programm | `C:\Program Files\SwitchMap` | `/opt/switchmap` |
| Einstellungen | `C:\ProgramData\SwitchMap\switchmap.conf` | `/etc/switchmap/switchmap.conf` |
| Datenbank | `C:\ProgramData\SwitchMap\switches.db` | `/var/lib/switchmap/switches.db` |
| Schlüssel | `…\switchmap.secret` | `/var/lib/switchmap/switchmap.secret` |
| Sicherungen | `…\backups` | `/var/lib/switchmap/backups` |
| Programmprotokoll | `…\logs\switchmap.log` | `/var/lib/switchmap/logs/switchmap.log` und `journalctl -u switchmap` |

Der Befehl `switchmap --paths` zeigt die Pfade auf einem bestimmten Server.

# Einstellungen {#config}

Die Datei `switchmap.conf` enthält Zeilen der Form `SCHLÜSSEL=Wert`. Starten Sie den Dienst nach Änderungen neu.

| Schlüssel | Wert |
|---|---|
| `SWITCHMAP_HOST` | `127.0.0.1` — nur dieser Rechner; `0.0.0.0` — aus dem Netz |
| `SWITCHMAP_PORT` | Port der Weboberfläche, standardmäßig `5000` |
| `SWITCHMAP_HTTPS` | `1` — SwitchMap läuft hinter einem HTTPS-Proxy |
| `SWITCHMAP_PROXY` | `1` — Benutzeradresse aus den Proxy-Headern übernehmen |
| `SWITCHMAP_DATA` | Anderer Datenordner |
| `SWITCHMAP_LOG_LEVEL` | Detailgrad des Protokolls: `DEBUG`, `INFO`, `WARNING` |
| `SWITCHMAP_UPDATE_CHECK` | `0`: nie nach neuen Versionen suchen (isoliertes Netz) |

Unter Linux öffnen Sie für den Netzzugriff nach `SWITCHMAP_HOST=0.0.0.0` den Port in der Firewall: `sudo firewall-cmd --permanent --add-port=5000/tcp && sudo firewall-cmd --reload` (RHEL) oder `sudo ufw allow 5000/tcp` (Ubuntu).

# HTTPS {#https}

SwitchMap selbst spricht HTTP. Wird von anderen Rechnern aus zugegriffen, stellen Sie einen HTTPS-Proxy davor — sonst gehen Passwörter im Klartext durchs Netz. Am einfachsten ist **Caddy** (kostenlos, holt und erneuert Zertifikate selbst).

1. Tragen Sie in `switchmap.conf` ein:
   ```
   SWITCHMAP_HOST=127.0.0.1
   SWITCHMAP_HTTPS=1
   SWITCHMAP_PROXY=1
   ```
   und starten Sie SwitchMap neu.
2. Installieren Sie Caddy: unter Debian und Ubuntu `sudo apt install caddy`, auf anderen Systemen nach der Anleitung auf caddyserver.com.
3. Richten Sie das `Caddyfile` ein (unter Linux `/etc/caddy/Caddyfile`):
   ```
   switchmap.company.local {
       tls internal
       reverse_proxy 127.0.0.1:5000
   }
   ```
   Mit `tls internal` stellt Caddy ein eigenes Zertifikat für das interne Netz aus (Browser fragen einmal, ob sie ihm vertrauen sollen). Für eine aus dem Internet erreichbare Domain entfernen Sie diese Zeile — Caddy holt sich selbst ein Let's-Encrypt-Zertifikat.
4. Laden Sie Caddy neu (`sudo systemctl reload caddy`) und öffnen Sie `https://switchmap.company.local`.

Haben Sie bereits nginx oder IIS, richten Sie einen Reverse Proxy auf `http://127.0.0.1:5000` ein, der die Header `X-Forwarded-For` und `X-Forwarded-Proto` weitergibt.

# Update {#update}

Installieren Sie die neue Version mit demselben Installationsprogramm oder Paket über die alte. Daten und Einstellungen bleiben erhalten, und vor einer Änderung der Datenbankstruktur wird automatisch eine Sicherung erstellt. Die Version steht im Profilmenü.

Einmal am Tag prüft SwitchMap auf GitHub, ob eine neue Version erschienen ist, und zeigt Administratoren den Hinweis „Eine neue Version ist verfügbar“ mit einem Link zur Download-Seite. Es lädt und installiert selbst nichts und überträgt keine Informationen über Ihr Netzwerk. Die Prüfung lässt sich unter **Einstellungen → Updates** abschalten oder in einem isolierten Netz mit `SWITCHMAP_UPDATE_CHECK=0` in der Einstellungsdatei ganz verbieten. Für den Zugang über einen Proxy setzen Sie die Umgebungsvariable `HTTPS_PROXY`.

# Deinstallation {#uninstall}

Die Deinstallation berührt die Daten nicht: Datenbank, Schlüssel und Sicherungen bleiben im Datenordner. Löschen Sie ihn manuell, wenn Sie sie nicht mehr brauchen.
