---
title: Data, backups and the change log
category: data
order: 1
summary: How long history is kept, how to make and restore backups, the change log and reverting.
keywords: backup restore retention history log audit revert move database compact
---
# History retention {#retention}

Section **Data and backups** (database icon). Every poll stores traffic, errors and port status. To keep the database from growing forever:

| Data | Default | What happens next |
|---|---|---|
| Detailed history (every poll) | 7 days | Rolled up into hourly values (average and maximum) |
| Hourly history | 365 days | Deleted |
| Events | 90 days | Deleted |

Database maintenance runs automatically every hour. **Run maintenance now** starts it immediately; **compact the database file** frees disk space after old data is deleted.

# Backups {#backups}

- **Daily automatic backup** — once a day; as many backups are kept as set in **Backups to keep** (14 by default), older ones are deleted.
- **Create backup** — manually, for example before big changes.
- A backup is also made automatically: on startup of a new version if the database structure changes, and before restoring another backup.

Each backup can be **downloaded**, **restored** or **deleted**. **Restore from file** uploads a backup downloaded earlier or made on another server.

> **Important:** backups are on the same disk as the database (the `backups` folder in the data folder). Download them regularly or copy the folder to another server — copies next to the database will not survive a disk failure.

The encryption keys (the `switchmap.secret` file) are **not** included in backups — so a backup is safe to store and transfer. But without this file the SNMPv3, email, Telegram and NetBox passwords from the backup will have to be entered again. Keep `switchmap.secret` separately in a safe place.

# Restore {#restore}

Click **Restore** next to the backup you need. The current database is saved to a separate backup first (“before restore”), so a restore can be undone by restoring that backup. Users and their passwords are not rolled back if the backup has none.

# Moving to another server {#move}

1. Stop SwitchMap on the old server.
2. Copy `switches.db` and `switchmap.secret` from the data folder.
3. Install SwitchMap on the new server, stop the service, put the files into its data folder and start the service.

Where the data folder is — see [Installation and configuration](/help/installation#files).

# Change log {#audit}

The **Change log** section (clock icon) shows who changed what and when: switches, connections, settings, users, and also failed sign-in attempts. Entries can be filtered by switch and type.

**Revert** next to a switch change restores the previous values. A deleted switch can be **restored** with its connections and devices.
