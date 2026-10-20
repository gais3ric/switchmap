# SwitchMap

Веб-приложение для учёта и мониторинга коммутаторов: схема портов и патч-панелей, опрос по SNMP (v2c/v3),
загрузка и ошибки портов, CPU и температура, поиск устройства по MAC/IP, топология по LLDP,
уведомления в Telegram и на почту, поиск коммутаторов в сети и импорт из NetBox.

## Установка на сервер

Готовые установщики — в разделе **Releases** на GitHub. Python ставить не нужно: он входит в программу.

| Система | Файл | Установка |
|---|---|---|
| Windows 10/11, Server 2016+ | `SwitchMap-Setup-X.Y.Z.exe` | запустить от имени администратора |
| Debian 12+, Ubuntu 22.04+ | `switchmap_X.Y.Z-1_amd64.deb` | `sudo apt install ./switchmap_X.Y.Z-1_amd64.deb` |
| RHEL / Alma / Rocky 9+ | `switchmap-X.Y.Z-1.x86_64.rpm` | `sudo dnf install ./switchmap-X.Y.Z-1.x86_64.rpm` |

SwitchMap работает как служба: запускается вместе с системой и перезапускается после сбоя.
Откройте `http://localhost:5000` и создайте администратора.

| | Windows | Linux |
|---|---|---|
| Настройки | `C:\ProgramData\SwitchMap\switchmap.conf` | `/etc/switchmap/switchmap.conf` |
| База, ключи, копии, журнал | `C:\ProgramData\SwitchMap` | `/var/lib/switchmap` |
| Перезапуск | `Restart-Service SwitchMap` | `sudo systemctl restart switchmap` |
| Сброс пароля | `& "C:\Program Files\SwitchMap\switchmap.exe" reset-password admin` | `sudo switchmap reset-password admin` |

Обновление — установка новой версии поверх: данные и настройки сохраняются.
Как выпустить релиз и собрать установщики самому — [packaging/README.md](packaging/README.md).

## Запуск из исходников (разработка)

Нужен Python 3.12 или новее.

```
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
python app.py
```

Данные при этом лежат в текущей папке.

| Настройка | Назначение |
|---|---|
| `SWITCHMAP_HOST` | адрес, на котором слушать; `0.0.0.0` — доступ из сети (по умолчанию только этот компьютер) |
| `SWITCHMAP_PORT` | порт, по умолчанию 5000 |
| `SWITCHMAP_HTTPS` | `1`, если приложение работает за HTTPS-прокси (cookie только по HTTPS) |
| `SWITCHMAP_DATA` | папка данных |
| `SWITCHMAP_LOG_LEVEL` | подробность журнала: `DEBUG`, `INFO`, `WARNING` |
| `SWITCHMAP_TELEGRAM_API` | свой сервер Telegram Bot API (необязательно) |

Настройки задаются переменными окружения или в файле `switchmap.conf` (образец — `packaging/switchmap.conf.example`).
`python app.py --paths` показывает, где лежат база, настройки и журнал.

## Файлы данных (не входят в репозиторий)

- `switches.db` — база;
- `switchmap.secret` — ключи подписи сессий и шифрования паролей (SNMPv3, почта, Telegram, NetBox).
  Храните отдельно и переносите вместе с базой; без него сохранённые пароли придётся ввести заново;
- `backups/` — резервные копии базы (ключи в них не попадают);
- `logs/switchmap.log` — журнал работы (5 файлов по 5 МБ).

## Тесты

```
python tests\run_all.py          # быстрые
python tests\run_all.py --all    # все, включая SNMP-симулятор и браузер
```

Подробности и подготовка — в [tests/README.md](tests/README.md).

## Структура

| Файл | Что внутри |
|---|---|
| `app.py` | веб-приложение, SNMP-опрос, планировщик |
| `config.py` | пути к данным, файл настроек, журнал |
| `security.py` | пользователи, вход, CSRF, шифрование секретов |
| `audit.py` | журнал изменений и откат |
| `maintenance.py` | свёртка истории, сроки хранения, резервные копии |
| `notify.py` | уведомления в Telegram и на почту |
| `discovery.py` | поиск коммутаторов в сети |
| `netbox.py` | интеграция с NetBox |
| `xlsx.py` | экспорт в Excel и CSV |
| `templates/`, `static/` | интерфейс (`static/vendor` — Chart.js, d3, pdfmake) |
| `packaging/` | сборка установщиков Windows, deb, rpm |
