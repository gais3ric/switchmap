---
title: 在交换机上启用 SNMP
category: devices
order: 3
summary: 适用于 Cisco、HPE/Aruba、Juniper、MikroTik、华为、D-Link、TP-Link、Eltex 等的现成命令。
keywords: 配置 启用 snmp cisco ios catalyst hpe aruba procurve comware h3c 华三 juniper junos mikrotik routeros huawei 华为 d-link dlink tp-link eltex ubiquiti unifi lldp community
---
以下是最小配置：**只读** 访问，限制为 SwitchMap 服务器地址，并启用 **LLDP** 以便生成[拓扑](/help/topology)。示例中：

| 值 | 替换为 |
|---|---|
| `192.168.1.10` | SwitchMap 服务器的 IP 地址 |
| `MyStr0ngRO` | 您自己的 community（v2c） |
| `swmap` | SNMPv3 用户名 |
| `AuthPass123`、`PrivPass123` | 您自己的 v3 密码，至少 8 个字符 |

> **重要：** 命令可能因型号和固件版本而略有不同。如果某条命令不被接受，请在厂商文档中查找“SNMP”章节——参数名称会很相似。

配置完成后，在 SwitchMap 中添加交换机并点击 **检查并填写**——立即可以看到访问是否正常。

# Cisco IOS 和 IOS-XE（Catalyst） {#cisco}

SNMP v2c：

```
configure terminal
access-list 10 permit 192.168.1.10
snmp-server community MyStr0ngRO RO 10
lldp run
end
write memory
```

SNMP v3（推荐）：

```
configure terminal
access-list 10 permit 192.168.1.10
snmp-server group SWMAP v3 priv access 10
snmp-server user swmap SWMAP v3 auth sha AuthPass123 priv aes 128 PrivPass123
lldp run
end
write memory
```

SNMPv3 用户不会显示在 `show running-config` 中——这是正常的。检查命令：`show snmp user`。

Cisco 为每个 VLAN 单独保存 MAC 表。要让 SwitchMap 通过 v3 看到所有 VLAN 的 MAC 地址，请允许 VLAN 上下文：`snmp-server group SWMAP v3 priv context vlan- match prefix`。

# Cisco Business 和 Small Business（CBS、SG） {#cisco-sb}

Web 界面：**SNMP → Engine ID**（保持默认）、**SNMP → Communities** 或 **SNMP → Users**（v3）。启用 SNMP：**Security → TCP/UDP Services → SNMP Service**。LLDP：**Administration → Discovery – LLDP → Properties**。

# HPE Aruba（ArubaOS-Switch、ProCurve） {#aruba}

```
configure
snmp-server community "MyStr0ngRO" operator restricted
snmpv3 enable
snmpv3 user swmap auth sha AuthPass123 priv aes PrivPass123
snmpv3 group operatorauth user swmap sec-model ver3
lldp run
write memory
```

`snmpv3 enable` 可能会要求输入初始密码——任意输入即可，之后删除初始用户 `initial`。

# HPE Aruba CX（AOS-CX） {#aruba-cx}

```
configure
snmp-server vrf default
snmp-server community MyStr0ngRO
snmpv3 user swmap auth sha auth-pass plaintext AuthPass123 priv aes priv-pass plaintext PrivPass123
lldp
write memory
```

如果通过 mgmt 端口管理，请使用 `snmp-server vrf mgmt`。

# HPE Comware 和 H3C（HPE 5130、5140、1950 等） {#comware}

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

# Juniper（Junos、EX 和 QFX） {#juniper}

SNMP v2c：

```
set snmp community MyStr0ngRO authorization read-only
set snmp community MyStr0ngRO clients 192.168.1.10/32
set protocols lldp interface all
commit
```

SNMP v3：

```
set snmp v3 usm local-engine user swmap authentication-sha authentication-password AuthPass123
set snmp v3 usm local-engine user swmap privacy-aes128 privacy-password PrivPass123
set snmp v3 vacm security-to-group security-model usm security-name swmap group swmap-grp
set snmp v3 vacm access group swmap-grp default-context-prefix security-model any security-level privacy read-view all
set snmp view all oid .1 include
commit
```

# MikroTik（RouterOS） {#mikrotik}

SNMP v2c：

```
/snmp set enabled=yes
/snmp community set [find default=yes] name=MyStr0ngRO addresses=192.168.1.10/32 read-access=yes write-access=no
```

SNMP v3（RouterOS 7）：在 RouterOS 中，community 名称同时也是 v3 用户名。

```
/snmp community add name=swmap addresses=192.168.1.10/32 security=private authentication-protocol=SHA1 authentication-password=AuthPass123 encryption-protocol=AES encryption-password=PrivPass123
```

LLDP（RouterOS 7）：`/ip neighbor discovery-settings set protocol=cdp,lldp,mndp`。

# 华为（VRP，S 系列） {#huawei}

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

最后两条命令会提示输入密码。

# D-Link（DGS、DES） {#dlink}

命令行（大多数 DGS-1210/3000/3100 型号）：

```
enable snmp
create snmp community MyStr0ngRO view CommunityView read_only
enable lldp
save
```

Web 界面：**Management → SNMP Settings**（启用 SNMP，添加 community 或 v3 用户）。配置 v3 用 Web 界面更方便。

# TP-Link（JetStream、Omada） {#tplink}

Web 界面：**Maintenance → SNMP → Global Config**——启用 SNMP；**SNMP → Community**——添加 **只读** community；v3——**SNMP User**。LLDP：**L2 Features → LLDP**。由 Omada 控制器管理的交换机在控制器中配置：**Settings → Services → SNMP**。

# Eltex（MES） {#eltex}

```
configure
snmp-server server
snmp-server community MyStr0ngRO ro 192.168.1.10
lldp run
end
write
```

# Ubiquiti UniFi {#unifi}

在 UniFi 控制器中启用 SNMP：**Settings → System → SNMP**（v1/v2c community 或 v3 用户）。该设置作用于站点内所有交换机。

# 从服务器检查 {#check}

如果安装了 Net-SNMP 工具，可以这样测试访问：

```
snmpget -v2c -c MyStr0ngRO 192.0.2.5 1.3.6.1.2.1.1.5.0
snmpget -v3 -l authPriv -u swmap -a SHA -A AuthPass123 -x AES -X PrivPass123 192.0.2.5 1.3.6.1.2.1.1.5.0
```

返回结果是交换机名称。“Timeout”表示网络不通、community 错误或用户错误。详见[故障排除](/help/troubleshooting)。
