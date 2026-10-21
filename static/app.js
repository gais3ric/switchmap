// Каркас приложения: тема, глобальный поиск, настройки, уведомления, подтверждения.
// Подключается на всех страницах после /static/events.js.

// ───────── CSRF и сессия ─────────
// Все изменяющие запросы к приложению получают заголовок X-CSRF-Token.
// Ответ 401 (сессия истекла) — переход на страницу входа с возвратом на текущую страницу.
(function () {
    const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const nativeFetch = window.fetch.bind(window);
    window.fetch = (input, init = {}) => {
        const method = (init.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
        const url = new URL(input instanceof Request ? input.url : input, location.href);
        if (url.origin === location.origin && !['GET', 'HEAD', 'OPTIONS'].includes(method)) {
            const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
            headers.set('X-CSRF-Token', token);
            init = { ...init, headers };
        }
        return nativeFetch(input, init).then(response => {
            if (response.status === 401 && url.origin === location.origin && !location.pathname.startsWith('/login')) {
                location.href = '/login?next=' + encodeURIComponent(location.pathname + location.search);
            }
            return response;
        });
    };
})();

// ───────── Действия без встроенного JavaScript ─────────
// Политика безопасности (CSP) запрещает onclick="…" и подобные атрибуты: внедрённая в страницу
// разметка не сможет выполнить код. Вместо них — данные в атрибутах, код — здесь:
//   <button data-click="saveSettings">                       → saveSettings()
//   <button data-click="deleteSwitch" data-args='[5, "SW1"]'>  → deleteSwitch(5, "SW1")
//   <input data-change="updateName" data-args='[3, "$value"]'> → updateName(3, input.value)
// Особые аргументы: "$el" — сам элемент, "$form" — его форма, "$value" — значение поля, "$event" — событие.
// Вызываются только функции, объявленные в скриптах приложения (глобальные function).
// Кликабельные строки таблиц сами пропускают клики по ссылкам и кнопкам внутри.
function runAction(el, attr, event) {
    const name = el.getAttribute(attr);
    const fn = window[name];
    if (typeof fn !== 'function') {
        console.warn('No action', name);
        return;
    }
    let args = [];
    if (el.dataset.args) {
        try { args = JSON.parse(el.dataset.args); } catch (err) { console.warn('Bad data-args', el); return; }
    }
    const special = { $el: el, $form: el.form, $value: el.value, $event: event };
    return fn.apply(el, args.map(a => (typeof a === 'string' && a in special) ? special[a] : a));
}

['click', 'change', 'input'].forEach(type => {
    document.addEventListener(type, event => {
        const el = event.target.closest(`[data-${type}]`);
        if (!el || el.disabled) return;
        runAction(el, `data-${type}`, event);
    });
});

// Мелкие действия для разметки
function focusById(id) { document.getElementById(id)?.focus(); }
function clickById(id) { document.getElementById(id)?.click(); }
function hideById(id, cls = 'visible') { document.getElementById(id)?.classList.remove(cls); }
function goBack() { history.back(); }

// ───────── Тема ─────────
// Начальная тема ставится ещё в <head> (base.html), чтобы не было вспышки.
const THEME_KEY = 'switchmap.theme';

function currentTheme() {
    return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}

function setTheme(theme) {
    document.body.classList.add('theme-transition');
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* без localStorage — только до перезагрузки */ }
    updateThemeButton();
    setTimeout(() => document.body.classList.remove('theme-transition'), 360);
    document.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
}

function toggleTheme() {
    setTheme(currentTheme() === 'dark' ? 'light' : 'dark');
}

function updateThemeButton() {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;
    const dark = currentTheme() === 'dark';
    btn.dataset.label = dark ? t('Светлая тема') : t('Тёмная тема');
    btn.querySelector('.icon-sun').hidden = !dark;
    btn.querySelector('.icon-moon').hidden = dark;
}

// Значение CSS-токена текущей темы (для графиков и canvas)
function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// ───────── Уведомления ─────────
const TOAST_ICONS = { success: '✓', error: '!', warning: '!', info: 'i' };

