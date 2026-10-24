// Страница коммутатора: схема портов, редактирование, SNMP, статистика.
// Данные страницы (SWITCH_ID, SWITCH_IP, SNMP_CFG, SAVED_DEVICES, SWITCH_DATA) задаёт шаблон switch_view.html.

const sidebar = document.getElementById("sidebar");
const form = document.getElementById("mainForm");
// Форма сохраняется только из saveChanges() через form.submit() — он не вызывает событие submit.
// Любую другую отправку (Enter в поле ввода, кнопка без type="button") блокируем:
// скрытые поля в этот момент пустые, и сервер затёр бы подключения, типы портов и IP.
form.addEventListener("submit", e => e.preventDefault());
const editIndicator = document.getElementById("editIndicator");
const rackContainer = document.getElementById("rackContainer");

function safeParsePatchPanels(value) {
    if (!value) return [];
    if (Array.isArray(value)) {
        return value.map(p => ({ ...p, layout: p.layout || 'single' }));
    }
    if (typeof value === 'string') {
        try {
            const parsed = JSON.parse(value);
            if (Array.isArray(parsed)) {
                return parsed.map(p => ({ ...p, layout: p.layout || 'single' }));
            }
        } catch (e) {
            console.error('Error parsing patch_panels:', e);
        }
    }
    return [];
}

function safeParseJSON(value, defaultValue = {}) {
    try {
        if (value === null || value === undefined || value === '') return defaultValue;
        const parsed = typeof value === 'string' ? JSON.parse(value) : value;
        return parsed || defaultValue;
    } catch (e) {
        console.error('Error parsing JSON:', e);
        return defaultValue;
    }
}

const INITIAL_STATE = {
    // Все значения проходят через |tojson: так они безопасно попадают в JS
    switchPortsCount: parseInt(SWITCH_DATA.ports) || 24,
    patchPanels: safeParsePatchPanels(SWITCH_DATA.patch_panels),
    connections: safeParseJSON(SWITCH_DATA.connections, {}),
    layout: (SWITCH_DATA.layout || 'single'),
    portTypes: safeParseJSON(SWITCH_DATA.port_types, {}),
    trunkPorts: safeParseJSON(SWITCH_DATA.trunk_ports, {}),
    portVlans: safeParseJSON(SWITCH_DATA.port_vlans, {}),
    vlanColors: safeParseJSON(SWITCH_DATA.vlan_colors, {})
};

let state = {
    switchPortsCount: INITIAL_STATE.switchPortsCount,
    patchPanels: JSON.parse(JSON.stringify(
        typeof INITIAL_STATE.patchPanels === 'string' ? JSON.parse(INITIAL_STATE.patchPanels) : INITIAL_STATE.patchPanels
    )),
    connections: (() => {
        const conns = JSON.parse(JSON.stringify(INITIAL_STATE.connections));
        for (let portNum in conns) {
            if (conns[portNum] && conns[portNum].patchPanel === undefined) {
                conns[portNum].patchPanel = 1; 
            }
        }
        return conns;
    })(),
    layout: INITIAL_STATE.layout,
    portTypes: JSON.parse(JSON.stringify(INITIAL_STATE.portTypes)),
    trunkPorts: JSON.parse(JSON.stringify(INITIAL_STATE.trunkPorts)),
    portVlans: JSON.parse(JSON.stringify(INITIAL_STATE.portVlans)),
    vlanColors: JSON.parse(JSON.stringify(INITIAL_STATE.vlanColors))
};

let selectedSwitchPort = null;
let editMode = false;
let vlanFilter = "";
let nextPatchPanelId = Math.max(...state.patchPanels.map(p => p.id), 0) + 1;

const tooltip = document.getElementById("tooltip");
const layoutSelect = document.getElementById("layoutSelect");
const portCountInput = document.getElementById("portCountInput");
const nameInput = document.getElementById("nameInput");
const editBtn = document.getElementById("editBtn");
const saveBtn = document.getElementById("saveBtn");
const cancelBtn = document.getElementById("cancelBtn");

layoutSelect.value = state.layout;
portCountInput.value = state.switchPortsCount;

function toggleMenu() { sidebar.classList.toggle("open"); }

function toggleSection(sectionId) {
    const content = document.getElementById(`content-${sectionId}`);
    const arrow = document.getElementById(`arrow-${sectionId}`);
    content.classList.toggle("open");
    arrow.classList.toggle("open");
}

function toggleEdit() {
    editMode = true;
    sidebar.classList.add("open");
    const sw = document.getElementById("content-switch");
    if (!sw.classList.contains("open")) toggleSection("switch");
    updateUIForEditMode();
    renderConnectionsList();
    renderPatchPanelsList();
}

function cancelEdit() {
    editMode = false;
    state.switchPortsCount = INITIAL_STATE.switchPortsCount;
    state.layout = INITIAL_STATE.layout;
    state.connections = JSON.parse(JSON.stringify(INITIAL_STATE.connections));
    state.portTypes = JSON.parse(JSON.stringify(INITIAL_STATE.portTypes));
    state.trunkPorts = JSON.parse(JSON.stringify(INITIAL_STATE.trunkPorts));
    state.portVlans = JSON.parse(JSON.stringify(INITIAL_STATE.portVlans));
    state.vlanColors = JSON.parse(JSON.stringify(INITIAL_STATE.vlanColors));
    state.patchPanels = JSON.parse(JSON.stringify(
        typeof INITIAL_STATE.patchPanels === 'string' ? JSON.parse(INITIAL_STATE.patchPanels) : INITIAL_STATE.patchPanels
    ));
    portCountInput.value = state.switchPortsCount;
    layoutSelect.value = state.layout;
    resetSnmpFields();
    updateUIForEditMode();
    renderRack();
    renderConnectionsList();
    renderPatchPanelsList();
}

// ─── Настройки SNMP (v2c / v3) ───
const SNMP_FIELD_IDS = ['snmpV3User', 'snmpV3AuthKey', 'snmpV3PrivKey', 'snmpV3Context'];
const SNMP_SELECT_IDS = ['snmpVersionSelect', 'snmpV3AuthProto', 'snmpV3PrivProto'];

function resetSnmpFields() {
    document.getElementById('snmpVersionSelect').value = SNMP_CFG.version;
    document.getElementById('snmpV3AuthProto').value = SNMP_CFG.auth_proto;
    document.getElementById('snmpV3PrivProto').value = SNMP_CFG.priv_proto;
    document.getElementById('snmpV3AuthKey').value = '';
    document.getElementById('snmpV3PrivKey').value = '';
    updateSnmpFieldsVisibility();
}

function updateSnmpFieldsVisibility() {
    const v3 = document.getElementById('snmpVersionSelect').value === '3';
    document.getElementById('snmpV2Fields').hidden = v3;
    document.getElementById('snmpV3Fields').hidden = !v3;
}

// Та же проверка, что и на сервере (RFC 3414): возвращает текст ошибки или ''
function validateSnmpFields() {
    if (document.getElementById('snmpVersionSelect').value !== '3') return '';
    const user = document.getElementById('snmpV3User').value.trim();
    const authProto = document.getElementById('snmpV3AuthProto').value;
    const privProto = document.getElementById('snmpV3PrivProto').value;
    const authKey = document.getElementById('snmpV3AuthKey').value;
    const privKey = document.getElementById('snmpV3PrivKey').value;
    if (!user) return t('SNMPv3: укажите имя пользователя');
    if (authProto === 'none' && privProto !== 'none') return t('SNMPv3: шифрование нельзя включить без аутентификации');
    if (authProto !== 'none' && (authKey ? authKey.length < 8 : !SNMP_CFG.has_auth_key))
        return t('SNMPv3: пароль аутентификации должен быть не короче 8 символов');
    if (privProto !== 'none' && (privKey ? privKey.length < 8 : !SNMP_CFG.has_priv_key))
        return t('SNMPv3: пароль шифрования должен быть не короче 8 символов');
    return '';
}

function setHiddenField(name, value) {
    let field = form.querySelector(`input[type="hidden"][name="${name}"]`);
    if (!field) {
        field = document.createElement('input');
        field.type = 'hidden';
        field.name = name;
        form.appendChild(field);
    }
    field.value = value;
}

function testSNMP() {
    const box = document.getElementById('snmpTestResult');
    const btn = document.getElementById('snmpTestBtn');
    box.hidden = false;
    box.className = 'snmp-test-result';
    if (editMode) {
        box.textContent = t('Проверяются сохранённые настройки — сначала нажмите «Сохранить».');
        return;
    }
    btn.disabled = true;
    box.textContent = t('Проверяю…');
    fetch(`/api/snmp_test/${SWITCH_ID}`, { method: 'POST' })
        .then(r => r.json())
        .then(d => {
            box.className = 'snmp-test-result ' + (d.ok ? 'ok' : 'fail');
            box.textContent = d.ok
                ? t('Успешно · {auth}: {sys_name}{v}', { auth: d.auth, sys_name: d.sys_name, v: d.sys_descr ? ' — ' + d.sys_descr : '' })
                : t('Ошибка · {v}{error}', { v: d.auth ? d.auth + ': ' : '', error: d.error });
        })
        .catch(() => { box.className = 'snmp-test-result fail'; box.textContent = t('Ошибка · нет связи с приложением'); })
        .finally(() => { btn.disabled = false; });
}

