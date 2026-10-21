---
title: Primeros pasos
category: start
order: 1
summary: Qué hace SwitchMap y cómo ver sus switches en 10 minutos.
keywords: inicio comienzo rápido introducción resumen
---
SwitchMap muestra los switches de su red como un mapa claro: qué puertos están en uso, a dónde va cada cable, qué dispositivo está conectado dónde y si un puerto está sobrecargado. Los datos vienen de los propios switches por SNMP: no hay que instalar nada en ellos, solo activar SNMP.

# Qué necesita {#requirements}

- Un ordenador o servidor con SwitchMap y acceso de red a los switches (puerto UDP 161).
- SNMP activado en los switches con acceso de solo lectura. Cómo hacerlo en distintos modelos: [Activar SNMP en los switches](/help/snmp-vendors).
- Las direcciones IP de gestión de los switches. Si son muchas o no las recuerda todas, SwitchMap las encontrará.

# Paso 1. Añada los switches {#add}

Hay dos formas:

1. **Uno a uno.** En la página de inicio pulse **Añadir switch**, indique la dirección IP y la configuración SNMP y pulse **Comprobar y rellenar**: el nombre, el número de puertos y el modelo se rellenan solos.
2. **Todos a la vez.** Pulse **Buscar en la red**, indique una red (por ejemplo `192.168.1.0/24`): SwitchMap comprueba cada dirección y muestra los switches encontrados. Marque los que necesite y pulse **Añadir seleccionados**.

Si usa NetBox, puede importar los switches desde allí: vea [Importar desde NetBox](/help/netbox).

# Paso 2. Consulte el switch {#poll}

Abra un switch y pulse **Consultar por SNMP**. En unos segundos el mapa muestra el estado de los puertos: los brillantes tienen enlace y los atenuados no. La tabla **Puertos** muestra la velocidad, la utilización, los errores y la VLAN de cada puerto.

Para que los datos se actualicen solos, abra **Configuración** (el engranaje abajo a la izquierda) y active el **Sondeo periódico**. Cinco minutos bastan a casi todo el mundo.

# Paso 3. Dibuje las conexiones {#connections}

El mapa también muestra lo que el switch no sabe: a dónde va cada puerto a través del panel de parcheo. Pulse **Editar**, añada un panel de parcheo, haga clic en un puerto del switch y luego en un puerto del panel y etiquete la conexión («Contabilidad, sala 214»). Más información: [Mapa de puertos y conexiones](/help/port-map).

# Y después {#next}

- [Buscar un dispositivo](/help/search) por MAC, IP o nombre: vea en qué puerto está conectado.
- [Notificaciones](/help/notifications) por Telegram o correo cuando un switch no responde o un puerto cae.
- [Topología](/help/topology): mapa de enlaces entre switches basado en LLDP.
- [Usuarios](/help/users): dé a sus compañeros acceso de solo lectura.

> **Consejo:** cada campo complejo tiene un icono **?**: pase el ratón por encima para ver una breve explicación. Cada página tiene arriba a la derecha un botón de ayuda sobre esa página.
