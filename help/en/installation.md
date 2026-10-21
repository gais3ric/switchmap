---
title: Installation and configuration
category: admin
order: 2
summary: Installers for Windows and Linux, the service, the settings file, network access, HTTPS, updates.
keywords: install installer service windows linux deb rpm ubuntu debian rhel settings switchmap.conf port https caddy proxy certificate update log logs
---
# Installation {#install}

Installers are in the **Releases** section of the SwitchMap repository. You do not need to install Python: it is bundled with the program.

| System | File | How to install |
|---|---|---|
| Windows 10/11, Server 2016+ | `SwitchMap-Setup-X.Y.Z.exe` | Run as administrator |
| Debian 12+, Ubuntu 22.04+ | `switchmap_X.Y.Z-1_amd64.deb` | `sudo apt install ./switchmap_X.Y.Z-1_amd64.deb` |
| RHEL, AlmaLinux, Rocky Linux 9+ | `switchmap-X.Y.Z-1.x86_64.rpm` | `sudo dnf install ./switchmap-X.Y.Z-1.x86_64.rpm` |

The Windows installer asks where SwitchMap may be opened from — only this computer or the network (then it opens the port in the firewall) — and the port number.

> **Tip:** Windows may show a SmartScreen warning “Unknown publisher” — the installer is not signed with a paid certificate. Click **More info → Run anyway**.

After installation open `http://localhost:5000` and create an administrator.

# Service {#service}

SwitchMap runs as a service: it starts with the system and restarts after a crash.

| Action | Windows (PowerShell as administrator) | Linux |
|---|---|---|
| Status | `Get-Service SwitchMap` | `systemctl status switchmap` |
| Restart | `Restart-Service SwitchMap` | `sudo systemctl restart switchmap` |
| Stop | `Stop-Service SwitchMap` | `sudo systemctl stop switchmap` |

On Windows the service runs under the restricted **LocalService** account; on Linux — as a separate `switchmap` user and can write only to its own data folder.

# Files {#files}

| | Windows | Linux |
|---|---|---|
| Program | `C:\Program Files\SwitchMap` | `/opt/switchmap` |
| Settings | `C:\ProgramData\SwitchMap\switchmap.conf` | `/etc/switchmap/switchmap.conf` |
| Database | `C:\ProgramData\SwitchMap\switches.db` | `/var/lib/switchmap/switches.db` |
| Encryption keys | `…\switchmap.secret` | `/var/lib/switchmap/switchmap.secret` |
| Backups | `…\backups` | `/var/lib/switchmap/backups` |
| Program log | `…\logs\switchmap.log` | `/var/lib/switchmap/logs/switchmap.log` and `journalctl -u switchmap` |

The `switchmap --paths` command shows the paths on a particular server.

# Settings {#config}

The `switchmap.conf` file contains lines like `KEY=value`. Restart the service after changing it.

| Key | Value |
|---|---|
| `SWITCHMAP_HOST` | `127.0.0.1` — this computer only; `0.0.0.0` — from the network |
| `SWITCHMAP_PORT` | Web interface port, `5000` by default |
| `SWITCHMAP_HTTPS` | `1` — SwitchMap runs behind an HTTPS proxy |
| `SWITCHMAP_PROXY` | `1` — take the user's address from the proxy headers |
| `SWITCHMAP_DATA` | Another data folder |
| `SWITCHMAP_LOG_LEVEL` | Log detail: `DEBUG`, `INFO`, `WARNING` |
| `SWITCHMAP_UPDATE_CHECK` | `0`: never check for new versions (isolated network) |

On Linux, to allow network access, after `SWITCHMAP_HOST=0.0.0.0` open the port in the firewall: `sudo firewall-cmd --permanent --add-port=5000/tcp && sudo firewall-cmd --reload` (RHEL) or `sudo ufw allow 5000/tcp` (Ubuntu).

# HTTPS {#https}

SwitchMap itself speaks HTTP. If people connect to it from other computers, put an HTTPS proxy in front of it — otherwise passwords travel over the network in clear text. The easiest option is **Caddy** (free, obtains and renews certificates by itself).

1. In `switchmap.conf` set:
   ```
   SWITCHMAP_HOST=127.0.0.1
   SWITCHMAP_HTTPS=1
   SWITCHMAP_PROXY=1
   ```
   and restart SwitchMap.
2. Install Caddy: on Debian and Ubuntu — `sudo apt install caddy`, on other systems — follow the instructions at caddyserver.com.
3. Configure the `Caddyfile` (on Linux — `/etc/caddy/Caddyfile`):
   ```
   switchmap.company.local {
       tls internal
       reverse_proxy 127.0.0.1:5000
   }
   ```
   `tls internal` makes Caddy issue its own certificate for the internal network (browsers ask once to trust it). For a domain reachable from the internet, remove this line — Caddy gets a Let's Encrypt certificate by itself.
4. Restart Caddy (`sudo systemctl reload caddy`) and open `https://switchmap.company.local`.

If you already have nginx or IIS, configure a reverse proxy to `http://127.0.0.1:5000` that passes the `X-Forwarded-For` and `X-Forwarded-Proto` headers.

# Updating {#update}

Install the new version over the old one with the same installer or package. Data and settings are kept, and a backup is made automatically before the database structure changes. The version is shown in the profile menu.

Once a day SwitchMap checks GitHub for a new version and shows administrators an «A new version is available» bar with a link to the download page. It never downloads or installs anything itself, and no information about your network is sent. You can turn the check off in **Settings → Updates**, or forbid it completely on an isolated network with `SWITCHMAP_UPDATE_CHECK=0` in the settings file. To go through a proxy, set the `HTTPS_PROXY` environment variable.

# Uninstalling {#uninstall}

Uninstalling the program does not touch the data: the database, keys and backups stay in the data folder. Delete it manually if you no longer need them.
