---
title: Glosario
category: start
order: 3
summary: Explicaciones sencillas de los términos de red que aparecen en SwitchMap.
keywords: glosario términos qué es vlan troncal uplink mac ip lldp snmp sfp poe panel de parcheo ifalias dúplex
---
| Término | Qué es |
|---|---|
| **Switch** | Dispositivo al que se conectan por cable ordenadores, teléfonos, puntos de acceso y otros switches. Transmite datos entre ellos |
| **Puerto** | Una toma del switch para un cable |
| **Enlace** | El puerto está conectado y al otro lado hay un dispositivo encendido |
| **Panel de parcheo** | Un panel de tomas en el rack donde llegan los cables de las oficinas. Se une al switch con cables cortos (latiguillos) |
| **RJ-45** | El conector de red de cobre habitual (par trenzado) |
| **SFP** | Una ranura para un módulo intercambiable, normalmente de fibra, para más distancia y velocidad |
| **Dirección MAC** | El «número de serie» único de un dispositivo de red, como `00:1A:2B:3C:4D:5E`. El switch recuerda qué MAC está detrás de cada puerto |
| **Dirección IP** | La dirección del dispositivo en la red, como `192.168.1.25` |
| **VLAN** | Una «subred» lógica dentro del switch: los puertos de VLAN distintas no se ven directamente. Por ejemplo VLAN 10 para contabilidad y VLAN 20 para teléfonos |
| **Troncal (trunk)** | Un puerto que lleva varias VLAN a la vez, normalmente un enlace a otro switch |
| **Uplink** | Un puerto que va «hacia arriba»: a otro switch o al núcleo de la red |
| **SNMP** | El protocolo con el que SwitchMap pregunta al switch por su estado. Vea [Qué es SNMP](/help/snmp-basics) |
| **Community** | La «contraseña» de SNMP v2c |
| **LLDP** | Un protocolo con el que los dispositivos vecinos se informan entre sí. La [topología](/help/topology) se construye con él |
| **Descripción del puerto (ifAlias)** | Una etiqueta del puerto definida en la configuración del switch (por ejemplo «uplink-core») |
| **Utilización del puerto** | Qué porcentaje de la velocidad del puerto ocupa el tráfico |
| **Errores del puerto** | Datos dañados en la transmisión. Suelen indicar un cable o conector defectuoso |
| **Velocidad y dúplex** | La velocidad del puerto (100 Mbit/s, 1 Gbit/s, 10 Gbit/s) y el modo «en ambos sentidos a la vez». Deben coincidir en los dos extremos del cable |
| **PoE** | Alimentar dispositivos (teléfonos, cámaras, puntos de acceso) por el cable de red |
| **Ping** | Una comprobación simple: ¿responde el dispositivo en la red? |
| **NetBox** | Un sistema de inventario de equipos de red. SwitchMap puede [importar](/help/netbox) switches desde él |
