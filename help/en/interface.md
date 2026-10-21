---
title: Interface overview
category: start
order: 2
summary: Where things are: menu, search, events, settings and language.
keywords: menu navigation pages icons theme language keyboard shortcuts
---
# Side menu {#menu}

| Icon | Section | What is there |
|---|---|---|
| Server | Switches | The list of switches with their availability, utilization and alerts. New switches are added here. |
| Diagram | Topology | A map of links between switches based on LLDP. |
| Clock | Change log | Who changed what and when; reverting changes. |
| Database | Data and backups | History retention, backups, restore. |
| Radar | Discovery and import | Network discovery and NetBox import (administrators only). |
| Paper plane | Notifications | Telegram and email messages (administrators only). |
| Magnifier | Find a device | Search by MAC, IP, name and port description. |

At the bottom of the menu: **Help**, the light/dark theme switch, **Settings** (polling and alert thresholds) and your profile.

# Profile and language {#language}

Click the circle with your initials at the bottom of the menu. There you can change your password, open help and choose the **interface language**. “System default” uses the browser language, which usually matches the language of the computer's operating system.

The change log, events and Telegram/email messages are written in one shared language — an administrator chooses it in **Settings → Language**.

# Events {#events}

The bell in the top bar shows recent events: a port went down or came up, high utilization, port errors, a switch is unreachable. The number on the bell is the unread count. Clicking an event opens the switch and highlights the port.

# Keyboard shortcuts {#keys}

| Keys | Action |
|---|---|
| [[Ctrl]] + [[K]] or [[/]] | Find a device |
| [[Esc]] | Close a window or menu |
| [[↑]] [[↓]] [[Enter]] | Pick a search result |

# Roles {#roles}

An **Administrator** can do everything. A **Viewer** sees all pages and can poll switches but cannot change anything — the edit buttons are hidden for them. More: [Users and roles](/help/users).
