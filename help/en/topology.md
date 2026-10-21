---
title: Network topology
category: monitoring
order: 3
summary: A map of links between switches based on LLDP: how to enable it and how to read it.
keywords: topology map network diagram lldp neighbors cdp links graph
---
The **Topology** page draws which switch is connected to which and through which ports. The data comes from **LLDP** — a protocol neighboring devices use to tell each other about themselves.

# What you need {#requirements}

1. Enable LLDP on the switches — commands for different vendors are in [Enabling SNMP](/help/snmp-vendors). Many models have it on by default.
2. The switches must be added to SwitchMap with an IP address and SNMP access.

# Reading the map {#read}

The legend is in the corner of the map:

| Mark | What it is |
|---|---|
| Blue bar | A switch in SwitchMap; the dot shows whether it is reachable |
| Light blue bar | A server or a device assigned to a port |
| Orange bar | An unknown LLDP neighbor — a device not in SwitchMap (access point, IP phone, another switch) |
| Solid line | A physical link from LLDP |
| Dashed line | A device assigned to a port manually |

Hover over a line to see the ports on both ends.

Drag the map with the mouse, zoom with the wheel, and the **Fit** button brings the whole map back on screen. Clicking a switch opens a card with an **Open switch** button.

> **Tip:** with **Follow LLDP neighbors** turned on in [network discovery](/help/add-switch#discovery), SwitchMap finds the switches that appear on this map as neighbors by itself.

# If there are no links {#empty}

- LLDP is disabled on the switch or on individual ports.
- The switch does not provide LLDP-MIB via SNMP (this happens with simple models).
- Some Cisco devices use only CDP by default — enable LLDP with `lldp run`.