function saveChanges() {
    const snmpError = validateSnmpFields();
    if (snmpError) {
        notify(snmpError, 'error');
        return;
    }
    let newCount = parseInt(portCountInput.value);
    if (!newCount || newCount < 1) newCount = 1;
    if (newCount > 96) newCount = 96;
    state.switchPortsCount = newCount;
    state.layout = layoutSelect.value;
    for (let sw in state.connections) {
        if (parseInt(sw) > state.switchPortsCount) delete state.connections[sw];
    }
    updateHiddenFields();

    const ip = (document.getElementById('ipInput') || {}).value || '';
    const snmp = (document.getElementById('snmpInput') || {}).value || 'public';
    let ipField = document.getElementById('ipHidden');
    let snmpField = document.getElementById('snmpHidden');
    if (!ipField) {
        ipField = document.createElement('input');
        ipField.type = 'hidden'; ipField.name = 'ip_address'; ipField.id = 'ipHidden';
        form.appendChild(ipField);
    }
    if (!snmpField) {
        snmpField = document.createElement('input');
        snmpField.type = 'hidden'; snmpField.name = 'snmp_community'; snmpField.id = 'snmpHidden';
        form.appendChild(snmpField);
    }
    ipField.value = ip;
    snmpField.value = snmp;

    // SNMPv3: пустой пароль на сервере означает «оставить сохранённый»
    setHiddenField('snmp_version', document.getElementById('snmpVersionSelect').value);
    setHiddenField('snmp_v3_user', document.getElementById('snmpV3User').value.trim());
    setHiddenField('snmp_v3_auth_proto', document.getElementById('snmpV3AuthProto').value);
    setHiddenField('snmp_v3_auth_key', document.getElementById('snmpV3AuthKey').value);
    setHiddenField('snmp_v3_priv_proto', document.getElementById('snmpV3PrivProto').value);
    setHiddenField('snmp_v3_priv_key', document.getElementById('snmpV3PrivKey').value);
    setHiddenField('snmp_v3_context', document.getElementById('snmpV3Context').value.trim());

    form.submit();
}

function updateUIForEditMode() {
    portCountInput.readOnly = !editMode;
    nameInput.readOnly = !editMode;
    layoutSelect.disabled = !editMode;
    document.getElementById("addPatchPanelBtn").disabled = !editMode;

    const ipInput = document.getElementById('ipInput');
    const snmpInput = document.getElementById('snmpInput');
    if (ipInput) ipInput.readOnly = !editMode;
    if (snmpInput) snmpInput.readOnly = !editMode;
    SNMP_FIELD_IDS.forEach(id => { document.getElementById(id).readOnly = !editMode; });
    SNMP_SELECT_IDS.forEach(id => { document.getElementById(id).disabled = !editMode; });

    if (editMode) {
        editBtn.hidden = true;
        saveBtn.hidden = false;
        cancelBtn.hidden = false;
        editIndicator.classList.add("active");
    } else {
        editBtn.hidden = false;
        saveBtn.hidden = true;
        cancelBtn.hidden = true;
        editIndicator.classList.remove("active");
    }
}

function renderRack() {
    rackContainer.innerHTML = "";
    let devices = [];
    state.patchPanels.filter(p => p.position === 'above').forEach(panel => {
        devices.push({ type: 'patch', data: panel });
    });
    devices.push({ type: 'switch', data: null });
    state.patchPanels.filter(p => p.position === 'below').forEach(panel => {
        devices.push({ type: 'patch', data: panel });
    });
    
    devices.forEach(device => {
        if (device.type === 'switch') renderSwitch();
        else renderPatchPanel(device.data);
    });
    
    restoreConnections();
    renderDeviceBadges(); // Обязательно перерисовываем бейджики после ререндера стойки
}

function renderSwitch() {
    const div = document.createElement("div");
    div.className = "device switch";
    // Больше 24 портов в ряду (48+4 в два ряда) — порты компактнее, чтобы ряд не переносился
    if ((state.layout === "double" ? Math.ceil(state.switchPortsCount / 2) : state.switchPortsCount) > 24) div.classList.add("dense");
    div.innerHTML = `<h3>${escapeHtml(t('Коммутатор'))}</h3><div id="switchPorts"></div>`;
    rackContainer.appendChild(div);
    const switchContainer = document.getElementById("switchPorts");
    
    if (state.layout === "double") {
        let row1 = document.createElement("div");
        let row2 = document.createElement("div");
        row1.className = "ports-row";
        row2.className = "ports-row";

        for (let i = 1; i <= state.switchPortsCount; i++) {
            let isTop = (i % 2 === 1); // Нечетные сверху
            let port = createSwitchPort(i, isTop);
            if (isTop) row1.appendChild(port);
            else row2.appendChild(port);
        }
        switchContainer.appendChild(row1);
        switchContainer.appendChild(row2);
    } else {
        let row = document.createElement("div");
        row.className = "ports-row";
        for (let i = 1; i <= state.switchPortsCount; i++) {
            row.appendChild(createSwitchPort(i, false)); // false = номер порта снизу
        }
        switchContainer.appendChild(row);
    }
}

function renderPatchPanel(panel) {
    const div = document.createElement("div");
    div.className = "device";
    if (((panel.layout || 'single') === "double" ? Math.ceil(panel.ports / 2) : panel.ports) > 24) div.classList.add("dense");
    div.innerHTML = `<h3>${escapeHtml(panel.name)}</h3><div id="patchPorts-${panel.id}"></div>`;
    rackContainer.appendChild(div);
    const patchContainer = document.getElementById(`patchPorts-${panel.id}`);
    
    if ((panel.layout || 'single') === "double") {
        let row1 = document.createElement("div");
        let row2 = document.createElement("div");
        row1.className = "ports-row";
        row2.className = "ports-row";

        for (let i = 1; i <= panel.ports; i++) {
            let isTop = (i % 2 === 1);
            let port = createPatchPort(panel.id, i, isTop);
            if (isTop) row1.appendChild(port);
            else row2.appendChild(port);
        }
        patchContainer.appendChild(row1);
        patchContainer.appendChild(row2);
    } else {
        let row = document.createElement("div");
        row.className = "ports-row";
        for (let i = 1; i <= panel.ports; i++) {
            row.appendChild(createPatchPort(panel.id, i, false));
        }
        patchContainer.appendChild(row);
    }
}

function createSwitchPort(i, isTop) {
    let container = document.createElement("div");
    container.className = "port-container";

    let label = document.createElement("div");
    label.className = "port-label";
    label.innerText = i;

    if (state.trunkPorts[i]) {
        let tBadge = document.createElement("span");
        tBadge.className = "trunk-label";
        tBadge.innerText = "T";
        label.appendChild(tBadge);
    }

    let div = document.createElement("div");
    const type = state.portTypes[i] || 'rj45';
    div.className = "port" + (type === 'sfp' ? ' sfp' : '');
    div.dataset.port = i;
    div.dataset.type = "switch";

    const vlanInfo = state.portVlans[i];
    if (vlanInfo && vlanInfo.id) {
        let vlanTag = document.createElement("span");
        vlanTag.className = "vlan-tag";
        vlanTag.style.background = state.vlanColors[vlanInfo.id] || '#666';
        vlanTag.title = `VLAN ${vlanInfo.id}${vlanInfo.name ? ' — ' + vlanInfo.name : ''}`;
        div.appendChild(vlanTag);
    }
    if (vlanFilter && (!vlanInfo || String(vlanInfo.id) !== String(vlanFilter))) {
        div.classList.add("vlan-dimmed");
    }

    div.onclick = () => {
        if (!editMode) return;
        selectedSwitchPort = i;
        document.querySelectorAll(".port[data-type='switch']").forEach(p => p.classList.remove("port-selected"));
        div.classList.add("port-selected");
    };

    div.oncontextmenu = (e) => {
        if (!editMode) return;
        e.preventDefault();
        selectedSwitchPort = i;
        showPortTypeMenu(e.clientX, e.clientY, i);
    };

    if (isTop) {
        container.appendChild(label);
        container.appendChild(div);
    } else {
        container.appendChild(div);
        container.appendChild(label);
    }

    return container;
}

function createPatchPort(panelId, portNum, isTop) {
    let container = document.createElement("div");
    container.className = "port-container";

    let label = document.createElement("div");
    label.className = "port-label";
    label.innerText = portNum;

    let div = document.createElement("div");
    div.className = "port";
    div.dataset.port = portNum;
    div.dataset.panel = panelId;
    div.dataset.type = "patch";

    div.onclick = () => connectPorts(panelId, portNum);

    if (isTop) {
        container.appendChild(label);
        container.appendChild(div);
    } else {
        container.appendChild(div);
        container.appendChild(label);
    }

    return container;
}

// Поля «назначение + цвет кабеля» для окна соединения
function connectionFields(name, color, label) {
    return [
        { name: 'name', label: label || t('Куда уходит сеть'), value: name || '', required: true, maxlength: 200,
          placeholder: t('например, «Бухгалтерия, ПК-3»') },
        { name: 'color', label: t('Цвет кабеля'), type: 'cable-color', value: color || 'gray' },
    ];
}

async function connectPorts(patchPanelId, patchPort) {
    if (!editMode || selectedSwitchPort === null) return;
    const swPort = selectedSwitchPort;
    const panel = state.patchPanels.find(p => p.id == patchPanelId);
    // Подсказываем описание порта с коммутатора (ifAlias), если оно есть
    const r = await formDialog({
        title: t('Новое соединение'),
        note: t('Порт {sw} коммутатора → «{panel}», порт {patch}', { sw: swPort, panel: panel ? panel.name : patchPanelId, patch: patchPort }),
        okText: t('Соединить'),
        fields: connectionFields(portAlias(swPort), 'gray'),
    });
    if (!r) return;
    const name = r.name, color = r.color;

    state.connections[swPort] = {
        patchPanel: patchPanelId,
        patch: patchPort,
        color: color,
        name: name
    };

    selectedSwitchPort = null;
    document.querySelectorAll(".port[data-type='switch']").forEach(p => p.classList.remove("port-selected"));
    restoreConnections();
    renderConnectionsList();
}

// Цвет подключения на порту (important — чтобы перекрыть любые стили состояния порта).
function paintPort(el, color) {
    if (color) el.style.setProperty("background", color, "important");
    else el.style.removeProperty("background");
}

function restoreConnections() {
    document.querySelectorAll(".port").forEach(p => {
        paintPort(p, null);
        p.onmouseenter = null;
        p.onmouseleave = null;
        p.onmousemove = null;
    });

    for (let sw in state.connections) {
        let data = state.connections[sw];
        if (!data) continue;

        let swEl = document.querySelector(`.port[data-type='switch'][data-port="${sw}"]`);
        if (!swEl) continue;

        function show(e) {
            showPortTooltip(e, [data.name, ...portInfoLines(sw)]);
        }

        if (data.patchPanel === null) {
            function highlightDirect() { paintPort(swEl, data.color); }
            function clearDirect() { paintPort(swEl, null); tooltip.style.opacity = 0; }
            swEl.onmouseenter = highlightDirect;
            swEl.onmouseleave = clearDirect;
            swEl.onmousemove = show;
        } else {
            let patchEl = document.querySelector(`.port[data-type='patch'][data-panel="${data.patchPanel}"][data-port="${data.patch}"]`);
            if (!patchEl) continue;

            function highlight() {
                paintPort(swEl, data.color);
                paintPort(patchEl, data.color);
            }
            function clear() {
                paintPort(swEl, null);
                paintPort(patchEl, null);
                tooltip.style.opacity = 0;
            }
            swEl.onmouseenter = highlight;
            patchEl.onmouseenter = highlight;
            swEl.onmouseleave = clear;
            patchEl.onmouseleave = clear;
            swEl.onmousemove = show;
            patchEl.onmousemove = show;
        }
    }
    applyPortLoad();
}

