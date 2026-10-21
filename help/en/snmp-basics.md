---
title: What is SNMP
category: devices
order: 2
summary: A plain explanation: versions v2c and v3, community, users and passwords, security.
keywords: snmp v2c v3 community user authentication privacy encryption sha aes md5 des context security udp 161
---
**SNMP** (Simple Network Management Protocol) is the standard way to ask a network device about its state: the list of ports, whether they are up, how much traffic has passed, which MAC addresses are seen, CPU load and temperature. Practically all managed switches support it.

SwitchMap only **reads** data — it never changes anything on the switches. Read-only access is enough.

Requests go to the switch's **UDP port 161**.

# v2c or v3 {#v2c-or-v3}

| | SNMP v2c | SNMP v3 |
|---|---|---|
| How access is checked | By a shared password — the **community** | User and password |
| Data encryption | None — everything is sent in clear text | Yes (AES, DES) |
| Setup | One line on the switch | A few lines |
| When to choose | An isolated management network | In all other cases |

> **Important:** everybody knows the community `public`. If you use v2c, set your own strong community and restrict SNMP access to the SwitchMap server address.

# Community {#community}

A community is just a string that the switch compares with the one it receives. For reading, a community with **RO** (read-only) rights is usually created. In SwitchMap it goes into the **Community** field. For network discovery you can list several, separated by commas.

# SNMPv3 {#snmpv3}

In v3 a **user** with two passwords is created on the switch:

- **Authentication** (SHA, SHA-256 and others, the outdated MD5) proves the request came from you and was not modified on the way.
- **Privacy** (AES128 and others, the outdated DES) hides the content of the replies.

Security levels:

| Level | Authentication | Privacy |
|---|---|---|
| noAuthNoPriv | no | no |
| authNoPriv | yes | no |
| authPriv | yes | yes — recommended |

In SwitchMap enter the same **algorithm** and the same **passwords** as on the switch. Passwords must be at least 8 characters (required by the standard).

The **context** is usually left empty. It is needed, for example, on Cisco switches, where the MAC table of a VLAN is read via the `vlan-10` context.

SNMPv3 passwords are stored encrypted in the SwitchMap database, and the encryption key is kept in a separate file, `switchmap.secret`.

# What SwitchMap reads {#what}

| Data | Source (MIB) |
|---|---|
| Name, description, location | SNMPv2-MIB (system) |
| Ports, their status, speed, traffic and error counters | IF-MIB |
| Port descriptions (ifAlias) | IF-MIB |
| MAC addresses on ports | BRIDGE-MIB, Q-BRIDGE-MIB |
| Port VLANs | Q-BRIDGE-MIB |
| Neighbors | LLDP-MIB |
| CPU, memory, temperature | various — depends on the vendor |
| PoE | POWER-ETHERNET-MIB |

If some of the data is missing, the switch does not provide it via SNMP or a different context is needed for it. Everything else still works.
