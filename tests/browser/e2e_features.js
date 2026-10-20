// Новые функции: поиск, оповещения, тепловая карта, описания портов, SNMPv3. node e2e_features.js <baseUrl> <shotsDir>
const puppeteer = require('puppeteer-core');
const path = require('path');
const [base, shots] = process.argv.slice(2);
const results = [];
const check = (name, cond, info = '') => {
    results.push(!!cond);
    console.log((cond ? 'OK   ' : 'FAIL ') + name + (info !== '' ? `  -> ${JSON.stringify(info)}` : ''));
};
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
    const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
    const page = await browser.newPage();
    await page.goto(base + '/login', { waitUntil: 'domcontentloaded' }); await page.type('#username', 'admin'); await page.type('#password', 'adminpass123');
    await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), page.click('button[type=submit]')]);
    await page.setViewport({ width: 1400, height: 900 });
    const jsErrors = [], dialogs = [];
    page.on('pageerror', e => jsErrors.push(String(e.message || e)));
    page.on('console', m => { if (m.type() === 'error' && !String(m.location().url).includes('favicon')) jsErrors.push('console: ' + m.text()); });
    page.on('dialog', async d => { dialogs.push(d.message()); await d.accept(d.defaultValue()); });
    const toastTexts = () => page.$$eval('.toast .toast-text', els => els.map(e => e.textContent));
    const open = async url => { await page.goto(base + url, { waitUntil: 'load', timeout: 60000 }); await sleep(500); };
    const sidebar = async () => {
        if (!(await page.$eval('#sidebar', el => el.classList.contains('open')))) { await page.click('.menu-toggle'); await sleep(400); }
        if (await page.$eval('#content-monitor', el => getComputedStyle(el).display === 'none')) { await page.click('#arrow-monitor'); await sleep(300); }
    };

    // ── 1. Поиск на главной
    await open('/');
    await page.type('#netSearchInput', '00-11-22-33-44-55');
    await sleep(900);
    const items = await page.$$eval('#netSearchResults .ns-item', els => els.map(e => ({ text: e.innerText.replace(/\s+/g, ' '), href: e.getAttribute('href'), uplink: e.classList.contains('is-uplink') })));
    check('поиск MAC: первым — Ядро Cisco порт 3', items[0] && items[0].text.includes('Ядро Cisco → порт 3') && items[0].href === '/switch/1?port=3', items);
    check('поиск MAC: D-Link порт 8 помечен uplink и стоит ниже', items.some(i => i.uplink && i.text.includes('Доступ D-Link → порт 8') && i.text.includes('uplink')) && items[items.length - 1].uplink, items);
    check('в результате виден IP и VLAN', items[0] && items[0].text.includes('192.0.2.50') && items[0].text.includes('VLAN 10'), items[0]);
    await page.screenshot({ path: path.join(shots, 'f1_search.png') });
    await Promise.all([page.waitForNavigation({ waitUntil: 'load' }), page.keyboard.press('Enter')]);
    await sleep(700);
    check('Enter открывает коммутатор с подсветкой порта', page.url().endsWith('/switch/1?port=3')
        && await page.$eval(".port[data-type='switch'][data-port='3']", el => el.classList.contains('port-highlight')), page.url());

    await open('/');
    await page.type('#netSearchInput', 'БУХГАЛТЕРИЯ');
    await sleep(900);
    const t2 = await page.$eval('#netSearchResults', el => el.innerText);
    check('поиск по описанию порта (регистр не важен)', t2.includes('«Бухгалтерия ПК-1»') && t2.includes('описание на коммутаторе'), t2);
    await page.$eval('#netSearchInput', el => { el.value = ''; });
    await page.type('#netSearchInput', 'zzzz-нет-такого');
    await sleep(900);
    check('ничего не найдено — понятное сообщение', (await page.$eval('#netSearchResults', el => el.innerText)).includes('Ничего не найдено'));

    await page.keyboard.press('Escape'); await sleep(200);
    check('Esc закрывает список результатов', await page.$eval('#netSearchResults', el => el.hidden));

    // ── 2. Пороги в настройках
    await page.click('button[onclick="openSettingsModal()"]');
    await sleep(600);
    check('окно настроек открылось', await page.$eval('#settingsModal', el => el.classList.contains('active')));
    const thr = await page.evaluate(() => ['alertUtilInput', 'alertErrorsInput', 'alertCpuInput', 'alertTempInput'].map(id => document.getElementById(id).value));
    check('настройки: пороги по умолчанию 80/10/90/70', thr.join() === '80,10,90,70', thr);
    await page.$eval('#alertUtilInput', el => { el.value = '95'; });
    await page.click('button[onclick="saveSettings()"]'); await sleep(600);
    await page.click('button[onclick="openSettingsModal()"]'); await sleep(600);
    check('порог сохраняется', await page.$eval('#alertUtilInput', el => el.value) === '95');
    await page.$eval('#alertUtilInput', el => { el.value = '80'; });
    await page.click('button[onclick="saveSettings()"]'); await sleep(600);

    // ── 3. Колокольчик: новые события со ссылками
    await page.click('.bell-btn'); await sleep(800);
    const ev = await page.$$eval('#eventsList .event-item', els => els.map(e => ({ text: e.innerText.replace(/\s+/g, ' '), href: e.getAttribute('href') })));
    check('событие «Высокая загрузка порта» с деталями', ev.some(e => e.text.includes('Высокая загрузка порта') && e.text.includes('порог 80%') && e.href === '/switch/1?port=9'), ev);
    check('событие «Высокая загрузка CPU»', ev.some(e => e.text.includes('Высокая загрузка CPU') && e.text.includes('CPU: 95%')), ev);
    check('событие «Ошибки на порту» D-Link порт 4', ev.some(e => e.text.includes('Ошибки на порту') && e.href === '/switch/2?port=4'), ev);
    await page.screenshot({ path: path.join(shots, 'f2_events.png') });
    await Promise.all([page.waitForNavigation({ waitUntil: 'load' }), page.click('#eventsList a[href="/switch/1?port=9"]')]);
    await sleep(800);
    check('клик по событию ведёт к порту 9 с подсветкой', await page.$eval(".port[data-type='switch'][data-port='9']", el => el.classList.contains('port-highlight')));

    // ── 4. Тепловая карта и подсказки
    await open('/switch/1');
    await sleep(800);
    const heat = await page.evaluate(() => {
        const p = n => document.querySelector(`.port[data-type='switch'][data-port='${n}']`);
        return { p9high: p(9).classList.contains('load-high'), p9bar: !!p(9).querySelector('.load-bar'),
                 p3bar: !!p(3).querySelector('.load-bar'), p3high: p(3).classList.contains('load-high'),
                 p5down: p(5).classList.contains('link-down'), legend: document.getElementById('loadLegendThreshold').textContent,
                 time: document.getElementById('loadLegendTime').textContent };
    });
    check('порт 9 (95%) подсвечен красным и с полоской', heat.p9high && heat.p9bar, heat);
    check('порт 3 (4%) с полоской, без подсветки', heat.p3bar && !heat.p3high, heat);
    check('порт 5 без линка затемнён', heat.p5down, heat);
    check('легенда: порог и время опроса', heat.legend === '80' && heat.time.startsWith('Данные опроса'), heat);
    const p3 = await page.$(".port[data-type='switch'][data-port='3']");
    const box = await p3.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.move(box.x + box.width / 2 + 2, box.y + box.height / 2 + 1);
    await sleep(300);
    const tip = await page.$eval('#tooltip', el => ({ text: el.innerText, op: getComputedStyle(el).opacity }));
    check('подсказка порта: описание, имя, скорость, загрузка', tip.op === '1' && tip.text.includes('«Бухгалтерия ПК-1»')
        && tip.text.includes('GigabitEthernet1/0/3 · 1 Гбит/с') && /Загрузка \d/.test(tip.text), tip);
    await page.screenshot({ path: path.join(shots, 'f3_heatmap.png') });
    await page.mouse.move(5, 5);
    await sleep(200);

    // Видимость оформления по вычисленным стилям (style.css задаёт box-shadow/background с !important)
    const vis = await page.evaluate(() => {
        const cs = n => getComputedStyle(document.querySelector(`.port[data-type='switch'][data-port='${n}']`));
        return { p9outline: cs(9).outlineStyle + ' ' + cs(9).outlineColor, p3outline: cs(3).outlineStyle };
    });
    check('красная обводка порта выше порога реально видна', vis.p9outline.startsWith('solid rgb(') && !vis.p9outline.includes('rgba(0, 0, 0, 0)') && vis.p3outline === 'none', vis);
    const p7 = await (await page.$(".port[data-type='switch'][data-port='7']")).boundingBox();
    await page.mouse.move(p7.x + p7.width / 2, p7.y + p7.height / 2);
    await page.mouse.move(p7.x + p7.width / 2 + 1, p7.y + p7.height / 2 + 1);
    await sleep(300);
    const hover = await page.evaluate(() => ({
        bg: getComputedStyle(document.querySelector(".port[data-type='switch'][data-port='7']")).backgroundColor,
        tip: document.getElementById('tooltip').innerText }));
    check('наведение на подключение красит порт его цветом', hover.bg === 'rgb(255, 0, 0)', hover);
    check('подсказка подключения: название + данные порта', hover.tip.startsWith('Склад принтер\nGigabitEthernet1/0/7'), hover.tip);
    await page.mouse.move(5, 5); await sleep(200);
    check('после ухода мыши цвет снимается', await page.$eval(".port[data-type='switch'][data-port='7']", el => getComputedStyle(el).backgroundColor) !== 'rgb(255, 0, 0)');
    await open('/switch/1?port=4');
    await sleep(300);
    check('подсветка порта из ссылки видна (outline)', await page.$eval(".port[data-type='switch'][data-port='4']", el => getComputedStyle(el).outlineStyle) === 'solid');

    await sidebar();
    await page.click('#loadToggle'); await sleep(300);
    check('переключатель скрывает загрузку', await page.$$eval('.load-bar', b => b.length) === 0);
    await open('/switch/1');
    check('выключенный переключатель запоминается', !(await page.$eval('#loadToggle', el => el.checked)) && await page.$$eval('.load-bar', b => b.length) === 0);
    await sidebar();
    await page.click('#loadToggle'); await sleep(300);
    check('включение возвращает полоски', await page.$$eval('.load-bar', b => b.length) > 0);

    // ── 5. Панель SNMP-опроса: номера портов и описания, VLAN по номеру порта
    await page.click('#snmpBtn');
    await page.waitForFunction(() => !document.getElementById('snmpBtn').disabled, { timeout: 60000 });
    await sleep(500);
    const panel = await page.$eval('#snmpContent', el => el.innerText);
    check('панель SNMP: описание порта видно', panel.includes('Бухгалтерия ПК-1') && panel.includes('Uplink к ядру'), panel.slice(0, 300));
    check('VLAN 10 отмечен на порту 3 схемы', await page.$eval(".port[data-type='switch'][data-port='3'] .vlan-tag", el => el.title).catch(() => '') === 'VLAN 10 — buh');
    await page.click('#snmpPanel .snmp-header button'); await sleep(200);

    // ── 6. Окно статистики: подписи портов
    await page.click('button[onclick="openStatsModal()"]'); await sleep(1200);
    const opts = await page.$$eval('#portSelectStats option', os => os.map(o => o.textContent));
    check('статистика: «Порт 3 · GigabitEthernet1/0/3 · «Бухгалтерия ПК-1»»', opts.includes('Порт 3 · GigabitEthernet1/0/3 · «Бухгалтерия ПК-1»'), opts.slice(0, 5));
    await page.keyboard.press('Escape'); await sleep(200);

    // ── 7. SNMPv3 через интерфейс
    await sidebar();
    await page.click('#editBtn'); await sleep(300);
    await page.select('#snmpVersionSelect', '3');
    check('v3: поля пользователя появились, community скрыт', await page.$eval('#snmpV3Fields', el => !el.hidden) && await page.$eval('#snmpV2Fields', el => el.hidden));
    await page.type('#snmpV3User', 'simuser');
    await page.select('#snmpV3AuthProto', 'SHA');
    await page.type('#snmpV3AuthKey', 'short');
    await page.select('#snmpV3PrivProto', 'AES128');
    await page.type('#snmpV3PrivKey', 'privpass123');
    await page.type('#snmpV3Context', 'public');
    const navBefore = page.url();
    await page.click('#saveBtn'); await sleep(800);
    const tt = await toastTexts();
    check('короткий пароль: сохранение отклонено с объяснением', tt.some(d => d.includes('не короче 8 символов')) && page.url() === navBefore, tt);
    await page.$eval('#snmpV3AuthKey', el => { el.value = ''; });
    await page.type('#snmpV3AuthKey', 'authpass123');
    await Promise.all([page.waitForNavigation({ waitUntil: 'load' }), page.click('#saveBtn')]);
    await sleep(600);
    const html = await page.content();
    check('пароли v3 не попадают в страницу', !html.includes('authpass123') && !html.includes('privpass123'));
    const v3state = await page.evaluate(() => ({ ver: document.getElementById('snmpVersionSelect').value,
        user: document.getElementById('snmpV3User').value, auth: document.getElementById('snmpV3AuthProto').value,
        priv: document.getElementById('snmpV3PrivProto').value, ctx: document.getElementById('snmpV3Context').value,
        ph: document.getElementById('snmpV3AuthKey').placeholder }));
    check('v3 сохранён: версия, пользователь, протоколы, контекст', v3state.ver === '3' && v3state.user === 'simuser'
        && v3state.auth === 'SHA' && v3state.priv === 'AES128' && v3state.ctx === 'public' && v3state.ph.startsWith('сохранён'), v3state);
    await sidebar();
    await page.click('#snmpTestBtn');
    await page.waitForFunction(() => /Успешно|Ошибка ·/.test(document.getElementById('snmpTestResult').textContent), { timeout: 30000 });
    const testOk = await page.$eval('#snmpTestResult', el => el.textContent);
    check('«Проверить SNMP» по v3: успех', testOk.includes('Успешно · SNMPv3 authPriv: sim-cisco'), testOk);
    await page.screenshot({ path: path.join(shots, 'f4_snmpv3.png') });

    await page.click('#editBtn'); await sleep(300);
    await page.type('#snmpV3AuthKey', 'wrongpass99');
    await Promise.all([page.waitForNavigation({ waitUntil: 'load' }), page.click('#saveBtn')]);
    await sleep(500); await sidebar();
    await page.click('#snmpTestBtn');
    await page.waitForFunction(() => /Успешно|Ошибка ·/.test(document.getElementById('snmpTestResult').textContent), { timeout: 30000 });
    const testFail = await page.$eval('#snmpTestResult', el => el.textContent);
    check('неверный пароль: понятная ошибка', testFail.includes('Ошибка ·') && testFail.includes('неверный пароль аутентификации'), testFail);

    await page.click('#editBtn'); await sleep(300);
    await page.select('#snmpVersionSelect', '2c');
    await Promise.all([page.waitForNavigation({ waitUntil: 'load' }), page.click('#saveBtn')]);
    await sleep(500); await sidebar();
    await page.click('#snmpTestBtn');
    await page.waitForFunction(() => /Успешно|Ошибка ·/.test(document.getElementById('snmpTestResult').textContent), { timeout: 30000 });
    check('возврат на v2c работает', (await page.$eval('#snmpTestResult', el => el.textContent)).includes('Успешно · SNMPv2c'));

    check('нет ошибок JS', jsErrors.length === 0, jsErrors);
    await browser.close();
    const failed = results.filter(r => !r).length;
    console.log(`\nИТОГО: ${failed ? 'провалено ' + failed : 'все проверки пройдены'} (${results.length} проверок)`);
})().catch(e => { console.error('СЦЕНАРИЙ УПАЛ:', e); process.exit(1); });