// ─── Загрузка портов (тепловая карта) и описания портов с коммутатора ───
// Данные — из последнего SNMP-опроса; ключ — номер порта на схеме.
let portLoad = {};
let loadThreshold = 80;
const LOAD_REFRESH_MS = 60000;

function showPortTooltip(e, lines) {
    const text = lines.filter(Boolean).join('\n');
    if (!text) return;
    tooltip.innerText = text;
    tooltip.style.opacity = 1;
    // tooltip — position: fixed, поэтому координаты окна, а не документа
    tooltip.style.left = Math.min(e.clientX + 12, window.innerWidth - tooltip.offsetWidth - 8) + "px";
    tooltip.style.top = (e.clientY + 12) + "px";
}

function formatPortSpeed(mbps) {
    if (!mbps) return '';
    return mbps >= 1000 ? t('{v} Гбит/с', { v: +(mbps / 1000).toFixed(1) }) : t('{mbps} Мбит/с', { mbps });
}

function portInfoLines(portNum) {
    const info = portLoad[portNum];
    if (!info) return [];
    const lines = [];
    if (info.alias) lines.push(`«${info.alias}»`);
    lines.push([info.name, formatPortSpeed(info.speed)].filter(Boolean).join(' · '));
    if (!info.up) {
        lines.push(t('Нет линка (down)'));
    } else if (typeof info.util === 'number') {
        lines.push(t('Загрузка {util}%: ↓ {in_mbps} · ↑ {out_mbps}', { util: info.util.toFixed(1), in_mbps: formatRate(info.in_mbps), out_mbps: formatRate(info.out_mbps) }));
    }
    if (info.errors_delta) lines.push(t('Ошибок с прошлого опроса: {errors_delta}', { errors_delta: info.errors_delta }));
    return lines;
}

function portAlias(portNum) {
    return (portLoad[portNum] || {}).alias || '';
}

function loadColor(util) {
    if (loadThreshold && util >= loadThreshold) return 'var(--load-4)';
    if (util >= 60) return 'var(--load-3)';
    if (util >= 30) return 'var(--load-2)';
    return 'var(--load-1)';
}

function isLoadShown() {
    const box = document.getElementById('loadToggle');
    return box ? box.checked : true;
}

function onLoadToggle() {
    try { localStorage.setItem('switchmap.showLoad', isLoadShown() ? '1' : '0'); } catch (e) { /* без localStorage */ }
    applyPortLoad();
}

function applyPortLoad() {
    const show = isLoadShown();
    document.getElementById('loadLegend').hidden = !show;
    document.querySelectorAll(".port[data-type='switch']").forEach(el => {
        const port = el.dataset.port;
        el.querySelector('.load-bar')?.remove();
        el.classList.remove('load-high', 'link-down');

        // Подсказка с описанием и загрузкой для портов без подключений
        // (у портов с подключениями её показывает restoreConnections)
        if (!el.onmousemove) {
            el.onmousemove = e => showPortTooltip(e, portInfoLines(port));
            el.onmouseleave = () => { tooltip.style.opacity = 0; };
        }

        const info = portLoad[port];
        if (!show || !info) return;
        if (!info.up) {
            el.classList.add('link-down');
            return;
        }
        if (typeof info.util === 'number') {
            const bar = document.createElement('span');
            bar.className = 'load-bar';
            bar.style.width = `calc((100% - 4px) * ${Math.max(0.06, Math.min(info.util, 100) / 100)})`;
            bar.style.background = loadColor(info.util);
            el.appendChild(bar);
            if (loadThreshold && info.util >= loadThreshold) el.classList.add('load-high');
        }
    });
}

function loadPortLoad() {
    return fetch(`/api/port_load/${SWITCH_ID}`)
        .then(r => r.json())
        .then(d => {
            if (d.error) return;
            portLoad = d.ports || {};
            loadThreshold = d.util_threshold || 0;
            document.getElementById('loadLegendThreshold').textContent = loadThreshold || '—';
            const times = Object.values(portLoad).map(p => p.time).filter(Boolean).sort();
            document.getElementById('loadLegendTime').textContent = times.length
                ? t('Данные опроса {v}', { v: times[times.length - 1] })
                : t('Нет данных — опросите коммутатор по SNMP');
            applyPortLoad();
            renderPortsTable();
        })
        .catch(() => {});
}

// ─── Таблица портов под схемой ───
let portsFilter = 'all';

function utilLevelColor(util) {
    return loadColor(util);
}

function renderPortsTable() {
    const body = document.getElementById('portsTableBody');
    const empty = document.getElementById('portsEmpty');
    const table = document.getElementById('portsTable');
    if (!body) return;
    const all = Object.entries(portLoad).sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
    document.getElementById('portsCount').textContent = all.length;
    empty.hidden = all.length > 0;
    table.parentElement.hidden = all.length === 0;

    const rows = all.filter(([, p]) =>
        portsFilter === 'up' ? p.up :
        portsFilter === 'down' ? !p.up :
        portsFilter === 'alerts' ? Object.keys(p.alerts || {}).length > 0 : true);

    body.innerHTML = rows.map(([port, p]) => {
        const conn = state.connections[port];
        const vlan = state.portVlans[port];
        const alerts = Object.keys(p.alerts || {});
        const status = !p.up
            ? `<span class="badge">${t('нет линка')}</span>`
            : alerts.length
                ? `<span class="badge badge-danger">${alerts.includes('util') ? t('перегрузка') : t('ошибки')}</span>`
                : `<span class="badge badge-success">${t('активен')}</span>`;
        const util = (p.up && typeof p.util === 'number')
            ? `<div class="util-inline"><div class="meter"><span style="width:${Math.min(p.util, 100)}%;background:${utilLevelColor(p.util)}"></span></div><span class="num">${p.util.toFixed(1)}%</span></div>`
            : '<span class="muted">—</span>';
        const desc = [p.alias ? escapeHtml(p.alias) : '', conn ? `<small>→ ${escapeHtml(conn.name)}</small>` : '']
            .filter(Boolean).join('') || '<span class="muted">—</span>';
        const vlanCell = vlan && vlan.id
            ? `<span class="vlan-chip"><i style="background:${escapeAttr(state.vlanColors[vlan.id] || 'var(--text-3)')}"></i>${escapeHtml(vlan.id)}${vlan.name ? ' · ' + escapeHtml(vlan.name) : ''}</span>`
            : '<span class="muted">—</span>';
        return `<tr data-port="${escapeAttr(port)}" title="${escapeAttr(t('Показать на схеме'))}">
            <td class="port-no">${escapeHtml(port)}</td>
            <td class="ifname">${escapeHtml(p.name || '')}</td>
            <td class="desc">${desc}</td>
            <td>${status}</td>
            <td class="col-optional num">${formatPortSpeed(p.speed) || '—'}</td>
            <td>${util}</td>
            <td class="col-optional num">${p.up ? formatRate(p.in_mbps) : '—'}</td>
            <td class="col-optional num">${p.up ? formatRate(p.out_mbps) : '—'}</td>
            <td class="col-optional num">${p.errors_delta ? `<span style="color:var(--danger)">${p.errors_delta}</span>` : '<span class="muted">0</span>'}</td>
            <td class="col-optional">${vlanCell}</td>
        </tr>`;
    }).join('') || t('<tr><td colspan="10" class="muted" style="text-align:center;padding:22px">Нет портов под выбранный фильтр</td></tr>');
}

document.getElementById('portsFilter')?.addEventListener('click', e => {
    const btn = e.target.closest('button[data-filter]');
    if (!btn) return;
    portsFilter = btn.dataset.filter;
    document.querySelectorAll('#portsFilter button').forEach(b => b.classList.toggle('is-active', b === btn));
    renderPortsTable();
});

document.getElementById('portsTableBody')?.addEventListener('click', e => {
    const row = e.target.closest('tr[data-port]');
    if (!row) return;
    const el = document.querySelector(`.port[data-type='switch'][data-port="${CSS.escape(row.dataset.port)}"]`);
    if (!el) return;
    el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' });
    el.classList.add('port-highlight');
    setTimeout(() => el.classList.remove('port-highlight'), 3000);
});

// Ссылка вида /switch/1?port=5 (из поиска или события) — подсвечиваем порт
function highlightPortFromUrl() {
    const port = new URLSearchParams(location.search).get('port');
    if (!port) return;
    const el = document.querySelector(`.port[data-type='switch'][data-port="${CSS.escape(port)}"]`);
    if (!el) return;
    el.classList.add('port-highlight');
    el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' });
    setTimeout(() => el.classList.remove('port-highlight'), 8000);
}

function renderConnectionsList() {
    const container = document.getElementById("connectionsList");
    if (Object.keys(state.connections).length === 0) {
        container.innerHTML = t('<div class="empty-note">Подключений пока нет</div>');
        return;
    }

    container.innerHTML = "";
    for (let portNum in state.connections) {
        let conn = state.connections[portNum];
        let destinationText = "";

        if (conn.patchPanel === null) {
            destinationText = t('Прямое подключение');
        } else {
            let panel = state.patchPanels.find(p => p.id == conn.patchPanel);
            let panelName = panel ? escapeHtml(panel.name) : `Panel ${escapeHtml(conn.patchPanel)}`;
            destinationText = t('→ {panelName} / Порт {patch}', { panelName, patch: escapeHtml(conn.patch) });
        }

        const connName = escapeHtml(conn.name);
        const connColor = escapeHtml(conn.color);

        let item = document.createElement("div");
        item.className = "connection-item";
        item.style.borderLeftColor = conn.color;
        item.innerHTML = `
            <div class="connection-header">
                <div class="connection-title">
                    <span class="color-preview" style="background: ${connColor};"></span>
                    ${escapeHtml(t('Порт {port}', { port: portNum }))}
                </div>
            </div>
            <div class="connection-details">
                ${connName}<br>
                <span class="muted">${destinationText}</span>
            </div>
            ${editMode ? `
            <div class="connection-actions">
                <button type="button" class="small" data-click="editConnection" data-args="[${parseInt(portNum)}]">${t('Изменить')}</button>
                <button type="button" class="small delete" data-click="deleteConnection" data-args="[${parseInt(portNum)}]">${t('Удалить')}</button>
            </div>
            ` : ''}
        `;
        container.appendChild(item);
    }
}

