---
title: Getting started
category: start
order: 1
summary: What SwitchMap does and how to see your switches in 10 minutes.
keywords: start quick start introduction overview
---
SwitchMap shows the switches in your network as a clear map: which ports are in use, where every cable goes, which device is connected where, and whether a port is overloaded. The data comes from the switches themselves over SNMP — nothing needs to be installed on them, you only need to enable SNMP.

# What you need {#requirements}

- A computer or server running SwitchMap with network access to the switches (UDP port 161).
- SNMP enabled on the switches with read-only access. How to do it on different models — see [Enabling SNMP on switches](/help/snmp-vendors).
- The management IP addresses of the switches. If there are many, or you do not remember them all, SwitchMap will find them.

# Step 1. Add switches {#add}

There are two ways:

1. **One at a time.** On the home page click **Add switch**, enter the IP address and SNMP settings and click **Check and fill in** — the name, number of ports and model are filled in automatically.
2. **All at once.** Click **Discover**, enter a network (for example `192.168.1.0/24`) — SwitchMap checks every address and lists the switches it finds. Select the ones you need and click **Add selected**.

If you use NetBox, you can import switches from it — see [Import from NetBox](/help/netbox).

# Step 2. Poll the switch {#poll}

Open a switch and click **Poll via SNMP**. In a few seconds the map shows port status: bright ports have link, faded ones do not. The **Ports** table shows the speed, utilization, errors and VLAN of every port.

To keep the data up to date automatically, open **Settings** (the gear icon at the bottom left) and turn on **Periodic polling**. Five minutes is enough for almost everyone.

# Step 3. Draw the connections {#connections}

The map also shows what the switch itself does not know: which port goes where through a patch panel. Click **Edit**, add a patch panel, then click a switch port and a patch panel port and label the connection (“Accounting, room 214”). More: [Port map and connections](/help/port-map).

# What next {#next}

- [Find a device](/help/search) by MAC, IP or name — see which port it is plugged into.
- [Notifications](/help/notifications) in Telegram or by email when a switch is unreachable or a port goes down.
- [Topology](/help/topology) — a map of links between switches based on LLDP.
- [Users](/help/users) — give colleagues view-only access.

> **Tip:** every complex field has a **?** icon — hover over it to see a short explanation. Every page has a help button for that page at the top right.
