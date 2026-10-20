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

После установки откройте `http://localhost:5000` и создайте администратора.

## Обновление

Установите новую версию поверх старой — база, ключи и настройки сохраняются, перед изменением схемы базы создаётся резервная копия.

Windows покажет предупреждение SmartScreen «Неизвестный издатель» — установщик не подписан сертификатом. Нажмите «Подробнее» → «Выполнить в любом случае». Контрольные суммы файлов — в `SHA256SUMS.txt`.
