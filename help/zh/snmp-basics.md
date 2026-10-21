---
title: 什么是 SNMP
category: devices
order: 2
summary: 通俗解释：v2c 与 v3 版本、community、用户与密码、安全性。
keywords: snmp v2c v3 community 用户 认证 加密 sha aes md5 des 上下文 安全 udp 161
---
**SNMP**（简单网络管理协议）是查询网络设备状态的标准方式：端口列表、端口是否启用、已传输多少流量、可见哪些 MAC 地址、CPU 负载和温度等。几乎所有可管理交换机都支持它。

SwitchMap 只 **读取** 数据——从不修改交换机上的任何内容，因此只读权限就足够了。

请求发送到交换机的 **UDP 161** 端口。

# v2c 还是 v3 {#v2c-or-v3}

| | SNMP v2c | SNMP v3 |
|---|---|---|
| 如何验证访问 | 通过共享密码——**community** | 用户和密码 |
| 数据加密 | 无——全部以明文传输 | 有（AES、DES） |
| 配置 | 交换机上一行命令 | 几行命令 |
| 何时选择 | 隔离的管理网络 | 其他所有情况 |

> **重要：** 人人都知道 community `public`。如果使用 v2c，请设置自己的强 community，并将 SNMP 访问限制为 SwitchMap 服务器地址。

# Community {#community}

community 只是一个字符串，交换机会将其与收到的进行比较。读取时通常创建具有 **RO**（只读）权限的 community。在 SwitchMap 中填写在 **Community** 字段。网络发现时可以用逗号分隔填写多个。

# SNMPv3 {#snmpv3}

在 v3 中，需要在交换机上创建一个带有两个密码的 **用户**：

- **认证**（SHA、SHA-256 等，以及过时的 MD5）——证明请求来自您且在传输中未被篡改。
- **加密**（AES128 等，以及过时的 DES）——隐藏响应内容。

安全级别：

| 级别 | 认证 | 加密 |
|---|---|---|
| noAuthNoPriv | 否 | 否 |
| authNoPriv | 是 | 否 |
| authPriv | 是 | 是——推荐 |

在 SwitchMap 中填写与交换机上相同的 **算法** 和 **密码**。密码至少 8 个字符（标准要求）。

**上下文** 通常留空。例如在 Cisco 交换机上需要它，通过 `vlan-10` 上下文读取某个 VLAN 的 MAC 表。

SNMPv3 密码在 SwitchMap 数据库中加密存储，加密密钥保存在单独的 `switchmap.secret` 文件中。

# SwitchMap 读取哪些数据 {#what}

| 数据 | 来源（MIB） |
|---|---|
| 名称、描述、位置 | SNMPv2-MIB（system） |
| 端口及其状态、速率、流量和错误计数 | IF-MIB |
| 端口描述（ifAlias） | IF-MIB |
| 端口上的 MAC 地址 | BRIDGE-MIB、Q-BRIDGE-MIB |
| 端口 VLAN | Q-BRIDGE-MIB |
| 邻居 | LLDP-MIB |
| CPU、内存、温度 | 各不相同——取决于厂商 |
| PoE | POWER-ETHERNET-MIB |

如果缺少某些数据，说明交换机不通过 SNMP 提供这些数据，或需要其他上下文。其余功能仍可正常工作。
