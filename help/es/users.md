---
title: Usuarios y roles
category: admin
order: 1
summary: Administradores y observadores, contraseñas, bloqueo y qué hacer si se olvida una contraseña.
keywords: usuario rol administrador observador contraseña inicio de sesión bloquear restablecer olvidé sesión
---
# Roles {#roles}

| Rol | Puede |
|---|---|
| **Administrador** | Todo: añadir y cambiar switches, configuración, notificaciones, usuarios, restaurar copias |
| **Observador** | Ver todas las páginas, consultar switches, buscar dispositivos, comprobar accesibilidad. No cambia nada |

El rol de observador es adecuado para personal de guardia, soporte y empresas externas. Los botones de edición están ocultos para él y, además, el servidor comprueba los permisos en cada acción.

# Añadir un usuario {#add}

Sección **Usuarios** (menú de perfil → **Usuarios**, solo administradores) → **Añadir usuario**: nombre, rol y una contraseña de al menos 8 caracteres. Comunique la contraseña al usuario: podrá cambiarla él mismo en el menú de perfil.

# Bloqueo y contraseñas {#manage}

- **Bloquear**: el usuario pierde el acceso al instante pero sigue en la lista (sus acciones en el registro se conservan).
- **Fijar contraseña**: una contraseña nueva; se cierran todas las sesiones del usuario en otros equipos.
- El último administrador no se puede eliminar, bloquear ni degradar: así siempre hay forma de iniciar sesión.

Tras 5 intentos fallidos seguidos, el inicio de sesión con ese nombre desde esa dirección se bloquea temporalmente. Los intentos fallidos se anotan en el registro de cambios.

# Olvidé la contraseña del administrador {#reset}

Fije una contraseña nueva desde la línea de comandos del servidor donde está instalado SwitchMap:

| Sistema | Comando |
|---|---|
| Windows (como administrador) | `& "C:\Program Files\SwitchMap\switchmap.exe" reset-password admin` |
| Linux | `sudo switchmap reset-password admin` |
| Desde el código fuente | `python app.py reset-password admin` |

Si no existe un usuario con ese nombre, el comando ofrece crear un administrador.

# Sesiones {#sessions}

Sin **Recordarme durante 30 días** la sesión termina tras 12 horas de inactividad; con esa opción, a los 30 días.
