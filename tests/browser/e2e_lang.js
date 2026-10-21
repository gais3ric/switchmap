// Смена языка интерфейса: меню профиля, окно «Настройки», язык журнала не меняет интерфейс.
// node e2e_lang.js <baseUrl> <shotsDir>
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
    await page.setViewport({ width: 1400, height: 900 });
    const jsErrors = [];
    page.on('pageerror', e => jsErrors.push(String(e.message || e)));
    page.on('console', m => { if (m.type() === 'error' && !String(m.location().url).includes('favicon')) jsErrors.push('console: ' + m.text()); });
    const lang = () => page.evaluate(() => document.documentElement.lang.split('-')[0]);
    const title = () => page.$eval('#settingsTitle', el => el.textContent.trim());
    const reloaded = () => page.waitForNavigation({ waitUntil: 'load', timeout: 15000 });

    try {
        await page.goto(base + '/login', { waitUntil: 'domcontentloaded' });
        await page.type('#username', 'admin'); await page.type('#password', 'adminpass123');
        await Promise.all([page.waitForNavigation({ waitUntil: 'load' }), page.click('button[type=submit]')]);
        check('по умолчанию — язык браузера (ru)', await lang() === 'ru', await lang());

        // ── Меню профиля
        await page.click('.rail-avatar'); await sleep(300);
        await Promise.all([reloaded(), page.select('#userLangSelect', 'en')]);
        check('меню профиля: English — страница на английском', await lang() === 'en' && await title() === 'Settings',
              [await lang(), await title()]);
        await page.goto(base + '/topology', { waitUntil: 'load' });
        check('язык сохраняется на других страницах', await lang() === 'en');

        // ── Окно «Настройки»
        await page.evaluate(() => openSettingsModal()); await sleep(500);
        check('в настройках выбран текущий язык интерфейса', await page.$eval('#settingsUiLang', el => el.value) === 'en');
        await page.select('#settingsUiLang', 'de');
        await Promise.all([reloaded(), page.click('#settingsModal .btn-primary')]);
        check('настройки: Deutsch — интерфейс сразу на немецком', await lang() === 'de' && await title() === 'Einstellungen',
              [await lang(), await title()]);
        await page.screenshot({ path: path.join(shots, 'lang_de.png') });

        // Язык журнала и уведомлений интерфейс не меняет
        await page.evaluate(() => openSettingsModal()); await sleep(500);
        await page.select('#serverLangInput', 'fr');
        await page.click('#settingsModal .btn-primary'); await sleep(800);
        check('язык журнала сохранён, интерфейс остался немецким', await lang() === 'de'
              && !(await page.$eval('#settingsModal', el => el.classList.contains('active'))));
        const s = await page.evaluate(() => fetch('/api/settings').then(r => r.json()));
        check('язык журнала — французский', s.server_language === 'fr', s.server_language);

        // Назад — «как в системе»
        await page.evaluate(() => openSettingsModal()); await sleep(500);
        await page.select('#settingsUiLang', '');
        await page.select('#serverLangInput', '');
        await Promise.all([reloaded(), page.click('#settingsModal .btn-primary')]);
        check('«как в системе» — снова язык браузера', await lang() === 'ru', await lang());

        // Страница входа: выбор языка до входа
        const page2 = await (await browser.createBrowserContext()).newPage();
        await page2.goto(base + '/login', { waitUntil: 'load' });
        const sel = await page2.$('select');
        if (sel) {
            const id = await page2.evaluate(el => el.id, sel);
            await Promise.all([page2.waitForNavigation({ waitUntil: 'load', timeout: 15000 }), page2.select('#' + id, 'zh')]);
        }
        check('страница входа: выбор языка работает', await page2.evaluate(() => document.documentElement.lang.startsWith('zh')),
              await page2.evaluate(() => document.documentElement.lang));
        // ── PDF: на китайском — шрифт с иероглифами, на русском — обычный Roboto
        const pdfFonts = async () => {
            await page.goto(base + '/switch/1', { waitUntil: 'load' }); await sleep(500);
            return page.evaluate(async () => {
                for (const [url, integrity] of PDFMAKE_SCRIPTS) await loadScript(url, integrity);
                const orig = pdfMake.createPdf;
                const pdf = await new Promise(resolve => {
                    pdfMake.createPdf = (...a) => { const d = orig.apply(pdfMake, a); d.download = () => d.getBase64(resolve); return d; };
                    exportToPDF();
                });
                const text = atob(pdf);
                return { size: text.length, noto: text.includes('NotoSansSC'), roboto: text.includes('Roboto'), pdf };
            });
        };
        await page.evaluate(() => fetch('/api/language', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"language":"zh"}' }));
        const zh = await pdfFonts();
        require('fs').writeFileSync(path.join(shots, 'export_zh.pdf'), Buffer.from(zh.pdf, 'base64'));
        check('PDF на китайском — шрифт Noto Sans SC с иероглифами', zh.noto && zh.size > 5000, { size: zh.size, noto: zh.noto });
        await page.evaluate(() => fetch('/api/language', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"language":"ru"}' }));
        const ru = await pdfFonts();
        check('PDF на русском — Roboto, без лишнего шрифта', ru.roboto && !ru.noto, { size: ru.size, roboto: ru.roboto });
        await page.evaluate(() => fetch('/api/language', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"language":""}' }));

        check('нет ошибок JS', jsErrors.length === 0, jsErrors);
    } catch (e) {
        console.log('СЦЕНАРИЙ УПАЛ: ' + (e.stack || e));
        results.push(false);
    }
    await browser.close();
    const failed = results.filter(r => !r).length;
    console.log(`\nИТОГО: ${failed ? 'провалено ' + failed : 'все проверки пройдены'} (${results.length} проверок)`);
    process.exit(failed ? 1 : 0);
})();
