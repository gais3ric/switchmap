---
title: Monitoring and alerts
category: monitoring
order: 1
summary: Scheduled polling, port utilization and errors, CPU and temperature, event thresholds, charts.
keywords: polling interval utilization traffic errors cpu memory temperature threshold event chart statistics poe
---
# Periodic polling {#polling}

Open **Settings** (the gear at the bottom of the menu) and turn on **Poll switches via SNMP periodically**. SwitchMap will poll every switch that has an IP address at the chosen interval.

| Interval | When it fits |
|---|---|
| 1–2 minutes | A small network where detailed charts are needed |
| 5 minutes | Almost everyone |
| 10–15 minutes | Hundreds of switches or slow links |

Without periodic polling, data is updated only by the **Poll via SNMP** button on the switch page.

**Port names, descriptions and VLANs** — how often to read data that rarely changes: port names and descriptions, VLANs, LLDP neighbors (for the topology).

| Mode | When to choose |
|---|---|
| Every poll | The network is being built, extended or repaired — changes show up immediately |
| Once an hour | The network is stable — almost half as many requests to the switches, less load on their CPU |

Port status, traffic, errors and MAC addresses are read on every poll in both modes. **Poll via SNMP** on the switch page always reads everything — press it after changing something on a switch instead of waiting an hour.

# What is measured {#metrics}

- **Port status** — link or no link. A change raises a “port down” or “port up” event.
- **Utilization** — traffic rate as a percentage of the port speed. It is calculated from the counter difference between polls, so it appears from the second poll on.
- **Errors** — how many receive and transmit errors accumulated since the last poll.
- **CPU, memory, temperature** — if the switch reports them via SNMP (depends on the vendor).
- **PoE** — per-port power consumption, if the switch supports POWER-ETHERNET-MIB.

# Alert thresholds {#thresholds}

In **Settings → Alert thresholds**:

| Threshold | Event |
|---|---|
| Port utilization, % | Traffic above this percentage of the port speed |
| Port errors between polls | Errors are growing — often a bad cable |
| CPU load, % | The switch CPU is overloaded |
| Temperature, °C | Overheating |

An event is raised when a threshold is exceeded and another one when the value returns to normal. **0** turns a threshold off. If a switch stops responding, a “switch unreachable” event explains whether it still answers ping (then the problem is the SNMP settings) or not (then it is the network or power). If a switch that is definitely disconnected «replies to ping», see [A disconnected switch replies to ping](/help/troubleshooting#fake-ping).

# Charts {#charts}

On the switch page the **Statistics** button opens charts:

- the traffic rate of any port (inbound and outbound);
- the switch's CPU, memory and temperature.

Periods range from 1 hour to 1 year. Long periods use hourly data, so charts render quickly. How much history is kept — see [Data and backups](/help/backups#retention).

# Events {#events}

All events are shown under the bell in the top bar and in the **Alerts** column on the home page. To receive them in Telegram or by email, set up [notifications](/help/notifications).
