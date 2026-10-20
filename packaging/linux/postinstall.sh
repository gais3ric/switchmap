#!/bin/sh
# deb: $1=configure, $2=прежняя версия (пусто при первой установке); rpm: $1=1 установка, 2 обновление
set -e
FIRST=0
case "$1" in
    configure) [ -z "$2" ] && FIRST=1 ;;
    1) FIRST=1 ;;
esac

install -d -o switchmap -g switchmap -m 0750 /var/lib/switchmap
chown -R switchmap:switchmap /var/lib/switchmap
if [ -f /etc/switchmap/switchmap.conf ]; then
    chown root:switchmap /etc/switchmap/switchmap.conf
    chmod 0640 /etc/switchmap/switchmap.conf
fi

if [ -d /run/systemd/system ]; then
    systemctl daemon-reload >/dev/null 2>&1 || true
    if [ "$FIRST" = 1 ]; then
        systemctl enable --now switchmap.service >/dev/null 2>&1 || true
        PORT=$(sed -n 's/^SWITCHMAP_PORT=//p' /etc/switchmap/switchmap.conf 2>/dev/null | tail -n1)
        echo "SwitchMap запущен: http://localhost:${PORT:-5000}/ — откройте и создайте администратора."
        echo "Доступ из сети: SWITCHMAP_HOST=0.0.0.0 в /etc/switchmap/switchmap.conf, затем systemctl restart switchmap"
    else
        # Обновление: перезапуск, только если служба работала
        systemctl try-restart switchmap.service >/dev/null 2>&1 || true
    fi
fi
exit 0
