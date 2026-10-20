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
    btn.dataset.label = dark ? 'Светлая тема' : 'Тёмная тема';
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
function confirmDialog(message, { title = 'Подтверждение', okText = 'OK', danger = false } = {}) {
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
        })
        .catch(() => notify('Не удалось загрузить настройки', 'error'));
    document.getElementById('settingsModal').classList.add('active');
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.remove('active');
}

function saveSettings() {
    const poll_enabled = document.getElementById('pollEnabledInput').checked;
    let poll_interval_minutes = parseInt(document.getElementById('pollIntervalInput').value, 10);
    if (!poll_interval_minutes || poll_interval_minutes < 1) poll_interval_minutes = 1;

    const body = { poll_enabled, poll_interval_minutes };
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
            closeSettingsModal();
            notify('Настройки сохранены', 'success');
        })
        .catch(() => notify('Не удалось сохранить настройки', 'error'));
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
        notify('Новые пароли не совпадают', 'error');
        return;
    }
    try {
        const r = await (await fetch('/api/account/password', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ current, password })
        })).json();
        if (!r.ok) throw new Error(r.error);
        closePasswordModal();
        notify('Пароль изменён', 'success');
    } catch (err) {
        notify(err.message || 'Не удалось сменить пароль', 'error');
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
            if (r.kind === 'device') extra.push('привязано вручную' + (r.notes ? `: ${esc(r.notes)}` : ''));
            if (r.vlan) extra.push(`VLAN ${esc(r.vlan)}`);
            if (r.last_seen) extra.push(`видели ${esc(r.last_seen)}`);
        }
        const where = `${esc(r.switch_name)} → ${r.port ? `порт ${esc(r.port)}` : 'порт не сопоставлен'}` +
                      (r.port_name ? ` (${esc(r.port_name)})` : '');
        const uplink = r.uplink
            ? `<span class="ns-badge ns-uplink" title="На этом порту видно много MAC-адресов или он помечен как транк — устройство подключено не сюда, а дальше по сети">uplink${r.mac_count ? ` · ${esc(r.mac_count)} MAC` : ''}</span>`
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
                    : '<div class="ns-empty">Ничего не найдено. Поиск идёт по данным SNMP-опросов — опросите коммутаторы или включите периодический опрос в настройках.</div>';
                focused = -1;
                box.hidden = false;
            })
            .catch(() => {
                box.innerHTML = '<div class="ns-empty">Ошибка поиска</div>';
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
        if ((e.key === 'k' || e.key === 'K' || e.key === 'л' || e.key === 'Л') && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            input.focus();
            input.select();
        } else if (e.key === '/' && !typing) {
            e.preventDefault();
            input.focus();
        }
    });
})();

// ───────── Выпадающие меню: <div class="menu-wrap"><button data-menu-toggle>…</button><div class="dropdown">… ─────────
document.addEventListener('click', e => {
    const toggle = e.target.closest('[data-menu-toggle]');
    document.querySelectorAll('.menu-wrap.open').forEach(w => {
        if (!toggle || !w.contains(toggle)) w.classList.remove('open');
    });
    if (toggle) {
        e.preventDefault();
        toggle.closest('.menu-wrap').classList.toggle('open');
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

function loadScript(src) {
    if (!_scriptPromises[src]) {
        _scriptPromises[src] = new Promise((resolve, reject) => {
            const existing = [...document.scripts].find(s => s.src === src);
            const el = existing || document.createElement('script');
            const done = () => resolve();
            const fail = () => { delete _scriptPromises[src]; reject(new Error('Не удалось загрузить ' + src)); };
            if (existing && existing.dataset.loaded) return resolve();
            el.addEventListener('load', () => { el.dataset.loaded = '1'; done(); });
            el.addEventListener('error', fail);
            if (!existing) {
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
    if (!n) return '0 Б';
    const units = ['Б', 'КБ', 'МБ', 'ГБ'];
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
    if (!values.snmp_v3_user) return 'SNMPv3: укажите пользователя';
    if (values.snmp_v3_auth_proto !== 'none' && (values.snmp_v3_auth_key || '').length < 8) return 'SNMPv3: пароль аутентификации — не короче 8 символов';
    if (values.snmp_v3_priv_proto && values.snmp_v3_priv_proto !== 'none' && (values.snmp_v3_priv_key || '').length < 8) return 'SNMPv3: пароль шифрования — не короче 8 символов';
    return '';
}

// «Проверить и заполнить» в форме добавления: опрос по SNMP, подстановка имени, портов и модели
async function probeSwitchForm(form, btn) {
    const field = name => form.querySelector(`[name="${name}"]`);
    const box = form.querySelector('[data-probe-result]');
    const values = { ip_address: field('ip_address').value.trim(), ...snmpValues(form.querySelector('[data-snmp]')) };
    const show = (cls, html) => { box.className = 'probe-result ' + cls; box.innerHTML = html; box.hidden = false; };
    if (!values.ip_address) { show('is-error', 'Сначала укажите IP-адрес.'); field('ip_address').focus(); return; }
    const invalid = snmpValidationError(values);
    if (invalid) { show('is-error', eventsEscape(invalid)); return; }
    btn.classList.add('is-loading');
    try {
        const r = await (await fetch('/api/snmp_probe', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(values) })).json();
        if (!r.ok) { show('is-error', `<b>Нет ответа по SNMP.</b> ${eventsEscape(r.error)}`); return; }
        const filled = [];
        if (r.sys_name && !field('name').value.trim()) { field('name').value = r.sys_name; filled.push('название'); }
        if (r.ports) { field('ports').value = Math.min(96, r.ports); filled.push('число портов'); }
        if (field('model')) field('model').value = r.model_label || '';
        show(r.existing ? 'is-warning' : 'is-ok', `
            <b>${eventsEscape(r.sys_name || values.ip_address)}</b> отвечает (${eventsEscape(r.auth)})
            ${r.model_label ? `<div class="muted">${eventsEscape(r.model_label)}</div>` : ''}
            <div class="muted">Ethernet-портов: ${r.ports || '—'}${r.location ? ' · ' + eventsEscape(r.location) : ''}</div>
            ${filled.length ? `<div>Заполнено: ${filled.join(', ')}.</div>` : ''}
            ${r.existing ? `<div><b>Этот IP уже добавлен:</b> <a href="/switch/${r.existing.id}">${eventsEscape(r.existing.name)}</a></div>` : ''}`);
    } catch (err) {
        show('is-error', 'Не удалось связаться с сервером');
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
