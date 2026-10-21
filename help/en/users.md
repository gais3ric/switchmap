---
title: Users and roles
category: admin
order: 1
summary: Administrators and viewers, passwords, blocking, and what to do if a password is forgotten.
keywords: user role administrator viewer password sign in block reset forgot session
---
# Roles {#roles}

| Role | Can |
|---|---|
| **Administrator** | Everything: add and change switches, settings, notifications, users, restore backups |
| **Viewer** | View all pages, poll switches, search devices, check reachability. Changes nothing |

The viewer role suits on-call staff, support and contractors. Edit buttons are hidden for them, and the server also checks permissions on every action.

# Adding a user {#add}

Section **Users** (profile menu → **Users**, administrators only) → **Add user**: name, role, a password of at least 8 characters. Give the password to the user — they can change it themselves in the profile menu.

# Blocking and passwords {#manage}

- **Block** — the user loses access immediately but stays in the list (their actions in the log are kept).
- **Set password** — a new password; all of the user's sessions on other computers end.
- The last administrator cannot be deleted, blocked or demoted — so there is always a way to sign in.

After 5 failed sign-in attempts in a row, sign-in for that name from that address is temporarily locked. Failed attempts are recorded in the change log.

# Forgot the administrator password {#reset}

Set a new password from the command line on the server where SwitchMap is installed:

| System | Command |
|---|---|
| Windows (as administrator) | `& "C:\Program Files\SwitchMap\switchmap.exe" reset-password admin` |
| Linux | `sudo switchmap reset-password admin` |
| From source | `python app.py reset-password admin` |

If there is no user with that name, the command offers to create an administrator.

# Sessions {#sessions}

Without **Remember me** a session ends after 12 hours of inactivity, with it — after 30 days.
