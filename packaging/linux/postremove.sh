#!/bin/sh
# Данные (/var/lib/switchmap) и настройки (/etc/switchmap) после удаления остаются
set -e
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload >/dev/null 2>&1 || true
fi
case "$1" in
    remove|0)
        echo "SwitchMap удалён. База, ключи и резервные копии остались в /var/lib/switchmap."
        ;;
esac
exit 0
