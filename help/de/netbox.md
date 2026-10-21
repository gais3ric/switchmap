---
title: Import aus NetBox
category: devices
order: 5
summary: Verbindung zu NetBox, Geräteauswahl, Zuordnung und Synchronisierung.
keywords: netbox import token api standort rolle tag synchronisierung dcim
---
Sind Ihre Switches in NetBox erfasst, können Sie sie mit Namen, IP-Adressen und Portanzahl in SwitchMap übernehmen. Bereich **Suche und Import → NetBox** (nur Administratoren).

# Verbindung {#token}

1. **NetBox-URL** — z. B. `https://netbox.company.local`.
2. **API-Token** — in NetBox anlegen: Benutzerprofil (oben rechts) → **API Tokens** → **Add a token**. Ein **Nur-Lese**-Token genügt. Beide Token-Formate funktionieren (klassisch und das neuere `nbt_…`).
3. Nutzt NetBox ein selbstsigniertes Zertifikat, deaktivieren Sie **Serverzertifikat prüfen**.
4. Klicken Sie auf **Prüfen und speichern**.

Das Token wird verschlüsselt auf dem SwitchMap-Server gespeichert und nie an den Browser gesendet.

# Import {#import}

1. Wählen Sie Filter: **Standort**, **Rolle** (z. B. „Access switch“), **Tag**. **Nur mit Status „Active“** blendet ausgemusterte und geplante Geräte aus.
2. Klicken Sie auf **Geräte anzeigen**.
3. Wählen Sie die gewünschten aus (neue Geräte mit IP sind vorausgewählt) und klicken Sie auf **Auswahl importieren**.

Die IP-Adresse stammt aus der **Primary IP** des Geräts, die Portanzahl aus seinen physischen Schnittstellen. Geben Sie die SNMP-Einstellungen auf derselben Seite an — sie gelten für alle importierten Switches.

# Zuordnung {#matching}

Ein NetBox-Gerät gilt als bereits vorhanden, wenn übereinstimmt:

1. die Verknüpfung (der Switch wurde früher aus NetBox importiert);
2. oder die IP-Adresse;
3. oder der Name.

Für solche Geräte sehen Sie, was sich ändern wird. **Bei bereits vorhandenen Name und IP aus NetBox aktualisieren** schaltet die Aktualisierung ein. Portplan, Verbindungen und Verlauf bleiben unverändert.

# Synchronisierung {#sync}

Der Block **Verknüpfte Switches**: **Jetzt synchronisieren** aktualisiert Namen und IPs aller verknüpften Switches aus NetBox. **Automatisch stündlich** erledigt das nach Zeitplan. Neue Geräte werden nicht automatisch hinzugefügt — nur über den Import.

Die Seite eines verknüpften Switches hat einen **NetBox**-Link zu seinem NetBox-Eintrag.