async function editConnection(portNum) {
    const conn = state.connections[portNum];
    if (!conn) return;
    const r = await formDialog({
        title: t('Соединение порта {port}', { port: portNum }),
        okText: t('Сохранить'),
        fields: connectionFields(conn.name, conn.color),
    });
    if (!r) return;
    conn.name = r.name;
    conn.color = r.color;
    updateHiddenFields();
    renderConnectionsList();
    restoreConnections();
}

async function deleteConnection(portNum) {
    if (await confirmDialog(t('Удалить соединение с портом {portNum}?', { portNum }), { okText: t('Удалить'), danger: true })) {
        delete state.connections[portNum];
        updateHiddenFields();
        renderConnectionsList();
        restoreConnections();
    }
}

// «Портов: 24 | Расположение: 1 строка | Позиция: под коммутатором» — для списка и PDF
function panelMeta(panel) {
    return t('Портов: {ports} | Расположение: {layout} | Позиция: {position}', {
        ports: panel.ports,
        layout: (panel.layout || 'single') === 'single' ? t('1 строка') : t('2 строки (шахматно)'),
        position: panel.position === 'above' ? t('Над коммутатором') : t('Под коммутатором'),
    });
}

function renderPatchPanelsList() {
    const container = document.getElementById("patchPanelsList");
    container.innerHTML = "";
    state.patchPanels.forEach((panel, index) => {
        let item = document.createElement("div");
        item.className = "patch-panel-item";
        item.innerHTML = `
            <div class="panel-header">
                <strong>${escapeHtml(panel.name)}</strong>
            </div>
            ${editMode ? `
                <label class="label">${t('Название:')}</label>
                <input type="text" value="${escapeAttr(panel.name)}" data-change="updatePatchPanelName" data-args='[${panel.id}, "$value"]'>
                <label class="label">${t('Количество портов:')}</label>
                <input type="number" value="${panel.ports}" min="1" max="96" data-change="updatePatchPanelPorts" data-args='[${panel.id}, "$value"]'>
                <label class="label">${t('Расположение портов:')}</label>
                <select data-change="updatePatchPanelLayout" data-args='[${panel.id}, "$value"]'>
                    <option value="single" ${(panel.layout || 'single') === 'single' ? 'selected' : ''}>${t('1 строка')}</option>
                    <option value="double" ${(panel.layout || 'single') === 'double' ? 'selected' : ''}>${t('2 строки (шахматно)')}</option>
                </select>
                <label class="label">${t('Позиция:')}</label>
                <select data-change="updatePatchPanelPosition" data-args='[${panel.id}, "$value"]'>
                    <option value="above" ${panel.position === 'above' ? 'selected' : ''}>${t('Над коммутатором')}</option>
                    <option value="below" ${panel.position === 'below' ? 'selected' : ''}>${t('Под коммутатором')}</option>
                </select>
                <button type="button" class="small delete" data-click="deletePatchPanel" data-args="[${panel.id}]">${t('Удалить панель')}</button>
            ` : `
                <div class="panel-meta">
                    ${panelMeta(panel)}
                </div>
            `}
        `;
        container.appendChild(item);
    });
}

async function addPatchPanel() {
    if (!editMode) return;
    const r = await formDialog({
        title: t('Новая патч-панель'),
        okText: t('Добавить'),
        fields: [
            { name: 'name', label: t('Название'), value: t('Патч-панель {n}', { n: nextPatchPanelId }), required: true, maxlength: 100 },
            { name: 'ports', label: t('Количество портов'), type: 'number', value: 24, min: 1, max: 96 },
        ],
    });
    if (!r) return;
    const name = r.name, ports = r.ports;
    state.patchPanels.push({ id: nextPatchPanelId++, name: name, ports: ports, position: 'below', layout: 'single' });
    updateHiddenFields();
    renderPatchPanelsList();
    renderRack();
}

function updatePatchPanelName(id, name) {
    let panel = state.patchPanels.find(p => p.id === id);
    if (panel) { panel.name = name; updateHiddenFields(); renderRack(); }
}

function updatePatchPanelPorts(id, ports) {
    let panel = state.patchPanels.find(p => p.id === id);
    if (panel) { panel.ports = parseInt(ports); updateHiddenFields(); renderRack(); }
}

function updatePatchPanelLayout(id, layout) {
    let panel = state.patchPanels.find(p => p.id === id);
    if (panel) { panel.layout = layout; updateHiddenFields(); renderRack(); }
}

function updatePatchPanelPosition(id, position) {
    let panel = state.patchPanels.find(p => p.id === id);
    if (panel) { panel.position = position; updateHiddenFields(); renderRack(); }
}

async function deletePatchPanel(id) {
    if (!await confirmDialog(t("Удалить эту патч-панель? Все соединения с ней будут удалены."), { okText: t('Удалить'), danger: true })) return;
    for (let sw in state.connections) {
        if (state.connections[sw].patchPanel === id) delete state.connections[sw];
    }
    state.patchPanels = state.patchPanels.filter(p => p.id !== id);
    updateHiddenFields();
    renderPatchPanelsList();
    renderConnectionsList();
    renderRack();
}

function updateHiddenFields() {
    document.getElementById("connectionsInput").value = JSON.stringify(state.connections);
    document.getElementById("layoutHidden").value = state.layout;
    document.getElementById("patchPanelsInput").value = JSON.stringify(state.patchPanels);
    document.getElementById("portTypesInput").value = JSON.stringify(state.portTypes);
    document.getElementById("trunkPortsInput").value = JSON.stringify(state.trunkPorts);
}

portCountInput.addEventListener("input", () => {
    if (!editMode) return;
    let newCount = parseInt(portCountInput.value);
    if (newCount && newCount > 0 && newCount <= 96) {
        state.switchPortsCount = newCount;
        renderRack();
    }
});

layoutSelect.addEventListener("change", () => {
    if (!editMode) return;
    state.layout = layoutSelect.value;
    renderRack();
});

renderRack();
renderConnectionsList();
renderPatchPanelsList();
renderVlanList();
updateHiddenFields();
resetSnmpFields();
try {
    if (localStorage.getItem('switchmap.showLoad') === '0') document.getElementById('loadToggle').checked = false;
} catch (e) { /* без localStorage — показываем загрузку */ }
highlightPortFromUrl();
loadPortLoad();
setInterval(loadPortLoad, LOAD_REFRESH_MS);


// Иероглифы, знаки препинания CJK и полноширинные символы
const CJK_RE = /[\u2E80-\u9FFF\uF900-\uFAFF\uFF00-\uFFEF]/;
const PDF_FONTS = {
    Roboto: { normal: 'Roboto-Regular.ttf', bold: 'Roboto-Medium.ttf', italics: 'Roboto-Italic.ttf', bolditalics: 'Roboto-MediumItalic.ttf' },
    NotoSansSC: { normal: 'NotoSansSC-Regular.ttf', bold: 'NotoSansSC-Bold.ttf', italics: 'NotoSansSC-Regular.ttf', bolditalics: 'NotoSansSC-Bold.ttf' },
};

// Шрифт с иероглифами (2 × 2,5 МБ) загружается только когда нужен — один раз за страницу
async function loadCjkFont() {
    if (pdfMake.vfs['NotoSansSC-Regular.ttf']) return;
    const wait = notify(t('Готовлю PDF…'), 'info', 15000);
    try {
        for (const name of ['NotoSansSC-Regular.ttf', 'NotoSansSC-Bold.ttf']) {
            const r = await fetch('/static/vendor/fonts/' + name);
            if (!r.ok) throw new Error(r.status);
            const bytes = new Uint8Array(await r.arrayBuffer());
            let bin = '';
            for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
            pdfMake.vfs[name] = btoa(bin);
        }
    } finally {
        wait.remove();
    }
}

