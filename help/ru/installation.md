---
title: Установка и настройка
category: admin
order: 2
summary: Установщики для Windows и Linux, служба, файл настроек, доступ из сети, HTTPS, обновление.
keywords: установка установщик служба windows linux deb rpm ubuntu debian rhel настройки switchmap.conf порт https caddy прокси сертификат обновление журнал логи
---
# Установка {#install}

Установщики — в разделе **Releases** репозитория SwitchMap. Python ставить не нужно: он входит в программу.

| Система | Файл | Как установить |
|---|---|---|
| Windows 10/11, Server 2016+ | `SwitchMap-Setup-X.Y.Z.exe` | Запустите от имени администратора |
| Debian 12+, Ubuntu 22.04+ | `switchmap_X.Y.Z-1_amd64.deb` | `sudo apt install ./switchmap_X.Y.Z-1_amd64.deb` |
| RHEL, AlmaLinux, Rocky Linux 9+ | `switchmap-X.Y.Z-1.x86_64.rpm` | `sudo dnf install ./switchmap-X.Y.Z-1.x86_64.rpm` |

Установщик Windows спросит, откуда можно будет открывать SwitchMap — только с этого компьютера или из сети (тогда он откроет порт в брандмауэре), — и номер порта.

> **Совет:** Windows может показать предупреждение SmartScreen «Неизвестный издатель» — установщик не подписан платным сертификатом. Нажмите **Подробнее → Выполнить в любом случае**.

После установки откройте `http://localhost:5000` и создайте администратора.

# Служба {#service}

SwitchMap работает как служба: запускается вместе с системой и перезапускается после сбоя.

| Действие | Windows (PowerShell от имени администратора) | Linux |
|---|---|---|
| Состояние | `Get-Service SwitchMap` | `systemctl status switchmap` |
| Перезапуск | `Restart-Service SwitchMap` | `sudo systemctl restart switchmap` |
| Остановка | `Stop-Service SwitchMap` | `sudo systemctl stop switchmap` |

На Windows служба работает под ограниченной учётной записью **LocalService**, на Linux — от отдельного пользователя `switchmap` и может писать только в свою папку данных.

# Файлы {#files}

| | Windows | Linux |
|---|---|---|
| Программа | `C:\Program Files\SwitchMap` | `/opt/switchmap` |
| Настройки | `C:\ProgramData\SwitchMap\switchmap.conf` | `/etc/switchmap/switchmap.conf` |
| База | `C:\ProgramData\SwitchMap\switches.db` | `/var/lib/switchmap/switches.db` |
| Ключи шифрования | `…\switchmap.secret` | `/var/lib/switchmap/switchmap.secret` |
| Резервные копии | `…\backups` | `/var/lib/switchmap/backups` |
| Журнал работы | `…\logs\switchmap.log` | `/var/lib/switchmap/logs/switchmap.log` и `journalctl -u switchmap` |

Команда `switchmap --paths` показывает пути на конкретном сервере.

# Настройки {#config}

Файл `switchmap.conf` — строки вида `КЛЮЧ=значение`. После изменения перезапустите службу.

| Ключ | Значение |
|---|---|
| `SWITCHMAP_HOST` | `127.0.0.1` — только с этого компьютера; `0.0.0.0` — из сети |
| `SWITCHMAP_PORT` | Порт веб-интерфейса, по умолчанию `5000` |
| `SWITCHMAP_HTTPS` | `1` — SwitchMap работает за HTTPS-прокси |
| `SWITCHMAP_PROXY` | `1` — брать адрес пользователя из заголовков прокси |
| `SWITCHMAP_DATA` | Другая папка данных |
| `SWITCHMAP_LOG_LEVEL` | Подробность журнала: `DEBUG`, `INFO`, `WARNING` |

На Linux, чтобы открыть доступ из сети, после `SWITCHMAP_HOST=0.0.0.0` откройте порт в брандмауэре: `sudo firewall-cmd --permanent --add-port=5000/tcp && sudo firewall-cmd --reload` (RHEL) или `sudo ufw allow 5000/tcp` (Ubuntu).

# HTTPS {#https}

Сам SwitchMap работает по HTTP. Если к нему подключаются с других компьютеров, поставьте перед ним HTTPS-прокси — иначе пароли передаются по сети открытым текстом. Проще всего — **Caddy** (бесплатный, сам получает и продлевает сертификаты).

1. В `switchmap.conf` укажите:
   ```
   SWITCHMAP_HOST=127.0.0.1
   SWITCHMAP_HTTPS=1
   SWITCHMAP_PROXY=1
   ```
   и перезапустите SwitchMap.
2. Установите Caddy: на Debian и Ubuntu — `sudo apt install caddy`, на других системах — по инструкции на caddyserver.com.
3. Настройте файл `Caddyfile` (на Linux — `/etc/caddy/Caddyfile`):
   ```
   switchmap.company.local {
       tls internal
       reverse_proxy 127.0.0.1:5000
   }
   ```
   `tls internal` — Caddy выпустит свой сертификат для внутренней сети (браузеры попросят один раз ему довериться). Для домена, доступного из интернета, эту строку уберите — Caddy получит сертификат Let's Encrypt сам.
4. Перезапустите Caddy (`sudo systemctl reload caddy`) и откройте `https://switchmap.company.local`.

Если у вас уже есть nginx или IIS — настройте в нём обратный прокси на `http://127.0.0.1:5000` с передачей заголовков `X-Forwarded-For` и `X-Forwarded-Proto`.

# Обновление {#update}

Установите новую версию поверх старой — тем же установщиком или пакетом. Данные и настройки сохраняются, а перед изменением устройства базы автоматически делается резервная копия. Версия видна в меню профиля.

# Удаление {#uninstall}

Удаление программы не трогает данные: база, ключи и резервные копии остаются в папке данных. Удалите её вручную, если они больше не нужны.
