---
title: Telegram and email notifications
category: monitoring
order: 2
summary: How to create a bot, find a chat, set up email and not drown in messages.
keywords: notifications alerts telegram bot botfather chat group email smtp gmail yandex app password quiet hours flapping port
---
Notifications report the same events you see under the bell: a switch is unreachable, a port went down, high utilization, errors, overheating. They are configured on the **Notifications** page (paper plane icon, administrators only).

> **Important:** events only appear when switches are polled. Turn on **Periodic polling** in **Settings**, otherwise there is nothing to report.

# Telegram {#telegram}

1. In Telegram open **@BotFather**, send `/newbot` and choose a name for the bot. BotFather replies with a **token** like `123456789:AAH…` — paste it into **Bot token**.
2. Send any message to your bot (for example `/start`). For a group — add the bot to the group and post something there.
3. Click **Find chats** and add the chat you need. You can also enter a chat ID manually: group IDs start with a minus.
4. Enable the channel, choose the events and click **Save**. **Send a test message** checks that everything works.

The SwitchMap server needs HTTPS access to `api.telegram.org`. If it reaches the internet through a proxy, enter it in **HTTP proxy** (`http://proxy:3128` or `http://login:password@proxy:3128`).

# Email {#email}

1. Click your mail service button — the server, port and encryption are filled in. For a corporate mail server, enter them yourself.
2. **Login** is usually the email address. **App password** — see below.
3. **Recipients** — one or more addresses, comma-separated.
4. Click **Send a test email**, then **Save**.

| Port | Encryption |
|---|---|
| 465 | SSL |
| 587 | STARTTLS |
| 25 | None (internal servers only) |

> **Important:** Gmail, Yandex, Mail.ru and Outlook do not accept your regular mail password. Create an **app password** in your mailbox security settings and use it.

# Avoiding too many messages {#filters}

| Setting | What it does |
|---|---|
| Choice of events | For example, only “switch unreachable” and “port down” |
| Recovery messages | Whether to report “port up”, “reachable again” |
| Important ports only | Only ports with a description on the switch, a connection on the map or a trunk — no user computers |
| Quiet hours | At night only critical events are sent |
| Flapping port | A port that goes down and up many times an hour produces one warning instead of dozens of messages |

Several events from one poll arrive in one message. If the network or Telegram was unavailable, messages are sent later — SwitchMap keeps retrying. Old events (more than a day) are not sent late — they are in the event log.

# Delivery history {#log}

At the bottom of the page — the latest messages sent and errors. The cause of an error is explained in plain words: “Telegram rejected the token”, “the server rejected the login or password” and so on.
