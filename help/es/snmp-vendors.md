---
title: Activar SNMP en los switches
category: devices
order: 3
summary: Comandos listos para Cisco, HPE/Aruba, Juniper, MikroTik, Huawei, D-Link, TP-Link, Eltex y otros.
keywords: configurar activar snmp cisco ios catalyst hpe aruba procurve comware h3c juniper junos mikrotik routeros huawei d-link dlink tp-link eltex ubiquiti unifi lldp community
---
A continuación, la configuración mínima: acceso de **solo lectura**, limitado a la dirección del servidor de SwitchMap, y **LLDP** activado para la [topología](/help/topology). En los ejemplos:

| Valor | Sustituir por |
|---|---|
| `192.168.1.10` | la dirección IP del servidor de SwitchMap |
| `MyStr0ngRO` | su propia community (para v2c) |
| `swmap` | el nombre del usuario SNMPv3 |
| `AuthPass123`, `PrivPass123` | sus propias contraseñas v3, de al menos 8 caracteres |

> **Importante:** los comandos pueden variar ligeramente según el modelo y la versión de firmware. Si un comando no se acepta, busque la sección «SNMP» en la documentación del fabricante: los nombres de los parámetros serán parecidos.

Después de configurarlo, añada el switch en SwitchMap y pulse **Comprobar y rellenar**: verá enseguida si el acceso funciona.

# Cisco IOS e IOS-XE (Catalyst) {#cisco}

SNMP v2c:

```
configure terminal
access-list 10 permit 192.168.1.10
snmp-server community MyStr0ngRO RO 10
lldp run
end
write memory
```

SNMP v3 (recomendado):

```
configure terminal
access-list 10 permit 192.168.1.10
snmp-server group SWMAP v3 priv access 10
snmp-server user swmap SWMAP v3 auth sha AuthPass123 priv aes 128 PrivPass123
lldp run
end
write memory
```

Los usuarios SNMPv3 no aparecen en `show running-config`: es normal. Para comprobarlo: `show snmp user`.

Cisco guarda una tabla MAC por cada VLAN. Para que SwitchMap vea las direcciones MAC de todas las VLAN por v3, permita los contextos de VLAN: `snmp-server group SWMAP v3 priv context vlan- match prefix`.

# Cisco Business y Small Business (CBS, SG) {#cisco-sb}

Interfaz web: **SNMP → Engine ID** (deje el valor por defecto), **SNMP → Communities** o **SNMP → Users** (para v3). Para activar SNMP: **Security → TCP/UDP Services → SNMP Service**. LLDP: **Administration → Discovery – LLDP → Properties**.

# HPE Aruba (ArubaOS-Switch, ProCurve) {#aruba}

```
configure
snmp-server community "MyStr0ngRO" operator restricted
snmpv3 enable
snmpv3 user swmap auth sha AuthPass123 priv aes PrivPass123
snmpv3 group operatorauth user swmap sec-model ver3
lldp run
write memory
```

`snmpv3 enable` puede pedir contraseñas iniciales: introduzca cualquiera y después elimine el usuario inicial `initial`.

# HPE Aruba CX (AOS-CX) {#aruba-cx}

```
configure
snmp-server vrf default
snmp-server community MyStr0ngRO
snmpv3 user swmap auth sha auth-pass plaintext AuthPass123 priv aes priv-pass plaintext PrivPass123
lldp
write memory
```

Si la gestión pasa por el puerto mgmt, use `snmp-server vrf mgmt`.

# HPE Comware y H3C (HPE 5130, 5140, 1950 y otros) {#comware}

```
system-view
snmp-agent
snmp-agent sys-info version v2c v3
snmp-agent community read MyStr0ngRO
snmp-agent group v3 swmap-grp privacy
snmp-agent usm-user v3 swmap swmap-grp simple authentication-mode sha AuthPass123 privacy-mode aes128 PrivPass123
lldp global enable
save
```

# Juniper (Junos, EX y QFX) {#juniper}

SNMP v2c:

```
set snmp community MyStr0ngRO authorization read-only
set snmp community MyStr0ngRO clients 192.168.1.10/32
set protocols lldp interface all
commit
```

SNMP v3:

```
set snmp v3 usm local-engine user swmap authentication-sha authentication-password AuthPass123
set snmp v3 usm local-engine user swmap privacy-aes128 privacy-password PrivPass123
set snmp v3 vacm security-to-group security-model usm security-name swmap group swmap-grp
set snmp v3 vacm access group swmap-grp default-context-prefix security-model any security-level privacy read-view all
set snmp view all oid .1 include
commit
```

# MikroTik (RouterOS) {#mikrotik}

SNMP v2c:

```
/snmp set enabled=yes
/snmp community set [find default=yes] name=MyStr0ngRO addresses=192.168.1.10/32 read-access=yes write-access=no
```

SNMP v3 (RouterOS 7): en RouterOS el nombre de la community es también el nombre del usuario v3.

```
/snmp community add name=swmap addresses=192.168.1.10/32 security=private authentication-protocol=SHA1 authentication-password=AuthPass123 encryption-protocol=AES encryption-password=PrivPass123
```

LLDP (RouterOS 7): `/ip neighbor discovery-settings set protocol=cdp,lldp,mndp`.

# Huawei (VRP, serie S) {#huawei}

```
system-view
snmp-agent
snmp-agent sys-info version v2c v3
snmp-agent community read cipher MyStr0ngRO
snmp-agent group v3 swmap-grp privacy
snmp-agent usm-user v3 swmap group swmap-grp
snmp-agent usm-user v3 swmap authentication-mode sha
snmp-agent usm-user v3 swmap privacy-mode aes128
lldp enable
save
```

Los dos últimos comandos piden las contraseñas.

# D-Link (DGS, DES) {#dlink}

Desde la línea de comandos (la mayoría de los modelos DGS-1210/3000/3100):

```
enable snmp
create snmp community MyStr0ngRO view CommunityView read_only
enable lldp
save
```

En la interfaz web: **Management → SNMP Settings** (activar SNMP, añadir una community o un usuario v3). Para v3 resulta más cómoda la interfaz web.

# TP-Link (JetStream, Omada) {#tplink}

Interfaz web: **Maintenance → SNMP → Global Config**: activar SNMP; **SNMP → Community**: añadir una community de **solo lectura**; para v3, **SNMP User**. LLDP: **L2 Features → LLDP**. Los switches gestionados por un controlador Omada se configuran en el controlador: **Settings → Services → SNMP**.

# Eltex (MES) {#eltex}

```
configure
snmp-server server
snmp-server community MyStr0ngRO ro 192.168.1.10
lldp run
end
write
```

# Ubiquiti UniFi {#unifi}

SNMP se activa en el controlador UniFi: **Settings → System → SNMP** (community v1/v2c o usuario v3). El ajuste se aplica a todos los switches del sitio.

# Comprobación desde el servidor {#check}

Si dispone de las herramientas Net-SNMP, puede probar el acceso así:

```
snmpget -v2c -c MyStr0ngRO 192.0.2.5 1.3.6.1.2.1.1.5.0
snmpget -v3 -l authPriv -u swmap -a SHA -A AuthPass123 -x AES -X PrivPass123 192.0.2.5 1.3.6.1.2.1.1.5.0
```

La respuesta es el nombre del switch. «Timeout» significa que no hay acceso de red o que la community o el usuario son incorrectos. Más información: [Solución de problemas](/help/troubleshooting).
