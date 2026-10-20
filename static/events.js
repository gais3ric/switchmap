// Колокольчик событий: общий для главной страницы и страницы коммутатора.
// Нужны элементы #bellBadge, #eventsPanel, #eventsList и кнопка .bell-btn.

// Важность: down — авария, warn — предупреждение, up — восстановление
const EVENT_TYPES = {
    switch_down: { text: t('Коммутатор недоступен'),        cls: 'event-type-down' },
    switch_up:   { text: t('Коммутатор снова доступен'),    cls: 'event-type-up' },
    down:       { text: t('Порт упал (down)'),            cls: 'event-type-down' },
    up:          { text: t('Порт поднялся (up)'),          cls: 'event-type-up' },
    util_high:   { text: t('Высокая загрузка порта'),      cls: 'event-type-warn' },
    util_ok:     { text: t('Загрузка порта в норме'),       cls: 'event-type-up' },
    errors_high: { text: t('Ошибки на порту'),              cls: 'event-type-warn' },
    errors_ok:   { text: t('Ошибки на порту прекратились'), cls: 'event-type-up' },
    cpu_high:    { text: t('Высокая загрузка CPU'),         cls: 'event-type-down' },
    cpu_ok:      { text: t('CPU в норме'),                  cls: 'event-type-up' },
    temp_high:   { text: t('Перегрев коммутатора'),         cls: 'event-type-down' },
    temp_ok:     { text: t('Температура в норме'),          cls: 'event-type-up' },
};

function eventsEscape(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
}

function eventTypeLabel(type) {
    const kind = EVENT_TYPES[type] || { text: type, cls: '' };
    return `<span class="event-type ${kind.cls}"><i class="ev-dot"></i>${eventsEscape(kind.text)}</span>`;
}

function refreshUnreadBadge() {
    fetch('/api/port_events/unread_count')
        .then(r => r.json())
        .then(data => {
            const badge = document.getElementById('bellBadge');
            if (!badge) return;
            const count = data.count || 0;
            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : count;
                badge.style.display = 'flex';
            } else {
                badge.style.display = 'none';
            }
        })
        .catch(() => {});
}

function eventLink(ev) {
    const port = ev.port_number ? `?port=${encodeURIComponent(ev.port_number)}` : '';
    return `/switch/${encodeURIComponent(ev.switch_id)}${port}`;
}

function loadEventsList() {
    const list = document.getElementById('eventsList');
    list.innerHTML = t('<div class="events-empty">Загрузка…</div>');
    fetch('/api/port_events?limit=50')
        .then(r => r.json())
        .then(events => {
            if (!events.length) {
                list.innerHTML = t('<div class="events-empty">Событий пока нет</div>');
                return;
            }
            list.innerHTML = events.map(ev => {
                const where = ev.ifindex === null || ev.ifindex === undefined
                    ? eventsEscape(ev.port_name)
                    : eventsEscape(t('порт {port}', { port: ev.port_number ? `${ev.port_number} · ${ev.port_name}` : ev.port_name }));
                return `
                <a class="event-item ${ev.is_read ? '' : 'unread'}" href="${eventLink(ev)}" title="${eventsEscape(t('Открыть коммутатор'))}">
                    ${eventTypeLabel(ev.event_type)}
                    ${ev.details ? `<div class="event-details">${eventsEscape(ev.details)}</div>` : ''}
                    <div class="event-meta">
                        ${eventsEscape(ev.switch_name)} — ${where}<br>
                        ${eventsEscape(ev.event_time)}
                    </div>
                </a>`;
            }).join('');
        })
        .catch(() => {
            list.innerHTML = t('<div class="events-empty">Ошибка загрузки</div>');
        });
}

function toggleEventsPanel() {
    const panel = document.getElementById('eventsPanel');
    const willShow = !panel.classList.contains('visible');
    panel.classList.toggle('visible', willShow);
    if (willShow) {
        loadEventsList();
    }
}

function markAllEventsRead() {
    fetch('/api/port_events/mark_read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ all: true })
    })
        .then(() => {
            refreshUnreadBadge();
            loadEventsList();
        })
        .catch(() => {});
}

document.addEventListener('click', (e) => {
    const panel = document.getElementById('eventsPanel');
    const bell = document.querySelector('.bell-btn');
    if (panel && panel.classList.contains('visible') && !panel.contains(e.target) && !(bell && bell.contains(e.target))) {
        panel.classList.remove('visible');
    }
});
