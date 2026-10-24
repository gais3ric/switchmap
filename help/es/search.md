---
title: Buscar un dispositivo en la red
category: monitoring
order: 4
summary: Cómo saber en qué puerto está conectado un dispositivo por MAC, IP o nombre.
keywords: buscar encontrar dispositivo mac ip nombre hostname puerto descripción uplink troncal dónde está conectado
---
El cuadro de búsqueda de la barra superior (o [[Ctrl]] + [[K]]) busca en todos los switches a la vez:

- **dirección MAC**, completa o parcial, con o sin dos puntos: `00:1a:2b`, `001a2b3c`;
- **dirección IP** o parte de ella;
- **nombre del dispositivo** (cuando se pudo resolver por DNS);
- **descripción del puerto** en el switch (ifAlias) y etiquetas de conexión del mapa.

El resultado es un switch y un puerto. Al hacer clic se abre el switch y se resalta el puerto en el mapa.

# De dónde salen los datos {#data}

Un switch recuerda las direcciones MAC de los dispositivos que ve en cada puerto. SwitchMap lee esas tablas en cada sondeo SNMP. Por eso:

- un dispositivo solo se encuentra si estaba en la red durante el último sondeo;
- con el sondeo periódico activado, los datos se actualizan solos.
- La **dirección IP y el nombre** solo se conocen si el switch conoce la IP del dispositivo. Un switch normal (de capa 2) solo conoce las IP de los equipos que se comunicaron con el propio switch, por lo que lo más fiable es buscar por **dirección MAC**.

Un dispositivo que debe encontrarse siempre (incluso apagado) se puede **asignar a un puerto** a mano: vea [Mapa de puertos](/help/port-map#devices).

# La marca uplink {#uplink}

Si un dispositivo aparece en un puerto donde también se ven muchas otras direcciones MAC, o el puerto está marcado como troncal, lo más probable es que no sea el puerto donde está conectado sino un enlace a otro switch. Esos resultados se marcan como **uplink** y se muestran más abajo. Busque la misma MAC en el siguiente switch: allí estará el puerto real.
