// Регрессия основных функций страницы коммутатора. node e2e_core.js <baseUrl> <shotsDir>
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
    const browser = await puppeteer.launch({
        executablePath: process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true,
        args: ['--lang=ru-RU', '--accept-lang=ru-RU'],
    });
    const page = await browser.newPage();
    await page.goto(base + '/login', { waitUntil: 'domcontentloaded' }); await page.type('#username', 'admin'); await page.type('#password', 'adminpass123');
    await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), page.click('button[type=submit]')]);
    await page.setViewport({ width: 1400, height: 900 });
    const jsErrors = [];
    let navigations = 0;
    page.on('pageerror', e => jsErrors.push(String(e.message || e)));
    page.on('console', m => { if (m.type() === 'error' && !String(m.location().url).includes('favicon')) jsErrors.push('console: ' + m.text()); });
    page.on('framenavigated', f => { if (f === page.mainFrame()) navigations++; });
    // Окна браузера (prompt/confirm) не должны появляться вовсе — всё во встроенных окнах приложения
    const nativeDialogs = [];
    page.on('dialog', async d => { nativeDialogs.push(d.type() + ': ' + d.message()); await d.dismiss(); });
    const formOpen = () => page.$eval('#formModal', el => el.classList.contains('active'));
    const fillForm = async values => {
        await page.waitForSelector('#formModal.active', { timeout: 5000 });
        const inputs = await page.$$('#formFields input');
        for (let i = 0; i < values.length; i++) {
            if (values[i] === undefined) continue;
            await inputs[i].click({ clickCount: 3 }); await page.keyboard.press('Backspace');
            await inputs[i].type(String(values[i]));
        }
    };
    const open = async url => { await page.goto(base + url, { waitUntil: 'load', timeout: 60000 }); await sleep(300); };
    const st = expr => page.evaluate(expr);
    const sidebar = async () => { if (!(await page.$eval('#sidebar', el => el.classList.contains('open')))) { await page.click('.menu-toggle'); await sleep(500); } };

    // ── A. Кнопки шапки больше не отправляют форму и не стирают данные
    await open('/switch/1');
    const before = await st(() => JSON.stringify({ pt: state.portTypes, tr: state.trunkPorts, ip: document.getElementById('ipInput').value }));
    check('исходные данные загружены из базы (типы портов, транки)', before.includes('"52":"sfp"') && before.includes('"50":true'), before);
    check('раскладка берётся из switch_layout', await st(() => state.layout) === 'single', await st(() => state.layout));
    const nav0 = navigations;
    await page.click('.bell-btn'); await sleep(400);
    await page.click('button[data-click="markAllEventsRead"]'); await sleep(400);
    await page.click('.page-actions [data-menu-toggle]'); await sleep(250); await page.click('button[data-click="exportToPDF"]'); await sleep(1500);
    await page.click('button[data-click="openStatsModal"]'); await sleep(500);
    await page.keyboard.press('Escape'); await sleep(200);
    check('клики по шапке не перезагружают страницу', navigations === nav0, navigations - nav0);
    await open('/switch/1');
    const after = await st(() => JSON.stringify({ pt: state.portTypes, tr: state.trunkPorts, ip: document.getElementById('ipInput').value }));
    check('после кликов данные в базе не изменились', after === before, { before, after });

    // ── B. Enter в поле ввода в режиме редактирования не отправляет форму
    await sidebar(); await page.click('#editBtn'); await sleep(200);
    const nav1 = navigations;
    await page.focus('#nameInput');
    await page.keyboard.press('Enter'); await sleep(1000);
    check('Enter в поле имени не отправляет форму', navigations === nav1);

    // ── C. Редактирование и сохранение переживают перезагрузку
    await page.select('#layoutSelect', 'double');
    if (await page.$eval('#content-patch', el => getComputedStyle(el).display === 'none')) { await page.click('#arrow-patch'); await sleep(400); }
    await page.click('#addPatchPanelBtn'); await sleep(300);
    check('«Добавить патч-панель» — окно приложения', await formOpen());
    await fillForm(['Тест-панель', 12]);
    await page.click('#formOk'); await sleep(400);
    check('патч-панель добавлена из окна', await st(() => state.patchPanels.some(p => p.name === 'Тест-панель' && p.ports === 12)));

    // Соединение «порт коммутатора → порт патч-панели» во встроенном окне
    const panelId = await st(() => state.patchPanels.find(p => p.name === 'Тест-панель').id);
    await page.click(".port[data-type='switch'][data-port='3']"); await sleep(200);
    await page.click(`.port[data-type='patch'][data-panel='${panelId}'][data-port='2']`); await sleep(400);
    check('соединение: открылось окно приложения, а не браузера', await formOpen() && nativeDialogs.length === 0, nativeDialogs);
    const note = await page.$eval('#formNote', el => el.textContent);
    check('в окне видно, что с чем соединяем', note.includes('3') && note.includes('Тест-панель') && note.includes('2'), note);
    check('палитра цветов кабеля', (await page.$$('#formFields .swatch')).length >= 6);
    await fillForm(['']);
    await page.click('#formOk'); await sleep(300);
    check('пустое назначение не принимается — подсказка в окне', await formOpen()
        && await page.$eval('#formFields .field-error', el => !el.hidden && el.textContent.length > 0));
    await fillForm(['Склад']);
    await page.click("#formFields .swatch[data-value='blue']");
    await page.keyboard.press('Enter'); await sleep(400);
    const c3 = await st(() => state.connections['3']);
    check('соединение создано: назначение, цвет, патч-панель и порт', !await formOpen() && c3 && c3.name === 'Склад'
        && c3.color === 'blue' && c3.patchPanel == panelId && c3.patch === 2, c3);
    await page.click(".port[data-type='switch'][data-port='4']"); await sleep(200);
    await page.click(`.port[data-type='patch'][data-panel='${panelId}'][data-port='5']`); await sleep(300);
    await page.keyboard.press('Escape'); await sleep(300);
    check('Esc закрывает окно без соединения', !await formOpen() && await st(() => !state.connections['4']));
    await page.click('#connectionsList [data-click="editConnection"][data-args="[3]"]'); await sleep(300);
    check('«Изменить»: окно с текущими значениями', await page.$eval('#formFields input', el => el.value) === 'Склад'
        && await page.$eval("#formFields .swatch[data-value='blue']", el => el.getAttribute('aria-checked') === 'true'));
    await page.click("#formFields .swatch[data-value='green']"); await page.click('#formOk'); await sleep(300);
    check('«Изменить»: цвет поменялся', await st(() => state.connections['3'].color === 'green'));
    await page.click('#connectionsList [data-click="deleteConnection"][data-args="[3]"]'); await sleep(300);
    check('«Удалить»: подтверждение в окне приложения', await page.$eval('#confirmModal', el => el.classList.contains('active')));
    await page.click('#confirmOk'); await sleep(300);
    check('соединение удалено', await st(() => !state.connections['3']));
    check('ни одного окна браузера', nativeDialogs.length === 0, nativeDialogs);
    if (await page.$eval('#content-monitor', el => getComputedStyle(el).display === 'none')) { await page.click('#arrow-monitor'); await sleep(400); }
    await page.click('#ipInput', { clickCount: 3 }); await page.keyboard.press('Backspace');
    await page.type('#ipInput', '10.0.0.1');
    await st(() => {
        state.connections['1'] = { patchPanel: null, patch: null, color: 'red', name: '<img src=x onerror="window.__xss=1">Линк' };
    });
    await Promise.all([page.waitForNavigation({ waitUntil: 'load', timeout: 60000 }), page.click('#saveBtn')]);
    await sleep(400);
    check('после сохранения: раскладка «2 строки»', await st(() => state.layout) === 'double' && await page.$eval('#layoutSelect', s => s.value) === 'double');
    const panels = await st(() => state.patchPanels.map(p => `${p.name}/${p.ports}`));
    check('после сохранения: патч-панель добавлена', panels.includes('Тест-панель/12'), panels);
    check('после сохранения: типы портов и транки на месте', await st(() => state.portTypes['52'] === 'sfp' && state.trunkPorts['50'] === true));
    check('после сохранения: IP на месте', await page.$eval('#ipInput', el => el.value) === '10.0.0.1');
    check('после сохранения: подключение порта 1 сохранено', await st(() => !!state.connections['1']));
    check('имя подключения выводится как текст, без XSS', await st(() => window.__xss === undefined)
        && (await page.$eval('#connectionsList', el => el.textContent)).includes('<img'));
    await page.screenshot({ path: path.join(shots, '5_switch_page.png') });

    // ── D. Отмена редактирования возвращает исходное состояние
    await sidebar(); await page.click('#editBtn'); await sleep(200);
    await page.select('#layoutSelect', 'single');
    await page.click('#cancelBtn'); await sleep(300);
    check('«Отмена» возвращает раскладку', await st(() => state.layout) === 'double' && await page.$eval('#layoutSelect', s => s.value) === 'double');

    // ── E. Остальные страницы
    for (const url of ['/', '/topology', '/add', '/switch/2']) {
        await open(url);
        check(`страница ${url} без ошибок JS`, jsErrors.length === 0, jsErrors);
    }
    check('коммутатор без данных (пустые поля) открывается', await st(() => typeof state === 'object' && Array.isArray(state.patchPanels)));

    check('нет ошибок JS', jsErrors.length === 0, jsErrors);
    await browser.close();
    const failed = results.filter(r => !r).length;
    console.log(`\nИТОГО: ${failed ? 'провалено ' + failed : 'все проверки пройдены'} (${results.length} проверок)`);
})().catch(e => { console.error('СЦЕНАРИЙ УПАЛ:', e); process.exit(1); });





