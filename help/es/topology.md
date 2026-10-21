---
title: Topología de la red
category: monitoring
order: 3
summary: Mapa de enlaces entre switches basado en LLDP: cómo activarlo y cómo leerlo.
keywords: topología mapa esquema de red lldp vecinos cdp enlaces grafo
---
La página **Topología** dibuja qué switch está conectado a cuál y por qué puertos. Los datos vienen de **LLDP**, un protocolo con el que los dispositivos vecinos se informan entre sí.

# Qué necesita {#requirements}

1. Active LLDP en los switches: los comandos de cada fabricante están en [Activar SNMP](/help/snmp-vendors). Muchos modelos lo traen activado de serie.
2. Los switches deben estar añadidos en SwitchMap con dirección IP y acceso SNMP.

# Cómo leer el mapa {#read}

La leyenda está en una esquina del mapa:

| Marca | Qué es |
|---|---|
| Barra azul | Un switch de SwitchMap; el punto indica si es accesible |
| Barra azul claro | Un servidor o un dispositivo asignado a un puerto |
| Barra naranja | Un vecino LLDP desconocido: un dispositivo que no está en SwitchMap (punto de acceso, teléfono IP, otro switch) |
| Línea continua | Un enlace físico según LLDP |
| Línea discontinua | Un dispositivo asignado a un puerto a mano |

Pase el ratón por una línea para ver los puertos de ambos extremos.

Arrastre el mapa con el ratón, haga zoom con la rueda, y el botón **Ajustar** vuelve a mostrar el mapa entero. Al hacer clic en un switch se abre una tarjeta con el botón **Abrir switch**.

> **Consejo:** con **Seguir vecinos LLDP** activado en la [búsqueda en la red](/help/add-switch#discovery), SwitchMap encuentra por sí mismo los switches que aparecen en este mapa como vecinos.

# Si no hay enlaces {#empty}

- LLDP está desactivado en el switch o en algunos puertos.
- El switch no ofrece LLDP-MIB por SNMP (ocurre en modelos sencillos).
- Algunos equipos Cisco solo usan CDP por defecto: active LLDP con `lldp run`.
