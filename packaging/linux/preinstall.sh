#!/bin/sh
# Системный пользователь службы (без входа в систему)
set -e
if ! getent group switchmap >/dev/null 2>&1; then
    groupadd --system switchmap
fi
if ! getent passwd switchmap >/dev/null 2>&1; then
    NOLOGIN=/usr/sbin/nologin
    [ -x "$NOLOGIN" ] || NOLOGIN=/sbin/nologin
    useradd --system --gid switchmap --home-dir /var/lib/switchmap --no-create-home \
        --shell "$NOLOGIN" --comment "SwitchMap service" switchmap
fi
exit 0
