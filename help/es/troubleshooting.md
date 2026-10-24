---
title: Solución de problemas
category: problems
order: 1
summary: Un switch no responde, errores de SNMPv3, no hay direcciones MAC, no llegan las notificaciones y más.
keywords: error no funciona sin respuesta timeout snmp v3 contraseña usuario mac sin datos notificaciones no llegan telegram correo errores de puerto lento
---
# Un switch no responde por SNMP {#no-response}

«El switch no respondió» significa que no llegó respuesta en el tiempo previsto. Paso a paso:

1. **¿Hay conexión?** En la página del switch pulse **Comprobar accesibilidad**. «Inaccesible» significa que no responde ni a SNMP ni al ping: el problema está en la red, la alimentación o la dirección. «Solo ping» significa que la red funciona y el problema está en SNMP (pasos 2–5).
2. **¿Está abierto el UDP 161?** Un cortafuegos entre el servidor de SwitchMap y el switch debe dejar pasar UDP 161 hacia el switch y las respuestas de vuelta.
3. **¿Está permitida la dirección del servidor en el switch?** Muchos switches solo responden por SNMP a las direcciones de una lista (ACL). Añada la IP del servidor de SwitchMap.
4. **¿Coinciden las credenciales?** La community y las contraseñas distinguen mayúsculas y minúsculas. Un switch que recibe una community incorrecta simplemente calla, así que el error parece igual que la falta de conectividad.
5. **¿Está SNMP activado?** Vea [Activar SNMP](/help/snmp-vendors).

> **Consejo:** si el ping funciona pero SNMP no, casi siempre son los puntos 3–5. SwitchMap lo indica directamente en el evento «switch inaccesible».

# Un switch desconectado responde al ping {#fake-ping}

El estado **En línea** significa que el switch respondió por SNMP. Si solo responde al ping, el estado es **Solo ping** (amarillo).

Si «Solo ping» aparece en un switch que sin duda está desconectado, quien responde al ping es otro. Lo hacen las VPN y los proxies en modo TUN (Happ, v2rayN, sing-box y otros): interceptan el tráfico y responden al ping por cualquier dirección. Compruébelo desde el servidor: `ping 10.123.45.67`; si una dirección inexistente «responde», esa es la causa. Excluya las redes locales de la VPN (opción «Omitir LAN» o rutas para 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) o desactive el modo TUN.

# Errores de SNMPv3 {#v3}

| Mensaje | Qué revisar |
|---|---|
| usuario SNMPv3 desconocido | El nombre de usuario; si el usuario existe en el switch |
| contraseña o protocolo de autenticación incorrectos | La contraseña y el algoritmo (SHA, SHA-256, MD5) |
| contraseña o protocolo de cifrado incorrectos | La contraseña y el algoritmo de cifrado (AES128, DES) |
| nivel de seguridad no admitido | El grupo del switch tiene otro nivel: por ejemplo, el usuario se creó sin cifrado pero en SwitchMap está activado |

# No hay direcciones MAC ni VLAN {#no-mac}

- Los dispositivos no aparecen hasta que su MAC está en la tabla del switch: el dispositivo debe estar encendido y enviando datos.
- En **Cisco** las direcciones MAC de cada VLAN se guardan por separado; SwitchMap consulta cada VLAN por sí mismo. Con SNMPv3 permita los contextos de VLAN en el switch y deje vacío el campo «Contexto» (vea [Cisco](/help/snmp-vendors#cisco)).
- Los switches sencillos y no gestionables («smart») a veces no ofrecen la tabla MAC por SNMP.

# No hay utilización de puertos {#no-util}

La utilización se calcula con la diferencia de contadores de tráfico entre dos sondeos. Tras el primero aún no existe: espere al segundo o active el [sondeo periódico](/help/monitoring#polling).

# Errores en el puerto {#port-errors}

Si crecen los errores de recepción y transmisión, suele ser un problema físico:

- un cable dañado o demasiado largo, un conector defectuoso, una roseta en mal estado;
- un desajuste de velocidad o dúplex (un extremo en «auto» y el otro fijado a mano);
- un módulo SFP averiado o un conector de fibra sucio.

Empiece por cambiar el latiguillo y revisar la configuración de velocidad en ambos extremos.

# No llegan las notificaciones {#notifications}

1. ¿Está activado el **Sondeo periódico** en **Configuración**? Sin sondeos no hay eventos.
2. ¿Está activado el canal y elegidos los eventos correctos en la página **Notificaciones**?
3. Mire el **Historial de envíos** al final de la página: ahí está la causa del error.
4. **Telegram:** el servidor necesita acceso a `api.telegram.org` (HTTPS). Si no lo tiene, configure un proxy.
5. **Correo:** Gmail, Yandex, Mail.ru y Outlook necesitan una contraseña de aplicación, no la contraseña habitual.
6. Revise los filtros: **Solo puertos importantes**, **Horas de silencio**, **Puerto inestable**.

# No puedo iniciar sesión {#login}

- Tras 5 intentos fallidos, el inicio de sesión con ese nombre se bloquea durante 5 minutos.
- Una contraseña de administrador olvidada se fija desde la línea de comandos del servidor: vea [Usuarios](/help/users#reset).

# Dónde está el registro del programa {#logs}

Los detalles de los fallos están en el registro del programa: `logs\switchmap.log` en la carpeta de datos (vea [Instalación y configuración](/help/installation#files)). En Linux, además, `journalctl -u switchmap`. Para un registro más detallado, indique `SWITCHMAP_LOG_LEVEL=DEBUG` en el archivo de configuración y reinicie el servicio.
