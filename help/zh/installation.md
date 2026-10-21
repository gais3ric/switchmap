---
title: 安装与配置
category: admin
order: 2
summary: Windows 和 Linux 安装程序、服务、设置文件、网络访问、HTTPS、更新。
keywords: 安装 安装程序 服务 windows linux deb rpm ubuntu debian rhel 设置 switchmap.conf 端口 https caddy 代理 证书 更新 日志
---
# 安装 {#install}

安装程序位于 SwitchMap 代码仓库的 **Releases** 页面。无需安装 Python：它已打包在程序中。

| 系统 | 文件 | 安装方式 |
|---|---|---|
| Windows 10/11、Server 2016+ | `SwitchMap-Setup-X.Y.Z.exe` | 以管理员身份运行 |
| Debian 12+、Ubuntu 22.04+ | `switchmap_X.Y.Z-1_amd64.deb` | `sudo apt install ./switchmap_X.Y.Z-1_amd64.deb` |
| RHEL、AlmaLinux、Rocky Linux 9+ | `switchmap-X.Y.Z-1.x86_64.rpm` | `sudo dnf install ./switchmap-X.Y.Z-1.x86_64.rpm` |

Windows 安装程序会询问 SwitchMap 可以从哪里打开——仅本机或网络（此时会在防火墙中开放端口）——以及端口号。

> **提示：** Windows 可能显示 SmartScreen 警告“未知发布者”——安装程序未使用付费证书签名。请点击 **更多信息 → 仍要运行**。

安装完成后打开 `http://localhost:5000` 并创建管理员。

# 服务 {#service}

SwitchMap 以服务方式运行：随系统启动，崩溃后自动重启。

| 操作 | Windows（以管理员身份运行 PowerShell） | Linux |
|---|---|---|
| 状态 | `Get-Service SwitchMap` | `systemctl status switchmap` |
| 重启 | `Restart-Service SwitchMap` | `sudo systemctl restart switchmap` |
| 停止 | `Stop-Service SwitchMap` | `sudo systemctl stop switchmap` |

在 Windows 上服务以受限的 **LocalService** 帐户运行；在 Linux 上以单独的 `switchmap` 用户运行，只能写入自己的数据文件夹。

# 文件 {#files}

| | Windows | Linux |
|---|---|---|
| 程序 | `C:\Program Files\SwitchMap` | `/opt/switchmap` |
| 设置 | `C:\ProgramData\SwitchMap\switchmap.conf` | `/etc/switchmap/switchmap.conf` |
| 数据库 | `C:\ProgramData\SwitchMap\switches.db` | `/var/lib/switchmap/switches.db` |
| 加密密钥 | `…\switchmap.secret` | `/var/lib/switchmap/switchmap.secret` |
| 备份 | `…\backups` | `/var/lib/switchmap/backups` |
| 程序日志 | `…\logs\switchmap.log` | `/var/lib/switchmap/logs/switchmap.log` 以及 `journalctl -u switchmap` |

`switchmap --paths` 命令会显示某台服务器上的具体路径。

# 设置 {#config}

`switchmap.conf` 文件由 `键=值` 形式的行组成。修改后请重启服务。

| 键 | 值 |
|---|---|
| `SWITCHMAP_HOST` | `127.0.0.1`——仅本机；`0.0.0.0`——允许网络访问 |
| `SWITCHMAP_PORT` | Web 界面端口，默认 `5000` |
| `SWITCHMAP_HTTPS` | `1`——SwitchMap 位于 HTTPS 代理之后 |
| `SWITCHMAP_PROXY` | `1`——从代理请求头获取用户地址 |
| `SWITCHMAP_DATA` | 其他数据文件夹 |
| `SWITCHMAP_LOG_LEVEL` | 日志详细程度：`DEBUG`、`INFO`、`WARNING` |

在 Linux 上，设置 `SWITCHMAP_HOST=0.0.0.0` 后，还需在防火墙中开放端口：`sudo firewall-cmd --permanent --add-port=5000/tcp && sudo firewall-cmd --reload`（RHEL）或 `sudo ufw allow 5000/tcp`（Ubuntu）。

# HTTPS {#https}

SwitchMap 本身使用 HTTP。如果有人从其他电脑访问，请在其前面放置 HTTPS 代理——否则密码会以明文在网络中传输。最简单的方案是 **Caddy**（免费，可自动获取并续期证书）。

1. 在 `switchmap.conf` 中设置：
   ```
   SWITCHMAP_HOST=127.0.0.1
   SWITCHMAP_HTTPS=1
   SWITCHMAP_PROXY=1
   ```
   然后重启 SwitchMap。
2. 安装 Caddy：Debian 和 Ubuntu 上执行 `sudo apt install caddy`，其他系统请按 caddyserver.com 上的说明安装。
3. 配置 `Caddyfile`（Linux 上为 `/etc/caddy/Caddyfile`）：
   ```
   switchmap.company.local {
       tls internal
       reverse_proxy 127.0.0.1:5000
   }
   ```
   `tls internal` 让 Caddy 为内网签发自己的证书（浏览器会要求信任一次）。对于可从互联网访问的域名，请删除这一行——Caddy 会自动获取 Let's Encrypt 证书。
4. 重新加载 Caddy（`sudo systemctl reload caddy`），然后打开 `https://switchmap.company.local`。

如果已有 nginx 或 IIS，请配置指向 `http://127.0.0.1:5000` 的反向代理，并传递 `X-Forwarded-For` 和 `X-Forwarded-Proto` 请求头。

# 更新 {#update}

使用同样的安装程序或软件包在旧版本上直接安装新版本。数据和设置会保留，数据库结构变化前会自动备份。版本号显示在个人菜单中。

# 卸载 {#uninstall}

卸载程序不会影响数据：数据库、密钥和备份仍保留在数据文件夹中。如果不再需要，请手动删除该文件夹。
