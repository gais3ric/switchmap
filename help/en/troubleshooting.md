---
title: Troubleshooting
category: problems
order: 1
summary: A switch does not respond, SNMPv3 errors, no MAC addresses, notifications do not arrive and more.
keywords: error not working no response timeout snmp v3 password user mac no data notifications not arriving telegram email port errors slow
---
# A switch does not respond to SNMP {#no-response}

“No response from the switch” means no reply arrived within the allotted time. Step by step:

1. **Is there a connection?** On the switch page press **Check reachability**. «Unreachable» means no reply to either SNMP or ping: the problem is the network, power or address. «Ping only» means the network works and the problem is SNMP (steps 2–5).
2. **Is UDP 161 open?** A firewall between the SwitchMap server and the switch must let UDP 161 through toward the switch and the replies back.
3. **Is the server's address allowed on the switch?** Many switches answer SNMP only to addresses on a list (ACL). Add the SwitchMap server's IP.
4. **Do the credentials match?** The community and passwords are case-sensitive. A switch that receives a wrong community simply stays silent — so the error looks the same as no connectivity.
5. **Is SNMP enabled at all?** See [Enabling SNMP](/help/snmp-vendors).

> **Tip:** if ping works but SNMP does not, it is almost always items 3–5. SwitchMap says so directly in the “switch unreachable” event.

# A disconnected switch replies to ping {#fake-ping}

The **Online** status means the switch replied over SNMP. If it only replies to ping, the status is **Ping only** (yellow).

If «Ping only» shows for a switch that is definitely disconnected, something else is answering the ping. VPNs and proxies in TUN mode (Happ, v2rayN, sing-box and others) do this: they intercept traffic and answer ping for any address. Check from the server: `ping 10.123.45.67` — if a non-existent address «replies», this is the cause. Exclude local networks from the VPN (a «Bypass LAN» setting or routes for 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) or turn off TUN mode.

# SNMPv3 errors {#v3}

| Message | What to check |
|---|---|
| unknown SNMPv3 user | The user name; whether the user exists on the switch |
| wrong authentication password or protocol | The password and algorithm (SHA, SHA-256, MD5) |
| wrong privacy password or protocol | The password and privacy algorithm (AES128, DES) |
| security level not supported | The group on the switch has a different level: for example, the user was created without privacy but privacy is on in SwitchMap |

# No MAC addresses or VLANs {#no-mac}

- Devices do not appear until their MAC addresses are in the switch table: the device must be on and sending data.
- On **Cisco** the MAC addresses of every VLAN are stored separately — SwitchMap queries each VLAN by itself. Over SNMPv3 allow the VLAN contexts on the switch and leave the «Context» field empty (see [Cisco](/help/snmp-vendors#cisco)).
- Simple and unmanaged (“smart”) switches sometimes do not provide the MAC table via SNMP at all.

# No port utilization {#no-util}

Utilization is calculated from the traffic counter difference between two polls. After the first poll it is not there yet — wait for the second one or turn on [periodic polling](/help/monitoring#polling).

# Port errors {#port-errors}

Growing receive and transmit errors usually mean a physical problem:

- a damaged or too long cable, a bad connector, a faulty wall socket;
- a speed or duplex mismatch (one side on “auto”, the other set manually);
- a faulty SFP module or a dirty fiber connector.

Start by replacing the patch cord and checking the speed settings on both ends.

# Notifications do not arrive {#notifications}

1. Is **Periodic polling** turned on in **Settings**? Without polls there are no events.
2. Is the channel enabled and are the right events selected on the **Notifications** page?
3. Look at **Delivery history** at the bottom of the page — the cause of the error is there.
4. **Telegram:** the server needs access to `api.telegram.org` (HTTPS). If there is no access, set a proxy.
5. **Email:** Gmail, Yandex, Mail.ru and Outlook need an app password, not your regular password.
6. Check the filters: **Important ports only**, **Quiet hours**, **Flapping port**.

# Cannot sign in {#login}

- After 5 failed attempts, sign-in for that name is temporarily locked for 5 minutes.
- A forgotten administrator password is set from the server command line — see [Users](/help/users#reset).

# Where to find the program log {#logs}

Details about failures are in the program log: `logs\switchmap.log` in the data folder (see [Installation and configuration](/help/installation#files)). On Linux also `journalctl -u switchmap`. For a more detailed log, set `SWITCHMAP_LOG_LEVEL=DEBUG` in the settings file and restart the service.
