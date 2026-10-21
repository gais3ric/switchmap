**Русский** · [English](#english)

Первый выпуск SwitchMap — учёт коммутаторов и мониторинг сети в одном веб-приложении.

## Что умеет

- **Схема портов** — коммутаторы и патч-панели как в стойке: порты RJ-45 и SFP, транки, подключения с цветом кабеля, VLAN, PoE.
- **Мониторинг по SNMP v2c/v3** — состояние, скорость, трафик, загрузка и ошибки портов; CPU, память и температура; графики от часа до года.
- **Оповещения** в Telegram и на почту: коммутатор недоступен, порт упал, высокая загрузка, ошибки, перегрев. Тихие часы, подавление «мигающих» портов.
- **Поиск устройства** по MAC, IP, имени и описанию порта — в каком коммутаторе и порту оно подключено.
- **Топология сети** по LLDP.
- **Поиск коммутаторов в сети** и **импорт из NetBox**.
- **Пользователи** с ролями «администратор» и «наблюдатель», **журнал изменений** с отменой, **резервные копии** базы.
- **Выгрузка** в Excel, CSV и PDF.
- **Шесть языков интерфейса** (русский, английский, китайский, испанский, немецкий, французский) и **встроенная справка** с подсказками у полей.
- Работает **без интернета**, тёмная и светлая темы, работает на телефоне.

## Установка

**Windows 10/11, Windows Server 2016+** — `SwitchMap-Setup-X.Y.Z.exe`
Запустите от имени администратора. Установщик спросит, откуда открывать веб-интерфейс (только с этого компьютера или из сети) и порт, зарегистрирует службу «SwitchMap» и запустит её. Данные: `C:\ProgramData\SwitchMap`.

**Debian 12+, Ubuntu 22.04+** — `switchmap_X.Y.Z-1_amd64.deb`
```
sudo apt install ./switchmap_X.Y.Z-1_amd64.deb
```

**RHEL / AlmaLinux / Rocky Linux 9+** — `switchmap-X.Y.Z-1.x86_64.rpm`
```
sudo dnf install ./switchmap-X.Y.Z-1.x86_64.rpm
```
Служба `switchmap` (systemd), настройки `/etc/switchmap/switchmap.conf`, данные `/var/lib/switchmap`.

После установки откройте `http://localhost:5000` и создайте администратора. Дальше помогут «Первые шаги» на главной странице и раздел «Справка».

## Обновление

Установите новую версию поверх старой — база, ключи и настройки сохраняются, перед изменением схемы базы создаётся резервная копия.

Windows покажет предупреждение SmartScreen «Неизвестный издатель» — установщик не подписан сертификатом. Нажмите «Подробнее» → «Выполнить в любом случае». Контрольные суммы файлов — в `SHA256SUMS.txt`.

---

<a id="english"></a>
**English**

The first release of SwitchMap — switch inventory and network monitoring in one web app.

## Highlights

- **Port map** — switches and patch panels as in the rack: RJ-45 and SFP ports, trunks, connections with cable colors, VLANs, PoE.
- **SNMP v2c/v3 monitoring** — port status, speed, traffic, utilization and errors; CPU, memory and temperature; charts from an hour to a year.
- **Alerts** to Telegram and email: switch down, port down, high utilization, errors, overheating. Quiet hours, flap suppression.
- **Find a device** by MAC, IP, name or port description — which switch and port it is plugged into.
- **Network topology** from LLDP.
- **Network discovery** and **NetBox import**.
- **Users** with administrator and viewer roles, **change log** with undo, database **backups**.
- **Export** to Excel, CSV and PDF.
- **Six interface languages** (English, Russian, Chinese, Spanish, German, French) and **built-in help** with hints next to fields.
- Works **offline**, dark and light themes, works on phones.

## Installation

| System | File | How to install |
|---|---|---|
| Windows 10/11, Server 2016+ | `SwitchMap-Setup-X.Y.Z.exe` | run as administrator |
| Debian 12+, Ubuntu 22.04+ | `switchmap_X.Y.Z-1_amd64.deb` | `sudo apt install ./switchmap_X.Y.Z-1_amd64.deb` |
| RHEL, AlmaLinux, Rocky Linux 9+ | `switchmap-X.Y.Z-1.x86_64.rpm` | `sudo dnf install ./switchmap-X.Y.Z-1.x86_64.rpm` |

Then open `http://localhost:5000` and create the administrator. To update, install the new version over the old one — data and settings are kept.

The installer is not signed, so Windows SmartScreen shows «Unknown publisher»: click **More info → Run anyway**. File checksums are in `SHA256SUMS.txt`.
