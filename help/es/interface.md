---
title: Recorrido por la interfaz
category: start
order: 2
summary: Dónde está cada cosa: menú, búsqueda, eventos, configuración e idioma.
keywords: menú navegación páginas iconos tema idioma atajos de teclado
---
# Menú lateral {#menu}

| Icono | Sección | Qué contiene |
|---|---|---|
| Servidor | Switches | La lista de switches con su disponibilidad, utilización y alertas. Aquí se añaden los nuevos. |
| Esquema | Topología | Mapa de enlaces entre switches basado en LLDP. |
| Reloj | Registro de cambios | Quién cambió qué y cuándo; revertir cambios. |
| Base de datos | Datos y copias de seguridad | Retención del historial, copias de seguridad, restauración. |
| Radar | Búsqueda e importación | Búsqueda en la red e importación desde NetBox (solo administradores). |
| Avión de papel | Notificaciones | Mensajes por Telegram y correo (solo administradores). |
| Lupa | Buscar dispositivo | Búsqueda por MAC, IP, nombre y descripción del puerto. |

En la parte inferior del menú: **Ayuda**, el cambio de tema claro/oscuro, **Configuración** (sondeo y umbrales de alerta) y su perfil.

# Perfil e idioma {#language}

Haga clic en el círculo con sus iniciales al final del menú. Allí puede cambiar la contraseña, abrir la ayuda y elegir el **idioma de la interfaz**. «Según el sistema» usa el idioma del navegador, que normalmente coincide con el del sistema operativo.

El registro de cambios, los eventos y los mensajes de Telegram y correo se escriben en un idioma común: lo elige un administrador en **Configuración → Idioma**.

# Eventos {#events}

La campana de la barra superior muestra los eventos recientes: un puerto cayó o se levantó, utilización alta, errores en el puerto, un switch inaccesible. El número de la campana indica los no leídos. Al hacer clic en un evento se abre el switch y se resalta el puerto.

# Atajos de teclado {#keys}

| Teclas | Acción |
|---|---|
| [[Ctrl]] + [[K]] o [[/]] | Buscar un dispositivo |
| [[Esc]] | Cerrar una ventana o un menú |
| [[↑]] [[↓]] [[Enter]] | Elegir un resultado de búsqueda |

# Roles {#roles}

Un **Administrador** puede hacerlo todo. Un **Observador** ve todas las páginas y puede consultar switches, pero no puede cambiar nada: los botones de edición están ocultos para él. Más información: [Usuarios y roles](/help/users).
