---
title: Import from NetBox
category: devices
order: 5
summary: Connecting to NetBox, choosing devices, matching and synchronization.
keywords: netbox import token api site role tag sync dcim
---
If your switches are recorded in NetBox, you can bring them into SwitchMap with their names, IP addresses and number of ports. Section **Discovery and import → NetBox** (administrators only).

# Connecting {#token}

1. **NetBox URL** — for example `https://netbox.company.local`.
2. **API token** — create one in NetBox: user profile (top right) → **API Tokens** → **Add a token**. A **read-only** token is enough. Both token formats work (classic and the newer `nbt_…`).
3. If NetBox uses a self-signed certificate, clear **Verify the server certificate**.
4. Click **Check and save**.

The token is stored encrypted on the SwitchMap server and is never sent to the browser.

# Import {#import}

1. Choose filters: **site**, **role** (for example “Access switch”), **tag**. **Only with status “Active”** hides decommissioned and planned devices.
2. Click **Show devices**.
3. Select the ones you need (new devices with an IP are selected by default) and click **Import selected**.

The IP address comes from the device's **Primary IP**, the number of ports from its physical interfaces. Enter the SNMP settings on the same page — they are applied to all imported switches.

# Matching {#matching}

A NetBox device is considered already added if one of these matches:

1. the link (the switch was imported from NetBox before);
2. or the IP address;
3. or the name.

For such devices you can see what will change. **For already added ones, update name and IP from NetBox** turns updating on. The port map, connections and history are not changed.

# Synchronization {#sync}

The **Linked switches** block: **Sync now** updates the names and IPs of all linked switches from NetBox. **Automatically every hour** does it on a schedule. New devices are not added automatically — only through import.

The page of a linked switch has a **NetBox** link to its NetBox record.
