---
title: Instalación y configuración
category: admin
order: 2
summary: Instaladores para Windows y Linux, el servicio, el archivo de configuración, acceso desde la red, HTTPS, actualizaciones.
keywords: instalar instalador servicio windows linux deb rpm ubuntu debian rhel configuración switchmap.conf puerto https caddy proxy certificado actualizar registro logs
---
# Instalación {#install}

Los instaladores están en la sección **Releases** del repositorio de SwitchMap. No hace falta instalar Python: va incluido en el programa.

| Sistema | Archivo | Cómo instalar |
|---|---|---|
| Windows 10/11, Server 2016+ | `SwitchMap-Setup-X.Y.Z.exe` | Ejecutar como administrador |
| Debian 12+, Ubuntu 22.04+ | `switchmap_X.Y.Z-1_amd64.deb` | `sudo apt install ./switchmap_X.Y.Z-1_amd64.deb` |
| RHEL, AlmaLinux, Rocky Linux 9+ | `switchmap-X.Y.Z-1.x86_64.rpm` | `sudo dnf install ./switchmap-X.Y.Z-1.x86_64.rpm` |

El instalador de Windows pregunta desde dónde se podrá abrir SwitchMap (solo este equipo o la red; en ese caso abre el puerto en el cortafuegos) y el número de puerto.

> **Consejo:** Windows puede mostrar el aviso de SmartScreen «Editor desconocido»: el instalador no está firmado con un certificado de pago. Pulse **Más información → Ejecutar de todas formas**.

Tras la instalación abra `http://localhost:5000` y cree un administrador.

# Servicio {#service}

SwitchMap funciona como servicio: arranca con el sistema y se reinicia tras un fallo.

| Acción | Windows (PowerShell como administrador) | Linux |
|---|---|---|
| Estado | `Get-Service SwitchMap` | `systemctl status switchmap` |
| Reiniciar | `Restart-Service SwitchMap` | `sudo systemctl restart switchmap` |
| Detener | `Stop-Service SwitchMap` | `sudo systemctl stop switchmap` |

En Windows el servicio se ejecuta con la cuenta restringida **LocalService**; en Linux, como el usuario independiente `switchmap`, y solo puede escribir en su carpeta de datos.

# Archivos {#files}

| | Windows | Linux |
|---|---|---|
| Programa | `C:\Program Files\SwitchMap` | `/opt/switchmap` |
| Configuración | `C:\ProgramData\SwitchMap\switchmap.conf` | `/etc/switchmap/switchmap.conf` |
| Base de datos | `C:\ProgramData\SwitchMap\switches.db` | `/var/lib/switchmap/switches.db` |
| Claves de cifrado | `…\switchmap.secret` | `/var/lib/switchmap/switchmap.secret` |
| Copias de seguridad | `…\backups` | `/var/lib/switchmap/backups` |
| Registro del programa | `…\logs\switchmap.log` | `/var/lib/switchmap/logs/switchmap.log` y `journalctl -u switchmap` |

El comando `switchmap --paths` muestra las rutas en un servidor concreto.

# Configuración {#config}

El archivo `switchmap.conf` contiene líneas del tipo `CLAVE=valor`. Reinicie el servicio tras cambiarlo.

| Clave | Valor |
|---|---|
| `SWITCHMAP_HOST` | `127.0.0.1`: solo este equipo; `0.0.0.0`: desde la red |
| `SWITCHMAP_PORT` | Puerto de la interfaz web, `5000` por defecto |
| `SWITCHMAP_HTTPS` | `1`: SwitchMap funciona detrás de un proxy HTTPS |
| `SWITCHMAP_PROXY` | `1`: tomar la dirección del usuario de las cabeceras del proxy |
| `SWITCHMAP_DATA` | Otra carpeta de datos |
| `SWITCHMAP_LOG_LEVEL` | Detalle del registro: `DEBUG`, `INFO`, `WARNING` |

En Linux, para permitir el acceso desde la red, tras `SWITCHMAP_HOST=0.0.0.0` abra el puerto en el cortafuegos: `sudo firewall-cmd --permanent --add-port=5000/tcp && sudo firewall-cmd --reload` (RHEL) o `sudo ufw allow 5000/tcp` (Ubuntu).

# HTTPS {#https}

SwitchMap habla HTTP. Si se conectan desde otros equipos, ponga delante un proxy HTTPS; si no, las contraseñas viajan por la red sin cifrar. Lo más sencillo es **Caddy** (gratuito, obtiene y renueva los certificados solo).

1. En `switchmap.conf` indique:
   ```
   SWITCHMAP_HOST=127.0.0.1
   SWITCHMAP_HTTPS=1
   SWITCHMAP_PROXY=1
   ```
   y reinicie SwitchMap.
2. Instale Caddy: en Debian y Ubuntu, `sudo apt install caddy`; en otros sistemas, siga las instrucciones de caddyserver.com.
3. Configure el `Caddyfile` (en Linux, `/etc/caddy/Caddyfile`):
   ```
   switchmap.company.local {
       tls internal
       reverse_proxy 127.0.0.1:5000
   }
   ```
   `tls internal` hace que Caddy emita su propio certificado para la red interna (los navegadores piden confiar en él una vez). Para un dominio accesible desde Internet, quite esa línea: Caddy obtendrá solo un certificado de Let's Encrypt.
4. Recargue Caddy (`sudo systemctl reload caddy`) y abra `https://switchmap.company.local`.

Si ya tiene nginx o IIS, configure un proxy inverso a `http://127.0.0.1:5000` que pase las cabeceras `X-Forwarded-For` y `X-Forwarded-Proto`.

# Actualización {#update}

Instale la versión nueva sobre la anterior con el mismo instalador o paquete. Los datos y la configuración se conservan, y antes de cambiar la estructura de la base de datos se hace una copia automáticamente. La versión se muestra en el menú de perfil.

# Desinstalación {#uninstall}

Desinstalar el programa no toca los datos: la base de datos, las claves y las copias se quedan en la carpeta de datos. Bórrela a mano si ya no los necesita.
