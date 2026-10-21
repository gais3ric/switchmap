---
title: Port map and connections
category: devices
order: 4
summary: How to read the switch map, draw connections through patch panels, and mark trunks and VLANs.
keywords: map port color patch panel connection cable trunk sfp rj45 vlan edit pdf export rack
---
# Reading the map {#read}

The switch page shows the **rack view**: the switch itself and its patch panels, port by port as on the front panel.

| What you see | What it means |
|---|---|
| Bright port | There is link — something is connected and powered on |
| Faded port | No link (according to the last poll) |
| Colored bar at the bottom of the port | Port utilization: up to 30%, up to 60%, up to the threshold and above it — colors in the legend above the map |
| Red outline | Utilization above the alert threshold |
| Letter **T** next to the number | The port is marked as a trunk (uplink to another switch) |
| Port with a “tab” at the bottom | SFP (fiber); a regular one is RJ-45 (copper) |
| Colored mark on the port | The port's VLAN (you can assign a color to a VLAN) |

Hover over a port to see a tooltip: interface name, description, speed, utilization, errors and connected devices. The **Port utilization** switch turns the colored bars on and off.

# Connections through patch panels {#connections}

A switch does not know where a cable goes after the patch panel. You know — draw it once:

1. Click **Edit**.
2. If there are no patch panels yet — **Settings → Patch panels → Add patch panel**: name, number of ports, position (above or below the switch).
3. Click a switch port, then a patch panel port.
4. Enter where the line goes (“Room 214, printer”) and the cable color.
5. Click **Save**.

If a cable goes straight to a device without a patch panel, right-click the port → **Assign directly…**

All connections are listed in **Settings → Switch → Port connections**. They can be edited or deleted there.

# Port type and trunk {#trunk}

Right-click a switch port:

- **RJ-45 (copper)** or **SFP (fiber)** — only how it looks on the map;
- **Mark as trunk** — for a port that connects another switch. Trunks count as important ports for [notifications](/help/notifications), and device search understands that a whole network is behind such a port, not one device.

# VLAN {#vlan}

After an SNMP poll, **Settings → VLAN** lists the switch's VLANs. Click the color square next to a VLAN and choose a color — the marks of that VLAN's ports on the map take this color. The VLAN filter fades all other ports. Each port's VLAN is also shown in the **Ports** table.

# Devices on ports {#devices}

After you click **Poll via SNMP**, the **Ports and devices (SNMP)** panel opens on the right: all interfaces and the MAC addresses the switch sees on each port, with IP and name when they could be determined. Click a port in the panel to expand its device list. **Assign to port** pins a device to a port with your note — it will be found by [search](/help/search) even when it is switched off.

# Export {#export}

The **Export** menu:

- **Excel** — ports, connections, patch panels and devices on separate sheets;
- **PDF datasheet** — a connection map to print or hand over to a contractor;
- **CSV** — individual tables for your own reports;
- **Change history** — all edits of this switch in the [log](/help/backups#audit).
