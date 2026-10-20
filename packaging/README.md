# Сборка установщиков

## Релиз (обычный путь)

```
git tag v1.2.0
git push origin v1.2.0
```

GitHub Actions (`.github/workflows/release.yml`) собирает программу на Windows и Linux, устанавливает её на чистые машины и проверяет:
- запуск службы, вход, страницы, опрос SNMP v2c/v3, ping;
- обновление поверх установленной версии;
- перезапуск службы после сбоя;
- удаление программы (данные при этом должны остаться).

Если всё прошло, создаётся релиз с файлами:

| Файл | Для чего |
|---|---|
| `SwitchMap-Setup-1.2.0.exe` | Windows 10/11, Server 2016+ (x64) |
| `switchmap_1.2.0-1_amd64.deb` | Debian 12+, Ubuntu 22.04+ |
| `switchmap-1.2.0-1.x86_64.rpm` | RHEL / AlmaLinux / Rocky Linux 9+ |
| `SHA256SUMS.txt` | контрольные суммы |

Пробная сборка без релиза: GitHub → Actions → Release → Run workflow. Файлы появятся в артефактах запуска.

## Локальная сборка (Windows)

Нужны Python 3.13 и Inno Setup 6 (`winget install Python.Python.3.13 JRSoftware.InnoSetup`).

```
py -3.13 -m venv build\venv313
build\venv313\Scripts\pip install -r packaging\requirements-build.txt
build\venv313\Scripts\python packaging\build.py --installer --version 1.2.0
```

Результат: `dist\SwitchMap-Setup-1.2.0.exe`. Проверить собранную программу без установки:

```
python packaging\smoke.py --exe dist\switchmap\switchmap.exe
```

## Что внутри

| Файл | Назначение |
|---|---|
| `build.py` | сборка: PyInstaller → `dist/switchmap/`, затем Inno Setup или nfpm |
| `entry.py` | точка входа программы |
| `smoke.py` | проверка программы «снаружи», по HTTP |
| `switchmap.conf.example` | файл настроек, кладётся при первой установке |
| `requirements-build.txt` | точные версии библиотек для сборки |
| `windows/switchmap.iss` | установщик Windows: служба, брандмауэр, права на папку данных |
| `windows/switchmap-service.xml` | служба Windows (WinSW 2.12, скачивается при сборке с проверкой контрольной суммы) |
| `linux/nfpm.yaml` | пакеты deb и rpm |
| `linux/switchmap.service` | служба systemd с ограничениями (пишет только в `/var/lib/switchmap`) |
| `linux/*.sh` | пользователь службы, запуск, остановка при удалении |

## Где программа хранит данные

| | Windows | Linux |
|---|---|---|
| Программа | `C:\Program Files\SwitchMap` | `/opt/switchmap` |
| Настройки | `C:\ProgramData\SwitchMap\switchmap.conf` | `/etc/switchmap/switchmap.conf` |
| База, ключи, копии, журнал | `C:\ProgramData\SwitchMap` | `/var/lib/switchmap` |
| Служба | «SwitchMap», учётная запись LocalService | `switchmap.service`, пользователь `switchmap` |

`switchmap --paths` показывает пути на конкретной машине.