async function exportToPDF() {
    // pdfmake (~1.5 МБ) нужен только здесь — загружаем при первом экспорте, а не с каждой страницей
    if (typeof pdfMake === 'undefined' || !pdfMake.vfs) {
        const wait = notify(t('Готовлю PDF…'), 'info', 15000);
        try {
            for (const [url, integrity] of PDFMAKE_SCRIPTS) await loadScript(url, integrity);  // шрифты — строго после pdfmake
        } catch (e) {
            notify(t('Не удалось загрузить библиотеку PDF. Проверьте подключение к интернету.'), 'error');
            return;
        } finally {
            wait.remove();
        }
    }
    try {
        const tableBody = [
            [
                { text: t('Порт\nкомм-ра'), style: 'tableHeader', alignment: 'center' },
                { text: t('Патч-панель'), style: 'tableHeader', alignment: 'center' },
                { text: t('Порт\nпанели'), style: 'tableHeader', alignment: 'center' },
                { text: t('Назначение'), style: 'tableHeader', alignment: 'center' },
                { text: t('Цвет кабеля'), style: 'tableHeader', alignment: 'center' }
            ]
        ];
        if (Object.keys(state.connections).length > 0) {
            const sortedConnections = Object.entries(state.connections).sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
            sortedConnections.forEach(([portNum, conn]) => {
                let panelName = "—"; let patchPort = "—";
                if (conn.patchPanel !== null) {
                    const panel = state.patchPanels.find(p => p.id == conn.patchPanel);
                    panelName = panel ? panel.name : `Panel ${conn.patchPanel}`;
                    patchPort = conn.patch.toString();
                }
                let portText = portNum.toString();
                if (state.trunkPorts && state.trunkPorts[portNum]) portText += " (T)";
                
                tableBody.push([
                    { text: portText, alignment: 'center', bold: true },
                    { text: panelName, alignment: 'left' },
                    { text: patchPort, alignment: 'center', bold: true },
                    { text: conn.name, alignment: 'left' },
                    { text: conn.color, alignment: 'center' }
                ]);
            });
        }
        
        const patchPanelsList = state.patchPanels.map((panel, index) => {
            return {
                text: [
                    { text: `${index + 1}. ${panel.name}\n`, bold: true },
                    { text: `   ${panelMeta(panel)}\n`, fontSize: 10, color: '#666' }
                ],
                margin: [0, 0, 0, 8]
            };
        });
        
        const docDefinition = {
            pageSize: 'A4',
            pageMargins: [40, 40, 40, 40],
            content: [
                { text: nameInput.value || t('Схема коммутатора'), style: 'header', alignment: 'center', margin: [0, 0, 0, 10] },
                { text: t('Дата создания: {v}', { v: new Date().toLocaleDateString(LOCALE) }), alignment: 'center', fontSize: 10, color: '#666', margin: [0, 0, 0, 20] },
                { text: t('Коммутатор'), style: 'subheader', margin: [0, 0, 0, 10] },
                {
                    text: [
                        { text: t('Количество портов: '), bold: true }, state.switchPortsCount.toString(), '\n',
                        { text: t('Расположение портов: '), bold: true }, state.layout === 'single' ? t('1 строка') : t('2 строки (шахматно)')
                    ],
                    margin: [0, 0, 0, 20]
                },
                { text: t('Патч-панели'), style: 'subheader', margin: [0, 0, 0, 10] },
                ...patchPanelsList,
                { text: t('Карта соединений'), style: 'subheader', margin: [0, 20, 0, 10] },
                Object.keys(state.connections).length > 0 ? {
                    table: { headerRows: 1, widths: [50, 100, 50, 150, 65], body: tableBody },
                    layout: { fillColor: function (rowIndex) { return (rowIndex === 0) ? '#4a2d3f' : null; } }
                } : { text: t('Нет настроенных соединений'), italics: true, color: '#999' }
            ],
            styles: {
                header: { fontSize: 20, bold: true, color: '#4a2d3f' },
                subheader: { fontSize: 14, bold: true, color: '#4a2d3f' },
                tableHeader: { bold: true, fontSize: 10, color: 'white' }
            },
            defaultStyle: { fontSize: 10 }
        };
        const filename = `${nameInput.value || 'switch'}_${t('схема')}.pdf`;
        // В Roboto нет иероглифов: для китайского интерфейса или китайских названий — шрифт Noto Sans SC
        let fonts;
        if ((window.I18N || {}).lang === 'zh' || CJK_RE.test(JSON.stringify(docDefinition))) {
            await loadCjkFont();
            fonts = PDF_FONTS;
            docDefinition.defaultStyle.font = 'NotoSansSC';
        }
        pdfMake.createPdf(docDefinition, null, fonts).download(filename);
    } catch (error) {
        notify(t('Ошибка при экспорте: ') + error.message, 'error');
    }
}

// ─── Мониторинг и SNMP ───────────────────────────────────

function checkSwitchStatus() {
    const ip = document.getElementById('ipInput').value.trim();
    const dot = document.getElementById('switchStatusDot');
    const txt = document.getElementById('switchStatusText');
    if (!ip) { txt.textContent = t('IP не задан'); return; }
    dot.className = 'status-indicator checking';
    txt.textContent = t('Проверка...');
    fetch(`/api/status/${SWITCH_ID}`)
        .then(r => r.json())
        .then(d => {
            txt.title = '';
            if (d.status === 'online') { dot.className = 'status-indicator online'; txt.textContent = t('Онлайн'); }
            else if (d.status === 'ping') {
                dot.className = 'status-indicator ping'; txt.textContent = t('Только ping');
                txt.title = t('Отвечает на ping, но не по SNMP. Проверьте настройки SNMP. Если на сервере работает VPN или прокси, он может отвечать на ping вместо отключённого коммутатора.');
            }
            else { dot.className = 'status-indicator offline'; txt.textContent = t('Недоступен'); }
        })
        .catch(() => { dot.className = 'status-indicator unknown'; txt.textContent = t('Ошибка'); });
}

function pollSNMP() {
    const btn = document.getElementById('snmpBtn');
    const panel = document.getElementById('snmpPanel');
    const content = document.getElementById('snmpContent');
    btn.disabled = true; btn.classList.add('is-loading');
    panel.classList.add('visible');
    content.innerHTML = t('<div class="snmp-message">Опрашиваю коммутатор по SNMP…</div>');

    fetch(`/api/poll_snmp/${SWITCH_ID}`, {method: 'POST'})
        .then(r => r.json())
        .then(data => {
            btn.disabled = false; btn.classList.remove('is-loading');
            if (data.error) { content.innerHTML = `<div class="snmp-message is-error">${escapeHtml(data.error)}</div>`; return; }
            renderSNMPResults(data);
            applyPolledVlans(data);
            refreshUnreadBadge();
            loadPortLoad();
        })
        .catch(e => {
            btn.disabled = false; btn.classList.remove('is-loading');
            content.innerHTML = t('<div class="snmp-message is-error">Ошибка соединения</div>');
        });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Значение для атрибута HTML (в кавычках). В атрибуты попадают только данные, не код (CSP запрещает onclick).
function escapeAttr(text) {
    return String(text).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
        .replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function renderSNMPResults(data) {
    const content = document.getElementById('snmpContent');
    // Физические порты (с номером на схеме) — по порядку, служебные интерфейсы — в конце
    const ports = Object.entries(data).sort((a, b) =>
        (a[1].port ?? 1e9) - (b[1].port ?? 1e9) || parseInt(a[0]) - parseInt(b[0]));
    if (ports.length === 0) {
        content.innerHTML = t('<div class="snmp-message">Нет данных (SNMP не ответил)</div>');
        return;
    }
    let html = t('<div class="snmp-summary">Найдено интерфейсов: {ports}</div>', { ports: ports.length });
    ports.forEach(([ifindex, info]) => {
        const devCount = info.devices ? info.devices.length : 0;
        const statusClass = info.up ? 'up' : 'down';
        const statusLabel = info.up ? '▲' : '▼';
        const portName = escapeHtml(info.name || 'Port '+ifindex);
        const portNo = info.port ? t('<span class="snmp-port-no" title="Номер порта на схеме">{port}</span>', { port: info.port }) : '';
        const alias = info.alias ? `<span class="snmp-port-alias">${escapeHtml(info.alias)}</span>` : '';
        const targetPort = parseInt(info.port || ifindex);
        html += `<div class="snmp-port-item">
            <div class="snmp-port-header" data-click="toggleSNMPDevices" data-args='["$el"]'>
                <span class="port-status-dot ${statusClass}" title="${info.up ? t('Активен') : t('Неактивен')}"></span>
                ${portNo}
                <span class="port-name">${portName}${alias}</span>
                <span class="port-device-count">${devCount > 0 ? escapeHtml(t('{n} устр.', { n: devCount })) : ''}</span>
                <span class="snmp-state">${statusLabel}</span>
            </div>`;
        if (devCount > 0) {
            html += `<div class="snmp-devices">`;
            info.devices.forEach(dev => {
                const mac = escapeHtml(dev.mac || '—');
                const ip = escapeHtml(dev.ip || '');
                const hostname = escapeHtml(dev.hostname || '');
                html += `<div class="snmp-device">
                    <div class="dev-mac">MAC: ${mac}</div>
                    ${dev.ip ? `<div class="dev-ip">IP: ${ip}</div>` : ''}
                    ${dev.hostname ? `<div class="dev-host">Host: ${hostname}</div>` : ''}
                    <button type="button" class="assign-btn" data-click="assignDeviceToPort" data-args="${escapeAttr(JSON.stringify([targetPort, dev.ip || '', dev.mac || '', dev.hostname || '']))}">
                        📌 ${t('Привязать к порту')}
                    </button>
                </div>`;
            });
            html += `</div>`;
        }
        html += `</div>`;
    });
    content.innerHTML = html;
}

function toggleSNMPDevices(header) {
    const devs = header.nextElementSibling;
    if (devs && devs.classList.contains('snmp-devices')) devs.classList.toggle('visible');
}

async function assignDeviceToPort(ifindex, ip, mac, hostname) {
    const r = await formDialog({
        title: t('Привязать устройство к порту'),
        note: [hostname, mac && `MAC: ${mac}`, ip && `IP: ${ip}`].filter(Boolean).join('\n'),
        okText: t('Привязать'),
        fields: [
            { name: 'port', label: t('Порт коммутатора'), type: 'number', value: ifindex, min: 1, max: state.switchPortsCount },
            { name: 'notes', label: t('Комментарий'), hint: t('Необязательно: что это за устройство, где стоит'), maxlength: 200 },
        ],
    });
    if (!r) return;
    const portNum = r.port, notes = r.notes || '';
    fetch(`/api/assign_device/${SWITCH_ID}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({port_number: parseInt(portNum), ip, mac, hostname, notes})
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) { notify(t('Устройство привязано к порту {portNum}', { portNum }), 'success'); setTimeout(() => location.reload(), 600); }
        else { notify(t('Ошибка: ') + (d.error || t('неизвестная ошибка')), 'error'); }
    });
}

async function removeDeviceFromPort(portNum, displayText) {
    const text = displayText ? t('Удалить устройство с порта {portNum}?\n{displayText}', { portNum, displayText })
                             : t('Удалить устройство с порта {portNum}?', { portNum });
    if (!await confirmDialog(text, { okText: t('Удалить'), danger: true })) return;
    fetch(`/api/remove_device/${SWITCH_ID}/${portNum}`, {method: 'POST'})
        .then(r => r.json())
        .then(() => location.reload());
}

function refreshDeviceStatuses() {
    fetch(`/api/refresh_devices/${SWITCH_ID}`, {method: 'POST'})
        .then(r => r.json())
        .then(data => {
            Object.entries(data).forEach(([devId, isOnline]) => {
                document.querySelectorAll('.port-device-badge[data-dev="' + devId + '"]').forEach(badge => {
                    if (isOnline === true) badge.classList.remove('offline');
                    else if (isOnline === false) badge.classList.add('offline');
                });
            });
        });
}

// ─── VLAN ──────────────────────────────────────────

function applyPolledVlans(data) {
    const portVlans = {};
    Object.entries(data).forEach(([ifindex, info]) => {
        if (info && info.vlan && info.vlan.id) {
            // На схеме порты нумеруются физически; ifIndex — только если номер не определён
            portVlans[info.port || ifindex] = { id: String(info.vlan.id), name: info.vlan.name || "" };
        }
    });
    state.portVlans = portVlans;
    INITIAL_STATE.portVlans = JSON.parse(JSON.stringify(portVlans));
    renderVlanList();
    renderRack();
}

function renderVlanList() {
    const container = document.getElementById('vlanList');
    const filterSelect = document.getElementById('vlanFilterSelect');
    if (!container) return;

    const vlans = {};
    Object.values(state.portVlans).forEach(v => {
        if (v && v.id) vlans[v.id] = v.name || '';
    });
    const ids = Object.keys(vlans).sort((a, b) => parseInt(a) - parseInt(b));

    if (ids.length === 0) {
        container.innerHTML = t('<div class="empty-note">Нет данных. Опросите коммутатор по SNMP.</div>');
    } else {
        container.innerHTML = ids.map(id => {
            // Имя VLAN приходит с коммутатора по SNMP — только экранированным
            const color = escapeAttr(state.vlanColors[id] || '#666');
            const name = vlans[id] ? ` — ${escapeHtml(vlans[id])}` : '';
            return `<div class="vlan-item">
                <span class="vlan-swatch" style="background:${color}" data-click="setVlanColor" data-args="${escapeAttr(JSON.stringify([id]))}" title="${escapeAttr(t('Назначить цвет'))}"></span>
                <span class="vlan-label">VLAN ${escapeHtml(id)}${name}</span>
            </div>`;
        }).join('');
    }

    if (filterSelect) {
        const prevValue = filterSelect.value;
        filterSelect.innerHTML = t('<option value="">Все порты</option>') +
            ids.map(id => `<option value="${id}">VLAN ${id}${vlans[id] ? ' — ' + vlans[id] : ''}</option>`).join('');
        if (ids.includes(prevValue)) filterSelect.value = prevValue;
        else vlanFilter = "";
    }
}

async function setVlanColor(vlanId) {
    const current = /^#[0-9a-f]{6}$/i.test(state.vlanColors[vlanId] || '') ? state.vlanColors[vlanId] : '#3498db';
    const r = await formDialog({
        title: t('Цвет VLAN {vlanId}', { vlanId }),
        okText: t('Сохранить'),
        fields: [{ name: 'color', label: t('Цвет'), type: 'color', value: current }],
    });
    if (!r) return;
    const trimmed = r.color;

    fetch(`/api/set_vlan_color/${SWITCH_ID}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({vlan_id: vlanId, color: trimmed})
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) {
            state.vlanColors = d.vlan_colors;
            renderVlanList();
            renderRack();
        } else {
            notify(t('Ошибка: ') + (d.error || t('неизвестная ошибка')), 'error');
        }
    })
    .catch(() => notify(t('Ошибка соединения'), 'error'));
}

