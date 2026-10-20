// Интерфейс: тема, поиск с клавиатуры, навигация, таблица портов, диалоги. node e2e_ui.js <baseUrl> <shotsDir>
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
    await page.goto(base + '/login', { waitUntil: 'domcontentloaded' }); await page.type('#username', 'admin'); await page.type('#password', 'adminpass123');
    await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), page.click('button[type=submit]')]);
    await page.setViewport({ width: 1440, height: 900 });
    const jsErrors = [];
    page.on('pageerror', e => jsErrors.push(String(e.message || e)));
    page.on('console', m => { if (m.type() === 'error' && !String(m.location().url).includes('favicon')) jsErrors.push('console: ' + m.text()); });
    const open = async url => { await page.goto(base + url, { waitUntil: 'load', timeout: 60000 }); await sleep(500); };
    const theme = () => page.evaluate(() => document.documentElement.dataset.theme);
    const toastTexts = () => page.$$eval('.toast .toast-text', els => els.map(e => e.textContent));

    // ── Тема
    await open('/');
    await page.evaluate(() => localStorage.removeItem('switchmap.theme'));
    await open('/');
    check('по умолчанию тёмная тема', await theme() === 'dark');
    const bgDark = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    await page.click('#themeToggle'); await sleep(450);
    const bgLight = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    check('переключение на светлую меняет цвета', await theme() === 'light' && bgDark !== bgLight, { bgDark, bgLight });
    await open('/switch/1');
    check('тема сохраняется между страницами', await theme() === 'light');
    check('подсказка кнопки темы соответствует состоянию', await page.$eval('#themeToggle', el => el.dataset.label) === 'Тёмная тема');

    // ── Навигация
    check('активный пункт меню на странице коммутатора — «Коммутаторы»',
        await page.$eval('.rail-item.is-active', el => el.dataset.label) === 'Коммутаторы');
    await open('/topology');
    check('на топологии активна «Топология»', await page.$eval('.rail-item.is-active', el => el.dataset.label) === 'Топология');
    check('крошки показывают текущий раздел', (await page.$eval('.crumbs', el => el.innerText)).includes('Топология'));

    // ── Поиск с клавиатуры (Ctrl+K, стрелки, Enter)
    await open('/');
    await page.keyboard.down('Control'); await page.keyboard.press('KeyK'); await page.keyboard.up('Control');
    check('Ctrl+K переводит фокус в поиск', await page.evaluate(() => document.activeElement.id) === 'netSearchInput');
    await page.keyboard.type('00:11:22:33:44:55');
    await sleep(800);
    await page.keyboard.press('ArrowDown'); await page.keyboard.press('ArrowDown');
    const focusedHref = await page.$eval('.ns-item.is-focused', el => el.getAttribute('href'));
    check('стрелки выбирают результат', focusedHref === '/switch/2?port=8', focusedHref);
    await Promise.all([page.waitForNavigation({ waitUntil: 'load' }), page.keyboard.press('Enter')]);
    check('Enter открывает выбранный результат', page.url().endsWith('/switch/2?port=8'), page.url());

    // ── Страница коммутатора: таблица портов
    await open('/switch/1');
    await sleep(800);
    const rows = () => page.$$eval('#portsTableBody tr[data-port]', trs => trs.map(t => t.dataset.port));
    check('таблица портов: 10 строк', (await rows()).length === 10, await rows());
    check('счётчик портов', await page.$eval('#portsCount', el => el.textContent) === '10');
    await page.click('#portsFilter button[data-filter="down"]'); await sleep(200);
    check('фильтр «Без линка» — только порт 5', JSON.stringify(await rows()) === '["5"]', await rows());
    await page.click('#portsFilter button[data-filter="alerts"]'); await sleep(200);
    check('фильтр «С оповещениями» — порт 9', JSON.stringify(await rows()) === '["9"]', await rows());
    check('у перегруженного порта статус «перегрузка»', (await page.$eval('#portsTableBody tr[data-port="9"]', el => el.innerText)).includes('перегрузка'));
    await page.click('#portsTableBody tr[data-port="9"]'); await sleep(400);
    check('клик по строке подсвечивает порт на схеме', await page.$eval(".port[data-type='switch'][data-port='9']", el => el.classList.contains('port-highlight')));
    await page.click('#portsFilter button[data-filter="all"]'); await sleep(200);
    check('описание и подключение в таблице', (await page.$eval('#portsTableBody tr[data-port="3"]', el => el.innerText)).includes('Бухгалтерия ПК-1')
        && (await page.$eval('#portsTableBody tr[data-port="7"]', el => el.innerText)).includes('Склад принтер'));

    // ── «Редактировать» открывает параметры
    check('панель параметров закрыта по умолчанию', !(await page.$eval('#sidebar', el => el.classList.contains('open'))));
    await page.click('#editBtn'); await sleep(450);
    const editState = await page.evaluate(() => ({
        open: document.getElementById('sidebar').classList.contains('open'),
        section: document.getElementById('content-switch').classList.contains('open'),
        badge: getComputedStyle(document.getElementById('editIndicator')).display,
        edit: document.getElementById('editBtn').hidden, save: document.getElementById('saveBtn').hidden,
        hint: getComputedStyle(document.querySelector('.schema-hint')).display }));
    check('«Редактировать»: открыта панель и раздел «Коммутатор»', editState.open && editState.section, editState);
    check('режим редактирования: бейдж, подсказка, кнопки Сохранить/Отмена', editState.badge !== 'none' && editState.hint === 'block'
        && editState.edit && !editState.save, editState);
    await page.click('#cancelBtn'); await sleep(200);
    check('«Отмена» возвращает кнопки', await page.evaluate(() => !document.getElementById('editBtn').hidden && document.getElementById('saveBtn').hidden));
    await page.evaluate(() => toggleMenu()); await sleep(400);

    // ── Смена темы перерисовывает графики без ошибок
    await page.click('button[onclick="openStatsModal()"]'); await sleep(1500);
    const before = await page.evaluate(() => Chart.getChart('healthChart')?.options.scales.x.ticks.color);
    await page.evaluate(() => toggleTheme()); await sleep(900);
    const after = await page.evaluate(() => Chart.getChart('healthChart')?.options.scales.x.ticks.color);
    check('смена темы перекрашивает графики', before && after && before !== after, { before, after });
    await page.keyboard.press('Escape'); await sleep(300);

    // ── Диалог удаления: отмена и подтверждение
    await open('/');
    const countRows = () => page.$$eval('#switchTable tr.is-link', r => r.length);
    const n0 = await countRows();
    await page.click('#sw-row-2 .btn-delete'); await sleep(400);
    check('удаление спрашивает подтверждение', await page.$eval('#confirmModal', el => el.classList.contains('active'))
        && (await page.$eval('#confirmText', el => el.textContent)).includes('Доступ D-Link'));
    await page.click('#confirmCancel'); await sleep(400);
    check('«Отмена» ничего не удаляет', !(await page.$eval('#confirmModal', el => el.classList.contains('active'))) && await countRows() === n0);
    await page.click('#sw-row-2 .btn-delete'); await sleep(400);
    await page.click('#confirmOk'); await sleep(200);
    check('после подтверждения — уведомление', (await toastTexts()).some(t => t.includes('удалён')), await toastTexts());
    await page.waitForNavigation({ waitUntil: 'load', timeout: 10000 }).catch(() => {});
    await sleep(500);
    check('коммутатор удалён из таблицы', await countRows() === n0 - 1);

    // ── Фильтр таблицы коммутаторов
    await page.type('#switchFilter', 'zzz'); await sleep(200);
    check('фильтр без совпадений показывает сообщение', await page.$eval('#noResults', el => !el.hidden));

    // ── Сохранение настроек — уведомление
    await page.evaluate(() => openSettingsModal()); await sleep(500);
    await page.click('#settingsModal .btn-primary'); await sleep(600);
    check('сохранение настроек — уведомление «Настройки сохранены»', (await toastTexts()).includes('Настройки сохранены'), await toastTexts());

    // ── Мобильная ширина: без горизонтальной прокрутки
    await page.setViewport({ width: 400, height: 860 });
    for (const url of ['/', '/switch/1', '/topology', '/add']) {
        await open(url);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        check(`400px: ${url} без горизонтальной прокрутки`, overflow <= 0, overflow);
    }
    check('400px: нижняя навигация видна', await page.$eval('.rail', el => getComputedStyle(el).height) === '56px');

    check('нет ошибок JS', jsErrors.length === 0, jsErrors);
    await browser.close();
    const failed = results.filter(r => !r).length;
    console.log(`\nИТОГО: ${failed ? 'провалено ' + failed : 'все проверки пройдены'} (${results.length} проверок)`);
})().catch(e => { console.error('СЦЕНАРИЙ УПАЛ:', e); process.exit(1); });
