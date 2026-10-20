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
    const answers = { 'Название новой патч-панели': 'Тест-панель', 'Количество портов': '12' };
    page.on('dialog', async d => {
        const key = Object.keys(answers).find(k => d.message().startsWith(k));
        if (d.type() === 'prompt') await d.accept(key ? answers[key] : d.defaultValue());
        else await d.accept();
    });
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