function onVlanFilterChange() {
    vlanFilter = document.getElementById('vlanFilterSelect').value;
    renderRack();
}

// ─── Тип порта, Прямое Назначение и Транки ────────

let portTypeMenuTarget = null;

function showPortTypeMenu(x, y, portNum) {
    portTypeMenuTarget = portNum;
    const menu = document.getElementById('portTypeMenu');
    
    const currentType = state.portTypes[portNum] || 'rj45';
    const isTrunk = state.trunkPorts && state.trunkPorts[portNum];

    document.getElementById('menuRJ45').classList.toggle('active', currentType === 'rj45');
    document.getElementById('menuSFP').classList.toggle('active', currentType === 'sfp');
    document.getElementById('menuTrunk').classList.toggle('active', !!isTrunk);
    
    menu.style.display = 'block';
    // У края окна меню открывается в обратную сторону, чтобы не уходить за экран
    const w = menu.offsetWidth, h = menu.offsetHeight, gap = 8;
    menu.style.left = Math.max(gap, Math.min(x, window.innerWidth - w - gap)) + 'px';
    menu.style.top = Math.max(gap, y + h > window.innerHeight - gap ? y - h : y) + 'px';
}

function setPortType(type) {
    if (portTypeMenuTarget === null) return;
    if (type === 'rj45') {
        delete state.portTypes[portTypeMenuTarget];
    } else {
        state.portTypes[portTypeMenuTarget] = type;
    }
    document.getElementById('portTypeMenu').style.display = 'none';
    updateHiddenFields();
    renderRack();
}

function toggleTrunk() {
    if (portTypeMenuTarget === null || !editMode) return;
    
    if (state.trunkPorts[portTypeMenuTarget]) {
        delete state.trunkPorts[portTypeMenuTarget];
    } else {
        state.trunkPorts[portTypeMenuTarget] = true;
    }
    
    document.getElementById('portTypeMenu').style.display = 'none';
    updateHiddenFields();
    renderConnectionsList(); 
    renderRack();
}

async function assignDirectPort() {
    if (portTypeMenuTarget === null || !editMode) return;
    const port = portTypeMenuTarget;
    document.getElementById('portTypeMenu').style.display = 'none';
    const r = await formDialog({
        title: t('Подключение порта {port} напрямую', { port }),
        note: t('Без патч-панели: кабель идёт от порта коммутатора прямо к устройству.'),
        okText: t('Сохранить'),
        fields: connectionFields(portAlias(port), 'gray', t('Назначение порта (куда идёт линк)')),
    });
    if (!r) return;
    const name = r.name, color = r.color;

    state.connections[port] = {
        patchPanel: null,
        patch: null,
        color: color,
        name: name
    };

    document.getElementById('portTypeMenu').style.display = 'none';
    
    document.querySelectorAll(".port[data-type='switch']").forEach(p => p.classList.remove("port-selected"));
    selectedSwitchPort = null;
    
    updateHiddenFields();
    renderConnectionsList();
    restoreConnections();
}

document.addEventListener('click', (e) => {
    if (!e.target.closest('.port') && !e.target.closest('#portTypeMenu')) {
        document.getElementById('portTypeMenu').style.display = 'none';
    }
});

document.addEventListener('DOMContentLoaded', () => {
    if (SWITCH_IP) {
        checkSwitchStatus();
        setInterval(checkSwitchStatus, 60000);
    }
});

// Колокольчик событий — в /static/events.js

function renderDeviceBadges() {
    Object.entries(SAVED_DEVICES).forEach(([portNum, dev]) => {
        const portEl = document.querySelector(`.port[data-type="switch"][data-port="${portNum}"]`);
        if (portEl) {
            // Удаляем старый бейдж, если был (защита от дубликатов при перерисовке)
            const existing = portEl.querySelector('.port-device-badge');
            if (existing) {
                // Клонируем элемент для удаления всех event listeners
                const clone = existing.cloneNode(true);
                existing.parentNode.replaceChild(clone, existing);
                clone.remove();
            }

            const badge = document.createElement('div');
            badge.className = 'port-device-badge' + (dev.is_online ? '' : ' offline');
            badge.dataset.dev = dev.id;
            const displayText = dev.hostname || dev.ip || dev.mac || '?';
            badge.title = t('{displayText}\nПравый клик — удалить', { displayText });
            badge.textContent = displayText;
            portEl.appendChild(badge);

            // Используем обработчик события вместо addEventListener для избежания дубликатов
            badge.oncontextmenu = function(e) {
                e.preventDefault();
                e.stopPropagation();
                removeDeviceFromPort(portNum, displayText);
            };
        }
    });
}

// ─────────────────────────────────────────
// СТАТИСТИКА (модальное окно)
// ─────────────────────────────────────────

// Окно показывает данные последнего SNMP-опроса (ручного или фонового).
// Новый опрос запускается только кнопкой «Обновить данные».
const STATS_AUTO_REFRESH_MS = 30000;
let healthChart = null;
let trafficChart = null;
let statsRefreshTimer = null;

function isStatsModalOpen() {
    return document.getElementById('statsModal').classList.contains('visible');
}

function openStatsModal() {
    if (isStatsModalOpen()) return;
    document.getElementById('statsModal').classList.add('visible');
    // Chart.js подключён с async — если ещё грузится, дожидаемся (не дольше 15 с)
    waitForGlobal('Chart').then(() => { if (isStatsModalOpen()) loadStatsData(); });
    statsRefreshTimer = setInterval(autoRefreshStats, STATS_AUTO_REFRESH_MS);
}

function closeStatsModal() {
    if (!isStatsModalOpen()) return;
    document.getElementById('statsModal').classList.remove('visible');
    clearInterval(statsRefreshTimer);
    statsRefreshTimer = null;
    if (healthChart) {
        healthChart.destroy();
        healthChart = null;
    }
    if (trafficChart) {
        trafficChart.destroy();
        trafficChart = null;
    }
}

async function loadStatsData() {
    await Promise.all([
        loadHealthStats(),
        loadHealthHistory(),
        loadPortList(),
        loadDuplicateMACs(),
        loadPoEStatus()
    ]);
    if (document.getElementById('portSelectStats').value) {
        await loadPortTraffic();
    }
}

async function autoRefreshStats() {
    if (!isStatsModalOpen()) return;
    await loadStatsData();
}

function chartLibMissing(emptyEl) {
    if (typeof Chart !== 'undefined') return false;
    emptyEl.textContent = t('Не удалось загрузить библиотеку графиков (Chart.js). Проверьте доступ к интернету.');
    emptyEl.hidden = false;
    return true;
}

function formatStatValue(value, unit) {
    return (typeof value === 'number' && value > 0) ? value.toFixed(1) + unit : '—';
}

// Карточка показателя: значение или «нет данных» с пояснением (не все коммутаторы сообщают всё)
function setStatCard(id, value, unit) {
    const el = document.getElementById(id);
    const label = el.parentElement.querySelector('.stat-label');
    if (label.dataset.text === undefined) label.dataset.text = label.textContent;
    const ok = typeof value === 'number' && value > 0;
    el.textContent = formatStatValue(value, unit);
    label.textContent = ok ? label.dataset.text : t('нет данных по SNMP');
    label.title = ok ? '' : t('Коммутатор не сообщает этот показатель по SNMP. Так бывает у некоторых моделей — например, многие Cisco 2960 не отдают температуру.');
}

