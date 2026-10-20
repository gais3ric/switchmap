// Политика безопасности (CSP): ни одного заблокированного скрипта на страницах и при действиях,
// которые переведены с onclick на data-click. node e2e_csp.js <baseUrl> <shotsDir>
const puppeteer = require('puppeteer-core');
const [base] = process.argv.slice(2);
const results = [];
const check = (name, cond, info = '') => {
    results.push(!!cond);
    console.log((cond ? 'OK   ' : 'FAIL ') + name + (info !== '' ? `  -> ${JSON.stringify(info)}` : ''));
};
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
    const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });
    const violations = [], errors = [];
    // Нарушения CSP ловим событием страницы — так видно и заблокированные обработчики, и eval
    await page.evaluateOnNewDocument(() => {
        document.addEventListener('securitypolicyviolation', e => {
            (window.__csp = window.__csp || []).push(`${e.violatedDirective} ${e.blockedURI || ''} ${e.sample || ''}`.trim());
        });
    });
    page.on('pageerror', e => errors.push(String(e.message || e)));
    page.on('console', m => { if (m.type() === 'error' && !/favicon|status of 40[0-9]/.test(m.text() + m.location().url)) errors.push(m.text()); });
    page.on('dialog', d => d.accept(d.type() === 'prompt' ? 'Тест' : undefined));
    const collect = async label => {
        const v = await page.evaluate(() => window.__csp || []).catch(() => []);
        v.forEach(x => violations.push(`${label}: ${x}`));
    };
    const press = sel => page.$eval(sel, el => el.click());  // клик через DOM: без зависимости от анимаций и прокрутки
    const open = async url => { await collect('до ' + url); await page.goto(base + url, { waitUntil: 'networkidle2', timeout: 60000 }); await sleep(600); };

    await page.goto(base + '/login', { waitUntil: 'domcontentloaded' });
    await page.type('#username', 'admin'); await page.type('#password', 'adminpass123');
    await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);

    for (const url of ['/', '/switch/1', '/topology', '/audit', '/maintenance', '/users', '/notifications', '/discover', '/add']) {
        await open(url);
    }
    await collect('страницы');
    check('страницы открываются без нарушений CSP', violations.length === 0, violations);

    // Каркас: тема, поиск, настройки, колокольчик, меню пользователя
    await open('/');
    const theme = await page.$eval('html', el => el.dataset.theme);
    await page.click('#themeToggle'); await sleep(200);
    check('кнопка темы (data-click)', (await page.$eval('html', el => el.dataset.theme)) !== theme);
    await page.click('#themeToggle');
    await page.click('.rail-item[data-click="focusById"]'); await sleep(150);
    check('кнопка поиска ставит фокус', await page.evaluate(() => document.activeElement.id === 'netSearchInput'));
    await page.click('[data-click="openSettingsModal"]'); await sleep(300);
    check('настройки открываются', await page.$eval('#settingsModal', el => el.classList.contains('active')));
    await page.click('#settingsModal [data-click="closeSettingsModal"]'); await sleep(300);
    check('и закрываются', !(await page.$eval('#settingsModal', el => el.classList.contains('active'))));
    await page.click('.bell-btn'); await sleep(400);
    check('колокольчик открывает события', await page.$eval('#eventsPanel', el => el.classList.contains('visible')));
    await page.click('.bell-btn'); await sleep(200);

    // Окно добавления: патч-панели (кнопки создаются скриптом)
    await press('.page-actions [data-click="openModal"]'); await sleep(400);
    await page.waitForFunction(() => document.querySelectorAll('#patchPanelsList .patch-panel-field').length === 1);
    await press('#addSwitchModal [data-click="addPatchPanelField"]'); await sleep(200);
    const panels = await page.$$eval('#patchPanelsList .patch-panel-field', els => els.length);
    await press('#patchPanelsList .patch-panel-field:last-child [data-click="removePatchPanel"]'); await sleep(200);
    check('патч-панели в окне добавления: добавить и удалить', panels === 2
        && (await page.$$eval('#patchPanelsList .patch-panel-field', els => els.length)) === 1, panels);
    await press('#addSwitchModal [data-click="closeModal"]'); await sleep(300);

    // Страница коммутатора: режим правки, патч-панель, разделы меню, тип порта
    await open('/switch/1');
    await press('#editBtn'); await sleep(400);
    await press('#addPatchPanelBtn'); await sleep(400);
    const nameInput = '#patchPanelsList .patch-panel-item:last-child [data-change="updatePatchPanelName"]';
    const hasPanelUi = await page.$(nameInput);
    if (hasPanelUi) {
        await page.$eval(nameInput, el => { el.value = 'Панель CSP'; el.dispatchEvent(new Event('change', { bubbles: true })); });
        await sleep(300);
    }
    const rack = await page.evaluate(() => JSON.stringify(state.patchPanels));
    check('патч-панель: добавление и переименование (data-change с $value)', rack.includes('Панель CSP'), rack.slice(0, 200));
    const before = await page.$eval('#content-monitor', el => el.classList.contains('open'));
    await press('[data-click="toggleSection"][data-args*="monitor"]'); await sleep(200);
    check('раздел меню сворачивается (data-args со строкой)', before !== await page.$eval('#content-monitor', el => el.classList.contains('open')));
    await press('#cancelBtn'); await sleep(400);
    // Тип порта через контекстное меню
    const port = await page.$('.port[data-type="switch"]');
    if (port) {
        await port.click({ button: 'right' }); await sleep(250);
        await page.click('#menuSFP').catch(() => {}); await sleep(250);
    }
    // PDF (pdfmake с CDN, с контрольной суммой)
    await page.click('.page-actions [data-menu-toggle]'); await sleep(250);
    await page.click('[data-click="exportToPDF"]');
    await page.waitForFunction(() => window.pdfMake, { timeout: 30000 }).catch(() => {});
    await sleep(2500);
    check('PDF: pdfmake загрузился с проверкой контрольной суммы', await page.evaluate(() => !!window.pdfMake));
    // Статистика (Chart.js)
    await page.click('[data-click="openStatsModal"]'); await sleep(1500);
    check('Chart.js загрузился с проверкой контрольной суммы', await page.evaluate(() => !!window.Chart));
    await page.click('[data-click="closeStatsModal"]'); await sleep(300);

    // Топология (d3)
    await open('/topology');
    await sleep(1200);
    check('топология: d3 загрузился и нарисовал граф', await page.evaluate(() => !!window.d3) && (await page.$$('#nodes g')).length > 0);
    await page.click('[data-click="fitGraph"]'); await sleep(300);

    // Внедрённый обработчик действительно не выполняется
    await open('/');
    const errorsBefore = errors.length;
    const injected = await page.evaluate(async () => {
        window.__pwned = false;
        const div = document.createElement('div');
        div.innerHTML = '<img src="x" onerror="window.__pwned = true"><button id="evil" onclick="window.__pwned = true">x</button>';
        document.body.appendChild(div);
        document.getElementById('evil').click();
        const s = document.createElement('script');
        s.textContent = 'window.__pwned = true';
        document.body.appendChild(s);
        await new Promise(r => setTimeout(r, 300));
        return window.__pwned;
    });
    check('внедрённые onclick, onerror и <script> без nonce заблокированы', injected === false);
    const blocked = await page.evaluate(() => (window.__csp || []).length);
    check('браузер сообщил о блокировке', blocked >= 2, blocked);
    await page.evaluate(() => { window.__csp = []; });
    errors.splice(errorsBefore);  // сообщения о намеренно заблокированном коде выше

    await collect('действия');
    check('действия без нарушений CSP', violations.length === 0, violations);
    check('нет ошибок JS', errors.length === 0, errors);
    await browser.close();
    const failed = results.filter(r => !r).length;
    console.log(`\nИТОГО: ${failed ? 'провалено ' + failed : 'все проверки пройдены'} (${results.length} проверок)`);
})().catch(e => { console.error('СЦЕНАРИЙ УПАЛ:', e); process.exit(1); });
