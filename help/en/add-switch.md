---
title: Adding switches
category: devices
order: 1
summary: Manually, by network discovery or from NetBox; what to do if a switch is not found.
keywords: add new switch discovery scan range network lldp
---
# Manually {#manual}

1. On the home page click **Add switch**.
2. Enter the management **IP address** and the SNMP settings (version, community or v3 user).
3. Click **Check and fill in**. If the switch responds, SwitchMap fills in its name, number of ports and model. If not, you will see why (for example “wrong SNMPv3 password”).
4. Add patch panels if needed and click **Create switch**.

You can also add a switch without an IP address — as a map for cable records. But then there is no port status, utilization or device search.

# Network discovery {#discovery}

The **Discovery and import** section (radar icon) checks many addresses at once.

1. In **Networks and addresses** enter where to look. Separate entries with commas or new lines:
   - a network: `192.168.1.0/24`;
   - a range: `10.0.0.1-10.0.0.50` or shorter `10.0.0.1-50`;
   - single addresses: `10.0.5.7`.
2. Enter the SNMP settings. For v2c you can list several communities separated by commas — all of them are tried.
3. **Follow LLDP neighbors**: discovered switches report their neighbors' addresses, and those are checked too. This finds switches in networks you did not list.
4. Click **Start scan**. The scan runs on the server — you can close the page and come back later.
5. In the results table select the devices you need, adjust the names if you want, and click **Add selected**.

One scan checks up to 4096 addresses (a /20 network). Switches that are already added are marked “already added” and are not duplicated.

> **Tip:** the **Switches / All devices** filter — by default only devices that look like switches are shown. Printers, UPSes and servers that also respond to SNMP are hidden.

# From NetBox {#netbox}

If your switches are already in NetBox, import them with their names, IP addresses and number of ports. See [Import from NetBox](/help/netbox).

# A switch is not found {#not-found}

- Check that the switch's **UDP 161** port is reachable from the SwitchMap server (firewalls, ACLs on the switch).
- Make sure SNMP is enabled on the switch and access is allowed from the SwitchMap server's address — many models accept requests only from a list of allowed addresses.
- Check the community or v3 credentials — they are case-sensitive.

More: [Troubleshooting](/help/troubleshooting).