async function loadHealthStats() {
    try {
        const response = await fetch(`/api/switch_health/${SWITCH_ID}`);
        const data = await response.json();

        setStatCard('cpuValue', data.cpu_usage, '%');
        setStatCard('ramValue', data.ram_usage, '%');
        setStatCard('tempValue', data.temperature, '°C');
        document.getElementById('statsLastPoll').textContent = data.last_poll_time
            ? t('Последний опрос: {last_poll_time}', { last_poll_time: data.last_poll_time })
            : t('Коммутатор ещё не опрашивался');
    } catch (error) {
        console.error('Error loading health stats:', error);
    }
}

// ─── Период графиков (1 ч … 1 год) ───
const PERIOD_LABELS = { '1h': t('последний час'), '6h': t('6 часов'), '24h': t('24 часа'), '7d': t('7 дней'), '30d': t('30 дней'), '1y': t('год') };
let statsPeriod = (() => {
    try { const p = localStorage.getItem('switchmap.statsPeriod'); return PERIOD_LABELS[p] ? p : '24h'; }
    catch (e) { return '24h'; }
})();

function syncPeriodButtons() {
    document.querySelectorAll('#statsPeriod button').forEach(b => b.classList.toggle('is-active', b.dataset.period === statsPeriod));
}

function setStatsPeriod(period) {
    if (!PERIOD_LABELS[period] || period === statsPeriod) return;
    statsPeriod = period;
    try { localStorage.setItem('switchmap.statsPeriod', period); } catch (e) { /* без localStorage */ }
    syncPeriodButtons();
    if (healthChart) { healthChart.destroy(); healthChart = null; }
    if (trafficChart) { trafficChart.destroy(); trafficChart = null; }
    loadHealthHistory();
    if (document.getElementById('portSelectStats').value) loadPortTraffic();
}

document.getElementById('statsPeriod')?.addEventListener('click', e => {
    const btn = e.target.closest('button[data-period]');
    if (btn) setStatsPeriod(btn.dataset.period);
});
syncPeriodButtons();

async function loadHealthHistory() {
    const emptyEl = document.getElementById('healthEmpty');
    try {
        const response = await fetch(`/api/switch_health_history/${SWITCH_ID}?period=${statsPeriod}`);
        const data = await response.json();
        const points = Array.isArray(data.points) ? data.points : [];

        if (points.length === 0) {
            if (healthChart) {
                healthChart.destroy();
                healthChart = null;
            }
            emptyEl.textContent = t('Нет данных за {statsPeriod} — нажмите «Обновить данные», чтобы опросить коммутатор.', { statsPeriod: PERIOD_LABELS[statsPeriod] });
            emptyEl.hidden = false;
            return;
        }
        if (chartLibMissing(emptyEl)) return;
        emptyEl.hidden = true;

        const bucketed = data.bucket_sec > 0;
        const labels = formatTimeLabels(points.map(d => d.timestamp), data.bucket_sec);

        // Анимируем только первую отрисовку, чтобы автообновление не «мигало»
        const animate = !healthChart;
        if (healthChart) {
            healthChart.destroy();
        }

        const CT = chartTheme();
        const ctx = document.getElementById('healthChart').getContext('2d');
        const series = (label, key, color, soft, axis) => ({
            label, data: points.map(d => d[key]), borderColor: color, backgroundColor: soft,
            tension: 0.3, fill: true, spanGaps: true, pointRadius: points.length > 60 ? 0 : 3, yAxisID: axis
        });
        healthChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    series('CPU %', 'cpu_usage', CT.blue, CT.blueSoft, 'y'),
                    series('RAM %', 'ram_usage', CT.violet, CT.violetSoft, 'y'),
                    series(t('Температура °C'), 'temperature', CT.red, CT.redSoft, 'y1')
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: animate ? undefined : false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { labels: { color: CT.text } },
                    tooltip: {
                        callbacks: {
                            title: items => bucketed
                                ? t('{label} · среднее за {bucket_sec}', { label: items[0].label, bucket_sec: formatInterval(data.bucket_sec) })
                                : items[0].label,
                            label: item => {
                                const p = points[item.dataIndex];
                                const key = ['cpu_usage', 'ram_usage', 'temperature'][item.datasetIndex];
                                const unit = key === 'temperature' ? '°C' : '%';
                                const v = p[key];
                                if (v === null || v === undefined) return t(' {label}: нет данных', { label: item.dataset.label });
                                const max = bucketed && p[key + '_max'] != null ? t(' (пик {v}{unit})', { v: p[key + '_max'].toFixed(1), unit }) : '';
                                return ` ${item.dataset.label.split(' ')[0]}: ${v.toFixed(1)}${unit}${max}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        type: 'linear', display: true, position: 'left', beginAtZero: true,
                        ticks: { color: CT.muted }, grid: { color: CT.grid },
                        title: { display: true, text: 'CPU/RAM %', color: CT.text }
                    },
                    y1: {
                        type: 'linear', display: true, position: 'right',
                        ticks: { color: CT.muted }, grid: { drawOnChartArea: false },
                        title: { display: true, text: t('Температура °C'), color: CT.text }
                    },
                    x: { ticks: { color: CT.muted, maxRotation: 0, autoSkipPadding: 16 }, grid: { color: CT.grid } }
                }
            }
        });
    } catch (error) {
        console.error('Error loading health history:', error);
    }
}

async function loadPortList() {
    try {
        const response = await fetch(`/api/stats_ports/${SWITCH_ID}`);
        const data = await response.json();
        if (!Array.isArray(data)) {
            return;
        }

        const select = document.getElementById('portSelectStats');
        const selected = select.value;
        select.innerHTML = '';

        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = data.length ? t('Выберите порт...') : t('Нет данных о портах — нажмите «Обновить данные»');
        select.appendChild(placeholder);

        // Сначала физические порты по номеру, затем служебные интерфейсы
        data.sort((a, b) => (a.port ?? 1e9) - (b.port ?? 1e9));
        data.forEach(port => {
            const option = document.createElement('option');
            option.value = port.ifindex;
            option.textContent = [port.port ? t('Порт {port}', { port: port.port }) : null, port.name, port.alias ? `«${port.alias}»` : null]
                .filter(Boolean).join(' · ');
            select.appendChild(option);
        });
        // Сохраняем выбор порта при автообновлении
        if (selected && data.some(p => String(p.ifindex) === selected)) {
            select.value = selected;
        }
    } catch (error) {
        console.error('Error loading port list:', error);
    }
}

// Время с сервера приходит как "2026-10-19 18:50:48" (локальное). Safari не понимает пробел.
function parseServerTime(ts) {
    return new Date(String(ts).replace(' ', 'T'));
}

// Подписи оси X: время; за несколько дней — дата и время; для суточных корзин — только дата
function formatTimeLabels(timestamps, bucketSec = 0) {
    const dates = timestamps.map(parseServerTime);
    if (bucketSec >= 86400) {
        return dates.map(d => d.toLocaleDateString(LOCALE, { day: '2-digit', month: '2-digit' }));
    }
    const multiDay = dates.length > 1 && dates[0].toDateString() !== dates[dates.length - 1].toDateString();
    return dates.map(d => multiDay
        ? d.toLocaleString(LOCALE, { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
        : d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit' }));
}

function formatInterval(sec) {
    if (sec < 90) return t('{sec} с', { sec: Math.round(sec) });
    if (sec < 5400) return t('{v} мин', { v: Math.round(sec / 60) });
    return t('{v} ч', { v: (sec / 3600).toFixed(1) });
}

function formatRate(mbps) {
    if (mbps === null || mbps === undefined) return '—';
    if (mbps >= 1000) return t('{v} Гбит/с', { v: (mbps / 1000).toFixed(2) });
    if (mbps >= 1) return t('{mbps} Мбит/с', { mbps: mbps.toFixed(2) });
    return t('{v} Кбит/с', { v: (mbps * 1000).toFixed(1) });
}

function clearTrafficChart(message) {
    if (trafficChart) {
        trafficChart.destroy();
        trafficChart = null;
    }
    const emptyEl = document.getElementById('trafficEmpty');
    emptyEl.textContent = message;
    emptyEl.hidden = false;
    document.getElementById('trafficSummary').textContent = '';
}

async function loadPortTraffic() {
    const ifindex = document.getElementById('portSelectStats').value;
    const emptyEl = document.getElementById('trafficEmpty');
    const summaryEl = document.getElementById('trafficSummary');
    if (!ifindex) {
        clearTrafficChart(t('Выберите порт, чтобы увидеть скорость трафика.'));
        return;
    }

    try {
        const response = await fetch(`/api/port_traffic/${SWITCH_ID}/${encodeURIComponent(ifindex)}?period=${statsPeriod}`);
        const data = await response.json();
        const points = Array.isArray(data.points) ? data.points : [];
        if (points.length === 0) {
            clearTrafficChart(t('Нет данных о скорости порта за {statsPeriod}. Для расчёта скорости нужно минимум два опроса — подождите следующего или нажмите «Обновить данные» позже.', { statsPeriod: PERIOD_LABELS[statsPeriod] }));
            return;
        }
        if (chartLibMissing(emptyEl)) return;
        emptyEl.hidden = true;

        const bucketed = data.bucket_sec > 0;
        const avg = arr => { const v = arr.filter(x => x !== null && x !== undefined); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
        const peak = arr => { const v = arr.filter(x => x !== null && x !== undefined); return v.length ? Math.max(...v) : null; };
        if (bucketed) {
            const errors = points.reduce((s, p) => s + (p.errors || 0), 0);
            summaryEl.textContent = t('За {statsPeriod}: в среднем ↓ {v} · ↑ {v2}', { statsPeriod: PERIOD_LABELS[statsPeriod], v: formatRate(avg(points.map(p => p.in_mbps))), v2: formatRate(avg(points.map(p => p.out_mbps))) }) +
                t(' · пик ↓ {v} · ↑ {v2} · ошибок: {errors}', { v: formatRate(peak(points.map(p => p.in_mbps_max))), v2: formatRate(peak(points.map(p => p.out_mbps_max))), errors });
        } else {
            const last = points[points.length - 1];
            summaryEl.textContent = last.in_mbps === null
                ? t('Последний интервал ({interval_sec}): счётчики сбросились — вероятно, коммутатор или порт перезагружался.', { interval_sec: formatInterval(last.interval_sec) })
                : t('Последний интервал ({interval_sec}): ↓ {in_mbps} · ↑ {out_mbps} · ошибок: {v}', { interval_sec: formatInterval(last.interval_sec), in_mbps: formatRate(last.in_mbps), out_mbps: formatRate(last.out_mbps), v: last.errors ?? 0 });
        }

        // Единица оси подстраивается под величину трафика
        const maxMbps = Math.max(0, ...points.map(p => Math.max(p.in_mbps ?? 0, p.out_mbps ?? 0, p.in_mbps_max ?? 0, p.out_mbps_max ?? 0)));
        const unit = maxMbps >= 1000 ? { k: 0.001, name: t('Гбит/с') }
                   : maxMbps >= 1    ? { k: 1, name: t('Мбит/с') }
                   :                   { k: 1000, name: t('Кбит/с') };
        const scaled = v => (v === null || v === undefined) ? null : +(v * unit.k).toFixed(3);

        const animate = !trafficChart;
        if (trafficChart) {
            trafficChart.destroy();
        }

        const CT = chartTheme();
        const pointRadius = points.length > 60 ? 0 : 3;
        const datasets = [
            {
                label: bucketed ? t('Входящий, среднее, {name}', { name: unit.name }) : t('Входящий, {name}', { name: unit.name }),
                data: points.map(p => scaled(p.in_mbps)),
                borderColor: CT.green, backgroundColor: CT.greenSoft,
                cubicInterpolationMode: 'monotone', // без выбросов ниже нуля между точками
                fill: true, spanGaps: false, pointRadius
            },
            {
                label: bucketed ? t('Исходящий, среднее, {name}', { name: unit.name }) : t('Исходящий, {name}', { name: unit.name }),
                data: points.map(p => scaled(p.out_mbps)),
                borderColor: CT.blue, backgroundColor: CT.blueSoft,
                cubicInterpolationMode: 'monotone',
                fill: true, spanGaps: false, pointRadius
            },
            {
                type: 'bar',
                label: bucketed ? t('Ошибки за {bucket_sec}', { bucket_sec: formatInterval(data.bucket_sec) }) : t('Ошибки за интервал'),
                data: points.map(p => p.errors ?? null),
                backgroundColor: CT.redBar, borderColor: CT.red,
                yAxisID: 'y1', maxBarThickness: 10
            }
        ];
        if (bucketed) {
            // Пики — пунктиром поверх средних
            datasets.push(
                { label: t('Пик входящий'), data: points.map(p => scaled(p.in_mbps_max)), borderColor: CT.green,
                  borderDash: [4, 4], borderWidth: 1.2, pointRadius: 0, fill: false, cubicInterpolationMode: 'monotone' },
                { label: t('Пик исходящий'), data: points.map(p => scaled(p.out_mbps_max)), borderColor: CT.blue,
                  borderDash: [4, 4], borderWidth: 1.2, pointRadius: 0, fill: false, cubicInterpolationMode: 'monotone' });
        }

        const ctx = document.getElementById('trafficChart').getContext('2d');
        trafficChart = new Chart(ctx, {
            type: 'line',
            data: { labels: formatTimeLabels(points.map(p => p.timestamp), data.bucket_sec), datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: animate ? undefined : false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { labels: { color: CT.text } },
                    tooltip: {
                        callbacks: {
                            title: items => {
                                const p = points[items[0].dataIndex];
                                return bucketed
                                    ? t('{label} · среднее за {bucket_sec}', { label: items[0].label, bucket_sec: formatInterval(data.bucket_sec) })
                                    : t('{label} (интервал {interval_sec})', { label: items[0].label, interval_sec: formatInterval(p.interval_sec) });
                            },
                            label: item => {
                                const p = points[item.dataIndex];
                                if (item.dataset.yAxisID === 'y1') return t(' Ошибки: {v}', { v: item.raw ?? '—' });
                                if (item.datasetIndex >= 3) return ` ${item.dataset.label}: ${formatRate(item.datasetIndex === 3 ? p.in_mbps_max : p.out_mbps_max)}`;
                                const mbps = item.datasetIndex === 0 ? p.in_mbps : p.out_mbps;
                                return ` ${item.datasetIndex === 0 ? t('Входящий') : t('Исходящий')}: ${mbps === null ? t('сброс счётчика') : formatRate(mbps)}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        type: 'linear', display: true, position: 'left', beginAtZero: true,
                        ticks: { color: CT.muted }, grid: { color: CT.grid },
                        title: { display: true, text: t('Скорость, {name}', { name: unit.name }), color: CT.text }
                    },
                    y1: {
                        type: 'linear', display: true, position: 'right', beginAtZero: true,
                        ticks: { color: CT.muted, precision: 0 }, grid: { drawOnChartArea: false },
                        title: { display: true, text: t('Ошибки'), color: CT.text }
                    },
                    x: { ticks: { color: CT.muted, maxRotation: 0, autoSkipPadding: 16 }, grid: { color: CT.grid } }
                }
            }
        });
    } catch (error) {
        console.error('Error loading port traffic:', error);
    }
}

