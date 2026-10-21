---
title: Añadir switches
category: devices
order: 1
summary: A mano, con búsqueda en la red o desde NetBox; qué hacer si no se encuentra un switch.
keywords: añadir nuevo switch búsqueda descubrimiento escaneo rango red lldp
---
# A mano {#manual}

1. En la página de inicio pulse **Añadir switch**.
2. Indique la **dirección IP** de gestión y la configuración SNMP (versión, community o usuario v3).
3. Pulse **Comprobar y rellenar**. Si el switch responde, SwitchMap rellena su nombre, número de puertos y modelo. Si no, verá el motivo (por ejemplo «contraseña SNMPv3 incorrecta»).
4. Añada paneles de parcheo si hace falta y pulse **Crear switch**.

También puede añadir un switch sin dirección IP, como mapa para documentar el cableado. Pero entonces no habrá estado de puertos, utilización ni búsqueda de dispositivos.

# Búsqueda en la red {#discovery}

La sección **Búsqueda e importación** (icono de radar) comprueba muchas direcciones a la vez.

1. En **Redes y direcciones** indique dónde buscar, separando con comas o saltos de línea:
   - una red: `192.168.1.0/24`;
   - un rango: `10.0.0.1-10.0.0.50` o más corto `10.0.0.1-50`;
   - direcciones sueltas: `10.0.5.7`.
2. Indique la configuración SNMP. En v2c puede poner varias community separadas por comas: se prueban todas.
3. **Seguir vecinos LLDP**: los switches encontrados informan de las direcciones de sus vecinos y también se comprueban. Así se encuentran switches en redes que no indicó.
4. Pulse **Iniciar búsqueda**. La búsqueda se ejecuta en el servidor: puede cerrar la página y volver más tarde.
5. En la tabla de resultados marque los dispositivos que necesita, ajuste los nombres si quiere y pulse **Añadir seleccionados**.

Una búsqueda comprueba hasta 4096 direcciones (una red /20). Los switches ya añadidos se marcan como «ya añadido» y no se duplican.

> **Consejo:** el filtro **Switches / Todos los dispositivos**: por defecto solo se muestran los dispositivos que parecen switches. Las impresoras, SAI y servidores que también responden por SNMP quedan ocultos.

# Desde NetBox {#netbox}

Si sus switches ya están en NetBox, impórtelos con sus nombres, direcciones IP y número de puertos. Vea [Importar desde NetBox](/help/netbox).

# No se encuentra un switch {#not-found}

- Compruebe que el puerto **UDP 161** del switch es accesible desde el servidor de SwitchMap (cortafuegos, ACL en el switch).
- Asegúrese de que SNMP está activado en el switch y de que se permite el acceso desde la dirección del servidor de SwitchMap: muchos modelos solo aceptan peticiones de una lista de direcciones permitidas.
- Revise la community o las credenciales v3: distinguen mayúsculas y minúsculas.

Más información: [Solución de problemas](/help/troubleshooting).
