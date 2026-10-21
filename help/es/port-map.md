---
title: Mapa de puertos y conexiones
category: devices
order: 4
summary: Cómo leer el mapa del switch, dibujar conexiones a través de paneles de parcheo y marcar troncales y VLAN.
keywords: mapa puerto color panel de parcheo conexión cable troncal sfp rj45 vlan editar pdf exportar rack
---
# Cómo leer el mapa {#read}

La página del switch muestra la **vista del rack**: el propio switch y sus paneles de parcheo, puerto a puerto como en el panel frontal.

| Qué ve | Qué significa |
|---|---|
| Puerto brillante | Hay enlace: algo está conectado y encendido |
| Puerto atenuado | Sin enlace (según el último sondeo) |
| Barra de color en la parte inferior del puerto | Utilización: hasta 30 %, hasta 60 %, hasta el umbral y por encima; colores en la leyenda sobre el mapa |
| Borde rojo | Utilización por encima del umbral de alerta |
| Letra **T** junto al número | El puerto está marcado como troncal (uplink a otro switch) |
| Puerto con una «pestaña» abajo | SFP (fibra); uno normal es RJ-45 (cobre) |
| Marca de color en el puerto | La VLAN del puerto (puede asignar un color a cada VLAN) |

Pase el ratón por un puerto para ver una ayuda: nombre de la interfaz, descripción, velocidad, utilización, errores y dispositivos conectados. El interruptor **Utilización de puertos** muestra u oculta las barras de color.

# Conexiones a través de paneles de parcheo {#connections}

El switch no sabe a dónde va un cable después del panel de parcheo. Usted sí: dibújelo una vez.

1. Pulse **Editar**.
2. Si aún no hay paneles: **Configuración → Paneles de parcheo → Añadir panel de parcheo**: nombre, número de puertos, posición (encima o debajo del switch).
3. Haga clic en un puerto del switch y luego en un puerto del panel.
4. Indique a dónde va la línea («Sala 214, impresora») y el color del cable.
5. Pulse **Guardar**.

Si un cable va directamente a un dispositivo sin panel, haga clic derecho en el puerto → **Asignar directamente…**

Todas las conexiones aparecen en **Configuración → Switch → Conexiones de los puertos**. Allí se pueden editar o eliminar.

# Tipo de puerto y troncal {#trunk}

Clic derecho en un puerto del switch:

- **RJ-45 (cobre)** o **SFP (fibra)**: solo cambia el aspecto en el mapa;
- **Marcar como troncal**: para un puerto que conecta otro switch. Los troncales cuentan como puertos importantes en las [notificaciones](/help/notifications), y la búsqueda de dispositivos entiende que detrás hay una red entera y no un dispositivo.

# VLAN {#vlan}

Tras un sondeo SNMP, **Configuración → VLAN** muestra las VLAN del switch. Haga clic en el cuadro de color junto a una VLAN y elija un color: las marcas de los puertos de esa VLAN tomarán ese color en el mapa. El filtro de VLAN atenúa todos los demás puertos. La VLAN de cada puerto también aparece en la tabla **Puertos**.

# Dispositivos en los puertos {#devices}

Al pulsar **Consultar por SNMP** se abre a la derecha el panel **Puertos y dispositivos (SNMP)**: todas las interfaces y las direcciones MAC que el switch ve en cada puerto, con IP y nombre cuando se pueden determinar. Haga clic en un puerto del panel para desplegar su lista de dispositivos. **Asignar al puerto** fija un dispositivo a un puerto con su nota: la [búsqueda](/help/search) lo encontrará aunque esté apagado.

# Exportar {#export}

El menú **Exportar**:

- **Excel**: puertos, conexiones, paneles de parcheo y dispositivos en hojas separadas;
- **Ficha en PDF**: un mapa de conexiones para imprimir o entregar a un instalador;
- **CSV**: tablas sueltas para sus propios informes;
- **Historial de cambios**: todas las modificaciones de este switch en el [registro](/help/backups#audit).
