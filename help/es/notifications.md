---
title: Notificaciones por Telegram y correo
category: monitoring
order: 2
summary: Cómo crear un bot, encontrar un chat, configurar el correo y no ahogarse en mensajes.
keywords: notificaciones alertas telegram bot botfather chat grupo correo smtp gmail yandex contraseña de aplicación horas de silencio puerto inestable
---
Las notificaciones informan de los mismos eventos que ve en la campana: un switch inaccesible, un puerto caído, utilización alta, errores, sobrecalentamiento. Se configuran en la página **Notificaciones** (icono de avión de papel, solo administradores).

> **Importante:** los eventos solo aparecen cuando se consultan los switches. Active el **Sondeo periódico** en **Configuración**; si no, no habrá nada que notificar.

# Telegram {#telegram}

1. En Telegram abra **@BotFather**, envíe `/newbot` y elija un nombre para el bot. BotFather responde con un **token** del tipo `123456789:AAH…`: péguelo en **Token del bot**.
2. Envíe cualquier mensaje a su bot (por ejemplo `/start`). Para un grupo: añada el bot al grupo y escriba algo allí.
3. Pulse **Buscar chats** y añada el chat que necesite. También puede indicar un ID de chat a mano: los de grupo empiezan por un signo menos.
4. Active el canal, elija los eventos y pulse **Guardar**. **Enviar un mensaje de prueba** comprueba que todo funciona.

El servidor de SwitchMap necesita acceso HTTPS a `api.telegram.org`. Si sale a Internet a través de un proxy, indíquelo en **Proxy HTTP** (`http://proxy:3128` o `http://usuario:contraseña@proxy:3128`).

# Correo {#email}

1. Pulse el botón de su servicio de correo: se rellenan el servidor, el puerto y el cifrado. Para un servidor corporativo, indíquelos usted.
2. **Usuario**: normalmente la dirección de correo. **Contraseña de aplicación**: vea más abajo.
3. **Destinatarios**: una o varias direcciones separadas por comas.
4. Pulse **Enviar un correo de prueba** y luego **Guardar**.

| Puerto | Cifrado |
|---|---|
| 465 | SSL |
| 587 | STARTTLS |
| 25 | Ninguno (solo servidores internos) |

> **Importante:** Gmail, Yandex, Mail.ru y Outlook no aceptan la contraseña habitual del correo. Cree una **contraseña de aplicación** en la configuración de seguridad del buzón y úsela.

# Para no recibir demasiados mensajes {#filters}

| Ajuste | Qué hace |
|---|---|
| Elección de eventos | Por ejemplo, solo «switch inaccesible» y «puerto caído» |
| Avisos de recuperación | Si se avisa de «puerto activo», «de nuevo accesible» |
| Solo puertos importantes | Solo puertos con descripción en el switch, conexión en el mapa o troncal: sin los ordenadores de los usuarios |
| Horas de silencio | De noche solo se envían los eventos críticos |
| Puerto inestable | Un puerto que cae y se levanta muchas veces en una hora genera un solo aviso en lugar de decenas de mensajes |

Varios eventos de un mismo sondeo llegan en un solo mensaje. Si la red o Telegram no estaban disponibles, los mensajes se envían más tarde: SwitchMap sigue reintentando. Los eventos antiguos (más de un día) no se envían con retraso: están en el registro de eventos.

# Historial de envíos {#log}

Al final de la página: los últimos mensajes enviados y los errores. La causa del error se explica con palabras sencillas: «Telegram rechazó el token», «el servidor rechazó el usuario o la contraseña», etc.
