---
title: Включение SNMP на коммутаторах
category: devices
order: 3
summary: Готовые команды для Cisco, HPE/Aruba, Juniper, MikroTik, Huawei, D-Link, TP-Link, Eltex и других.
keywords: настроить включить snmp cisco ios catalyst hpe aruba procurve comware h3c juniper junos mikrotik routeros huawei d-link dlink tp-link eltex ubiquiti unifi lldp community
---
Ниже — минимальные настройки: доступ **только на чтение**, ограниченный адресом сервера SwitchMap, и включённый **LLDP** для [топологии](/help/topology). В примерах:

| Значение | Что подставить |
|---|---|
| `192.168.1.10` | IP-адрес сервера SwitchMap |
| `MyStr0ngRO` | своё community (для v2c) |
| `swmap` | имя пользователя SNMPv3 |
| `AuthPass123`, `PrivPass123` | свои пароли v3, не короче 8 символов |

> **Важно:** команды могут немного отличаться в зависимости от модели и версии прошивки. Если команда не принимается, найдите в документации производителя раздел «SNMP» — названия параметров будут похожими.

После настройки добавьте коммутатор в SwitchMap и нажмите **Проверить и заполнить** — так сразу видно, работает ли доступ.

# Cisco IOS и IOS-XE (Catalyst) {#cisco}

SNMP v2c:

```
configure terminal
access-list 10 permit 192.168.1.10
snmp-server community MyStr0ngRO RO 10
lldp run
end
write memory
```

SNMP v3 (рекомендуется):

```
configure terminal
access-list 10 permit 192.168.1.10
snmp-server group SWMAP v3 priv access 10
snmp-server user swmap SWMAP v3 auth sha AuthPass123 priv aes 128 PrivPass123
lldp run
end
write memory
```

Пользователи SNMPv3 не показываются в `show running-config` — это нормально. Проверка: `show snmp user`.

Cisco хранит таблицы MAC-адресов отдельно для каждого VLAN. Чтобы SwitchMap видел MAC-адреса во всех VLAN по v3, разрешите контексты VLAN: `snmp-server group SWMAP v3 priv context vlan- match prefix`.

# Cisco Business и Small Business (CBS, SG) {#cisco-sb}

Веб-интерфейс: **SNMP → Engine ID** (оставить по умолчанию), **SNMP → Communities** или **SNMP → Users** (для v3). Включить сам SNMP: **Security → TCP/UDP Services → SNMP Service**. LLDP: **Administration → Discovery – LLDP → Properties**.

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

`snmpv3 enable` может спросить начальные пароли — их можно задать любые, затем удалить начального пользователя `initial`.

# HPE Aruba CX (AOS-CX) {#aruba-cx}

```
configure
snmp-server vrf default
snmp-server community MyStr0ngRO
snmpv3 user swmap auth sha auth-pass plaintext AuthPass123 priv aes priv-pass plaintext PrivPass123
lldp
write memory
```

Если управление идёт через порт mgmt, укажите `snmp-server vrf mgmt`.

# HPE Comware и H3C (HPE 5130, 5140, 1950 и др.) {#comware}

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

# Juniper (Junos, EX и QFX) {#juniper}

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

SNMP v3 (RouterOS 7): в RouterOS имя community — это и есть имя пользователя v3.

```
/snmp community add name=swmap addresses=192.168.1.10/32 security=private authentication-protocol=SHA1 authentication-password=AuthPass123 encryption-protocol=AES encryption-password=PrivPass123
```

LLDP (RouterOS 7): `/ip neighbor discovery-settings set protocol=cdp,lldp,mndp`.

# Huawei (VRP, серии S) {#huawei}

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

Последние две команды спросят пароли.

# D-Link (DGS, DES) {#dlink}

Через командную строку (большинство моделей DGS-1210/3000/3100):

```
enable snmp
create snmp community MyStr0ngRO view CommunityView read_only
enable lldp
save
```

В веб-интерфейсе: **Management → SNMP Settings** (включить SNMP, добавить community или пользователя v3). Для v3 удобнее веб-интерфейс.

# TP-Link (JetStream, Omada) {#tplink}

Веб-интерфейс: **Maintenance → SNMP → Global Config** — включить SNMP; **SNMP → Community** — добавить community с доступом **read-only**; для v3 — **SNMP User**. LLDP: **L2 Features → LLDP**. Коммутаторы под управлением контроллера Omada настраиваются в контроллере: **Settings → Services → SNMP**.

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

SNMP включается в контроллере UniFi: **Settings → System → SNMP** (v1/v2c community или пользователь v3). Настройка действует на все коммутаторы площадки.

# Проверка с сервера {#check}

Если под рукой есть утилиты Net-SNMP, проверить доступ можно так:

```
snmpget -v2c -c MyStr0ngRO 192.0.2.5 1.3.6.1.2.1.1.5.0
snmpget -v3 -l authPriv -u swmap -a SHA -A AuthPass123 -x AES -X PrivPass123 192.0.2.5 1.3.6.1.2.1.1.5.0
```

Ответ — имя коммутатора. «Timeout» — нет доступа по сети, неверный community или пользователь. Подробнее — [Решение проблем](/help/troubleshooting).