function notify(message, kind = 'info', timeout) {
    let box = document.getElementById('toasts');
    if (!box) {
        box = document.createElement('div');
        box.id = 'toasts';
        box.className = 'toasts';
        box.setAttribute('role', 'status');
        box.setAttribute('aria-live', 'polite');
        document.body.appendChild(box);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${kind}`;
    toast.innerHTML = `<span class="toast-icon">${TOAST_ICONS[kind] || 'i'}</span><span class="toast-text"></span>`;
    toast.querySelector('.toast-text').textContent = message;
    box.appendChild(toast);
    const close = () => {
        toast.classList.add('is-leaving');
        setTimeout(() => toast.remove(), 220);
    };
    toast.addEventListener('click', close);
    setTimeout(close, timeout || (kind === 'error' ? 7000 : 4000));
    return toast;
}

// ───────── Подтверждение (вместо confirm) ─────────
function confirmDialog(message, { title = t('Подтверждение'), okText = 'OK', danger = false } = {}) {
    return new Promise(resolve => {
        const modal = document.getElementById('confirmModal');
        modal.querySelector('#confirmTitle').textContent = title;
        modal.querySelector('#confirmText').textContent = message;
        const ok = modal.querySelector('#confirmOk');
        ok.textContent = okText;
        ok.className = 'btn ' + (danger ? 'btn-danger-solid' : 'btn-primary');
        const cancel = modal.querySelector('#confirmCancel');
        const done = result => {
            modal.classList.remove('active');
            ok.onclick = cancel.onclick = modal.onclick = null;
            document.removeEventListener('keydown', onKey, true);
            resolve(result);
        };
        const onKey = e => {
            if (e.key === 'Escape') { e.stopPropagation(); done(false); }
            if (e.key === 'Enter') { e.preventDefault(); done(true); }
        };
        ok.onclick = () => done(true);
        cancel.onclick = () => done(false);
        modal.onclick = e => { if (e.target === modal) done(false); };
        document.addEventListener('keydown', onKey, true);
        modal.classList.add('active');
        setTimeout(() => ok.focus(), 50);
    });
}

// ───────── Окно-форма (вместо prompt) ─────────
// Цвета кабеля: значение — цвет CSS (так они хранятся в подключениях), подпись — на языке интерфейса
const CABLE_COLORS = [
    ['gray', t('серый')], ['blue', t('синий')], ['green', t('зелёный')], ['yellow', t('жёлтый')],
    ['orange', t('оранжевый')], ['red', t('красный')], ['purple', t('фиолетовый')], ['white', t('белый')],
    ['black', t('чёрный')],
];

// formDialog({ title, note, okText, fields: [{ name, label, type, value, placeholder, hint, required, min, max }] })
// type: text (по умолчанию), number, cable-color (палитра), color (выбор цвета #RRGGBB).
// Возвращает Promise: объект { name: значение } или null, если окно закрыли.
function formDialog({ title, note = '', okText = 'OK', fields = [] }) {
    return new Promise(resolve => {
        const modal = document.getElementById('formModal');
        const form = document.getElementById('formDialogForm');
        const box = document.getElementById('formFields');
        document.getElementById('formTitle').textContent = title;
        const noteEl = document.getElementById('formNote');
        noteEl.textContent = note;
        noteEl.hidden = !note;
        document.getElementById('formOk').textContent = okText;
        box.replaceChildren();
        const getters = {};

        fields.forEach((f, i) => {
            const wrap = document.createElement('div');
            wrap.className = 'field';
            const id = `formField${i}`;
            const label = document.createElement('label');
            label.textContent = f.label || '';
            label.htmlFor = id;
            wrap.appendChild(label);

            if (f.type === 'cable-color') {
                const palette = document.createElement('div');
                palette.className = 'swatch-row';
                palette.setAttribute('role', 'radiogroup');
                palette.setAttribute('aria-label', f.label || '');
                const colors = CABLE_COLORS.slice();
                if (f.value && !colors.some(([c]) => c === f.value)) colors.push([f.value, f.value]);  // старый свой цвет
                let current = f.value || colors[0][0];
                const buttons = colors.map(([value, name]) => {
                    const b = document.createElement('button');
                    b.type = 'button';
                    b.className = 'swatch';
                    b.dataset.value = value;
                    b.setAttribute('role', 'radio');
                    b.title = name;
                    b.setAttribute('aria-label', name);
                    b.style.setProperty('--swatch', value);
                    b.onclick = () => select(value);
                    palette.appendChild(b);
                    return b;
                });
                const caption = document.createElement('span');
                caption.className = 'swatch-caption';
                const select = value => {
                    current = value;
                    buttons.forEach(b => b.setAttribute('aria-checked', String(b.dataset.value === value)));
                    caption.textContent = (colors.find(([c]) => c === value) || [value, value])[1];
                };
                select(current);
                buttons[0].id = id;
                palette.appendChild(caption);
                wrap.appendChild(palette);
                getters[f.name] = () => current;
            } else {
                const input = document.createElement('input');
                input.id = id;
                input.name = f.name;
                input.type = f.type === 'number' ? 'number' : f.type === 'color' ? 'color' : 'text';
                if (f.placeholder) input.placeholder = f.placeholder;
                if (f.min !== undefined) input.min = f.min;
                if (f.max !== undefined) input.max = f.max;
                if (f.maxlength) input.maxLength = f.maxlength;
                input.value = f.value ?? '';
                input.autocomplete = 'off';
                wrap.appendChild(input);
                getters[f.name] = () => f.type === 'number' ? input.valueAsNumber : input.value.trim();
                getters[f.name].input = input;
            }
            if (f.hint) {
                const hint = document.createElement('div');
                hint.className = 'hint';
                hint.textContent = f.hint;
                wrap.appendChild(hint);
            }
            const err = document.createElement('div');
            err.className = 'field-error';
            err.hidden = true;
            wrap.appendChild(err);
            getters[f.name].error = err;
            box.appendChild(wrap);
        });

        const done = result => {
            modal.classList.remove('active');
            form.onsubmit = modal.onclick = null;
            document.getElementById('formCancel').onclick = document.getElementById('formClose').onclick = null;
            document.removeEventListener('keydown', onKey, true);
            resolve(result);
        };
        const onKey = e => {
            if (e.key === 'Escape') { e.stopPropagation(); done(null); }
            // Enter на кнопке палитры — тоже «сохранить», а не повторный выбор цвета
            if (e.key === 'Enter' && e.target.closest && e.target.closest('#formModal .swatch')) { e.preventDefault(); form.requestSubmit(); }
        };
        form.onsubmit = e => {
            e.preventDefault();
            const values = {};
            let firstBad = null;
            fields.forEach(f => {
                const get = getters[f.name];
                const v = get();
                let msg = '';
                if (f.type === 'number') {
                    if (!Number.isFinite(v)) msg = t('Введите число');
                    else if (f.min !== undefined && v < f.min || f.max !== undefined && v > f.max) msg = t('Допустимо от {min} до {max}', { min: f.min, max: f.max });
                } else if (f.required && !v) {
                    msg = t('Заполните это поле');
                }
                get.error.textContent = msg;
                get.error.hidden = !msg;
                if (get.input) get.input.classList.toggle('is-invalid', !!msg);
                if (msg && !firstBad) firstBad = get.input;
                values[f.name] = v;
            });
            if (firstBad) { firstBad.focus(); return; }
            if (Object.values(getters).some(g => !g.error.hidden)) return;
            done(values);
        };
        document.getElementById('formCancel').onclick = () => done(null);
        document.getElementById('formClose').onclick = () => done(null);
        modal.onclick = e => { if (e.target === modal) done(null); };
        document.addEventListener('keydown', onKey, true);
        modal.classList.add('active');
        setTimeout(() => {
            const first = box.querySelector('input:not([type=color]), .swatch[aria-checked="true"]');
            if (first) { first.focus(); if (first.select) first.select(); }
        }, 50);
    });
}

// ───────── Настройки (окно доступно на всех страницах) ─────────
const THRESHOLD_INPUTS = {
    alert_util_percent: 'alertUtilInput',
    alert_errors_per_poll: 'alertErrorsInput',
    alert_cpu_percent: 'alertCpuInput',
    alert_temp_c: 'alertTempInput',
};

function openSettingsModal() {
    fetch('/api/settings')
        .then(r => r.json())
        .then(data => {
            document.getElementById('pollEnabledInput').checked = !!data.poll_enabled;
            document.getElementById('pollIntervalInput').value = data.poll_interval_minutes || 5;
            Object.entries(THRESHOLD_INPUTS).forEach(([key, id]) => {
                document.getElementById(id).value = data[key] ?? 0;
            });
            document.getElementById('serverLangInput').value = data.server_language || '';
            document.getElementById('updateCheckInput').checked = !!data.update_check;
        })
        .catch(() => notify(t('Не удалось загрузить настройки'), 'error'));
    const uiLang = document.getElementById('settingsUiLang');
    uiLang.value = uiLang.dataset.current;
    fetch('/api/update').then(r => r.json()).then(showUpdateStatus).catch(() => {});
    document.getElementById('settingsModal').classList.add('active');
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.remove('active');
}

function saveSettings() {
    const poll_enabled = document.getElementById('pollEnabledInput').checked;
    let poll_interval_minutes = parseInt(document.getElementById('pollIntervalInput').value, 10);
    if (!poll_interval_minutes || poll_interval_minutes < 1) poll_interval_minutes = 1;

    const body = { poll_enabled, poll_interval_minutes, server_language: document.getElementById('serverLangInput').value };
    const updateCheck = document.getElementById('updateCheckInput');
    if (!updateCheck.disabled) body.update_check = updateCheck.checked;
    Object.entries(THRESHOLD_INPUTS).forEach(([key, id]) => {
        const v = parseInt(document.getElementById(id).value, 10);
        body[key] = Number.isFinite(v) && v > 0 ? v : 0;
    });
    fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
        .then(r => { if (!r.ok) throw new Error(); return r.json(); })
        .then(() => {
            const uiLang = document.getElementById('settingsUiLang');
            if (uiLang.value !== uiLang.dataset.current) return setUserLanguage(uiLang.value);  // перезагрузит страницу
            closeSettingsModal();
            notify(t('Настройки сохранены'), 'success');
        })
        .catch(() => notify(t('Не удалось сохранить настройки'), 'error'));
}

// ───────── Новые версии ─────────
function showUpdateStatus(s) {
    const el = document.getElementById('updateStatus');
    if (!s.allowed) { el.textContent = t('Проверка отключена в файле настроек сервера (SWITCHMAP_UPDATE_CHECK=0).'); return; }
    let text = t('Установлена версия {v}.', { v: s.current });
    if (s.newer) text += ' ' + t('Доступна {v}.', { v: s.latest });
    else if (s.latest) text += ' ' + t('Это последняя версия.');
    if (s.error) text += ' ' + t('Последняя проверка не удалась: {e}', { e: s.error });
    else if (s.checked_at) text += ' ' + t('Проверено: {when}', { when: s.checked_at });
    el.textContent = text;
}

async function checkUpdatesNow() {
    const btn = document.getElementById('updateCheckNow');
    btn.disabled = true;
    try {
        const r = await fetch('/api/update/check', { method: 'POST' });
        const s = await r.json();
        if (!r.ok) throw new Error(s.error || r.status);
        showUpdateStatus(s);
        if (s.newer) notify(t('Доступна новая версия: {v}', { v: s.latest }), 'success');
    } catch (err) {
        notify(t('Не удалось проверить обновления: {e}', { e: err.message }), 'error');
    } finally {
        btn.disabled = false;
    }
}

async function dismissUpdate(version) {
    try { await fetch('/api/update/dismiss', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version }) }); } catch (e) { /* не важно */ }
    document.getElementById('updateBar')?.remove();
}

// ───────── Подсказки «?» (templates/_help.html) ─────────
// Текст подсказки показывается в одном общем окошке поверх всей страницы (position: fixed в <body>):
// внутри панелей, окон и таблиц с прокруткой встроенную подсказку обрезал бы край контейнера.
// Наведение, фокус (Tab) и нажатие (сенсорные экраны) открывают; уход мыши, Esc, прокрутка — закрывают.
const helpPopover = (() => {
    const el = document.createElement('div');
    el.id = 'helpPopover';
    el.className = 'help-pop help-pop-floating';
    el.setAttribute('role', 'tooltip');
    el.hidden = true;
    document.body.appendChild(el);
    return el;
})();
let helpTipCurrent = null, helpTipHideTimer = null, helpTipPinned = false;

function showHelpTip(tip, pinned = false) {
    clearTimeout(helpTipHideTimer);
    const src = tip.querySelector('.help-pop');
    if (!src) return;
    if (helpTipCurrent !== tip) {
        helpPopover.replaceChildren(...[...src.childNodes].map(n => n.cloneNode(true)));
        helpPopover.querySelectorAll('a').forEach(a => a.removeAttribute('tabindex'));
    }
    if (helpTipCurrent && helpTipCurrent !== tip) helpTipCurrent.classList.remove('is-open');
    helpTipCurrent = tip;
    helpTipPinned = pinned;
    tip.classList.add('is-open');
    tip.setAttribute('aria-describedby', 'helpPopover');
    helpPopover.hidden = false;
    // Сверху от «?», если помещается, иначе снизу; по горизонтали — по центру, но не за край окна
    const r = tip.getBoundingClientRect(), w = helpPopover.offsetWidth, h = helpPopover.offsetHeight, gap = 8;
    let top = r.top - h - gap;
    if (top < gap) top = Math.min(r.bottom + gap, window.innerHeight - h - gap);
    const left = Math.max(gap, Math.min(r.left + r.width / 2 - w / 2, window.innerWidth - w - gap));
    helpPopover.style.left = `${Math.round(left)}px`;
    helpPopover.style.top = `${Math.round(Math.max(gap, top))}px`;
}

function hideHelpTip(delay = 0) {
    clearTimeout(helpTipHideTimer);
    const hide = () => {
        helpPopover.hidden = true;
        if (helpTipCurrent) {
            helpTipCurrent.classList.remove('is-open');
            helpTipCurrent.removeAttribute('aria-describedby');
        }
        helpTipCurrent = null;
        helpTipPinned = false;
    };
    if (delay) helpTipHideTimer = setTimeout(hide, delay); else hide();
}

document.addEventListener('mouseover', e => {
    const tip = e.target.closest('.help-tip');
    if (tip) showHelpTip(tip, helpTipPinned && helpTipCurrent === tip);
    else if (e.target.closest('#helpPopover')) clearTimeout(helpTipHideTimer);
});
document.addEventListener('mouseout', e => {
    if (helpTipPinned || !helpTipCurrent) return;
    const from = e.target.closest('.help-tip, #helpPopover');
    const to = e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('.help-tip, #helpPopover');
    if (from && from !== to) hideHelpTip(200);  // пауза — чтобы успеть перевести мышь на ссылку «Подробнее»
});
document.addEventListener('focusin', e => {
    const tip = e.target.closest('.help-tip');
    if (tip) showHelpTip(tip);
    else if (helpTipCurrent && !e.target.closest('#helpPopover')) hideHelpTip();
});
document.addEventListener('click', e => {
    const tip = e.target.closest('.help-tip');
    if (tip) {
        // «?» часто стоит в заголовке, который сам что-то делает по клику (раскрывает секцию) — не передаём клик
        e.preventDefault();
        e.stopPropagation();
        if (helpTipCurrent === tip && helpTipPinned) hideHelpTip(); else showHelpTip(tip, true);
    } else if (helpTipCurrent && !e.target.closest('#helpPopover')) {
        hideHelpTip();
    }
}, true);
document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && helpTipCurrent) { e.stopPropagation(); hideHelpTip(); }
    if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('help-tip')) {
        e.preventDefault();
        showHelpTip(e.target, true);
    }
}, true);
window.addEventListener('scroll', () => { if (helpTipCurrent) hideHelpTip(); }, true);
window.addEventListener('resize', () => { if (helpTipCurrent) hideHelpTip(); });

// ───────── Язык интерфейса (меню пользователя) ─────────
// "" — как в системе (язык браузера); иначе код языка. Сохраняется в профиле, страница перезагружается.
async function setUserLanguage(language) {
    try {
        const r = await fetch('/api/language', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language }) });
        if (!r.ok) throw new Error();
        location.reload();
    } catch (err) {
        notify(t('Не удалось сменить язык'), 'error');
    }
}

// ───────── Смена своего пароля ─────────
function openPasswordModal() {
    const form = document.getElementById('passwordForm');
    form.reset();
    document.getElementById('passwordModal').classList.add('active');
    setTimeout(() => document.getElementById('pwCurrent').focus(), 80);
}

function closePasswordModal() {
    document.getElementById('passwordModal')?.classList.remove('active');
}

document.getElementById('passwordForm')?.addEventListener('submit', async e => {
    e.preventDefault();
    const current = document.getElementById('pwCurrent').value;
    const password = document.getElementById('pwNew').value;
    if (password !== document.getElementById('pwNew2').value) {
        notify(t('Новые пароли не совпадают'), 'error');
        return;
    }
    try {
        const r = await (await fetch('/api/account/password', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ current, password })
        })).json();
        if (!r.ok) throw new Error(r.error);
        closePasswordModal();
        notify(t('Пароль изменён'), 'success');
    } catch (err) {
        notify(err.message || t('Не удалось сменить пароль'), 'error');
    }
});
document.getElementById('passwordModal')?.addEventListener('click', e => {
    if (e.target.id === 'passwordModal') closePasswordModal();
});

// ───────── Глобальный поиск устройства по сети ─────────
(function () {
    const input = document.getElementById('netSearchInput');
    const box = document.getElementById('netSearchResults');
    if (!input || !box) return;
    let timer = null;
    let lastQuery = '';
    let focused = -1;

    const esc = eventsEscape;  // из /static/events.js

    function resultHtml(r) {
        const href = `/switch/${encodeURIComponent(r.switch_id)}${r.port ? `?port=${encodeURIComponent(r.port)}` : ''}`;
        let title, extra = [];
        if (r.kind === 'port') {
            title = `«${esc(r.label)}»`;
            extra.push(esc(r.source));
        } else {
            title = [r.hostname, r.ip, r.mac].filter(Boolean).map(esc).join(' · ') || '—';
            if (r.kind === 'device') extra.push(t('привязано вручную') + (r.notes ? `: ${esc(r.notes)}` : ''));
            if (r.vlan) extra.push(`VLAN ${esc(r.vlan)}`);
            if (r.last_seen) extra.push(t('видели {last_seen}', { last_seen: esc(r.last_seen) }));
        }
        const where = `${esc(r.switch_name)} → ${r.port ? esc(t('порт {port}', { port: r.port })) : t('порт не сопоставлен')}` +
                      (r.port_name ? ` (${esc(r.port_name)})` : '');
        const uplink = r.uplink
            ? `<span class="ns-badge ns-uplink" title="${esc(t('На этом порту видно много MAC-адресов или он помечен как транк — устройство подключено не сюда, а дальше по сети'))}">uplink${r.mac_count ? ` · ${esc(r.mac_count)} MAC` : ''}</span>`
            : '';
        return `<a class="ns-item${r.uplink ? ' is-uplink' : ''}" href="${href}">
                    <div class="ns-title">${title} ${uplink}</div>
                    <div class="ns-where">${where}</div>
                    ${extra.length ? `<div class="ns-extra">${extra.join(' · ')}</div>` : ''}
                </a>`;
    }

    function setFocus(i) {
        const items = [...box.querySelectorAll('.ns-item')];
        items.forEach(el => el.classList.remove('is-focused'));
        if (!items.length) { focused = -1; return; }
        focused = (i + items.length) % items.length;
        items[focused].classList.add('is-focused');
        items[focused].scrollIntoView({ block: 'nearest' });
    }

    function search(q) {
        lastQuery = q;
        fetch(`/api/search?q=${encodeURIComponent(q)}`)
            .then(r => r.json())
            .then(results => {
                if (q !== lastQuery) return;  // пришёл ответ на устаревший запрос
                box.innerHTML = results.length
                    ? results.map(resultHtml).join('')
                    : `<div class="ns-empty">${t('Ничего не найдено. Поиск идёт по данным SNMP-опросов — опросите коммутаторы или включите периодический опрос в настройках.')}</div>`;
                focused = -1;
                box.hidden = false;
            })
            .catch(() => {
                box.innerHTML = `<div class="ns-empty">${t('Ошибка поиска')}</div>`;
                box.hidden = false;
            });
    }

    input.addEventListener('input', () => {
        clearTimeout(timer);
        const q = input.value.trim();
        if (q.length < 2) {
            lastQuery = '';
            box.hidden = true;
            return;
        }
        timer = setTimeout(() => search(q), 220);
    });
    input.addEventListener('keydown', e => {
        if (e.key === 'Escape') { box.hidden = true; input.blur(); }
        if (e.key === 'ArrowDown') { e.preventDefault(); setFocus(focused + 1); }
        if (e.key === 'ArrowUp') { e.preventDefault(); setFocus(focused - 1); }
        if (e.key === 'Enter') {
            const items = box.querySelectorAll('.ns-item');
            const target = items[focused >= 0 ? focused : 0];
            if (!box.hidden && target) target.click();
        }
    });
    input.addEventListener('focus', () => { if (box.innerHTML && input.value.trim().length >= 2) box.hidden = false; });
    document.addEventListener('click', e => {
        if (!e.target.closest('.net-search')) box.hidden = true;
    });
    // Ctrl+K / Cmd+K или «/» — перейти к поиску
    document.addEventListener('keydown', e => {
        const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '');
        // «л» — та же клавиша K в русской раскладке
        if ((e.key === 'k' || e.key === 'K' || e.key === 'л' || e.key === 'Л') && (e.ctrlKey || e.metaKey)) {  // i18n: ignore
            e.preventDefault();
            input.focus();
            input.select();
        } else if (e.key === '/' && !typing) {
            e.preventDefault();
            input.focus();
        }
    });
})();

// Выпадающее меню у края узкого экрана сдвигается внутрь, а не уходит за край
function keepInViewport(el, gap = 8) {
    if (!el) return;
    el.style.translate = '';
    const r = el.getBoundingClientRect();
    let dx = 0;
    if (r.right > window.innerWidth - gap) dx = window.innerWidth - gap - r.right;
    if (r.left + dx < gap) dx = gap - r.left;
    if (dx) el.style.translate = `${Math.round(dx)}px 0`;
}

// ───────── Выпадающие меню: <div class="menu-wrap"><button data-menu-toggle>…</button><div class="dropdown">… ─────────
document.addEventListener('click', e => {
    const toggle = e.target.closest('[data-menu-toggle]');
    document.querySelectorAll('.menu-wrap.open').forEach(w => {
        if (!toggle || !w.contains(toggle)) w.classList.remove('open');
    });
    if (toggle) {
        e.preventDefault();
        const wrap = toggle.closest('.menu-wrap');
        wrap.classList.toggle('open');
        if (wrap.classList.contains('open')) keepInViewport(wrap.querySelector('.dropdown'));
    } else if (e.target.closest('.dropdown a, .dropdown button')) {
        e.target.closest('.menu-wrap')?.classList.remove('open');
    }
});

// ───────── Общие обработчики ─────────
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        closeSettingsModal();
        closePasswordModal();
        document.querySelectorAll('.menu-wrap.open').forEach(w => w.classList.remove('open'));
    }
});

// ───────── Загрузка внешних скриптов по требованию ─────────
const _scriptPromises = {};

// integrity — контрольная сумма SRI (sha384-…): подменённый на CDN файл браузер не выполнит
function loadScript(src, integrity) {
    if (!_scriptPromises[src]) {
        _scriptPromises[src] = new Promise((resolve, reject) => {
            const existing = [...document.scripts].find(s => s.src === src);
            const el = existing || document.createElement('script');
            const done = () => resolve();
            const fail = () => { delete _scriptPromises[src]; reject(new Error(t('Не удалось загрузить {src}', { src }))); };
            if (existing && existing.dataset.loaded) return resolve();
            el.addEventListener('load', () => { el.dataset.loaded = '1'; done(); });
            el.addEventListener('error', fail);
            if (!existing) {
                if (integrity) {
                    el.integrity = integrity;
                    el.crossOrigin = 'anonymous';
                }
                el.src = src;
                el.async = true;
                document.head.appendChild(el);
            }
        });
    }
    return _scriptPromises[src];
}

// Ждём глобальную переменную библиотеки (скрипт уже подключён с async) — не дольше timeoutMs
function waitForGlobal(name, timeoutMs = 15000) {
    return new Promise(resolve => {
        if (window[name]) return resolve(true);
        const started = Date.now();
        const timer = setInterval(() => {
            if (window[name] || Date.now() - started > timeoutMs) {
                clearInterval(timer);
                resolve(!!window[name]);
            }
        }, 100);
    });
}

// Размер в байтах → «1.4 МБ»
function formatBytes(n) {
    const units = [t('Б'), t('КБ'), t('МБ'), t('ГБ')];
    if (!n) return '0 ' + units[0];
    const i = Math.min(units.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
    return `${(n / 1024 ** i).toFixed(i ? 1 : 0)} ${units[i]}`;
}

// ───────── Поля SNMP (шаблон _snmp.html) ─────────
function syncSnmpFields(root) {
    const v3 = root.querySelector('[data-snmp-version]').value === '3';
    root.querySelectorAll('[data-snmp-v2]').forEach(el => { el.hidden = v3; });
    root.querySelectorAll('[data-snmp-v3]').forEach(el => { el.hidden = !v3; });
    // Без аутентификации шифрование невозможно (RFC 3414) — поля блокируются
    const auth = root.querySelector('[data-snmp-auth]');
    const priv = root.querySelector('[data-snmp-priv]');
    const noAuth = auth.value === 'none';
    root.querySelector('[name="snmp_v3_auth_key"]').disabled = noAuth;
    if (noAuth) priv.value = 'none';
    priv.disabled = noAuth;
    root.querySelector('[name="snmp_v3_priv_key"]').disabled = priv.value === 'none';
}

function initSnmpFields(scope = document) {
    scope.querySelectorAll('[data-snmp]').forEach(root => {
        if (root.dataset.ready) return;
        root.dataset.ready = '1';
        root.addEventListener('change', () => syncSnmpFields(root));
        syncSnmpFields(root);
    });
}

// Значения полей SNMP объектом (для JSON-запросов). Заблокированные поля не отправляем.
function snmpValues(root) {
    const out = {};
    root.querySelectorAll('[name^="snmp_"]').forEach(el => { if (!el.disabled) out[el.name] = el.value.trim(); });
    if (out.snmp_version !== '3') Object.keys(out).filter(k => k.startsWith('snmp_v3_')).forEach(k => delete out[k]);
    return out;
}

// Ошибка настроек SNMPv3 до отправки на сервер — те же правила, что на сервере
function snmpValidationError(values) {
    if (values.snmp_version !== '3') return '';
    if (!values.snmp_v3_user) return t('SNMPv3: укажите пользователя');
    if (values.snmp_v3_auth_proto !== 'none' && (values.snmp_v3_auth_key || '').length < 8) return t('SNMPv3: пароль аутентификации — не короче 8 символов');
    if (values.snmp_v3_priv_proto && values.snmp_v3_priv_proto !== 'none' && (values.snmp_v3_priv_key || '').length < 8) return t('SNMPv3: пароль шифрования — не короче 8 символов');
    return '';
}

// «Проверить и заполнить» в форме добавления: опрос по SNMP, подстановка имени, портов и модели
async function probeSwitchForm(form, btn) {
    const field = name => form.querySelector(`[name="${name}"]`);
    const box = form.querySelector('[data-probe-result]');
    const values = { ip_address: field('ip_address').value.trim(), ...snmpValues(form.querySelector('[data-snmp]')) };
    const show = (cls, html) => { box.className = 'probe-result ' + cls; box.innerHTML = html; box.hidden = false; };
    if (!values.ip_address) { show('is-error', t('Сначала укажите IP-адрес.')); field('ip_address').focus(); return; }
    const invalid = snmpValidationError(values);
    if (invalid) { show('is-error', eventsEscape(invalid)); return; }
    btn.classList.add('is-loading');
    try {
        const r = await (await fetch('/api/snmp_probe', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(values) })).json();
        if (!r.ok) { show('is-error', `<b>${t('Нет ответа по SNMP.')}</b> ${eventsEscape(r.error)}`); return; }
        const filled = [];
        if (r.sys_name && !field('name').value.trim()) { field('name').value = r.sys_name; filled.push(t('название')); }
        if (r.ports) { field('ports').value = Math.min(96, r.ports); filled.push(t('число портов')); }
        if (field('model')) field('model').value = r.model_label || '';
        show(r.existing ? 'is-warning' : 'is-ok', `
            ${t('<b>{name}</b> отвечает ({auth})', { name: eventsEscape(r.sys_name || values.ip_address), auth: eventsEscape(r.auth) })}
            ${r.model_label ? `<div class="muted">${eventsEscape(r.model_label)}</div>` : ''}
            <div class="muted">${t('Ethernet-портов: {n}', { n: r.ports || '—' })}${r.location ? ' · ' + eventsEscape(r.location) : ''}</div>
            ${filled.length ? `<div>${t('Заполнено: {fields}.', { fields: filled.join(', ') })}</div>` : ''}
            ${r.existing ? `<div><b>${t('Этот IP уже добавлен:')}</b> <a href="/switch/${r.existing.id}">${eventsEscape(r.existing.name)}</a></div>` : ''}`);
    } catch (err) {
        show('is-error', t('Не удалось связаться с сервером'));
    } finally {
        btn.classList.remove('is-loading');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initSnmpFields();
    updateThemeButton();
    const settings = document.getElementById('settingsModal');
    if (settings) settings.addEventListener('click', e => { if (e.target === settings) closeSettingsModal(); });
    refreshUnreadBadge();
    setInterval(refreshUnreadBadge, 20000);
});