async function loadDuplicateMACs() {
    try {
        const response = await fetch(`/api/duplicate_macs/${SWITCH_ID}`);
        const data = await response.json();

        if (data.length > 0) {
            document.getElementById('duplicateAlert').style.display = 'block';
            const list = document.getElementById('duplicateList');
            list.innerHTML = data.map(dup =>
                t('<div class="alert-item">MAC {mac} обнаружен на портах: {v}</div>', { mac: escapeHtml(dup.mac), v: dup.ports.join(', ') })
            ).join('');
        } else {
            document.getElementById('duplicateAlert').style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading duplicate MACs:', error);
    }
}

const POE_STATE_BY_CODE = { 1: 'disabled', 2: 'searching', 3: 'delivering', 4: 'fault', 5: 'test', 6: 'fault' };
const POE_STATE_VIEW = {
    delivering: { cls: 'delivering', text: t('Питание') },
    searching:  { cls: 'searching',  text: t('Поиск') },
    disabled:   { cls: 'disabled',   text: t('Выключен') },
    test:       { cls: 'searching',  text: t('Тест') },
    fault:      { cls: 'fault',      text: t('Ошибка') },
    unknown:    { cls: 'disabled',   text: t('Неизвестно') }
};

async function loadPoEStatus() {
    try {
        const response = await fetch(`/api/poe_status/${SWITCH_ID}`);
        const data = await response.json();
        const container = document.getElementById('poeContainer');

        if (!response.ok || data.error || Object.keys(data).length === 0) {
            container.style.display = 'none';
            return;
        }

        container.style.display = 'block';
        const grid = document.getElementById('poeGrid');
        grid.innerHTML = '';

        Object.entries(data).forEach(([ifindex, info]) => {
            const poe = info.poe;
            // pethPsePortDetectionStatus (RFC 3621)
            const state = poe.state || POE_STATE_BY_CODE[poe.status] || 'unknown';
            const view = POE_STATE_VIEW[state] || POE_STATE_VIEW.unknown;
            const power = (typeof poe.power_consumed === 'number')
                ? `${poe.power_consumed.toFixed(1)} W` : '— W';

            const card = document.createElement('div');
            card.className = `poe-port ${state === 'delivering' ? 'active' : ''}`;
            card.innerHTML = `
                <div class="poe-port-header">
                    <div class="poe-port-name">${escapeHtml(info.port_name || ('Port ' + ifindex))}</div>
                    <div class="poe-status ${view.cls}">${view.text}</div>
                </div>
                <div class="poe-power" title="${typeof poe.power_consumed === 'number' ? '' : escapeAttr(t('Коммутатор не сообщает потребление по портам'))}">${power}</div>
            `;
            grid.appendChild(card);
        });
    } catch (error) {
        console.error('Error loading PoE status:', error);
    }
}

async function refreshStatsData() {
    const btn = document.getElementById('refreshStatsBtn');
    btn.disabled = true;
    btn.classList.add('is-loading');

    try {
        const response = await fetch(`/api/poll_snmp/${SWITCH_ID}`, { method: 'POST' });
        const result = await response.json();
        if (result && result.error) {
            notify(t('Ошибка SNMP-опроса: ') + result.error, 'error');
        }
        await loadStatsData();
    } catch (error) {
        console.error('Error refreshing stats:', error);
        notify(t('Ошибка при обновлении данных'), 'error');
    } finally {
        btn.disabled = false;
        btn.classList.remove('is-loading');
    }
}

// Закрытие модального окна по клику вне его
document.addEventListener('click', (e) => {
    const modal = document.getElementById('statsModal');
    if (modal && e.target === modal) {
        closeStatsModal();
    }
});

// Закрытие по ESC
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isStatsModalOpen()) {
        closeStatsModal();
    }
});



// ─── Тема для графиков и схемы ───
function hexToRgba(color, alpha) {
    const m = /^#?([0-9a-f]{6})$/i.exec(color.trim());
    if (!m) return color;
    const n = parseInt(m[1], 16);
    return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function chartTheme() {
    const accent = cssVar('--accent'), danger = cssVar('--danger'), success = cssVar('--success');
    if (typeof Chart !== 'undefined') {
        Chart.defaults.font.family = cssVar('--font');
        Chart.defaults.font.size = 11;
    }
    return {
        text: cssVar('--text-2'), muted: cssVar('--text-3'), grid: cssVar('--chart-grid'),
        blue: accent, blueSoft: hexToRgba(accent, .12),
        violet: '#8b6cff', violetSoft: 'rgba(139, 108, 255, .12)',
        red: danger, redSoft: hexToRgba(danger, .1), redBar: hexToRgba(danger, .6),
        green: success, greenSoft: hexToRgba(success, .12),
    };
}

document.addEventListener('themechange', () => {
    applyPortLoad();
    if (isStatsModalOpen()) {
        if (healthChart) { healthChart.destroy(); healthChart = null; }
        if (trafficChart) { trafficChart.destroy(); trafficChart = null; }
        loadHealthHistory();
        if (document.getElementById('portSelectStats').value) loadPortTraffic();
    }
});
