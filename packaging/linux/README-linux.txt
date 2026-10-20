SwitchMap для Linux

Служба
    sudo systemctl status switchmap         состояние
    sudo systemctl restart switchmap        перезапуск (после изменения настроек)
    sudo journalctl -u switchmap -f         журнал службы

Файлы
    /etc/switchmap/switchmap.conf           настройки: адрес, порт, HTTPS
    /var/lib/switchmap/switches.db          база
    /var/lib/switchmap/switchmap.secret     ключи шифрования — переносите вместе с базой
    /var/lib/switchmap/backups/             резервные копии
    /var/lib/switchmap/logs/switchmap.log   журнал работы
    /opt/switchmap/                         программа

Доступ из сети
    В /etc/switchmap/switchmap.conf: SWITCHMAP_HOST=0.0.0.0, затем sudo systemctl restart switchmap.
    Откройте порт в брандмауэре, если он включён:
        firewalld: sudo firewall-cmd --permanent --add-port=5000/tcp && sudo firewall-cmd --reload
        ufw:       sudo ufw allow 5000/tcp

Забыли пароль администратора
    sudo switchmap reset-password admin

Перенос данных с другого сервера (Windows или Linux)
    sudo systemctl stop switchmap
    скопируйте switches.db и switchmap.secret в /var/lib/switchmap/
    sudo chown switchmap:switchmap /var/lib/switchmap/*
    sudo systemctl start switchmap

Обновление — установка нового пакета поверх: данные и настройки сохраняются,
перед изменением схемы базы создаётся резервная копия.
    Debian/Ubuntu:  sudo apt install ./switchmap_X.Y.Z_amd64.deb
    RHEL/Alma/Rocky: sudo dnf install ./switchmap-X.Y.Z-1.x86_64.rpm
