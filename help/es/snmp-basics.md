---
title: Qué es SNMP
category: devices
order: 2
summary: Explicación sencilla: versiones v2c y v3, community, usuarios y contraseñas, seguridad.
keywords: snmp v2c v3 community usuario autenticación cifrado sha aes md5 des contexto seguridad udp 161
---
**SNMP** (Simple Network Management Protocol) es la forma estándar de preguntar a un dispositivo de red por su estado: la lista de puertos, si están activos, cuánto tráfico ha pasado, qué direcciones MAC se ven, la carga de CPU y la temperatura. Prácticamente todos los switches gestionables lo admiten.

SwitchMap solo **lee** datos: nunca cambia nada en los switches. Basta con acceso de solo lectura.

Las peticiones van al **puerto UDP 161** del switch.

# v2c o v3 {#v2c-or-v3}

| | SNMP v2c | SNMP v3 |
|---|---|---|
| Cómo se comprueba el acceso | Con una contraseña compartida: la **community** | Usuario y contraseña |
| Cifrado de datos | Ninguno: todo viaja sin cifrar | Sí (AES, DES) |
| Configuración | Una línea en el switch | Unas pocas líneas |
| Cuándo elegirlo | Una red de gestión aislada | En todos los demás casos |

> **Importante:** todo el mundo conoce la community `public`. Si usa v2c, defina una community propia y robusta y limite el acceso SNMP a la dirección del servidor de SwitchMap.

# Community {#community}

Una community es solo una cadena que el switch compara con la que recibe. Para leer se suele crear una community con derechos **RO** (solo lectura). En SwitchMap se escribe en el campo **Community**. En la búsqueda en la red puede indicar varias separadas por comas.

# SNMPv3 {#snmpv3}

En v3 se crea en el switch un **usuario** con dos contraseñas:

- **Autenticación** (SHA, SHA-256 y otros, el antiguo MD5): demuestra que la petición viene de usted y no se alteró por el camino.
- **Cifrado** (AES128 y otros, el antiguo DES): oculta el contenido de las respuestas.

Niveles de seguridad:

| Nivel | Autenticación | Cifrado |
|---|---|---|
| noAuthNoPriv | no | no |
| authNoPriv | sí | no |
| authPriv | sí | sí: recomendado |

En SwitchMap indique el mismo **algoritmo** y las mismas **contraseñas** que en el switch. Las contraseñas deben tener al menos 8 caracteres (lo exige el estándar).

El **contexto** suele dejarse vacío. En los switches Cisco, SwitchMap lee por sí mismo los datos de cada VLAN mediante los contextos `vlan-N`; hay que permitirlos en el switch (vea [Cisco](/help/snmp-vendors#cisco)). Si indica un contexto manualmente, solo se leerá ese.

Las contraseñas SNMPv3 se guardan cifradas en la base de datos de SwitchMap, y la clave de cifrado está en un archivo aparte, `switchmap.secret`.

# Qué lee SwitchMap {#what}

| Datos | Origen (MIB) |
|---|---|
| Nombre, descripción, ubicación | SNMPv2-MIB (system) |
| Puertos, su estado, velocidad, contadores de tráfico y errores | IF-MIB |
| Descripciones de puertos (ifAlias) | IF-MIB |
| Direcciones MAC en los puertos | BRIDGE-MIB, Q-BRIDGE-MIB; en Cisco, por cada VLAN |
| VLAN de los puertos | Q-BRIDGE-MIB; en Cisco, CISCO-VLAN-MEMBERSHIP-MIB y CISCO-VTP-MIB |
| Vecinos | LLDP-MIB |
| CPU, memoria, temperatura | varios: depende del fabricante |
| PoE | POWER-ETHERNET-MIB |

Si faltan algunos datos, el switch no los ofrece por SNMP o necesitan otro contexto. Todo lo demás sigue funcionando.
