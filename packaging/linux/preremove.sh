#!/bin/sh
# Останавливаем службу только при удалении пакета, не при обновлении
# (deb: $1=remove|upgrade|...; rpm: $1=0 удаление, 1 обновление)
set -e
case "$1" in
    remove|purge|0)
        if [ -d /run/systemd/system ]; then
            systemctl disable --now switchmap.service >/dev/null 2>&1 || true
        fi
        ;;
esac
exit 0
