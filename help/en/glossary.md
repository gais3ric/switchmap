---
title: Glossary
category: start
order: 3
summary: Plain explanations of the networking terms used in SwitchMap.
keywords: glossary terms dictionary what is vlan trunk uplink mac ip lldp snmp sfp poe patch panel ifalias duplex
---
| Term | What it is |
|---|---|
| **Switch** | A device that computers, phones, access points and other switches plug into with cables. It passes data between them |
| **Port** | A socket on the switch for one cable |
| **Link** | The port is connected and there is a powered device on the other end |
| **Patch panel** | A panel of sockets in the rack where cables from the offices arrive. It is connected to the switch with short cables — patch cords |
| **RJ-45** | The usual copper network connector (twisted pair) |
| **SFP** | A slot for a replaceable module — usually fiber, for longer distances and higher speeds |
| **MAC address** | A unique “serial number” of a network device, such as `00:1A:2B:3C:4D:5E`. A switch remembers which MAC is behind which port |
| **IP address** | The address of a device in the network, such as `192.168.1.25` |
| **VLAN** | A logical “sub-network” inside a switch: ports in different VLANs do not see each other directly. For example VLAN 10 for accounting, VLAN 20 for phones |
| **Trunk** | A port that carries several VLANs at once — usually a link to another switch |
| **Uplink** | A port leading “up” — to another switch or the network core |
| **SNMP** | The protocol SwitchMap uses to ask a switch about its state. See [What is SNMP](/help/snmp-basics) |
| **Community** | The “password” of SNMP v2c |
| **LLDP** | A protocol neighboring devices use to tell each other about themselves. The [topology](/help/topology) is built from it |
| **Port description (ifAlias)** | A port label set in the switch configuration (for example “uplink-core”) |
| **Port utilization** | How much of the port speed is used by traffic, in percent |
| **Port errors** | Data damaged in transmission. Usually a sign of a bad cable or connector |
| **Speed and duplex** | The port speed (100 Mbit/s, 1 Gbit/s, 10 Gbit/s) and the “both directions at once” mode. They must match on both ends of a cable |
| **PoE** | Powering devices (phones, cameras, access points) over the network cable |
| **Ping** | A simple check: does the device answer on the network |
| **NetBox** | A network equipment inventory system. SwitchMap can [import](/help/netbox) switches from it |
