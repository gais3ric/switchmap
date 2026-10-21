---
title: Datos, copias de seguridad y registro de cambios
category: data
order: 1
summary: Cuánto tiempo se guarda el historial, cómo crear y restaurar copias, el registro de cambios y la reversión.
keywords: copia de seguridad backup restaurar retención historial registro auditoría revertir mover base de datos compactar
---
# Retención del historial {#retention}

Sección **Datos y copias de seguridad** (icono de base de datos). Cada sondeo guarda el tráfico, los errores y el estado de los puertos. Para que la base de datos no crezca sin fin:

| Datos | Por defecto | Qué ocurre después |
|---|---|---|
| Historial detallado (cada sondeo) | 7 días | Se agrega en valores por hora (media y máximo) |
| Historial por horas | 365 días | Se elimina |
| Eventos | 90 días | Se eliminan |

El mantenimiento de la base de datos se ejecuta automáticamente cada hora. **Ejecutar mantenimiento ahora** lo lanza al momento; **compactar el archivo de la base** libera espacio en disco tras borrar datos antiguos.

# Copias de seguridad {#backups}

- **Copia automática diaria**: una vez al día; se conservan tantas copias como indique **Copias a conservar** (14 por defecto) y las más antiguas se eliminan.
- **Crear copia**: a mano, por ejemplo antes de cambios importantes.
- También se hace una copia automáticamente: al iniciar una versión nueva si cambia la estructura de la base de datos y antes de restaurar otra copia.

Cada copia se puede **descargar**, **restaurar** o **eliminar**. **Restaurar desde archivo** sube una copia descargada antes o hecha en otro servidor.

> **Importante:** las copias están en el mismo disco que la base de datos (la carpeta `backups` dentro de la carpeta de datos). Descárguelas con regularidad o copie la carpeta a otro servidor: las copias junto a la base no sobreviven a una avería del disco.

Las claves de cifrado (el archivo `switchmap.secret`) **no** se incluyen en las copias, así que una copia se puede guardar y transferir con seguridad. Pero sin ese archivo habrá que volver a introducir las contraseñas de SNMPv3, correo, Telegram y NetBox de la copia. Guarde `switchmap.secret` aparte en un lugar seguro.

# Restauración {#restore}

Pulse **Restaurar** junto a la copia que necesite. Antes, la base de datos actual se guarda en una copia aparte («antes de restaurar»), así que una restauración se puede deshacer restaurando esa copia. Los usuarios y sus contraseñas no se revierten si la copia no los contiene.

# Mover a otro servidor {#move}

1. Detenga SwitchMap en el servidor antiguo.
2. Copie `switches.db` y `switchmap.secret` de la carpeta de datos.
3. Instale SwitchMap en el servidor nuevo, detenga el servicio, coloque los archivos en su carpeta de datos e inicie el servicio.

Dónde está la carpeta de datos: vea [Instalación y configuración](/help/installation#files).

# Registro de cambios {#audit}

La sección **Registro de cambios** (icono de reloj) muestra quién cambió qué y cuándo: switches, conexiones, configuración, usuarios y también los intentos fallidos de inicio de sesión. Se puede filtrar por switch y tipo.

**Revertir** junto a un cambio de switch restaura los valores anteriores. Un switch eliminado se puede **restaurar** con sus conexiones y dispositivos.
