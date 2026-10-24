---
title: Finding a device in the network
category: monitoring
order: 4
summary: How to find which port a device is plugged into by MAC, IP or name.
keywords: search find device mac ip name hostname port description uplink trunk where connected
---
The search box in the top bar (or [[Ctrl]] + [[K]]) searches all switches at once:

- **MAC address** — whole or partial, with or without colons: `00:1a:2b`, `001a2b3c`;
- **IP address** or part of it;
- **device name** (when it could be resolved via DNS);
- **port description** on the switch (ifAlias) and connection labels on the map.

The result is a switch and a port. Clicking it opens the switch and highlights the port on the map.

# Where the data comes from {#data}

A switch remembers which devices' MAC addresses it sees on each port. SwitchMap reads these tables on every SNMP poll. Therefore:

- a device is found only if it was on the network during the last poll;
- with periodic polling turned on, the data updates by itself.
- An **IP address and name** are known only if the switch knows the device's IP. An ordinary (layer 2) switch only knows the IPs of hosts that talked to the switch itself, so searching by **MAC address** is the most reliable.

A device that should always be found (even when switched off) can be **assigned to a port** manually — see [Port map](/help/port-map#devices).

# The uplink mark {#uplink}

If a device is seen on a port where many other MAC addresses are seen too, or the port is marked as a trunk, it is most likely not the port the device is plugged into but a link to another switch. Such results are marked **uplink** and shown lower. Look for the same MAC on the next switch — the real port will be there.
